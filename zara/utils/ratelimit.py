"""What the provider says about our quota, as opposed to what we think it is.

F7: the sidebar read "16,435 / 200,000 tokens - ~22 runs left today" while Groq's
TPD had been exhausted minutes earlier at 199,473/200,000. The meter was counting
local telemetry, which diverges from the truth three ways: the deployed run store
is ephemeral, the quota is account-wide across every machine using the key, and
the day boundaries do not agree.

Groq states the answer on every response, including 429s. This module captures
that statement and remembers the last one seen, so the meter can show a
measurement with its age instead of an estimate wearing a measurement's clothes.
Headers are free -- they ride on calls already being made.

Two things are deliberately kept apart:

  MEASURED  -- the provider told us this, at a known time. It can be stale, and
               how stale matters differently per window: a 60-second token bucket
               observed 4 minutes ago says nothing, while a daily request count
               observed 4 minutes ago is still broadly true.
  ESTIMATE  -- our own tally. Correct only if every call to this key came from
               this store, which on a shared key is never guaranteed.

Never having seen a header is its own state, and it is not "quota is full".
That is Compass VII applied to our own dashboard.
"""
import datetime
import json
import os
import re
import sys

STATE_FILE_ENV = "ZARA_RATELIMIT_FILE"
DEFAULT_STATE_FILE = ".ratelimit.json"

# The per-minute token bucket refills in 60s, so an older reading is not evidence
# about the bucket now. The daily counters move slowly enough to stay useful.
MINUTE_WINDOW_MAX_AGE_S = 60
DAY_WINDOW_MAX_AGE_S = 6 * 60 * 60

# "Rate limit reached ... on tokens per day (TPD): Limit 200000, Used 199473, ..."
# The TPD ceiling is not in any header -- this body is the only place the account's
# daily limit is ever stated, so it is worth parsing precisely once it appears.
_TPD_BODY = re.compile(
    r"tokens?\s+per\s+day|TPD", re.IGNORECASE)
_LIMIT_USED = re.compile(
    r"Limit\s+(\d+)\s*,\s*Used\s+(\d+)", re.IGNORECASE)


def _state_path() -> str:
    """Where the last observation lives.

    The default sits in the working directory, which is fine locally and is NOT
    guaranteed on a hosted container: if it is read-only the cache silently never
    persists, every render falls back to the local estimate, and the meter looks
    broken for a reason nothing reports. Fall back to the temp directory, which is
    writable everywhere, and which is honest about being per-instance and
    short-lived -- exactly what this cache is.
    """
    override = os.environ.get(STATE_FILE_ENV)
    if override:
        return override

    directory = os.path.dirname(os.path.abspath(DEFAULT_STATE_FILE)) or "."
    if os.access(directory, os.W_OK):
        return DEFAULT_STATE_FILE

    import tempfile
    return os.path.join(tempfile.gettempdir(), "zara-ratelimit.json")


def _read() -> dict:
    try:
        with open(_state_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write(state: dict):
    try:
        with open(_state_path(), "w") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        # A meter that cannot persist is a degraded meter, not a failed run.
        print(f"[ratelimit] could not persist observation: {e}", file=sys.stderr)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _to_int(raw):
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def observe(provider: str, headers=None, *, status_code: int = None, body: str = None):
    """Record what this response said about our quota. Never raises.

    Called from the provider on every outcome, so a 429 -- the one response that
    carries the daily ceiling -- is captured as carefully as a 200.
    """
    try:
        headers = headers or {}
        # httpx headers are case-insensitive; a plain dict from a test may not be.
        get = headers.get if hasattr(headers, "get") else (lambda k, d=None: d)
        lower = {str(k).lower(): v for k, v in dict(headers).items()} if headers else {}

        def head(name):
            return get(name, None) if get(name, None) is not None else lower.get(name)

        state = _read()
        entry = dict(state.get(provider, {}))

        fields = {
            "limit_requests": _to_int(head("x-ratelimit-limit-requests")),
            "remaining_requests": _to_int(head("x-ratelimit-remaining-requests")),
            "limit_tokens": _to_int(head("x-ratelimit-limit-tokens")),
            "remaining_tokens": _to_int(head("x-ratelimit-remaining-tokens")),
        }
        if any(v is not None for v in fields.values()):
            entry.update({k: v for k, v in fields.items() if v is not None})
            entry["reset_requests"] = head("x-ratelimit-reset-requests") or entry.get("reset_requests")
            entry["reset_tokens"] = head("x-ratelimit-reset-tokens") or entry.get("reset_tokens")
            entry["observed_at"] = _now_iso()

        # The daily token ceiling exists only in the 429 body.
        if status_code == 429 and body and _TPD_BODY.search(body):
            m = _LIMIT_USED.search(body)
            if m:
                entry["tpd_limit"] = int(m.group(1))
                entry["tpd_used"] = int(m.group(2))
                entry["tpd_observed_at"] = _now_iso()

        if entry:
            state[provider] = entry
            _write(state)
    except Exception as e:
        print(f"[ratelimit] observe failed: {e}", file=sys.stderr)


def _age_s(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        dt = datetime.datetime.fromisoformat(stamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return max(0.0, (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds())
    except ValueError:
        return None


def last_observed(provider: str) -> dict | None:
    """The most recent statement from this provider, with the age of each part.

    Returns None when we have never seen one -- which the caller must render as
    "not measured", never as a number.
    """
    entry = _read().get(provider)
    if not entry:
        return None
    out = dict(entry)
    out["age_s"] = _age_s(entry.get("observed_at"))
    out["tpd_age_s"] = _age_s(entry.get("tpd_observed_at"))
    return out


def reset():
    """Drop all observations. For tests and for a deliberate re-baseline."""
    try:
        os.remove(_state_path())
    except OSError:
        pass
