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

# The voice rules for every email this product writes, hook or no hook.
#
# These lived inside draft_email's main path, so the no-signal fallback -- the
# one draft that most needs to sound like a person wrote it, because it has no
# evidence to lean on -- never saw them. It shipped "I'm reaching out because",
# "streamline your operations" and "I'd love to", all three banned by name a few
# lines away. Module level so there is one copy and both callers get it.
_STYLE_RULES = (
    "You write cold outreach emails a busy operator would actually reply to.\n\n"
    "Never narrate your own reasoning. Never explain why you are writing.\n\n"
    "Banned: \"I noticed\", \"I saw your recent\", \"It sounds like\", \"I'd love to explore\",\n"
    "\"I'd love to\", \"I'm reaching out because\", \"in your space\", \"leverage\", \"solutions\",\n"
    "\"streamline\", \"back-office toil\", \"reach out\", \"higher-value work\",\n"
    "\"minimal setup\", \"seamless\".\n\n"
    "Never use an em dash or an en dash. Use a comma, a full stop, or a colon. "
    "This is absolute: a dash of that kind is the single clearest tell that a "
    "machine wrote the message, and it undoes the point of the whole exercise.\n\n"
    "Plain, specific, unhurried. No exclamation marks.\n\n"
    "Sentence rhythm carries more of the tell than vocabulary does. Vary the lengths.\n"
    "Do not write three sentences in a row of similar length.\n\n"
    "Also banned, because they are the shapes a machine reaches for:\n"
    "- Setup-and-reverse: \"It is not X, it is Y\", \"The question is not X but Y\",\n"
    "  \"X is not the problem, Y is\". State Y.\n"
    "- Listing what something is not before saying what it is.\n"
    "- Fragments for emphasis: \"That is it.\", \"Every time.\"\n"
    "- Adverbs. Cut all of them.\n"
    "- Passive voice. Name who does the thing.\n"
    "- Any sentence that would work as a pull quote. You are writing to one person."
)


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
            
        # This path used to carry its own short system prompt, which meant the
        # no-signal email was the ONE draft that never saw the style rules. It
        # opened "I'm reaching out because", promised to "streamline your
        # operations" and closed with "I'd love to" -- three phrases banned by
        # name a hundred lines below. The honest-degradation path was the
        # sloppiest thing the product produced. It gets the same rules now.
        fallback_system = (
            _STYLE_RULES
            + "\n\nYou have no prospect-specific signal. Write the company-level version: say "
              "plainly what you do and why it might matter to a company like theirs. Do not "
              "manufacture a hook, do not imply you researched them, and do not apologise for "
              "having nothing. Subject: 4-7 words, no colon-clause, name the thing not the benefit."
        )
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
        prompt += f"  source snippet, for accuracy, do not quote at length: {winning_card.card.snippet[:400]}\n"
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

    # The four moves stay. I removed them once and the emails got worse: with only
    # constraints and no running order, "vary the lengths" plus "offer it as a
    # hypothesis" produced "I could be wrong.", "Maybe I'm off." and "I appreciate
    # your insight." as standalone sentences. The skeleton holds the email tight;
    # what made every email identical was the fixed closing line, not the shape.
    #
    # Each constraint below is here because a live run broke it:
    #   - a word budget, after "one sentence, mechanism not benefit" came back as
    #     six clauses and forty words wearing a sentence's punctuation;
    #   - "grammatical clause", after "Stord raised $250M funding round." arrived
    #     as a headline fragment;
    #   - first name only, because "Hi Stephanie Fielding," announces the
    #     automation before the first comma.
    prompt += ("SHAPE (50-90 words total). Four moves, in this order. They are not four sentences\n"
               "of equal weight, so vary the lengths. Do not spend a sentence on hedging: say the\n"
               "observation once, as a hypothesis, and move on.\n")
    _first_name = (ranked_prospect.prospect.person_name or "").strip().split(" ")[0]
    prompt += f"1. \"Hi {_first_name or ranked_prospect.prospect.person_name},\" on its own line.\n"
    prompt += ("2. The evidence as a complete, grammatical clause in <=12 words -- not a headline "
               "fragment -- then the observation it leads to. Two sentences max.\n"
               "   Do not begin the observation with \"That suggests\", \"That means\", \"This means\", "
               "\"That could mean\" or \"That implies\". Every draft used one of them; start with the "
               "thing itself instead.\n"
               "   The observation is a guess about how work like theirs usually goes, not a "
               "finding about them: never assert it about their company as fact, and never spend "
               "a separate sentence saying you might be wrong. Do not open it with a stock frame "
               "either. \"Teams of this size\", \"Teams at this scale\" and \"Companies like yours\" "
               "are banned openers, and so is any other formula you would reuse on the next "
               "prospect. Get into the generalisation a different way each time.\n"
               "   Do not greet the fact or praise it. \"Excited to see\", \"Great to see\", "
               "\"Congratulations on\", \"I enjoyed\" and \"Interesting to read\" are all banned: "
               "state what they did or said, flat, and move to the observation.\n"
               "   The recipient's name appears in the greeting and NOWHERE else. \"Jon Anderson "
               "shared strategic insights\" is written at a man called Jon about a man called Jon. "
               "Say \"you\", or say what was said without naming anyone. Same for their job title.\n"
               "   Never state how old the evidence is. The age is given to you so you do not "
               "miscall something recent, not to be repeated back: \"posted 362 days ago\" in an "
               "email to a stranger is not something a person writes.\n")
    prompt += ("3. What we do about that specific thing. ONE mechanism, at most 20 words, written as "
               "a grammatical English sentence. Name the single most relevant one; never list "
               "capabilities, and never stack time words (instantly / in real time / daily).\n")
    # "The ask, as given" put the same closing sentence on every email this has ever
    # written. Read two in a row and the template is the first thing you see. The ask
    # stays the same ASK; the wording is the writer's to fit to what came before it.
    prompt += ("4. Close by asking for what THE ASK describes. Do not reuse its wording verbatim, "
               "and do not open that sentence with \"Worth\". One sentence.\n")
    prompt += f"Sign: {sender_name}\n\n"

    # An undated card cannot support ANY claim about when the thing happened.
    # This is where "New finance chief" came from: an undated listicle whose pain
    # reason asserted "New CFO appointment within six months" about someone three
    # and a half years into the job. The verifier now catches the phrasing; this
    # stops it being written in the first place.
    if winning_card is not None and winning_card.recency_days is None:
        prompt += ("TIMING - the evidence carries NO publication date. Do not call it new, recent, "
                   "just-announced, or imply when it happened. Do not describe anyone as a new or "
                   "incoming hire. Write it as a standing fact, not as news.\n\n")

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
        _STYLE_RULES
        + "\n\n"
          "- The recipient already knows their own news. Reference it in at most 12 words, as proof\n"
          "  you read it. Never summarise it back to them.\n"
          "- The value of the email is the observation AFTER the evidence: what that fact usually\n"
          "  means operationally. Offer it as a hypothesis you could be wrong about, not as a\n"
          "  diagnosis of them.\n"
          "- Describe what we do as a mechanism, concretely. No benefit adjectives, no outcome claims."
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
