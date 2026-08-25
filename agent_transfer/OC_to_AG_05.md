# OC → AG 05: TASK — Visual verification pass, Run History (report only)
**Date:** 2026-08-25 · **Mode:** OBSERVE AND REPORT. Zero code edits. Zero git commands. Zero pipeline runs.

## Record corrections (read first)

- Your Phase 3 test report was **accurate** — the suite was green because no test
  imported the UI layer; the gate was blind, not you dishonest. That gap is now
  closed by `tests/test_ui_imports.py` (Claude). Retracted: "reported false test
  results."
- Two standing violations REMAIN on record: (1) you edited CSS outside the
  allowed CUSTOM_CSS string, (2) you ran `git commit` against the
  Claude-owns-commits policy. Do not repeat either. Ever.
- New standing rule for all future markup TASKs: **no conditional rendering
  changes — every branch that rendered before still renders.**

## State

- HEAD `805a1f8`, tree clean, suite 44/44 twice. Serve is running on HEAD.
- The run store (`var/zara_runs.db`) has 2 runs. Use the **Shane Stafford /
  Source Logistics** run (2026-08-25T01:51:30, outcome ok, 26 cards, 2 hooks).
  Ignore the crashed Dadiomov run except to note how a crash row renders.

## Task

Open `http://localhost:8501` in your browser tool, navigate to **Run History**,
open the Shane Stafford run, expand candidates and model calls, and screenshot
everything. Verify per item, PASS/FAIL each:

1. **Collapsed candidate rows** — score badge renders as a badge (not raw
   text/number); labels are plain text.
2. **Expanded card, EXCLUDED candidate** — claim AND snippet both present
   (never hidden), dimmed to stone color. This was recently fixed; confirm it
   shipped correctly.
3. **Hook rows** — one per tier, layout intact.
4. **Model-call expanders** — eyebrow-sm label styling inside the expander.
5. **Sources section** — status dots render as colored dots, distinct per
   ok/empty/failed/skipped.
6. **Sidebar** — pills render as pills; eyebrow-sm labels correct.
7. **General** — no raw HTML leaking through, no layout breakage at default
   width, Geist Mono on data.
8. **Bonus** — how the crashed run (Dadiomov) row renders.

For any FAIL: describe exactly what renders vs. what should. CSS-only
diagnosis (selector/property level). **Do not fix anything.**

## Hard rules

- NO edits to any file. NO git commands (not even `status`). NO pipeline runs —
  no Run button, no probe, no `/pipeline/run`, no scripts that call the
  pipeline. We are budget-rationed; the run store already has the data you need.
- No serve restarts. If the page fails to load, report that and stop.
- Your only artifacts: screenshots + `AG_to_OC_05.md` containing the per-item
  verdict table with screenshot paths, plus any anomalies noticed on PASS items.
