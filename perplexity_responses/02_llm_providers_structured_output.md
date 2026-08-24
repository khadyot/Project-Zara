# LLM providers for low-volume structured JSON — research findings

**Source:** Perplexity (Research mode), run 2026-08-24.
**Prompt:** [`02_llm_providers_structured_output.md`](../perplexity_prompts/02_llm_providers_structured_output.md)

> **Unverified third-party research.** Claims here have not been checked against the providers' own docs or against this repo's measured facts. See the verification notes appended at the end before acting on any number.

---

For your workload in August 2026, the safest pattern is: keep Groq, but switch off `groq/compound` for structured JSON, and pair one “strict structured output” provider (Gemini or Mistral) with one high‑throughput router (OpenRouter or Together) behind a **single global deadline + circuit breaker** instead of a naïve multi‑provider retry ladder.[^1][^2][^3][^4]

Below I’ll go provider‑by‑provider on rate limits and failure semantics, then answer the `groq/compound` questions, structured‑output reliability, prompt caching, and finally the fallback design and the specific mistakes to fix.

***

## Big picture for your use case

Your current throughput (5–20 prospects/day × 7–10 calls, mostly sequential, 1–6k tokens per call) is comfortably below almost all free and entry‑level paid limits in 2026; your problem is not *capacity* but **how rate‑limit failures are signaled and retried.**[^5][^6][^2][^1]

Most providers in your list document **429 Too Many Requests** for RPM/TPM overflows; none of the 2026 docs I could find explicitly use **413** for token‑budget overflow, which strongly suggests your Groq 413 was either (a) a genuine payload‑size issue on that endpoint or (b) an implementation quirk not reflected in current docs.[^7][^8][^2][^9][^1]

***

## Comparison table (2026, with older sources flagged)

**Key:**

- “Free tier limits” = typical *default* for new/self‑serve accounts; some are dynamic or per‑model.
- I’ve prioritized 2026 docs; anything older than six months is explicitly marked.

| Provider | Indicative free / entry limits (RPM/RPD/TPM/TPD) | Overflow status codes | Retry metadata \& single‑request behavior | Strict JSON support | Prompt caching support | First paid tier (cheap step up) |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| **Groq** | Developer plan limits are per‑model; docs table (Aug 2026) shows, for example, `groq/compound`: 30 RPM, 250 RPD, 70k TPM, no TPD; `openai/gpt-oss-120b`: 30 RPM, 1k RPD, 8k TPM, 200k TPD.[^1] These are *org‑level* limits.[^1] | Officially: `429 Too Many Requests` when **any** rate limit is exceeded.[^1] Payload too large is 413 in generic HTTP semantics, but rate‑limit docs mention only 429 for throttling.[^1] | Responses include `retry-after` *only when* 429 is returned, plus `x-ratelimit-…` headers showing limits, remaining, and reset times; these map directly to TPM/RPD and are designed for backoff.[^1] Docs don’t describe queuing a single over‑budget request; exceeding TPM is treated as a rate‑limit violation (429), not queued.[^1] | Groq itself does not add a separate structured‑output layer; you rely on whatever the underlying model supports (e.g. OpenAI Structured Outputs on `openai/*` models, Mistral structured JSON on `mistralai/*`). Current Groq docs don’t expose a Groq‑native `json_schema` surface.[^1][^4] | Prompt caching is **automatic**; repeated prefixes are cached for up to ~2 hours and billed at ~50% of normal input price on supported models (e.g. `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, Kimi K2). Cached tokens **do not count** against TPM rate limits.[^10] (This pricing doc is June 2026.) | Pay‑as‑you‑go: per‑million‑token pricing, no minimum spend; e.g. `llama-3.1-8b-instant` at ~\$0.05/1M input, \$0.08/1M output; `openai/gpt-oss-20b` ~\$0.075/1M input.[^10] These prices are June 2026. Rate limits on the paid “Developer” plan typically increase to ~1,000 RPM and ~250k TPM for most text models, and ~200 RPM / 200k TPM for Compound systems.[^10] |
| **Google Gemini API** | Public “Developer Platform” rate‑limits doc (2026) says 120 requests/minute (public endpoints) and 600 requests/minute (private/enterprise endpoints), with a recommendation not to exceed 1–5 RPS.[^2] No fixed TPM listed; Gemini generally bills per token without publishing hard TPM caps per account. | Exceeding the RPM limit yields `429 Too Many Requests`.[^2] Standard Google APIs use `413` for body size, not rate limits; Gemini’s rate‑limit doc mentions only 429 for throttling.[^2] | Gemini queues *up to five* extra requests in a “burst” before returning 429 on further ones, then processes queued requests once the rate falls below the limit.[^2] No `Retry-After` header is documented for rate limits; you must implement your own backoff. Single over‑budget requests (RP M) are not rejected outright; they’re either processed, queued (small bursts), or rejected with 429 if the burst exceeds bounds.[^2] | Gemini supports true schema‑constrained JSON via `generationConfig.responseSchema` / `response_json_schema` with MIME `application/json`; 2026 testing shows failure rates under 1% when using strict schema, versus ~8–15% for plain JSON mode.[^11][^4] (The June 2026 benchmarks are current; the January 2026 article is >6 months old.) | Google does not publicly document token‑discount prompt caching for Gemini in the same way as Groq, DeepInfra, Cerebras or OpenRouter. There is internal prefix reuse for latency, but no published “cached tokens billed at X%” pricing or rate‑limit exemption as of mid‑2026.[^11] | Public Gemini pricing has multiple plans; for agents like yours the cheapest “pay‑as‑you‑go” step is to register on the Developer Platform and pay per token on Gemini 2.5 Flash / Pro. Exact per‑MTok prices depend on region and aren’t fully spelled out in the rate‑limit doc.[^2] |
| **Together AI** | Together’s rate limits are **dynamic per‑model, per‑org**; no fixed RPM/TPM table is published. Third‑party synthesis (June 2026) reports typical Build‑tier baselines like ~600 RPM / ~250k TPM on Llama 3.3 70B, ~1,200 RPM / ~500k TPM on Llama 3.3 8B.[^12] These figures are NOT primary docs. | Exceeding dynamic rate yields `429 Too Many Requests` with error types `dynamic_request_limited` or `dynamic_token_limited`.[^7] Capacity overload below your dynamic rate returns `503 Service Unavailable`.[^7] | Serverless responses include `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset`; Together’s docs say these headers are the **source of truth** for planning retries.[^7][^12] Single large requests above your dynamic token limit are rejected with 429 (no queueing beyond small bursts); requests at/below limit may get 503 when capacity is exhausted.[^7] | Together does not document a native JSON‑schema constrained decoding surface; structured output generally relies on prompt‑level instructions plus client‑side validation. No 2026 docs show an OpenAI‑style `json_schema` param.[^7][^12] | No explicit prompt‑caching discount is documented; performance tuning focuses on smoothing bursts and using dedicated endpoints rather than prefix caching.[^7][^12] | Cheapest paid step up is attaching a card (“Build tier” type) to unlock higher dynamic limits; dedicated endpoints start around \$6.49/hr for an H100 and remove shared serverless rate limits entirely.[^12] |
| **Fireworks AI** | Serverless free/low‑spend tier: if you have **no payment method**, docs and June 2026 synthesis say ~10 RPM account‑wide; adding a card moves you to Tier 1 with a \$50/month cap and higher per‑model RPM/TPM (per Fireworks rate‑limits doc).[^5] Typical per‑model serverless ceilings are around 600 RPM (10 RPS) and dynamic TPM; account‑wide hard cap is 6,000 RPM.[^5] | Rate‑limit overflows use `429 Too Many Requests`; platform outages use `503 Service Unavailable`.[^9] | Serverless 429 means RPM/TPM exceeded; Fireworks recommends exponential backoff and reading rate‑limit headers.[^9] On dedicated/on‑demand deployments there are no account‑level rate limits; a 429 there signals the GPUs are saturated and you must scale the deployment.[^9] Single requests are not documented as being queued beyond capacity; exceeding limits yields 429. | Fireworks exposes many upstream models but does not currently ship a generic strict JSON‑schema surface; structured outputs depend on the upstream model (e.g. OpenAI) or your own prompting.[^9] | Fireworks has no public “prompt caching discount” surface; cost optimizations focus on dedicated deployments and batching.[^5][^9] | Cheapest paid step is adding a payment method and entering Tier 1 with a \$50/month cap; serverless per‑token pricing then applies, and your dynamic limits scale up with spend.[^5] |
| **DeepInfra** | DeepInfra documents **concurrent request limits**, not RPM/TPM: default 200 concurrent requests per model. At 1s average duration that’s ~12,000 RPM; at 10s, ~1,200 RPM.[^8] They don’t publish a free‑vs‑paid RPM/TPM table; usage is billed per token with a generous default concurrency ceiling, suitable for small teams.[^8][^13] | Exceeding concurrency or internal capacity yields HTTP `429` with a simple “Rate limited” message; occasional 429 can appear even under limit when a model is temporarily busy.[^8] | No `Retry-After` header is documented; guidance is to “retry after a short delay” and optionally request a limit increase.[^8] Single large requests within concurrency are accepted; there’s no separate TPM bucket documented, so overflow is about active request count, not minute‑level tokens.[^8] | DeepInfra doesn’t document strict JSON schema decoding; JSON reliability depends on model and prompting. | DeepInfra supports **automatic prompt caching** and explicit keys + retention windows (5m or 1h), with cached input billed at a discounted rate; retention can be enforced via `prompt_cache_key` and `prompt_cache_options`.[^14][^15] Cached tokens reduce billed cost but DeepInfra’s rate‑limit doc is concurrency‑based, not TPM‑based, so caching doesn’t change concurrency limits.[^8][^14] | DeepInfra runs pay‑as‑you‑go pricing across models, with some 50% cached‑prompt discounts on specific models (e.g. Qwen3 Coder) according to 2025 community posts (older than six months).[^16] Official 2026 docs emphasize per‑token billing without a free tier RPM table.[^8] |
| **Cerebras Inference** | Official rate‑limit docs (June 2026) show **Free trial** tier: 5 RPM, 30k TPM, 1M tokens/day, on `gpt-oss-120b` and GLM‑4.7.[^17][^18] Developer tier (unlocked by first pay‑as‑you‑go purchase) raises per‑model limits to e.g. 1,000 RPM / 1M TPM on `gpt-oss-120b`, with daily caps removed.[^17][^18] | Cerebras uses `429` for rate‑limit errors; August 2026 change‑log describes dual‑bucket limiting (“uncached TPM” and “total TPM”) with 429 indicating which bucket was exceeded.[^19] | Rate‑limit responses distinguish between uncached and total token limits; headers document remaining and reset intervals in the console. Single requests that exceed uncached TPM are rejected with 429; there’s no documented queuing beyond normal capacity.[^19] | Strict structured outputs depend on upstream models (OpenAI GPT‑OSS, GLM) rather than a Cerebras‑specific JSON schema layer; Cerebras doesn’t document its own structured JSON surface.[^17][^4] | Cerebras now treats cached tokens as exempt from the **uncached TPM** limit; cached prefix reuse lets you process more total tokens within the same uncached budget.[^19] Billing still charges cached tokens at a discounted rate; exact discount varies by model and is not spelled out in the change‑log.[^19][^17] | Cheapest step up: first pay‑as‑you‑go purchase (docs mention “Developer tier starting at \$10”), which unlocks much higher RPM/TPM and removes hourly/daily caps.[^17][^18] |
| **Mistral La Plateforme** | Mistral’s own console is the source of truth; public docs no longer publish fixed RPM, but third‑party monitoring (July 2026) notes a free **Experiment** tier with ~1B tokens/month and low RPM (check console), and a pay‑as‑you‑go tier with ~300 RPM baseline on `mistral-large-3`.[^3] Free/trial workspaces are described as ~1 req/sec and ~500k TPM in a July 2026 monitoring guide (not an official doc).[^20] | Exceeding any workspace‑level limit (req/sec, TPM, monthly cap) yields `429`; docs and monitors treat 429 as the standard rate‑limit signal.[^20][^3] | Responses include a body describing which limit was hit; standard advice is exponential backoff and upgrading from free to pay‑as‑you‑go for production.[^20][^3] There is no public description of queuing large over‑budget requests; assume immediate 429. | Mistral exposes **schema‑constrained structured outputs** across models; 2026 comparative work lists Mistral alongside OpenAI/Gemini as supporting constrained JSON on La Plateforme.[^4] That article (Jan 2026) is just over six months old, but corroborated by current API examples in the docs. | Mistral supports **context caching** that discounts repeated prefixes; a July 2026 write‑up notes a batch discount and “context caching discounts repeated‑prefix input at a rate not yet published”, so the exact cached‑token price is unclear.[^3] | Cheapest paid step: add a billing card to your La Plateforme workspace; pay‑as‑you‑go has no monthly minimum and unlocks production RPM/TPM. Batch mode grants further discounts.[^3] |
| **OpenRouter** | Free tier for `:free` models: **20 requests/minute** and **50 requests/day** across ~28 free models (DeepSeek R1, Llama 3.3 70B, Gemini Flash, etc.). Spending **\$10 once** in credits raises the daily limit to **1,000 requests/day** but per‑minute stays at 20.[^6] TPM limits depend on upstream providers.[^6] BYOK routing offers 1M free routed requests/month.[^6] | OpenRouter itself rate‑limits on RPM/RPD, returning `429`; underlying providers may also rate‑limit with their own 429/503 semantics. The router’s logs show which provider failed.[^6][^21] Payload‑size issues use generic 413. | OpenRouter exposes `x-openrouter-…` headers for response caching (HIT/MISS, TTL) and surfaces usage and cached tokens from upstream providers; its own RPM/RPD are simple fixed caps.[^21][^22] Single requests above RPM are rejected immediately; no queueing documented. | Structured output support depends on the upstream provider (OpenAI, Claude, Gemini, Mistral, Z.ai, MiniMax, DeepSeek). 2026 comparisons show strong strict JSON from OpenAI, Claude, Gemini; routers pass through that behavior.[^11][^4] | OpenRouter supports **prompt caching and response caching**. Prompt caching: for some upstreams (GLM‑5, MiniMax‑M2.5) cached tokens get 0.1–0.5× normal input price; others (DeepSeek, Kimi, GPT‑4o, Claude) expose no cached tokens.[^23][^24] Response caching: `X-OpenRouter-Cache: true` makes identical requests free and instant; cache hits do **not** count against provider rate limits.[^21][^22] | Cheapest paid step: buy \$10 credits once to raise daily free‑model limit to 1,000 requests/day; pay‑as‑you‑go applies per‑model pricing thereafter.[^6] BYOK routing offers 1M free requests/month before a 5% routing fee on the underlying provider’s rate.[^6] |
| **Z.ai / Zhipu GLM** | Consumer “coding plan” article (June 2026, not API‑specific) shows Lite/Pro/Max subscription plans with prompt caps per 5‑hour window and weekly caps, e.g. Lite 80 prompts/5h, 400/week; Max 1,600 prompts/5h, 8,000/week.[^25] These are product‑level, not API RPM/TPM. API pricing for GLM‑5.2 is quoted at ~\$1.40/1M input, \$4.40/1M output, about one‑sixth Claude Opus.[^25] I could not find a current official API rate‑limits doc in English. | Z.ai’s own API error semantics are poorly documented in English; their GLM endpoints typically use `429` for rate limits and `413` for payload size, but this is based on indirect reports, not primary docs (older than six months).[^23] | Unknown in detail; no public `Retry-After`/`x-ratelimit-*` documentation surfaced. | GLM‑5 via OpenRouter shows strong prompt caching and structured‑output support; native Z.ai structured JSON support is present but poorly documented in English.[^23][^26] | Z.ai supports prompt caching discounts natively (GLM‑5 billing 75% less on cached prefixes in OpenRouter experiments); exact caching rules and rate‑limit interactions are poorly documented.[^23][^24] | Cheapest paid API tier is unclear from English docs; GLM‑5.2 per‑token prices are known, but rate‑limit and subscription tiers are aimed at domestic China users.[^25] |

Where I’ve relied on sources older than six months (e.g. Groq compound description from a March 2024 guide, Mistral structured outputs from a Jan 2026 article, DeepInfra cached‑prompt pricing from 2025), I’ve either cross‑checked against newer docs when possible or explicitly noted that the claim may be stale.[^16][^4][^27]

***

## Groq and `groq/compound` specifically

### What `groq/compound` is

- Groq’s own docs list `groq/compound` alongside models, with a rate‑limit row and no special endpoint; it behaves like a model ID on the chat/completions API.[^1]
- External guides describe Compound as an **agentic AI system** that can perform web search, site visits, code execution and other tools server‑side. This description is from March 2024 – older than six months – but consistent with Groq’s current positioning of “Compound AI systems” as multi‑tool agents.[^27]

Given the age of the detailed description, I would treat `groq/compound` as **agentic**, not a plain text model: it may trigger web search and other tools even when your prompt doesn’t ask for it, which can inflate token usage and latency and complicate your failure semantics. (Older than six months.)[^27]

### Rate limits and token accounting vs ordinary Groq models

- Rate‑limit table (Aug 2026) shows `groq/compound` at 30 RPM, 250 RPD, 70k TPM on the Developer plan.[^1]
- A June 2026 pricing guide notes that **Compound AI systems on the paid developer tier are capped at ~200 RPM and 200k TPM**, lower than simple text models which often reach ~1,000 RPM / ~250k TPM.[^10]
- Groq’s docs emphasize that **rate limits are organization‑wide** and that **cached tokens do not count towards TPM**, which is particularly relevant if Compound reuses long system prompts.[^10][^1]

Groq does not publicly break out server‑side “tool tokens” vs “text tokens” in its rate‑limit docs: everything the model and tools consume counts toward TPM, except cached‑prefix hits which are explicitly exempt.[^10][^1]

### Is `groq/compound` appropriate for deterministic structured JSON?

From current docs:

- Compound is optimized for agentic, search‑enhanced workflows; nothing in Groq’s 2026 documentation claims it has **better structured‑output behavior** than a standard text model. (Compound description source is older than six months.)[^27][^1][^10]
- Groq’s structured JSON behavior is inherited from the upstream model. For example, `openai/gpt-oss-*` models can benefit from OpenAI’s Structured Outputs when called via OpenAI’s own API, but Groq’s wrapper does not expose an equivalent `json_schema` surface in its own docs.[^4][^1]

Given that, **Compound is not the right choice** for deterministic `response_format: {"type": "json_object"}` calls that need schema‑valid output and no web search. Use a **plain model** instead (e.g. `openai/gpt-oss-20b` or `llama-3.1-8b-instant`) and keep agentic behavior out of this pipeline.[^1][^10]

### Does `groq/compound` honor `response_format: {"type": "json_object"}`?

Groq exposes OpenAI‑style `response_format` parameters on its chat API, but there is **no public, Groq‑side documentation** asserting that Compound respects `type: "json_object"` more strictly than other models.[^1]

Because Groq doesn’t publish its own constrained‑decoding JSON API, anything beyond “syntactically valid JSON” is best‑effort prompting. For **guaranteed schema‑valid JSON**, you should not rely on Compound or Groq wrappers; use native structured‑output APIs (OpenAI, Claude, Gemini, or Mistral) directly.[^11][^26][^4]

### Correct Groq model choice for cheap, fast, schema‑valid JSON

Given your volume and latency targets:

- For Groq itself, **`openai/gpt-oss-20b`** is a good balance of speed and cost for JSON: it’s fast (~1,000 tok/s) and cheap per MTok, with decent rate limits.[^10]
- **`openai/gpt-oss-120b`** is still listed in Groq’s August 2026 rate‑limits table (30 RPM, 1,000 RPD, 8k TPM, 200k TPD), so it’s available and current. It’s more expensive but has higher quality; still no Groq‑native strict JSON.[^1]
- If you want true strict JSON and are willing to pay a bit, the most robust pattern is: **use Groq for cheap non‑critical calls**, but route **critical structured outputs to Gemini or Mistral** using their native schema‑constrained APIs.[^2][^3][^4]

***

## Structured output reliability (schema vs prompt)

### Who supports strict / constrained JSON schema decoding?

From 2026 comparative work and docs:

- **OpenAI** – Structured Outputs with `response_format: { type: "json_schema", strict: true }` and tool strict mode; ~0.0% schema failures in a 500‑request test. (June 2026 benchmarks; OpenAI isn’t in your provider list but matters conceptually.)[^26][^11][^4]
- **Anthropic (Claude)** – `output_config.format` + `strict: true` on tools and dedicated structured output path; ~0.2% failures in the same study. (Some of this is January 2026 and older than six months; behavior is still consistent.)[^11][^26][^4]
- **Google Gemini** – `responseSchema` with MIME `application/json` and strict JSON Schema enforcement; ~0.6% failures in the 500‑request test.[^4][^11]
- **Mistral La Plateforme** – custom structured outputs with schema‑constrained JSON across models; documented alongside those three as “grammar‑constrained JSON”. (Jan 2026; older than six months.)[^4]

None of Groq, Together, Fireworks, DeepInfra, Cerebras or OpenRouter add their **own** strict JSON layer; instead they proxy or host models that may support structured outputs on their native APIs (e.g. OpenAI via Fireworks or OpenRouter).[^17][^12][^8][^6][^9][^4][^1]

### Unsupported schema features and gotchas

From the August 2026 structured‑output deep dive (and earlier Jan 2026 work, which is >6 months old but still the best synthesis):[^26][^4]

- **OpenAI strict mode**
    - Every object must set `additionalProperties: false`; schemas that omit this are rejected.[^26]
    - Every field must appear in `required`; “truly optional” fields need to be expressed as nullable types instead.[^26]
    - Max nesting depth around 10 levels; very large schemas (over ~120k characters) or more than ~1,000 enum values are rejected.[^26]
- **Gemini**
    - Supports enums, numeric bounds, array bounds, and `propertyOrdering`; some features (like external `$ref`) are silently ignored.[^4][^26]
    - Large or deeply nested schemas may be rejected, but no numeric ceiling is publicly disclosed.[^26]
- **Claude**
    - More restrictive subset than OpenAI: no recursive schemas, narrower `oneOf`/`anyOf` support; optional fields again need nullable types.[^4][^26]
- **Cross‑provider schemas**
    - A single JSON Schema that works on OpenAI may be rejected on Gemini or Claude and vice versa; 2026 guidance is to **maintain provider‑specific variants** rather than one shared schema.[^4][^26]

Your observation about Pydantic’s `model_json_schema()` omitting `additionalProperties: false` and full `required` arrays is consistent with these findings: using raw Pydantic output directly in strict mode will get you rejected or partial enforcement.[^26]

### Array outputs: dropped elements under load?

There is no official provider doc stating “we may drop array elements under load”, but empirical work in 2026 shows:

- **Plain JSON mode** (no constrained decoding) fails 8–15% of the time on non‑trivial schemas, with common issues including missing entries in arrays of structured items.[^11][^4]
- **Strict structured outputs** (OpenAI, Claude, Gemini) reduce parse/schema failures to under 1%, but still do not **semantically guarantee** “exactly N items”; they only guarantee syntactic/schema validity.[^11][^4][^26]

I couldn’t find a published benchmark or issue‑tracker discussion specifically measuring “array element dropping” under load, but given the 8–15% failure rates in plain JSON mode, you should assume that **array length is not guaranteed** unless your schema encodes it (e.g. via `minItems`/`maxItems` both = N) and the provider actually honors those keywords.[^11][^26]

***

## Practical patterns for robust array‑returning calls

Given the above, patterns that are widely recommended in 2026:[^4][^26]

1. **Encode the count in the schema**
    - Add `minItems: N` and `maxItems: N` to your array definition, and ensure the provider accepts those keywords (Gemini, OpenAI, Claude, Mistral do). This forces sampling to respect length where grammar‑constrained decoding is truly enforced.[^26][^4]
2. **Echo input IDs and include a count field**
    - Each array element should include a stable `id` that matches your input index; add a top‑level `expected_count` field and validate both the count and coverage on the client side.
3. **Retry on structural mismatch, not just syntax errors**
    - Your client should treat “array length != N” or “missing one of the expected IDs” as a parse failure, not a business error, and rerun the call with a backoff.
4. **Avoid per‑item calls unless absolutely necessary**
    - Providers strongly discourage “N requests for N items” when rate limiting is per minute; the strict JSON modes are designed to keep multi‑item outputs workable.[^7][^2][^1]

Your current failure (“my code assumes every input index comes back and crashes when one does not”) is exactly the pattern that 2026 guidance warns against: treat the length and coverage as part of validation and apply retries upstream rather than letting the crash propagate.[^11][^4][^26]

***

## Prompt caching: who supports what, and does it help with rate limits?

### Providers with explicit cached‑prefix support and discounts

From 2026 docs and measurements:

- **Groq** – automatic prompt caching per org and model; cached input prefixes are billed at 50% of normal input price and **do not count toward TPM rate limits**. This is explicitly stated, and directly helpful for your problem.[^10][^1]
- **DeepInfra** – automatic prefix caching plus explicit `prompt_cache_key` and retention windows (5m / 1h). Cached tokens are billed at a reduced “cache‑read” rate; retention incurs a write premium. Caching affects billing and latency but rate‑limit enforcement is concurrency‑based, not TPM, so it does not change rate limits.[^8][^15][^14]
- **Cerebras** – dual‑bucket limiting where cached tokens don’t count against the **uncached TPM** bucket; this lets you push more total tokens through within the same uncached budget.[^19]
- **Mistral** – context caching with a discount on repeated‑prefix input; exact cached‑token price is “not yet published”, per July 2026 monitoring.[^3]
- **OpenRouter** – prompt caching and response caching:
    - Prompt caching: for models like GLM‑5 and MiniMax‑M2.5, repeat prefixes show thousands of `cached_tokens` and 62–75% cost reductions; other models show no cached tokens.[^23][^24]
    - Response caching: `X-OpenRouter-Cache: true` gives free, instantaneous responses for identical requests; cache hits do **not** reach the provider and thus do not consume provider rate limits.[^21][^22]


### Does caching reduce *rate‑limit* consumption or just billing?

- On **Groq**, cached tokens explicitly do **not count** towards TPM, so caching reduces both billing and rate‑limit pressure.[^10][^1]
- On **Cerebras**, cached tokens bypass the uncached TPM bucket; they still count towards total TPM but the effective budget is widened.[^19]
- On **DeepInfra**, **Mistral**, and **OpenRouter**, cached tokens reduce billing and latency but do not alter RPM or concurrency limits; rate limiting is separate from caching.[^14][^22][^8][^3][^23][^21]

For your pattern (long stable schema + pain list + config, repeated 7–10 times per prospect), Groq’s caching is uniquely helpful because it directly reduces TPM consumption against the org limit. On other providers, caching is mostly a cost and latency optimization, not a rate‑limit escape hatch.

***

## Fallback chain design \& failure semantics

### Is multi‑provider fallback still good practice?

For small B2B agents like yours, in 2026 the standard pattern is:

- **One primary provider** with strict structured JSON and clear rate‑limit headers (Gemini, Mistral, OpenAI/Anthropic if you can afford them).[^2][^3][^11][^4][^26]
- **One router or secondary provider** for cheap/fast non‑critical calls and emergency fallback (OpenRouter, Together, Groq).[^12][^6][^7][^1]

A naive “primary → secondary → tertiary” chain that independently discovers outages for each call is considered an anti‑pattern; instead, best practice is:

- A **global pipeline deadline** (e.g. 45–60 seconds for your 7–10 calls).
- **Per‑provider circuit breakers** that open quickly on repeated 429/5xx failures and keep subsequent calls from exploring the same failure.
- A **queue with backpressure** when more prospects arrive than your primary/secondary can handle; this is often hosted in Redis or a lightweight job queue, not per‑call retries.


### Standard patterns and libraries (Python)

Using general engineering practice (not tied to a specific provider doc):

- For retries and backoff: `tenacity` or `aiohttp`’s retry middleware with **exponential backoff honoring `Retry-After`** where available (Groq, Fireworks, Together, some routers).[^9][^7][^1]
- For circuit breakers: libraries like `pybreaker` or a custom implementation that tracks failure counts per provider and opens the breaker on threshold, with half‑open probing.
- For global deadlines: pass a “time budget” object down the pipeline (e.g. `deadline = start_time + 45s`), and have each call compute `timeout = max(1s, deadline - now)` rather than a fixed 60s timeout.

These patterns don’t need provider‑specific docs, but they align with what rate‑limit and monitoring guides recommend (exponential backoff, avoiding bursts, using dedicated endpoints or higher tiers when 429s become normal).[^28][^20][^9][^7]

### Detecting “listed but not callable” models

There is no universal fix, but common patterns:

- Treat “404 Not Found” or provider‑specific `model_not_found` errors as **structural**, not transient; mark that model ID as disabled in configuration for the remainder of the run.
- Compare `models.list()` output against a **manually curated allow‑list** of models you’ve actually tested, rather than auto‑trusting everything listed.
- On routers (OpenRouter, Together), check provider status pages and logs; they often call out models that are temporarily disabled.[^6][^28][^21]

***

## Direct recommendations: one primary and one fallback

### Primary: Gemini or Mistral for strict JSON

For **structured, schema‑valid JSON at your volume**:

- **Primary choice: Gemini 2.x (Flash or Pro)**
    - Strict JSON via `responseSchema`, well‑documented; failure rate under 1% in benchmarks.[^11][^4]
    - Clear 429 semantics and burst queueing behavior; high RPM for public/private endpoints.[^2]
    - Very suitable for your 7–10 calls / prospect pattern, with 1–6k tokens per call and single‑digit seconds latency.
- **Alternative primary: Mistral Large / Medium on La Plateforme**
    - Structured outputs documented; free Experiment tier with ~1B tokens/month is generous enough to explore.[^3][^4]
    - Pay‑as‑you‑go unlocks ~300 RPM baseline and higher limits over time.[^3]

If you want to stay closer to your current stack and keep some free capacity:

- Use **Groq + `openai/gpt-oss-20b`** for non‑critical tasks (drafting, hooks, classifier), taking advantage of caching and low token prices.[^10]
- Reserve **Gemini** (or Mistral) for **ranker and verifier** calls that must return schema‑valid JSON.


### Fallback: OpenRouter or Groq

For **fallback and cost‑optimization**:

- **OpenRouter** makes sense as a fallback because:
    - You can route to GLM‑5, MiniMax‑M2.5, DeepSeek, Mistral, and Gemini through a single endpoint.[^24][^6][^23]
    - Prompt caching and response caching reduce both cost and repeated failure surface; response cache hits don’t consume provider limits.[^22][^21]
    - Free tier (20 RPM, 1k RPD after \$10) is ample for your volume.[^6]
- **Groq** remains useful as **cheap, blazing‑fast fallback** for non‑schema‑critical calls:
    - Caching doesn’t count against TPM, which is very friendly to your “fixed prefix + variable tail” pattern.[^1][^10]
    - You can keep using `openai/gpt-oss-*` or Llama 3.x models without Compound’s agentic overhead.

Given your preference for deterministic behavior, I’d recommend:

- **Primary:** Gemini Flash/Pro with strict `responseSchema` for all structured JSON calls.
- **Fallback:** Groq (`openai/gpt-oss-20b` or `llama-3.1-8b-instant`) for cheap, prompt‑level JSON plus OpenRouter for emergency structured‑output rerouting when Gemini is degraded.

***

## Specific mistakes in your current setup to stop making

Based on the evidence above, the biggest issues in your current design are:

1. **Using `groq/compound` for non‑agentic, structured JSON calls**
    - Compound is an agentic system optimized for search and tools, with tighter rate limits and no special structured‑output guarantees; using it as a generic JSON generator increases token usage, latency, and rate‑limit fragility. (Compound description source is older than six months.)[^27][^1][^10]
2. **Assuming 413 == token budget overflow on Groq**
    - Groq’s official rate‑limit docs say 429 is used for rate‑limit violations; 413 is not documented as a token‑budget signal. Your 413 incident likely arose from payload or some other constraint, and retrying it as if it were a transient quota issue caused unnecessary ladder burn.[^1]
3. **Treating each call as independently discovering outages**
    - Without a global pipeline deadline and circuit breakers per provider, every call in your 7–10‑step chain can re‑hit the same outage and run a full retry ladder, leading to multi‑minute hangs and exhausted quotas.[^20][^28][^9][^7]
4. **Assuming “N items in, N items out” without structural validation**
    - With plain JSON mode, failure rates up to 8–15% are normal; missing or extra array elements are a known failure mode. Your current assumption that every index returns once and only once is brittle; you need schema‑level min/max bounds and client‑side coverage checks.[^11][^4]
5. **Using Pydantic’s raw `model_json_schema()` for strict structured‑output APIs**
    - Strict JSON schema modes (OpenAI, Gemini, Claude) require `additionalProperties: false` and full `required` arrays; raw Pydantic output omits these, causing rejection or partial enforcement. You should post‑process schemas before sending them or maintain hand‑tuned JSON Schema files per provider.[^26]
6. **Not leveraging prompt caching where it helps most**
    - On Groq, cached tokens don’t count towards TPM; your long, repeated prefixes are ideal candidates for caching. Currently you’re paying and consuming rate limit for full prefixes 7–10 times per prospect.[^10][^1]

If you re‑architect around **strict structured outputs for ranker/classifier/verifier**, **Groq caching for cheap prefix reuse**, and a **global deadline + per‑provider circuit breaker**, your pipeline should comfortably stay within free/entry limits and avoid the multi‑minute hangs and quota burns you’re seeing now.
<span style="display:none">[^29]</span>

<div align="center">⁂</div>

[^1]: https://console.groq.com/docs/rate-limits

[^2]: https://developer.gemini.com/rate-limit

[^3]: https://www.rapidevelopers.com/ai-api-limits-performance-matrix/mistral-large

[^4]: https://collinwilkins.com/articles/structured-output

[^5]: https://aipromptshub.co/limits/fireworks-rate-limits

[^6]: https://klymentiev.com/blog/openrouter-free-tier

[^7]: https://docs.together.ai/docs/serverless/rate-limits

[^8]: https://docs.deepinfra.com/account/rate-limits

[^9]: https://docs.fireworks.ai/guides/inference-error-codes

[^10]: https://www.eesel.ai/blog/groq-pricing

[^11]: https://hamzashabbir.dev/article/reliable-json-llm-structured-outputs-compared-2026

[^12]: https://aipromptshub.co/limits/together-rate-limits

[^13]: https://deepinfra.com/

[^14]: https://docs.deepinfra.com/chat/prompt-caching

[^15]: https://docs.deepinfra.com/chat/prompt-cache-retention

[^16]: https://www.reddit.com/r/kilocode/comments/1n6qh7v/v0860_deepinfra_is_now_in_kilocode_50/

[^17]: https://www.morphllm.com/cerebras-pricing

[^18]: https://locoroo.net/reports/2026-june/cerebras

[^19]: https://inference-docs.cerebras.ai/support/change-log

[^20]: https://apistatuscheck.com/blog/mistral-api-monitoring-guide

[^21]: https://x.com/OpenRouter/status/2050616603830530072

[^22]: https://x.com/OpenRouter/status/2050616590098473445

[^23]: https://china-llm.com/blog/openrouter-prompt-caching

[^24]: https://www.aibase.com/news/29789

[^25]: https://zenn.dev/ykkn/articles/d5f31dc2c375e4?locale=en

[^26]: https://www.digitalapplied.com/blog/llm-structured-output-json-reliability-production

[^27]: https://www.ampcome.com/post/how-to-use-groq-api-the-comprehensive-guide-you-need

[^28]: https://apistatuscheck.com/blog/together-ai-api-monitoring-guide

[^29]: https://docs.together.ai/docs/billing-usage-limits

---

# Verification notes (Claude, 2026-08-24)

Added after reading. Perplexity has a history of confident-but-wrong numbers on this project; nothing below has been confirmed against a primary source unless marked.

## VERIFIED against our own account dashboards (2026-08-24)

Ground truth now lives in `Groq API Key Rate Limit.md` and `Gemini API Key Rate Limits.md` at repo root — screenshots of our actual org limits. These supersede both Perplexity and `HANDOFF.md`.

### Groq — Perplexity was exactly right

| Model | RPM | RPD | **TPM** | TPD |
|---|---|---|---|---|
| `groq/compound` | 30 | 250 | 70K | no limit |
| `openai/gpt-oss-120b` | 30 | 1K | **8K** | 200K |
| `openai/gpt-oss-20b` | 30 | 1K | **8K** | 200K |
| `qwen/qwen3.6-27b` | 30 | 1K | **8K** | 200K |

Perplexity's Groq row matched this table exactly (compound 30/250/70K; gpt-oss-120b 30/1K/8K/200K). That row is confirmed.

**The 413 mechanism is now definitively settled.** Compound has **70K TPM** and *no daily token cap*. A ~200-character query cannot overflow a 70K/min bucket. My original "TPM overflow" claim is conclusively wrong, and Perplexity's "genuine payload size" is also wrong for a 200-char body. The only reading left standing: **compound's server-side tool expansion inflated the assembled context past the model's limit.** Agentic behaviour, not quota.

**The decisive constraint nobody had named: every non-compound Groq chat model is capped at 8K TPM.**
Measured token cost of one prospect, from the snapshot payload sizes:

| Stage | ~tokens |
|---|---|
| Ranker, 3 batches | ~2,300 |
| Hook articulation | ~600 |
| Drafter | ~750 |
| Classifier | ~250 |
| **Verifier ×2** | **~11,000** |
| **Total** | **~15,000** |

Against an 8K/minute ceiling, **a single prospect cannot complete inside one minute**, and one verifier call alone (~5.5K) is 69% of the per-minute budget. At 200K TPD that is ~13 prospects/day.

**The verifier is ~73% of all token spend.** Capping its evidence to the cards that actually support the draft takes a prospect from ~15K to ~4.7K tokens — fits inside 8K TPM with headroom, and lifts the daily ceiling to ~42 prospects. **D7 is therefore the highest-leverage fix in the entire backlog**, not a payload nicety.

### Gemini — free tier is ~20 requests/day, so it cannot be primary

Read from the AI Studio dashboard screenshot. **The table is `peak usage / limit`, not limits alone** — every row reads "0 / N", meaning zero used against a limit of N over the last 28 days. All usage is zero because Groq has been primary.

Per-model limits for our key:

| Model | RPM limit | TPM limit |
|---|---|---|
| Gemini 3.1 Flash Lite | 15 | 250K |
| Gemini 3.5 Flash Lite | 15 | 250K |
| Gemini 2.5 / 3.5 / 3.6 / 3.7 Flash | 5 | 250K |
| Gemini 2.5 Pro · 3.1 Pro · Gemini 2 Flash | 0 | 0 |

**The binding limit is not in the table.** The "Peak requests per day (RPD)" trend chart at the bottom of the dashboard shows a limit line at **20 RPD** for Gemini 3.6 Flash. This confirms `HANDOFF.md:97` ("Free Gemini tier is 20 requests PER DAY per model"), which I wrongly retracted on the grounds that no daily column appeared in the table view. It is charted, not tabulated.

**Consequence:** at ~7 LLM calls per prospect, 20 RPD is **under 3 prospects per day**. Gemini cannot be the primary provider regardless of its generous 250K TPM. It is viable only as a **fallback for a small number of calls**, or spread across several models to multiply the daily budget (each model carries its own RPD).

Perplexity's "120 RPM / 600 RPM" claim remains wrong, and its recommendation of Gemini as primary is wrong for our tier — right conclusion shape, wrong numbers, wrong outcome.

**This removes the second of the two routes I proposed.** Groq stays primary on limits alone (30 RPM / 1K RPD / 8K TPM / 200K TPD), which makes **D7 — capping verifier evidence — the only route to a working free tier**, not one option of two. The 8K TPM ceiling and the 73%-of-spend verifier are now the whole problem.

Rows showing a `0` limit (Gemini 2.5 Pro, 3.1 Pro, Gemini 2 Flash, 2 Flash Lite) are genuinely unavailable, independently confirming HANDOFF's 404s. `provider.py:131` targets `gemini-2.5-flash`, which shows a **5 RPM limit** here rather than 0 — so it may be callable after all, contradicting `HANDOFF.md:89`. One live call settles it.

## AMBER — plausible, high-leverage, must be confirmed

**"Cached tokens do not count towards Groq TPM."** Now considerably more important than when first noted: with the ceiling confirmed at **8K TPM**, exempting a cached prefix is the difference between fitting a prospect in one minute and not. Our shape is a fixed prefix (pains block + JSON schema + system prompt) re-sent 7–10× per prospect. Cited only to a June 2026 pricing page. **Verify in Groq's own docs before designing around it** — if false, D7 (capping verifier evidence) is the only route to fitting inside 8K TPM.

**Free-tier limits for providers we do not hold keys to** (Together, Fireworks, DeepInfra, Cerebras, Mistral, OpenRouter) remain entirely unverified. The Groq and Gemini rows are now settled by our own dashboards; nothing else in that table is.

## Correction to my earlier claim

Superseded by the VERIFIED section above: my "413 = TPM overflow" claim is conclusively wrong (compound has 70K TPM). Conclusion unchanged — compound is the wrong model for structured JSON calls — but the mechanism is server-side tool expansion, not quota.

## GREEN — consistent with what I found in the code

- Compound is agentic and inappropriate for deterministic structured output. Matches `provider.py:207` + `compound.py:8` sharing one bucket.
- No global deadline / circuit breaker is the cause of multi-minute hangs. Matches `provider.py:223`.
- Models can silently drop array elements under load — corroborates the crash path at `drafter.py:63` (D16).
- Pydantic's raw `model_json_schema()` omits `additionalProperties: false` and full `required`. Already documented in `HANDOFF.md:99`.
