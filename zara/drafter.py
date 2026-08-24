import os
import sys
import asyncio
from typing import Literal
from pydantic import BaseModel
from zara.models import RankedProspect, RankedCard, DraftResult, VerificationResult
from zara.utils.provider import generate_content_with_retry, ProviderProbeFailedError

class DraftOutput(BaseModel):
    draft_text: str

def compute_claim_strength(winning_card: RankedCard | None) -> Literal["person_authored", "person_attributed", "colleague_authored", "company_action", "database_only", "no_signal"]:
    if not winning_card:
        return "no_signal"
    if winning_card.proximity == "database":
        return "database_only"
    if winning_card.proximity == "company_action":
        return "company_action"
    if winning_card.proximity == "authored":
        return "person_authored"
    if winning_card.proximity == "colleague_authored":
        return "colleague_authored"
    if winning_card.proximity == "attributed":
        # ranker.py assigns "attributed" to every person-tier card that is not
        # social or profile -- i.e. every person_mention, the most common person
        # card there is. Without this branch it fell through to "no_signal", so a
        # found, ranked, drafted person hook reported "no signal" on its face.
        return "person_attributed"
    return "no_signal"

async def draft_email(ranked_prospect: RankedProspect, value_prop: dict, strictness: str = "strict", feedback_tokens: list[str] = None, hook: object = None, style: str = "auto") -> str | None:
    winning_card = ranked_prospect.winning_card
    sender_name = value_prop.get("sender_name", "Zamp")
    offer = value_prop.get("product", "")

    if not winning_card:
        # FALLBACK: Draft a generic company-level email using the LLM
        fallback_prompt = (
            f"Draft a generic 60-120 word B2B sales email to {ranked_prospect.prospect.person_name} "
            f"at their company, {ranked_prospect.prospect.company}.\n"
            f"Since we couldn't find a specific personal hook, frame the email around the general value we provide "
            f"to companies in their space.\n\n"
            f"WHAT WE SELL: {offer}\n"
            f"Constraints:\n"
            f"- Sign exactly as: {sender_name}\n"
            f"- Do NOT invent a human signer or job title.\n"
            f"- Do NOT invent specific company news (like funding or leadership changes) since none was verified.\n"
        )
        if style and style != "auto":
            fallback_prompt += f"- Email opening style: {style}.\n"
            
        fallback_system = "You are an expert B2B SDR drafting concise, generic outreach emails."
        try:
            resp = await generate_content_with_retry(
                prompt=fallback_prompt,
                schema=DraftOutput,
                system_instruction=fallback_system,
                stage="drafter_no_signal",
            )
            return resp.draft_text
        except ProviderProbeFailedError as e:
            print(f"WARNING: Drafter fallback model failed: {e}", file=sys.stderr)
            return f"Hi {ranked_prospect.prospect.person_name},\n\nI looked across the web, your LinkedIn, and news sources to find what you're focusing on right now, but couldn't find a strong signal. If you're open to it, I'd love to learn what's top of mind for you. {offer}. Let me know if you're open to a chat.\n\nBest,\n{sender_name}"

    pain_statement = ""
    if winning_card.pain_match and winning_card.pain_match.pain_id == "general_news":
        pain_statement = "We don't know their specific pain yet, but we want to start a conversation about how we help companies in their space."
    else:
        for p in value_prop.get("pains", []):
            if p["id"] == winning_card.pain_match.pain_id:
                pain_statement = p["statement"]
                break

    prompt = (
        f"Draft a 60-120 word email to {ranked_prospect.prospect.person_name} at {ranked_prospect.prospect.company}.\n"
        f"Use this EXACT syllogism logic:\n"
        f"1. Hook: based ONLY on this snippet: '{winning_card.card.snippet}'\n"
    )

    # Whose words are these? Getting this wrong produces a confident fabrication
    # that reads as deep personalisation, which is the worst output this system
    # can emit. State it explicitly rather than letting the model assume.
    if winning_card.proximity == "colleague_authored":
        speaker = winning_card.attributed_to or f"a colleague at {ranked_prospect.prospect.company}"
        prompt += (
            f"   ATTRIBUTION -- CRITICAL: the snippet is NOT the recipient speaking. "
            f"It is {speaker}. You MUST attribute it to them explicitly "
            f"(for example: \"your {speaker.split(',')[-1].strip()} said ...\"). "
            f"NEVER write \"you said\", \"I saw you\", \"your view that\", or any second-person "
            f"phrasing that implies {ranked_prospect.prospect.person_name} said or wrote this.\n"
        )
    elif winning_card.proximity in ("company_action", "database"):
        prompt += (
            f"   ATTRIBUTION: this is a company-level fact, not something "
            f"{ranked_prospect.prospect.person_name} personally said or did. Reference it as "
            f"company news. Never imply they authored or said it.\n"
        )
    if hook is not None:
        prompt += (
            f"   Lead with this hook (its facts must match the snippet): {hook.hook_text}\n"
            f"   Why it matters to them: {hook.rationale}\n"
            f"   Bridge to the offer: {hook.bridge}\n"
        )
    prompt += (
        f"2. Pain: {pain_statement}\n"
        f"3. Offer: {offer}\n\n"
        f"Constraints:\n"
        f"- Sign exactly as: {sender_name}\n"
        f"- Do NOT invent a human signer or job title.\n"
        f"- Quote or compress the snippet, but never embellish.\n"
    )
    if style and style != "auto":
        prompt += f"- Email opening style: {style}.\n"
    
    if strictness == "strict":
        prompt += "- Do NOT invent proof points or customer metrics.\n"
    elif strictness == "permissive":
        pp = value_prop.get("proof_point")
        if pp:
            prompt += f"- You may use this proof point: {pp}\n"
        else:
            prompt += "- Do NOT invent proof points or customer metrics.\n"
    
    if feedback_tokens:
        prompt += "\nREVISE. Fix each issue below. Items prefixed FORMAT are style problems, not factual errors; everything else is an unsupported claim that must be removed or replaced with a grounded fact:\n"
        prompt += "\n".join(feedback_tokens)
    
    prompt += f"Product/Offer: {value_prop.get('product', '')}\n"
    prompt += f"Signer: {sender_name}\n"
    
    system_instruction = (
        "You are an expert B2B SDR drafting emails based on syllogisms. "
        "State the middle term (the pain point) as an inference in your own plain words. "
        "Do NOT quote the raw snippet as a block. "
        "Do NOT recite the exact pain statement verbatim from the instructions."
    )
        
    try:
        resp = await generate_content_with_retry(
            prompt=prompt,
            schema=DraftOutput,
            system_instruction=system_instruction,
            stage="drafter_revision" if feedback_tokens else "drafter",
        )
        return resp.draft_text
    except ProviderProbeFailedError as e:
        print(f"WARNING: Drafter model failed: {e}", file=sys.stderr)
        return None
