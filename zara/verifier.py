import os
import sys
import re
import asyncio
from typing import Literal
from pydantic import BaseModel
from zara.models import RankedProspect, DraftResult, VerificationResult
from zara.utils.provider import generate_content_with_retry, ProviderProbeFailedError

def _normalize(text: str) -> str:
    # casefold, strip punctuation and possessives, collapse whitespace
    text = text.casefold()
    text = re.sub(r"'s\b", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# The draft can only be grounded in what the drafter was actually shown: the
# winning card's snippet, plus the prospect and offer facts. Sending every card
# -- including ones the ranker excluded for never_reference or eligibility --
# both bloats the payload (measured 18-22k chars, ~73% of a prospect's whole
# token spend against an 8K TPM ceiling) and lets a vetoed layoff snippet act as
# valid grounding, which is a Compass X hole in the final gate.
def build_evidence_list(prospect: RankedProspect, value_prop: dict, supporting_only: bool = True,
                       strictness: str = "strict") -> list[str]:
    evidence = []
    if prospect.prospect.person_name:
        evidence.append(prospect.prospect.person_name)
    if prospect.prospect.company:
        evidence.append(prospect.prospect.company)
    if prospect.prospect.title:
        evidence.append(prospect.prospect.title)

    for k, v in value_prop.items():
        # `proof_point` carries a hard number ("30-40%"). In strict mode the
        # drafter is explicitly forbidden to use it, so admitting it as evidence
        # licenses the exact claim we told the model not to make: grounding is a
        # substring test, so an invented "30% cut in processing time" matched the
        # "30-40%" in a proof point that was never allowed into the draft.
        # You cannot ground against something you are forbidden to say.
        if k == "proof_point" and strictness != "permissive":
            continue
        if isinstance(v, str):
            evidence.append(v)

    # `pains` is a list of dicts, so the isinstance(str) loop above silently
    # skipped it and the verifier never saw what we sell against. The drafter is
    # instructed to state the matched pain as the middle term of the syllogism;
    # without this the judge blocks our own value proposition as a fabrication.
    # (Caught on the Versapay stress run: "intercompany reconciliation sprawl" is
    # verbatim from structural_complexity's statement.)
    for pain in value_prop.get("pains", []) or []:
        if isinstance(pain, dict) and pain.get("statement"):
            evidence.append(pain["statement"])

    if supporting_only:
        cards = [c for c in prospect.cards if c.excluded is None]
        if prospect.winning_card is not None and prospect.winning_card not in cards:
            cards.append(prospect.winning_card)
    else:
        cards = list(prospect.cards)

    for c in cards:
        evidence.append(c.card.snippet)

    return evidence

WORD_MIN, WORD_MAX = 60, 120


def check_format(draft_text: str) -> list[str]:
    """Format problems. Ruling #6: these are rewritten, never reported as
    fabrication and never used to block."""
    notes = []
    n = len(draft_text.split())
    if n < WORD_MIN or n > WORD_MAX:
        notes.append(f"word count {n} outside {WORD_MIN}-{WORD_MAX}")
    return notes


def pass1_grounding(draft_text: str, prospect: RankedProspect, value_prop: dict,
                    strictness: str = "strict") -> list[str]:
    # Extract numbers, dates, quoted strings, URLs, and multi-word proper nouns
    # For a simple deterministic pass, we'll extract tokens that look like these.
    
    # 1. Numbers (including $1.2M, 1,000, etc)
    numbers = re.findall(r'\b\$?\d+(?:[.,]\d+)*(?:[a-zA-Z]+)?\b', draft_text)
    
    # 2. URLs
    urls = re.findall(r'https?://[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', draft_text)
    
    # 3. Quoted strings (simple heuristic)
    quotes = re.findall(r'"([^"]*)"', draft_text)
    
    # 4. Multi-word proper nouns (Title Case words in sequence)
    proper_nouns = []
    for match in re.finditer(r'\b([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', draft_text):
        pn = match.group(1)
        pn = re.sub(r'^(?:Hi|Hello|Dear|Best|Regards|Thanks|Sincerely|Zamp)\s+', '', pn)
        if ' ' in pn:
            proper_nouns.append(pn)
        
    # sorted, not set: set iteration order varies with PYTHONHASHSEED across
    # processes, which reordered `ungrounded` and so changed the drafter's
    # self-correction prompt between otherwise identical runs.
    candidates = sorted(set(numbers + urls + quotes + proper_nouns))
    
    # Gather all evidence text
    evidence = build_evidence_list(prospect, value_prop, strictness=strictness)
    evidence_text = " ".join(evidence)
    norm_evidence = _normalize(evidence_text)
    
    ungrounded = []
    for cand in candidates:
        norm_cand = _normalize(cand)
        if len(norm_cand) > 0 and norm_cand not in norm_evidence:
            ungrounded.append(cand)
            
    return ungrounded

class Pass2Output(BaseModel):
    passed: bool
    reason: str

async def pass2_llm_judge(draft_text: str, prospect: RankedProspect, value_prop: dict) -> VerificationResult:
    # Prompt the LLM
    prompt = (
        "You are a strict verifier checking one thing: does the draft invent FACTS "
        "ABOUT THE PROSPECT OR THEIR COMPANY that the evidence does not support?\n\n"
        "Two things are NOT fabrication and must not be flagged:\n"
        "  1. The sender's value proposition and the pain they sell against. These are "
        "the sender's own general claims about how companies like this tend to operate. "
        "They appear in the evidence list and may be stated as inference or hypothesis "
        "('many fast-scaling companies see X'), which is exactly what a sales email does.\n"
        "  2. Ordinary connective language, framing, and the call to action.\n\n"
        "Flag ONLY: invented metrics, invented customer names, fabricated quotes, or "
        "specific claims about this prospect or company that no snippet supports.\n\n"
        "Evidence snippets:\n"
    )
    evidence = build_evidence_list(prospect, value_prop)
    for ev in evidence:
        prompt += f"- {ev}\n"
            
    prompt += f"\nDraft Email:\n{draft_text}\n\n"
    prompt += "Does the draft email invent any factual claims, metrics, or customer names not present in the evidence? Answer passed=False if there are unsupported claims."
    
    try:
        resp = await generate_content_with_retry(
            prompt=prompt,
            schema=Pass2Output,
            system_instruction="You are a strict B2B verifier.",
            stage="verifier_judge",
        )
        if resp.passed:
            return VerificationResult(passed=True, status="clean", reason=None)
        else:
            return VerificationResult(passed=False, status="blocked_hallucination", reason=resp.reason)
    except ProviderProbeFailedError as e:
        return VerificationResult(passed=False, status="could_not_run", reason=str(e))

# Second-person phrasing that claims the recipient personally said or did the thing.
_SECOND_PERSON_CLAIM = re.compile(
    r"\b(?:i\s+(?:saw|read|noticed|caught|heard)\s+(?:that\s+)?you\b"
    r"|you\s+(?:said|wrote|posted|shared|mentioned|described|talked about|spoke about)\b"
    r"|your\s+(?:view|take|point|comment|post|remark)s?\b"
    r"|you\s+take\s+a\b)",
    re.I,
)

_RECENCY_CLAIM = re.compile(
    r"\b(recent(ly)?|newly|this (week|month)|days ago|latest"
    r"|just\s+(announced|launched|raised|closed|hired|appointed|published|posted|shipped|opened|acquired|named|rolled out)"
    # "New finance chief" is a time claim wearing an adjective. The pattern had
    # "newly" but not bare "new", so a draft calling someone appointed in
    # February 2023 the "new finance chief" passed clean -- from an UNDATED
    # listicle, which is the case this guard exists for. Scoped to role nouns so
    # "a new ledger" or "new payment methods" stay unaffected.
    r"|new\s+(finance\s+|interim\s+)?(chief|cfo|ceo|coo|cto|cio|vp|head|president|leader|hire|appointment|role|seat)"
    r"|incoming\s+(chief|cfo|ceo|coo|cto|cio|vp|head|president)"
    r"|(has\s+)?just\s+joined|steps?\s+into\s+the\s+role|takes?\s+over\s+as)\b",
    re.I,
)

# Beyond this, "recently" is a false claim rather than a vague one. Data, not a
# buried constant, so it can be argued with -- same treatment as never_reference
# and proximity_weights.
STALE_DAYS = 180


def _stale_days(value_prop: dict | None = None) -> int:
    if not value_prop:
        from zara.utils.config import load_value_prop
        try:
            value_prop = load_value_prop()
        except Exception:
            return STALE_DAYS
    try:
        return int(value_prop.get("guardrails", {}).get("stale_days", STALE_DAYS))
    except (TypeError, ValueError, AttributeError):
        return STALE_DAYS


def check_recency(draft_text: str, prospect: RankedProspect, value_prop: dict | None = None) -> list[str]:
    """A time claim the evidence cannot carry.

    Two ways it cannot carry it, and the original only guarded the first:

      no date  -- nothing to check the claim against (F5, fixed earlier).
      old date -- there IS a date and it is years past, which the early return
                  `published_date is not None` treated as fully satisfying the
                  claim. That shipped "You recently discussed..." about a card
                  1,826 days old, on the deployed app, on the flagship demo.
    """
    win = prospect.winning_card
    if win is None:
        return []

    m = _RECENCY_CLAIM.search(draft_text)
    if not m:
        return []

    if win.card.published_date is None:
        return [
            f'unverifiable recency: draft says "{m.group(0)}" but the winning card carries no publication date'
        ]

    limit = _stale_days(value_prop)
    age = win.recency_days
    if age is not None and age > limit:
        years = age / 365.25
        readable = f"{years:.1f} years" if age >= 365 else f"{age} days"
        return [
            f'false recency: draft says "{m.group(0)}" but the winning card is {age} days old '
            f'({readable}). State the period instead, or drop the time claim.'
        ]

    return []


def check_attribution(draft_text: str, prospect: RankedProspect) -> list[str]:
    """Blocks the failure that passed clean on the Versapay run: the winning card
    was a transcript of a DIFFERENT executive, and the draft opened "I saw you
    take a funnel-oriented view...". Token grounding cannot catch this -- the
    draft never names the real speaker, so no ungrounded token exists."""
    win = prospect.winning_card
    if win is None or win.proximity == "authored":
        return []
    m = _SECOND_PERSON_CLAIM.search(draft_text)
    if not m:
        return []
    whose = win.attributed_to or ("company-level material" if win.proximity in ("company_action", "database")
                                  else "someone other than the recipient")
    return [
        f'misattribution: draft says "{m.group(0)}" as if {prospect.prospect.person_name} '
        f"said or did it, but the evidence is {whose} (proximity={win.proximity})"
    ]


async def verify_draft(draft_text: str, prospect: RankedProspect, value_prop: dict,
                       strictness: str = "strict") -> VerificationResult:
    # Compass I: The no_signal note skips grounding extraction.
    # We identify it by checking if it's the no_signal note (winning_card is None implies no_signal note was used)
    # However, since verify_draft only takes draft_text, prospect, value_prop, we check winning_card
    if prospect.winning_card is None:
        sender_name = value_prop.get("sender_name", "Zamp")
        if sender_name not in draft_text:
            return VerificationResult(passed=False, status="blocked_hallucination", reason=f"Missing sender_name: {sender_name}")
        # This used to `return passed=True` here, skipping verification entirely.
        # That inverted the whole gate: the draft with the STRONGEST evidence got
        # the strictest checking, and the draft with NO evidence got none at all --
        # on exactly the path where the model has nothing to work from and is
        # therefore most likely to invent. It shipped a fabricated "30% cut in
        # processing time" in strict mode.
        #
        # Grounding still applies, and applies cleanly: with no cards the evidence
        # list is the prospect, the offer, and the pain statements, so ordinary
        # framing passes while an invented number, URL, quote, or proper noun does
        # not. Falls through to the same path as every other draft.
        pass

    ungrounded = check_attribution(draft_text, prospect) + check_recency(draft_text, prospect, value_prop)
    ungrounded += pass1_grounding(draft_text, prospect, value_prop, strictness=strictness)
    if ungrounded:
        return VerificationResult(
            passed=False, 
            status="blocked_hallucination", 
            reason=f"Pass 1 Grounding failed on tokens: {', '.join(ungrounded)}",
            first_pass_hallucinations=ungrounded
        )
        
    # Pass 2
    return await pass2_llm_judge(draft_text, prospect, value_prop)
