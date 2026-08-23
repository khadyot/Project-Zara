import asyncio
from zara.models import Prospect, SignalCard, RankedProspect, SourceResult
from zara.ranker import rank_prospect
from zara.verifier import pass1_grounding

async def main():
    print("=== 2. Layoff Veto Firing ===")
    prospect = Prospect("Test", "Test Co")
    card = SignalCard(
        claim="Restructuring affects team", signal_type="news", source_url="", published_date=None,
        snippet="ShipBob announced layoffs affecting 200 warehouse staff after restructuring.", tier="company", source="TestATS"
    )
    class MockHashNoPain:
        def __init__(self, *args, **kwargs): pass
        def hexdigest(self): return 'test_hash_no_pain'
    import hashlib
    hashlib.md5 = MockHashNoPain
    
    res = await rank_prospect(prospect, [SourceResult(source="T", rung=0, status="ok", reason=None, cards=[card], cost_usd=0, elapsed_ms=0)])
    print(f"Snippet: {card.snippet}")
    print(f"Exclusion: {res.cards[0].excluded}\n")

    print("=== 3. Clean vs Fabricated Draft (Pass 1) ===")
    import yaml
    with open("value_prop.yaml") as f:
        vp = yaml.safe_load(f)
    
    rp = RankedProspect(
        prospect=Prospect("Dimitri Dadiomov", "Modern Treasury"),
        cards=[], icp_fit="fit", winning_card=None
    )
    
    clean = "Hi Dimitri Dadiomov, Modern Treasury is a payment operations platform. We help operations teams automate manual, reconciliation-heavy processes. " + "This is extra padding to ensure the word count exceeds the sixty word minimum limit required by the verifier script. " * 4
    hallucinated = "Hi Dimitri Dadiomov, Modern Treasury is a payment operations platform. We saved $1.5M. " + "This is extra padding to ensure the word count exceeds the sixty word minimum limit required by the verifier script. " * 4
    
    print(f"Clean ungrounded tokens: {pass1_grounding(clean, rp, vp)}")
    print(f"Fabricated ungrounded tokens: {pass1_grounding(hallucinated, rp, vp)}")

if __name__ == "__main__":
    import os
    os.environ["USE_FIXTURES"] = "1"
    asyncio.run(main())
