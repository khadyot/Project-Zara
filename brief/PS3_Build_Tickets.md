# PS-3 Build Tickets

Work one ticket at a time. Clear context (new session, or explicit reset) between each one, don't chain them in a single long-running conversation. Each ticket from T2 onward ships with automated tests covering its stage(s), not just manual verification. After each ticket, ask Claude Code to review its own work against the spec in a fresh context before moving to the next ticket, don't trust same-session self-review.

Roughly 2-3 tickets per day across a 3-4 day build.

---

**T1 — Scaffold**
Project structure, chosen stack wired up, empty schemas (Signal Record, Draft Record) as actual types/interfaces, fake CRM fixture loaded from `PS3_Test_Fixtures.md`. No pipeline logic yet. Done when: project runs, schemas exist, fixtures load.

**T2 — Identity resolution + suppression check**
Pipeline stages 1-2. Given a prospect name/company, confirm identity, then check against the fake CRM list. Test against Fixture 5 (Sarah Kim), should halt with the correct stated reason before anything else runs. Local/deterministic only — no external API calls in this ticket (see spec's error-handling principle: stage functions return typed results, never throw for expected failures). Ship the schema amendment for early halts (`gate_result` widened, new `halted_at_stage`/`PipelineStage`/`PipelineStageEvent`, `DraftStatus: "halted"`) and the first automated tests (Vitest — none exists yet, add it).

**T3 — Enrichment + signal discovery**
Pipeline stages 3-4. Company/contact enrichment, then signal search producing Signal Records (per schema) categorized as authored / business-event / firmographic. Per the Data Source Strategy in the implementation spec (DECIDED, see `docs/research/data-source-strategy.md` for citations, spec updated since for Bright Data/Firecrawl/etc.):
- General web/business-events/press: Claude's native `web_search` tool finds candidate URLs; **Firecrawl** `/scrape` reads the full page (web_search's citations alone are too short to build a confident quote).
- Additional authored-content sources: YouTube Data API, podcast search (Listen Notes-style), GitHub — all official/free, for conference talks, podcast appearances, technical bios.
- Firmographics: People Data Labs free tier (structured), `web_search` as opportunistic fallback.
- X/Twitter authored content: X API, pay-per-use, live.
- LinkedIn: **Bright Data** (free tier, public-data-only, no login) for the live backend path; manually-sourced fixture data for prepared demo prospects. Do NOT build login-based automation (Apify/PhantomBuster actors, Unipile/Linked API) — evaluated and explicitly rejected, see spec.
Requires new env vars before this ticket: `X_API_BEARER_TOKEN`, `PEOPLE_DATA_LABS_API_KEY`, `BRIGHT_DATA_API_KEY`, `FIRECRAWL_API_KEY` (all same-day self-serve signups, free tier/pay-per-use, no subscriptions — do this first). **Must actually work on an arbitrary real name/company, not just the fixtures.** Fixtures 1-4 are the automated regression suite and demo-reliability fallback, not the only supported input. Test both: fixtures produce expected Signal Records (including correct `source_method` per record), and a live run on a real, unseen name produces *some* categorized signal from at least the web_search/Firecrawl/X/PDL/Bright Data paths — a correctly-gated absence on any one source is a valid outcome, not a bug.

**T4 — Scoring + confidence gate**
Pipeline stages 5-6. Implement the fit (1-3) × signal-strength (0-3) lookup table exactly as specified, including the signal decay rule (DECIDED in spec: halve `confidence_score` past 30 days). Test all five fixtures produce the expected gate result from the spec.

**T5 — Angle selection + draft generation + human-judgment routing**
Pipeline stages 7a/7b. Apply the hook-ranking rule (authored > business-event > firmographic). Verify Fixture 1 leads with the LinkedIn post, not the funding round. Verify Fixture 2 routes to human-judgment rather than fabricating. Verify Fixture 3 doesn't assert a stale signal as current. Verify Fixture 4 doesn't force-connect an irrelevant hook to the pitch. Implement `src/lib/config.ts` with the sender-offering constant (DECIDED in spec) so drafts are consistent across runs instead of the LLM inventing a different offering each time.

**T6 — Run view UI**
Live-updating view showing each pipeline stage as it executes, per the case study's explicit requirement. Wire it to real pipeline output from T1-T5, not mocked data.

**T7 — Dashboard**
History across runs, status per run, enough surfaced detail to inspect why the system made each decision. Reasoning trail from the Draft Record schema should be visible here, not just the final draft. Persistence is DECIDED in the spec: Vercel Postgres, provisioned via the Vercel dashboard integration — not local disk/SQLite, not client-only storage.

**T8 — Full fixture pass + edge case verification**
Run all five fixtures end to end through the complete pipeline. Confirm all three locked edge cases behave as specified. This is a review/verification ticket, not new features, fix anything the fixtures reveal.

**T9 — Deploy**
Push to Vercel. Enable Fluid Compute + raise `maxDuration` (see Real risks #1 in the brief — decided: config bump, not a job-queue rewrite, unless T8 timing proves otherwise). Set all env vars in Vercel (Anthropic API key, X API bearer token, People Data Labs API key, Bright Data API key, Firecrawl API key). Confirm the pipeline completes within timeout on a real deployment, not just locally. If it's close to the limit, this is where you find out, not during the live demo.
