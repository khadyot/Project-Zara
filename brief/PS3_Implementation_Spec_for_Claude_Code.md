# PS-3 Implementation Spec: Single-Prospect Outreach Research & Drafting Agent

This file is the build spec for the Zamp AI Solutions Associate case study, Problem Statement 3 (GTM). It's written for an implementing agent (Claude Code) to work from directly. Where a decision is marked OPEN, ask before assuming. Everything else here is DECIDED — do not silently reopen a decided item; if you think it's wrong, say so explicitly and ask.

## What this system does

Given one prospect (name, company, LinkedIn URL, or similar identifying input), the system:
1. Researches the prospect and their company for genuine, verifiable signal
2. Judges which signal, if any, is actually worth leading with
3. Drafts a personalized outreach message grounded in that judgment
4. Surfaces everything transparently in a run view, never auto-sends
5. Logs the run to a dashboard showing history, status, and outcomes across runs

The case study guide explicitly requires: a live run view showing each stage as it executes, and a dashboard showing history/status/outputs across runs. Both are graded, not optional polish.

## Core design principle (build this correctly before anything else)

**The system must be able to say "I don't have enough to personalize this confidently" rather than fabricate.** This is the single most load-bearing design decision in the entire build. Every downstream architecture choice should protect this property.

## Pipeline stages

```
[Prospect input: name + company, at minimum]
  → 1. Identity resolution (confirm the person, current role, current company)
  → 2. Suppression check (is this person already an active customer, mid-deal, or on a do-not-contact list? Tied to CRM deal-stage/engagement state in real tools — fake it here, but fake it as this named, standard practice.)
  → 3. Enrichment (company + contact firmographic data — see Data Source Strategy below)
  → 4. Signal discovery (bounded AI research step — see Signal Record schema and Data Source Strategy below)
  → 5. Signal scoring + ranking (apply the hook-ranking rule)
  → 6. Confidence gate (this is the anti-fabrication core — see below)
  → 7a. [If gate passes] Angle selection → draft generation
  → 7b. [If gate fails] Route to "needs human judgment" state, do not draft
  → 8. Output: draft + full reasoning trail, surfaced in run view, logged to dashboard
```

Step 2 is easy to skip and shouldn't be. It's cheap to fake (a small local list of "existing contacts" to check against) and it's exactly the kind of unglamorous operational detail that separates a considered build from a toy one — this is standard, named practice ("suppression list handling") in every real outreach tool, not an invented nicety.

Step 4's research agent should be explicitly bounded and required to produce "no evidence found" as a valid, expected output, not just a safety fallback: constrain scope to the company domain and named public pages/APIs (see Data Source Strategy), cap page/call count, and treat absence of evidence as a first-class result the prompt is built to produce.

## The hook-ranking rule (locked, do not deviate without asking)

Rank candidate signals in this order, highest priority first:

1. **Authored content** — a LinkedIn post, an interview quote, a conference talk, anything the prospect or their company chose to say publicly and recently.
2. **Observed business events** — funding round, hiring spike, leadership change, product launch. True, but not something they chose to reveal; treat as supporting evidence, not the lead.
3. **Static firmographic data** — industry, company size, headcount. Never a standalone hook. Context only.

The primary hook in a draft should always be the highest-ranked signal type available. Lower-ranked signals may appear as one supporting line, never as the headline, and never combined into a single opening sentence (avoid the "personalized-opener-generic-offer" failure mode by keeping the connection between hook and pitch explicit and singular).

## The confidence gate (anti-fabrication core — build this first, build it well)

Score the prospect on two separate axes, don't collapse them into one number from the start:

1. **ICP fit** (1-3): good fit / somewhat / not a fit, with a stated reason attached.
2. **Signal strength** (0-3): independent of fit, how much verifiable signal was actually found.

Combine using this lookup table (CONFIRMED, not open):

| ICP Fit | Signal Strength | Gate Result |
|---|---|---|
| Good fit (1) | Strong (2-3) | Pass — generate personalized draft |
| Good fit (1) | Weak (0-1) | Needs human judgment |
| Somewhat fit (2) | Strong (2-3) | Pass, but flag for review before send |
| Somewhat fit (2) | Weak (0-1) | Needs human judgment |
| Not a fit (3) | Any | Needs human judgment — don't draft outreach to a bad-fit prospect regardless of signal |

**Signal decay — DECIDED:** any signal with `recency_days > 30` has its `confidence_score` halved (rounded down) before it feeds the lookup table above. Applies per-signal during scoring (stage 5), not as a separate step. `decayedScore = recency_days > 30 ? Math.floor(confidence_score / 2) : confidence_score`. The Priya Nair fixture (45-day-old hiring post, `confidence_score: 1`) decays to 0, correctly landing in the weak-signal band without a special case.

If the result is "Needs human judgment":

- Route the record to a "needs human judgment" state
- State the reason plainly and visibly: e.g., "No authored signal found. Only firmographic data available."
- Do not silently discard, and do not force a weak personalization through

This state should be visually distinct in the run view and dashboard, it's not a failure, it's the system correctly exercising judgment. Treat it as a feature to show off in the demo, not something to hide.

**Stretch goal, build only if MVP is solid and time remains:** add a second, post-generation verification pass. After a draft is generated, check every factual claim in it against the actual source material gathered in step 4. Anything that can't be traced back to real evidence gets flagged or stripped before the draft is shown. This is a stronger architecture than the pre-generation gate alone, but it's additive complexity, do the simple version first.

## Data schema

### Signal record
```
{
  signal_type: "authored_content" | "business_event" | "firmographic",
  subtype: string,          // e.g. "linkedin_post", "x_post", "funding_round", "hiring_post", "industry"
  content: string,          // the actual evidence, quote or paraphrase
  source_url: string,
  source_method: "web_search" | "firecrawl" | "x_api" | "people_data_labs" | "bright_data" | "youtube_api" | "podcast_api" | "github_api" | "manual_fixture", // how this signal was obtained — required, feeds the reasoning trail
  event_date: date,
  recency_days: int,
  confidence_score: number, // 0-3 or similar
  relevance_note: string    // why this might matter to this contact specifically
}
```

### Draft record

**Schema amendment (DECIDED, T2):** the original 2-value `gate_result` only modeled the stage-6 confidence-gate outcome, with no way to represent an earlier halt (stage 1 identity failure, stage 2 suppression) — both need to show up in the run view/dashboard the same way a gate failure does (halted, reason stated, no draft), but conflating "halted before the gate ran" with "the gate itself said needs_human_judgment" is a real ambiguity risk for anything branching on this field later (T4/T6/T7). Fixed by widening `gate_result` and adding an explicit `halted_at_stage` field so the two cases are never confusable:

```
{
  prospect_id: string,
  primary_signal: SignalRecord | null,
  supporting_signal: SignalRecord | null,  // optional, at most one
  gate_result: "passed" | "needs_human_judgment" | "suppressed" | "identity_unresolved",
  gate_reason: string,       // required whenever gate_result !== "passed" — states why, at whichever stage
  halted_at_stage: PipelineStage | null, // null iff gate_result === "passed". Disambiguates "halted before stage 6" from "stage 6 gate returned needs_human_judgment"
  draft_subject: string | null,
  draft_body: string | null,
  reasoning_trail: string[], // human-readable log of each pipeline stage's output, for the run view
  status: "drafted" | "pending_review" | "approved" | "rejected" | "halted", // "halted" is the terminal state for suppressed/identity_unresolved runs specifically
  created_at: timestamp
}
```

```
// PipelineStage — names all 7 stages, used by halted_at_stage above and by T6's
// "which stage is running now" display. PipelineStageEvent is the lightweight,
// transport-agnostic shape T3-T6 share for stage progress; T6 decides how it's
// actually streamed (SSE), this is just the vocabulary.
type PipelineStage = "identity_resolution" | "suppression_check" | "enrichment" | "signal_discovery" | "scoring" | "confidence_gate" | "drafting";
type PipelineStageEvent = { stage: PipelineStage; status: "running" | "complete" | "halted"; message: string; timestamp: string };
```

**Error-handling principle (DECIDED, applies from T2 onward):** every pipeline stage function returns a typed result (a discriminated union / ok-or-reason shape), never throws for an *expected* failure mode (missing input, no signal found, upstream API error). Exceptions are reserved for genuinely unexpected bugs, not expected business outcomes.

**Sender offering (DECIDED, for T5's draft generation):** "We help operations teams automate manual, reconciliation-heavy processes" — reuses the assumption `PS3_Test_Fixtures.md` already states and flags as unresolved, so the LLM has one consistent offering to draft against instead of inventing a different one per run. Implement as a constant in `src/lib/config.ts` when T5 first needs it.

## Test fixtures

A separate file, `PS3_Test_Fixtures.md`, contains five synthetic prospects: one clean happy path, one per locked edge case, and one for the suppression check. Use these for local development and demo rehearsal rather than depending on live scraping returning fresh, predictable data during the actual interview. Includes a small fake CRM/suppression list for the existing-context check at pipeline stage 2.

## Edge cases to build and demo (locked, build a distinct test scenario for each)

1. **Hallucinated facts** — construct a test prospect where the available real data is sparse enough that a naive system would be tempted to invent detail. Verify the gate catches it.
2. **Real-signal-wrong-inference** — construct a test case where a real signal exists (e.g. a job posting) but the obvious inference is wrong (e.g. the role was already filled, or it's a backfill not an expansion). The system should either avoid the wrong inference or flag appropriate uncertainty.
3. **Personalized-opener-generic-offer** — construct a test case that would tempt a naive system into a strong hook followed by a disconnected generic pitch. Verify the draft generation stage explicitly connects hook to offer, not just juxtaposes them.

## Data Source Strategy (DECIDED — see `docs/research/data-source-strategy.md` for full primary-source citations)

**The verified finding:** no competitor fetches a stranger's LinkedIn data live, per-request, via a login-based automated account. Apollo built a warehouse over years of continuous crawling on its own infrastructure; Clay waterfalls across paid vendors, with licensed exports (e.g. Sales Navigator) rather than live scraping; Unify is largely first-party. LinkedIn's User Agreement explicitly prohibits automated scraping (Section 8.2), and LinkedIn sued and shut down Proxycurl — the leading third-party "LinkedIn data API" — in 2025 for exactly this (fake accounts, bulk resale). **Decision: no login-based / account-automation LinkedIn retrieval is built (rules out Apify/PhantomBuster-style actors and "connect your account" products like Unipile/Linked API for the live backend)** — that category carries real ban/breach-of-contract risk to whichever account is used and, for the account-connect products, a recurring subscription this project isn't paying for. **This does not rule out LinkedIn signal entirely** — see the LinkedIn subsection below for the two paths actually built (Bright Data for the live backend, manual/assisted sourcing for demo prep).

**Per source, per signal tier:**

- **Business events + firmographics (funding, hiring, launches, company facts) — live, low risk:**
  - Primary: Claude's native `web_search` tool. Covers press/news/blog content well; this is exactly what it's built for.
  - Firmographics specifically: add **People Data Labs** free tier (100 company lookups/month, no card) as a structured fallback/primary for headcount, industry, funding stage — more reliable than opportunistic web-search extraction. Requires a PDL account + API key in Vercel env vars (same-day setup, do this during T3, not demo day).
  - Optional free supplement: **GDELT** (no API key, global news index) as a zero-setup cross-check for business-event detection specifically.

- **Authored content, general web (blog posts, interviews, conference talks, press quotes, guest bylines/op-eds, Substack/newsletters) — live, low risk:**
  - Claude's native `web_search` tool finds candidate pages (search only, ~150-char cited snippets — not enough on its own to build a confident quote/paraphrase).
  - **Firecrawl** (`/scrape`) reads the full page once `web_search` finds the URL — converts it to clean text/markdown so the signal's `content` field is a real, complete excerpt, not a truncated snippet. Free tier: 1,000 credits/month, 1 credit/scrape — no subscription needed at this project's volume. Also use `/scrape` (or `/map` for multi-page) on a company's own blog/newsroom domain directly, rather than relying on opportunistic `web_search` hits for that specifically.
  - **YouTube Data API** (official, free tier) — conference talks/interviews that got uploaded.
  - **Podcast search** (e.g. Listen Notes API, free/cheap tier) — podcast appearances by name.
  - **GitHub** (official, free API) — for technical prospects: commits, repo READMEs, bio. Real authored signal, zero risk.

- **Authored content, X/Twitter — live, low risk (distinct from LinkedIn, do not bucket together):**
  - X has a real, self-serve, official pay-per-use API (no waitlist, ~$0.005-0.01/read) — unlike LinkedIn, this is genuinely usable live, on a name the system has never seen. **Build this as a live source in T3.** Requires an X developer account + payment method (same-day setup, do this during T3).

- **Authored content, LinkedIn — two distinct, intentional paths, both decided:**
  1. **Live backend (the deployed app, a cold name given at demo time): Bright Data's LinkedIn Scraper API, free tier.** Public-data-only, no login/credentials, no account to ban — 5,000 lookups/month free, ~$0.0015/lookup beyond that, no subscription. This is a deliberate, considered choice, not a last resort: it's meaningfully lower legal risk than any login-based option (no ToS-breach-by-account-holder theory applies, since there's no account), Bright Data has prevailed in court against similar claims from Meta and X Corp (though not tested against LinkedIn specifically — real but reduced risk, not zero), and it's the only LinkedIn option that's genuinely stateless and Vercel-serverless-compatible without a persistent session.
  2. **Demo prep (prospects deliberately researched ahead of the interview): manual sourcing, optionally assisted by an interactive session using the builder's own already-authenticated LinkedIn browser session** (e.g. Claude Code driving a real logged-in browser at human pace, one profile at a time — not an unattended automated backend process) to pull real content faster than typing it by hand. Zero new risk beyond ordinary personal browsing. Mark these Signal Records `source_method: "manual_fixture"`.
  
  **Explicitly evaluated and rejected: Apify/PhantomBuster-style login-based automation, and Unipile/Linked API-style "connect your account" products**, for the live/always-on backend specifically. Not because occasional personal use is unsafe (it may well not be, at low volume) — but because an unattended, publicly-triggered backend process is a materially different, higher-risk usage pattern than a human occasionally running a tool themselves, and Unipile/Linked API additionally cost a recurring subscription (~€49/mo minimum) this project isn't paying for. If `web_search`/Firecrawl/X API happen to surface real LinkedIn-originated content that made it into a general index, that's a legitimate bonus. Otherwise, LinkedIn-sourced authored-content signal is absent by default for a genuinely cold live name — this correctly pushes weak-signal cold-name runs toward "needs human judgment," which is intentional, demonstrable differentiator behavior, not a gap to hide.

**If this becomes more than a case study later:** the durable path for real, at-scale LinkedIn access is either buying into an existing licensed data warehouse (a Clay/Apollo-style vendor relationship) or an account-based API where a real logged-in user authorizes access (e.g. Unipile, Linked API) once ongoing subscription cost is acceptable. Not needed now.

## Tech stack

- **Frontend/backend:** Next.js + TypeScript on Vercel — CONFIRMED, already built (T1, committed to `main`). Not open.
- **Deployment target:** Vercel, confirmed.
- **Version control:** GitHub, confirmed.
- **Model:** Anthropic API access confirmed available. Per Apollo's own documented finding (blind-tested for their cold-outbound use case), a smaller, well-constrained model can outperform a larger one on latency and reliability for this kind of task — don't default to the biggest available model without reason.
- **Serverless execution — DECIDED, do not reopen without new evidence from T8 timing:** enable Fluid Compute and raise `maxDuration` (800s GA on Pro) rather than standing up a background-job queue (Inngest/Trigger.dev/Vercel Workflow) — a single-prospect, single-request pipeline doesn't need that complexity. Stream pipeline stage output to the client via SSE as it runs; this doubles as T6's live-updating run view. Only escalate to a job queue if real T8/T9 timing shows the config bump is insufficient.
- **New external accounts needed before T3 (same-day setup, not zero-setup — do not leave to demo day):** X developer account + payment method; People Data Labs free-tier account + API key; Bright Data free-tier account + API key; Firecrawl free-tier account + API key. All stored as Vercel env vars. All free-tier/pay-per-use, no recurring subscription required for any of them.
- **Test data:** Build and rehearse against the 5 synthetic fixtures (`PS3_Test_Fixtures.md`), fully controlled and independent of live search/API calls succeeding. Live search/APIs are real, shipped code paths (exercised in T3/T8), not a stretch goal — but the demo rehearsal should not depend on them succeeding live in front of an interviewer for the pre-selected fixture prospects. A prospect named live and cold by the interviewer legitimately exercises the live path end to end, including the "needs human judgment" outcome described above.
- **Automated testing — DECIDED:** each ticket from T2 onward ships with automated tests (not just manual/self-review) covering its stage(s) against the 5 fixtures and the 3 locked edge cases where applicable. T8 remains the full end-to-end + edge-case verification pass, but per-stage regressions should be caught by tests as they're built, not deferred entirely to T8.
- **Persistence — DECIDED:** run history (Draft Records + run metadata) is stored in **Vercel Postgres** (Neon-backed, provisioned via the native Vercel dashboard integration) — not local disk/SQLite (Vercel's filesystem is ephemeral, won't survive across invocations, not a real production deploy) and not client-only `localStorage` (dashboard must show history across sessions/devices — a graded requirement, not a nice-to-have). Add a `runs` table keyed by run ID: Draft Record fields plus run metadata (start/end time, prospect input, stage timestamps). Provision and wire up during T7.

## Explicitly out of scope

- Deliverability infrastructure (domain warming, spam avoidance, mailbox rotation) — this is a batch/volume problem, not relevant to a single-prospect build.
- Batch/list processing — the case study is explicitly single-prospect ("a rep names a target").
- Actual sending — human review gate is required before anything would go out; do not build a send capability.
- Login-based / account-automation LinkedIn retrieval for the live backend (Apify/PhantomBuster-style actors, Unipile/Linked API-style "connect your account" products) — see Data Source Strategy above for why, this was evaluated and explicitly rejected, not overlooked. (Bright Data's no-login public API and manual/assisted demo-prep sourcing ARE in scope — see Data Source Strategy.)
- Any paid subscription for a third-party data vendor — every source in this build runs on a free tier at this project's volume (People Data Labs, Bright Data, Firecrawl) or pay-per-use with no minimum (X API). If a source only offers a paid plan, it's not used.

## UI / Run View / Dashboard requirements (graded explicitly by the case study)

- **Run view:** show each pipeline stage executing in something close to real time — input received, identity resolved, signals found (list them with type/source/source_method), gate evaluated (pass/fail with reason), draft generated or routed to human-judgment state.
- **Dashboard:** history of past runs, status of each (drafted / pending review / approved / rejected), and enough detail per run to inspect why the system made the decision it made.

The reasoning transparency is not a nice-to-have, it's the mechanism that makes the "needs human judgment" state legible and demonstrable rather than a silent failure.
