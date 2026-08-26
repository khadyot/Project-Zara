# Demo recording plan — Project Zara

Written 2026-08-26 for the case-study video. Read once before recording.

---

## 0. Budget: no longer a constraint

Five Groq keys are pooled, each with its own bucket (verified live: all five returned
`7927/8000` independently). Effective ceiling is **1,000,000 tokens/day**, and a run's calls are
spread round-robin across keys, so **the 40-60s rate-limit stall should no longer happen**. A
prospect still costs ~16k, so that is ~60 runs/day rather than ~5.

If a 429 does appear, the pipeline now switches key instead of sleeping, and only waits once
every key has refused.

**Demo mode is restored**, so you can record without spending anything at all.

---

## 0b. Demo mode: type these names exactly

The fixture hash includes the prospect's NAME. Demo mode replays only for the pair it was
recorded under; anything else misses the fixture and errors.

| Type this name | and this company | Snapshot | What it demonstrates |
|---|---|---|---|
| `Alex Rivera` | `ShipBob` | shipbob | Normal good run, `company_action`, verifier clean |
| `Sam Okafor` | `Versapay` | versapay | Normal good run |
| `Jordan Ellis` | `Modern Treasury` | modern_treasury | Normal good run |
| `Riley Chen` | `Northwind Freight` | no_signal | **`no_signal`** path, honest generic offer, verifies clean |
| `Dana Lee` | `Acme Logistics` | thin_prospect | **`blocked_hallucination`**: the verifier refuses its own draft |

All five replay with zero network calls. `Dana Lee` is the strongest edge case you have on tape
(see 3I) and `Riley Chen` is 3B.

## 1. What the video is actually arguing

Not "look, it writes emails." The argument is:

> Personalisation worked because it was **costly** — expensive to fake. AI made writing free,
> so the cost had to move to **judgment**: saying honestly how good the evidence is, including
> when it's thin. Any tool writes a confident paragraph. The hard part is knowing when you
> don't have enough, and saying so.

So the hero of the video is **the decision card**, not the draft. Show what it found, what it
threw away and *why*, how close the evidence sits to the person, and how strong a claim that
supports.

---

## 2. Recording order (roughly 6–8 min)

1. **The problem** (~45s) — one slide or just talk. Costly-signal thesis above.
2. **One good run, end to end** (~2 min) — your best prospect. Show: retrieval ladder → decision
   card → hook options → draft → verifier clean.
3. **The decision card in detail** (~2 min) — this is the centrepiece. Walk the "Not chosen"
   list. Point at a card that was excluded and read the reason aloud.
4. **An edge case or two** (~2 min) — from §3. This is what separates you from a prompt wrapper.
5. **Limits, honestly** (~45s) — §5. Naming your own limits *is* the thesis.

---

## 3. The edge cases — what they are and why each matters

These are the behaviours worth showing. Each one exists because it broke on a real run.

### A. Company-only signal → `company_action`
Nothing the person themselves said; only company news. The card labels it `company_action`
and does **not** pretend they said it.
**Why it matters:** most prospects are this. Claiming otherwise is the #1 way outbound gets
caught lying. **Likely to hit:** very. Safe to show.

### B. No signal at all → `no_signal`
Nothing prospect-specific found. It still writes an email — "degrade, never refuse" — but
flags `offer_is_generic` and says on the output's face that a human must judge it.
**Why it matters:** refusing helps nobody; pretending is worse.
**Now safe to show.** The no-signal path got the style rules and verifies clean; replay it with
`Riley Chen` @ `Northwind Freight`.

### C. Stale evidence → recency guard
Evidence older than 180 days, or with no date at all. The draft is forbidden from calling it
"new"/"recent", and the verifier blocks the phrasing if it slips through.
**Why it matters:** this is the fix that turned "New finance chief" (she'd been there 3.5
years) into an honest opener. Great story if you have a before/after screenshot.

### D. Undated evidence loses a near-tie
A dated card within 0.15 relevance beats an undated one. A hook's job is a reason to write
*now*; an undated card gives no *now*.
**Why it matters:** it's why Stord flipped from a stale listicle to the $250M round.

### E. Namesake collision
A card matching the person's name but never mentioning the company is flagged
*"possible namesake"* and downweighted.
**Why it matters:** without it you draft from a stranger's biography. Real case: a Stephanie
Neill (Stripe) competing for a hook about Stephanie Fielding (Stord).

### F. Ambiguous company name
Two different companies share a name (real case: "Moov" the payments firm vs "Moov" the
Twin Cities ride-hailing service). Both get retrieved; the wrong one is outranked.
**Why it matters:** entity resolution is the unglamorous half of research.
**Note:** currently handled by ranking, not by an explicit check — be honest about that.

### G. Guardrail — relevance is not permission
`never_reference`: layoffs, litigation, bereavement, regulatory action. These score *highest*
on naive relevance and are unusable.
**Why it matters:** the single clearest demonstration that the system has judgment, not just
retrieval. **How to show:** point at an excluded card in "Not chosen" reading
`never_reference: …`.

### H. ICP deviation never blocks
Out-of-band headcount is a **note**, not a veto. If someone typed the name in, assume a reason.
Unknown headcount reads *"unknown — could not verify"*, never `0`.
**Why it matters:** "couldn't look" ≠ "looked and found none". Same discipline as the
per-source `ok`/`empty`/`failed`/`skipped` statuses.

### I. Verifier catches its own fabrication
Two passes: deterministic grounding, then an LLM judge. On a caught fabrication it retries;
a passing retry ships with `self_corrected: true`, a failing one ends `blocked_hallucination`
with **no email**.
**Why it matters:** *the strongest moment available to you.* A system refusing to send its own
draft is the thesis in one screen. Real case: it invented a causal link to FedNow/RTP and
blocked itself.

### J. Source status honesty
The retrieval ladder shows `ok` / `empty` / `failed` / `skipped` **with a reason** — including
five ATS sources marked `skipped: job postings cut from the product`.
**Why it matters:** you removed a feature on principle ("I saw you're hiring" is the most worn-out
hook in outbound) and the system says so rather than hiding it.

**Best three to actually show:** **I** (self-blocking), **G** (guardrail), **C/D** (recency).
Those three carry the whole argument.

---

## 4. Sourcing the names — paste this into Perplexity

> I need 12 real B2B prospects for testing an outreach-research tool. For each: full name,
> exact job title, company, company domain. Public professional information only — no email
> addresses, no phone numbers, no personal details.
>
> Target profile: operations or finance leaders (CFO, VP Finance, Controller, Head of
> Operations, Head of Payment Ops) at **private companies of 50–500 employees** in
> high-transaction sectors — payments, fintech infrastructure, ecommerce logistics, 3PL,
> marketplaces, freight. US-based.
>
> Give me 2 each in these six categories, and label which category each belongs to:
> 1. Person with a strong recent public signal — a talk, podcast, byline, or quoted interview
>    in the last 6 months where THEY speak.
> 2. Person with no personal public presence, at a company with recent dated news.
> 3. Company whose name is ambiguous — shared with a different well-known company or a common word.
> 4. Person whose full name is shared with someone else notable in a different industry.
> 5. Company whose most recent news is negative — layoffs, a lawsuit, or a regulatory action.
> 6. Company that is genuinely obscure — little or no press coverage in the last 2 years.
>
> For each, cite the specific source URL for the signal you're referencing, and state its
> publication date. If you cannot verify a person currently holds the role, say so explicitly.

Category → edge case: 1→best case (person-tier) · 2→A · 3→F · 4→E · 5→G · 6→B.

**Before recording, verify each name yourself** — Perplexity hallucinates confidently on this
project. Confirm the person still holds the role. The tool will not do this for you.

---

## 5. Limits to state out loud

Say these; don't let a reviewer find them.

- **It never sends.** No send path exists; a test asserts it.
- **It does not verify employment.** It will happily draft to someone who left last month.
  A human checks before sending. (Live case: Bloomberg listed our Stord prospect as *Former* CFO.)
- **One card wins.** A hypothesis that only sharpens when three facts sit side by side is out of
  reach today — that's the next architectural step.
- **Free tier, 8,000 TPM.** A run stalls ~45s. Structural, not a bug.
- **Snapshots were recorded against a placeholder name**, so the person tier is the least-tested
  path. Live runs are the real test.

---

## 6. Pre-flight checklist

- [ ] Names chosen and **employment verified by hand**
- [ ] Budget checked (sidebar meter — it now reads Groq's own headers, labelled `measured` vs `estimate`)
- [ ] Decide: terminal (`python -m zara.probe`) or Streamlit UI. UI is better on camera; the
      decision card renders properly.
- [ ] **If demoing the deployed app:** it redirects to Streamlit account auth. Fix visibility or
      demo locally.
- [ ] **Streamlit Cloud secrets need updating** or the deploy is behind: add `ZARA_ADMIN_PASSWORD`
      (developer mode no longer opens without it) and `GROQ_API_KEY_2..5` for the pool.
- [ ] Rotate all five Groq keys after recording: they were pasted into a chat transcript.
- [ ] Screen recording at a readable font size — the decision card is dense.
- [ ] Have the Stord before/after to hand for the §3C story.

---

## 7. Known-good fallbacks (already run tonight, all clean)

If a fresh name fails on camera and budget is gone:

| Prospect | Company | Hook it chose | Age |
|---|---|---|---|
| Stephanie Fielding | Stord | $250M Series F (Bloomberg) | 92d |
| Matthew Raile | Moov Financial | Apple/Google Pay disbursements (own blog) | 103d |
| Richie Serna | Finix | Unattended terminal launch (own press) | 104d |

All three: dated hook, verifier clean first pass. Re-running these costs the same 16k as a new
name but has a known outcome.
