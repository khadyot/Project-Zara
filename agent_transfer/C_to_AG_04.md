# C → AG 04: Slice 1 — Retrieval. Final execution ticket.

**From:** Claude (Brain)
**To:** Antigravity (Executioner)
**Date:** 2026-08-23

**Supersedes `C_to_AG_03.md`.** The human has broadened Apify's role. Everything in 03 still holds except the source register, which is replaced below.

---

## The decision that changed

Apify covers **everything relevant**, not just LinkedIn. But free direct APIs still win wherever they exist, and we must stay inside Apify's **free tier**.

Those constraints conflict on their face. The arithmetic:

- Apify free plan: **$5/month** platform credits. No rollover. **Hard block** when exhausted. 7-day data retention.
- At 20 prospects/day → 600 runs/month → **$0.008 per prospect**.
- One LinkedIn profile pull → **$0.004–0.012**.

That funds **one to two Apify calls per prospect**, not the six-to-ten "everything relevant" implies if all actors fire every run.

**Resolution: separate integration from invocation.** Wire everything relevant. Fire narrowly, ordered by cost, escalating only when cheaper rungs come back thin. This is the confidence ladder applied to money.

---

## Source register — build in this order

### Rung 0 — free, unauthenticated, always fires in parallel

| Source | Endpoint |
|---|---|
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/{token}/jobs` |
| Lever | `https://api.lever.co/v0/postings/{slug}?mode=json` |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/{name}` |
| SmartRecruiters | `https://api.smartrecruiters.com/v1/companies/{id}/postings` |
| Recruitee | `https://api.recruitee.com/c/{slug}/careers/offers` |
| Google News RSS | `https://news.google.com/rss/search?q="{company}"&hl=en-US&gl=US&ceid=US:en` |

Two to verify rather than assume:
- **Greenhouse descriptions.** The bare `/jobs` endpoint returns metadata only. The job *description* is where the reconciliation and tech-stack signal lives — find the parameter or per-job endpoint that returns body content, and report what you find.
- **SmartRecruiters** docs are pre-2025. Confirm it is live in 2026; if dead, `skipped` with that reason and tell me.

### Rung 1 — free tier, always fires

**Exa** — `EXA_API_KEY` is in `.env.local`. Query pattern is always `"{person_name}" "{company}"`, both quoted, always paired. The name alone collides and is useless.

### Rung 2 — Apify, always fires (~$0.004)

**LinkedIn Company Detail** — returns employee count, industry tags, HQ, website.

This one is always-on for a specific reason: that is exactly the **ICP rubric input** (ops/finance persona, 50–500 headcount, high-transaction sector) and the project currently has **no source for it at all**. Worth its cent on every run.

### Rung 3 — Apify, conditional (~$0.004–0.012 each)

**LinkedIn Jobs Scraper** — fires only if rung 0 produced no usable company hook (all ATS `empty` or `skipped`).
**LinkedIn Profile Scraper** — fires only if rung 1 produced no person-tier signal.

### Rung 4 — Apify, `--deep` flag or total-miss only

Indeed, SERP/Google Search, company-data enrichment, review sites, Product Hunt.

Wire **at least one** of these to prove the pattern. Register the rest in the source table without implementing them.

### Explicitly excluded

TikTok, Instagram, Craigslist, Maps, consumer social. The Store has 30,000+ actors; relevance is defined by our ICP and the hook hierarchy, not by what exists in the catalog.

### Never via Apify

Anything rung 0 already covers. Paying a vendor to proxy a free, unauthenticated, syndication-intended endpoint adds cost and a dependency for nothing.

---

## Actor selection constraints — all non-negotiable

- **Cookieless actors only.** Never one reusing the human's LinkedIn session cookie; that puts the ban on their personal account.
- **Pay-per-event or pay-per-usage only.** The **rental model retires 1 October 2026** — about six weeks out. A rental actor breaks under us. Verify the model before picking.
- **Read-only.** No connection requests, no DMs, no view automation.
- **Pin actor IDs** and record them in the repo. These are third-party code that can change or vanish.

---

## Budget guard — build this, do not defer it

Every `SourceResult` carries `cost_usd`. The run artifact totals them. Persist a running monthly tally.

**When projected spend crosses $4 of the $5, rungs 3 and 4 stop firing** and report `skipped` with reason `"budget guard"`.

Why this is not optional: the free plan **hard-blocks** rather than degrading. Without the guard, the pipeline dies mid-month and every source starts reporting `failed` for reasons that have nothing to do with the prospect — which is precisely the "couldn't look" vs "found nothing" confusion the whole system exists to prevent.

---

## Types

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
    claim: str
    signal_type: Literal["hiring", "news", "funding", "product", "person_mention", "profile", "firmographic"]
    source_url: str
    published_date: str | None
    snippet: str          # VERBATIM from source, never paraphrased
    tier: Literal["company", "person"]
    source: str

@dataclass(frozen=True)
class SourceResult:
    source: str
    rung: int
    status: RetrievalStatus
    reason: str | None    # REQUIRED when status != "ok"
    cards: list[SignalCard]
    cost_usd: float
    elapsed_ms: int
```

Enforce in `__post_init__`: `reason` non-None whenever `status != "ok"`; `cards` empty whenever `status != "ok"`. Raise on violation — that is a genuine bug, not an expected failure.

**The four statuses are the product.** `empty` = we looked, nothing there. `failed` = we could not look. `skipped` = we chose not to. A 200 wrapping an error object is `failed` — inspect the body, never trust the status code.

Every fetcher sits behind one common interface so the escalation policy can order them without knowing their internals.

---

## Slug resolver

ATS slugs are usually guessable from the company name, and **slug hit rate is the single biggest determinant of whether a prospect is workable at all.** Try candidates across all five platforms, cache hits, report the rate. If it is poor, say so — that changes the architecture and I would rather know now.

## CLI

```
python -m zara.probe --name "Priya Sharma" --company "Acme Corp" \
    [--domain acme.com] [--linkedin URL] [--deep] [--json]
```

Prints every `SourceResult` — `failed`, `empty`, `skipped` included, with reasons — then the cards, then **the run cost and the month-to-date total**.

No scoring, no ranking, no LLM, no drafting.

## Tests

1. `empty` vs `failed` — mock a 200-with-error-body, assert `failed`.
2. `SourceResult` invariants raise when violated.
3. One fetcher timing out does not fail the run.
4. **Budget guard trips** and downgrades rungs 3–4 to `skipped`.
5. Escalation: rung 3 does *not* fire when rung 0 returned usable cards.
6. Unicode and embedded quotes from `reference/competitor-research/sample-leads/test_leads.csv` (`José Müller`, `Alice "The Boss"`, `X Æ A-12`).
7. Grep test: `drafts.send` and `messages.send` appear nowhere. (There is no drafts-only Gmail scope — `gmail.compose` permits sending, so "never auto-send" is a code-level guarantee.)

---

## Environment

- Python 3.13.2. `uv` **not installed** — install it or use `venv`+`pip`; record which.
- `.env.local` has `EXA_API_KEY`, `FIRECRAWL_API_KEY`, `GEMINI_API_KEY`.
- **`APIFY_API_TOKEN` is not present.** The human is supplying it. Until it lands, all Apify fetchers return `skipped` with reason `"no APIFY_API_TOKEN"` — build so they work the moment it arrives.
- `GROQ_API_KEY` in the shell is a **7-character placeholder** shadowing the real value. `dotenv` will not override an already-set env var. On `401 Invalid API Key` there is **no correct code change** — diagnose with `python3 -c "import os;print(os.environ.get('GROQ_API_KEY'))"`, work around with `env -u GROQ_API_KEY <command>`. Not this slice, but it will bite in Slice 2.
- Repo has **no commits and no remote**. Initialize and commit this slice.

## Report back in `AG_to_C_03.md`

Run against three real companies in ICP shape (50–500 employees; payments, logistics, e-commerce, marketplaces, billing-heavy SaaS).

1. Per source, per rung: status and card count. **`failed` and `empty` broken out specifically.**
2. ATS slug hit rate across all five platforms. Which platforms actually carry our ICP?
3. **Measured cost per prospect** against the $0.008 budget. Does the free tier survive contact with reality?
4. Did rung 3 escalation trigger, and was it right to?
5. Are Exa person results signal or noise — name collisions, wrong-company matches, aggregator junk?
6. Did Greenhouse job descriptions come through, and how?
7. Which Apify actors you chose, their IDs, and their pricing model (confirm not rental).
8. Three verbatim cards, including one bad one.
9. Anything suggesting my design is wrong. Push back rather than working around it silently.

## Out of scope

Ranking, scoring, LLM calls, drafting, verification, Gmail, UI, database.

## Coming in Slice 2

Rank → draft → verify, with the verifier retrying on hallucination rather than killing the run, and flagging the self-correction to the reviewer. Ranking needs the sender's **pain list**, which does not exist yet — a human decision in flight, blocking Slice 2 but not this one.
