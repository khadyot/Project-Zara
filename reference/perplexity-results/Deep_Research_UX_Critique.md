# Deep Research: AI SDR UX Flow Critique

*Source: Perplexity Deep Research (Aug 22, 2026)*

## 1. Missing Edge Cases

### Conflicting data: CSV vs enrichment
- Title/company mismatch: CSV says “VP Ops, Acme”; enrichment says “Director, Acme Health”.
- Identity ambiguity: Enrichment finds multiple Priya Nairs, or a prior role vs current role.
- Location / segment mismatch: User marked “EMEA”; enrichment says US.
- **Solution:** Per-field provenance (badges showing "from CSV" vs "from Enrichment"), explicit conflict states, and source priority rules.

### Pipeline halt vs gate failure
- Collapsing multiple failure modes (Identity unresolved, Suppression, Bad Signal, Bad ICP) into a single "Refused" state makes the product feel flaky.
- **Solution:** Distinct gate results (passed, needs_human_judgment, suppressed, identity_unresolved) and explicit "halted_at_stage" indicators.

### Human edits after gating
- If a user edits a record after the gate runs, the gate decision is stale.
- **Solution:** Versioned snapshots and a clear "Re-evaluate gate" affordance.

### Multi‑offering and multi‑ICP reality
- Hardcoding one offering breaks down in real workflows (different offers per segment).
- **Solution:** Campaign-level ICP/offer configuration at the top of the flow.

### Signal contradictions and decay
- Conflicting signals (hiring vs layoffs) or stale signals.
- **Solution:** Surface signal recency/confidence clearly; route contradictions to human judgment.

### Language, region, and compliance
- Non-English content, GDPR regions, localized titles.
- **Solution:** Language detection, region tagging, and compliance gate conditions.

## 2. Friction and Fatigue Points

### Phase 1: CSV import and mapping
- Manual column mapping and late detection of bad data causes friction.
- **Solution:** Auto-mapping with confidence scores, fast "Data health" summaries (missing fields, suspected personal emails), and workspace templates.

### Phase 2: Enrichment
- Long blocking jobs with no feedback.
- **Solution:** Clear job models with ETAs, progressive disclosure (show samples early), and "light vs deep" enrichment profiles.

### Phase 3: Cleaned Data Preview (The Fatigue Trap)
- Expecting users to inspect 10,000 rows is impossible and leads to cognitive overload.
- **Solution:** "Issues-first" views (default to showing rows with conflicts/ambiguities), sampling (spot-check 25 random leads), summary metrics, and optional detail views.

### Phase 4: Gate + Draft / Refusal
- A wall of refusals with no bulk controls makes the gate an unhelpful judge.
- **Solution:** Bulk views grouped by gate result, per-group actions (e.g., "mark as manual research backlog"), and adjustable gate policies (Strict vs Balanced vs Exploratory).

## 3. Concrete UI/UX Solutions

- **Data Provenance UI:** Source chips (CSV, CRM, Enrichment) on key fields.
- **Issue Review Phase:** Replace "Cleaned Data Preview" with an "Issue Review" phase focused on conflicts.
- **Gate Transparency:** A dedicated "Gate Policy" page and distinct gate result groupings.
- **Prospect Run View:** Detailed timeline per prospect (Identity -> Suppression -> Enrichment -> Signal -> Scoring -> Gate -> Draft).
- **Research Backlog:** A dedicated queue for "Needs Human Judgment" cases with in-app tools (note fields, manual hooks) to attach signals and re-run the gate.
- **Mode-aware Onboarding:** "Ops-first" (high control) vs "SDR-first" (high automation) presets.
