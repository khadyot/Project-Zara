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
    "Never assert what the recipient's company or team does internally. You cannot see it.\n"
    # One licensed exception, because the shape asks for it by name. "I imagine
    # keeping payment records aligned across systems can become increasingly
    # time-consuming" hedges, and its subject is the work, not their payroll.
    # "Your reconciliation load is growing" is still a claim about the inside of
    # a company nobody outside it can see, and stays blocked.
    "One exception: \"I imagine <the work> can become increasingly time-consuming\" is "
    "allowed. It hedges, and it is about the work, not about what their people do.\n\n"
    "Banned: \"It sounds like\", \"I'd love to explore\",\n"
    "\"I'd love to\", \"in your space\", \"leverage\", \"solutions\",\n"
    "\"streamline\", \"back-office toil\", \"higher-value work\",\n"
    "\"minimal setup\", \"seamless\".\n\n"
    "Never use an em dash, an en dash, or any non-ASCII hyphen. Write compound words "
    "with a plain keyboard hyphen: \"time-consuming\", never \"time\u2011consuming\". "
    "Use a comma, a full stop, or a colon in place of a dash. "
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
    # Was "Adverbs. Cut all of them.", which is right about emphasis adverbs and
    # wrong about the two the shape depends on: "especially your point about X"
    # and "increasingly time-consuming" are both hedges, and cutting them flattens
    # the softness the whole voice is built from.
    "- Adverbs that only add emphasis. The hedging ones the shape calls for\n"
    "  (\"especially\", \"increasingly\") stay.\n"
    "- Passive voice. Name who does the thing.\n"
    "- Any sentence that would work as a pull quote. You are writing to one person."
)

# The close, fixed. Two sentences, in this order. The second one negotiates a
# calendar, which every earlier version of this prompt banned outright; the ban
# is lifted here deliberately, because the hand-written drafts this voice is
# copied from both end exactly this way.
#
# These stay literals where the introduction became config: they are house voice,
# they say nothing about who is sending or what they sell, and there is no field
# in value_prop.yaml that describes them.
CLOSE_QUESTION = "Curious if this is something"
CLOSE_OFFER = "Happy to connect for a quick chat."


# U+2010 HYPHEN, U+2011 NON-BREAKING HYPHEN, U+2012 FIGURE DASH. All three render
# as an ordinary hyphen and none of them is one, so "time-consuming" arrives
# looking correct and is not.
_UNICODE_HYPHENS = str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-"})


def ascii_hyphens(text: str | None) -> str | None:
    """Replace look-alike hyphens with the keyboard one.

    _STYLE_RULES bans these by name and the model still emits them: they came
    back in a recorded draft three prompt revisions after the ban was written.
    A ban the model obeys most of the time is not a guarantee, and this one is
    pure character substitution with nothing to decide, so it stops being a
    request and becomes a transform.

    Em and en dashes are deliberately NOT handled here. Those need the sentence
    reworded around a comma or a full stop, which is a writing decision the
    prompt owns and a substitution would paper over.
    """
    return text if text is None else text.translate(_UNICODE_HYPHENS)


def identity_line(value_prop: dict) -> str:
    """The sender's own introduction, composed from config.

    This was the literal "I'm Zamp from Zamp Technologies." until 2026-08-29.
    Two things were wrong with that, and only the first was obvious: every
    sender introduced itself as Zamp, and -- because the verifier grounds
    proper nouns against the string values of value_prop -- a name that lived
    in code rather than config read as an invention, so any other sender's
    drafts were BLOCKED for containing the sender's own company name.

    Degrades rather than breaks. Missing person, missing company, or the two
    set to the same word all have an honest form; none of them produce
    "I'm Zamp from Zamp".
    """
    person = (value_prop.get("sender_person") or "").strip()
    company = (value_prop.get("sender_company") or "").strip()
    name = (value_prop.get("sender_name") or "").strip()

    if person and company and person.casefold() != company.casefold():
        return f"I'm {person} from {company}."
    # No human signer configured -- signing as the company is the documented
    # default in value_prop.yaml, so the introduction is the company's too.
    entity = company or name or person
    if not entity:
        return "I'm reaching out."
    return f"I'm reaching out from {entity}."


def function_word(title: str | None) -> str | None:
    """The function a title owns, for "your <function> team".

    Was `"financ" in title or "cfo" in title`, which gave the team form to
    finance buyers and the bare "you're" to everybody else -- a rule shaped
    entirely by the two demo prospects, who were both CFOs. Read off the
    prospect's own title so it works for any ICP, and returns None rather than
    guessing when the title names no function or is absent.
    """
    t = (title or "").casefold()
    if not t:
        return None
    for function, cues in (
        ("finance", ("financ", "cfo", "controller", "accounting", "treasur")),
        # Before operations on purpose: "Director of People Ops" matches the "ops"
        # cue too, and the more specific function is the right answer.
        ("people", ("people", "human resources", "chro", " hr", "talent", "recruit")),
        ("operations", ("operation", "coo", "ops", "supply chain", "logistic", "fulfil")),
        ("revenue", ("revenue", "cro", "sales", "growth")),
        ("marketing", ("marketing", "cmo", "brand", "demand gen")),
        ("engineering", ("engineer", "cto", "infrastructure", "platform", "technical")),
        ("product", ("product", "cpo")),
        ("legal", ("legal", "counsel", "compliance", "risk")),
    ):
        if any(cue in t for cue in cues):
            return function
    return None

# Phrasing this prompt DICTATES, so it repeats across every draft in a batch by
# construction rather than by the writer running out of ideas. antitemplate's
# 4-gram check would otherwise read the second draft as a mail merge of the
# first and rewrite the voice back out; s2 registers these as supplied.
#
# Kept next to the prompt that mandates them: if a phrase changes above and not
# here, the repetition check quietly starts eating the house style again.
# These are word RUNS, not sentences: antitemplate compares 4-grams, so what has
# to be listed is every stretch of four consecutive words two drafts will share.
# The variable middles ("your finance team", "keeping payment records aligned")
# differ per prospect and are not listed, by design.
#
# Some entries run two fixed phrases together across a sentence or paragraph
# break. That is not redundancy: shingles ignore punctuation, so "...right now?
# Happy to connect..." produces the 4-gram ("about","right","now","happy"),
# which belongs to NEITHER phrase on its own and leaked through a version of
# this list that registered them separately.
#
# A function, not a constant, since the introduction is now composed from
# value_prop. `functions` is the set of team nouns the close may take across the
# batch: it cannot be known from one prospect, so callers pass what they have and
# the generic forms always cover the rest.
def scaffold_phrases(value_prop: dict, functions: tuple[str, ...] = ()) -> tuple[str, ...]:
    identity = identity_line(value_prop)
    phrases = [
        identity,
        CLOSE_QUESTION,
        # Was "...time-consuming. We build bots that", bridging into a mechanism
        # opener this prompt no longer dictates. Paragraph 3 is the writer's
        # again, so its repetition is a real tell and must be reported; the
        # straddle rule in antitemplate absorbs the sentence boundary itself.
        "can become increasingly time-consuming",
        f"is thinking about right now. {CLOSE_OFFER}",
        f"you're thinking about right now. {CLOSE_OFFER}",
        f"{identity} We",
        # The close's middle varies with who owns the problem, so CLOSE_QUESTION
        # alone leaves "something your finance team is" unregistered -- and every
        # draft written to one kind of owner shares it. Full sentences, so the
        # whole close is covered end to end whichever subject it takes.
        f"{CLOSE_QUESTION} your team is thinking about right now. {CLOSE_OFFER}",
        f"{CLOSE_QUESTION} you're thinking about right now. {CLOSE_OFFER}",
    ]
    for function in functions:
        if function:
            phrases.append(
                f"{CLOSE_QUESTION} your {function} team is thinking about right now. {CLOSE_OFFER}"
            )
    return tuple(phrases)


async def draft_email(ranked_prospect: RankedProspect, value_prop: dict, strictness: str = "strict", feedback_tokens: list[str] = None, hook: object = None, style: str = "auto") -> DraftOutput | None:
    winning_card = ranked_prospect.winning_card
    # No literal default. A "Zamp" fallback here signed someone else's email with
    # our name whenever the config was incomplete, which is the loudest possible
    # way to be wrong; an empty sender is visible and fixable, a wrong one is not.
    sender_name = value_prop.get("sender_person") or value_prop.get("sender_name") or ""
    identity = identity_line(value_prop)
    offer = value_prop.get("product", "")
    cta = value_prop.get("cta", "")

    if not winning_card:
        # First name only, same as the hooked path. The first recording of the new
        # shape came back "Hi Riley Chen," because this path was handed the full
        # name and never told otherwise.
        _fb_first = (ranked_prospect.prospect.person_name or "").strip().split(" ")[0]
        fallback_prompt = (
            f"Draft a generic 60-120 word B2B sales email to {_fb_first}, "
            f"at their company, {ranked_prospect.prospect.company}.\n"
            f"Greet them as \"Hi {_fb_first},\" -- first name only, and their name appears\n"
            f"nowhere else in the email.\n"
            f"Since we couldn't find a specific personal hook, frame the email around the general value we provide "
            f"to companies in their space.\n\n"
            f"WHAT WE SELL: {offer}\n"
            f"Constraints:\n"
            f"- Sign off on two lines: \"Best,\" then \"{sender_name}\".\n"
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
              "paragraphs separated by BLANK LINES, then a blank line, then \"Best,\" and the "
              "sender on the line below. Never one wall of text.\n"
            # The identity line and the close are the house voice, and this path
            # gets them too. A prospect who reads the no-signal email and then a
            # hooked one should not be able to tell they came from two writers.
            # The first recording of this shape came back as five paragraphs, with
            # "Our platform connects to existing systems", a whole paragraph of
            # "it works with the tools you already use", and the two closing
            # sentences split across two paragraphs. The count and the mechanism
            # opening are stated here because they were the two things it got
            # wrong, and a shape given as prose is a shape it will improvise on.
            + "THREE paragraphs. Not four, not five.\n"
            + f"  1. Two sentences: \"{identity}\" then, plainly, what we do.\n"
              "  2. One or two sentences: you looked and found no specific signal, said\n"
              "     without apology, and the kind of work we help with.\n"
              f"  3. Both closing sentences, IN ONE PARAGRAPH: \"{CLOSE_QUESTION} you're\n"
              f"     thinking about right now?\" then \"{CLOSE_OFFER}\"\n"
              "Ask one thing. Do not name a day, a duration or a meeting length, and do not\n"
              "stack that with \"a short demo\" or \"schedule a call\".\n"
              # Was: the mechanism sentence opens "We build bots that ...". That
              # asserted a product. It is true of the sender this was written for
              # and false of anyone else who configures this file, so the rule now
              # points at WHAT WE SELL instead of naming the thing sold.
              "The mechanism sentence starts with \"We\" and describes, concretely, the\n"
              "operation named in WHAT WE SELL above. Not \"automate\" as the verb: say what\n"
              "is actually done to what. \"Our platform ...\" is banned: it is the seam where\n"
              "the email stops being about them, and this path already has the least to say.\n"
              "Do not add a paragraph listing what it works with or how little it changes.\n"
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
            return DraftOutput(subject=ascii_hyphens(resp.subject),
                               draft_text=ascii_hyphens(resp.draft_text))
        except ProviderProbeFailedError as e:
            print(f"WARNING: Drafter fallback model failed: {e}", file=sys.stderr)
            return DraftOutput(
                subject=f"Connecting with {ranked_prospect.prospect.company}",
                # Last resort, written by hand because the model is unreachable.
                # It follows the same house shape as every other draft: identity,
                # what we found (nothing), what we do, the two-sentence close.
                draft_text=(
                    f"Hi {(ranked_prospect.prospect.person_name or '').strip().split(' ')[0]},\n\n"
                    f"{identity} {offer}.\n\n"
                    "I looked across the web, your LinkedIn, and news sources to find what "
                    "you're focusing on right now, but couldn't find a strong signal.\n\n"
                    f"{CLOSE_QUESTION} you're thinking about right now? {CLOSE_OFFER}\n\n"
                    f"Best,\n{sender_name}"
                )
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

    # The shape below is copied from two emails the user wrote by hand, and it
    # deliberately reverses several rules this prompt used to enforce by name: the
    # self-introduction, and the two-sentence close that offers a chat. The
    # earlier rules were aimed at making each email feel unrepeatable; the user's
    # judgement is that a consistent, plainly-introduced house voice reads better
    # than a set of individually clever ones. Where a rule below contradicts an
    # older comment in this file, the rule wins.
    #
    # What is fixed is VOICE. Nothing fixed here may assert what the sender sells:
    # the introduction is composed from value_prop, and paragraph 3 describes
    # whatever WHAT WE DO names. An earlier version required the literal "We build
    # bots that", which was true for one sender and a lie for every other.
    #
    # Consistency is the point for the voice, so the repetition check has to be
    # told which runs of words are ours rather than the writer's:
    # scaffold_phrases(), above, registered as supplied in s2. Change a fixed
    # phrase here and change it there.
    prompt += ("WRITE THE EMAIL. 70-110 words, four paragraphs, in this exact order. The\n"
               "paragraphs are short: one idea each, none over two sentences.\n"
               # The first recording of this shape dropped the full stop on three
               # of Chermaine's four paragraphs, because the examples below are
               # quoted as fragments and the model matched the fragment.
               "EVERY sentence ends with a full stop or a question mark, including the last\n"
               "one in a paragraph. The examples below show the SHAPE of a sentence, not\n"
               "text to paste: write your own, about this prospect, starting with a capital.\n\n")

    prompt += ("FORMAT -- this is literal, and every draft has got it wrong so far:\n"
               f"  Line 1: \"Hi {_first_name or ranked_prospect.prospect.person_name},\"\n"
               "  Then a BLANK LINE.\n"
               "  Then the paragraphs, each separated from the next by a BLANK LINE.\n"
               "  Sentences INSIDE a paragraph run on together, separated by a single space.\n"
               "  Never put a line break between two sentences of the same paragraph: that\n"
               "  renders as a column of orphaned lines and it is the thing that looks least\n"
               "  like a person typed it.\n"
               "  Then a BLANK LINE, then \"Best,\" on its own line, then the sender on the\n"
               "  line below it.\n"
               "Emails are not one wall of text. If two sentences belong to different\n"
               "thoughts, they belong to different paragraphs with a blank line between them.\n\n")

    prompt += ("PARAGRAPH 1 -- WHO YOU ARE. Two sentences. The first is fixed, word for word:\n"
               f"  \"{identity}\"\n")
    if _is_authored:
        # The example used to be "the complexity that comes with expanding payment
        # operations", which is Episode Six's world and nobody else's. Every
        # example in this prompt is now a shape with the content marked out, so it
        # teaches the sentence without handing over a vocabulary.
        prompt += ("Then ONE sentence naming the area you think you could help with, hedged and\n"
                   "general, in this shape: \"I'm reaching out because <the area of work their\n"
                   "evidence points at> may be an area we could help with.\" It names the\n"
                   "territory, not a diagnosis of them, and it does not yet mention the\n"
                   "evidence. That is paragraph 2's job. Fill the angle brackets from THIS\n"
                   "prospect and WHAT WE DO, never with the words of the example, and end the\n"
                   "sentence with a full stop.\n\n")
    else:
        prompt += ("Then ONE sentence saying plainly what we do, drawn from WHAT WE DO above. No\n"
                   "hedge needed here: it is a fact about us, not a claim about them.\n\n")

    prompt += "PARAGRAPH 2 -- WHAT YOU SAW, AND WHAT YOU MAKE OF IT. Two sentences, in one\nparagraph.\n"
    if _is_authored:
        prompt += ("  First: that you read what they wrote, and the specific idea in it. \"I read\n"
                   "  your post about <their subject>, especially your point about <the one\n"
                   "  specific idea in it>.\" Name the actual idea. \"I saw your recent post\"\n"
                   "  names none and tells them only that something automated found a page. Do\n"
                   "  not reproduce their sentence: compress it, shorter than the original. They\n"
                   "  wrote it, they will recognise it, and reading someone their own line back\n"
                   "  is the tell.\n")
    else:
        # The blanket ban on "I saw" for non-authored cards is lifted here. A
        # hand-written draft opened "Saw that <company>'s new ... center", which
        # claims only that the writer saw a public company fact -- true, and not a
        # claim that the recipient said it. What stays banned is the second
        # person: "you said", "your point", which check_attribution blocks anyway.
        prompt += ("  First: the company fact itself, opened with \"Saw that\", and ONLY what the\n"
                   "  evidence actually says. \"Saw that <company> <did the thing the evidence\n"
                   "  reports>.\" You may say you saw it, because you did. You may NOT imply\n"
                   "  they said or wrote it: no \"you said\", no \"your point\", no second\n"
                   "  person about the evidence at all.\n"
                   # A first recording wrote "...brings a broader range of SKUs per order
                   # and higher transaction volumes" here and the verifier blocked the
                   # draft, correctly: the article reports a launch, not its effects.
                   "  Do not append a consequence to this sentence. \"...which brings higher\n"
                   "  transaction volumes\" states as fact something the evidence does not\n"
                   "  report, and the verifier blocks the whole draft for it. Consequences are\n"
                   "  the next sentence's job, where they are hedged and marked as yours.\n")
    prompt += ("  Second: what you imagine that means for the work, hedged, in this shape:\n"
               "  \"I imagine <gerund naming the actual work> can become increasingly\n"
               "  time-consuming.\" Name the real artifacts, the way the person doing the job\n"
               "  would: \"keeping <the actual records> aligned across <the actual systems>\",\n"
               "  \"keeping up with <the actual work the evidence implies>\". \"keeping things\n"
               "  aligned\" names nothing and is the version every prospect gets.\n"
               "  The subject is the WORK, never their people:\n"
               "  \"your reconciliation load is growing\" and \"finance teams allocate extra staff\"\n"
               "  are claims about the inside of a company you cannot see, and are blocked.\n"
               "  Never invent a quantity or an outcome: no percentages, no hours saved, no\n"
               "  headcount, no timeframe. Do not open the sentence with \"That suggests\", \"That\n"
               "  means\", \"This means\" or \"That implies\", and do not use a stock frame like\n"
               "  \"Companies like yours\". Never say how old the evidence is.\n\n")

    # This paragraph used to open with a required literal, "We build bots that".
    # It was true of the sender the voice was fitted to and a lie for anyone else
    # who edits value_prop.yaml, so the rule now points at WHAT WE DO and lets the
    # sentence be composed from it. Consequence, accepted deliberately: paragraph
    # 3 is the writer's again, so it can repeat across a batch -- which is a real
    # tell, is no longer exempt scaffolding, and antitemplate reports it.
    prompt += ("PARAGRAPH 3 -- WHAT WE DO ABOUT IT. ONE sentence, at most 25 words. The\n"
               "subject is \"we\", and the sentence describes the MECHANISM named in WHAT WE DO\n"
               "above: what is actually done, to what.\n"
               # Every draft in the first recording of this shape read "...that
               # automate ...". "Automate" is the category, not the operation, and
               # it is the word every one of these emails reaches for first.
               "Do not use \"automate\" as the verb: it names the category, not the operation.\n"
               "Say the operation on the data, the way someone who built the thing would\n"
               "describe it, in the vocabulary of WHAT WE DO. If WHAT WE DO does not name a\n"
               "mechanism, say plainly what it does and stop; do not invent one.\n"
               # Caught running a sender whose product string is already one
               # concrete sentence: paragraph 1 said it, and paragraph 3 said it
               # again, word for word, four lines later.
               "Do NOT repeat paragraph 1's sentence. If WHAT WE DO is already a single\n"
               "concrete sentence, paragraph 1 has spent it: here, name the part of that work\n"
               "which bites for THIS prospect, in different words. Two paragraphs carrying one\n"
               "sentence twice reads as a form letter that lost its place.\n"
               "\"Our platform ...\" and \"We provide a tool that ...\" are banned openings: that\n"
               "is the seam where the email stops being about them. It must be a COMPLETE\n"
               "SENTENCE with a subject and a main verb -- avoiding a banned opening does not\n"
               "mean deleting the subject, and a fragment is not a fix.\n"
               "End with a short clause naming what that saves, written for THIS prospect\n"
               "rather than reaching for the same stock phrase every time.\n"
               # "saving your finance team manual reconciliation effort" was really
               # written here. It passed the verifier and should not have: nobody
               # outside the company knows what its finance team does by hand.
               "That clause names the WORK, never their people: \"reducing repetitive manual\n"
               "checks\" is fine, \"saving your finance team manual reconciliation effort\" is a\n"
               "claim about the inside of a company you cannot see. No \"your team\", no \"your\n"
               "finance team\", no \"your staff\" anywhere in this sentence.\n"
               "Concrete mechanism, no benefit adjectives, no capability list, and never stack\n"
               "time words (instantly / in real time / daily). The subject is \"we\", never\n"
               "\"I\": you may write \"I\" about reading their post, because a person did that,\n"
               "but the product is the company's.\n\n")

    # "your <function> team" when the title says which function owns this, "you"
    # otherwise. Was a bare test for "financ"/"cfo" -- a rule shaped by the two
    # demo prospects, who were both CFOs, and one that gave every other ICP the
    # generic form. A suggestion in the prompt, not a string the model must paste.
    _function = function_word(ranked_prospect.prospect.title)
    _close_subject = f"your {_function} team is" if _function else "you're"

    prompt += ("PARAGRAPH 4 -- THE CLOSE. Two sentences, in this order, and close to these words:\n"
               f"  \"{CLOSE_QUESTION} {_close_subject} thinking about right now?\"\n"
               f"  \"{CLOSE_OFFER}\"\n"
               "Those two sentences are fixed. Adjust only who the question is about ( \"you\"\n"
               "or the team whose problem this is). Do not add words to the end of either one:\n"
               "\"...thinking about right now today?\" was really written by this prompt.\n"
               "The question must be answerable by someone not ready to book anything, which is\n"
               "why it asks what they are thinking about rather than for time. Ask ONE thing:\n"
               "two questions joined by \"and\" is a survey. Do not restate paragraph 2 before\n"
               "asking. Do not name a day, a duration, or a meeting length.\n\n")

    prompt += ("THE NAME. Their first name appears in the greeting and NOWHERE else, and never\n"
               "their job title. \"Jon Anderson shared strategic insights\" is written at a man\n"
               "called Jon about a man called Jon. Say \"you\".\n\n")

    prompt += ("SIGN OFF exactly like this, on two lines, after a blank line:\n"
               "  \"Best,\"\n"
               f"  \"{sender_name}\"\n\n")

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
        # A repetition note can point at a line this prompt DICTATES, and the
        # obedient fix is to reword it -- which is how a rewrite quietly undoes
        # the house voice it was never complaining about. s2 exempts those runs
        # from the check; this is the second belt.
        prompt += ("The fixed lines above are not yours to change: the introduction, the two\n"
                   "closing sentences and the sign-off stay word for word. Fix the sentences\n"
                   "around them. Paragraph 3 is NOT fixed: if the note says it repeats an\n"
                   "earlier draft, that is the sentence to rewrite.\n")
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
          "- Describe what we do as a mechanism, concretely. No benefit adjectives, and no\n"
          "  outcome you cannot show: naming the manual work the mechanism removes\n"
          "  (\"reducing repetitive manual checks\") is describing the mechanism. Claiming\n"
          "  what it achieves for them (\"cuts your close by a day\") is not."
    )
        
    try:
        resp = await generate_content_with_retry(
            prompt=prompt,
            schema=DraftOutput,
            system_instruction=system_instruction,
            stage="drafter_revision" if feedback_tokens else "drafter",
        )
        return DraftOutput(subject=ascii_hyphens(resp.subject),
                           draft_text=ascii_hyphens(resp.draft_text))
    except ProviderProbeFailedError as e:
        print(f"WARNING: Drafter model failed: {e}", file=sys.stderr)
        return None
