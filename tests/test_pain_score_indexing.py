"""The pain scorer must attach each verdict to the card it was written about.

From the Prajit Nanu / Nium run, 2026-09-07. The prompt labelled every card with
its GLOBAL id and the model answered with POSITIONS, 0..n-1. The read-back did
`ranked_cards_map[s.index]`, and because a position is always a valid global id
the `in ranked_cards_map` guard could never fire -- it only ever caught
out-of-range.

Ten cards were sent (18, 8, 25, 26, 9, 30, 27, 2, 1, 15) and ten DIFFERENT cards
were scored (0-6, 8, 9, 10): six scored without being sent, five sent and never
scored. Every reason in the run log was correct for its position and wrong for
its card, which is why it read as coherent and survived two weeks. A US card
issuance launch, a textbook `silent_breaks` observable, was scored `general_news`
against a LinkedIn anniversary post.

These tests use no model calls.
"""
import asyncio

import pytest

from zara.models import Prospect, SignalCard, SourceResult


def _news(claim, snippet, date):
    return SignalCard(claim=claim, signal_type="news",
                      source_url="https://www.stord.com/newsroom/" + claim.split()[0].lower(),
                      published_date=date, snippet=snippet, tier="company",
                      source="TestSource")


def _rank_with_positional_scorer(prospect, cards, scores, monkeypatch):
    """Run the full ranker against a scorer that answers positionally, which is
    what the real model does. Returns (ranked_prospect, prompt_seen)."""
    import zara.ranker as ranker

    seen = {}

    async def fake(prompt, schema, system_instruction, stage="unknown"):
        if stage == "ranker_pain_scoring":
            seen["prompt"] = prompt
            return schema(scores=scores)
        # Hooks are articulated after scoring; this test is not about them.
        return schema(hooks=[])

    monkeypatch.setattr(ranker, "generate_content_with_retry", fake)
    results = [SourceResult(source="TestSource", rung=0, status="ok", reason=None,
                            cards=cards, cost_usd=0.0, elapsed_ms=1)]
    rp = asyncio.run(ranker.rank_prospect(prospect, results))
    return rp, seen.get("prompt", "")


def _reason_for(ranked, marker):
    """The pain reason attached to the card whose snippet carries `marker`."""
    for rc in ranked.cards:
        if marker in rc.card.snippet:
            return rc.pain_match.reason if rc.pain_match else None
    raise AssertionError(f"no card carrying {marker!r}")


# --------------------------------------------------------------------------
# The reordering is the whole point: the pre-sort means position != global id.
# --------------------------------------------------------------------------

def _three_cards_out_of_order():
    """A pool whose id space and position space cannot coincide.

    The leading card is ineligible, so it never enters the scoring chunk but does
    occupy global id 0. The remaining three are then reversed by the pre-sort. So
    global ids 1, 2, 3 arrive at the scorer as positions 2, 1, 0 -- no id equals
    its own position, and confusing the two spaces cannot pass by luck.
    """
    personal = SignalCard(
        claim="Sean Henry family photo", signal_type="social",
        source_url="https://example.com/personal", published_date="2026-08-25T00:00:00Z",
        snippet="MARKER_SKIP A personal post, out of scope for outreach.",
        tier="person", source="TestSource", eligibility="personal")
    return [
        personal,
        _news("Alpha reconciliation platform expands",
              "MARKER_OLD Stord opened a new ledger reconciliation office.",
              "2024-01-10T00:00:00Z"),
        _news("Bravo settlement partner added",
              "MARKER_MID Stord added a new settlement partner in Europe.",
              "2026-02-10T00:00:00Z"),
        _news("Charlie payment rail launched",
              "MARKER_NEW Stord launched a new payment rail this month.",
              "2026-08-20T00:00:00Z"),
    ]


def test_each_verdict_lands_on_the_card_it_describes(monkeypatch):
    """The regression itself. A scorer answering positionally must still have its
    verdicts land on the cards those verdicts were written about."""
    prospect = Prospect("Sean Henry", "Stord")
    cards = _three_cards_out_of_order()

    ranked, prompt = _rank_with_positional_scorer(
        prospect, cards,
        scores=[
            {"index": 0, "matched_pain_id": "silent_breaks", "score": 0.8,
             "reason": "VERDICT_NEW"},
            {"index": 1, "matched_pain_id": "silent_breaks", "score": 0.7,
             "reason": "VERDICT_MID"},
            {"index": 2, "matched_pain_id": "general_news", "score": 0.3,
             "reason": "VERDICT_OLD"},
        ],
        monkeypatch=monkeypatch,
    )

    # Guard the premise: the freshest card really is presented first, so global
    # id and position genuinely disagree. Without this the test could pass on a
    # pool the pre-sort happened to leave in order.
    assert prompt.index("MARKER_NEW") < prompt.index("MARKER_MID") < prompt.index("MARKER_OLD")

    assert _reason_for(ranked, "MARKER_NEW") == "VERDICT_NEW"
    assert _reason_for(ranked, "MARKER_MID") == "VERDICT_MID"
    assert _reason_for(ranked, "MARKER_OLD") == "VERDICT_OLD"


def test_the_card_labels_the_model_sees_are_positions(monkeypatch):
    """The contract stated in the prompt must be the one the read-back uses.
    Labelling with global ids while parsing positions is what broke."""
    prospect = Prospect("Sean Henry", "Stord")
    _, prompt = _rank_with_positional_scorer(
        prospect, _three_cards_out_of_order(),
        scores=[], monkeypatch=monkeypatch,
    )
    body = prompt.split("Cards:", 1)[1]
    # Three cards reach the chunk, and their global ids are 1, 2, 3. Labels must
    # be 0, 1, 2 -- the positions the model actually answers with.
    assert "[0]" in body, "cards are not labelled from 0, so a positional reply misreads"
    assert "[3]" not in body, "cards are still labelled with their global ids"


# --------------------------------------------------------------------------
# A reply that does not answer the question asked must not be absorbed.
# --------------------------------------------------------------------------

def test_scores_beyond_the_chunk_are_rejected(monkeypatch):
    """The Nium reply carried eleven scores for ten cards. Index 3 here is a real
    global id -- it is the freshest card -- but there is no position 3 in a chunk
    of three, so it describes nothing that was sent and must be dropped. This is
    exactly the case the old `in ranked_cards_map` guard could not see."""
    prospect = Prospect("Sean Henry", "Stord")
    ranked, _ = _rank_with_positional_scorer(
        prospect, _three_cards_out_of_order(),
        scores=[
            {"index": 0, "matched_pain_id": "silent_breaks", "score": 0.8,
             "reason": "VERDICT_NEW"},
            {"index": 3, "matched_pain_id": "close_drag", "score": 0.9,
             "reason": "VERDICT_PHANTOM"},
        ],
        monkeypatch=monkeypatch,
    )
    reasons = [rc.pain_match.reason for rc in ranked.cards if rc.pain_match]
    assert "VERDICT_PHANTOM" not in reasons
    assert "VERDICT_NEW" in reasons


def test_a_repeated_index_does_not_overwrite_the_first_verdict(monkeypatch):
    """A model that loses its place repeats an index. Taking the later one would
    replace a real match with whatever came after it."""
    prospect = Prospect("Sean Henry", "Stord")
    ranked, _ = _rank_with_positional_scorer(
        prospect, _three_cards_out_of_order(),
        scores=[
            {"index": 0, "matched_pain_id": "silent_breaks", "score": 0.8,
             "reason": "VERDICT_FIRST"},
            {"index": 0, "matched_pain_id": "general_news", "score": 0.3,
             "reason": "VERDICT_SECOND"},
        ],
        monkeypatch=monkeypatch,
    )
    assert _reason_for(ranked, "MARKER_NEW") == "VERDICT_FIRST"


def test_a_card_the_scorer_ignored_is_labelled_not_silently_eligible(monkeypatch):
    """Compass VII. A card we sent and got no verdict for is not a card that
    scored zero. Unlabelled it keeps excluded=None and score=0.0 from
    construction, which leaves it eligible to be picked as a winner."""
    prospect = Prospect("Sean Henry", "Stord")
    ranked, _ = _rank_with_positional_scorer(
        prospect, _three_cards_out_of_order(),
        scores=[
            {"index": 0, "matched_pain_id": "silent_breaks", "score": 0.8,
             "reason": "VERDICT_NEW"},
        ],
        monkeypatch=monkeypatch,
    )
    for marker in ("MARKER_MID", "MARKER_OLD"):
        rc = next(c for c in ranked.cards if marker in c.card.snippet)
        assert rc.excluded == "scorer returned no verdict for this card", (
            f"{marker} was skipped by the scorer but is still eligible"
        )
