# Audit — hook selection and the draft prompt

**Date:** 2026-08-26. Static read of `zara/ranker.py` and `zara/drafter.py` plus the five
draft outputs already in the run stores. Zero pipeline runs, zero model calls.

Scope was deliberately narrow: (1) after cards are gathered, how does a hook get chosen, and
(2) what is the email-draft prompt actually asking for. Everything else was left alone.

---

## Path 1 — hook selection

### H1. The articulated hooks never reach the default draft

`_articulate_hooks` ([ranker.py:368](../zara/ranker.py#L368)) makes a full model call and
produces `hook_text` + `rationale` + `bridge` + `strength` for the top 3 cards.

`draft_email` receives `hook=None` on:

| Caller | Line |
|---|---|
| initial pipeline run | `orchestrator` → `s2.process_prospect` (no hook arg) |
| **Regenerate** button | [app.py:722](../app.py#L722) |
| **Deep Search** button | [app.py:728](../app.py#L728) |

The only caller that passes a real hook is the per-hook "use this" button at
[app.py:767](../app.py#L767).

So the default email is drafted from `winning_card.card.snippet` — raw retrieved text — and
the `hook.hook_text / rationale / bridge` block at
[drafter.py:114-120](../zara/drafter.py#L114-L120) is skipped. **The most-reasoned artifact in
the system is decorative by default, and its model call is paid for on every run.**

This is the single largest contributor to "the emails could be much better".

### H2. Hook strength has no influence on which card wins

[ranker.py:344-347](../zara/ranker.py#L344-L347) selects the winner by
`(proximity_weight, pain_score, tiebreak)` — and it runs *before* `_articulate_hooks`. A hook
the model itself rates 0.9 loses to one it rates 0.3 whenever proximity is higher.

Observed consequence, Alex Rivera / ShipBob (seed run `7099a32a4781`): an **engineering** card
won on `colleague_authored` proximity — *"dumped 500 codebases overnight, slashing
commit-to-push time by 50% and tripling weighted PR velocity"* — and was used to sell
**finance reconciliation**. Compass III's three-way join (signal × what we sell × role) failed
and nothing downstream caught it.

### H3. Exactly two hooks, never three

The Compass VI swap test dedupes on `card.tier`
([ranker.py:325-334](../zara/ranker.py#L325-L334)), and `tier` has only two values
(`company` / `person`). So `remaining_eligible` is at most 2 entries before `[:3]` is applied.

Confirmed against the run store: `hooks = 2` on every successful run, `0` on `no_signal` and
crashed runs. Never 3. This is open question Q3 — `tier` is doing three jobs and needs
splitting into `proximity` and `hook_kind`.

### H4. Recency is absent from the winner sort

Known and deliberately deferred (see the 2026-08-25 plan). An `authored` card at weight 4 beats
a `company_action` card at weight 2 regardless of age. Mitigated, not fixed, by the honesty
guard in `f38cf46`: an old card can still win, but the draft must now describe its age
truthfully.

---

## Path 2 — the draft prompt

The grounded prompt is [drafter.py:85-155](../zara/drafter.py#L85-L155). It is a fixed
syllogism: `1. Hook (raw snippet) → 2. Pain (from value_prop) → 3. Offer`, plus an attribution
block, plus strictness constraints. System instruction at
[drafter.py:150-155](../zara/drafter.py#L150-L155).

Read against the five real outputs, four concrete defects:

### D1. Only the first sentence is personalised

Sentences 2-4 are the same `pain_statement` paraphrased. `"reconciliation-heavy"` appears in
**5 of 5** drafts. `"automate those manual, reconciliation-heavy processes"` is near-verbatim
in three.

The system instruction already forbids reciting the pain statement verbatim — so the model
paraphrases *the same source sentence* *the same way* every time. Guarding the wording did not
produce variety, because the input never varies. The pain statement is one of five fixed
strings in `value_prop.yaml`; nothing derives sentence 2 from *this* prospect's evidence.

### D2. The prompt explicitly asks for the mushy connective

> *"State the middle term (the pain point) as an inference in your own plain words."*

That instruction is why two of five drafts open sentence 2 with **"It sounds like…"** — the
model narrating its own reasoning rather than writing an email. The syllogism is a good
*internal* structure and a bad *surface* structure; right now it is both.

### D3. Attribution is correct and unusable

When `attributed_to` is `None`, [drafter.py:105](../zara/drafter.py#L105) falls back to
`f"a colleague at {company}"`, producing:

> *"A colleague at Modern Treasury mentioned that you're celebrating the company's eighth
> birthday…"*

This attributes to a colleague a fact about the **recipient**. It is grammatically faithful to
the constraint and unsendable. The guard is right — the fallback string is not.

### D4. Structural gaps

| Gap | Evidence |
|---|---|
| No subject line | `DraftOutput` is `draft_text: str` only ([drafter.py:9](../zara/drafter.py#L9)) |
| CTA never requested | absent from both prompt branches; Jordan Ellis draft has **no CTA at all** |
| Greeting inconsistent | Alex Rivera draft opens with no "Hi Alex," |
| Signed by a company | `Best, Zamp` — `sender_name` is a company string and a human signer is explicitly forbidden ([drafter.py:47](../zara/drafter.py#L47)) |

D4 is D18 in the backlog: it needs the in-app sender profile (person, role, one-liner, outreach
intent, CTA, tone, length), not a prompt tweak.

---

## Recommendation

**Hook path — wire it up first, tune the sort second.**

Step 1 is small and high-leverage: pass the top-strength hook into the default draft, so
`s2.process_prospect` selects `hooks[0]` (or the hook whose `card_index` maps to the winning
card) when no hook is supplied. This alone stops the raw-snippet drafting and stops paying for
a discarded model call. It does **not** re-record fixtures — the ranker prompt is untouched.

Step 2 — blending `hook_strength` into the winner sort to kill the Alex Rivera mismatch class —
should wait until step 1's output is visible. The weighting is a judgement call about a decay
curve, and guessing it now without seeing hook-led drafts is the same mistake as the recency
sort. It also changes ranking, so it costs a re-record.

**Draft prompt — the voice and the boilerplate are one fix, the structure is another.**

D1 + D2 + D3 are all the same root cause: the prompt hands the model a fixed pain sentence and
asks it to narrate the join out loud. Fixing them together is a prompt-and-fallback change
inside `drafter.py`, one re-record.

D4 is blocked on D18 (sender profile) and should not be attempted as a prompt patch —
adding a CTA instruction without a configured CTA just moves the invention risk into the
model.

---

## Not in scope, noted

- Q3 (`tier` → `proximity` + `hook_kind`) is the real fix for H3, and is a vocabulary problem
  before a code problem — warrants an ADR.
- Q4 (`general_news` winning with no middle term) interacts with D1: when `pain_match` is
  `None` or `general_news`, `pain_statement` becomes *"We don't know their specific pain
  yet…"* ([drafter.py:81](../zara/drafter.py#L81)), which the model faithfully renders as
  generic filler.
