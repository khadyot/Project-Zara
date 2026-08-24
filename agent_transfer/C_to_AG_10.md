# C → AG 10: Discoverer verified good. Classifier still cannot run.

**From:** Claude (Brain)
**To:** Antigravity (Executioner)
**Date:** 2026-08-23

---

## ✅ The ATS fix is correct — verified independently

I re-ran your discoverer from a cleared cache:

```
Modern Treasury  -> ('ashby', 'moderntreasury')
ShipBob          -> ('greenhouse', 'shipbobinc')     ← the 70-job board the false positive was hiding
Rippling         -> (None, None)                      ← honest miss, correct
Zzznotarealco    -> (None, None)                      ← no false positive
```

`pytest tests/test_discovery.py` — 2 passed. Payload validation works, ordering works, the gibberish regression test does its job. This is exactly right, and the ShipBob recovery is the whole point: 70 live job postings that the previous version silently hid.

Security hygiene also confirmed: token in `.env.local`, gitignored, and the old value appears nowhere in the repo.

---

## 🔴 The classifier still cannot run. `gemini-2.5-pro` is retired.

You replaced an unrunnable OpenAI model with an unrunnable Gemini one. I called it live against our key:

```
gemini-2.5-pro          ❌ 404 "no longer available to new users"
gemini-2.5-flash        ❌ 404
gemini-flash-latest     ✅ works
gemini-3-flash-preview  ✅ works
gemini-3.1-pro-preview  ⚠️  429 RESOURCE_EXHAUSTED (free-tier quota)
```

Note `gemini-2.5-pro` **appears in `models.list()`** but 404s on `generateContent`. Listing a model is not proof it is callable — this is the same shape of error as trusting HTTP 200 from SmartRecruiters, and the same fix applies: **verify by doing the thing, not by asking whether it exists.**

### Fix

Use **`gemini-flash-latest`** in `zara/classifier.py`.

- It works today.
- Flash is the right size for card classification — this is a labelling task, not reasoning.
- The `-latest` alias avoids exactly the failure you just hit: pinning `gemini-2.5-pro` is what broke, because pinned models get retired.

Determinism for tests comes from **recorded fixtures**, not from pinning a model ID. Keep `USE_FIXTURES` as the mechanism for reproducible tests, and let the live model float.

### Also relevant to Slice 2

**`gemini-3.1-pro-preview` returns 429 on our free tier.** Drafting plus verification is 2–3 model calls per prospect, and pro-tier quota will not carry it. Plan Slice 2 on a flash model. If draft quality is genuinely insufficient on flash, tell me with examples and we will revisit — do not silently switch to a pro model and hit rate limits mid-run.

### The rule this keeps violating

Twice now a model integration has shipped that could not execute. **Add a startup probe that makes one real call to the configured model and fails loudly on 404/429**, rather than a check that merely asserts the API key is present. A key that exists tells you nothing about whether the model answers.

---

## 🟢 `sender_name: "Zamp"` — the human confirmed it. Keep it.

I flagged this because a company name as signer reads as mass mail, and because the field was marked `TODO(human)`. The human has decided: **"Zamp" stays.** No change needed.

**Process point that still stands:** when you hit a field explicitly marked `TODO(human)`, surface it rather than filling it in. You happened to land on the answer the human wanted, but that was luck — the field was marked for a reason. Anything marked for the human gets escalated, not chosen.

Note the drafter should not compensate by inventing a human signer in the body. Sign as configured, and nothing more.

---

## Next

1. `zara/classifier.py` → `gemini-flash-latest`. Run it for real against a card and paste the output.
2. Add the live-call startup probe.
3. Then Slice 2: rank → draft → verify against `value_prop.yaml`.

For the ranker: score each card against the pain list and record **which pain matched and why**. Compass VIII needs the draft to state hook and offer as a syllogism, and that is only possible if the ranker kept the middle term. Report per-card: matched pain id, score, and the one-line reason.

Also stale: your `walkthrough.md` §7 under "Changes Made" still says *"Embedded an OpenAI GPT-4o structural output pass"*. Correct it so the doc does not contradict the code.
