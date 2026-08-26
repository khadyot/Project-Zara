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


@pytest.fixture
def ratelimit_store(tmp_path, monkeypatch):
    from zara.utils import ratelimit

    monkeypatch.setenv(ratelimit.STATE_FILE_ENV, str(tmp_path / "ratelimit.json"))
    yield ratelimit


def _row(key):
    return next(x for x in quota.headroom() if x["resource"] == key)


def test_unobserved_quota_is_labelled_an_estimate(store, ratelimit_store):
    """Never having seen a header is its own state, not a measurement.

    F7: the meter showed a local tally as if it were the account quota, and was
    wrong by 183k tokens. If nothing has been observed, every row must say so.
    """
    assert _row("groq tokens/day")["source"] == "estimate"
    assert _row("groq requests/day")["source"] == "estimate"


def test_groq_headers_override_the_local_tally(store, ratelimit_store):
    """The provider's own count beats ours -- the quota is account-wide."""
    quota.record("groq", "m", stage="drafter", prompt_tokens=10, completion_tokens=10, status="ok")

    ratelimit_store.observe("groq", {
        "x-ratelimit-limit-requests": "1000",
        "x-ratelimit-remaining-requests": "965",
    }, status_code=200)

    row = _row("groq requests/day")
    assert row["source"] == "measured"
    assert row["used"] == 35, "used must be limit - remaining, not our own row count"
    assert row["limit"] == 1000
    assert row["observed_age_s"] is not None


def test_tpd_ceiling_is_parsed_from_the_429_body(store, ratelimit_store):
    """The daily token ceiling appears in no header -- only in the 429 body.

    This is the reading that would have caught F7: Groq said 199,473/200,000
    while the sidebar said 16,435.
    """
    body = ("Rate limit reached for model `openai/gpt-oss-120b` in organization acme "
            "on tokens per day (TPD): Limit 200000, Used 199473, Requested 1200.")
    ratelimit_store.observe("groq", {"x-ratelimit-reset-tokens": "2m52.8s"},
                            status_code=429, body=body)

    row = _row("groq tokens/day")
    assert row["source"] == "measured"
    assert row["used"] == 199473
    assert row["limit"] == 200000
    assert row["status"] == "critical"


def test_a_stale_per_minute_reading_is_not_presented_as_measured(store, ratelimit_store):
    """A 60-second bucket observed minutes ago says nothing about it now."""
    import json
    import os

    ratelimit_store.observe("groq", {
        "x-ratelimit-limit-tokens": "8000",
        "x-ratelimit-remaining-tokens": "120",
    }, status_code=200)

    path = os.environ[ratelimit_store.STATE_FILE_ENV]
    with open(path) as f:
        state = json.load(f)
    state["groq"]["observed_at"] = "2020-01-01T00:00:00"
    with open(path, "w") as f:
        json.dump(state, f)

    assert _row("groq tokens/min")["source"] == "estimate"
