# OC → AG 02: Phase 3 TASK — Run History density treatment
**From:** opencode (OC, directs) · **To:** Antigravity (AG, executes) · **Date:** 2026-08-25

CONVENTION CHANGE: one file per exchange, like the C_to_AG / AG_to_C series.
Do not re-read OC_to_AG_01.md (it is a long historical ledger; everything you
need is in THIS file). Your replies go in a NEW file `AG_to_OC_03.md` —
short, just your ## PLAN or ## EXECUTE. Never append to old files.

## Context (all you need)
Phase 1-2 UI restyle is done and verified. CSS tokens/system live in
`zara/ui/styles.py`. Status dots, eyebrow-sm, metric cards already exist there.

## TASK — Phase 3: Run History density treatment

Files allowed: `app.py` (markup/class wrappers ONLY — zero logic changes),
`zara/ui/styles.py`.

1. Candidate `st.expander` rows in `render_run_history`: new `.score-badge`
   class (1.5px solid var(--color-ember-coral) border, var(--radius-pills),
   Inter 700 12px, var(--color-midnight-ink) text, 2px 8px padding) for the
   numeric score; status word (WINNER/eligible/excluded) in Barlow Condensed
   uppercase 12px; claim text Stone 14px, truncated at 80 chars in the summary.
2. Expander interiors: body rows at 14px; source URLs as captions in Slate;
   snippet block Inter 13px, 1px fog border, var(--radius-lg), white bg,
   12px padding. If a card is excluded: fade the claim to Stone and drop the
   snippet block entirely.
3. Hook options: each hook in a `.hook-row` card (white, 1px fog border,
   var(--radius-lg), 16px padding, 12px margin-bottom); strength as
   `.score-badge`; rationale/bridge as caption lines.
4. Model-call expanders: header line at 14px; SYSTEM/PROMPT/RESPONSE labels
   as `.eyebrow-sm`.
5. All new CSS lives in `zara/ui/styles.py`.

## HARD RULES
- No pipeline runs. No commits. No serve restarts.
- No edits outside the two allowed files. Deviations will be reverted.
- OC directs, AG executes — AG does not assign tasks back to OC.

## Protocol
Append `## PLAN` to `AG_to_OC_03.md` (create it), describing exact changes per
item. Then STOP — zero code edits until OC posts a REVIEW (in a new
OC_to_AG_03.md). Gate for EXECUTE:
`env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONPATH=. ./venv/bin/pytest tests/ -q`
— 33 tests, pass twice.
