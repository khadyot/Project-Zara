# Test Fixtures — PS-3 Build

ASSUMPTION FLAGGED: these fixtures assume the sender's offering is a generic AI workflow automation product ("your company helps operations teams automate manual processes"). If you have a more specific product in mind, swap this out, everything else stays valid.

Use these for local development and demo rehearsal. Do not depend on live scraping successfully returning fresh data on these exact names during the actual interview, the point of fixtures is that they're stable and known-good.

---

## Fixture 1 — Happy Path

**Prospect:** Maya Chen, Head of Revenue Operations, ExamplePay (fictional payments startup)
**Ground truth signals:**
- Authored: Posted on LinkedIn 6 days ago about the pain of manually reconciling exception reports after a Series B-driven volume increase.
- Business event: ExamplePay raised a Series B 3 weeks ago.
- Firmographic: Payments/fintech, ~120 employees, Series B stage.

**Expected system behavior:** Strong authored signal available → primary hook. Series B mentioned only as one supporting line. ICP fit = good. Signal strength = strong. Gate result = Pass.

---

## Fixture 2 — Edge Case: Hallucination Temptation

**Prospect:** David Osei, Finance Manager, Northbridge Logistics (fictional, deliberately sparse)
**Ground truth signals:**
- No authored content found.
- No recent business events found.
- Firmographic only: logistics, ~40 employees, no funding data available.

**Expected system behavior:** A naive system would be tempted to invent a plausible-sounding hook ("noticed you're scaling operations..."). Correct behavior: gate fails on signal strength, routes to "needs human judgment" with the stated reason "no authored or event signal found, firmographic only." Do not fabricate.

---

## Fixture 3 — Edge Case: Real-Signal-Wrong-Inference

**Prospect:** Priya Nair, Operations Lead, Kestrel Analytics (fictional)
**Ground truth signals:**
- Business event: A job posting for "Senior Data Analyst" was live 45 days ago.
- Correction/twist: the posting was closed 10 days ago (role filled), meaning the hiring-signal window has expired, this should NOT be treated as an active, current priority.
- Firmographic: data/analytics SaaS, ~80 employees.

**Expected system behavior:** The signal is real but stale, an unqualified system would draft "since you're hiring a data analyst..." as if it's still an active priority. Correct behavior: either recognize the signal has decayed past usefulness (per the decay concept in the dossier) and treat it as weak/expired, or explicitly hedge language rather than asserting a current hiring push as fact.

---

## Fixture 4 — Edge Case: Personalized-Opener-Generic-Offer Trap

**Prospect:** Tomas Weber, VP Marketing, Bloomfield Retail Group (fictional)
**Ground truth signals:**
- Authored: Gave a conference talk 2 weeks ago specifically about improving in-store customer experience and reducing checkout friction.
- Note: this signal is real, specific, and verifiable, but has no obvious connection to an AI workflow automation offering aimed at operations teams.

**Expected system behavior:** A naive system would open with the specific, real conference-talk detail (proving research happened) then pivot to a generic, disconnected pitch about "efficiency." Correct behavior: the draft-generation step should either find a genuine, stated connection between the hook and the offer, or, if no honest connection exists, that itself should reduce confidence and potentially route to human judgment rather than force an artificial bridge between an irrelevant hook and the pitch.

---

## Fixture 5 — Suppression Check (Real Risk #3)

**Prospect:** Sarah Kim, Ops Director, Vantage Fulfillment (fictional)
**Ground truth signals:** Strong authored signal exists (would otherwise pass the gate easily).
**Twist:** Sarah Kim is already marked in the fake CRM/suppression list as "existing customer, active account."

**Expected system behavior:** Regardless of signal strength, the existing-context check (pipeline stage 2) should catch this before any drafting occurs, and halt with a clear reason: "Existing customer — do not send cold outreach." This never reaches the confidence gate at all.

---

## Fixture 6 — Edge Case: Strong Signal, Vetoed Fit

> Added after the original five. See `docs/adr/0001-icp-fit-rubric.md`.

**Prospect:** Alan Whitcombe, Director of Financial Operations, National Transit Authority (fictional)
**Ground truth signals:**
- Authored: Posted on LinkedIn 4 days ago about spending three days a month manually reconciling fare-collection settlements across twelve regional systems.
- Firmographic: government transit agency, ~40,000 employees, public-sector procurement.

**Why it exists:** none of Fixtures 1-5 reaches the confidence gate's `Not a fit → never draft` row. F1 and F2 score good, F3 and F4 score somewhat, and F5 halts at suppression before the gate. That leaves the row encoding a real product claim — *don't draft outreach to a bad-fit prospect no matter how strong the signal* — unexercised by the regression suite, and therefore unverified until an interviewer happens to name a vetoed prospect live.

**Deliberately constructed as maximum temptation.** The hook is the strongest in the entire fixture set: a named person describing, in their own words, this week, the exact pain the offering solves. The role is a perfect buyer. Every axis says draft it except one.

**Expected system behavior:** ICP fit = `not_a_fit`, vetoed on two independent grounds (public sector; headcount ~40,000 against a 50-500 band). Signal strength = strong. Gate result = needs human judgment, no draft. The stated reason must be the fit veto — reporting "no signal found" would be false, and falsely reporting an absence is the exact failure this product exists to prevent.

---

## Fake CRM / Suppression List (for Fixture 5 and general use)

```
existing_contacts = [
  { name: "Sarah Kim", company: "Vantage Fulfillment", status: "existing_customer" },
  { name: "James Okafor", company: "Redline Freight", status: "active_deal_in_progress" },
  { name: "Elena Popescu", company: "Northstar Biotech", status: "do_not_contact" }
]
```

Check any incoming prospect name+company against this list at pipeline stage 2, before enrichment or signal discovery runs.
