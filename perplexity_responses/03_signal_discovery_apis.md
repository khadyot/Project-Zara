# Observable signals of operational pain, and the APIs that surface them — research findings

**Source:** Perplexity (Research mode), run 2026-08-24.
**Prompt:** [`03_signal_discovery_apis.md`](../perplexity_prompts/03_signal_discovery_apis.md)

> **Unverified third-party research.** Vendor names, pricing, and coverage claims have not been confirmed against primary sources. See the verification notes appended at the end before acting on any of it.

---

For your volume (5–20 prospects/day), the most actionable public signals for ops/reconciliation pain are: (1) reviews written by your target’s staff about the tools they use, (2) vendor case studies and partner/marketplace listings that explicitly describe finance/ops workflows, and (3) observable complexity in the payment/ERP stack from tech‑detection tools and status pages. Funding/leadership-change feeds are the single highest‑impact purchase for improving prospect quality at this scale.  

Below I go through signals, concrete `observable_via` conditions, web search APIs, firmographic/event feeds, and which pains you likely have to drop.

***

## Part 1 – Ranked observable signals

### Ranked table of signals

**Legend (hit rate / false-positive):**  
- Hit rate: Very low (<10%), Low (10–20%), Medium (20–40%), High (>40%), for 50–2,000‑employee private companies.  
- False-positive: Low (mostly on-target), Medium (lots of “interesting but irrelevant”), High (often noisy).

| Rank | Signal | What it actually observes / which pain(s) | How to retrieve (API/scrape) | Expected hit rate | Date availability | False‑positive risk |
|------|--------|-------------------------------------------|------------------------------|-------------------|-------------------|---------------------|
| 1 | **Staff-authored reviews on B2B software review sites** (G2, Capterra, TrustRadius, etc.) | Reviews written by employees at the target company about finance/ops tools (ERP, billing, reconciliation, FP&A, order management), including complaints like “month‑end close is manual,” “we reconcile invoices in Excel,” “lots of exceptions handled outside the system.” Evidence for: (1) month‑end close drags, (2) reconciliation breaks, (4) exceptions handled in spreadsheets. | Use review scrapers that take a **domain or product URL** and return structured reviews with text, role, company name, and date. Apify’s G2 Reviews Scraper actor supports domain-based multi‑platform scraping and exposes `publishedAfter` / `lookbackDays` and role fields.[apify.com](https://apify.com/focused_vanguard/multi-platform-reviews-scraper?share_frome=aipt)[apify.com](https://apify.com/zen-studio/g2-reviews-scraper?share_frome=aipt)[apify](https://apify.com/automation-lab/g2-scraper?share_frome=aipt) Many generic web‑scraping APIs (AlterLab, Crawlbase, ScraperAPI) provide rendered HTML for G2/Capterra URLs that you can parse yourself.[alterlab.io](https://alterlab.io/data-from/g2-reviews?share_frome=aipt)[scrapfly](https://scrapfly.io/blog/posts/how-to-scrape-g2-company-data-and-reviews?share_frome=aipt)[crawlbase](https://crawlbase.com/blog/scrape-g2-reviews-using-javascript/?share_frome=aipt)[scraperapi](https://www.scraperapi.com/blog/how-to-scrape-g2-reviews-using-python/?share_frome=aipt) | **Low–Medium** – many mid‑market firms will have **some** staff review activity, but not most. For your 50–2,000 segment, think in the 10–30% band, skewed towards software, ecommerce, and modern finance teams. | Yes. Review platforms surface explicit review dates; scrapers expose them in structured outputs (`publishedAt` or similar).[apify.com](https://apify.com/zen-studio/g2-reviews-scraper?share_frome=aipt)[apify](https://apify.com/automation-lab/g2-scraper?share_frome=aipt)[crawlbase](https://crawlbase.com/blog/scrape-g2-reviews-using-javascript/?share_frome=aipt) | **Low–Medium.** The people writing reviews usually work with the tool they’re describing; complaints about “manual reconciliation” or “Excel hell” correlate strongly with the pains you care about. False positives mostly come from general dissatisfaction (“UI is slow”) rather than specific ops pain. |
| 2 | **Vendor customer stories and case studies naming the company** | Named references to your target in ERP / accounting / billing / payments / reconciliation vendors’ case studies, detailing “before” and “after” states: e.g., “month‑end close went from 10 days to 3,” “we automated settlement reconciliation across multiple PSPs,” “eliminated spreadsheet-based exception handling.” Strong evidence for all four pains, especially (1), (2), (4). | Use search APIs (Exa, Tavily, Brave) to query `"\"<Company Name>\" NetSuite case study"`, `"\"<Company Name>\" \"month-end close\" \"case study\""`, `"\"<Company Name>\" \"payment reconciliation\""` with date filters and domain constraints (e.g. `includeDomains` for `netsuite.com`, `sap.com`, `stripe.com`).[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/web-search?share_frome=aipt) For **system integrator and implementation-partner case studies**, target SI domains plus ERP names (e.g. `<Company Name> "NetSuite implementation" "partner"`). | **Low.** Most private mid‑market firms never appear in public case studies. Hit rate is higher for tech‑forward companies and those using marquee SaaS (Stripe, NetSuite, SAP, Coupa). Often single‑digit percentages. | Yes. Case-study pages usually carry publication dates or at least dated blog metadata; Exa and Tavily expose a `publishedDate` field when available.[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt) | **Low.** When you find a case study, it is almost always describing real, historically painful processes. The challenge is *scarcity*, not noise. One caution: pain may have been partially addressed already, so outreach should reference **remaining gaps** or adjacent workflows. |
| 3 | **Review‑site movement around finance/ops tools** (reviews on tools your prospect uses) | Changes over time in the volume, recency, and sentiment of reviews about specific ERPs, billing, and reconciliation tools used by similar companies (even if not your exact target). Evidence for: general market pain patterns that you can bucket by ICP (e.g., “NetSuite customers at 50–500 employees often complain about bank reconciliation”). | Use platform‑wide review scrapers (Apify multi‑platform actor for G2+Capterra+TrustRadius+Trustpilot). Query by **product** (e.g. `NetSuite`, `SAP Business One`, `Stripe Billing`) and filter by reviewer company size/industry to match your ICP.[apify.com](https://apify.com/focused_vanguard/multi-platform-reviews-scraper?share_frome=aipt)[apify](https://apify.com/automation-lab/g2-scraper?share_frome=aipt) For tool‑specific research, you can run scheduled scrapes to track new reviews and keywords over time. | **High** at the **tool** level (popular ERPs/payments tools have lots of reviews), but indirect at the **company** level—you’ll rarely see your exact target among them. | Yes. Reviews carry dates; scrapers preserve them.[apify.com](https://apify.com/zen-studio/g2-reviews-scraper?share_frome=aipt)[apify](https://apify.com/automation-lab/g2-scraper?share_frome=aipt) | **Medium.** This is ICP‑level, not company‑specific, evidence: great for “NetSuite customers like you struggle with X,” weaker for “Your company definitely struggles with X.” Treat it as pattern evidence, not a trigger. |
| 4 | **Public status pages and incident logs owned by the target** | Incident reports on the target’s own status page (e.g. `status.<company>.com`) about delayed payouts, ledger mismatches, transaction processing delays, or data-integrity issues. Evidence for: (2) reconciliation breaks, occasionally (1) and (4) if they mention manual fallback procedures. | Use a simple **status‑page discovery heuristic**: try known patterns (`status.company.com`, `company.statuspage.io`, `company.instatus.com`) and, if found, scrape the incident archive. Firecrawl’s `monitor` endpoint can crawl and re‑check status pages cheaply (1 credit per page per check).[firecrawl.dev](https://www.firecrawl.dev/pricing?share_frome=aipt) Alternatively, custom scraping + HTML parsing. | **Very low.** Only SaaS and fintech-ish companies tend to run public status pages; many ops-heavy companies don’t. Even when present, incident types may be mostly availability rather than reconciliation. | Yes. Incidents are timestamped, and many tools expose machine‑readable histories (RSS/JSON). | **Medium.** An incident about “delayed payouts” is good evidence of reconciliation or settlement pain. But many incidents are generic downtime. You’ll need keyword filters (“payout”, “settlement”, “reconciliation”, “ledger”, “duplicate”, “data mismatch”) to avoid false positives. |
| 5 | **Web‑visible payment stack complexity** (multiple processors, complex checkout) | Presence of multiple payment processors, BNPL providers, wallets, and region/currency variants in the public web stack, especially for ecommerce or marketplace businesses. Evidence for: (2) reconciliation breaks and (3) ops headcount scaling with volume (more PSPs → more reconciliation surfaces). | Use tech‑stack detectors that classify web technologies including payment processors: WhatStack and DataFragment both claim detection of 200–315 payment processor technologies and enumerate them per site.[whatstack.ai](https://whatstack.ai/technologies/ecommerce-payments/payment-processor?share_frome=aipt)[datafragment.com](https://www.datafragment.com/resources/free-technology-lookup-tool?share_frome=aipt) StackDetector offers a headless‑browser‑based tech‑stack API returning categorized technologies (including PSPs) per URL with confidence scores and pricing around $9.50 per 1,000 scans on its Starter tier (verified June 2026).[stackdetector.com](https://stackdetector.com/?share_frome=aipt) BuiltWith and similar tools also detect PSPs, carts, and ecommerce tech but skew to front‑end web.[builtwith](https://builtwith.com/?share_frome=aipt)[builtwith.com](https://builtwith.com/report-filtering?share_frome=aipt) | **Medium** for firms with online sales / portals; **low** for back‑office‑heavy companies without meaningful web commerce. Among 50–2,000‑employee targets, expect patchy coverage unless you narrow ICP to companies with online transactions. | Yes. You can track **changes over time** by snapshotting detected technologies and differencing; BuiltWith’s “Actionable Insights” and report filtering are built around tech‑change signals but are mostly front‑end.[blog.builtwith.com](https://blog.builtwith.com/2026/01/08/actionable-insights/?share_frome=aipt)[builtwith.com](https://builtwith.com/report-filtering?share_frome=aipt) | **Medium–High.** A complex PSP mix correlates with reconciliation and ops load but doesn’t guarantee pain—some teams might be well‑automated. It’s strongest as a **complexity proxy** (“you likely have a lot to reconcile”), not a direct pain label. |
| 6 | **Integration / partner / marketplace listings** | Appearances of the target in partner directories, integration listings, and marketplaces of ERPs, PSPs, CRMs, and workflow tools. Evidence for: (1) multi‑system month‑end matching, (2) reconciliation complexity, sometimes (3) linear ops headcount (“lots of tools, not much automation”). | For major vendors (Stripe, Adyen, NetSuite, SAP, Shopify, etc.), scrape marketplace/partner directories or search site‑restricted with Exa/Tavily: `"\"<Company Name>\" site:stripe.com \"partner\"` or `"\"<Company Name>\" \"integration\"` with `includeDomains` or `excludeDomains` as needed.[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt) This is largely custom scraping, but volume at 5–20 companies/day is manageable. | **Low–Medium.** Partners and marketplace listings skew to SaaS and mid/upper‑mid‑market companies; many private firms might never list. But when present, listings give very clean signals about stack composition. | Sometimes. Directories may or may not expose listing dates; changes over time usually require snapshotting and version control yourself. | **Medium.** Presence indicates tool usage and interfaces, but not whether workflows are manual. Use it primarily to **infer system graph** (“ERP X, PSP Y, billing Z”) and then combine with other signals (reviews, blogs) for pain evidence. |
| 7 | **Funding + leadership change events** | Funding rounds, new CFO/VP Finance/COO, acquisitions, and expansion announcements for the target. These don’t directly state reconciliation pain but reliably indicate **change moments** where process improvement is on the agenda. Evidence for: general receptivity to automation; strongest for (1) and (3). | Crunchbase covers 4M+ companies with funding history, investor relationships, and leadership changes; Pro seat pricing is $99/month month‑to‑month or $49/month equivalent billed annually, but **full API access sits behind Enterprise with custom “Contact Sales” pricing and no published rate card**.[marketintelligencetools.com](https://marketintelligencetools.com/reports/crunchbase-pricing/?share_frome=aipt)[marketintelligencetools.com](https://marketintelligencetools.com/reviews/crunchbase/?share_frome=aipt)[pipeline.zoominfo](https://pipeline.zoominfo.com/sales/crunchbase-api?share_frome=aipt)[prospeo.io](https://prospeo.io/s/what-is-crunchbase?share_frome=aipt)[netrows.com](https://www.netrows.com/blog/best-startup-data-apis-2026?share_frome=aipt) Harmonic exposes funding and team-change data via a gated REST/GraphQL API with no public pricing; third‑party estimates place minimum contracts around $25K/year with a 3‑seat minimum – effectively enterprise‑only.[tryfundable.ai](https://www.tryfundable.ai/blog/crunchbase-api-alternatives?share_frome=aipt)[quotaengine.com](https://www.quotaengine.com/tools/harmonic/?share_frome=aipt)[prospeo](https://prospeo.io/s/harmonic-pricing-reviews-pros-and-cons?share_frome=aipt)[apis.io](https://apis.io/plans/harmonic-ai/harmonic-ai-plans-pricing/?share_frome=aipt) Fundable positions itself as a self‑serve funding‑data API with plans from $20/month (Hobby), $50/month (Pro), $100/month (Pro+), and API credits starting at $0.05/credit with 200 free credits, no card required.[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt) Tracxn’s data solutions are also “Contact our specialist to discuss pricing,” with public listings showing starting prices around $500/month usage‑based.[tracxn.com](https://tracxn.com/pricing?share_frome=aipt)[getapp.com](https://www.getapp.com/marketing-software/a/tracxn/?share_frome=aipt)[softwareadvice.com](https://www.softwareadvice.com/market-research/tracxn-profile/?share_frome=aipt) | **Medium** – most funded mid‑market companies will show up in Crunchbase and/or Fundable, with reasonable coverage of leadership changes and expansions.[salesrobot.co](https://www.salesrobot.co/blogs/crunchbase-review?share_frome=aipt)[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt) But bootstrapped firms may be invisible. | Yes. Funding rounds and leadership changes are dated events; both Crunchbase and Fundable expose event dates.[salesrobot.co](https://www.salesrobot.co/blogs/crunchbase-review?share_frome=aipt)[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt) | **Medium.** A new CFO or fresh Series B correlates with openness to financial automation but not with a specific reconciliation failure. Use these as **timing signals** (“now is a change moment”), then combine with more specific evidence. |
| 8 | **Company blogs, CFO/COO interviews, and thought-leadership content** | Blog posts, interviews, and talks where finance/ops leaders at the target describe their workflows in detail (e.g., “we still close in spreadsheets,” “our order-to-cash process spans five systems,” “exceptions get dumped into Excel”). Evidence for (1) and (4), sometimes (2). | Use semantic search APIs (Exa/Tavily/Brave) with company name + role + pain keywords, constrained by date: e.g. `"\"<Company Name>\" \"VP Finance\" \"month-end close\""` with `startPublishedDate` on Exa,[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt) or Tavily `start_date`/`end_date` and `time_range`.[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)[tavily](https://help.tavily.com/articles/3347142954-best-practices?share_frome=aipt) Brave’s `freshness` parameter (`pd`, `pw`, `pm`, `py` or explicit `YYYY-MM-DDtoYYYY-MM-DD`) filters web/news results.[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/web-search?share_frome=aipt) | **Low.** Only a small fraction of private mid‑market finance leaders produce detailed public content, and even fewer mention operational pain explicitly. | Yes. Blogs and interviews almost always carry publication dates; Exa/Tavily/Brave expose date metadata when available, though “publishedDate” may be null for some pages.[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt) | **Medium–Low.** When you find content, pain descriptions are usually genuine; false positives arise from very high‑level “we care about efficiency” messaging that doesn’t map cleanly to your four pains. |
| 9 | **Community footprints (forums, Reddit, Slack/Discord, accounting/finance boards)** | Public posts where people mention working at `<Company>` and complain about specific workflows (e.g., “I reconcile five PSPs manually,” “we run month‑end with CSV dumps”). Evidence for (1), (2), (4). | Use web search APIs and domain scoping with keywords: `"\"<Company Name>\" \"month-end\" \"Excel\" site:reddit.com"`, `"\"<Company Name>\" \"reconciliation\" \"spreadsheet\""` via Exa/Tavily/Brave.[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt) Most forums have no official API at your scale; scraping is ad‑hoc. | **Very low.** It’s rare for staff at mid‑market firms to publicly air detailed ops complaints with company names attached in indexed public forums. | Yes, when present (posts carry timestamps). | **High.** Many posts are anonymous or pseudonymous; mapping them to your target company is unreliable unless the company name is explicit and context is clear. Treat these as “bonus color” when present, never as primary evidence. |
| 10 | **Procurement and RFP notices** | Public RFPs or procurement notices where the company spells out requirements like “multi‑entity reconciliation,” “automated exception handling,” “month‑end close acceleration.” Evidence for all pains if present. | Primarily government and public‑sector vendors; for private firms, occasional RFPs are hosted on vendor portals or PDF attachments. Discoverable via generic search (company + “RFP”, “proposal”, “tender”) but not consistently via any one API. | **Very low** in your target segment, and often restricted access. | Yes, where present. | **Low noise, but not worth it.** When found, RFPs are excellent evidence—but hit rate is so low that, at 5–20 prospects/day, building automation around this is unlikely to pay back. |

**Signals not worth building (for your use-case):**

- **Job‑posting-based technographics and hiring signals (e.g. TheirStack):** TheirStack explicitly infers technologies from job descriptions and processes millions of postings per day. That entire path is explicitly closed in your pipeline, and using such vendors would violate your constraint.[theirstack.com](https://theirstack.com/en/technographic-signals?share_frome=aipt)[theirstack.com](https://theirstack.com/en?share_frome=aipt)[theirstack.com](https://theirstack.com/en/docs/guides/how-to-find-companies-by-technology-stack?share_frome=aipt)[predictleads.com](https://predictleads.com/blog/outbound-buying-signal-tools/?share_frome=aipt)
- **Generic “community presence” metrics** (e.g., number of Reddit mentions, generic Glassdoor reviews): they rarely describe concrete finance/ops workflows and are noisy for your pains.  
- **Generic “funding-only” feeds without leadership or sector data**: funding alone is too coarse as a pain proxy; you need at least role‑level signals (new CFO/COO) or sector tags to make it useful.

***

## Part 2 – Concrete `observable_via` conditions for your four pains

Below I phrase conditions in a way a script could test, assuming you have a prospect `company_name`, `company_domain`, and sources plugged in (search APIs, review scrapers, tech‑stack detectors, event feeds).

### Pain 1 – Month-end close drags because matching is manual across systems

**Key observable patterns:**

1. **Direct language about manual month‑end and reconciliation in staff reviews.**

   - Source: G2/Capterra/TrustRadius reviews scraped via domain-based actors (e.g. Apify multi‑platform or G2‑only actors).[apify.com](https://apify.com/focused_vanguard/multi-platform-reviews-scraper?share_frome=aipt)[apify.com](https://apify.com/zen-studio/g2-reviews-scraper?share_frome=aipt)[apify](https://apify.com/automation-lab/g2-scraper?share_frome=aipt)
   - Condition (pseudo):

     > `exists_review(company_domain, text_contains_any([ "month-end close", "month end", "closing the books", "manual reconciliation", "manual matching", "reconcile in Excel", "CSV exports from multiple systems", "we stitch data across systems" ]))`

   - If true on a review where `reviewer_role` contains `"Finance"`, `"Accounting"`, `"Controller"`, `"FP&A"`, or `"RevOps"`, treat as **strong evidence**.

2. **Vendor case studies citing manual matching across multiple systems.**

   - Source: ERP/billing/finance automation vendor case studies retrieved via Exa/Tavily with date filters.[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)
   - Condition:

     > `exists_page(vendor_domains, company_name, text_contains_any([ "month-end close", "close went from", "manual matching", "spreadsheet reconciliation", "CSV dumps from", "multiple systems reconciled manually" ]))`

   - Attach `publishedDate` and require it to be within, say, last 36 months to avoid very stale process descriptions.

3. **Evidence of a complex multi‑system financial stack with low automation proxies.**

   - Source: tech‑stack detectors (WhatStack, DataFragment, StackDetector) and integration listings.[whatstack.ai](https://whatstack.ai/technologies/ecommerce-payments/payment-processor?share_frome=aipt)[datafragment.com](https://www.datafragment.com/resources/free-technology-lookup-tool?share_frome=aipt)[stackdetector.com](https://stackdetector.com/?share_frome=aipt)[builtwith.com](https://builtwith.com/report-filtering?share_frome=aipt)
   - Condition:

     > `count(payment_processor_technologies(company_domain)) >= 3` AND  
     > `count(erp_or_accounting_technologies(company_domain)) >= 2`

   - This is a **complexity proxy**: more PSPs and multiple finance systems → more data to reconcile. Not a direct pain signal, but useful when combined with #1 or #2.

4. **Blog/interview content about slow month‑end.**

   - Source: Exa/Tavily/Brave search with `startPublishedDate` / `time_range`.[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/web-search?share_frome=aipt)[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)
   - Condition:

     > `exists_page(all_web, company_name && role_keywords, text_contains_any([ "month-end close", "closing the books", "takes us X days to close", "we're trying to automate close" ]))`

   - Role keywords: `"CFO"`, `"VP Finance"`, `"Controller"`, `"Head of Finance"`, `"COO"`.

**Suggested rule:**

- Mark **Pain 1 “observable”** if **any of (#1, #2, #4) is true**, and **Pain 1 “likely”** if (#3 is true AND headcount/event signals indicate growth).

### Pain 2 – Payment, ledger, and bank reconciliation breaks silently and surfaces late

**Key observable patterns:**

1. **Status-page incidents about payouts, settlements, ledger/transaction mismatches.**

   - Source: status page scraping + Firecrawl monitor.[firecrawl.dev](https://www.firecrawl.dev/pricing?share_frome=aipt)
   - Condition:

     > `exists_incident(status_page(company_domain), text_contains_any([ "delayed payout", "settlement delay", "settlement issue", "double charge", "duplicate transactions", "ledger discrepancy", "bank reconciliation issue", "incorrect balances", "data mismatch" ]))`

   - Require multiple incidents or one **recent** (e.g. `incident_date >= today - 180 days`).

2. **Vendor case studies describing reconciliation failures before automation.**

   - Source: vendor case studies for payments reconciliation tools, R2R automation, etc., via Exa/Tavily.[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)
   - Condition:

     > `exists_page(vendor_domains, company_name, text_contains_any([ "payment reconciliation", "settlement reconciliation", "reconcile PSPs", "ledger vs bank mismatch", "reconciliation errors", "exceptions during reconciliation" ]))`

3. **Staff reviews mentioning reconciliation pain.**

   - Source: G2/Capterra reviews.[apify.com](https://apify.com/zen-studio/g2-reviews-scraper?share_frome=aipt)[apify](https://apify.com/automation-lab/g2-scraper?share_frome=aipt)
   - Condition:

     > `exists_review(company_domain, text_contains_any([ "reconciliation", "settlement", "payouts", "we manually reconcile", "bank reconciliation", "close out payments manually", "exceptions during reconciliation" ]))`

   - Again, gate on `reviewer_role` ∈ {Finance, Accounting, Treasury, RevOps}.

4. **News/blog posts about payment outages impacting customer balances or payouts.**

   - Source: Exa with `category: "news"` and `startPublishedDate`. Brave News search with `freshness` + `extra_snippets`.[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/web-search?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/news-search?share_frome=aipt)[exa.ai](https://exa.ai/docs/reference/verticals/news-for-coding-agents?share_frome=aipt)[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)
   - Condition:

     > `exists_article(company_name, text_contains_any([ "payment outage", "payouts delayed", "customers were charged twice", "refund issues", "billing system outage" ]))`

**Suggested rule:**

- Mark **Pain 2 “observable”** if (#1 or #3 or #2 or #4) hits *recently* (within 24–36 months).  
- Weight #1 and #2 highest (company‑owned logs or deep case studies); treat #3 and #4 as supporting evidence.

### Pain 3 – Ops headcount scales linearly with transaction volume

This is intrinsically hard without job postings or LinkedIn. Realistically you cannot see “linear scaling” from outside; you can only guess from **complexity** and **growth**.

Possible—but weak—proxies:

1. **High transaction complexity without visible automation investments.**

   - Condition:

     > `count(payment_processor_technologies(company_domain)) >= 3` AND  
     > `sector` ∈ {ecommerce, marketplace, logistics, supply chain} AND  
     > NOT `exists_page(company_name, text_contains_any(["automation", "workflow", "process orchestration", "robotic process automation", "RPA", "no-code automation"]))`

   - This says: “you handle complex flows but don’t talk publicly about automation.” It’s weak and prone to false positives.

2. **Rapid company growth signals (funding, expansion) with flat ops tooling footprint.**

   - Combining events from Fundable/Crunchbase (Series B/C, expansion) with tech‑stack detectors showing no major ERP/ops upgrades over the same period.[datafragment.com](https://www.datafragment.com/resources/free-technology-lookup-tool?share_frome=aipt)[builtwith.com](https://builtwith.com/report-filtering?share_frome=aipt)[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt)[salesrobot.co](https://www.salesrobot.co/blogs/crunchbase-review?share_frome=aipt)

Even with these, you **cannot** reliably claim “ops headcount scales linearly.” You just infer “you likely have growing transaction volume and non‑trivial complexity.” I’d treat Pain 3 as **not reliably observable** and use these proxies only for generic “you’re scaling; ops is probably under pressure” messaging.

### Pain 4 – Exceptions handled in spreadsheets with no audit trail

**Key observable patterns:**

1. **Direct Excel/Spreadsheet complaints in staff reviews.**

   - Source: G2/Capterra/TrustRadius.[apify](https://apify.com/automation-lab/g2-scraper?share_frome=aipt)[apify.com](https://apify.com/zen-studio/g2-reviews-scraper?share_frome=aipt)
   - Condition:

     > `exists_review(company_domain, text_contains_any([ "spreadsheet", "Excel", "Google Sheets", "CSV", "manual tracking", "off-system tracking", "we track exceptions in Excel", "exceptions in spreadsheets" ]))`

   - Use role filter (Finance, Ops, Supply Chain, RevOps).

2. **Blog/interview text explicitly describing spreadsheet exception handling.**

   - Source: Exa/Tavily/Brave search.[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt)
   - Condition:

     > `exists_page(company_name, text_contains_any([ "exceptions handled in Excel", "exceptions go into a spreadsheet", "we manage exceptions manually", "no audit trail" ]))`

3. **Vendor case studies describing spreadsheet exceptions as “before” state.**

   - Source: ERP/workflow automation vendors.[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)
   - Condition:

     > `exists_page(vendor_domains, company_name, text_contains_any([ "exceptions managed in spreadsheets", "spreadsheet-based workflow", "no audit trail", "unstructured exception handling" ]))`

**Suggested rule:**

- Mark **Pain 4 “observable”** only when you have **direct language** (#1–#3). Without job postings, this pain is rarely stated publicly; you’ll have many targets where you simply have no evidence either way.

***

## Part 3 – Web search APIs, judged on your six properties

### Overview of the main contenders (2026)

Below is a comparison of Exa, Tavily, Firecrawl, Serper, Brave Search API, and self‑hosted SearXNG.

#### Table – Date filtering, date reliability, snippet windowing, and price

| API | Date filtering at query time (parameter) | Date reliability in results | Snippet / content windowing behaviour | Domain scoping | Pricing (free + first paid tier) |
|-----|------------------------------------------|-----------------------------|----------------------------------------|----------------|----------------------------------|
| **Exa** | `startPublishedDate` / `endPublishedDate` (ISO 8601) on `/search`; `startCrawlDate` / `endCrawlDate` exist but have been silently ignored since April 15, 2026 per independent testing, while `startPublishedDate` remains documented as the recommended strict filter.[dev.to](https://dev.to/flarecanary/exa-just-removed-research-and-started-silently-ignoring-two-date-filters-your-agent-is-probably-1p51?share_frome=aipt)[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[exa.ai](https://exa.ai/docs/reference/verticals/news-for-coding-agents?share_frome=aipt) | Results include `publishedDate` where Exa can infer it; spec notes it may be null when no date is parsed.[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt) There is no public, quantified evaluation of “percentage of results with non‑null dates,” but Exa is explicit about carrying a `publishedDate` field. | Snippets can be **match‑centred** via the `contents.highlights` option. Passing `contents.highlights: true` or an object (`{query, maxCharacters}`) returns key excerpts relevant to the query from each page, rather than just the head of the document.[exa.ai](https://exa.ai/docs/reference/search-api-guide-for-coding-agents?share_frome=aipt) Alternatively, you can fetch full text via `/contents` and window yourself.[exa](https://exa.ai/docs/reference/pricing?share_frome=aipt)[exa](https://exa.ai/docs/changelog?share_frome=aipt) | Strong domain scoping via `includeDomains`, `excludeDomains`, plus `category` with specialized handling for `company` and `people` searches.[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt) | Pay‑as‑you‑go. Search with contents: **$7 per 1,000 requests** (includes up to 10 results with text + highlights); Deep Search **$12–15 per 1,000**; Contents **$1 per 1,000 pages**; Answer **$5 per 1,000 requests**.[exa](https://exa.ai/docs/reference/pricing?share_frome=aipt)[exa.ai](https://exa.ai/pricing?share_frome=aipt)[exa](https://exa.ai/docs/changelog?share_frome=aipt)[fastcrw](https://fastcrw.com/blog/exa-pricing-explained?share_frome=aipt)[usagepricing.com](https://www.usagepricing.com/tools/pricing-calculator/exa-ai?share_frome=aipt) New accounts get **$20 in free credits** (~2,800 searches) and an ongoing **$10 monthly free credit**.[exa](https://exa.ai/docs/reference/pricing?share_frome=aipt) |
| **Tavily** | Relative `time_range` (`"day"`, `"week"`, `"month"`, `"year"`) and absolute `start_date` / `end_date` (`YYYY-MM-DD`) on the `search` endpoint.[tavily](https://help.tavily.com/articles/3347142954-best-practices?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)[github](https://github.com/tavily-ai/langchain-tavily?share_frome=aipt)[reference.langchain.com](https://reference.langchain.com/python/langchain-tavily/tavily_search/TavilySearchInput/start_date?share_frome=aipt)[reference.langchain.com](https://reference.langchain.com/python/langchain-tavily/tavily_search/TavilySearchInput/end_date?share_frome=aipt) Note: key best‑practice docs were last updated August 2025, slightly more than 12 months ago; behaviour appears unchanged but should be validated.[tavily](https://help.tavily.com/articles/3347142954-best-practices?share_frome=aipt) | When `topic: "news"` is used, Tavily returns `published_date` metadata per source.[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt) For general web results, Tavily returns the “most query‑related content” (`content`) plus optional `rawContent`; there is no published evaluation of date completeness across all sources.[docs.tavily.com](https://docs.tavily.com/documentation/api-reference/endpoint/search?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/sdk/javascript/reference?share_frome=aipt) | **Chunk‑based, match‑centred content.** Both `search_depth=advanced` and, since July 2026, `search_depth=basic` return multiple semantically relevant **chunks** per URL, up to 500 characters each, joined into `content`. You can control chunk count via `chunks_per_source` and optionally receive full `rawContent` for your own windowing.[docs.tavily.com](https://docs.tavily.com/documentation/api-reference/endpoint/search?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/changelog?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/sdk/javascript/reference?share_frome=aipt) This is exactly the “evidence‑dense window” behaviour you measured. | Domain scoping via `include_domains` and `exclude_domains` parameters, and `country` boosting.[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt) | Credit‑based. Free tier: **1,000 credits/month**.[docs.tavily.com](https://docs.tavily.com/documentation/api-credits?share_frome=aipt)[coldiq.com](https://coldiq.com/blog/tavily-pricing?share_frome=aipt) Basic search costs **1 credit**, advanced search **2 credits** per request.[docs.tavily.com](https://docs.tavily.com/documentation/api-credits?share_frome=aipt) Paid plans: “Project” 4,000 credits for **$30/month**, “Bootstrap” 15,000 for **$100/month**, “Startup” 38,000 for **$220/month**, “Growth” 100,000 for **$500/month**; pay‑as‑you‑go at **$0.008 per credit**.[docs.tavily.com](https://docs.tavily.com/documentation/api-credits?share_frome=aipt)[coldiq.com](https://coldiq.com/blog/tavily-pricing?share_frome=aipt)[help.tavily.com](https://help.tavily.com/articles/8816424538-pricing?share_frome=aipt) |
| **Firecrawl** | Firecrawl is primarily a **scrape/crawl** engine, not a relevance‑ranked search index. Its `search` endpoint operates on its own index, with credits, but most workflows at your scale will use `scrape` + custom search. There is no built‑in, Google‑like date filter parameter; instead you can read page dates yourself from scraped HTML/Markdown.[firecrawl.dev](https://www.firecrawl.dev/pricing?share_frome=aipt)[use-apify.com](https://use-apify.com/blog/firecrawl-review-2026?share_frome=aipt)[bestscraperapi.com](https://bestscraperapi.com/guides/firecrawl-review?share_frome=aipt)[usagepricing.com](https://www.usagepricing.com/blueprint/firecrawl?share_frome=aipt) | Firecrawl returns **full page HTML or Markdown**, so any date metadata is as‑is from the page; reliability depends entirely on the site. No cross‑site date normalization. | It returns **full content**, not fixed snippets. You implement your own snippet windowing (e.g. find keyword matches and extract ±250 chars). That gives you maximum control but requires more logic. | Domain scoping is inherent—you scrape explicit URLs or crawl within domains. There is no “global index” with `includeDomains`; you supply the domains/URLs yourself.[firecrawl.dev](https://www.firecrawl.dev/pricing?share_frome=aipt) | Credit‑based scraping. Free: **1,000 credits/month**, 1 credit per scraped page.[firecrawl.dev](https://www.firecrawl.dev/pricing?share_frome=aipt)[use-apify.com](https://use-apify.com/blog/firecrawl-review-2026?share_frome=aipt)[bestscraperapi.com](https://bestscraperapi.com/guides/firecrawl-review?share_frome=aipt)[usagepricing.com](https://www.usagepricing.com/blueprint/firecrawl?share_frome=aipt) Hobby: **$16/month billed yearly** for 5,000 credits; Standard **$83/month** for 100,000 credits; Growth **$333/month** for 500,000; Scale **$599/month** for 1,000,000 credits.[firecrawl.dev](https://www.firecrawl.dev/pricing?share_frome=aipt)[bestscraperapi.com](https://bestscraperapi.com/guides/firecrawl-review?share_frome=aipt)[usagepricing.com](https://www.usagepricing.com/blueprint/firecrawl?share_frome=aipt) |
| **Serper** (Google SERP API) | The documented interface is Google‑style SERP. Serper itself does not publish date filter parameters publicly; instead, you use query syntax (`"site:"`, `"before:"`, `"after:"`) or rely on Google result “tools” semantics. There is **no structured `freshness` parameter** like Brave or Exa; date control is limited and not guaranteed. Public docs do not expose a per‑parameter date filter as of mid‑2026.[apiserpent.com](https://apiserpent.com/blog/serper-pricing-credits-explained?share_frome=aipt)[coldiq.com](https://coldiq.com/blog/serper-pricing?share_frome=aipt)[companyview.io](https://companyview.io/software/serper?share_frome=aipt) | Serper returns whatever Google SERP exposes (some results with dates, some without). There is no vendor‑level guarantee on date metadata completeness; independent pricing reviews focus solely on credits and costs, not date reliability.[coldiq.com](https://coldiq.com/blog/serper-pricing?share_frome=aipt)[companyview.io](https://companyview.io/software/serper?share_frome=aipt) | Snippets are **Google’s own SERP snippets**, typically short excerpts near the top of the page. There is no API parameter for match‑centred windowing; you either accept the SERP snippet or fetch the page yourself for custom windowing. | Domain scoping via standard Google `site:` queries in the `q` parameter. No first‑class `includeDomains` array; scoping quality thus depends on Google’s query parser. | Prepaid credit packs. Free: **2,500 queries** per account, no card required.[apiserpent.com](https://apiserpent.com/blog/serper-pricing-credits-explained?share_frome=aipt)[coldiq.com](https://coldiq.com/blog/serper-pricing?share_frome=aipt)[companyview.io](https://companyview.io/software/serper?share_frome=aipt) Starter: **$50 for 50,000 credits** (~$1.00 per 1,000 queries); Standard: **$375 for 500,000** (~$0.75/1,000); Scale: **$1,250 for 2.5M** (~$0.50/1,000); Ultimate: **$3,750 for 12.5M** (~$0.30/1,000). Credits valid 6 months.[coldiq.com](https://coldiq.com/blog/serper-pricing?share_frome=aipt)[apiserpent.com](https://apiserpent.com/blog/serper-pricing-credits-explained?share_frome=aipt)[companyview.io](https://companyview.io/software/serper?share_frome=aipt)[toolradar.com](https://toolradar.com/tools/serper/pricing?share_frome=aipt) |
| **Brave Search API** | `freshness` parameter on web and news search: `pd` (last 24h), `pw` (last 7 days), `pm` (last 31 days), `py` (last year), or explicit `YYYY-MM-DDtoYYYY-MM-DD` ranges.[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/news-search?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/app/documentation/news-search/get-started?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/web-search?share_frome=aipt) | Brave determines page age from the “most relevant date reported by the content (published or last modified).”[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt) Results are returned with snippet text; full structured metadata is not extensively documented, but date filtering is native. | Default snippets appear like traditional search results. Enabling `extra_snippets=true` returns **up to 5 additional excerpts per result**, giving multiple windows from a long page.[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/news-search?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/web-search?share_frome=aipt) This isn’t strictly match‑centred but provides richer context than a single head‑of‑document snippet. | Domain scoping through query syntax (e.g., `site:example.com`) in `q`; no dedicated `includeDomains` array in the API reference. | Usage‑based. Web Search: **$5 per 1,000 requests**, 50 QPS.[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/pricing?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/app/plans?share_frome=aipt)[costbench.com](https://costbench.com/software/ai-search-apis/brave-search-api/?share_frome=aipt)[webscraping.cc](https://webscraping.cc/tool/brave-search/?share_frome=aipt)[companyview.io](https://companyview.io/software/brave-search-api?share_frome=aipt) Answers: **$4 per 1,000 requests + $5 per 1,000,000 input tokens + $5 per 1,000,000 output tokens**, 2 QPS.[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/pricing?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/app/plans?share_frome=aipt)[webscraping.cc](https://webscraping.cc/tool/brave-search/?share_frome=aipt)[companyview.io](https://companyview.io/software/brave-search-api?share_frome=aipt)[makerstack.co](https://makerstack.co/reviews/brave-search-api-review/?share_frome=aipt) Each account gets **$5 in monthly credits** automatically, covering roughly 1,000 Search requests; free tier requires a credit card.[webscraping.cc](https://webscraping.cc/tool/brave-search/?share_frome=aipt)[companyview.io](https://companyview.io/software/brave-search-api?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/pricing?share_frome=aipt) |
| **SearXNG (self‑hosted)** | `time_range` parameter supports `day`, `month`, `year` for engines that implement date filtering.[searxng](https://docs.searxng.org/dev/search_api.html?share_frome=aipt) You can configure which upstream search engines to use (e.g., Google, Bing, Brave) and rely on their date handling. | Date reliability depends entirely on upstream engines; SearXNG doesn’t normalize date metadata beyond what engines return. | Snippets are whatever upstream engines provide (usually head‑of‑document snippets). No native match‑centred windowing; you’d need a second fetch for custom snippets. | Strong domain scoping via query syntax and instance configuration; you choose which engines to query and can constrain per‑query. | SearXNG itself is free/open‑source; cost is hosting and upstream engines (if you pay for them). There’s no vendor pricing, but you may call paid APIs underneath (e.g. Brave, Serper). Docs as of August 22, 2026 confirm API structure and `time_range`.[searxng](https://docs.searxng.org/dev/search_api.html?share_frome=aipt) |

#### Date reliability verdict

- **Exa:** Best available *structured* date handling (`startPublishedDate`, `publishedDate` field). Your own measurement that only ~17–26% of results had parseable dates is consistent with Exa’s admission that `publishedDate` can be null; date reliability is good on news and blogs, weaker on arbitrary pages.[exa.ai](https://exa.ai/docs/reference/verticals/news-for-coding-agents?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)
- **Tavily:** Solid for news (`published_date` via `topic: "news"`), but there’s no vendor‑published evaluation of date coverage across all content types.[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)
- **Brave:** Strong for recency filtering via `freshness`; date metadata is derived from page content, but there is no coverage percentage published.[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/web-search?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt)
- **Serper + SearXNG:** Date metadata entirely depends on Google/Bing etc; there is no independent evaluation.  
- **Firecrawl:** Whatever the page itself exposes; it’s your job to extract dates.

Given your own measurements, you should treat *all* engines as “date best‑effort” and use strict filters (`startPublishedDate`, `freshness`, Tavily `start_date`) plus your own date parsing.

#### Snippet windowing verdict

Based on your 0.00 vs 0.80 relevance experiment, match‑centred windows matter a lot.  

- **Exa:** Best for “snippet around match” via `contents.highlights`. You can tune `maxCharacters` and rely on Exa’s highlighting to return key sentences.[exa.ai](https://exa.ai/docs/reference/search-api-guide-for-coding-agents?share_frome=aipt)
- **Tavily:** Very strong; both basic and advanced search now return **reranked chunks** of up to 500 characters per source, tuned for query relevance. This is explicitly designed to bring back evidence‑dense windows.[docs.tavily.com](https://docs.tavily.com/documentation/api-reference/endpoint/search?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/sdk/javascript/reference?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/changelog?share_frome=aipt)
- **Brave:** `extra_snippets` gives more excerpts but not necessarily tight windows around your match; still better than document‑head only.[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/news-search?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/services/web-search?share_frome=aipt)
- **Firecrawl:** Gives you full content; you can implement optimal windowing but have to write the logic.  
- **Serper/SearXNG:** Document‑head snippets only; you will need a second step (scrape via Firecrawl or your own HTTP client) to get match‑centred windows.

#### Person-level precision and namesake handling

- **Exa:** Supports `category: "people"` and `category: "company"` with special semantics—`people` uses a limited set of filters and `includeDomains` limited to LinkedIn; responses are tuned for LinkedIn profiles and company pages. That’s the closest thing to entity‑level disambiguation among these tools.[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)
- **Tavily:** No explicit “entity category”; it uses LLM‑guided ranking and supports `exact_match` to constrain to quoted phrases, which helps with namesakes but is still query‑level.[docs.tavily.com](https://docs.tavily.com/sdk/javascript/reference?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/changelog?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/sdk/python/reference?share_frome=aipt)
- **Brave, Serper, SearXNG:** Plain keyword matching; you can add company name and role to the query (“`\"Jane Doe\" \"Acme Corp\" CFO`”) but there’s no entity model.  
- **Firecrawl:** Not a search engine; you use it downstream once you have URLs.

#### Domain scoping quality

- **Exa and Tavily** are strongest: both support explicit `includeDomains`/`excludeDomains` arrays, so you can target vendor sites, review platforms, or your prospect’s own domain precisely.[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)
- **Brave/Serper/SearXNG** rely on query syntax like `site:example.com`, which is fine but less structured; quality depends on upstream engine behaviour.  
- **Firecrawl** is “you provide the URL”; scoping is under your control.

#### Pricing at your volume (5–20 prospects/day × 6–10 queries)

Rough usage: **30–200 searches/day → 900–6,000/month**.

- Exa: At $7 per 1,000 searches, 6,000 searches ≈ $42/month, likely offset entirely by the $10 monthly free credit for modest usage.[exa](https://exa.ai/docs/reference/pricing?share_frome=aipt)[exa.ai](https://exa.ai/pricing?share_frome=aipt)[usagepricing.com](https://www.usagepricing.com/tools/pricing-calculator/exa-ai?share_frome=aipt)
- Tavily: Free tier (1,000 credits/month) will be exceeded if you use advanced search widely; at 6,000 basic searches you’d fall in the Project ($30) or Bootstrap ($100) tier depending on depth.[docs.tavily.com](https://docs.tavily.com/documentation/api-credits?share_frome=aipt)[coldiq.com](https://coldiq.com/blog/tavily-pricing?share_frome=aipt)
- Brave: $5 per 1,000 requests with $5 monthly credit means your first ~1,000 searches are free; at 6,000 searches, ≈$25/month.[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/documentation/pricing?share_frome=aipt)[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/app/plans?share_frome=aipt)[webscraping.cc](https://webscraping.cc/tool/brave-search/?share_frome=aipt)[companyview.io](https://companyview.io/software/brave-search-api?share_frome=aipt)
- Serper: Starter pack $50 for 50,000 credits (queries) is more than enough; you’d be well under that.[coldiq.com](https://coldiq.com/blog/serper-pricing?share_frome=aipt)[companyview.io](https://companyview.io/software/serper?share_frome=aipt)
- Firecrawl: If you only scrape pages you *already* know you care about (case studies, status pages, review pages), you’ll stay inside the 1,000‑credit free tier or Hobby $16/month.[use-apify.com](https://use-apify.com/blog/firecrawl-review-2026?share_frome=aipt)[bestscraperapi.com](https://bestscraperapi.com/guides/firecrawl-review?share_frome=aipt)[usagepricing.com](https://www.usagepricing.com/blueprint/firecrawl?share_frome=aipt)[firecrawl.dev](https://www.firecrawl.dev/pricing?share_frome=aipt)

### Exa vs Tavily – direct verdict for your job

For **single‑prospect, evidence‑led outbound**:

- **Tavily** gives you:  
  - Chunked, match‑centred content windows suitable for feeding straight into your ranking and drafting stages.[docs.tavily.com](https://docs.tavily.com/changelog?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/api-reference/endpoint/search?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/sdk/javascript/reference?share_frome=aipt)
  - Simple relative date filters (`time_range`) and absolute `start_date`/`end_date` for news and web content.[tavily](https://help.tavily.com/articles/3347142954-best-practices?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)
  - Clean domain scoping via `include_domains`/`exclude_domains`.[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)
  - A free tier and low per‑credit cost at your scale.[coldiq.com](https://coldiq.com/blog/tavily-pricing?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/api-credits?share_frome=aipt)

- **Exa** gives you:  
  - Strong semantic search and flexible date filtering via `startPublishedDate`/`endPublishedDate`.[exa.ai](https://exa.ai/docs/reference/verticals/news-for-coding-agents?share_frome=aipt)[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)
  - Highlight‑based snippets that can be tuned per query for match‑centred windows.[exa.ai](https://exa.ai/docs/reference/search-api-guide-for-coding-agents?share_frome=aipt)
  - Entity categories (`people`, `company`) that help when searching for individuals and company pages together.[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)

Given your workflow, I’d treat **Tavily as the default evidence‑fetcher** (especially for review‑site and vendor‑content discovery) and **Exa as the “precision drill”** for tricky queries (hard‑to‑find case studies, niche blog posts, person‑level disambiguation). Running both is *not* redundant—their strengths are complementary—but if you want to simplify, Tavily alone plus Firecrawl (for full‑content scrape) will cover most of your needs.

***

## Part 4 – Company resolution and firmographic / event feeds

### 1. Company name → official domain

Clearbit’s free Name‑to‑Domain API effectively disappeared after HubSpot’s acquisition; free tools were sunset April 30, 2025, and the capability now lives inside HubSpot Breeze Intelligence, an enterprise add‑on around $3,600/year. For 2026, your best **free or cheap** options are:[prospeo](https://prospeo.io/s/company-name-to-domain-api?share_frome=aipt)[cufinder](https://cufinder.io/blog/what-are-the-best-company-name-to-domain-finder/?share_frome=aipt)

- **Clearout Autocomplete API (Name → Domain)**  
  - Public endpoint: `GET https://api.clearout.io/public/companies/autocomplete?query=amazon`. Returns company domain, logo URL, and a 0–100 confidence score.[prospeo](https://prospeo.io/s/company-name-to-domain-api?share_frome=aipt)
  - Free tier: **100 credits on signup**, rate limit 100 requests/min.[prospeo](https://prospeo.io/s/company-name-to-domain-api?share_frome=aipt)
  - Good fit for prototyping and low‑volume lookups; “Not Found” is explicit, so you can distinguish “unknown” from “wrong.”

- **Logo.dev Company Search API**  
  - Product: “Company Search API: Name to Domain – Type‑ahead over 50M+ companies; resolve messy human names to canonical domain.”[logo](https://www.logo.dev/products/brand-search-api?share_frome=aipt)
  - Free across plans for name‑to‑domain; you get an API key and can use it without seat pricing.[logo](https://www.logo.dev/products/brand-search-api?share_frome=aipt)

- **CUFinder, Datablist, Hunter, Tomba** (mostly enrichment tools with name→domain features)  
  - CUFinder: strong accuracy (~98%) and daily refreshed domains; pricing from **$49/month**, with 50 free credits.[cufinder](https://cufinder.io/blog/what-are-the-best-company-name-to-domain-finder/?share_frome=aipt)
  - Hunter: free 25 searches/month.[cufinder](https://cufinder.io/blog/what-are-the-best-company-name-to-domain-finder/?share_frome=aipt)
  - Tomba: name→domain as part of its company‑to‑website tool, free 25 searches/month, Starter at $49/month.[tomba](https://tomba.io/blog/company-name-to-domain-api?share_frome=aipt)

**Recommended pipeline for your volume:**

- **Primary:** Logo.dev + Clearout for free, high‑confidence resolution (`observable_via` conditions should treat `confidence < threshold` as “unknown”).[logo](https://www.logo.dev/products/brand-search-api?share_frome=aipt)[prospeo](https://prospeo.io/s/company-name-to-domain-api?share_frome=aipt)
- **Fallback:** CUFinder or Hunter when free tiers are exhausted, specifically on ambiguous names (`Acme`, `Global Logistics Inc`) where confidence scores are low.

### 2. Funding, leadership change, M&A, expansion feeds

For **20 company lookups/day (~600/month)** you need something better than scraping Crunchbase’s HTML, but full enterprise APIs (Crunchbase, Harmonic) are overkill:

- **Crunchbase**  
  - Pro seat: $99/month (monthly) or $49/month equivalent billed annually ($588/year) for search and exports; Business starts at $199/month billed annually.[marketintelligencetools.com](https://marketintelligencetools.com/reports/crunchbase-pricing/?share_frome=aipt)[marketintelligencetools.com](https://marketintelligencetools.com/reviews/crunchbase/?share_frome=aipt)[prospeo.io](https://prospeo.io/s/what-is-crunchbase?share_frome=aipt)[g2](https://www.g2.com/products/crunchbase/pricing?share_frome=aipt)[easyvc](https://easyvc.ai/vs/crunchbase-pricing/?share_frome=aipt)
  - **API access (“Custom Data Access”) is Enterprise‑only**, behind “Contact Sales”; no published pricing, with third‑party benchmarks placing contracts in the tens of thousands per year.[marketintelligencetools.com](https://marketintelligencetools.com/reviews/crunchbase/?share_frome=aipt)[pipeline.zoominfo](https://pipeline.zoominfo.com/sales/crunchbase-api?share_frome=aipt)[tryfundable.ai](https://www.tryfundable.ai/blog/crunchbase-api-alternatives?share_frome=aipt)[dataforb2b](https://dataforb2b.ai/blog/crunchbase-api-review?share_frome=aipt)[fundediq.co](https://fundediq.co/compare/crunchbase-pricing/?share_frome=aipt)[marketintelligencetools.com](https://marketintelligencetools.com/reports/crunchbase-pricing/?share_frome=aipt)
  - Free API tier has been discontinued; basic API is closed to new keys.[pipeline.zoominfo](https://pipeline.zoominfo.com/sales/crunchbase-api?share_frome=aipt)[dataforb2b](https://dataforb2b.ai/blog/crunchbase-api-review?share_frome=aipt)[dev](https://dev.to/agenthustler/crunchbase-api-in-2026-free-tier-gone-what-startup-data-hunters-do-now-1177?share_frome=aipt)
  - Verdict: **effectively enterprise‑only API**; for your scale, use the web UI or Exa/Tavily search instead of trying to buy the API.

- **Harmonic**  
  - Startup intelligence graph with funding, headcount, team composition and investor relationships via REST/GraphQL and MCP.[apis.io](https://apis.io/plans/harmonic-ai/harmonic-ai-plans-pricing/?share_frome=aipt)[apis.io](https://apis.io/providers/harmonic-ai/?share_frome=aipt)
  - Pricing is entirely “Get pricing”; third‑party estimates put minimum commitments around **$25K/year**, roughly $10K/seat/year with a 3‑seat minimum.[tryfundable.ai](https://www.tryfundable.ai/blog/crunchbase-api-alternatives?share_frome=aipt)[quotaengine.com](https://www.quotaengine.com/tools/harmonic/?share_frome=aipt)[prospeo](https://prospeo.io/s/harmonic-pricing-reviews-pros-and-cons?share_frome=aipt)[apis.io](https://apis.io/plans/harmonic-ai/harmonic-ai-plans-pricing/?share_frome=aipt)
  - Verdict: **enterprise tool**, not economical for a single‑agent workflow.

- **Fundable (funding‑data API)**  
  - Designed explicitly as a self‑serve funding‑data provider. Plans: Hobby **$20/month**, Pro **$50/month**, Pro+ **$100/month**, with **200 free credits** and credit‑based API access starting at **$0.05 per credit**.[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt)
  - All paid plans include **self‑serve API** and an MCP server; Pro+ adds MCP integration for agent workflows.[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt)
  - Third‑party comparison vs Harmonic emphasises much lower cost, self‑serve API on all paid plans, and typical usage like “funding rounds, investor data” at credit rates.[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt)
  - Verdict: **best fit at your scale** for programmatic funding and leadership events.

- **Tracxn, Ocean.io, others**  
  - Tracxn: data solutions and APIs are “Contact our specialist”; public listings show starting price **$500/month usage‑based**.[tracxn.com](https://tracxn.com/pricing?share_frome=aipt)[getapp.com](https://www.getapp.com/marketing-software/a/tracxn/?share_frome=aipt)[softwareadvice.com](https://www.softwareadvice.com/market-research/tracxn-profile/?share_frome=aipt)
  - Ocean.io: primarily a lookalike prospecting and contact data tool; pricing from **$79/month** for Starter with credit‑based exports, but focus is emails/phones, not funding events.[ocean.io](https://www.ocean.io/pricing?share_frome=aipt)[capterra.com](https://www.capterra.com/p/181991/Ocean-io/?share_frome=aipt)[getapp.com](https://www.getapp.com/sales-software/a/ocean-io/?share_frome=aipt)[pipeline.zoominfo](https://pipeline.zoominfo.com/sales/ocean-io-review?share_frome=aipt)[syncgtm.com](https://syncgtm.com/blog/ocean-io-review-2026?share_frome=aipt)[coldiq.com](https://coldiq.com/tools/oceanio?share_frome=aipt)
  - Verdict: more useful for contact enrichment than for your event‑signal needs.

**Recommended:**  

- Use **Fundable’s API** as your primary event feed: pull funding rounds, leadership changes, and expansions per company; pair these with your own search to find leadership‑change news (new CFO/COO).[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt)
- Treat Crunchbase’s web UI and Exa/Tavily search as **supplementary** (manual check for high‑value accounts).

### 3. Firmographics (headcount, sector) – “number, not marketing page”

For lightweight firmographics where approximate numbers are acceptable but “unknown” must be explicit:

- **BuiltWith**  
  - BuiltWith tracks ecommerce technologies and “exportable attributes including spend, revenue, employee count, industry, location, rank and many more” for 26M e‑commerce websites.[builtwith](https://builtwith.com/?share_frome=aipt)
  - Report filtering allows segmentation by revenue and employee count alongside tech stack signals.[builtwith.com](https://builtwith.com/report-filtering?share_frome=aipt)
  - Pricing for Basic/Pro plans is not directly on the snippet we have, but independent comparisons show Basic around $295/month with tiered, opaque pricing.[stackdetector.com](https://stackdetector.com/?share_frome=aipt)
  - Verdict: Good structured firmographics if your ICP is **ecommerce/online retail** and you can justify ~$300/month. Treat “no BuiltWith record” as “unknown.”

- **Crunchbase Pro (seat)**  
  - Includes firmographics like employee range, industry classification, funding, and growth signals at the seat level.[nubela](https://nubela.co/blog/crunchbase-api-guide/?share_frome=aipt)[marketintelligencetools.com](https://marketintelligencetools.com/reports/crunchbase-pricing/?share_frome=aipt)
  - At $49–99/month per seat, it’s plausible if you’re comfortable doing 600 manual lookups/month.[g2](https://www.g2.com/products/crunchbase/pricing?share_frome=aipt)[easyvc](https://easyvc.ai/vs/crunchbase-pricing/?share_frome=aipt)[marketintelligencetools.com](https://marketintelligencetools.com/reports/crunchbase-pricing/?share_frome=aipt)[marketintelligencetools.com](https://marketintelligencetools.com/reviews/crunchbase/?share_frome=aipt)
  - Verdict: Good manual firmographics; less useful for fully automated workflows without the Enterprise API.

- **Smaller name‑to‑domain + enrichment providers (CUFinder, Hunter, Tomba, Prospeo)**  
  - These often bundle firmographic fields (company size, sector) into their enrichment endpoints at low per‑domain costs (e.g. Datablist around $0.005/domain, Prospeo enrichment around ~$0.01/email).[cufinder](https://cufinder.io/blog/what-are-the-best-company-name-to-domain-finder/?share_frome=aipt)[prospeo](https://prospeo.io/s/company-name-to-domain-api?share_frome=aipt)
  - Verdict: For your scale, **piggybacking firmographics onto your name→domain/enrichment pipeline** is cheaper than licensing big firmographic databases. Use “no data returned” as explicit “unknown.”

So, for **cheap, reliable-enough numbers** at 20 lookups/day:

- Resolve domain via Logo.dev/Clearout.[prospeo](https://prospeo.io/s/company-name-to-domain-api?share_frome=aipt)[logo](https://www.logo.dev/products/brand-search-api?share_frome=aipt)
- Call a **lightweight enrichment API** (CUFinder, Prospeo, Datablist) that returns employee counts and industry codes. Treat missing fields as “unknown,” not “0”.

***

## Part 5 – What serious outbound teams use in 2026 (beyond LinkedIn, news, job boards)

A recent evaluation of buying‑signal tools emphasizes that modern outbound teams combine **multiple signal types**—funding, technographics, review data, and product usage—rather than relying on a single source. Leaving out LinkedIn and job boards, the main additional signals are:[predictleads.com](https://predictleads.com/blog/outbound-buying-signal-tools/?share_frome=aipt)

1. **Technographic web‑stack signals**  
   - Tools: BuiltWith, Wappalyzer, WhatStack, StackDetector, DataFragment.[wappalyzer.com](https://www.wappalyzer.com/?share_frome=aipt)[whatstack.ai](https://whatstack.ai/technologies/ecommerce-payments/payment-processor?share_frome=aipt)[datafragment.com](https://www.datafragment.com/resources/free-technology-lookup-tool?share_frome=aipt)[stackdetector.com](https://stackdetector.com/?share_frome=aipt)[builtwith](https://builtwith.com/?share_frome=aipt)
   - Automatable at 20 lookups/day: Yes; each provides either a free tier or entry‑level plan suitable for thousands of scans/month.  
   - Costs: StackDetector Starter ~$19/month with ~$9.50/1,000 scans; BuiltWith Basic around $295/month (tiered).[stackdetector.com](https://stackdetector.com/?share_frome=aipt)[builtwith.com](https://builtwith.com/report-filtering?share_frome=aipt)
   - Pain evidenced: complexity of payment stack, multiplicity of CRMs/ERPs, signs of migration (new tools appearing, old ones disappearing). Primarily supports Pain 1 and Pain 2 via “you reconcile across many systems.”

2. **Funding + event signals from dedicated startup-data APIs**  
   - Tools: Fundable (self‑serve API), Crunchbase Pro (seat), Tracxn.[salesrobot.co](https://www.salesrobot.co/blogs/crunchbase-review?share_frome=aipt)[tracxn.com](https://tracxn.com/pricing?share_frome=aipt)[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt)
   - Automatable: Yes. Fundable is built for programmatic access; others are more enterprise.  
   - Costs: Fundable Hobby/Pro at $20–50/month plus $0.05/credit API usage.[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt)
   - Pain evidenced: none directly, but strong **timing and priority context**: new finance leadership, expansions, post‑funding scale‑up where automation projects are likely to be funded.

3. **Review‑site scraping across multiple platforms**  
   - Tools: Apify’s multi‑platform review scraper (G2, Capterra, Trustpilot, Gartner, Reddit).[apify.com](https://apify.com/focused_vanguard/multi-platform-reviews-scraper?share_frome=aipt)[apify](https://apify.com/automation-lab/g2-scraper?share_frome=aipt)
   - Automatable: Yes, easily at 20 domains/day. Actors accept domains and return structured reviews with dates.  
   - Costs: Apify usage from roughly $1–1.50 per 1,000 reviews depending on actor; free tiers exist for low volume.[apify.com](https://apify.com/zen-studio/g2-reviews-scraper/api/python?share_frome=aipt)[apify.com](https://apify.com/zen-studio/g2-reviews-scraper?share_frome=aipt)
   - Pain evidenced: direct complaints about tools, including “manual reconciliation,” “spreadsheet exception handling,” “slow month‑end.”

4. **Vendor usage and customer evidence (case studies, logos, marketplaces)**  
   - Tools: None specialized; teams use Exa/Tavily/Brave/Serper to search vendor sites and marketplaces.[api-dashboard.search.brave.com](https://api-dashboard.search.brave.com/api-reference/web/search/get?share_frome=aipt)[exa](https://exa.ai/docs/reference/migrating-from-bing?share_frome=aipt)[raw.githubusercontent.com](https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?share_frome=aipt)[exa.ai](https://exa.ai/docs/sdks/typescript-sdk-specification?share_frome=aipt)[docs.tavily.com](https://docs.tavily.com/documentation/best-practices/best-practices-search?share_frome=aipt)
   - Automatable: Yes; your volume is tiny compared to these tools’ capacity.  
   - Costs: as in the search API section.  
   - Pain evidenced: when vendors make “before/after” claims involving manual finance/ops workflows.

5. **Product usage telemetry and “powered by” signals**  
   - Tools: web‑stack detectors and custom scraping of “powered by” badges (e.g., “Powered by Stripe,” “Runs on NetSuite”) on checkout and login pages.[whatstack.ai](https://whatstack.ai/technologies/ecommerce-payments/payment-processor?share_frome=aipt)[datafragment.com](https://www.datafragment.com/resources/free-technology-lookup-tool?share_frome=aipt)
   - Automatable: Yes; primarily HTML parsing.  
   - Pain evidenced: stack composition and complexity; again, this supports Pain 1 and Pain 2 as complexity proxies.

Tools like **TheirStack** (job‑posting technographics) and hiring‑signal platforms are widely used by outbound teams, but they rely on job‑description mining and are therefore excluded under your constraints.[theirstack.com](https://theirstack.com/en?share_frome=aipt)[theirstack.com](https://theirstack.com/en/docs/guides/how-to-find-companies-by-technology-stack?share_frome=aipt)[theirstack.com](https://theirstack.com/en/technographic-signals?share_frome=aipt)[predictleads.com](https://predictleads.com/blog/outbound-buying-signal-tools/?share_frome=aipt)

***

## Part 6 – Single purchase that most improves prospect quality at 5–20 prospects/day

Given your constraints (no LinkedIn/job boards, modest daily volume, need for **specific, evidence‑led pains**), the **single highest‑impact purchase** is:

### Fundable – self-serve funding & leadership-change API

- **What it gives you:**  
  - Programmatic access to funding rounds, investor relationships, and leadership changes (new CFO/COO/Vice President roles) across startups and mid‑market companies.[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt)
  - A self‑serve API with credit‑based usage starting at **$0.05 per credit**, with **200 free credits** and paid plans from **$20/month (Hobby)**, **$50/month (Pro)**, **$100/month (Pro+)**.[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt)
  - MCP server integration on Pro+ for agent workflows.

- **Why it improves prospect quality:**
  - Funding and new finance leadership are **high‑leverage timing signals** for the exact pains you sell against: post‑funding process overhauls, new leaders tasked with “fix manual close,” “automate reconciliation,” “scale ops without linear headcount.”  
  - For each prospect, you can reliably answer: “Is this company at a change moment where my automation pitch is credible right now?”  
  - Your agent can combine Fundable events with tech‑stack complexity and review evidence to construct stronger narratives: “After your Series B and hiring a new CFO, you’re expanding PSP coverage across 3 regions; we automate the month‑end reconciliation workload that grows with each PSP.”

- **Cost at your scale:**
  - At 20 companies/day (~600/month), even 3–5 credits/company (funding + leadership queries) keeps you comfortably in the Hobby/Pro tier; arithmetic is straightforward because credit prices are explicit.[tryfundable.ai](https://www.tryfundable.ai/blog/harmonic-vs-fundable?share_frome=aipt)
  - Crucially, **pricing is self‑serve, not “Contact Sales”**, unlike Crunchbase or Harmonic.[prospeo](https://prospeo.io/s/harmonic-pricing-reviews-pros-and-cons?share_frome=aipt)[pipeline.zoominfo](https://pipeline.zoominfo.com/sales/crunchbase-api?share_frome=aipt)[tryfundable.ai](https://www.tryfundable.ai/blog/crunchbase-api-alternatives?share_frome=aipt)

If you only buy **one** thing, Fundable (or an equivalent self‑serve funding/leadership API) will give you **far more reliable timing and ICP alignment** than any single technographic tool, and combines well with free/cheap review and tech‑stack scraping.

***

## Part 7 – Pains that are not reliably observable without job postings

To avoid self‑deception, here’s an honest assessment:

1. **Ops headcount scales linearly with transaction volume (Pain 3)**  
   - Without LinkedIn and job postings, you have no direct view of headcount or how it scales against volume.  
   - Complexity proxies (PSP count, multi‑system stack, growth signals) hint that ops could be under pressure, but you cannot distinguish “we hired 5 automation engineers and kept ops flat” from “we hired 20 ops analysts.”  
   - Verdict: **not reliably observable**. You can still pitch “scale ops without scaling headcount,” but you should treat it as a *generic benefit*, not an evidence‑driven pain per prospect.

2. **Exceptions get handled in spreadsheets with no audit trail (Pain 4)**  
   - You can sometimes detect this via explicit complaints in reviews or blogs, but for most private mid‑market companies there will be **no public mention**.  
   - Without job descriptions spelling out “exceptions handled in Excel,” you’ll usually have no observable signal.  
   - Verdict: **observable only in rare cases** (when you find direct text). As a general, per‑prospect pain, it’s **not reliably observable**.

3. **Month‑end close drags because matching is manual (Pain 1)**  
   - This is **partially observable**: you can detect  
     - direct complaints in reviews and content,  
     - case studies describing manual close pre‑automation,  
     - and stack complexity as indirect evidence.  
   - But for many companies, you’ll have no concrete signals—only generic growth/event signals.  
   - Verdict: **keep Pain 1**, but design your agent to **SKIP** claiming it when no direct evidence (reviews/case studies/status incidents/blog text) is found.

4. **Payment, ledger, and bank reconciliation breaks silently and surfaces late (Pain 2)**  
   - You can observe **visible** reconciliation issues (status incidents, outage news, some reviews), but “silent breaks that surface late” are, by definition, not publicly exposed.  
   - Verdict: **partially observable**. Pitch “we reduce reconciliation errors and delays” only when you have some incident or complaint evidence; otherwise treat it as a generic benefit.

In practice, your **evidence‑led pain set** for private mid‑market companies without job posting data should prioritize:

- Pain 1: Slow, manual month‑end close across multiple systems – **use when reviews/case studies/blogs mention it or complexity is extreme.**  
- Pain 2: Visible reconciliation and payout issues – **use when status incidents, reviews, or news exist.**  

And treat:

- Pain 3 (linear headcount scaling) and Pain 4 (spreadsheet exceptions) as **generic value props**, not per‑prospect “observed pains,” unless you have explicit textual evidence for a given company.

***

## Summary of `observable_via` conditions you can implement

For your agent, a practical concrete list of `observable_via` checks per prospect could be:

1. **Review-based conditions** (via G2/Capterra/TrustRadius scrapers):  
   - `has_review_reconciliation_pain(company_domain)`  
   - `has_review_month_end_pain(company_domain)`  
   - `has_review_spreadsheet_exceptions(company_domain)`

2. **Case-study conditions** (via Exa/Tavily search):  
   - `has_vendor_case_study(company_name, keywords = ["month-end close", "manual reconciliation", "spreadsheet exceptions"])`  
   - `has_vendor_case_study(company_name, keywords = ["payouts delayed", "settlement reconciliation", "bank reconciliation"])`

3. **Status-page conditions**:  
   - `has_recent_status_incident(company_domain, keywords = ["payout", "settlement", "reconciliation", "ledger discrepancy", "double charge"])`

4. **Tech-stack complexity conditions** (via StackDetector/DataFragment/WhatStack/BuiltWith):  
   - `payment_processor_count(company_domain) >= 3`  
   - `erp_system_count(company_domain) >= 2`

5. **Event conditions** (via Fundable/funding API):  
   - `has_recent_funding(company_name, within_months = 24)`  
   - `has_recent_finance_leader_change(company_name, within_months = 24)`

6. **Content conditions** (via Exa/Tavily/Brave):  
   - `has_public_content(company_name, role = finance/ops, keywords = ["month-end close", "manual", "Excel", "spreadsheet", "reconciliation"])`

Your agent can then:

- **Attach pains only when corresponding `observable_via` conditions are true.**  
- **Skip drafting** when only generic signals (funding, tech‑stack complexity) are present, to avoid hallucinated specificity.  

This should let you rebuild your evidence map without going back to job postings or LinkedIn, while being honest about what you can and cannot see.

---

# Verification notes (Claude, 2026-08-24)

Added after reading. Nothing below is confirmed against a primary source unless marked.

## RED — the headline recommendation is weakly sourced

**"Fundable" (`tryfundable.ai`) is named the single best purchase, and every citation for it points at its own blog.** The comparison articles cited (`harmonic-vs-fundable`, `crunchbase-api-alternatives`) are vendor-authored marketing content — exactly the pattern that produces confident recommendations for products that barely exist. **Confirm the company is real, funded, and has the API described before spending anything.** Cheap to check; do it first.

Same sourcing weakness applies to:
- **Harmonic "~$25K/year, 3-seat minimum"** — cited to `quotaengine.com`, `prospeo.io`, `apis.io`, not Harmonic.
- **Crunchbase "$99/mo, API behind Enterprise"** — cited to `marketintelligencetools.com`, not Crunchbase.
- **StackDetector "$9.50 per 1,000 scans"**, **WhatStack / DataFragment "200–315 payment processors detected"** — vendors I cannot independently corroborate.

Directionally these may be right. None is a number to plan a budget around.

## GREEN — concrete, testable, and the most valuable part of the document

**Date-filter parameters, all checkable against keys we already hold:**
- Exa: `startPublishedDate` / `endPublishedDate`
- Tavily: `time_range`, plus absolute `start_date` / `end_date`
- Brave: `freshness` (`pd` / `pw` / `pm` / `py`, or `YYYY-MM-DDtoYYYY-MM-DD`)

This directly fixes D21 (17–26% of cards had a parseable date; Tavily 0/32) **at the source** rather than by post-filtering. Highest value, lowest risk, costs nothing to verify.

**Snippet windowing:** Tavily returns chunked, match-centred content; Exa exposes tunable highlights. This is the property measured at `HANDOFF.md:103` as the difference between a 0.00 and a 0.80 relevance score on the same document. Also testable with existing keys.

**Exa vs Tavily verdict:** keep both, different jobs — Tavily as default evidence fetcher, Exa as precision drill for hard queries and person disambiguation. Reasonable, and consistent with `HANDOFF.md:81` ("unscoped Exa is noise, scoped Exa is precise").

## The finding that matters most — and it is free to test

**Its #1 ranked signal is staff-authored G2 / Capterra / TrustRadius reviews, retrieved via Apify actors. We already own that fetcher and never fire it.**
`zara/fetchers/apify.py:150-153` — `ApifyG2CapterraFetcher` → `zen-studio/software-review-scraper`, sitting at **rung 4**, so it only runs in deep mode and is skipped entirely whenever the gap-filler gate trips (D4). `HANDOFF.md:110` confirms all 16 actor IDs resolve. The top-ranked recommendation in this research is a source that is already built, already paid for, and switched off by default.

## Confirms the warning I raised before the ruling

Part 7 reaches this independently, with the no-job-postings constraint imposed:

| Pain | Verdict without job postings |
|---|---|
| `close_drag` — month-end close drags | **Partially observable** — only when reviews / case studies / blogs say so |
| `silent_breaks` — reconciliation breaks silently | **Partially observable** — "silent breaks that surface late are, by definition, not publicly exposed" |
| `linear_headcount` — ops headcount scales with volume | **Not reliably observable** |
| `spreadsheet_exceptions` — exceptions in spreadsheets | **Not reliably observable** |

Two of four pains become undetectable, two degrade to conditional. This is an argument from absence rather than a sourced claim, so it is not subject to the hallucination risk above — and it matches what I flagged before the ruling was made.

Its own recommendation: demote `linear_headcount` and `spreadsheet_exceptions` from per-prospect observed pains to **generic value props**, and have the agent skip claiming a pain when no direct textual evidence exists. That second half is Compass I and IV restated, and is the right shape.

Note the remaining detectable signals cluster on funding, new finance leadership, and expansion — i.e. `structural_complexity`, the fifth pain, whose `observable_via` never depended on job ads. The pain list risks collapsing toward that single detectable pain, which is the outcome to design against.
