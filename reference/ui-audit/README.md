# UI audit shots

Before/after evidence for UI defects, so a fix has something to be measured against.

- `2026-08-28-decision-card-noise.png` — the Draft page (Jordan Ellis / Modern Treasury)
  before the decision-card cleanup. Shows the four defects that motivated it: a ~300-character
  Google News redirect URL rendered bare, a full `HTTPStatusError` including the MDN link httpx
  appends, a "Retrieval" section collapsed into one unreadable paragraph, and a second copy of the
  draft, hook options and verification below the ones already on screen.

  Root cause: `render_decision_card()` (`zara/s2.py`) formats for `print()` — fixed-width columns
  and single newlines — and `app.py` was passing that string to `st.markdown()`.

- `2026-08-28-decision-card-cleaned.png` — the same run after. The expander now carries only what
  is not already on screen: deviations, then the rejected cards as scored rows with the zero-score
  tail collapsed into a count.
