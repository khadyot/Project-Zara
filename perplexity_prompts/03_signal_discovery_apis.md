# Perplexity Prompt 03 — Observable signals of operational pain, and the APIs that surface them (2026)

> **Human:** paste everything below the line into Perplexity. Use Research/Deep Research mode if available. Save the reply to `perplexity_responses/03_signal_discovery_apis.md`.

---

**Today's date is 24 August 2026.** Prioritise sources from 2026. Cite every pricing, coverage, or limit claim with a link and a publication date, preferring the vendor's own docs or pricing page over third-party summaries. Flag anything resting on information older than twelve months. If a product looks alive on its marketing site but is effectively dead, say so. Never estimate a price — if it is gated behind "contact sales", report that as the finding.

## My context

I run a single-prospect B2B research agent. Input is one person's name plus their company. It fans out across sources, ranks what it finds against a fixed list of business pains, and drafts one personalised cold email for a human to review. It never auto-sends. Volume is **5–20 prospects per day**, interactive, one at a time — **not** bulk lead-list building, so per-record pricing matters far more than seat pricing.

The sender sells software that automates manual, reconciliation-heavy operations and finance work. Targets are ops, finance, RevOps, and supply-chain leaders, mostly at **50–2,000 employee, privately held** companies — the hard case, because they file nothing and issue few press releases.

Two constraints on your answer:

- **I have deliberately removed job postings / ATS data from my pipeline.** Do not recommend job-board APIs, ATS scrapers, hiring-signal vendors, or job-description mining. That path is closed. This is the single most important constraint in this prompt.
- I have already researched LinkedIn scraping vendors and workflow orchestration. **Do not re-cover those.**

## The core problem

My email must connect a *specific observed fact* about the company to a *specific operational pain*, or it is generic spam. The pains I sell against are things like:

- Month-end close drags because matching is manual across systems
- Payment, ledger, and bank reconciliation breaks silently and surfaces late
- Ops headcount scales linearly with transaction volume
- Exceptions get handled in spreadsheets with no audit trail

Historically I detected these from job descriptions, which state them in the employer's own words. Having removed that source, **I need to rebuild my list of observables from scratch.**

## Part 1 — What publicly observable signals evidence operational or reconciliation pain?

This is the most important part of the prompt. For a **private, 50–2,000 employee company**, what publicly available, machine-retrievable signals correlate with the pains above? Be concrete and mechanical — I need things a script can fetch, not intuitions.

Consider at minimum, and add whatever I have missed:

- **Tech-stack change detection** — a company adding a new payment processor, ERP, billing platform, or bank integration. What detects this: BuiltWith, Wappalyzer, HTTP Archive, TheirStack's tech signals, or something else? Does any of it work for *back-office finance* systems, or only for front-end web tech?
- **ERP / finance-system migration signals** — implementation-partner case studies, systems-integrator announcements, certification directories, user-group and community-forum posts.
- **Integration, partner, and marketplace listings** — a company appearing in a payment provider's or ERP's partner directory, and when that listing changed.
- **Developer-facing artefacts** — public API docs, changelogs, status pages, and status-page incident history. Do incident histories reveal reconciliation or settlement problems in a usable way?
- **Procurement and RFP notices**, where public.
- **Conference, webinar, and podcast speaker listings** for finance/ops roles — do accessible directories of these exist?
- **Review-site movement** — G2/Capterra/TrustRadius reviews *written by* the company's staff about tools they use, which reveals their actual stack and complaints.
- **Community footprints** — Reddit, Slack/Discord communities, Stack Overflow, and accounting/finance forums where staff describe their own workflows.

For each signal you propose, answer:

1. **What exactly does it observe**, and which of my four pains would it credibly evidence?
2. **Is it retrievable by API or scrape** at 5–20 companies/day, and by what specific service?
3. **How often is it present** for a private mid-market company — is this a signal I will find for 5% of targets or 60%?
4. **Does it carry a date**, so I can tell recent from stale?
5. **False-positive risk** — how often does this signal appear for companies that do *not* have the pain?

Rank your proposals by **expected hit rate × evidential strength**, and say plainly which ones are not worth building.

## Part 2 — Web search APIs, judged on three properties I have measured

Compare **Exa**, **Tavily**, **Firecrawl**, **Serper**, **Brave Search API**, **SearXNG** (self-hosted), and current alternatives, on these specifically:

1. **Date filtering at query time** — can I constrain to the last N months? Name the exact parameter. Without this I get five-year-old funding news ranked as current news; I measured exactly that.
2. **Date reliability in results** — does every result carry a publication date? In my own measurements only **17–26%** of returned items had a parseable date, and one provider returned **zero dates across 32 results**. Any published evaluation of this per vendor.
3. **Snippet windowing — the property I most want an answer on.** When a long page matches, does the API return the text *around the match*, or the top of the document? I measured this on my own data: the head-of-document snippet scored **0.00** for relevance, while the evidence-dense window from the *same document* scored **0.80**. Same page, same query, 0 vs 0.8 purely on which ~500 characters come back. Which vendors return match-centred windows, which return document-head, and which return full text so I can window it myself?
4. **Person-level precision and namesake handling** — searching a person's name plus their company. Does any vendor expose entity disambiguation rather than plain keyword matching?
5. **Domain scoping** — include/exclude domain lists, and whether scoping degrades quality.
6. **Free tier and first paid tier**, concretely, at 5–20 prospects/day with ~6–10 queries each.

Give a direct verdict on **Exa versus Tavily** for this exact job. I currently run both and want to know whether that is justified or redundant.

## Part 3 — Company resolution, and firmographic / event feeds

1. **Company name → official domain**, reliably, handling typos and legal-suffix variations. Free options first. What replaced Clearbit's free domain lookup after the HubSpot acquisition, and is anything comparable free in 2026?
2. **Funding, leadership change, M&A, and expansion feeds** with a usable free or cheap tier at low volume — Crunchbase's current API terms, Harmonic, Specter, Ocean.io, Tracxn, or open alternatives. Real cost for ~20 company lookups a day. New finance leadership and expansion financing are two of my strongest remaining pain proxies, so this matters more than it would otherwise.
3. **Firmographics (headcount, sector)** from a source returning a *number* rather than a marketing page. Cheapest reliable option at this volume. Note: this only annotates a decision card and never rejects a prospect, so approximate data is fine — but "unknown" must be distinguishable from "wrong".

## Part 4 — What serious outbound teams actually use in 2026

Setting aside LinkedIn, generic news, and job boards: what signal sources do effective outbound teams use today that I have not listed? For each, say whether it is realistically automatable at 20 lookups/day, what it costs, and what pain it evidences. I am specifically interested in anything that works for **private companies that publish very little**.

## Output I want

1. **A ranked table of observable signals** — signal, what it evidences, how to retrieve it, expected hit rate for a private mid-market company, date availability, false-positive risk.
2. **A proposed replacement list of `observable_via` conditions** for the four pains above, written concretely enough that a script could test them. This is the deliverable I care most about.
3. A comparison table for the search APIs covering date filtering, date reliability, snippet windowing, and price.
4. One direct answer: **which single purchase, if any, most improves prospect quality at 5–20 prospects/day?** Name it, price it, justify it.
5. An honest list of the pains above that you believe are **not reliably observable** for a private mid-market company without job-posting data — I would rather cut a pain than pretend I can detect it.
