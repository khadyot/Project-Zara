# Transfer AG -> C (29): Brave Search API Deep-Dive & Integration Plan for Zara

**Context:** Complete technical analysis and product evaluation of the [Brave Search API documentation](https://api-dashboard.search.brave.com/documentation) mapped against the pipeline audit in `reference/product-audit.md`.

---

## 1. Executive Summary

In `reference/product-audit.md` (§1, §14), we diagnosed that **retrieval is the single binding constraint on the entire Zara pipeline**—it currently operates at ~1/3 capacity, capped at 10 Exa cards, plagued by 100-character Google News RSS description fragments without article bodies, missing link traversal, undated signal penalty (0.8x in `ranker.py`), and a broken entity resolution condition (`resolve.py:68`) that silently disables domain lookups for clean company names.

**Brave Search API directly resolves these bottlenecks.** In 2025–2026, Brave introduced dedicated AI infrastructure, most notably the **LLM Context API** (`/v1/llm/context`), an **OpenAI-compatible Answers API** (`/v1/chat/completions`), and native **Goggles re-ranking**.

Key advantages for Zara:
1. **Agent-Native Smart Chunks:** LLM Context returns pre-extracted, machine-optimized clean text passages, tables, and structured data with zero scraping furniture.
2. **Deterministic ISO 8601 Timestamps:** Every result returns 4 date formats in `sources[url].age` including an ISO 8601 timestamp, fixing the `0.8` undated penalty in `ranker.py`.
3. **Goggles Filtering DSL:** We can inject inline or hosted rules to boost high-signal financial/B2B sources (`sec.gov`, `techcrunch.com`, `businesswire.com`) and hard-discard consumer noise (`glassdoor.com`, `pinterest.com`).
4. **Strict Groundedness Compliance:** Verbatim text spans from indexed web pages fulfill Zara's zero-hallucination rubric.
5. **Cost-Effective:** $5.00 / 1,000 queries with $5.00/mo free credits (~1,000 free searches/mo) and 50 QPS.

---

## 2. Brave Search API Capability & Product Matrix

| Endpoint | Protocol / Path | Input Payload | Output Format | Latency / Rate Limit | Pricing | Best Role in Zara |
|---|---|---|---|---|---|---|
| **LLM Context API** | `GET` / `POST`<br>`/res/v1/llm/context` | `q`, token budgets (`maximum_number_of_tokens`), `context_threshold_mode`, `goggles`, `freshness` | `grounding.generic[]` (smart chunks) + `sources[url]` (ISO dates, metadata) | ~500–800ms<br>50 QPS | $5.00 / 1k req ($5/mo free credit) | **Core Rung 0/1 Evidence Fetcher** (Replaces GoogleNewsRSS, supplements Exa) |
| **Web Search API** | `GET`<br>`/res/v1/web/search` | `q`, `extra_snippets=true`, `freshness` (`pd`/`pw`/`pm`/`py`), `goggles`, search operators | Traditional SERP with up to 5 `extra_snippets` per URL + rich vertical data | ~400–700ms<br>50 QPS | $5.00 / 1k req ($5/mo free credit) | **Stage 0 Entity Resolution & Deep Windowing** |
| **News Search API** | `GET`<br>`/res/v1/news/search` | `q`, `freshness`, `goggles`, `country`, `search_lang` | Structured news articles with author, publisher, and timestamp | ~400–600ms<br>50 QPS | $5.00 / 1k req ($5/mo free credit) | **Rung 0 Real-time News** (Clean, full-sentence news vs broken RSS) |
| **Answers API** | `POST`<br>`/res/v1/chat/completions` | OpenAI SDK format (`model="brave"`), `stream=True`, `extra_body={"enable_research": True}` | Grounded synthesis streaming `<citation>` tags and `<usage>` metadata | 4.5s (single)<br>10–60s (research)<br>2 QPS | $4.00 / 1k queries + $5/1M input tok + $5/1M output tok | **Deep Prospect Briefs & Verification Subagent** |
| **Goggles DSL** | Parameter in `llm/context`, `web/search`, `news/search` | Inline string (`$boost=3,site=...`) or hosted `.goggle` URL (up to 3 values) | Re-ranked / filtered search index output | 0ms overhead | Included with search | **Targeted B2B Filtering & Noise Discard** |
| **Autosuggest & Spellcheck** | `GET`<br>`/res/v1/suggest`, `/res/v1/spellcheck` | `q` prefix | Suggested terms & spell corrections | ~100ms<br>100 QPS | $5.00 / 10k req | **Entity Autocomplete & Query Hygiene** |

---

## 3. How Brave Search Solves Zara's Specific Audit Defects

### 3.1 Defect §12.3 & Stage 0: Broken Entity Resolution (`zara/utils/resolve.py`)
* **The Defect:** `resolve.py:68` gates Tavily lookup on `normalized != raw_company.strip()`. Any company typed without a corporate suffix (*Episode Six*, *ShipMonk*, *Stord*) normalizes to itself, so domain lookup never fires. Downstream `ExaBlogFetcher` and Jina fail or guess.
* **Brave Solution:** Run a deterministic Brave Web Search query:
  ```python
  q = f'"{company_name}" official website'
  ```
  Extract the top canonical domain, verified LinkedIn company URL, and headquarters location in ~400ms for $0.005.

### 3.2 Defect §1.2 & Stage 1: Retrieval Ladder Thinness & 10-Card Exa Ceiling
* **The Defect:** 
  1. GoogleNewsRSS provides only ~100 chars (headline + publisher) and disables TLS verification.
  2. Exa is hard-capped at 10 results total (5 fetchers × 2 results) and uses keyword `OR` syntax that confuses neural embeddings.
* **Brave Solution:**
  * **`BraveLLMContextFetcher`:** Directly returns pre-extracted smart chunks (`grounding.generic[].snippets`) matching target B2B pain keywords (e.g. ERP migration, reconciliation, billing workflows).
  * **`BraveNewsFetcher`:** Replaces GoogleNewsRSS with full-body news snippets and `freshness="py"`.
  * **`extra_snippets=true`:** Ingests up to 5 multi-window text excerpts per result URL without web-scraping overhead.

### 3.3 Defect §4e & Stage 4: The 0.8x Undated Card Penalty (`ranker.py:348`)
* **The Defect:** The ranker penalizes undated cards with `recency_multiplier = 0.8`. RSS and Exa frequently omit clean publication timestamps.
* **Brave Solution:** Brave LLM Context guarantees 4 date fields in `sources[url].age`:
  `[Full Date, "YYYY-MM-DD", Relative Age, "ISO 8601 Timestamp"]`
  This feeds exact ISO 8601 dates directly into `SignalCard.published_date`, preserving rightful 1.0x or 0.95x recency multipliers.

### 3.4 Defect §12.2 & Stage 2: Evidence Cleaning & Snippet Furniture
* **The Defect:** `ranker.py:709` and guardrails read raw snippet prefixes containing `#` markdown headers and author bios from Exa.
* **Brave Solution:** Brave LLM Context extracts only verbatim content passages, eliminating furniture before `evidence.py` is invoked.

### 3.5 Stage 4 & Precision Filtering: Zara B2B Goggles
* **The Opportunity:** Instead of post-filtering noisy results with hardcoded Python blocklists (`AMBIGUOUS_NAMES`), we pass an inline Goggle directly into Brave Search:
  ```goggle
  ! name: Zara B2B Outreach Filter
  $boost=3,site=sec.gov
  $boost=3,site=techcrunch.com
  $boost=3,site=businesswire.com
  $boost=3,site=prnewswire.com
  $boost=2,site=bloomberg.com
  $boost=2,site=wsj.com
  $boost=2,site=forbes.com
  $discard,site=glassdoor.com
  $discard,site=pinterest.com
  $discard,site=comparably.com
  $discard,site=zoominfo.com
  ```

---

## 4. Proposed Implementation Architecture

### 4.1 Interface Contract
All fetchers implement `zara.fetchers.base.Fetcher` and return a validated, immutable `SourceResult` (`zara/models.py:27`) containing `SignalCard` items:

```python
# zara/fetchers/brave.py
import os
import httpx
from typing import Optional
from zara.models import Prospect, SignalCard, SourceResult

class BraveLLMContextFetcher:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY")
        self.endpoint = "https://api.search.brave.com/res/v1/llm/context"

    async def fetch(self, prospect: Prospect) -> SourceResult:
        if not self.api_key:
            return SourceResult(source="brave_llm_context", status="skipped", reason="missing BRAVE_SEARCH_API_KEY")

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        
        # Target finance & ops pains matching value_prop.yaml
        query = f'"{prospect.company}" ("reconciliation" OR "month-end close" OR "ERP" OR "NetSuite" OR "billing")'
        
        params = {
            "q": query,
            "count": 10,
            "maximum_number_of_tokens": 4096,
            "context_threshold_mode": "strict",
            "enable_source_metadata": True,
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.endpoint, headers=headers, params=params)
            if resp.status_code != 200:
                return SourceResult(source="brave_llm_context", status="failed", reason=f"HTTP {resp.status_code}")
                
            data = resp.json()
            cards = []
            generic = data.get("grounding", {}).get("generic", [])
            sources = data.get("sources", {})
            
            for item in generic:
                url = item.get("url", "")
                title = item.get("title", "")
                snippets = item.get("snippets", [])
                
                # Extract ISO 8601 date if present
                meta = sources.get(url, {})
                age_list = meta.get("age", [])
                pub_date = age_list[3] if len(age_list) >= 4 else (age_list[1] if len(age_list) >= 2 else None)
                
                for snippet in snippets:
                    cards.append(
                        SignalCard(
                            claim=title,
                            signal_type="financial_ops",
                            source_url=url,
                            published_date=pub_date,
                            snippet=snippet,
                            tier="company",
                            source="brave_llm_context",
                        )
                    )
            
            if not cards:
                return SourceResult(source="brave_llm_context", status="empty", reason="no relevant grounding chunks")
                
            return SourceResult(source="brave_llm_context", status="ok", cards=cards)
```

### 4.2 Placement in Orchestrator Ladder (`zara/orchestrator.py`)
```
Rung 0 (Free/Low-cost baseline):
  - BraveNewsFetcher (Replaces GoogleNewsRSS)
  - JinaCompanySiteFetcher

Rung 1 (Semantic & Targeted Web):
  - BraveLLMContextFetcher (B2B pain & leadership signals with Goggles)
  - ExaLinkedInFetcher
  - ExaNewsFetcher / ExaBlogFetcher

Rung 2–4 (Apify enrichers):
  - Gated by gap-filler rule
```

---

## 5. Architectural Decisions for Claude (The Brain)

Please rule on the following design decisions so Antigravity can proceed with implementation:

1. **Rung 0 vs Rung 1 Placement:**
   * Should `BraveLLMContextFetcher` sit in **Rung 0** (always run as the primary baseline alongside `BraveNewsFetcher`) or in **Rung 1** alongside `Exa`?
2. **Google News RSS Deprecation:**
   * Do you approve completely replacing `GoogleNewsRSSFetcher` with `BraveNewsFetcher` (utilizing `freshness="py"` and Goggles)?
3. **Stage 0 Entity Resolution Provider:**
   * Should Brave Web Search (`/res/v1/web/search`) become the primary domain and company resolution provider in `resolve.py`, retiring the brittle Tavily suffix-regex logic?
4. **Goggles Rule Strategy:**
   * Should we maintain inline Goggles strings in `zara/fetchers/brave.py`, or host a version-controlled `.goggle` file in the repo / GitHub Gist?

---

*Awaiting your ruling and execution instructions.*
