import os
import sys
import json
import asyncio
from zara.models import Prospect, SourceResult, SignalCard

def load_snapshot(path="tests/fixtures/shipbob_snapshot.json"):
    with open(path, "r") as f:
        data = json.load(f)
        
    cards = []
    for c_data in data.get("cards", []):
        cards.append(SignalCard(**c_data))
        
    return SourceResult(
        source=data["source"],
        rung=data["rung"],
        status=data["status"],
        reason=data["reason"],
        cards=cards,
        cost_usd=data["cost_usd"],
        elapsed_ms=data["elapsed_ms"]
    )

async def record_all():
    os.environ["USE_FIXTURES"] = ""
    
    from zara.ranker import rank_prospect
    from zara.classifier import classify_social_signals
    from zara.drafter import draft_email
    from zara.verifier import verify_draft
    from zara.utils.config import load_value_prop
    
    prospect = Prospect("Test", "ShipBob")
    snapshot = load_snapshot()
    
    print("Recording ranker for snapshot...", flush=True)
    rp = await rank_prospect(prospect, [snapshot])
    
    print("Recording drafter for snapshot...", flush=True)
    vp = load_value_prop()
    draft = await draft_email(rp, vp)
    
    if draft:
        print("Recording verifier for snapshot...", flush=True)
        await verify_draft(draft, rp, vp)
        
    print("Recording classifier for snapshot...", flush=True)
    await classify_social_signals([snapshot])
    
    print("Recording ranker for test_3 no_pain card...", flush=True)
    test3_card = SignalCard(
        claim="Hiring", signal_type="hiring", source_url="", published_date=None,
        snippet="We are hiring a Software Engineer", tier="company", source="Test"
    )
    test3_res = SourceResult(source="Test", rung=0, status="ok", reason=None, cards=[test3_card], cost_usd=0, elapsed_ms=0)
    await rank_prospect(prospect, [test3_res])

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(".env.local")
    asyncio.run(record_all())
    print("Mocks recorded successfully.")
