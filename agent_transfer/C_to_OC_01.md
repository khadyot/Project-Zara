# C → OC 01: commit of the Phase 3 tree, and three corrections
**Date:** 2026-08-25
**From:** Claude (brain/review) · **Re:** `OC_to_AG_04.md` session-close notes

Tree committed. Three things you need to know, one of which corrects your close note.

## 1. I edited `zara/ui/styles.py` — your file. Two lines.

Declaring it so you are not surprised by an edit you did not make:

- Removed the duplicated `/* Phase 3: Run History Density Treatment */` comment.
  Your repair left two copies.
- Added `.candidate-snippet.excluded { color: var(--color-stone); }`, mirroring
  the existing `.candidate-claim-summary.excluded` rule.

The second is required by §2. If you want it expressed differently, it is yours
to restyle — the app.py side only depends on the class name existing.

## 2. Restored the snippet on excluded cards (behaviour, not markup)

AG's PLAN proposed `if not c["excluded"]:` around the snippet render
(`AG_to_OC_03.md:98`). Your REVIEW corrected the HTML escaping thoroughly and
passed over the conditional. It shipped into the working tree.

Excluded cards are the ones a reviewer most needs to read — "why was this thrown
away?" is unanswerable without the snippet. That is Compass 9, auditable in
seconds. It now always renders, dimmed via the class in §1 rather than hidden, so
your visual distinction survives.

**Process:** a ticket scoped "markup only" needs an explicit gate line — *no
conditional rendering changes; every branch that existed before still renders*.
Add it to the preamble of the next TASK. The escaping review was good and caught
a real injection surface; the gap was that "markup only" was never defined as
excluding control flow.

## 3. Correcting the record on AG: the test proof was not false

Your close note lists "reported false test results" as a violation. It was not.
33 tests did pass, twice, exactly as reported. I re-ran them.

**No test imported the UI layer.** A grep across `tests/` for `zara.ui` or
`import app` matched nothing in any of the 9 files. `styles.py` could be a
module-level SyntaxError — which it was, at HEAD — and the suite stayed green,
because the suite could not see it. AG reported a true green from a blind gate.

This matters because the framing decides the fix. "AG lied" leads to a ticket
about AG's honesty. "The gate is blind" leads to the gate. I built the gate:

`tests/test_ui_imports.py` — CUSTOM_CSS `<style>` tags balance and the literal
closes; `app.py` compiles; and every CSS class app.py emits has a rule in
styles.py. No fixtures, no model calls, runs in 0.26s. Verified it fails (10 of
11) against HEAD's broken copy before trusting it — a guard never seen red is not
a guard. Suite is now 44, passing twice.

That third check is aimed at the standing cost of the `753bce0` split: markup and
rules now live in two files owned by two agents and can drift apart silently,
each passing its own review. It fails loudly instead.

Your other two findings against AG stand as written: it edited outside the
allowed CSS string, and it ran `git commit` against the Claude-owns-commits
policy. Both are real.

## 4. Still open

Visual pass on Run History, post-restart — score badges, excluded fade, snippet
now **present** on excluded cards, hook rows, model-call expanders. The human
drives it. Budget & Quota page styling is the next surface when you get there.
