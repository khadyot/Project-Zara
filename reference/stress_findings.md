# Stress-test findings

Running log. One entry per defect found by driving real prospects through the pipeline.
Raw runs: `reference/stress_log.jsonl` (machine) and `reference/stress_log.md` (table).
Runner: `scripts/stress_run.py`.

---

## 2026-08-25 · Batch 0 — baseline (baseline prospect (CFO, mid-market payments SaaS))

Single prospect, run repeatedly while fixing. Three defects found, all fixed.

### F1 — Misattribution passed the verifier as `person_authored` (CRITICAL)

The winning hook was a YouTube transcript of **Russell Lester**, the payments company's CFO. The
prospect's name appeared nowhere in it. The draft opened *"I saw **you** take a
funnel-oriented view…"* — attributing a colleague's words to the prospect — and the
verifier returned `clean`.

Root cause: `_compute_proximity(card)` did not take the prospect as an argument, so it
could not distinguish the prospect speaking from anyone else at the company speaking.
Any `tier=person, signal_type=social` card became `authored`, the highest claim-strength
tier. Deterministic grounding could not catch it: the draft never named the real speaker,
so no ungrounded token existed.

Fix: new proximity rung **`colleague_authored`** (weight 2.5) — a named exec at the
company on the record is real evidence about how the org runs, but it is their voice.
`mentions_prospect()` verifies the surname is in the content before granting `authored`.
`RankedCard.attributed_to` carries the speaker so the drafter can say *"your CFO said…"*.
`check_attribution()` in the verifier blocks second-person phrasing when the winning card
is not about the prospect.

**Design note (from the human, and correct):** the retrieval here was good — finding the
company's CFO discussing operational handoffs is a genuine signal. The bug was the
attribution layer, not the fetch. Reclassify, never discard.

### F2 — 28 of 49 seconds spent on sources returning nothing

- `CompoundFetcher`: 0/5 successes across every recorded run, ~9–12s each, always
  `413`. `groq/compound` is agentic; its server-side tool expansion overflows the model
  context. It also drew on the same Groq token bucket the ranker needs. **Unwired.**
- `ApifyLinkedInCompany`: sent `{"urls": [...]}`. The actor's build schema accepts
  `companies` (URLs) or `searches` (names) — so it ignored our input, logged
  *"No companies provided to scrape"*, took 8.5s and returned `ok` with 0 cards.
  **Fixed to `{"searches": [company]}`.**
- `ApifyLinkedInJobs`: same class of bug, and retired anyway under ruling #7.
- `_parse_items` dumped raw JSON as the snippet, so `_compute_icp_fit`'s
  `headcount: N` regex never matched and `icp_fit` was permanently `unknown`.
  **Added a real firmographic parser.**
- An actor returning zero usable cards reported `ok`. **Now `empty`** — Compass VII.

### F3 — The verifier blocked our own value proposition as a fabrication

Run ended `blocked_hallucination` on the phrase *"intercompany reconciliation sprawl"* —
which is **verbatim from `structural_complexity`'s pain statement** in `value_prop.yaml`.

Root cause: `build_evidence_list` collected `value_prop` values via
`if isinstance(v, str)`. `pains` is a **list of dicts**, so it was silently skipped and
the verifier never saw what we sell against. Meanwhile the drafter is explicitly
instructed to state the matched pain as the middle term of the syllogism. The system was
required to say the thing it then blocked itself for saying.

Fix: pain statements added to the evidence list; the pass-2 judge prompt now distinguishes
*facts about the prospect* (fabrication, blocks) from *the sender's value proposition and
pain hypothesis* (legitimately stated as inference — that is what a sales email is).

### Result on the baseline prospect

| | Before | After |
|---|---|---|
| Hook | Russell Lester's transcript (wrong person) | "the payments company Appoints the baseline prospect CFO" |
| Pain | `general_news` 0.30 | `structural_complexity` 0.95 |
| Claim strength | `person_authored` (false) | `person_attributed` (true) |
| ICP | unknown | fit — headcount 374 |
| Verifier | `clean` on a fabrication | `clean` on a grounded draft |
| Time | 49.4s | 32–42s |
| Cost | $0.0080 | $0.0040 |

### Still open after this batch

- **`ApifyLinkedInCompany` is now ~16s of a ~35s run** — the single largest latency item.
  Earning its place (it is where headcount comes from) but belongs off the critical path.
- **No configured CTA.** Under retry pressure the drafter dropped the call to action
  entirely. This is D18 (sender identity / outreach intent is not a feature yet).
- **One hook option, not three.** `tier ∈ {company, person}` collapses the Compass VI
  swap test to at most two survivors.
- **Verifier outcome is non-deterministic** at `temperature=0` — the same draft blocked on
  one run and self-corrected on the next. Worth understanding before trusting the gate.
- Early exit still discards cards after the first ≥0.8 hook, including ones that would
  have made better second options.

---

## 2026-08-25 · Batch 1 — Run 1 (Run 1 prospect (VP Transportation, mid-market logistics))

First run recorded end-to-end by the new telemetry (`var/zara_runs.db`, run `222e2f57cdae`).
Category 3 in `reference/stress_set.csv` — "verifiably in post, no personal web presence".

**The pipeline did well on the thing being tested.** The winning card was a the logistics company
LinkedIn post that *directly quotes him*: `"We have a strong focus on streamlining our
processes and procedures to ensure we're meeting customer requirements but also enabling
further expansion."` The draft paraphrased his own words, `proximity=attributed`,
`claim_strength=person_attributed`, verifier clean. **No F1-style misattribution.**

Note the corpus was wrong, not the pipeline: the row was labelled "no personal web presence"
but a direct quote exists. Perplexity sourced him from a leadership page and a scraped
directory and asserted absence it had not established. Category 3 needs re-sourcing.

### F4 — A run costs 2.6x what the budget assumed, and most of the clock is a rate-limit stall

`HANDOFF-2026-08-25.md` §6 said ~5.2K tokens and ~35 runs/day. Measured:

| | Assumed | Measured |
|---|---|---|
| Tokens / run | ~5,200 | **13,311** |
| Runs / day (200K TPD) | ~35 | **15** |
| vs the 8K TPM bucket | 0.65x | **1.66x** |

A single prospect now exceeds the *per-minute* bucket, so every run stalls by construction:

```
wall 90.8s → retrieval 21.3s · rank/draft/verify 68.4s
             of which actual model time  17.1s
             UNACCOUNTED                 51.3s   ← "Groq 429, waiting 52.5s"
```

**57% of wall time was one 429 wait.** The pipeline is not slow, it is throttled. Root cause
was the ranker: 3 of 7 calls and 7.2k of 13.3k tokens, because `chunk_size = 5` re-sent the
entire pains block with every chunk.

**Fixed, partially.** Two changes, each measured on the identical ShipBob snapshot:

| | orig | one call | + terse reason |
|---|---|---|---|
| Model calls | 6 | 4 | 4 |
| Ranker tokens | ~5,900 | 4,665 | **4,029** |
| Run total | ~10,000 | 9,230 | **8,060** |
| vs 8K TPM | 1.25x | 1.15x | **1.01x** |

1. `chunk_size` → all cards in one call. Removes the duplicated pains block.
2. `CardScoreOutput.reason` capped at 15 words. This field was the largest single line item
   in a run — one justification per card, 2,539 completion tokens across 15 cards. It still
   names the observable that matched, which is what makes the pick auditable.

Also retired the **early exit** (previously listed as "still open" above): it stopped scoring
after the first chunk containing a ≥0.8 match, discarding candidates needed for the Compass VI
swap test and the audit trail. Every capped card is now scored, and the run is still cheaper.

**Honest limit:** extrapolated to a live run this is ~10.7k tokens, still ~1.3x the per-minute
bucket. The stall should shorten, not disappear. Batching alone was predicted to roughly halve
cost and did not — the duplication removed was real but output tokens dominate, and those
scale with cards scored, not with call count.

### F5 — An unverifiable recency claim passes the verifier

The draft opened *"I saw your **recent** insight..."*. The winning card has
`published_date: None` and `recency_days: None` — there is no date evidence at all.

The verifier passed it clean, correctly by its own rules: "recent" is not a number, a URL, a
quote, or a proper noun, so `pass1_grounding` cannot extract it, and the LLM judge treats it
as ordinary framing. So an unfalsifiable time claim is invisible to both gates.

Not fixed yet. The cheap fix is a deterministic check in the same family as
`check_attribution`: if the draft asserts recency (`recent`, `just`, `this week`, `newly`)
while the winning card has no `published_date`, flag it. Same shape as F1 — a claim the
evidence does not carry, which token grounding structurally cannot see.

### F6 — The editable draft box ignored every draft after the first (UI)

Reported by the human, invisible to telemetry: the draft rendered in the audit trail but
"The draft (editable)" kept its placeholder. `app.py` used a fixed `key="draft_editor"` on
the `text_area`. Streamlit gives `session_state` precedence over `value=` for a keyed widget,
so the box locked onto whatever it first rendered and ignored every later draft, regenerations
included. Key is now derived from the draft's own digest: new text gets a fresh widget, an
unchanged draft keeps the user's edits.

Worth noting as a class: **the run store cannot see the UI layer.** Anything between the
`DraftResult` and the screen needs a human looking at it.

### Still open after this batch

- **Regenerate / Tavily-boost paths are untraced.** `app.py`'s redraft and force-fetch make
  model calls that never open a trace, so they spend budget invisibly.
- **F5 unfixed** — no recency guard.
- A live run is still ~1.3x the per-minute token bucket.
- Category 3 of the stress set needs re-sourcing; "no web presence" was asserted, not verified.
