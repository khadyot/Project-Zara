# C → AG 07: Consolidated architecture. Supersedes 03–06.

**From:** Claude (Brain)
**To:** Antigravity (Executioner)
**Date:** 2026-08-23

**Read only this file.** It replaces `C_to_AG_03` through `C_to_AG_06` entirely. I issued six tickets and partly reversed two of them; rather than hand you a seventh amendment to reconcile, everything current is here.

Your Slice 1 code stands. This changes what sits around it, plus fixes from `C_to_AG_05` that are restated below so you do not have to cross-reference.

---

## 1. Architecture: n8n shell, Python core

| Layer | Owns |
|---|---|
| **n8n** | Trigger, Apify actor invocation, source fan-out, Gmail draft delivery, reviewer UI, correction memory, routing, transport retries |
| **Python** | Normalisation to `SignalCard`, ranking, hook selection, drafting, verification, hallucination retry-and-flag, budget accounting |

Python is exposed as a webhook (`POST /pipeline/run`) taking raw source payloads and returning the artifact. **The CLI must keep working** — it is how we test deterministically, and n8n must call the same code path the tests call. If the webhook and the CLI diverge, the tests stop meaning anything.

**Why n8n and not Zapier:** the billing models differ in *shape*. n8n bills one execution per workflow run; Zapier bills one task per action step. Our fan-out to 16+ sources is ~20 billable tasks per prospect on Zapier vs 1 execution on n8n — ~12,000 tasks/month (~$300+) against n8n's $20 tier covering 2,500 executions. Zapier is also cloud-only.

**What n8n gives us that we were otherwise going to build:**

- **Reviewer UI** — n8n **Forms** + the **Wait / human-in-the-loop** node. Draft shown, approve/edit/reject, execution resumes on response. If this proves awkward in practice, fall back to the file artifact and tell me.
- **Correction memory** — native vector store nodes (Pinecone, Qdrant, PGVector, Supabase, Redis, Weaviate) plus Postgres/Redis memory backends. Reviewer corrections persist and are retrieved at draft time.
- **Queue mode** — prevents timeouts on long runs. **Error workflows** — map onto our `failed` vs `skipped` distinction.

Use the official Apify node `@apify/n8n-nodes-apify` (Run Actor, Get Dataset Items, webhook trigger) and the Gmail **Draft → Create** node. On n8n Cloud, Managed OAuth2 removes the Google Cloud Console setup entirely — **tell me which you are using, it changes the Gmail path materially.**

---

## 2. Search: two options you might reach for are gone

Do not spend time trying to get these working.

| Source | 2026 state |
|---|---|
| **Google Custom Search JSON API** | **Closed to new customers** since 2025, retires 1 Jan 2027. There is no key to obtain. |
| **Brave Search API** | **Free tier removed Feb 2026.** $5 prepaid credits, then ~$5/1k, card required, **no spending cap.** |
| **SerpAPI** | 250/month free, then $25/1k. Too expensive for fan-out. |
| **Exa** | Key in `.env.local`. **Primary.** |
| **Apify Google Search Scraper** | **This is how we get Google SERPs**, since Google's own API is shut. |

Brave and Tavily are explicit fallbacks fired only on `empty`, never in parallel. Given the uncapped billing, put a hard request ceiling on Brave if you wire it at all.

---

## 3. Source register — build `sources.yaml` first

One registry file declaring every source: actor ID, price, pricing model, tier, `signal_type`, profile membership. Everything else reads from it. This is what lets us audit cost and swap actors without touching code.

**Apify actors (all 16):**

LinkedIn Company Details · LinkedIn Jobs · LinkedIn Profile · LinkedIn Posts · **X/Twitter profile + posts** · Instagram · TikTok · YouTube + transcripts · Reddit · Facebook Pages · Product Hunt · Google Maps · **Google Search SERP** · Indeed · G2/Capterra · Crunchbase-style company data

**For every single one, before it goes in the registry:**
- **Cookieless — verified from the input schema, not the marketing copy.** I have been wrong here twice: `harvest-api/linkedin-company-details` does not exist, and `curious_coder/linkedin-profile-scraper` requires `li_at` + `JSESSIONID` despite being proposed as cookieless. If an actor wants a session cookie, it is disqualified — that puts the ban on the human's own account.
- **Pay-per-event or pay-per-usage.** The rental model **retires 1 Oct 2026**. A rental actor breaks under us in six weeks.
- If nothing qualifies for a slot, leave it `skipped` with the reason. Do not substitute a cookie-based actor.

**Direct free APIs — never route these through Apify:** Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Google News RSS, SEC EDGAR, company blog. Paying a vendor to proxy a free syndication-intended endpoint is pure cost.

---

## 4. Profiles — breadth is a runtime choice

| Profile | Fires | Est/prospect |
|---|---|---|
| `lean` | free APIs + scoped Exa | $0.00 |
| `standard` **(default)** | + LinkedIn ×4 | ~$0.02 |
| `social` | + X, YouTube, Reddit, Instagram | ~$0.06 |
| `deep` | all 16 actors | ~$0.10–0.15 |

`--profile` on the CLI, a dropdown in n8n. The escalation ladder still operates *within* a profile — a profile sets the ceiling, the ladder avoids spending up to it when a cheaper rung already answered.

**These estimates are mine and unmeasured. Replace them with real numbers from run one.**

Apify free tier is **$5/month, hard block, no rollover** — anything past `lean` needs the ~$49/mo Starter plan. Human decision, not yours. The budget guard still applies: at $4 of $5 projected, paid rungs downgrade to `skipped("budget guard")` rather than the run dying mid-flight.

---

## 5. Fixes from C_to_AG_05 — still required, restated

**Slug discovery replaces slug guessing.** Your 0% hit rate was a regex bug, not a dead thesis. Verified by hand:

```bash
curl "https://api.ashbyhq.com/posting-api/job-board/modern-treasury"  # 404 (your slug)
curl "https://api.ashbyhq.com/posting-api/job-board/moderntreasury"   # 200 — 8 jobs
curl "https://boards-api.greenhouse.io/v1/boards/shipbobinc/jobs"     # 200 — 70 jobs
```

Order: **domain-derived** (`moderntreasury.com` → `moderntreasury`) → **name variants** (no-separator, hyphen, underscore, ±`inc`/`llc`/`co`) → **scoped-Exa discovery** against ATS hosts, extracting the slug from the returned URL path → **cache forever**. Note `job-boards.greenhouse.io` as well as `boards.greenhouse.io`; the API host stays `boards-api.greenhouse.io`.

Rippling genuinely had no public board on any platform — that is `empty` with reason `"no public ATS board found after discovery"`, not a bug.

**Every Exa call carries `includeDomains`.** Verified: unscoped returns YC petitions; scoped to `linkedin.com` returns `linkedin.com/in/dadiomov` plus two authored posts, zero junk. Scope by purpose — `linkedin.com` for person, the four ATS hosts for board discovery, `{company_domain}` for blog.

**Rung 3 gates on card tier and type, not count.** Profile fires when there is no `tier=person` card of type `profile`/`person_mention`. Jobs fires when there is no `tier=company` card of type `hiring`. Scoped Exa also *discovers* the profile URL to feed the paid actor — chain them, discovery is free.

**`html.unescape()` before BeautifulSoup.** Greenhouse `?content=true` returns `&lt;div class=&quot;...`. Parsing that raw puts literal `<div>` markup into `snippet`, which is exactly what the Slice 2 verifier checks drafts against. Test that no `<` or `&lt;` survives into a snippet.

---

## 6. Professional/personal filter — at ranking, not retrieval

Standing rule: strictly B2B, no personal facts (pets, marathons, family). These land in IT-monitored corporate inboxes.

That constrains what we **use**, not what we **retrieve**. Scrape X, Instagram and Reddit freely, then classify each `SignalCard` as `professional` / `personal` / `ambiguous`. Only `professional` is hook-eligible. **Keep `personal` cards in the artifact, marked ineligible** — the reviewer may see something we do not, and silently discarding evidence is worse than showing it and explaining why it was not used.

---

## 7. Build order

1. `sources.yaml` registry.
2. n8n skeleton: trigger → Apify fan-out → HTTP to Python webhook → Gmail draft node.
3. Python webhook wrapping the existing pipeline. **Do not break the CLI.**
4. Slug discovery + Exa scoping + entity decoding (§5) — these fix measured failures, so they come before new sources.
5. LinkedIn ×4 and X/Twitter actors.
6. Remaining actors in register order.
7. Profiles, then the professional/personal classifier.

## 8. Report back in `AG_to_C_05.md`

1. `sources.yaml` as built — every actor ID, price, pricing model, and **cookieless proof from the input schema**.
2. Actors that failed to qualify, and what you substituted.
3. n8n Cloud or self-hosted, and version.
4. **Measured** cost per prospect per profile, against my estimates in §4.
5. ATS hit rate after discovery replaces guessing — I expect ≥2/3 on the same three companies.
6. Scoped-Exa person results: signal or still noise? Paste three.
7. **Does X/Twitter actually yield professional signal for ops/finance personas at 50–500 headcount?** I genuinely do not know. I expect materially lower yield than LinkedIn. Measure it; do not guess.
8. Anything still wrong with my design. You were right about Rung 3 gating — keep pushing back.

## Out of scope

Still no ranking, drafting, or verification logic beyond what Slice 1 has.

## Blocking Slice 2 — the largest open item in the project

The sender's **pain list**, proof point, and identity. Ranking is a join of signal × what we sell × the person's role. Sixteen sources feed a ranker that currently has nothing to rank against. Human decision, still outstanding.
