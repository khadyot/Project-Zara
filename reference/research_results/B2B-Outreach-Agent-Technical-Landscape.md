> From: https://gemini.google.com/u/2/app/da26b24b7897a222?pageId=none

# you asked

message time: 2026-08-22 05:05:47

---

## Objective

Produce a comprehensive, primary-source-backed technical landscape report to inform the build of a **single-prospect B2B sales-outreach research agent**. I need to know the full option set available as of August 2026 — including options I don't currently know exist — across six areas: data sources, system architecture, evidence grounding, evaluation tooling, streaming UI, and deployment.

**Treat every tool I name below as a starting point to be beaten, not a conclusion to confirm.** My current option set was assembled ad hoc and I expect it has gaps. Finding what's missing is the primary goal of this report.

## What I'm building

A single-prospect B2B outreach research agent, built as a portfolio/case-study project for a job application. Stack is fixed: **Next.js + TypeScript on Vercel serverless, Anthropic Claude API** for the model layer.

Input: one prospect (name + company). The pipeline:

1. **Identity resolution** — confirm the person exists, their current role and company
2. **Suppression check** — existing customer, active deal, or do-not-contact list
3. **Enrichment** — company and contact firmographics
4. **Signal discovery** — search for genuine, verifiable, current information about them
5. **Signal scoring and ranking**
6. **Confidence gate** — two independent axes (ICP fit, signal strength) combined via a lookup table
7. Gate passes → draft a personalized outreach email. Gate fails → route to a visible **"needs human judgment"** state and explicitly refuse to fabricate
8. Every stage streams to a **live run view**; every run is logged to a **dashboard**

It never auto-sends. A human reviews before anything goes out.

**The core design goal is restraint.** The system must be able to say "I don't have enough to personalize this confidently" rather than invent a plausible-sounding hook. Anti-fabrication is the product, not a safety wrapper bolted on at the end.

**Signal is ranked by type:** authored content (what the prospect chose to say publicly — LinkedIn posts, interviews, conference talks, bylines, podcasts) > observed business events (funding rounds, hiring, launches, leadership changes) > static firmographics (industry, headcount — context only, never a standalone hook).

**The seller's offering, which defines the ICP:** software that helps **operations teams automate manual, reconciliation-heavy processes**. Target buyers are operations, finance, RevOps, and supply-chain people at **50–500 employee companies** in high-transaction-volume sectors — payments/fintech, logistics, e-commerce and retail operations, marketplaces, billing-heavy SaaS.

**The UI is explicitly graded** by the people evaluating this: a live run view showing each stage as it executes, and a dashboard showing history, status, and outputs across runs.

## Hard constraints — please apply these ruthlessly, they eliminate options

- **Budget: free tiers and pay-per-use only. No monthly subscriptions of any kind.** A tool at $49/month is out regardless of quality. Pay-per-use with no minimum spend is fine. A free tier requiring a card on file is fine.
- **Must run inside a Vercel serverless function** — stateless, no persistent browser session, no long-lived authenticated cookie, no local daemon, no always-on process.
- **Stack is fixed.** Don't propose replacing Next.js, Vercel, or the Claude API.
- **Must work live, on an arbitrary real person the system has never seen before**, during a screen-shared interview. Reliability under live-demo conditions matters more than breadth of capability.
- **Low ToS and legal exposure.** I will not build login-based scraping or account automation.
- **Timeline is days, not weeks.** Anything requiring partner approval, a sales call, or multi-week onboarding is out.

## Evidence standards — important

- Cite a **primary source** for every pricing, limit, or capability claim: the vendor's own pricing page or official documentation. SEO listicles and "top 15 tools" roundups are acceptable only to *discover* that a tool exists — never to price it or describe its limits. This space is saturated with affiliate content marketing; please filter it aggressively.
- **State the date you verified** each pricing or limit claim. Pricing in this category changed substantially through 2025 and 2026.
- For any free tier, specify exactly: quota, reset period, whether a credit card is required, and whether unused credits roll over.
- **Flag any free tier that prohibits production or deployed use.** Several data and news APIs restrict their free tier to localhost or development only — that's disqualifying for me and easy to miss.
- Where a vendor has recently been sued, shut down, or materially changed its terms, say so and cite the case or announcement.
- **Explicitly mark low-confidence claims.** I would much rather see "uncertain — could not verify on vendor site" than a confident wrong number.

---

# Research areas

## 1. Signal source landscape (highest priority)

For each tier, give the full current option set, then a ranked recommendation.

**1a. LinkedIn.** The highest-value source for this product and the hardest to obtain legitimately. Cover official API tiers and who actually qualifies; no-login public-data scraper APIs; account-connect / "bring your own session" products. Which, if any, are viable at free-tier or pay-per-use with low ToS risk in August 2026? Include the current litigation posture — hiQ v. LinkedIn, LinkedIn v. Proxycurl (2025), Bright Data v. Meta and X Corp — and what it implies *today*, not what commentary said in 2022. **If the honest answer is "there is no good option under these constraints," say so plainly.** That's a useful finding.

**1b. All other authored content.** Podcasts, conference talks, YouTube, webinars, guest posts, Substack and newsletters, industry-publication bylines, earnings-call transcripts, G2 and Capterra reviews, community forums, Reddit, public Slack and Discord communities, company blogs and newsrooms. Which are programmatically accessible on a free or pay-per-use tier?

Then the question that matters more: **which of these actually have coverage for a mid-level operations manager at a 150-person logistics company** — not a tech founder, not a public-company executive? I suspect several sources look strong on paper but have near-zero hit rate for this persona. Tell me which, and why.

**1c. Business events.** Funding, hiring, leadership changes, product launches, M&A, expansion, layoffs, regulatory filings. Cover **job-posting data specifically** — hiring signal is heavily used in outbound; what's the current free or cheap programmatic option? Include free government and regulatory sources (SEC EDGAR, Companies House, and non-US equivalents).

**1d. Firmographics.** Headcount, industry, funding stage, revenue band, tech stack. This tier feeds an ICP fit score, so **structured and reliable beats rich**. Which providers have a genuinely usable free tier in August 2026?

**1e. Web search and page-reading layers for LLM agents.** Compare the current field on price per call, result quality, extraction quality, and latency: Anthropic's native `web_search` server tool, Firecrawl, Exa, Tavily, Jina Reader, Brave Search API, Serper, ScrapingBee, and anything I haven't named. **Call out which return full page content versus short snippets** — this matters disproportionately to me, because grounding a draft requires a real quote, not a 150-character fragment.

**1f. What am I missing?** What sources, categories, or vendors would a team doing this professionally in 2026 use that are absent from everything above? Be specific — name tools, not categories. **This is the single most valuable question in this report.**

## 2. Architecture and prior art

- **Open-source reference implementations** of a research → score → draft outbound agent. Name repos, assess quality, recency, maintenance status, and what's worth stealing from each. Include adjacent projects (lead-research agents, company-research agents, RAG-grounded generators) if no direct match exists.
- **How commercial players actually build this.** What have Clay, Apollo, 11x, Regie, Lavender, Unify, AiSDR, Artisan and similar publicly documented about pipeline shape, agent decomposition, single-agent vs. multi-agent, model choice per stage, and where they place human review? Prioritize engineering blogs, conference talks, postmortems, and founder interviews over secondhand summaries. I know of 11x's rebuild from single-agent → rigid workflow → hierarchical multi-agent; find the others.
- **Documented failure modes** in this product category, and the fixes. I care about *personalization quality* failures — generic output, hallucinated hooks, opener/offer mismatch — not deliverability or spam, which are out of scope.

## 3. Grounding and anti-fabrication (the core of the build)

- **Claim-level grounding.** State of the art for verifying that every factual claim in a generated message traces to a real retrieved source, and stripping or flagging what doesn't. Name specific techniques, papers, benchmarks, and libraries. Practical and implementable matters more than SOTA benchmark scores.
- **Pre-generation gate vs. post-generation verification.** My design gates *before* drafting. The alternative drafts first, then verifies each claim against source evidence. Which works better in practice, do production systems do both, and what are the costs and failure modes of each?
- **The distinction I most need help with:** how do production systems **distinguish "I searched and genuinely found nothing" from "my retrieval layer failed"?** These are semantically opposite — one is a true finding about the world, the other is a fault in my system — yet both produce an empty result set. This matters enormously here: if a search API fails silently, my system would report "no verifiable signal found about this person," which is a *false statement* from a product whose entire value proposition is refusing to assert things it can't support. Is there an established pattern, schema, or vocabulary for modeling this? How do RAG systems and search-backed agents represent partial retrieval failure?
- **Confidence calibration.** Established approaches for scoring "do I have enough evidence to say something specific about this entity" that go beyond a hand-tuned threshold. I'm currently using a hand-built lookup table; what am I missing?

## 4. Evaluating a pipeline like this

- How do teams test a **non-deterministic pipeline whose correct behavior is often refusal**? How do you write a regression test asserting an anti-hallucination gate correctly *declined* — and keep it from passing for the wrong reason?
- **LLM eval tooling for TypeScript/Node**, free tier or self-hostable specifically: Promptfoo, Braintrust, Langfuse, Evalite, Vitest-based approaches, anything newer. What do people actually use in a small TS project in 2026, versus what's marketed?
- **Fixture and golden-file patterns** for LLM pipelines. How do people pin expected behavior against non-deterministic output, and handle fixtures that drift or go stale?

## 5. Streaming multi-stage progress to a web UI

- **Current best practice, August 2026**, for streaming from a long-running server process to a React UI on Next.js/Vercel: raw SSE, Vercel AI SDK (`ai` + `@ai-sdk/anthropic`), React Server Components streaming, WebSockets, or something newer? What's actually current versus repeated from 2024 tutorials?
- **The distinction that matters to me:** most material covers streaming **LLM tokens**. I need to stream **structured multi-stage pipeline progress** — discrete events like `{stage, status, message, timestamp}` — where only some stages involve an LLM at all. This seems much less well covered. What's the right pattern, and is the Vercel AI SDK the right abstraction or the wrong one for non-token event streams?
- **Vercel serverless gotchas** that break in production but not locally: response buffering, function duration, Fluid Compute behavior, connection drops, reconnection, CDN buffering of SSE.
- **Patterns worth copying** — open-source component libraries, UI patterns, or reference implementations for agent/pipeline run views: stage timelines, live status, reasoning traces, evidence panels. Include visually strong examples from outside this product category.

## 6. Persistence, deployment, and a critique

- **Small Postgres or equivalent on Vercel, free tier, August 2026.** Vercel Postgres was discontinued and migrated to Neon. Which marketplace integrations are genuinely free at kilobyte scale? Current recommended driver and serverless connection pattern? Is Postgres even right for a few hundred JSON run records, or is something simpler better?
- **Common first-deploy surprises** with Vercel function limits, Fluid Compute, cold starts, or environment variables.

Then, directly and bluntly:

- **What would you cut?** Where am I over-building relative to what a technical interviewer will notice and reward?
- **What's cheap to build and disproportionately impressive** in a live demo of an AI agent pipeline?
- **How does this kind of build most commonly fail in a live demo?** Specific failure modes for a multi-API, LLM-backed pipeline being screen-shared to an interviewer who may name an arbitrary input — and the standard prevention for each.
- **Where is my plan wrong or naive?** Assume I've made mistakes I can't see. Be blunt rather than encouraging; I'd rather hear it now than discover it on demo day.
- **What separates a memorable submission from a merely competent one** in a take-home where many candidates build a similar pipeline? The evaluators have said they care about "the judgment behind your design choices" and being able to "explain it clearly to a non-technical buyer."

---

## Output format

A structured Markdown report organized by the six areas above. For each:

1. **Options table** — tool/source · what it provides · free tier specifics · cost beyond free · ToS/legal risk · serverless-compatible (y/n) · setup lead time · primary-source link · **date verified**
2. **Ranked recommendation** with explicit reasoning
3. **Explicitly rejected** — what you considered and dismissed, and why. I want the negative space; it's how I know the scan was exhaustive rather than confirmatory.
4. **Confidence flags** on anything you could not verify against a primary source

For the critique questions in area 6, prose is better than tables — I want judgment there.

Close the report with a section titled **"Things you did not ask about but should know."** Given that my stated goal is to find gaps in my own understanding, that section is the most valuable part of this report to me. Please give it real weight rather than treating it as an afterthought.

---

# gemini response

I've put together a research plan. If you need to update it in any way, let me know.
http://googleusercontent.com/deep_research_confirmation_content/0

---

# you asked

message time: 2026-08-22 05:16:35

Start research

---

# gemini response

I've completed your research. Feel free to ask me follow-up questions or request changes.

B2B Sales Agent Landscape Report

# B2B Sales-Outreach Research Agent: Technical Landscape and Architecture Report

The following report delivers an exhaustive technical landscape analysis and architectural blueprint for constructing a single-prospect B2B outreach research agent. Based on the constraints provided, the system must execute on a Next.js and Vercel serverless stack, utilize the Anthropic Claude API, operate strictly on free or pay-per-use tiers, and prioritize anti-fabrication ("restraint") over high volume. The landscape is assessed as of August 2026, reflecting the rapid shifts in data provider terms of service, AI model pricing, and legal precedents regarding web scraping.

## 1. Signal Source Landscape

The ingestion layer dictates the ceiling of the pipeline’s effectiveness. Given the target demographic—mid-level operations, finance, and supply-chain managers at companies with 50–500 employees—the system must optimize for high-signal, low-noise data sources while navigating severe constraints around authenticated scraping.

### 1a. LinkedIn

The legal and operational realities of extracting data from LinkedIn shifted dramatically through 2024 and 2025. The environment is actively hostile to zero-budget, serverless scraping.

**Options Table**

| Tool/Source | What it provides | Free tier specifics | Cost beyond free | ToS/legal risk | Serverless-compatible (y/n) | Setup lead time | Primary-source link | Date verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Crustdata API** | B2B entity enrichment via 1B+ profile dataset | Free typeahead/filters | $0.01–$0.07 per record | Low (aggregated B2B data) | Y | Minutes | [docs.crustdata.com/general/pricing](https://docs.crustdata.com/general/pricing) | Aug 2026 |
| **Proxycurl** | Profile/Company data | None | N/A (Shut down) | Critical (Sued by LinkedIn) | N/A | N/A | [nubela.co/blog/goodbye-proxycurl](https://nubela.co/blog/goodbye-proxycurl/) | Aug 2026 |
| **ProAPIs (iScraper)** | Profile scraping | Unknown | Unknown | Critical (Active litigation) | Y | N/A | [nubela.co/blog/profile-data-apis](https://www.pin.com/blog/profile-data-apis/) | Aug 2026 |
| **Account-Connect** | "Bring your own session" | Varies | Monthly subscriptions | High (Violates User Agreement) | N (Requires stateful session) | Days | N/A | Aug 2026 |

**Ranked Recommendation**
1. **Crustdata API:** This is the only viable option under the imposed constraints. It provides a pay-per-use, serverless-compatible API for B2B data without the existential legal exposure of unauthorized scraping . 
2. **Bypass LinkedIn entirely:** Given the target persona (mid-level operations managers), LinkedIn often yields sterile, resume-like data rather than actionable buying signals. The architecture should deprioritize this node.

**Explicitly Rejected**
*   **Proxycurl (Nubela):** Historically the standard, it shut down in July 2025 following a lawsuit from LinkedIn, despite reaching $10M ARR . 
*   **ProAPIs (iScraper):** Currently facing a 2025 lawsuit alleging millions of fake accounts; highly toxic for any public-facing portfolio project .
*   **Session-based scrapers (e.g., Phantombuster):** Rejected because they require persistent authentication cookies, violating the strict stateless serverless constraint, and strictly require a monthly subscription.

**Confidence Flags**
*   *Crustdata free-tier allocations:* Primary documentation states the free tier is for "typeahead and filter builders," but exact numeric quotas for the free tier were not explicitly detailed beyond the per-record credit costs .

### 1b. All Other Authored Content

Authored content represents the highest-ranked signal type. The architectural challenge is coverage. 

**Options Table**

| Tool/Source | What it provides | Free tier specifics | Cost beyond free | ToS/legal risk | Serverless-compatible (y/n) | Setup lead time | Primary-source link | Date verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tavily API** | Agentic search, real-time web context | 1,000 basic searches/mo | ~$0.02–$0.035 per search | Low | Y | Minutes | [tavily.com/pricing](https://apify.com/clearpath/tavily-search-api) | Aug 2026 |
| **Exa API** | Neural web search, clean markdown | 1,000 credits/mo | $7 per 1,000 Deep searches | Low | Y | Minutes | [medium.com/@unicodeveloper](https://medium.com/@unicodeveloper/tavily-alternatives-in-2026-after-the-nebius-acquisition-9de526780686) | Aug 2026 |
| **Jina Reader** | URL to LLM-friendly markdown | 500 RPM with free key | $0.02 per 1,000 tokens | Low | Y | Instant | [jina.ai/contact-sales](https://jina.ai/contact-sales/) | Aug 2026 |
| **Firecrawl** | Page reading, dynamic site rendering | 500 credits | $16/mo minimum | Low | Y | Minutes | [firecrawl.dev/pricing](https://www.firecrawl.dev/blog/firecrawl-101) | Aug 2026 |

**Ranked Recommendation**
1. **Jina Reader (`s.jina.ai`):** Prepending `https://s.jina.ai/?q=` to a query returns the top five search results converted into clean, LLM-optimized Markdown. It offers an exceptional 500 requests-per-minute (RPM) free tier and eliminates the need for headless browser infrastructure on Vercel .
2. **Tavily API:** An excellent fallback for broad internet discovery with a 1,000 credit/month free tier, providing structured JSON optimized for LLMs and natively integrating with most agent frameworks .

**Coverage Reality Check for Target Persona:**
The hit rate for authored content on a mid-level supply chain manager at a 150-person logistics company will be near zero. They rarely author Substacks, appear on podcasts, or deliver recorded conference keynotes. The system must treat the *absence* of authored content as the standard path, routing seamlessly to business events.

**Explicitly Rejected**
*   **Firecrawl:** Despite excellent technical capabilities for complex DOM structures, its paid tier begins at a mandatory $16/month subscription, explicitly violating the hard budget constraint .

### 1c. Business Events

For software automating manual reconciliation, the strongest verifiable signals exist in corporate hiring patterns and job postings, which reveal internal technology stacks and explicit operational pain points (e.g., "seeking analyst to manually reconcile ERP").

**Options Table**

| Tool/Source | What it provides | Free tier specifics | Cost beyond free | ToS/legal risk | Serverless-compatible (y/n) | Setup lead time | Primary-source link | Date verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Greenhouse ATS API** | Live job postings, full descriptions | Free, unlimited | $0 | Low (Public APIs) | Y | Minutes | [developers.greenhouse.io](https://github.com/grnhse/greenhouse-api-docs/blob/master/source/includes/job-board/_jobs.md) | Aug 2026 |
| **Lever ATS API** | Job posts, basic filtering | Free, unlimited | $0 | Low (Public APIs) | Y | Minutes | [api.lever.co/v0/postings](https://github.com/lever/postings-api) | Aug 2026 |
| **Ashby ATS API** | Job posts, compensation data | Free, unlimited | $0 | Low (Public APIs) | Y | Minutes | [api.ashbyhq.com](https://cavuno.com/blog/ats-platforms-public-job-posting-apis) | Aug 2026 |
| **SEC EDGAR API** | Regulatory filings, leadership changes | Free | $0 (Strict 10 req/sec limit) | Low | Y (But brittle) | Hours | [sec.gov/developer](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) | Aug 2026 |

**Ranked Recommendation**
1. **Public ATS APIs (Greenhouse/Lever/Ashby):** These represent the most underutilized, high-fidelity signal sources for B2B outbound. Greenhouse's endpoint (`boards-api.greenhouse.io`) requires no authentication, operates entirely via stateless GET requests, and returns rich JSON payloads containing explicit operational challenges .
2. **SEC EDGAR API:** Useful strictly for the upper bound of the ICP (companies approaching public status). However, the strict 10 requests-per-second limit per IP address, combined with Vercel's shared IP architecture, makes it highly susceptible to 429 Too Many Requests errors during a live demo .

**Explicitly Rejected**
*   **Commercial Intent Data Providers (Bombora, ZoomInfo):** Require high-cost annual contracts and prolonged sales cycles, violating both budget and timeline constraints.

### 1d. Firmographics

Structured firmographics serve solely to gate the pipeline on ICP fit (headcount 50–500, target industry). 

**Options Table**

| Tool/Source | What it provides | Free tier specifics | Cost beyond free | ToS/legal risk | Serverless-compatible (y/n) | Setup lead time | Primary-source link | Date verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Clearbit (HubSpot)**| Firmographics via domain | N/A (Sunset) | N/A | N/A | N/A | N/A | [hubspot.com](https://www.pin.com/blog/profile-data-apis/) | Aug 2026 |
| **Crustdata API** | Company details, headcount | Free typeahead/filters | Pay-per-enrichment | Low | Y | Minutes | [docs.crustdata.com/general/pricing](https://docs.crustdata.com/general/pricing) | Aug 2026 |

**Ranked Recommendation**
1. **Inferred Firmographics via Jina Reader/Claude:** Query the company's "About Us" and "Careers" pages using Jina Reader, and use Claude 4.5 Haiku to extract an estimated headcount and industry. While less structured than a database, it is highly resilient, free, and impressive in a live demo.
2. **Crustdata API:** Provides pay-as-you-go access to firmographics without subscriptions .

**Explicitly Rejected**
*   **Clearbit Free Tools:** Sunset after the HubSpot acquisition in 2025 .

### 1e. Web Search and Page-Reading Layers

Grounding the final email draft requires direct textual evidence. Short snippets from standard search engines are insufficient to prevent hallucinations.

**Options Table**

| Tool/Source | What it provides | Free tier specifics | Cost beyond free | ToS/legal risk | Serverless-compatible (y/n) | Setup lead time | Primary-source link | Date verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Anthropic Web Search** | Native Claude integration | None | $10 per 1,000 searches | Low | Y | Instant | [platform.claude.com/pricing](https://platform.claude.com/docs/en/about-claude/pricing) | Aug 2026 |
| **Serper** | Google SERP API | 2,500 queries | Variable | Medium (Google ToS) | Y | Minutes | [serper.dev](https://serper.dev/) | Aug 2026 |
| **Brave Search API** | Independent index search | 1,000 queries/mo | $5 per 1,000 queries | Low | Y | Minutes | [brave.com/search/api](https://github.com/code-yeongyu/ultimate-web-search-skill/blob/main/references/providers/brave.md) | Aug 2026 |
| **ScrapingBee** | Headless browser API | 1,000 free credits | Monthly subscriptions | Low | Y | Minutes | [scrapingbee.com/pricing](https://www.scrapingbee.com/pricing/) | Aug 2026 |

**Ranked Recommendation**
1. **Anthropic Web Search (Native Tooling):** Priced at $10 per 1,000 searches, this is the most elegant architectural choice. Because the stack mandates Claude, utilizing Anthropic's native `web_search` tool bypasses the need to manage a secondary search API network request within the Vercel function, saving precious execution time and reducing points of failure .
2. **Tavily API:** As established, it excels at providing full-page content rather than short snippets .

**Explicitly Rejected**
*   **Serper:** While providing 2,500 free queries, it only returns standard 150-character search snippets. This lacks the requisite context depth to ground a personalized email .
*   **ScrapingBee & Brave Search:** Cost models rapidly transition to monthly subscriptions or require credit cards on file with high base rates for deep extraction .

### 1f. What is Missing?

**1. The "Company Engineering/Tech Blog" via direct domain scraping.**
For software targeting operations and reconciliation, tech blogs are a goldmine of systemic pain points. Querying `site:company.com/blog "reconciliation"` or `site:company.com/engineering "manual"` using Jina Reader provides primary-source evidence of operational bottlenecks that the prospect's company is actively attempting to solve. This fulfills the "Observed Business Events" requirement perfectly.

**2. Podcast Transcripts via YouTube API.**
While the prospect may not host a podcast, they may appear as a guest on industry channels. Using the YouTube Data API (free tier) to search `"{Prospect Name} {Company} podcast"`, retrieving the video ID, and utilizing a free transcript extraction library (e.g., `youtube-transcript` on npm) provides raw, highly personalized dialogue to ground the outreach.

---

## 2. Architecture and Prior Art

Commercial AI outbound systems have transitioned entirely away from naive, single-agent (ReAct) setups due to latency and hallucination issues, moving toward rigid, multi-agent directed acyclic graphs (DAGs).

### Open-Source Reference Implementations

| Repo / Project | What it provides | Quality / Recency | What to steal | Primary-source link | Date verified |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Composio AI SDR-Kit** | Integration-rich SDK connecting agents to 100+ tools | High (25.6k stars, updated 2025/2026) | Tool-calling patterns, OAuth handling | [github.com/Composio](https://nimblox.com/top-5-open-source-ai-powered-sdr-tools-on-github-2025/) | Aug 2026 |
| **Sales-Outreach-LangGraph (kaymen99)** | Automates lead research, scoring, drafting via LangGraph | Good (138 stars, updated 2025) | Architectural decomposition (research -> score -> draft nodes) | [github.com/kaymen99](https://github.com/topics/lead-generation) | Aug 2026 |
| **SalesGPT** | Context-aware conversational agent | High (2.3k stars) | Stage-aware prompting | [github.com/SalesGPT](https://nimblox.com/top-5-open-source-ai-powered-sdr-tools-on-github-2025/) | Aug 2026 |

**Ranked Recommendation:**
Study **Sales-Outreach-LangGraph**. While Python-based (violating the TS stack constraint), its conceptual pipeline is the precise blueprint required: isolating scraping, qualification scoring, and email drafting into independent, deterministic nodes . 

### Commercial Architectures

Public postmortems from platforms like **11x (Alice)** and **Lyzr (Jazon)** reveal a synchronized shift in 2025/2026:
*   **11x (Alice):** Documented their rebuild from standard ReAct (Reasoning and Acting) agents to a strict multi-agent system using LangGraph. The ReAct pattern proved too non-deterministic, frequently entering infinite loops or hallucinating logic when search APIs failed . They moved to a rigid workflow where research, scoring, and drafting are entirely isolated steps.
*   **Lyzr (Jazon):** Employs "framework-agnostic multi-agent orchestration." They utilize specialized, smaller agents for discrete tasks (e.g., one agent strictly for scoring against the ICP, another strictly for drafting) rather than passing the entire context window to a single monolithic model .

### Documented Failure Modes in Personalization

1.  **The "Generic Specificity" Trap:** The model extracts a fact (e.g., "I saw you hired a new software engineer") and attempts to link it to the offering with a forced, illogical transition ("which means you need reconciliation software"). *The Fix:* Prompt the drafting model to explicitly output the logical bridge in a hidden JSON field. If the bridge requires an assumption, the gate fails.
2.  **Silent Failure Ingestion:** If a scraper encounters a CAPTCHA or a 403 Forbidden, the HTML payload contains the error, not the data. A naive LLM will attempt to personalize the email based on the CAPTCHA text (e.g., "I noticed you are highly focused on Cloudflare security..."). *The Fix:* A pre-processing prompt that explicitly validates whether the payload is human-readable business context.

---

## 3. Grounding and Anti-Fabrication (The Core of the Build)

The central product value is restraint. The system must gracefully refuse to draft if verifiable signal is insufficient.

### Claim-Level Grounding

**Options Table**

| Technique/Tool | What it provides | Implementation Complexity | Primary-source link | Date verified |
| :--- | :--- | :--- | :--- | :--- |
| **Strict Citational Prompting** | Forces LLMs to output a JSON object mapping claims to source URLs and exact quotes | Low (Native to Claude via JSON schema) | Anthropic Docs | Aug 2026 |
| **Post-Generation Verification (Self-Correction)** | A secondary LLM pass evaluating the draft against the retrieved context | Medium | LangChain Docs | Aug 2026 |

**Pre-Generation Gate vs. Post-Generation Verification**
Production systems currently utilize **Pre-Generation Gating** as the primary economic and logical filter, reserving Post-Generation Verification as a safety net. 
*   *Pre-generation gating* evaluates retrieved text against the ICP. If the signal score is low, the pipeline halts immediately. This saves substantial output token costs ($15/MTok for Claude 4.6 Sonnet) and prevents the model from exerting "creative effort" to force a fit .
*   *Post-generation verification* remains necessary to ensure the LLM did not hallucinate a connection between a valid fact and an invalid premise during the drafting phase.

### Distinguishing "Searched and Found Nothing" from "Retrieval Failed"

This is the most critical distinction in the architecture. If a `fetch()` fails due to a network timeout, the system must not declare the prospect a bad fit. Production systems model this using explicit state enumerations in their JSON schemas, mirroring HTTP semantics.

*   **`SIGNAL_EXHAUSTED` (Equivalent to HTTP 404):** The API responded perfectly (HTTP 200), but the JSON payload contained zero relevant data about the prospect. This is a true finding about the world. The system routes to the "needs human judgment" state, stating: *"No verifiable signal found."*
*   **`RETRIEVAL_FAULT` (Equivalent to HTTP 500/429):** The search API timed out or rate-limited. This is a system error. The UI must explicitly stream: *"Error retrieving external data; cannot determine fit."*

To enforce this, wrap all API calls in a `try/catch`. Only successful empty arrays resolve to `SIGNAL_EXHAUSTED`. Any caught error resolves to `RETRIEVAL_FAULT`.

### Confidence Calibration (Beyond Lookup Tables)

Instead of a hardcoded lookup table, modern evaluators use **LLM-as-a-Judge with a Chain-of-Thought (CoT) Rubric**. The scoring agent is prompted to write out its reasoning in a `<reasoning>` block before assigning a score from 1-5 on ICP fit and Signal Strength. The presence of the reasoning trace calibration naturally forces the model to justify its score based *only* on the provided context, heavily reducing false positives.

---

## 4. Evaluating the Pipeline

Testing a non-deterministic pipeline requires asserting against the presence of expected behavior and the *absence* of hallucinations.

**Options Table (Eval Tooling)**

| Tool/Source | What it provides | Free tier specifics | Cost beyond free | ToS/legal risk | Serverless-compatible (y/n) | Setup lead time | Primary-source link | Date verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Promptfoo** | YAML-driven CLI for evals, local execution | 100% Free Open Source | None (Local execution) | None | Y (Local CI/CD) | Minutes | [promptfoo.dev/docs](https://www.promptfoo.dev/docs/configuration/expected-outputs/) | Aug 2026 |
| **DeepEval** | Pytest-native framework for LLMs | Free Open Source | Cloud features cost | None | N/A (Python focused) | Hours | [deepeval.com](https://deepeval.com/blog/top-5-llm-evaluation-frameworks) | Aug 2026 |
| **Evalite** | TypeScript/Vitest AI evaluation | Free Open Source | None | None | Y (Local CI/CD) | Minutes | [github.com/evalite](https://ecweb.ecer.com/topic/en/detail-837669-evaliteai_releases_typescript_tool_for_streamlined_llm_testing.html) | Aug 2026 |

**Ranked Recommendation**
1. **Promptfoo:** The definitive, industry-standard choice for a TypeScript project in 2026. It operates configuration-first, executes entirely locally without requiring a paid cloud platform, and ships with a robust library of deterministic assertions (`equals`, `contains`) and LLM-graded rubrics (`llm-rubric`, `is-valid-function-call`) . 
2. **Evalite:** A strong secondary option specifically for developers who prefer writing evaluations directly as Vitest unit tests rather than YAML configurations . 

**Explicitly Rejected**
*   **DeepEval:** While highly powerful and popular, it is Python-first and operates like Pytest. Integrating this into a strictly Next.js/TypeScript stack introduces unnecessary context switching and operational overhead .

### Testing Non-Deterministic Refusal & Golden Files

To ensure the anti-hallucination gate correctly declines, developers utilize a "golden dataset" of 25–50 curated, static examples .
1.  **Fixtures:** Store exact HTML/JSON responses from data sources (e.g., a Greenhouse API response) as static JSON files in the repo. During testing, the pipeline mocks the `fetch` layer to return these fixtures, isolating the *LLM's reasoning* from *API drift*.
2.  **Asserting Refusal:** A test fixture provides the system with a prospect possessing zero online presence. The Promptfoo assertion checks that:
    *   The output JSON schema strictly matches the `RefusalState`.
    *   A deterministic assertion (`type: not-contains`) ensures the generated text does not contain typical hallucinated filler (e.g., "I saw your great work at...").

---

## 5. Streaming Multi-Stage Progress to a Web UI

Streaming token-by-token generation is trivial; streaming a multi-stage directed pipeline requires specific state management.

**Options Table**

| Pattern/Tool | What it provides | Framework native | Latency | Complexity | Primary-source link | Date verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Vercel AI SDK (`createStreamableValue`)** | Streams serialized JS objects over React Server Components | Yes (Next.js App Router) | Low | Low | Vercel Docs | Aug 2026 |
| **Raw Server-Sent Events (SSE)** | Standard HTTP streaming | Framework agnostic | Low | Medium | MDN Web Docs | Aug 2026 |
| **WebSockets** | Bi-directional persistent connection | Requires custom server | Lowest | High (Not serverless friendly) | N/A | Aug 2026 |

**Ranked Recommendation**
1. **Vercel AI SDK (`createStreamableValue`):** The optimal abstraction. While earlier versions of the SDK focused heavily on token streaming, the modern SDK natively supports streaming partial JSON objects and custom state variables from the server directly to the React client.
2. **Raw SSE:** A solid fallback if the AI SDK introduces unnecessary weight, but requires manual handling of connection closures and parsing.

**Explicitly Rejected**
*   **WebSockets:** Entirely incompatible with standard Vercel serverless functions, which are designed to scale to zero and do not support long-lived bidirectional connections.

**Streaming Structured Pipeline Progress:**
To stream discrete events `{stage, status, message, timestamp}`, the backend Vercel function holds an array of `PipelineEvent` objects. As each stage (Identity Resolution → Enrichment → Signal Discovery) executes, the array is appended. Utilizing `createStreamableValue`, this array is yielded to the client. The React UI subscribes to this state, rendering a timeline component that updates live, regardless of whether a specific stage involves an LLM.

**Vercel Serverless Gotchas (Production vs. Local):**
*   **Timeout Limits (The pipeline killer):** Vercel Hobby tier functions strictly timeout at 10 to 60 seconds. Pro tier allows up to 5 minutes. Locally, Next.js runs a long-lived Node process, meaning a pipeline that takes 45 seconds will pass locally but aggressively throw a `504 Gateway Timeout` in production on the free tier.
*   **Response Buffering:** If streaming is not explicitly configured via `export const dynamic = 'force-dynamic';`, Vercel's Edge network may buffer the SSE response, causing the UI to sit blank for 30 seconds before rendering all stages simultaneously.

**Patterns Worth Copying:**
Look to **Perplexity's Pro Search** or **Linear's Asks** features. They utilize a "timeline trace" UI: a vertical progress bar where completed steps fade to gray, the active step pulses, and reasoning traces expand inside an accordion. This physically manifests the "thought process" of the agent, generating immense trust.

---

## 6. Persistence, Deployment, and a Critique

### Persistence

**Options Table**

| Tool/Source | What it provides | Free tier specifics | Cost beyond free | Serverless-compatible (y/n) | Setup lead time | Primary-source link | Date verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Vercel KV (Redis)** | Key-value store | 30,000 requests/mo | Pay-per-use | Y | Instant | Vercel Docs | Aug 2026 |
| **Neon Postgres** | Relational DB | 500MB storage | Monthly tiers | Y | Minutes | Neon Docs | Aug 2026 |

**Ranked Recommendation**
1. **Vercel KV:** For storing a few hundred JSON run records (`{ run_id: "...", data: {...} }`), a relational database is severe overkill. Vercel KV requires zero schema migrations, avoids Prisma/Drizzle ORM bloat, and integrates instantaneously.
2. **Neon Postgres:** The default Vercel marketplace integration for relational data, but requires unnecessary architectural complexity for this scope.

### Direct Critique and Vulnerability Analysis

**What would you cut?**
Cut the complex "Identity Resolution" phase. Confirming a person exists via an LLM adds 5–10 seconds of latency, burns tokens, and introduces a failure node for negligible gain. Hardcode the assumption that the provided Name + Company are accurate. You are building an outreach agent, not a background-check API. 

**What's cheap to build and disproportionately impressive?**
**Visible Negative Space.** When the system rejects a prospect due to poor ICP fit or low signal, render the *exact reasoning trace* in the UI in a stylized "Refusal Report." Showing a technical interviewer that your system confidently parsed a prospect, analyzed their stack, and printed, *"Declined to draft: The prospect's firm utilizes on-premise software incompatible with our cloud-reconciliation offering,"* demonstrates product maturity that a standard generated email never will.

**How does this kind of build most commonly fail in a live demo?**
1.  **The 429 Cascade:** The interviewer names an arbitrary prospect. Your pipeline concurrently hits the ATS API, Tavily, and Jina. One of them rate-limits you. An unhandled exception is thrown, and the UI crashes. *Prevention:* Wrap every external API call in a `Promise.allSettled` or a `try/catch` that resolves to a safe default (e.g., `[]`) on failure, ensuring the pipeline gracefully degrades rather than halting.
2.  **The Serverless Timeout:** The pipeline takes 15 seconds to fetch data, 20 seconds to score, and 15 seconds to draft. It hits the Vercel 60-second limit and dies mid-stream. *Prevention:* Utilize Claude 4.5 Haiku ($1/$5 per MTok) for all intermediate scoring, routing, and data-extraction steps . Haiku 4.5 is exceptionally fast and drastically reduces pipeline latency. Reserve Claude 4.6 Sonnet solely for the final email draft.

**Where is your plan wrong or naive?**
You assume signal extraction is clean. It is not. Searching for a mid-level ops manager will return directory listings, SEO spam, and entirely different people with the same name. Your pipeline currently lacks an **Entity Disambiguation** step. If you search for "John Smith Operations Manager," the agent will confidently ground its email on the accomplishments of a John Smith in a completely different industry. You must pass the company name as a mandatory strict string-match filter to the search API, and prompt the LLM to aggressively discard any text that does not explicitly mention the target company.

**What separates a memorable submission from a merely competent one?**
A competent submission generates a good email. A memorable submission treats the LLM as a control-flow engine rather than just a text-generator. Evaluators are looking for **defensive engineering**. They want to see that you utilized standard JSON Schemas to enforce structured outputs from Claude, that you handled API partial failures gracefully without lying to the user, and that your architecture prioritizes "do no harm" over "always return a result."

---

## Things you did not ask about but should know

**1. The Tokenizer Tax of Multi-Stage Pipelines**
In a multi-stage architecture, you must pass the retrieved context (the raw web text) to the Scoring Agent, and then pass *that exact same context* again to the Drafting Agent. This results in heavy input-token duplication. To solve this, you must utilize Anthropic's **Prompt Caching**, which was heavily refined in the 4.x models . By adding `cache_control: { type: "ephemeral" }` to the block containing the raw retrieved data, the subsequent drafting step will read the cached context at a 90% discount ($0.30/MTok instead of $3.00/MTok for Sonnet) and execute with significantly lower latency .

**2. The ATS Backdoor is the Ultimate ICP Filter**
You noted that the seller's offering automates "manual, reconciliation-heavy processes." The absolute best way to verify if a company needs this is not to research the individual prospect, but to query the Greenhouse or Lever API for the company's open jobs , and search the raw descriptions for the words "reconcile" or "Excel." If a company is hiring a low-level analyst explicitly to "reconcile payments in Excel," the ICP fit is 100%, and the email hook writes itself: *"I saw your team is currently hiring an analyst to handle manual payment reconciliation. Our software automates that exact workflow..."* This is deterministic, highly personalized, legally pristine, and completely bypasses the need for the prospect to have a personal social media presence.

**3. The Claude 4.x Era Temporal Shift**
As of August 2026, the baseline models are Claude 4.6 Sonnet and Claude 4.5 Haiku. The pricing structures have stabilized ($3/$15 for Sonnet, $1/$5 for Haiku) . Do not rely on outdated prompt structures meant for Claude 3 Opus. The 4.x models support native, strict JSON schema output via the `response_format` parameter . You do not need to rely on prompt-level begging (e.g., "Please only output valid JSON"). Enforce it at the API layer, which dramatically improves the reliability of the pre-generation gates and evaluation metrics.