"""Who is allowed to open developer mode.

This lived in app.py as `admin_pass == "123"` -- a literal, in a public
repository, gating the panel that rewrites value_prop.yaml (the engine's brain)
on a publicly reachable URL.

Currently unused. The Visual Settings Engine this gated was removed from app.py
on 2026-09-08 (three defects, listed in the sidebar comment there), so nothing
calls this right now. It is kept, and kept tested, because the gate was not what
was broken -- reinstating a fixed panel should be a matter of calling this again,
not of rewriting the password check a second time.

It lives here rather than in app.py so it can be tested: importing app.py
executes Streamlit at module level, which is why tests/test_ui_imports.py
compiles that file instead of importing it. A gate nothing can test is a gate
nobody checks.
"""
import hmac
import os

ENV_VAR = "ZARA_ADMIN_PASSWORD"


def developer_mode_unlocked(entered: str | None) -> bool:
    """True only when the entered value matches the configured secret.

    There is deliberately NO default. If ZARA_ADMIN_PASSWORD is unset, developer
    mode never opens -- a fallback password in source is the same defect wearing
    a longer string. Compared with hmac.compare_digest so the check does not leak
    length or prefix through timing.
    """
    expected = (os.environ.get(ENV_VAR) or "").strip()
    entered = (entered or "").strip()
    if not expected or not entered:
        return False
    return hmac.compare_digest(entered, expected)
