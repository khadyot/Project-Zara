# C → AG 24: TASK — deploy, verify, one live run
**Date:** 2026-08-25 · **Mode:** PLAN → REVIEW → EXECUTE.
**Supersedes `C_to_AG_23.md` entirely.** That ticket assumed you could not handle secrets and
would hand the browser back at the Secrets step. Both assumptions were wrong; ignore it.

Your `app.py` lane is committed (`6314be0`). Everything is merged and pushed — HEAD is
`7fd0999`. **Nothing needs committing or pushing. Do not run git at all.**

Three tasks, in order. Stop and report if any of them fails; do not improvise past a failure.

---

## SECRETS — the one rule, and what it actually protects

You **may** read `.env.local` and type the key values into the Streamlit Cloud Secrets form.
That is the job.

You **may not** persist a key value anywhere:

- not in `AG_to_C_*.md` or any other file in `agent_transfer/`
- not in your report, summary, or chat message
- not in a screenshot — if a frame would contain the Secrets panel with values visible, **do not
  take it**
- not in a log line, not "partially redacted", not "last 4 characters only"

**Why, concretely:** everything in `agent_transfer/` gets committed, and
`github.com/khadyot/Project-Zara` is a **public** repository. An Apify token was leaked into a
chat log on this project once and had to be rotated. The rule is about *persistence*, not
access. Read them, type them, never write them down.

I will grep the tree and every `agent_transfer/` file for key patterns before anything is
committed.

---

## Task 1 — Deploy

At **share.streamlit.io** → *Create app* → *Deploy a public app from GitHub*:

| Field | Value |
|---|---|
| Repository | `khadyot/Project-Zara` |
| Branch | `main` |
| Main file path | `app.py` |
| Python version (**Advanced settings**) | **3.13** |

Set the Python version explicitly. `.python-version` is committed but Cloud's support for it is
inconsistent, and the code needs ≥3.10 — dataclass fields use PEP 604 unions (`str | None`)
which are evaluated at import, so an older interpreter fails before the app runs at all.

**Secrets.** Read these from `.env.local` and enter them in the Secrets panel as TOML:

```toml
GROQ_API_KEY = "..."
GEMINI_API_KEY = "..."
ZAI_API_KEY = "..."
EXA_API_KEY = "..."
TAVILY_API_KEY = "..."
APIFY_API_TOKEN = "..."
APP_PASSWORD = "..."
```

`APP_PASSWORD` is **not** in `.env.local` — **you generate it**: 16+ random alphanumeric
characters. It gates the public URL, which otherwise lets anyone who finds it burn a 1,000
req/day Groq quota. This is the one credential you *should* report back in chat, because it
protects quota rather than an account and the human can rotate it in one click. Report it
plainly so they can get in.

If `ZAI_API_KEY` is absent from `.env.local`, omit that line — it is a last-resort fallback and
its absence is not an error.

**On build failure:** quote the build log **verbatim** and stop. Do not edit `requirements.txt`
or any other file. It was rebuilt specifically for this failure mode and verified against a
clean virtualenv, so a dependency error is new information I need to see, not a known gap for
you to patch.

## Task 2 — Verify the deployed app (read-only)

On the deployed URL, check and screenshot each. PASS/FAIL per item.

1. **Password gate** appears and accepts your generated password.
2. **Run History shows 4 seeded runs** — Alex Rivera / ShipBob, Sam Okafor / Versapay, Jordan
   Ellis / Modern Treasury, Riley Chen / Northwind Freight.
   **This is the most important check in the ticket.** It proves the seeded store restored onto
   Cloud's ephemeral filesystem — the one deploy behaviour that could not be tested locally. An
   empty Run History is a real bug on a graded surface, not a cosmetic one. Report it loudly.
3. **Riley Chen** run: shows `no_signal` and the warning *"No prospect-specific signal found…"*.
   That banner is the graded differentiator; confirm it actually renders.
4. **Alex Rivera** run: shows `blocked_hallucination` with the verifier's reason text visible.
5. **Draft view**: form has Prospect Name, Company, **Title / Role (Optional)**, Domain,
   LinkedIn URL. Sidebar has **Demo mode (offline)**; ticking it reveals a snapshot selector
   listing **5** snapshots including `no_signal_snapshot.json`.
6. No raw HTML leaking, no Streamlit exception or traceback anywhere on the page.

## Task 3 — One live run, and a DOM capture

**One prospect. Once.** A run costs ~8K tokens against a 200K/day budget.

1. Untick demo mode. Enter a real prospect — use **Dimitri Dadiomov / Modern Treasury**, title
   **CEO**. Click Run.
2. **Expect a ~40 second stall** partway through, with a rate-limit message. That is measured
   and structural on the Groq free tier, not a fault. Let it finish; do not retry, do not click
   Run twice.
3. Report: did it complete, what `claim_strength` did it produce, what did the verifier say,
   and did **Run History gain a fifth row**.
4. While you are on the page, **capture the rendered DOM** of the sidebar navigation radio group
   (the Draft / Run History / Budget & Quota selector) — the outer wrapper element and its
   descendants, with their `class` and `data-*` attributes. Paste the HTML into your report.
   Its pill styling is broken and I need the real DOM to write the selector against; it has been
   misdiagnosed twice already from guesswork. **Do not fix it** — `zara/ui/styles.py` is not
   yours and I am writing that CSS myself.

---

## Deliverable

1. **PLAN first.** Do not touch share.streamlit.io until I review it.
2. Then EXECUTE and report:
   - the **live URL** and the **APP_PASSWORD** you generated
   - a PASS/FAIL table for Task 2's six items, with screenshots
   - Task 3's outcome and the sidebar DOM
   - any build log, verbatim, if something failed

## Hard rules

- No `git` commands of any kind. HEAD is already correct.
- No edits to any file in the repo. This is deploy-and-verify only.
- One live run, exactly one.
- The secrets rule above overrides everything else in this ticket.
