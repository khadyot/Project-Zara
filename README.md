# Zara

A single-prospect outreach agent. Give it a name and a company; it researches the person,
judges which signal is actually worth leading with, and drafts a cold email for a human to
review.

**It never sends.** There is no send path in the codebase, and a test asserts it
(`tests/test_retrieval.py::test_no_gmail_sends_in_codebase`).

---

## The idea

Personalised outreach worked because it was a **costly signal** — expensive to fake, so
receiving one told you something. AI made composition free, which destroyed the mechanism.
Everyone can now generate a paragraph that mentions your funding round.

So the cost has to move somewhere else. In Zara it moves to **judgment**: the willingness to
say honestly how good the material actually is, including when it is thin. Any tool can write
a confident email. The hard part — and the only part still worth paying for — is knowing when
you do not have enough to say something real, and saying so instead of guessing.

That is why the interesting surface here is not the draft. It is the **decision card** next to
it: what was found, what was thrown away and why, how close the evidence sits to the prospect,
and how strong a claim it can support.

## What it does

```
prospect ──▶ retrieve ──▶ rank ──▶ draft ──▶ verify ──▶ decision card + draft
              (rungs)    (pain    (syllogism) (2 passes)
                          match)
```

**Retrieve** — a cost-ordered ladder. Rung 0–1 are free (Google News, the company's own site,
Exa ×5, Tavily); rungs 2–4 are paid Apify actors that only fire when the free rungs come up
short. Every source reports `ok` / `empty` / `failed` / `skipped` **with a reason**, because
"found nothing" and "couldn't look" are different facts and collapsing them is how a pipeline
lies to you quietly.

**Rank** — each signal is scored against the pains in `value_prop.yaml`, and the match carries
its own one-line justification. Relevance is a three-way join: the signal × what we sell × this
person's role. A card that evidences no pain cannot become a hook.

**Draft** — one email, built as an explicit syllogism: hook (from the evidence) → pain (the
inference) → offer. The hook has to entail the offer, or the email has not earned the reply.

**Verify** — two passes. A deterministic grounding check that every claim traces to retrieved
evidence, then an LLM judge. Fabrication blocks. Format problems get quietly rewritten, never
reported as hallucination. Fit notes annotate and never gate.

### Claim strength — stated on the output's face

Every draft is labelled with how close its evidence sits to the prospect:

| Label | Means |
|---|---|
| `person_authored` | Their own words, name verified in the content |
| `person_attributed` | Them, named by someone else |
| `colleague_authored` | A named exec at the company, on the record — **not** the prospect's voice |
| `company_action` | Something the company did |
| `database_only` | Firmographics |
| `no_signal` | Nothing prospect-specific was found |

`no_signal` still produces an email — refusing outright helps nobody — but the output says
plainly that the opener is company-level and the offer is generic, and that a human needs to
judge it before it goes anywhere. Degrade, never refuse; but never silently.

The `colleague_authored` rung exists because of a real bug found in testing: a company CFO's
interview was being drafted as *"I saw you take a funnel-oriented view…"* to a different
person, and it passed verification, because nothing checked whose words they were. Retrieval
was right; attribution was wrong. Reclassify, never discard.

## Running it

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.local.example .env.local      # then add your keys
./venv/bin/streamlit run app.py       # http://localhost:8501
```

Other entrypoints:

```bash
PYTHONPATH=. ./venv/bin/python -m zara.probe --name "Dana Lee" --company "Acme"
./venv/bin/uvicorn zara.server:app     # POST /pipeline/run
./scripts/serve.sh start|status|logs   # managed local service, reports the git SHA it launched at
```

### Demo mode

A sidebar toggle replays a recorded retrieval snapshot and the recorded model responses, so a
full run completes with **zero network calls**. The pipeline itself still runs: ranking,
drafting and verification all execute for real against replayed inputs.

Fixtures are keyed on a hash of the prompt, and the prompt contains the prospect's **name** — so
demo mode only replays for a pair that was recorded. The recorded pairs are:

| Name | Company | Title | What it shows |
|---|---|---|---|
| Devin Weil | ShipMonk | Chief Financial Officer | `company_action`. Three data-breach cards vetoed before scoring; an undated card that led on score loses to a dated one |
| Chermaine Hu | Episode Six | Co-Founder & Chief Financial Officer | `person_authored` — the strongest claim the product can make |
| Riley Chen | Northwind Freight | *leave empty* | the `no_signal` path: nothing found, and the source table saying why |

Type the title exactly as written, or leave it empty for Riley. The title is part of
the prompt, so it is part of the hash the fixture is keyed on.

### Tests

```bash
env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONPATH=. ./venv/bin/pytest tests/ -q
```

126 tests, no live calls (fixtures replay). They must pass **twice consecutively** — the suite
has caught real non-determinism that a single green run hid.

## Configuration

`value_prop.yaml` is the brain: the pains signals are scored against, each with the observables
that would evidence it; the ICP rubric; the proximity weights; and the `never_reference`
guardrails. The Settings UI edits it visually behind a developer-mode password.

**Who the email is from** is configuration, not code:

| Field | Used for |
|---|---|
| `sender_name` | the sign-off, and the fallback identity |
| `sender_person` | the "I" in the opening line — the company speaking in the first person, not an invented human |
| `sender_company` | the entity the email introduces itself as: *"I'm \<person\> from \<company\>."* |

All three are editable from the sidebar and default to the file. Any of them may be
empty; the introduction degrades to a shorter honest form rather than breaking.

These live in config rather than in the prompt for a reason that is easy to get wrong:
the verifier grounds proper nouns against the string values of `value_prop.yaml`, so a
sender name that lives in code is a name no evidence contains, and the draft gets
blocked for saying who sent it.

The Settings UI sits behind developer mode, which opens only against
`ZARA_ADMIN_PASSWORD`. There is no default: unset means it never opens.

ICP is **informational and never rejects a prospect**. If someone typed this name in, assume
they had a reason; a headcount mismatch is a note on the card, not a veto.

`never_reference` is the other half — layoffs, bereavement, litigation, regulatory action.
These score *highest* on naive relevance and are unusable. Relevance is not permission.

## Limits — read this before trusting a number

- **Groq's free tier is per key: 8,000 tokens/minute and 200,000/day, each.** One prospect costs
  ~16k tokens across ~4 calls, so a single key spends ~45s of every run asleep on its own 429 and
  runs dry after about twelve prospects. Several keys can be pooled (`GROQ_API_KEY`,
  `GROQ_API_KEY_2..10`, or a comma-separated `GROQ_API_KEYS`): calls are spread round-robin so the
  per-minute bucket stops binding, and a 429 moves to the next key rather than sleeping. The
  daily ceiling multiplies by the number of keys; the per-minute bucket does not, because one
  call draws on one key.
- **Gemini's free tier is ~20 requests per day, per model** — enough for about three prospects.
  It is a fallback, and cannot be the primary provider.
- **Job postings were cut from the product.** A job ad is recruiter boilerplate, not the
  prospect's voice, and "I saw you're hiring" is the most worn-out hook in outbound. The five
  ATS fetchers still exist and are reported as `skipped` with that reason rather than silently
  dropped. Cost of the decision: the pain observables had to be rewritten away from job ads,
  and retrieval breadth is thinner for it.
- **Run history does not survive a restart** when deployed — the store is a local SQLite file
  and the host's filesystem is ephemeral. A seeded database ships with the app so the dashboard
  is never empty.
- **Snapshots were recorded against a placeholder person name**, so they exercise the company
  tier far better than the person tier. Live runs are the real test.
- Latency baseline from a prior build was p50 5.7s / p90 11.1s. Current runs are materially
  slower, and the rate-limit stall above is most of the difference.

## Repository map

| Path | What |
|---|---|
| `app.py` | Streamlit UI — Draft, Run History, Budget & Quota |
| `zara/fetchers/` | Sources: news, company site, Exa ×5, Tavily, Apify actors |
| `zara/ranker.py` | Pain matching, proximity, guardrails, hook articulation |
| `zara/drafter.py` | The syllogism |
| `zara/verifier.py` | Grounding pass, then the judge |
| `zara/orchestrator.py` | The rung ladder, the gap-filler gate, run deadline |
| `zara/utils/telemetry.py` | Per-run store: every card, prompt, and model call |
| `value_prop.yaml` | Pains, ICP, weights, guardrails |
| `brief/` | The case-study brief this was built against |

## Design constraints

Ten of them shaped this build. The load-bearing ones, keeping their original numbers (4 and 6 are real, just less interesting to read cold):

1. Degrade, never refuse — but never silently.
2. The costly signal is judgment, not composition.
3. Relevance is a three-way join.
5. Proximity to the prospect: authored > company action > database. `company-only` is honest, not failed.
7. Absence has two meanings. `empty` ≠ `failed` ≠ `skipped`.
8. Earn the turn: the hook must entail the offer.
9. The human is a collaborator, not an inspector — options, not verdicts, auditable in seconds.
10. Relevance is not permission.
