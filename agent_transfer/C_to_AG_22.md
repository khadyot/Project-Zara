# C → AG 22: TASK — `app.py` MVP lane (7 items)
**Date:** 2026-08-25 · **Mode:** PLAN → REVIEW → EXECUTE. Do not execute before I review your PLAN.

We are shipping. Goal is a deployed, graded MVP inside two days. You own **one file** in this
lane and I am working the rest of the tree at the same time, so the file boundary is load-bearing,
not a formality.

## Hard boundary

- **You may edit `app.py` and nothing else.** Not `zara/ui/styles.py`, not `zara/**`, not
  `value_prop.yaml`, not `requirements.txt`. If an item looks like it needs a change outside
  `app.py`, stop and say so in your PLAN — do not make it.
- **Claude owns all commits.** No `git commit`, no `git add`, no `git push`, no `git checkout`.
  Not even to "save progress". I integrate.
- **No pipeline runs.** No Run button, no `python -m zara.probe`, no `scripts/stress_run.py`.
  We are budget-rationed and I am editing the engine under you.
- **No conditional-rendering changes.** Every branch that rendered before still renders. This is
  the rule the `if not c["excluded"]:` regression went through last time.
- CSS belongs in `zara/ui/styles.py`, which is **not yours this round**. If you need a new class,
  name it in your PLAN and I will add the rule.

## Context you need

Two things already exist in the tree as of now — I landed them before writing this ticket, so
code against them as facts, not promises:

1. `zara/models.py :: DraftResult` has a new field:
   ```python
   offer_is_generic: bool = False
   ```
   It is `True` when the pipeline found no prospect-specific signal, so the opener is
   company-level and the offer is not tied to anything we actually retrieved. I am wiring the
   engine side; you render it.
2. `requirements.txt` is repinned. Do not touch it.

## The 7 items

### 1. Prospect title input (~15m)
`Prospect.title` already exists on the dataclass and is **already consumed** by
`zara/ranker.py:362`, `zara/fetchers/tavily.py:41-42`, and `zara/verifier.py:30`. The form at
`app.py:388-410` never collects it, so it is permanently `None` and all three silently degrade
to their "unknown role" branch.

Add a `Title / Role (Optional)` text input to the form and pass it through to `Prospect(...)`
as `title=title if title else None`. Placeholder e.g. `e.g. VP Finance`.

### 2. Secrets bridge (~30m)
The app is going on Streamlit Community Cloud, where keys are set in its dashboard and arrive as
`st.secrets`, not as environment variables. `zara/utils/provider.py` and the fetchers read
`os.environ`. At startup, before any `zara` import does its key lookup, copy every key in
`st.secrets` into `os.environ` **without overwriting an already-set variable** (local `.env.local`
must keep winning, and there is a documented `GROQ_API_KEY` shadowing gotcha — do not make it
worse). Wrap in try/except: `st.secrets` raises if no secrets file exists locally.

**Never print, log, echo, or `st.write` a secret value.**

### 3. Password gate (~30m)
The GitHub repo is public and the Groq free tier is 1,000 requests/day. An unguarded public URL
means anyone who finds it burns the demo quota.

Gate the whole app behind a single shared password read from `st.secrets["APP_PASSWORD"]`. If
that secret is absent (local dev), the gate is **off** — do not lock me out of my own laptop.
Store the pass/fail in `st.session_state` so it is asked once per session. This is separate from
the existing Developer-Mode `admin_pass` at `app.py:246`; leave that alone.

### 4. No-signal banner (~20m)
When `draft_res.offer_is_generic` is `True`, render a visible callout immediately above the draft:

> **No prospect-specific signal found.** The opener is company-level and the offer is generic —
> human judgment required before sending.

`st.warning` is fine. The point is that a no-signal draft must not be visually indistinguishable
from a grounded one; that is the single failure this project's thesis cannot survive. Render it
in the Draft view and in the Run History detail view if that view has the field available.

### 5. Settings drift (~30m)
Two real bugs in the Visual Settings Engine, both of which silently ignore the operator:

- `app.py:302-306` writes `icp.headcount.min` / `icp.headcount.max`. `zara/ranker.py:31-32`
  reads `icp.headcount.preferred_min` / `preferred_max`. **Nothing the operator types has ever
  had any effect.** Fix the written key names to `preferred_min`/`preferred_max`, and fix the
  two `value=` reads at :303/:305 to match so the form shows the real current values.
- `zara/utils/config.py:5` — `load_value_prop` is `@lru_cache(maxsize=1)`, so a save does not
  take effect until the process restarts, while the UI at `app.py:~289` claims *"Changes take
  effect on the next run."* After a successful save, call `load_value_prop.cache_clear()`.
  Import it as `from zara.utils.config import load_value_prop`.

Also at `app.py:314-318`: the form writes `buyer_titles`, but `value_prop.yaml` has
`buyer_functions` and nothing reads `buyer_titles`. Note it in your PLAN; do not fix it blind.

**Out of scope:** preserving YAML comments through `yaml.dump`. Known, accepted, not this round.

### 6. Demo mode toggle (~30m)
Insurance for the live interview demo. A run stalls ~50s on a Groq 429 by measurement, and I am
not letting a rate limit or a provider outage kill the demo.

Add a sidebar control group **Demo mode (offline)**:
- a checkbox, and
- when checked, a selectbox of the four available snapshots. Populate it by globbing
  `tests/fixtures/*_snapshot.json` — do not hardcode the list.

When checked:
- set `os.environ["USE_FIXTURES"] = "1"`,
- put `settings["replay_snapshot"] = "<selected path>"` into the settings dict.

When unchecked, remove/clear both.

**You do not implement the replay.** `settings["replay_snapshot"]` is consumed by
`zara/orchestrator.py`, which is mine and which I am wiring in parallel. Your job ends at putting
the key in the dict. Until my side lands, the key is simply ignored — that is expected, and is
not a bug for you to chase.

Note for your PLAN: `USE_FIXTURES=1` on its own only stubs the Apify fetchers and the LLM
provider; the snapshot is what makes retrieval offline. Both halves are needed, which is why this
is split.

### 7. Drop the ATS checkbox (~5m)
`app.py:242` — `use_ats = st.checkbox("ATS Fetchers (Free)", value=True)`. Job postings are
retired as a source (product ruling, 2026-08-24). Remove the checkbox and the `"use_ats"` key
from the `settings` dict at `app.py:~268`. The engine side of the retirement is mine.

## Deliverable

1. A **PLAN** first: per item, what you will change and roughly where. Flag anything that appears
   to need a file outside `app.py`. Flag the `buyer_titles` question. Do not write code yet.
2. I review and send a go.
3. Then EXECUTE, and report: what changed per item, and `python -c "import ast;ast.parse(open('app.py').read())"`
   clean. Do not run the test suite — it does not import `app.py` except through
   `tests/test_ui_imports.py`, which I will run on integration.
