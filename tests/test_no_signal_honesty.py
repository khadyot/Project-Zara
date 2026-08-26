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
        ranked_prospect=ranked, subject="Subject", draft_text="Hi Dana, ...", verification=None,
        claim_strength="no_signal" if winning is None else "company_action",
        offer_is_generic=generic,
    )


def test_offer_is_generic_defaults_false():
    """The flag must be opt-in. A default of True would label every grounded draft."""
    assert DraftResult(
        ranked_prospect=RankedProspect(prospect=Prospect("A", "B"), cards=[], icp_fit="unknown", winning_card=None),
        subject=None, draft_text=None, verification=None, claim_strength="no_signal",
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


# --- the no-signal path must be verified, not waved through --------------------
# verify_draft used to `return passed=True` whenever winning_card was None, so the
# draft with NO evidence got NO grounding check -- the inversion of the gate. It
# shipped "companies typically see a 30% cut in processing time" in strict mode,
# on the one path where the model has nothing to work from and is most likely to
# invent. Found by driving a genuinely thin prospect through the pipeline.

import yaml
import pytest

from zara.verifier import pass1_grounding, build_evidence_list


@pytest.fixture
def vp():
    with open("value_prop.yaml") as f:
        return yaml.safe_load(f)


def _no_signal_prospect():
    return RankedProspect(
        prospect=Prospect("Riley Chen", "Northwind Freight", title="CFO"),
        cards=[], icp_fit="unknown", winning_card=None,
    )


FABRICATED = ("Hi Riley,\n\nMany freight operators face reconciliation drag. Companies that "
              "adopt our solution typically see a 30% cut in processing time.\n\nBest,\nZamp")
HONEST = ("Hi Riley,\n\nMany freight operators carry reconciliation work that eats the "
          "month-end close. We automate those manual matching steps. Worth a short "
          "conversation?\n\nBest,\nZamp")


def test_invented_metric_is_caught_on_the_no_signal_path(vp):
    assert "30" in pass1_grounding(FABRICATED, _no_signal_prospect(), vp)


def test_honest_generic_copy_is_not_flagged(vp):
    """Generic framing is the point of this path. It must not read as fabrication."""
    assert pass1_grounding(HONEST, _no_signal_prospect(), vp) == []


# These two describe what happens WHEN a proof point is configured. They used to
# read it out of value_prop.yaml, which meant emptying that field -- the correct
# thing to do, since HANDOFF.md records proof_point as null deliberately -- broke
# them. A test of "how a configured proof point behaves" must configure one, not
# depend on production config holding a claim we do not want to ship.
SANCTIONED = "cut month-end close times by up to 30-40% without ripping out existing ERPs"


@pytest.fixture
def vp_with_proof_point(vp):
    return {**vp, "proof_point": SANCTIONED}


def test_proof_point_is_not_evidence_in_strict_mode(vp_with_proof_point):
    """Grounding is a substring test, so a sanctioned '30-40%' licenses any '30'.

    In strict mode the drafter is forbidden to use proof_point, so admitting it
    as evidence would license exactly the claim we told the model not to make.
    """
    strict = build_evidence_list(_no_signal_prospect(), vp_with_proof_point, strictness="strict")
    permissive = build_evidence_list(_no_signal_prospect(), vp_with_proof_point, strictness="permissive")
    assert SANCTIONED not in strict
    assert SANCTIONED in permissive


def test_permissive_mode_still_allows_the_sanctioned_proof_point(vp_with_proof_point):
    assert pass1_grounding(FABRICATED, _no_signal_prospect(), vp_with_proof_point,
                           strictness="permissive") == []


def test_shipped_config_carries_no_proof_point(vp):
    """The default must stay empty. An invented benchmark in config is the same
    defect as an invented benchmark in an email, one indirection earlier."""
    assert not (vp.get("proof_point") or "").strip(), (
        "value_prop.yaml has a proof_point again -- permissive mode will state it as fact"
    )
