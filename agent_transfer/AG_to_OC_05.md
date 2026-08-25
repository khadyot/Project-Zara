# AG → OC 05: Visual verification pass, Run History (report only)

**Date:** 2026-08-25
**Mode:** OBSERVE AND REPORT.

## Verification Verdict

| Item | Verdict | Diagnosis / Note |
|---|---|---|
| 1. Collapsed candidate rows | FAIL | The score badge `[0.30]` renders as raw text in the expander header, not as a badge component. There is no CSS isolating it; it's plain text in `.streamlit-expanderHeader`. |
| 2. Expanded card, EXCLUDED | FAIL | Claim and snippet are both present, but they are NOT dimmed to stone color. They use standard dark text color. Missing CSS to apply opacity/stone color to excluded card content. |
| 3. Hook rows | FAIL | Hook rows are completely missing from the UI (none rendered below the candidates or inside the winner). |
| 4. Model-call expanders | FAIL | `SYSTEM` and `PROMPT` labels inside the expander are rendering as standard headings with the red squiggle underline (matching `.stMarkdown h3` or `h4`), not as plain `eyebrow-sm`. |
| 5. Sources section | PASS | Status dots correctly render as colored dots (e.g. green for `ok`, gray for `empty`). |
| 6. Sidebar | FAIL | `Draft`/`Run History` are default radio buttons, not pills. Headings (`1. IDENTITY`, etc.) have the red squiggle underline instead of `eyebrow-sm` styling. |
| 7. General | FAIL | Data values like `90.8s` and `13,311` in metrics use the default sans-serif font, not Geist Mono. CSS missing for `[data-testid="stMetricValue"] { font-family: 'Geist Mono'; }`. No raw HTML leaking, but `Claim strength` value is truncated. |
| 8. Bonus (Dadiomov run) | PASS | The crashed run appears in the dropdown as `· CRASH ·`. When selected, it gracefully renders a red `CRASHED` alert box with the exception, a collapsed `Traceback` expander, and a `No draft produced.` info box. |

## Notes
- Screenshots of all these items have been captured and saved as artifacts.
- No code edits were made. I only observed and reported CSS/rendering issues.
