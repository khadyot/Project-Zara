"""The run store must capture the production path, not just the pieces.

An earlier smoke test drove ranker/drafter/verifier directly and never called
capture_draft, so it reported success while `draft_text` was silently null. These
tests go through `s2.process_prospect` -- the function the orchestrator actually
calls -- so a logging regression surfaces here rather than on a live run that
costs part of the daily budget.
"""
import json
import os
import sqlite3

import pytest

from zara.models import Prospect
from zara.utils import telemetry


@pytest.fixture
def store(tmp_path, monkeypatch):
    db = tmp_path / "runs.db"
    monkeypatch.setenv("ZARA_RUN_DB", str(db))
    monkeypatch.setattr(telemetry, "DB_PATH", str(db))
    yield db


@pytest.fixture
def use_fixtures(monkeypatch):
    monkeypatch.setenv("USE_FIXTURES", "1")
    yield


def _read(db, table, run_id=None):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    q = f"SELECT * FROM {table}"
    args = ()
    if run_id:
        q += " WHERE run_id=?"
        args = (run_id,)
    return [dict(r) for r in conn.execute(q, args)]


@pytest.mark.asyncio
async def test_production_path_captures_draft_and_decision_path(store, use_fixtures):
    from scripts.record_mock import load_snapshot
    from zara.s2 import process_prospect

    prospect = Prospect("Test", "ShipBob")
    results = load_snapshot()

    with telemetry.trace_run(prospect, trigger="test") as t:
        t.capture_sources(results)
        draft = await process_prospect(prospect, results)
        t.capture_draft(draft)
        run_id = t.run_id

    rows = _read(store, "runs")
    assert len(rows) == 1
    r = rows[0]

    # The columns the smoke test silently left null.
    assert r["draft_text"], "draft_text must be captured from the production path"
    assert r["claim_strength"], "claim_strength must be captured"
    assert r["verification_status"], "verifier outcome must be captured"
    assert r["draft_words"] and r["draft_words"] > 0

    # The decision path: candidates, their scores, and why losers lost.
    cards = _read(store, "cards", run_id)
    assert cards, "every candidate card must be recorded"
    assert any(c["is_winner"] for c in cards), "the winning card must be marked"
    assert any(c["excluded"] for c in cards), "exclusion reasons must be recorded"
    assert any(c["pain_reason"] for c in cards), "the ranker's justification must be recorded"

    # Per-call accounting.
    calls = _read(store, "llm_calls", run_id)
    assert calls, "model calls must be recorded"
    assert {c["stage"] for c in calls} & {"drafter", "verifier_judge", "ranker_pain_scoring"}
    assert all(c["prompt_tokens"] is not None for c in calls), "token counts must be recorded"

    # Fingerprint: without it a code change is indistinguishable from model variance.
    assert r["git_sha"] and r["value_prop_sha"] and r["groq_model"]


@pytest.mark.asyncio
async def test_prompt_text_is_captured(store, use_fixtures):
    """'How did it write that?' is only answerable if the prompt survives."""
    from scripts.record_mock import load_snapshot
    from zara.s2 import process_prospect

    prospect = Prospect("Test", "ShipBob")
    with telemetry.trace_run(prospect, trigger="test") as t:
        await process_prospect(prospect, load_snapshot())
        run_id = t.run_id

    drafter = [c for c in _read(store, "llm_calls", run_id) if c["stage"] == "drafter"]
    assert drafter, "the drafter call must be recorded"
    assert drafter[0]["prompt_text"], "the drafter prompt must be stored"
    assert drafter[0]["system_text"], "the system instruction must be stored"


@pytest.mark.asyncio
async def test_prompt_capture_can_be_switched_off(store, use_fixtures, monkeypatch):
    monkeypatch.setenv("ZARA_LOG_PROMPTS", "0")
    from scripts.record_mock import load_snapshot
    from zara.s2 import process_prospect

    with telemetry.trace_run(Prospect("Test", "ShipBob"), trigger="test") as t:
        await process_prospect(Prospect("Test", "ShipBob"), load_snapshot())
        run_id = t.run_id

    calls = _read(store, "llm_calls", run_id)
    assert calls, "calls are still counted"
    assert all(c["prompt_text"] is None for c in calls), "prompt text must be omitted"
    assert all(c["prompt_tokens"] is not None for c in calls), "counts must survive"


def test_crash_inside_a_trace_is_still_recorded(store):
    """Crashes are the runs most worth having."""
    with pytest.raises(ValueError):
        with telemetry.trace_run(Prospect("Ada", "Analytical Engines"), trigger="test"):
            raise ValueError("boom")

    rows = _read(store, "runs")
    assert len(rows) == 1
    assert rows[0]["outcome"] == "crash"
    assert "boom" in rows[0]["error"]
    assert rows[0]["traceback"], "a traceback must be kept for diagnosis"


def test_no_trace_means_no_writes_and_no_errors(store, use_fixtures):
    """The property that keeps the existing suite honest: telemetry is inert
    unless a run explicitly opens a trace."""
    from zara.utils.provider import _log_llm
    import time

    assert telemetry.current() is None
    _log_llm("groq", "m", {"prompt_tokens": 5}, time.monotonic(), "p")  # must not raise

    assert not os.path.exists(store), "nothing may be written without an active trace"
