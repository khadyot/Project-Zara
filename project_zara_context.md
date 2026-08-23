# Project Zara: Core Architecture & Context

**Objective:** Solve the Zamp ASA Case Study (PS-3: GTM Personalised Outreach) by building a fully automated, live-runnable process that researches prospects and drafts highly personalised, grounded outreach emails.

---

## 1. Core Principles (The "Hidden Rubric")
To win the case study, this project is built on pragmatism and resilience, not AI complexity:
1. **It Must Run Live:** The system cannot break during the demo. We prioritize resilient data sources and graceful degradation over brittle scraping.
2. **The UX Matters:** We need a "Live Run View" and a "Dashboard" to prove we understand how non-technical buyers interact with AI tools.
3. **Edge Cases as a Differentiator:** We will explicitly handle the messy reality of the internet (e.g., missing data, bad news, generic companies).
4. **Groundedness (Zero Hallucination):** Every claim in the generated email must be traced back to a specific data snippet we extracted.

---

## 2. The Ideal Stack
Based on first-principles thinking, here is the architecture we are building:

*   **Frontend/UI:** **Streamlit (Python).** Allows us to quickly build a beautiful web app with a "Live Run View" (using `st.status()`) and a historical dashboard (using tables).
*   **Orchestration:** **Pure Python (`asyncio`).** Cleaner and more controllable than n8n when paired with a custom UI.
*   **Data Sources (The Research):** 
    *   **Apify:** For structured LinkedIn Person and Company data (bypasses bans).
    *   **Exa AI / Perplexity API:** For reliable company news and funding (bypasses generic Google noise).
*   **LLM Engine:** **Claude 3.5 Sonnet / Gemini Pro.** For nuanced reasoning, scoring, and writing.

---

## 3. The Data Flow & LLM Reasoning Engine

When a user inputs a Prospect Name & Company:

1. **Signal Acquisition (Parallel):**
   - Fire Apify `LinkedIn Person Scraper` -> Get Bio, Title, Recent Posts.
   - Fire Apify `LinkedIn Company Scraper` -> Get Company Size, About, Recent Posts.
   - Fire `Exa AI` -> Get recent company news/funding.
2. **Fact Extraction & Scoring (LLM Call 1):**
   - The LLM reads all JSON data and extracts discrete facts.
   - It scores each fact (1-10) based on relevance to our `value_prop.yaml`.
3. **Drafting (LLM Call 2):**
   - The LLM writes a 60-120 word email utilizing the top-scored hook.
4. **The Swap Test Verifier (LLM Call 3):**
   - A separate LLM prompt reviews the draft: *"If I swap the company name to a competitor, does this still make sense?"* 
   - It verifies every claim exists in the extracted data. If it fails, it rewrites.

---

## 4. The Edge Cases (Our Checkmate Moves)

The system is explicitly designed to handle these three scenarios gracefully:

1. **The "Digital Ghost":** Prospect has a private LinkedIn and zero digital footprint.
   * *Resolution:* Abort person-level hook. Fall back to the top Company-level hook. Flag the UI output as `Confidence: Low (Company-Only)`.
2. **The "Tragic News" Filter:** The company just had massive layoffs or a lawsuit.
   * *Resolution:* The scoring LLM has a "Sentiment Gate". Highly negative news hooks are discarded so we never draft a tone-deaf email.
3. **The "Mega-Corp Noise":** Prospect works at Apple or Amazon.
   * *Resolution:* If company size > 10,000, bypass generic web news search (which returns consumer junk) and rely purely on LinkedIn specific department data or job postings.

---

## 5. Next Steps for the New Workspace

When we boot up the new "Project Zara" folder, here is our immediate action plan:

1. **Run Perplexity Research:** Run the queries below to validate our stack choices (Apify vs alternatives, Exa AI vs alternatives).
2. **Apify Sandbox:** Manually run the Apify LinkedIn scraper to get sample JSON outputs.
3. **Prompt Engineering:** Write a simple Python script to pass the sample JSON into the LLM and test the "Scoring -> Drafting -> Swap Test" chain.
4. **Build the Streamlit UI:** Once the logic works, wrap it in a clean Streamlit interface.

### Perplexity Research Queries to Run:
*   "What are the best modern tools for orchestrating AI agent workflows that also provide a live execution UI and dashboard? Compare n8n, Make, LangGraph Studio, and building a custom Streamlit UI."
*   "What are the most reliable APIs for extracting structured data from LinkedIn profiles and Company pages in 2024/2025? Compare Apify (LinkedIn Scraper actors), Proxycurl, PhantomBuster, and BrightData on cost and ban-resistance."
*   "What are the best AI-native search APIs for researching B2B companies? Compare Exa AI, Tavily, Perplexity API, and Firecrawl for finding recent, specific company events."
*   "What are the best prompting strategies for building a 'verifier' or 'evaluator' LLM step (like a 'swap test') to automatically reject generic cold email drafts?"
