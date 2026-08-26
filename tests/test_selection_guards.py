"""Guards on WHICH card is allowed to become a hook.

Every case here comes from a live run on a real prospect (Stephanie Fielding at
Stord, 2026-08-26) in which the pipeline led with an undated "CFO Pros on the
Move" listicle and called someone three and a half years into the job the "new
finance chief" -- while six separate copies of that company's $250M funding
round were discarded before pain matching ever saw them.

These tests use no model calls. Card selection is deterministic code, and it was
the deterministic code that was wrong.
"""
import asyncio

import pytest

from zara.models import Prospect, SignalCard, SourceResult
from zara.ranker import _company_is_mentioned, _compute_relevance
from zara.verifier import _RECENCY_CLAIM

WEIGHTS = {"authored": 4, "attributed": 3, "colleague_authored": 2.5,
           "company_action": 2, "database": 1}


def _card(claim, snippet, *, url="https://example.com/a", date=None,
          tier="company", stype="news", source="TestSource"):
    return SignalCard(claim=claim, signal_type=stype, source_url=url,
                      published_date=date, snippet=snippet, tier=tier, source=source)


# --------------------------------------------------------------------------
# 1. Not knowing a date must not beat knowing an inconvenient one.
# --------------------------------------------------------------------------

def test_undated_ranks_below_every_known_age_under_two_years():
    """The undated multiplier sat at 0.9, above the 0.85 given to a card known to
    be up to two years old -- so absence of a date outranked presence of one."""
    undated = _compute_relevance(0.8, "company_action", None, WEIGHTS)
    for known_age in (0, 90, 180, 300, 700):
        assert undated < _compute_relevance(0.8, "company_action", known_age, WEIGHTS), (
            f"undated card outranks one known to be {known_age} days old"
        )


def test_undated_still_beats_a_genuinely_ancient_card():
    """Unknown is worse than recent, not worse than everything. A five-year-old
    card should still lose to one whose date we simply do not have."""
    assert (_compute_relevance(0.8, "company_action", None, WEIGHTS)
            > _compute_relevance(0.8, "company_action", 1883, WEIGHTS))


# --------------------------------------------------------------------------
# 2. Namesakes.
# --------------------------------------------------------------------------

def test_card_that_never_mentions_the_company_is_flagged():
    """Cards about Stephanie Neill (Stripe) and Stephanie Stollar (PhD) entered
    the Stord candidate pool as eligible and were merely outscored."""
    prospect = Prospect("Stephanie Fielding", "Stord")
    stranger = _card("Why AI Doesn't Replace Product Thinking: Stephanie Neill, Stripe",
                     "A conversation with Stephanie Neill of Stripe about product.",
                     url="https://youtube.com/watch?v=abc")
    assert not _company_is_mentioned(stranger, prospect)


def test_company_named_anywhere_in_the_evidence_counts():
    prospect = Prospect("Stephanie Fielding", "Stord")
    assert _company_is_mentioned(
        _card("Stord appoints CFO", "Atlanta-based Stord named a new finance chief."), prospect)
    # URL alone is enough -- a genuine post may not name the employer in its body.
    assert _company_is_mentioned(
        _card("An update from our founders", "We have news to share today.",
              url="https://www.stord.com/newsroom/update"), prospect)


def test_company_of_only_noise_words_never_flags():
    """"The Co" has no significant token; we cannot judge, so we must not accuse."""
    assert _company_is_mentioned(_card("x", "y"), Prospect("A Person", "The Co"))


# --------------------------------------------------------------------------
# 3. Guardrails scope to the evidence that can actually reach a draft.
# --------------------------------------------------------------------------

def _rank_capturing_shortlist(prospect, cards, monkeypatch):
    """Run the ranker far enough to see which cards reached pain scoring."""
    import zara.ranker as ranker

    captured = {}

    async def fake(prompt, schema, system_instruction, stage="unknown"):
        captured["prompt"] = prompt
        raise RuntimeError("stop after shortlist")

    monkeypatch.setattr(ranker, "generate_content_with_retry", fake)
    results = [SourceResult(source="TestSource", rung=0, status="ok", reason=None,
                            cards=cards, cost_usd=0.0, elapsed_ms=1)]
    try:
        asyncio.run(ranker.rank_prospect(prospect, results))
    except RuntimeError as e:          # our own sentinel, not a real failure
        if "stop after shortlist" not in str(e):
            raise
    return captured.get("prompt", "")


def test_guardrail_term_buried_in_page_boilerplate_does_not_veto(monkeypatch):
    """A $250M funding story was excluded as `never_reference: litigation` because
    the word appeared far below the evidence, in page furniture the model never
    sees. The guardrail now scopes to the first 500 chars, which is exactly what
    the pain scorer, the hook prompt and the drafter are shown."""
    prospect = Prospect("Sean Henry", "Stord")
    good_evidence = "Stord raised $250 million at a $3 billion valuation. " + ("x " * 300)
    card = _card("Stord raises $250M Series F",
                 good_evidence + " Read our terms: this is not a class action lawsuit notice.",
                 date="2026-05-26T00:00:00Z")
    prompt = _rank_capturing_shortlist(prospect, [card], monkeypatch)
    assert "Stord raised $250 million" in prompt, (
        "card was vetoed by a guardrail term outside the evidence window"
    )


def test_guardrail_term_inside_the_evidence_still_vetoes(monkeypatch):
    """The other half: scoping must not defang the guardrail where it matters."""
    prospect = Prospect("Sean Henry", "Stord")
    card = _card("Stord faces class action",
                 "Stord is the subject of a class action lawsuit filed this week.",
                 date="2026-05-26T00:00:00Z")
    prompt = _rank_capturing_shortlist(prospect, [card], monkeypatch)
    assert "class action" not in prompt, "a real litigation card reached the ranker"


# --------------------------------------------------------------------------
# 4. The freshest dated news cannot be crowded out entirely.
# --------------------------------------------------------------------------

def test_fresh_dated_news_survives_a_pool_of_higher_proximity_cards(monkeypatch):
    """Six copies of Stord's $250M round were cut as "outside the top 10 by
    proximity" before scoring. Reserved slots mean the newest dated card is
    scored even when an entire higher-proximity tier is competing."""
    prospect = Prospect("Stephanie Fielding", "Stord")
    crowd = [
        _card(f"Stord profile mention {i}",
              f"Stephanie Fielding of Stord is listed in directory entry {i}.",
              url=f"https://linkedin.com/in/person{i}", tier="person", stype="person_mention")
        for i in range(14)
    ]
    fresh = _card("Stord Raises $250M Series F at $3B",
                  "Stord raised $250 million in a Series F round at a $3 billion valuation.",
                  url="https://www.stord.com/newsroom/series-f",
                  date="2026-08-20T00:00:00Z")
    prompt = _rank_capturing_shortlist(prospect, crowd + [fresh], monkeypatch)
    assert "$250 million" in prompt, "the freshest dated card never reached pain scoring"


# --------------------------------------------------------------------------
# 5. "New CFO" is a time claim.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "New finance chief after eight years at Amazon.",
    "the new CFO of Stord",
    "Your incoming CFO starts Monday",
    "just appointed to the board",
    "takes over as head of finance",
])
def test_new_role_phrasing_is_a_recency_claim(text):
    assert _RECENCY_CLAIM.search(text), f"not caught as a time claim: {text}"


@pytest.mark.parametrize("text", [
    "We build a new ledger for you.",
    "adding new payment methods like FedNow and RTP",
    "new business units after the raise",
    "a new customer onboarding flow",
])
def test_ordinary_uses_of_new_are_not_recency_claims(text):
    assert not _RECENCY_CLAIM.search(text), f"false positive on: {text}"


# --------------------------------------------------------------------------
# 6. A near-tie breaks toward evidence we can date.
# --------------------------------------------------------------------------

def _ranked(score, recency, tier, claim):
    from zara.models import RankedCard, PainMatch
    return RankedCard(
        card=_card(claim, claim, date=None if recency is None else "2026-05-26T00:00:00Z",
                   tier=tier),
        pain_match=PainMatch(pain_id="structural_complexity", score=0.9, reason=claim),
        proximity="attributed" if recency is None else "company_action",
        recency_days=recency, score=score, excluded=None,
    )


def test_dated_card_wins_a_near_tie_against_an_undated_one():
    """The Stord numbers exactly: an undated listicle at 0.54 against a dated
    $250M funding round at 0.42. Proximity outweighs the undated penalty by more
    than weight tuning can close, so selection has to state the preference."""
    from zara.ranker import _select_winner

    undated = _ranked(0.54, None, "person", "New CFO appointment at Stord")
    dated = _ranked(0.42, 92, "company", "Stord raised $250M funding round")
    win, _, _ = _select_winner([undated, dated], [undated, dated], [])
    assert win is dated, "a dateless hook won a near-tie over dated evidence"


def test_undated_card_still_wins_when_it_leads_by_a_clear_margin():
    """A preference, not a veto. Sometimes the undated card really is all we have."""
    from zara.ranker import _select_winner

    undated = _ranked(0.80, None, "person", "CEO describes reconciliation pain")
    dated = _ranked(0.20, 92, "company", "Company opens a new office")
    win, _, _ = _select_winner([undated, dated], [undated, dated], [])
    assert win is undated


# --------------------------------------------------------------------------
# 7. Absence must not be rendered as a number.
# --------------------------------------------------------------------------

def test_zero_headcount_reads_as_unknown_not_as_a_measurement():
    """Apify returned employeeCount 0 for a company that plainly has employees,
    and the decision card printed "headcount 0 -- outside preferred 50-2000
    band" as though we had measured it."""
    from zara.ranker import _compute_icp_fit

    fit, notes = _compute_icp_fit([_card("Firmographics", "headcount: 0, sector: payments",
                                         stype="firmographic")], {})
    assert fit == "unknown"
    assert any("unknown" in n for n in notes), notes
    assert not any("outside preferred" in n for n in notes), (
        "a missing headcount was reported as an ICP deviation"
    )
