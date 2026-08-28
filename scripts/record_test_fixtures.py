"""Re-record the LLM fixtures the test suite needs after a prompt change.

The tests pin USE_FIXTURES=1 through monkeypatch, so they can never record; a
missing hash is a hard failure by design. This replays the same pipeline calls
they make, with USE_FIXTURES=fill, so the hashes exist by the time pytest asks.

Run it after any edit to a prompt in ranker / drafter / verifier / classifier,
then run the suite twice.
"""
import asyncio
import os
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv(".env.local")
os.environ["USE_FIXTURES"] = "fill"

from zara.ranker import FIXTURE_CLOCK  # noqa: E402

os.environ["ZARA_NOW"] = FIXTURE_CLOCK

from scripts.record_mock import load_snapshot  # noqa: E402
from zara.models import Prospect  # noqa: E402
from zara.s2 import process_prospect  # noqa: E402
from zara.orchestrator import run_end_to_end_pipeline  # noqa: E402

# Exactly what tests/test_s2.py, test_telemetry.py and test_demo_mode.py run:
# the placeholder name "Test" against the ShipBob snapshot, strict, no identity.
SNAPSHOT = "tests/fixtures/shipbob_snapshot.json"


async def main():
    prospect = Prospect("Test", "ShipBob")

    print("recording: process_prospect (strict)", flush=True)
    results = load_snapshot(SNAPSHOT)
    d = await process_prospect(prospect, results, strictness="strict")
    print(f"  -> {d.claim_strength} / {d.verification.status}", flush=True)

    print("recording: run_end_to_end_pipeline (strict)", flush=True)
    _, d2 = await run_end_to_end_pipeline(
        prospect,
        settings={"replay_snapshot": SNAPSHOT, "strictness": "strict"},
    )
    print(f"  -> {d2.claim_strength} / {d2.verification.status}", flush=True)


asyncio.run(main())
