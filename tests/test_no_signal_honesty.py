"""The no-signal path must announce itself, and a retired source must say so.

Both are Compass I ("degrade, never refuse -- but never silently") and Compass VII
("found nothing" is not "could not look"). Neither is observable from the run store,
so they need their own guard: a no-signal draft that looks identical to a grounded
one is the single failure this project's thesis cannot survive.
"""
import pytest

from zara.models import Prospect, SignalCard, RankedCard, RankedProspect, DraftResult, SourceResult
from zara.orchestrator import _retired_source_results, RETIRED_SOURCES, RETIRED_REASON
from zara.s2 import render_decision_card


def _card():
    return SignalCard(
        claim="Acme names new CFO", signal_type="news", source_url="https://x.test/1",
        published_date=None, snippet="Acme has appointed a new CFO.", tier="company",
        source="GoogleNewsRSS",
    )


def _draft_result(winning, generic):
    ranked = RankedProspect(
        prospect=Prospect("Dana Lee", "Acme"),
        cards=[], icp_fit="unknown", winning_card=winning,
    )
    return DraftResult(
        ranked_prospect=ranked, draft_text="Hi Dana, ...", verification=None,
        claim_strength="no_signal" if winning is None else "company_action",
        offer_is_generic=generic,
    )


def test_offer_is_generic_defaults_false():
    """The flag must be opt-in. A default of True would label every grounded draft."""
    assert DraftResult(
        ranked_prospect=RankedProspect(prospect=Prospect("A", "B"), cards=[], icp_fit="unknown", winning_card=None),
        draft_text=None, verification=None, claim_strength="no_signal",
    ).offer_is_generic is False


def test_decision_card_announces_a_generic_offer():
    md = render_decision_card(_draft_result(None, True), [])
    assert "NO PROSPECT-SPECIFIC SIGNAL FOUND" in md
    assert "Human judgment required before sending" in md


def test_decision_card_stays_quiet_when_the_draft_is_grounded():
    rc = RankedCard(card=_card(), pain_match=None, proximity="company_action",
                    recency_days=None, score=0.5, excluded=None)
    md = render_decision_card(_draft_result(rc, False), [])
    assert "NO PROSPECT-SPECIFIC SIGNAL FOUND" not in md


def test_retired_sources_are_skipped_with_a_reason_not_empty():
    """`empty` would read as 'we looked and found no jobs'. We did not look."""
    rows = _retired_source_results()
    assert {r.source for r in rows} == set(RETIRED_SOURCES)
    for r in rows:
        assert r.status == "skipped", f"{r.source} must be skipped, not {r.status}"
        assert r.reason == RETIRED_REASON
        assert r.cards == []
        assert r.cost_usd == 0.0


def test_retired_rows_survive_the_sourceresult_invariants():
    """SourceResult.__post_init__ rejects a non-ok row with no reason."""
    for r in _retired_source_results():
        SourceResult(source=r.source, rung=r.rung, status=r.status, reason=r.reason,
                     cards=[], cost_usd=0.0, elapsed_ms=0)
