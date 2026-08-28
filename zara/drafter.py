import os
import sys
import asyncio
from typing import Literal
from pydantic import BaseModel
from zara.models import RankedProspect, RankedCard, DraftResult, VerificationResult
from zara.evidence import clean_snippet
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
    "Never narrate your own reasoning.\n\n"
    # "Never explain why you are writing" and a blanket ban on "I noticed" used to
    # live here. Both were mine, both were wrong, and together they left the model
    # no honest way to open: it could not say it had read something, so it opened
    # by asserting the thing it had read as its own thought. Saying why you are
    # writing is what an email IS. The per-proximity opening rules in the prompt
    # now govern this: allowed when they authored the evidence, banned otherwise.
    # These live in the system instruction rather than in the prompt body because
    # the prompt is long now, and a ban buried two hundred lines down gets lost:
    # "in real time" came back three drafts after it was banned mid-prompt.
    "Never write \"in real time\", \"instantly\", \"immediately\" or \"daily\" about what we do.\n"
    "Never invent a number: no percentages, no hours saved, no headcount, no timeframe.\n"
    "Never assert what the recipient's company or team does internally. You cannot see it.\n\n"
    "Banned: \"It sounds like\", \"I'd love to explore\",\n"
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
        # The formatting and closing rules used to live only in the hooked path, so
        # the no-signal email came out as one unbroken wall of text that closed by
        # asking for "a few minutes next week" -- the exact calendar negotiation
        # banned three inches away. The honest-degradation path keeps being the
        # sloppiest thing the product prints, because it is the one nobody reads.
        fallback_system = (
            _STYLE_RULES
            + "\n\nYou have no prospect-specific signal. Write the company-level version: say "
              "plainly what you do and why it might matter to a company like theirs. Do not "
              "manufacture a hook, do not imply you researched them, and do not apologise for "
              "having nothing. Subject: 4-7 words, no colon-clause, name the thing not the benefit."
            + "\n\nFORMAT, literally: \"Hi <first name>,\" then a BLANK LINE, then short "
              "paragraphs separated by BLANK LINES, then a blank line and the sign-off on its "
              "own line. Never one wall of text.\n"
              "Close with one answerable question. Do not negotiate a calendar: \"a few minutes "
              "next week\", \"a short demo\", \"schedule a call\", \"a brief conversation\" and "
              "every near-miss are banned.\n"
              "You have NO evidence about this company, so you have nothing to report about "
              "outcomes either. \"Teams that adopt this report fewer errors\" is a customer "
              "metric with the number filed off, and it is the exact claim this path has no "
              "standing to make. Say what the thing does. Never what it achieves."
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
        # Was snippet[:400], and that 400 was the real cause of the bad drafts: for a
        # LinkedIn card the head of the snippet is deterministically header plus
        # profile bio, so the writer got ~110 characters of actual content and
        # reached for the one sentence it could see. clean_snippet drops the
        # furniture and this passes what is left, whole.
        prompt += f"  the evidence in full, for accuracy, never to be copied from verbatim: {clean_snippet(winning_card.card.snippet)}\n"
        prompt += f"  age: {age_phrase}\n"
        prompt += f"  whose words these are: {attribution_line}\n"
        prompt += f"WHY IT MATTERS: {hook.rationale}\n"
    else:
        prompt += f"EVIDENCE (the only facts you may use): {clean_snippet(winning_card.card.snippet)}\n"
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
    # Whether the writer may say "I read your post" turns on whether they actually
    # did read something the prospect wrote. Ruled by the user: allowed for
    # person_authored, banned everywhere else, because "I noticed your company
    # opened a facility" is filler dressed as attention.
    _is_authored = winning_card.proximity == "authored"
    # First name only. "Hi Stephanie Fielding," announces the automation before the
    # first comma.
    _first_name = (ranked_prospect.prospect.person_name or "").strip().split(" ")[0]

    # The four numbered moves are gone. They produced four emails that walked the
    # same beats in the same order, and no amount of banned vocabulary fixed that:
    # a reader feels the scaffolding, not the words. What is left is the running
    # order a person actually uses -- why I am writing, the thought it gave me,
    # what we do about it, one question -- with the length ratios left open.
    prompt += ("WRITE THE EMAIL. 70-110 words. Four short paragraphs, and the paragraph is the\n"
               "unit: one idea each, wildly different lengths, no paragraph over three sentences.\n\n")

    prompt += ("FORMAT -- this is literal, and every draft has got it wrong so far:\n"
               f"  Line 1: \"Hi {_first_name or ranked_prospect.prospect.person_name},\"\n"
               "  Then a BLANK LINE.\n"
               "  Then the paragraphs, each separated from the next by a BLANK LINE.\n"
               "  Sentences INSIDE a paragraph run on together, separated by a single space.\n"
               "  Never put a line break between two sentences of the same paragraph: that\n"
               "  renders as a column of orphaned lines and it is the thing that looks least\n"
               "  like a person typed it.\n"
               "  Then a BLANK LINE, then the sign-off on its own line.\n"
               "Emails are not one wall of text. If two sentences belong to different\n"
               "thoughts, they belong to different paragraphs with a blank line between them.\n\n")

    if _is_authored:
        prompt += ("OPENING. You are writing because you read something they wrote. Say so, plainly,\n"
                   "in the first person, and name the actual idea in the same breath: \"I read your\n"
                   "post on X and the line about Y stuck\". \"I noticed\", \"I read\", \"I came across\"\n"
                   "are all fine here. What is NOT fine is the version that names no idea -- \"I\n"
                   "noticed your strategic insights\", \"I saw your recent post\" -- which tells them\n"
                   "only that something automated found a page. The specific detail IS the proof\n"
                   "you read it, so you never have to claim you did.\n"
                   "Do not reproduce their sentence. They wrote it, they will recognise it, and\n"
                   "reading someone their own line back is the clearest possible tell.\n\n")
    else:
        prompt += ("OPENING. This is not something they wrote, so do NOT open with \"I noticed\", \"I\n"
                   "read\", \"I saw\" or any first-person claim to have been paying attention. Open\n"
                   "on the substance itself and let the relevance do the work.\n\n")

    prompt += ("THE THOUGHT. One claim you are willing to make, about how this KIND of business\n"
               "or this kind of work goes. Not a hedge, not a generality about \"teams\", and not\n"
               "an assertion about the inside of their company, which you cannot see and which\n"
               "the verifier will block: \"apparel is the category that breaks reconciliation\" is\n"
               "yours to say, \"your reconciliation load is growing\" is not.\n"
               "The test is grammatical, so apply it to every sentence: if the SUBJECT is their\n"
               "company, their team, their finance function or their people, and the verb says\n"
               "what those people do, you have made it up. \"Finance teams allocate extra staff\n"
               "to keep the books balanced\" was really written, and blocked, about a company\n"
               "whose staffing nobody outside it can see. Write the pattern, not the payroll.\n"
               "Never invent a quantity or an outcome either -- no percentages, no hours saved,\n"
               "no \"could shrink the close by a day or two\", no headcount, no timeframe. Those\n"
               "are the numbers a buyer checks first, and you do not have them.\n"
               "Do not open any sentence with \"That suggests\", \"That means\", \"This means\",\n"
               "\"That could mean\" or \"That implies\". Do not use a stock frame like \"Teams of\n"
               "this size\" or \"Companies like yours\". Never say how old the evidence is.\n\n")

    prompt += ("WHAT WE DO. One mechanism, at most 25 words, hung off the claim you just made\n"
               "rather than announced as a new subject. \"Our platform...\", \"We provide a tool\n"
               "that...\" and \"We build bots that...\" are banned openings: that is the seam where\n"
               "the email stops being about them. Ban the PATTERN, not the string: \"Our team\n"
               "builds bots that...\" is the same announcement wearing a hat, and so is any\n"
               "\"<we/our team/our platform> build(s) <product noun> that...\" opening.\n"
               "The subject is \"we\", never \"I\". You may write \"I\" about reading their post,\n"
               f"because a person did that, but the product is {sender_name}'s and \"I built a bot\"\n"
               "claims you personally built it. Read the reading, built by we.\n"
               "ONE sentence. Not two, not a sentence plus a gloss on it. Never list\n"
               "capabilities, and never stack time words (instantly / in real time / daily).\n"
               "It must be a COMPLETE SENTENCE, with a subject and a main verb. Avoiding the\n"
               "banned openings does not mean deleting the subject: \"A service that cross-checks\n"
               "incoming payment data\" is a fragment, and a fragment is not a fix. \"We\" is a\n"
               "perfectly good subject; it is \"Our platform\" as an announcement that is banned.\n\n")

    prompt += ("THE CLOSE. Do not restate the claim before asking. A run-up sentence that says\n"
               "again what the second paragraph already said is padding, and it reads as though\n"
               "you did not trust the reader the first time.\n"
               "One sentence, one question, and it must be answerable by someone who\n"
               "is not ready to book anything -- \"is that still manageable, or is it costing you\n"
               "real hours?\". Do not negotiate a calendar. Banned: \"schedule a brief call next\n"
               "week\" and every near-miss (short call, quick call, call next week, to explore, to\n"
               "discuss), and \"Would you have N minutes\". Never stack hedges: \"a short brief\n"
               "quick call\" was really written by this prompt. Do not open with \"Worth\".\n"
               "Two questions joined by \"and\" is a survey. Ask one thing.\n\n")

    prompt += ("THE NAME. Their first name appears in the greeting and NOWHERE else, and never\n"
               "their job title. \"Jon Anderson shared strategic insights\" is written at a man\n"
               "called Jon about a man called Jon. Say \"you\".\n\n")

    prompt += f"Sign off exactly as: {sender_name}\n\n"

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
          "- The recipient already knows their own news, so do not summarise it back to them.\n"
          "  Refer to it the way you would to someone who was there: name the specific part\n"
          "  that mattered to you and move on. (This used to demand 'at most 12 words, as proof\n"
          "  you read it', which, on a card whose only visible sentence was the prospect's own\n"
          "  headline, made copying that headline the cheapest way to comply.)\n"
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
