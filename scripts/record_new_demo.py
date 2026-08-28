"""Record the LLM fixtures for the four real demo prospects, and print the drafts.

USE_FIXTURES=fill: replay every fixture that already exists, go live only for the
missing ones. Never run this with fixtures off -- that re-answers prompts whose
recordings were fine, and because a downstream prompt's hash depends on upstream
output, it invalidates hashes the tests are still asking for.
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

from zara.models import Prospect  # noqa: E402
from zara.orchestrator import run_end_to_end_pipeline  # noqa: E402

IDENTITY = {
    "sender_name": "Zamp",
    "product": "We help operations teams automate manual, reconciliation-heavy processes",
    "proof_point": None,
}

PAIRS = [
    ("Devin Weil", "ShipMonk", "Chief Financial Officer", "shipmonk"),
    ("Chermaine Hu", "Episode Six", "Co-Founder & Chief Financial Officer", "episodesix"),
    ("Jon Anderson", "Payouts Network", "Chief Financial Officer", "payoutsnetwork"),
    # Midwest 3PL was dropped: its name reduces to "midwest", a common word, so
    # entity resolution kept pulling regional roundups instead of the firm.
    # Fulfyld is coined, obscure, and a single facility in Madison, Alabama.
    ("AJ Khanijow", "Fulfyld", "Founder & Chief Executive Officer", "fulfyld"),
    # The no-signal path, kept from the original set. Its fallback prompt now
    # inherits _STYLE_RULES, which it never used to.
    ("Riley Chen", "Northwind Freight", None, "no_signal"),
]


async def main():
    for name, company, title, snap in PAIRS:
        print(f"\n{'=' * 78}\n### {name} @ {company}", flush=True)
        try:
            results, draft = await run_end_to_end_pipeline(
                Prospect(name, company, title=title),
                settings={
                    "replay_snapshot": f"tests/fixtures/{snap}_snapshot.json",
                    "strictness": "strict",
                    "identity": IDENTITY,
                },
            )
        except Exception as e:
            print(f"  FAILED {type(e).__name__}: {str(e)[:220]}", flush=True)
            continue

        v = draft.verification
        win = draft.ranked_prospect.winning_card
        if win:
            age = f"{win.recency_days}d" if win.recency_days is not None else "undated"
        else:
            age = "-"
        print(
            f"claim_strength={draft.claim_strength}  verify={v.status}  "
            f"generic={draft.offer_is_generic}  age={age}",
            flush=True,
        )
        if win:
            print(f"HOOK: {win.card.claim[:90]}", flush=True)
            rej = [c for c in draft.ranked_prospect.cards if c is not win and c.guardrail_hit]
            for r in rej[:3]:
                print(f"  GUARDRAIL: {r.guardrail_hit} <- {r.card.claim[:56]}", flush=True)
        if v.reason:
            print(f"REASON: {v.reason[:200]}", flush=True)
        print(f"SUBJECT: {draft.subject}", flush=True)
        print("-" * 78, flush=True)
        print(draft.draft_text or "<<< NO EMAIL >>>", flush=True)


asyncio.run(main())
