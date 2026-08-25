import pytest
from zara.verifier import check_recency
from zara.models import RankedProspect, RankedCard, Prospect, SignalCard
from zara.ranker import PainMatch

@pytest.fixture
def base_prospect():
    return RankedProspect(
        prospect=Prospect(person_name="Test", company="Company"),
        cards=[],
        hooks=[],
        icp_fit="ok",
        icp_notes=[],
        winning_card=None
    )

def test_recency_flagged_if_no_date(base_prospect):
    card = SignalCard("claim", "news", source="Tavily", source_url="x", published_date=None, snippet="test", tier="company")
    win = RankedCard(card, pain_match=None, proximity="authored", score=10.0, excluded=None, guardrail_hit=None, recency_days=None)
    base_prospect = RankedProspect(prospect=base_prospect.prospect, cards=[], icp_fit="ok", winning_card=win)
    
    draft = "I saw your recent insight on linkedin."
    issues = check_recency(draft, base_prospect)
    assert len(issues) == 1
    assert 'unverifiable recency: draft says "recent"' in issues[0]
    
def test_recency_ok_if_date_present(base_prospect):
    card = SignalCard("claim", "news", source="Tavily", source_url="x", published_date="2023-10-01", snippet="test", tier="company")
    win = RankedCard(card, pain_match=None, proximity="authored", score=10.0, excluded=None, guardrail_hit=None, recency_days=5)
    base_prospect = RankedProspect(prospect=base_prospect.prospect, cards=[], icp_fit="ok", winning_card=win)
    
    draft = "I saw your recent insight on linkedin."
    issues = check_recency(draft, base_prospect)
    assert len(issues) == 0

def test_recency_ok_if_no_time_claim(base_prospect):
    card = SignalCard("claim", "news", source="Tavily", source_url="x", published_date=None, snippet="test", tier="company")
    win = RankedCard(card, pain_match=None, proximity="authored", score=10.0, excluded=None, guardrail_hit=None, recency_days=None)
    base_prospect = RankedProspect(prospect=base_prospect.prospect, cards=[], icp_fit="ok", winning_card=win)
    
    draft = "I saw your insight on linkedin."
    issues = check_recency(draft, base_prospect)
    assert len(issues) == 0

def test_recency_ok_if_no_winning_card(base_prospect):
    base_prospect = RankedProspect(prospect=base_prospect.prospect, cards=[], icp_fit="ok", winning_card=None)
    draft = "I saw your recent insight on linkedin."
    issues = check_recency(draft, base_prospect)
    assert len(issues) == 0

def test_recency_bare_just_ignored(base_prospect):
    # 'just' is often an adverb in sales copy (e.g. "I just wanted to reach out").
    # It only denotes recency when modifying an event verb (e.g. "just launched").
    card = SignalCard("claim", "news", source="Tavily", source_url="x", published_date=None, snippet="test", tier="company")
    win = RankedCard(card, pain_match=None, proximity="authored", score=10.0, excluded=None, guardrail_hit=None, recency_days=None)
    base_prospect = RankedProspect(prospect=base_prospect.prospect, cards=[], icp_fit="ok", winning_card=win)
    
    issues1 = check_recency("I just wanted to reach out about your ops.", base_prospect)
    assert len(issues1) == 0
    
    issues2 = check_recency("We just help teams automate this.", base_prospect)
    assert len(issues2) == 0
    
    issues3 = check_recency("I saw that you just announced the new funding.", base_prospect)
    assert len(issues3) == 1
    assert 'unverifiable recency: draft says "just announced"' in issues3[0]



# --- stale dates, not just missing ones ---------------------------------------
# check_recency early-returned on `published_date is not None`, so a date years
# past counted as fully satisfying a recency claim. That shipped, on the deployed
# app, on the flagship demo: "You recently discussed..." about a Modern Treasury
# podcast 1,826 days old, while yesterday's 8-K sat in the losers pile.

def _win(days, published="2021-08-25"):
    card = SignalCard("claim", "news", source="ExaYouTube", source_url="x",
                      published_date=published, snippet="test", tier="person")
    return RankedCard(card, pain_match=None, proximity="authored", score=10.0,
                      excluded=None, guardrail_hit=None, recency_days=days)


def _prospect(base, win):
    return RankedProspect(prospect=base.prospect, cards=[], icp_fit="ok", winning_card=win)


def test_recency_flagged_when_the_card_is_years_old(base_prospect):
    """The exact defect, as a regression: a dated card is not a fresh one."""
    p = _prospect(base_prospect, _win(1826))
    out = check_recency("I caught your recent conversation on the podcast.", p)
    assert out, "a 1,826-day-old card must not satisfy 'recent'"
    assert "1826 days old" in out[0]


def test_recency_not_flagged_when_the_card_is_fresh(base_prospect):
    p = _prospect(base_prospect, _win(3, published="2026-08-24"))
    assert check_recency("I saw your recent 8-K filing.", p) == []


def test_stale_card_without_a_time_claim_is_fine(base_prospect):
    """Leading with old material is allowed. Calling it recent is not."""
    p = _prospect(base_prospect, _win(1826))
    assert check_recency("In your 2021 conversation you discussed bank payments.", p) == []


def test_threshold_is_configurable(base_prospect):
    p = _prospect(base_prospect, _win(200))
    assert check_recency("your recent post", p, {"guardrails": {"stale_days": 180}})
    assert check_recency("your recent post", p, {"guardrails": {"stale_days": 365}}) == []


def test_bad_threshold_config_falls_back_rather_than_crashing(base_prospect):
    """A malformed guardrail must not take the verifier down with it."""
    p = _prospect(base_prospect, _win(1826))
    assert check_recency("your recent post", p, {"guardrails": {"stale_days": "soon"}})
