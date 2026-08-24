"""Read the run store.

    scripts/runlog.py                 # recent runs
    scripts/runlog.py --run <id>      # the full decision path for one run
    scripts/runlog.py --last          # decision path for the most recent run
    scripts/runlog.py --diff a b      # what changed between two runs
    scripts/runlog.py --failures      # crashes and blocked verifications
    scripts/runlog.py --summary       # aggregates by category / claim strength

Output is deliberately compact: this gets read a lot.
"""
import argparse, json, sys, textwrap
sys.path.insert(0, ".")
from zara.utils.telemetry import connect


def _rows(conn, q, *a):
    return [dict(r) for r in conn.execute(q, a)]


def _fmt_tokens(n):
    return f"{n/1000:.1f}k" if n and n >= 1000 else str(n or 0)


def list_runs(conn, limit):
    rs = _rows(conn, "SELECT * FROM runs ORDER BY ts DESC, rowid DESC LIMIT ?", limit)
    if not rs:
        print("no runs recorded yet")
        return
    print(f"{'run':<13}{'when':<20}{'who':<34}{'time':>7}{'tok':>7}  {'strength':<18}{'verifier':<22}fingerprint")
    print("-" * 145)
    for r in rs:
        who = f"{r['person_name'] or '?'} @ {r['company'] or '?'}"[:32]
        v = r["verification_status"] or ("CRASH" if r["outcome"] == "crash" else "-")
        if r["self_corrected"]:
            v += " (corrected)"
        tok = (r["prompt_tokens"] or 0) + (r["completion_tokens"] or 0)
        print(f"{r['run_id']:<13}{(r['ts'] or '')[5:16]:<20}{who:<34}"
              f"{(r['duration_ms'] or 0)/1000:>6.1f}s{_fmt_tokens(tok):>7}  "
              f"{(r['claim_strength'] or '-'):<18}{v:<22}{r['git_sha'] or '?'}")


def show_run(conn, run_id):
    r = _rows(conn, "SELECT * FROM runs WHERE run_id LIKE ?", run_id + "%")
    if not r:
        print(f"no run matching {run_id}")
        return
    r = r[0]
    rid = r["run_id"]
    w = 100

    print("=" * w)
    print(f"  {r['person_name']} · {r['title'] or 'title not given'} · {r['company']}")
    print(f"  run {rid} · {r['ts']} · trigger={r['trigger']} · profile={r['profile']}")
    print(f"  code {r['git_sha']} · value_prop {r['value_prop_sha']} · model {r['groq_model']}")
    print("=" * w)

    if r["outcome"] == "crash":
        print(f"\nCRASHED: {r['error']}\n")
        if r["traceback"]:
            print(textwrap.indent(r["traceback"][-1500:], "  "))

    # -- timing and spend
    print(f"\n── COST ──")
    print(f"  wall {(r['duration_ms'] or 0)/1000:.1f}s · "
          f"{r['llm_calls'] or 0} model calls · "
          f"{_fmt_tokens(r['prompt_tokens'])} in / {_fmt_tokens(r['completion_tokens'])} out · "
          f"sources ${r['source_cost_usd'] or 0:.4f}")
    for s in _rows(conn, "SELECT * FROM stages WHERE run_id=? ORDER BY seq", rid):
        print(f"    {s['stage']:<22}{s['elapsed_ms']/1000:>7.1f}s")

    print(f"\n── MODEL CALLS ──")
    calls = _rows(conn, "SELECT * FROM llm_calls WHERE run_id=? ORDER BY seq", rid)
    if not calls:
        print("  none recorded")
    for c in calls:
        att = f" attempt {c['attempt']}" if (c["attempt"] or 1) > 1 else ""
        print(f"  {c['stage']:<24}{c['provider']:<8}"
              f"{_fmt_tokens(c['prompt_tokens']):>7} in {_fmt_tokens(c['completion_tokens']):>7} out"
              f"{c['elapsed_ms']/1000:>7.1f}s{att}")

    # -- retrieval
    print(f"\n── SOURCES ──")
    srcs = _rows(conn, "SELECT * FROM source_calls WHERE run_id=? ORDER BY seq", rid)
    by = {}
    for s in srcs:
        by.setdefault(s["status"], []).append(s)
    for status in ("ok", "empty", "failed", "skipped"):
        got = by.get(status, [])
        if not got:
            continue
        print(f"  {status} ({len(got)}):")
        for s in got:
            extra = f" — {s['reason'][:70]}" if s["reason"] and status != "ok" else ""
            cards = f"{s['cards']} cards" if status == "ok" else ""
            print(f"    {s['source']:<32}{s['elapsed_ms']/1000:>6.1f}s  {cards}{extra}")

    # -- the decision path
    print(f"\n── WHAT IT CONSIDERED ──   ({r['cards_total'] or 0} cards, {r['cards_eligible'] or 0} eligible)")
    cards = _rows(conn, "SELECT * FROM cards WHERE run_id=? ORDER BY is_winner DESC, score DESC", rid)
    for c in cards:
        mark = ">>" if c["is_winner"] else ("  " if c["excluded"] is None else "xx")
        print(f"\n {mark} [{c['score'] or 0:.2f}] {c['proximity']:<18} {c['source']} · {c['tier']}")
        print(f"      {(c['claim'] or '')[:110]}")
        if c["pain_id"]:
            print(f"      pain: {c['pain_id']} ({c['pain_score']:.2f}) — {(c['pain_reason'] or '')[:90]}")
        if c["attributed_to"]:
            print(f"      ATTRIBUTED TO: {c['attributed_to']}   <- not the prospect")
        if c["excluded"]:
            print(f"      excluded: {c['excluded']}")
        if c["guardrail_hit"]:
            print(f"      guardrail: {c['guardrail_hit']}")
        if c["source_url"]:
            print(f"      {c['source_url'][:110]}")

    hooks = _rows(conn, "SELECT * FROM hooks WHERE run_id=? ORDER BY strength DESC", rid)
    print(f"\n── HOOK OPTIONS ──   ({len(hooks)})")
    for h in hooks:
        print(f"  [{h['strength']:.2f}] {h['hook_text']}")
        print(f"         why: {(h['rationale'] or '')[:100]}")
        print(f"       bridge: {(h['bridge'] or '')[:100]}")
    if len(hooks) < 2:
        print("  (only one option — Compass VI cannot run a swap test with one survivor)")

    print(f"\n── ICP ──")
    print(f"  {r['icp_fit']}  {', '.join(json.loads(r['icp_notes'] or '[]'))}")

    print(f"\n── DRAFT ──   {r['draft_words'] or 0} words · claim strength: {r['claim_strength']}")
    if r["draft_text"]:
        print(textwrap.indent(r["draft_text"], "  "))

    print(f"\n── VERIFIER ──")
    print(f"  {r['verification_status']} · passed={bool(r['verification_passed'])}"
          f" · self_corrected={bool(r['self_corrected'])}")
    if r["verification_reason"]:
        print(textwrap.indent(textwrap.fill(r["verification_reason"], 96), "  "))
    print()


def diff(conn, a, b):
    ra = _rows(conn, "SELECT * FROM runs WHERE run_id LIKE ?", a + "%")
    rb = _rows(conn, "SELECT * FROM runs WHERE run_id LIKE ?", b + "%")
    if not ra or not rb:
        print("run not found")
        return
    ra, rb = ra[0], rb[0]
    # Fingerprint first, always: a code change masquerading as model variance is
    # exactly the mistake that produced the false "verifier is non-deterministic"
    # conclusion in HANDOFF §8.
    print("── FINGERPRINT ──")
    same = True
    for k in ("git_sha", "value_prop_sha", "groq_model"):
        flag = "  same" if ra[k] == rb[k] else "  DIFFERENT"
        if ra[k] != rb[k]:
            same = False
        print(f"{flag:<12}{k:<16}{ra[k]}  ->  {rb[k]}")
    print("\n  " + ("same code and config: differences below are model or retrieval variance"
                    if same else
                    "CODE OR CONFIG CHANGED: differences below are not evidence of nondeterminism"))
    print("\n── OUTCOME ──")
    for k in ("claim_strength", "icp_fit", "cards_total", "cards_eligible", "hooks_count",
              "verification_status", "self_corrected", "draft_words", "duration_ms",
              "prompt_tokens", "completion_tokens"):
        m = "  " if ra[k] == rb[k] else "* "
        print(f"{m}{k:<22}{str(ra[k]):<28}{rb[k]}")
    wa = json.loads(ra["winning_card"] or "null") or {}
    wb = json.loads(rb["winning_card"] or "null") or {}
    print("\n── WINNING CARD ──")
    for k in ("claim", "source", "proximity", "pain", "score"):
        m = "  " if wa.get(k) == wb.get(k) else "* "
        print(f"{m}{k:<12}{str(wa.get(k))[:50]:<52}{str(wb.get(k))[:50]}")
    print("\n── DRAFT ──")
    print("  identical" if ra["draft_text"] == rb["draft_text"] else "  DIFFERENT")


def failures(conn):
    rs = _rows(conn, "SELECT * FROM runs WHERE outcome='crash' OR verification_passed=0 "
                     "ORDER BY ts DESC LIMIT 40")
    for r in rs:
        print(f"{r['run_id']}  {r['person_name']} @ {r['company']}")
        print(f"    {r['error'] or r['verification_status']}: "
              f"{(r['error'] or r['verification_reason'] or '')[:150]}")


def summary(conn):
    print("by claim strength:")
    for r in _rows(conn, "SELECT claim_strength c, COUNT(*) n FROM runs GROUP BY c ORDER BY n DESC"):
        print(f"  {r['c'] or '(crash)':<22}{r['n']}")
    print("\nby verifier status:")
    for r in _rows(conn, "SELECT verification_status v, COUNT(*) n FROM runs GROUP BY v ORDER BY n DESC"):
        print(f"  {r['v'] or '(none)':<22}{r['n']}")
    print("\nby category:")
    for r in _rows(conn, "SELECT category c, COUNT(*) n FROM runs GROUP BY c ORDER BY n DESC"):
        print(f"  {r['c'] or '(none)':<22}{r['n']}")
    t = _rows(conn, "SELECT COUNT(*) n, SUM(prompt_tokens+completion_tokens) tok, "
                    "SUM(source_cost_usd) usd, AVG(duration_ms) ms FROM runs")[0]
    print(f"\n{t['n']} runs · {_fmt_tokens(t['tok'])} tokens · ${t['usd'] or 0:.4f} "
          f"· mean {(t['ms'] or 0)/1000:.1f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run"); ap.add_argument("--last", action="store_true")
    ap.add_argument("--diff", nargs=2); ap.add_argument("--failures", action="store_true")
    ap.add_argument("--summary", action="store_true"); ap.add_argument("-n", type=int, default=20)
    a = ap.parse_args()
    conn = connect()
    if a.diff: diff(conn, *a.diff)
    elif a.failures: failures(conn)
    elif a.summary: summary(conn)
    elif a.run: show_run(conn, a.run)
    elif a.last:
        r = _rows(conn, "SELECT run_id FROM runs ORDER BY ts DESC, rowid DESC LIMIT 1")
        show_run(conn, r[0]["run_id"]) if r else print("no runs yet")
    else: list_runs(conn, a.n)
