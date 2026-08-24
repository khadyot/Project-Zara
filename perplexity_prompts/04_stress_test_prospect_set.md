# Perplexity Prompt 04 — A breakpoint-hunting prospect set for pipeline stress testing

> **Human:** paste everything below the line into Perplexity. Use Research/Deep Research mode if available. Save the reply to `perplexity_responses/04_stress_test_prospect_set.md`.

---

**Today's date is 25 August 2026.** Every person and company below must be **real and currently verifiable**, with a citation for each. Prefer 2026 sources. If you cannot verify that a person currently holds the role you list, say so in the row rather than guessing — a wrong row is worse than a missing one, because I will be testing a system against it and cannot tell a system bug from your error.

## What I am building and why I need this

I run a B2B research agent. Given **a person's name and their company**, it researches them across public sources, picks the most relevant signal, and drafts one personalised email **for a human to review**. It never sends anything, and no message will ever be sent to anyone on this list. This is a **test corpus for finding where my pipeline breaks.**

### Fields I need — and one I explicitly do not

For each row: **full name · current job title · company · company website domain · one-line note on why this row is a hard case · source link.**

**Do not include email addresses, phone numbers, home locations, social handles, or any personal contact details.** My system never uses them, so collecting them would serve no purpose. Public professional role and employer only — the kind of thing on a company leadership page or a press release.

## The important part: I want hard cases, not a good list

A list of 30 well-known executives at well-covered companies would tell me my pipeline works on easy inputs, which I already know. I need rows that **attack specific assumptions**. Give me roughly **40 rows total**, distributed across the ten categories below. Label every row with its category.

**Target profile when a category doesn't say otherwise:** operations, finance, or supply-chain leaders (CFO, VP/Director of Finance or Operations, Controller, Head of RevOps, COO) at companies with **50–2,000 employees** in high-transaction sectors — payments, fintech, ecommerce, logistics, marketplaces, SaaS billing.

### 1. Ambiguous company names (5 rows)
Companies whose name is also a common English word or another well-known entity — e.g. Ramp, Beam, Atlas, Summit, Cascade, Apex, Vertex, Mesa, Anchor, Column. I need to see whether the system retrieves the *company* or the dictionary word.

### 2. Namesake-heavy person names (5 rows)
Real executives whose names are common enough that a web search returns many different people — e.g. common Anglophone names, or names shared with a public figure, athlete, or actor.

### 3. Low or no personal web presence (5 rows)
Real, currently-serving executives who are **verifiably in post** but who have published essentially nothing personally — no interviews, no talks, no bylined articles, no podcast appearances. Confirm the role from a company page or press release, and confirm the absence of personal content. **This is my most important category**: the system must degrade honestly to company-level evidence rather than inventing a personal hook.

### 4. Non-ASCII and multi-part names (4 rows)
Names with diacritics, non-Latin scripts, multi-part surnames, or patronymics. I am testing encoding, tokenisation, and name-matching.

### 5. Renamed, merged, or acquired companies (4 rows)
Companies that changed name, rebranded, or were acquired in the last ~3 years, where searching the old or new name gives materially different results. Note both names.

### 6. Very small companies (4 rows)
Under ~50 employees, minimal press coverage, possibly no news at all. Testing honest "found nothing".

### 7. Large and heavily covered (3 rows)
Well-known companies generating enormous volumes of news, where the risk is drowning in noise and picking something stale or irrelevant instead of something specific.

### 8. Deliberately outside my stated ICP (4 rows)
Sectors and sizes I did **not** ask for — a non-profit, a public-sector body, a very large enterprise, a low-transaction professional-services firm. My system's rule is that it must never *reject* a prospect for poor fit; it must note the mismatch and proceed. I need rows that exercise that.

### 9. Recently appointed vs. long-tenured (3 rows)
Two people appointed within the last ~6 months, one in post for 10+ years. Testing whether recency detection works and whether a stale signal gets treated as current.

### 10. Public companies that file (3 rows)
Companies with real regulatory filings, so I can check whether filing-derived signals are usable or just noise. Most of my targets are private, so I need a small contrast set.

## Output format

One markdown table, one row per prospect, columns:

`Category | Full name | Title | Company | Domain | Why this is a hard case | Source`

Then a short section: **"Rows I could not verify"** — anything you considered and dropped, and why. I would rather have 32 solid rows and an honest list of 8 rejects than 40 rows where some are guesses.

Finally: **"Categories you think I am missing"** — given that this is a name-plus-company research pipeline, what other kind of input would you expect to break it that I have not asked for?
