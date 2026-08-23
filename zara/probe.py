import argparse
import asyncio
import json
from dataclasses import asdict
from dotenv import load_dotenv

from zara.models import Prospect
from zara.orchestrator import run_pipeline
from zara.fetchers.ats import GreenhouseFetcher, LeverFetcher, AshbyFetcher, SmartRecruitersFetcher, RecruiteeFetcher
from zara.fetchers.news import GoogleNewsFetcher

from zara.utils.budget import get_mtd_spend
from zara.s2 import process_prospect, render_decision_card

async def main():
    load_dotenv(".env.local")
    
    parser = argparse.ArgumentParser(description="Probe a prospect through the Zara retrieval pipeline.")
    parser.add_argument("--name", required=True, help="Prospect's name")
    parser.add_argument("--company", required=True, help="Prospect's company name")
    parser.add_argument("--domain", help="Company domain")
    parser.add_argument("--linkedin", help="LinkedIn URL")
    parser.add_argument("--deep", action="store_true", help="Force deep search (Rung 4)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    parser.add_argument("--profile", type=str, choices=["lean", "standard", "social", "deep"], default="standard", help="Breadth profile")
    
    args = parser.parse_args()
    
    prospect = Prospect(
        person_name=args.name,
        company=args.company,
        company_domain=args.domain,
        linkedin_url=args.linkedin
    )
    
    print(f"=== ZARA RETRIEVAL PROBE ===")
    print(f"Prospect: {prospect.person_name} @ {prospect.company}")
    print(f"Profile: {args.profile}")
    print(f"============================")
    
    # ---------------------------
    # Rung 0: ATS & Free APIs
    # ---------------------------
    from zara.fetchers.ats import GreenhouseFetcher, LeverFetcher, AshbyFetcher, SmartRecruitersFetcher, RecruiteeFetcher
    from zara.fetchers.news import GoogleNewsFetcher
    rung0 = [
        GreenhouseFetcher(), LeverFetcher(), AshbyFetcher(), 
        SmartRecruitersFetcher(), RecruiteeFetcher(), GoogleNewsFetcher()
    ]
    
    # ---------------------------
    # Rung 1: Scoped Exa
    # ---------------------------
    from zara.fetchers.exa import ExaLinkedInFetcher, ExaNewsFetcher, ExaBlogFetcher, ExaEdgarFetcher, ExaYouTubeFetcher
    rung1 = [
        ExaLinkedInFetcher(), ExaNewsFetcher(), ExaBlogFetcher(),
        ExaEdgarFetcher(), ExaYouTubeFetcher()
    ]
    
    # ---------------------------
    # Rung 2, 3, 4: Apify
    # ---------------------------
    from zara.fetchers.apify import (
        ApifyLinkedInCompanyFetcher, ApifyLinkedInProfileFetcher, ApifyLinkedInJobsFetcher,
        ApifyLinkedInPostsFetcher, ApifyTwitterFetcher, ApifyInstagramFetcher,
        ApifyTikTokFetcher, ApifyYouTubeFetcher, ApifyRedditFetcher,
        ApifyFacebookFetcher, ApifyProductHuntFetcher, ApifyGoogleMapsFetcher,
        ApifyGoogleSearchFetcher, ApifyIndeedFetcher, ApifyG2CapterraFetcher, ApifyCrunchbaseFetcher
    )
    
    rung2 = []
    rung3 = []
    rung4 = []
    
    if args.profile in ["standard", "social", "deep"]:
        rung2.append(ApifyLinkedInCompanyFetcher())
        rung3.extend([ApifyLinkedInProfileFetcher(), ApifyLinkedInJobsFetcher()])
        rung4.append(ApifyLinkedInPostsFetcher())
        
    if args.profile in ["social", "deep"]:
        rung4.extend([ApifyTwitterFetcher(), ApifyYouTubeFetcher(), ApifyRedditFetcher(), ApifyInstagramFetcher()])
        
    if args.profile == "deep":
        rung4.extend([
            ApifyTikTokFetcher(), ApifyFacebookFetcher(), ApifyProductHuntFetcher(), 
            ApifyGoogleMapsFetcher(), ApifyGoogleSearchFetcher(), ApifyIndeedFetcher(),
            ApifyG2CapterraFetcher(), ApifyCrunchbaseFetcher()
        ])
    
    results = await run_pipeline(
        prospect,
        rung0_fetchers=rung0,
        rung1_fetchers=rung1,
        rung2_fetchers=rung2,
        rung3_fetchers=rung3,
        rung4_fetchers=rung4,
        deep_mode=(args.profile == "deep")
    )
    
    # Calculate run cost
    run_cost = sum(r.cost_usd for r in results)
    
    # Slice 2: Process prospect
    draft_res = await process_prospect(prospect, results)
    
    if args.json:
        import dataclasses
        def _asdict_safe(obj):
            if dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj)
            return obj
            
        out = {
            "prospect": asdict(prospect),
            "results": [asdict(r) for r in results],
            "draft_result": _asdict_safe(draft_res),
            "run_cost": run_cost,
            "mtd_budget": get_mtd_spend()
        }
        print(json.dumps(out, indent=2, default=str))
        return

    # Text output
    print(f"\n=== ZARA RANKER TABLE ===")
    print(f"{'INDEX':<5} | {'TIER':<7} | {'PROXIMITY':<14} | {'RECENCY':<7} | {'PAIN ID':<20} | {'SCORE':<5} | {'EXCLUSION / REASON'}")
    print("-" * 120)
    for i, c in enumerate(draft_res.ranked_prospect.cards):
        pain_id = c.pain_match.pain_id if c.pain_match else "-"
        score = f"{c.score:.2f}"
        rec = str(c.recency_days) if c.recency_days is not None else "-"
        if c.excluded:
            exc = f"EXCLUDED: {c.excluded}"
        else:
            exc = c.pain_match.reason if c.pain_match else "-"
        print(f"{i:<5} | {c.card.tier:<7} | {c.proximity:<14} | {rec:<7} | {pain_id:<20} | {score:<5} | {exc}")

    print(f"\n=== ZARA DECISION CARD ===")
    print(render_decision_card(draft_res, results))
    print(f"\nRun Cost: ${run_cost:.4f}")
    print(f"MTD Spend: ${get_mtd_spend():.4f} (Cap: $4.00 for Apify)")

if __name__ == "__main__":
    asyncio.run(main())
