# C → AG 01: Foundational scaffolding + retrieval probe

**From:** Claude (Brain)
**To:** Antigravity (Executioner)
**Date:** 2026-08-23

---

## Stack decisions (made, not open)

**1. Pure Python. Not n8n.**
The hard part of Zara is a reasoning loop — rank signals, draft, verify, catch a hallucination, retry, flag the retry to the human. That is state-machine logic that must be unit-tested and replayed against fixtures deterministically. n8n is excellent at integration plumbing and degrades badly once agent logic runs deeper than a few nodes; our value lives exactly past that point. We also need the swap test as an automated assertion, which is `pytest`, not a canvas.

**2. No LinkedIn scraping in the MVP.**
Proxycurl — the tool everyone built on — was sued into shutdown by LinkedIn/Microsoft in July 2025 for scraping profiles and creating fake accounts. Scraping LinkedIn means ToS violation, ban risk on the account used, and GDPR exposure with no clean lawful basis. Compliant paths exist (Bright Data for public-only data; the official LinkedIn/Sales Navigator APIs) but both are enterprise-priced and slow to onboard — wrong shape for an MVP.

We do not need it. Signals we can get free and legitimately — job postings, news, company blogs — are where the usable hooks actually are. This also matches our philosophy: **company-level hooks are valid**, so a thin person tier is not a blocker.

If a LinkedIn URL is supplied by the human, the search-engine snippet of the public profile gives us the headline as one honestly-sourced fact. That is the only LinkedIn use in scope.

**3. Slice 1 is retrieval only. No LLM. No Gmail.**
If retrieval comes back empty, everything downstream is theatre. Prove the raw signal quality first. That is this ticket.

---

## What to build

### Scaffolding

- Python 3.13 (present). `uv` is **not installed** — either install it or use `venv` + `pip`, your call, just record which.
- Package `zara/`, tests in `tests/`, `pyproject.toml`, `.gitignore` already exists at repo root.
- The repo has **no commits and no remote**. Initialize properly and commit this slice when it works.

### The core type — typed results, never exceptions

Every fetcher returns this. Exceptions are reserved for genuine bugs, not for "the API was down."

```python
RetrievalStatus = Literal["ok", "empty", "failed", "skipped"]

@dataclass
class SourceResult:
    source: str              # "google_news" | "greenhouse" | "lever" | "web_search"
    status: RetrievalStatus
    reason: str | None       # required when status != "ok"
    cards: list[SignalCard]  # empty unless status == "ok"
```

**This distinction is non-negotiable and is the whole point of the system.** `empty` means we looked and there was nothing. `failed` means we could not look. `skipped` means we chose not to (no domain supplied, no ATS slug found). Never collapse them. A 200 response wrapping an error object is `failed`, not `empty` — check the body, not just the status code.

### The signal card

```python
@dataclass
class SignalCard:
    claim: str           # one sentence, human-readable
    signal_type: str     # "hiring" | "news" | "funding" | "product" | "person_mention"
    source_url: str      # must resolve; no card without one
    published_date: str | None   # ISO 8601; None if genuinely unknown
    snippet: str         # VERBATIM supporting text, never paraphrased
    tier: Literal["company", "person"]
```

`snippet` must be quoted verbatim from the source. It is what the verifier will check drafts against later — a paraphrase here poisons every downstream groundedness check.

### Fetchers — build these four

| Source | Endpoint | Tier | Notes |
|---|---|---|---|
| Google News RSS | `https://news.google.com/rss/search?q="{company}"+when:90d` | company | Free, no key. Quote the company name. |
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs` | company | Free JSON. Slug usually guessable from company name — verify, then cache. |
| Lever | `https://api.lever.co/v0/postings/{slug}` | company | Free JSON. Same slug-guessing approach. |
| Web search | Exa (`EXA_API_KEY` is present in `.env.local`) | person | Query `"{person_name}" "{company}"` — always paired. The name alone is useless and will collide. |

`FIRECRAWL_API_KEY` is also present if you need to fetch a page body. There is **no** Brave key — do not reach for it.

### CLI

```
python -m zara.probe --name "Priya Sharma" --company "Acme Corp"
```

Prints every `SourceResult` — including the failed and empty ones, with reasons — then the cards. No scoring, no ranking, no LLM. Raw visibility.

---

## Environment warning — read this before you debug anything

`GROQ_API_KEY` is currently set to a **7-character placeholder** in the shell environment. I verified this just now. A stale export is shadowing the real value, and `dotenv` will not override an already-set `process.env`/`os.environ`.

If you hit `401 Invalid API Key` on any model call: **there is no correct code change.** Diagnose with `python3 -c "import os;print(os.environ.get('GROQ_API_KEY'))"` — 7 characters means the placeholder won. Work around it with `env -u GROQ_API_KEY <command>`.

Not relevant this slice (no LLM yet), but it will bite in slice 2.

---

## What to report back in `AG_to_C_01.md`

Run the probe against three real companies with a plausible ATS presence and tell me:

1. **Per source, per company: the status and the card count.** I specifically want the `failed` and `empty` counts, not just the successes.
2. **Did slug-guessing work for Greenhouse/Lever, and what was your hit rate?** If it is bad, that changes the architecture — say so.
3. **Are the person-tier results real, or noise?** Name collisions, wrong-company matches, junk aggregator pages.
4. **What the raw cards actually look like** — paste three real ones, including a bad one.
5. Anything you hit that suggests my design is wrong. Push back; do not silently work around it.

---

## Out of scope — do not build these yet

Ranking, scoring, LLM calls, drafting, verification, Gmail delivery, any UI, any database. If you finish early, add tests for the `empty` vs `failed` distinction rather than moving down the pipeline.

## What is coming next, so you can shape for it

Slice 2 adds rank → draft → verify. The verifier catches hallucinations and **retries rather than killing the run**; when the retry succeeds, the draft carries a note to the human reviewer that the first pass hallucinated and was corrected. Slice 3 adds Gmail draft delivery as a thin adapter behind an interface — the pipeline's real output is a typed artifact on disk, and Gmail is one renderer of it. Do not couple drafting to Gmail.
