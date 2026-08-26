"""The Groq key pool.

Groq's free tier is per key: 8,000 tokens/minute and 200,000/day EACH. One
prospect costs ~16k across ~4 calls, so a single key spends ~45s of every run
asleep on its own 429 and runs dry after about twelve prospects. Pooling fixes
both, but only if calls are spread round-robin (kills the stall) AND a 429 moves
to the next key before sleeping (kills the ceiling).

No model calls here: the pool is deterministic code.
"""
import pytest

from zara.utils import keypool, quota


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ["GROQ_API_KEY", "GROQ_API_KEYS"] + [f"GROQ_API_KEY_{i}" for i in range(2, 11)]:
        monkeypatch.delenv(name, raising=False)
    keypool.reset()


def test_single_key_behaves_exactly_as_before(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k-primary")
    assert keypool.groq_keys() == ["k-primary"]
    assert keypool.count() == 1


def test_numbered_and_comma_separated_keys_are_both_collected(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("GROQ_API_KEY_2", "k2")
    monkeypatch.setenv("GROQ_API_KEYS", "k3, k4")
    assert keypool.groq_keys() == ["k1", "k3", "k4", "k2"]


def test_the_primary_key_is_always_first(monkeypatch):
    """A single-key setup must not change behaviour just because the module exists."""
    monkeypatch.setenv("GROQ_API_KEY", "k-primary")
    monkeypatch.setenv("GROQ_API_KEY_2", "k-second")
    assert keypool.groq_keys()[0] == "k-primary"


def test_duplicate_keys_are_collapsed(monkeypatch):
    """Pasting the same key twice must not look like twice the quota."""
    monkeypatch.setenv("GROQ_API_KEY", "same")
    monkeypatch.setenv("GROQ_API_KEY_2", "same")
    assert keypool.count() == 1


def test_no_keys_is_zero_not_a_crash(monkeypatch):
    assert keypool.groq_keys() == []
    assert keypool.count() == 0


def test_rotation_advances_so_consecutive_calls_use_different_keys(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("GROQ_API_KEY_2", "k2")
    monkeypatch.setenv("GROQ_API_KEY_3", "k3")
    keys = keypool.groq_keys()
    picks = [keys[keypool.next_start() % len(keys)] for _ in range(3)]
    assert len(set(picks)) == 3, f"rotation reused a key inside one cycle: {picks}"


def test_daily_ceiling_scales_with_the_pool(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("GROQ_API_KEY_2", "k2")
    monkeypatch.setenv("GROQ_API_KEY_3", "k3")
    monkeypatch.setenv("GROQ_API_KEY_4", "k4")
    assert quota.get_limit("groq_tokens/day") == 800000.0
    assert quota.get_limit("groq_requests/day") == 4000.0


def test_per_minute_buckets_do_not_scale(monkeypatch):
    """One call draws on one key's bucket. Pooling spreads calls; it does not
    make any single bucket larger, and claiming otherwise would re-introduce the
    stall while telling the operator it cannot happen."""
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("GROQ_API_KEY_2", "k2")
    assert quota.get_limit("groq_tokens/min") == 8000.0


def test_keys_are_never_exposed_by_the_display_surface(monkeypatch):
    """count() is the only pool fact anything is allowed to show a human."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_supersecretvalue")
    from zara.utils import health

    rendered = repr(health.key_status())
    assert "gsk_supersecretvalue" not in rendered
