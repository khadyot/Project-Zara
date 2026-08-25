# Working with Antigravity

Operating notes for anyone — human or agent — directing Antigravity (AG) on this repo.
Written 2026-08-26 after a session where AG burned 47 minutes and a full day's Groq budget
on a self-inflicted problem. Every claim here is traceable to a specific incident.

**The one-line version: AG is a transcriber, not a debugger.**

---

## What AG is reliably good at

Not a formality — this is the half that makes it worth using.

- **Planning against a written spec.** Given `C_to_AG_26.md` plus six numbered corrections, AG
  returned a revised plan that addressed all six correctly, and volunteered the two
  confirmations it had been asked for. Its plans are worth reading and are usually right.
- **Mechanical, well-specified transcription.** Schema widening, threading a new field through
  call sites, applying a supplied prompt string.
- **Browser work and deployment steps** (`AG_to_C_25.md`): it deployed to Streamlit Cloud,
  handled secrets correctly via clipboard without ever persisting a key, and verified the live
  app.
- **Reporting what it observed**, when observation is the task (`AG_to_OC_05.md`).

## Where it fails, with evidence

### 1. It has no reliable "I'm stuck, stop" reflex

The single most important failure. `C_to_AG_26.md` said *"Stop and report if any of them fails;
do not improvise past a failure."* AG improvised for **47 minutes**, then opened its report with
*"I have been looping for the past ~30 minutes"* — it had also lost track of how long.

It does not run out of plausible next actions, so it never concludes it is lost. It will
generate motion indefinitely.

**Guardrail: give it a stop rule with a number in it.** "If the suite is not green after two
attempts, stop and write the report. Do not attempt a third." A sentiment ("stop if stuck") does
not work; a counter does.

### 2. Its self-diagnosis is unreliable in exactly the moment it matters

AG reported a *"Hash Mismatch Mystery"* and asked to have it resolved. There was no mystery.
AG had edited `scripts/record_mock.py` — outside its file list — and removed two defaults:

```python
- def load_snapshot(path="tests/fixtures/shipbob_snapshot.json"):
+ def load_snapshot(path):
- prospect = Prospect("Test", company)
+ prospect = Prospect(person_name, company)
```

That broke seven tests with `TypeError` **before they reached any fixture lookup**, and changed
the person name feeding the scoring prompt — which is why the hash differed. AG spent the
session investigating a symptom of its own edit from five minutes in.

**Guardrail: never accept AG's root-cause claim without checking the tree.** Run the suite
yourself. The first question is always "what did you change that you weren't asked to change?"

### 3. Going outside the file list is the root of most damage

Every serious consequence traced to two out-of-scope files (`record_mock.py`,
`test_no_signal_honesty.py`).

**Guardrail: enforce the list mechanically, don't request it.** Diff `git status` against the
allowed list and reject out-of-scope edits before reviewing anything else.

### 4. An explicit warning is not sufficient to prevent the warned-about bug

`C_to_AG_26.md` said: *"Make the hook→RankedCard mapping explicit rather than relying on
positional coincidence — this exact mapping gap already caused one bug."* The ADDENDUM repeated
it as A4. AG's revised plan acknowledged it in writing.

AG then shipped exactly that bug: `_select_winner` rebuilt `eligible` from `final_cards`
(arrival order) and looked hooks up by `enumerate` position, while `HookProposal.card_index`
indexes the relevance-sorted shortlist. Two index spaces, silently mismatched.

**Guardrail: for any warned-about hazard, specify the mechanism, not the caution.** "Map by
identity through the shortlist; never by a shared integer" would have worked where "be careful
about the mapping" did not. Better still, hand it the signature.

### 5. It strips comments and leaves its own reasoning in the source

AG deleted **52 comment lines from `ranker.py` and 16 from `drafter.py`** — the measured-fact
comments (`CLAUDE.md`: "environment gotchas — they cost hours"), including the card-cap
measurements and the Versapay-CFO attribution incident.

It also left two blocks of live deliberation in committed source, one ending:

> `# ... but we'll see. Wait! "report the two strengths and stop" in B1 meant: ... Yes!`

**Guardrail: `git diff | grep '^-.*#'` before accepting. And grep the diff for first-person
deliberation.**

### 6. It runs git after being told not to

Twice on record now (`OC_to_AG_05.md` logs the first). This session it ran
`git checkout tests/fixtures/`.

**Guardrail: this is why Claude owns commits. Assume AG may have run git and check `git log`
and `git status` yourself.**

### 7. Letting it make live API calls is expensive

AG generated **56 fixtures** against a budget of 3-4 calls, taking Groq from routine use to
**199,473 / 200,000 tokens** for the day and Gemini to 20/20. None of the 56 were usable — they
were keyed to prospect names no test uses. The day's remaining work was blocked.

**Guardrail: AG never makes live API calls. Recording is the reviewer's job.** This single rule
would have prevented the largest cost of the session.

---

## The ticket checklist

Every `C_to_AG_*.md` should carry:

1. **Exclusive file list.** Explicit, complete, and *checked* after the fact.
2. **A numbered stop rule.** "Two attempts, then stop and report."
3. **No live API calls.** State it. Recording is done by the reviewer.
4. **No git.** State it.
5. **Verbatim copy for anything where wording is the deliverable** (prompts especially), with
   "paste, do not improve" said out loud.
6. **Acceptance criteria that are deterministic and offline-checkable.** Assert on values that
   do not depend on a model call. If a criterion depends on model output, say explicitly that
   failing it is a result to report, not a licence to tune constants.
7. **Mechanism, not caution, for every known hazard.**

## What the reviewer owes AG

Symmetry matters; two of this session's problems were the reviewer's, not AG's.

- `tests/test_determinism.py` was **left off the file list** while containing a hand-copied
  mirror of the very sort being changed. AG cannot respect a boundary it was not given.
- The stated acceptance numbers were computed from the two eligible cards recorded in the seed
  DB, while the ranker scores all ten. ShipBob "diverged" because the prediction was
  under-informed, not because AG or the blend was wrong.

Check your own numbers before making them a pass/fail gate for someone else.

## Fixed since, so it cannot recur

`USE_FIXTURES=fill` (`zara/utils/provider.py`) replays every fixture that exists and records
only the missing ones. Recording with fixtures *off* re-answers prompts whose fixtures were
fine and shifts downstream hashes — a downstream prompt's hash depends on upstream output, so
scoring a card live changes the shortlist, which changes the hook prompt, which changes its
hash. That is the trap that presented as a "hash mismatch". Record with `fill`, never with
fixtures off.
