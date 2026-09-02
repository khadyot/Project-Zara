import pytest
import asyncio
import httpx
import os
import subprocess
from unittest.mock import patch, MagicMock, AsyncMock

from zara.models import Prospect, SourceResult, SignalCard
from zara.orchestrator import run_pipeline
from zara.fetchers.ats import GreenhouseFetcher
from zara.utils.discovery import guess_slug

# 1. SourceResult invariants
def test_source_result_invariants():
    # Should raise if status != ok and reason is None
    with pytest.raises(ValueError, match="must have a reason"):
        SourceResult(source="Test", rung=0, status="failed", reason=None, cards=[], cost_usd=0.0, elapsed_ms=0)
        
    # Should raise if status != ok and cards is not empty
    with pytest.raises(ValueError, match="must have an empty cards list"):
        card = SignalCard("c", "hiring", "url", None, "snip", "company", "Test")
        SourceResult(source="Test", rung=0, status="failed", reason="err", cards=[card], cost_usd=0.0, elapsed_ms=0)
        
    # Should succeed
    res = SourceResult(source="Test", rung=0, status="ok", reason=None, cards=[], cost_usd=0.0, elapsed_ms=0)
    assert res.status == "ok"

# 2. Empty vs Failed distinction (Mocking HTTPX)
@pytest.mark.asyncio
async def test_greenhouse_empty_vs_failed():
    fetcher = GreenhouseFetcher()
    prospect = Prospect("John", "Acme")

    # Bypass ATS discovery (networked) — we only want to test response handling
    discover = patch(
        "zara.fetchers.ats.ATSDiscoverer.discover",
        new=AsyncMock(return_value=("greenhouse", "acme")),
    )

    # Mock a 200 response that actually contains an error object
    class MockResponse:
        def __init__(self, status, json_data):
            self.status_code = status
            self._json = json_data
        def json(self):
            return self._json

    # Test Failed (200 but error body)
    with discover, patch("httpx.AsyncClient.get", return_value=MockResponse(200, {"error": "Invalid board"})):
        res = await fetcher.fetch(prospect)
        assert res.status == "failed"
        assert "Invalid board" in res.reason

    # Test Empty (200 but no jobs)
    with discover, patch("httpx.AsyncClient.get", return_value=MockResponse(200, {"jobs": []})):
        res = await fetcher.fetch(prospect)
        assert res.status == "empty"
        assert "no open jobs" in res.reason

# 3. Budget Guard triggering
@pytest.mark.asyncio
async def test_budget_guard_triggers():
    # Setup mock fetchers
    class MockPaidFetcher2:
        async def fetch(self, p): return SourceResult("Rung2", 2, "ok", None, [], 0.005, 0)
        
    class MockProfileFetcher3:
        async def fetch(self, p): return SourceResult("Rung3Profile", 3, "ok", None, [], 0.005, 0)
        
    class MockSearchFetcher4:
        async def fetch(self, p): return SourceResult("Rung4", 4, "ok", None, [], 0.005, 0)
            
    prospect = Prospect("John", "Acme")
    
    with patch("zara.orchestrator.get_mtd_spend", return_value=4.50):
        # MTD spend is 4.50, which is over the 4.00 cap. 
        # Rung 2, 3, 4 should all skip.
        rung2 = [MockPaidFetcher2()]
        rung3 = [MockProfileFetcher3()]
        rung4 = [MockSearchFetcher4()]
        
        results = await run_pipeline(
            prospect, [], [], rung2, rung3, rung4, deep_mode=True
        )
        
        for r in results:
            if r.rung in (2, 3, 4):
                assert r.status == "skipped"
                assert r.reason == "budget guard"

# 4. Escalation Correctness
@pytest.mark.asyncio
async def test_escalation_correctness():
    # Rung 0 returns cards. Rung 3 should NOT fire.
    class MockRung0:
        async def fetch(self, p):
            card = SignalCard("c", "hiring", "url", None, "snip", "company", "Mock0")
            return SourceResult("Mock0", 0, "ok", None, [card], 0.0, 0)
            
    class MockRung1:
        async def fetch(self, p):
            card = SignalCard("c", "person_mention", "url", None, "snip", "person", "Mock1")
            return SourceResult("Mock1", 1, "ok", None, [card], 0.0, 0)
            
    class MockRung3Jobs:
        async def fetch(self, p):
            return SourceResult("Mock3Jobs", 3, "ok", None, [], 0.0, 0)
            
    class MockRung3Profile:
        async def fetch(self, p):
            return SourceResult("Mock3Profile", 3, "ok", None, [], 0.0, 0)
            
    prospect = Prospect("John", "Acme")
    with patch("zara.orchestrator.get_mtd_spend", return_value=0.0):
        results = await run_pipeline(
            prospect,
            [MockRung0()],
            [MockRung1()],
            [],
            [MockRung3Jobs(), MockRung3Profile()],
            []
        )
        
        rung3_jobs = [r for r in results if r.source == "MockRung3Jobs"][0]
        rung3_prof = [r for r in results if r.source == "MockRung3Profile"][0]
        
        assert rung3_jobs.status == "skipped"
        assert rung3_jobs.reason == "cheaper rung succeeded"
        
        assert rung3_prof.status == "skipped"
        assert rung3_prof.reason == "cheaper rung succeeded"

# 5. Hostile CSV (Unicode and Quotes)
def test_hostile_csv_unicode():
    # We just want to ensure our Prospect and slug parsing doesn't crash
    hostile_prospects = [
        Prospect("José Müller", "Global Enterprises"),
        Prospect('Alice "The Boss"', 'Super Fast Startup Inc. Which Has An Extremely Long Name That Might Break UI Layouts'),
        Prospect("X Æ A-12", "SpaceX"),
        Prospect("田中 一郎", "Tokyo Tech")
    ]
    
    for p in hostile_prospects:
        slug = guess_slug(p.company)
        assert isinstance(slug, str)

# 6. Grep test for drafts.send and messages.send
def test_no_gmail_sends_in_codebase():
    # Check all python files in zara/ for 'drafts.send' or 'messages.send'
    result = subprocess.run(
        ["grep", "-riE", r"drafts\.send|messages\.send", "zara/"],
        capture_output=True,
        text=True
    )
    # The return code of grep is 1 if no lines were selected, 0 if selected.
    assert result.returncode == 1, "Found forbidden Gmail send methods in codebase!"


@pytest.mark.asyncio
async def test_parallel_search_is_wired_into_rung_one():
    """The primary search source must actually be in the ladder, at rung 1.

    Rung 0 is what the gap-filler gate counts, so a paid source there commits
    spend before the gate can decide anything.
    """
    import inspect
    from zara import orchestrator

    src = inspect.getsource(orchestrator._run_end_to_end)
    rung1 = src.split("rung1 = [", 1)[1].split("]", 1)[0]
    assert "ParallelSearchFetcher()" in rung1, "ParallelSearch must sit in rung 1"

    rung0 = src.split("rung0 = [", 1)[1].split("]", 1)[0]
    assert "Parallel" not in rung0, "a paid source must not sit in rung 0"


@pytest.mark.asyncio
async def test_parallel_search_degrades_without_a_key(monkeypatch):
    """No key is `skipped` with a reason, never a crash and never a bare `empty`."""
    from zara.fetchers.parallel import ParallelSearchFetcher
    from zara.models import Prospect

    monkeypatch.delenv("PARALLEL_API_KEY", raising=False)
    res = await ParallelSearchFetcher().fetch(Prospect("A B", "Acme"))
    assert res.status == "skipped"
    assert res.reason and "PARALLEL_API_KEY" in res.reason
    assert res.cards == [] and res.cost_usd == 0.0


def test_retrieval_vocabulary_comes_from_config_not_code():
    """Editing a pain's vocabulary in value_prop must change what we search for.

    The Exa fetchers hardcode their queries, so the Settings UI could rewrite the
    pains and retrieval would go on asking for the same thing.
    """
    from zara.fetchers.queries import build_query_plan
    from zara.models import Prospect

    p = Prospect("Dana Lee", "Northwind", title="CFO")
    _, queries = build_query_plan(p, {"retrieval": {"search_terms": ["zebra husbandry"]}})
    assert any("zebra husbandry" in q for q in queries), \
        "search_terms from value_prop must reach the query"

    # And an unconfigured value_prop still searches for something (Compass I).
    _, fallback = build_query_plan(p, {})
    assert fallback and all(q.strip() for q in fallback)
