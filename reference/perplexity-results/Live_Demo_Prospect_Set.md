# Live demo prospect set

**Sourced:** 2026-08-28 via Perplexity, using the prompt in `DEMO-PLAN.md` §4.
**Purpose:** candidate names for *live* pipeline runs, to cover the edge cases the recorded
snapshots cannot reach (see `DEMO-PLAN.md` §8.3).

> **Not verified.** Everything below is Perplexity's output with its citation noise stripped and
> its own caveats preserved. The plan's rule stands: **verify each person still holds the role by
> hand before using them.** Two concrete fabrications are already flagged in "Problems" below.
> Public professional information only — no emails, no phone numbers.

---

## Quick reference

Twelve slots, but several people appear twice. **10 unique people across 8 companies.**

| # | Category | Name | Title | Company | Domain |
|---|---|---|---|---|---|
| 1A | Strong personal signal | Chermaine Hu | Co-Founder & CFO | Episode Six | `episodesix.com` |
| 1B | Strong personal signal | Benyam Hagos | CFO | Form3 | `form3.tech` |
| 2A | Company news only | Glen Braganza | CFO | Versapay | `versapay.com` |
| 2B | Company news only | Kevin Wall | CFO | Stax Payments | `staxpayments.com` |
| 3A | Ambiguous name | Manikandan Chandramohan | VP, Client Operations | Episode Six | `episodesix.com` |
| 3B | Ambiguous name | Mike Passales | Chief Supply Chain Officer | ShipMonk | `shipmonk.com` |
| 4A | Namesake collision | Jon Anderson | CFO | Payouts Network | `payoutsnetwork.com` |
| 4B | Namesake collision | Kevin Wall *(dup of 2B)* | CFO | Stax Payments | `staxpayments.com` |
| 5A | Negative news | Devin Weil | CFO | ShipMonk | `shipmonk.com` |
| 5B | Negative news | Glen Braganza *(dup of 2A)* | CFO | Versapay | `versapay.com` |
| 6A | Obscure company | Derek Thurston | CFO / Co-Founder | Premium3PL LLC | unverified |
| 6B | Obscure company | Bruce J. Amerman | CFO | Midwest 3PL | unverified |

---

## Signals, with dates

| # | Signal | Type | Date |
|---|---|---|---|
| 1A | "EP 56: Building a Fintech Company From the Ground Up with Chermaine Hu", Venture F podcast — `venturef.com/podcast/chermaine-hu` | She speaks | 2026-02-26 |
| 1B | "Episode 9 \| Benyam Hagos on Payments, Resilience and the Modern CFO", Finance Chief Podcast | He speaks | 2026-07-02 |
| 2A | "Versapay Names Glen Braganza Chief Financial Officer", PRNewswire via Yahoo Finance | Company PR | 2026-08-20 |
| 2B | "Stax Payments Completes Evolution Into a Full-Stack, End-to-End Payments Processor", Business Wire | Company PR | 2025-10-06 |
| 3A | Episode Six leadership page — `episodesix.com/about-us` | Corporate bio | undated |
| 3B | "ShipMonk Supercharges Fulfillment with Explosive Expansion in Nevada and Pennsylvania", Business Wire — quotes him directly | Quoted in PR | 2025-03-11 |
| 4A | "Global Fintech Interview with Jon Anderson, Payouts Network", GlobalFinTechSeries | He speaks | 2024-12-02 |
| 5A | WARN notice, Bedabox LLC dba ShipMonk — San Bernardino CA closure, 145 affected — `warntracker.com` | Layoff filing | filed 2026-03-24, effective 2026-06-30 |
| 5B | *Griffin v. Versapay Corporation*, N.D. Ga. docket 1:26-cv-01347, Title VII race discrimination | Litigation | filed 2026-03-11 |
| 6A | LinkedIn profile only — `linkedin.com/in/derekthurston` | Profile | undated |
| 6B | LinkedIn profile only — `linkedin.com/in/bruceamermanjr` | Profile | undated |

---

## Problems found in this output

Read these before using any name.

1. **"Trevor Stone" is fabricated.** Perplexity's own closing summary lists Trevor Stone among
   people with direct-speech signals. **He appears nowhere in the twelve entries.** This is exactly
   the failure mode `DEMO-PLAN.md` §4 warns about. Discard.

2. **Versapay CFO contradiction.** Perplexity cites a Versapay page titled *"Versapay Appoints Ed
   Neumann as Chief Financial Officer"* as a source while claiming Glen Braganza is CFO. Two
   different names for one role. One of them is stale or wrong — resolve before use.

3. **Form3 is probably outside the ICP.** The Org says 51–200 employees; LinkedIn says 501–1000.
   Perplexity flags this itself.

4. **ShipMonk is far outside the ICP.** The CFO Weekly episode describes Devin Weil overseeing
   12 warehouses and **~1,600 employees**. Useful as an ICP-deviation test, not as an ICP match.

5. **The ShipMonk "ambiguity" rationale is wrong.** Perplexity claims ShipMonk has branding around
   Fattmerchant/Stax — that is Stax Payments, an unrelated company. The real collision worth
   testing is **ShipMonk vs ShipBob**, which is also a name you already use in a snapshot. Be
   careful not to confuse the two on camera.

6. **Two domains are guessed, not verified** — Premium3PL and Midwest 3PL. Perplexity says so.

7. **Jon Anderson's signal is ~21 months old** (Dec 2024). It will trip the recency guard
   (>180 days) and be labelled stale. That is correct behaviour, not a failure — but do not expect
   a fresh hook from him.

8. **Kevin Wall's namesake is weak** (a concert producer plus an artist page). Jon Anderson's
   collision with the Yes vocalist is far stronger and is the better test of edge case E.

9. **Versapay already exists as a recorded snapshot.** A live Versapay run duplicates a demo you
   already have on tape.

---

## How these map to Zara's edge cases

Coverage gaps in the recorded snapshots are listed in `DEMO-PLAN.md` §8.3. These candidates close
them:

| Zara edge case | Covered by | Why it matters |
|---|---|---|
| **Person-authored tier** (no snapshot has one) | **1A Chermaine Hu**, 1B Benyam Hagos | The strongest claim tier is entirely unrecorded |
| **G — guardrail, relevance is not permission** | **5A Devin Weil (layoffs)**, 5B Glen Braganza (lawsuit) | Currently only demonstrable as policy, not a caught card |
| E — namesake collision | **4A Jon Anderson** (Yes vocalist) | Not present in any snapshot |
| F — ambiguous company | 3A Episode Six, 3B ShipMonk | Not present in any snapshot |
| H — ICP deviation never blocks | 1B Form3, 5A ShipMonk (~1,600 staff) | Headcount out of band should note, never veto |
| B — no signal / hard entity resolution | 6A Premium3PL, 6B Midwest 3PL | Unverified domains make this hard mode |

### The three live runs worth recording

1. **Devin Weil @ ShipMonk** — the highest-value run available. He has a **January 2026 podcast**
   (a genuine person-authored signal) *and* a **WARN layoff filing**. So the pipeline should pick
   the podcast and **exclude the layoff by `never_reference`**, producing a real caught guardrail
   card in "What it rejected". That single run demonstrates the person tier and the guardrail
   together — the two biggest holes in the recorded set.
2. **Chermaine Hu @ Episode Six** — clean `person_authored` hook from a Feb 2026 podcast, and the
   company name doubles as an entity-resolution test.
3. **Jon Anderson @ Payouts Network** — namesake collision against the Yes vocalist.

Verify employment by hand for all three first. Budget is not the constraint (5 pooled Groq keys,
~1M tokens/day, ~16k per run).
