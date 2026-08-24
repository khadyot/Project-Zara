import os
import sys
import asyncio
import httpx
from collections import Counter
from zara.models import Prospect
from zara.utils.config import load_value_prop

def block_network(*args, **kwargs):
    raise RuntimeError("Zero-Network Enforcement: Network request attempted during replay!")

async def replay_prospect(company: str):
    print(f"\n--- Replaying {company} ---")
    
    from zara.ranker import rank_prospect
    from zara.classifier import classify_social_signals
    from zara.drafter import draft_email
    from zara.verifier import verify_draft
    from scripts.record_mock import load_snapshot
    
    prospect = Prospect("Test", company)
    # The filename might need to be sanitized
    safe_company = company.lower().replace(" ", "_")
    snapshot_path = f"tests/fixtures/{safe_company}_snapshot.json"
    
    if not os.path.exists(snapshot_path):
        print(f"Skipping {company} - no snapshot found at {snapshot_path}")
        return None
        
    snapshot_results = load_snapshot(snapshot_path)
    vp = load_value_prop()
    
    # Initialize metrics
    hook_tiers = Counter()
    claim_strengths = Counter()
    guardrail_trips = 0
    prompt_tokens = 0
    completion_tokens = 0
    
    # Clear fixture usage tracker
    if hasattr(sys, "_fixture_usage"):
        sys._fixture_usage.clear()
        
    rp = await rank_prospect(prospect, snapshot_results)
    
    # The ranker model now outputs multiple hooks? No, it outputs winning_hook
    if getattr(rp, "winning_hook", None):
        hook_tiers[rp.winning_hook.tier] += 1
    elif getattr(rp, "hooks", None):
        for h in rp.hooks:
            hook_tiers[h.tier] += 1
            
    claim_strengths[rp.claim_strength] += 1
    
    draft = await draft_email(rp, vp)
    if draft:
        v_res = await verify_draft(draft, rp, vp)
        if not v_res.passed:
            guardrail_trips += 1
            
    await classify_social_signals(snapshot_results)
    
    # Tally usage
    if hasattr(sys, "_fixture_usage"):
        for h, usage in sys._fixture_usage.items():
            if isinstance(usage.get("prompt_tokens"), int):
                prompt_tokens += usage["prompt_tokens"]
            if isinstance(usage.get("completion_tokens"), int):
                completion_tokens += usage["completion_tokens"]
                
    print(f"Hook tiers: {dict(hook_tiers)}")
    print(f"Claim strengths: {dict(claim_strengths)}")
    print(f"Guardrail trips (Verifier blocked): {guardrail_trips}")
    print(f"Tokens Spent: {prompt_tokens} prompt / {completion_tokens} completion")
    
    return {
        "company": company,
        "hook_tiers": dict(hook_tiers),
        "claim_strengths": dict(claim_strengths),
        "guardrail_trips": guardrail_trips,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens
    }

async def main():
    os.environ["USE_FIXTURES"] = "1"
    
    # Enforce zero network calls
    httpx.AsyncClient.send = block_network
    
    prospects = ["Versapay", "ShipBob", "Modern Treasury", "Thin Prospect"]
    
    all_results = []
    for p in prospects:
        res = await replay_prospect(p)
        if res:
            all_results.append(res)
            
    print("\n=== GOLDEN SET REPLAY SUMMARY ===")
    for r in all_results:
        print(f"{r['company']}: Hooks={r['hook_tiers']} | Claims={r['claim_strengths']} | Guardrails={r['guardrail_trips']} | Tokens={r['prompt_tokens']}/{r['completion_tokens']}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(".env.local")
    asyncio.run(main())
