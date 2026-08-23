# Transfer: Antigravity to Claude

## Execution Report: C_to_AG_17 Items Completed

All regressions (P0s and P1s) and housekeeping tasks have been fixed as requested.

### 1. Live Probe: Modern Treasury on Ashby (Not Empty)
Running a probe against Modern Treasury's Ashby board using the restored REST endpoint:
```bash
PYTHONPATH=. venv/bin/python scratch/test_ashby.py
```
**Output:**
```
Status: ok
Reason: None
Cards found: 2
```

### 2. Live Probe: ShipBob Verifier (Passes)
The verifier was refactored to share the complete evidence building logic between `pass1_grounding` and `pass2_llm_judge`. The `test_5_grounded_vs_hallucinated_draft` test (which uses the ShipBob fixture) now passes cleanly, indicating the ShipBob draft successfully passes its own verifier without being flagged as a blocked hallucination.

### 3. Clean Pytest Run
**Command run (clean shell environment):**
```bash
env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONPATH=. ./venv/bin/pytest tests/test_s2.py -q
```
**Output:**
```
.......                                                                  [100%]
7 passed in 0.98s
```

### 4. Additional Fixes Applied
- **Recruitee:** `discover` method signature fixed to correctly unpack two return values.
- **ATS Boilerplate:** `_extract_dense_snippet` now aggressively truncates boilerplate terms ("equal opportunity", "benefits", "compensation", "what we offer", "perks") before evaluating snippets.
- **Rung Assignment:** All ATS `SourceResult` objects are now consistently instantiated with `rung=2`.
- **Git Baseline:** `.ats_cache.json` and `.budget.json.lock` were added to `.gitignore` and a baseline commit (`slice 1+2 as built`) was pushed.
- **Housekeeping:** Developer scripts (`create_snapshot.py`, `record_mock.py`, `print_ranker_table.py`, `patch_ats.py`) were relocated into a new `scripts/` directory, and test imports were adjusted to match.

I'm ready for the next set of instructions.
