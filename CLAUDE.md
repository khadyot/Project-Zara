# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Project Zara is a **planning and reference bundle, not a codebase.** There is no source code, no manifest, no build tooling, and no commits yet — every file is untracked on an unborn `main`. The goal is a personalized-outreach agent: given a prospect (name + company), research them, decide which signal is worth leading with, and produce a grounded cold-email draft for human review. It never auto-sends.

**Start fresh.** Everything under `brief/` and `reference/` is carried-forward material from a prior attempt (`../Project Zebra`). Treat it as weighted reference — evidence to reason from, not decisions already made. Do not inherit the previous project's architecture, conventions, ticket numbering, or file layout by default. Where a carried doc asserts something is "DECIDED" or "CONFIRMED", that reflects the *old* project's state; re-decide it here.

## Nothing is locked yet — ask before choosing

Three fundamental choices are open, and the carried docs disagree with each other. Do not silently pick one:

- **Stack** — `brief/PS3_Implementation_Spec_for_Claude_Code.md` says Next.js + TypeScript on Vercel; `project_zara_context.md` says Streamlit + Python; `reference/ml_pipeline_part2.md` says a file-output pipeline with SQLite and no web UI.
- **Design direction** — `brief/ZAMP_DESIGN_SYSTEM.md` (zamp.ai: sharp corners, pill buttons, Geist Mono for data, `#005EFF`) and `brief/DESIGN.md` (Clearbit: `#091135`, `#0f77ff`, InterVar) are both complete and mutually incompatible.
- **Model provider** — `.env.local` sets `MODEL_PROVIDER="groq"` and holds Groq + Gemini keys; the spec assumes Anthropic's native `web_search`; there is no `ANTHROPIC_API_KEY`.

Also undefined anywhere in the repo: the **ICP rubric**. Half of any confidence-gate design depends on it. Ask rather than inventing one.

## Doc map

- `CARRIED-FORWARD.md` — read first. What survived the reset and why.
- `brief/` — the case study brief, spec, tickets, fixtures, design systems, and an audit of the prior build.
- `reference/data-source-strategy.md` — per-source pricing, rate limits, and legal exposure, all traced to primary sources. **Do not re-research this.**
- `reference/competitor-research/sample-leads/test_leads.csv` — a deliberately hostile 14-row CSV (unicode, embedded quotes, duplicates, invalid email, near-empty row). Use it as the CSV-ingestion test set.
- `reference/prototypes/*.html` — visual reference only; both still say "Zebra".

## Environment gotchas

These are measured facts, not opinions — they cost hours previously.

- **`GROQ_API_KEY` shadowing.** `dotenv` does not override an already-set `process.env`. A stale placeholder exported from `~/.zshrc` silently wins and produces `401 Invalid API Key` on every model call. The zshrc line is gone, but any process started before its removal still carries the placeholder into everything it spawns. Diagnose with `python3 -c "import os;print(os.environ.get('GROQ_API_KEY'))"` — a 7-character value is the placeholder. Work around it with `env -u GROQ_API_KEY <command>`. **There is no correct code change in response to a 401 here.**
- **Groq's binding free-tier limit is 8,000 TPM, not 30 RPM** — roughly 4 model calls per minute. On a rate-limit response, wait a full minute, not the suggested retry delay. Tight loops and test harnesses hit this instantly.
- **Vercel "Sensitive" env vars cannot be read back.** `vercel env pull` returns the literal `[SENSITIVE]`. Presence is checkable via `vercel env ls`; the value is not recoverable.
- **Under Vercel deployment protection, use the aliased URL.** The `<project>-<hash>-<team>.vercel.app` form returns 401.
- `.env.local` and `.env.production` hold live keys and are gitignored. There is no `.env.example`.
- Two files in `reference/research_results/` have names beginning with `#` and containing spaces and em-dashes — quote them in shell commands.

## Time-sensitive defect to design out

`brief/PS3_Test_Fixtures.md` computes `recency_days` live, and a signal older than 30 days is scored down. That makes fixtures expire: one stops exercising its happy path on **2026-09-15** and another stops testing its edge case on **2026-09-07**, and both keep passing for the wrong reason. Pin fixture **ages** (`event_date: daysAgo(6)`), never absolute dates.

## Design principles worth keeping

Two findings from the prior build are worth carrying as design constraints, because they are evidence rather than preference:

- **"Searched and found nothing" must never collapse into "couldn't search."** Search APIs fail softly — a 200 response can wrap an error object, and quota exhaustion looks like an empty result. Track per-source retrieval status (`ok` / `empty` / `failed` / `skipped`, with a reason) and give "we couldn't look" its own outcome, distinct from "we looked and there was nothing." A system selling epistemic honesty must not assert absence it didn't verify.
- **Prefer typed results over exceptions for expected failure modes** — return an ok-or-reason union from pipeline stages, and reserve thrown exceptions for genuine bugs.

## Tooling

`gh` is installed. There is no git remote and no commits — set both up before treating anything here as saved.

Once a stack is chosen and scaffolded, add a format/lint-on-edit hook (`/hooks` or `.claude/settings.json`); there is no formatter or linter config in the repo today.

<!-- PERPLEXITY-MCP-START -->
# Perplexity MCP Server

## Available Tools

- **perplexity_search** — Fast web search with source citations. Use for quick factual lookups. Works with or without authentication.
- **perplexity_reason** — Step-by-step reasoning with web context. Requires Pro account.
- **perplexity_research** — Deep multi-section research reports (30-120s). Requires Pro account.
- **perplexity_ask** — Flexible queries with explicit model/mode/follow-up control.
- **perplexity_compute** — ASI/Computer mode for complex multi-step tasks. Requires Max account.
- **perplexity_models** — List available models, account tier, and rate limits.
- **perplexity_retrieve** — Poll results from pending research/compute tasks.
- **perplexity_export** — Export a saved history entry as PDF, markdown, or DOCX. Uses Perplexity's native export when available.
- **perplexity_sync_cloud** — Sync Perplexity cloud history into the local history store.
- **perplexity_hydrate_cloud_entry** — Hydrate a single cloud-backed history entry by id.
- **perplexity_list_researches** — List saved research history with status.
- **perplexity_get_research** — Fetch full content of a saved research.
- **perplexity_login** — Open browser for Perplexity authentication.
- **perplexity_doctor** — Run diagnostic checks against your Perplexity MCP install. Returns a Markdown report; pass probe:true for a live search probe.

## Usage Guidelines

1. **Start with perplexity_search** for quick questions. Only escalate to research or reason when depth is needed.
2. **Check rate limits** with perplexity_models before batch operations.
3. **Always cite sources** from search results in your responses.
4. **For multi-turn conversations**, pass the follow_up_context JSON from perplexity_ask responses back in subsequent calls.
5. **Long-running research**: perplexity_compute may time out. Use perplexity_retrieve with the returned research_id to poll for results.
6. **Language parameter**: Defaults to en-US. Set explicitly for non-English queries.

## Model Selection

| Tool | Default Model | Best For |
|------|--------------|----------|
| perplexity_search | pplx_pro | General web search |
| perplexity_reason | claude46sonnetthinking | Step-by-step analysis |
| perplexity_research | pplx_alpha | Deep research reports |
| perplexity_compute | pplx_asi | Complex multi-step tasks |
<!-- PERPLEXITY-MCP-END -->
