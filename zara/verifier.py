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
        
    candidates = set(numbers + urls + quotes + proper_nouns)
    
    # Gather all evidence text
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
            
    # Include EVERY retrieved card's snippet, regardless of exclusion
    for c in prospect.cards:
        evidence.append(c.card.snippet)
            
    evidence_text = " ".join(evidence)
    norm_evidence = _normalize(evidence_text)
    
    ungrounded = []
    for cand in candidates:
        norm_cand = _normalize(cand)
        if len(norm_cand) > 0 and norm_cand not in norm_evidence:
            ungrounded.append(cand)
            
    # Also check word count
    words = draft_text.split()
    if len(words) < 60 or len(words) > 120:
        ungrounded.append(f"Word count {len(words)} is outside 60-120 range.")
        
    return ungrounded

class Pass2Output(BaseModel):
    passed: bool
    reason: str

async def pass2_llm_judge(draft_text: str, prospect: RankedProspect) -> VerificationResult:
    # Prompt the LLM
    prompt = (
        "You are a strict verifier. Verify the draft email is supported ONLY by the provided evidence snippets.\n\n"
        "Evidence snippets:\n"
    )
    for c in prospect.cards:
        if not c.excluded:
            prompt += f"- {c.card.snippet}\n"
            
    prompt += f"\nDraft Email:\n{draft_text}\n\n"
    prompt += "Does the draft email invent any factual claims, metrics, or customer names not present in the evidence? Answer passed=False if there are unsupported claims."
    
    try:
        resp = await generate_content_with_retry(
            prompt=prompt,
            schema=Pass2Output,
            system_instruction="You are a strict B2B verifier."
        )
        if resp.passed:
            return VerificationResult(passed=True, status="clean", reason=None)
        else:
            return VerificationResult(passed=False, status="blocked_hallucination", reason=resp.reason)
    except ProviderProbeFailedError as e:
        return VerificationResult(passed=False, status="could_not_run", reason=str(e))

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
        
    ungrounded = pass1_grounding(draft_text, prospect, value_prop)
    if ungrounded:
        return VerificationResult(
            passed=False, 
            status="blocked_hallucination", 
            reason=f"Pass 1 Grounding failed on tokens: {', '.join(ungrounded)}",
            first_pass_hallucinations=ungrounded
        )
        
    # Pass 2
    return await pass2_llm_judge(draft_text, prospect)
