"""Search provider bake-off: incumbent vs Brave LLM Context vs Parallel Search.

Measures what the RANKER would make of each provider's output, not what the
vendor claims. Proximity, dating and directory-junk detection all run through the
real functions in zara.ranker, because "10 results" means nothing if the pipeline
demotes all ten to `database`.

Incumbent baseline comes from the recorded snapshots -- those are what retrieval
actually produced for these exact prospects, and replaying them is free.

    ./venv/bin/python scripts/bakeoff_search.py
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(".env.local")

from scripts.record_mock import load_snapshot
from zara.models import Prospect
from zara.ranker import _compute_proximity, _compute_recency, _is_directory_row
from zara.fetchers.brave import BraveContextFetcher
from zara.fetchers.parallel import ParallelSearchFetcher

# The three that replay in the demo, with the titles the prompt hash depends on.
PROSPECTS = [
    Prospect("Chermaine Hu", "Episode Six", title="Co-Founder & Chief Financial Officer"),
    Prospect("Devin Weil", "ShipMonk", title="Chief Financial Officer"),
    Prospect("Riley Chen", "Northwind Freight", title=None),
]
SNAPSHOTS = {
    "Episode Six": "tests/fixtures/episodesix_snapshot.json",
    "ShipMonk": "tests/fixtures/shipmonk_snapshot.json",
    "Northwind Freight": "tests/fixtures/no_signal_snapshot.json",
}


def query_plan(p: Prospect) -> tuple[str, list[str]]:
    """One plan, handed to both providers, so the comparison is of engines and
    not of prompts. Deliberately the same three angles the pain set cares about:
    the person in their own words, what the company did, how they run finance."""
    role = p.title or "finance leader"
    objective = (
        f"Recent public statements by {p.person_name} ({role} at {p.company}), and "
        f"announcements about {p.company} that would indicate reconciliation, "
        f"month-end close, ERP migration or payment-operations workload."
    )
    return objective, [
        f'"{p.person_name}" {p.company} interview OR podcast OR post',
        f'"{p.company}" announcement expansion funding launch',
        f'"{p.company}" finance operations reconciliation ERP billing',
    ]


def profile(cards, prospect) -> dict:
    """What the pipeline would make of these cards."""
    n = len(cards)
    if not n:
        return dict(cards=0, dated=0, person=0, directory=0, chars=0)
    prox = [_compute_proximity(c, prospect) for c in cards]
    return dict(
        cards=n,
        dated=sum(1 for c in cards if _compute_recency(c.published_date) is not None),
        person=sum(1 for x in prox if x in ("authored", "attributed", "colleague_authored")),
        directory=sum(1 for c in cards if _is_directory_row(c)),
        chars=sum(len(c.snippet or "") for c in cards) // n,
    )


async def run_one(prospect):
    objective, queries = query_plan(prospect)
    rows = []

    snap = SNAPSHOTS.get(prospect.company)
    inc_cards = []
    if snap and os.path.exists(snap):
        for r in load_snapshot(snap):
            inc_cards.extend(r.cards)
    rows.append(("incumbent (recorded)", profile(inc_cards, prospect), 0.0, 0))

    # Brave bills per QUERY, so the three-angle plan is three calls.
    t0 = time.time()
    brave_results = await asyncio.gather(*(
        BraveContextFetcher(query=q, count=10).fetch(prospect) for q in queries
    ))
    brave_cards, brave_cost = [], 0.0
    for r in brave_results:
        brave_cards.extend(r.cards)
        brave_cost += r.cost_usd
        if r.status != "ok":
            print(f"    brave {r.status}: {r.reason}", file=sys.stderr)
    rows.append(("brave llm-context", profile(brave_cards, prospect), brave_cost,
                 int((time.time() - t0) * 1000)))

    # Parallel bills per REQUEST, so the same three queries are one call.
    t0 = time.time()
    pr = await ParallelSearchFetcher(objective=objective, queries=queries,
                                     mode="fast").fetch(prospect)
    if pr.status != "ok":
        print(f"    parallel {pr.status}: {pr.reason}", file=sys.stderr)
    rows.append(("parallel search", profile(pr.cards, prospect), pr.cost_usd,
                 int((time.time() - t0) * 1000)))

    return rows, brave_cards, pr.cards


async def main():
    print(f"{'prospect':<20} {'provider':<22} {'cards':>5} {'dated':>6} {'person':>7} "
          f"{'dir':>4} {'avg chars':>10} {'cost $':>8} {'ms':>6}")
    print("-" * 96)
    totals = {}
    person_urls = {}
    for p in PROSPECTS:
        rows, brave_cards, par_cards = await run_one(p)
        for name, m, cost, ms in rows:
            print(f"{p.company:<20} {name:<22} {m['cards']:>5} {m['dated']:>6} "
                  f"{m['person']:>7} {m['directory']:>4} {m['chars']:>10} "
                  f"{cost:>8.4f} {ms:>6}")
            t = totals.setdefault(name, dict(cards=0, dated=0, person=0, directory=0, cost=0.0))
            for k in ("cards", "dated", "person", "directory"):
                t[k] += m[k]
            t["cost"] += cost
        person_urls.setdefault(p.company, {})
        for label, cards in (("brave", brave_cards), ("parallel", par_cards)):
            person_urls[p.company][label] = [
                c.source_url for c in cards
                if _compute_proximity(c, p) in ("authored", "attributed", "colleague_authored")
            ]
        print()

    print("=" * 96)
    print(f"{'TOTAL':<20} {'provider':<22} {'cards':>5} {'dated':>6} {'person':>7} {'dir':>4} {'':>10} {'cost $':>8}")
    for name, t in totals.items():
        print(f"{'':<20} {name:<22} {t['cards']:>5} {t['dated']:>6} {t['person']:>7} "
              f"{t['directory']:>4} {'':>10} {t['cost']:>8.4f}")

    print("\nPerson-tier URLs found (the scarce resource):")
    for company, byprov in person_urls.items():
        for prov, urls in byprov.items():
            for u in urls:
                print(f"  {company:<20} {prov:<10} {u[:78]}")


asyncio.run(main())
