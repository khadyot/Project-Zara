import yaml
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import asyncio
from pydantic import BaseModel, Field
from typing import Literal
import sys

from zara.evidence import clean_snippet
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


# Exa renders a LinkedIn post with the AUTHOR's bio block ahead of the body:
# "**Keith Smith**: Founder, CEO and President at Payouts Network for 10 years ...".
# That byline is the only reliable statement of who actually wrote the thing.
_LINKEDIN_BIO = re.compile(r"^\*\*([^*]+?)\*\*:\s*(.+)$", re.M)


def _post_author(card: SignalCard) -> tuple[str, str] | None:
    """(name, role) of whoever wrote this post, or None if there is no byline."""
    m = _LINKEDIN_BIO.search(card.snippet or "")
    if not m:
        return None
    name, rest = m.group(1).strip(), m.group(2).strip()
    # A real bio reads "Role at Company for N years ... Based in ...". A bolded
    # line without any of that is a label in the body, not a byline.
    if not re.search(r"\b(years?|experience|Based in)\b", rest, re.I):
        return None
    role = re.split(r"\s+for\s+\d|\.\s", rest)[0].strip(" .")
    return (name, role) if name else None


def _same_person(author: str, person_name: str) -> bool:
    """Do these two strings name the same human?

    Surname equality alone is not enough in either direction: Exa abbreviates, so
    Fulfyld's founder appears as "AJ K." while we hold "AJ Khanijow". Given name
    must agree; the surname may be an initial of the other.
    """
    a = [t.strip(".,").lower() for t in (author or "").split() if t.strip(".,")]
    b = [t.strip(".,").lower() for t in (person_name or "").split() if t.strip(".,")]
    if not a or not b or a[0] != b[0]:
        return False
    if len(a) == 1 or len(b) == 1:
        return True
    x, y = a[-1], b[-1]
    return x == y or (len(x) == 1 and y.startswith(x)) or (len(y) == 1 and x.startswith(y))


def _is_prospect_authored(card: SignalCard, person_name: str) -> bool:
    """Did the PROSPECT write this, as opposed to merely appearing in it?

    mentions_prospect only asks whether the surname occurs somewhere in the text,
    and a colleague announcing someone's appointment names them repeatedly. That
    is how Keith Smith's congratulatory repost about Jon Anderson was scored
    `authored` -- the strongest label the product has -- and handed to the drafter
    as "the recipient's own words", so the email told Jon what Jon supposedly said
    while quoting Keith's bio. When a byline exists it decides; otherwise fall
    back to the mention test, which is all there is for non-LinkedIn cards.
    """
    author = _post_author(card)
    if author:
        return _same_person(author[0], person_name)
    return mentions_prospect(card, person_name)


# A third-party article that quotes the prospect verbatim is closer to their own
# voice than a news item that merely announces their hire. Compass V ranks by
# proximity to the prospect, and "he highlighted that '...'" IS the prospect
# speaking, whoever published it. Without this, Jon Anderson's winner was a wire
# story about his appointment while an interview containing his actual words on
# payments infrastructure sat unused two cards down.
_SPEECH = re.compile(r"\b(said|says|told|noted|notes|explains|explained|highlighted|highlights|"
                     r"argues|argued|adds|added|emphasi[sz]ed|wrote|writes)\b", re.I)
_QUOTED = re.compile(r"[\"\u201c]([^\"\u201d]{40,})[\"\u201d]")

# Deliberately narrow. Requiring a real quoted span AND a speech verb introducing
# it rejects the two things that look similar and are not: a colleague's
# congratulation ("Excited to see Jon sharing his insights") carries no quote, and
# a namesake's podcast transcript carries no speech verb before one.
VOICE_BONUS = 1.25


def quotes_prospect(card: SignalCard, person_name: str) -> bool:
    """Is the prospect actually speaking here, even though someone else published it?"""
    toks = _name_tokens(person_name)
    if not toks:
        return False
    surname = toks[0].lower()
    hay = f"{card.claim} {card.snippet}"
    low = hay.lower()
    if not re.search(r"\b" + re.escape(surname) + r"\b", low):
        return False
    return any(_SPEECH.search(low[max(0, m.start() - 200):m.start()])
               for m in _QUOTED.finditer(hay))


# Compass X: relevance is not permission. An announcement of the PROSPECT'S OWN
# appointment scores well on every axis this ranker measures -- person-tier,
# recent, and it genuinely evidences structural_complexity -- and it is unusable,
# because the resulting email explains to a CFO that hiring a CFO creates
# reconciliation work. It is what cut Jon Anderson from the demo set, and a live
# run on 2026-09-02 produced it again for Devin Weil at person_authored with a
# clean verification: the strongest claim tier the product has, on its weakest
# possible reason to write.
#
# This cannot live in never_reference. That list matches topics, and appointments
# are not an off-limits topic -- structural_complexity names "recent appointments
# of new finance leadership" as an observable, so a colleague's appointment is
# real evidence we want. What makes it unusable is RELATIONAL: the appointee is
# the recipient. So it is computed here, against the prospect, like the namesake
# check.
_APPOINT_ROLE = (r"chief\s+[\w\s]{0,24}?officer|c[efotmr]o|president|founder|co-?founder"
                 r"|controller|vice\s+president|vp|head\s+of\s+[\w\s]{2,24}"
                 r"|director\s+of\s+[\w\s]{2,24}")

_APPOINT = re.compile(
    r"\b(?:appoint(?:s|ed|ing|ment)?|names?\s+(?!a\b)|named\s+(?:as\s+)?"
    r"|welcom(?:e|es|ed)|hir(?:e|es|ed)\s+|promot(?:e|es|ed)\s+"
    r"|join(?:s|ed|ing)?\s+(?:\w+\s+){0,3}?as\b|steps?\s+into\s+the\s+role"
    r"|takes?\s+over\s+as|expands?\s+[\w\s]{0,24}team\s+with)\b", re.I)

_FIRST_PERSON_JOIN = re.compile(
    r"\b(?:i\s+(?:am|'m|have|'ve)?\s*(?:absolutely\s+|so\s+|very\s+)?"
    r"(?:thrilled|excited|delighted|pleased|happy|proud)?[\s\w]{0,24}?"
    r"(?:to\s+)?(?:have\s+)?join(?:ed|ing)?\b"
    r"|i\s+(?:have\s+)?join(?:ed|ing)?\b"
    r"|(?:thrilled|excited|delighted|pleased|proud)\s+to\s+(?:have\s+)?"
    r"(?:join(?:ed|ing)?|be\s+join(?:ing)?)\b)", re.I)

# A role named shortly after the join is what makes it employment rather than an
# appearance on somebody's show. Without this the demo's hero card is flagged:
# Chermaine Hu's post opens "I recently joined @Venture:F to talk about what
# building modern issuer processing actually looks like", which is a podcast.
_ROLE_NEAR = re.compile(r"\b(?:" + _APPOINT_ROLE + r"|team)\b", re.I)

_APPOINTEE_NAME = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]*\.?){1,2})\b")


def is_own_appointment(card: SignalCard, person_name: str, proximity: str) -> bool:
    """Is this card the announcement of the prospect's own hire?

    Measured across all 181 recorded cards: 3 flagged, all of them genuine --
    two Payouts Network releases naming Jon Anderson and one "DEVIN WEIL NEW
    CHIEF FINANCIAL OFFICER". Zero false positives, including on the three
    appointment cards about OTHER people at Payouts Network, which must survive.
    """
    if not person_name:
        return False
    text = f"{card.claim}\n{card.snippet or ''}"

    # Their own post about the move. Requires a role, per _ROLE_NEAR above.
    if proximity == "authored":
        for m in _FIRST_PERSON_JOIN.finditer(text):
            if _ROLE_NEAR.search(text[m.end(): m.end() + 130]):
                return True

    # A third party placing a NAMED person into a role. Whose hire it is decides
    # everything: Payouts Network appointing Jon Anderson is unusable to Jon,
    # while Payouts Network appointing a VP of Sales is evidence we want.
    for m in _APPOINT.finditer(text):
        window = text[max(0, m.start() - 90): m.end() + 90]
        for cand in _APPOINTEE_NAME.findall(window):
            if _same_person(cand, person_name):
                return True
    return False


_ROLE_RE = re.compile(
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[,\-—|]\s*"
    r"((?:Chief[\w\s]*Officer|C[EFTOM]O|President|Founder|Co-?founder|"
    r"(?:VP|Vice President|Head|Director|Manager)(?:\s+of\s+[\w\s]+)?))",
    re.I,
)


def _speaker_label(card: SignalCard) -> str | None:
    """Who to credit. The byline wins; _extract_speaker is the fallback for cards
    that carry no bio block (news, transcripts)."""
    author = _post_author(card)
    if author:
        return f"{author[0]}, {author[1]}" if author[1] else author[0]
    return _extract_speaker(card)


def _extract_speaker(card: SignalCard) -> str | None:
    """Best-effort 'Name, Role' from the claim/title, so the drafter can say
    whose words these are instead of implying they are the recipient's."""
    m = _ROLE_RE.search(card.claim) or _ROLE_RE.search(card.snippet[:300])
    if m:
        return f"{m.group(1).strip()}, {m.group(2).strip()}"
    return None


# Lead-database and org-chart hosts. A scraped row in a contact database is not
# the person speaking, however prominently their name sits in the title. Typed
# "person_mention" by the fetcher, these were landing on `attributed` and taking
# the 3x proximity weight that tier carries: a ShipMonk run led with a lead411
# row and an Instagram hire announcement while an 11-day-old news story sat
# three places below, and Devin Weil's own LinkedIn post sat below that.
_DIRECTORY_HOSTS = (
    "zoominfo.com", "rocketreach.co", "lead411.com", "datanyze.com", "theorg.com",
    "seamless.ai", "apollo.io", "lusha.com", "signalhire.com", "contactout.com",
    "leadiq.com", "success.ai", "equilar.com", "owler.com", "pitchbook.com",
    "clearbit.com", "hunter.io", "snov.io", "uplead.com", "adapt.io",
    "crunchbase.com", "peopledatalabs.com",
)


def _is_directory_row(card: SignalCard) -> bool:
    url = (card.source_url or "").lower()
    # A post is authored content wherever it sits, so it is never a directory row.
    if "/posts/" in url:
        return False
    # The same LinkedIn profile arrived twice on one run: Exa typed it "profile"
    # and Tavily typed it "person_mention", so one copy scored as a database row
    # and the other as person-tier evidence. The URL is what decides, not the
    # fetcher that happened to find it.
    if "linkedin.com/in/" in url:
        return True
    return any(h in url for h in _DIRECTORY_HOSTS)


def _compute_proximity(card: SignalCard, prospect: Prospect | None = None) -> Literal["authored", "colleague_authored", "attributed", "company_action", "database"]:
    person_name = prospect.person_name if prospect else ""

    # Checked before tier: a directory row is a directory row whatever the
    # fetcher tagged it, and the whole point of the tier is proximity to the
    # person's own voice.
    if _is_directory_row(card):
        return "database"

    if card.tier == "person":
        if card.signal_type == "social":
            # Authored means AUTHORED. If the prospect is not in the content, this
            # is somebody else at the company talking -- still real evidence, but
            # it is their voice, not the prospect's.
            if person_name and not _is_prospect_authored(card, person_name):
                return "colleague_authored"
            return "authored"
        if card.signal_type == "profile":
            # Exa tags both /in/ profiles and /posts/ under "profile". The first is
            # a directory row; the second is the prospect writing in their own
            # words, which is the strongest evidence this product can find. Devin
            # Weil's post about operational focus at ShipMonk was being scored as
            # database-tier alongside his ZoomInfo entry.
            if "/posts/" in (card.source_url or "").lower():
                if person_name and not _is_prospect_authored(card, person_name):
                    return "colleague_authored"
                return "authored"
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
    """Age in days, or None when the source gave us no usable date.

    Two formats arrive here. Exa sends ISO 8601. Google News RSS sends RFC 822
    ("Tue, 04 Aug 2026 07:00:00 GMT"), which fromisoformat cannot read -- so
    parsing ISO alone left every news card undated, and a silent
    `except: return None` hid it.

    That cost real hooks. Undated cards take the worst multiplier in
    _pre_score, so all six GoogleNewsRSS cards fell outside card_cap and were
    never scored. Worse, the recency_reserve promotion below filters on
    `is not None`, so the guard written to stop precisely this could not see
    them. A ShipBob run led with a 2021 funding round while a three-week-old
    product launch sat in the rejected pile.
    """
    if not published_date:
        return None
    raw = str(published_date).strip()
    # Several fetchers store the string "None" rather than the value.
    if not raw or raw.lower() in ("none", "null"):
        return None

    dt = None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (_now() - dt).days)


# How hard to push down a card whose evidence never names the prospect's company.
# A penalty, not a veto: a genuine post by the prospect that omits their employer
# is exactly the case this must not kill, so it stays in the running and keeps its
# flag on the decision card. It just stops beating cards that ARE about them.
NAMESAKE_PENALTY = 0.35

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
    raw = (prospect.company or "").lower().strip()
    if not raw:
        return True
    hay = f"{card.claim} {clean_snippet(card.snippet)[:500]} {card.source_url or ''}".lower()

    # The whole name, as a phrase, always counts.
    if raw and raw in hay:
        return True
    # ...and with punctuation and spacing removed, so "Midwest 3PL" matches
    # "midwest3pl.com" and "C.H. Robinson" matches "CH Robinson".
    squashed = re.sub(r"[^a-z0-9]+", "", raw)
    if squashed and squashed in re.sub(r"[^a-z0-9]+", "", hay):
        return True

    tokens = [t for t in re.split(r"[^a-z0-9]+", raw)
              if len(t) >= 4 and t not in _COMPANY_NOISE]
    if not tokens:
        return True

    # One significant token is not an identification when that token is a common
    # word. "Midwest 3PL" reduces to "midwest" ("3pl" is too short to keep), and
    # a C.H. Robinson press release that says "midwest" anywhere passed the check
    # -- which is how a CFO at Midwest 3PL got drafted an email about somebody
    # else's acquisition. With a single token, require it in the claim, where a
    # match means the card is titled about them rather than merely adjacent.
    if len(tokens) == 1:
        return tokens[0] in card.claim.lower()

    # Every token, not any of them. The single-token path above was hardened after
    # the C.H. Robinson incident and this branch was left as `any`, which fails for
    # exactly the same reason one word ahead: a two-word company whose second word
    # names its industry matches every page in that industry. "Northwind Freight"
    # reduces to ('northwind', 'freight'), so "Freight invoice reconciliation in
    # SAP" and "3PL freight reconciliation" both identified it.
    #
    # Measured 2026-09-02 on live retrieval for a company that does not exist:
    # 20 of 21 cards passed under `any`, 1 under `all` -- and that one is a real
    # Northwind Freight Systems in Ontario, which is a genuine namesake rather
    # than noise and is precisely what the flag is for. Cost on real prospects is
    # one card each on Modern Treasury and Payouts Network, none on the
    # single-token names.
    #
    # Known limit: a long corporate name is harder to satisfy, so a card naming
    # "Merrill Lynch" would not identify a prospect entered as "Bank of America
    # Merrill Lynch". The exact phrase and its squashed form are both checked
    # above, this only downweights rather than excluding outside strict mode, and
    # no such prospect has been run. Revisit with data, not in anticipation.
    return all(t in hay for t in tokens)


def _compute_relevance(pain_score: float, proximity: str, recency_days: int | None, prox_val: dict,
                       voice: bool = False) -> float:
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
    # Never applied to `authored`, which is already the ceiling. That keeps the
    # bonus incapable of pushing a third-party article past the prospect's own
    # post: 0.75 x 1.25 is still below 1.0.
    if voice and proximity != "authored":
        prox_mult *= VOICE_BONUS

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
                   hooks: list) -> tuple[RankedCard | None, float | None, list, object | None]:
    """Pick the winner from the shortlist, after the hooks have been articulated.

    Returns `(winning_card, winning_score, surviving_hooks, winning_hook)`.

    The fourth element exists because this is the ONLY scope that can bind a hook
    to a card correctly -- `shortlist` is in scope here and `hook_for` keys on
    identity. Callers that tried to recover it downstream had nothing but
    `card_index` and the wrong list to apply it to; see the warning below.

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
        return None, None, [], None

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
    win_final, win_card, win_hook = survivors[0]
    if win_card.recency_days is None:
        from zara.utils.config import load_value_prop
        try:
            margin = float(load_value_prop().get("ranker", {}).get("dated_preference_margin", 0.15))
        except Exception:
            margin = 0.15
        dated = [(f, c, h) for f, c, h in survivors if c.recency_days is not None]
        if dated and dated[0][0] >= win_final - margin:
            win_final, win_card, win_hook = dated[0]
            survivors = [dated[0]] + [x for x in survivors if x is not dated[0]]
    surviving_hooks = [h for _, _, h in survivors if h is not None]
    return win_card, win_final, surviving_hooks, win_hook


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
            # Scoped to the window the pain scorer sees, so the guardrail covers
            # what can realistically reach a draft. Matching the full page body made
            # a $250M funding story fire `never_reference: litigation` on boilerplate
            # buried far below the evidence -- the guardrail eating the signal it
            # was never aimed at, so the bound stays.
            #
            # Cleaned first, same as the scorer: 500 raw characters of a LinkedIn
            # card are mostly header and author bio, so the guardrail was reading
            # furniture instead of the post it is meant to police.
            lower_text = f"{card.claim} {clean_snippet(card.snippet)[:500]}".lower()
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
        # colleague_authored belongs here too. It makes the same unbacked
        # assertion -- "this evidence is about our prospect's company" -- and
        # leaving it out let a basketball interview win a logistics prospect:
        # _company_is_mentioned returned False, but the check never ran.
        # Every tier, not a chosen few. A company_action card about a DIFFERENT
        # company reads as plausible in a way the obvious junk does not: a live
        # run drafted "C.H. Robinson announced acquisition of DeSpir Logistics"
        # to a CFO at Midwest 3PL, and the verifier passed it clean because the
        # sentence is true. It is simply true about somebody else.
        # Checked before the namesake guard so the more specific reason is the one
        # rendered on the decision card.
        if not excluded and not guardrail_hit:
            if is_own_appointment(card, prospect.person_name if prospect else "", proximity):
                guardrail_hit = ("own appointment: this announces the recipient's own hire — "
                                 "relevant, and not a reason to write to them")

        if not excluded and not guardrail_hit:
            if not _company_is_mentioned(card, prospect):
                guardrail_hit = "possible namesake: the evidence does not fully name the company"

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
            attributed_to=_speaker_label(card) if proximity == "colleague_authored" else None,
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
            # Same bonus in the pre-score, or a quoted card gets cut by the top-10
            # cap before its relevance is ever computed.
            if prox != "authored" and quotes_prospect(card, prospect.person_name if prospect else ""):
                prox_mult *= VOICE_BONUS
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
                # clean_snippet, not the raw text. The drafter and the hook prompt
                # were fixed in 4f8bc46; this call -- the one that decides which
                # cards survive at all -- was left reading Exa's generated header
                # and the author's bio block, roughly 290 of the 500 characters on
                # a LinkedIn card. Cards were being scored on furniture.
                for i, card in chunk:
                    prompt += f"[{i}] {clean_snippet(card.snippet)[:500]}\n\n"
                    
                resp = await generate_content_with_retry(
                    prompt=prompt,
                    schema=BatchScoreOutput,
                    system_instruction=sys_prompt,
                    stage="ranker_pain_scoring",
                )
                
                scores = resp.scores
                for s in scores:
                    if s.index in ranked_cards_map:
                        rc = ranked_cards_map[s.index]
                        if s.matched_pain_id and s.score > 0:
                            pm = PainMatch(pain_id=s.matched_pain_id, score=s.score, reason=s.reason)
                            final_score = s.score
                            if rc.guardrail_hit:
                                final_score = round(s.score * 0.5, 4)
                                
                            relevance = _compute_relevance(
                                final_score, rc.proximity, rc.recency_days, prox_val,
                                voice=quotes_prospect(rc.card, prospect.person_name),
                            )
                            # The docstring on _company_is_mentioned promised this
                            # downweight; nothing applied it, so the flag was decoration.
                            # A card that never names the company outscored every card
                            # that did, and a CFO at Midwest 3PL got an email about
                            # C.H. Robinson acquiring DeSpir Logistics. True sentence,
                            # wrong company, verifier clean.
                            if rc.guardrail_hit and rc.guardrail_hit.startswith("possible namesake"):
                                relevance *= NAMESAKE_PENALTY
                            ranked_cards_map[s.index] = RankedCard(
                                card=rc.card, pain_match=pm, proximity=rc.proximity,
                                recency_days=rc.recency_days, score=relevance, excluded=None,
                                guardrail_hit=rc.guardrail_hit, attributed_to=rc.attributed_to
                            )
                        else:
                            # B2: pain_match is None must contribute pain_score 0.0, as it already does.
                            relevance = _compute_relevance(0.0, rc.proximity, rc.recency_days, prox_val)
                            ranked_cards_map[s.index] = RankedCard(
                                card=rc.card, pain_match=None, proximity=rc.proximity,
                                recency_days=rc.recency_days, score=relevance, excluded="matches no pain in value_prop",
                                guardrail_hit=rc.guardrail_hit, attributed_to=rc.attributed_to
                            )
                
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

    # In strict mode a card whose evidence never names the company cannot WIN.
    # The downweight alone was not enough: hook strength multiplies the score, and
    # a meaty acquisition story out-argued a thin but correct card by 0.009. So a
    # CFO at Midwest 3PL kept getting an email about C.H. Robinson buying DeSpir
    # Logistics -- a true sentence about the wrong company, which the verifier
    # passes because it is checking grounding, not identity.
    #
    # Permissive mode keeps the old downweight-only behaviour (Compass IV and X:
    # infer structurally, label it, never hard-block). And nothing is dropped from
    # the decision card either way -- these still render under "What it rejected"
    # carrying their flag, which is the difference between "we looked and set this
    # aside" and "we never looked".
    if strictness != "permissive":
        named = [c for c in eligible
                 if not (c.guardrail_hit or "").startswith("possible namesake")]
        if named:
            eligible = named

        # A lead-database row cannot be the hook either. "Your profile notes a
        # career that began in public accounting" is true, and it is also just a
        # scrape of a directory page read back to the person it describes: no
        # event, no reason to write today. When a company genuinely has nothing,
        # the honest output is the no-signal path and the banner that comes with
        # it, not a hook manufactured from a contact record.
        # An announcement of the recipient's own hire cannot be the hook. Unlike the
        # two filters around it this one drops to the honest empty set rather than
        # keeping its cards: if the only thing we found about someone is that they
        # got the job, we have no reason to write, and the no-signal path says so.
        not_own = [c for c in eligible
                   if not (c.guardrail_hit or "").startswith("own appointment")]
        eligible = not_own

        real = [c for c in eligible if c.proximity != "database"]
        if real:
            eligible = real
        else:
            eligible = []

    eligible.sort(key=lambda x: (x.score, _tiebreak(x.card)), reverse=True)
    shortlist = eligible[:int(vp.get("ranker", {}).get("hook_shortlist", 4))]

    hooks = await _articulate_hooks(prospect, shortlist, vp)

    winning_card, winning_score, final_hooks, winning_hook = _select_winner(final_cards, shortlist, hooks)

    # Compass I: degrade, but never silently. Both repaired seed runs land at ~0.30
    # -- the pick is right and the evidence is still thin, and the reviewer is told
    # so on the output's face rather than having to open the audit trail.
    signal_quality = "thin" if winning_score is not None and winning_score < THIN_SIGNAL_FLOOR else "ok"

    return RankedProspect(
        prospect=prospect, cards=final_cards, icp_fit=icp_fit,
        winning_card=winning_card, winning_score=winning_score, signal_quality=signal_quality,
        hooks=final_hooks, winning_hook=winning_hook, icp_notes=icp_notes
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
        prompt += f"\n[{idx}] ({age}) {clean_snippet(c.card.snippet)}\n"
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
