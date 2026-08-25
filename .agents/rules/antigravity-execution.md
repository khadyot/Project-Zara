# Antigravity: execution rules

Applies to Antigravity when executing a `C_to_AG_*.md` ticket in this repo.
Rationale and the incidents behind each rule: `reference/working-with-antigravity.md`.

## Hard rules

1. **Stay inside the ticket's exclusive file list.** If a change appears to require another
   file, STOP and report. Do not edit it "just to unblock". Every serious failure in the
   2026-08-26 session traced to two out-of-scope files.

2. **Two attempts, then stop.** If verification is not green after two attempts, stop and
   write the report with what you observed. Do not attempt a third. A long loop is never
   progress — a session was lost to a 47-minute one.

3. **No live API calls.** Never run recording, replay-with-fixtures-off, or any script that
   hits a provider. Recording is the reviewer's job. AG once spent a full day's Groq budget
   (199,473/200,000 tokens) generating 56 fixtures, none usable.

4. **No git. At all.** No commit, stage, push, checkout, or restore. Claude owns commits.

5. **Never delete a comment to make room for your code.** The comments in `zara/` record
   measured facts — token counts, rate limits, specific past bugs — that cost hours to learn.
   `CLAUDE.md` calls these out explicitly. Removing them destroys the reason a decision exists.

6. **Never leave your own reasoning in the source.** No "Actually…", "but wait", "we'll see",
   "Yes!". Deliberation belongs in your report, not in a committed file. If you are unsure
   what a requirement means, that is a question for the report, not a comment.

7. **Prompt copy marked verbatim is verbatim.** Paste it. Do not reword, tighten, or improve
   it. When wording is the deliverable it was derived from evidence you have not seen.

8. **Do not tune constants to hit an expected number.** If an acceptance value does not fall
   out naturally, that is a finding. Report it. Forcing it hides the very thing the number
   was there to detect.

## Before you report

- `git status` — is every changed file on the list? If not, say so at the top of your report.
- `git diff | grep '^-.*#'` — did you delete comments? Restore them.
- Did you run the suite, or are you inferring? Run it.
- Is your root cause checked, or assumed? "I changed something I wasn't asked to" is the
  first hypothesis, not the last.

## Report honestly

A report that says "I broke X, I don't know why, here is the evidence" is worth far more than
one asserting a confident wrong diagnosis. In the 2026-08-26 session a `TypeError` cascade was
reported as a "Hash Mismatch Mystery" and handed back for someone else to solve; the cause was
an out-of-scope edit made five minutes in. State what you changed before you theorise about
what broke.
