# Ranking audit

## 2026-08-28 — Google News dates never parse, so the freshest source is invisible

`2026-08-28-google-news-shipbob-baseline.png` is a plain Google News search for "shipbob",
kept as the baseline a human would get with no tooling at all. It surfaces, among others:

- "ShipBob Launches First Anthropic-Verified Fulfillment Connector, Anchoring its AI Suite" (3 weeks)
- "ShipBob Wants AI to Run Retail Fulfillment" (3 weeks)
- "ShipBob's Spring 2026 Release" (May 2026)

Our pipeline **retrieved the same stories** — they are in `tests/fixtures/shipbob_snapshot.json`
under `GoogleNewsRSS` — and then led with a **2021 funding round** instead.

### Cause

One line. `_compute_recency()` (`zara/ranker.py:150`) parses dates with
`datetime.fromisoformat()`. Google News RSS emits **RFC 822**:

    'Tue, 04 Aug 2026 07:00:00 GMT'      -> fromisoformat raises -> except: return None
    '2021-06-29T00:00:00.000Z'  (Exa)    -> parses fine -> 1883 days

Every Google News card therefore comes out **undated**, and the failure is silent — the
`except Exception: return None` is the exact antipattern CLAUDE.md forbids importing from Zen.

### Why that loses the hook

Undated cards take the worst recency multiplier in `_pre_score`, so they sort to the bottom of
the pre-scoring order and fall outside the `card_cap` of 10 — they are never scored at all. Every
`GoogleNewsRSS` card on the ShipBob run is excluded with
`outside the top 10 by relevance (hard cap)`.

Worse, the safety net written for precisely this case cannot fire. The `recency_reserve`
(`ranker.py:455-465`) promotes the freshest cards regardless of proximity — its comment reads
*"we never looked at the biggest news of the quarter is not a defensible way to lose a hook"* —
but it filters on `_compute_recency(...) is not None`, so it can only ever promote **dated**
cards. The bug makes the guard blind to the one source it exists to protect.

### Fix

Fall back to RFC 822 when ISO parsing fails:

    from email.utils import parsedate_to_datetime
    # after fromisoformat raises:
    dt = parsedate_to_datetime(published_date)

Verified against the snapshot's real values: 23, 7, 107 and 272 days respectively.

Two smaller defects found alongside:

- Several fetchers store the **string** `"None"` rather than `None` for a missing date
  (Jina, Tavily, ExaEdgar). `if not published_date` does not catch it; it fails in the parser
  instead and lands on the same silent `return None`.
- News snippets are the headline plus the publisher and nothing else, so even once a card is
  scored there is little text for pain matching to work with.

### Blast radius

`recency_days` is interpolated into the ranker prompt (`ranker.py:606`) and changes which cards
enter the shortlist, so **fixing this changes every downstream prompt and invalidates every
recorded fixture.** It is a re-record, not a patch. Do it with `USE_FIXTURES=fill` and re-verify
all five demo pairs afterwards.

---

## 2026-08-28 — the namesake guard has a one-tier hole

Found while explaining why the `thin_prospect` snapshot leads with a basketball interview.

`_company_is_mentioned()` correctly returns **False** for
*"Tre White 1-on-1 Interview | Indiana Pacers Prospect Workouts"* against Acme Logistics — neither
"acme" nor "logistics" appears anywhere in the card. The guard works.

It never runs. `ranker.py:396` gates it on proximity:

    if not excluded and not guardrail_hit and proximity in ("authored", "attributed"):

The winning card is **`colleague_authored`**, which is not in that tuple. So a card that never
names the company is exempt from the namesake check purely because of how its proximity was
classified, and can win outright.

The original defect this guard was written for (a Stephanie Neill at Stripe competing for a hook
about Stephanie Fielding at Stord) was an `authored` case, which is presumably why the tuple stops
there.

**Fix:** include `colleague_authored` in the gate. It is the same unbacked assertion — "this
evidence is about our prospect's company" — and the same downweight is the right response.

Related: `THIN_SIGNAL_FLOOR = 0.35` correctly marked this run `thin` (the badge reads
"thin signal"), but a thin flag annotates the output; it does not stop a 0.19 card from winning or
fall the run back to `no_signal`. Worth deciding whether it should.

### Note on the snapshot itself

`thin_prospect_snapshot.json` was recorded against a placeholder named literally "thin prospect",
so every card is a keyword match on those words — Phillies thin prospect pool, Top 100 Prospect
Rankings, ThinOptics Inc, tensile properties of thin plastics, thin-bedded turbidites. Retrieval
never saw "Dana Lee" or "Acme Logistics". That makes it a good junk-evidence stress case and a
bad example of live retrieval; describe it as the former.
