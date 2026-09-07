"""The gate that decides WHICH cards get scored must agree with the scoring.

Two defects, both found on 2026-09-07 while comparing a live Nium run against
independent research.

1. `_pre_score` carried its own copy of the four-bucket step curve that a6be978
   replaced everywhere else. So admission believed a 2019 card was worth 0.75
   while `_compute_relevance` believed 0.023, and the ten scarce slots kept going
   to cards the scorer would then bury.

2. Unifying the curve is a real tightening for UNDATED cards (0.8 -> 0.236), and
   the person-tier material worth having -- interviews, quoted articles, most of
   what Tavily and Parallel return -- usually arrives undated. Without a reserve
   that can see them, fixing (1) makes the person tier worse.

Worth knowing when reading these: the two person-reserve tests do NOT fail
against the pre-2026-09-07 code, because the old buckets were generous to undated
cards (0.8) and an undated interview beat fresh company news on merit. They fail
when the curve is unified and the reserve is removed. They guard the interaction
between the two changes, which is the thing that would silently regress.

No model calls: admission is deterministic code, and it was the deterministic
code that was wrong.
"""
import asyncio
import re

import pytest

from zara.models import Prospect, SignalCard, SourceResult
from zara.ranker import recency_multiplier


def _card(claim, snippet, *, url="https://example.com/a", date=None,
          tier="company", stype="news"):
    return SignalCard(claim=claim, signal_type=stype, source_url=url,
                      published_date=date, snippet=snippet, tier=tier,
                      source="TestSource")


def _shortlist(prospect, cards, monkeypatch):
    """The snippets that actually reached the pain scorer, in order."""
    import zara.ranker as ranker

    seen = {}

    async def fake(prompt, schema, system_instruction, stage="unknown"):
        if stage == "ranker_pain_scoring":
            seen["prompt"] = prompt
        raise RuntimeError("stop after shortlist")

    monkeypatch.setattr(ranker, "generate_content_with_retry", fake)
    results = [SourceResult(source="TestSource", rung=0, status="ok", reason=None,
                            cards=cards, cost_usd=0.0, elapsed_ms=1)]
    try:
        asyncio.run(ranker.rank_prospect(prospect, results))
    except RuntimeError as e:
        if "stop after shortlist" not in str(e):
            raise
    body = seen.get("prompt", "").split("Cards:", 1)[-1]
    return body


# --------------------------------------------------------------------------
# 1. One curve, one opinion about age.
# --------------------------------------------------------------------------

def test_the_presort_uses_the_same_recency_curve_as_scoring(monkeypatch):
    """A five-year-old card must not hold a slot against a fresh one. Under the
    old local buckets both sat inside 0.75-1.0 and proximity decided everything;
    the shared curve puts five years at roughly 0.03."""
    import zara.ranker as ranker

    prospect = Prospect("Sean Henry", "Stord")
    ancient = [
        _card(f"Stord ancient item {i}",
              f"MARKER_ANCIENT_{i} Stord announced something in 2021.",
              url=f"https://www.stord.com/a{i}", date="2021-01-05T00:00:00Z")
        for i in range(12)
    ]
    fresh = _card("Stord launches new settlement rail",
                  "MARKER_FRESH Stord launched a new settlement rail this month.",
                  url="https://www.stord.com/fresh", date="2026-08-20T00:00:00Z")

    body = _shortlist(prospect, ancient + [fresh], monkeypatch)
    assert "MARKER_FRESH" in body, "a fresh card lost its slot to five-year-old ones"


def test_no_second_recency_curve_survives_in_the_ranker():
    """The duplicate buckets are the defect. If they come back, so does the
    disagreement between what gets admitted and what gets scored."""
    import inspect

    import zara.ranker as ranker

    src = inspect.getsource(ranker.rank_prospect)
    assert "rec_mult = 0.8" not in src, (
        "_pre_score has grown its own recency curve again; it must call "
        "recency_multiplier so admission and scoring cannot disagree"
    )


def test_undated_is_treated_the_same_way_in_both_places():
    """The pre-sort gave undated 0.8 while scoring gave it 0.236. Whatever the
    value, there must be exactly one of it."""
    assert recency_multiplier(None) == pytest.approx(0.5 ** (760.0 / 365.0), abs=1e-6)


# --------------------------------------------------------------------------
# 2. The person tier gets a slot it cannot be crowded out of.
# --------------------------------------------------------------------------

def _crowd_of_fresh_company_news(n=12):
    return [
        _card(f"Stord company item {i}",
              f"MARKER_CO_{i} Stord announced a new fulfilment centre this week.",
              url=f"https://www.stord.com/news{i}", date="2026-08-25T00:00:00Z")
        for i in range(n)
    ]


def test_an_undated_person_card_survives_a_flood_of_fresh_company_news(monkeypatch):
    """The Nium case. Fresh dated company press releases fill both the merit head
    and the recency reserve, and an undated interview -- the thing this product
    exists to lead with -- never reaches the scorer."""
    prospect = Prospect("Sean Henry", "Stord")
    interview = _card(
        "Sean Henry on why reconciliation breaks late",
        'MARKER_INTERVIEW Henry said "the moment you settle across two systems, '
        'the break shows up days later and nobody owns it" in the interview.',
        url="https://www.fintechtimes.com/sean-henry-interview",
        tier="person", stype="person_mention", date=None)

    body = _shortlist(prospect, _crowd_of_fresh_company_news() + [interview],
                      monkeypatch)
    assert "MARKER_INTERVIEW" in body, (
        "an undated person-tier card was cut by fresh company news; the person "
        "reserve is not holding a slot"
    )


def test_the_person_reserve_does_not_spend_its_slot_on_a_directory_row(monkeypatch):
    """Measured on the Episode Six snapshot: ordering the reserve by the blended
    pre-score put a 33-day-old LinkedIn directory row (proximity `database`)
    above her actual recorded interview, and the interview was cut. A listing
    that a person exists is not that person on the record."""
    prospect = Prospect("Sean Henry", "Stord")
    directory = _card(
        "Sean Henry", "MARKER_DIRECTORY Sean Henry, Chief Executive Officer at Stord.",
        url="https://www.linkedin.com/in/seanhenry", tier="person",
        stype="person_mention", date="2026-08-25T00:00:00Z")
    interview = _card(
        "Sean Henry on why reconciliation breaks late",
        'MARKER_INTERVIEW Henry said "the moment you settle across two systems, '
        'the break shows up days later and nobody owns it" in the interview.',
        url="https://www.fintechtimes.com/sean-henry-interview",
        tier="person", stype="person_mention", date=None)

    body = _shortlist(prospect, _crowd_of_fresh_company_news() + [directory, interview],
                      monkeypatch)
    assert "MARKER_INTERVIEW" in body, (
        "the person reserve was spent on a directory row instead of on evidence"
    )


def test_the_reserves_are_configuration_not_hidden_defaults():
    """They decide half the shortlist. This repo's own rule is that a constant
    which changes the answer belongs in value_prop.yaml where it can be argued
    with, not in a `.get(..., 3)` fallback."""
    from zara.utils.config import load_value_prop

    ranker_cfg = load_value_prop().get("ranker", {})
    for key in ("card_cap", "recency_reserve", "person_reserve", "hook_shortlist"):
        assert key in ranker_cfg, f"{key} is not stated in value_prop.yaml"

    # The head is what is still decided on merit. If the reserves ever grow to
    # consume most of the cap, the pre-score has stopped being the thing that
    # chooses and nobody will notice from the outside.
    head = ranker_cfg["card_cap"] - ranker_cfg["recency_reserve"] - ranker_cfg["person_reserve"]
    assert head >= ranker_cfg["card_cap"] // 2, (
        f"reserves take {ranker_cfg['card_cap'] - head} of {ranker_cfg['card_cap']} "
        "slots; merit no longer decides the shortlist"
    )
