# MISSION LEDGER: PROJECT ZARA UI REVAMP — PHASE 3 HANDOFF

**Origin:** Antigravity (AG)
**Destination:** OpenCode (OC) (powered by GLM-5.3)

## STATUS LOG

**What AG accomplished:**
1. **Phase 2c (Leftovers):** Replaced ASCII icon maps in `render_run_history` with `<span class='status-dot status-{status}'></span>`. Swapped all 5 sidebar eyebrows to `.eyebrow-sm` and removed inline styles. 
2. **Phase 2d-fix (on_event_sink):** Investigated the deletion of `t.on_event_sink = True`. Confirmed via project-wide search that it is 100% dead code; left it deleted. `pytest` suite ran twice sequentially and passed (`31/31`).
3. **UI Verification & Pipeline Test:** Used an automated browser subagent to interact with `http://localhost:8501`. 
   - Visually confirmed all Phase 1-2 styling changes: lime pill tabs, gradient hero, white metric cards, status dots, and layout components.
   - **Important Usage Note:** Only **ONE (1)** prospect pipeline run was executed during this test to verify the `on_event` live progress streaming.

**🚨 CRITICAL FINDING FOR OC:**
During the single pipeline run ("Dimitri Dadiomov" at "Modern Treasury"), the UI live streaming worked flawlessly, but the backend crashed roughly 40 seconds in.

**Traceback (`zara_runs.db`):**
```python
  File ".../zara/s2.py", line 113, in process_prospect
    draft_text = await draft_email(ranked_prospect, vp, strictness=strictness, hook=hook, style=style)
  File ".../zara/drafter.py", line 70, in draft_email
    if p["id"] == winning_card.pain_match.pain_id:
AttributeError: 'NoneType' object has no attribute 'pain_id'
```
**Diagnosis:** `winning_card.pain_match` can be `None`, but `drafter.py:70` unconditionally attempts to access `.pain_id` on it.

## TASKS FOR OC

### TASK 1: Fix `drafter.py` Crash
- Remediate the `AttributeError` in `zara/drafter.py:70` to safely handle cases where `winning_card.pain_match` is `None`.
- Verify the fix against the test suite.

### TASK 2: Phase 3 (Run History Density Treatment)
- Proceed with Phase 3 UI work as originally outlined in `OC_to_AG_01.md`:
  1. Candidate `st.expander` rows: implement new `.score-badge` class.
  2. Implement conditional rendering: if the card is excluded, fade the claim to `var(--color-stone)` and drop the snippet entirely.
  3. Swap the `[0.72]` score brackets for the styled badge pill.
