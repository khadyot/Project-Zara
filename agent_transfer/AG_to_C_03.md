# Human Bridge: Transfer AG -> C (Execution Complete)

## Objective
Slice 1 (Retrieval Subsystem) is complete. The Python environment, `zara` module, fetchers, strict types, budget guard, and probe script are built and tested. 

## Report: Real World Probe Results

I ran `zara/probe.py` against three ICP companies: Modern Treasury (Dimitri Dadiomov), ShipBob (Jinal Jhaveri), and Rippling (Parker Conrad).

**1. Per source, per rung (Status & Cards):**
- **[Rung 0] ATS Boards (Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee):** All returned `EMPTY` (404 no board found or no open jobs). 0 cards.
- **[Rung 0] GoogleNewsRSS:** `OK` (after fixing an SSL cert issue using `httpx`). Returned 3 cards per prospect.
- **[Rung 1] ExaSearch:** `OK`. Returned 2 cards per prospect.
- **[Rung 2] HarvestApiCompanyFetcher:** `FAILED`. The actor `harvest-api/linkedin-company-details` does not exist on Apify (404). 
- **[Rung 3] GetLeadsProfileFetcher:** `SKIPPED`. Reason: "cheaper rung succeeded". 
- **[Rung 4] ApifyGoogleSearchFetcher:** `SKIPPED`. Reason: "cheaper rungs succeeded" (unless forced with `--deep`).

**2. ATS Slug Hit Rate:**
0% hit rate across all 5 platforms for these 3 companies. The slug guessing `re.sub(r'\s+', '-', name).lower()` is too naïve. Companies use custom domains (careers.rippling.com) or completely different slugs.

**3. Cost per prospect:**
$0.000. The free tier (News + Exa) survives and provides cards. Paid rungs didn't charge because they either failed (missing actor) or skipped due to the budget guard's escalation logic.

**4. Did Rung 3 trigger correctly?**
**No, and this is a design flaw in the ticket.** The ticket states: *Rung 3 fires only when cheaper rungs come back thin.* Because ExaSearch (Rung 1) always returned *something*, Rung 3 (Profile) was skipped. But Rung 1 returns news/mentions, NOT structured profile data. 

**5. Are Exa results signal or noise?**
**Noise.** Exa returned aggregator junk and broad mentions: Forbes profile snippets, Wikipedia stubs, and YCombinator petitions. It did not return structured LinkedIn data.

**6. Greenhouse jobs?**
All returned `EMPTY`, so we didn't get any job descriptions. (The BS4 parsing is implemented strictly to `.get_text(strip=True)` verbatim).

**7. Apify Actors Chosen:**
- **Rung 2:** `harvest-api/linkedin-company-details` (Pay per event, but doesn't exist).
- **Rung 3:** `get-leads/linkedin-scraper` (Cookieless mode, pay per event $0.004).
- **Rung 4:** `apify/google-search-scraper` (Pay per event $0.005).

**8. Verbatim Cards (Examples):**
*Good (News):*
```
[GoogleNewsRSS] COMPANY | NEWS
Claim: In the news: ShipBob Launches First Anthropic-Verified Fulfillment Connector...
URL: https://news.google.com/rss/articles/...
Snippet: ShipBob Launches First Anthropic-Verified Fulfillment Connector, Anchoring its AI Suite PR Newswire...
```

*Bad/Noise (Exa):*
```
[ExaSearch] PERSON | PERSON_MENTION
Claim: Mentioned on: Urgent: Sign the petition now | Y Combinator
URL: https://www.ycombinator.com/blog/urgent-sign-the-petition-now...
Snippet: Urgent: Sign the petition now | Y Combinator
March 11, 2023·by Y Combinator
Over 5,000 CEOs and founders representi...
```

**9. Pushback / Design flaws:**
1. **Gating Rung 3 on Rung 1 is wrong.** Exa returns news/PR noise, not profile data. If we need a LinkedIn profile to write a good email, Rung 3 must be decoupled from Rung 1's success.
2. **ATS slug guessing is useless.** We either need a Clearbit/Apollo enrichment step to get the exact ATS URL, or we should drop Rung 0 ATS fetchers and just rely on Google Search (Rung 4) to find the careers page.
3. **Harvest API actor is missing.** We need a real cookieless firmographic actor for Rung 2.

## Handoff
All code is in `/zara/` and tests pass. Awaiting Slice 2 (Rank, Draft, Verify) instructions.
