import os
import sys
import asyncio
from typing import Literal
from pydantic import BaseModel
from zara.models import RankedProspect, RankedCard, DraftResult, VerificationResult
from zara.utils.provider import generate_content_with_retry, ProviderProbeFailedError

class DraftOutput(BaseModel):
    subject: str
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
        return "person_attributed"
    return "no_signal"

async def draft_email(ranked_prospect: RankedProspect, value_prop: dict, strictness: str = "strict", feedback_tokens: list[str] = None, hook: object = None, style: str = "auto") -> DraftOutput | None:
    winning_card = ranked_prospect.winning_card
    sender_name = value_prop.get("sender_person") or value_prop.get("sender_name", "Zamp")
    offer = value_prop.get("product", "")
    cta = value_prop.get("cta", "")

    if not winning_card:
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
        if strictness == "permissive" and value_prop.get("proof_point"):
            fallback_prompt += f"- You may use this proof point verbatim, and no other: {value_prop['proof_point']}\n"
        else:
            fallback_prompt += (
                "- Do NOT invent proof points, customer metrics, percentages, or numbers "
                "of any kind. No statistic that is not given to you above.\n"
            )
        if style and style != "auto":
            fallback_prompt += f"- Email opening style: {style}.\n"
            
        fallback_system = "You are an expert B2B SDR drafting concise, generic outreach emails. 4-7 words for subject, no colon-clause, names the specific thing not the benefit."
        try:
            resp = await generate_content_with_retry(
                prompt=fallback_prompt,
                schema=DraftOutput,
                system_instruction=fallback_system,
                stage="drafter_no_signal",
            )
            return resp
        except ProviderProbeFailedError as e:
            print(f"WARNING: Drafter fallback model failed: {e}", file=sys.stderr)
            return DraftOutput(
                subject=f"Connecting with {ranked_prospect.prospect.company}",
                draft_text=f"Hi {ranked_prospect.prospect.person_name},\n\nI looked across the web, your LinkedIn, and news sources to find what you're focusing on right now, but couldn't find a strong signal. If you're open to it, I'd love to learn what's top of mind for you. {offer}. Let me know if you're open to a chat.\n\nBest,\n{sender_name}"
            )

    pain_statement = ""
    pm = winning_card.pain_match
    if pm is None or pm.pain_id == "general_news":
        pain_statement = "We don't know their specific pain yet, but we want to start a conversation about how we help companies in their space."
        pain_reason = ""
    else:
        pain_reason = pm.reason
        for p in value_prop.get("pains", []):
            if p["id"] == pm.pain_id:
                pain_statement = p["statement"]
                break

    attribution_line = ""
    if winning_card.proximity == "colleague_authored":
        if winning_card.attributed_to:
            speaker = winning_card.attributed_to
            attribution_line = f"NOT the recipient speaking. It is {speaker}. You MUST attribute it to them explicitly (for example: \"your {speaker.split(',')[-1].strip()} said ...\"). NEVER write \"you said\", \"I saw you\", \"your view that\", or any second-person phrasing that implies {ranked_prospect.prospect.person_name} said or wrote this."
        else:
            attribution_line = f"this is a company-level fact, not something {ranked_prospect.prospect.person_name} personally said or did. Reference it as company news. Never imply they authored or said it."
    elif winning_card.proximity in ("company_action", "database"):
        attribution_line = f"this is a company-level fact, not something {ranked_prospect.prospect.person_name} personally said or did. Reference it as company news. Never imply they authored or said it."
    else:
        attribution_line = "the recipient's own words."
        
    age_phrase = f"published {winning_card.recency_days} days ago" if winning_card.recency_days is not None else "publication date unknown"
    
    prompt = f"RECIPIENT: {ranked_prospect.prospect.person_name}, {ranked_prospect.prospect.title or 'role unknown'} at {ranked_prospect.prospect.company}\n"
    if hook is not None:
        prompt += f"EVIDENCE (the only facts you may use): {hook.hook_text}\n"
        prompt += f"  source snippet, for accuracy — do not quote at length: {winning_card.card.snippet[:400]}\n"
        prompt += f"  age: {age_phrase}\n"
        prompt += f"  whose words these are: {attribution_line}\n"
        prompt += f"WHY IT MATTERS: {hook.rationale}\n"
    else:
        prompt += f"EVIDENCE (the only facts you may use): {winning_card.card.snippet[:400]}\n"
        prompt += f"  age: {age_phrase}\n"
        prompt += f"  whose words these are: {attribution_line}\n"

    prompt += f"THE PATTERN: {pain_statement}\n"
    prompt += f"WHAT MADE US THINK SO HERE: {pain_reason}\n"
    prompt += f"WHAT WE DO: {offer}\n"
    prompt += f"THE ASK: {cta}\n\n"

    prompt += "SHAPE — 50-90 words total:\n"
    prompt += f"1. \"Hi {ranked_prospect.prospect.person_name},\" on its own line.\n"
    prompt += "2. The evidence in <=12 words, then the observation it leads to. Two sentences max.\n"
    prompt += "3. What we do about that specific thing. One sentence, mechanism not benefit.\n"
    prompt += "4. The ask, as given. One sentence.\n"
    prompt += f"Sign: {sender_name}\n\n"

    if strictness == "strict":
        prompt += "Constraints:\n- Do NOT invent proof points or customer metrics.\n"
    elif strictness == "permissive":
        pp = value_prop.get("proof_point")
        if pp:
            prompt += f"Constraints:\n- You may use this proof point: {pp}\n"
        else:
            prompt += "Constraints:\n- Do NOT invent proof points or customer metrics.\n"
            
    if style and style != "auto":
        prompt += f"- Email opening style: {style}.\n"
    
    if feedback_tokens:
        prompt += "\nREVISE. Fix each issue below. Items prefixed FORMAT are style problems, not factual errors; everything else is an unsupported claim that must be removed or replaced with a grounded fact:\n"
        prompt += "\n".join(feedback_tokens)

    system_instruction = (
        "You write cold outreach emails a busy operator would actually reply to.\n\n"
        "- The recipient already knows their own news. Reference it in at most 12 words, as proof\n"
        "  you read it. Never summarise it back to them.\n"
        "- The value of the email is the observation AFTER the evidence: what that fact usually\n"
        "  means operationally. Offer it as a hypothesis you could be wrong about, not as a\n"
        "  diagnosis of them.\n"
        "- Describe what we do as a mechanism, concretely. No benefit adjectives, no outcome claims.\n"
        "- Never narrate your own reasoning. Never explain why you are writing.\n\n"
        "Banned: \"I noticed\", \"I saw your recent\", \"It sounds like\", \"I'd love to explore\",\n"
        "\"I'm reaching out because\", \"in your space\", \"leverage\", \"solutions\",\n"
        "\"streamline your operations\", \"back-office toil\", \"reach out\".\n\n"
        "Plain, specific, unhurried. No exclamation marks."
    )
        
    try:
        resp = await generate_content_with_retry(
            prompt=prompt,
            schema=DraftOutput,
            system_instruction=system_instruction,
            stage="drafter_revision" if feedback_tokens else "drafter",
        )
        return resp
    except ProviderProbeFailedError as e:
        print(f"WARNING: Drafter model failed: {e}", file=sys.stderr)
        return None
