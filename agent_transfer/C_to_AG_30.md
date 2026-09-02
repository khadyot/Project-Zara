# C -> AG (30): §12 cleanup batch — four mechanical fixes, one doc correction

Executor ticket. Every fact below was verified against the tree and against live
APIs by the reviewer on 2026-09-02. **You do not need to verify any of it, and you
must not try** — several checks require live API calls, which you may not make.

Source of the defect numbering: `reference/product-audit.md` §12.
Out of scope: 12.1, 12.2 (already fixed), 12.5 (ICP fit — the human has deferred it).

---

## Non-negotiables

1. **Exclusive file list.** You may edit ONLY these five files:
   - `zara/utils/resolve.py`
   - `zara/fetchers/news.py`
   - `zara/fetchers/exa.py`
   - `zara/fetchers/tavily.py`
   - `zara/ranker.py`
   - `CLAUDE.md`

   Nothing else. Not tests, not fixtures, not `value_prop.yaml`, not `sources.yaml`.
   If a task seems to require another file, **stop and report** — that is a sign
   the ticket is wrong, not that the boundary is.

2. **No git.** Do not run `git` at all: no add, no commit, no checkout, no stash.

3. **No live API calls.** Do not run the app, `zara.probe`, `scripts/bakeoff_search.py`,
   or anything that reaches Groq, Gemini, Exa, Tavily, Brave, Parallel or Apify.
   The only command you run is the test suite in §Acceptance.

4. **Stop rule: two attempts.** If a task fails twice, stop, revert that task's edit,
   and report. Do not try a third approach.

5. **No fixture re-recording.** See §Acceptance — a hash mismatch means you changed
   something you were not asked to change.

---

## Task 1 — 12.3: the domain lookup never fires

**File:** `zara/utils/resolve.py`

`resolve_company_entity` gates its Tavily domain lookup on the company name having
had a corporate suffix stripped. Any company typed without one — *Episode Six*,
*ShipMonk*, *Stord*, most real inputs — normalizes to itself, so the lookup never
runs and `domain` stays None. That disables `ExaBlogFetcher` outright (it returns
`empty: no domain`) and drops `JinaCompanySiteFetcher` to guessing four spellings.
Observed live on 2026-09-02: `[ ] r1 ExaBlog  no domain`.

**Change exactly one line.**

Find:
```python
    if tavily_key and normalized != raw_company.strip():
```
Replace with:
```python
    # The suffix condition that used to sit here (`normalized != raw_company.strip()`)
    # meant the lookup only ran when normalize_company had actually stripped
    # something, so every company typed without an Inc/LLC/Ltd never got a domain
    # at all -- which is most of them.
    if tavily_key:
```

Nothing else in this file changes.

---

## Task 2 — 12.7: TLS verification is disabled

**File:** `zara/fetchers/news.py`

Find:
```python
            async with httpx.AsyncClient(verify=False) as client:
```
Replace with:
```python
            async with httpx.AsyncClient() as client:
```

**Verified by the reviewer**, so do not re-test it: the same Google News RSS query
returns HTTP 200 and 43 entries with verification both on and off. The `verify=False`
was a leftover from a macOS SSL problem whose documented fix is to use `httpx`,
which this code already does.

---

## Task 3 — 12.4: the YouTube transcript code cannot run

**File:** `zara/fetchers/exa.py`, in `ExaYouTubeFetcher.fetch`

This block is dead **twice over**, and both causes must be fixed or it stays dead:

1. `card.snippet = text[:1500]` assigns to a `@dataclass(frozen=True)`, raising
   `FrozenInstanceError` straight into the bare `except Exception: pass` below it.
2. `YouTubeTranscriptApi.get_transcript` **does not exist** in the installed
   version. Confirmed: `youtube-transcript-api==1.2.4`, where
   `hasattr(YouTubeTranscriptApi, "get_transcript")` is `False`. The current API is
   an instance method: `YouTubeTranscriptApi().fetch(video_id)`, which returns an
   iterable of snippet objects carrying a `.text` attribute.

Replace the whole `if res.status == "ok":` block (from `# Now supplement the cards`
down to and including `return res`) with:

```python
        # Transcript enrichment was dead in two ways at once. SignalCard is
        # frozen, so `card.snippet = ...` raised FrozenInstanceError into the bare
        # except below; and YouTubeTranscriptApi.get_transcript was removed in
        # v1.x, so the call could never have run either. Rebuild the card instead
        # of mutating it, and use the instance API.
        if res.status == "ok" and res.cards:
            enriched = []
            for card in res.cards:
                text = ""
                try:
                    parsed = urlparse.urlparse(card.source_url)
                    video_id = urlparse.parse_qs(parsed.query).get("v")
                    if video_id:
                        fetched = await asyncio.to_thread(
                            YouTubeTranscriptApi().fetch, video_id[0]
                        )
                        text = " ".join(s.text for s in fetched if getattr(s, "text", ""))
                except Exception:
                    text = ""
                enriched.append(
                    dataclasses.replace(card, snippet=text[:1500]) if text else card
                )
            res = dataclasses.replace(res, cards=enriched)
        return res
```

Add `import dataclasses` to the imports at the top of the file if it is not already
there.

**Note the failure mode is silent by design**: a video with no transcript keeps its
original snippet. That is correct — do not add logging or change it.

---

## Task 4 — 12.9: Tavily spend is invisible

**File:** `zara/fetchers/tavily.py`

`_result` hardcodes `cost_usd=0.0`, so Tavily never appears in the run cost on the
decision card and never reaches the budget guard, while `sources.yaml` types it
`paid_api`.

Price, traced in `reference/data-source-strategy.md` and **not to be re-researched**:
Tavily's entry paid tier is $30/month for 4,000 credits, and one search query is one
credit — **$0.0075 per query**.

**4a.** Add near the top of the file, just below `TAVILY_URL`:
```python
# $30/month for 4,000 credits at the entry tier, one credit per search query.
# Traced in reference/data-source-strategy.md.
COST_PER_QUERY = 0.0075
```

**4b.** Change the `_result` signature to accept a cost, defaulting to zero:
```python
    def _result(self, status, reason, cards, start, cost_usd: float = 0.0) -> SourceResult:
        return SourceResult(
            source="Tavily", rung=1, status=status, reason=reason,
            cards=cards, cost_usd=cost_usd,
            elapsed_ms=int((time.time() - start) * 1000),
        )
```

**4c.** Pass the cost only on the paths where queries were actually dispatched.
There are five `self._result(...)` call sites. Leave the two `"skipped"` ones alone
(no key, budget exhausted) — those spend nothing. For the three that run **after**
`outcomes = await asyncio.gather(...)` — the `"failed"`, `"empty"` and `"ok"`
returns at the end of `fetch` — add `len(query_plan) * COST_PER_QUERY` as the fifth
argument. Example for the last one:
```python
        return self._result("ok", None, cards, start, len(query_plan) * COST_PER_QUERY)
```

`query_plan` is already in scope at all three sites (it is assigned earlier in
`fetch`). Charging for dispatched queries slightly over-counts when one errors;
that is deliberate — over-reporting spend is the safe direction for a budget guard.

---

## Task 5 — 12.8: an unreachable branch in the ranker

**File:** `zara/ranker.py`, inside `rank_prospect`

`chunk_size = max(len(to_score), 1)` means the `for chunk_idx in range(0, len(to_score), chunk_size)`
loop always has exactly one iteration, so the early-exit machinery can never run:
`chunk_idx + chunk_size` is always `>= len(to_score)`, making the inner range empty,
and the `break` exits a loop that was ending anyway.

Delete these three things, and nothing else:

1. The line `found_strong_hook = False` (immediately after `scores = resp.scores`).
2. The two lines that set it:
```python
                            if final_score >= 0.8:
                                found_strong_hook = True
```
3. The whole trailing block:
```python
                if found_strong_hook:
                    for remain_idx in range(chunk_idx + chunk_size, len(to_score)):
                        i, _ = to_score[remain_idx]
                        rc = ranked_cards_map[i]
                        ranked_cards_map[i] = RankedCard(
                            card=rc.card, pain_match=None, proximity=rc.proximity,
                            recency_days=rc.recency_days, score=0.0, excluded="skipped due to early exit (strong hook found)",
                            guardrail_hit=rc.guardrail_hit, attributed_to=rc.attributed_to
                        )
                    break
```

**Do not** touch `chunk_size`, the `for chunk_idx` loop itself, or anything else in
this function. Leaving the single-chunk loop in place is intentional.

---

## Task 6 — 12.6 was NOT a defect: correct the doc instead

**File:** `CLAUDE.md`

`reference/product-audit.md` §12.6 claimed `provider.py`'s `GEMINI_MODEL =
"gemini-2.5-flash"` named a retired model. **That was wrong, and the code is
correct.** Verified live on 2026-09-02 against the exact endpoint and auth header
the code uses (`/v1beta/openai/chat/completions`, `Authorization: Bearer`):
`gemini-2.5-flash` returns HTTP 200. `gemini-flash-latest` also works.

`CLAUDE.md` is the file carrying the wrong fact. Under "Environment gotchas", find:
```
- **Gemini models that appear in `models.list()` may 404 on generate** — listing ≠ callable. `gemini-2.5-pro`/`gemini-2.5-flash` are retired for new users.
```
Replace with:
```
- **Gemini models that appear in `models.list()` may 404 on generate** — listing ≠ callable, so verify the exact model against the exact endpoint before believing either. Re-checked 2026-09-02: `gemini-2.5-flash` and `gemini-flash-latest` both return 200 on `/v1beta/openai/chat/completions` with `Authorization: Bearer`. An earlier note here called `gemini-2.5-flash` retired; that was wrong, and `provider.py` was right to keep it.
```

**Do not change `zara/utils/provider.py`.** It is correct as written.

---

## Acceptance

Run exactly this, twice in a row:

```
env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONPATH=. ./venv/bin/pytest tests/ -q
```

**Expected both times: `133 passed, 2 skipped`.**

That number is the whole gate, and it is exact — the reviewer ran it on the tree
you are starting from.

**No fixture should need recording.** The reviewer confirmed why: none of these six
tasks changes any prompt text, and Task 1 cannot reach the fixture path because
`_run_end_to_end` short-circuits `_resolve()` whenever `replay_snapshot` is set, and
no test calls `resolve_company_entity`.

**So if you see `FileNotFoundError: Fixture not found for prompt hash ...`, you have
edited something outside this ticket.** Do not record a fixture. Do not set
`USE_FIXTURES=fill`. Revert your last edit and report.

## Report back

- Both test-run outputs, pasted verbatim.
- A plain list of every file you edited. **Do not run `git status` to produce it** —
  rule 2 means no git at all. Write the list from memory of what you touched; the
  reviewer will check it against the tree.
- Any task you stopped on, and at which attempt.
