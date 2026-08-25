"""Build the demo seed run store, offline.

Two jobs:
  1. Records the model fixtures for the demo prospects, so demo mode has a
     complete replay chain (record pass, one live call chain per prospect).
  2. Writes seed/zara_runs_demo.db, which ships with the app so the Run History
     dashboard is never empty on a fresh deploy -- the host filesystem is
     ephemeral and var/ is gitignored.

The seed deliberately does NOT reuse var/zara_runs.db: that store holds real
named people from the stress corpus, which is gitignored precisely because this
repo is public. These prospects are invented; the companies are public.

  record:  PYTHONPATH=. ./venv/bin/python scripts/seed_demo_runs.py --record
  seed:    PYTHONPATH=. ./venv/bin/python scripts/seed_demo_runs.py
"""
import argparse
import asyncio
import os
import sys

DEMOS = [
    ("Alex Rivera",  "ShipBob",         "VP Finance",        "tests/fixtures/shipbob_snapshot.json"),
    ("Sam Okafor",   "Versapay",        "Controller",        "tests/fixtures/versapay_snapshot.json"),
    ("Jordan Ellis", "Modern Treasury", "Director of Ops",   "tests/fixtures/modern_treasury_snapshot.json"),
    # The honest-degradation case, and the one the brief calls the differentiator:
    # nothing was found, so the draft says so instead of inventing a hook.
    ("Riley Chen",   "Northwind Freight", "CFO",             "tests/fixtures/no_signal_snapshot.json"),
]


async def _one(name, company, title, snap, record):
    from zara.models import Prospect
    from zara.utils import telemetry
    from zara.orchestrator import run_end_to_end_pipeline

    p = Prospect(name, company, title=title)
    with telemetry.trace_run(p, trigger="seed_demo") as t:
        results, draft = await run_end_to_end_pipeline(
            p, settings={"replay_snapshot": snap, "strictness": "strict"}
        )
        t.capture_sources(results)
        t.capture_draft(draft)
    print(f"{name:14} {company:18} claim={draft.claim_strength:18} "
          f"generic={draft.offer_is_generic} sources={len(results)} "
          f"words={len((draft.draft_text or '').split())}", flush=True)


async def main(record):
    if record:
        from dotenv import load_dotenv
        load_dotenv(".env.local")
        os.environ.pop("USE_FIXTURES", None)
        print("RECORD pass: retrieval is replayed, model calls are LIVE.", flush=True)
    else:
        os.environ["USE_FIXTURES"] = "1"
        import httpx
        def _boom(*a, **k):
            raise RuntimeError("NETWORK CALL ATTEMPTED IN DEMO MODE")
        for m in ("send", "post", "get", "request"):
            setattr(httpx.AsyncClient, m, _boom)
            setattr(httpx.Client, m, _boom)
        print("SEED pass: network hard-blocked.", flush=True)

    for name, company, title, snap in DEMOS:
        await _one(name, company, title, snap, record)

    if not record:
        print("\nzero network calls -- demo mode verified offline", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true",
                    help="make live model calls to record the fixtures")
    args = ap.parse_args()
    if not args.record and not os.environ.get("ZARA_RUN_DB"):
        os.environ["ZARA_RUN_DB"] = "seed/zara_runs_demo.db"
    asyncio.run(main(args.record))
