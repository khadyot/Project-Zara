"""Per-run trace: what happened, how long it took, what it cost, and *why the
pipeline chose what it chose*.

Design notes
------------
* The active trace lives in a ContextVar, mirroring the `_deadline` pattern in
  `provider.py`. Call sites do not pass a trace around.
* **When no trace is active every method is a no-op.** Tests, fixture replay and
  `record_mock.py` therefore behave exactly as before.
* Recording must never break a run. Every public method swallows its own errors;
  losing a log line is always preferable to losing the draft.
* The store is SQLite because we compare runs across days, not because the data
  is large. `stress_log.jsonl` stays as-is for grep-ability.

The `cards` table is the point of the whole thing: it keeps every candidate the
ranker saw, its pain match and score, and the reason each losing card was
excluded -- so "what else could it have led with?" is answerable after the fact.
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import sqlite3
import subprocess
import time
import uuid

DB_PATH = os.environ.get("ZARA_RUN_DB") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "var", "zara_runs.db",
)

_current: contextvars.ContextVar["RunTrace | None"] = contextvars.ContextVar(
    "zara_run_trace", default=None
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, ts TEXT, trigger TEXT, duration_ms INTEGER,
  person_name TEXT, company TEXT, title TEXT, domain TEXT, linkedin TEXT,
  category TEXT, profile TEXT,
  outcome TEXT, error TEXT, traceback TEXT,
  claim_strength TEXT, icp_fit TEXT, icp_notes TEXT, signal_quality TEXT,
  cards_total INTEGER, cards_eligible INTEGER, hooks_count INTEGER,
  winning_card TEXT, verification_status TEXT, verification_passed INTEGER,
  verification_reason TEXT, self_corrected INTEGER,
  verification_failed_pass TEXT, first_pass_hallucinations TEXT,
  subject TEXT, draft_text TEXT, draft_words INTEGER,
  prompt_tokens INTEGER, completion_tokens INTEGER, llm_calls INTEGER,
  source_cost_usd REAL,
  git_sha TEXT, code_dirty INTEGER, value_prop_sha TEXT, groq_model TEXT
);
CREATE TABLE IF NOT EXISTS llm_calls (
  run_id TEXT, seq INTEGER, stage TEXT, provider TEXT, model TEXT,
  attempt INTEGER, status TEXT, elapsed_ms INTEGER,
  prompt_tokens INTEGER, completion_tokens INTEGER,
  prompt_chars INTEGER, error TEXT,
  system_text TEXT, prompt_text TEXT, response_text TEXT
);
CREATE TABLE IF NOT EXISTS source_calls (
  run_id TEXT, seq INTEGER, source TEXT, rung INTEGER, status TEXT,
  reason TEXT, cards INTEGER, cost_usd REAL, elapsed_ms INTEGER
);
CREATE TABLE IF NOT EXISTS cards (
  run_id TEXT, seq INTEGER, source TEXT, tier TEXT, signal_type TEXT,
  claim TEXT, snippet TEXT, source_url TEXT, published_date TEXT,
  proximity TEXT, attributed_to TEXT, recency_days INTEGER,
  pain_id TEXT, pain_score REAL, pain_reason TEXT, score REAL,
  excluded TEXT, guardrail_hit TEXT, is_winner INTEGER
);
CREATE TABLE IF NOT EXISTS hooks (
  run_id TEXT, seq INTEGER, card_index INTEGER, strength REAL,
  hook_text TEXT, rationale TEXT, bridge TEXT
);
CREATE TABLE IF NOT EXISTS stages (
  run_id TEXT, seq INTEGER, stage TEXT, elapsed_ms INTEGER
);
CREATE TABLE IF NOT EXISTS events (
  run_id TEXT, seq INTEGER, offset_ms INTEGER, type TEXT,
  name TEXT, status TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS usage (
  ts TEXT,
  provider TEXT,
  model TEXT,
  stage TEXT,
  context TEXT,
  run_id TEXT,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  status TEXT,
  http_status INTEGER,
  elapsed_ms INTEGER,
  wait_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_runs_ts ON runs(ts);
CREATE INDEX IF NOT EXISTS idx_llm_run ON llm_calls(run_id);
CREATE INDEX IF NOT EXISTS idx_cards_run ON cards(run_id);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage(ts);
CREATE INDEX IF NOT EXISTS idx_usage_provider ON usage(provider);
"""


SEED_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "seed", "zara_runs_demo.db")


def _restore_seed(path: str) -> None:
    """First run on a fresh filesystem gets the demo history, not an empty page.

    The run store lives under var/, which is gitignored, and a hosted deploy has
    an ephemeral filesystem -- so without this the Run History dashboard is blank
    on the deployed URL until someone happens to run a prospect.

    Seeding is a deployment bootstrap, not a property of the store, so it is
    opt-out: set ZARA_SEED_DEMO=0 for a store that must start genuinely empty.
    The tests do exactly that -- an implicitly pre-populated "fresh" store made
    three of them assert against rows they had not written.

    A store that already exists is never overwritten.
    """
    if os.environ.get("ZARA_SEED_DEMO", "1") != "1":
        return
    if os.path.exists(path) or not os.path.exists(SEED_DB):
        return
    try:
        import shutil
        shutil.copyfile(SEED_DB, path)
    except OSError:
        pass   # a missing seed is cosmetic; never let it stop a run


def connect(path: str = None) -> sqlite3.Connection:
    path = path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _restore_seed(path)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def _fingerprint() -> dict:
    """Git SHA plus a digest of uncommitted changes.

    Comparing commit SHAs alone is not enough: most iteration happens in the
    working tree. Without this field a code change is indistinguishable from
    model variance -- which is exactly how HANDOFF §8 concluded the verifier was
    non-deterministic when in fact a fix had landed between the two runs.
    """
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    def _git(*args):
        try:
            return subprocess.run(["git", "-C", root, *args], capture_output=True,
                                  text=True, timeout=5).stdout.strip()
        except Exception:
            return ""
    sha = _git("rev-parse", "--short", "HEAD") or "unknown"
    diff = _git("diff", "HEAD")
    vp_sha = ""
    try:
        with open(os.path.join(root, "value_prop.yaml"), "rb") as f:
            vp_sha = hashlib.sha256(f.read()).hexdigest()[:12]
    except Exception:
        pass
    from zara.utils.provider import GROQ_MODEL
    return {
        "git_sha": sha + (("+wip." + hashlib.sha1(diff.encode()).hexdigest()[:8]) if diff else ""),
        "code_dirty": 1 if diff else 0,
        "value_prop_sha": vp_sha,
        "groq_model": GROQ_MODEL,
    }


class RunTrace:
    def __init__(self, prospect=None, trigger="ui", profile="standard", category=None):
        self.run_id = uuid.uuid4().hex[:12]
        self.t0 = time.monotonic()
        self.ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.trigger, self.profile, self.category = trigger, profile, category
        self.prospect = prospect
        self.llm: list[dict] = []
        self.sources: list[dict] = []
        self.cards: list[dict] = []
        self.hooks: list[dict] = []
        self.stage_times: list[dict] = []
        self.events: list[dict] = []
        self.outcome, self.error, self.traceback = "ok", None, None
        self.subject = None
        self.draft_text = None
        self.result = {}

    # -- recording -----------------------------------------------------------
    def llm_call(self, **kw):
        try:
            kw["seq"] = len(self.llm)
            self.llm.append(kw)
        except Exception:
            pass

    def event(self, e: dict):
        try:
            self.events.append({
                "seq": len(self.events),
                "offset_ms": int((time.monotonic() - self.t0) * 1000),
                "type": e.get("type"), "name": e.get("name"),
                "status": e.get("status"), "detail": str(e.get("detail") or "")[:300],
            })
        except Exception:
            pass

    @contextlib.contextmanager
    def stage(self, name: str):
        t = time.monotonic()
        try:
            yield
        finally:
            try:
                self.stage_times.append({
                    "seq": len(self.stage_times), "stage": name,
                    "elapsed_ms": int((time.monotonic() - t) * 1000),
                })
            except Exception:
                pass

    def capture_sources(self, results):
        try:
            self.sources = [{
                "seq": i, "source": r.source, "rung": r.rung, "status": r.status,
                "reason": (r.reason or "")[:400], "cards": len(r.cards),
                "cost_usd": r.cost_usd, "elapsed_ms": r.elapsed_ms,
            } for i, r in enumerate(results)]
        except Exception:
            pass

    def capture_ranked(self, rp):
        """Every candidate, not just the winner -- this is the decision path."""
        try:
            win = rp.winning_card
            self.cards = []
            for i, c in enumerate(rp.cards):
                pm = c.pain_match
                self.cards.append({
                    "seq": i, "source": c.card.source, "tier": c.card.tier,
                    "signal_type": c.card.signal_type, "claim": c.card.claim,
                    "snippet": (c.card.snippet or "")[:1500],
                    "source_url": c.card.source_url,
                    "published_date": c.card.published_date,
                    "proximity": c.proximity, "attributed_to": c.attributed_to,
                    "recency_days": c.recency_days,
                    "pain_id": pm.pain_id if pm else None,
                    "pain_score": pm.score if pm else None,
                    "pain_reason": pm.reason if pm else None,
                    "score": c.score, "excluded": c.excluded,
                    "guardrail_hit": c.guardrail_hit,
                    "is_winner": 1 if (win is not None and c is win) else 0,
                })
            self.hooks = [{
                "seq": i, "card_index": h.card_index, "strength": h.strength,
                "hook_text": h.hook_text, "rationale": h.rationale, "bridge": h.bridge,
            } for i, h in enumerate(rp.hooks or [])]
            self.result.update({
                "icp_fit": rp.icp_fit,
                "icp_notes": json.dumps(list(rp.icp_notes or [])),
                "signal_quality": getattr(rp, "signal_quality", "ok"),
                "cards_total": len(rp.cards),
                "cards_eligible": sum(1 for c in rp.cards if c.excluded is None),
                "hooks_count": len(rp.hooks or []),
                "winning_card": json.dumps({
                    "claim": win.card.claim, "source": win.card.source,
                    "url": win.card.source_url, "proximity": win.proximity,
                    "attributed_to": win.attributed_to, "score": win.score,
                    "pain": win.pain_match.pain_id if win.pain_match else None,
                    "recency_days": win.recency_days,
                }) if win else None,
            })
        except Exception:
            pass

    def capture_draft(self, draft):
        try:
            if draft is None:
                return
            self.draft_text = draft.draft_text
            self.subject = getattr(draft, "subject", None)
            self.result["claim_strength"] = draft.claim_strength
            self.result["draft_words"] = len((draft.draft_text or "").split())
            v = draft.verification
            if v:
                # Which gate failed decides the fix: an ungrounded token means the
                # drafter invented something, an attribution hit means we implied the
                # wrong person said it, and a judge block with neither means the LLM
                # disagreed about evidence it *was* shown. Opposite remedies, so the
                # truncated reason string is not enough to tell them apart.
                fp = list(v.first_pass_hallucinations or [])
                failed_pass = None
                if not v.passed:
                    if any(str(x).startswith("misattribution:") for x in fp):
                        failed_pass = "attribution"
                    elif fp:
                        failed_pass = "grounding"
                    elif v.status == "could_not_run":
                        failed_pass = "could_not_run"
                    else:
                        failed_pass = "llm_judge"
                self.result.update({
                    "verification_status": v.status,
                    "verification_passed": 1 if v.passed else 0,
                    "verification_reason": (v.reason or "")[:1000],
                    "self_corrected": 1 if v.self_corrected else 0,
                    "verification_failed_pass": failed_pass,
                    "first_pass_hallucinations": json.dumps(fp) if fp else None,
                })
            if getattr(draft, "ranked_prospect", None) is not None:
                self.capture_ranked(draft.ranked_prospect)
        except Exception:
            pass

    def fail(self, exc, tb=None):
        self.outcome, self.error = "crash", f"{type(exc).__name__}: {exc}"
        self.traceback = (tb or "")[-4000:]

    # -- persistence ---------------------------------------------------------
    def save(self) -> str | None:
        try:
            p = self.prospect
            row = {
                "run_id": self.run_id, "ts": self.ts, "trigger": self.trigger,
                "duration_ms": int((time.monotonic() - self.t0) * 1000),
                "person_name": getattr(p, "person_name", None),
                "company": getattr(p, "company", None),
                "title": getattr(p, "title", None),
                "domain": getattr(p, "company_domain", None),
                "linkedin": getattr(p, "linkedin_url", None),
                "category": self.category, "profile": self.profile,
                "outcome": self.outcome, "error": self.error, "traceback": self.traceback,
                "subject": self.subject,
                "draft_text": self.draft_text,
                "prompt_tokens": sum(c.get("prompt_tokens") or 0 for c in self.llm),
                "completion_tokens": sum(c.get("completion_tokens") or 0 for c in self.llm),
                "llm_calls": len(self.llm),
                "source_cost_usd": round(sum(s.get("cost_usd") or 0 for s in self.sources), 6),
                **_fingerprint(),
                **self.result,
            }
            cols = [c[1] for c in connect().execute("PRAGMA table_info(runs)")]
            row = {k: v for k, v in row.items() if k in cols}
            with connect() as conn:
                conn.execute(
                    f"INSERT OR REPLACE INTO runs ({','.join(row)}) "
                    f"VALUES ({','.join('?' * len(row))})", list(row.values()))
                for table, rows in (("llm_calls", self.llm), ("source_calls", self.sources),
                                    ("cards", self.cards), ("hooks", self.hooks),
                                    ("stages", self.stage_times), ("events", self.events)):
                    if not rows:
                        continue
                    valid = [c[1] for c in conn.execute(f"PRAGMA table_info({table})")]
                    for r in rows:
                        r = {k: v for k, v in r.items() if k in valid}
                        r["run_id"] = self.run_id
                        conn.execute(
                            f"INSERT INTO {table} ({','.join(r)}) "
                            f"VALUES ({','.join('?' * len(r))})", list(r.values()))
            return self.run_id
        except Exception as e:  # never let logging kill a run
            print(f"[telemetry] save failed: {type(e).__name__}: {e}")
            return None


def current() -> "RunTrace | None":
    return _current.get()


@contextlib.contextmanager
def trace_run(prospect=None, trigger="ui", profile="standard", category=None):
    """Open a trace for one pipeline run. Saves on success *and* on exception --
    crashes are the runs most worth having."""
    import traceback as _tb
    t = RunTrace(prospect, trigger=trigger, profile=profile, category=category)
    token = _current.set(t)
    try:
        yield t
    except BaseException as e:
        t.fail(e, _tb.format_exc())
        raise
    finally:
        _current.reset(token)
        t.save()
