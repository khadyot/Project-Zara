"""Show a draft with its per-sentence citations. Read-only, no model calls.

    python scripts/check_citations.py shipmonk "Devin Weil" "ShipMonk"
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
from zara.ui.citations import attribute  # noqa: E402

IDENT = {
    "sender_name": "Zamp",
    "product": "We help operations teams automate manual, reconciliation-heavy processes",
    "proof_point": None,
}
snap, name, company = sys.argv[1], sys.argv[2], sys.argv[3]


async def main():
    _, d = await run_end_to_end_pipeline(
        Prospect(name, company, title="Chief Financial Officer"),
        settings={
            "replay_snapshot": f"tests/fixtures/{snap}_snapshot.json",
            "strictness": "strict",
            "identity": IDENT,
        },
    )
    cards = [c.card for c in d.ranked_prospect.cards if c.excluded is None]
    win = d.ranked_prospect.winning_card.card if d.ranked_prospect.winning_card else None
    marked, sources = attribute(d.draft_text, cards, win)
    for s, n in marked:
        print(f"  [{n if n else ' '}] {s[:94]}")
    print("\nSOURCES")
    for i, c in enumerate(sources, 1):
        print(f"  [{i}] {c.claim[:64]}")
        print(f"      {(c.source_url or '')[:100]}")


asyncio.run(main())
