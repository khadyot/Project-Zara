import os
import sys
import json
import asyncio
from zara.models import Prospect, SourceResult, SignalCard

def load_snapshot(path="tests/fixtures/shipbob_snapshot.json"):
    with open(path, "r") as f:
        data = json.load(f)
        
    results = []
    # Support both old format (single result dict) and new format (dict with 'results' list)
    raw_results = data.get("results", [data]) if isinstance(data, dict) and "results" in data else [data] if isinstance(data, dict) else data
    
    for r_data in raw_results:
        cards = []
        for c_data in r_data.get("cards", []):
            cards.append(SignalCard(**c_data))
            
        results.append(SourceResult(
            source=r_data["source"],
            rung=r_data["rung"],
            status=r_data["status"],
            reason=r_data["reason"],
            cards=cards,
            cost_usd=r_data["cost_usd"],
            elapsed_ms=r_data["elapsed_ms"]
        ))
    return results

async def record_all(path="tests/fixtures/shipbob_snapshot.json", company="ShipBob"):
    os.environ["USE_FIXTURES"] = ""
    
    from zara.ranker import rank_prospect
    from zara.classifier import classify_social_signals
    from zara.drafter import draft_email
    from zara.verifier import verify_draft
    from zara.utils.config import load_value_prop
    
    prospect = Prospect("Test", company)
    snapshot_results = load_snapshot(path)
    
    print(f"Recording ranker for {company} snapshot...", flush=True)
    rp = await rank_prospect(prospect, snapshot_results)
    
    print(f"Recording drafter for {company} snapshot...", flush=True)
    vp = load_value_prop()
    draft = await draft_email(rp, vp)
    
    if draft:
        print(f"Recording verifier for {company} snapshot...", flush=True)
        await verify_draft(draft, rp, vp)
        
    print(f"Recording classifier for {company} snapshot...", flush=True)
    await classify_social_signals(snapshot_results)
    
if __name__ == "__main__":
    from dotenv import load_dotenv
    import argparse
    load_dotenv(".env.local")
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=str, default="tests/fixtures/shipbob_snapshot.json")
    parser.add_argument("--company", type=str, default="ShipBob")
    args = parser.parse_args()
    
    asyncio.run(record_all(args.path, args.company))
    print(f"Mocks recorded successfully for {args.company}.")
