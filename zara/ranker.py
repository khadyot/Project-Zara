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
    # A headcount of zero is a missing value wearing a number. Apify returned
    # employeeCount 0 for a company that plainly has employees, and the card then
    # read "headcount 0 -- outside preferred 50-2000 band" as though we had
    # measured it. Same failure as the budget meter in F7: absence rendered with
    # the confidence of a reading. Compass VII -- "couldn't look" is not "looked
    # and found none".
    if headcount is None or headcount <= 0:
        return "unknown", ["headcount unknown — could not verify"]

    if headcount < hc_pref_min or headcount > hc_pref_max:
        notes.append(f"headcount {headcount} — outside preferred {hc_pref_min}-{hc_pref_max} band")
    else:
        notes.append(f"headcount {headcount} — within preferred band")

    return "fit", notes

def _name_tokens(person_name: str) -> list[str]:
    """Surname plus any given name long enough not to collide with common words."""
    parts = [p.strip(".,") for p in (person_name or "").split() if len(p.strip(".,")) >= 3]
    return parts[-1:] + parts[:-1] if parts else []


def mentions_prospect(card: SignalCard, person_name: str) -> bool:
    """Is this card actually ABOUT the named person? Surname must appear in the
    claim, the title, or the body. Without this the ranker cannot tell the
    prospect speaking from a colleague speaking -- which is how a transcript of
    Versapay's CFO became 'person_authored' evidence about a different exec."""
    toks = _name_tokens(person_name)
    if not toks:
        return False
    hay = f"{card.claim} {card.snippet}".lower()
    surname = toks[0].lower()
    return re.search(r"\b" + re.escape(surname) + r"\b", hay) is not None


_ROLE_RE = re.compile(
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[,\-—|]\s*"
    r"((?:Chief[\w\s]*Officer|C[EFTOM]O|President|Founder|Co-?founder|"
    r"(?:VP|Vice President|Head|Director|Manager)(?:\s+of\s+[\w\s]+)?))",
    re.I,
)


def _extract_speaker(card: SignalCard) -> str | None:
    """Best-effort 'Name, Role' from the claim/title, so the drafter can say
    whose words these are instead of implying they are the recipient's."""
    m = _ROLE_RE.search(card.claim) or _ROLE_RE.search(card.snippet[:300])
    if m:
        return f"{m.group(1).strip()}, {m.group(2).strip()}"
    return None


def _compute_proximity(card: SignalCard, prospect: Prospect | None = None) -> Literal["authored", "colleague_authored", "attributed", "company_action", "database"]:
    person_name = prospect.person_name if prospect else ""
    if card.tier == "person":
        if card.signal_type == "social":
            # Authored means AUTHORED. If the prospect is not in the content, this
            # is somebody else at the company talking -- still real evidence, but
            # it is their voice, not the prospect's.
            if person_name and not mentions_prospect(card, person_name):
                return "colleague_authored"
            return "authored"
        if card.signal_type == "profile":
            return "database"
        if person_name and not mentions_prospect(card, person_name):
            return "company_action"
        return "attributed"
    if card.signal_type == "firmographic":
        return "database"
    return "company_action"

def _tiebreak(card: SignalCard) -> tuple[str, str]:
    """Stable, content-derived last resort for every sort in this module.

    Card order arrives from the orchestrator and every sort here is a stable
    `list.sort`, so ties would otherwise be resolved by arrival order. Keying on
    the card's own identity makes ties resolve the same way on every run.
    """
    return (card.source or "", card.source_url or "")


# The instant the fixture set was recorded, in UTC. Anything replaying those
# fixtures -- the test suite, the offline demo toggle -- must pin the clock here,
# or card ages drift off the recorded prompts and every fixture hash misses.
FIXTURE_CLOCK = "2026-08-25T21:00:00+00:00"


def _now() -> datetime:
    """Wall clock, overridable with ZARA_NOW (ISO 8601).

    Card age is not just a score input -- it is written verbatim into the drafter and
    hook prompts ("published N days ago"), and fixtures are keyed on the md5 of the
    prompt. So with a real clock every recorded fixture silently expires at the next
    midnight the age crosses, and the suite fails as an unexplained hash mismatch far
    from here. Pinning the clock in the test environment makes replay reproducible;
    production leaves ZARA_NOW unset and gets the real time.
    """
    pin = os.environ.get("ZARA_NOW")
    if pin:
        try:
            dt = datetime.fromisoformat(pin.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _compute_recency(published_date: str | None) -> int | None:
    if not published_date:
        return None
    try:
        dt = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
        return max(0, (_now() - dt).days)
    except Exception:
        return None


THIN_SIGNAL_FLOOR = 0.35


_COMPANY_NOISE = {"inc", "llc", "corp", "corporation", "ltd", "limited", "co",
                  "company", "group", "holdings", "technologies", "labs", "the"}


def _company_is_mentioned(card, prospect) -> bool:
    """Does this card actually talk about the company we were asked about?

    On the Stord run, cards about Stephanie Neill (Stripe) and Stephanie Stollar
    (PhD) entered the candidate pool as eligible and were merely outscored -- two
    different people who happen to share a first name with the prospect. Nothing
    checked that the employer appeared anywhere. With slightly different scores
    the draft would have been written from a stranger's biography.

    Deliberately permissive: any one significant token of the company name, found
    anywhere in the evidence we would actually use, is enough. A genuine post by
    the prospect that never names their employer is the case this must not kill,
    so a miss DOWNWEIGHTS rather than excludes (see the guardrail_hit path).
    """
    tokens = [t for t in re.split(r"[^a-z0-9]+", (prospect.company or "").lower())
              if len(t) >= 4 and t not in _COMPANY_NOISE]
    if not tokens:
        return True
    hay = f"{card.claim} {card.snippet[:500]} {card.source_url or ''}".lower()
    return any(t in hay for t in tokens)


def _compute_relevance(pain_score: float, proximity: str, recency_days: int | None, prox_val: dict) -> float:
    """Relevance is a PRODUCT, not a sort tuple.

    The old winner sort keyed on `(proximity_weight, pain_score, tiebreak)`. Tuple
    comparison is lexicographic, so proximity was the primary key and pain_score
    could only ever break its ties -- which is how a card scored 0.00 beat one
    scored 0.80 on the Modern Treasury seed run, and 0.30 beat 0.80 on ShipBob.
    Multiplying instead means a card with no pain match is unwinnable however
    proximate it is, which is the whole point.

    `proximity_weights` in value_prop.yaml stays the single source of truth; it is
    normalised here at runtime rather than duplicated, because the Settings UI can
    rewrite those weights and a hardcoded divisor would silently go stale.
    """
    max_prox = max(prox_val.values()) if prox_val else 1.0
    if max_prox == 0:
        max_prox = 1.0
    prox_mult = prox_val.get(proximity, 0) / max_prox

    # Gentle on purpose: an old card should lose ties, not be disqualified. The
    # honesty guard already forces the draft to name the period rather than call
    # a five-year-old podcast "recent".
    if recency_days is None:
        # Below every "known and younger than two years" tier on purpose. This sat
        # at 0.9 -- ABOVE the 0.85 and 0.75 given to cards whose age we actually
        # knew -- so not knowing a date scored better than knowing an inconvenient
        # one. That is how an undated "CFO Pros on the Move" listicle beat a dated
        # $250M funding round and produced "New finance chief" about someone three
        # and a half years into the job. Compass VII: absence is not evidence.
        rec_mult = 0.8
    elif recency_days <= 180:
        rec_mult = 1.0
    elif recency_days <= 365:
        rec_mult = 0.95
    elif recency_days <= 730:
        rec_mult = 0.85
    else:
        rec_mult = 0.75

    return pain_score * prox_mult * rec_mult


def _select_winner(final_cards: list[RankedCard], shortlist: list[RankedCard],
                   hooks: list) -> tuple[RankedCard | None, float | None, list]:
    """Pick the winner from the shortlist, after the hooks have been articulated.

    Returns `(winning_card, winning_score, surviving_hooks)`.

    TWO INDEX SPACES, and conflating them is a live bug this signature exists to
    prevent. `HookProposal.card_index` indexes into `shortlist` -- the relevance-
    sorted top-N handed to `_articulate_hooks`. It does NOT index into
    `final_cards`, which is in original card order. Map hook -> card through
    `shortlist` by identity, never by a shared integer.

    Hook strength modulates between 0.5x and 1.0x: it is a real signal but the
    least grounded of the three inputs, so it may reorder near-ties and must not
    dominate. When articulation failed entirely (`hooks == []`, which
    `_articulate_hooks` returns deliberately) selection falls back to raw
    relevance -- the run loses its options, not its winner.
    """
    if not shortlist:
        return None, None, []

    hook_for = {}
    for h in hooks:
        if 0 <= h.card_index < len(shortlist):
            hook_for[id(shortlist[h.card_index])] = h

    scored = []
    for c in shortlist:
        h = hook_for.get(id(c))
        final = c.score if not hooks else c.score * (0.5 + 0.5 * (h.strength if h else 0.0))
        scored.append((final, c, h))
    scored.sort(key=lambda x: (x[0], _tiebreak(x[1].card)), reverse=True)

    # Compass VI swap test: one hook per kind. Applied to the ARTICULATED set, so
    # the human still gets genuinely distinct options rather than two phrasings of
    # the same card.
    seen_tiers = set()
    seen_hooks = set()
    survivors = []
    for final, c, h in scored:
        # Two copies of the same story, retrieved by two sources and tiered
        # differently, both cleared the tier check and the reviewer was offered
        # the same sentence twice (options 1 and 3, character for character, on
        # the Finix run). Compass VI is "no two hooks of a kind", and identical
        # text is definitionally the same kind -- the tier is a proxy for that,
        # not the thing itself.
        _hook_key = re.sub(r"[^a-z0-9]+", " ", (h.hook_text or "").lower()).strip() if h else None
        if _hook_key and _hook_key in seen_hooks:
            for idx, fc in enumerate(final_cards):
                if fc is c:
                    final_cards[idx] = RankedCard(
                        card=c.card, pain_match=c.pain_match, proximity=c.proximity,
                        recency_days=c.recency_days, score=c.score,
                        excluded="duplicate hook text (Compass VI swap test)",
                        guardrail_hit=c.guardrail_hit, attributed_to=c.attributed_to,
                    )
                    break
            continue
        if c.card.tier in seen_tiers:
            for idx, fc in enumerate(final_cards):
                if fc is c:
                    final_cards[idx] = RankedCard(
                        card=c.card, pain_match=c.pain_match, proximity=c.proximity,
                        recency_days=c.recency_days, score=c.score,
                        excluded="same hook kind as winner (Compass VI swap test)",
                        guardrail_hit=c.guardrail_hit, attributed_to=c.attributed_to,
                    )
                    break
        else:
            seen_tiers.add(c.card.tier)
            if _hook_key:
                seen_hooks.add(_hook_key)
            survivors.append((final, c, h))

    if not survivors:
        return None, None, []

    # A near-tie breaks toward evidence we can date.
    #
    # A hook's job is to supply a reason to write NOW, and an undated card supplies
    # no now. On the Stord run an undated "CFO Pros on the Move" listicle beat a
    # dated $250M funding round 0.54 to 0.42 -- proximity `attributed` outweighs
    # `company_action` by more than the undated penalty removes, so weight tuning
    # alone will not reach this. The result was an opener built from a three-and-a-
    # half-year-old appointment instead of the biggest thing that happened to the
    # company this quarter.
    #
    # This is a preference, not a veto: an undated card that leads by a clear
    # margin still wins, because sometimes it really is the best thing we have.
    win_final, win_card, _ = survivors[0]
    if win_card.recency_days is None:
        from zara.utils.config import load_value_prop
        try:
            margin = float(load_value_prop().get("ranker", {}).get("dated_preference_margin", 0.15))
        except Exception:
            margin = 0.15
        dated = [(f, c, h) for f, c, h in survivors if c.recency_days is not None]
        if dated and dated[0][0] >= win_final - margin:
            win_final, win_card, _ = dated[0]
            survivors = [dated[0]] + [x for x in survivors if x is not dated[0]]
    surviving_hooks = [h for _, _, h in survivors if h is not None]
    return win_card, win_final, surviving_hooks


class CardScoreOutput(BaseModel):
    index: int
    matched_pain_id: str | None
    score: float
    reason: str = Field(description="At most 15 words. Name the observable that matched, or why none did. No restating the snippet.")

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
    
    prox_val = vp.get("proximity_weights", {"authored": 4, "attributed": 3, "colleague_authored": 2.5, "company_action": 2, "database": 1})
    
    for i, card in enumerate(all_cards):
        proximity = _compute_proximity(card, prospect)
        recency = _compute_recency(card.published_date)
        
        excluded = None
        guardrail_hit = None
        if card.eligibility in ("personal", "ambiguous", "unknown"):
            excluded = f"eligibility: {card.eligibility}"

        if not excluded:
            # Only the first 500 chars of the snippet are ever shown to the pain
            # scorer, the hook prompt or the drafter, so the guardrail scopes to
            # exactly what can reach a draft. Matching the full page body made a
            # $250M funding story fire `never_reference: litigation` on boilerplate
            # buried far below the evidence -- the guardrail eating the signal it
            # was never aimed at.
            lower_text = f"{card.claim} {card.snippet[:500]}".lower()
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

        # Person-tier proximity asserts "this is about our prospect". If the
        # employer is never mentioned, that assertion is unbacked -- downweight it
        # so a namesake cannot quietly win, and say so on the card.
        if not excluded and not guardrail_hit and proximity in ("authored", "attributed"):
            if not _company_is_mentioned(card, prospect):
                guardrail_hit = "possible namesake: company never mentioned in the evidence"

        if not excluded:
            to_score.append((i, card))

        ranked_cards_map[i] = RankedCard(
            card=card,
            pain_match=None,
            proximity=proximity,
            recency_days=recency,
            score=0.0,
            excluded=excluded,
            guardrail_hit=guardrail_hit,
            attributed_to=_extract_speaker(card) if proximity == "colleague_authored" else None,
        )
        
    if to_score:
        # Which cards are even ALLOWED to be scored used to be decided by a
        # lexicographic tuple keyed on proximity, so proximity was the primary key
        # and nothing else could overcome it -- the exact bug that was fixed for
        # winner selection and left standing here. On the Stord run that cut six
        # separate copies of a $250M funding round before pain matching ever saw
        # them, every one logged as "outside the top 10 by proximity".
        #
        # Same shape as _compute_relevance: a product, not a sort tuple. Pain score
        # is not known yet (scoring is what computes it), so the pre-score is the
        # part we can know -- proximity x recency.
        max_prox = max(prox_val.values()) if prox_val else 1.0
        if max_prox == 0:
            max_prox = 1.0

        def _pre_score(item):
            card = item[1]
            prox = _compute_proximity(card, prospect)
            rec = _compute_recency(card.published_date)
            prox_mult = prox_val.get(prox, 0) / max_prox
            if rec is None:
                rec_mult = 0.8
            elif rec <= 180:
                rec_mult = 1.0
            elif rec <= 365:
                rec_mult = 0.95
            elif rec <= 730:
                rec_mult = 0.85
            else:
                rec_mult = 0.75
            return prox_mult * rec_mult

        to_score.sort(key=lambda item: (_pre_score(item), _tiebreak(item[1])), reverse=True)

        card_cap = int(vp.get("ranker", {}).get("card_cap", 10))

        # Reserve slots for the freshest DATED cards regardless of proximity.
        # A blended pre-score still lets a whole proximity tier crowd out the
        # newest thing that happened to this company, and "we never looked at the
        # biggest news of the quarter" is not a defensible way to lose a hook.
        # The cap is unchanged, so this costs no extra tokens.
        reserve = int(vp.get("ranker", {}).get("recency_reserve", 3))
        if reserve > 0 and len(to_score) > card_cap:
            head = to_score[:max(0, card_cap - reserve)]
            chosen = {id(item) for item in head}
            dated = [it for it in to_score
                     if id(it) not in chosen and _compute_recency(it[1].published_date) is not None]
            dated.sort(key=lambda it: (_compute_recency(it[1].published_date), _tiebreak(it[1])))
            promoted = dated[:reserve]
            picked = {id(it) for it in head} | {id(it) for it in promoted}
            remainder = [it for it in to_score if id(it) not in picked]
            to_score = head + promoted + remainder
        for i, card in to_score[card_cap:]:
            rc = ranked_cards_map[i]
            ranked_cards_map[i] = RankedCard(
                card=rc.card, pain_match=None, proximity=rc.proximity,
                recency_days=rc.recency_days, score=0.0, excluded=f"outside the top {card_cap} by relevance (hard cap)",
                guardrail_hit=rc.guardrail_hit, attributed_to=rc.attributed_to
            )
        to_score = to_score[:card_cap]

        sys_prompt = "You are an expert sales ranker."
        if strictness == "permissive":
            sys_prompt += " You are allowed to use structural pattern recognition (e.g. inferring system evaluation windows from new executive appointments, debt/funding facilities, or M&A). You do not need explicit verbatim complaints to score a match. If the snippet has interesting company/person news but DOES NOT map to a specific pain point, map it to 'general_news' with a score of 0.4."
        else:
            sys_prompt += " You must be extremely strict. Only match if the snippet explicitly proves the 'observable_via' condition. Do not make inferential leaps. If the snippet has interesting company/person news but DOES NOT map to a specific pain point, you may map it to 'general_news' with a score of 0.3."
            
        chunk_size = max(len(to_score), 1)
        try:
            for chunk_idx in range(0, len(to_score), chunk_size):
                chunk = to_score[chunk_idx:chunk_idx + chunk_size]
                
                prompt = ("Score each card against the following pains (0.0 to 1.0) on how well its snippet matches the 'observable_via' condition. "
                          "Output 'general_news' for matched_pain_id if it matches no pain but is interesting company/person news. "
                          "Keep each reason to at most 15 words: name the observable that matched, or why none did.\n\nPains:\n")
                for p in pains:
                    prompt += f"- ID: {p['id']}, Statement: {p['statement']}, Observable: {', '.join(p['observable_via'])}\n"
                    
                prompt += "\nCards:\n"
                for i, card in chunk:
                    prompt += f"[{i}] {card.snippet[:500]}\n\n"
                    
                resp = await generate_content_with_retry(
                    prompt=prompt,
                    schema=BatchScoreOutput,
                    system_instruction=sys_prompt,
                    stage="ranker_pain_scoring",
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
                                
                            relevance = _compute_relevance(final_score, rc.proximity, rc.recency_days, prox_val)
                            ranked_cards_map[s.index] = RankedCard(
                                card=rc.card, pain_match=pm, proximity=rc.proximity,
                                recency_days=rc.recency_days, score=relevance, excluded=None,
                                guardrail_hit=rc.guardrail_hit, attributed_to=rc.attributed_to
                            )
                            if final_score >= 0.8:
                                found_strong_hook = True
                        else:
                            # B2: pain_match is None must contribute pain_score 0.0, as it already does.
                            relevance = _compute_relevance(0.0, rc.proximity, rc.recency_days, prox_val)
                            ranked_cards_map[s.index] = RankedCard(
                                card=rc.card, pain_match=None, proximity=rc.proximity,
                                recency_days=rc.recency_days, score=relevance, excluded="matches no pain in value_prop",
                                guardrail_hit=rc.guardrail_hit, attributed_to=rc.attributed_to
                            )
                
                if found_strong_hook:
                    for remain_idx in range(chunk_idx + chunk_size, len(to_score)):
                        i, _ = to_score[remain_idx]
                        rc = ranked_cards_map[i]
                        ranked_cards_map[i] = RankedCard(
                            card=rc.card, pain_match=None, proximity=rc.proximity,
                            recency_days=rc.recency_days, score=0.0, excluded="skipped due to early exit (strong hook found)",
                            guardrail_hit=rc.guardrail_hit, attributed_to=rc.attributed_to
                        )
                    break
        except ProviderProbeFailedError as e:
            for i, card in to_score:
                rc = ranked_cards_map[i]
                ranked_cards_map[i] = RankedCard(
                    card=rc.card, pain_match=None, proximity=rc.proximity,
                    recency_days=rc.recency_days, score=0.0, excluded=f"scoring unavailable ({str(e)})",
                    guardrail_hit=rc.guardrail_hit, attributed_to=rc.attributed_to
                )
    
    final_cards = list(ranked_cards_map.values())
    
    # Hooks are articulated BEFORE the winner is chosen, so the model's own read on
    # hook quality gets a vote. Previously this call ran after selection and its
    # output never reached the draft at all -- a paid call, discarded every run.
    #
    # No tier dedup yet: the swap test used to run first and, because `tier` only
    # has two values, collapsed the candidate set to two before the hook call ever
    # saw it. Every run produced exactly two hooks. Dedup now happens inside
    # _select_winner, on the articulated set.
    eligible = [c for c in final_cards if c.excluded is None]
    eligible.sort(key=lambda x: (x.score, _tiebreak(x.card)), reverse=True)
    shortlist = eligible[:int(vp.get("ranker", {}).get("hook_shortlist", 4))]

    hooks = await _articulate_hooks(prospect, shortlist, vp)

    winning_card, winning_score, final_hooks = _select_winner(final_cards, shortlist, hooks)

    # Compass I: degrade, but never silently. Both repaired seed runs land at ~0.30
    # -- the pick is right and the evidence is still thin, and the reviewer is told
    # so on the output's face rather than having to open the audit trail.
    signal_quality = "thin" if winning_score is not None and winning_score < THIN_SIGNAL_FLOOR else "ok"

    return RankedProspect(
        prospect=prospect, cards=final_cards, icp_fit=icp_fit,
        winning_card=winning_card, winning_score=winning_score, signal_quality=signal_quality,
        hooks=final_hooks, icp_notes=icp_notes
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
        age = (f"published {c.recency_days} days ago" if c.recency_days is not None
               else "publication date unknown")
        prompt += f"\n[{idx}] ({age}) {c.card.snippet[:450]}\n"
    prompt += (
        "\nFor each card output: hook_text (one sentence stating the specific fact to lead with), "
        "rationale (why this matters to THIS person — tie it to their actual role when the role is known "
        "and related to the pain; if the role is unknown or unrelated, hook on the company-level fact and "
        "say so plainly in the rationale — never invent a role connection), "
        "bridge (how it connects to what we sell), "
        "strength (0.0-1.0 overall hook quality). Only use facts present in the snippets. "
        "TIMEFRAME: each card states its age. Be honest about it. Never call something recent, "
        "new, or 'just' anything unless it is under six months old. For older material name the "
        "period instead ('in your 2021 conversation'), and if the date is unknown make no time "
        "claim at all."
    )

    try:
        resp = await generate_content_with_retry(
            prompt=prompt,
            schema=HooksOutput,
            system_instruction="You are an expert B2B outreach strategist. Never invent facts.",
            stage="ranker_hooks",
        )
        hooks = []
        resp_hooks = getattr(resp, "hooks", None) or []
        for h in resp_hooks:
            if 0 <= h.card_index < len(top_cards):
                _src = top_cards[h.card_index]
                hooks.append(HookProposal(
                    card_index=h.card_index,
                    hook_text=h.hook_text,
                    rationale=h.rationale,
                    bridge=h.bridge,
                    strength=max(0.0, min(1.0, h.strength)),
                    recency_days=_src.recency_days if _src else None,
                ))
        return hooks
    except Exception as e:
        import sys
        print(f"WARNING: hook articulation failed, no options offered: "
              f"{type(e).__name__}: {e}", file=sys.stderr)
        return []
