# Perplexity Prompt 01 — Data sources & orchestration for a B2B prospect-research agent

> **Human:** paste everything below the line into Perplexity. Use Research/Deep Research mode if available. Save the reply to `perplexity_responses/01_best_data_sources.md`.

---

**Today's date is 23 August 2026.** Prioritise sources from 2026. Explicitly flag any claim resting on information older than twelve months, and say when a cited source predates a known change in the landscape. Do not present pre-2025 legal analysis as current. Cite every factual claim with a link and a publication date.

## My context

I am building a single-prospect B2B research-and-drafting agent. Given a person's name and their company, it researches them, picks the most relevant signal, and drafts a personalised cold email for a human to review. It never auto-sends. Volume is low — 5 to 20 prospects per day, one at a time, not bulk lead-list building.

The sender sells software that helps operations teams automate manual, reconciliation-heavy processes. Buyers are ops, finance, RevOps, and supply-chain people at 50–500 employee companies in high-transaction sectors.

Constraints: solo developer, MVP in days not months, strong preference for free or low-cost tiers, and the output goes into corporate inboxes so legal and reputational exposure matters more than raw data volume.

## Part 1 — LinkedIn data extraction

Compare the realistic options for programmatically obtaining LinkedIn profile and company data in 2026:

- **Apify** LinkedIn actors — including which specific actors are current, and critically: which require the user's own session cookie versus which do not
- **PhantomBuster**
- **Bright Data** LinkedIn datasets and scraping APIs
- **Proxycurl** — I believe this shut down in 2025 after litigation; confirm or correct, with dates
- Newer entrants: ScrapIn, LinkdAPI, HarvestAPI, Linked API, or anything that has displaced the above
- The **official** LinkedIn Marketing / Sales Navigator APIs — actual cost, partnership requirements, and realistic onboarding time for a small company

For each, report:

1. **Pricing** — concrete cost per 1,000 profiles or per month at my volume, not "contact sales"
2. **Ban resistance** — does it need a logged-in session cookie? If yes, whose account gets banned when it fails? Are there published block rates?
3. **Legal exposure** — LinkedIn ToS position; the current state of *hiQ v. LinkedIn* and what the Ninth Circuit ultimately held on contract versus CFAA grounds; whether "public data" is a defence in 2026
4. **GDPR / data-protection basis** — what lawful basis vendors claim for scraped personal data, whether regulators have accepted or rejected "legitimate interest" for this use, and any enforcement actions or fines in 2025–2026
5. **Reliability** — does it actually still work, or is it a dead product with a live marketing site?

## Part 2 — Is LinkedIn even the right source?

This is the question I most want challenged rather than confirmed.

Evidence from my own earlier build: across 10 real prospects, 8 of 8 usable drafts hooked on an **ATS job posting** (Greenhouse/Lever), and not one hooked on anything the prospect had personally said or published. That suggests person-level LinkedIn data may be an expensive, legally fraught path to a tier that was not producing usable hooks anyway.

Assess honestly:

- For **B2B cold outreach personalisation specifically**, what is the measured or reported yield of person-level LinkedIn signals versus company-level signals (job postings, funding, news, product launches, earnings, hiring patterns)?
- Are there 2026 sources — practitioner writeups, vendor benchmarks, studies — on which signal types actually correlate with reply rates?
- What do the better-regarded outreach teams and tools use as their primary signal in 2026?
- **Argue the opposite case:** what does person-level LinkedIn data give that ATS + news + company blog genuinely cannot?

## Part 3 — Free and low-cost alternative sources

Evaluate current status, rate limits, cost, and reliability of:

- Greenhouse and Lever public job-board JSON APIs — are they still open and unauthenticated in 2026?
- Ashby, Workable, SmartRecruiters, Recruitee — equivalents worth adding?
- Google News RSS for company news — still viable unauthenticated, or rate-limited/deprecated?
- SEC EDGAR for US funding and filings
- Exa, Firecrawl, Brave Search, Tavily — for person-level web search; compare cost and result quality for the query pattern `"Person Name" "Company Name"`
- YouTube transcripts, podcast RSS, GitHub — worth it at this volume?
- Anything materially better that I have not listed

## Part 4 — Orchestration: pure Python versus n8n

My pipeline is: intake → parallel retrieval across sources → normalise → rank → select hook → draft via LLM → verify draft against evidence → on hallucination, retry once and flag the retry to the human → deliver as a Gmail draft.

The verification step is the important one: it must catch fabricated claims, force a redraft, and record that the redraft happened.

Address:

1. Which suits **this specific workload** — a reasoning and verification loop with retry and state, not linear integration plumbing?
2. Where does n8n stop being appropriate as agent logic deepens, and is that a real boundary or vendor positioning?
3. Testability: I need automated tests, including a "swap test" that substitutes a different prospect and asserts the draft *stops* making sense. How does each approach handle deterministic replay against fixtures?
4. Is the hybrid pattern (n8n for triggering and routing, Python for reasoning) worth the added moving parts at 5–20 runs per day?
5. If Python: is a framework (LangGraph, OpenAI Agents SDK, PydanticAI) warranted at this scale, or is plain `asyncio` with typed return values sufficient?

## Part 5 — Gmail draft creation

I want the final output saved as a **draft** in the sender's Gmail, never auto-sent.

- Current 2026 mechanics for creating a Gmail draft from Python: OAuth2 scopes needed, whether `gmail.compose` suffices or `gmail.modify` is required
- What Google's verification process demands for an app that only creates drafts — does a solo developer hit the restricted-scope security assessment, and at what point?
- Realistic setup time for a single-user internal script
- Whether there is a lower-friction path for personal/internal use

## Output format

For each part: a comparison table with concrete numbers, then a short prose recommendation. End with:

- **A single recommended stack** for this MVP, with the reasoning stated plainly
- **The strongest argument against** that recommendation
- **What you are uncertain about** and what would resolve it

Prefer primary sources — vendor docs, court filings, regulator statements — over listicles and affiliate content. Much of the "best LinkedIn scraper" content online is affiliate marketing; discount it and say when you are doing so.
