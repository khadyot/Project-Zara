# Carried forward into Project Zara

Fresh start. Nothing here is code from the previous build — only inputs,
research, and facts that cost real time to establish and would cost it again.

The previous project is intact and untouched at
`../Project Zebra` (git HEAD `de3b170`, clean tree). Nothing was deleted or
moved out of it; everything below is a copy.

## What's in this folder

| Path | What it is | Status |
|---|---|---|
| `brief/` | Original PS-3 problem statement and build source material | Authoritative input |
| `reference/ml_pipeline_part2.md` | Pre-build design doc: two-tier pipeline, hook pairing, verify pass, swap test | The design basis for this rebuild |
| `reference/data-source-strategy.md` | Source-by-source prices and rate limits | All 9 figures traced to primary sources — do not re-research |
| `reference/prototypes/` | Two standalone UI prototypes (HTML) | Visual reference only |
| `reference/competitor-research/` | Competitor research | Raw, unfiltered |
| `reference/perplexity-results/`, `reference/research_results/` | Prior research output | Raw, unfiltered |
| `.env.local`, `.env.production` | Working API keys | Live and correct. Gitignored. |

Left behind deliberately: previous `src/`, its docs, its agent-exchange logs,
and `.vercel/` (this project wants its own deployment link).

## Environment facts — these cost hours to find

**1. `dotenv` does not override an already-set `process.env`.**
A stale `export GROQ_API_KEY=yourkey` in `~/.zshrc` silently beat the real key
in `.env.local`, producing `401 Invalid API Key` on every model call. The zshrc
line is gone, but **any process started before its removal still carries the
placeholder and passes it to everything it spawns** — including editors and
agent sessions.
- Diagnose: `python3 -c "import os;print(os.environ.get('GROQ_API_KEY'))"` — a
  7-character value is the placeholder.
- Work around without restarting: `env -u GROQ_API_KEY <command>`.
- There is no correct code change in response to a 401 here.

**2. Groq's binding free-tier limit is TPM, not RPM.**
Published as 30 RPM / 1,000 RPD, but what actually fires is **8,000 tokens per
minute**. One draft-sized call requested ~1,869 tokens — roughly **4 model calls
per minute**, not 30. Verbatim:
> `Rate limit reached … on tokens per minute (TPM): Limit 8000, Used 7429,
> Requested 1869. Please try again in 9.735s`

A full pipeline run passed cleanly only because it spent 20–40s in retrieval
before reaching the model, spacing requests naturally. Anything that calls the
model directly — a test harness, a tight loop, an eval run — hits this fast.
On a rate-limit message wait a full minute, not the 9.7s suggested.

**3. Vercel "Sensitive" env vars cannot be read back.** `vercel env pull`
returns `[SENSITIVE]`. Presence is checkable with `vercel env ls`; the value is
not recoverable.

**4. Under Vercel deployment protection, use the aliased URL.** The
`<project>-<hash>-<team>.vercel.app` form returns 401; the stable alias works.

## Signal-sourcing facts — the constraint the last build hit

- **LinkedIn is permanently unreadable.** No scraping. A search-engine snippet
  of a public profile is the only honest way to get anything from it.
- **A person-name web search returns mostly LinkedIn**, which means it mostly
  returns nothing usable. Person-level signal is the scarce resource.
- **Consequence, measured:** across 10 real prospects, **8 of 8 drafts hooked on
  an ATS job posting, and not one hooked on anything the prospect personally
  said.** Five of the 8 traced to just two postings; one posting produced
  near-identical emails for three different people at the same company.
- **A job posting is a fact about the company, not the person.** Any design that
  treats company-tier and person-tier evidence as interchangeable reproduces the
  above. `reference/ml_pipeline_part2.md` addresses this directly (tier the
  hooks, pair one of each, label the draft when only company-tier exists).
- **ATS coverage is the real limit** on which companies work at all — only
  companies with a public Greenhouse/Lever/Ashby board yielded signal. Only 11
  distinct companies were ever tried, all chosen for having one.
- Free and keyless, never wired up last time: Google News RSS
  (`news.google.com/rss/search?q="Company"+when:90d`) and SEC EDGAR.

## Two defects worth designing out from the start

**Runs that never end.** A row persisted as `running` with no abort handler and
no reaper leaves rows stuck forever when the client disconnects, the function
times out, or a deploy lands mid-run — **27 of 84 runs** ended that way. Decide
the terminal state up front, and make it honest: "we stopped hearing" is not the
same as "it failed."

**Capacity rendered as a crash.** Hitting the TPM ceiling surfaced to the user
as `run_error: "Draft generation failed: rate-limited"`, which reads as a broken
product. Capacity exhaustion is a distinct state from a research failure, and
should carry the retry hint. Also: a rate-limited call that retries 3 times
spends 3 units of budget to fail once.

## Measured performance of the previous build

p50 **5.7s**, p90 **11.1s**, max **24.5s** end to end. Useful as a baseline —
if the rebuild is materially slower, that's a regression worth explaining.
