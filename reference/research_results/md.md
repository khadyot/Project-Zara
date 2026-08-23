# Streaming UI, Deployment, and Build Critique

## A. Streaming multi-stage pipeline progress to a web UI

### A1. Current best practice, August 2026

For Next.js on Vercel, raw Server-Sent Events (SSE) remain the transport underneath every modern option — WebSockets are not needed and are harder to run on stateless serverless functions. The real question is which abstraction sits on top of SSE.[^1]

The Vercel AI SDK v5 (`ai` + `@ai-sdk/anthropic`) introduced **UI Message Streams** with `createUIMessageStream`, which is the current (2025–26) replacement for the older ad hoc "data stream protocol" that used single-letter prefixes (`0:`, `2:`, `8:`, etc.) — that older protocol shows up in a lot of 2024-era tutorials and gists and is now legacy. The v5 protocol streams typed "parts" over SSE, requires the `x-vercel-ai-ui-message-stream: v1` header when the stream originates from a custom (non-AI-SDK) backend, and is consumed on the client by `useChat`.[^2][^3][^4]

Critically for this build, AI SDK v5 added **custom data parts** (`type: 'data-*'`) specifically so you can stream arbitrary, non-token, application-specific JSON — not just LLM tokens — alongside or independently of text generation. This is the mechanism, not RSC streaming or WebSockets, that current practice actually uses for structured event streams in 2026.[^5][^2]

### A2. The distinction that matters: streaming non-token pipeline events

This is answerable, but it requires combining two under-documented AI SDK v5 features rather than following the mainstream "stream the LLM's answer" tutorials, which is why it looks under-covered.

**Data parts vs. transient parts** is the key design choice:

| Feature | Regular data part | Transient part |
|---|---|---|
| Persists to `message.parts` / history | Yes | No — only visible in `onData` callback |
| Use case here | Final per-stage results you want to keep (e.g., "firmographics found: X") | Live status ticks ("signal_discovery: running...") you don't need to replay |
| Reconciliation | Same `id` → client automatically replaces/updates that part | N/A, ephemeral |

Source: AI SDK docs, "Streaming Custom Data".[^6][^2]

For a `{stage, status, message, timestamp}` event model like yours, the practical pattern is: emit each stage transition as a data part with `type: 'data-stage'` and a stable `id` per stage (e.g. `id: "stage-signal_discovery"`), so subsequent status updates for that same stage (`running` → `done`/`error`) replace the previous part via reconciliation instead of appending duplicate entries. Use `writer.write({ type: 'data-stage', id, data: {...} })` inside `createUIMessageStream`'s `execute` callback, which can run arbitrary async code (calling your enrichment APIs, scoring logic, etc.) interleaved with any actual LLM calls for drafting.[^2][^6]

**Is the AI SDK the right abstraction, or overkill?** Partial answer, moderate confidence: it is *not* the wrong abstraction, but it is more than the minimum needed. Since only some stages involve an LLM at all, you could implement the identical wire protocol with a hand-rolled SSE `ReadableStream` in a Next.js Route Handler and skip the AI SDK entirely — the protocol itself (`data: {"type":"data-stage",...}\n\n`) is simple enough to hand-write. The AI SDK's value-add is the client-side `useChat`/`onData` plumbing, reconnection handling, and type-safety via `UIMessage<Metadata, DataParts, Tools>` generics — worth it if you're already pulling in `ai` for the drafting-stage Claude calls (which you are, per your stack), marginal if you weren't.[^3][^5]

**Ranked recommendation:** Use `createUIMessageStream` with a custom `MyUIMessage` type; model every non-LLM pipeline stage as a `data-stage` part (persistent, reconciled by id) and use transient parts only for sub-stage chatter you don't want to keep (e.g. "querying Serper... querying Exa..." inside signal discovery). Reserve actual token streaming (`streamText`) only for the email-drafting stage.

**Explicitly rejected:** Raw WebSockets — no persistent connection is possible in a stateless Vercel function without an external WS gateway (Pusher/Ably), adding a dependency and cost for no benefit over SSE on a single-request pipeline. React Server Components streaming — RSC streams HTML/JSX chunks progressively during render, not arbitrary structured JSON events over the life of a multi-minute background pipeline; it's the wrong tool for this shape of problem and is not what production agent UIs use for stage timelines.[^1]

### A3. Vercel serverless specifics — what breaks in production but not locally

| Issue | What happens | Source/date | Fix |
|---|---|---|---|
| Function duration limits | Default/max is 300s on lower tiers; Pro/Enterprise can extend to 800s, or 1800s in beta for Node/Python with explicit `maxDuration` config | Vercel docs, current[^1] | Set `export const maxDuration` per-route explicitly; for anything approaching the limit, use Vercel Workflows (no duration cap, pause/resume) rather than one long function[^1] |
| Fluid Compute changes defaults | Fluid Compute (now default) changes concurrency/instance-reuse behavior versus classic Lambda-style isolation — cold-start and in-flight-request behavior differs from what many 2024 tutorials describe | Vercel docs[^1] | Re-verify any duration/timeout assumptions against current plan; don't trust cached knowledge of "10s default" from older posts |
| CDN/proxy buffering of SSE | Locally, dev server flushes chunks immediately; in production, intermediate proxies/CDNs can buffer response bodies, delaying or batching SSE events so the UI appears to freeze then dump all events at once | Widely reported pattern for Vercel + Cloudflare + similar edge stacks (uncertain — no single Vercel primary-source page found in this pass, flag as **moderate confidence**) | Ensure `Content-Type: text/event-stream`, disable any `Cache-Control` caching on the route, and confirm the response isn't being run through Vercel's Data Cache; test the actual deployed URL, not just `next dev`, before demo day |
| Connection drop / no reconnection by default | A dropped SSE connection (laptop sleep, wifi blip during a live demo) does not auto-resume pipeline state unless you implement it | AI SDK protocol supports reconnect at transport level[^3], but *your* pipeline state needs to be resumable server-side too | Persist pipeline state (Postgres or even in-memory + DB write per stage) so a reconnecting client can re-fetch current run status rather than losing all progress |
| Serverless function is stateless between invocations | If your "run view" polls or reconnects, a *new* invocation has no memory of the in-progress run unless state was externalized | Structural, not a bug | Write stage status to your DB as each stage completes, not just to the in-memory stream — this doubles as the run history for the dashboard requirement |

**Confidence flag:** the CDN-buffering claim is a well-known category of problem for SSE-over-serverless generally, but a primary Vercel doc specifically confirming SSE buffering behavior in production was not found in this pass — verify with a live deployed smoke test well before demo day, not just local testing.

### A4. Patterns worth copying — pipeline/agent run-view UIs

- **Vercel AI SDK's own reference chat UI + tool-call visualizations** (elements in `@ai-sdk/react`, and the "AI Elements" component set) — shows tool-call start/delta/result states, which map directly onto your stage states.[^5][^2]
- **LangGraph Studio / LangSmith trace UI** — not directly embeddable in your stack, but the visual pattern (node graph lighting up per step, collapsible per-node detail) is the standard mental model for "agent run view" and is worth studying even though you'd build your own React version.
- **CI pipeline UIs (GitHub Actions run view, Vercel's own deployment build logs)** — outside the AI category but the closest UX analog to "sequential stages, each with running/success/fail state, expandable logs, timestamps." Vercel's own dashboard is a good reference precisely because your interviewer already knows that UX language.
- **11x's/LangChain's supervisor-pattern diagrams** — useful less as UI, more for how to *label* stages (a "researcher" doing signal discovery, a "report/scoring" step, a "drafter") so your live view reads as a legible pipeline rather than an opaque black box.[^7][^8]

***

## B. Persistence and deployment

### B1. Postgres on Vercel — free tier, August 2026

Vercel discontinued its native Postgres product; existing databases were migrated to Neon between Q4 2024 and Q1 2025, and Postgres is now offered only via the **Vercel Marketplace**, which provisions a third-party provider and injects the connection string into your env vars.[^9][^10]

| Provider | Free tier (as of 2026) | Idle/scale behavior | Card required | Source date |
|---|---|---|---|---|
| Neon (via Vercel Marketplace) | 0.5 GB storage per project, up to 100 projects, 100 CU-hours/mo compute, autoscale to 2 CU | Scale-to-zero after 5 min idle | Not required | Jul 2026[^11] |
| Supabase | 500 MB database, 2 active projects | Pauses after 7 days idle | Not required | Jul 2026[^11] |
| Prisma Postgres / CockroachDB | Also offered via Marketplace with free tiers | Not deeply verified in this pass | Uncertain | — |

For "a few hundred JSON run records," Neon's free 0.5 GB is comfortable, but note the 5-minute scale-to-zero: your dashboard's first load after idle time will hit a cold Postgres connection, adding latency you should account for in a live demo (warm it up before the interviewer watches).

**Driver/connection pattern:** the current recommended pattern for serverless Postgres is the Neon serverless HTTP driver (`@neondatabase/serverless`) or Prisma's driver adapters, not a traditional long-lived `pg` Pool — pooled TCP connections don't play well with functions that can scale to zero and spin up many short-lived instances; use the unpooled/HTTP connection string variant provided in your env vars.[^12][^10]

**Is Postgres even the right call?** Reasonable challenge to your own plan: for a few hundred JSON run records with no relational structure requirement, options worth weighing:
- **Vercel KV / Upstash Redis (Marketplace)** — simpler, free tier exists, fine for a flat run log, but loses SQL query flexibility for a dashboard with filters.
- **Vercel Blob** — could store one JSON file per run, cheapest and simplest, but you'd hand-roll listing/filtering.
- **Neon Postgres** — still the most defensible choice if the dashboard needs to filter/sort/aggregate runs (by ICP score, date, status) since that's exactly what SQL is good at, and it costs nothing at this scale. **Recommendation: keep Postgres**, but don't over-engineer the schema — a `runs` table with a `JSONB` payload column plus a few indexed scalar columns (status, score, created_at) for filtering is enough; you don't need normalized tables for signals/events.

### B2. Common production surprises on first deploy

- **Environment variables not set per-environment.** A very common first-deploy failure: keys set for "Production" in Vercel's dashboard don't automatically apply to Preview deployments (and vice versa) — if your interview demo runs off a preview URL rather than production, missing env vars is the single most common "worked locally, broke live" bug.
- **`maxDuration` defaults catching a multi-API pipeline.** If signal discovery calls 4–5 external APIs sequentially and each takes a few seconds, a naive implementation can approach the default 300s ceiling faster than expected, especially with retries; explicitly set `maxDuration` and parallelize independent API calls.[^1]
- **Fluid Compute concurrency assumptions.** Because Fluid Compute changes how instances are reused across concurrent requests, code that assumes one clean instance per request (e.g., module-level mutable state used as a cache) can leak between users/requests in ways that don't show up in local dev's single-process model.[^1]
- **Cold starts on the demo's actual first request.** If the interviewer's very first live input triggers a cold Lambda/Neon wake-up simultaneously, the demo's *first* impression is a multi-second stall — mitigate by triggering a warm-up request yourself moments before starting the screen share.

***

## C. Critique

### C1. What would you cut?

Cut ambition on breadth of signal sources before cutting the confidence-gate/anti-fabrication logic — the gate is your differentiator; a fifth data source is not. Cut any attempt at a fully generic multi-tenant "suppression check" system (existing customer / active deal / do-not-contact) with real CRM integration — for a portfolio demo, a hardcoded or trivially-seeded lookup table proves the *concept* of suppression without needing a real Salesforce/HubSpot connection, and building real CRM auth under a days-long timeline is a bad trade. Similarly, don't build real authentication/multi-user support for the dashboard — a single unauthenticated (or trivially password-gated) dashboard is fine for a take-home; interviewers grading "judgment" will not reward auth scaffolding here and may even see it as a sign you misjudged scope.

### C2. What's cheap and disproportionately impressive?

- **A visible, itemized confidence-gate breakdown** (ICP fit score, signal strength score, the lookup-table decision, and *why* — e.g., "signal strength: 2/5 — only firmographic data found, no authored content") shown in the run view, not just a pass/fail. This directly demonstrates the "restraint" thesis in a way a screen-share audience can see in seconds.
- **A literal "needs human judgment" state that looks deliberate**, not like an error — a distinct UI treatment (different color, explicit reasoning shown, maybe a suggested next action like "try again in 2 weeks" or "check LinkedIn manually") signals product thinking rather than a fallback.
- **Live streaming stage-by-stage view with real per-stage timing.** Trivial to build given the AI SDK data-parts pattern above, and vastly more impressive live than a spinner — it's the single highest-leverage UI investment for this specific grading rubric.
- **Distinguishing "found nothing" from "search failed"** in the UI (see A2/B3 discussion above about retrieval failure vs. genuine null result) — showing this distinction explicitly ("3 of 4 signal sources returned no results; 1 source errored and was excluded from scoring") is cheap to implement relative to how rarely competitors will think to do it, and it's a direct, concrete demonstration of anti-fabrication rigor.
- **A one-line, always-visible "why this decision" explanation attached to the final output** — whether drafting or routing to human review, a plain-English one-sentence justification is nearly free and is exactly what "explain it to a non-technical buyer" rewards.

### C3. How this fails in a live demo, and standard prevention

- **An external API is down, rate-limited, or returns an unexpected shape for the specific real person named live.** Standard prevention: every external call wrapped in a timeout + typed try/catch that converts failures into an explicit "source unavailable" signal state (not a silent empty result) — this is precisely the B3 distinction from Part 2, and it's your single highest-risk failure mode given a truly arbitrary, unseen input.
- **The named person has zero public digital footprint** (very plausible for a mid-level ops manager). If your system isn't built to gracefully and *convincingly* route to "needs human judgment" for this exact case, the demo either stalls or — worse — the model fabricates a hook live in front of the interviewer, directly falsifying your product's stated thesis. Prevention: explicitly test this exact scenario (a low-visibility, non-founder persona) before demo day, not just a founder/VP case that will always have signal.
- **Cold start / first-request latency stacking with LLM latency**, making the very first pipeline run look sluggish or frozen. Prevention: warm up serverless functions and DB connections minutes before starting.
- **SSE connection drop mid-run during screen share** (network hiccup, laptop sleep). Prevention: server-side state persistence per stage (per B1) so a page refresh recovers the run rather than losing it — critical since you cannot control the interviewer's network or your own screen-share tooling.
- **Interviewer picks a person whose name collides with someone more famous/higher-signal**, and your identity-resolution stage confidently attaches the wrong person's signal to the prospect. This is a real and underestimated risk category (entity-attribution failure, distinct from hallucination — see Part 2's "deceptive grounding" research) — prevention: surface the resolved identity's disambiguating details (company, title) prominently in the run view *before* showing any signal, so a wrong match is visually obvious rather than silently baked into a confident draft.[^13]

### C4. Where the plan is likely wrong or naive

- **The confidence gate is described as pre-generation only**, but the plan doesn't specify how the gate handles *partial* signal — e.g., strong firmographics plus one weak, unverified authored-content hit. A binary "draft or route to human" from a lookup table risks either being too conservative (routing everything with any ambiguity to human, defeating the demo's purpose of showing a drafted email at all) or too permissive (drafting on thin signal). This needs a middle state, and the plan as described doesn't obviously have one — worth explicitly deciding and being able to explain the boundary case, since an interviewer will likely probe exactly this seam.
- **"Never auto-sends" is stated as a safety property but isn't described as visibly enforced in the architecture** — if there's no literal missing-send-capability (no email API credentials wired to anything, no button that could accidentally be conflated with "send"), state that explicitly and visibly in the demo, because a reviewer assessing judgment will specifically look for whether restraint is architectural or just a policy note.
- **Identity resolution risk is understated.** The pipeline treats "identity resolution" as a single early stage, but for a common name at a mid-size company, this is arguably the highest-risk stage in the entire pipeline (see C3 above) and deserves the same confidence-scoring rigor as signal discovery — the plan as described applies confidence scoring only to signal strength and ICP fit, not to identity-match certainty, which is a gap.
- **The suppression check (existing customer / active deal / do-not-contact) is functionally decorative in a single-prospect demo** unless there's a visible, populated mock dataset the interviewer can see triggering it — otherwise it's a pipeline stage that always trivially passes, which an alert interviewer may notice does nothing observable. Either seed a mock CRM record deliberately near the demo's real input (own risk: too contrived) or be upfront that it's a stub with real logic behind a placeholder data source.
- **Streaming of non-LLM stages via the AI SDK's `useChat`-centric model is a slight architectural mismatch** you should be ready to explain — `useChat` is fundamentally a chat-message abstraction; you're repurposing it for a single non-conversational pipeline run. It works (per A2), but it's worth being able to articulate *why* this was the right trade (reuse the same client-side infra as the drafting LLM call) rather than appearing to have not noticed the mismatch.

### C5. What separates a memorable submission from a competent one

Most candidates will build a working pipeline with a plausible-looking email at the end; the brief's own language ("judgment behind your design choices," "explain it clearly to a non-technical buyer") signals the bar is explanatory clarity about trade-offs, not feature count. Concretely: be able to state, in one or two sentences each, *why* you chose the specific confidence-gate boundary, *why* restraint is the product rather than a safety feature bolted on, and *what you deliberately left out and why* (e.g., "I didn't build real CRM suppression because a demo needs a visible mock, and building real OAuth to a CRM under this timeline was the wrong trade for a case study"). A memorable submission treats the "needs human judgment" state as a first-class, well-designed output — most competent submissions will treat it as an afterthought error state. Finally, the ability to run the exact stated scenario — an arbitrary, low-signal, non-famous person, live, with the system correctly declining to fabricate — is the single most memorable possible demo moment in this category, more valuable than any additional data source or UI polish.

***

## Things you did not ask about but should know

- **`Vercel Workflows`** (referenced in the Fluid Compute docs) is a newer primitive specifically designed for exactly your problem shape — long-running, multi-step processes with pause/resume and no hard duration ceiling. It wasn't asked about, but given your pipeline is multi-stage and calls multiple external APIs sequentially, it may be a better fit than a single long serverless function even for a days-long timeline, since it directly solves the "what if one stage runs long" problem without you having to hand-build resumable state. Worth at least a 30-minute evaluation before committing to a single monolithic API route.[^1]
- **AI SDK v5's stream protocol changed from the letter-prefixed format to the JSON-object SSE format** — if you find any code snippets or Stack Overflow answers using `0:`, `2:`, `8:` prefixes, they are for the deprecated protocol and will not work with current `useChat`/`createUIMessageStream`. This is an easy trap because a lot of indexed tutorial content is not yet updated.[^4][^3]
- **The Neon free tier's 5-minute scale-to-zero is a live-demo-specific risk**, not just a performance footnote — if you don't touch the database for 5+ minutes while setting up the screen share, your dashboard's very first query during the actual demo will incur a cold-start penalty. Ping the DB right before you start.
- **OpenTelemetry's GenAI semantic conventions** (from Part 2's research) actually give you a ready-made, standardized vocabulary for exactly the "did retrieval fail vs. return legitimately empty" distinction discussed in C3/A3 — `error.type`, span status, and the broader `rag.retrieval.empty_result` pattern are directly reusable as your internal event schema for pipeline stages, even without adopting full OTel tracing infrastructure. Borrowing the vocabulary (not necessarily the infrastructure) costs nothing and gives your event schema a defensible, industry-aligned design if an interviewer asks about it.[^14][^15]
- **A hardcoded "warm-up" ping button or automatic pre-flight check** (hit the DB, hit each external API with a lightweight health check) run automatically a few seconds before the interviewer's real input is submitted is a nearly free addition that directly prevents the most likely live-demo failure (cold starts stacking with real latency) and can be framed in the interview as evidence of thinking about production reliability, which reads well against the "judgment" criterion.

---

## References

1. [Fluid compute](https://vercel.com/docs/fluid-compute)

2. [Streaming Custom Data - AI SDK UI](https://ai-sdk.dev/docs/ai-sdk-ui/streaming-data) - The AI SDK provides several helpers that allows you to stream additional data to the client and atta...

3. [Stream Protocols - AI SDK UI](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol) - AI SDK UI functions such as useChat and useCompletion support both text streams and data streams. Da...

4. [vercel-ai-sdk-stream-protocol.md](https://gist.github.com/ahmadrosid/c297498488795fb36d8076477c76e49e) - GitHub Gist: instantly share code, notes, and snippets.

5. [AI SDK 5 - Vercel](https://vercel.com/blog/ai-sdk-5) - All frameworks now get the same powerful features: custom message types for your application's speci...

6. [Customizing Data Parts in the Vercel AI SDK to Visualize Search ...](https://zenn.dev/tsuboi/articles/26e3fe8fb6dc98?locale=en)

7. [11x: Rebuilding an AI SDR Agent with Multi-Agent Architecture for ...](https://www.zenml.io/llmops-database/rebuilding-an-ai-sdr-agent-with-multi-agent-architecture-for-enterprise-sales-automation) - 11x rebuilt their AI Sales Development Representative (SDR) product Alice from scratch in just 3 mon...

8. [Luis Acevedo II's Post - How 11x Rebuilt Their Alice Agent - LinkedIn](https://www.linkedin.com/posts/luis-acevedo-ii-664b1020a_how-11x-rebuilt-their-alice-agent-from-react-activity-7340777815304216578-FMVd) - Building a great AI agent is less like coding and more like organizational design. Leaders are chasi...

9. [Vercel Postgres Sunset: What to Use Instead 2026](https://kuberns.com/blogs/vercel-postgres-dead-what-replaced-it/)

10. [Vercel Postgres Transition Guide - Neon Docs](https://neon.com/docs/guides/vercel-postgres-transition-guide)

11. [Neon vs Supabase vs Vercel Postgres: Cheapest Serverless ...](https://www.saasturf.com/blog/neon-vs-supabase-vs-vercel-postgres/) - A cost-first comparison of Neon, Supabase, and Vercel Postgres for bootstrapped SaaS — free tiers, s...

12. [NightOwl + Vercel Postgres: Setup Guide (2026)](https://usenightowl.com/guides/setup-nightowl-with-vercel-postgres/) - Step-by-step tutorial: connect NightOwl Laravel monitoring to a free Vercel Postgres (powered by Neo...

13. [Deceptive Grounding: Entity Attribution Failure in Clinical ...](https://arxiv.org/html/2607.09349v1)

14. [RAG Pipeline Observability with OpenTelemetry - Uptrace](https://uptrace.dev/guides/opentelemetry-rag-observability) - How to trace every stage of a RAG pipeline with OpenTelemetry — embedding, vector search, reranking,...

15. [Semantic conventions for exceptions on spans - OpenTelemetry](https://opentelemetry.io/docs/specs/semconv/exceptions/exceptions-spans/) - Use Semantic conventions for exceptions in logs instead. This document defines semantic conventions ...

