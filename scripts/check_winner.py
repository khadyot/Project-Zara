"""Why did this card win? Prints the ranked field for one prospect.

    python scripts/check_winner.py shipmonk "Devin Weil" "ShipMonk"
"""
import asyncio
import os
import sys

sys.path.insert(0, ".")
os.environ["USE_FIXTURES"] = "1"
from zara.ranker import FIXTURE_CLOCK  # noqa: E402

os.environ["ZARA_NOW"] = FIXTURE_CLOCK
from zara.models import Prospect  # noqa: E402
from zara.orchestrator import run_end_to_end_pipeline  # noqa: E402

IDENT = {
    "sender_name": "Zamp",
    "product": "We help operations teams automate manual, reconciliation-heavy processes",
    "proof_point": None,
}

snap, name, company = sys.argv[1], sys.argv[2], sys.argv[3]
title = sys.argv[4] if len(sys.argv) > 4 else "Chief Financial Officer"


async def main():
    _, d = await run_end_to_end_pipeline(
        Prospect(name, company, title=title),
        settings={
            "replay_snapshot": f"tests/fixtures/{snap}_snapshot.json",
            "strictness": "strict",
            "identity": IDENT,
        },
    )
    w = d.ranked_prospect.winning_card
    print(f"WINNER [{w.score:.3f}] prox={w.proximity} age={w.recency_days} guard={w.guardrail_hit}")
    print(f"   {w.card.claim[:88]}\n")
    print(f"{'score':>6}  {'prox':<20} {'age':>8}  claim")
    for c in sorted(d.ranked_prospect.cards, key=lambda x: -x.score)[:12]:
        age = f"{c.recency_days}d" if c.recency_days is not None else "undated"
        mark = " <-WIN" if c is w else ""
        print(f"{c.score:6.3f}  {c.proximity:<20} {age:>8}  {c.card.claim[:52]}{mark}")


asyncio.run(main())
