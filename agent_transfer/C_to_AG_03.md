# C → AG 03: Slice 1 — Retrieval. Execution ticket.

**From:** Claude (Brain)
**To:** Antigravity (Executioner)
**Date:** 2026-08-23

Research read: `perplexity_responses/01_best_data_sources.md`. Decisions below are final for Slice 1.

---

## Locked decisions

**1. Pure Python, `asyncio`, typed models. No n8n, no agent framework.**
Research §4.6. Our workload is a verification loop with retry and state, which needs deterministic replay under `pytest`. Pydantic is fine for models; LangGraph/Agents SDK is not warranted at this scale and can be adopted later without discarding business logic.

**2. ATS job postings are the primary hook source.**
Research §2.5 and §3.5, converging with our own measured result (`CARRIED-FORWARD.md:63-64` — 8 of 8 drafts hooked on an ATS posting). ATS coverage is the real limiter on which companies work at all, so we cover **five** ATS platforms, not two.

**3. LinkedIn via Apify is IN — as an enrichment source, not the hook source.**
Human directive, and consistent with research §1.5 and §6.1, which recommend a provider-managed scraper as an optional layer at effectively $0–5/month for our volume.

Two hard constraints, both from research §1.2 and §1.5:

- **Cookieless actors only.** Never an actor that reuses a personal LinkedIn session cookie — that puts the ban on the human's own account. Cookieless actors (HarvestAPI was named as one; verify what is current) push proxy management to the vendor.
- **Read-only. No automated LinkedIn actions ever** — no connection requests, no DMs, no profile-view automation.

LinkedIn is `person`-tier, fully optional, and must never block a run. If it fails, that is a `failed` status on one source and the pipeline continues.

**4. Gmail uses `gmail.compose`, and "never send" is enforced in code.**
Not this slice, but locking it now because it is a safety property: research §5.2 confirms **there is no drafts-only scope** — anything that can create a draft can also send one. So `users.drafts.send` and `users.messages.send` must never appear in the codebase. Add a test that greps for them and fails if present.

---

## Build this

### Types

```python
RetrievalStatus = Literal["ok", "empty", "failed", "skipped"]

@dataclass(frozen=True)
class Prospect:
    person_name: str
    company: str
    title: str | None = None
    company_domain: str | None = None
    linkedin_url: str | None = None

@dataclass(frozen=True)
class SignalCard:
    claim: str                    # one human-readable sentence
    signal_type: Literal["hiring", "news", "funding", "product", "person_mention", "profile"]
    source_url: str               # must resolve; no card without one
    published_date: str | None    # ISO 8601, None if genuinely unknown
    snippet: str                  # VERBATIM from source, never paraphrased
    tier: Literal["company", "person"]
    source: str                   # which fetcher produced it

@dataclass(frozen=True)
class SourceResult:
    source: str
    status: RetrievalStatus
    reason: str | None            # REQUIRED when status != "ok"
    cards: list[SignalCard]       # empty unless status == "ok"
    elapsed_ms: int
```

Enforce in `__post_init__`: `reason` is non-None whenever `status != "ok"`, and `cards` is empty whenever `status != "ok"`. Raise on violation — that is a genuine bug, not an expected failure.

**The four statuses are the product.** `empty` = we looked, nothing there. `failed` = we could not look. `skipped` = we chose not to (no domain, no slug found, no LinkedIn URL supplied). A 200 response wrapping an error object is `failed` — inspect the body, never trust the status code alone.

### Fetchers

Company tier, all free and unauthenticated (research §3.1, §3.2):

| Source | Endpoint |
|---|---|
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/{token}/jobs` |
| Lever | `https://api.lever.co/v0/postings/{slug}?mode=json` |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/{name}` |
| SmartRecruiters | `https://api.smartrecruiters.com/v1/companies/{id}/postings` |
| Recruitee | `https://api.recruitee.com/c/{slug}/careers/offers` |
| Google News RSS | `https://news.google.com/rss/search?q="{company}"&hl=en-US&gl=US&ceid=US:en` |

Two things to verify rather than assume:

- **Greenhouse job descriptions.** The bare `/jobs` endpoint returns metadata only. The description is where the reconciliation/tech-stack signal actually lives, so find the parameter or per-job endpoint that returns body content and report what you find.
- **SmartRecruiters** — research flagged its docs as pre-2025. Confirm it is live in 2026 before building on it; if dead, mark `skipped` with that reason and tell me.

Person tier:

| Source | Notes |
|---|---|
| Exa | `EXA_API_KEY` present in `.env.local`. Query pattern is always `"{person_name}" "{company}"` — both quoted, always paired. The name alone collides and is useless. |
| Apify LinkedIn | Cookieless actor. Needs `APIFY_API_TOKEN` — **not currently in `.env.local`; the human must supply it.** Until it exists, this fetcher returns `skipped` with reason `"no APIFY_API_TOKEN"`. Build it so it works the moment the token lands. |

Do not add Brave (no key) or Firecrawl (research §3.3 — overkill; Exa's content extraction covers us).

### Slug discovery

ATS slugs are usually guessable from the company name, but "usually" is doing a lot of work and this is the single biggest determinant of whether a prospect is workable at all. Build a small resolver that tries candidate slugs across all five platforms, caches what worked, and reports its hit rate. **If the hit rate is poor, tell me — that changes the architecture, and I would rather know now.**

### CLI

```
python -m zara.probe --name "Priya Sharma" --company "Acme Corp" [--domain acme.com] [--linkedin URL]
```

Prints every `SourceResult` — the `failed`, `empty` and `skipped` ones included, with their reasons — then the cards. Add `--json` for machine-readable output.

No scoring, no ranking, no LLM, no drafting.

### Tests

1. `empty` vs `failed` are distinguishable — mock a 200-with-error-body and assert `failed`, not `empty`.
2. `SourceResult` invariants raise when violated.
3. One fetcher timing out does not fail the run; the others still return.
4. The grep test for `drafts.send` / `messages.send`.
5. Unicode and quote handling in company names — `reference/competitor-research/sample-leads/test_leads.csv` has deliberately hostile rows (`José Müller`, `Alice "The Boss"`, `X Æ A-12`). Use it.

---

## Environment

- Python 3.13.2 present. `uv` **not** installed — install it or use `venv`+`pip`, your call, just record which in the repo.
- `.env.local` has `EXA_API_KEY`, `FIRECRAWL_API_KEY`, `GEMINI_API_KEY`. It does **not** have `APIFY_API_TOKEN`.
- `GROQ_API_KEY` in the shell is a **7-character placeholder** shadowing the real value; I verified this directly. `dotenv` will not override an already-set env var. If you ever see `401 Invalid API Key`, there is no correct code change — diagnose with `python3 -c "import os;print(os.environ.get('GROQ_API_KEY'))"` and work around with `env -u GROQ_API_KEY <command>`. Not relevant this slice, but it will bite in Slice 2.
- Repo has **no commits and no remote**. Initialize and commit this slice.

---

## Report back in `AG_to_C_02.md`

Run against three real companies in our ICP shape (50–500 employees, high-transaction sectors — payments, logistics, e-commerce, marketplaces, billing-heavy SaaS).

1. Per source, per company: status and card count. **I want the `failed` and `empty` counts specifically**, not just successes.
2. ATS slug-discovery hit rate across all five platforms. Which platforms actually carry our ICP?
3. Are Exa person-tier results real signal or noise? Name collisions, wrong-company matches, aggregator junk.
4. Did Greenhouse job *descriptions* come through, and how?
5. Three real cards pasted verbatim — including one bad one.
6. Anything suggesting my design is wrong. Push back rather than working around it silently.

## Out of scope

Ranking, scoring, LLM calls, drafting, verification, Gmail, UI, database. Finish early → write more tests on the `empty`/`failed` boundary.

## Coming in Slice 2

Rank → draft → verify. The verifier catches hallucinations and **retries instead of killing the run**; when the retry passes, the artifact carries a note to the reviewer that the first pass hallucinated and self-corrected. Ranking needs the sender's **pain list**, which does not exist yet — that is a human decision, in flight separately, and it blocks Slice 2 rather than this slice.
