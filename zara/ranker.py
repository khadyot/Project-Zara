import yaml
import os
import re
from datetime import datetime, timezone
import asyncio
from pydantic import BaseModel, Field
from typing import Literal
import sys

from zara.models import (
    Prospect, SourceResult, SignalCard, RankedCard, RankedProspect, PainMatch
)
from zara.utils.provider import generate_content_with_retry, ProviderProbeFailedError

def _parse_firmographic(snippet: str) -> dict:
    # simple parser if firmographic info is in snippet like "headcount: 120, sector: payments"
    res = {}
    hc_match = re.search(r'(?i)headcount:\s*([\d,]+)', snippet)
    if hc_match:
        res['headcount'] = int(hc_match.group(1).replace(',', ''))
    
    sec_match = re.search(r'(?i)(?:sector|industry):\s*([a-zA-Z0-9\s,-]+)', snippet)
    if sec_match:
        res['sector'] = sec_match.group(1).strip().lower()
    return res

def _compute_icp_fit(cards: list[SignalCard], value_prop: dict) -> tuple[Literal["fit", "unknown"], list[str]]:
    """Informational only — never rejects. Returns (verdict, deviations) where
    deviations are surfaced on the decision card, not used to gate anything."""
    icp = value_prop.get('icp', {})
    hc_pref_min = icp.get('headcount', {}).get('preferred_min', 50)
    hc_pref_max = icp.get('headcount', {}).get('preferred_max', 2000)

    headcount = None
    sector = None
    for c in cards:
        if c.signal_type == "firmographic":
            data = _parse_firmographic(c.snippet)
            if 'headcount' in data: headcount = data['headcount']
            if 'sector' in data: sector = data['sector']

    notes: list[str] = []
    if headcount is None:
        return "unknown", ["headcount unknown — could not verify"]

    if headcount < hc_pref_min or headcount > hc_pref_max:
        notes.append(f"headcount {headcount} — outside preferred {hc_pref_min}-{hc_pref_max} band")
    else:
        notes.append(f"headcount {headcount} — within preferred band")

    return "fit", notes

def _compute_proximity(card: SignalCard) -> Literal["authored", "attributed", "company_action", "database"]:
    if card.tier == "person":
        if card.signal_type == "social":
            return "authored"
        if card.signal_type == "profile":
            return "database"
        return "attributed"
    if card.signal_type == "firmographic":
        return "database"
    return "company_action"

def _compute_recency(published_date: str | None) -> int | None:
    if not published_date:
        return None
    try:
        dt = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0, (now - dt).days)
    except Exception:
        return None

class CardScoreOutput(BaseModel):
    index: int
    matched_pain_id: str | None
    score: float
    reason: str

class BatchScoreOutput(BaseModel):
    scores: list[CardScoreOutput]

async def rank_prospect(prospect: Prospect, results: list[SourceResult], strictness: str = "strict") -> RankedProspect:
    from zara.utils.config import load_value_prop
    vp = load_value_prop()
        
    never_reference = vp.get("never_reference", [])
    pains = vp.get("pains", [])
    
    all_cards = []
    for r in results:
        all_cards.extend(r.cards)
        
    icp_fit, icp_notes = _compute_icp_fit(all_cards, vp)
    
    ranked_cards_map = {}
    to_score = []
    
    for i, card in enumerate(all_cards):
        proximity = _compute_proximity(card)
        recency = _compute_recency(card.published_date)
        
        excluded = None
        guardrail_hit = None
        if card.eligibility in ("personal", "ambiguous", "unknown"):
            excluded = f"eligibility: {card.eligibility}"

        if not excluded:
            lower_text = f"{card.claim} {card.snippet}".lower()
            for nr in never_reference:
                nr_id = nr["id"]
                terms = nr["terms"]
                for t in terms:
                    pattern = r'\b' + re.escape(t.lower())
                    if re.search(pattern, lower_text):
                        if strictness == "permissive":
                            guardrail_hit = f"never_reference (soft): {nr_id}"
                        else:
                            excluded = f"never_reference: {nr_id}"
                        break
                if excluded or guardrail_hit:
                    break

        if not excluded:
            to_score.append((i, card))

        ranked_cards_map[i] = RankedCard(
            card=card,
            pain_match=None,
            proximity=proximity,
            recency_days=recency,
            score=0.0,
            excluded=excluded,
            guardrail_hit=guardrail_hit
        )
        
    if to_score:
        prox_val = vp.get("proximity_weights", {"authored": 4, "attributed": 3, "company_action": 2, "database": 1})
        to_score.sort(key=lambda item: (
            prox_val.get(_compute_proximity(item[1]), 0), 
            _compute_recency(item[1].published_date) is not None,
            -(_compute_recency(item[1].published_date) or 9999)
        ), reverse=True)
        
        # Hard cap to top 15 cards
        for i, card in to_score[15:]:
            rc = ranked_cards_map[i]
            ranked_cards_map[i] = RankedCard(
                card=rc.card, pain_match=None, proximity=rc.proximity,
                recency_days=rc.recency_days, score=0.0, excluded="hard cap limit exceeded",
                guardrail_hit=rc.guardrail_hit
            )
        to_score = to_score[:15]

        sys_prompt = "You are an expert sales ranker."
        if strictness == "permissive":
            sys_prompt += " You are allowed to use structural pattern recognition (e.g. inferring system evaluation windows from new executive appointments, debt/funding facilities, or M&A). You do not need explicit verbatim complaints to score a match. If the snippet has interesting company/person news but DOES NOT map to a specific pain point, map it to 'general_news' with a score of 0.4."
        else:
            sys_prompt += " You must be extremely strict. Only match if the snippet explicitly proves the 'observable_via' condition. Do not make inferential leaps. If the snippet has interesting company/person news but DOES NOT map to a specific pain point, you may map it to 'general_news' with a score of 0.3."
            
        chunk_size = 5
        try:
            for chunk_idx in range(0, len(to_score), chunk_size):
                chunk = to_score[chunk_idx:chunk_idx + chunk_size]
                
                prompt = "Score each card against the following pains (0.0 to 1.0) on how well its snippet matches the 'observable_via' condition. Output 'general_news' for matched_pain_id if it matches no pain but is interesting company/person news.\n\nPains:\n"
                for p in pains:
                    prompt += f"- ID: {p['id']}, Statement: {p['statement']}, Observable: {', '.join(p['observable_via'])}\n"
                    
                prompt += "\nCards:\n"
                for i, card in chunk:
                    prompt += f"[{i}] {card.snippet[:500]}\n\n"
                    
                resp = await generate_content_with_retry(
                    prompt=prompt,
                    schema=BatchScoreOutput,
                    system_instruction=sys_prompt
                )
                
                scores = resp.scores
                found_strong_hook = False
                for s in scores:
                    if s.index in ranked_cards_map:
                        rc = ranked_cards_map[s.index]
                        if s.matched_pain_id and s.score > 0:
                            pm = PainMatch(pain_id=s.matched_pain_id, score=s.score, reason=s.reason)
                            final_score = s.score
                            if rc.guardrail_hit:
                                final_score = round(s.score * 0.5, 4)
                            ranked_cards_map[s.index] = RankedCard(
                                card=rc.card, pain_match=pm, proximity=rc.proximity,
                                recency_days=rc.recency_days, score=final_score, excluded=None,
                                guardrail_hit=rc.guardrail_hit
                            )
                            if final_score >= 0.8:
                                found_strong_hook = True
                        else:
                            ranked_cards_map[s.index] = RankedCard(
                                card=rc.card, pain_match=None, proximity=rc.proximity,
                                recency_days=rc.recency_days, score=0.0, excluded="matches no pain in value_prop",
                                guardrail_hit=rc.guardrail_hit
                            )
                
                if found_strong_hook:
                    # Early exit: Mark the rest of the cards as skipped
                    for remain_idx in range(chunk_idx + chunk_size, len(to_score)):
                        i, _ = to_score[remain_idx]
                        rc = ranked_cards_map[i]
                        ranked_cards_map[i] = RankedCard(
                            card=rc.card, pain_match=None, proximity=rc.proximity,
                            recency_days=rc.recency_days, score=0.0, excluded="skipped due to early exit (strong hook found)",
                            guardrail_hit=rc.guardrail_hit
                        )
                    break
        except ProviderProbeFailedError as e:
            # Mark as unscored with reason
            for i, card in to_score:
                rc = ranked_cards_map[i]
                ranked_cards_map[i] = RankedCard(
                    card=rc.card, pain_match=None, proximity=rc.proximity,
                    recency_days=rc.recency_days, score=0.0, excluded=f"scoring unavailable ({str(e)})",
                    guardrail_hit=rc.guardrail_hit
                )
    
    final_cards = list(ranked_cards_map.values())
    
    # Compass VI swap test - remove duplicate hooks of same tier
    # Group eligible ones by tier, sort by proximity/score and exclude lowers
    eligible = [c for c in final_cards if c.excluded is None]
    
    # Sort eligible by proximity priority then score.
    prox_val = vp.get("proximity_weights", {"authored": 4, "attributed": 3, "company_action": 2, "database": 1})
    eligible.sort(key=lambda x: (prox_val.get(x.proximity, 0), x.score), reverse=True)
    
    seen_tiers = set()
    for c in eligible:
        if c.card.tier in seen_tiers:
            for i, fc in enumerate(final_cards):
                if fc is c:
                    final_cards[i] = RankedCard(
                        card=c.card, pain_match=c.pain_match, proximity=c.proximity,
                        recency_days=c.recency_days, score=c.score,
                        excluded="same hook kind as winner (Compass VI swap test)",
                        guardrail_hit=c.guardrail_hit
                    )
        else:
            seen_tiers.add(c.card.tier)
            
    # Winning card
    winning_card = None
    remaining_eligible = [c for c in final_cards if c.excluded is None]
    if remaining_eligible:
        remaining_eligible.sort(key=lambda x: (prox_val.get(x.proximity, 0), x.score), reverse=True)
        winning_card = remaining_eligible[0]

    hooks = await _articulate_hooks(prospect, remaining_eligible[:3], vp)

    return RankedProspect(
        prospect=prospect, cards=final_cards, icp_fit=icp_fit,
        winning_card=winning_card, hooks=hooks, icp_notes=icp_notes
    )


class HookOutput(BaseModel):
    card_index: int
    hook_text: str
    rationale: str
    bridge: str
    strength: float

class HooksOutput(BaseModel):
    hooks: list[HookOutput]


async def _articulate_hooks(prospect: Prospect, top_cards: list[RankedCard], vp: dict) -> list:
    from zara.models import HookProposal
    if not top_cards:
        return []

    offer = vp.get("product", "")
    prompt = (
        f"For each research card below about {prospect.person_name} (role: {prospect.title or 'unknown'}) "
        f"at {prospect.company}, write an outreach hook.\n\n"
        f"WHAT WE SELL: {offer}\n\n"
        f"CARDS (index, verbatim snippet):\n"
    )
    for idx, c in enumerate(top_cards):
        prompt += f"\n[{idx}] {c.card.snippet[:600]}\n"
    prompt += (
        "\nFor each card output: hook_text (one sentence stating the specific fact to lead with), "
        "rationale (why this matters to THIS person — tie it to their actual role when the role is known "
        "and related to the pain; if the role is unknown or unrelated, hook on the company-level fact and "
        "say so plainly in the rationale — never invent a role connection), "
        "bridge (how it connects to what we sell), "
        "strength (0.0-1.0 overall hook quality). Only use facts present in the snippets."
    )

    try:
        resp = await generate_content_with_retry(
            prompt=prompt,
            schema=HooksOutput,
            system_instruction="You are an expert B2B outreach strategist. Never invent facts."
        )
        hooks = []
        resp_hooks = getattr(resp, "hooks", None) or []
        for h in resp_hooks:
            if 0 <= h.card_index < len(top_cards):
                hooks.append(HookProposal(
                    card_index=h.card_index,
                    hook_text=h.hook_text,
                    rationale=h.rationale,
                    bridge=h.bridge,
                    strength=max(0.0, min(1.0, h.strength)),
                ))
        return hooks
    except Exception:
        return []
