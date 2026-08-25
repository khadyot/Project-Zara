"""Demo mode must be genuinely offline, or it is not insurance.

The point of demo mode is that a live interview demo cannot be killed by a rate
limit or someone else's outage. That guarantee is only worth something if it is
enforced: `USE_FIXTURES=1` alone stubs the Apify fetchers and the LLM provider,
but leaves GoogleNews, Jina, Exa and Tavily -- and entity resolution, which runs
before retrieval -- making live calls. This test blocks the network outright.
"""
import pytest

from zara.models import Prospect, SourceResult
from zara.orchestrator import _load_replay_snapshot, RETIRED_SOURCES

SNAPSHOT = "tests/fixtures/shipbob_snapshot.json"


@pytest.fixture
def no_network(monkeypatch):
    import httpx

    def boom(*args, **kwargs):
        raise AssertionError("demo mode attempted a network call")

    for method in ("send", "post", "get", "request"):
        monkeypatch.setattr(httpx.AsyncClient, method, boom, raising=False)
        monkeypatch.setattr(httpx.Client, method, boom, raising=False)


def test_replay_returns_recorded_sources(no_network):
    results = _load_replay_snapshot(SNAPSHOT)
    assert results, "replay must return the recorded retrieval"
    assert all(isinstance(r, SourceResult) for r in results)


def test_replay_rewrites_retired_sources_rather_than_duplicating_them(no_network):
    """Snapshots predate the ATS retirement and still carry those five rows."""
    results = _load_replay_snapshot(SNAPSHOT)
    names = [r.source for r in results]
    for retired in RETIRED_SOURCES:
        assert names.count(retired) == 1, f"{retired} appears {names.count(retired)}x"
    for r in results:
        if r.source in RETIRED_SOURCES:
            assert r.status == "skipped" and r.reason


@pytest.mark.asyncio
async def test_full_pipeline_makes_zero_network_calls_in_demo_mode(no_network, monkeypatch):
    """The whole path: entity resolution, retrieval, rank, draft, verify."""
    monkeypatch.setenv("USE_FIXTURES", "1")
    from zara.orchestrator import run_end_to_end_pipeline

    results, draft = await run_end_to_end_pipeline(
        Prospect("Test", "ShipBob"),
        settings={"replay_snapshot": SNAPSHOT, "strictness": "strict"},
    )
    assert results, "demo run must still report its sources"
    assert draft is not None
    assert draft.claim_strength, "the claim-strength label is the output's face"


# --- the demo seed store ------------------------------------------------------
# Run History is a graded surface and the deployed filesystem is ephemeral, so a
# fresh deploy must not show an empty dashboard. Seeding is opt-out rather than
# unconditional: making it a property of connect() silently pre-populated every
# "fresh" store, including three telemetry tests that assert on their own rows.

import sqlite3


def _seed_fixture(tmp_path, monkeypatch, contents=b"seeded"):
    from zara.utils import telemetry
    fake_seed = tmp_path / "seed.db"
    fake_seed.write_bytes(contents)
    monkeypatch.setattr(telemetry, "SEED_DB", str(fake_seed))
    return telemetry


def test_seed_populates_a_store_that_does_not_exist_yet(tmp_path, monkeypatch):
    telemetry = _seed_fixture(tmp_path, monkeypatch)
    monkeypatch.setenv("ZARA_SEED_DEMO", "1")
    target = tmp_path / "var" / "runs.db"
    target.parent.mkdir()
    telemetry._restore_seed(str(target))
    assert target.read_bytes() == b"seeded"


def test_seed_never_overwrites_a_real_store(tmp_path, monkeypatch):
    """Losing a user's actual run history to a demo seed would be unforgivable."""
    telemetry = _seed_fixture(tmp_path, monkeypatch)
    monkeypatch.setenv("ZARA_SEED_DEMO", "1")
    target = tmp_path / "runs.db"
    target.write_bytes(b"real history")
    telemetry._restore_seed(str(target))
    assert target.read_bytes() == b"real history"


def test_seed_can_be_switched_off(tmp_path, monkeypatch):
    telemetry = _seed_fixture(tmp_path, monkeypatch)
    monkeypatch.setenv("ZARA_SEED_DEMO", "0")
    target = tmp_path / "runs.db"
    telemetry._restore_seed(str(target))
    assert not target.exists()


def test_seed_absence_is_not_fatal(tmp_path, monkeypatch):
    """A missing seed is cosmetic. It must never stop a run."""
    from zara.utils import telemetry
    monkeypatch.setattr(telemetry, "SEED_DB", str(tmp_path / "nope.db"))
    monkeypatch.setenv("ZARA_SEED_DEMO", "1")
    target = tmp_path / "runs.db"
    telemetry._restore_seed(str(target))       # must not raise
    assert not target.exists()
