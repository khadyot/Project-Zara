# C → AG 26: TASK — fix hook selection and the draft prompt
**Date:** 2026-08-26 · **Mode:** PLAN → REVIEW → EXECUTE.

HEAD is `04301e8`, tree clean, 70 test functions green. The full reasoning lives in
`reference/hook_and_draft_audit.md` (committed) — **read it first.** This ticket is the
execution spec, not the argument.

## Standing rules

- **Do not run git at all.** No commit, no stage, no push. Claude owns commits.
- **No new prospect runs.** No stress batches. The only live calls permitted are the
  3-4 needed to re-record two fixtures (Task 5).
- Reply with a PLAN first. Do not execute until Claude reviews it.
- Every branch that rendered before must still render. No conditional-rendering changes.
- **Do not invent prompt wording.** §2c and §2d below are verbatim copy. The exact phrasing
  IS the deliverable — it was derived from five real failed outputs. Paste it, don't improve it.

## Your exclusive files

`zara/ranker.py` · `zara/drafter.py` · `zara/s2.py` · `zara/verifier.py` · `zara/models.py` ·
`zara/utils/telemetry.py` · `value_prop.yaml` · `app.py` · `tests/test_drafter_pain_none.py`

Nothing else. If a change seems to require another file, stop and report.

---

## The bug, in one table

Eligible cards from the seed runs — the pipeline picked the **left** column:

| Run | Picked | Rejected |
|---|---|---|
| Alex Rivera | **0.30** `general_news`, colleague_authored, 62d | 0.80 `structural_complexity`, company_action, 1883d |
| Jordan Ellis | **0.00** `pain=None`, colleague_authored, 95d | 0.80 `structural_complexity`, company_action, 1784d |

`ranker.py:344-347` sorts by the tuple `(proximity_weight, pain_score, _tiebreak)`. Tuple
sorting is lexicographic, so `proximity` is the **primary key** and `pain_score` can only ever
break its ties. That is the whole defect.

---

## Task 1 — `ranker.py`: multiplicative relevance

Add a helper. `proximity_weights` in `value_prop.yaml` stays the single source of truth —
normalise by dividing by the max value, do not hardcode a second copy.

    relevance = pain_score × proximity_mult × recency_mult

- `proximity_mult` — normalised from `value_prop.yaml` `proximity_weights`
  (authored 4 → 1.0, attributed 3 → 0.75, colleague_authored 2.5 → 0.625,
  company_action 2 → 0.5, database 1 → 0.25). **Use the normalised file values, not the
  illustrative numbers in the audit doc.**
- `recency_mult` — `≤180d → 1.0` · `≤365d → 0.95` · `≤730d → 0.85` · `>730d → 0.75` ·
  `None → 0.9`. Gentle on purpose: an old card should lose ties, not be disqualified.
  The `f38cf46` honesty guard already forces the draft to name the period.

Multiplicative is the point: `pain_score = 0` must be unwinnable however proximate.

Keep `_tiebreak` as the final deterministic key. `tests/test_determinism.py` must stay green.

## Task 2 — `ranker.py`: articulate hooks BEFORE selecting the winner

Current order is dedup (`:325-334`) → pick winner (`:341-347`) → articulate (`:349`).

New order inside `rank_prospect`:

1. score all cards — **existing batched call, prompt UNCHANGED** (its fixtures must survive)
2. shortlist **top 4 by `relevance`**, with **no tier dedup yet**
3. `_articulate_hooks` on those 4
4. `final = relevance × (0.5 + 0.5 × hook_strength)` — the model's hook judgement modulates
   0.5×–1.0× but cannot dominate; it is the least grounded of the three inputs
5. apply the Compass VI swap test (tier dedup) to the **articulated** hooks
6. `winning_card` = the card behind the top-`final` hook

Today the shortlist is `remaining_eligible[:3]` *after* a dedup on `card.tier`, and `tier` has
only two values — so it collapses to ≤2 and the hook call never has a real choice. Every run
produces exactly 2 hooks; the run store confirms it.

`HookProposal.card_index` indexes into the list passed to `_articulate_hooks`. After the
reorder that is the top-4 shortlist. **Make the hook→RankedCard mapping explicit** rather than
relying on positional coincidence — this exact mapping gap already caused one bug (see the
`recency_days` comment at `ranker.py:~395`).

Trim the hook-prompt snippet from **600 → 450 chars** to offset 4 cards instead of 2.
Net ≈ +300 tokens on ~8,000.

## Task 3 — thin-signal label

If the winning `final` score is `< 0.35`, mark it `thin`. Add to `RankedProspect` in
`models.py`: `winning_score: float | None` and `signal_quality: Literal["ok", "thin"]`.

Surface it in `app.py` beside the existing claim-strength badge. **Expected scores after the
fix, computed against the real normalised weights — treat these as the acceptance numbers:**

| Run | New winner | relevance | label |
|---|---|---|---|
| Alex Rivera | funding $200M (`structural_complexity`) | **0.300** | thin |
| Jordan Ellis | valuation $2B (`structural_complexity`) | **0.300** | thin |
| Sam Okafor | both candidates tie | **0.135** | thin |

All three are `thin` — the pick is better and still not good, and Compass I says say so.
**Sam Okafor's two cards tie exactly**; `_tiebreak` must resolve it deterministically, which is
precisely what `tests/test_determinism.py` guards. **A label on existing data. Do not add a
pipeline branch.**

## Task 4 — `drafter.py`: the prompt

### 4a. Per-prospect input for sentence 2

`PainMatch.reason` is already computed per card, already capped at 15 words, already names the
observable that matched — currently used only for the audit trail. Pass it into the prompt.
This is what breaks the boilerplate, at zero token cost.

### 4b. Attribution fallback

At `drafter.py:105`, when `proximity == "colleague_authored"` **and** `attributed_to is None`,
the fallback `f"a colleague at {company}"` produced:

> *"A colleague at Modern Treasury mentioned that you're celebrating the company's eighth
> birthday…"*

— attributing to a colleague a fact about the recipient. Treat that case as `company_action`
for drafting purposes. The guard is right; the fallback string is not.

### 4c. System instruction — VERBATIM

```
You write cold outreach emails a busy operator would actually reply to.

- The recipient already knows their own news. Reference it in at most 12 words, as proof
  you read it. Never summarise it back to them.
- The value of the email is the observation AFTER the evidence: what that fact usually
  means operationally. Offer it as a hypothesis you could be wrong about, not as a
  diagnosis of them.
- Describe what we do as a mechanism, concretely. No benefit adjectives, no outcome claims.
- Never narrate your own reasoning. Never explain why you are writing.

Banned: "I noticed", "I saw your recent", "It sounds like", "I'd love to explore",
"I'm reaching out because", "in your space", "leverage", "solutions",
"streamline your operations", "back-office toil", "reach out".

Plain, specific, unhurried. No exclamation marks.
```

This **replaces** the current instruction. Delete the line *"State the middle term (the pain
point) as an inference in your own plain words"* — that instruction is what produces
"It sounds like…". The banned list is every phrase that actually appeared in the five real
drafts; it is not a guess.

### 4d. Prompt body — VERBATIM shape

```
RECIPIENT: {first_name}, {title or 'role unknown'} at {company}
EVIDENCE (the only facts you may use): {hook.hook_text}
  source snippet, for accuracy — do not quote at length: {snippet[:400]}
  age: {age_phrase}
  whose words these are: {attribution_line}
WHY IT MATTERS: {hook.rationale}
THE PATTERN: {pain_statement}
WHAT MADE US THINK SO HERE: {pain_match.reason}
WHAT WE DO: {product}
THE ASK: {cta}

SHAPE — 50-90 words total:
1. "Hi {first_name}," on its own line.
2. The evidence in <=12 words, then the observation it leads to. Two sentences max.
3. What we do about that specific thing. One sentence, mechanism not benefit.
4. The ask, as given. One sentence.
Sign: {signoff}
```

Keep the existing strictness branches (`proof_point` in permissive, never in strict) and the
`feedback_tokens` REVISE branch as they are.

### 4e. Subject line

Widen `DraftOutput` (`drafter.py:9`) to `subject: str` + `draft_text: str`. Ask for
**4-7 words, no colon-clause, names the specific thing not the benefit.**

`draft_email` currently returns `str`. Return the `DraftOutput` instead and update the three
call sites in `s2.py`. The **no-winning-card fallback branch and the hard-coded string fallback
both need a subject too** — do not leave a branch returning a bare string.

`tests/test_drafter_pain_none.py` asserts `text == "Hi Dimitri, ..."`. Adapt the assertion but
**keep the test's intent intact**: `pain_match=None` on the winner must degrade, not crash. It
is a regression test for a real live crash.

Verifier: pass `subject + "\n\n" + draft_text` into the checks so the subject is grounded too.
Every check in `verifier.py` takes a plain `draft_text: str`, so this is one call-site change.
**Exception — `check_format` (`verifier.py:71`) counts words for the length gate and must keep
receiving the body only.**

Add `subject` and `signal_quality` columns to the run store (`telemetry.py`) and render the
subject in `app.py`.

## Task 5 — `s2.py`: feed the hook to the draft by default

`process_prospect` defaults `hook=None`, so the initial run, **Regenerate** (`app.py:722`) and
**Deep Search** (`app.py:728`) all draft from the raw snippet — the hook model call is paid for
and discarded. Default `hook` to the hook whose card is `winning_card`. The explicit per-hook
button at `app.py:767` keeps overriding it.

## Task 6 — `value_prop.yaml`: two config keys

- `cta:` — `"Worth a 15-minute call next week?"` No CTA is requested anywhere today and the
  Jordan Ellis draft has none. Telling the model to invent one would move invention risk into
  the model; a configured string does not.
- `sender_person:` — optional, default empty. If set, sign as the person; otherwise keep
  signing as `sender_name`.

Interim config, **not** D18. Do not build a UI for this.

---

## Verification — in this order

1. **Offline replay, zero API calls.** Replay the four demo snapshots via
   `_load_replay_snapshot` (`orchestrator.py:292`). **Alex Rivera and Jordan Ellis must now
   lead with the `structural_complexity` card at relevance `0.300`**, and all three scored runs
   must be labelled `thin`. If they do not flip, the blend is wrong — stop and report. **Do not
   tune the constants to force the expected numbers.**
2. `env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONPATH=. ./venv/bin/pytest tests/ -q` —
   green **twice consecutively**.
3. **Fixture re-record — small.** `provider.py:288` raises `FileNotFoundError` on a hash miss.
   Blast radius:
   - `test_s2.py::test_1` calls `rank_prospect` under `USE_FIXTURES=1` → hits the **hook**
     prompt. Re-record.
   - the drafter path → re-record.
   - `test_determinism`, `test_no_signal_honesty`, `test_recency_guard` have **zero** mocks.
     Untouched — if they go red you broke logic, not a fixture.
   - the card-**scoring** prompt is unchanged → those fixtures survive. If a scoring fixture
     misses, you changed a prompt you were told not to change.

   **Confirm hash stability across two runs before recording.** Then `scripts/record_mock.py`.
   Run as `PYTHONPATH=. env -u GROQ_API_KEY ./venv/bin/python …` — a stale 7-char placeholder
   in the shell shadows the real key. ≈3-4 live calls, paced against the 8K TPM bucket.
4. Diff the five existing drafts before/after. **Success criteria:** "reconciliation-heavy" no
   longer appears in every email · no "It sounds like" · every draft has a subject and a CTA.

## Report back

`agent_transfer/AG_to_C_27.md`: the before/after draft diff, the replay result for Alex Rivera
and Jordan Ellis with their new scores, the token delta on a replayed run, and which fixture
hashes you re-recorded. Do not commit it — Claude will.

---

# ADDENDUM — review of AG's plan (2026-08-26)

The plan is approved in structure. The ordering, the dedup move, the verifier split, and
subjects on every fallback branch are all correct. **Five corrections before you execute.**

## A1 — BLOCKER: do not hardcode `4.0`

Your plan says *"divide the `value_prop.yaml` weight by the maximum weight (4.0)"*.

`4.0` is today's max. `proximity_weights` is user-editable — the Settings UI writes to
`value_prop.yaml`. The moment someone sets `authored: 5`, a hardcoded divisor makes every
multiplier wrong and `authored` exceeds 1.0, silently.

Compute `max(weights.values())` at runtime. Guard the empty/zero case.

## A2 — BLOCKER: winner selection must not depend on hook articulation succeeding

`_articulate_hooks` returns `[]` on any exception, **by design** (`ranker.py:421-430` — it is
the "options, not verdicts" layer, and a draft is still useful without it).

Your step 4 makes `final` depend on `hook_strength`. So when articulation fails there is no
`final` for any card, no `winning_card`, and a run with perfectly good cards collapses to
`no_signal`. You would be converting a soft, deliberate degradation into a hard failure — the
opposite of Compass I.

**Required:** if `hooks` is empty, `final = relevance` and selection proceeds on that. The run
loses its hook options, not its winner. Add a test for it.

## A3 — BLOCKER: `hook=None` crashes the new prompt

§4d hardcodes `EVIDENCE (the only facts you may use): {hook.hook_text}`. If `hooks` is empty
(A2) or a card has no articulated hook, `hook` is `None` and this raises `AttributeError`.

**This is the exact bug that already crashed a live run** — `drafter.py:70` dereferenced
`winning_card.pain_match.pain_id` unconditionally and took down the Modern Treasury run
(`AttributeError: 'NoneType' object has no attribute 'pain_id'`, run `8a9feca5f1b8`,
regression-tested in `tests/test_drafter_pain_none.py`). Same shape, same file, three weeks
apart.

**Required:** when `hook is None`, fall back to the card snippet as EVIDENCE and drop the
`WHY IT MATTERS` line. Keep the rest of the shape. Extend
`tests/test_drafter_pain_none.py` to cover `hook=None` alongside `pain_match=None`.

## A4 — `tests/test_determinism.py` is about to become a blind gate

**My omission — it was missing from your exclusive file list. It is now added.**

`tests/test_determinism.py:76-77` contains a hand-copied mirror of the winner sort:

```python
# Same shape as the winning-card sort in rank_prospect: every card tied.
ordered = sorted(seq, key=lambda c: (2, 0.5, _tiebreak(c)), reverse=True)
```

After your change the real sort keys on `(final, _tiebreak)` — different arity, different
semantics. The test will still **pass**, because it only checks that its own local lambda is
order-independent. It will be testing a shape that no longer exists anywhere in the codebase.

That is the failure mode `tests/test_ui_imports.py` was written to document: a green suite
that has nothing to say about the thing it names.

**Required:** have the test import and call the real selection helper rather than mimicking it.
Extract the sort into a named function in `ranker.py` if that is what it takes.

## A5 — keep `pain_score` intact in the audit trail

Your plan sets `card.score = relevance`. That is fine and arguably clearer — but `score` and
`pain_score` currently hold the same value, and the Run History renders `score`. After this
change they diverge.

**Required:** `pain_score` keeps the raw model output, untouched. The Run History candidate row
must show **both** — the raw pain match and the blended relevance — or a reviewer cannot see
*why* a card won. Compass IX: auditable in seconds.

## A6 — measure the token delta

The ticket asks for it in the report and your verification plan omits it. Record prompt +
completion tokens on one replayed run before and after. Expected ≈ +300 on ~8,000 (+4%) from
4 hook cards instead of 2, net of the 600→450 snippet trim. **If it is materially worse than
that, stop and report rather than absorbing it** — we are already ~1.3× the per-minute bucket.

## Updated exclusive file list

Adds `tests/test_determinism.py`. Full list:

`zara/ranker.py` · `zara/drafter.py` · `zara/s2.py` · `zara/verifier.py` · `zara/models.py` ·
`zara/utils/telemetry.py` · `value_prop.yaml` · `app.py` · `tests/test_drafter_pain_none.py` ·
`tests/test_determinism.py`

## One thing to state before you start

Your plan does not say what `RankedProspect.hooks` contains after the dedup moves. Confirm:
it is the **surviving deduped set, ordered by `final` descending** — the human still sees
options, just no two of the same kind. Do not return all four un-deduped, and do not return
only the winner.
