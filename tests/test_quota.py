import pytest
import sqlite3
from zara.utils import telemetry, quota

@pytest.fixture
def store(tmp_path, monkeypatch):
    db = tmp_path / "runs.db"
    monkeypatch.setenv("ZARA_RUN_DB", str(db))
    monkeypatch.setattr(telemetry, "DB_PATH", str(db))
    
    # Init DB
    telemetry.connect()
    yield db

def test_redraft_does_not_move_forecast(store):
    from zara.models import Prospect
    prospect = Prospect("Test", "Company")

    # Record a standard run
    with telemetry.trace_run(prospect, trigger="ui") as t:
        quota.record("groq", "test-model", stage="drafter", prompt_tokens=5000, completion_tokens=1000, status="ok")

    f1 = quota.forecast()
    assert f1["recorded_runs"] == 1
    assert f1["mean_tokens"] == 6000

    # Record a redraft
    with telemetry.trace_run(prospect, trigger="ui_redraft") as t:
        quota.record("groq", "test-model", stage="drafter", prompt_tokens=1000, completion_tokens=500, status="ok")

    f2 = quota.forecast()
    assert f2["recorded_runs"] == 1, "forecast should ignore ui_redraft runs"
    assert f2["mean_tokens"] == 6000, "forecast mean should not be affected by ui_redraft"
