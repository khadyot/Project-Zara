import os
import pytest
import asyncio
import json
import hashlib
from unittest.mock import patch

from zara.models import Prospect, SourceResult, SignalCard
from zara.s2 import process_prospect, render_decision_card
from zara.ranker import rank_prospect
from zara.drafter import draft_email
from zara.verifier import pass1_grounding, verify_draft
from zara.utils.provider import generate_content_with_retry, ProviderProbeFailedError

@pytest.fixture
def use_fixtures(monkeypatch):
    # Preserve an outer USE_FIXTURES=fill. Hardcoding "1" here made the documented
    # re-record workflow silently impossible: `fill` was clobbered on the way in, so
    # a missing hash raised instead of recording, and the only way through was to
    # turn fixtures off -- the exact footgun CLAUDE.md warns costs a day of budget.
    monkeypatch.setenv("USE_FIXTURES", os.environ.get("USE_FIXTURES") or "1")
    yield

def write_fixture(prompt: str, instruction: str, response: dict):
    h = hashlib.md5((prompt + instruction).encode()).hexdigest()
    path = f"tests/fixtures/{h}.json"
    with open(path, "w") as f:
        json.dump(response, f)
        
@pytest.fixture
def value_prop():
    import yaml
    with open("value_prop.yaml", "r") as f:
        return yaml.safe_load(f)

@pytest.mark.asyncio
async def test_1_zero_network_calls_under_fixtures(use_fixtures, monkeypatch):
    """1. Zero network calls under fixtures — assert it, by patching the transport to raise on any outbound call."""
    def mock_raise(*args, **kwargs):
        raise RuntimeError("NETWORK CALL ATTEMPTED!")
        
    monkeypatch.setattr("httpx.AsyncClient.send", mock_raise)
    monkeypatch.setattr("httpx.AsyncClient.post", mock_raise)
    monkeypatch.setattr("httpx.AsyncClient.get", mock_raise)
    
    prospect = Prospect("Test", "ShipBob")
    from scripts.record_mock import load_snapshot
    snapshot = load_snapshot()   # returns a list[SourceResult]

    res = await rank_prospect(prospect, snapshot)
    assert res is not None

@pytest.mark.asyncio
async def test_2_layoff_veto(value_prop):
    """2. A real layoff sentence is vetoed even at score 1.0."""
    prospect = Prospect("Test", "Test Co")
    card = SignalCard(
        claim="Restructuring affects team",
        signal_type="news",
        source_url="",
        published_date=None,
        snippet="ShipBob announced layoffs affecting 200 warehouse staff after restructuring.",
        tier="company",
        source="TestATS"
    )
    result = SourceResult(source="Test", rung=0, status="ok", reason=None, cards=[card], cost_usd=0, elapsed_ms=0)
    
    res = await rank_prospect(prospect, [result])
    # Should be excluded because of layoffs
    assert res.cards[0].excluded == "never_reference: layoffs"

@pytest.mark.asyncio
async def test_3_card_matching_no_pain_excluded(use_fixtures, monkeypatch):
    """3. A card matching no pain is excluded — via a replayed fixture, not a literal."""
    prospect = Prospect("Test", "Test Co")
    card = SignalCard(
        claim="Hiring", signal_type="hiring", source_url="", published_date=None,
        snippet="We are hiring a Software Engineer", tier="company", source="Test"
    )
    result = SourceResult(source="Test", rung=0, status="ok", reason=None, cards=[card], cost_usd=0, elapsed_ms=0)
    
    res = await rank_prospect(prospect, [result])
    rc = res.cards[0]

    # CONTRACT CHANGED, DELIBERATELY, AND THIS TEST NOW RECORDS THE NEW ONE.
    # Before `general_news` was added to the ranker prompt, a card evidencing no
    # pain came back with no match and was excluded as "matches no pain in
    # value_prop". The recorded fixture shows the model now reasons correctly
    # ("does not match any observable finance/ops pain") and then, as the prompt
    # instructs, labels it general_news @ 0.3 -- so `excluded` is None and the
    # old assertion is unreachable in strict mode.
    #
    # What this test protects is the invariant, not the mechanism: a card that
    # evidences no pain must never become a usable hook. OPEN QUESTION for the
    # product (plan Q4): does general_news survive at all, and if so must it be
    # labelled as an icebreaker on the face of the output? See C_to_AG_18 §2.
    if rc.excluded is None:
        assert rc.pain_match is not None and rc.pain_match.pain_id == "general_news"
        assert rc.score <= 0.4, "a no-pain card must not reach hook-worthy score"
    else:
        assert rc.excluded == "matches no pain in value_prop"

@pytest.mark.asyncio
async def test_4_two_same_kind_hooks_collapse():
    """4. Two same-kind hooks collapse to one, and the loser is present with the swap-test reason."""
    prospect = Prospect("Test", "Test Co")
    c1 = SignalCard(claim="C1", signal_type="hiring", source_url="", published_date=None, snippet="Foo", tier="company", source="Test")
    c2 = SignalCard(claim="C2", signal_type="hiring", source_url="", published_date=None, snippet="Bar", tier="company", source="Test")
    
    # We will mock the provider to score both highly
    async def mock_generate(*args, **kwargs):
        return type('obj', (object,), {'scores': [
            type('s1', (object,), {'index': 0, 'matched_pain_id': 'close_drag', 'score': 0.9, 'reason': 'a'}),
            type('s2', (object,), {'index': 1, 'matched_pain_id': 'close_drag', 'score': 0.8, 'reason': 'b'}),
        ]})()
        
    with patch("zara.ranker.generate_content_with_retry", side_effect=mock_generate):
        res = await rank_prospect(prospect, [SourceResult("T", 0, "ok", None, [c1, c2], 0, 0)])
        
    assert len(res.cards) == 2
    excluded_count = sum(1 for c in res.cards if c.excluded == "same hook kind as winner (Compass VI swap test)")
    assert excluded_count == 1
    
@pytest.mark.asyncio
async def test_5_grounded_vs_hallucinated_draft(value_prop):
    """5. A correct, grounded draft passes Pass 1. A draft with an invented metric fails it."""
    from zara.models import RankedProspect
    
    prospect = RankedProspect(
        prospect=Prospect("Dimitri Dadiomov", "Modern Treasury"),
        cards=[
            type('RankedCard', (object,), {
                'card': type('SignalCard', (object,), {'snippet': 'Modern Treasury is a payment operations platform. We automate reconciliation.'})(),
                'excluded': None
            })()
        ],
        icp_fit="fit",
        winning_card=None
    )
    
    # Realistic draft (must be > 60 words)
    clean = "Hi Dimitri Dadiomov,\n\nI noticed Modern Treasury is a payment operations platform focusing on automating reconciliation. Manual reconciliation typically drags month-end close. We help operations teams automate manual, reconciliation-heavy processes. This is an additional sentence to ensure the word count exceeds the sixty word minimum limit required by the verifier script without appending obvious hallucinated text or repetitive padding blocks.\n\nBest,\nZamp"
    ungrounded_clean = pass1_grounding(clean, prospect, value_prop)
    assert len(ungrounded_clean) == 0, f"Clean draft failed: {ungrounded_clean}"
    
    # Hallucinated draft
    hallucinated = "Hi Dimitri Dadiomov,\n\nI noticed Modern Treasury is a payment operations platform focusing on automating reconciliation. Manual reconciliation typically drags month-end close. We saved $1.5M for a similar company. We help operations teams automate manual, reconciliation-heavy processes. This is an additional sentence to ensure the word count exceeds the sixty word minimum limit required by the verifier script without appending obvious hallucinated text.\n\nBest,\nZamp"
    ungrounded_hallucinated = pass1_grounding(hallucinated, prospect, value_prop)
    assert len(ungrounded_hallucinated) > 0
    assert "1.5M" in ungrounded_hallucinated

@pytest.mark.asyncio
async def test_6_classifier_503_unknown():
    """6. Classifier 503 → cards land unknown → decision card says so."""
    from zara.orchestrator import run_pipeline
    from zara.fetchers.ats import AshbyFetcher
    
    prospect = Prospect("Test", "Test Co")
    
    # Patch classifier generation to raise ProviderProbeFailedError
    async def mock_gen(*args, **kwargs):
        raise ProviderProbeFailedError("429 RESOURCE_EXHAUSTED")
        
    with patch("zara.classifier.generate_content_with_retry", side_effect=mock_gen):
        # mock probe to pass
        with patch("zara.classifier.run_probe", return_value=None):
            from zara.classifier import classify_social_signals
            card = SignalCard(claim="", signal_type="social", source_url="", published_date=None, snippet="Hello", tier="person", source="Test")
            res = SourceResult("Test", 0, "ok", None, [card], 0, 0)
            
            c_res = await classify_social_signals([res])
            assert c_res.status == "failed"
            assert c_res.results[0].cards[0].eligibility == "unknown"
            
            # Now we mock process_prospect to check if decision card says so
            from zara.s2 import process_prospect, render_decision_card
            # But process_prospect calls ranker which also would fail. Let's just pass the unknown card to ranker
            ranker_res = await rank_prospect(prospect, c_res.results)
            assert ranker_res.cards[0].excluded == "eligibility: unknown"

@pytest.mark.asyncio
async def test_7_fetcher_raises_failed_row():
    """7. A fetcher that raises → failed row with a non-empty reason."""
    from zara.orchestrator import run_pipeline
    
    class RaisingFetcher:
        rung = 0
        async def fetch(self, prospect):
            raise TimeoutError("connection timed out")
            
    res = await run_pipeline(Prospect("Test", "Test Co"), [RaisingFetcher()], [], [], [], [])
    assert len(res) == 1
    assert res[0].status == "failed"
    assert res[0].reason == "TimeoutError: connection timed out"


@pytest.mark.asyncio
async def test_hooks_are_actually_produced(use_fixtures, monkeypatch):
    """The suite must fail when hook generation breaks, not shrug.

    _articulate_hooks ends in `return []` on any exception -- deliberately, since
    a draft is still useful without options. But nothing asserted hooks existed,
    so when the hook prompt changed and its fixture went missing, every hook call
    raised, every hook list came back empty, and all 83 tests stayed green. A
    gate that cannot see the thing it guards is not a gate.
    """
    from scripts.record_mock import load_snapshot

    res = await rank_prospect(Prospect("Test", "ShipBob"), load_snapshot())
    assert res.hooks, "hook articulation produced nothing — check for a fixture miss on stderr"
    for h in res.hooks:
        assert h.hook_text.strip()
        assert 0.0 <= h.strength <= 1.0


@pytest.mark.asyncio
async def test_hooks_carry_the_age_of_their_evidence(use_fixtures, monkeypatch):
    """card_index points into the shortlist, not RankedProspect.cards, so without
    this the UI cannot tell a reviewer that the lead signal is five years old."""
    from scripts.record_mock import load_snapshot

    res = await rank_prospect(Prospect("Test", "ShipBob"), load_snapshot())
    assert any(h.recency_days is not None for h in res.hooks), \
        "no hook carried an age; recency_days is not being populated"
