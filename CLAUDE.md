# CLAUDE.md

Guidance for AI agents working in this repository.

## What this repo is

Project Zara is a **personalized-outreach agent** (Zamp "AI Solutions Associate" case study, Problem Statement 3): given a prospect (name + company), research them, decide which signal is worth leading with, and produce a grounded cold-email draft for human review. **It never auto-sends.**

Core thesis: personalization worked because it was a costly signal. AI made it cheap, so the cost relocated to **judgment** — honest self-assessment of evidence quality, including when it is thin. "Pipelines > prompts."

Status: **working local prototype.** Slices 1–2 built (retrieval → rank → draft → verify), Zen integration in progress (gap-filler economics, collaboration loop).

## Stack (decided, built)

- **Python 3.13 + asyncio**, venv at `./venv` (use `./venv/bin/python`)
- **Streamlit UI** (`app.py`, port 8501) with Visual Settings Engine (Developer Mode password gate, tabs: ICP & Targeting / Weights / Pains Engine / Guardrails) serializing into `value_prop.yaml`
- **Providers:** Groq `openai/gpt-oss-120b` (primary) → Gemini `gemini-flash-latest` → Z.ai GLM (fallback chain in `zara/utils/provider.py`)
- **Orchestration target:** n8n Cloud (planned, Slice 3); CLI `python -m zara.probe`; FastAPI `POST /pipeline/run`
- **Design reference:** `brief/ZAMP_DESIGN_SYSTEM.md` (sharp corners, Geist Mono for data, `#005EFF`)

## Architecture

`zara/` package: `fetchers/` (ATS ×5, Exa scoped, Google News RSS, compound search, Apify actors ×16, Tavily, Jina) → `ranker.py` (pain-matching + tier system, strict/permissive modes) → `drafter.py` → `verifier.py` (deterministic grounding pass + LLM judge; retries hallucinations, never kills the run) → `orchestrator.py` (`run_end_to_end_pipeline`, gap-filler gate: paid rungs fire only if free rungs yield <2 person-tier cards). `value_prop.yaml` is the brain config (pains with `observable_via`, computable ICP with vetoes, weights, guardrails). `sources.yaml` is the source registry.

## The 10 Compasses (design constraints)

1. Degrade, never refuse — but never silently. Always return something; claim strength varies, stated on the output's face.
2. Relocated cost: the costly signal is judgment, not composition.
3. Relevance is a three-way join: signal × what we sell × this person's role.
4. Evidence before inference; inference declared. Permissive mode may infer structurally, but output must be labeled as inferred.
5. Proximity to prospect: authored > company action > database. `company-only` is honest, not failed.
6. No two hooks of a kind: one per tier.
7. Absence has two meanings: "found nothing" ≠ "couldn't look." Track per-source status `ok`/`empty`/`failed`/`skipped` with reason. A 200 wrapping an error body is `failed`, not `empty`.
8. Earn the turn: the hook must entail the offer.
9. The human is a collaborator: options not verdicts, auditable in seconds.
10. Relevance is not permission: layoffs/bereavement/litigation score high on naive relevance and are unusable. (Soft guardrail in permissive mode: downweight, never block.)

## Hard rules

- **Verifier is the final gate and never gets softened.** Claim-strength labels stay visible, non-blocking in permissive mode.
- **Typed results over exceptions** for expected failure modes; thrown exceptions are for genuine bugs.
- **Never print/echo secret values.** Keys live only in `.env.local`/`.env.production` (gitignored).
- **`empty` ≠ `failed` ≠ `skipped`** on every SourceResult — violations have happened 3×; grep `except` blocks producing `empty` when touching fetchers.
- **Never adopt from Zen:** silent `except → []`, random format roulette, `_ensure_structure` post-patching, prompt-only grounding. `project-zen/` is a read-only reference repo.
- Gmail (when built): `gmail.compose` Draft→Create only; grep test asserts `drafts.send`/`messages.send` appear nowhere.

## Environment gotchas (measured facts — they cost hours)

- **`GROQ_API_KEY` shadowing:** dotenv does not override an already-set `process.env`. A stale 7-char placeholder from old `~/.zshrc` beats the real key → `401 Invalid API Key`. Diagnose: `python3 -c "import os;print(len(os.environ.get('GROQ_API_KEY','')))"; ` — 7 chars = placeholder. Work around: `env -u GROQ_API_KEY <cmd>`; clean shell: `env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONPATH=. ./venv/bin/pytest tests/ -q`.
- **Groq free tier is 8,000 TPM (~4 model calls/min), not 30 RPM.** On 429, wait a full minute, not the suggested retry delay. Test harnesses hit this instantly.
- **macOS Python SSL failures with urllib** — use `httpx` or `curl`.
- **Gemini `gemini-flash-latest` 503s intermittently** — retry with backoff, never fatal. Free tier is 20 req/day per model.
- **SmartRecruiters returns HTTP 200 with `totalFound=0` for gibberish** — validate on payload, never status. Greenhouse `?content=true` returns JSON with HTML-entity-encoded content (`html.unescape` before BeautifulSoup).
- **Gemini models that appear in `models.list()` may 404 on generate** — listing ≠ callable, so verify the exact model against the exact endpoint before believing either. Re-checked 2026-09-02: `gemini-2.5-flash` and `gemini-flash-latest` both return 200 on `/v1beta/openai/chat/completions` with `Authorization: Bearer`. An earlier note here called `gemini-2.5-flash` retired; that was wrong, and `provider.py` was right to keep it.
- **`.streamlit/secrets.toml` beats the shell environment.** Streamlit exports secrets.toml into
  `os.environ`, so `FOO=x streamlit run app.py` is silently ignored for any key the file also
  defines. Cost a debugging cycle on `ZARA_ADMIN_PASSWORD`: the sidebar box appeared (key was
  truthy) but every entered value failed, because the expected value came from secrets.toml.
  Check that file first, not the shell.
- Two files in `reference/research_results/` start with `#` and contain spaces/em-dashes — quote in shell.
- Fixture-expiry defect: never write absolute dates in fixtures — pin ages (`event_date: daysAgo(6)`).

## Testing

`env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONPATH=. ./venv/bin/pytest tests/ -q` — 15 tests, all must pass twice consecutively (fixtures replay; zero live calls under fixtures). Fixtures are prompt-hash-keyed; if you change a prompt in ranker/drafter/verifier/classifier, re-record the missing fixture hash (see `scripts/record_mock.py`). Verify hashes are stable across two runs before recording.

**Always re-record with `USE_FIXTURES=fill`, never with fixtures off.** `fill` replays every fixture that exists and goes live only for the missing ones. Recording with fixtures *off* re-answers prompts whose fixtures were fine, overwriting good recordings with fresh non-deterministic output — and, worse, **a downstream prompt's hash depends on upstream output**: score the cards live and the shortlist shifts, so the hook prompt text changes, so its hash never matches the one the test is asking for. That failure presents as an inexplicable "hash mismatch" and cost two sessions ~50 wasted live calls plus a full day's Groq budget before it was understood.

## Key docs

> Session handoffs, working notes and rate-limit screenshots are gitignored: useful on
> disk, not part of what this repository hands to a reader.

- `agent_transfer/` — protocol logs from the build; chronological, never append to old files
- `reference/data-source-strategy.md` — per-source pricing/limits traced to primary sources; **do not re-research**
- `reference/competitor-research/sample-leads/test_leads.csv` — hostile 14-row CSV ingestion test set
- `reference/ml_pipeline_part2.md` — two-tier pipeline design basis
- `reference/working-with-antigravity.md` — **read before writing any AG ticket.** AG's real strengths, its seven documented failure modes with incidents, and the ticket checklist
- `.agents/rules/antigravity-execution.md` — the rules AG itself must follow

## Delegating to Antigravity

**AG is a transcriber, not a debugger.** It plans well against a written spec and executes
mechanical changes reliably. It has no dependable "I'm stuck, stop" reflex, and its
self-diagnosis is unreliable in exactly the moment it matters — a `TypeError` cascade from its
own out-of-scope edit was reported back as an unexplained "hash mismatch" after a 47-minute loop.

Non-negotiables on every ticket (full rationale in `reference/working-with-antigravity.md`):

- **Exclusive file list, and check `git status` against it afterwards.** Out-of-scope edits are
  the root of nearly all damage.
- **A stop rule with a number** — "two attempts, then report". Sentiment doesn't work; a counter does.
- **AG never makes live API calls.** Recording is the reviewer's job. AG once spent a whole day's
  Groq budget (199,473/200,000) on 56 unusable fixtures.
- **AG never runs git.** Twice violated on record.
- **For a known hazard, specify the mechanism, not the caution.** A warning repeated twice did not
  stop AG shipping the exact bug it warned about; handing it the function signature would have.
- **Verify AG's claims against the tree before acting on them.** Run the suite yourself.

Reviewer's own duty: give a complete file list (a boundary not given cannot be respected), and
check your acceptance numbers before making them someone else's pass/fail gate.

## Baseline performance (prior build)

p50 5.7s, p90 11.1s, max 24.5s end-to-end. Materially slower rebuild = regression worth explaining.
