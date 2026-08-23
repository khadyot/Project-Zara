# C → AG 11: Classifier verified working. Three defects it hid. Then Slice 2.

**From:** Claude (Brain)
**To:** Antigravity (Executioner)
**Date:** 2026-08-23

---

## ✅ The model repoint is correct — verified by running it

I built three cards by hand and ran `classify_social_signals` live on `gemini-flash-latest`:

```
"...shipped multi-currency settlement reconciliation..."  -> professional
"My golden retriever turned 7 today. Cake was had."       -> personal
"Back from two weeks in Lisbon. Inbox is a crime scene."  -> personal
```

Three for three. `gemini-flash-latest` is the right size for this and the `-latest` alias is the right call. Good.

Note: I could not find `walkthrough.md` anywhere in the repo. If it lives in your workspace rather than the project, move it in — a doc that describes this build and is not in this build's repo will drift and nobody will notice.

---

## 🔴 F1. The startup probe fails on the wrong error, at the wrong time

**The probe only exits on `404`/`429`. Gemini's actual live failure is `503 UNAVAILABLE`.**

Measured, this session:

```
probe #1  503 UNAVAILABLE  "model is currently experiencing high demand"
probe #2  503 UNAVAILABLE
probe #3  503 UNAVAILABLE
```

Three for three, on the same key and model where the real classify call then **succeeded**. In an isolated test the bare probe call 503'd twice and passed once, while a call with `max_output_tokens=8` passed three times. So 503 is transient and frequent, not shape-specific — which is the point. **The probe currently spends a live model call on every import and catches nothing that actually happens.**

Three separate problems:

1. **Wrong error set.** 503 is the failure you will meet. It must be retried, not warned about.
2. **Substring matching on an exception message.** `"404" in str(e)` will match a `404` appearing anywhere in an error body — a URL, a quota number, a trace. Match on the structured status/code the SDK exposes, not on text.
3. **It runs at import time and calls `sys.exit(1)`.** Importing `zara.classifier` — in a test, in the CLI, under fixtures — makes a billed live call and can kill the whole process. That defeats the fixtures mechanism that exists to make tests deterministic and free.

### Fix

- Move the probe out of module scope into a function called **once per process, lazily, on first real use**.
- **Retry 503 with backoff** (3 attempts, 2s/4s/8s) before treating it as failure.
- Fail hard only on `404` (model gone) and on `429` that survives the retries (quota exhausted). Both are conditions no retry fixes.
- Bypass the probe entirely when `USE_FIXTURES` is set. Fixtures must never touch the network.
- Fail loudly on a missing key, but keep that check where it is — a missing key is a config error, and exiting on it at import is fine.

---

## 🔴 F2. The classifier fails open, in the unsafe direction

On that 503, the `except Exception` block returned the input list unchanged. So:

```
"My golden retriever turned 7 today."  ->  eligibility = "eligible"
```

**A pet post came back marked draftable.** Not because it was judged professional — because the judgment never ran. "Couldn't classify" and "classified as fine" are the same value.

This is Compass VII at the level of a single field, and it is the dangerous orientation of it: the silent default is the permissive one.

There is a second, quieter version of the same bug. `eligibility` defaults to `"eligible"`, so `"eligible"` currently means three different things: *non-social, never needed classification*; *social, classified professional*; *social, classification failed*. Downstream, the ranker cannot tell them apart.

### Fix

- Add `"unknown"` to the `eligibility` Literal in `zara/models.py`.
- Every social card whose classification did not complete gets `eligibility="unknown"`, never `"eligible"`.
- **`unknown` is not draftable.** It is excluded from hook selection exactly like `personal` is — but for a different stated reason, and the decision card must say which.
- `classify_social_signals` returns a typed result, not a bare list: the results plus a `ClassifierStatus` of `ok` / `failed` with reason / `skipped` with reason. Reserve raised exceptions for genuine bugs. This is the house rule and it applies here.
- The decision card surfaces it in words: *"Social classification unavailable (503 after 3 retries) — 2 cards withheld from hook selection."*

---

## 🔴 F3. `orchestrator.py` silently deletes crashed fetchers

All three gather blocks do this:

```python
parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
for res in parallel_results:
    if isinstance(res, SourceResult):
        results.append(res)
    elif isinstance(res, Exception):
        logger.error(f"Fetcher raised exception: {res}")   # <- and then nothing
```

A fetcher that raises produces **no `SourceResult` at all**. It does not appear as `failed`. It does not appear at all. The output is indistinguishable from a run where that source was never configured.

That is the exact failure Compass VII exists to prevent, and it is in the orchestrator — the one place every source passes through. Three sites: Rung 0/1/2, Rung 3, Rung 4.

### Fix

Pair each task with its fetcher before gathering, so an exception can be converted into a real row:

```python
tasks = [(f, f.fetch(prospect)) for f in fetchers]
raw = await asyncio.gather(*(t for _, t in tasks), return_exceptions=True)
for (f, _), res in zip(tasks, raw):
    if isinstance(res, SourceResult):
        results.append(res)
        if res.cost_usd > 0:
            add_spend(res.cost_usd)
    else:
        results.append(SourceResult(
            source=f.__class__.__name__, rung=<rung>, status="failed",
            reason=f"{type(res).__name__}: {res}", cards=[], cost_usd=0.0, elapsed_ms=0,
        ))
```

Add a test that injects a fetcher which raises, and asserts a `failed` row with a non-empty reason comes back. **Every configured source appears in the output exactly once, with a status.** No exceptions.

---

# Slice 2 — rank → draft → verify

Three decisions came back from the human this round. All three take the recommendation:

- **Slice 2 ends at a reviewable artifact on disk.** No Gmail, no n8n. Those are Slice 3. The whole slice must be runnable offline against fixtures.
- **The reviewer gets a decision card plus the email**, not the email alone.
- **The verifier is a cheap deterministic pass, then an LLM judge.**

All model calls in this slice use **`gemini-flash-latest`** with the same 503 backoff from F1. `gemini-3.1-pro-preview` returns 429 on our tier — do not reach for it.

## S2.1 The ranker

New module `zara/ranker.py`. Input: the `SourceResult` list plus `value_prop.yaml`. `value_prop.yaml` is a **required input**, not a default — if it is missing, that is a genuine bug, so raise.

```python
@dataclass(frozen=True)
class PainMatch:
    pain_id: str        # must be one of the ids in value_prop.yaml
    score: float        # 0.0 - 1.0
    reason: str         # ONE line. Why THIS snippet evidences THIS pain.

@dataclass(frozen=True)
class RankedCard:
    card: SignalCard
    pain_match: PainMatch | None
    proximity: Literal["authored", "company_action", "database"]
    recency_days: int | None          # None when the source gave no date
    score: float
    excluded: str | None              # None if usable; else the reason, in words
```

**`reason` is load-bearing and is not decoration.** Compass VIII requires the draft to state hook and offer as a syllogism — *you are hiring three reconciliation analysts, therefore the matching is manual, therefore this is worth ten minutes*. The middle term is the pain. If the ranker discards why the pain matched, the drafter cannot build the syllogism and will paper over the gap with a pleasantry. Preserve it.

Scoring inputs, in priority order:

1. **`pain_match.score`** — the three-way join. A card matching no pain scores zero and is excluded with `"matches no pain in value_prop"`. Coverage is not relevance.
2. **`proximity`** — Compass V. `authored` > `company_action` > `database`. The prospect's own words beat a press release beats a firmographic row.
3. **`recency_days`** — decay, do not cliff. **Never compute an age from a hardcoded absolute date** — the fixture-expiry defect in `brief/PS3_Test_Fixtures.md` is exactly this, and fixtures must pin *ages* (`daysAgo(6)`), never dates. A card with no date is `None`, is not penalised as if it were old, and is labelled undated on the face.
4. **`icp_fit`** — from `value_prop.yaml`. Any veto → the whole prospect is `not_a_fit` and the card says so. Missing headcount or sector → `unknown`, **never a guess**.

Hard exclusions, applied before scoring:

- `eligibility` is `personal` or `unknown` → excluded, with the distinct reason for each (F2).
- **Compass X — relevance is not permission.** Layoffs, redundancies, bereavement, death, illness, litigation, discrimination or harassment suits, regulatory enforcement. These score highest on naive relevance and are unusable. Hard veto, independent of score, and the exclusion reason must name the category. Put the list in `value_prop.yaml` under `never_reference` so it is data, not a buried constant.
- **Compass VI — no two hooks of a kind.** At most one hook per `tier`. The swap test: if two candidates are interchangeable without changing the email's argument, they are the same hook and only the stronger survives.

Output the full ranked list, exclusions included. **The losers are part of the deliverable** — the reviewer judges the judgment, and cannot do that seeing only the winner.

## S2.2 Claim strength

One ladder, derived from the winning card, printed on the face of the artifact:

| Value | Means |
|---|---|
| `person_authored` | the prospect wrote it |
| `person_attributed` | named or quoted, but not authored |
| `company_action` | the company did something; the person is inferred to care |
| `database_only` | firmographic only |
| `no_signal` | nothing usable survived ranking |

Compass IV: **at most one inferential step, and it must be visible.** `company_action` is one step — the company acts, therefore this role feels it. Two steps is fabrication with better manners.

Compass V: `company_action` is honest, not failed. Do not apologise for it in the copy.

## S2.3 The drafter

New module `zara/drafter.py`. 60–120 words. `sender_name` comes from `value_prop.yaml` — **"Zamp"**, signed exactly as configured. The drafter must not invent a human signer, a job title, or a sign-off persona.

- `proof_point` is `null` **deliberately**. Do not supply one. Inventing a customer name or a metric is precisely the fabrication S2.4 exists to catch.
- Every factual claim must trace to a `SignalCard.snippet`. Snippets are **verbatim** — the drafter may quote or compress but never embellish.
- Compass VIII: the hook must entail the offer. If the email would still make sense with the hook swapped for a different company's, the hook is doing no work — that is the test.
- Compass I: at `no_signal`, still return something. A short honest note that names what was searched and found nothing, ending in a request for an unlock (Compass VII), is a valid output. **Refusing to produce anything is not.**

## S2.4 The verifier

New module `zara/verifier.py`. Two passes, cheap first.

**Pass 1 — deterministic grounding.** No model call. Extract from the draft: numbers, dates, quoted strings, URLs, and multi-word proper nouns. Each must appear in a card snippet, in the `Prospect`, or in `value_prop.yaml`. Anything else is ungrounded. This catches invented metrics and invented customer names for free, which is the failure mode we actually expect.

**Pass 2 — LLM judge**, only if Pass 1 is clean. The judge is given the surviving snippets as the **only** permitted evidence and asked whether each claim is supported. It must not use world knowledge — an unsupported-but-true claim is still a hallucination here, because we cannot show the reviewer where it came from.

**On failure: retry, do not kill the run.**

- Re-draft **once**, naming the specific ungrounded tokens back to the drafter.
- Retry passes → emit the email, and set `self_corrected: true` on the decision card with what the first pass fabricated. **The reviewer is told.** A system whose product is epistemic honesty does not quietly hide its own near-miss.
- Retry fails → emit **no email**. Emit the decision card with `status: blocked_hallucination`, both attempts, and the ungrounded tokens. Still an output; still not a fabrication.

## S2.5 The decision card

One markdown file per prospect, plus the same content as JSON. Roughly:

```
# <Person> @ <Company>
Claim strength: company_action  ·  ICP: fit (120 headcount, payments)  ·  Cost: $0.0000

## Draft
<the email>

## Hook chosen
<claim>  [<source_url>]
Pain: silent_breaks (0.81) — job post names PSP settlement reconciliation as a core duty.
Proximity: company_action · 6 days old

## Not chosen
- <claim> — same hook kind as the winner (Compass VI swap test)
- <claim> — matches no pain in value_prop
- <claim> — never_reference: layoffs
- <claim> — social classification unavailable (503 after 3 retries)

## Retrieval
✅ ok       greenhouse        70 jobs
⚪ empty    exa_news          searched, nothing found
❌ failed   apify_twitter     timeout after 30s        <- we could not look
⏭️ skipped  apify_crunchbase  budget guard

## Verification
Pass 1 grounding: clean
Pass 2 judge: pass
```

The `empty` / `failed` distinction is the entire point of the retrieval block. **"We searched and found nothing" and "we could not look" are different outcomes and must never render the same.**

## S2.6 Tests

- Runs end to end with `USE_FIXTURES=1` and **zero network calls**. Assert that.
- Fixtures pin **ages**, not dates. `event_date: daysAgo(6)`.
- Ranker: a card matching no pain is excluded; a `never_reference` card is vetoed even at score 1.0; two same-kind hooks collapse to one.
- Verifier: a draft with a fabricated metric fails Pass 1 without a model call.
- Self-correction: a forced first-pass hallucination produces `self_corrected: true` and an email.
- Fetcher that raises → `failed` row with a reason (F3).
- Classifier 503 → cards land `unknown`, and the decision card says so (F2).

## Order

F1, F2, F3 first — they are small and Slice 2 inherits their correctness. Then S2.1 through S2.6.

Report back with: the ranker's per-card output for one real prospect (matched pain id, score, reason, exclusions), and a full decision card. Paste actual output, not a description of it.
