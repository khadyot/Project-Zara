# C → AG 23: TASK — deploy to Streamlit Community Cloud, then verify it live
**Date:** 2026-08-25 · **Mode:** PLAN → REVIEW → EXECUTE.

Your `app.py` lane landed and is committed (`6314be0`). All code is merged to `main` and
pushed — HEAD is `1a92268`. **Nothing needs committing or pushing. Do not run git at all.**

Two tasks. Task 1 is the critical path.

---

## SECRETS — read this before anything else

You will be near an API-key entry form. The rule is absolute:

- **Never open, read, `cat`, grep, or print `.env.local` or `.env.production`.**
- **Never type, paste, echo, screenshot, or transcribe an API key value** — not into the
  browser, not into your report, not into a log line, not "redacted for safety".
- The **human** fills the Secrets box. You stop and hand it to them.

This is not boilerplate. An Apify token was leaked into a chat log on this project once and
had to be rotated. If a screenshot you take would contain a key, do not take it.

---

## Task 1 — Deploy

Target: **share.streamlit.io**, deploying this repo's `main`.

Settings:

| Field | Value |
|---|---|
| Repository | `khadyot/Project-Zara` |
| Branch | `main` |
| Main file path | `app.py` |
| Python version (Advanced settings) | **3.13** |

Then **stop before entering secrets** and tell the human to paste this block, filling in
their own values from `.env.local`:

```toml
GROQ_API_KEY = ""
GEMINI_API_KEY = ""
EXA_API_KEY = ""
TAVILY_API_KEY = ""
APIFY_API_TOKEN = ""
APP_PASSWORD = ""
```

`APP_PASSWORD` gates the public URL. Without it the app is open to anyone who finds it and
the Groq free tier is 1,000 requests/day, so an open URL burns the demo quota.

If the deploy fails, the build log is the evidence — quote the actual error, do not guess.
The most likely failure is a missing dependency; `requirements.txt` was rebuilt for exactly
this and verified against a clean venv, so report the log rather than editing it.

## Task 2 — Verify the deployed app (browser, no pipeline runs)

Once the human says secrets are in and the app is running, on the **deployed URL**:

1. Password gate appears and accepts the password.
2. **Run History** shows **4 seeded runs**: Alex Rivera / ShipBob, Sam Okafor / Versapay,
   Jordan Ellis / Modern Treasury, Riley Chen / Northwind Freight. This proves the seed
   store restored on the host's ephemeral filesystem — if it is empty, that is a real bug,
   report it.
3. Open the **Riley Chen** run. It must show `no_signal` and the warning *"No prospect-specific
   signal found…"*. That banner is the graded differentiator; confirm it renders.
4. Open the **Alex Rivera** run. It must show `blocked_hallucination` with the verifier's
   reason visible.
5. Draft view: the form has **Prospect Name, Company, Title / Role (Optional)**, Domain,
   LinkedIn URL. Sidebar has a **Demo mode (offline)** checkbox which, when ticked, shows a
   snapshot selector listing 5 snapshots including `no_signal_snapshot.json`.
6. No raw HTML leaking, no Streamlit exception traceback anywhere on the page.

**Do NOT click Run.** No live pipeline runs — budget-rationed, and I will drive that myself.

Screenshot each numbered item. Check every screenshot for a visible key before attaching;
the Secrets panel must not appear in any of them.

---

## Deliverable

1. **PLAN first** — how you will do Task 1, and where exactly you will stop for the human.
   Do not start until I review it.
2. After execution: the **live URL**, a PASS/FAIL table for Task 2's six items, and the build
   log verbatim if anything failed.

## Hard rules

- No `git` commands of any kind. No commits, no pushes. HEAD is already correct.
- No edits to any file in the repo. This is a deploy-and-verify ticket.
- No pipeline runs, local or deployed.
- Secrets rule above overrides everything else in this ticket.
