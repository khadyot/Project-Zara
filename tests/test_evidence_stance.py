"""The posture the email may take toward its evidence.

Written after a live run drafted "I imagine processing the myriad market signals
and aligning them with internal rates can become increasingly time-consuming" at
Ryan Petersen, who had that week announced his team cut ocean-freight pricing from
days to ten minutes. The signal was true and the inference was wrong, which is the
project's own "real-signal-wrong-inference" edge case -- and it was not a model
slip, it was the prompt: the pain sentence was mandatory whatever the evidence
said, so with nothing matched the writer filled a pain-shaped hole from the only
material present, the prospect's own announcement.
"""
import pytest
from unittest.mock import patch, AsyncMock

from zara.models import Prospect, SignalCard, RankedCard, RankedProspect, PainMatch
from zara.drafter import evidence_stance, draft_email, DraftOutput

VALUE_PROP = {
    "product": "We connect the systems finance and ops run on and match records across them",
    "sender_name": "Khadyot", "sender_person": "Khadyot", "sender_company": "Zamp",
    "cta": "a quick chat",
    "pains": [{"id": "linear_headcount", "statement": "Ops headcount scales with volume."}],
}


def _card(claim, signal_type="news", snippet="a snippet"):
    return RankedCard(
        card=SignalCard(claim=claim, signal_type=signal_type, source_url="https://x",
                        published_date=None, snippet=snippet, tier="person", source="s"),
        pain_match=None, proximity="authored", recency_days=10, score=0.3, excluded=None)


@pytest.mark.parametrize("claim,signal_type,pain_id,expected", [
    ("anything at all",                              "news",    "linear_headcount", "evidenced_pain"),
    ("Introducing AI-powered pricing for ocean freight.", "news", "general_news",   "achievement"),
    ("Flexport Launches Fulfillment Services in Canada",  "news", "general_news",   "achievement"),
    ("Zamp raises $30M to scale",                    "news",    None,               "achievement"),
    ("Series C closed",                              "funding", None,               "achievement"),
    ("some capability shipped",                      "product", None,               "achievement"),
    ("Ryan Petersen",                                "profile", "general_news",     "unevidenced"),
    ("Ryan Petersen on the Knowledge Project",       "news",    None,               "unevidenced"),
])
def test_stance_classification(claim, signal_type, pain_id, expected):
    pm = PainMatch(pain_id=pain_id, score=0.8, reason="r") if pain_id else None
    assert evidence_stance(_card(claim, signal_type), pm) == expected


def _prospect(claim, signal_type, pain_id):
    rc = _card(claim, signal_type)
    pm = PainMatch(pain_id=pain_id, score=0.8, reason="r") if pain_id else None
    rc = RankedCard(card=rc.card, pain_match=pm, proximity="authored", recency_days=27,
                    score=0.3, excluded=None)
    return RankedProspect(
        prospect=Prospect(person_name="Ryan", company="Flexport", title="CEO"),
        cards=[rc], icp_fit="unknown", winning_card=rc, winning_score=0.3,
        signal_quality="thin", hooks=[])


async def _prompt_for(rp):
    with patch("zara.drafter.generate_content_with_retry", new=AsyncMock()) as gen:
        gen.return_value = DraftOutput(subject="s", draft_text="Hi Ryan, ...")
        await draft_email(rp, VALUE_PROP, strictness="strict")
    return gen.call_args.kwargs["prompt"]


@pytest.mark.asyncio
async def test_achievement_never_calls_the_solved_thing_hard():
    """The regression that started this: do not tell someone their win is a burden."""
    prompt = await _prompt_for(
        _prospect("Introducing AI-powered pricing for ocean freight.", "product", "general_news"))
    assert "can become increasingly" not in prompt
    assert "most patronising" in prompt      # the achievement branch is the one selected
    assert "go one step PAST it" in prompt


@pytest.mark.asyncio
async def test_unevidenced_forbids_asserting_a_pain():
    prompt = await _prompt_for(_prospect("Ryan Petersen", "profile", "general_news"))
    assert "No pain is evidenced" in prompt
    assert "do NOT assert one" in prompt
    assert "can become increasingly" not in prompt


@pytest.mark.asyncio
async def test_evidenced_pain_keeps_the_original_hedged_shape():
    """When a pain really did match, the old sentence is still the right one."""
    prompt = await _prompt_for(_prospect("whatever", "news", "linear_headcount"))
    assert "can become increasingly" in prompt
    assert "Ops headcount scales with volume." in prompt
