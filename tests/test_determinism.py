"""Same input, same output.

Card order used to come from fetcher *completion* order: `_gather_results`
appended inside `_run_one` under `asyncio.gather`, so a slow fetcher landed last.
Every sort in the ranker is a stable `list.sort`, so that order survived into the
15-card hard cap and the winning-card pick -- meaning the same prospect could
yield a different hook, draft and verifier verdict with no code change at all.

That is not a cosmetic bug: it makes "did my change help?" unanswerable, which is
the whole point of the stress log.
"""
import asyncio
import pytest

from zara.models import Prospect, SignalCard, SourceResult, RankedCard
from zara.orchestrator import _gather_results
from zara.ranker import _tiebreak, _select_winner


def _card(source: str, url: str) -> SignalCard:
    return SignalCard(
        claim=f"claim from {source}", signal_type="news", source_url=url,
        published_date=None, snippet=f"snippet from {source}",
        tier="company", source=source,
    )


class _SlowFetcher:
    """Fetcher whose latency is the opposite of its declaration order."""

    def __init__(self, name: str, delay: float):
        self.name, self.delay, self.rung = name, delay, 0

    async def fetch(self, prospect):
        await asyncio.sleep(self.delay)
        return SourceResult(
            source=self.name, rung=0, status="ok", reason=None,
            cards=[_card(self.name, f"https://{self.name}.example/1")],
            cost_usd=0.0, elapsed_ms=int(self.delay * 1000),
        )


@pytest.mark.asyncio
async def test_gather_preserves_declaration_order_not_completion_order():
    # Declared fast->slow->faster; if results follow completion the order inverts.
    fetchers = [_SlowFetcher("alpha", 0.06), _SlowFetcher("beta", 0.01), _SlowFetcher("gamma", 0.03)]
    prospect = Prospect("Test", "Test Co")

    results: list[SourceResult] = []
    await _gather_results([(f, f.fetch(prospect)) for f in fetchers], results)

    assert [r.source for r in results] == ["alpha", "beta", "gamma"], (
        "results must follow fetcher declaration order; completion order would give "
        "beta, gamma, alpha"
    )


@pytest.mark.asyncio
async def test_gather_order_is_identical_across_repeated_runs():
    prospect = Prospect("Test", "Test Co")
    orders = []
    for _ in range(3):
        fetchers = [_SlowFetcher("alpha", 0.05), _SlowFetcher("beta", 0.01), _SlowFetcher("gamma", 0.02)]
        results: list[SourceResult] = []
        await _gather_results([(f, f.fetch(prospect)) for f in fetchers], results)
        orders.append([r.source for r in results])
    assert orders[0] == orders[1] == orders[2]


def test_tiebreak_makes_a_tied_sort_independent_of_input_order():
    """The winning-card sort keys on (final, _tiebreak) and ties are common."""
    cards = [_card("apify", "https://a.example/1"),
             _card("exa", "https://b.example/2"),
             _card("news", "https://c.example/3")]

    def winner(seq):
        rcs = []
        for c in seq:
            rcs.append(RankedCard(card=c, pain_match=None, proximity="company_action", recency_days=None, score=0.5, excluded=None))
        win, _, _ = _select_winner(rcs, rcs, [])
        return win.card.source

    assert winner(cards) == winner(list(reversed(cards))) == winner([cards[1], cards[2], cards[0]])


def test_empty_hooks_does_not_break_winner_selection():
    """_articulate_hooks returns [] on failure BY DESIGN, so selection must survive it.

    Making the winner depend on hook strength would convert a deliberate soft
    degradation into a hard failure: no winner, and a run with perfectly good
    cards reporting `no_signal`.
    """
    c = _card("apify", "https://a.example/1")
    rc = RankedCard(card=c, pain_match=None, proximity="company_action", recency_days=None, score=0.5, excluded=None)
    win, final, final_hooks = _select_winner([rc], [rc], [])
    assert win is not None
    assert win.card.source == "apify"
    assert final == 0.5, "with no hooks, final must fall back to raw relevance"
    assert len(final_hooks) == 0


def test_hook_index_maps_through_the_shortlist_not_the_card_list():
    """HookProposal.card_index indexes the SHORTLIST, never final_cards.

    Regression: the first implementation rebuilt `eligible` from `final_cards`
    (original card order) and then looked hooks up by `enumerate` position, while
    card_index referred to the relevance-sorted shortlist. The two index spaces
    only coincide by luck, so hooks were attached to the wrong cards.
    """
    from zara.models import HookProposal

    low = RankedCard(card=_card("news", "https://n.example/1"), pain_match=None,
                     proximity="company_action", recency_days=None, score=0.20, excluded=None)
    high = RankedCard(card=_card("exa", "https://e.example/1"), pain_match=None,
                      proximity="company_action", recency_days=None, score=0.90, excluded=None)

    # final_cards in ARRIVAL order (low first); shortlist in RELEVANCE order (high first).
    final_cards = [low, high]
    shortlist = [high, low]

    # card_index 0 refers to `high` -- the first shortlist entry.
    hooks = [HookProposal(card_index=0, hook_text="h", rationale="r", bridge="b", strength=1.0)]

    win, final, _ = _select_winner(final_cards, shortlist, hooks)
    assert win is high, "hook 0 must map to shortlist[0], not final_cards[0]"
    assert final == pytest.approx(0.90), "full-strength hook must not discount its own card"

def test_tiebreak_is_total_for_distinct_cards():
    """A tiebreak that collides still leaves arrival order deciding."""
    cards = [_card("apify", "https://a.example/1"),
             _card("apify", "https://a.example/2"),
             _card("exa", "https://a.example/1")]
    assert len({_tiebreak(c) for c in cards}) == len(cards)


def test_verifier_candidate_order_is_stable():
    """pass1 used a set, whose iteration order varies with PYTHONHASHSEED, so the
    ungrounded list -- and thus the drafter's self-correction prompt -- shifted
    between processes."""
    from zara.verifier import pass1_grounding
    from zara.models import RankedProspect

    rp = RankedProspect(
        prospect=Prospect("Ada Lovelace", "Analytical Engines"),
        cards=[], icp_fit="unknown", winning_card=None,
    )
    draft = ('Hi Ada Lovelace, I saw Analytical Engines raised $4.2M and that Charles Babbage '
             'said "the engine is ready" at https://example.com/news today.')
    runs = [pass1_grounding(draft, rp, {}) for _ in range(5)]
    assert all(r == runs[0] for r in runs), "ungrounded token order must be stable"

