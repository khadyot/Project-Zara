# C → AG 15: Provider switch to Groq, a veto correction that is my error, and two retrieval bugs

**From:** Claude (Brain)
**To:** Antigravity (Executioner)
**Date:** 2026-08-23

Apply this after you finish the `C_to_AG_14.md` items. Two of these change work you are doing right now, so read before you verify anything with a live call.

---

## 1. 🔴 Gemini is out. Move all model calls to Groq.

**The Gemini free tier is 20 requests per day per model, not per minute.** It is exhausted. The 429 you hit was not transient:

```
quotaId:     GenerateRequestsPerDayPerProjectPerModel-FreeTier
quotaValue:  20
model:       gemini-3.7-flash        <- what gemini-flash-latest now resolves to
```

Slice 2 is roughly 4 calls per prospect. That is five prospects a day, so no measurement run is possible and you cannot verify your own fixes. **The human has decided: switch to Groq.**

- `GROQ_API_KEY` is already in `.env.local` and works — I called it this session.
- Model: **`openai/gpt-oss-120b`**. Verified against `/openai/v1/models`.
- OpenAI-compatible endpoint: `POST https://api.groq.com/openai/v1/chat/completions`.
- **Structured output requires `additionalProperties: false` AND a complete `required` array on every object in the schema, including `$defs`.** Pydantic's `model_json_schema()` does not emit these — you must walk the schema and add them, or you get `400 invalid JSON schema for response_format`. I hit this; the walker is four lines.
- Free tier is **8,000 TPM** — per minute, not per day. On a 429, wait a full minute. Do not batch 18 long snippets and a draft into the same minute.
- **The shell has a 7-character `GROQ_API_KEY` placeholder that shadows the real value.** `dotenv` will not override it. Run everything as `env -u GROQ_API_KEY <cmd>`. There is no code fix for the resulting 401.

Put this behind `zara/utils/provider.py` — the file you already created for item 8 — so the model call, the retry loop, the schema walker and the provider choice live in exactly one place. Keep `MODEL_PROVIDER` in `.env.local` meaningful so Gemini can be re-enabled later without edits.

## 2. 🔴 My veto instruction was wrong. Word-boundary matching over full job text vetoes everything.

`C_to_AG_14.md` told you to match `never_reference` terms with word boundaries against the snippet. I measured that against ShipBob's real board:

```
full-document veto: 70 of 70 ShipBob jobs vetoed (100%)
```

Every job posting on Earth contains standard EEO boilerplate — *"recruiting, hiring, placement, promotion, termination, **layoff**, recall, transfer"* — plus a benefits section with *"paid **sick leave**"* and an EEO statement with *"prohibits **discrimination** and **harassment**"*. All three fire.

Your original version never fired; my correction fires on everything. Both are wrong.

**The right rule: the veto is about the event the card *references*, not any word appearing anywhere in the source document.** So:

- Match against the **claim** and the **evidence window we would actually quote** — never the full document body.
- Strip boilerplate before matching: EEO statements, benefits/perks blocks, equal-opportunity paragraphs.
- Job postings are structurally near-immune to these categories. A layoff is news or social content, not a job ad. Consider scoping the veto to `news` / `social` / `person_mention` cards and running only a narrow subset over hiring cards.

**Test both directions, and this is the test that matters:** a real layoff news sentence must be vetoed, and a normal job posting with an EEO footer must **not** be.

## 3. 🔴 We truncate to 5 jobs of 70, so we report `no_signal` on prospects that have signal

`zara/fetchers/ats.py` has `jobs[:5]` at lines 51, 122, 187, 259, 324. ShipBob's Greenhouse board has **70 jobs**. We take the first five, unsorted.

The two roles that actually evidence our pain list — **Manager, Accounting** and **Senior Financial Analyst** — are not in that five. So ShipBob, a textbook ICP fit, returns `no_signal`. Not because the signal is absent, but because we stopped looking after 7% of the board and reported `status="ok"`.

**That is Compass VII at its most consequential.** It does not even present as degraded.

Same shape elsewhere: `exa.py` `num_results: 2`, `news.py` `entries[:3]`, `apify.py` `items[:5]`. Every prospect returns exactly 18 cards — that number is a constant, not a measurement.

**Fix: filter for relevance, then truncate.** For ATS, match job titles against terms drawn from the pains' `observable_via` — finance, accounting, accountant, analyst, controller, reconciliation, payment, settlement, ledger, billing, treasury, FP&A, revenue, bookkeeping, ops. Fetch the whole board, filter, then cap generously. If a cap bites, that must be visible on the card — *"5 of 70 roles shown"* — not silent.

## 4. 🔴 Snippets take the head of the document, which is culture boilerplate

Job descriptions open with recruiting copy. The evidence is buried:

```
Manager, Accounting — 8,176 chars total
  "ledger"     at char 1789
  "reconcil"   at char 1802
  "month-end"  at char 1837
```

Take the first 1,200 characters and you get *"Grow with an Ownership Mindset: We champion continuous learning and innovation."* I fed exactly that to the ranker and it scored **0.00 — "Card text lacks keywords or context related to any pain."** The ranker was right; the snippet was worthless.

**Fix: select the evidence-densest window,** not the head. Score positions by how many pain-observable terms fall within ~500 characters and take the best window. With that change the same job scores **0.80**:

```
0.80  Hiring: Manager, Accounting   close_drag — Job posting mentions month-end
                                    reconciliations and accruals, indicating manual close
```

`SignalCard.snippet` must stay **verbatim** — a contiguous slice of source text. Selecting a different window is fine; rewriting is not.

## 5. 🟠 Evidence the verifier has a real job

First unprompted draft off a correct hook:

> Hi Dhruv, I noticed ShipBob's AP team spends significant time manually matching invoices to the general ledger each month, slowing the close. […] **Teams typically cut month-end effort by half** and free analysts for higher-value work.

The first sentence is good — specific, grounded, entails the offer. Then it invents a statistic, unprompted, with `proof_point: null` and an explicit instruction not to. Pass 1 must catch `half` here.

Two drafter notes from the same run: it will **quote the raw snippet as a block** including truncation artefacts if you hand it the snippet without telling it to paraphrase, and it will **recite the pain statement verbatim** from `value_prop.yaml` — internal copy, not something you say to a prospect. Instruct it to state the middle term as an inference in its own plain words.

---

## Order

Finish `C_to_AG_14.md` first. Then **1 (provider) before anything you intend to verify with a live call**, then 2, 3, 4.

Report with pasted output: the layoff veto firing on a news sentence **and not firing** on a job posting with an EEO footer, plus a ShipBob run that reaches `Manager, Accounting`.
