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
        # This branch used to read, in full: "the recipient's own words." A noun
        # phrase, no directive, in the one case where attribution matters most.
        # Both other branches give an explicit MUST/NEVER, so person_authored was
        # the only proximity with nothing to obey, and the model did the cheapest
        # thing available: pasted the prospect's own sentence in as the sender's
        # opening line. Chermaine Hu's draft opened with twelve words she wrote
        # herself, unattributed, presented as ours. Quoting someone their own
        # sentence back at them with no attribution is worse than having no hook.
        attribution_line = (
            f"{ranked_prospect.prospect.person_name} wrote or said this. These are THEIR words, "
            "not yours, and the email must not pass them off as yours. But do NOT report the "
            "fact that they said it: \"You noted X\" as a standalone sentence is the machine "
            "move, and it was the first thing this got wrong. Their point is the premise of "
            "YOUR argument, and possessive phrasing carries the attribution without a sentence "
            "spent on it. \"Your point about legacy rails not fitting how fintech operates now "
            "holds a layer further down\" attributes, engages and advances in one line. "
            "Never reproduce their wording verbatim: compress it, shorter than the original. "
            "If you are copying a run of their words, you have got it wrong."
        )
        
    age_phrase = f"published {winning_card.recency_days} days ago" if winning_card.recency_days is not None else "publication date unknown"
    
    prompt = f"RECIPIENT: {ranked_prospect.prospect.person_name}, {ranked_prospect.prospect.title or 'role unknown'} at {ranked_prospect.prospect.company}\n"
    if hook is not None:
        prompt += f"EVIDENCE (the only facts you may use): {hook.hook_text}\n"
        # "do not quote at length" was read as permission to quote briefly, which
        # is exactly the failure: the hook sentence arrived verbatim because it
        # happened to fit the 12-word budget in move 2.
        prompt += f"  source snippet, given for accuracy only, never to be copied from: {winning_card.card.snippet[:400]}\n"
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
    # 70-110, not the 50-90 this asked for until now. The verifier's own budget is
    # WORD_MIN/WORD_MAX = 60-120, so every draft that landed in the 50s satisfied
    # the prompt and failed check_format, and its rewrite could never clear a bar
    # the prompt had not aimed at. Two of four demo drafts sat there permanently.
    # Nothing surfaced it while the format retry was the only caller; it broke in
    # the open once the repetition check depended on that retry succeeding.
    prompt += ("SHAPE (70-110 words total). Four moves, in this order. They are not four sentences\n"
               "of equal weight, so vary the lengths. Do not spend a sentence on hedging: say the\n"
               "observation once, as a hypothesis, and move on.\n")
    _first_name = (ranked_prospect.prospect.person_name or "").strip().split(" ")[0]
    prompt += f"1. \"Hi {_first_name or ranked_prospect.prospect.person_name},\" on its own line.\n"
    # Move 2 used to read "the evidence as a clause, THEN the observation it leads
    # to". That is an instruction to prove you read something and then pivot, and
    # it is the source of every "You noted", "You discussed", "You shared" this
    # has ever written. A person does not report someone's own point back to them
    # before making theirs; they make one argument, and the other person's point
    # is the premise of it. "Your point about legacy rails not fitting how fintech
    # operates now holds a layer further down" needs no announcement that it was
    # read. So the move is now the argument, not the transcript.
    prompt += ("2. ONE argument, in which the evidence is the premise and YOUR claim is the point. "
               "Two to three sentences. Not a report followed by a pivot.\n"
               "   Make a claim. This is the part that earns a reply, and it has been missing: "
               "every draft hedged into a generality about how work usually goes for other "
               "people, which is safe and says nothing. Assert something you believe and let the "
               "evidence carry it.\n"
               "   The claim is about the CATEGORY, never about the inside of their company. This "
               "is the whole line, and getting it wrong is fabrication: you have no visibility "
               "into their systems, their volumes or their close. \"Apparel is the category that "
               "breaks reconciliation\" is a claim you can make, because it is about apparel. "
               "\"Their reconciliation load grows in lockstep with transaction volume\" and "
               "\"transaction data arrives in fragmented batches\" are not claims, they are "
               "inventions about a company you cannot see into, and the verifier blocks them. "
               "Say what is true of this kind of business, then let them recognise themselves in "
               "it. Never state their internal condition as fact.\n"
               "   NEVER spend a sentence whose only job is to show you did the reading. Banned "
               "as sentence openers: \"You noted\", \"You mentioned\", \"You discussed\", \"You "
               "shared\", \"You talked about\", \"You wrote about\", \"You recently\", \"I read\", "
               "\"I came across\". If you reference what they said, the reference must carry the "
               "actual content of their point and be doing work inside a larger sentence. \"You "
               "discussed strategic insights in a Q&A\" is the failure: it names no idea, so it "
               "communicates only that a machine found a page.\n"
               "   Never restate the evidence as a list. One draft opened by naming fifteen "
               "service lines from a page, which is transcription wearing a sentence. If the "
               "evidence is a list, characterise it in a few words and move to the claim.\n"
               "   Put it in YOUR words. When the evidence is already a clean sentence the "
               "recipient wrote, copying it is the cheapest way to fill this move, and it is the "
               "one thing you must not do: they wrote it, they will recognise it, and an "
               "unattributed copy of their own line reads as a machine that pattern-matched "
               "them. Compress, do not transcribe.\n"
               "   Do not begin any sentence with \"That suggests\", \"That means\", \"This means\", "
               "\"That could mean\" or \"That implies\". Every draft used one of them; start with the "
               "thing itself instead.\n"
               "   Never spend a separate sentence saying you might be wrong. Do not open with a "
               "stock frame: \"Teams of this size\", \"Teams at this scale\" and \"Companies like "
               "yours\" are banned, and so is any other formula you would reuse on the next "
               "prospect.\n"
               "   Do not greet the fact or praise it. \"Excited to see\", \"Great to see\", "
               "\"Congratulations on\", \"I enjoyed\" and \"Interesting to read\" are all banned: "
               "state what they did or said, flat, and move to the observation.\n"
               "   The recipient's name appears in the greeting and NOWHERE else. \"Jon Anderson "
               "shared strategic insights\" is written at a man called Jon about a man called Jon. "
               "Say \"you\", or say what was said without naming anyone. Same for their job title.\n"
               "   Never state how old the evidence is. The age is given to you so you do not "
               "miscall something recent, not to be repeated back: \"posted 362 days ago\" in an "
               "email to a stranger is not something a person writes.\n")
    prompt += ("3. The mechanism, attached to the argument you just made. ONE mechanism, at most "
               "25 words. Never list capabilities, never stack time words (instantly / in real "
               "time / daily).\n"
               "   Attach it, do not announce it. This move kept arriving as a fresh sentence "
               "about us -- \"Our platform extracts...\", \"We provide a tool that...\", \"We build "
               "bots that...\" -- which reads as the point where the email stops being about them. "
               "All three of those openers are banned. Hang the mechanism off the thing you just "
               "claimed instead: \"that gap is what we work on\", \"we put that on rails\". Those two "
               "are illustrations of the SHAPE, not phrases to reuse: \"we put that on rails\" "
               "came back verbatim the moment it was offered. Write your own.\n")
    # "The ask, as given" put the same closing sentence on every email this has ever
    # written. Read two in a row and the template is the first thing you see. The ask
    # stays the same ASK; the wording is the writer's to fit to what came before it.
    # THE ASK is the outcome wanted, not the sentence to write. Read literally it
    # produced "Would you have 20 minutes next week to see if it fits?" on four
    # consecutive emails. A question about their own situation gets answered by
    # people who are not ready to book anything, and a reply is the actual goal.
    prompt += ("4. Close. One sentence, and it must be ANSWERABLE. Either ask for what THE ASK "
               "describes, or ask a real question about their situation that a reply can answer: "
               "\"is your team feeling that yet, or is it still manageable?\", \"if you are doing "
               "it by hand today, what does it cost you in hours?\". Prefer the question when the "
               "argument in move 2 sets one up. Ask ONE thing: two questions stapled together "
               "with \"and\" is a survey, and it halves the chance of an answer.\n"
               "   Do not negotiate a calendar. Banned outright, because every draft converged on "
               "them: \"schedule a brief call next week\" and any near-miss (short call, quick "
               "call, call next week, to explore, to discuss), and \"Would you have N minutes\". "
               "Do not stack hedges: \"a short brief quick call\" was really written. Do not open "
               "with \"Worth\".\n")
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
