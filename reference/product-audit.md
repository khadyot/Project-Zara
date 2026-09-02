# Zara — full product audit, stage by stage

> **Status, updated 2026-09-02 (end of session).** Written against `6df85ef`; the
> work below has since landed on `khadyot/hook-binding-and-clean-scoring`, 8 commits.
> §12 is closed except 12.5. §14 items 1 and 3 are done. Sections 0–11 describe the
> pipeline as audited — where a stage has since changed, the §12 entry says so.
> **Read §12 and §14 first; they carry the current state.**

## Context

You are revamping the product and want to drive the decisions yourself. Your method: take
one stage at a time, research best practice externally, come back with a ruling. You have
already done this for web search (Brave Search API, Perplexity Search API) and will hand
those over next.

This document is the input to that process. For every stage it states **what it does**,
**how it actually does it** (read off the code, not the docs — the docs have drifted once
already), **how well it is doing**, and **the decision that is yours to make**.

Read against the tree at `6df85ef`. 7,498 lines of Python, 126 tests, ~5–7 LLM calls and
~16k tokens per prospect.

Nine defects surfaced during this audit that were not on any prior list. They are collected
in §12 — three of them are load-bearing on quality and one silently discards a paid LLM call
on most runs.

---

## The pipeline, end to end

```
input (name, company, title)
  └─ 0. entity resolution ─────────── resolve.py       normalize + optional Tavily domain lookup
  └─ 1. retrieval ladder ──────────── orchestrator.py  rung 0 → 1 → (gate) → 2 → 3 → 4
  └─ 2. eligibility classification ── classifier.py    1 LLM call, professional/personal/ambiguous
  └─ 3. ranking ───────────────────── ranker.py        proximity → guardrails → cap → 1 LLM call
  └─ 4. hook articulation ─────────── ranker.py        1 LLM call, N hook options
  └─ 5. winner selection ──────────── ranker.py        deterministic, score × hook strength
  └─ 6. drafting ──────────────────── drafter.py       1 LLM call (+ up to 3 retries)
  └─ 7. anti-template ─────────────── antitemplate.py  cross-draft repetition, deterministic
  └─ 8. verification ──────────────── verifier.py      deterministic pass + 1 LLM call
  └─ 9. presentation ──────────────── app.py / s2.py   decision card
```

---

## 0. Entity resolution — `zara/utils/resolve.py`

**What it does.** Turns the typed company string into a canonical name and, ideally, a domain.
The domain is what `ExaBlogFetcher` searches and what `JinaCompanySiteFetcher` reads.

**How.** `normalize_company()` strips corporate suffixes off the tail (`Inc`, `LLC`, `Technologies`,
`Labs`, …). Then, **only if the normalized string differs from the input**, it makes one Tavily
call for `"<name> company official website"` and regex-matches a domain out of the top 3 results.
Otherwise it returns `domain=None`.

**How it's doing — badly, and it's structural.** The condition on line 68 is
`normalized != raw_company.strip()`. A company typed without a corporate suffix — *Episode Six*,
*ShipMonk*, *Stord*, most real inputs — normalizes to itself, so **the domain lookup never fires**.
Downstream: `ExaBlogFetcher` returns `empty: no domain` and Jina falls back to guessing
`<name>.com`, `<name>.io`, `get<name>.com`, `<name>hq.com` in sequence. Two of your ~11 sources are
running on a coin flip.

**Your decision.** Whether entity resolution deserves a real identity step (domain + canonical
name + maybe LinkedIn company URL) as a first-class stage, and what supplies it. This is the
stage that decides *who you are researching* — everything downstream inherits its errors, and it
is currently the thinnest code in the repo.

---

## 1. Retrieval — the part you are already working on

### The ladder as built

| Rung | Sources | Cost | Fires when |
|---|---|---|---|
| 0 | GoogleNewsRSS, Jina (company homepage) | free | always |
| — | **gap-filler gate** | — | counts person-tier cards from rung 0 |
| 1 | Exa ×5 (LinkedIn, News, Blog, EDGAR, YouTube), Tavily | free | **always** — gate deliberately does not cover rung 1 |
| 2 | Apify LinkedIn Company | ~$0.002 | gate open + budget |
| 3 | Apify LinkedIn Profile | ~$0.004 | gate open + no person profile found yet |
| 4 | Apify posts/Twitter/YouTube/Reddit/Instagram (+7 more in deep) | ~$0.005 | gate open + total miss, or deep mode |
| — | 5 ATS fetchers (Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee) | — | **retired**, reported `skipped` with reason |

Gate rule: if rung 0 yields **≥2 person-tier cards**, rungs 2–4 are all skipped with
`gap_filler: sufficient person signal from free rungs`. Budget cap `$4.00` month-to-date.

### What each source actually sends

**GoogleNewsRSS** — `"<company>" AND (company OR startup OR funding OR CEO OR revenue OR platform
OR software OR hires OR launches)`. Takes 10 entries, keeps ≤6. Filters noise through two
hardcoded word lists: `NOISE_PATTERNS` (highway, police, crash, weather…) and `AMBIGUOUS_NAMES`
(`ramp`, `beam`, `trail`, `summit`, `atlas`, `cascade`, `zen`) — a literal denylist of company
names that collide with English words. Snippet is the RSS `<description>`, HTML-stripped, capped
at 1000 chars. **In practice that description is the headline plus the publisher name** — Google
News RSS carries no article body, so these cards are ~100 useful characters each. Runs with
`httpx.AsyncClient(verify=False)` — TLS verification disabled.

**Exa ×5** — all five share one method. `type="auto"`, **`num_results=2`**, snippet `res.text[:1500]`.
Queries are literal f-strings:

| Fetcher | Query | Domain scope |
|---|---|---|
| ExaLinkedIn | `"{person} {company}"` | linkedin.com |
| ExaNews | `"{company} news OR launch OR funding"` | 7 hardcoded outlets (TechCrunch, Forbes, WSJ, Bloomberg, Reuters, CNBC, FT) |
| ExaBlog | `"{company} product launch OR news"` | the company domain — **usually absent, see §0** |
| ExaEdgar | `"{company} 8-K OR funding"` | sec.gov |
| ExaYouTube | `"{person} {company} talk OR interview"` | youtube.com |

Three things to notice. **Ten cards is the entire Exa ceiling** for a prospect (5 × 2). The `OR`
syntax is keyword-search idiom being fed to a neural/semantic engine — it is being embedded as
literal text, not parsed as an operator. And no call passes a date filter, a `livecrawl` setting,
or a text-length option, so recency is something the ranker fixes up afterwards rather than
something retrieval asks for.

**Tavily** — 2–3 queries: `"{person}" {company}`, `"{company}" news funding announcement 2026`, and
if a title is known `"{company}" "{title}" priorities`. `max_results=4`, content `[:1200]`. No
`search_depth="advanced"`, no `include_raw_content`. Note the hardcoded `2026` in query two.
Registry calls Tavily paid; the code reports `cost_usd=0.0` and it sits in the free rung — it
meters itself through a separate credit counter instead.

**Jina** — reads the company homepage as markdown, 2000 chars, tagged `firmographic`. This is
marketing copy; as personalization evidence it is close to inert, and it is also the only
rung-0 source that can ever produce a "person" card (it can't), which matters for the gate.

**Apify ×16** — cookieless actors, pay-per-event, all documented in `sources.yaml` with a
`cookieless_proof` field. Only the LinkedIn ones fire under the default `standard` profile.

### How it's doing

The honest summary: **retrieval is the binding constraint on the whole product, and it is running
at roughly a third of its own configured capacity.** Ten Exa results, six news headlines with no
bodies, a homepage dump, and a domain lookup that usually doesn't fire. Every quality problem
downstream — thin hooks, stale hooks, company-tier drafts where you wanted person-tier — traces
back here. The ranking machinery above it is considerably more sophisticated than the evidence
it is being asked to rank.

### The interface a replacement has to satisfy

Any new search provider drops in as a class with one method. This is the whole contract:

```python
class MyFetcher:
    async def fetch(self, prospect: Prospect) -> SourceResult: ...
```

`SourceResult` (`zara/models.py:27`) is frozen and validates itself: `status` is one of
`ok` / `empty` / `failed` / `skipped`; a non-`ok` status **must** carry a `reason` and **must**
have zero cards. `SignalCard` needs `claim`, `signal_type`, `source_url`, `published_date`,
`snippet` (verbatim — never paraphrased), `tier` (`company` | `person`), `source`. Register the
instance in the right rung list in `orchestrator.py:375`.

**Your decisions here.**
1. Which providers, at which rung, replacing or supplementing what. Brave and Perplexity are
   different shapes — Brave is an index you query, Perplexity answers a question and cites. The
   second is a different contract from `SignalCard` (a synthesized answer is not a verbatim
   snippet) and it is worth deciding deliberately whether an answer-shaped source is allowed to
   produce evidence, or only to *find* URLs that a reader then fetches.
2. Query strategy: how many queries per prospect, and written how. Today they are f-strings; the
   alternative is generating queries from the prospect + the pains.
3. Whether retrieval fetches page bodies. Right now nothing follows a link — including links
   inside a post that won.
4. The date question: filter at retrieval, or retrieve wide and let the ranker discount age.

---

## 2. Evidence cleaning — `zara/evidence.py`

**What it does.** Strips fetcher furniture off a snippet: Exa's generated `#` header, the author
bio block, `---` separator, engagement tails, markdown link URLs. Removal only, never rewriting,
because `SignalCard.snippet` is contractually verbatim.

**How it's doing.** This is good code and it earned its place — it took Chermaine Hu's card from
1254 chars of mostly bio down to 728 chars of actual post. **But it is not applied everywhere.**
The hook prompt and the drafter call `clean_snippet()`. The pain scorer, the guardrail matcher,
and the namesake check all read `card.snippet[:500]` **raw** — so the stage that decides which
cards survive at all is reading exactly the header-and-bio furniture this module exists to
remove. See §12.2.

**Your decision.** Probably none — this is a bug to fix, not a policy to set. Worth knowing it
exists because it changes what "the ranker scored it low" means today.

---

## 3. Eligibility classification — `zara/classifier.py`

**What it does.** One LLM call over social cards, labelling each `professional` / `personal` /
`ambiguous` / `unknown`. Anything not `professional` is excluded in the ranker. On failure,
everything is marked `unknown` — which excludes it.

**How it's doing.** Defensible but expensive: a full LLM call per run to make a judgment that
mostly reduces to "is this about their work". Fails closed, which is the right direction but
means a provider hiccup silently costs you your social tier.

**Your decision.** Whether "is this personal life" is worth a dedicated model call, or belongs
folded into the pain-scoring call (one fewer round trip, one fewer failure mode), or is a rule.

---

## 4. Ranking — `zara/ranker.py`, 902 lines, the densest thing in the repo

Five sub-stages, in order:

**4a. Proximity** — the tier ladder, computed deterministically from URL and content:

| Label | Weight | Means |
|---|---|---|
| `authored` | 4 | the prospect wrote it — LinkedIn `/posts/` byline matches, or content mentions them |
| `attributed` | 3 | them, named by someone else |
| `colleague_authored` | 2.5 | a named exec at the company, on the record — not the prospect |
| `company_action` | 2 | the company did something |
| `database` | 1 | a directory row (22 hardcoded hosts + any `linkedin.com/in/`) |

Authorship is decided by parsing Exa's `**Name**: Role at Company for N years` byline. `_same_person`
tolerates abbreviated surnames ("AJ K." vs "AJ Khanijow"). A `VOICE_BONUS` of 1.25 promotes a
third-party piece that *quotes* the prospect (requires a 40+ char quoted span introduced by a
speech verb) — capped so it can never beat `authored`.

**4b. Guardrails** — `never_reference` term matching over `claim + snippet[:500]`. Eight topics:
layoffs, bereavement, illness, litigation, discrimination, regulatory action, forced departure,
data breach. Strict mode excludes; permissive downweights. Plus a namesake check
(`_company_is_mentioned`) that multiplies score by `NAMESAKE_PENALTY = 0.35` and, in strict mode,
makes the card unwinnable.

**4c. The cap** — cards are pre-scored on `proximity × recency` and cut to `card_cap = 10`, with
`recency_reserve = 3` slots held for the freshest *dated* cards regardless of proximity.

**4d. Pain scoring** — one LLM call. All ≤10 surviving cards in one prompt, scored 0.0–1.0
against the five pains in `value_prop.yaml` by their `observable_via` lines, with a ≤15-word
justification each. No match → `general_news` at 0.3 (strict) or 0.4 (permissive).

**4e. Relevance** — `pain_score × proximity_multiplier × recency_multiplier`, a **product**, not a
sort tuple. Recency multipliers: ≤180d = 1.0, ≤365d = 0.95, ≤730d = 0.85, older = 0.75,
**undated = 0.8** — deliberately below known-and-old, because not knowing is worse than knowing
something inconvenient.

**How it's doing.** This is the best-engineered part of the product and it is where the thesis
actually lives. Nearly every line has a real incident behind it. Two caveats: it is reading
uncleaned snippets (§12.2), and its sophistication now considerably exceeds the quality of what
retrieval hands it — tuning here has diminishing returns until §1 improves.

**Your decisions.**
1. **The pain set.** Five pains, each with 3–4 `observable_via` lines, all rewritten after job
   postings were cut. Everything the ranker can possibly find is defined by these lines — this is
   the highest-leverage config in the repo and it deserves the same treatment you are giving search.
2. **The weights.** `authored 4 / attributed 3 / colleague 2.5 / company 2 / database 1`, recency
   multipliers, `VOICE_BONUS 1.25`, `NAMESAKE_PENALTY 0.35`, `card_cap 10`, `recency_reserve 3`,
   `hook_shortlist 4`, `THIN_SIGNAL_FLOOR 0.35`. All arrived at by hand against a handful of runs.
3. **The `general_news` floor** (0.3/0.4) — it decides how often a prospect degrades to a
   company-tier email.
4. **Whether one LLM call should score all cards at once.** Cheap, but cards are scored in each
   other's company, which is not obviously neutral.

---

## 5. Hook articulation — `ranker.py:848`

One LLM call over the top 4 cards. Each returns `hook_text` (the fact to lead with), `rationale`
(why it matters to this person), `bridge` (how it connects to the offer), `strength` (0–1). Each
card is labelled with its age and the prompt forbids calling anything recent unless it is under
six months old.

**How it's doing.** The prompt is good. **The output mostly does not reach the drafter** — see
§12.1, the single most consequential defect in this audit.

**Your decision.** Whether hooks are options for the human (Compass IX — "options, not verdicts")
or an input to the machine, or both. Today the UI renders all of them and the drafter gets one,
unreliably.

---

## 6. Winner selection — `ranker.py:433`

Deterministic. `final = relevance × (0.5 + 0.5 × hook_strength)`, so hook strength modulates
between 0.5× and 1.0× and can reorder near-ties without dominating. Then the Compass VI swap
test: one hook per kind, and identical hook text is definitionally the same kind. Then a
tiebreak preferring dated evidence when an undated card wins by less than
`dated_preference_margin = 0.15`.

**How it's doing.** Sound, well-tested, honest about its two index spaces. No changes indicated.

---

## 7. Drafting — `zara/drafter.py`, 661 lines

**What it does.** One email as an explicit syllogism: hook (evidence) → pain (inference) → offer.
Four moves, 70–110 words, first name only, no em dashes, self-introduction from `sender_company`,
one soft question to close.

**How.** The prompt carries: the recipient, the evidence, its **age in days**, an
`attribution_line` that differs per proximity tier (the `person_authored` branch is the strict
one — engage with their point, never reproduce their wording, never report the fact that they
said it), the pain statement, what made us think so, the offer, the ask, plus `_STYLE_RULES`
shared by both the hooked and no-signal paths.

Retry ladder: format violation → rewrite; repetition collision → up to 2 rewrites; verifier
grounding failure → 1 self-correction pass. Worst case 4 drafter calls in a run.

**How it's doing.** Four commits of hard-won work sit here and the voice is now yours rather than
the model's. Two live constraints: it gets the *cleaned* winning snippet (good) but usually
without the articulated hook (§12.1), and the sender identity is only partly configurable —
`sender_name` and `sender_company` are UI fields, `sender_person` is config-only, which
contradicts your own ruling that the sender profile is an app feature.

**Your decisions.** The voice itself (you already wrote the reference emails by hand — that is
the spec); the word budget; whether "I read your post" stays restricted to `person_authored`;
and how much the retry ladder is allowed to spend.

---

## 8. Anti-template — `zara/antitemplate.py`

Compares drafts in a batch on shared 4-word runs. Phrasing supplied by the offer, CTA, pain
statements, the prospect's own evidence, and the dictated house scaffolding is excluded, so only
phrasing the *writer* chose can count as repetition. A collision routes into the format-rewrite
path — never blocks, never reported as fabrication.

**How it's doing.** Correct, and now live in the app (a `st.session_state` batch spans runs in a
sitting). Only fires when you draft more than one prospect in a session.

---

## 9. Verification — `zara/verifier.py`

Four checks, in order, then a judge:

1. **`check_attribution`** — blocks second-person claims ("I saw you said…") when proximity is not
   `authored`. Catches the failure token-grounding structurally cannot: the draft never names the
   real speaker, so there is no ungrounded token.
2. **`check_recency`** — blocks a time claim ("recently", "new CFO", "just announced") when the
   winning card is undated or older than `stale_days = 180`.
3. **`pass1_grounding`** — deterministic. Extracts numbers, URLs, quoted strings and multi-word
   proper nouns from the draft, normalizes, and requires each to appear in the evidence list.
   Durations are stripped first ("15 minutes" is the writer's choice, not a claim). The subject
   line is excluded from proper-noun extraction (Title Case is house style, not assertion).
   Sender names are read from config so a sender can say its own name.
4. **`check_format`** — 60–120 words. Rewrites, never blocks.
5. **`pass2_llm_judge`** — one call. Flags only invented metrics, invented customer names,
   fabricated quotes, or specific claims about this prospect no snippet supports. Explicitly told
   the sender's value proposition and ordinary connective language are not fabrication.

**How it's doing.** This is the strongest component and the one you have ruled must never be
softened. It has caught real failures repeatedly, including drafts that were factually true about
the wrong company. Its known cost is false positives on a shrinking list of edge cases.

**Your decision.** Only whether the judge's model should differ from the drafter's. Everything
else here is settled policy.

---

## 10. Presentation — `app.py`, `zara/ui/`

Streamlit, one prospect per run. Surfaces: the draft; **Draft with sources** (each sentence cited
back to the card it came from, deterministic, so a citation cannot be invented — sentences with
no marker are *ours*, and that distinction is the point); why this hook won; hook options with
strength and age; **What it rejected** (every card, with reason, as clickable links); the full
14-row source table with `ok`/`empty`/`failed`/`skipped` and a reason each; budget meter;
Developer Mode behind a password gate with four settings tabs.

**How it's doing.** The decision card is the product's actual argument and it renders it well.
The dead `Proof Point` control is the one blemish (strict mode ignores it, and strict is
hardcoded).

**Your decision.** Whether one-prospect-at-a-time is the shape, or whether a list/queue is. That
choice changes the anti-template stage, the budget model, and the whole UI.

---

## 11. Model & infrastructure layer

**Providers.** Groq `openai/gpt-oss-120b` → Gemini → Z.ai GLM `glm-4.5-flash`, `temperature=0.0`
throughout, structured output against Pydantic schemas. Groq keys are pooled round-robin
(`GROQ_API_KEY`, `_2..10`) so the per-minute bucket stops binding and a 429 moves to the next key.
Per-run deadline 180s. Circuit breakers per provider. Full telemetry: every card, prompt, and
model call recorded to SQLite.

**Budget.** `$4.00` month-to-date cap on Apify, checked before each paid rung. Groq quota metered
off the response headers, labelled `measured` vs `estimate` — a freshly booted container says
"≈N runs per full day of quota" rather than "N runs left", because a projection is not a balance.

**Fixtures.** Prompt-hash-keyed. 126 tests, zero live calls, `ZARA_NOW` pins the clock so card
ages don't drift the hashes. `ZARA_LIVE_STAGES` lets you iterate one stage live against frozen
upstream output.

**How it's doing.** Genuinely good infrastructure — better than the product it currently serves.
Two notes: `GEMINI_MODEL = "gemini-2.5-flash"` contradicts your own recorded finding that this
model is retired for new users (§12.6), and the ~45s rate-limit stall that explains the gap from
the old p50 of 5.7s has not been re-measured since key pooling landed.

**Your decision.** Model choice per stage. Right now one model does ranking, hooks, drafting,
classification and judging. These are different jobs — scoring wants cheap and consistent,
drafting wants good, judging wants adversarial and ideally not the same model that wrote it.

---

## 12. Defects found in this audit — RESOLVED except 12.5

| # | defect | outcome |
|---|---|---|
| 12.1 | articulated hook never reached the drafter | **fixed** `21889cd` — and it was worse than described: on the ShipBob snapshot the winning card sat at index 0 and hook `card_index` values were `[3,0,3]`, so the lookup *found* a hook belonging to a different card. Both failure modes were live. |
| 12.2 | pain scorer read uncleaned snippets | **fixed** `21889cd` |
| 12.3 | domain resolution never fired | **fixed** `9c57d72` — and it was **two** bugs stacked. Removing the suffix gate was necessary and insufficient; underneath, `max_results: 3` returned only aggregator profiles (preqin, builtin, linkedin for Episode Six), none containing the company token. At n=8 both Episode Six and ShipMonk resolve. |
| 12.4 | YouTube transcript code dead | **fixed** `9c57d72` — dead twice: frozen dataclass *and* `get_transcript` absent from youtube-transcript-api 1.2.4 |
| 12.5 | ICP fit always `unknown` | **open, deferred by the human.** Needs a ruling on where firmographics come from. |
| 12.6 | Gemini fallback names a retired model | **WITHDRAWN — this was wrong.** `gemini-2.5-flash` returns 200 against the exact endpoint and auth `provider.py` uses. The code was right; `CLAUDE.md` carried the wrong fact and has been corrected. |
| 12.7 | TLS verification disabled | **fixed** `9c57d72` |
| 12.8 | unreachable early-exit branch | **fixed** `9c57d72` |
| 12.9 | Tavily cost invisible | **fixed** `9c57d72` — $0.0075/query |

### Found after the audit, while fixing the above

- **The namesake guard let an industry word identify a company** (`f3dafd6`). The
  single-token path was hardened after the C.H. Robinson incident; the multi-token
  path was left as `any()`, so "Northwind Freight" was identified by the word
  *freight* alone. Live retrieval against a company that does not exist returned 21
  cards and **20 passed the check**. That would have destroyed the no-signal demo
  beat. Now requires every significant token: 20 survivors down to 1, and that one
  is a real Northwind Freight Systems in Ontario.
- **Own-appointment guardrail** (`fe85c84`). Pitching someone their own hire scored
  `person_authored` with a clean verification on a live run — the strongest claim
  tier on the weakest reason to write. Cannot live in `never_reference`, because
  appointments are a legitimate observable; what makes it unusable is *relational*.
- **`USE_FIXTURES=fill` could not reach three test modules** (`21889cd`). Each
  hardcoded `USE_FIXTURES=1`, clobbering it, so the documented re-record procedure
  raised instead of recording and the only way through was fixtures-off — the
  footgun that costs a day of Groq budget.
- **`apify.py` writes a fixture after every successful live actor call**,
  unconditionally. Any live run silently rewrites the recorded Apify corpus. Same
  family as the fixtures-off footgun. **Not fixed.**

### Original write-ups

Ordered by how much they cost you.

**12.1 — The articulated hook usually never reaches the drafter.** `zara/s2.py:122` looks up the
winning hook by matching `HookProposal.card_index` against a position in `ranked_prospect.cards`.
But `card_index` indexes the **shortlist** (relevance-sorted top 4); `cards` is every card in
original retrieval order. Two different index spaces — the exact confusion `_select_winner`'s
docstring at `ranker.py:440` was written to prevent, committed in the one place that docstring
does not guard. Result: `hook` is usually `None`, so the drafter falls to the `else` branch at
`drafter.py:396` and loses both `hook.hook_text` (the specific fact chosen to lead with) and
`hook.rationale` (`WHY IT MATTERS`). When the indices *do* collide, it silently attaches a hook
belonging to a different card. A paid LLM call, discarded on most runs — and a plausible share of
the "the drafter picked the wrong thing to say" complaints.

**12.2 — The pain scorer reads uncleaned snippets.** `ranker.py:709` sends `card.snippet[:500]`
raw. `4f8bc46` fixed exactly this for the drafter and the hook prompt but left the *scoring*
stage — the one that decides which cards survive — reading the header-and-bio furniture.
For a LinkedIn card that is ~290 of the 500 characters. The guardrail matcher (`:580`) and
`_company_is_mentioned` (`:358`) read raw too, so both are matching against boilerplate.

**12.3 — Company domain resolution almost never fires.** `resolve.py:68` gates the lookup on
`normalized != raw_company.strip()`, true only when a corporate suffix was stripped. Any company
typed without one — most of them — gets `domain=None`, which disables `ExaBlogFetcher` entirely
and drops Jina to guessing four domain spellings.

**12.4 — YouTube transcript enrichment is dead code.** `exa.py:134` does `card.snippet = text[...]`
on `SignalCard`, which is `@dataclass(frozen=True)`. Every execution raises `FrozenInstanceError`
into the bare `except Exception: pass` on the next line. No transcript has ever reached a card.

**12.5 — ICP fit is effectively always `unknown`.** Headcount is parsed by regex for the literal
string `headcount: N`, which only `ApifyBaseFetcher._firmographic_snippet` ever emits — and Apify
rung 2 is skipped whenever the gap-filler gate closes. So on good prospects, ICP is blank.

**12.6 — The Gemini fallback names a retired model.** `provider.py:17` is `gemini-2.5-flash`,
commented "verified callable 2026-08-24"; `CLAUDE.md` records `gemini-2.5-flash` as retired for
new users and `gemini-flash-latest` as the working id. One of the two is wrong, and the failure
mode is a fallback that only fails when you need it.

**12.7 — Google News runs with TLS verification off.** `news.py:39`, `verify=False`. Almost
certainly a leftover from the documented macOS SSL problem, for which the documented fix is
`httpx` — which this already uses.

**12.8 — The ranker's early-exit branch is unreachable.** `chunk_size = max(len(to_score), 1)`
means there is only ever one chunk, so the `found_strong_hook` break at `:757` and its
"skipped due to early exit" labelling can never run.

**12.9 — Tavily's cost accounting is inconsistent.** `sources.yaml` types it `paid_api`; the
fetcher hardcodes `cost_usd=0.0` and sits in the free rung, metering itself through a separate
credit counter. So Tavily spend never appears in the run cost shown on the decision card.

---

## 13. Still open from the previous backlog

`POST /pipeline/run` is a stub; run history dies on restart when deployed; the five
Groq keys are still owed a rotation; Streamlit Cloud secrets are behind; the dead
`Proof Point` control; `sender_person` not editable in the UI; `DEMO-PLAN.md` §8.4
stale. **Closed since:** the own-hire guardrail.

---

## 14. Research order — updated

1. ~~**Search & retrieval**~~ — **done.** Bake-off measured both providers through the
   real ranker functions rather than their docs. Parallel Search leads rung 1
   (`cd082d9`): 56% person-tier density against Brave's 19%, and one request carries
   the whole three-angle plan at $0.001 where Brave bills per query ($0.015 for the
   same plan). Brave stays registered in `sources.yaml`, unwired, with its reason —
   it dates 87% of its cards against Parallel's 60%. Query vocabulary moved out of
   Python into `value_prop.retrieval.search_terms`.
2. ~~**Entity resolution**~~ — **done** as part of 12.3, though the resolver is still
   a Tavily search with a regex match. It works for the cases tested; it has not been
   designed.
3. ~~**The pain set**~~ — **done** (`0bb64fe`). Measurement said 77% of all evidence
   matched no pain, and everything scoring ≥0.70 was a press release while everything
   a person *said* failed. Each pain now accepts a **category argument** — the
   prospect arguing publicly about a limitation, whether or not they claim it of
   their own company. Person-tier cards matching a real pain went **14% → 43%** live.

### 4. Read page bodies — the new top priority

The pain-set work exposed the next constraint, and it is not the pain set. On the
live ShipMonk run the CFO Weekly podcast cards *still* scored `general_news`,
because their snippets are **138 characters of show description**; one `authored`
card held **1,500 characters of LinkedIn cookie-consent boilerplate**. There is no
argument in those cards to credit.

We retrieve the listing page, never the thing the person said. Nothing in the
pipeline follows a link. Parallel Extract is $0.001/URL and was measured working
during the bake-off. **Until this lands, person-tier evidence keeps losing to press
releases, which carry their content inline.** Weights (below) should not be tuned
before it, or they are tuned against a distribution about to change.

5. **Model assignment per stage.** One model does ranking, hooks, drafting,
   classification and judging — five different jobs.
6. **Weights and thresholds.** After item 4, not before.
7. **Product shape.** One prospect at a time, or a list.
8. **12.5, ICP fit.** Needs a ruling on where firmographics come from.

---

## Measured baselines, for comparison after the next change

From `var/zara_runs.db` (38 runs, 238 scored cards) and the live runs of 2026-09-02.

| metric | value |
|---|---|
| `general_news` share of scored cards (pre-fix) | 76.9% |
| person-tier cards matching a real pain | 14% → **43%** live after `0bb64fe` |
| winners by proximity (pre-fix) | 61% `company_action`, 25% `authored` |
| snapshot corpus proximity mix | 68% `company_action`, **4.4% `authored`** |
| retrieval, 3 demo prospects | incumbent 58 cards / 45% dated / 9 directory rows |
| | Parallel 25 / 60% / **1** · Brave 54 / **87%** / 3 |
| end-to-end live run | ~31s, ~$0.005 |

**The snapshot corpus cannot test the person tier** — 4.4% `authored`, recorded
against a placeholder name before the retrieval work. Any person-tier claim must be
measured on a live run, not on snapshots.

---

## Verification

Any change: `env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONPATH=. ./venv/bin/pytest tests/ -q` —
126 pass, twice consecutively, zero live calls. Then replay Chermaine Hu / Episode Six,
Devin Weil / ShipMonk, Riley Chen / Northwind Freight in demo mode and confirm
`provider='fixture'` throughout. Any change touching a prompt in ranker/drafter/verifier/
classifier invalidates fixture hashes — re-record with `USE_FIXTURES=fill`, never with
fixtures off.
