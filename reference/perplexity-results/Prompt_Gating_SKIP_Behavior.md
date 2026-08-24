# Perplexity Research: Prompt-Level Gating & "SKIP" Behavior

**Source:** Perplexity
**Date:** August 22, 2026

---

You won’t find Apollo/Clay/11x’s *exact* internal system prompts, but their public docs and community posts are detailed enough to copy the patterns: role‑based prompts with explicit evidence listing, hard missing‑data rules, and JSON outputs that carry confidence + reasons + citations.[^1][^2][^3][^4][^5]

Below is a distilled, Claude‑ready version of those patterns you can drop straight into your Drafting stage.

***

## Prompt‑level gating patterns in Apollo \& Clay

Apollo’s AI prompt guides emphasize four parts: context (“you are an expert researcher”), where to search (company site, PR, LinkedIn), what to analyze (e.g., AI adoption level), and an output section that *must include reasoning and source links* so the user can verify the facts before personalization.[^3][^1]
They also show explicit fallback instructions like “If no recent and relevant information is found, respond ONLY and EXACTLY with ‘No news found online in the last 3 months’” plus rules to skip uncertain or stale news, which is effectively a prompt‑level SKIP when data is missing or old.[^3]

Claygent’s prompt engineering guides push a similar structure: role context (“you are a B2B research analyst”), a specific task tied to concrete pages, an explicit output JSON schema, and constraints like “Return ONLY valid JSON. If you cannot find the information, return null for that field.”—with an added confidence field and reasoning that downstream steps filter on.[^2][^4]
The AutoClaygent lessons formalize this into five parts: input context, goal, step‑by‑step instructions with decision logic, fallback instructions for missing data, and a JSON output spec with fields like `confidence` and `evidence_url`, plus rules like “If no platform detected, return empty array (don’t guess).”[^6]

**Implication for you:** Your drafting prompt should (1) force the model to list verified facts + sources first, (2) apply decision logic to label the situation as `PROCEED`, `LOW_CONFIDENCE`, or `SKIP`, and only (3) conditionally generate the email body when status is `PROCEED`.

***

## JSON output schemas you can mirror

Claygent routinely returns structured payloads with fields such as yes/no, reason, confidence score, and a citation URL “inside one row, all populated from one page visit.”[^2]
Their JSON schema guidance requires an object root with `additionalProperties: false` on every nested object, enumerated fields, and explicit `confidence` and evidence fields; optional fields are handled via `anyOf` with null, rather than being omitted.[^7]

Clay’s wiki recommends adding a `confidence` field and filtering downstream processes to only run on high‑confidence results, and instructs Claygent to return `null` for fields when data can’t be verified instead of fabricating.[^4]
LeadMagic’s GTM prompts toolkit generalizes this pattern: every prompt must have role + task, named inputs, an explicit output format (JSON/markdown template), constraints, and a missing‑data rule like “If unknown, return null—do not guess,” plus a `source_url` requirement for factual claims.[^5]

**A Claude‑friendly schema for your Drafting stage could look like:**

```json
{
  "status": "PROCEED" | "LOW_CONFIDENCE" | "SKIP",
  "confidence_score": 0,
  "skip_reason": null,
  "facts": [
    {
      "fact": "string",
      "source_url": "string",
      "recency_days": 0,
      "used_as_hook": true
    }
  ],
  "email_subject": null,
  "email_body": null
}
```

Where:

- `status` encodes the gate decision.
- `confidence_score` is the model’s self‑reported confidence (0–100 or High/Medium/Low).
- `facts` contains only verified signals with URLs and recency.
- `email_subject` / `email_body` must be `null` unless `status === "PROCEED"`.

That schema is directly inspired by Claygent’s “yes/no, reason, confidence, citation URL” pattern and JSON constraints.[^6][^7][^2]

***

## Handling stale or weak data in prompts

Apollo’s AI prompt examples literally bake time windows into the instructions: one best‑practice template requires the model to return recent news only, and if nothing relevant is found in the last three months, to output a fixed fallback string, with strict guidance to omit uncertain or mis‑matched items.[^3]
Clay’s wiki warns that vague prompts and missing pages cause hallucinations, and explicitly recommends fallback logic like “If the page returns a 404 or the information is not found, return null” plus constraints to prevent the model from guessing when data is sparse.[^4]

AutoClaygent goes further by defining confidence criteria—e.g., “high = subdomain pattern match, medium = redirect/widget, low = text mentions only”—and instructs the model to return an empty array when platforms can’t be verified, instead of inferring from weak hints.[^6]

**Translate this to your signals:**

- Include `recency_days` (you already have this) in the prompt input and tell Claude:
    - “If all candidate hooks have `recency_days > 90`, mark them as stale and do NOT use them as the opening hook.”
    - “Stale signals may be mentioned only as context in the body if `status !== "SKIP"`, never as the primary hook.”
- Add a rule: “If no non‑stale authored content or business events exist, set `status` to `SKIP` or `LOW_CONFIDENCE` and return `email_subject` and `email_body` as null.”
- Enforce a missing‑data constraint: “If critical fields like `current_role`, `company_industry`, or any signal with `used_as_hook` cannot be verified, treat the record as `LOW_CONFIDENCE` or `SKIP`—do not invent substitutes.”

This is the same pattern as Apollo’s “No news found online in the last 3 months” fallback and Claygent’s `null` for unavailable fields.[^4][^3]

***

## Concrete Claude system prompt for your Drafting stage

Here’s a Claude‑oriented system prompt skeleton that combines Apollo/Clay patterns with your 2D gate; you’ll pass in your ICP fit, signal strength scores, and a list of signals as JSON in the user or tool message.

> **Role \& mission**
> You are an AI SDR drafting assistant.
> Your mission is to decide whether we have enough *current, verifiable signal* to write a personalized cold email, and to refuse to draft when the data is weak or stale.
>
> **Inputs you receive**
> - `prospect`: name, title, company, industry.
> - `icp_fit`: 1 (good), 2 (somewhat), 3 (not a fit).
> - `signal_strength`: 0–3 based on prior scoring.
> - `signals`: array of candidate hooks with:
>   - `signal_type` ("authored_content" | "business_event" | "firmographic")
>   - `content` (short summary or quote)
>   - `source_url`
>   - `event_date` and `recency_days`
>   - `confidence_score` (0–3)
>   - `relevance_note` (why it matters).
>
> **Decision logic**
> 1. List the facts you intend to rely on, with `source_url` and `recency_days` for each.
> 2. Apply these rules:
>    - If `icp_fit === 3` (not a fit), set `status = "SKIP"`. Do NOT draft an email.
>    - If all candidate signals have `recency_days > 90` OR `confidence_score <= 1`, treat them as stale/weak. Prefer `status = "LOW_CONFIDENCE"` or `status = "SKIP"`.
>    - If no authored or business‑event signals exist and only firmographics remain, prefer `status = "LOW_CONFIDENCE"` or `status = "SKIP"`.
> 3. Only if you can identify at least one **recent (≤90 days), high‑confidence (≥2) authored or business‑event signal** that matches the prospect’s ICP fit may you set `status = "PROCEED"` and use it as the main hook.
>
> **Output format (JSON ONLY)**
> Return a single JSON object with this exact schema:
>
> ```json
> {
>   "status": "PROCEED" | "LOW_CONFIDENCE" | "SKIP",
>   "confidence_score": 0,
>   "skip_reason": null,
>   "facts": [
>     {
>       "fact": "string",
>       "source_url": "string",
>       "recency_days": 0,
>       "used_as_hook": false
>     }
>   ],
>   "email_subject": null,
>   "email_body": null
> }
> ```
>
> **Constraints**
> - If `status` is `"LOW_CONFIDENCE"` or `"SKIP"`, you **must** set `email_subject` and `email_body` to `null` and explain briefly in `skip_reason` why the data is insufficient (e.g., “Only firmographic data; no recent authored content or events”).
> - Do not mention any fact in `email_body` that is not present in `facts`.
> - Do not guess or infer missing details. If something is unknown, omit it and explain in `skip_reason`.
> - If unsure whether a fact is correct, treat it as unusable and lower `confidence_score`.
> - Return **only** JSON. No prose, no Markdown, no explanation outside the fields above.

This prompt mirrors Apollo’s “No news found if older than X months” + explicit output instructions, and Claygent’s JSON + confidence + evidence pattern, but expressed for Claude in your drafting stage.[^5][^2][^6][^3][^4]

On the Next.js side, you’d:

- Run your existing numeric gate first (ICP × signal strength) and pass those scores into this prompt as inputs.
- Parse the JSON, and if `status !== "PROCEED"`, surface the `skip_reason` and facts in your run view as a “needs human judgment / bounce firewall” outcome instead of showing an email.
- If `status === "PROCEED"`, display the email along with the fact list and sources in your UI so the human reviewer can quickly see what the hook is grounded in—exactly what Apollo’s “preview + source links” workflow does.[^8][^1][^3]

<div align="center">⁂</div>

[^1]: https://www.apollo.io/magazine/ai-sdr-how-to-build-your-own
[^2]: https://www.nebor.ai/blog/clay-ai-claygent
[^3]: https://knowledge.apollo.io/hc/en-us/articles/31293336264717-AI-Prompt-Best-Practices
[^4]: https://thegtmos.ai/clay-wiki/claygent-prompts
[^5]: https://leadmagic.io/gtm-skills/ai-prompts-toolkit
[^6]: https://www.autoclaygent.com/lessons/prompt-anatomy
[^7]: https://www.autoclaygent.com/lessons/json-schema
[^8]: https://www.explorium.ai/blog/data-for-gtm/how-to-build-an-outbound-agent-with-apollo/
