# Deep Research: AI SDR CSV Ingestion & Waterfall Enrichment

*Source: Perplexity Deep Research (Aug 22, 2026)*

## Theme 1: Intelligent CSV Ingestion (Clay vs Fulgurite)

Modern AI outbound stacks treat CSV import in two distinctly different ways:

### The "Data Engineer" Paradigm (Clay)
- **Programmable Table:** Treats CSV import as a programmable data pipeline. The UI is a "spreadsheet-meets-terminal".
- **AI as a Column:** Users add "Claygent" columns to run LLM prompts over messy data (e.g., extracting intent from random notes, normalizing partial URLs).
- **Contracts:** Prompts must return structured outputs ("contracts") with evidence URLs.
- **Human-in-the-loop:** Happens at the *data level*. Users test 10 rows, spot-check the evidence links, and only scale to 1,000 rows when they trust the prompt. They audit the data *before* outreach.

### The "Draft Reviewer" Paradigm (Fulgurite)
- **Opaque Pipeline:** Treats CSV upload as a simple input. The data cleaning, normalization, and enrichment are internal and hidden.
- **Review-Before-Send:** The primary validation surface is the *email draft itself*.
- **Human-in-the-loop:** Happens at the *message level*. Users trust the system by reading the output draft, not by auditing the intermediate structured data.

## Theme 2: Waterfall Enrichment & LinkedIn Reality

### Visualizing Waterfalls
- **Clay:** Visual list of providers per column (e.g., Apollo -> Clearbit -> Datagma). Evaluated sequentially to save credits.
- **Apollo:** Admin-level settings that cascade through third-party vendors behind a simple "Find data via Waterfall" toggle.

### The LinkedIn Scraping Reality (2024-2026)
- **Scraping is Dead:** Direct live-scraping via session cookies or extensions is actively banned and penalized by LinkedIn (e.g., lawsuits against Proxycurl, bans on Apollo/Seamless extensions).
- **Identifiers, not Scraping:** Modern platforms treat `linkedin_url` as a high-confidence identifier passed to pre-harvested, licensed enrichment APIs (like PeopleDataLabs).
- **Technical translation:** AI SDRs do not point headless browsers at LinkedIn in real-time. They hit B2B data vendor APIs.

### Custom URLs
- Custom URLs (like a podcast link, a blog post, or a specific press release) are **not** part of the contact-data waterfall.
- They are ingested via dedicated AI research columns (LLM/RAG layers) that read the specific page to extract personalization hooks, running parallel to the contact enrichment waterfall.
