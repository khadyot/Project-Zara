import asyncio
import os
from zara.models import Prospect
from zara.record_mock import load_snapshot

async def main():
    os.environ["USE_FIXTURES"] = "1"
    from zara.ranker import rank_prospect
    
    prospect = Prospect("Test", "ShipBob")
    snapshot = load_snapshot()
    
    rp = await rank_prospect(prospect, [snapshot])
    
    print("Ranker Table:")
    print("idx | tier | proximity | recency | pain_id | score | exclusion | reason")
    print("-" * 80)
    for i, c in enumerate(rp.cards):
        pain_id = c.pain_match.pain_id if c.pain_match else "none"
        score = c.score
        reason = c.pain_match.reason if c.pain_match else "none"
        excl = c.excluded or "none"
        print(f"{i:<3} | {c.card.tier:<8} | {c.proximity:<12} | {c.recency_days or 'none':<5} | {pain_id:<12} | {score:<5.2f} | {excl:<15} | {reason}")
        
if __name__ == "__main__":
    asyncio.run(main())
