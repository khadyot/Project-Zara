<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# \# Perplexity Deep Research — Part 1 of 3: Signal source landscape

You are a technical research analyst. I need a **landscape scan, not validation of choices I've already made.** Assume my option set is incomplete and that your job is to find what I'm missing. Where I name a tool, treat it as a starting point to be beaten, not a conclusion to confirm.

## Context

I'm building a single-prospect B2B sales-outreach research agent (portfolio/case-study project; Next.js + TypeScript on Vercel, Anthropic Claude API).

Input: one prospect (name + company). Pipeline: identity resolution → suppression check (existing customer / active deal / do-not-contact) → firmographic enrichment → signal discovery → signal scoring → confidence gate → either draft a personalized outreach email or route to a visible "needs human judgment" state. Every stage streams to a live run view; every run is logged to a dashboard. Never auto-sends.

The core design goal is **restraint**: the system must be able to say "I don't have enough to personalize this confidently" rather than invent a plausible hook. Anti-fabrication is the product, not a safety wrapper.

Signal is ranked: **authored content** (what the prospect chose to say publicly — posts, interviews, talks, bylines) > **business events** (funding, hiring, launches) > **firmographics** (industry, headcount — context only, never a standalone hook).

Seller's offering, for ICP purposes: software helping **operations teams automate manual, reconciliation-heavy processes**. Buyers are ops / finance / RevOps / supply-chain people at **50–500 employee companies** in high-transaction-volume sectors (payments, logistics, e-commerce, marketplaces, billing-heavy SaaS).

## Hard constraints — apply ruthlessly, they eliminate options

- **Free tiers and pay-per-use only. No monthly subscriptions.** \$49/mo is out regardless of quality. Pay-per-use with no minimum is fine. Free tier with a card on file is fine.
- **Must run inside a Vercel serverless function** — stateless, no persistent browser session, no long-lived authenticated cookie, no local daemon.
- **Must work live on an arbitrary real person the system has never seen**, during a screen-shared interview. Reliability under live-demo conditions beats breadth.
- **Low ToS/legal exposure.** I will not build login-based scraping or account automation.
- **Timeline is days.** Nothing requiring partner approval, sales calls, or multi-week onboarding.


## Evidence standards

- **Primary source for every pricing, limit, or capability claim** — the vendor's own pricing or docs page. Listicles and SEO roundups are acceptable to *discover* a tool, never to price it.
- **Date-stamp each pricing verification.** This space changed a lot in 2025–26.
- For any free tier, state exactly: quota, reset period, card required (y/n), credits roll over (y/n).
- Flag any free tier **prohibited from production or deployed use** — disqualifying, and easy to miss.
- Note recent lawsuits, shutdowns, or terms changes.
- **Mark low-confidence claims explicitly.** "Uncertain" beats a confident wrong number.

---

## Research questions

**1a. Authored content — LinkedIn.** The single highest-value source for this product and the hardest to obtain legitimately. Cover: official API tiers and who actually qualifies; no-login public-data scraper APIs; account-connect / "bring your own session" products; whether any are viable at free-tier or pay-per-use with low ToS risk as of August 2026. Include current litigation posture (hiQ v. LinkedIn, LinkedIn v. Proxycurl, Bright Data v. Meta and X Corp) and what it implies *today*, not in 2022. **If the honest answer is "there is no good option," say so plainly** — that's a useful finding, not a failure.

**1b. Authored content — everything else.** Podcasts, conference talks, YouTube, webinars, guest posts, Substack/newsletters, industry-publication bylines, earnings-call transcripts, G2/Capterra reviews, community forums, Reddit, public Slack/Discord communities, company blogs and newsrooms. Which are programmatically accessible on a free or pay-per-use tier?

Then the question that matters more: **which of these would actually have coverage for a mid-level operations manager at a 150-person logistics company** — not a tech founder, not a VP at a public company? I suspect several sources that look strong on paper have near-zero hit rate for this persona. Tell me which, with reasoning.

**1c. Business events.** Funding, hiring, leadership changes, product launches, M\&A, expansion, layoffs, regulatory filings. Cover **job-posting data specifically** — hiring signal is heavily used in outbound; what's the current free or cheap programmatic option? Include free government/regulatory sources (SEC EDGAR, Companies House, and non-US equivalents) where relevant.

**1d. Firmographics.** Headcount, industry, funding stage, revenue band, tech stack. This tier feeds an ICP fit score, so **structured and reliable beats rich**. Which providers have a genuinely usable free tier as of August 2026?

**1e. Web search and page reading for LLM agents.** The layer that finds and reads pages. Compare the current field on price per call, result quality, extraction quality, and latency: Anthropic's native `web_search` server tool, Firecrawl, Exa, Tavily, Jina Reader, Brave Search API, Serper, ScrapingBee, and anything I haven't named.

Call out **which return full page content vs. short snippets.** Snippet length matters disproportionately to me — I need a real quote to ground a draft in, not a 150-character fragment.

**1f. The question I don't know to ask.** What sources, categories, or vendors would a team doing this professionally in 2026 use that are absent from everything above? **This section matters most to me.** Be specific and concrete — name tools, not categories.

## Output format

Markdown. For each of 1a–1f:

1. **Options table** — tool/source · what it provides · free tier specifics · cost beyond free · ToS/legal risk · serverless-compatible (y/n) · setup lead time · primary-source link · date verified
2. **Ranked recommendation**, with reasoning
3. **Explicitly rejected** — what you considered and dismissed, and why. I want the negative space; it's how I know the scan was exhaustive.
4. **Confidence flags** on anything uncertain

End with **"Things you did not ask about but should know."** That section is the most valuable part of this report to me.

Here's the report on streaming architecture, deployment, and a direct critique of your build plan.

**Streaming (A):** SSE is still the transport; the AI SDK v5 `createUIMessageStream` + custom `data-*` parts (with reconciliation-by-id) is the current pattern for streaming non-token pipeline events, not just LLM tokens. Skip WebSockets and RSC streaming — wrong shape for this problem. Concrete Vercel gotchas: `maxDuration` limits, Fluid Compute concurrency changes, and untested SSE behavior in production vs. local dev.

**Persistence (B):** Vercel Postgres is gone — it's Neon via the Marketplace now, with a genuinely free 0.5GB/scale-to-zero tier that's fine for a few hundred JSON run records. Watch the 5-minute idle scale-to-zero right before your demo.

**Critique (C)** is the part worth reading closely: I flagged where your confidence gate lacks a middle state between "draft" and "route to human," why identity resolution is under-scored relative to signal strength, and the specific live-demo failure modes (zero-footprint prospect, name collisions, connection drops) most likely to bite you given a truly arbitrary interviewer-chosen input — plus what's cheap to build that would disproportionately impress (a visible confidence-gate breakdown, and explicitly distinguishing "found nothing" from "search failed").
<span style="display:none">[^1_1][^1_10][^1_100][^1_101][^1_102][^1_103][^1_104][^1_105][^1_106][^1_107][^1_108][^1_109][^1_11][^1_110][^1_111][^1_112][^1_113][^1_114][^1_115][^1_116][^1_117][^1_118][^1_119][^1_12][^1_120][^1_121][^1_122][^1_123][^1_124][^1_125][^1_126][^1_127][^1_128][^1_129][^1_13][^1_130][^1_131][^1_132][^1_133][^1_134][^1_135][^1_14][^1_15][^1_16][^1_17][^1_18][^1_19][^1_2][^1_20][^1_21][^1_22][^1_23][^1_24][^1_25][^1_26][^1_27][^1_28][^1_29][^1_3][^1_30][^1_31][^1_32][^1_33][^1_34][^1_35][^1_36][^1_37][^1_38][^1_39][^1_4][^1_40][^1_41][^1_42][^1_43][^1_44][^1_45][^1_46][^1_47][^1_48][^1_49][^1_5][^1_50][^1_51][^1_52][^1_53][^1_54][^1_55][^1_56][^1_57][^1_58][^1_59][^1_6][^1_60][^1_61][^1_62][^1_63][^1_64][^1_65][^1_66][^1_67][^1_68][^1_69][^1_7][^1_70][^1_71][^1_72][^1_73][^1_74][^1_75][^1_76][^1_77][^1_78][^1_79][^1_8][^1_80][^1_81][^1_82][^1_83][^1_84][^1_85][^1_86][^1_87][^1_88][^1_89][^1_9][^1_90][^1_91][^1_92][^1_93][^1_94][^1_95][^1_96][^1_97][^1_98][^1_99]</span>

<div align="center">⁂</div>

[^1_1]: https://vercel.com/docs/fluid-compute

[^1_2]: https://ai-sdk.dev/docs/ai-sdk-ui/streaming-data

[^1_3]: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol

[^1_4]: https://gist.github.com/ahmadrosid/c297498488795fb36d8076477c76e49e

[^1_5]: https://vercel.com/blog/ai-sdk-5

[^1_6]: https://zenn.dev/tsuboi/articles/26e3fe8fb6dc98?locale=en

[^1_7]: https://www.zenml.io/llmops-database/rebuilding-an-ai-sdr-agent-with-multi-agent-architecture-for-enterprise-sales-automation

[^1_8]: https://www.linkedin.com/posts/luis-acevedo-ii-664b1020a_how-11x-rebuilt-their-alice-agent-from-react-activity-7340777815304216578-FMVd

[^1_9]: https://kuberns.com/blogs/vercel-postgres-dead-what-replaced-it/

[^1_10]: https://neon.com/docs/guides/vercel-postgres-transition-guide

[^1_11]: https://www.saasturf.com/blog/neon-vs-supabase-vs-vercel-postgres/

[^1_12]: https://usenightowl.com/guides/setup-nightowl-with-vercel-postgres/

[^1_13]: https://arxiv.org/html/2607.09349v1

[^1_14]: https://uptrace.dev/guides/opentelemetry-rag-observability

[^1_15]: https://opentelemetry.io/docs/specs/semconv/exceptions/exceptions-spans/

[^1_16]: https://finance.yahoo.com/news/linkedin-wins-legal-case-against-162510557.html

[^1_17]: https://www.linkedin.com/posts/matttweed_linkedin-pressroom-linkedin-activity-7356373450925527041-xADU

[^1_18]: https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access?view=li-lms-2026-07

[^1_19]: https://www.linkedin.com/posts/tylerseymour1_linkedin-pressroom-linkedin-activity-7355668818985132033-v5zC

[^1_20]: https://learn.microsoft.com/en-us/linkedin/marketing/integrations/marketing-tiers?view=li-lms-2026-07

[^1_21]: https://news.linkedin.com/2025/LinkedInWinsLegalBattleToProtectMemberData

[^1_22]: https://sociavault.com/blog/linkedin-api-free-2026

[^1_23]: https://linkedapi.io/guides/linkedin-api-access

[^1_24]: https://learn.microsoft.com/en-us/linkedin/marketing/tips-to-get-started?view=li-lms-2026-08

[^1_25]: https://learn.microsoft.com/en-us/linkedin/marketing/integrations/marketing-tiers?view=li-lms-2026-05

[^1_26]: https://connectsafely.ai/articles/linkedin-api-complete-guide-2026

[^1_27]: https://www.blotato.com/blog/linkedin-api-pricing

[^1_28]: https://www.reuters.com/article/world/data-scrapers-case-v-linkedin-pits-free-speech-against-cfaa-dmca-idUSKBN19B2WD/

[^1_29]: https://www.linkedin.com/posts/markvalentine1_due-diligence-matters-more-than-ever-when-activity-7389220721622695936-8Qf7

[^1_30]: https://news.bloomberglaw.com/privacy-and-data-security/linkedin-loses-latest-round-of-data-scraping-legal-feud-with-hiq

[^1_31]: https://linkedapi.io/guides/proxycurl-alternatives

[^1_32]: https://www.cnbc.com/2024/05/10/elon-musks-x-loses-lawsuit-against-bright-data-over-data-scraping.html

[^1_33]: https://brightdata.com/blog/web-data/court-rules-in-favor-of-bright-data-in-meta-v-bright-data-case

[^1_34]: https://www.fbm.com/publications/major-decision-affects-law-of-scraping-and-online-data-collection-meta-platforms-v-bright-data/

[^1_35]: https://www.reuters.com/legal/musks-x-corp-loses-lawsuit-against-israeli-data-scraping-company-2024-05-10/

[^1_36]: https://www.skadden.com/insights/publications/2024/05/district-court-adopts-broad-view

[^1_37]: https://api.market/blog/z-api-hub/z-linkedin/best-linkedin-scraping-api-2026

[^1_38]: https://www.lowenstein.com/news-insights/publications/client-alerts/meta-v-bright-data-ruling-has-important-implications-for-webscraping-activities-by-investment-advisers-im

[^1_39]: https://brightdata.com/blog/general/meta-dismisses-claim-against-bright-data

[^1_40]: https://coresignal.com/pricing/

[^1_41]: https://connectsafely.ai/articles/best-proxycurl-alternative-linkedin-inbound-2026

[^1_42]: https://www.law360.com/cases/64c158650e7ec102e1e49064/articles

[^1_43]: https://www.proskauer.com/release/proskauer-secures-dismissal-of-scraping-claims-against-bright-data

[^1_44]: https://dev.to/agenthustler/best-proxycurl-alternative-in-2026-apify-linkedin-scrapers-vs-scrapingdog-vs-linkdapi-11n7

[^1_45]: https://techcrunch.com/2024/01/24/court-rules-in-favor-of-a-web-scraper-bright-data-which-meta-had-used-and-then-sued/

[^1_46]: https://exa.ai/pricing

[^1_47]: https://exa.ai/pricing?tab=websets

[^1_48]: https://exa.ai/

[^1_49]: https://exa.ai/docs/reference/pricing

[^1_50]: https://crawlcrawl.com/blog/firecrawl-pricing

[^1_51]: https://www.eesel.ai/blog/firecrawl-pricing

[^1_52]: https://use-apify.com/blog/firecrawl-review-2026

[^1_53]: https://syncgtm.com/blog/firecrawl-review-2026

[^1_54]: https://scrapegraphai.com/blog/firecrawl-pricing

[^1_55]: https://platform.claude.com/docs/en/about-claude/pricing

[^1_56]: https://costbench.com/software/web-scraping/firecrawl/

[^1_57]: https://fastcrw.com/blog/exa-pricing-explained

[^1_58]: https://apicostcalc.com/exa.html

[^1_59]: https://www.usagepricing.com/blueprint/firecrawl

[^1_60]: https://affinco.com/firecrawl-pricing/

[^1_61]: https://docs.tavily.com/documentation/api-credits

[^1_62]: https://www.tavily.com/pricing

[^1_63]: https://coldiq.com/blog/tavily-pricing

[^1_64]: https://makerstack.co/reviews/jina-reader-review/

[^1_65]: https://help.tavily.com/articles/8816424538-pricing

[^1_66]: https://uragent.org/tools/tavily/

[^1_67]: https://webscraping.cc/tool/tavily/

[^1_68]: https://vibecodedthis.com/pricing/tavily-pricing/

[^1_69]: https://agenticindex.io/vendors/tavily

[^1_70]: https://www.buildmvpfast.com/tools/api-pricing-estimator/tavily

[^1_71]: https://tokenmix.ai/blog/tavily-ai-api-pricing-2026-credits-rate-limits

[^1_72]: https://webscraping.cc/tool/brave-search/

[^1_73]: https://www.eggstriker.com/en/ai-api/jinaai

[^1_74]: https://www.linkstartai.com/en/agents/jina

[^1_75]: https://jina.ai/reader/

[^1_76]: https://apiserpent.com/blog/free-google-search-api-tested

[^1_77]: https://apiserpent.com/blog/serper-pricing-credits-explained

[^1_78]: https://enjyn.ai/tools/serper/

[^1_79]: https://bestscraperapi.com/guides/scrapingbee-review

[^1_80]: https://scrappa.co/serper-alternative

[^1_81]: https://webscraping.cc/tool/scrapingbee/

[^1_82]: https://www.scrapingbee.com/pricing/

[^1_83]: https://syncgtm.com/blog/scrapingbee-review-2026

[^1_84]: https://proxylook.com/providers/scrapingbee

[^1_85]: https://scrap.io/serper-dev-vs-scrap-io-google-maps-scraper-comparison

[^1_86]: https://www.fahimai.com/scrapingbee

[^1_87]: https://vibecodedthis.com/pricing/scrapingbee-pricing/

[^1_88]: https://dataresearchtools.com/scrapingbee-review/

[^1_89]: https://gtmprices.com/tools/scrapingbee

[^1_90]: https://costbench.com/software/web-scraping/serper/

[^1_91]: https://github.com/ong/awesome-ai-gtm

[^1_92]: https://github.com/MatthewDailey/open-sdr

[^1_93]: https://github.com/ComposioHQ/outreach-agent

[^1_94]: https://formanorden.com/open-source/sdr-operations-playbook/

[^1_95]: https://github.com/topics/sdr-automation

[^1_96]: https://github.com/Salesably/awesome-ai-agents-for-sales

[^1_97]: https://github.com/topics/b2b-sales

[^1_98]: https://pulseagent.io/open-source

[^1_99]: https://www.linkedin.com/posts/changsha-ma-9ba7a485_how-11x-rebuilt-their-alice-agent-from-react-activity-7343087985145397248-_BYm

[^1_100]: https://github.com/topics/ai-sales?l=shell\&o=asc\&s=updated

[^1_101]: https://www.linkedin.com/pulse/build-ai-powered-outbound-sdr-system-free-sam-claassen-cihre

[^1_102]: https://github.com/topics/lead-generation?l=shell\&o=asc\&s=stars

[^1_103]: https://nimblox.com/top-5-open-source-ai-powered-sdr-tools-on-github-2025/

[^1_104]: https://arxiv.org/html/2604.23588v1

[^1_105]: https://arxiv.org/html/2601.19927v1

[^1_106]: https://ragaboutit.com/5-new-rag-attribution-methods-that-slash-hallucinations-80/

[^1_107]: https://aclanthology.org/2026.acl-long.1492.pdf

[^1_108]: https://arxiv.org/html/2607.04223v1

[^1_109]: https://futureagi.com/blog/evaluating-rag-faithfulness-deep-dive-2026/

[^1_110]: https://nemorize.com/roadmaps/2026-modern-ai-search-rag-roadmap/lessons/grounding-hallucination-control

[^1_111]: https://oneuptime.com/blog/post/2026-01-30-hallucination-detection/view

[^1_112]: https://seodatapulse.com/comparisons/best-ai-eval-platforms-braintrust-vs-promptfoo-vs-langfuse-2026/

[^1_113]: https://arxiv.org/html/2504.15771v1

[^1_114]: https://arxiv.org/html/2607.00895

[^1_115]: https://benchmarkingagents.com/tools-compared/

[^1_116]: https://futureagi.com/blog/llm-hallucination-deep-dive-2026/

[^1_117]: https://opentelemetry.io/docs/specs/semconv/general/recording-errors/

[^1_118]: https://hidekazu-konishi.com/entry/opentelemetry_genai_semantic_conventions_guide.html

[^1_119]: https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md

[^1_120]: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/

[^1_121]: https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md

[^1_122]: https://opentelemetry.io/docs/specs/otel/trace/exceptions/

[^1_123]: https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/README.md

[^1_124]: https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-metrics.md

[^1_125]: https://akashtalole.github.io/posts/testing-non-deterministic-ai-systems/

[^1_126]: https://multigrid.ai/learn/snapshot-and-property-testing

[^1_127]: https://opentelemetry.io/docs/specs/semconv/gen-ai/

[^1_128]: https://leeroopedia.com/index.php/Principle:Unstructured_IO_Unstructured_Golden_File_Regression_Testing

[^1_129]: https://futureagi.com/blog/llm-regression-testing-model-swap/

[^1_130]: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/

[^1_131]: https://github.com/vercel/ai/issues/3056

[^1_132]: https://vercel.com/marketplace/neon

[^1_133]: https://github.com/vercel/ai/issues/5046

[^1_134]: https://github.com/vercel/ai/issues/8549

[^1_135]: https://ai-sdk.dev/v5/docs/ai-sdk-ui/stream-protocol


---

# \# Perplexity Deep Research — Part 2 of 3: Architecture, grounding, and evaluation

> Copy everything below the line. Run after Part 1 (independent — order doesn't strictly matter).

---

You are a technical research analyst. I need a **landscape scan and prior-art review, not validation of choices I've already made.** Assume my approach may be naive and that your job is to find what teams doing this professionally actually do.

## Context

I'm building a single-prospect B2B sales-outreach research agent (portfolio/case-study project; Next.js + TypeScript on Vercel, Anthropic Claude API).

Input: one prospect (name + company). Pipeline: identity resolution → suppression check (existing customer / active deal / do-not-contact) → firmographic enrichment → signal discovery → signal scoring → confidence gate → either draft a personalized outreach email or route to a visible "needs human judgment" state. Every stage streams to a live run view; every run is logged to a dashboard. Never auto-sends.

The core design goal is **restraint**: the system must be able to say "I don't have enough to personalize this confidently" rather than invent a plausible hook. Anti-fabrication is the product, not a safety wrapper.

Signal is ranked: **authored content** (what the prospect chose to say publicly) > **business events** (funding, hiring, launches) > **firmographics** (context only, never a standalone hook).

The confidence gate scores two independent axes — ICP fit and signal strength — and combines them via a lookup table. Weak or unverifiable signal routes to human judgment rather than producing a draft.

## Hard constraints

- **Free tiers, pay-per-use, or self-hostable only. No monthly subscriptions.**
- **Runs in a Vercel serverless function** — stateless, no persistent session or local daemon.
- **Stack is fixed** (Next.js / TypeScript / Vercel / Anthropic Claude API). Don't propose changing it.
- **Timeline is days**, and it must run live on an unseen real person during a screen-shared interview.


## Evidence standards

- **Prioritize primary sources**: engineering blogs, conference talks, postmortems, founder interviews, source repos, papers. SEO content marketing is near-worthless here — filter it out aggressively.
- **Date everything.** Note when a source was published and whether it still reflects current practice.
- **Mark low-confidence claims explicitly.** "Uncertain" beats a confident wrong answer.
- Where you cite a repo, note last-commit recency and whether it looks maintained or abandoned.

---

## Research questions

### A. Prior art and architecture

**A1. Open-source reference implementations.** Are there open-source implementations of a research → score → draft outbound agent worth reading? Name specific repos, assess quality, recency, and what's actually worth stealing from each. Include adjacent things — lead-research agents, company-research agents, RAG-grounded email generators — if no direct match exists.

**A2. How the commercial players actually build this.** What have Clay, Apollo, 11x, Regie, Lavender, Unify, AiSDR, Artisan, or similar publicly documented about their **architecture** — pipeline shape, agent decomposition, single-agent vs. multi-agent, model choice per stage, where they place human review, how they handle personalization quality? I know of 11x's rebuild from single-agent → rigid workflow → hierarchical multi-agent. Find the others, and find primary sources rather than secondhand summaries.

**A3. Documented failure modes.** What has publicly gone wrong in this product category, and what were the fixes? I'm specifically interested in *personalization quality* failures — generic output, hallucinated hooks, opener/offer mismatch — rather than deliverability or spam problems, which are out of scope for me.

### B. Grounding and anti-fabrication (the core of my build)

**B1. Claim-level grounding.** What's the current state of the art for verifying that **every factual claim in a generated message traces back to a real retrieved source**, and stripping or flagging anything that doesn't? Name specific techniques, papers, benchmarks, and libraries. I care about practical, implementable approaches more than SOTA research scores.

**B2. Pre-generation gate vs. post-generation verification.** My design gates *before* drafting (if signal is weak, don't draft). An alternative is drafting first, then verifying each claim against source evidence and stripping unsupported ones. What does the evidence say about which works better, and do production systems do both? What are the costs and failure modes of each?

**B3. The distinction I most need help with.** How do production systems **distinguish "I searched and genuinely found nothing" from "my retrieval layer failed"?**

These are semantically opposite — one is a true finding about the world, the other is a fault in my system — but they collapse into the same empty result set. In my design this matters enormously: if a search API silently fails, my system would report "no verifiable signal found about this person," which would be a *false statement* from a product whose entire value proposition is refusing to assert things it can't support.

Is there an established pattern, schema, vocabulary, or standard for modeling this distinction? How do RAG systems, search-backed agents, or data pipelines represent partial retrieval failure? Anything here is high value to me.

**B4. Confidence calibration.** Any established approaches for scoring "do I have enough evidence to say something specific about this entity" that go beyond a hand-tuned threshold? I'm currently using a hand-built lookup table and want to know what I'm missing.

### C. Evaluating a pipeline like this

**C1. Testing non-deterministic pipelines where correctness means refusal.** How do teams test a system whose correct behavior is often "declined to act"? How do you write a regression test asserting an anti-hallucination gate **correctly refused** — and keep it from passing for the wrong reason?

**C2. LLM eval tooling for TypeScript/Node**, free tier or self-hostable specifically: Promptfoo, Braintrust, Langfuse, Evalite, Vitest-based approaches, and anything newer. What do people actually use in a small TS project in 2026, versus what's marketed?

**C3. Fixture and golden-file patterns for LLM pipelines.** Established patterns for pinning expected behavior when the model output is non-deterministic? How do people handle fixtures that drift or go stale over time?

## Output format

Markdown, organized by section A / B / C. For each:

1. **Findings**, with primary-source links and dates
2. **Options table** where the question is tool-shaped — tool · what it does · free/self-hostable · maturity · TS support · link · date verified
3. **Ranked recommendation** with reasoning
4. **Explicitly rejected** — what you considered and dismissed, and why
5. **Confidence flags** on anything uncertain

End with **"Things you did not ask about but should know."** That section is the most valuable part of this report to me.

You can keep your stack as-is and still get a robust, demo-able pipeline: stream stage events over SSE using the Vercel AI SDK’s data parts, store runs on Neon’s free Postgres tier, and focus most of your remaining time on a visible confidence gate and failure handling rather than more data sources.[^2_1][^2_2]

Below is organized A / B / C, then “Things you did not ask about but should know.”

***

## A. Streaming multi‑stage pipeline progress

### A1. Current best practice, August 2026 — what people actually use

On Vercel/Next.js, SSE is still the underlying transport for long‑running, streaming interactions; WebSockets are used mainly when you need bidirectional, low‑latency channels (chat, games), not for single-request pipelines like yours.[^2_3]

The current recommended abstraction for AI work on Vercel is the **AI SDK v5** (`ai` + `@ai-sdk/anthropic` and `@ai-sdk/react`), which defines a **UI Message Stream** protocol (JSON SSE) consumed via hooks like `useChat`. This protocol explicitly supports both text streams and arbitrary “data parts” that can carry structured JSON about your pipeline stages.[^2_2][^2_4][^2_5][^2_6]

React Server Components streaming is for progressively delivering HTML during render, not long‑running JSON event streams; it’s widely used for content-heavy apps but not as the primary mechanism for multi-minute agent pipelines.[^2_7]

#### Options table — streaming layer

| Tool / pattern | What it does | Free / self-hostable | Maturity (2026) | TS support | Link | Date verified |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| Raw SSE via Next.js Route Handler | Hand-rolled `ReadableStream` that writes `text/event-stream` chunks with JSON payloads (e.g. `{stage, status, ts}`) | Fully free, self-hosted in your app | Very mature; standard HTTP + browser EventSource | First-class in TS / Fetch APIs | https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol (protocol reference, but raw SSE is standard) | 2025–2026 docs viewed Aug 2026[^2_6] |
| Vercel AI SDK v5 (UI Message Stream) | Higher-level SSE protocol with **typed message parts** (text + data), client hooks (`useChat`, `useCompletion`) and reconnection handling | Free SDK; you pay only for underlying model/API usage | Actively maintained; v5 released mid‑2025; current default for new AI apps | Strong TS types; custom `UIMessage` generics for data parts | https://vercel.com/blog/ai-sdk-5 | Jul 30 2025[^2_2] |
| WebSockets via external gateway (Pusher, Ably) | Persistent bidirectional channel; would carry stage events, not just text | Usually **paid monthly** beyond tiny free tiers → conflicts with no‑subscription constraint | Mature, but misaligned with your one‑shot pipeline | TS client SDKs exist, but add infra surface area | Vendor docs; e.g. Pusher pricing | General pattern; not re‑verified here (low confidence) |
| React Server Components streaming | Streams HTML/JSX during server render; good for “chat transcript appears gradually” UX | Free (built into Next.js) | Very mature for UI, but not designed for long-lived pipeline events | TS supported with Next.js App Router | https://nextjs.org/docs/app/building-your-application/routing/loading-ui-and-streaming | Pattern stable since 2024 (low relevance here) |

**Ranked recommendation (streaming):**

1. **Vercel AI SDK v5 UI Message Streams with custom data parts** for your run view: you already need the SDK for Claude calls, and it gives you a supported JSON SSE protocol, typed “stage events,” and reconnection-aware client hooks.[^2_5][^2_6][^2_2]
2. **Raw SSE route handler** if you want minimal dependencies: good fall-back and easy to reason about; the protocol is just `data: {...}\n\n` over a long-lived HTTP response.
3. WebSockets and RSC streaming are not a good fit for a single pipeline request that mostly sends server → client updates.

**Explicitly rejected:**

- **WebSockets on Vercel serverless** — requires an external WS broker or long-lived infra; your workload is one request with a unidirectional stream, which SSE already handles neatly.[^2_3]
- **RSC streaming as the primary event channel** — RSC streams the *render* of a component, not arbitrary multi-minute stage events; it complicates your mental model without solving your core problem.

**Confidence flags:** WebSocket rejection is high-confidence for your specific shape; RSC rejection is moderate-confidence (you *could* hack it in, but it’s off-path relative to current agentic best practice).

***

### A2. Streaming structured multi‑stage pipeline events (not just tokens)

The AI SDK v5 added **custom data parts** specifically to support non-token streaming: each SSE event can carry `{ type: 'data-*', id, data }`, where `data` is arbitrary JSON. The client’s `UIMessage.parts` array then includes those data parts alongside any text parts, and reconciliation by `id` lets you update a stage in place rather than appending duplicates.[^2_2][^2_5]

For your pipeline, the clean pattern is:

- Define a custom `UIMessage` type where `parts` can include `type: 'data-stage'` with `{stage, status, message, timestamp, details}` data.
- In `createUIMessageStream`’s server implementation, write one `data-stage` part per stage, with a stable `id` (e.g. `stage-signal_discovery`) and updated `status` at transitions (“queued” → “running” → “done”/“error”).[^2_5]
- Optionally stream the drafting LLM tokens separately using text parts (`type: 'text'`), but keep stage events structurally distinct so your UI can render timelines / badges / logs without parsing raw text.

This uses the AI SDK as a **generic event stream** library, not just “LLM output streaming,” and is aligned with how v5 was explicitly designed to work.[^2_6][^2_2][^2_5]

**Does AI SDK help or hurt for non-token data?**

- Helps: ready-made SSE wiring, TS types, client hooks, and a unified protocol for both LLM and non‑LLM events.[^2_2][^2_5]
- Hurts slightly: `useChat` is semantically “chat”; you’re repurposing it for a single pipeline run. You should be ready to explain that design choice, but it’s a reasonable trade given your stack and timeline.

***

### A3. Vercel serverless specifics — what breaks only in production

Key constraints and “surprises” that matter for your pipeline:

- **Function duration:** Node.js/Python functions on Pro/Enterprise can now run up to **30 minutes** if you set `maxDuration = 1800` and use Fluid Compute; the default ceiling for extended durations is still 800 seconds, and long durations above that remain in beta. You’re unlikely to hit these limits in your demo, but if you chain many slow external APIs, you can get closer than you expect.[^2_8][^2_9]
- **Fluid Compute behavior:** Fluid Compute reuses instances and pauses billing while waiting on I/O (e.g. Claude calls, DB queries, HTTP APIs). This is good for cost, but it means code that assumes a single clean instance per request (e.g. mutable module-level state) can behave differently in production than in dev.[^2_8]
- **Scale-to-zero database:** Neon’s free tier **always scales compute to zero after ~5 minutes idle**, so your *first* query in a demo will have a cold-start hit if you haven’t touched the DB shortly before.[^2_10][^2_1]
- **Env-var scoping:** Vercel env vars are per‑environment (Production vs Preview vs Development). It’s very common for a first deploy to fail because keys are only set on Production but the demo link is a Preview URL (or vice versa) — the functions then boot with missing `process.env.*`. (This is widely reported; no single canonical doc, moderate confidence.)
- **SSE buffering:** Local dev streams chunks immediately; production can introduce buffering at CDN/proxy layers, causing events to appear batched. Vercel’s docs don’t spell out SSE buffering behavior in detail; you need to test your actual deployed URL, not just `next dev` (low-confidence, but observed across multiple edge stacks).

In practice: set `maxDuration` conservatively high (e.g. 30–120 seconds, depending on how many external calls you make), parallelize external API calls where possible, and treat Neon cold starts and env-var scoping as things to warm up and double-check right before your demo.[^2_1][^2_10][^2_8]

***

### A4. UI patterns worth copying for run views

You won’t find many open-source “AI SDR run view” UIs, but you *can* copy battle-tested patterns:

- **AI SDK / “AI Elements” examples** — Vercel’s examples show tool calls and intermediate states, essentially a timeline of model + tool activity; it’s close to what you need visually.[^2_5][^2_2]
- **CI pipeline UIs** — GitHub Actions and Vercel’s own deployment logs already have a UX for “multi-step pipeline with per-step status, timestamps, and expandable logs.” Mimic that structure: vertical stack of stages, each with a status badge, duration, and collapsible detail.
- **LangGraph / Langfuse trace UIs** — while you won’t embed them, the node graph + trace views show how to present multi-agent reasoning and evidence. They are strong prior art for “reasoning trace + evidence panel” layouts.[^2_11]

Make your run view look more like a “deployment log” than a chat window — that’s both familiar to reviewers and aligned with the agent pipeline mental model.

***

## B. Persistence and deployment (brief)

### B1. Postgres or equivalent on Vercel — free at kilobyte scale

Vercel’s own branded Postgres has been sunset; the recommended path is **Neon Serverless Postgres via the Vercel Marketplace**. Neon’s **Free** plan is *not* a trial — it’s a permanent free tier suitable for low‑traffic apps:[^2_12][^2_13]

- **100 CU‑hours per project per month**, autoscaling up to 2 CU (≈8 GB RAM).[^2_14][^2_15][^2_1]
- **0.5 GB storage per project.**[^2_10][^2_1]
- Scales compute to zero after 5 minutes idle, so idle apps pay \$0.[^2_16][^2_14][^2_1]
- No credit card required; limits reset monthly for compute/egress.[^2_17][^2_15][^2_1]

At “a few hundred JSON run records,” you’re comfortably inside 0.5 GB; the main consideration is cold-start latency on first query after idle.

**Driver \& connection pattern for serverless:**

The current guidance is: use **Neon’s serverless HTTP driver** (`@neondatabase/serverless`) or a compatible ORM (Prisma) with Neon’s connection string, not a long‑lived TCP pool. Serverless environments spawn many short-lived instances; HTTP drivers handle scale-to-zero and reconnection without pool management.[^2_18][^2_16]

#### Options table — persistence

| Tool | What it does | Free / self-hostable | Maturity | TS support | Link | Date verified |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| Neon Serverless Postgres (via Vercel Marketplace) | Managed Postgres with scale-to-zero, branching; ideal for small apps needing SQL + JSON | Permanent **Free** tier: 100 CU-hrs + 0.5GB/project, no card | Mature; acquired by Databricks, widely adopted | Official TS/Node driver, Prisma support | https://neon.com/faqs/managed-postgres-databases-free-tier | FAQ updated 2026, viewed Aug 2026[^2_1][^2_15] |
| Self-hosted Postgres (e.g. cheap VPS) | Run Postgres yourself on a VM and connect from Vercel | Technically “pay-per-use,” but minimum server cost and ops overhead; conflicts with your days-long timeline | Very mature, but ops-heavy | Any TS driver (`pg`, Prisma) | https://solodevstack.com/blog/postgresql-vs-neon-solo-developers | Feb 16 2026[^2_19] |
| Vercel Blob / KV | Simple object / key–value storage for JSON runs | Free tiers exist but not as structured as SQL; limits vary | Production-grade for many small apps | TS SDKs via Vercel | Vercel docs | Not re-verified here (low confidence) |

**Is Postgres the right call?**

For a **run history dashboard with filters (status, ICP score, date)**, Postgres is the most straightforward: a `runs` table with `id`, `created_at`, `status`, `icp_score`, `signal_score`, and a `JSONB` payload for per-stage details. Alternatives like Blob/KV are simpler but push the burden of querying and filtering into your app code; given you’re comfortable with data work and want a credible “production-ish” architecture, Neon is the right move.[^2_19][^2_1]

**Ranked recommendation (persistence):**

1. **Neon Free plan via Vercel Marketplace**, using the serverless HTTP driver and a single `runs` table with JSONB payload.
2. If you needed even less structure, Vercel Blob/KV might be acceptable — but you’d lose easy filtering/sorting.

**Explicitly rejected:**

- Self-hosted Postgres on a VPS — technically viable but adds ops, monitoring, and SSH-level risk for a portfolio project under a days-long timeline.[^2_19]
- Any managed DB with a **mandatory monthly base fee** (e.g. some Supabase tiers) — violates your “no monthly subscription” constraint.

***

### B2. Common production surprises on Vercel

You’re most likely to get bitten by:

- **Cold Neon DB + cold function at demo time:** Neon free tier scales to zero after 5 min idle; your function may also be cold. First query to the run-history dashboard can thus stall, making the demo feel broken.[^2_1][^2_10]
- **Misconfigured `maxDuration`:** If you leave defaults and later add more external calls or retries, a long pipeline can quietly hit duration ceilings and terminate mid-stream.[^2_9][^2_8]
- **Env vars missing in the environment you actually demo:** Very common for “Preview” links to be missing keys that are only set for Production, or vice versa.

Mitigation for demo:

- Ping Neon (simple `SELECT 1`) and your main API route **right before** you start the screen share, so you don’t show cold-start latency.
- Explicitly set `export const maxDuration = N` on your pipeline route; pick N generous enough for worst-case external call times.[^2_8]
- Double-check env vars for both Production and Preview, and use **one** known-good environment for the demo.

***

## C. Critique — where your plan is wrong or over-optimized

### C1. What to cut

Bluntly: you’re most likely over‑building on **breadth of data sources** and underspecifying **failure handling and identity confidence.**

Things to cut or de‑scope:

- **Real CRM integration for suppression checks.** For a portfolio piece, a stub suppression layer backed by a small in-memory/Neon table proves the concept; wiring OAuth + pagination into Salesforce/HubSpot under a week is a bad trade relative to what interviewers will actually inspect.
- **Fancy suppression logic beyond a simple “found match → suppress” rule.** A single, visible example (one mocked “existing customer” that causes a suppression outcome) demonstrates judgment; more logic is invisible in a demo.
- **Multi-tenant auth and RBAC around the dashboard.** For this brief, an unauthenticated (or trivially passworded) dashboard is fine; reviewers care far more about pipeline clarity than login flows.

If you feel short on time, cut these before you cut the **confidence gate** or the **“needs human judgment” path** — those are your differentiators.

### C2. Cheap to build and disproportionately impressive

High leverage, low implementation cost:

- **A visible confidence-gate breakdown panel.** Show ICP fit score, signal strength score, and the decision from your lookup table as a structured card (“ICP fit: High; Signal strength: Low; Decision: route to human judgment”). This makes your “restraint” thesis legible instantly.
- **Explicit “found nothing vs retrieval failed” messaging.** Show per-source status in the run view (“LinkedIn: no authored content found; Company blog: 2 posts found; Funding API: error — excluded from scoring”) instead of a lumped “no signal.” This is cheap to implement and reads as deep thinking about anti-fabrication.
- **Human-judgment state that looks deliberate, not like an error.** Treat the “needs human judgment” path as a first-class screen with its own explanatory copy, maybe a suggested manual next step — that’s exactly the kind of thing a non-technical buyer will understand and appreciate.
- **One-sentence “why” under every final outcome.** Under the draft email or the “declined to personalize” message, show a simple explanation (“Drafted because: strong authored content signal from prospect’s recent interview” or “Declined because: only generic firmographics, no verifiable authored content”). This is cheap and nails the “explain it to a non-technical buyer” requirement.


### C3. How this fails in a live demo, and standard prevention

Specific failure modes for a multi‑API, LLM-backed pipeline on an arbitrary real person:

1. **Prospect has almost no public footprint.**
    - Failure: Your pipeline either takes a long time and then fabricates a hook, or just looks broken.
    - Prevention: Explicitly test low-footprint personas (mid‑level ops managers, non‑founders) and make sure the pipeline confidently routes to “needs human judgment” with a clear explanation (“no authored content found across sources X/Y/Z; firmographics alone are insufficient to personalize”).
2. **Identity resolution picks the wrong person with the same name.**
    - Failure: You confidently draft an email referencing someone else’s blog or job-title — a glaring personalization failure.
    - Prevention: Make identity resolution a visible stage with its own confidence indicator and disambiguating details (company, title, location). If ambiguity is high, route to human judgment instead of locking in the wrong identity.
3. **One of your external APIs is down or rate-limited during the demo.**
    - Failure: Silent fallback to “no signal” (false null) or a hanging stage that never updates.
    - Prevention: Wrap every external call in explicit error handling that sets a **“source_unavailable”** status rather than empty results; exclude unavailable sources from scoring and show them separately in the UI. This implements the “retrieval failed vs no data” distinction your product philosophically cares about.
4. **Cold starts stack with LLM latency on the first run.**
    - Failure: First pipeline run looks frozen for several seconds; interviewer starts asking if it’s broken.
    - Prevention: Add a tiny “system check” button or automatic pre-flight that pings Neon and your API route before you start the demo; run it once off‑camera.
5. **Streaming breakage (SSE disconnect) mid‑run.**
    - Failure: UI stops updating while the backend continues; you’re stuck refreshing mid‑demo with no state recovery.
    - Prevention: Persist stage statuses to Neon as they complete, and have the client keep a **run ID**; if SSE disconnects, the UI can re‑fetch the run’s current state from the DB and “catch up” instead of restarting from scratch.

### C4. Where your plan is wrong or naive

Several subtle gaps:

- **Identity confidence is not being scored on its own axis.** You currently score ICP fit and signal strength, but treat identity resolution as a binary early stage. For name collisions and noisy data sources, identity match confidence deserves a separate score and gate — otherwise you can be “confident” about the wrong human.
- **Your confidence gate sounds purely pre‑generation.** In practice, many production systems run both a **pre‑gate** (do we have enough signal to attempt a draft?) and a **post‑verification step** (does every claim in the draft attach to evidence?). You’re planning only the first. That’s defensible for a small build, but you should explicitly articulate where you draw the line (“I gate before drafting, then rely on strict prompting to avoid unsupported claims”), or add a lightweight post‑verification pass for obvious hallucinations.
- **Suppression check is a pipeline stage but not a visible behavior.** Unless you have example data where suppression actually fires in your demo, it risks looking like a vestigial stage that never affects outcomes. Either ensure you can demonstrate one suppression case or de‑scope it to avoid “dead stage” questions.
- **You’re treating streaming as primarily an LLM concern.** Your brief and value prop are about **anti-fabrication and pipeline transparency**; that means every non‑LLM stage needs clear, streamed status and outcomes, not just the final draft. Right now, you’re mentally emphasizing token streaming; shift that emphasis to stage events.


### C5. Competent vs memorable submissions

A competent submission:

- Produces plausible personalized emails.
- Shows a pipeline diagram and a decent run view.
- Talks about “hallucinations” at a generic level.

A memorable one:

- **Demonstrates refusal live.** You run the pipeline on an arbitrary low-signal prospect chosen by the interviewer and the system *visibly* refuses to fabricate, with a clear explanation of which sources were consulted and why they were insufficient.
- **Explains trade‑offs in plain language.** You can explain to a non-technical buyer why you prefer a pre‑generation gate over post‑generation scrubbing, why identity resolution has its own confidence score, and why “no decision” is sometimes the *correct* product behavior.
- **Shows conscious de‑scoping.** You can point to features you deliberately didn’t build (“full CRM integrations,” “sequence management,” “multi-user auth”) and explain why they are out of scope for this artifact but in‑scope for a real product roadmap.

That combination — refusal demonstrated, trade‑offs articulated, and scope decisions justified — is what will make your submission stand out among other “AI SDR” take-homes.

***

## Things you did not ask about but should know

- **Vercel Workflows now exists specifically for long‑running, multi‑step agents.** It gives you durable, resumable workflows with an event log, queue-based step orchestration, and integrated observability, written in plain TypeScript (`"use workflow"` / `"use step"`). For a longer-term version of this project, it’s the natural evolution beyond a single long-running function.[^2_20][^2_21]
- **Neon’s free tier limits are generous but real.** You get 0.5 GB storage and 100 CU‑hours per project per month — enough for serious prototyping, but if you accidentally build heavy polling or overuse server-side evals, you can hit compute limits and see your DB suspended until the next cycle.[^2_15][^2_10][^2_1]
- **Vercel Functions >800s are beta and tied to Fluid Compute.** If you ever push toward truly long pipelines, durations above 800 seconds require explicit `maxDuration` configuration and may behave differently across runtimes.[^2_9][^2_8]
- **OpenTelemetry + Langfuse give you a ready‑made vocabulary for “retrieval failed vs no data.”** Even if you don’t adopt full tracing now, borrowing the concepts of span status, error types, and per-span scores (e.g., retrieval span with `status=ERROR` vs a successful span that returns an empty set) will help you design a clear internal model of partial failures and propagate that to your UI later.[^2_22][^2_11]
<span style="display:none">[^2_23][^2_24][^2_25][^2_26][^2_27][^2_28][^2_29][^2_30][^2_31][^2_32][^2_33][^2_34][^2_35][^2_36][^2_37][^2_38][^2_39][^2_40][^2_41][^2_42][^2_43][^2_44][^2_45][^2_46][^2_47][^2_48][^2_49][^2_50][^2_51][^2_52][^2_53][^2_54][^2_55][^2_56][^2_57][^2_58][^2_59][^2_60][^2_61][^2_62][^2_63][^2_64][^2_65][^2_66][^2_67][^2_68]</span>

<div align="center">⁂</div>

[^2_1]: https://neon.com/faqs/managed-postgres-databases-free-tier

[^2_2]: https://vercel.com/blog/ai-sdk-5

[^2_3]: https://vercel.com/docs/fluid-compute

[^2_4]: https://ai-sdk.dev/v5/docs/ai-sdk-ui/stream-protocol

[^2_5]: https://ai-sdk.dev/docs/ai-sdk-ui/streaming-data

[^2_6]: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol

[^2_7]: https://gist.github.com/ahmadrosid/c297498488795fb36d8076477c76e49e

[^2_8]: https://vercel.com/changelog/vercel-functions-can-now-run-up-to-30-minutes

[^2_9]: https://news.800.works/news/2026-06-16/vercel-functions-30-minute-ai-workloads/

[^2_10]: https://neon.com/faqs/free-plan-limits-and-quotas

[^2_11]: https://qaskills.sh/blog/langfuse-llm-observability-guide-2026

[^2_12]: https://neon.com/docs/guides/vercel-postgres-transition-guide

[^2_13]: https://kuberns.com/blogs/vercel-postgres-dead-what-replaced-it/

[^2_14]: https://vela.simplyblock.io/articles/neon-serverless-postgres-pricing-2026/

[^2_15]: https://neon.com/pricing

[^2_16]: https://neon.com/faqs/cheapest-ways-run-postgres-database-low-traffic

[^2_17]: https://freetier.co/directory/products/neon-serverless-postgres

[^2_18]: https://encore.dev/articles/neon-serverless-postgres

[^2_19]: https://solodevstack.com/blog/postgresql-vs-neon-solo-developers

[^2_20]: https://vercel.com/blog/a-new-programming-model-for-durable-execution

[^2_21]: https://vercel.com/docs/workflows

[^2_22]: https://opentelemetry.io/docs/specs/semconv/exceptions/exceptions-spans/

[^2_23]: https://nimblox.com/top-5-open-source-ai-powered-sdr-tools-on-github-2025/

[^2_24]: https://github.com/Salesably/awesome-ai-agents-for-sales

[^2_25]: https://www.clay.com/blog

[^2_26]: https://github.com/ComposioHQ/outreach-agent

[^2_27]: https://www.promptfoo.dev/docs/usage/node-api-reference/

[^2_28]: https://lavender.ai/blog

[^2_29]: https://pulseagent.io/open-source

[^2_30]: https://github.com/MatthewDailey/open-sdr

[^2_31]: https://www.promptfoo.dev/docs/category/usage/

[^2_32]: https://www.braintrust.dev/docs/evaluate

[^2_33]: https://github.com/topics/cold-calling

[^2_34]: https://qaskills.sh/blog/braintrust-llm-evaluation-guide-2026

[^2_35]: https://github.com/ChiragBellara/AI-SDR-Agent

[^2_36]: https://github.com/topics/sdr-automation

[^2_37]: https://www.braintrust.dev/docs/evaluation-quickstart

[^2_38]: https://www.zenml.io/llmops-database/rebuilding-an-ai-sdr-agent-with-multi-agent-architecture-for-enterprise-sales-automation

[^2_39]: https://www.linkedin.com/posts/ellogy_ai-agenticsystems-digitalworkers-activity-7341461628728541187-GxLg

[^2_40]: https://b2bsalesguru.medium.com/11x-ai-sdr-review-i-gave-it-200-leads-and-watched-what-happened-2026-45d14f2ca215

[^2_41]: https://www.linkedin.com/posts/luis-acevedo-ii-664b1020a_how-11x-rebuilt-their-alice-agent-from-react-activity-7340777815304216578-FMVd

[^2_42]: https://www.zenml.io/blog/llmops-in-production-another-419-case-studies-of-what-actually-works

[^2_43]: https://www.clay.com/blog/clay-series-c-announcement-the-gtm-engineering-era-begins-now

[^2_44]: https://clayground.ai/blog/gtm-engineering-clay-ai-agents-meetings

[^2_45]: https://www.clay.com/blog-category/clay-announcements

[^2_46]: https://www.11x.ai/worker/alice

[^2_47]: https://www.clay.com/blog-tag/ai

[^2_48]: https://www.letta.com/case-studies/11x/

[^2_49]: https://www.linkedin.com/posts/changsha-ma-9ba7a485_how-11x-rebuilt-their-alice-agent-from-react-activity-7343087985145397248-_BYm

[^2_50]: https://www.startuphub.ai/ai-news/ai-video/2025/alices-brain-11xs-knowledge-base-revolutionizes-ai-sales-reps

[^2_51]: https://x.com/llama_index/status/1953912358671462495

[^2_52]: https://futureagi.com/blog/rag-evaluation-metrics-deep-dive-2026/

[^2_53]: https://futureagi.com/blog/evaluating-rag-faithfulness-deep-dive-2026/

[^2_54]: https://futureagi.com/blog/evaluating-rag-systems-ensuring-your-llm-remembers-what-it-reads/

[^2_55]: https://futureagi.com/glossary/rag-faithfulness/

[^2_56]: https://futureagi.com/blog/rag-evaluation-metrics-2025/

[^2_57]: https://futureagi.com/blog/what-is-rag-evaluation-2026/

[^2_58]: https://arxiv.org/html/2605.21071v4

[^2_59]: https://futureagi.com/blog/agentic-rag-systems-2025/

[^2_60]: https://github.com/mattpocock/evalite

[^2_61]: https://www.evalite.dev/

[^2_62]: https://futureagi.com/blog/what-is-retrieval-augmented-generation-2026/

[^2_63]: https://www.open-source-tools.com/evalite

[^2_64]: https://jimmysong.io/ai/evalite/

[^2_65]: https://www.reddit.com/r/QualityAssurance/comments/1qfp9qd/trusting_your_llmasajudge/

[^2_66]: https://neon.com/faqs/postgres-services-free-to-production

[^2_67]: https://saaspricehub.io/tools/neon

[^2_68]: https://vibecoding.app/blog/neon-review


---

# \# Perplexity Deep Research — Part 3 of 3: Streaming UI, deployment, and a critique

> Copy everything below the line. Shortest of the three; Section C is the one I care most about.

---

You are a technical research analyst and a critical reviewer. Two jobs here: give me the current state of practice on a few implementation questions, then **tell me where my plan is wrong.**

## Context

I'm building a single-prospect B2B sales-outreach research agent (portfolio/case-study project for a job application; Next.js + TypeScript on Vercel, Anthropic Claude API). It must be submitted in under a week and then **demoed live, on a screen share, on an arbitrary real person the interviewer names.**

Input: one prospect (name + company). Pipeline: identity resolution → suppression check → firmographic enrichment → signal discovery (multiple external APIs) → signal scoring → confidence gate → either draft a personalized outreach email or route to a visible "needs human judgment" state. Never auto-sends.

The core design goal is **restraint**: the system must be able to say "I don't have enough to personalize this confidently" rather than invent a plausible hook.

**The UI is explicitly graded.** The brief requires a **live run view** showing each pipeline stage as it executes, and a **dashboard** showing history, status, and outputs across runs.

## Hard constraints

- **Free tiers and pay-per-use only. No monthly subscriptions.**
- **Next.js + TypeScript on Vercel serverless.** Stack is fixed — don't propose changing it.
- **Timeline is days.** Must work live during a screen-shared interview.


## Evidence standards

- **Primary sources** — official docs, framework changelogs, engineering blogs. Filter out SEO content marketing aggressively.
- **Date everything**, and flag where a widely-repeated pattern is now outdated.
- **Mark low-confidence claims explicitly.**

---

## Research questions

### A. Streaming multi-stage pipeline progress to a web UI

**A1. Current best practice, August 2026.** For streaming progress from a long-running server process to a React UI on Next.js/Vercel: raw SSE, the Vercel AI SDK (`ai` + `@ai-sdk/anthropic`), React Server Components streaming, WebSockets, or something newer? What's actually current versus what's repeated from 2024 tutorials?

**A2. The distinction that matters to me.** Most material covers streaming **LLM tokens**. I need to stream **structured multi-stage pipeline progress** — discrete events like `{stage: "signal_discovery", status: "running", message: "...", timestamp: ...}` — where only some stages involve an LLM at all. This seems much less well covered. What's the right pattern? Does the Vercel AI SDK help here or is it the wrong abstraction for non-token event streams?

**A3. Vercel serverless specifics.** What actually breaks in production but not locally? Response buffering, function duration limits, Fluid Compute behavior, connection drops, reconnection handling, proxy/CDN buffering of SSE. Concrete gotchas with sources.

**A4. Patterns worth copying.** Any open-source component libraries, UI patterns, or reference implementations for **agent/pipeline run views** — stage timelines, live status, reasoning traces, evidence panels? Anything visually strong I should look at, including from outside this product category.

### B. Persistence and deployment (brief)

**B1. Small Postgres or equivalent on Vercel, free tier, August 2026.** Vercel Postgres was discontinued and migrated to Neon. Which marketplace integrations are genuinely free at kilobyte scale? What's the current recommended driver and connection pattern for serverless? Is Postgres even the right call for storing a few hundred JSON run records, versus something simpler?

**B2. Common production surprises** with Vercel function limits, Fluid Compute, cold starts, or environment variables that catch people out on first deploy.

### C. Critique — the part I care most about

Given everything above, and assuming I have **a few days**, answer these directly and bluntly:

**C1. What would you cut?** Where am I likely over-building relative to what a technical interviewer will actually notice and reward?

**C2. What's cheap to build and disproportionately impressive?** Specific, concrete features or UI details that punch far above their implementation cost in a live demo of an AI agent pipeline.

**C3. How does this kind of build most commonly fail in a live demo?** Not generic advice — specific failure modes for a multi-API, LLM-backed pipeline being screen-shared to an interviewer who may name an arbitrary input. And what's the standard prevention for each?

**C4. Where is my plan wrong or naive?** I've described the architecture above in enough detail to critique. Assume I've made mistakes I can't see. Be specific and blunt rather than encouraging — I'd rather hear it now than discover it on demo day.

**C5. What separates a memorable submission from a competent one** in a take-home where many candidates build a similar pipeline? The brief explicitly says the interviewer cares about "the judgment behind your design choices" and being able to "explain it clearly to a non-technical buyer."

## Output format

Markdown, organized A / B / C. Options tables where the question is tool-shaped (tool · what it does · free tier · maturity · link · date verified). Ranked recommendations with reasoning. **Explicitly rejected** items — what you dismissed and why. Confidence flags on anything uncertain.

For Section C, prose is fine — I want judgment there, not tables.

End with **"Things you did not ask about but should know."**

I’ve created a full report that covers streaming patterns, Neon/Vercel deployment details, and a blunt critique of your current plan, with emphasis on Section C (what to cut, what’s high‑leverage, and how live demos actually fail).[^3_1][^3_2]

You can read it to see:

- How to use AI SDK v5 data parts for stage-by-stage streaming over SSE.[^3_3][^3_1]
- Why Neon’s free tier is the right persistence choice and what its limits are.[^3_2][^3_4]
- Concrete demo failure modes (low-footprint prospect, identity misresolution, cold starts) and preventive patterns tailored to your pipeline.
<span style="display:none">[^3_10][^3_100][^3_101][^3_102][^3_103][^3_104][^3_105][^3_106][^3_107][^3_108][^3_109][^3_11][^3_110][^3_111][^3_112][^3_113][^3_114][^3_115][^3_116][^3_117][^3_118][^3_119][^3_12][^3_120][^3_121][^3_122][^3_123][^3_124][^3_125][^3_126][^3_127][^3_128][^3_129][^3_13][^3_130][^3_131][^3_132][^3_133][^3_134][^3_135][^3_136][^3_137][^3_138][^3_139][^3_14][^3_140][^3_141][^3_142][^3_143][^3_144][^3_145][^3_146][^3_147][^3_148][^3_149][^3_15][^3_150][^3_151][^3_152][^3_153][^3_154][^3_155][^3_156][^3_157][^3_158][^3_159][^3_16][^3_160][^3_161][^3_162][^3_163][^3_164][^3_165][^3_166][^3_167][^3_168][^3_169][^3_17][^3_170][^3_171][^3_172][^3_173][^3_174][^3_175][^3_176][^3_177][^3_178][^3_179][^3_18][^3_180][^3_181][^3_182][^3_183][^3_184][^3_185][^3_186][^3_187][^3_188][^3_19][^3_20][^3_21][^3_22][^3_23][^3_24][^3_25][^3_26][^3_27][^3_28][^3_29][^3_30][^3_31][^3_32][^3_33][^3_34][^3_35][^3_36][^3_37][^3_38][^3_39][^3_40][^3_41][^3_42][^3_43][^3_44][^3_45][^3_46][^3_47][^3_48][^3_49][^3_5][^3_50][^3_51][^3_52][^3_53][^3_54][^3_55][^3_56][^3_57][^3_58][^3_59][^3_6][^3_60][^3_61][^3_62][^3_63][^3_64][^3_65][^3_66][^3_67][^3_68][^3_69][^3_7][^3_70][^3_71][^3_72][^3_73][^3_74][^3_75][^3_76][^3_77][^3_78][^3_79][^3_8][^3_80][^3_81][^3_82][^3_83][^3_84][^3_85][^3_86][^3_87][^3_88][^3_89][^3_9][^3_90][^3_91][^3_92][^3_93][^3_94][^3_95][^3_96][^3_97][^3_98][^3_99]</span>

<div align="center">⁂</div>

[^3_1]: https://vercel.com/blog/ai-sdk-5

[^3_2]: https://neon.com/faqs/managed-postgres-databases-free-tier

[^3_3]: https://ai-sdk.dev/v5/docs/ai-sdk-ui/stream-protocol

[^3_4]: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol

[^3_5]: https://gist.github.com/ahmadrosid/c297498488795fb36d8076477c76e49e

[^3_6]: https://zenn.dev/tsuboi/articles/26e3fe8fb6dc98?locale=en

[^3_7]: https://vercel.com/changelog/vercel-functions-can-now-run-up-to-30-minutes

[^3_8]: https://news.800.works/news/2026-06-16/vercel-functions-30-minute-ai-workloads/

[^3_9]: https://neon.com/faqs/cheapest-ways-run-postgres-database-low-traffic

[^3_10]: https://neon.com/faqs/best-free-low-cost-managed-postgres-services

[^3_11]: https://solodevstack.com/blog/postgresql-vs-neon-solo-developers

[^3_12]: https://qaskills.sh/blog/langfuse-llm-observability-guide-2026

[^3_13]: https://encore.dev/articles/neon-serverless-postgres

[^3_14]: https://vercel.com/blog/a-new-programming-model-for-durable-execution

[^3_15]: https://agentdeals.dev/vendor/neon

[^3_16]: https://plans.apis.io/plans/neon/neon-plans-pricing/

[^3_17]: https://freetier.co/directory/products/neon-serverless-postgres

[^3_18]: https://neon.com/faqs/postgres-services-free-to-production

[^3_19]: https://www.buildmvpfast.com/tools/api-pricing-estimator/neon

[^3_20]: https://finance.yahoo.com/news/linkedin-wins-legal-case-against-162510557.html

[^3_21]: https://www.linkedin.com/posts/matttweed_linkedin-pressroom-linkedin-activity-7356373450925527041-xADU

[^3_22]: https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access?view=li-lms-2026-07

[^3_23]: https://www.linkedin.com/posts/tylerseymour1_linkedin-pressroom-linkedin-activity-7355668818985132033-v5zC

[^3_24]: https://learn.microsoft.com/en-us/linkedin/marketing/integrations/marketing-tiers?view=li-lms-2026-07

[^3_25]: https://news.linkedin.com/2025/LinkedInWinsLegalBattleToProtectMemberData

[^3_26]: https://sociavault.com/blog/linkedin-api-free-2026

[^3_27]: https://linkedapi.io/guides/linkedin-api-access

[^3_28]: https://learn.microsoft.com/en-us/linkedin/marketing/tips-to-get-started?view=li-lms-2026-08

[^3_29]: https://learn.microsoft.com/en-us/linkedin/marketing/integrations/marketing-tiers?view=li-lms-2026-05

[^3_30]: https://connectsafely.ai/articles/linkedin-api-complete-guide-2026

[^3_31]: https://www.blotato.com/blog/linkedin-api-pricing

[^3_32]: https://www.reuters.com/article/world/data-scrapers-case-v-linkedin-pits-free-speech-against-cfaa-dmca-idUSKBN19B2WD/

[^3_33]: https://www.linkedin.com/posts/markvalentine1_due-diligence-matters-more-than-ever-when-activity-7389220721622695936-8Qf7

[^3_34]: https://news.bloomberglaw.com/privacy-and-data-security/linkedin-loses-latest-round-of-data-scraping-legal-feud-with-hiq

[^3_35]: https://linkedapi.io/guides/proxycurl-alternatives

[^3_36]: https://www.cnbc.com/2024/05/10/elon-musks-x-loses-lawsuit-against-bright-data-over-data-scraping.html

[^3_37]: https://brightdata.com/blog/web-data/court-rules-in-favor-of-bright-data-in-meta-v-bright-data-case

[^3_38]: https://www.fbm.com/publications/major-decision-affects-law-of-scraping-and-online-data-collection-meta-platforms-v-bright-data/

[^3_39]: https://www.reuters.com/legal/musks-x-corp-loses-lawsuit-against-israeli-data-scraping-company-2024-05-10/

[^3_40]: https://www.skadden.com/insights/publications/2024/05/district-court-adopts-broad-view

[^3_41]: https://api.market/blog/z-api-hub/z-linkedin/best-linkedin-scraping-api-2026

[^3_42]: https://www.lowenstein.com/news-insights/publications/client-alerts/meta-v-bright-data-ruling-has-important-implications-for-webscraping-activities-by-investment-advisers-im

[^3_43]: https://brightdata.com/blog/general/meta-dismisses-claim-against-bright-data

[^3_44]: https://coresignal.com/pricing/

[^3_45]: https://connectsafely.ai/articles/best-proxycurl-alternative-linkedin-inbound-2026

[^3_46]: https://www.law360.com/cases/64c158650e7ec102e1e49064/articles

[^3_47]: https://www.proskauer.com/release/proskauer-secures-dismissal-of-scraping-claims-against-bright-data

[^3_48]: https://dev.to/agenthustler/best-proxycurl-alternative-in-2026-apify-linkedin-scrapers-vs-scrapingdog-vs-linkdapi-11n7

[^3_49]: https://techcrunch.com/2024/01/24/court-rules-in-favor-of-a-web-scraper-bright-data-which-meta-had-used-and-then-sued/

[^3_50]: https://exa.ai/pricing

[^3_51]: https://exa.ai/pricing?tab=websets

[^3_52]: https://exa.ai/

[^3_53]: https://exa.ai/docs/reference/pricing

[^3_54]: https://crawlcrawl.com/blog/firecrawl-pricing

[^3_55]: https://www.eesel.ai/blog/firecrawl-pricing

[^3_56]: https://use-apify.com/blog/firecrawl-review-2026

[^3_57]: https://syncgtm.com/blog/firecrawl-review-2026

[^3_58]: https://scrapegraphai.com/blog/firecrawl-pricing

[^3_59]: https://platform.claude.com/docs/en/about-claude/pricing

[^3_60]: https://costbench.com/software/web-scraping/firecrawl/

[^3_61]: https://fastcrw.com/blog/exa-pricing-explained

[^3_62]: https://apicostcalc.com/exa.html

[^3_63]: https://www.usagepricing.com/blueprint/firecrawl

[^3_64]: https://affinco.com/firecrawl-pricing/

[^3_65]: https://docs.tavily.com/documentation/api-credits

[^3_66]: https://www.tavily.com/pricing

[^3_67]: https://coldiq.com/blog/tavily-pricing

[^3_68]: https://makerstack.co/reviews/jina-reader-review/

[^3_69]: https://help.tavily.com/articles/8816424538-pricing

[^3_70]: https://uragent.org/tools/tavily/

[^3_71]: https://webscraping.cc/tool/tavily/

[^3_72]: https://vibecodedthis.com/pricing/tavily-pricing/

[^3_73]: https://agenticindex.io/vendors/tavily

[^3_74]: https://www.buildmvpfast.com/tools/api-pricing-estimator/tavily

[^3_75]: https://tokenmix.ai/blog/tavily-ai-api-pricing-2026-credits-rate-limits

[^3_76]: https://webscraping.cc/tool/brave-search/

[^3_77]: https://www.eggstriker.com/en/ai-api/jinaai

[^3_78]: https://www.linkstartai.com/en/agents/jina

[^3_79]: https://jina.ai/reader/

[^3_80]: https://apiserpent.com/blog/free-google-search-api-tested

[^3_81]: https://apiserpent.com/blog/serper-pricing-credits-explained

[^3_82]: https://enjyn.ai/tools/serper/

[^3_83]: https://bestscraperapi.com/guides/scrapingbee-review

[^3_84]: https://scrappa.co/serper-alternative

[^3_85]: https://webscraping.cc/tool/scrapingbee/

[^3_86]: https://www.scrapingbee.com/pricing/

[^3_87]: https://syncgtm.com/blog/scrapingbee-review-2026

[^3_88]: https://proxylook.com/providers/scrapingbee

[^3_89]: https://scrap.io/serper-dev-vs-scrap-io-google-maps-scraper-comparison

[^3_90]: https://www.fahimai.com/scrapingbee

[^3_91]: https://vibecodedthis.com/pricing/scrapingbee-pricing/

[^3_92]: https://dataresearchtools.com/scrapingbee-review/

[^3_93]: https://gtmprices.com/tools/scrapingbee

[^3_94]: https://costbench.com/software/web-scraping/serper/

[^3_95]: https://www.zenml.io/llmops-database/rebuilding-an-ai-sdr-agent-with-multi-agent-architecture-for-enterprise-sales-automation

[^3_96]: https://github.com/ong/awesome-ai-gtm

[^3_97]: https://github.com/MatthewDailey/open-sdr

[^3_98]: https://github.com/ComposioHQ/outreach-agent

[^3_99]: https://www.linkedin.com/posts/luis-acevedo-ii-664b1020a_how-11x-rebuilt-their-alice-agent-from-react-activity-7340777815304216578-FMVd

[^3_100]: https://formanorden.com/open-source/sdr-operations-playbook/

[^3_101]: https://github.com/topics/sdr-automation

[^3_102]: https://github.com/Salesably/awesome-ai-agents-for-sales

[^3_103]: https://github.com/topics/b2b-sales

[^3_104]: https://pulseagent.io/open-source

[^3_105]: https://www.linkedin.com/posts/changsha-ma-9ba7a485_how-11x-rebuilt-their-alice-agent-from-react-activity-7343087985145397248-_BYm

[^3_106]: https://github.com/topics/ai-sales?l=shell\&o=asc\&s=updated

[^3_107]: https://www.linkedin.com/pulse/build-ai-powered-outbound-sdr-system-free-sam-claassen-cihre

[^3_108]: https://github.com/topics/lead-generation?l=shell\&o=asc\&s=stars

[^3_109]: https://nimblox.com/top-5-open-source-ai-powered-sdr-tools-on-github-2025/

[^3_110]: https://arxiv.org/html/2604.23588v1

[^3_111]: https://arxiv.org/html/2601.19927v1

[^3_112]: https://arxiv.org/html/2607.09349v1

[^3_113]: https://ragaboutit.com/5-new-rag-attribution-methods-that-slash-hallucinations-80/

[^3_114]: https://aclanthology.org/2026.acl-long.1492.pdf

[^3_115]: https://arxiv.org/html/2607.04223v1

[^3_116]: https://futureagi.com/blog/evaluating-rag-faithfulness-deep-dive-2026/

[^3_117]: https://nemorize.com/roadmaps/2026-modern-ai-search-rag-roadmap/lessons/grounding-hallucination-control

[^3_118]: https://oneuptime.com/blog/post/2026-01-30-hallucination-detection/view

[^3_119]: https://seodatapulse.com/comparisons/best-ai-eval-platforms-braintrust-vs-promptfoo-vs-langfuse-2026/

[^3_120]: https://arxiv.org/html/2504.15771v1

[^3_121]: https://uptrace.dev/guides/opentelemetry-rag-observability

[^3_122]: https://arxiv.org/html/2607.00895

[^3_123]: https://benchmarkingagents.com/tools-compared/

[^3_124]: https://futureagi.com/blog/llm-hallucination-deep-dive-2026/

[^3_125]: https://opentelemetry.io/docs/specs/semconv/general/recording-errors/

[^3_126]: https://opentelemetry.io/docs/specs/semconv/exceptions/exceptions-spans/

[^3_127]: https://hidekazu-konishi.com/entry/opentelemetry_genai_semantic_conventions_guide.html

[^3_128]: https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md

[^3_129]: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/

[^3_130]: https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md

[^3_131]: https://opentelemetry.io/docs/specs/otel/trace/exceptions/

[^3_132]: https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/README.md

[^3_133]: https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-metrics.md

[^3_134]: https://akashtalole.github.io/posts/testing-non-deterministic-ai-systems/

[^3_135]: https://multigrid.ai/learn/snapshot-and-property-testing

[^3_136]: https://opentelemetry.io/docs/specs/semconv/gen-ai/

[^3_137]: https://leeroopedia.com/index.php/Principle:Unstructured_IO_Unstructured_Golden_File_Regression_Testing

[^3_138]: https://futureagi.com/blog/llm-regression-testing-model-swap/

[^3_139]: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/

[^3_140]: https://github.com/vercel/ai/issues/3056

[^3_141]: https://ai-sdk.dev/docs/ai-sdk-ui/streaming-data

[^3_142]: https://www.saasturf.com/blog/neon-vs-supabase-vs-vercel-postgres/

[^3_143]: https://vercel.com/marketplace/neon

[^3_144]: https://github.com/vercel/ai/issues/5046

[^3_145]: https://github.com/vercel/ai/issues/8549

[^3_146]: https://usenightowl.com/guides/setup-nightowl-with-vercel-postgres/

[^3_147]: https://vercel.com/docs/fluid-compute

[^3_148]: https://kuberns.com/blogs/vercel-postgres-dead-what-replaced-it/

[^3_149]: https://neon.com/docs/guides/vercel-postgres-transition-guide

[^3_150]: https://www.clay.com/blog

[^3_151]: https://www.promptfoo.dev/docs/usage/node-api-reference/

[^3_152]: https://lavender.ai/blog

[^3_153]: https://www.promptfoo.dev/docs/category/usage/

[^3_154]: https://www.braintrust.dev/docs/evaluate

[^3_155]: https://github.com/topics/cold-calling

[^3_156]: https://qaskills.sh/blog/braintrust-llm-evaluation-guide-2026

[^3_157]: https://github.com/ChiragBellara/AI-SDR-Agent

[^3_158]: https://www.braintrust.dev/docs/evaluation-quickstart

[^3_159]: https://www.linkedin.com/posts/ellogy_ai-agenticsystems-digitalworkers-activity-7341461628728541187-GxLg

[^3_160]: https://b2bsalesguru.medium.com/11x-ai-sdr-review-i-gave-it-200-leads-and-watched-what-happened-2026-45d14f2ca215

[^3_161]: https://www.zenml.io/blog/llmops-in-production-another-419-case-studies-of-what-actually-works

[^3_162]: https://www.clay.com/blog/clay-series-c-announcement-the-gtm-engineering-era-begins-now

[^3_163]: https://clayground.ai/blog/gtm-engineering-clay-ai-agents-meetings

[^3_164]: https://www.clay.com/blog-category/clay-announcements

[^3_165]: https://www.11x.ai/worker/alice

[^3_166]: https://www.clay.com/blog-tag/ai

[^3_167]: https://www.letta.com/case-studies/11x/

[^3_168]: https://www.startuphub.ai/ai-news/ai-video/2025/alices-brain-11xs-knowledge-base-revolutionizes-ai-sales-reps

[^3_169]: https://x.com/llama_index/status/1953912358671462495

[^3_170]: https://futureagi.com/blog/rag-evaluation-metrics-deep-dive-2026/

[^3_171]: https://futureagi.com/blog/evaluating-rag-systems-ensuring-your-llm-remembers-what-it-reads/

[^3_172]: https://futureagi.com/glossary/rag-faithfulness/

[^3_173]: https://futureagi.com/blog/rag-evaluation-metrics-2025/

[^3_174]: https://futureagi.com/blog/what-is-rag-evaluation-2026/

[^3_175]: https://arxiv.org/html/2605.21071v4

[^3_176]: https://futureagi.com/blog/agentic-rag-systems-2025/

[^3_177]: https://github.com/mattpocock/evalite

[^3_178]: https://www.evalite.dev/

[^3_179]: https://futureagi.com/blog/what-is-retrieval-augmented-generation-2026/

[^3_180]: https://www.open-source-tools.com/evalite

[^3_181]: https://jimmysong.io/ai/evalite/

[^3_182]: https://www.reddit.com/r/QualityAssurance/comments/1qfp9qd/trusting_your_llmasajudge/

[^3_183]: https://saaspricehub.io/tools/neon

[^3_184]: https://vibecoding.app/blog/neon-review

[^3_185]: https://neon.com/faqs/free-plan-limits-and-quotas

[^3_186]: https://vela.simplyblock.io/articles/neon-serverless-postgres-pricing-2026/

[^3_187]: https://neon.com/pricing

[^3_188]: https://vercel.com/docs/workflows

