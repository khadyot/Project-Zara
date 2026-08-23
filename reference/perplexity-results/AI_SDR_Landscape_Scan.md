# Perplexity Research: AI SDR Landscape Scan & Open Source Projects

**Source:** Perplexity
**Date:** August 22, 2026

---

You already have a fairly “reference‑grade” architecture; the good news is that there *are* open‑source AI SDR / outbound projects and vendor write‑ups whose patterns line up closely with what you’re building, especially around multi‑stage pipelines and confidence gating.

Below is a curated map of the most relevant repos and pipelines, what they’re doing architecturally, and what you can steal to make your Next.js + Claude build feel faster and more grounded.

***

## Key open‑source AI SDR / outbound repos

These are the most directly relevant GitHub projects (plus two curated lists) for AI SDR / cold outbound workflows.

### Core repos

- **ZeroGTM – AI SDR \& lead‑gen engine**
Open‑source AI SDR / lead enrichment engine that turns Google Maps into a “lead goldmine”, then runs a multi‑step enrichment pipeline (map scrape → contact mining → decision‑maker discovery → identity verification → data sanitization). Stack is Docker + Supabase + workers, with a mobile‑first UI.
- **b2b-sdr-agent-template (PulseAgent)**
Production‑ready template for AI SDRs with a 10‑stage sales pipeline, 10 cron jobs, 4‑engine memory, and multi‑channel outreach (WhatsApp, Telegram, email) built on OpenClaw; the repo is framed explicitly as an “AI SDR agent template for B2B export.”
- **ComposioHQ/outreach-agent**
Demonstration of an outreach automation workflow using Google ADK and Composio Gemini, with two agents: a BDR agent that researches candidate + company and drafts a hyper‑personalized email (using Gmail tools), and a Sales Agent that does deeper research across web, LinkedIn, and Google, returning a research report with sources.
- **AI-agent-for-cold-emails (Ionio)**
LangChain‑based autonomous agent for cold emails: builds a knowledge base from past emails, classifies inbound messages, fetches information about the lead and their organization, then uses Smartlead’s API to reply in your tone—essentially “research + personalization” on top of existing email history.
- **Lead Generation and Cold Email Automation with n8n**
Fully automated end‑to‑end workflow: scrapes leads via Google Places API, enriches data (website, phone, ratings, reviews), uses GPT‑4o‑mini to generate personalized cold emails, scrapes contact pages for emails, writes rows to Google Sheets, and sends via Gmail + Twilio.
- **Cold-Email-Automations (Job extraction + cold emails)**
Python + LangChain + ChatGroq pipeline that scrapes a careers page, extracts structured job postings, then generates personalized cold emails based on job data and a company portfolio.
- **AI-SDR-Agent**
Agentic research pipeline taking a company URL, scraping latest news/blog, finding a relevant lead on LinkedIn (simulated or via API), and generating a hyper‑personalized multi‑channel outreach strategy; includes a Python backend (uv) and a separate frontend (npm dev server on port 5173).
- **OpenSales**
Multi‑agent outbound sales system where an SDR agent finds target companies and decision‑makers and pushes every prospect into a Google Sheets pipeline.
- **open-sdr (MatthewDailey/open-sdr)**
“Automate research and outbound lead generation… helps you research companies and find people on LinkedIn, automating the tedious aspects of lead generation.”

### Orchestrator / skills repos

- **growthenginenowoslawski/coldoutboundskills**
Open‑source *Claude Code* skills for cold email infrastructure, lead sourcing, copywriting, and ops (Prospeo, Smartlead, Google Maps scraping, campaign grading, etc.), organized into ~28–29 skills that work together; you wire them via Claude Code rather than building a monolith.
- **GitHub Topic: sdr-automation**
Includes:
    - **jeremylongshore/intent-outreach** – described as a “Claude‑Code‑native SDR orchestrator” with phase sub‑agents and an MCP server, model‑agnostic.
    - **Abdullateef1x/ai-sdr-approval-workflow** – Make.com + GPT‑4 SDR system with a human‑in‑the‑loop Slack approval workflow before Gmail sends.
- **Curated lists: awesome-ai-agents-for-sales \& awesome-ai-gtm**
    - Salesably’s list highlights open‑source AI sales agents like *AI-Cold-Email-Generator*, *SalesGPT*, *GPT-Sales-Assistant*, etc.
    - `ong/awesome-ai-gtm` maps commercial AI SDR tools (11x, Artisan Ava, AiSDR, Regie.ai, Salesforge, etc.) and notes that Clay aggregates 150+ data providers into an enrichment + AI messaging stack.

***

## How these repos structure their pipelines

Most of the serious projects converge on a multi‑stage pipeline very similar to your Zamp case‑study spec: discovery → enrichment → scoring/qualification → drafting → sending/hand‑off.

### Common architecture patterns

- **Explicit multi‑stage enrichment pipeline**
    - ZeroGTM runs a five‑step enrichment pipeline on each lead: map scrape for businesses, contact mining via OpenWeb Ninja, decision‑maker identification via “About” page scraping, identity verification via an email finder, then data sanitization.
    - n8n lead‑gen workflow is similarly staged: Google Places scraping → data cleaning/enrichment → AI email generation → email discovery on contact pages → persistence to Sheets → sending via Gmail/SMS.
- **Separation of “research” from “drafting”**
    - AI-SDR-Agent clearly separates a research pipeline (scrape site + find LinkedIn contact) from multi‑channel strategy generation.
    - Composio’s outreach-agent has a Sales Agent that only returns a research report (with sources) and a BDR Agent that uses that research plus Gmail tools to draft outreach.
    - Your own Zamp spec similarly separates identity resolution, suppression, enrichment, signal discovery, scoring, gating, and drafting stages, with a `PipelineStageEvent` type for tracking each stage in a run view.
- **Time‑ and source‑bounded research**
    - Explorium’s Apollo outbound agent architecture uses a discovery stage against filtered search endpoints, then enrichment via `bulk_match`, then a bounce‑firewall stage that runs MX/SMTP checks and routes records to send/low‑confidence/suppress queues.
    - Clay’s AI SDR pipeline (Claygent + GPT‑5) similarly runs multiple enrichment tasks per contact (LinkedIn page, Crunchbase funding, headcount trends, tech stack) and attaches confidence scores to each enriched column.

***

## Signal discovery: web, LinkedIn, and other sources

The stronger systems treat “signal discovery” as its own layer, aggregating multiple providers and keeping LinkedIn in a separate risk bucket.

### Source patterns you can copy

- **Maps / Places for SMB leads**
    - ZeroGTM uses Google Maps (RapidAPI) as its primary lead source, then deep‑crawls socials and contact info via OpenWeb Ninja and Anymail Finder, giving you a clean pipeline for local SMB lead discovery that doesn’t depend on LinkedIn at all.
    - The n8n workflow uses Google Places API plus scraping of /contact pages to discover emails, which is a similar “places → contact info → outreach” pattern.
- **Job boards / careers pages for hiring signals**
    - Cold-Email-Automations scrapes a careers page, extracts structured job postings, and then uses that signal (role, skills, description) to drive cold emails to potential clients.
- **Company websites, blogs, and press**
    - AI-SDR-Agent scrapes a company’s latest news/blog and uses that as authored content for outreach strategy.
    - Claygent’s workflow in the AI SDR article leans heavily on company LinkedIn page, Crunchbase funding, tech stack (BuiltWith), and press/news as enrichment columns.
- **LinkedIn and risk considerations**
    - AI-SDR-Agent mentions finding a relevant lead on LinkedIn via simulated or API‑based access, but doesn’t detail the compliance approach.
    - Apollo’s AI SDR and Outbound Copilot treat LinkedIn scraping as part of internal, licensed data ingestion (LinkedIn + other web pages) via Apollo’s AI prompts, rather than ad‑hoc scraping from your own backend.
    - Your spec already bakes in a conservative LinkedIn strategy (Bright Data public scraper + manual fixtures; no login‑based automation), which is aligned with current best practice for small agentic projects.

***

## Confidence gates and quality checks

Most open‑source repos don’t explicitly talk about “confidence gates” the way your spec does, but vendor blogs and two workflows show clear gating patterns that you can mirror.

### Gating and “refuse to draft” patterns

- **Clay’s confidence threshold per row**
Claygent produces a structured payload with confidence scores per enrichment result, and low‑confidence rows are *flagged rather than passed silently*; only when a row’s confidence exceeds your threshold does Clay push it into Smartlead/Instantly/Lemlist or CRM.
This is almost exactly your stage‑5/6 ICP × signal‑strength gate (1–3 ICP fit, 0–3 signal strength, with recency decay and “needs human judgment” routing).
- **Apollo’s bounce firewall + “SKIP” on weak signals**
Explorium’s Apollo architecture has a “bounce firewall” gate (MX/SMTP + freshness checks) that routes leads into send, low‑confidence, or suppress queues, and personalization prompts that return “SKIP” if any fact is missing or older than 90 days.
That combination—hard deliverability gate plus prompt‑level SKIP—forms a two‑layer confidence system similar to your pre‑generation gate plus optional post‑generation verification.
- **Human‑in‑the‑loop approval workflows**
The `ai-sdr-approval-workflow` repo uses Make.com + GPT‑4 to run an SDR system with a Slack approval step; only approved drafts go out via Gmail.
Apollo’s Outbound Copilot supports manual approval before new prospects are added to workflows and sequences, maintaining an explicit human gate even after AI discovery.
- **Your gate logic is ahead of most open‑source templates**
Your 2D gate (ICP fit and signal strength, with decayed confidence and explicit `gate_result` + `halted_at_stage`) is more explicit than what most GitHub repos describe, and already implements the “refuse to fabricate” behavior Clay and 11x found critical.

***

## Tech stack and UI patterns

Most repos decouple UI from orchestration, and several use fairly lightweight frontends while keeping orchestration in Python, n8n, or Claude Code skills.

### Stacks

- **Python + workers + DB**
    - ZeroGTM: Docker containers + Supabase + background workers, with mobile‑first UI; enrichment pipeline likely runs as background jobs triggered by campaign actions.
    - Composio outreach-agent: Python backend orchestrated by `main.py`, Google ADK, Composio Gemini, and Gmail tools; the sample script prints results, but the pattern is “agents in Python, frontends optional.”
- **Low‑code orchestration (n8n, Make.com)**
    - n8n lead‑gen workflow: orchestrated entirely in n8n, with Google Places, OpenAI, Google Sheets, Gmail, and Twilio nodes.
    - ai-sdr-approval-workflow: Make.com integration + Slack + Gmail + GPT‑4; good example of multi‑step pipeline without manually writing orchestrator code.
- **Claude Code + TS skills**
coldoutboundskills is TypeScript‑based, designed specifically for Claude Code, with TSX scripts and skills that you invoke from Claude; orchestration is “in” the agent environment rather than in a web app.
- **Polyglot web apps**
AI-SDR-Agent has a Python backend (`uv sync`, `uv run main.py`) and a separate UI (npm dev server on port 5173), likely using a JS framework such as Vite/React.
ZeroGTM’s mobile‑first UI suggests a JS frontend with a REST/GraphQL API over the enrichment pipeline.


### UI for pipeline progress

- Most repos show progress via:
    - Tables / dashboards in Google Sheets (n8n workflow).
    - Web dashboards or mobile campaign views (ZeroGTM).
    - Agent logs and console output (Composio, growthengine skills).

Your spec’s `PipelineStageEvent` and run view/dashboard requirement (live stage display + historical runs in Vercel Postgres) is more explicit and polished than what most open‑source repos document; it maps to the “workflow visualization” that Apollo shows for Outbound Copilot.

***

## What you can learn and reuse

Here are the main patterns and shortcuts that stand out, especially relevant to your Next.js + TypeScript + Claude build on Vercel.

### Patterns you’re already using (good)

- **Multi‑stage, typed pipeline** – Your staged architecture (identity → suppression → enrichment → signal discovery → scoring → gate → drafting) with typed results and `PipelineStageEvent` mirrors best‑practice reference architectures from Apollo (six stages: trigger, discovery, match, verify, personalize, sequence) and Clay (four stages: ICP list, Claygent enrichment, GPT‑5 personalization, outreach handoff).
- **Confidence gate and “needs human judgment” state** – Clay’s and Apollo’s blogs treat confidence gating and explicit SKIP outcomes as essential; your 2D gate plus “needs human judgment” outcome is exactly that behavior, already built in stages 5–6.
- **No login‑based LinkedIn scraping** – Your deliberate avoidance of login‑automation and use of Bright Data public LinkedIn scraping / manual fixtures matches what more conservative architectures recommend for small projects.

### Patterns you can adopt to make the build feel faster

1. **Lean on orchestrators or skills instead of custom glue everywhere**
    - For “ops‑y” stages (Google Maps, Prospeo, Smartlead, Gmail), coldoutboundskills and n8n workflows show how much you can outsource to Claude Code skills or low‑code orchestrators rather than writing API glue in your own backend.
    - Given you’re already heavy on Claude, you could proto a “fast path” pipeline as a Claude Code skill (or future MCP connector) and keep your Next.js app focused on run visualization and state storage.
2. **Adopt Apollo MCP and Clay connectors where it makes sense**
    - Apollo’s native MCP server for Claude lets you search leads, enrich records, and add them to sequences from inside a Claude conversation, with OAuth and Apollo credits instead of custom enrichment code.
    - For a demo‑grade build, you could make your “identity + enrichment” stage call Apollo via MCP from Claude rather than wiring People Data Labs / X / Bright Data yourself, trading some control for a massive speed‑up.
3. **Copy prompt‑level SKIP behavior**
    - Apollo’s outbound architecture uses a personalization prompt that returns “SKIP” whenever key facts are missing or stale; that’s a cheap but powerful pattern to implement your “confidence gate” at the prompt level as well as in numeric ICP/signal scoring.
    - Claygent’s confidence scores per enrichment column suggest a pattern where your drafting prompt only sees signals above a threshold, reducing hallucination risk.
4. **Consider external workers for slow enrichment steps**
    - ZeroGTM and n8n both run enrichment as asynchronous workers/pipelines rather than synchronous HTTP flows, which sidesteps serverless time limits.
    - Your spec already notes Vercel Fluid Compute with higher `maxDuration` as the first line of defense; if you still feel “slow”, the next step is to offload heavy enrichment stages (Firecrawl, Bright Data, PDL) to background jobs that stream status back via SSE.
5. **Start with one “reference” enrichment path (like Clay’s minimal stack)**
    - Clay’s guide recommends a minimum viable stack of three tools: Clay for enrichment/messaging, a sender (Instantly/Smartlead), and a CRM.
    - For your build, that could translate into: Claude `web_search` + Firecrawl for authored content, one firmographic API (PDL or Apollo), and your own fake CRM suppression list, keeping the number of data sources small until the pipeline feels snappy.
