# Project Zebra — Independent Audit #2

**Date:** 2026-08-22 · **Auditor:** fresh pass, Opus · **Scope:** every file in the repo, every load-bearing external assumption, re-verified against primary sources.
**Constraint honored:** no files were edited except this one. Another session is actively working the tree.

**Method.** Read all 8 planning docs, all 14 source files, all config, and the case-study rubric itself. Re-verified every external technical claim the spec depends on against vendor primary sources (Vercel docs, Firecrawl pricing, Bright Data, PDL, Anthropic API reference). Ran an executable simulation of the decay rule against fixture dates rather than reasoning about it on paper. Findings below are marked ✅ **verified** (checked against a primary source or executed), or ⚠️ **reasoned** (an argument, not a measurement).

**State at audit time:** T1 and T2 committed; T2 has uncommitted refinements in flight. `npm run typecheck && lint && build && test` all pass.

---

## 0. Status of Audit #1 — closed, superseded, and one correction

| Audit #1 finding | Status now |
|---|---|
| Spec file renamed, stale references | ✅ Closed — no `_updated` file exists |
| Tech stack still says "OPEN" | ✅ Closed — reads CONFIRMED |
| `server.js` dead file in root | ✅ Closed — does not exist |
| `LayoutProps<"/">` may be wrong | ✅ Closed — correct Next 16 generated type |
| Streaming architecture undesigned | ✅ Closed — SSE decided (spec:173), vocabulary typed (`PipelineStageEvent`) |
| Sender's offering undefined | ✅ Closed — spec:126, assigned to T5 |
| CSS font cascade bug | ✅ Fixed |
| `recency_days` hardcoded | ⚠️ **Fixed into a worse bug — see C2** |
| Signal decay undefined | ⚠️ **Decided, and the decision has a side effect — see C2** |
| Persistence undecided | ⚠️ **Decided, but names a product that no longer exists — see C1** |
| `source_method` missing from code | ✅ Closed by the other session mid-audit |

**Correction to Audit #1.** It stated the web search tool type is `web_search_20250305`. That is now the *legacy* variant. See M1 — this is my error, propagated into a doc the build is reading.

---

## 1. CRITICAL

### C1 — The persistence decision names a product that was discontinued 14 months ago ✅ verified

Spec:177 reads: *"run history … is stored in **Vercel Postgres** (Neon-backed, provisioned via the native Vercel dashboard integration)."*

Vercel's own docs (`/docs/postgres`, last updated 2026-01-13):

> **Vercel Postgres is no longer available.** If you had an existing Vercel Postgres database, we automatically moved it to Neon in December 2024. For new projects, install a Postgres integration from the Marketplace.

The strategy is right; the name is dead. An agent implementing T7 literally will search "Vercel Postgres", land on a sunset page, and likely reach for the deprecated `@vercel/postgres` package.

**Correct wording:** Neon Postgres via the **Vercel Marketplace native integration** (billed through Vercel, env vars auto-injected). Driver: `@neondatabase/serverless`. Not `@vercel/postgres`.

**Cost check (removes a blocker):** Neon free tier is 0.5 GB storage, 100 CU-hours/month, scale-to-zero after 5 min idle. A demo's run history is kilobytes. **$0.** This satisfies "no paid subscription" (spec:185) and the user's "must be properly production-deployable" requirement simultaneously.

*Ownership note: I wrote that spec line in the previous session. It was wrong.*

---

### C2 — The fixtures self-destruct on a timer. Two of them are already scheduled to break. ✅ verified by execution

Two individually-correct decisions combine into a defect:

1. Audit #1 → `recency_days` now computed live from `event_date` (`fixtures.ts:180`)
2. The other session → decay rule: `recency_days > 30` halves `confidence_score` (spec:66)

Result: **fixture gate outcomes are now a function of the wall clock.** I simulated the rule against every fixture signal:

| Signal | `event_date` | Decays on | Effect |
|---|---|---|---|
| F1 ExamplePay Series B (supporting) | 2026-07-31 | **2026-08-31** | 2 → 1 |
| F4 Tomas Weber conference talk | 2026-08-07 | **2026-09-07** | 3 → 1 — **invalidates the edge case** |
| F1 Maya Chen LinkedIn post (primary) | 2026-08-15 | **2026-09-15** | 3 → 1 — **happy path fails the gate** |
| F3 Priya Nair hiring post | 2026-07-07 | already decayed | 1 → 0 ✅ intended |

Two consequences, in increasing severity:

**(a) The happy path stops passing on 2026-09-15.** Fixture 1 is the demo. Its `expected_behavior_note` says "Gate result = Pass." After Sept 15 it routes to needs-human-judgment. If the interview slips, or anyone re-runs this later, the flagship demo inverts.

**(b) Worse — Fixture 4 silently stops testing what it claims.** F4 exists to test *personalized-opener-generic-offer*: a **strong**, real hook with no honest connection to the offer. The intended pass condition is that **draft generation** refuses to force a bridge. After Sept 7, the talk decays to weak and the run halts at the **confidence gate** instead — never reaching the logic under test. The assertion still goes green. **The test passes for the wrong reason and the edge case is no longer covered.** This is the kind of thing that looks fine until an interviewer asks "show me the case where the hook is strong but irrelevant."

**Fix:** pin fixture *ages*, not dates. Replace absolute `event_date` literals with a helper — `event_date: daysAgo(6)` — so "a 6-day-old post" stays a 6-day-old post forever. This preserves both prior fixes and is a ~10-line change to `fixtures.ts`. (Alternative: freeze a `NOW` for fixture evaluation. Weaker — it re-introduces the drift between the fixture and the live path that computing recency was meant to remove.)

---

### C3 — "I searched and found nothing" and "I couldn't search" are the same outcome. That undermines the differentiator. ✅ verified (API behavior) / ⚠️ reasoned (consequence)

The product's entire claim is epistemic honesty: *"the system must be able to say 'I don't have enough to personalize this confidently' rather than fabricate."*

Verified API behavior: **Anthropic's `web_search` server tool does not throw on failure.** It returns HTTP 200 with an error object inside the `web_search_tool_result` block (e.g. `{error_code: "max_uses_exceeded"}`). On success `.content` is a *list*; on error it is an *object*. Firecrawl 429s, PDL quota exhaustion, an X API billing lapse, and a Bright Data timeout all behave analogously — soft failures that produce *no signal*, not an exception.

The spec's error-handling principle (spec:124) correctly says stages return typed results rather than throw. But **nothing in the schema distinguishes empty-because-nothing-exists from empty-because-retrieval-broke.** Both collapse to signal strength 0 → "needs human judgment: no authored or event signal found."

That statement would be **false**. The honest statement is "3 of 5 sources were unavailable; I cannot assess this prospect." A system whose selling point is refusing to assert things it can't support would be, at that moment, asserting something it can't support. It is the single deepest design flaw in the build, and it lives exactly where the project's credibility is concentrated.

It is also cheap to fix *now* and expensive after T3/T4/T6 are built on the two-value assumption:

- Track per-source retrieval status alongside signals (`ok` / `failed` / `skipped` + reason).
- Add a gate outcome distinct from `needs_human_judgment` — e.g. `research_incomplete`. `GateResult` was already widened once in T2, so the precedent and the mechanism exist.
- Surface it in the run view: *"LinkedIn: no data (by design) · Firecrawl: rate-limited · web_search: 4 results"* — per-source status is a genuinely impressive run-view element and costs almost nothing once the data is there.

This is also the best answer available to the interview question "what happens when your tools fail?"

---

### C4 — Schedule: 7 of 9 tickets remain, and T3 has quietly grown 8× ⚠️ reasoned

Commit history: first commit **2026-08-20 08:42**. Today is **2026-08-22**. The rubric is a 7-day exercise (Day 1 pick, Days 2–6 build, Day 7 submit) → submission ≈ **Aug 26–27**. Roughly **4–5 days left.**

Done: T1, T2. Remaining: **T3, T4, T5, T6, T7, T8, T9 + a rehearsed 5-minute video.** T6 and T7 are the two explicitly graded UI tickets and neither has a line of code.

Meanwhile T3's source list grew across three commits:

| Commit | T3 sources |
|---|---|
| b4b48c5 | `web_search` (1) |
| 32df871 | + PDL, X API (3) |
| 960e541 | + Firecrawl, Bright Data, YouTube, podcast, GitHub (**8**) |

Eight integrations, **four new external accounts with payment methods**, in the hardest ticket, with ~4 days left and both graded UI tickets unstarted.

The rubric says this in as many words:

> *"A process that handles 3 scenarios well beats one that half-handles ten."*
> *"Submit something that runs, even if it's not perfect… A process that executes end-to-end — even if it only handles the happy path — is always better than one that's 80% built and can't actually run."*

**Recommendation — cut T3 to three sources:** `web_search` (business events + general authored) + **Firecrawl** (turns a 150-char citation into a real quote — this one genuinely earns its place) + **PDL** (structured firmographics). That covers all three tiers of the hook-ranking rule and is defensible in the interview. Move X / Bright Data / YouTube / podcast / GitHub to an explicit **"if time remains"** list.

The LinkedIn absence is already argued beautifully in the docs as a *deliberate position*. Spending scarce days closing it with Bright Data trades a strong narrative for a weak integration. Say the position out loud in the demo instead — it's stronger than the feature would be.

---

## 2. HIGH

### H1 — Half the confidence gate is undefined. There is no ICP anywhere in the project. ✅ verified by exhaustive search

The gate is **ICP fit × signal strength**. Signal strength is fully specified: 0–3, per-signal, plus a decay rule. ICP fit is specified as:

> *"**ICP fit** (1-3): good fit / somewhat / not a fit, with a stated reason attached."*

That is the entire definition. Searched all 8 docs: **no target industry, no size band, no role seniority, no geography, no rubric, no worked example.** The sender's *offering* was defined (spec:126) — an offering is not an ICP.

Consequences: T4 cannot implement the gate without inventing the missing axis. If it delegates fit to the LLM per-run, the gate becomes non-deterministic and the fixtures' stated expectations ("ICP fit = good") aren't reproducible run to run — which is fatal for a live demo *and* for the automated regression suite the spec mandates.

It also collides with H3: for a cold live name, `role` is `""` (stage1-identity.ts:82), so a role-based fit rule has no input.

**Needs a decision before T4:** (a) explicit ICP criteria, and (b) rule-based or LLM-judged. Recommend **rule-based over firmographics + role title** — deterministic, demo-safe, and trivially explainable when the interviewer asks why a prospect scored the way it did. Given the offering ("operations teams, manual reconciliation-heavy processes"), something like: ops/finance/RevOps title **and** 50–500 headcount **and** not in an excluded industry → good fit.

### H2 — The two gate axes run in opposite directions ⚠️ reasoned

In one table: **fit 1 = best, 3 = worst.** **Strength 0 = worst, 3 = best.** Nothing marks the inversion.

An implementing agent reading `fit=3` naturally reads "highest fit"; the table means "not a fit — never draft." That single inversion silently converts the anti-fabrication gate into a fabrication engine for exactly the prospects it was built to stop. It is also awkward to explain live.

**Fix:** make fit a named union — `"good" | "somewhat" | "not_a_fit"` — not a number. Zero ambiguity, self-documenting in the run view, and it can't be arithmetically confused with `confidence_score`.

### H3 — Stage 1 cannot fail for any real input, and no ticket fixes it ✅ verified by reading

`resolveIdentity` returns `ok: true` for **any** non-blank name + company (stage1-identity.ts:75–86). `identity_unresolved` is therefore reachable *only* via blank input. The graded "identity resolution" stage performs no resolution.

The code is honest about this — the header comment explicitly defers live confirmation to T3. **But no ticket picks it up.** T3 reads "Company/contact enrichment, then signal search." Retrofitting stage 1 to actually confirm a person exists is in no ticket, and T8 is verification-only.

**Concrete demo failure:** interviewer types a plausible non-existent person. System resolves them, enriches nothing, finds nothing, and reports *"needs human judgment: no authored or event signal found"* — implying the person exists but is quiet. The correct, far more impressive answer is *"I could not confirm this person exists at this company."*

That's a 30-second demo moment that directly showcases the differentiator, and it is currently unbuilt and unassigned. Add it to T3 explicitly.

### H4 — The suppression demo breaks if the interviewer types the company slightly differently ✅ verified

`normalizeForMatch` handles case, whitespace, and NFKC. The other session documented the remaining gap in-code (good practice, credit where due) — legal-entity suffixes are unhandled, and the failure direction is a false **negative**.

Why it matters more than the comment implies: **Fixture 5 is the suppression demo, and halting is its entire purpose.** "Vantage Fulfillment**, Inc.**", "Vantage Fulfilment" (British spelling), or "vantage fulfillment llc" all fail to match → no suppression → the system cheerfully drafts cold outreach to an existing customer, live, in front of the interviewer. The one fixture whose job is to stop.

**Fix:** strip common legal suffixes (`inc|llc|ltd|limited|corp|co|gmbh|pvt`) and trailing punctuation in the normalizer. ~3 lines. Given this is a suppression gate, biasing toward false positives is the correct trade.

---

## 3. MEDIUM

**M1 — Stale `web_search` tool version (my error from Audit #1).** ✅ verified. `web_search_20250305` is the **basic/legacy** variant. Current for Opus 5 / Sonnet 5 / Opus 4.6+ is **`web_search_20260209`**, which adds dynamic filtering — the model filters results *before* they enter context, materially cheaper for a multi-search research stage like T3. Two gotchas: do **not** also declare `code_execution` in `tools` (dynamic filtering runs it internally; a second execution environment confuses the model), and handle `stop_reason: "pause_turn"` — long server-tool runs can pause and must be resumed or output truncates silently. Pricing confirmed: **$10 / 1,000 searches** + tokens for retrieved content.

**M2 — No model chosen.** Spec:172 gestures at Apollo's "smaller model can win" finding but names no model. T3/T5 will need one. Valid IDs: `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`. **Never append a date suffix** — a remembered `claude-sonnet-5-20260514`-style ID returns a 400. Suggested split: Sonnet 5 for extraction/enrichment, Opus 5 for gate reasoning and drafting where judgment quality is the whole point.

**M3 — Persistence was decided but the schema for it doesn't exist.** Spec:177 requires "a `runs` table keyed by run ID." There is no `run_id`, no `PipelineRun`, no start/end time, no echo of the raw prospect input, no stage timestamps. `PipelineStageEvent` exists (good) but isn't tied to a run. Also `prospect_id: ""` on identity-unresolved halts (run-stages-1-2.ts:26) → unidentifiable dashboard rows; carry the raw input string instead. Define this now — a schema migration mid-T7, on the last day, is exactly the avoidable kind of pain.

**M4 — The spec contradicts the research doc it cites as its authority.** ✅ verified. Spec:138 cites `docs/research/data-source-strategy.md` for the data-source decision. That doc's own **Recommended stack** table says: *"**Do not build a dedicated LinkedIn retrieval path.**"* and recommends Exa/Tavily. The spec now mandates Bright Data + Firecrawl. `PS3_Build_Tickets.md:16` even carries a parenthetical *"(spec updated since for Bright Data/Firecrawl/etc.)"* — an acknowledgment that the citation is stale. An agent following the citation gets the opposite instruction from the spec. Add a dated amendment header to the research doc; don't leave two live, contradicting recommendations in the repo.

**M5 — No `.env.example`, and the env surface is now six secrets.** `ANTHROPIC_API_KEY`, `X_API_BEARER_TOKEN`, `PEOPLE_DATA_LABS_API_KEY`, `BRIGHT_DATA_API_KEY`, `FIRECRAWL_API_KEY`, + a database URL. Nothing enumerates them. T9 says "set all env vars in Vercel" with no canonical list to check against. `.gitignore` correctly covers `.env*` ✅.

**M6 — The test config will silently ignore all UI tests.** `vitest.config.mts` matches only `src/**/*.test.ts` under `environment: "node"`. T6/T7 component tests are `.test.tsx` and need jsdom. They won't error — they'll be **invisible**. Given the spec mandates tests from T2 onward and the UI is explicitly graded, widen the glob before T6 or you'll ship the graded surface with zero coverage and no signal that anything is missing.

**M7 — README is a stub.** *"This repository is under active development."* This repo is a submission artifact; the interviewer will open it before they open the app. The material for a strong README already exists across the planning docs — the restraint thesis, the LinkedIn position, the hook-ranking rule. It just isn't where a reader will find it.

**M8 — Repo hygiene for something you're submitting to an employer.** `.agents/skills/` ships ~100 files of unrelated third-party tooling. `archived/` contains two verbatim third-party articles, one titled *"How I use Claude Code for real engineering.txt"*. Redistributing someone else's article text in a repo submitted to a hiring committee is an avoidable copyright and professionalism smell, and the clutter dilutes an otherwise disciplined-looking project. Recommend removing `archived/` from the tree (git history keeps it) and deciding deliberately whether `.agents/` belongs in the submission.

---

## 4. LOW / polish

- `page.module.css` dark mode sets `--foreground: #000` against a `#000` page background — black on black. Confined to the T1 scaffold page that T6 replaces; noted only so it isn't rediscovered as a mystery bug.
- `daysSince` compares UTC midnight against local `now` — off-by-one possible near midnight in non-UTC zones. Immaterial *except* on the 30-day decay boundary, which per **C2** is exactly where fixtures will sit.
- Fixture `content` prose still hardcodes ages — *"was live 45 days ago; posting closed 10 days ago"* (fixtures.ts:103) — even though `recency_days` is computed. Half-fixed: the number is live, the sentence drifts. The run view renders the sentence.
- Fixture `source_url`s are fabricated `linkedin.com/fixtures/...` paths. If the run view renders them as links, an interviewer may click one and get a 404 during the demo. Render as non-links, or label them clearly as fixture provenance.
- `CLAUDE.md` declares a `CONTEXT.md` + `docs/adr/` convention. Neither exists. Either create them or drop the claim — an agent will otherwise look for them.

---

## 5. What is genuinely strong (do not let the fix list obscure this)

- **The restraint thesis is real, and it is correctly load-bearing.** It's in the brief, the spec, the schema, the fixtures, and now the code. Most builds bolt a confidence score on at the end; this one made it the architecture. That is the correct read of the problem.
- **The data-source research is unusually good.** Primary sources, fetched ToS text, current litigation (hiQ's $500K judgment; the Proxycurl shutdown, Jan–Jul 2025), with the reasoning shown. I independently re-verified the numbers that gate decisions: Bright Data 5,000 records/month free ✅, Firecrawl 1,000 credits/month, 1/scrape, no rollover ✅, PDL 100 lookups/month, no card ✅. All accurate. The LinkedIn position is defensible and *interesting* — lead with it.
- **The T2 schema amendment was the right call, made for the right reason.** Widening `GateResult` and adding `halted_at_stage` rather than overloading one field is exactly the discipline that prevents a T6/T7 branching bug. The discriminated-union refactor in the uncommitted diff is better still. C3 is the same instinct applied one level deeper.
- **Test quality is high.** `run-stages-1-2.test.ts:18–21` asserts that Fixture 5's *planted decoy signal is never touched* — testing the absence of an effect, not just a return value. That's a well-constructed test.
- **The self-documented suppression limitation** in `normalize.ts` is the habit you want. H4 only argues the risk is higher than the comment implies.
- **Timeout risk is smaller than the docs assume** ✅ verified: Vercel Hobby now allows **300s default and maximum**; Pro allows 800s GA / 1800s beta; Fluid Compute is **on by default for new projects**. A single-prospect pipeline will not approach 300s. T9's "enable Fluid Compute + raise maxDuration" is close to a no-op, and Pro is not required. Downgrade this from "Real Risk #1" and reclaim the worry.

---

## 6. Recommended sequence

Ordered by *cost of fixing later ÷ cost of fixing now*:

1. **Decide the ICP rubric (H1).** Blocks T4. Nothing else in the gate can be built or tested without it. ~30 min of decision, not code.
2. **Pin fixture ages (C2).** ~10 lines in `fixtures.ts`. Do it before T4 writes assertions against outcomes that are about to change.
3. **Model retrieval failure as distinct from absence (C3).** Add the third gate outcome + per-source status now, while `GateResult` is still cheap to widen. This is the finding with the highest interview leverage.
4. **Cut T3 to three sources (C4).** The single highest-value schedule decision available. Every hour saved here buys an hour of the graded UI.
5. **Fix the suppression normalizer (H4).** ~3 lines. Protects a live demo moment.
6. **Rename the persistence target to Neon-via-Vercel-Marketplace (C1)** and note the driver. One sentence, saves an hour on the last day.
7. **Name fit as a string union (H2)** and **assign live identity confirmation to T3 (H3)** while the tickets are open.
8. **Widen the vitest glob (M6)** before T6 exists, not after.
9. **`.env.example` (M5)**, then **README (M7)** and **repo cleanup (M8)** on submission day.

---

## 7. Questions only you can answer

1. **ICP definition — what is it?** (H1 blocks T4. Suggested default: ops/finance/RevOps title + 50–500 headcount + not excluded industry.)
2. **Confirm submission date.** Everything in C4 keys off Aug 26–27. If that's wrong, the scope advice changes.
3. **Cut T3 to 3 sources — yes or no?** If no, what gets dropped instead, given T6/T7 are graded and unstarted?
4. **Is ICP fit rule-based or LLM-judged?** Determinism vs. flexibility. Recommend rule-based for demo safety.
5. **Does `archived/` and `.agents/` ship in the submitted repo?**
6. **Vercel plan — Hobby or Pro?** Not blocking (300s is ample either way), but it settles T9's wording.
