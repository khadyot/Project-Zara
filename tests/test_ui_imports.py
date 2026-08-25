"""The UI layer must at minimum import.

Commit ab76c1a ("stage E (opencode): stylesheet pass") shipped a `zara/ui/styles.py`
in which a block of CSS had been pasted *after* the closing tag and triple-quote
that terminate the CUSTOM_CSS literal -- i.e. raw CSS sitting at Python module
level. The file was a SyntaxError and the Streamlit app could not start on that
commit at all.

It went in behind a green suite, and the suite was not lying: no test imported the
UI layer -- a grep across tests/ for "zara.ui" or "import app" matched nothing. The whole
rendering surface was outside the gate, so the gate had nothing to say about it.

That is the gap these tests close. They are deliberately cheap -- no fixtures, no
value_prop.yaml, no model calls -- because their value is being impossible to skip,
not being thorough.

The class-reference test exists for a related hazard: CSS was extracted out of
app.py into styles.py (753bce0) so that two agents could work without collisions.
The cost of that split is that the markup and the rules it depends on can now drift
apart silently, each file passing its own review.
"""
import py_compile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Every class name the Run History markup in app.py emits.
REFERENCED_CSS_CLASSES = [
    "score-badge",
    "candidate-status",
    "candidate-claim-summary",
    "candidate-source-url",
    "candidate-snippet",
    "hook-row",
    "hook-caption",
    "model-call-header",
    "eyebrow-sm",
]


def test_styles_module_imports():
    """CUSTOM_CSS must be a string with every <style> tag closed.

    The ab76c1a break was CSS escaping the string literal, so checking that the
    tags balance tests the thing that actually went wrong -- not just that the
    module happens to import today.
    """
    from zara.ui import styles

    assert isinstance(styles.CUSTOM_CSS, str)
    assert styles.CUSTOM_CSS.strip(), "CUSTOM_CSS is empty"
    assert styles.CUSTOM_CSS.count("<style>") == styles.CUSTOM_CSS.count("</style>"), (
        "unbalanced <style> tags in CUSTOM_CSS -- CSS has probably escaped the "
        "string literal, which is a module-level SyntaxError waiting to happen"
    )
    assert styles.CUSTOM_CSS.rstrip().endswith("</style>"), (
        "CUSTOM_CSS does not end with a closing </style> -- anything appended "
        "after it is Python, not CSS"
    )
    assert callable(styles.render_hero)


def test_app_compiles():
    """app.py must parse.

    Compiled, not imported: app.py executes Streamlit calls at module level, so
    importing it here would try to render a page. Compiling catches the syntax
    breakage without that.
    """
    py_compile.compile(str(REPO_ROOT / "app.py"), doraise=True)


@pytest.mark.parametrize("css_class", REFERENCED_CSS_CLASSES)
def test_referenced_css_classes_exist(css_class):
    """Markup in app.py and rules in styles.py must not drift apart."""
    from zara.ui import styles

    assert f".{css_class}" in styles.CUSTOM_CSS, (
        f"app.py emits class '{css_class}' but styles.py defines no rule for it"
    )
