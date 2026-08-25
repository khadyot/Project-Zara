"""The status panel must be honest and must never leak a key."""
import pytest
from zara.utils import health


def test_absent_key_reports_absent(monkeypatch):
    for name, _, _ in health.PROVIDER_KEYS:
        monkeypatch.delenv(name, raising=False)
    rows = health.key_status()
    assert all(not r["present"] for r in rows)
    assert not health.secrets_bridge_ok()


def test_present_key_reports_present(monkeypatch):
    for name, _, _ in health.PROVIDER_KEYS:
        monkeypatch.setenv(name, "x" * 40)
    rows = health.key_status()
    assert all(r["present"] and r["length"] == 40 for r in rows)
    assert health.secrets_bridge_ok()


def test_short_key_is_flagged_suspicious(monkeypatch):
    """The documented failure here is a 7-char placeholder shadowing a real key.

    Presence alone cannot tell those apart, which is the whole reason length is
    surfaced.
    """
    monkeypatch.setenv("GROQ_API_KEY", "gsk_abc")
    row = next(r for r in health.key_status() if r["name"] == "GROQ_API_KEY")
    assert row["present"] and row["suspicious"]


def test_status_never_contains_a_key_value(monkeypatch):
    secret = "NOTAREALKEY-canary-for-leak-detection-0001"
    monkeypatch.setenv("GROQ_API_KEY", secret)
    blob = repr(health.key_status())
    assert secret not in blob
    assert "canary-for-leak-detection" not in blob


@pytest.mark.asyncio
async def test_probe_without_a_key_says_so(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    res = await health.groq_probe()
    assert res["status"] == "no_key"


@pytest.mark.asyncio
@pytest.mark.parametrize("exc,expected", [
    ("auth", "rejected"),
    ("429", "throttled"),
    ("other", "unreachable"),
    (None, "ok"),
])
async def test_probe_outcomes_map_to_verdicts(monkeypatch, exc, expected):
    """No live call: the three failure modes must stay distinguishable, because
    401 means the deploy is broken while 429 means it is fine."""
    from zara.utils import provider

    monkeypatch.setenv("GROQ_API_KEY", "x" * 40)

    async def fake_probe():
        if exc == "auth":
            raise provider.ProviderAuthError("401")
        if exc == "429":
            raise provider.ProviderProbeFailedError("Probe failed hard: HTTP 429")
        if exc == "other":
            raise provider.ProviderProbeFailedError("connection reset")
        return None

    monkeypatch.setattr(provider, "run_probe", fake_probe)
    res = await health.groq_probe()
    assert res["status"] == expected


# --- the secrets bridge must say WHY, not just THAT ----------------------------
# app.py's bridge used to end in `except Exception: pass`. Non-fatal was right --
# there is no secrets file locally -- but silent was not: "no secrets configured"
# (a two-minute fix in a web form) and "the copy loop is broken" (a code bug)
# both rendered as a bare "key absent". This caught a real dead deploy.

@pytest.mark.parametrize("raw,state", [
    ("unavailable|StreamlitSecretNotFoundError", "unavailable"),
    ("empty|st.secrets contains no entries", "empty"),
    ("copied|7 of 7 entries copied", "copied"),
    ("", "unknown"),
    ("garbage-with-no-pipe", "unknown"),
])
def test_bridge_states_are_distinguishable(monkeypatch, raw, state):
    monkeypatch.setenv("ZARA_SECRETS_BRIDGE", raw)
    assert health.bridge_status()["state"] == state


def test_every_bridge_state_carries_actionable_advice(monkeypatch):
    for raw in ("unavailable|X", "empty|Y", "copied|Z", ""):
        monkeypatch.setenv("ZARA_SECRETS_BRIDGE", raw)
        assert health.bridge_status()["advice"].strip()


def test_copied_is_not_healthy_when_required_keys_are_still_missing(monkeypatch):
    """A [section] header makes the loop run and copy nothing usable.

    'The bridge ran' and 'the app has what it needs' are different claims.
    """
    monkeypatch.setenv("ZARA_SECRETS_BRIDGE", "copied|1 of 1 entries copied")
    for name, _, _ in health.PROVIDER_KEYS:
        monkeypatch.delenv(name, raising=False)
    assert health.bridge_status()["healthy"] is False


def test_bridge_healthy_only_when_required_keys_present(monkeypatch):
    monkeypatch.setenv("ZARA_SECRETS_BRIDGE", "copied|7 of 7 entries copied")
    for name, _, _ in health.PROVIDER_KEYS:
        monkeypatch.setenv(name, "x" * 40)
    assert health.bridge_status()["healthy"] is True


def test_bridge_status_never_leaks_a_value(monkeypatch):
    secret = "NOTAREALKEY-canary-for-leak-detection-0002"
    monkeypatch.setenv("ZARA_SECRETS_BRIDGE", "copied|7 of 7 entries copied")
    monkeypatch.setenv("GROQ_API_KEY", secret)
    assert secret not in repr(health.bridge_status())
