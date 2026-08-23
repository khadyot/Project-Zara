# Project Zen: Architectural Learnings & Patterns

This document summarizes the key takeaways, architectural patterns, and smart design choices extracted from the `project-zen` repository. The project is an automated B2B sales outreach tool that researches a prospect and drafts highly personalized cold emails.

## 1. System Architecture & UI Communication
- **Framework**: FastAPI backend with a simple HTML frontend.
- **Streaming State via SSE**: The backend uses Server-Sent Events (SSE) in `main.py` (`/api/draft`) to stream real-time progress updates to the frontend. This is an excellent pattern for long-running AI agent tasks, as it keeps the user informed ("Researching...", "Judging signal relevance...", "Writing email draft...") instead of letting the UI hang.

## 2. Cost Management & "Gap-Filler" Strategy
The project exhibits a highly optimized, cost-conscious approach to data gathering:
- **Free Sources First**: The pipeline (`pipeline.py`) kicks off a parallel `asyncio.gather` across multiple free sources (Google News RSS, GitHub scraping, Job boards, Jina for company sites).
- **Compound Model for Free Search**: It uses Groq's `compound` model (`backend/fetchers/compound.py`) as an agentic web searcher, saving on paid search API costs.
- **Tavily as a Paid Gap-Filler**: Tavily (a paid search API) is strictly gated. It is *only* called if the free sources yield fewer than 2 person-specific signals. 
- **Strict Budgeting System**: `budget.py` implements a hard budget limit for Tavily usage, tracking it month-to-month and throwing a `BudgetExhausted` exception before making a call if the limit is reached.

## 3. LLM Orchestration & Resilience
- **Multi-Model Redundancy**: `llm.py` attempts to use Groq (`gpt-oss-120b`) first, and if it fails, falls back to Z.ai (`glm-4.5-flash`). This ensures high availability.
- **Robust JSON Extraction**: Instead of relying solely on the LLM to output perfect JSON, `extract_json` strips markdown fences and uses bracket-matching to salvage valid JSON even if there's surrounding prose.
- **Reasoning Model Handling**: The code strips `<think>...</think>` blocks natively for reasoning models, ensuring clean outputs.

## 4. Prompt Engineering: The Ranker -> Drafter Pipeline
The AI drafting process is split into two distinct, highly effective stages:

### Stage 1: The Ranker (`ranker.py`)
- Instead of feeding raw text straight into a drafting prompt, an LLM evaluates the raw signals first.
- It identifies the 1-3 strongest "hooks" and scores them from 0.0 to 1.0 based on recency, person-specificity, and relevance to the seller's value proposition.
- If the top hook's strength is below 0.35, the pipeline gracefully aborts, stating: *"Insufficient signal — a draft here would be generic."* This prevents hallucinated or poor-quality emails.

### Stage 2: The Drafter (`drafter.py`)
- **Evidence-Based Grounding**: The drafter is fed an `_evidence_block` with specific citations. The prompt explicitly forces the LLM to cite these concrete facts, preventing hallucinations.
- **Format Randomization**: To prevent all generated emails from sounding like the same AI, the drafter randomly selects one of 6 formats (e.g., "observation-led", "question-led", "story-led").
- **Post-Processing Guardrails**: `_ensure_structure` runs after generation to guarantee the email has a proper greeting (`Hi Name,`) and sign-off, even if the LLM forgets them.

> [!TIP]
> **Key Takeaway for Project Zara**: The "Ranker -> Drafter" pattern with strict evidence blocks is highly effective for reducing AI hallucinations in generated content. Additionally, the fallback search strategy (Free first -> Assess Signal -> Paid gap-filler) is a fantastic way to control API costs at scale.
