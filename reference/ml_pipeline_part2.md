**Redesigned Plan: Known-Input Prospect Research -> Personalized Draft**

**Design premise:** The rep provides the target. There is no prospect discovery, no entity resolution, no "figuring out which company." The system's entire job is: given a known person at a known company, find the most relevant real thing about them, and turn it into a draft worth sending.

---

**1. Input Contract**

```yaml
# One prospect per request
input:
  person_name: "Priya Sharma"      # required
  company: "Acme Corp"             # required - known, verified by the rep
  title: "VP Engineering"          # strongly recommended - picks the pain angle
  company_domain: "acme.com"       # optional - unlocks direct site crawling
  linkedin_url: "..."              # optional - public headline via search results

Plus one shared config the user edits once:

# value_prop.yaml - WHAT YOU SELL (the relevance lens for everything)
product: "one sentence describing your product"
buyer_titles: ["VP Engineering", "CTO", "Head of Platform"]
pains:
  - "pain 1 your product solves"
  - "pain 2"
  - "pain 3"
proof_point: "one line of credibility (customer, metric, or differentiator)"
sender_name: "..."
```

**Why this matters:** "Acme raised $30M" is a great hook for a recruiting tool, mediocre for office furniture. Relevance is judged **against the brief**, not in the abstract.

---

**2. Architecture: Two-Tier Pipeline**

```text
person + company -> [ TIER A: COMPANY DOSSIER (cached) ]
                    [ fetched once per company, ~7d TTL  ]
                    [ news • funding • hiring • launches ]
                                  |
                    [ TIER B: PERSON LOOKUP (per request)]
                    [ talks • quotes • posts • podcasts  ]
                                  |
                    NORMALIZE -> RANK -> HOOK SELECT -> DRAFT -> VERIFY -> REVIEW FILE
```

The split is the key efficiency idea: company signals are identical for all 5 prospects at Acme, so fetch once and cache. Only the cheap person-level lookup runs per prospect. At your test volume (5-10/day) this barely matters - but it makes the pipeline idempotent (re-running a prospect is free) and it's the shape that survives if volume grows.

---

**3. Stage by Stage**

**Tier A - Company dossier (all free, all keyed off the known company)**

| Signal | Source | How (given known company) | Cost |
| :--- | :--- | :--- | :--- |
| **News / announcements** | Google News RSS | `https://news.google.com/rss/search?q="Acme Corp"+when:90d` - quoted name, time-bounded | Free, no key |
| **Funding** | SEC EDGAR (US) | Company name -> CIK lookup API -> Form D / 8-K filings | Free gov API |
| **Hiring signals** | Greenhouse / Lever public APIs | Slug is usually guessable from company name (`boards-api.greenhouse.io/v1/boards/{slug}/jobs`, `api.lever.co/v0/postings/{slug}`); verify once, cache slug. Yields: open roles, team growth, tech stack from job descriptions | Free, public JSON |
| **Product launches** | Product Hunt RSS + news query `"{company}" (launches OR unveils OR announces)` | Free | |
| **Blog / press / changelog** | Direct crawl of `{company_domain}/blog`, `/newsroom`, `/careers` if domain provided | Free | |
| **Tech stack** | Inferred from job descriptions (free) instead of BuiltWith (paid) | Free | |

**Tier B - Person lookup (anchored queries)**

Every query pairs the name with the known company - this kills the name-collision problem ("Priya Sharma" alone is useless; "Priya Sharma" "Acme Corp" is precise):

- **Brave Search API** (2,000 queries/mo free): `"Priya Sharma" "Acme Corp"` -> public profiles, quotes, mentions
- **YouTube search + youtube-transcript-api** (free Python lib): `"{name}" {company} (interview OR talk OR keynote)` -> pull transcript, extract their actual stated priorities - the highest-quality person signal that exists
- **Podcasts:** `"{name}" podcast` via search -> episode RSS, show notes
- **GitHub API** (free tier): if they're an engineer, public repos/activity under their name
- **LinkedIn: no scraping** (ToS + ban risk). If the URL is provided, the search engine snippet of the public profile gives the headline - one reliable fact, honestly sourced.

**Normalize - signal cards**

Every fetcher emits the same shape. This is what makes verification possible later:

```json
{
  "claim": "Acme is hiring 12 backend engineers, all mentioning Kubernetes migration",
  "signal_type": "hiring",
  "source_url": "https://boards.greenhouse.io/acme",
  "published_date": "2026-08-18",
  "snippet": "<verbatim supporting text>",
  "tier": "company"
}
```

**Rank - the judgment you're automating**

Each card scored 0-1 on three axes (one batched Gemini Flash call, free tier):

1. **Recency** - deterministic decay, ~30-day half-life (no LLM needed)
2. **Specificity** - could this sentence apply to any company, or only this one?
3. **Relevance** - does it connect to a pain in `value_prop.yaml`, for this person's title? (CFO hook != VP Eng hook)

**Hook selection - the pairing rule**

Pick the top **company-tier** hook and the top **person-tier** hook. One of each reads as genuinely researched; two funding mentions reads as a newsletter. If person-tier comes back empty (private person, no public footprint - this will happen), fall back to top-2 company hooks and mark the draft **confidence: company-only**. Never fabricate a person-level hook.

**Draft**

One LLM call with: value prop brief + 2 hooks + sender name. Hard constraints in the prompt:

- 60-120 words, plain text, one idea
- Structure: observed fact about them -> why it likely matters -> one soft ask
- Banned: "I hope this finds you well", flattery openers, buzzwords, fake familiarity ("I've been following your journey")
- Must reference the hook's implication, not just the fact ("saw you raised $30M - congrats!" is a failing draft)

**Verify - the anti-generic guardrail (second LLM call)**

Independent check, given the draft + the signal cards:

1. **Groundedness** - every factual claim must trace to a card's snippet. Unsupported claim -> fail.
2. **Swap test** - "If I replaced the company name with a competitor's, would this email still make sense?" Yes -> fail (it's a dressed-up template).
3. **Tone** - sounds like a busy human wrote it, not a mail merge.

Fail -> one rewrite with the failure reason fed back -> fail again -> emit draft with `low_confidence` flag for stricter human review.

---

**4. Output (review UI deferred -> file-based)**

Per prospect, one file the human reads before anything goes anywhere:

```markdown
# Draft - Priya Sharma, VP Eng @ Acme Corp
confidence: high | company-only | low_confidence

## Draft
<email text>

## Evidence
1. [HIRING] Acme hiring 12 backend engineers (K8s migration) - Aug 18
   -> https://boards.greenhouse.io/acme
2. [PERSON] Priya's talk at KubeCon: "our platform sprawl is slowing us"
   -> https://youtube.com/watch?v=...

## Why these hooks
<ranker scores: recency / specificity / relevance>
```

The reviewer approves/edits/deletes the file. 30 seconds per prospect, not 5 minutes of re-research - the evidence panel is the whole point. Sending **stays manual and out of scope** - keeps the compliance story clean.

---

**5. Free Stack Summary (test volume: 5-10 prospects/day)**

| Component | Choice | Free allowance vs. usage |
| :--- | :--- | :--- |
| **LLM (rank/draft/verify)** | **Gemini Flash** via Google AI Studio | ~1,500 req/day free; you'll use ~40-60/day |
| **LLM fallback** | **Groq** (Llama 3.x) or local **Ollama** | Free |
| **Web search** | **Brave Search API** | 2,000 queries/mo free; you'll use ~100/mo |
| **News** | **Google News RSS** | Unlimited, no key |
| **Jobs/hiring** | **Greenhouse + Lever public APIs** | Unlimited, public |
| **Funding** | **SEC EDGAR** | Unlimited |
| **Talks/interviews** | **YouTube + youtube-transcript-api** | Free |
| **Storage/cache** | **SQLite** | Built into Python |
| **Orchestration** | Plain Python + `asyncio` (no framework needed at this scale) | - |

Total cost: ₹0 / $0. Free tiers are ~30x above your usage.

---

**6. Build Order (test version)**

1. **Slice 1 (day 1):** one prospect -> News RSS + Greenhouse/Lever + Brave -> signal cards printed. No LLM yet. Validate the raw signal quality first - everything depends on it.
2. **Slice 2 (day 2):** rank + hook pairing + draft + verify -> markdown file out.
3. **Slice 3 (day 3):** company dossier caching (SQLite), batch CSV in -> files out, `value_prop.yaml` config.
4. **Later:** Streamlit review UI, edit-feedback logging, more fetchers (podcasts, Product Hunt), per-person YouTube transcripts.

---

**7. How You Know It Works**

- **Swap test (automated, in the verifier):** every draft must fail when the company name is swapped for a competitor.
- **Golden set:** 10 prospects where a human pre-picks the best hook; measure ranker top-1 agreement.
- **Ground truth (when used for real):** reply rate vs. the team's template baseline. That's the only number that ultimately matters.

---

**Loose ends before building**

1. **Title availability** - if reps often *don't* know the person's title, the relevance scoring loses a dimension. Should the system treat title as truly optional, or attempt a best-effort title lookup via search? (I'd say: optional, and person-tier just scores lower without it.)
2. **Non-US companies** - SEC EDGAR only covers US filings. For Indian/global targets, funding signal falls back to news RSS (Tracxn/Crunchbase are paywalled). Acceptable?
3. **Where should this live when built** - standalone repo or a module here? (Can decide later; doesn't affect the design.)
