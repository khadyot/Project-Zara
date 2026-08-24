"""Stress-test runner: drive the pipeline across a prospect set, log every run.

Usage:
    PYTHONPATH=. env -u GROQ_API_KEY ./venv/bin/python scripts/stress_run.py \
        --set reference/stress_set.csv --limit 5 [--start 0] [--profile standard]

CSV columns: category,name,title,company,domain   (title/domain may be blank)

Pacing: one prospect costs ~5.2K tokens against an 8K TPM Groq bucket, so runs
are spaced by --gap seconds (default 60). Results append to
reference/stress_log.jsonl and a human-readable reference/stress_log.md.
"""
import argparse, asyncio, csv, json, os, sys, time, traceback
from collections import Counter

LOG_JSONL = "reference/stress_log.jsonl"
LOG_MD = "reference/stress_log.md"


def _summarise(prospect, results, draft, elapsed):
    rp = draft.ranked_prospect
    win = rp.winning_card
    by_status = Counter(r.status for r in results)
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "name": prospect.person_name,
        "company": prospect.company,
        "title": prospect.title,
        "elapsed_s": round(elapsed, 2),
        "cost_usd": round(sum(r.cost_usd for r in results), 4),
        "claim_strength": draft.claim_strength,
        "icp_fit": rp.icp_fit,
        "icp_notes": list(rp.icp_notes or []),
        "cards_total": len(rp.cards),
        "sources": dict(by_status),
        "failed_sources": [f"{r.source}: {(r.reason or '')[:80]}" for r in results if r.status == "failed"],
        "hooks": len(rp.hooks or []),
        "winning": None,
        "verification": None,
        "draft_words": len(draft.draft_text.split()) if draft.draft_text else 0,
        "draft": draft.draft_text,
    }
    if win:
        row["winning"] = {
            "claim": win.card.claim[:160],
            "source": win.card.source,
            "url": win.card.source_url[:160],
            "proximity": win.proximity,
            "attributed_to": win.attributed_to,
            "pain": win.pain_match.pain_id if win.pain_match else None,
            "score": win.score,
            "recency_days": win.recency_days,
        }
    if draft.verification:
        row["verification"] = {
            "status": draft.verification.status,
            "passed": draft.verification.passed,
            "self_corrected": draft.verification.self_corrected,
            "reason": (draft.verification.reason or "")[:300],
        }
    return row


def _md_row(r):
    if r.get("error"):
        return f"| {r['name']} @ {r['company']} | **CRASH** | — | — | — | — | `{r['error'][:80]}` |"
    w = r.get("winning") or {}
    v = r.get("verification") or {}
    verdict = v.get("status", "no-draft")
    if v.get("self_corrected"):
        verdict += " (self-corrected)"
    return (f"| {r['name']} @ {r['company']} | {r['elapsed_s']}s | {r['claim_strength']} | "
            f"{w.get('pain') or '—'} {w.get('score') or ''} | {w.get('proximity') or '—'} | "
            f"{r['icp_fit']} | {verdict} |")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="reference/stress_set.csv")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--gap", type=float, default=60.0, help="seconds between runs (8K TPM bucket)")
    ap.add_argument("--profile", default="standard")
    args = ap.parse_args()

    os.environ.pop("USE_FIXTURES", None)
    from dotenv import load_dotenv
    load_dotenv(".env.local")
    from zara.models import Prospect
    from zara.orchestrator import run_end_to_end_pipeline

    with open(args.set) as f:
        rows = [r for r in csv.DictReader(f) if (r.get("name") or "").strip()]
    rows = rows[args.start:args.start + args.limit]
    print(f"{len(rows)} prospects, gap {args.gap}s\n")

    os.makedirs("reference", exist_ok=True)
    out = []
    for i, r in enumerate(rows):
        p = Prospect(r["name"].strip(), r["company"].strip(),
                     title=(r.get("title") or "").strip() or None,
                     company_domain=(r.get("domain") or "").strip() or None)
        print(f"[{i+1}/{len(rows)}] {p.person_name} @ {p.company}  ({r.get('category','')})")
        t0 = time.time()
        try:
            results, draft = await run_end_to_end_pipeline(p, profile=args.profile)
            row = _summarise(p, results, draft, time.time() - t0)
        except Exception as e:
            row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "name": p.person_name,
                   "company": p.company, "title": p.title, "elapsed_s": round(time.time()-t0, 2),
                   "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1200:]}
            print(f"     CRASH {row['error']}")
        row["category"] = r.get("category", "")
        out.append(row)
        with open(LOG_JSONL, "a") as f:
            f.write(json.dumps(row) + "\n")
        if not row.get("error"):
            w = row.get("winning") or {}
            print(f"     {row['elapsed_s']}s · {row['claim_strength']} · pain={w.get('pain')} "
                  f"{w.get('score') or ''} · prox={w.get('proximity')} · "
                  f"verify={(row.get('verification') or {}).get('status')}")
        if i < len(rows) - 1:
            await asyncio.sleep(args.gap)

    hdr = ("| Prospect | Time | Claim strength | Pain | Proximity | ICP | Verifier |\n"
           "|---|---|---|---|---|---|---|\n")
    with open(LOG_MD, "a") as f:
        f.write(f"\n## Batch {time.strftime('%Y-%m-%d %H:%M')} — {len(out)} runs\n\n{hdr}")
        for r in out:
            f.write(_md_row(r) + "\n")

    ok = [r for r in out if not r.get("error")]
    print(f"\n=== {len(ok)}/{len(out)} completed ===")
    if ok:
        print("claim_strength:", dict(Counter(r["claim_strength"] for r in ok)))
        print("verifier      :", dict(Counter((r.get("verification") or {}).get("status") for r in ok)))
        print("median time   :", sorted(r["elapsed_s"] for r in ok)[len(ok)//2], "s")
        print("total cost    : $", round(sum(r["cost_usd"] for r in ok), 4))
    print(f"\nlogged -> {LOG_JSONL} and {LOG_MD}")

if __name__ == "__main__":
    asyncio.run(main())
