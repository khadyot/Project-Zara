"""Developer mode must not open on a literal in the source tree."""
import pathlib

import pytest

from zara.ui.auth import ENV_VAR, developer_mode_unlocked

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_password(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)


def test_unset_password_never_unlocks(monkeypatch):
    """No default. An unset secret means the panel that rewrites value_prop.yaml
    simply does not open -- a fallback in source is the same defect, longer."""
    for attempt in ["", "123", "admin", "password", None]:
        assert developer_mode_unlocked(attempt) is False


def test_correct_password_unlocks(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "a-real-secret")
    assert developer_mode_unlocked("a-real-secret") is True
    assert developer_mode_unlocked(" a-real-secret ") is True, "surrounding space should not matter"


def test_wrong_password_does_not_unlock(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "a-real-secret")
    for attempt in ["a-real-secre", "A-Real-Secret", "123", ""]:
        assert developer_mode_unlocked(attempt) is False


def test_the_old_hardcoded_gate_is_gone():
    """The literal this replaced. Kept as a test because the failure mode is a
    revert or a copy-paste bringing it back, not a subtle logic error."""
    app = (REPO_ROOT / "app.py").read_text()
    assert 'admin_pass == "123"' not in app
    assert '== "123"' not in app, "a hardcoded credential comparison is back in app.py"
