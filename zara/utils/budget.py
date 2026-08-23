import json
import os
import datetime
from filelock import FileLock

BUDGET_FILE = ".budget.json"
BUDGET_LOCK_FILE = ".budget.json.lock"

DEFAULT_CREDIT_LIMITS = {
    "tavily": 1000,
}
DEFAULT_QUERIES_PER_PROSPECT = {
    "tavily": 3,
}


def _read_state_unlocked() -> dict:
    if not os.path.exists(BUDGET_FILE):
        return {}
    try:
        with open(BUDGET_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return {}


def _write_state_unlocked(state: dict):
    with open(BUDGET_FILE, "w") as f:
        json.dump(state, f, indent=2)


class BudgetExhausted(Exception):
    pass


def get_mtd_spend() -> float:
    with FileLock(BUDGET_LOCK_FILE):
        return float(_read_state_unlocked().get("mtd_spend_usd", 0.0))


def add_spend(amount: float):
    if amount <= 0:
        return
    with FileLock(BUDGET_LOCK_FILE):
        state = _read_state_unlocked()
        state["mtd_spend_usd"] = float(state.get("mtd_spend_usd", 0.0)) + amount
        _write_state_unlocked(state)


def refund(amount: float):
    if amount <= 0:
        return
    with FileLock(BUDGET_LOCK_FILE):
        state = _read_state_unlocked()
        state["mtd_spend_usd"] = max(0.0, float(state.get("mtd_spend_usd", 0.0)) - amount)
        _write_state_unlocked(state)


def _current_month() -> str:
    return datetime.date.today().strftime("%Y-%m")


def _credit_limit(source: str) -> int:
    return int(os.environ.get(f"{source.upper()}_LIMIT", DEFAULT_CREDIT_LIMITS.get(source, 0)))


def _credits_bucket_unlocked(state: dict, source: str) -> dict:
    bucket = state.setdefault("credits", {}).setdefault(source, {})
    if bucket.get("month") != _current_month():
        bucket["month"] = _current_month()
        bucket["used"] = 0
    return bucket


def get_credit_usage(source: str) -> dict:
    with FileLock(BUDGET_LOCK_FILE):
        state = _read_state_unlocked()
        bucket = state.get("credits", {}).get(source, {})
        if bucket.get("month") != _current_month():
            bucket = {"month": _current_month(), "used": 0}
    limit = _credit_limit(source)
    used = int(bucket.get("used", 0))
    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "month": _current_month(),
    }


def check_and_increment(source: str, n: int = 1):
    """Hard pre-call gate. Raises BudgetExhausted if over. Call BEFORE the paid request."""
    with FileLock(BUDGET_LOCK_FILE):
        state = _read_state_unlocked()
        bucket = _credits_bucket_unlocked(state, source)
        limit = _credit_limit(source)
        if bucket["used"] + n > limit:
            raise BudgetExhausted(f"{source} budget exhausted ({bucket['used']}/{limit} this month)")
        bucket["used"] += n
        _write_state_unlocked(state)


def refund_credits(source: str, n: int = 1):
    """Refund failed calls so they don't burn credits."""
    if n <= 0:
        return
    with FileLock(BUDGET_LOCK_FILE):
        state = _read_state_unlocked()
        bucket = _credits_bucket_unlocked(state, source)
        bucket["used"] = max(0, bucket.get("used", 0) - n)
        _write_state_unlocked(state)


def reset_credits(source: str):
    with FileLock(BUDGET_LOCK_FILE):
        state = _read_state_unlocked()
        state.setdefault("credits", {})[source] = {"month": _current_month(), "used": 0}
        _write_state_unlocked(state)


def queries_allowed(source: str, prospect_key: str | None = None) -> int:
    """Per-prospect query cap, composed with remaining monthly credits."""
    cap = int(os.environ.get(
        f"{source.upper()}_QUERIES_PER_PROSPECT",
        DEFAULT_QUERIES_PER_PROSPECT.get(source, 0),
    ))
    usage = get_credit_usage(source)
    return min(cap, usage["remaining"])
