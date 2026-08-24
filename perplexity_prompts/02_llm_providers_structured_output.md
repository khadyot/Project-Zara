# Perplexity Prompt 02 — LLM providers for low-volume structured JSON (2026)

> **Human:** paste everything below the line into Perplexity. Use Research/Deep Research mode if available. Save the reply to `perplexity_responses/02_llm_providers_structured_output.md`.

---

**Today's date is 24 August 2026.** Prioritise sources from 2026. Explicitly flag any claim resting on information older than six months — this landscape changes fast and free tiers are frequently cut. Cite every pricing or rate-limit claim with a link and a publication date, and prefer the provider's own docs or pricing page over third-party summaries. If you cannot find a primary source for a number, say so rather than estimating.

## My context

I run a small B2B research-and-drafting agent. Per prospect it makes roughly **7–10 LLM calls**: a ranker (scores research snippets against a list of pain points), a classifier, a hook writer, a drafter, and a verifier that runs twice. Volume is **5–20 prospects per day**, one at a time, interactive — a human is watching a progress bar.

Every call demands **schema-valid JSON** matching a Pydantic model. Typical request is 1,000–6,000 tokens of prompt; one call sends ~20,000 characters. Responses are small. Latency target is single-digit seconds per call; the whole run should finish in well under a minute.

Solo developer, strong preference for free or very cheap tiers, but paying a small amount is acceptable if it removes an operational failure mode.

## What went wrong, and what I actually need to know

I am currently on Groq with `openai/gpt-oss-120b` as the documented choice, but the code was changed to **`groq/compound`** as the primary model for all of the above calls. I hit `HTTP 413 Payload Too Large` on a request whose body was only a few hundred characters, which suggests Groq returns 413 for **token-per-minute budget overflow**, not for literal request size. My retry ladder then burned the remaining quota and the run hung for minutes. My Gemini fallback pointed at a model that 404s, and my third fallback hangs on a 60-second read timeout.

So the questions below are about **failure semantics and limits**, not about which model writes the nicest prose.

## Part 1 — Rate-limit and overflow semantics per provider

For each of: **Groq**, **Google Gemini API**, **Together AI**, **Fireworks AI**, **DeepInfra**, **Cerebras**, **Mistral La Plateforme**, **OpenRouter**, **Z.ai / Zhipu GLM**, and any 2026 entrant that has displaced these:

1. **Free tier, concretely** — requests/minute, requests/day, tokens/minute, tokens/day, as published. Note where a limit is per-model rather than per-account.
2. **What the API returns when each limit is exceeded** — exact HTTP status and error code. Specifically: which providers use **413 to signal a token-budget problem** rather than a body-size problem, and which use 429. This distinction cost me hours; document it per provider.
3. **Whether the response carries usable retry metadata** — `Retry-After`, `x-ratelimit-reset-*`, or equivalent — and whether that value is trustworthy in practice for per-minute token buckets.
4. **Whether a single request can exceed a per-minute token bucket** and be rejected outright no matter how long you wait, versus being queued.
5. **Cheapest paid step up** from free, with the actual first-tier price and what the limits become. I want the number, not "contact sales".

## Part 2 — `groq/compound` specifically

- What **is** `groq/compound` — is it a plain model or an agentic system that performs web search and tool calls server-side?
- Are its rate limits, latency, and token accounting **different from ordinary Groq chat models**, and by how much? Does server-side tool output count against my token budget?
- Is it appropriate for **deterministic structured-output calls** that involve no search, or is it search-only by design?
- Does it honour `response_format: {"type": "json_object"}` and strict JSON schemas reliably?
- What is the correct current Groq model for **cheap, fast, schema-valid JSON** at my volume in 2026? Confirm whether `openai/gpt-oss-120b` is still available and current.

## Part 3 — Structured output reliability

1. Which of these providers support **strict/constrained JSON schema decoding** (guaranteed-valid output) versus best-effort prompt-level JSON?
2. For providers with strict mode: what schema features are **unsupported** — I have already been bitten by needing `additionalProperties: false` and a complete `required` array on every object including `$defs`, which Pydantic's `model_json_schema()` omits.
3. **Critical failure mode I need documented:** when asked to return an array of N scored items, do these models reliably return all N, or do they silently drop elements under load or at length? My code assumes every input index comes back and crashes when one does not. Is there published evidence, benchmark, or issue-tracker discussion on element dropping in structured array outputs?
4. Practical guidance on making array-returning calls robust — does anyone recommend a per-item call, a required count field, echoing input ids, or another pattern?

## Part 4 — Prompt caching

- Which of these providers support **cached prompt prefixes**, and what are the concrete rules: minimum cacheable prefix length, TTL, whether it is automatic or opt-in, and the discount on cached tokens?
- Does caching apply to a **system prompt plus a static config block that is re-sent on every call**? That is my exact shape — a fixed pain list and JSON schema re-sent on each of ~10 calls per prospect.
- Does a cached prefix reduce the tokens counted against a **rate limit**, or only against the bill? This determines whether caching solves my problem or only makes it cheaper.

## Part 5 — Fallback chain design

- Is a multi-provider fallback chain (primary → secondary → tertiary) still considered good practice in 2026 for this use case, or has the field moved to a single provider plus a request queue with proper backpressure?
- What is the **standard pattern for a global deadline and circuit breaker** across a multi-call pipeline, so that one exhausted provider does not cause every subsequent call to independently re-discover the outage and pay a full retry ladder? Name specific libraries or patterns with current, maintained implementations in Python.
- Is there a reliable way to **detect a model id that is listed but not callable**? I have hit models that appear in `models.list()` and then 404 on generate.

## Output I want

1. A comparison table: provider, free-tier RPM/RPD/TPM/TPD, overflow status code, retry metadata quality, strict JSON support, prompt caching, first paid tier price.
2. A direct recommendation: **one primary and one fallback** for this workload, with reasoning tied to the failure modes above rather than to benchmark scores.
3. A short list of the specific mistakes in my current setup that the evidence says I should stop making.
