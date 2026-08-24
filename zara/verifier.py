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
def build_evidence_list(prospect: RankedProspect, value_prop: dict, supporting_only: bool = True) -> list[str]:
    evidence = []
    if prospect.prospect.person_name:
        evidence.append(prospect.prospect.person_name)
    if prospect.prospect.company:
        evidence.append(prospect.prospect.company)
    if prospect.prospect.title:
        evidence.append(prospect.prospect.title)

    for k, v in value_prop.items():
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


def pass1_grounding(draft_text: str, prospect: RankedProspect, value_prop: dict) -> list[str]:
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
    evidence = build_evidence_list(prospect, value_prop)
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
    r"|just\s+(announced|launched|raised|closed|hired|appointed|published|posted|shipped|opened|acquired|named|rolled out))\b",
    re.I,
)

def check_recency(draft_text: str, prospect: RankedProspect) -> list[str]:
    """A time claim the evidence cannot carry."""
    win = prospect.winning_card
    if win is None or win.card.published_date is not None:
        return []
        
    m = _RECENCY_CLAIM.search(draft_text)
    if not m:
        return []
        
    return [
        f'unverifiable recency: draft says "{m.group(0)}" but the winning card carries no publication date'
    ]


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


async def verify_draft(draft_text: str, prospect: RankedProspect, value_prop: dict) -> VerificationResult:
    # Compass I: The no_signal note skips grounding extraction.
    # We identify it by checking if it's the no_signal note (winning_card is None implies no_signal note was used)
    # However, since verify_draft only takes draft_text, prospect, value_prop, we check winning_card
    if prospect.winning_card is None:
        sender_name = value_prop.get("sender_name", "Zamp")
        if sender_name not in draft_text:
            return VerificationResult(passed=False, status="blocked_hallucination", reason=f"Missing sender_name: {sender_name}")
        # Verify it doesn't invent anything by skipping pass 1, but we can just say it passed
        return VerificationResult(passed=True, status="clean", reason=None)
        
    ungrounded = check_attribution(draft_text, prospect) + check_recency(draft_text, prospect)
    ungrounded += pass1_grounding(draft_text, prospect, value_prop)
    if ungrounded:
        return VerificationResult(
            passed=False, 
            status="blocked_hallucination", 
            reason=f"Pass 1 Grounding failed on tokens: {', '.join(ungrounded)}",
            first_pass_hallucinations=ungrounded
        )
        
    # Pass 2
    return await pass2_llm_judge(draft_text, prospect, value_prop)
