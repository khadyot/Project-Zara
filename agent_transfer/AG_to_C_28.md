# Transfer AG -> C (28): Parallel AI Evaluation & Strategic Integration Plan

**Context:** Research and capability analysis of [Parallel AI](https://docs.parallel.ai/getting-started/overview) evaluated against our full system audit in `reference/product-audit.md`.

---

## 1. Executive Summary

In `reference/product-audit.md` (§1, §14), we established that **retrieval is the binding constraint on the entire Zara pipeline**—running at ~1/3 capacity, capped at 10 Exa cards, plagued by truncated Google News RSS descriptions, unread page links, and a broken entity resolution condition (§12.3) that disables domain-scoped searches.

**Parallel AI directly solves both Stage 0 (Entity Resolution) and Stage 1 (Retrieval Ladder).** It provides an AI-native web intelligence suite with sub-second latency, pre-compressed LLM-ready excerpts, and transparent, field-level auditable citations (`output.basis`).

---

## 2. Parallel AI Capabilities & Product Matrix

| API Product | Query Input | Output Format | Latency | Unit Cost | Best Role in Zara |
|---|---|---|---|---|---|
| **Search API** (`fast` mode) | Natural-language `objective` + 2–3 keyword `search_queries` | Top 10 URLs with **pre-compressed, LLM-optimized excerpts** | ~700ms | $0.001 / req ($1/1k) | **Primary Rung 1 Search Fetcher** (Replaces/augments Exa & Tavily) |
| **Extract API** | List of URLs (≤20) + optional `target_content` objective | Clean Markdown excerpts (handles JS SPAs & PDFs) | 1–3s | $0.001 / 1k URLs | **Page Body Fetcher** for high-ranking article/blog URLs |
| **Entity Search API** (`beta`) | `entity_type` (`companies`/`people`) + `objective` | Ranked list of canonical `name`, `url`, and `description` | 1–3s (sync) | $0.005 / req ($5/1k) | **Stage 0 Entity Resolution** (Replaces broken Tavily suffix regex) |
| **Task API** (`processor="lite"`) | Structured input dict + JSON output schema | Typed JSON + **Research Basis** (citations, reasoning, confidence) | 10–20s | $0.005 / run ($5/1k) | **Firmographic & ICP Fit Enrichment** (Fixes §12.5) |
| **Responses API** | Question input + `reasoning.effort` (`low`/`medium`) | Synthesized text + citations (OpenAI-compatible) | 5–20s | $0.010–$0.050 / req | **Complex Pain Analysis Subagent** |
| **FindAll API** | Custom boolean `match_conditions` + enrichments | Evaluated candidates list with verified status | Asynchronous | Fixed + per-match | **Future Batch Discovery / Lead Gen Mode** |

---

## 3. How Parallel Solves Zara's Specific Audit Defects

### 3.1 Defect §12.3 & Stage 0: Entity Resolution (`zara/utils/resolve.py`)
* **The Problem:** `resolve.py:68` gates domain lookup on `normalized != raw_company.strip()`. Any company typed without a corporate suffix (*Episode Six*, *ShipMonk*, *Stord*) normalizes to itself, yielding `domain=None` and breaking `ExaBlogFetcher` and Jina.
* **Parallel Solution:** A single call to `client.beta.findall.entity_search(entity_type="companies", objective=raw_company, match_limit=5)` synchronously resolves the canonical company name, verified domain URL, and core description in ~1.5s for $0.005.

### 3.2 Defect §1.2 & Stage 1: Retrieval Thinness & Exa Keyword Mismatch
* **The Problem:** 10 Exa cards max per prospect, keyword `OR` syntax treated as literal text, Google News snippets capped at ~100 characters with no article bodies.
* **Parallel Solution:** `ParallelSearchFetcher` (using `mode="fast"`) takes a rich research objective + 3 diverse queries (person interview, company expansion/news, pain topic) and returns 10 dense, high-information-density excerpts with zero snippet furniture in ~700ms at $0.001.

### 3.3 Defect §1.4: Link Following & Deep Reading
* **The Problem:** Zara never follows links. If an Exa/news snippet mentions a relevant announcement, we only ever evaluate the first 300 characters.
* **Parallel Solution:** When a high-ranking signal is identified, `client.extract(urls=[url], objective=pain_description)` pulls the relevant markdown section from the underlying article/blog post for $0.001.

### 3.4 Defect §12.2: Evidence Cleaning & Boilerplate
* **The Problem:** `ranker.py:709` and guardrail checks read raw snippet prefixes containing author bios, headers, and markdown link URLs.
* **Parallel Solution:** Parallel excerpts arrive pre-compressed and focused strictly on the query objective, eliminating header/bio noise before the snippet even reaches `evidence.py`.

### 3.5 Defect §12.5: ICP Fit Always `unknown`
* **The Problem:** Headcount is only parsed by regex on Apify company scraper outputs (which are skipped whenever the gap-filler gate closes).
* **Parallel Solution:** A lightweight `Task API` call (`processor="lite-fast"`) with schema `{employee_count: str, funding_stage: str, hq_location: str}` guarantees structured firmographic data and confidence scores on every prospect.

### 3.6 Stage 8: Grounding & Verification Synergy
* **The Principle:** Zara's core rubric is zero-hallucination groundedness back to verbatim source snippets.
* **Parallel Alignment:** Parallel's `output.basis` carries per-field `citations` with verbatim `excerpts` and `confidence` ratings (`high`, `medium`, `low`), matching Zara's `SignalCard` and `verifier.py` requirements.

---

## 4. Architectural Decisions for Claude (The Brain)

Before writing code, please rule on the following design decisions:

1. **Evidence vs. Synthesized Sources Contract:**
   * *Option A (Recommended):* Use **Parallel Search** and **Parallel Extract** as primary `SignalCard` evidence generators (pure verbatim excerpts). Use **Parallel Task Lite** strictly for firmographics/ICP metadata. Do not allow synthesized answer text into `SignalCard.snippet`.
   * *Option B:* Allow synthesized answers from Parallel Responses API as a distinct `synthetic_summary` tier in the ranker.
2. **Entity Resolution Placement:**
   * Replace the regex-gated Tavily call in `resolve.py` entirely with `Parallel Entity Search`. Should we cache resolved company domains in a local `.domain_cache.json` to prevent re-querying common companies?
3. **Retrieval Ladder Structure:**
   * How should Parallel fit into the rungs?
     * *Rung 0:* Free cache / RSS / Parallel Memory
     * *Rung 1 (Primary Search):* `ParallelSearchFetcher` (Person + Company + Pain queries) — fast, high recall, $0.001.
     * *Rung 2 (Deep Extraction):* `ParallelExtractFetcher` (Targeted page body reading for top candidates).
     * *Rung 3 (Fallback/Deep):* Apify cookieless actors for private LinkedIn posts (only if gate open).
4. **Model Tiering & Telemetry:**
   * Map `PARALLEL_API_KEY` into `sources.yaml` under `paid_api`, properly metered in the budget tracker.

---

## 5. Ready-to-Execute Implementation Steps (Awaiting Claude's Instruction)

Once approved, AG is ready to implement:
1. **`zara/utils/resolve.py`**: Wire `resolve_company()` to `Parallel.beta.findall.entity_search`.
2. **`zara/sources/parallel_search.py`**: Create `ParallelSearchFetcher` adhering to `Fetcher` protocol (`async def fetch(self, prospect: Prospect) -> SourceResult`).
3. **`zara/sources/parallel_extract.py`**: Create `ParallelExtractFetcher` for deep signal URL reading.
4. **`zara/orchestrator.py` & `sources.yaml`**: Register fetchers in Rung 1 and update cost accounting.
5. **Tests & Fixtures**: Write unit tests for new fetchers and update offline test harness.
