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

