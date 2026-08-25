import asyncio
import os
import sys
import yaml

from zara.models import Prospect, SourceResult, DraftResult, RankedCard
from zara.ranker import rank_prospect
from zara.drafter import draft_email, compute_claim_strength
from zara.verifier import verify_draft, check_format

def render_decision_card(draft_res: DraftResult, results: list[SourceResult]) -> str:
    md = []
    prospect = draft_res.ranked_prospect.prospect
    md.append(f"# {prospect.person_name} @ {prospect.company}")
    res_info = draft_res.ranked_prospect.resolution
    if res_info and res_info.input_company.strip() != res_info.resolved_company:
        md.append(f"Resolved company: '{res_info.input_company}' → '{res_info.resolved_company}' ({res_info.method}{', ' + res_info.domain if res_info.domain else ''})")
    
    sq = getattr(draft_res.ranked_prospect, "signal_quality", "ok")
    sq_str = f" · Signal: {sq}" if sq == "thin" else ""
    md.append(f"Claim strength: {draft_res.claim_strength}{sq_str}  ·  ICP: {draft_res.ranked_prospect.icp_fit}  ·  Cost: ${sum(r.cost_usd for r in results):.4f}")
    
    icp_notes = getattr(draft_res.ranked_prospect, "icp_notes", None)
    if icp_notes:
        md.append("")
        md.append("## Deviations (informational, never blocking)")
        for n in icp_notes:
            md.append(f"- {n}")
    md.append("")
    if draft_res.offer_is_generic:
        md.append("> NO PROSPECT-SPECIFIC SIGNAL FOUND. The opener is company-level and the")
        md.append("> offer is generic -- it is not tied to anything we retrieved about this")
        md.append("> person. Human judgment required before sending.")
        md.append("")
    md.append("## Draft")
    if draft_res.draft_text:
        if draft_res.subject:
            md.append(f"**Subject:** {draft_res.subject}")
            md.append("")
        md.append(draft_res.draft_text)
    else:
        md.append("*No draft generated.*")
    md.append("")
    
    md.append("## Hook chosen")
    win = draft_res.ranked_prospect.winning_card
    if win:
        md.append(f"{win.card.claim}  [{win.card.source_url}]")
        pain_id = win.pain_match.pain_id if win.pain_match else "none"
        score = win.score
        reason = win.pain_match.reason if win.pain_match else "no reason"
        md.append(f"Pain: {pain_id} (relevance {score:.2f}) — {reason}")
        md.append(f"Proximity: {win.proximity} · {win.recency_days or 'undated'} days old")
    else:
        md.append("*None*")
    md.append("")
    
    md.append("## Not chosen")
    not_chosen = [c for c in draft_res.ranked_prospect.cards if c is not win]
    if not not_chosen:
        md.append("*None*")
    for c in not_chosen:
        reason = c.excluded or 'eligible but outscored'
        if c.guardrail_hit:
            reason = f"{reason} · {c.guardrail_hit}"
        md.append(f"- {c.card.claim} — {reason}")
    md.append("")

    md.append("## Hook options")
    if draft_res.ranked_prospect.hooks:
        for i, h in enumerate(draft_res.ranked_prospect.hooks):
            md.append(f"{i+1}. [{h.strength:.2f}] {h.hook_text}")
            md.append(f"   _Why: {h.rationale}_")
            md.append(f"   _Bridge: {h.bridge}_")
    else:
        md.append("*None articulated.*")
    md.append("")
    
    md.append("## Retrieval")
    for r in sorted(results, key=lambda x: x.rung):
        marker = {"ok": "[+]", "failed": "[!]", "empty": "[ ]", "skipped": "[>]"}.get(r.status, "[?]")
        detail = f"{len(r.cards)} cards" if r.status == "ok" else (r.reason or "")
        md.append(f"{marker} {r.status:<8} {r.source:<25} {detail}")
    md.append("")
    
    md.append("## Verification")
    if draft_res.verification:
        md.append(f"Pass 1 grounding: {'clean' if draft_res.verification.status != 'could_not_run' and not draft_res.verification.first_pass_hallucinations else 'failed/hallucinated'}")
        if draft_res.verification.self_corrected:
            md.append("Self-corrected: true (first pass hallucinated)")
        md.append(f"Status: {draft_res.verification.status}")
        if draft_res.verification.reason:
            md.append(f"Reason: {draft_res.verification.reason}")
    else:
        md.append("*No verification run.*")
        
    return "\n".join(md)

async def process_prospect(prospect: Prospect, results: list[SourceResult], strictness: str = "strict", vp_override: dict = None, resolution=None, hook=None, style: str = "auto", on_event=None) -> DraftResult:
    if on_event:
        on_event({"type": "stage", "name": "ranking signals", "status": "running"})
    ranked_prospect = await rank_prospect(prospect, results, strictness=strictness)
    from dataclasses import replace as _replace
    if resolution is not None:
        ranked_prospect = _replace(ranked_prospect, resolution=resolution)
    claim_strength = compute_claim_strength(ranked_prospect.winning_card)
    offer_is_generic = ranked_prospect.winning_card is None
    if on_event:
        on_event({"type": "stage", "name": "ranking signals", "status": "done",
                  "detail": f"claim strength: {claim_strength}, hooks: {len(ranked_prospect.hooks)}"})
        for h in ranked_prospect.hooks:
            on_event({"type": "hook", "text": h.hook_text, "strength": h.strength})

    from zara.utils.config import load_value_prop
    vp = load_value_prop()
    if vp_override:
        vp = {**vp, **vp_override}

    # Task 5: Default hook to the hook whose card is winning_card
    if hook is None and ranked_prospect.winning_card and ranked_prospect.hooks:
        win_idx = next((i for i, c in enumerate(ranked_prospect.cards) if c is ranked_prospect.winning_card), None)
        if win_idx is not None:
            hook = next((h for h in ranked_prospect.hooks if h.card_index == win_idx), None)

    if on_event:
        on_event({"type": "stage", "name": "writing draft", "status": "running"})
    draft_output = await draft_email(ranked_prospect, vp, strictness=strictness, hook=hook, style=style)
    
    if not draft_output:
        return DraftResult(
            ranked_prospect=ranked_prospect,
            draft_text=None,
            subject=None,
            verification=None,
            claim_strength=claim_strength,
            offer_is_generic=offer_is_generic
        )
        
    draft_text = draft_output.draft_text
    subject = draft_output.subject
        
    fmt = check_format(draft_text)
    if fmt:
        retry = await draft_email(
            ranked_prospect, vp, strictness=strictness, hook=hook, style=style,
            feedback_tokens=[f"FORMAT (not a factual error): {n}" for n in fmt],
        )
        if retry and not check_format(retry.draft_text):
            draft_text = retry.draft_text
            subject = retry.subject

    if on_event:
        on_event({"type": "stage", "name": "verifying draft", "status": "running"})
    
    verify_text = f"{subject}\n\n{draft_text}" if subject else draft_text
    verification = await verify_draft(verify_text, ranked_prospect, vp, strictness=strictness)
    
    if on_event:
        on_event({"type": "stage", "name": "verifying draft", "status": "done",
                  "detail": verification.status})
    
    if verification.passed:
        return DraftResult(
            ranked_prospect=ranked_prospect,
            draft_text=draft_text,
            subject=subject,
            verification=verification,
            claim_strength=claim_strength,
            offer_is_generic=offer_is_generic
        )
        
    if verification.status == "blocked_hallucination" and verification.first_pass_hallucinations:
        draft_output_retry = await draft_email(ranked_prospect, vp, strictness=strictness, feedback_tokens=verification.first_pass_hallucinations, hook=hook, style=style)
        if draft_output_retry:
            draft_text_retry = draft_output_retry.draft_text
            subject_retry = draft_output_retry.subject
            verify_text_retry = f"{subject_retry}\n\n{draft_text_retry}" if subject_retry else draft_text_retry
            verification_retry = await verify_draft(verify_text_retry, ranked_prospect, vp, strictness=strictness)
            if verification_retry.passed:
                from dataclasses import replace
                verification_retry = replace(verification_retry, self_corrected=True)
                return DraftResult(
                    ranked_prospect=ranked_prospect,
                    draft_text=draft_text_retry,
                    subject=subject_retry,
                    verification=verification_retry,
                    claim_strength=claim_strength,
                    offer_is_generic=offer_is_generic
                )
            else:
                return DraftResult(
                    ranked_prospect=ranked_prospect,
                    draft_text=draft_text_retry,
                    subject=subject_retry,
                    verification=verification_retry,
                    claim_strength=claim_strength,
                    offer_is_generic=offer_is_generic
                )
                
    return DraftResult(
        ranked_prospect=ranked_prospect,
        draft_text=draft_text,
        subject=subject,
        verification=verification,
        claim_strength=claim_strength,
        offer_is_generic=offer_is_generic
    )

async def main():
    pass

if __name__ == "__main__":
    asyncio.run(main())
