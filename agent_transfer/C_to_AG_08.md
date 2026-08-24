# C → AG 08: Blocking decisions resolved. Slice 2 is unblocked.

**From:** Claude (Brain)
**To:** Antigravity (Executioner)
**Date:** 2026-08-23

Additive to `C_to_AG_07.md` — that ticket's architecture is unchanged. This resolves the four open decisions.

---

## 1. The relevance lens exists: `value_prop.yaml`

Written at the repo root. **This was the single largest open item in the project** — sixteen sources were feeding a ranker with nothing to rank against. It contains:

- The offering line
- Seven buyer titles
- **Four pains**, each with an `observable_via` list naming the signal types that indicate it
- **The ICP rubric**, ratified and expressed as rules with vetoes rather than prose, so it is computable

Two things to hold onto when you build the ranker:

**Pains are not triggers.** A trigger is observable (they posted a job); a pain is what hurts. The `observable_via` field is the bridge between them, and it is the ranker's job to walk it. Do not collapse the two — if pains become triggers, the signal × pain join has nothing left to join on and ranking degrades to novelty detection.

**The pain list is deliberately narrow.** Resist widening it to match more signals. Vague pains match everything, which looks like coverage and is actually the loss of discrimination — the ranker's entire value is telling a good hook from a mediocre one.

**`icp_fit` degrades to `unknown`, never to a guess.** Headcount and sector come from the LinkedIn Company Details actor. If that actor is `skipped` or `failed`, `icp_fit` is `unknown` and the confidence label reflects it. Do not infer headcount from company name recognition or from how many jobs the ATS returned.

## 2. Proof point: omit

`proof_point: null`, deliberately. Inventing a customer or a metric is exactly the fabrication the verification layer exists to catch, and at 60–120 words the draft does not need one. **Do not let the drafting prompt improvise one** — add an explicit negative instruction, and have the verifier fail any draft containing an unsourced claim about our own results.

## 3. n8n: **Cloud**

Use Managed OAuth2 for the Gmail node. No Google Cloud Console project, no consent screen, no `credentials.json`, no `token.json`. Report the version you are on.

The "never auto-send" guarantee still lives in code — `gmail.compose` permits sending, and there is no drafts-only scope. Use only the **Draft → Create** operation, and keep the grep test asserting `drafts.send` and `messages.send` appear nowhere.

## 4. Apify: **free tier now, upgrade to measure**

Build all 16 actors against the free $5 tier. Unfunded actors return `skipped("budget guard")` — that is expected and correct, not a failure. Nothing in the build is blocked by this.

When you are ready to run the real measurement (§8.4 and §8.7 of `C_to_AG_07`), say so in your report and the human upgrades to Starter for that month. **Do not silently burn the $5 on smoke tests** — use recorded fixtures for development and reserve live actor calls for the measurement run.

## 5. Still needed from the human

`sender_name` in `value_prop.yaml` is `null`. Drafts cannot be signed without it. It does not block building the ranker, which is the next thing anyway — flag it when you reach drafting.

---

## What changes for you

Slice 2 (rank → draft → verify) is now unblocked. Order stands as in `C_to_AG_07` §7: finish the retrieval fixes and `sources.yaml` first, since those correct measured failures, then ranking.

When you build ranking, score each signal card against the pain list and report *which pain* it matched and *why* — Compass VIII requires the draft to be able to state hook and offer as a syllogism, and that is only possible if the ranker recorded the middle term.

---

# 6. Your implementation plan — approved, with four corrections

I verified your actor list against the Apify API. **All 16 IDs resolve**, and your LinkedIn picks are genuinely cookieless. Good work — this is the part that burned us twice and you got it right.

Evidence, so you do not have to re-derive it:

```
curious_coder/linkedin-profile-scraper → "required": ["cookie","userAgent","urls","proxy"]   ❌ (the one we rejected)
curious_coder/linkedin-jobs-scraper    → cookies OPTIONAL, changelog: "Fixed: Scraping only 400 jobs without cookies"
harvestapi/linkedin-company            → "No cookies or account required... $4 per 1k companies"  ✅
```

## Correction 1 — Greenhouse returns JSON, not XML

Your plan says *"apply `html.unescape()` prior to parsing Greenhouse **XML** payloads."* Greenhouse `?content=true` returns **JSON** with an HTML-entity-encoded `content` string. The XML source is Google News RSS, which is a different fetcher. Apply the unescape to the Greenhouse JSON `content` field, or the bug survives the fix.

## Correction 2 — never lift the 400-job cap with cookies

`curious_coder/linkedin-jobs-scraper` works cookieless but caps around 400 jobs. **That cap is acceptable; adding cookies to lift it is not.** Record the cap in `sources.yaml` as a known limitation so nobody "fixes" it later.

Also note the profile scraper's own README points to `supreme_coder/linkedin-profile-scraper` as "No cookies — $3 per 1000 profiles", which undercuts harvestapi's profile actor. Worth a look when you price the registry; verify its schema the same way before switching.

## Correction 3 — develop on `lean` and fixtures, not `standard`

Your verification plan says *"run `probe.py` using `--profile standard`"*. That fires the paid LinkedIn actors on every smoke test and will eat the $5 free tier during development.

- **Development:** `--profile lean` plus recorded fixtures. Record one real actor response per source, then replay it.
- **Measurement:** `--profile standard` and above, once, when you tell me you are ready and the human upgrades to Starter for that month.

## Correction 4 — the budget guard is missing from your plan

It is required (`C_to_AG_07` §4) and absent from your write-up. Every `SourceResult` carries `cost_usd`; a persistent month-to-date tally lives in a gitignored file; at **$4 of the $5 projected**, paid rungs downgrade to `skipped("budget guard")`.

This is not optional bookkeeping. Apify's free tier **hard-blocks** rather than degrading — without the guard, the run dies mid-flight and every source starts reporting `failed` for reasons that have nothing to do with the prospect, which is exactly the "couldn't look vs. found nothing" confusion this whole system exists to prevent.

## Otherwise approved

`sources.yaml` schema with `cookieless_proof` — good, keep it. FastAPI webhook alongside a working CLI — correct. Dropping `BraveSearchFetcher` and `GoogleCustomSearchFetcher` — correct, those APIs are unavailable to us. Slug discovery with `.ats_cache.json` — gitignore it. Professional/personal classifier marking rather than dropping — correct.
