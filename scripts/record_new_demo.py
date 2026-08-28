"""Record the LLM fixtures for the four real demo prospects, and print the drafts.

USE_FIXTURES=fill: replay every fixture that already exists, go live only for the
missing ones. Never run this with fixtures off -- that re-answers prompts whose
recordings were fine, and because a downstream prompt's hash depends on upstream
output, it invalidates hashes the tests are still asking for.
"""
import asyncio
import itertools
import os
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv(".env.local")
os.environ["USE_FIXTURES"] = "fill"

from zara.ranker import FIXTURE_CLOCK  # noqa: E402

os.environ["ZARA_NOW"] = FIXTURE_CLOCK

from zara import antitemplate  # noqa: E402
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
    # Jon Anderson dropped 2026-08-28. His winning card is the announcement of his
    # own appointment, so the email tells a CFO that hiring a CFO creates
    # reconciliation work. The card is also undated, and the drafter kept calling
    # it recent, which the verifier correctly blocked on the app path. The right
    # fix is a guardrail against pitching someone their own hire; that is a
    # product change, not a demo change, and it is not being rushed before a
    # recording. Snapshot and fixtures stay on disk.
    # ("Jon Anderson", "Payouts Network", "Chief Financial Officer", "payoutsnetwork"),
    # Midwest 3PL was dropped: its name reduces to "midwest", a common word, so
    # entity resolution kept pulling regional roundups instead of the firm.
    # Fulfyld is coined, obscure, and a single facility in Madison, Alabama.
    # Fulfyld dropped from the demo set 2026-08-28. Cleaning the snippets changed
    # the hook prompt, so a different card won and its winning evidence went from
    # 71 days old to 665. The draft is clean and the age label is honest, but a
    # personalisation demo whose hook is 22 months old argues against itself.
    # Snapshot and fixtures stay on disk; scripts/try_draft.py can still run it.
    # ("AJ Khanijow", "Fulfyld", "Founder & Chief Executive Officer", "fulfyld"),
    # The no-signal path, kept from the original set. Its fallback prompt now
    # inherits _STYLE_RULES, which it never used to.
    ("Riley Chen", "Northwind Freight", None, "no_signal"),
]


async def main():
    # The repetition check compares each draft against the ones already written
    # in this run, so PAIRS order is load-bearing: change it and the drafts that
    # get asked to rewrite change with it, and recorded fixtures stop matching.
    with antitemplate.batch():
        await _run_all()

    if "--orderings" in sys.argv:
        await _record_orderings()


async def _record_orderings():
    """Every click order the demo operator could use.

    The app keeps one repetition batch per sitting, so the Nth prospect is
    compared against the N-1 already drafted. A different click order is a
    different comparison, so a different rewrite, so a prompt hash that the
    PAIRS-order recording above never produced -- and under USE_FIXTURES=1 a
    missing hash is a FileNotFoundError in front of the interviewer, not a
    degraded draft. Recording every permutation is what makes "click order does
    not matter" true rather than merely believed.

    Cheap after the first pass: fill replays everything already on disk and only
    the genuinely new states go live.
    """
    for order in itertools.permutations(PAIRS):
        names = " -> ".join(p[0].split()[0] for p in order)
        print(f"\n{'#' * 78}\n### ORDERING: {names}", flush=True)
        with antitemplate.batch():
            await _run_all(order, quiet=True)


async def _run_all(pairs=None, quiet=False):
    for name, company, title, snap in (pairs or PAIRS):
        if not quiet:
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
        if not quiet:
            print("-" * 78, flush=True)
            print(draft.draft_text or "<<< NO EMAIL >>>", flush=True)


asyncio.run(main())
