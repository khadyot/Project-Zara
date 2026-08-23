<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

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

You can keep your stack as-is and still get a robust, demo-able pipeline: stream stage events over SSE using the Vercel AI SDK’s data parts, store runs on Neon’s free Postgres tier, and focus most of your remaining time on a visible confidence gate and failure handling rather than more data sources.[^1][^2]

Below is organized A / B / C, then “Things you did not ask about but should know.”

***

## A. Streaming multi‑stage pipeline progress

### A1. Current best practice, August 2026 — what people actually use

On Vercel/Next.js, SSE is still the underlying transport for long‑running, streaming interactions; WebSockets are used mainly when you need bidirectional, low‑latency channels (chat, games), not for single-request pipelines like yours.[^3]

The current recommended abstraction for AI work on Vercel is the **AI SDK v5** (`ai` + `@ai-sdk/anthropic` and `@ai-sdk/react`), which defines a **UI Message Stream** protocol (JSON SSE) consumed via hooks like `useChat`. This protocol explicitly supports both text streams and arbitrary “data parts” that can carry structured JSON about your pipeline stages.[^2][^4][^5][^6]

React Server Components streaming is for progressively delivering HTML during render, not long‑running JSON event streams; it’s widely used for content-heavy apps but not as the primary mechanism for multi-minute agent pipelines.[^7]

#### Options table — streaming layer

| Tool / pattern | What it does | Free / self-hostable | Maturity (2026) | TS support | Link | Date verified |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| Raw SSE via Next.js Route Handler | Hand-rolled `ReadableStream` that writes `text/event-stream` chunks with JSON payloads (e.g. `{stage, status, ts}`) | Fully free, self-hosted in your app | Very mature; standard HTTP + browser EventSource | First-class in TS / Fetch APIs | https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol (protocol reference, but raw SSE is standard) | 2025–2026 docs viewed Aug 2026[^6] |
| Vercel AI SDK v5 (UI Message Stream) | Higher-level SSE protocol with **typed message parts** (text + data), client hooks (`useChat`, `useCompletion`) and reconnection handling | Free SDK; you pay only for underlying model/API usage | Actively maintained; v5 released mid‑2025; current default for new AI apps | Strong TS types; custom `UIMessage` generics for data parts | https://vercel.com/blog/ai-sdk-5 | Jul 30 2025[^2] |
| WebSockets via external gateway (Pusher, Ably) | Persistent bidirectional channel; would carry stage events, not just text | Usually **paid monthly** beyond tiny free tiers → conflicts with no‑subscription constraint | Mature, but misaligned with your one‑shot pipeline | TS client SDKs exist, but add infra surface area | Vendor docs; e.g. Pusher pricing | General pattern; not re‑verified here (low confidence) |
| React Server Components streaming | Streams HTML/JSX during server render; good for “chat transcript appears gradually” UX | Free (built into Next.js) | Very mature for UI, but not designed for long-lived pipeline events | TS supported with Next.js App Router | https://nextjs.org/docs/app/building-your-application/routing/loading-ui-and-streaming | Pattern stable since 2024 (low relevance here) |

**Ranked recommendation (streaming):**

1. **Vercel AI SDK v5 UI Message Streams with custom data parts** for your run view: you already need the SDK for Claude calls, and it gives you a supported JSON SSE protocol, typed “stage events,” and reconnection-aware client hooks.[^5][^6][^2]
2. **Raw SSE route handler** if you want minimal dependencies: good fall-back and easy to reason about; the protocol is just `data: {...}\n\n` over a long-lived HTTP response.
3. WebSockets and RSC streaming are not a good fit for a single pipeline request that mostly sends server → client updates.

**Explicitly rejected:**

- **WebSockets on Vercel serverless** — requires an external WS broker or long-lived infra; your workload is one request with a unidirectional stream, which SSE already handles neatly.[^3]
- **RSC streaming as the primary event channel** — RSC streams the *render* of a component, not arbitrary multi-minute stage events; it complicates your mental model without solving your core problem.

**Confidence flags:** WebSocket rejection is high-confidence for your specific shape; RSC rejection is moderate-confidence (you *could* hack it in, but it’s off-path relative to current agentic best practice).

***

### A2. Streaming structured multi‑stage pipeline events (not just tokens)

The AI SDK v5 added **custom data parts** specifically to support non-token streaming: each SSE event can carry `{ type: 'data-*', id, data }`, where `data` is arbitrary JSON. The client’s `UIMessage.parts` array then includes those data parts alongside any text parts, and reconciliation by `id` lets you update a stage in place rather than appending duplicates.[^2][^5]

For your pipeline, the clean pattern is:

- Define a custom `UIMessage` type where `parts` can include `type: 'data-stage'` with `{stage, status, message, timestamp, details}` data.
- In `createUIMessageStream`’s server implementation, write one `data-stage` part per stage, with a stable `id` (e.g. `stage-signal_discovery`) and updated `status` at transitions (“queued” → “running” → “done”/“error”).[^5]
- Optionally stream the drafting LLM tokens separately using text parts (`type: 'text'`), but keep stage events structurally distinct so your UI can render timelines / badges / logs without parsing raw text.

This uses the AI SDK as a **generic event stream** library, not just “LLM output streaming,” and is aligned with how v5 was explicitly designed to work.[^6][^2][^5]

**Does AI SDK help or hurt for non-token data?**

- Helps: ready-made SSE wiring, TS types, client hooks, and a unified protocol for both LLM and non‑LLM events.[^2][^5]
- Hurts slightly: `useChat` is semantically “chat”; you’re repurposing it for a single pipeline run. You should be ready to explain that design choice, but it’s a reasonable trade given your stack and timeline.

***

### A3. Vercel serverless specifics — what breaks only in production

Key constraints and “surprises” that matter for your pipeline:

- **Function duration:** Node.js/Python functions on Pro/Enterprise can now run up to **30 minutes** if you set `maxDuration = 1800` and use Fluid Compute; the default ceiling for extended durations is still 800 seconds, and long durations above that remain in beta. You’re unlikely to hit these limits in your demo, but if you chain many slow external APIs, you can get closer than you expect.[^8][^9]
- **Fluid Compute behavior:** Fluid Compute reuses instances and pauses billing while waiting on I/O (e.g. Claude calls, DB queries, HTTP APIs). This is good for cost, but it means code that assumes a single clean instance per request (e.g. mutable module-level state) can behave differently in production than in dev.[^8]
- **Scale-to-zero database:** Neon’s free tier **always scales compute to zero after ~5 minutes idle**, so your *first* query in a demo will have a cold-start hit if you haven’t touched the DB shortly before.[^10][^1]
- **Env-var scoping:** Vercel env vars are per‑environment (Production vs Preview vs Development). It’s very common for a first deploy to fail because keys are only set on Production but the demo link is a Preview URL (or vice versa) — the functions then boot with missing `process.env.*`. (This is widely reported; no single canonical doc, moderate confidence.)
- **SSE buffering:** Local dev streams chunks immediately; production can introduce buffering at CDN/proxy layers, causing events to appear batched. Vercel’s docs don’t spell out SSE buffering behavior in detail; you need to test your actual deployed URL, not just `next dev` (low-confidence, but observed across multiple edge stacks).

In practice: set `maxDuration` conservatively high (e.g. 30–120 seconds, depending on how many external calls you make), parallelize external API calls where possible, and treat Neon cold starts and env-var scoping as things to warm up and double-check right before your demo.[^1][^10][^8]

***

### A4. UI patterns worth copying for run views

You won’t find many open-source “AI SDR run view” UIs, but you *can* copy battle-tested patterns:

- **AI SDK / “AI Elements” examples** — Vercel’s examples show tool calls and intermediate states, essentially a timeline of model + tool activity; it’s close to what you need visually.[^5][^2]
- **CI pipeline UIs** — GitHub Actions and Vercel’s own deployment logs already have a UX for “multi-step pipeline with per-step status, timestamps, and expandable logs.” Mimic that structure: vertical stack of stages, each with a status badge, duration, and collapsible detail.
- **LangGraph / Langfuse trace UIs** — while you won’t embed them, the node graph + trace views show how to present multi-agent reasoning and evidence. They are strong prior art for “reasoning trace + evidence panel” layouts.[^11]

Make your run view look more like a “deployment log” than a chat window — that’s both familiar to reviewers and aligned with the agent pipeline mental model.

***

## B. Persistence and deployment (brief)

### B1. Postgres or equivalent on Vercel — free at kilobyte scale

Vercel’s own branded Postgres has been sunset; the recommended path is **Neon Serverless Postgres via the Vercel Marketplace**. Neon’s **Free** plan is *not* a trial — it’s a permanent free tier suitable for low‑traffic apps:[^12][^13]

- **100 CU‑hours per project per month**, autoscaling up to 2 CU (≈8 GB RAM).[^14][^15][^1]
- **0.5 GB storage per project.**[^10][^1]
- Scales compute to zero after 5 minutes idle, so idle apps pay \$0.[^16][^14][^1]
- No credit card required; limits reset monthly for compute/egress.[^17][^15][^1]

At “a few hundred JSON run records,” you’re comfortably inside 0.5 GB; the main consideration is cold-start latency on first query after idle.

**Driver \& connection pattern for serverless:**

The current guidance is: use **Neon’s serverless HTTP driver** (`@neondatabase/serverless`) or a compatible ORM (Prisma) with Neon’s connection string, not a long‑lived TCP pool. Serverless environments spawn many short-lived instances; HTTP drivers handle scale-to-zero and reconnection without pool management.[^18][^16]

#### Options table — persistence

| Tool | What it does | Free / self-hostable | Maturity | TS support | Link | Date verified |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| Neon Serverless Postgres (via Vercel Marketplace) | Managed Postgres with scale-to-zero, branching; ideal for small apps needing SQL + JSON | Permanent **Free** tier: 100 CU-hrs + 0.5GB/project, no card | Mature; acquired by Databricks, widely adopted | Official TS/Node driver, Prisma support | https://neon.com/faqs/managed-postgres-databases-free-tier | FAQ updated 2026, viewed Aug 2026[^1][^15] |
| Self-hosted Postgres (e.g. cheap VPS) | Run Postgres yourself on a VM and connect from Vercel | Technically “pay-per-use,” but minimum server cost and ops overhead; conflicts with your days-long timeline | Very mature, but ops-heavy | Any TS driver (`pg`, Prisma) | https://solodevstack.com/blog/postgresql-vs-neon-solo-developers | Feb 16 2026[^19] |
| Vercel Blob / KV | Simple object / key–value storage for JSON runs | Free tiers exist but not as structured as SQL; limits vary | Production-grade for many small apps | TS SDKs via Vercel | Vercel docs | Not re-verified here (low confidence) |

**Is Postgres the right call?**

For a **run history dashboard with filters (status, ICP score, date)**, Postgres is the most straightforward: a `runs` table with `id`, `created_at`, `status`, `icp_score`, `signal_score`, and a `JSONB` payload for per-stage details. Alternatives like Blob/KV are simpler but push the burden of querying and filtering into your app code; given you’re comfortable with data work and want a credible “production-ish” architecture, Neon is the right move.[^19][^1]

**Ranked recommendation (persistence):**

1. **Neon Free plan via Vercel Marketplace**, using the serverless HTTP driver and a single `runs` table with JSONB payload.
2. If you needed even less structure, Vercel Blob/KV might be acceptable — but you’d lose easy filtering/sorting.

**Explicitly rejected:**

- Self-hosted Postgres on a VPS — technically viable but adds ops, monitoring, and SSH-level risk for a portfolio project under a days-long timeline.[^19]
- Any managed DB with a **mandatory monthly base fee** (e.g. some Supabase tiers) — violates your “no monthly subscription” constraint.

***

### B2. Common production surprises on Vercel

You’re most likely to get bitten by:

- **Cold Neon DB + cold function at demo time:** Neon free tier scales to zero after 5 min idle; your function may also be cold. First query to the run-history dashboard can thus stall, making the demo feel broken.[^1][^10]
- **Misconfigured `maxDuration`:** If you leave defaults and later add more external calls or retries, a long pipeline can quietly hit duration ceilings and terminate mid-stream.[^9][^8]
- **Env vars missing in the environment you actually demo:** Very common for “Preview” links to be missing keys that are only set for Production, or vice versa.

Mitigation for demo:

- Ping Neon (simple `SELECT 1`) and your main API route **right before** you start the screen share, so you don’t show cold-start latency.
- Explicitly set `export const maxDuration = N` on your pipeline route; pick N generous enough for worst-case external call times.[^8]
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

- **Vercel Workflows now exists specifically for long‑running, multi‑step agents.** It gives you durable, resumable workflows with an event log, queue-based step orchestration, and integrated observability, written in plain TypeScript (`"use workflow"` / `"use step"`). For a longer-term version of this project, it’s the natural evolution beyond a single long-running function.[^20][^21]
- **Neon’s free tier limits are generous but real.** You get 0.5 GB storage and 100 CU‑hours per project per month — enough for serious prototyping, but if you accidentally build heavy polling or overuse server-side evals, you can hit compute limits and see your DB suspended until the next cycle.[^15][^10][^1]
- **Vercel Functions >800s are beta and tied to Fluid Compute.** If you ever push toward truly long pipelines, durations above 800 seconds require explicit `maxDuration` configuration and may behave differently across runtimes.[^9][^8]
- **OpenTelemetry + Langfuse give you a ready‑made vocabulary for “retrieval failed vs no data.”** Even if you don’t adopt full tracing now, borrowing the concepts of span status, error types, and per-span scores (e.g., retrieval span with `status=ERROR` vs a successful span that returns an empty set) will help you design a clear internal model of partial failures and propagate that to your UI later.[^22][^11]
<span style="display:none">[^23][^24][^25][^26][^27][^28][^29][^30][^31][^32][^33][^34][^35][^36][^37][^38][^39][^40][^41][^42][^43][^44][^45][^46][^47][^48][^49][^50][^51][^52][^53][^54][^55][^56][^57][^58][^59][^60][^61][^62][^63][^64][^65][^66][^67][^68]</span>

<div align="center">⁂</div>

[^1]: https://neon.com/faqs/managed-postgres-databases-free-tier

[^2]: https://vercel.com/blog/ai-sdk-5

[^3]: https://vercel.com/docs/fluid-compute

[^4]: https://ai-sdk.dev/v5/docs/ai-sdk-ui/stream-protocol

[^5]: https://ai-sdk.dev/docs/ai-sdk-ui/streaming-data

[^6]: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol

[^7]: https://gist.github.com/ahmadrosid/c297498488795fb36d8076477c76e49e

[^8]: https://vercel.com/changelog/vercel-functions-can-now-run-up-to-30-minutes

[^9]: https://news.800.works/news/2026-06-16/vercel-functions-30-minute-ai-workloads/

[^10]: https://neon.com/faqs/free-plan-limits-and-quotas

[^11]: https://qaskills.sh/blog/langfuse-llm-observability-guide-2026

[^12]: https://neon.com/docs/guides/vercel-postgres-transition-guide

[^13]: https://kuberns.com/blogs/vercel-postgres-dead-what-replaced-it/

[^14]: https://vela.simplyblock.io/articles/neon-serverless-postgres-pricing-2026/

[^15]: https://neon.com/pricing

[^16]: https://neon.com/faqs/cheapest-ways-run-postgres-database-low-traffic

[^17]: https://freetier.co/directory/products/neon-serverless-postgres

[^18]: https://encore.dev/articles/neon-serverless-postgres

[^19]: https://solodevstack.com/blog/postgresql-vs-neon-solo-developers

[^20]: https://vercel.com/blog/a-new-programming-model-for-durable-execution

[^21]: https://vercel.com/docs/workflows

[^22]: https://opentelemetry.io/docs/specs/semconv/exceptions/exceptions-spans/

[^23]: https://nimblox.com/top-5-open-source-ai-powered-sdr-tools-on-github-2025/

[^24]: https://github.com/Salesably/awesome-ai-agents-for-sales

[^25]: https://www.clay.com/blog

[^26]: https://github.com/ComposioHQ/outreach-agent

[^27]: https://www.promptfoo.dev/docs/usage/node-api-reference/

[^28]: https://lavender.ai/blog

[^29]: https://pulseagent.io/open-source

[^30]: https://github.com/MatthewDailey/open-sdr

[^31]: https://www.promptfoo.dev/docs/category/usage/

[^32]: https://www.braintrust.dev/docs/evaluate

[^33]: https://github.com/topics/cold-calling

[^34]: https://qaskills.sh/blog/braintrust-llm-evaluation-guide-2026

[^35]: https://github.com/ChiragBellara/AI-SDR-Agent

[^36]: https://github.com/topics/sdr-automation

[^37]: https://www.braintrust.dev/docs/evaluation-quickstart

[^38]: https://www.zenml.io/llmops-database/rebuilding-an-ai-sdr-agent-with-multi-agent-architecture-for-enterprise-sales-automation

[^39]: https://www.linkedin.com/posts/ellogy_ai-agenticsystems-digitalworkers-activity-7341461628728541187-GxLg

[^40]: https://b2bsalesguru.medium.com/11x-ai-sdr-review-i-gave-it-200-leads-and-watched-what-happened-2026-45d14f2ca215

[^41]: https://www.linkedin.com/posts/luis-acevedo-ii-664b1020a_how-11x-rebuilt-their-alice-agent-from-react-activity-7340777815304216578-FMVd

[^42]: https://www.zenml.io/blog/llmops-in-production-another-419-case-studies-of-what-actually-works

[^43]: https://www.clay.com/blog/clay-series-c-announcement-the-gtm-engineering-era-begins-now

[^44]: https://clayground.ai/blog/gtm-engineering-clay-ai-agents-meetings

[^45]: https://www.clay.com/blog-category/clay-announcements

[^46]: https://www.11x.ai/worker/alice

[^47]: https://www.clay.com/blog-tag/ai

[^48]: https://www.letta.com/case-studies/11x/

[^49]: https://www.linkedin.com/posts/changsha-ma-9ba7a485_how-11x-rebuilt-their-alice-agent-from-react-activity-7343087985145397248-_BYm

[^50]: https://www.startuphub.ai/ai-news/ai-video/2025/alices-brain-11xs-knowledge-base-revolutionizes-ai-sales-reps

[^51]: https://x.com/llama_index/status/1953912358671462495

[^52]: https://futureagi.com/blog/rag-evaluation-metrics-deep-dive-2026/

[^53]: https://futureagi.com/blog/evaluating-rag-faithfulness-deep-dive-2026/

[^54]: https://futureagi.com/blog/evaluating-rag-systems-ensuring-your-llm-remembers-what-it-reads/

[^55]: https://futureagi.com/glossary/rag-faithfulness/

[^56]: https://futureagi.com/blog/rag-evaluation-metrics-2025/

[^57]: https://futureagi.com/blog/what-is-rag-evaluation-2026/

[^58]: https://arxiv.org/html/2605.21071v4

[^59]: https://futureagi.com/blog/agentic-rag-systems-2025/

[^60]: https://github.com/mattpocock/evalite

[^61]: https://www.evalite.dev/

[^62]: https://futureagi.com/blog/what-is-retrieval-augmented-generation-2026/

[^63]: https://www.open-source-tools.com/evalite

[^64]: https://jimmysong.io/ai/evalite/

[^65]: https://www.reddit.com/r/QualityAssurance/comments/1qfp9qd/trusting_your_llmasajudge/

[^66]: https://neon.com/faqs/postgres-services-free-to-production

[^67]: https://saaspricehub.io/tools/neon

[^68]: https://vibecoding.app/blog/neon-review

