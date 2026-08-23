# Project Zara — Session Handoff

**Written:** 2026-08-23 · **For:** the next Claude session picking this up mid-flight.

Read this first, then `value_prop.yaml`, then the latest `agent_transfer/C_to_AG_*.md`. Do not re-derive anything in §4 — it was verified with live calls and cost real time.

---

## 1. What this is

A single-prospect B2B outreach agent. Given a name + company, it researches them, judges which signal is worth leading with, and drafts a personalised cold email for human review. **It never auto-sends.**

Built for the Zamp "AI Solutions Associate" case study, Problem Statement 3. `brief/` and `reference/` are carried-forward material from a prior attempt (`../Project Zebra`) — weighted reference, not decisions.

**The core thesis:** personalisation worked because it was a *costly signal* — expensive to fake. AI destroys that mechanism by making it cheap. So the cost must relocate to **judgment**: the willingness to say honestly how good the material actually is, including when it is thin.

---

## 2. How this session works — read before acting

**Three-party setup:**

| Party | Role |
|---|---|
| **Claude (you)** | The "Brain". Architecture, data structures, decisions, research, verification. Writes tickets. |
| **Antigravity (AG)** | The "Executioner". Filesystem, Python, running code. |
| **The human** | Runs both. Pastes prompts into AG. Makes product decisions. |

Protocol is in `agent_transfer/00_PROTOCOL.md`: chronological file drops, `C_to_AG_NN.md` and `AG_to_C_NN.md`. Never append to old files.

**Three hard-won working rules:**

1. **AG only runs when the human pastes a prompt into it.** Writing the ticket file is not enough. **End every turn with exactly one paste-ready prompt.** Multiple pastes per turn confused the human; they asked for one.

2. **Present decisions as labelled options (A/B/C) with a recommendation — never open questions.** The human said this explicitly. Do the thinking, draft the actual candidate answers, mark one Recommended, use `AskUserQuestion`. Batch related decisions into one call.

3. **Verify AG's claims. Do not take them at face value.** This has caught something in *every single round*:
   - Proposed `curious_coder/linkedin-profile-scraper` as "cookieless" — its schema has `"required": ["cookie", …]`
   - Reported ATS hit rate 0/3 and recommended dropping the primary source — was a regex bug; 2/3 were reachable
   - Reported hit rate 3/3 after "fixing" — false positives from SmartRecruiters returning HTTP 200 for gibberish
   - Shipped a classifier on OpenAI with no OpenAI key in the project
   - Replaced it with `gemini-2.5-pro`, which is retired and 404s

   The pattern: **AG checks that things exist rather than that they work.** Verify by *doing the thing*.

Perplexity has no native MCP access — research routes through the human via `perplexity_prompts/` → `perplexity_responses/`. The Perplexity block in `CLAUDE.md` describes tools that do not resolve in-session; use `WebSearch`.

---

## 3. Current state

**Slice 1 (retrieval) is built and working.** `zara/` package, venv, CLI at `python -m zara.probe`, FastAPI webhook at `POST /pipeline/run`, `sources.yaml` registry, budget guard, 16 Apify actors, scoped Exa, ATS discovery, tests passing.

**`C_to_AG_10.md` is DONE and verified.** Classifier runs live on `gemini-flash-latest`; 3/3 correct on hand-built cards. `walkthrough.md` does not exist anywhere in the repo — AG's copy is outside the project.

**Outstanding — `C_to_AG_11.md` is written and pasted, awaiting AG.** Three defects found by running AG's code, none self-reported:
- **F1** — the startup probe only exits on 404/429, but Gemini's live failure is **503 UNAVAILABLE** (3/3 runs). It also matches on exception *substrings* and runs at import time with `sys.exit(1)`, so importing `zara.classifier` under fixtures burns a live call. Move it lazy, retry 503 with backoff, bypass under `USE_FIXTURES`.
- **F2** — `classify_social_signals` fails open: on 503 its `except Exception` returns the input unchanged, so a pet post came back `eligibility="eligible"`. Also `"eligible"` currently means three different things. Add `"unknown"`, make it non-draftable, return a typed status.
- **F3** — `orchestrator.py` silently deletes crashed fetchers. All three `asyncio.gather(..., return_exceptions=True)` blocks log the exception and append nothing, so a raising fetcher vanishes rather than appearing as `failed`.

Slice 2 is specified in the same ticket.

**Next: Slice 2 — rank → draft → verify.** Fully specified in `C_to_AG_11.md` (§S2.1–S2.6): `zara/ranker.py`, `zara/drafter.py`, `zara/verifier.py`, `RankedCard` / `PainMatch` shapes, the claim-strength ladder, and the decision-card layout.

Ranker keeps the middle term — matched pain id, score, and a one-line reason per card — because Compass VIII's syllogism is impossible without it. Verifier **retries on hallucination rather than killing the run**; on a passing retry it emits the email with `self_corrected: true` and tells the reviewer what the first pass fabricated; on a failing retry it emits the decision card with `status: blocked_hallucination` and no email.

---

## 4. Verified facts — do NOT re-derive

All confirmed with live calls this session.

### ATS
- `api.ashbyhq.com/posting-api/job-board/moderntreasury` → 200, 8 jobs. `modern-treasury` → 404. **Slug munging fails; discovery works.**
- `boards-api.greenhouse.io/v1/boards/shipbobinc/jobs` → 200, **70 jobs**. Found via domain-scoped Exa, not guessable.
- Rippling has **no public board** on any of the five platforms. Legitimate `empty`.
- **SmartRecruiters returns HTTP 200 with `totalFound=0` for any string, including gibberish.** Greenhouse/Lever/Ashby/Recruitee all 404 correctly. Validate on payload, never status.
- Greenhouse `?content=true` returns **JSON** (not XML) with HTML-entity-encoded `content`. `html.unescape()` before BeautifulSoup.

### Exa
- **Unscoped Exa is noise** (YC petitions, Wikipedia). **Scoped Exa is precise.** `includeDomains: ["linkedin.com"]` returned `linkedin.com/in/dadiomov` plus two authored posts, zero junk.
- Same trick does ATS discovery: scope to the four ATS hosts, extract the slug from the returned URL path.

### Models (called live against our key)
| Model | Result |
|---|---|
| `gemini-flash-latest` | ✅ works — **use this** |
| `gemini-3-flash-preview` | ✅ works |
| `gemini-2.5-pro` | ❌ 404, retired for new users |
| `gemini-2.5-flash` | ❌ 404 |
| `gemini-3.1-pro-preview` | ⚠️ 429, free-tier quota |

**`gemini-2.5-pro` appears in `models.list()` but 404s on `generateContent`.** Listing ≠ callable.

**`gemini-flash-latest` returns `503 UNAVAILABLE` intermittently and often** — 3/3 probe calls in one run, 2/3 in an isolated test, on a key where the real call then succeeded. **503 is the failure mode to design for, not 404.** Retry with backoff; never treat it as fatal and never let it silently pass through as success.

**Free Gemini tier is 20 requests PER DAY per model** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, quotaValue 20) — not per minute. `gemini-flash-latest` now resolves to `gemini-3.7-flash`. At ~4 calls per prospect that is 5 prospects/day; no measurement run is possible.

**DECIDED 2026-08-23: all model calls move to Groq.** `GROQ_API_KEY` is in `.env.local` and works. Model **`openai/gpt-oss-120b`** (verified via `/openai/v1/models`), OpenAI-compatible endpoint. Free tier 8,000 TPM — per minute, so a 429 means wait a full minute. Groq strict structured output **requires `additionalProperties: false` and a full `required` array on every object including `$defs`**; Pydantic's `model_json_schema()` omits both, so walk the schema. Remember `env -u GROQ_API_KEY` for the shell placeholder.

### Retrieval breadth — measured 2026-08-23
- **`ats.py` takes `jobs[:5]`** (lines 51/122/187/259/324). ShipBob's Greenhouse board has **70 jobs**; the only two that evidence our pains (*Manager, Accounting*, *Senior Financial Analyst*) are not in the first five. ShipBob therefore returns `no_signal` with `status="ok"`. Also `exa.py num_results: 2`, `news.py entries[:3]`, `apify.py items[:5]` — every prospect returns exactly 18 cards. **Filter for relevance, then truncate.**
- **Snippets take the head of the document, which is recruiting boilerplate.** In that 8,176-char job description `ledger` is at char 1789, `reconcil` at 1802, `month-end` at 1837. Head-of-document snippet → ranker scores **0.00**; evidence-densest ~500-char window → **0.80** on `close_drag`. Snippet must stay a verbatim contiguous slice; choose a better window, never rewrite.
- **A word-boundary `never_reference` veto over full job text vetoes 70 of 70 jobs.** EEO boilerplate contains "termination, layoff, recall, transfer"; benefits say "paid sick leave"; the EEO statement says "discrimination and harassment". Veto must run on the claim and the evidence window after boilerplate stripping — and a layoff is news/social content, not a job ad.

### Apify actors (verified via `api.apify.com/v2/acts/{user}~{name}/builds/default`)
- `harvestapi/linkedin-company` — cookieless, "$4 per 1k companies" ✅
- `supreme_coder/linkedin-profile-scraper` — cookieless, `"required": ["urls"]` ✅
- `curious_coder/linkedin-jobs-scraper` — cookies **optional**, caps ~400 jobs without. Cap is acceptable; **never add cookies to lift it.**
- `curious_coder/linkedin-profile-scraper` — ❌ requires `li_at` + `JSESSIONID`. Rejected.
- All 16 actor IDs in `sources.yaml` resolve.
- Apify free tier: **$5/mo, hard block, no rollover.** Rental pricing model **retires 1 Oct 2026**.

### Search landscape 2026
- **Google Custom Search JSON API: closed to new customers**, retires 1 Jan 2027. Unavailable to us.
- **Brave: free tier killed Feb 2026.** $5 credits then ~$5/1k, card required, **no spending cap.**
- Route to Google SERPs is the Apify actor.
- n8n bills **per execution**; Zapier bills **per action step**. Our 16-source fan-out is ~20 Zapier tasks vs 1 n8n execution — ~$300/mo vs $20. That is why Zapier was rejected.

---

## 5. Decisions locked

| Decision | Value | Note |
|---|---|---|
| Orchestration | **n8n Cloud** + Python core | Managed OAuth2 removes all GCP console work |
| Reasoning core | **Python**, `asyncio`, typed models | CLI must keep working — it is how we test |
| Sources | 16 Apify actors + free direct APIs | Never proxy a free endpoint through Apify |
| Apify plan | **Free tier while building**, upgrade to Starter for the measurement run | Use fixtures for dev |
| Pain list | 4 reconciliation-specific pains, in `value_prop.yaml` | Each has `observable_via` |
| ICP | 50–500 headcount, high-transaction sectors, with vetoes | From LinkedIn Company Details; degrades to `unknown`, never a guess |
| `proof_point` | **`null`, deliberately** | Inventing one is the fabrication the verifier exists to catch |
| `sender_name` | **"Zamp"** — human confirmed | Drafter must not invent a human signer |
| Gmail | `gmail.compose`, Draft→Create only | **No drafts-only scope exists** — "never send" is a code guarantee. Grep test asserts `drafts.send`/`messages.send` appear nowhere |
| X/social | Measured as low yield for ops/finance | Keep in `social`/`deep` profiles only |

---

## 6. Environment gotchas

- **`GROQ_API_KEY` in the shell is a 7-character placeholder** shadowing the real value. `dotenv` will not override an already-set env var. On `401 Invalid API Key` there is **no correct code change** — diagnose with `python3 -c "import os;print(os.environ.get('GROQ_API_KEY'))"`, work around with `env -u GROQ_API_KEY <cmd>`.
- **macOS Python SSL cert failures** hitting APIs — use `httpx` or `curl`, not `urllib`.
- `.env.local` holds live keys, gitignored. **Never echo a secret into a shell command** — AG leaked the Apify token into a chat log once; it has been rotated.
- Two files in `reference/research_results/` have names starting with `#` and containing spaces — quote them.
- Repo had no commits and no remote at session start. Check `git log` before assuming anything is saved.

---

## 7. The 10 Compasses

Design constraints. Full reasoning in `agent_transfer/C_to_AG_02.md`.

1. **Degrade, never refuse — but never silently.** Always return something; what varies is claim strength, stated on the output's face.
2. **Relocated cost.** Composition is free; the costly signal is judgment and honest self-assessment.
3. **Relevance is a three-way join.** Signal × what we sell × this person's role.
4. **Evidence before inference; inference declared.** At most one inferential step, visibly marked.
5. **Proximity to the prospect.** Authored > company action > database. `company-only` is honest, not failed.
6. **No two hooks of a kind.** One per tier. Enforced by the swap test.
7. **Absence has two meanings.** "Found nothing" ≠ "couldn't look." Ends in a request for an unlock.
8. **Earn the turn.** Hook must entail the offer.
9. **The human is a collaborator, not an inspector.** Options not verdicts; auditable in seconds; corrections compound.
10. **Relevance is not permission.** Layoffs, bereavement, litigation score highest on naive relevance and are unusable.

`empty` / `failed` / `skipped` (with reason) on every `SourceResult` is the mechanical expression of Compass VII. **A 200 response wrapping an empty or error body is `failed`, not `empty`.** This rule has been violated twice — apply it everywhere, including discovery code.

---

## 8. Open items

1. **AG to complete `C_to_AG_11.md`** — defects F1/F2/F3, then Slice 2.
2. **Slice 3 (not started)** — Gmail `gmail.compose` Draft→Create with the grep test, and the n8n leg. Deliberately deferred so Slice 2 stays runnable offline.
3. **Nothing else blocks.** Decisions taken 2026-08-23: Slice 2 ends at a reviewable artifact on disk (no Gmail, no n8n); the reviewer gets a decision card **plus** the email, losers included; the verifier is a deterministic grounding pass **then** an LLM judge.

Session memory lives at `~/.claude/projects/-Users-khadyot-Desktop-Ongoing-Projects-AI-IDE-Project-Zara/memory/`.
