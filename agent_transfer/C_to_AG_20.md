# C → AG 20: usage ledger, quota headroom, and run-budget forecasting

**Goal.** One place that answers: how much have we spent, on what, how much is left,
how many more prospects can we run today, and — when production stalls — which limit
caused it.

**Do not change pipeline behaviour.** This ticket is accounting and reporting only.
No prompt strings may change (fixtures are prompt-hash keyed; a changed prompt breaks
the suite). Run `env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONPATH=. ./venv/bin/pytest tests/ -q`
before and after; 25 tests must pass twice consecutively.

---

## The bug that motivates this — read first

`zara/utils/provider.py::_log_llm` currently starts with:

```python
t = current()
if t is None:
    return          # <-- every call outside a RunTrace is invisible
```

So `scripts/record_mock.py`, `scripts/probe`, tests, and any CLI work consume real Groq
quota and record **nothing**. Measured today: the `runs` table says 13,311 tokens; actual
consumption was roughly 4x that, because three fixture re-record cycles went unrecorded.

**A usage ledger keyed on runs is therefore wrong by construction.** Accounting must happen
for every call, run or no run. That is the central requirement of this ticket.

---

## 1. `zara/utils/quota.py` (new)

### 1a. Limit registry

Declarative, one place, with provenance comments. Verified values — do not re-research:

| Resource | Limits | Source |
|---|---|---|
| groq `openai/gpt-oss-120b` | 30 RPM · 1,000 RPD · 8,000 TPM · 200,000 TPD | org dashboard screenshot, `Groq API Key Rate Limit.md` |
| gemini `gemini-2.5-flash` | ~20 requests/day | free tier, HANDOFF §5 (confirmed correct) |
| zai `glm-4.5-flash` | unknown | record usage, report "no known limit" |
| tavily | 1,000 credits/month | `zara/utils/budget.py::DEFAULT_CREDIT_LIMITS` |
| apify | $4.00 cap | `BUDGET_CAP` in `zara/orchestrator.py` |

Env-overridable (`GROQ_TPD_LIMIT` etc). Windows: RPM/TPM = rolling 60s; RPD/TPD = calendar
day; tavily = calendar month. **State the timezone assumption in a comment and make it
configurable** (`ZARA_QUOTA_TZ`, default UTC) — Groq's daily reset is UTC, and getting this
wrong silently doubles or halves every forecast.

### 1b. `usage` table

Same SQLite file as the run store (`zara/utils/telemetry.py::connect` already creates the
schema — add this table there or in quota.py, your call, but reuse that connection helper
and its WAL setting).

```
usage(
  ts TEXT,              -- ISO8601 UTC
  provider TEXT,        -- groq | gemini | zai | fixture
  model TEXT,
  stage TEXT,           -- ranker_pain_scoring, drafter, ... ("unknown" is fine)
  context TEXT,         -- ui | batch | record_mock | test | probe | unknown
  run_id TEXT,          -- NULL when no trace is active. This is the point.
  prompt_tokens INTEGER, completion_tokens INTEGER,
  status TEXT,          -- ok | 429 | error
  http_status INTEGER,
  elapsed_ms INTEGER,
  wait_ms INTEGER       -- backoff actually slept on a 429; 0 otherwise
)
```
Index on `ts` and on `provider`.

`fixture` rows must be recorded but **excluded from all quota maths** — replays cost nothing.
Make that exclusion explicit in the query, not implicit.

### 1c. API

- `record(provider, model, *, stage, prompt_tokens, completion_tokens, status, http_status=None, elapsed_ms=None, wait_ms=0)`
  — appends one row. Never raises; wrap in try/except like the rest of telemetry. Reads
  `run_id` from `telemetry.current()` if a trace is active, else NULL.
- `context()` — resolve from env var `ZARA_CONTEXT` (default `unknown`); `serve.sh` sets
  `ZARA_CONTEXT=ui`, `stress_run.py` sets `batch`, `record_mock.py` sets `record_mock`.
- `headroom() -> list[dict]` — per limited resource:
  `{resource, window, used, limit, remaining, pct_used, resets_in_s, status}` where
  `status ∈ {ok, warn, critical, exhausted}` at <70% / 70–89% / 90–99% / ≥100%.
- `forecast() -> dict` — see §3.

---

## 2. Wire it up (small, surgical)

1. **`provider.py::_log_llm`** — move the `quota.record(...)` call **above** the
   `if t is None: return` guard so it fires for every call. Keep the existing trace write
   below it, unchanged.
2. **Record 429s.** The 429 branch currently retries without logging. Add a
   `quota.record(..., status="429", wait_ms=int(wait*1000))` there. Stall time is the single
   most useful production signal we have — one 429 was 57% of a 90.8s run — and right now it
   only exists in stderr.
3. **Record hard failures** (`status="error"`, with `http_status`) in the non-200 branch.
4. `scripts/record_mock.py`, `scripts/stress_run.py`, `scripts/serve.sh` set `ZARA_CONTEXT`.

---

## 3. `scripts/budget.py` (new CLI)

Default view — compact, this gets read constantly:

```
QUOTA                    used        limit    remaining   resets   status
groq tokens/day        47,180      200,000      152,820    6h14m   ok
groq tokens/min         2,140        8,000        5,860       38s   ok
groq requests/day          31        1,000          969    6h14m   ok
gemini requests/day         0           20           20    6h14m   ok
tavily credits/month       93        1,000          907     6d      ok
apify spend            $0.296        $4.00       $3.704     6d      ok

RUNS                            value
recorded runs (all time)            1
avg tokens/run                 13,311
p50 / p90                 13,311 / 13,311
stdev                             n/a  (need >=3 runs)
avg wall time                    90.8s
of which 429 stall               51.3s  (57%)

FORECAST (today, groq TPD)
  expected      11 more runs   (at mean 13,311/run)
  conservative  11 more runs   (at p90 13,311/run)
  NOTE: forecast uses recorded runs only; N=1, treat as indicative
```

Flags:
- `--stages` — token share per stage, descending. Answers "what is eating the budget".
- `--context` — split by ui / batch / record_mock, so non-production spend is visible.
- `--trend [N]` — tokens per run over the last N runs; flag if the last 3 exceed the mean by >25%.
- `--why` — **the production triage view.** If any resource is `critical`/`exhausted`, print
  which one, when it resets, and how many 429s and how much stall time occurred in the last
  hour. If everything is `ok`, say so plainly.
- `--json` — machine-readable, same numbers.

**Forecasting rules (get these right):**
- Remaining runs = `remaining_tpd // tokens_per_run`. Report **both** mean (expected) and
  p90 (conservative) — a single number will be believed and will be wrong.
- With fewer than 3 recorded runs, print the estimate but label it indicative. **Never
  present a forecast from N=1 as if it were a distribution.**
- The binding constraint may not be TPD. Compute remaining runs against *every* groq limit
  (TPD, RPD) and report the **minimum**, naming which limit binds.
- Exclude `fixture` and `status='error'` rows from consumption maths; include `429` rows
  (a rejected request still consumed nothing but the retry did — count the successful retry
  once, not twice; verify against `attempt` in `llm_calls`).

---

## 4. App page: "Budget & Quota"

`app.py` already has a `page` radio (`Draft` / `Run History`) and a `render_budget_meter()`
in the sidebar. Add a third page rendering the same numbers as §3:

- Headroom bars per resource, coloured by status.
- The runs/forecast block.
- Token share by stage (bar chart).
- Recent 429s with timestamp, stage, and wait — so a stall is self-explaining.
- Replace the existing sidebar meter's hardcoded 200,000 with `quota.headroom()` so there is
  one source of truth.

---

## Verification

1. Test suite green twice, 25 passing.
2. `PYTHONPATH=. ./venv/bin/python -c "from zara.utils import quota; print(quota.headroom())"` —
   returns rows with no live calls made.
3. Run `scripts/record_mock.py` (it makes real calls) and confirm **usage rows appear with
   `run_id IS NULL` and `context='record_mock'`** — this is the whole point of the ticket.
4. `scripts/budget.py --why` with everything healthy prints a clear all-clear.
5. Temporarily set `GROQ_TPD_LIMIT=1` and confirm `--why` names groq TPD as exhausted and the
   app page shows it red. Unset afterwards.
6. Do **not** burn prospect runs to test this. Fixture replays and `record_mock` are enough.

## Report back

A short summary: files changed, the numbers `budget.py` prints on the current store, and
anything in §1–4 you think is wrong. Flag disagreements rather than silently deviating.
