# C → AG 21: recency guard, trace the redraft paths, Run History dots

Three independent tasks. Same rules as ticket 20: **no prompt string may change**
(fixtures are prompt-hash keyed), typed results over exceptions, `empty != failed !=
skipped`. Gate: `env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONPATH=. ./venv/bin/pytest tests/ -q`
— 25 tests, pass twice consecutively. **Do not spend prospect runs**; fixtures only.

---

## 1. F5 — unverifiable recency claims pass both verifier gates (highest value)

**Evidence.** Run `222e2f57cdae` drafted *"I saw your **recent** insight…"* while the winning
card had `published_date: None` and `recency_days: None`. Verifier returned `clean`.

**Why both gates miss it.** `pass1_grounding` extracts numbers, URLs, quotes and proper
nouns — "recent" is none of those. The LLM judge reads it as ordinary framing. So a claim
the evidence cannot support is structurally invisible. Same shape as F1, which
`check_attribution` was written to catch.

**Build it in `zara/verifier.py`**, modelled directly on `check_attribution`
(same file, same return shape — a `list[str]` of problems):

```python
_RECENCY_CLAIM = re.compile(r"\b(recent(ly)?|just|newly|this (week|month)|days ago|latest)\b", re.I)

def check_recency(draft_text, prospect) -> list[str]:
    """A time claim the evidence cannot carry."""
```
Fire only when `prospect.winning_card` exists and its `card.published_date` is None.
Return a message naming the matched phrase and the card, e.g.
`unverifiable recency: draft says "recent" but the winning card carries no publication date`.

Wire it in `verify_draft` on the line above `pass1_grounding`, exactly like `check_attribution`:
`ungrounded = check_attribution(...) + check_recency(...)`. It must flow into
`first_pass_hallucinations` so the existing self-correction retry rewrites the draft — this
is a fixable defect, not a kill.

**Tests** in `tests/test_determinism.py` or a new file: (a) draft says "recent", card has no
date → one problem returned; (b) same draft, card HAS a `published_date` → none; (c) draft
makes no time claim → none; (d) `winning_card is None` → none, no crash.

## 2. The redraft paths spend budget invisibly

`app.py`'s `redraft()` and the Tavily force-fetch button call the model but never open a
trace, so their tokens land in `usage` with `run_id NULL` and appear in no run. Wrap both in
`telemetry.trace_run(prospect, trigger="ui_redraft")` / `trigger="ui_boost"`, mirroring the
main run at the `run_end_to_end_pipeline` call site. Trace must be opened **inside** the
coroutine — `asyncio.run` creates a fresh context and the trace is a ContextVar.

## 3. Run History status markers

`render_run_history` in `app.py` prints sources with ASCII markers (`OK`/`--`/`XX`/`>>`).
Replace with the existing dot spans, matching what `app.py` already does elsewhere:
`<span class='status-dot status-{status}'></span>` plus `unsafe_allow_html=True`.
CSS already exists in `zara/ui/styles.py`. **Do not touch `zara/s2.py`** — its markers are
typographic on purpose (the decision card is copied out as plain text).

---

## Report back
Files changed, test output, and anything above you think is wrong — flag it rather than
deviating silently. You were right to push back on ticket 20's 429 wording.
