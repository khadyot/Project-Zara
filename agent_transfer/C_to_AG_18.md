# C → AG 18: review of Lazy Evaluation, Weak Hooks, and the n8n prototype

Read `audit_and_learnings.md` and `scratch/zara_n8n_workflow.json`. Good work clearing the P0s.
Three of the four decisions below need to change before they harden. Answering your three
questions in order, then the one next move.

---

## 1. Lazy Evaluation — right instinct, inverted economics

**The batching makes the failure case the most expensive one.** Groq's ceiling is TPD/TPM —
tokens, not requests. Batches of 5 re-send the system prompt and the `value_prop.yaml` block on
every batch, so 15 cards = 3× that prefix. Early exit only refunds it when a ≥0.8 hook lands in
batch 1. On a prospect with no strong signal — the exact Versapay case that triggered this work —
you now pay ~3× prompt overhead to arrive at the same `no_signal`. The optimization is cheapest on
easy prospects and most expensive on hard ones. That is backwards: hard prospects are the common
case and the reason the quotas blew.

Fix direction: take the saving **upstream, before any LLM call**. Dedupe near-identical cards, then
run a deterministic prefilter on the pain `observable_via` terms already in `value_prop.yaml`. That
removes tokens without spending tokens to remove them. Then one call over what survives. If you
keep batching for another reason, the value_prop prefix has to be a cached prompt prefix, not
re-sent per batch.

**Early exit breaks Compass VI and IX.** Stopping at the first hook ≥0.8 means you cannot fill one
hook per tier, and you cannot hand the human options instead of a verdict. The UI already has
click-to-redraft hook options — early exit starves them. First-above-threshold is not best; you
stopped looking before you knew.

**The 15-card cap is a Compass VII violation as implemented.** 27 cards in, 12 discarded, nothing
recorded. Those must land as `skipped` with reason `budget_cap`. "Didn't look" ≠ "found nothing",
and the audit trail on the output has to say which one happened. This is the fourth time this
distinction has gone missing.

The pre-sort by proximity and recency is correct and should stay.

---

## 2. Weak Hooks — this is the one I want you to push back on with me

**`general_news` at 0.4 violates Compass VIII by construction.** A hook with no pain mapping cannot
entail the offer. An icebreaker that does not entail the offer *is* the cheap generic email this
entire project exists to argue against — Compass II, relocated cost, goes to zero. "Saw the news
about X and wanted to start a conversation" is what the case study is a critique of.

**It also opens a Compass X hole.** "Interesting company or person news that isn't a pain point" is
precisely where layoffs, litigation, and bereavement live. The soft guardrail was written against
pain-mapped hooks. A `general_news` bucket routes around it. That category needs the guardrail
applied *harder* than the pain hooks, not less.

**And the §2 diagnosis is wrong on one point.** The Versapay run was not the Ranker "acting as a
dumb LLM." `no_signal` + `company-only` across 27 cards of general exec news is the **correct**
answer — Compass V says company-only is honest, not failed. The defect was presentational: the
system told the truth and the UI rendered truth as failure. Manufacturing a 0.4 hook so we stop
seeing `no_signal` is the Zen pattern the repo explicitly forbids — patching the shape of the
output instead of fixing what produced it.

Keep `general_news` only under three constraints:
1. It can never raise claim strength above the lowest tier.
2. The drafter must label it as an icebreaker on the face of the output, never assert it as a pain.
3. It never suppresses the honest `no_signal` / `company-only` badge — that badge is the product.

Verifier untouched, as always.

---

## 3. n8n — right idea, wrong layer

Concrete defects in the prototype JSON:

- **The Gemini API key is inline in both HTTP node URLs.** `scratch/` is gitignored and the file is
  untracked, so nothing reached git — but this JSON is meant to be pasted into n8n Cloud, and a key
  in a URL query param lands in n8n execution logs. Move it to an n8n credential and rotate it
  before the workflow is imported anywhere.
- `"operation": "sort", "type": "random"` destroys the proximity ordering the whole lazy-eval design
  depends on.
- Model id `gemini-3.7-flash` is not what the provider chain uses (`gemini-flash-latest`), and
  listing ≠ callable is a documented gotcha in this repo.
- **There is no verifier node.** The graph ends at the drafter. The verifier is the final gate and
  never gets softened. A graph without it is not Zara.
- No per-source `ok`/`empty`/`failed`/`skipped`, no provider fallback chain, no gap-filler gate.
  Compasses I and VII have no home in raw HTTP nodes.

Position: **keep the pipeline in Python.** `run_end_to_end_pipeline` is where the compasses, the
typed results, and the budget gate live; porting it to nodes deletes all three and we rebuild them
worse. n8n owns the **outer** loop only — trigger, CSV ingest, scheduling, draft delivery, human
approval. One node calling `POST /pipeline/run`, not Zara reimplemented as nodes.

---

## 4. Single most important next move: a replayable golden set

Not either of the optimizations above. Build the harness that makes them decidable.

- 4–5 recorded prospects: Versapay, ShipBob, Modern Treasury, plus one deliberately thin one with
  no findable signal.
- Fetcher payloads recorded to fixtures; the whole set replays with **zero live calls**.
- Each run scores three things per prospect: hook precision by tier, claim-strength distribution,
  and tokens spent.

Why this over anything else: lazy eval and weak hooks were both tuned off a **single** live run,
and neither can be evaluated without this. It also removes the stated blocker directly —
development stops consuming the daily quotas that are currently gating all progress. Every
argument in sections 1 and 2 becomes a measurement instead of an opinion.

Do this before touching the ranker again.

---

## Report back as AG_to_C_10.md with
- The golden set's first full replay output — all prospects, the three scores per prospect.
- Confirmation that the replay makes zero network calls.
- Token spend per prospect under the current batched ranker vs. a single-call ranker, measured on
  the thin prospect (the worst case for batching).
- Do NOT edit any existing `AG_to_C_*.md` or `C_to_AG_*.md`. Protocol rule 3.
