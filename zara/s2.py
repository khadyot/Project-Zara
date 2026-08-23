import asyncio
import os
import sys
import yaml

from zara.models import Prospect, SourceResult, DraftResult, RankedCard
from zara.ranker import rank_prospect
from zara.drafter import draft_email, compute_claim_strength
from zara.verifier import verify_draft

def render_decision_card(draft_res: DraftResult, results: list[SourceResult]) -> str:
    md = []
    prospect = draft_res.ranked_prospect.prospect
    md.append(f"# {prospect.person_name} @ {prospect.company}")
    md.append(f"Claim strength: {draft_res.claim_strength}  ·  ICP: {draft_res.ranked_prospect.icp_fit}  ·  Cost: ${sum(r.cost_usd for r in results):.4f}")
    md.append("")
    md.append("## Draft")
    if draft_res.draft_text:
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
        md.append(f"Pain: {pain_id} ({score:.2f}) — {reason}")
        md.append(f"Proximity: {win.proximity} · {win.recency_days or 'undated'} days old")
    else:
        md.append("*None*")
    md.append("")
    
    md.append("## Not chosen")
    not_chosen = [c for c in draft_res.ranked_prospect.cards if c is not win]
    if not not_chosen:
        md.append("*None*")
    for c in not_chosen:
        md.append(f"- {c.card.claim} — {c.excluded or 'eligible but outscored'}")
    md.append("")
    
    md.append("## Retrieval")
    for r in sorted(results, key=lambda x: x.rung):
        marker = "✅" if r.status == "ok" else "❌" if r.status == "failed" else "⚪" if r.status == "empty" else "⏭️"
        # simple display of count or reason
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

async def process_prospect(prospect: Prospect, results: list[SourceResult]) -> DraftResult:
    # 1. Rank
    ranked_prospect = await rank_prospect(prospect, results)
    claim_strength = compute_claim_strength(ranked_prospect.winning_card)
    
    from zara.utils.config import load_value_prop
    vp = load_value_prop()
        
    # 2. Draft
    draft_text = await draft_email(ranked_prospect, vp)
    
    if not draft_text:
        return DraftResult(
            ranked_prospect=ranked_prospect,
            draft_text=None,
            verification=None,
            claim_strength=claim_strength
        )
        
    # 3. Verify
    verification = await verify_draft(draft_text, ranked_prospect, vp)
    
    if verification.passed:
        return DraftResult(
            ranked_prospect=ranked_prospect,
            draft_text=draft_text,
            verification=verification,
            claim_strength=claim_strength
        )
        
    # Retry on failure (blocked_hallucination)
    if verification.status == "blocked_hallucination" and verification.first_pass_hallucinations:
        draft_text_retry = await draft_email(ranked_prospect, vp, feedback_tokens=verification.first_pass_hallucinations)
        if draft_text_retry:
            verification_retry = await verify_draft(draft_text_retry, ranked_prospect, vp)
            if verification_retry.passed:
                # self corrected
                from dataclasses import replace
                verification_retry = replace(verification_retry, self_corrected=True)
                return DraftResult(
                    ranked_prospect=ranked_prospect,
                    draft_text=draft_text_retry,
                    verification=verification_retry,
                    claim_strength=claim_strength
                )
            else:
                return DraftResult(
                    ranked_prospect=ranked_prospect,
                    draft_text=f"ATTEMPT 1:\n{draft_text}\n\nATTEMPT 2:\n{draft_text_retry}",
                    verification=verification_retry,
                    claim_strength=claim_strength
                )
                
    return DraftResult(
        ranked_prospect=ranked_prospect,
        draft_text=draft_text,
        verification=verification,
        claim_strength=claim_strength
    )

async def main():
    # Helper to test one real prospect using fixtures or real.
    pass

if __name__ == "__main__":
    asyncio.run(main())
