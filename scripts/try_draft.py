"""Re-draft ONE prospect live, replaying everything upstream. Records nothing.

    PYTHONPATH=. ./venv/bin/python scripts/try_draft.py episodesix

Costs one or two model calls. The alternative -- what was actually done four times
-- is re-recording all five prospects to see whether a wording change helped, which
is roughly 25 calls and most of a day's Groq allowance.

Ranking, pain scoring and the hook all replay from fixtures, so the shortlist the
drafter is handed is identical between attempts and the only thing that moved is
the prompt being tuned. Nothing here writes a fixture: see _live_stages() in
zara/utils/provider.py.
"""
import asyncio
import os
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv(".env.local")

# Replay everything, except the stages being iterated on.
os.environ["USE_FIXTURES"] = "1"
# The judge has to come live too: it scores the draft, so a new draft is a new
# verifier prompt and its fixture cannot exist yet. Three calls an iteration.
os.environ["ZARA_LIVE_STAGES"] = "drafter,drafter_revision,drafter_no_signal,verifier_judge"

from zara.ranker import FIXTURE_CLOCK  # noqa: E402

os.environ["ZARA_NOW"] = FIXTURE_CLOCK

from zara.models import Prospect  # noqa: E402
from zara.orchestrator import run_end_to_end_pipeline  # noqa: E402

IDENTITY = {
    "sender_name": "Zamp",
    "product": "We help operations teams automate manual, reconciliation-heavy processes",
    "proof_point": None,
}

# Same rows as scripts/record_new_demo.py. Title is load-bearing: it interpolates
# into the ranker and hook prompts, so a wrong one misses their fixtures.
PROSPECTS = {
    "shipmonk": ("Devin Weil", "ShipMonk", "Chief Financial Officer"),
    "episodesix": ("Chermaine Hu", "Episode Six", "Co-Founder & Chief Financial Officer"),
    "payoutsnetwork": ("Jon Anderson", "Payouts Network", "Chief Financial Officer"),
    "fulfyld": ("AJ Khanijow", "Fulfyld", "Founder & Chief Executive Officer"),
    "no_signal": ("Riley Chen", "Northwind Freight", None),
}


async def main(snap: str):
    name, company, title = PROSPECTS[snap]
    results, draft = await run_end_to_end_pipeline(
        Prospect(name, company, title=title),
        settings={
            "replay_snapshot": f"tests/fixtures/{snap}_snapshot.json",
            "strictness": "strict",
            "identity": IDENTITY,
        },
    )
    win = draft.ranked_prospect.winning_card
    v = draft.verification
    print(f"\n{'=' * 78}\n{name} @ {company}")
    print(f"claim_strength={draft.claim_strength}  verify={v.status if v else '-'}")
    if win:
        print(f"proximity={win.proximity}  attributed_to={win.attributed_to}")
        print(f"HOOK: {win.card.claim[:88]}")
    if v and v.reason:
        print(f"REASON: {v.reason[:200]}")
    print(f"words={len((draft.draft_text or '').split())}")
    print("-" * 78)
    print(f"SUBJECT: {draft.subject}\n")
    # repr on the blank lines too: the formatting is part of what is being reviewed
    print(draft.draft_text or "<<< NO EMAIL >>>")
    print("-" * 78)


if __name__ == "__main__":
    snap = sys.argv[1] if len(sys.argv) > 1 else "episodesix"
    if snap not in PROSPECTS:
        sys.exit(f"unknown snapshot '{snap}'. one of: {', '.join(PROSPECTS)}")
    asyncio.run(main(snap))
