"""Regression: drafter must not crash when the winning card has no pain_match.

The ranker's pain-scoring LLM can omit a card's index from its response; that
card then stays eligible with pain_match=None and can win. drafter.py used to
dereference .pain_id unconditionally (AttributeError, live crash on the
Modern Treasury run 2026-08-25).
"""
import pytest
from unittest.mock import AsyncMock, patch

from zara.models import Prospect, SignalCard, RankedCard, RankedProspect
from zara.drafter import draft_email


def _winning_prospect(pain_match):
    card = SignalCard(
        claim="a claim", signal_type="news", source="Tavily",
        source_url="https://example.com/x", published_date=None,
        snippet="a snippet", tier="company",
    )
    win = RankedCard(
        card=card, pain_match=pain_match, proximity="company_action",
        recency_days=None, score=0.5, excluded=None, guardrail_hit=None,
        attributed_to=None,
    )
    return RankedProspect(
        prospect=Prospect(person_name="Dimitri", company="Modern Treasury"),
        cards=[win], icp_fit="ok", winning_card=win, hooks=[], icp_notes=[],
    )


VALUE_PROP = {
    "sender_name": "Zamp",
    "offer": "We automate reconciliation-heavy processes.",
    "pains": [{"id": "structural_complexity", "statement": "Reconciliation sprawl hurts."}],
}


@pytest.mark.asyncio
async def test_winning_card_without_pain_match_drafts():
    """pain_match=None on the winner must degrade, not crash."""
    prospect = _winning_prospect(pain_match=None)
    with patch("zara.drafter.generate_content_with_retry", new=AsyncMock()) as gen:
        from zara.drafter import DraftOutput
        gen.return_value = DraftOutput(subject="subject", draft_text="Hi Dimitri, ...")
        res = await draft_email(prospect, VALUE_PROP, strictness="strict")
    assert res.draft_text == "Hi Dimitri, ..."
    prompt = gen.call_args.kwargs["prompt"]
    assert "We don't know their specific pain yet" in prompt


@pytest.mark.asyncio
async def test_winning_card_with_pain_match_uses_pain_statement():
    """The normal path still resolves the pain statement from value_prop."""
    from zara.models import PainMatch
    prospect = _winning_prospect(
        pain_match=PainMatch(pain_id="structural_complexity", score=0.9, reason="r")
    )
    with patch("zara.drafter.generate_content_with_retry", new=AsyncMock()) as gen:
        from zara.drafter import DraftOutput
        gen.return_value = DraftOutput(subject="subject", draft_text="Hi Dimitri, ...")
        await draft_email(prospect, VALUE_PROP, strictness="strict")
    prompt = gen.call_args.kwargs["prompt"]
    assert "Reconciliation sprawl hurts." in prompt

@pytest.mark.asyncio
async def test_winning_card_with_hook_none_drafts():
    """hook=None must degrade, not crash."""
    prospect = _winning_prospect(pain_match=None)
    with patch("zara.drafter.generate_content_with_retry", new=AsyncMock()) as gen:
        from zara.drafter import DraftOutput
        gen.return_value = DraftOutput(subject="subject", draft_text="Hi Dimitri, ...")
        res = await draft_email(prospect, VALUE_PROP, strictness="strict", hook=None)
    assert res.draft_text == "Hi Dimitri, ..."
    prompt = gen.call_args.kwargs["prompt"]
    assert "EVIDENCE (the only facts you may use): a snippet" in prompt
