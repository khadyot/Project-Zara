import asyncio
from zara.models import Prospect, SourceResult
from zara.utils.budget import get_mtd_spend, add_spend
from zara.classifier import classify_social_signals
import logging

logger = logging.getLogger(__name__)

BUDGET_CAP = 4.00

async def run_pipeline(
    prospect: Prospect,
    rung0_fetchers: list,
    rung1_fetchers: list,
    rung2_fetchers: list,
    rung3_fetchers: list,
    rung4_fetchers: list,
    deep_mode: bool = False
) -> list[SourceResult]:
    """
    Executes the retrieval pipeline according to the cost-ordered escalation ladder.
    """
    results: list[SourceResult] = []
    
    # 1. Budget check for Rung 2
    mtd_spend = get_mtd_spend()
    # Rung 2 projected cost is ~$0.002
    projected_spend = 0.002
    
    fetcher_tasks = []
    # Rung 0 (Always fires, free)
    for f in rung0_fetchers:
        fetcher_tasks.append((f, f.fetch(prospect)))
        
    # Rung 1 (Always fires, free tier)
    for f in rung1_fetchers:
        fetcher_tasks.append((f, f.fetch(prospect)))
        
    # Rung 2 (Always fires if budget permits)
    rung2_allowed = (mtd_spend + projected_spend) <= BUDGET_CAP
    for f in rung2_fetchers:
        if rung2_allowed:
            fetcher_tasks.append((f, f.fetch(prospect)))
        else:
            # We must return a skipped result if gated
            results.append(SourceResult(
                source=f.__class__.__name__,
                rung=2,
                status="skipped",
                reason="budget guard",
                cards=[],
                cost_usd=0.0,
                elapsed_ms=0
            ))
            
    # Execute Rung 0, 1, 2 in parallel
    if fetcher_tasks:
        parallel_results = await asyncio.gather(*(t for _, t in fetcher_tasks), return_exceptions=True)
        for (f, _), res in zip(fetcher_tasks, parallel_results):
            if isinstance(res, SourceResult):
                results.append(res)
                if res.cost_usd > 0:
                    add_spend(res.cost_usd)
            elif isinstance(res, Exception):
                logger.error(f"Fetcher raised exception: {type(res).__name__}: {res}")
                results.append(SourceResult(
                    source=f.__class__.__name__,
                    rung=getattr(f, 'rung', 0), # Fallback if rung not present
                    status="failed",
                    reason=f"{type(res).__name__}: {res}",
                    cards=[],
                    cost_usd=0.0,
                    elapsed_ms=0
                ))
                
    has_person_profile = False
    has_company_hiring = False
    discovered_linkedin_url = None
    
    for r in results:
        for card in r.cards:
            if card.tier == "person" and card.signal_type in ("profile", "person_mention"):
                has_person_profile = True
            if card.tier == "company" and card.signal_type == "hiring":
                has_company_hiring = True
            if not discovered_linkedin_url and "linkedin.com/in/" in card.source_url:
                discovered_linkedin_url = card.source_url
                
    if discovered_linkedin_url and not prospect.linkedin_url:
        from dataclasses import replace
        prospect = replace(prospect, linkedin_url=discovered_linkedin_url)
    
    # Rung 3: LinkedIn Jobs (if no hiring), LinkedIn Profile (if no profile)
    rung3_tasks = []
    mtd_spend = get_mtd_spend()
    projected_spend = 0.004 # roughly per rung 3 call
    
    # We differentiate LinkedIn Profile vs Jobs based on the fetcher name for now
    for f in rung3_fetchers:
        is_profile = "Profile" in f.__class__.__name__ or "LinkedInScraper" in f.__class__.__name__
        is_jobs = "Jobs" in f.__class__.__name__
        
        should_fire = False
        if is_profile and not has_person_profile:
            should_fire = True
        if is_jobs and not has_company_hiring:
            should_fire = True
            
        if should_fire:
            if (mtd_spend + projected_spend) <= BUDGET_CAP:
                rung3_tasks.append((f, f.fetch(prospect)))
            else:
                results.append(SourceResult(
                    source=f.__class__.__name__,
                    rung=3,
                    status="skipped",
                    reason="budget guard",
                    cards=[],
                    cost_usd=0.0,
                    elapsed_ms=0
                ))
        else:
            results.append(SourceResult(
                source=f.__class__.__name__,
                rung=3,
                status="skipped",
                reason="cheaper rung succeeded",
                cards=[],
                cost_usd=0.0,
                elapsed_ms=0
            ))

    if rung3_tasks:
        rung3_results = await asyncio.gather(*(t for _, t in rung3_tasks), return_exceptions=True)
        for (f, _), res in zip(rung3_tasks, rung3_results):
            if isinstance(res, SourceResult):
                results.append(res)
                if res.cost_usd > 0:
                    add_spend(res.cost_usd)
            elif isinstance(res, Exception):
                logger.error(f"Rung 3 Fetcher raised exception: {type(res).__name__}: {res}")
                results.append(SourceResult(
                    source=f.__class__.__name__,
                    rung=3,
                    status="failed",
                    reason=f"{type(res).__name__}: {res}",
                    cards=[],
                    cost_usd=0.0,
                    elapsed_ms=0
                ))
                
    # Rung 4: Deep mode or total miss
    # Total miss means no usable cards from Rung 0, 1, 3
    total_has_cards = any(len(r.cards) > 0 for r in results)
    if not total_has_cards or deep_mode:
        mtd_spend = get_mtd_spend()
        if (mtd_spend + 0.005) <= BUDGET_CAP:
            rung4_tasks = [(f, f.fetch(prospect)) for f in rung4_fetchers]
            if rung4_tasks:
                rung4_results = await asyncio.gather(*(t for _, t in rung4_tasks), return_exceptions=True)
                for (f, _), res in zip(rung4_tasks, rung4_results):
                    if isinstance(res, SourceResult):
                        results.append(res)
                        if res.cost_usd > 0:
                            add_spend(res.cost_usd)
                    elif isinstance(res, Exception):
                        logger.error(f"Rung 4 Fetcher raised exception: {type(res).__name__}: {res}")
                        results.append(SourceResult(
                            source=f.__class__.__name__,
                            rung=4,
                            status="failed",
                            reason=f"{type(res).__name__}: {res}",
                            cards=[],
                            cost_usd=0.0,
                            elapsed_ms=0
                        ))
        else:
            for f in rung4_fetchers:
                results.append(SourceResult(
                    source=f.__class__.__name__,
                    rung=4,
                    status="skipped",
                    reason="budget guard",
                    cards=[],
                    cost_usd=0.0,
                    elapsed_ms=0
                ))
    else:
        # Skipped because not deep mode and not a total miss
        for f in rung4_fetchers:
            results.append(SourceResult(
                source=f.__class__.__name__,
                rung=4,
                status="skipped",
                reason="cheaper rungs succeeded",
                cards=[],
                cost_usd=0.0,
                elapsed_ms=0
            ))
            
    # Classify social signals
    classifier_result = await classify_social_signals(results)
    if classifier_result.status == "failed":
        logger.warning(f"Social classification failed: {classifier_result.reason}")
    results = classifier_result.results
                
    return results

async def run_end_to_end_pipeline(prospect: Prospect, profile: str = "standard"):
    """
    Instantiates fetchers based on profile, runs the retrieval pipeline,
    and then processes the prospect through ranking, drafting, and verification.
    """
    from zara.fetchers.ats import GreenhouseFetcher, LeverFetcher, AshbyFetcher, SmartRecruitersFetcher, RecruiteeFetcher
    from zara.fetchers.news import GoogleNewsFetcher
    from zara.fetchers.exa import ExaLinkedInFetcher, ExaNewsFetcher, ExaBlogFetcher, ExaEdgarFetcher, ExaYouTubeFetcher
    from zara.fetchers.apify import (
        ApifyLinkedInCompanyFetcher, ApifyLinkedInProfileFetcher, ApifyLinkedInJobsFetcher,
        ApifyLinkedInPostsFetcher, ApifyTwitterFetcher, ApifyInstagramFetcher,
        ApifyTikTokFetcher, ApifyYouTubeFetcher, ApifyRedditFetcher,
        ApifyFacebookFetcher, ApifyProductHuntFetcher, ApifyGoogleMapsFetcher,
        ApifyGoogleSearchFetcher, ApifyIndeedFetcher, ApifyG2CapterraFetcher, ApifyCrunchbaseFetcher
    )
    from zara.s2 import process_prospect

    rung0 = [
        GreenhouseFetcher(), LeverFetcher(), AshbyFetcher(), 
        SmartRecruitersFetcher(), RecruiteeFetcher(), GoogleNewsFetcher()
    ]
    
    rung1 = [
        ExaLinkedInFetcher(), ExaNewsFetcher(), ExaBlogFetcher(),
        ExaEdgarFetcher(), ExaYouTubeFetcher()
    ]
    
    rung2 = []
    rung3 = []
    rung4 = []
    
    if profile in ["standard", "social", "deep"]:
        rung2.append(ApifyLinkedInCompanyFetcher())
        rung3.extend([ApifyLinkedInProfileFetcher(), ApifyLinkedInJobsFetcher()])
        rung4.append(ApifyLinkedInPostsFetcher())
        
    if profile in ["social", "deep"]:
        rung4.extend([ApifyTwitterFetcher(), ApifyYouTubeFetcher(), ApifyRedditFetcher(), ApifyInstagramFetcher()])
        
    if profile == "deep":
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
        deep_mode=(profile == "deep")
    )
    
    draft_res = await process_prospect(prospect, results)
    
    return results, draft_res
