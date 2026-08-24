# Antigravity to Claude Transfer (AG_to_C_10)
**Context:** We have successfully built the Golden Set replay harness, generated the snapshots, and discovered exactly why the pipeline is crashing in production (413 Payload Too Large on Free-Tier models like Groq, due to massive scraped text payloads). We are currently in the **Problem Definition Phase**. No code has been executed to solve these issues yet.

The user and I have discussed the current bottlenecks and core structural issues in the pipeline. Please review this summary. Your goal at this stage is strictly to review these identified problems, provide your "daddy agent" strategic oversight, and identify any additional bottlenecks or constraints we might have missed in our past runs.

### 1. Payload & TPM Bottleneck (The 413 Root Cause)
When we hit a popular company (e.g., ShipBob), fetchers like `Jina` and `Exa` return massive unstructured text dumps (full Markdown homepages, SEC headers). Passing 5-15 of these verbatim `SignalCards` easily exceeds Free-Tier TPM ceilings (triggering a 413 Payload Too Large, which then exhausts the fallback chain and hangs). 
*User's Insight:* This bottleneck is especially harmful because, for less popular companies, we *have* to search more broadly to find any signal. If our architecture can't handle a high volume of cards gracefully, we fail both extremes: popular companies crash the system, and unpopular ones don't get searched enough.

### 2. LLM Trimming (URLs & Previews)
We currently pass the entire `snippet` and `source_url` to the Ranker LLM. The LLM only needs to do a binary relevance check. URLs are token-heavy and offer no semantic reasoning value.
*User's Insight:* We need a much deeper strategy for compressing and formatting the information before it reaches the LLM. 

### 3. High-Signal vs. Noisy Fetchers
We blindly fire 14 fetchers per prospect. Our ShipBob snapshot revealed wildly varying quality: `Tavily` brought back specific conversational mentions, while `GoogleNewsRSS` returned generic PR spam, and `Compound` hit its own 413 error.
*User's Insight:* We must evaluate exactly what each fetcher brings to the table and ensure we're getting high-quality data. Firing everything blindly is wasteful.

### 4. Prospect Title & Query Flexibility
Currently, `person_name` and `company` are used, causing namesake collisions. However, hardcoding the prospect's `title` into boolean search queries (e.g., `"John Smith" AND "VP of Sales"`) risks returning zero results if the internet refers to him slightly differently.
*User's Insight:* The "person" or "title" should be a "good-to-have" soft hint, not a hard deciding factor. If a specific VP has no online presence, the pipeline shouldn't fail—it should pivot to company-level signals (like recent funding or product launches).

### 5. Qualification vs. Hallucination Guardrails
The Verifier currently acts as a rigid gatekeeper. If a prospect's company size or sector isn't perfectly identifiable in the search results, the Verifier blocks the entire output (`status: blocked_hallucination`).
*User's Insight:* This breaks the core SDR workflow. If a rep inputs a specific prospect, they *already* intend to email them. Rigid firmographic restrictions are unnecessary blockers. We must decouple "Hallucination Guardrails" (preventing the AI from inventing fake facts) from "Qualification" (scoring if they are a good fit). Qualification should be an optional toggle or a passive warning, not a hard block.

### Claude's Action Required:
- Please review this problem definition. 
- Review the past documented runs and our previous conversations.
- Identify any *other* potential bottlenecks, constraints, or structural flaws in the pipeline that we haven't listed here.
- Do not propose code solutions yet; focus entirely on confirming and expanding the problem space.
