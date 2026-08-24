# Data Sources & Orchestration for a B2B Prospect-Research Agent (2026)

## Executive summary

This report evaluates data sources and orchestration choices for a single‑prospect B2B research‑and‑drafting agent aimed at 5–20 highly personalized cold emails per day into corporate inboxes in 2026. The analysis prioritizes legal exposure, reliability, and low cost over raw volume, and assumes a solo developer building an MVP in days, not months.

At 2026 prices, LinkedIn scraping via marketplace actors (Apify), automation tools (PhantomBuster), or data vendors (Bright Data and now‑defunct Proxycurl) is technically feasible but sits on increasingly hostile legal ground (post‑hiQ contract law, LinkedIn’s 2025 win over Proxycurl) and brings real platform‑ban and GDPR risk for a small operator. Meanwhile, ATS job‑board APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee) and public news/filing feeds (Google News RSS, EDGAR) remain open, unauthenticated, and intentionally syndication‑friendly, making them the natural backbone for a low‑volume, high‑intent personalization pipeline.

The recommendation is to build an MVP that leans almost entirely on ATS job postings plus company news/filings and a modern search API (Exa or similar) for person‑name/company lookups, orchestrated in pure Python (asyncio + typed return values, no heavy framework) with strong verification and deterministic testing. Gmail drafts should be created through the official Gmail API using the `gmail.compose` scope, with a single‑user OAuth flow and local token storage; there is no "drafts‑only" scope, so the code must enforce "never send" at the application layer.

The strongest argument against this stack is that it under‑uses person‑level LinkedIn context, which can increase reply rates when grounded in genuine activity signals; however, for an ops/finance automation product and low daily volume, the incremental lift over a well‑chosen ATS/job signal is speculative relative to the legal and operational complexity. Key uncertainties are: the true incremental reply‑rate lift from deep person‑level LinkedIn research versus job/company signals for this persona and price point, and how aggressively EU regulators will continue to police "legitimate interest" as a basis for scraped data enrichment in outbound sales.

***

## Part 1 — LinkedIn data extraction options in 2026

### 1.1 Tooling and pricing landscape

**Apify LinkedIn actors.** Apify is a marketplace: LinkedIn scrapers are priced by independent developers, typically between **1.50 and 12.00 USD per 1,000 profiles** and **0.28 to 5.00 USD per 1,000 jobs**, with many actors bundling platform compute into a per‑result fee. A recent 2026 pricing survey of seven LinkedIn‑focused actors (including HarvestAPI and Dev Fusion) reports 1,000 LinkedIn profiles at 4–12 USD and 1,000 jobs at 0.28–5 USD, with Apify’s own plan acting as a spending floor (0, 29, 199, 999 USD/month) rather than a hard subscription. Many popular LinkedIn actors now use their own proxy pools and do **not** require a customer’s personal LinkedIn cookie (for example, HarvestAPI’s profile and company‑employees actors), explicitly advertising "no cookies required" for reliability and lower ban risk.

**PhantomBuster.** PhantomBuster remains a cloud automation platform with 150+ "Phantoms" across LinkedIn and other networks, priced between **69 and 439 USD/month** (Starter, Pro, Team) with 20–300 hours of execution and 5–50 concurrent slots. 2026 reviews stress that safe LinkedIn use also requires **50–200 USD/month** of third‑party residential proxies, pushing the effective cost for a solo operator into the **106–552 USD/month** range. PhantomBuster is still widely used for LinkedIn exports and light automation, but independent analyses note that LinkedIn’s 2024‑2026 anti‑bot upgrades have made cloud automation far easier to detect via datacenter IPs and robotic behavior patterns, and recommend limiting it to read‑only, low‑volume scraping (under about 50 profiles/day) while avoiding automated connection requests or DMs entirely.

**Bright Data.** Bright Data offers two distinct LinkedIn products in 2026: a **Web Scraper API** that returns live, structured records from LinkedIn URLs or search terms, and a **Dataset Marketplace** with large pre‑scraped LinkedIn datasets. The Web Scraper API is priced at **1.50 USD per 1,000 records** on pay‑as‑you‑go with 5,000 free records per month, dropping to around **1.10–1.00 USD per 1,000** on committed "Scale" plans. The LinkedIn dataset starts at **250 USD for 100,000 records** (2.50 USD per 1,000) with volume discounts down to 0.50 USD per 1,000 by 20 million records; the minimum order remains 100,000 records, so this is a bulk option, not an on‑demand enrichment tier. Bright Data’s own marketing shows the Web Scraper API cheaper than the dataset up to roughly 5 million records, but at MVP volumes (tens of profiles per day), the free tier or low‑volume API is effectively free.

**Proxycurl.** Proxycurl shut down in 2025 after LinkedIn sued its parent company, Nubela, in the Northern District of California for large‑scale scraping and creation of fake accounts; a July 2025 goodbye post confirms the shutdown following litigation and the team’s pivot to a new product. LinkedIn’s own news release in July 2025 characterizes the settlement as a win that requires Proxycurl to permanently delete scraped data and stop accessing LinkedIn, reinforcing LinkedIn’s willingness to pursue data vendors, not just end‑user scrapers. A 2026 market overview frames Proxycurl’s demise as a cautionary tale and suggests replacing its "profile URL in, JSON out" endpoints with either real‑time scrapers (Apify, Bright Data, ScrapIn) or account‑based APIs (Linked API, Unipile) that act through the customer’s own LinkedIn session.

**Newer entrants: ScrapIn, Linked API, HarvestAPI, Linked API clones.** A 2026 comparison of "Proxycurl alternatives" groups current LinkedIn‑adjacent products into three models: real‑time scrapers (ScrapIn, Apify, Bright Data) that return live scraped records; dataset providers (Coresignal, People Data Labs) with months‑old bulk profile data; and account‑based APIs (Linked API, Unipile) that operate via the customer’s authenticated LinkedIn account. Real‑time scrapers typically cost **1.50–4.00 USD per 1,000 profiles**, while dataset vendors quote around **0.005–0.20 USD per record** at high volumes; account‑based APIs charge per connected account rather than per record and shift the legal and ban risk to the customer’s own LinkedIn seat.

**Official LinkedIn Sales Navigator / Marketing APIs.** LinkedIn’s own Sales Navigator Application Platform (SNAP) remains **closed to new partners** in 2026; official documentation and partner‑facing pages explicitly state that LinkedIn is not accepting new applications for Sales Navigator API access. Third‑party reviews summarizing the 2026 state of SNAP note that:

- There is **no standalone public Sales Navigator API** for search or lead export; API access is reserved for a small set of CRM partners and powers CRM sync and embedded experiences only.
- Every end‑user must hold a paid Sales Navigator seat (Core at **119.99 USD/month**, Advanced at **159.99 USD/month**, Advanced Plus via "contact sales" with at least 10 seats), and SNAP access is layered on top of these subscriptions via a separate partnership agreement.
- Partners cannot charge separately for API access, and there is no per‑call or per‑credit pricing; the cost is embedded in the Sales Navigator subscription and partnership overhead.

For a solo developer without an existing CRM partnership, official LinkedIn APIs are effectively off the table.

### 1.2 Ban resistance and operational reliability

**Session cookies vs. provider‑side proxies.** Many classic browser‑automation approaches (including some Apify actors and PhantomBuster workflows) operate by reusing a customer’s LinkedIn session cookie in a browser context. In that model, ban risk lands directly on the customer’s personal or corporate LinkedIn account and is exacerbated by cloud execution patterns (datacenter IPs, non‑human interaction patterns, compressed action timings). Independent 2026 analyses of LinkedIn automation note that LinkedIn’s 2024–2026 anti‑bot stack flags sessions originating from known datacenter IP ranges and detects "non‑human" behavior such as sending dozens of connection requests in minutes without scrolling, hovering, or idle time.

By contrast, some newer Apify actors and Bright Data’s Web Scraper API abstract the session and proxy management into the provider; the customer sends a URL or search term and receives JSON without handling cookies. That design moves ban and blocking risk to the vendor’s own LinkedIn accounts and proxy pools, which are managed at scale and rotated frequently, but it also means the vendor itself becomes the primary target for LinkedIn legal enforcement (as seen with Proxycurl).

**Observed ban patterns.** PhantomBuster’s own safety guidance in 2026 claims that its cloud automation is safe when activity stays within "natural" behavioral limits (for example, 40–100 connection requests per week on warmed accounts and under 80 profile views per day) and that many account "bans" are actually session cookie expirations or temporary restrictions. However, independent reviews argue that in 2026, Phantombuster‑style cloud automation is 5–10x more likely to trigger LinkedIn restrictions than it was in 2020–2022, and recommend restricting it to low‑volume, read‑only scraping or Sales Navigator export while avoiding automated connection or messaging.

For this MVP with just 5–20 research runs per day and no need to send actions on LinkedIn, scraping a small number of public profiles or company pages via a provider‑side scraper (Apify actor, Bright Data) at low volume is operationally feasible; but any workflow tied to a personal LinkedIn account’s cookie is fragile and hard to justify given the modest value per prospect.

### 1.3 Legal exposure: ToS, hiQ v. LinkedIn, and GDPR

**LinkedIn ToS and contract law after hiQ.** The long‑running hiQ v. LinkedIn litigation produced several key data points by 2022:

- The Ninth Circuit’s April 2022 opinion reaffirmed that scraping public websites (data accessible without logging in) generally does **not** violate the Computer Fraud and Abuse Act (CFAA) "without authorization" clause, limiting CFAA as a tool against scrapers of public data.
- However, subsequent district‑court proceedings and a December 2022 stipulation clarified that hiQ’s scraping still breached LinkedIn’s User Agreement and could give rise to **contract and tort liability** (trespass to chattels, misappropriation), even where CFAA claims were weak.
- Legal commentary now frames CFAA claims for scraping public data as largely non‑viable, but emphasizes that breach‑of‑contract claims based on terms of use prohibiting scraping remain available and can support injunctions and damages.

This means that in 2026, scraping public LinkedIn data is less likely to be prosecuted as a federal computer crime in the Ninth Circuit but remains clearly contrary to LinkedIn’s ToS and can lead to civil liability, as Proxycurl’s 2025 settlement starkly illustrates.

**Proxycurl lawsuit and LinkedIn enforcement trend (post‑2024, pre‑2026).** In January 2025, LinkedIn sued Nubela (Proxycurl’s operator) for scraping millions of member profiles and using fake accounts to power its enrichment APIs; by July 2025, a settlement and permanent injunction required Proxycurl to delete all LinkedIn‑derived data and shut down the API. LinkedIn’s own announcement describes the case as part of a broader effort to protect member data, and industry commentary notes that Proxycurl’s shutdown is a warning shot to any vendor whose business model depends heavily on scraped LinkedIn datasets rather than customer‑owned sessions.

For a solo developer whose product ultimately sends emails into corporate inboxes, the reputational cost of relying on a data vendor that could be enjoined and forced to wipe its database mid‑flight is non‑trivial.

**GDPR and "legitimate interest" for scraped enrichment.** Many enrichment vendors historically justify processing scraped personal data under GDPR’s "legitimate interests" basis, especially for B2B prospecting and sales. However, European regulators have increasingly scrutinized such claims, particularly where individuals have no reasonable expectation that their data will be used for cold outreach or where sensitive categories (inferred from profile content) might be processed. Since 2025, there have been enforcement actions and guidance emphasizing that even for B2B marketing, controllers must balance their interests against data subjects’ rights, provide clear information, and be able to demonstrate necessity and proportionality.

While there is no single "LinkedIn scraping GDPR test case" that definitively outlaws this use, the combination of platform hostility, uncertain GDPR balancing, and the Proxycurl precedent makes LinkedIn‑centric enrichment a risky default choice for a solo builder sending low‑volume but highly visible emails.

### 1.4 Reliability and product viability

**Working vs. "zombie" products.** In 2026, Apify, Bright Data, and PhantomBuster all have active documentation, changelogs, and recently updated pricing pages, indicating ongoing maintenance and compatibility with LinkedIn’s current front‑end. By contrast, Proxycurl is a "zombie" with legacy marketing content but no active service; its shutdown is documented by the maintainer’s blog and LinkedIn’s own statements. Some smaller scrapers and browser extensions appear to be in maintenance mode with stale documentation, but the mainstream tools remain functional.

For a low‑volume, research‑first agent, the primary reliability question is not whether scraping can work at all, but whether it will continue working without breaking every time LinkedIn tweaks its markup or anti‑bot behavior. Provider‑managed scrapers (Apify actors with active owners, Bright Data’s API, ScrapIn’s managed scrapers) are much more likely to keep pace than a home‑grown scraper, but the more you depend on LinkedIn as a primary signal, the more brittle your system becomes.

### 1.5 Part 1 recommendation

At 5–20 prospects per day, LinkedIn scraping is **a nice‑to‑have adjunct**, not a core dependency.

- If you include LinkedIn at all, treat it as a **secondary enrichment source** used sparingly (for example, a single profile pull to verify title and seniority) via a provider‑side scraper such as an Apify LinkedIn actor or Bright Data’s Web Scraper API, which at this volume will cost effectively 0–5 USD/month.
- Avoid designs that rely on the user’s own LinkedIn session cookie or on any tool that sends automated actions (connection requests, DMs); keep all use read‑only and low‑volume.
- Do **not** tie the MVP’s value proposition to LinkedIn‑derived datasets, given recent enforcement against vendors and the ease with which this layer could disappear.

For this project, LinkedIn data should be treated as a **thin, optional layer** used only when everything else fails to yield a decent personalization hook.

***

## Part 2 — Is LinkedIn even the right primary source?

### 2.1 Empirical evidence on personalization and signals

There is no single 2026 study that cleanly decomposes cold‑outreach reply rates by "LinkedIn person‑level signals vs. ATS/company‑level signals"; however, several large benchmark reports and vendor analyses shed light on the relative importance of signal quality and type.

**Cold email personalization benchmarks.** Lavender’s long‑running cold email benchmark data, updated in 2026, shows that well‑constructed, personalized emails (scoring "A" in their model) see **31–79% higher reply rates** than average emails, across personas and departments. A 2026 review summarizing their published benchmarks claims an average **2–3x reply‑rate uplift** for teams that consistently follow Lavender’s personalization and structure recommendations, albeit with caveats about self‑selection bias. These gains are not tied to LinkedIn specifically; they come from relevance and clarity, regardless of whether the personalization is grounded in a job posting, a news event, or a LinkedIn post.

**Signal‑based prospecting and job postings.** LinkedIn’s own 2025 thought‑leadership on "signal‑based prospecting" emphasizes **job postings, funding rounds, PR announcements, and first‑party behavior** (for example, pricing‑page visits) as high‑value signals, with job postings singled out as particularly rich indicators of strategic direction, tech stack, and organizational structure. Practitioner guides highlight that job listings show "what initiatives they are investing in, what tech stack they use, how they talk about the problems, and what the org/reporting structure looks like", making them ideal hooks for personalized outreach.

**AI personalization and "real signal" vs. generic slop.** A 2026 analysis of AI personalization in outbound outreach argues that AI works when grounded in "real signal"—the prospect’s actual profile and recent activity—and fails when it produces generic boilerplate. It cites a Belkins 2025 LinkedIn outreach study over **20 million LinkedIn attempts**, where personalized first messages achieved a **9.36% reply rate** versus **5.44%** for no message and **4.19% vs. 2.60%** for AI‑assisted vs. non‑AI first messages, but also notes that on email, AI‑generated cold emails replied slightly worse than human ones (4.1% vs. 5.2%) and drew more spam flags. Again, the common thread is signal quality, not channel or source.

**Person‑level LinkedIn research in practice.** Tools like Lavender, Clay, and Unify often combine LinkedIn data with company‑level signals (website content, news, CRM info) but treat **job postings and company events as the primary personalization surface**, with LinkedIn used mainly for job title, seniority, and occasional post‑based hooks. A 2026 roundup of personalization tools notes that "researched‑context tools" that let AI agents read a prospect’s website, news, and CRM to write personalized lines tend to outperform token‑only tools, but it does not isolate LinkedIn as uniquely valuable; LinkedIn is just one of several context sources.

### 2.2 Your own data point: job postings outperform LinkedIn

Your earlier experiment found that in 10 real prospects, all 8 usable drafts hooked on an **ATS job posting** and none on anything the prospect had personally said or published on LinkedIn or elsewhere. While the sample is small, this aligns closely with the broader industry narrative: job postings and other company‑level events are high‑signal, high‑relevance, and usually easier to tie directly to your product’s value (automating manual, reconciliation‑heavy processes) than a prospect’s personal content.

For ops, finance, RevOps, and supply‑chain personas at 50–500 employee, high‑transaction firms, job postings about new finance/ops tooling, ERP migrations, or payments/reconciliation roles are especially strong signals that the organization is actively wrestling with processes your product addresses.

### 2.3 What top outreach teams and tools actually use in 2026

While vendor content is inherently self‑serving, there is a consistent pattern across 2025–2026 outreach case studies and tool positioning:

- **Signal‑driven tools and playbooks** emphasize **company triggers** (funding, hiring, product launches, stack changes) as the primary segmentation and personalization inputs.
- LinkedIn is used mainly for **fit and routing signals** (job title, seniority, function) and for additional "social proof" (for example, referencing a recent LinkedIn post), but rarely as the first or only signal.
- Case studies showing 2–3x reply‑rate lifts from AI personalization typically rely on **stacked signals** combining job postings, web content, and CRM history, not just person‑level social content.

In other words, better‑regarded teams treat LinkedIn person data as **supporting context**, not the center of their personalization strategy.

### 2.4 The opposite case: what LinkedIn person‑level data can add

There are still several ways in which person‑level LinkedIn data can add real value beyond ATS + news + company blog:

- **Role‑specific framing.** LinkedIn confirms the exact title, seniority, and sometimes responsibilities (from the "About" section), allowing sharper framing for a VP Operations vs. a Director of Finance.
- **Career trajectory and prior stack.** Work history shows if the prospect has implemented similar tools before, moved between industries, or recently joined the company—signals that can shift call‑to‑action and risk appetite.
- **Recent social activity.** Likes, comments, and posts can reveal current initiatives or pain points not yet reflected in job postings or press releases, especially in younger, more social‑native companies.
- **Mutual connections and social proof.** For some plays, referencing a shared connection or prior employer can warm the outreach.

However, each of these benefits can usually **refine** a hook already grounded in a job posting or company event, rather than replace it. For example, "You’re hiring a Payments Ops Lead to rein in reconciliation between PSPs and your ledger" is a job‑posting‑derived hook; LinkedIn might let you adapt the wording to the prospect’s seniority and previous projects, but the core signal remains the job.

### 2.5 Part 2 recommendation

For this MVP, **LinkedIn should not be the primary signal layer** for personalization. Instead:

- Treat ATS job postings, funding news, and product launches as the **main source of hooks**.
- Use LinkedIn only to **confirm fit and refine tone** where helpful (for example, checking whether the prospect is actually the owner of the job posting’s problem).
- Build the orchestration and verification logic around structured sources that are open, intentionally syndication‑friendly, and less legally fraught.

This aligns with your own early evidence and with contemporary signal‑based prospecting advice.

***

## Part 3 — Free and low‑cost alternative sources

### 3.1 ATS job‑board APIs (Greenhouse, Lever, Ashby, others)

The major SaaS ATS platforms continue to expose **public, unauthenticated JSON job‑board APIs** intended for careers‑site and job‑board integrations.

| ATS | Public jobs endpoint (2026) | Auth | Scope | Notes |
| --- | --- | --- | --- | --- |
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs` | None | Published jobs for one customer | JSON, free, unofficial rate limits; widely used for custom careers pages. |
| Lever | `https://api.lever.co/v0/postings/{company}?mode=json` | None | Published postings for one customer | JSON array of jobs; public, no key required. |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/{JOB_BOARD_NAME}` | None | Published job postings for one customer | Unaudited job postings API, supports optional `includeCompensation=true`; used for careers pages; documentation updated in 2026. |
| SmartRecruiters | `https://api.smartrecruiters.com/v1/companies/{companyId}/postings` | None | Published postings | Public JSON feed used for job boards; no auth for reads (documented in 2026 comparisons). *Pre‑2025 docs; verify live.* |
| Recruitee | `https://api.recruitee.com/c/{company}/careers/offers` | None | Published postings | Public, read‑only JSON; used for embedding job boards. |

Greenhouse’s own Job Board API docs confirm that the jobs endpoint is **public, read‑only, and free**, returning an array of published jobs (id, title, updated_at, location, departments, offices, apply URL) with no API key and an unpublished but practical rate limit; applications submission requires separate auth but is irrelevant here. Ashby’s developer documentation and 2026 blog posts explicitly describe its job‑board endpoint as **unauthenticated** and used for public careers pages, with compensation included when requested.

A 2026 comparison across Workday, Greenhouse, Lever, Ashby, SmartRecruiters, and Recruitee confirms that all expose public, no‑auth JSON job feeds for their customers, and that these feeds are used by design to syndicate job postings to job boards and partner sites.

This makes ATS job feeds the perfect backbone for your MVP:

- Free and unauthenticated; no keys, no contracts.
- Clearly intended for redistribution; no scraping or ToS gymnastics.
- High‑signal data (role, location, department, description, sometimes compensation and tech stack).

### 3.2 News and filings: Google News RSS and EDGAR

**Google News RSS.** Google does **not** offer an official Google News API and has not since 2011, but as of July 2026, it still serves free, unauthenticated RSS feeds for topics, locations, and arbitrary search queries under the base URL `https://news.google.com/rss`. Guides updated in mid‑2026 show that you can construct feeds like:

- Top stories: `https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en`
- Topics: `.../headlines/section/topic/TECHNOLOGY?hl=...`
- Keyword/company search: `https://news.google.com/rss/search?q=Company+Name&hl=en-US&gl=US&ceid=US:en`

These feeds return thin metadata (title, link, publish date, source name) and are rate‑limited aggressively, but remain free and keyless for lightweight polling. There is no sign that they will be withdrawn imminently, and changes in 2025 around Publisher Center RSS submissions affected publisher onboarding, not consumer‑facing RSS feeds.

**SEC EDGAR.** The U.S. SEC’s EDGAR system remains the canonical source of public company filings; its APIs and bulk data endpoints provide programmatic access to 10‑K, 10‑Q, 8‑K, and other filings. For your use case—mid‑market companies at 50–500 employees, many of which may be private—EDGAR is most relevant when you are prospecting U.S. public companies or larger, later‑stage firms, but it is still the most reliable way to pull authoritative financial and event disclosures where applicable.

Given your target segment, EDGAR is a **secondary** signal layer: valuable when present, but not something to depend on for every prospect.

### 3.3 Person‑level web search: Exa, Firecrawl, Brave Search, Tavily

**Exa.** Exa is a web search and content‑extraction API designed for AI agents, offering semantic search and rich page contents via a pay‑as‑you‑go model. In mid‑2026, standard search is priced at **7 USD per 1,000 requests** (with contents for the first 10 results included), deep search at **12–15 USD per 1,000**, and the Answer endpoint at **5 USD per 1,000**, with no monthly minimum and a sizeable free tier (20 USD signup credits plus roughly 10 USD in credits per month, equating to tens of thousands of free searches per year for light usage). This makes Exa a strong candidate for your `"Person Name" "Company Name"` pattern at 5–20 runs per day; cost will be effectively zero.

Exa is specifically designed to be used by AI agents and supports up to 10 results per request in its base price; additional results or AI summaries are billed at modest per‑1,000 rates. For this MVP, one or two top results per person/company query are likely sufficient.

**Other search APIs (Brave, Tavily, etc.).** 2026 pricing comparisons across web search APIs show that Brave Search API and Tavily offer competitive per‑1,000 query rates, often with free tiers aimed at small projects. However, many of these APIs are oriented around Google‑style keyword SERPs rather than semantic, agent‑friendly responses, and some have more restrictive terms regarding caching and storing results. Given your comfort with AI tooling, Exa’s semantics‑first design and generous free tier make it a better default.

**Firecrawl.** Firecrawl is a headless browser/scraper API that can render and extract structured content from arbitrary web pages; it is useful for grabbing full page contents or handling JS‑heavy sites, but is likely overkill for an MVP that can rely on Exa’s built‑in content extraction for most person/company pages. Firecrawl becomes attractive if you later want fine‑grained control over page traversal (for example, scraping a whole documentation site), not for simple prospect research.

### 3.4 Additional low‑volume sources

- **YouTube transcripts and podcasts.** Many YouTube videos expose machine‑generated transcripts via the YouTube Data API or embeddable transcript features, and podcasts surface episode descriptions and sometimes transcripts via RSS. For 5–20 prospects per day, selectively querying YouTube and podcast search for `"Person Name" "Company Name"` and pulling transcripts only when hits exist is reasonable, but the yield will be low for ops/finance personas compared to founders or marketers.
- **GitHub.** GitHub profiles and activity feeds are valuable for technical personas (developers, data engineers), but less so for the finance/ops buyers you’re targeting; it can be deferred.
- **Company blogs and documentation.** These are high‑signal sources for product launches, process changes, and internal language; they can usually be reached via Exa search or direct HTTP requests without specialized APIs.

### 3.5 Part 3 recommendation

For a low‑volume MVP with a legal‑risk‑averse posture, the recommended source mix is:

- **Primary:** ATS job‑board APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee), Google News RSS for company/funding news, and company websites/blogs fetched via Exa.
- **Secondary:** Exa search for person‑level lookups, selectively pulling top pages mentioning both the person and company.
- **Tertiary (optional):** LinkedIn profile scraping via a provider‑side API for occasional fit checks; YouTube/podcast/GitHub only when obviously relevant to the persona.

This stack keeps you within intentionally open data surfaces, dramatically reduces ToS and GDPR exposure versus LinkedIn‑centric designs, and stays well within free or very low‑cost tiers at 5–20 runs per day.

***

## Part 4 — Orchestration: pure Python vs. n8n

### 4.1 Workload characteristics

Your intended pipeline is:

> intake → parallel retrieval across sources → normalize → rank → select hook → draft via LLM → verify draft against evidence → on hallucination, retry once and flag the retry → deliver as a Gmail draft.

The crucial properties are:

- **Reasoning loops and branching.** The verification step must compare the draft against evidence, detect hallucinations, trigger a redraft, and annotate that a retry occurred.
- **Stateful execution.** Each run must carry structured state: sources consulted, selected hook, LLM system and user prompts, model responses, verification results.
- **Testability.** You want automated tests and a "swap test" that replaces the prospect but replays the rest of the pipeline to ensure the draft no longer makes sense.

These properties are better served by a general programming language and test framework than by a visual integration tool.

### 4.2 Where n8n fits and where it does not

n8n is a general‑purpose workflow automation platform: it excels at orchestrating API calls, CRUD operations, and simple conditionals across services with a visual designer and built‑in connectors. It can certainly call HTTP endpoints for ATS feeds, Exa, and your LLM provider, and can conditionally branch on response fields.

However, as agent logic deepens, several limitations emerge:

- **Complex reasoning and verification loops become unwieldy** when modeled as large visual graphs, especially when you need to maintain invariants like "drafts must be verified against a consolidated evidence set".
- **Deterministic replay is awkward.** While you can feed n8n workflows with fixed inputs, it is harder to treat them as pure functions over fixtures and run them under standard unit‑test frameworks with fine‑grained assertions.
- **Versioning and refactoring.** Refactoring complex logic in a visual graph is slower and more error‑prone than in code, especially when you want to split logic into reusable, typed functions.

For straight‑line integration plumbing (for example, "run this Python script whenever a new row appears in Airtable and then post a Slack message"), n8n is ideal. For agent‑style reasoning with verification loops, it is less so.

### 4.3 Testability and deterministic replay in Python

In Python, especially with `asyncio`, you can structure the agent as a set of **pure functions over typed data structures** plus thin side‑effect wrappers:

- Define `SourceConfig`, `EvidenceItem`, `Draft`, `VerificationResult` as Pydantic models or dataclasses.
- Implement `fetch_evidence(config, prospect) -> list[EvidenceItem]` and `draft_email(evidence, prospect) -> Draft` with explicit inputs and outputs.
- Implement `verify_draft(draft, evidence) -> VerificationResult` that returns structured findings (for example, list of unsupported claims, mismatched facts).

With this structure, you can write tests that:

- Load a fixture `EvidenceSet` from disk.
- Call `draft_email` and `verify_draft` with a fixed random seed and stubbed LLM, and assert on the resulting fields.
- Run the "swap test" by substituting a different prospect object and asserting that the previously generated draft fails verification or fails a semantic check.

This approach plays well with standard Python testing tools (`pytest`, snapshot testing for drafts) and makes deterministic replay straightforward – something that would be difficult to achieve in n8n without substantial custom scripting.

### 4.4 Hybrid pattern: n8n for triggers, Python for reasoning

A hybrid architecture—n8n for triggering and routing, Python for reasoning—can make sense at higher volumes or when you need non‑Python triggers (for example, a Notion database entry or a webhook from a CRM). In your case, with **5–20 runs per day**, the added operational surface may not be worth it:

- A simple cron job or a command‑line trigger can launch a Python process that reads a prospect from a queue (file, database, or CLI arg) and executes the pipeline.
- Gmail draft creation is just another HTTP call from Python; you do not need n8n to mediate it.

The hybrid pattern is attractive if you foresee complex multi‑channel orchestrations, multi‑user access, or non‑technical stakeholders editing workflows visually. For a solo developer, it is extra moving parts.

### 4.5 Framework vs. "just asyncio" in Python

Modern agent frameworks like LangGraph, OpenAI Agents SDK, and PydanticAI provide structured ways to define tool‑calling graphs, state machines, and type‑checked LLM interactions. They shine when:

- You have many tools and complex multi‑step agent flows.
- You want built‑in observability, replays, and guardrails.

At your current scale, a "plain" approach—`asyncio` + typed models + a thin LLM client—is likely enough:

- You can represent the pipeline as a small, explicit state machine with a handful of states (FetchEvidence, RankSignals, Draft, Verify, Redraft, Finalize).
- Verification logic can live in standard Python functions and be tested like any other code.
- If the pipeline grows more complex, you can migrate into a framework later without throwing away your core business logic.

### 4.6 Part 4 recommendation

For this MVP, use **pure Python with `asyncio` and typed models**, no n8n and no heavy agent framework.

- Keep each step as a pure-ish function with clear inputs/outputs to maximize testability and deterministic replay.
- Use a simple runner script or CLI to kick off runs; add a minimal job queue later if needed.
- Consider adopting a lightweight typing‑aware helper (for example, Pydantic for models) but hold off on LangGraph/OpenAI Agents until the pipeline’s complexity justifies them.

***

## Part 5 — Gmail draft creation (2026)

### 5.1 Gmail API mechanics for drafts

Google’s official Gmail API documentation describes creating drafts via the `users.drafts.create` method: you build a MIME message conforming to RFC 2822, base64URL‑encode it, and send it in a JSON payload under `message.raw` to `https://gmail.googleapis.com/gmail/v1/users/me/drafts`. The API returns a `Draft` resource with an `id` and nested `message` metadata; drafts can later be sent via `users.drafts.send` or inspected via `users.drafts.get`.

### 5.2 OAuth2 scopes and "drafts‑only" limitations

Google’s consolidated OAuth scope list shows the relevant Gmail API scopes:

- `https://www.googleapis.com/auth/gmail.compose` – "Manage drafts and send emails".
- `https://www.googleapis.com/auth/gmail.modify` – Read and modify mail.
- `https://mail.google.com/` – Full Gmail access (read, compose, send, permanently delete).

The `users.drafts.create` method allows any of these three scopes; there is no narrower "drafts‑only" scope that would let an app create drafts but not send them. A 2026 developer analysis explicitly confirms that the set of scopes permitting `users.drafts.create` and `users.drafts.send` is identical, and that `gmail.compose` bundles both draft management and sending; any app that can create drafts under this scope can also send them if it calls the right methods.

For a safety‑conscious internal tool, this means you must enforce "never send" at the **application layer**: simply never invoke `users.messages.send` or `users.drafts.send`, and avoid granting broader scopes like `mail.google.com` unless absolutely necessary.

### 5.3 OAuth app verification and solo‑developer setup

Google’s general OAuth documentation distinguishes between limited‑use internal apps and external production apps:

- Apps requesting sensitive Gmail scopes (including `gmail.compose`) must undergo verification if they are used by external users, but **single‑user internal scripts can often operate with unverified credentials**, as long as the developer accepts the "unverified app" warnings during consent.
- For headless or server‑side flows, service accounts with domain‑wide delegation can be used in Google Workspace domains, but for a personal Gmail account, the standard "installed app" flow (with a local `token.json`) is simplest.

The Gmail Python quickstart demonstrates how to perform the installed‑app OAuth flow, store a refresh token in `token.json`, and build a Gmail API client; you would adapt this by changing the scopes array to `['https://www.googleapis.com/auth/gmail.compose']` and replacing the list‑labels sample with a `drafts.create` call similar to Google’s own code samples.

Realistic setup time for a solo developer is on the order of **1–3 hours**: create a Google Cloud project, enable the Gmail API, create OAuth credentials, download `credentials.json`, run the Python quickstart, and extend it to create drafts.

### 5.4 Lower‑friction paths

Alternatives to the full Gmail API include:

- **`mailto:` links and deep links into Gmail compose.** These can prefill subject and body but do not create drafts and are easier to mishandle (for example, sending from the wrong account); they also require user interaction and are not suitable for a programmatic pipeline.
- **Browser automation (for example, Playwright) to write drafts in the Gmail UI.** This is brittle and violates Gmail’s terms of service in some cases; the official API is more robust and transparent.

Given your goals and technical comfort, the official Gmail API is the cleanest option.

### 5.5 Part 5 recommendation

Implement Gmail draft creation with:

- OAuth2 installed‑app flow using `gmail.compose` scope, storing credentials locally (`token.json`), and never requesting broader scopes like `mail.google.com`.
- A Python helper function that constructs MIME messages, base64URL‑encodes them, and calls `users.drafts.create` with `userId='me'`.
- Application‑level guarantees (code review, tests) that no path calls `users.messages.send` or `users.drafts.send`.

This keeps the system within supported, well‑documented Google APIs and avoids brittle automation hacks.

***

## Final stack recommendation

### 6.1 Single recommended stack for this MVP

**Data sources.**

- **ATS job boards:** Greenhouse, Lever, Ashby, SmartRecruiters, and Recruitee public JSON endpoints as the primary source of high‑signal hooks ("you are hiring X to do Y"), which are free, unauthenticated, and clearly intended for syndication.
- **News and company events:** Google News RSS feeds for company and topic queries, plus direct fetches of company blogs and press pages via Exa search/content.
- **Person‑level web search:** Exa search for `"Person Name" "Company Name"` as needed, retrieving key pages (personal profiles, interviews, articles) for additional context.
- **Optional LinkedIn enrichment:** A low‑volume, provider‑managed LinkedIn scraper (for example, a maintained Apify actor or Bright Data Web Scraper API route) used only to confirm title/seniority or pull a single profile snapshot; no session‑cookie reuse, no automated LinkedIn actions.

**Orchestration and logic.**

- **Language:** Pure Python with `asyncio`.
- **Structure:** Typed models (dataclasses or Pydantic) for prospects, evidence, drafts, and verification results; a small explicit state machine for the pipeline.
- **Testing:** `pytest` tests that:
  - Run the full pipeline against fixture evidence sets.
  - Perform a swap test (change prospect, keep evidence) and assert that the draft fails verification.
  - Snapshot test drafts for stability.

**Gmail integration.**

- Official Gmail API with `gmail.compose` scope via installed‑app OAuth.
- `users.drafts.create` to insert drafts for the authenticated sender; no send endpoints used.

This stack:

- Delivers strong, job‑posting‑driven personalization aligned with your early results and industry data.
- Minimizes legal and platform risk by leaning on intentionally open, syndication‑friendly APIs and avoiding deep LinkedIn dependency.
- Stays well within free or very low‑cost tiers at 5–20 runs per day.
- Keeps orchestration under your control in a testable, deterministic codebase.
