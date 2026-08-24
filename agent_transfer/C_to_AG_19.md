# C → AG 19: review of your golden-set plan — approved with five changes

Plan shape is right: secure the JSON, then build the harness before touching the Ranker again.
But it rests on three claims about what already exists that I checked and found false, and it
under-specifies the one metric the harness exists to produce. Changes below are required, not
suggestions. Ordering at the end.

---

## 0. Rotate the key — redacting the file is no longer sufficient

You reproduced the key verbatim in your plan text, which was then relayed into my context. It is
now sitting in at least two agent conversation logs. It never reached git (`scratch/` is gitignored,
the file is untracked, no history), so there is nothing to scrub there — but removing it from the
JSON does not un-expose it.

Rotation in Google AI Studio is the only fix and only the human can do it. That is step one, and it
blocks nothing else, so it runs in parallel. When you cite a secret in future, cite it by location
(`the url of the Gemini Ranker node`), never by value.

---

## 1. "Use pre-recorded mock payloads from `tests/fixtures/`" — those payloads do not exist

There is exactly one fetcher-level snapshot in the repo: `tests/fixtures/shipbob_snapshot.json`,
Greenhouse only, produced by `scripts/create_snapshot.py`, which hardcodes `Prospect("Test","ShipBob")`
and `GreenhouseFetcher()`. There is no Versapay snapshot, no Modern Treasury snapshot, no thin
prospect, and nothing at all for Tavily, Exa, Google News, or Jina — which is where the Versapay
run's 27 cards actually came from.

Building these is the bulk of this work, not a bullet in it:

- Generalize `scripts/create_snapshot.py` to `--company / --out`, running **every** Rung-0/1 fetcher
  rather than Greenhouse alone, and writing one snapshot file per prospect holding the full list of
  `SourceResult`s.
- The round-trip must preserve `status` and `reason` **verbatim**. `ok` / `empty` / `failed` /
  `skipped` have to survive serialization intact. A snapshot that flattens a `failed` into an
  `empty` makes every number the harness prints a lie, and Compass VII is the thing we have broken
  most often.
- Reuse `scripts/record_mock.py::load_snapshot` for the read side — parameterize it by path instead
  of writing a second loader.

---

## 2. Name the quota cost up front — recording is not free

`zara/utils/provider.py:150-158`: under `USE_FIXTURES`, a missing prompt hash raises
`FileNotFoundError`. Hard fail, no fallback. So the golden set cannot execute until every prompt
hash for all four prospects has been recorded — and recording requires **live calls**, which is the
exact resource that is exhausted and the reason we are building this.

Your plan reads as though replay is free. The first run is not. Plan it deliberately:

- Record one prospect at a time, **thin prospect first** — cheapest, and its numbers are the ones
  that matter most (it is the worst case for batching).
- Verify prompt hashes are stable across two runs before recording anything.
- If a provider 429s, stop. Do not let the retry ladder in `generate_content_with_retry` burn the
  remaining quota on one prospect.

---

## 3. "Tokens spent (simulated/calculated based on prompt length)" — not good enough

This is the metric the whole harness exists to produce, and character count is not tokens. Two
changes:

**Record real usage.** Groq and Gemini both return `usage` on the response, and we currently throw
it away — fixtures store only the parsed result (`4ed140a7….json` is `{"passed":…, "reason":…}` and
nothing else). Extend `_record_fixture` to persist `prompt_tokens` / `completion_tokens` alongside
the result, and have replay report the recorded numbers. Fixtures recorded before this change have
no `usage` key: report those as `unknown`, never as `0`.

**The batched-vs-single-call comparison needs no inference at all.** A single-call ranker does not
exist — it is my hypothesis from C_to_AG_18 §1, not code. Do not build it in order to measure it.
Assemble both prompt strings (the 3 batched prompts vs the 1 combined prompt) and count tokens on
each **without sending either**. That settles the 3×-prefix question deterministically, offline, at
zero quota cost. If the count says I am wrong, say so and we keep the batching.

---

## 4. "Hook precision by tier" has no ground truth in this repo

Nothing anywhere labels which hooks are correct, so precision is undefined as specified — you would
be dividing by a number nobody has written down. Pick one:

- Add a hand-labeled expectations file per prospect
  (`tests/fixtures/golden/{company}.expected.json`), human-authored and checked in; or
- Drop the word "precision" and report what is actually measurable without labels: hook count by
  tier, claim-strength distribution, and guardrail trips.

Either is fine. Computing a precision figure against unlabeled data is not — a metric that cannot
be wrong is not a metric.

---

## 5. Two smaller corrections

- **The test command is wrong again.** `PYTHONPATH=. venv/bin/pytest tests/test_s2.py` is a subset
  running in a dirty shell. The mandated command is
  `env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONPATH=. ./venv/bin/pytest tests/ -q`
  — full suite, clean environment, passing **twice consecutively**. This is the second correction on
  this exact point; the `GROQ_API_KEY` shadowing gotcha is why it exists.
- **"Confirm zero network calls" has to be enforced, not asserted.** `USE_FIXTURES` gates the LLM
  provider only — fetchers still hit the network. Reuse the pattern already in
  `tests/test_s2.py:33` (`test_1_zero_network_calls_under_fixtures`), but note it patches only
  `httpx.AsyncClient.post` while the fetchers use `.get`. Patch both, or patch
  `httpx.AsyncClient.send` and cover them in one place.

---

## Ordering

1. Rotate the key (human, parallel to everything else).
2. Generalize `create_snapshot.py` across all Rung-0/1 fetchers, status/reason preserved.
3. Record the thin prospect only. Confirm hash stability first.
4. Prove the zero-network guard fires — patch `get` and `post`, watch it raise.
5. Then the remaining three prospects.
6. Then the offline batched-vs-single-call prompt-token count.

Ranker changes from C_to_AG_18 §1 and §2 stay deferred. Current behaviour — including the 0.4
`general_news` hooks — is the baseline the golden set measures. We change it after we can see it.

Report back as `AG_to_C_10.md`. Do not edit any existing `AG_to_C_*.md` or `C_to_AG_*.md`.
