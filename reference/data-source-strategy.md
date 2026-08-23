# Data source strategy for live signal discovery (PS-3)

Research pass requested by the project owner after pushback on the assumption that Claude's native
`web_search` tool alone is sufficient for T3 (signal discovery). Question: for each signal tier the
product needs (authored content, business events, firmographic data), what real, currently-available,
primary-sourced options exist, what do they cost today, what's the ToS/legal exposure, and are they
feasible inside a Vercel serverless function. Researched 2026-08-21.

**Bottom line up front:** the current plan (`web_search` alone) covers business-event and general-news
signal reasonably well, and firmographic signal partially, but it does **not** meaningfully cover
LinkedIn or X/Twitter authored content — the two source types the brief's own hook-ranking rule treats
as most valuable. LinkedIn in particular is close to unreachable programmatically without either paying
for enterprise-tier partner access or taking on real legal/ToS exposure. Recommended stack is at the
bottom.

---

## 1. Authored content

### LinkedIn

**Official API.** LinkedIn closed public API access in 2015; all access now requires becoming an
approved LinkedIn Partner through the LinkedIn Developer Portal. There is no self-serve tier that
returns a third party's public posts. The only self-serve products are Sign In with LinkedIn (OpenID
Connect) and Share on LinkedIn (posting *as* the authenticated user) — neither retrieves someone else's
authored content. Reading another member's posts/activity requires Marketing Developer Platform or
similar partner access, which LinkedIn does not publish pricing for; the reported real-world range is
**$10,000–50,000+/year**, with a **4–8 week fast path / 3–4 month typical** approval timeline, and it's
"generally reserved for enterprise partners." Sales Navigator API onboarding was paused for new
partners entirely in 2026.
[LinkedIn API in 2026: Access, Endpoints, Limits & Alternatives](https://connectsafely.ai/articles/linkedin-api-complete-guide-2026) ·
[LinkedIn API Access in 2026: Tiers, Approval & Alternatives](https://www.getphyllo.com/post/linkedin-api-access-in-2026-partner-program-approval-timeline-alternatives) ·
[Getting Access to LinkedIn APIs — Microsoft Learn](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access)

**Verdict: not viable for this project.** Even the fast path (4–8 weeks) is longer than any reasonable
demo runway, the price is far above a case-study budget, and approval is discretionary/enterprise-only.

**ToS on scraping — primary source.** Fetched LinkedIn's live User Agreement directly
(https://www.linkedin.com/legal/user-agreement), Section 8.2 "Don'ts":
- Item 2: *"Develop, support or use software, devices, scripts, robots or any other means or processes
  (such as crawlers, browser plugins and add-ons or any other technology) to scrape or copy the
  Services, including profiles and other data from the Services"*
- Item 13: *"Use bots or other unauthorized automated methods to access the Services, add or download
  contacts, send or redirect messages, create, comment on, like, share, or re-share posts, or otherwise
  drive inauthentic engagement"*

This is an unambiguous, currently-live contractual prohibition, not a stale or disputed clause.

**Litigation history — what it actually means today.** The famous case for "scraping public LinkedIn
data is fine" is *hiQ Labs v. LinkedIn*. That case is over, and it ended badly for the scraper: after
years of litigation the Ninth Circuit's earlier CFAA-favorable ruling was followed by a November 2022
district-court summary judgment holding that **LinkedIn's User Agreement's anti-scraping clause is
enforceable as a breach-of-contract claim**, and the case closed with a **stipulated $500,000 judgment
against hiQ**, a finding of liability for trespass to chattels and misappropriation under California
common law, and a permanent injunction forcing hiQ to stop scraping and delete all scraped data/derived
code. hiQ's parent company went out of business shortly after.
[Morgan Lewis: LinkedIn v. hiQ, landmark suit provides guidance](https://www.morganlewis.com/blogs/sourcingatmorganlewis/2022/12/linkedin-v-hiq-landmark-data-scraping-suit-provides-guidance-to-data-scrapers-and-web-operators) ·
[Proskauer: hiQ and LinkedIn reach proposed settlement](https://www.proskauer.com/blog/hiq-and-linkedin-reach-proposed-settlement-in-landmark-scraping-case)

**More current and more relevant: LinkedIn v. Proxycurl/Nubela (2025).** Proxycurl was, until mid-2025,
the most widely used third-party "LinkedIn data API" — exactly the kind of product this project might
otherwise have reached for. LinkedIn (and Microsoft) sued Nubela Pte. Ltd. / Proxycurl LLC in the
Northern District of California on **January 24, 2025** (Case No. 3:25-cv-00828), alleging the company
created hundreds of thousands of fake LinkedIn accounts to scrape millions of profiles (including
non-public data) and resold that data via API — breach of contract, fraud, and trademark claims. The
case settled and **Proxycurl shut down entirely on July 4, 2025**, with a public "goodbye" post from the
founder and customer data slated for deletion.
[Law.com: LinkedIn suit says millions of profiles scraped](https://www.law.com/therecorder/2025/01/27/linkedin-suit-says-millions-of-profiles-scraped-by-singapore-firms-fake-accounts/) ·
[Nubela: "Proxycurl Shuts Down. Thank you."](https://nubela.co/blog/goodbye-proxycurl/) ·
[Nubela: "Is Scraping LinkedIn Legal in 2026? (I Was Sued by LinkedIn)"](https://nubela.co/blog/is-scraping-linkedin-legal-in-2026/)

This is the single most important, most current data point: it is a 2025 enforcement action, against a
funded, established commercial vendor, that resulted in total shutdown. Any third-party "LinkedIn data
API" that is not an official LinkedIn partner should be assumed to be one lawsuit away from
disappearing — which also makes it a bad choice for a *product* dependency even ignoring the ethics.

**Account-automation tools (PhantomBuster, similar browser-automation "cookie" tools).** These log in as
a real LinkedIn account and drive a browser. LinkedIn's terms (quoted above) explicitly ban this. In
practice the consequence is account-level (restriction/ban of the LinkedIn account used), not
necessarily litigation against the tool vendor, but LinkedIn's 2026 bot-detection is reported as
materially better (keystroke-timing analysis, IP/behavior fingerprinting), and case reports describe
bans within two weeks of aggressive use and multi-week suspensions even from "conservative" use.
[PhantomBuster's own blog: "Navigating LinkedIn's Limits in 2026"](https://phantombuster.com/blog/linkedin-automation/linkedin-limits-workaround/) ·
[stormy.ai: Avoiding LinkedIn Bans in 2026](https://stormy.ai/blog/linkedin-automation-safety-2026-phantombuster-bereach-guide)

**Feasibility in Vercel serverless even if you accepted the risk:** these tools require a persistent,
authenticated, cookie-based browser session tied to a specific LinkedIn account and IP reputation over
time. That's fundamentally a stateful, long-lived-session pattern — the opposite of a stateless
serverless invocation. You'd be calling out to a third-party session-hosting service (which is really
just re-adding the ToS risk one layer removed) rather than running it in-function.

**What's actually left: indexed/public surfacing via general search.** LinkedIn's own `robots.txt`
(https://www.linkedin.com/robots.txt) disallows Googlebot from crawling `/profile/` and related profile
paths, while it *allows* LinkedIn's own bot. In practice this means **LinkedIn profile pages are largely
not indexed by Google/Bing/Brave**, so a general web-search tool (including Anthropic's `web_search`)
essentially cannot retrieve profile content. Individual **posts** are a partial exception: LinkedIn posts
that get enough engagement can be indexed by Google within days and surfaced in results — but this is
inconsistent, engagement-gated, and not a reliable retrieval path for an arbitrary, possibly low-traffic
individual on demo day.
[LinkedIn robots.txt](https://www.linkedin.com/robots.txt) ·
[hyperclapper: bypassing LinkedIn Google-indexing limits](https://www.hyperclapper.com/blog-posts/remove-linkedin-from-google-search-bypass-limits)

**Practical conclusion for LinkedIn:** there is no free-tier, low-risk, fast-to-set-up option that
reliably retrieves a named person's LinkedIn posts. The only legitimate options are (a) enterprise
partner access — too slow, too expensive, discretionary approval, ruled out for this project; or (b)
accept that LinkedIn coverage will be thin/best-effort via general web search and design the product to
degrade gracefully (this is directly compatible with the brief's own "needs human judgment" gate — a
missing/weak LinkedIn signal is exactly the kind of gap that gate exists to handle honestly).

### Twitter/X

**Official API — current pricing (fetched directly from `docs.x.com`, Feb 2026 pricing model).** X
replaced its subscription tiers with pay-per-use as the default for new developers:
- Reads: **$0.005/post**, $0.010/user lookup, $0.010/following-followers, $0.005/list, $0.001/like
- Writes: **$0.015/post created**, **$0.20/post containing a link**, $0.015/DM
- "Owned reads" (your own account's data) are cheaper: **$0.001/resource**
- No published free tier and no minimum spend stated for pay-per-use; you prepay credits
[X API pricing docs](https://docs.x.com/x-api/getting-started/pricing) (fetched directly)

Legacy subscription tiers (**Basic $200/mo, Pro $5,000/mo**) still exist for pre-existing subscribers
only, and X has been auto-migrating remaining legacy subscribers to pay-per-use since June 2026.
**Enterprise / full-archive search runs ~$42,000+/month.** New developers cannot sign up for Basic or
Pro today — pay-per-use or Enterprise are the only options.
[Postproxy: X API Pricing in 2026](https://postproxy.dev/blog/x-api-pricing-2026/) ·
[xpoz.ai: Twitter/X API Pricing 2026 ($0–$42K compared)](https://www.xpoz.ai/blog/guides/understanding-twitter-api-pricing-tiers-and-alternatives/)

For a small case-study project, reads at $0.005–0.01/resource are cheap in absolute terms for a single
lookup (a handful of cents per prospect), and unlike LinkedIn, **this is a real, self-serve, immediately
available API** — no partner approval, no waitlist. That's a meaningful asymmetry versus LinkedIn.

**ToS.** X's Developer Agreement/Policy bans scraping or crawling without prior written consent (a
tightening from an earlier robots.txt-based carve-out), separately from the paid API. The official
developer policy is at https://docs.x.com/developer-terms/policy. Automated non-API access (scraping) is
out of scope for a legitimate build here — use the paid API, not scraping.

**Litigation context (X Corp v. Bright Data).** Worth knowing but doesn't change the recommendation: a
federal court (N.D. Cal., May 2024) dismissed X's ToS-breach claims against scraper/proxy vendor Bright
Data on copyright-preemption grounds, and refused to let X revive misappropriation claims, though it did
let X pursue a narrower "server impairment" theory in late 2024. Net effect: some legal uncertainty
around *X's* ability to enforce its ToS against third-party scrapers via contract law specifically, but
this is irrelevant to this project since the recommended path is the paid official API, not scraping.
[MoFo: Federal court holds X's claims preempted](https://www.mofo.com/resources/insights/240604-california-federal-court-holds-x-s-claims) ·
[Natural Law Review: Judge dismisses X's case against Bright Data](https://natlawreview.com/article/x-corp-loses-battle-over-public-data-access)

**Feasibility in Vercel serverless.** Fully stateless REST calls with a bearer token — no persistent
session needed. Straightforward to call from a serverless function with normal HTTP request latency
(hundreds of ms). No setup lead time beyond creating a developer account and adding a payment method,
which can be done same-day.

### General web / blogs / podcasts / conference talks

This is squarely what Anthropic's `web_search` is built for — see Section 3 (baseline evaluation) below.
Supplementary options if coverage/cost becomes an issue:
- **Exa.ai** — neural/semantic search API built for LLM agents. **$7/1,000 requests** (up to 10 results),
  $12/1,000 for Deep Search, $1/1,000 for each result past 10. Free: **$20 signup credit + $10/month
  recurring** (not one-time), enough for roughly 1,400 basic searches/month indefinitely on the free
  allowance. [Exa pricing](https://exa.ai/pricing)
- **Tavily** — search + extraction API for RAG/agents. Free: **1,000 credits/month**, no card required.
  Paid starts at **$30/mo for 4,000 credits** ($0.0075–0.005/credit as volume rises).
  [Tavily pricing coverage](https://coldiq.com/blog/tavily-pricing)
- **NewsAPI.org** — broad source coverage (80,000+ sources) but the free "Developer" tier is
  **explicitly prohibited from production/deployed use** (localhost-only, 25 req/day). Cheapest
  production-legal tier is **$449/mo** (Business). Not worth it for this project's budget.
  [apitube.io: News API pricing breakdown 2026](https://apitube.io/en-at/blog/post/news-api-pricing-breakdown-2026)
- **GDELT Project** — free, no API key, indexes global news in 100+ languages, updated every 15 minutes,
  7 years of full-text search history. Good free fallback specifically for **business-event/press**
  coverage (funding, executive moves, etc.) rather than authored personal content.
  [GDELT Project](https://www.gdeltproject.org/) · [GDELT 2.0 docs](https://docs.gdeltcloud.com/)

---

## 2. Business events (funding, hiring, launches, press)

This is the tier general web search covers best, and it's also the tier the brief explicitly ranks
*lowest* priority (supporting line only, never the headline) — so partial coverage here is lower-stakes
than partial LinkedIn coverage.

- **Anthropic `web_search`** (see Section 3) will surface funding-round press releases, launch
  announcements, and news coverage reasonably well since these are exactly the kind of content that gets
  indexed and picked up by mainstream search.
- **GDELT** (above) as a free, no-signup supplement/fallback specifically for news-event detection.
- **Crunchbase API** for funding-round specificity/structure (see firmographic section — same product
  covers both funding events and firmographics).

---

## 3. Firmographic data (company size, industry, funding stage, tech stack)

| Provider | What it covers | Current pricing | Notes |
|---|---|---|---|
| **Crunchbase API/Data Licensing** | Funding rounds, investor data, company profiles | Free tier **eliminated in 2025**. Public "Basic" API now **$49/mo**, full "Pro" **$99/mo**. Programmatic Data Licensing access is quote-only, Enterprise-gated. | [Crunchbase API review 2026](https://dev.to/agenthustler/crunchbase-api-in-2026-free-tier-gone-what-startup-data-hunters-do-now-1177) |
| **People Data Labs (PDL)** | Company enrichment: headcount, funding, industry, workforce growth/churn | Free: **$0/mo, 100 person/company lookups per month**. Pro: **$98/mo**, 1,000 company lookups. Pay-as-you-go: **$0.10/credit for company enrichment** (vs. $0.28 for person). | [PDL pricing](https://nubela.co/blog/people-data-labs-pricing/) |
| **Apollo.io** | Firmographics + contact enrichment, bundled with outbound tooling | Free tier exists (unlimited email credits, ~75 contact reveals/month via annual credit pool) but **API access is limited on Free**; full API unlocks at **Organization tier, $119/user/month**, 3-user minimum. | [Apollo pricing 2026](https://hackingdemand.com/blog/apollo-io-pricing-2026) |
| **Clearbit (now HubSpot Breeze Intelligence)** | Company enrichment | Standalone Clearbit API is sunset. Breeze Intelligence: **~$45/mo for 100 credits**, requires an underlying paid HubSpot subscription (**+$20/mo min**), realistic floor **~$65/mo**. Not usable as a lightweight standalone add-on anymore. | [Breeze Intelligence pricing breakdown](https://marketbetter.ai/blog/clearbit-pricing-breakdown-2026/) |
| **BuiltWith** (tech stack specifically) | What technologies a company's website runs | Free: **single-site lookup only**, no bulk/API. API access requires **Pro tier, $200+/mo**; full API access **$295–495/mo**. Credit costs per call are undocumented. | [BuiltWith pricing 2026](https://derrick-app.com/tools/builtwith-pricing) |

**Assessment:** People Data Labs is the standout for this project — a genuinely usable free tier (100
company lookups/month, no card required per typical PDL free-tier setup) that covers headcount, industry,
and funding stage, which is exactly the firmographic slice this product needs (lowest-priority tier per
the hook-ranking rule, so "good enough" coverage is fine here). It's a stateless REST API, trivially
callable from a serverless function.

For tech-stack specifically: BuiltWith's free single-lookup tool (via web form, no API) could be used
manually during fixture-building, but there's no free programmatic path — and tech stack is explicitly
the lowest-value firmographic detail per the brief ("never a standalone hook, context only"), so it's
reasonable to simply not build automated tech-stack lookup and rely on whatever the general search /
company-enrichment call surfaces incidentally.

---

## Baseline evaluation: Anthropic's native `web_search` tool

Checked directly against Anthropic's own docs (fetched from `platform.claude.com`, current as of
2026-08-21) rather than a summary:

**How it works.** Server-side tool on the Messages API. Claude decides when to search, generates
queries, gets results, can re-search, and returns a response with inline citations
(`web_search_result_location`, `cited_text` up to 150 chars). Supports `max_uses` (cap searches per
request), `allowed_domains`/`blocked_domains` (mutually exclusive), and `user_location` for
localization. Three tool versions exist as of this writing (`web_search_20250305` basic,
`web_search_20260209` adds "dynamic filtering" — Claude writes code to filter results before they hit
context, reducing token cost, `web_search_20260318` adds response-inclusion control). Available on the
direct Claude API, Claude Platform on AWS, and Microsoft Foundry (Hosted-on-Anthropic only); **not
available on Amazon Bedrock**.
[Web search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)

**Pricing (verbatim from docs):** *"Web search is available on the Claude API for $10 per 1,000
searches, plus standard token costs for search-generated content."* Failed searches (errors) aren't
billed. Each search call — regardless of number of results returned — counts as one use.
[Same source as above]

**Search backend.** Not stated in Anthropic's own docs, but independently reported (via citation-overlap
analysis) to be **Brave Search**. [Simon Willison / Cobus Greyling analysis of citation overlap](https://cobusgreyling.substack.com/p/anthropic-web-search-tool) — this
is secondary/inferred, not Anthropic-confirmed, flagged as such.

**Concrete coverage gaps for this product's needs:**

1. **LinkedIn — largest gap.** LinkedIn's `robots.txt` blocks Googlebot (and by extension most general
   search crawlers) from `/profile/` paths; profile content is not indexed. Individual **posts** are a
   partial exception (engagement-gated, inconsistent, days-long indexing lag) but there is no reliable
   way for `web_search` to retrieve "this named person's recent LinkedIn activity" on demand. Since the
   product's own hook-ranking rule puts LinkedIn-style authored content at the *top* of signal priority,
   this is the most consequential gap in the current plan, not a minor one.
2. **X/Twitter — likely thin.** X's terms restrict third-party scraping/crawling without consent, and a
   general web index will only surface tweets that happen to be embedded/quoted on other indexed pages
   (news articles, aggregator sites) rather than direct profile/timeline access. `web_search` was not
   built as an X client and has no privileged access to X's index.
3. **General web/news — the strongest fit.** Blog posts, press coverage, conference-talk writeups,
   podcast show notes, and funding announcements are exactly the kind of content that's normally
   well-indexed and where `web_search` should perform close to "as good as a human googling it."
4. **Firmographic — partial.** `web_search` can surface *some* firmographic facts opportunistically (a
   TechCrunch funding writeup mentioning employee count) but it's not a structured firmographic database
   — no guaranteed schema, no headcount time series, no reliable "give me size/industry/stage for this
   exact company" call.

**Rough fraction covered:** of the three signal tiers, `web_search` covers general-web authored content
and business-event/press signal well (tiers where it's the right tool), partially covers firmographic
signal (opportunistic, not structured), and does **not** meaningfully cover the two authored-content
sub-sources the hook-ranking rule prioritizes most (LinkedIn, X) — which is the core of the owner's
pushback and appears justified by primary-source evidence, not just intuition.

---

## Feasibility in Vercel serverless — summary across all options

| Option | Stateless? | Latency profile | Setup lead time |
|---|---|---|---|
| Anthropic `web_search` | Yes — server tool, called inline from your Messages API request | Adds a search round-trip inside the model call; typically sub-second to a few seconds per search, multiple searches can chain | None (already available if not admin-disabled) |
| X API (pay-per-use) | Yes — plain REST + bearer token | Normal HTTP latency (hundreds of ms) | Same-day: create dev account, add payment method |
| People Data Labs | Yes — plain REST | Normal HTTP latency | Same-day: free-tier signup |
| Exa / Tavily | Yes — plain REST | Normal HTTP latency | Same-day: free-tier signup, no card |
| GDELT | Yes — plain REST, no key | Normal HTTP latency | None |
| LinkedIn official partner API | N/A — not reachable in time | N/A | **4–8 weeks minimum, typically 3–4 months, discretionary approval** — rule out for this project |
| LinkedIn via account-automation (PhantomBuster-style) | **No** — requires a persistent authenticated browser session tied to one LinkedIn account/IP over time | Slow, session-dependent, and the session itself can't live inside a single serverless invocation | Immediate signup but operationally fragile from day one (ban risk starts accruing immediately) |
| LinkedIn via unofficial scraper/RapidAPI vendors | Technically statelessly callable | Varies | Immediate — but see legal risk above; also inherits Proxycurl's fate risk (vendor could disappear mid-project) |

---

## Recommended stack

Optimized for: small budget, must work live on a name the system has never seen, minimal ToS/legal
exposure, must run in Vercel serverless.

| Signal tier | Recommended source | Why |
|---|---|---|
| **Authored content (general web: blogs, podcasts, conference talks, press quotes)** | **Keep Anthropic `web_search`** as primary. It's already wired into the model call, has no separate integration cost, and this is the sub-tier it's actually good at. | No change from current plan — already correct here. |
| **Authored content (X/Twitter specifically)** | **X API, pay-per-use tier**, called as a normal stateless REST lookup (recent posts by handle/name search) alongside `web_search`. | Real, self-serve, official, immediately available (no waitlist), cheap at single-prospect volume (~$0.01–0.05/lookup), fully stateless. |
| **Authored content (LinkedIn specifically)** | **Do not build a dedicated LinkedIn retrieval path.** Rely on whatever `web_search` opportunistically surfaces (occasionally an indexed high-engagement post), and treat LinkedIn as a known, disclosed gap. | Every real alternative (official partner API, account-automation tools, third-party scraper APIs) is either too slow to arrange before a demo, priced far above budget, contractually prohibited, or actively being litigated into nonexistence (Proxycurl, Jan–Jul 2025). This is not a corner being cut casually — it's the one path here that carries genuine legal exposure and product-continuity risk (a vendor can vanish mid-project the way Proxycurl did). |
| **Business events (funding, hiring, launches, press)** | **Anthropic `web_search`**, with **GDELT** as a free fallback/cross-check for press-driven events specifically. | Both stateless, both free-or-included, both well-suited to this content type. |
| **Firmographic (size, industry, funding stage)** | **People Data Labs free tier** (100 lookups/month, no card) as primary; fall back to whatever `web_search` surfaces if a company isn't in PDL's index. | Genuinely free at demo/project scale, structured/reliable schema (unlike opportunistic web search), stateless REST, same-day signup. |
| **Firmographic (tech stack)** | **Skip automated tech-stack lookup.** | Lowest-value firmographic sub-signal per the brief's own ranking ("never a standalone hook"); the only real API option (BuiltWith) starts at $200+/mo, disproportionate to its value here. |

### Explicit "needs lead time" flags for the owner

- **LinkedIn official API access** — 4–8 weeks fast path, 3–4 months typical, discretionary enterprise
  approval. **Not usable for the demo under any circumstance** given the timeline; flagging so it's a
  known, deliberate exclusion rather than a surprise gap discovered late.
- **X API** — no waitlist, but requires creating an X developer account and attaching a payment method
  before first use. Trivial (same day) but not "already there" — do this during T3 build, not the day of
  the demo.
- **People Data Labs / Exa / Tavily free tiers** — instant self-serve signup, no approval process, but
  still needs an account + API key generated and stored in Vercel env vars before the demo. Same-day, no
  real lead time, just don't leave it to the last five minutes.
- Everything else in the recommended stack (`web_search`, GDELT) requires no new setup at all.

### What this means for the existing fixture-fallback plan

The brief already correctly hedges on this ("LinkedIn blocks direct scraping, so don't gamble the live
interview demo on a fresh scrape succeeding") — this research confirms that instinct was right and
extends it: it's not just that a *fresh scrape* might fail, it's that there is no legitimate LinkedIn
retrieval path at all within this project's constraints. The fixtures-as-demo-fallback strategy is doing
real, necessary work here, specifically for LinkedIn-flavored authored content — not just as a
reliability hedge but as a compensating control for a genuine, permanent capability gap in the live path.
