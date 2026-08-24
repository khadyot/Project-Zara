import asyncio
from zara.models import Prospect, SourceResult
from zara.utils.budget import get_mtd_spend, add_spend
from zara.classifier import classify_social_signals
import logging

logger = logging.getLogger(__name__)

BUDGET_CAP = 4.00

async def _gather_results(fetcher_tasks: list, results: list[SourceResult], rung: int = 0, on_event=None) -> None:
    if not fetcher_tasks:
        return

    async def _run_one(f, coro):
        try:
            res = await coro
        except Exception as e:
            logger.error(f"Fetcher raised exception: {type(e).__name__}: {e}")
            res = SourceResult(
                source=f.__class__.__name__,
                rung=getattr(f, 'rung', rung),
                status="failed",
                reason=f"{type(e).__name__}: {e}",
                cards=[],
                cost_usd=0.0,
                elapsed_ms=0
            )
        results.append(res)
        if isinstance(res, SourceResult) and res.cost_usd > 0:
            add_spend(res.cost_usd)
        if on_event:
            on_event({
                "type": "source", "name": f.__class__.__name__, "status": res.status,
                "detail": f"{len(res.cards)} cards" if res.status == "ok" else (res.reason or "")[:80],
            })

    if on_event:
        for f, _ in fetcher_tasks:
            on_event({"type": "source", "name": f.__class__.__name__, "status": "running"})
    await asyncio.gather(*(_run_one(f, t) for f, t in fetcher_tasks))

async def run_pipeline(
    prospect: Prospect,
    rung0_fetchers: list,
    rung1_fetchers: list,
    rung2_fetchers: list,
    rung3_fetchers: list,
    rung4_fetchers: list,
    deep_mode: bool = False,
    gap_filler_gate: bool = False,
    on_event=None
) -> list[SourceResult]:
    """
    Executes the retrieval pipeline according to the cost-ordered escalation ladder.
    With gap_filler_gate=True, rung 0 executes first; if it yields >= 2 person-tier
    cards, all paid rungs are skipped with a gap_filler reason.
    """
    results: list[SourceResult] = []

    fetcher_tasks = [(f, f.fetch(prospect)) for f in rung0_fetchers]

    gate_skip_paid = False
    if gap_filler_gate:
        if on_event:
            on_event({"type": "stage", "name": "free sources", "status": "running"})
        await _gather_results(fetcher_tasks, results, rung=0, on_event=on_event)
        fetcher_tasks = []
        person_signal_count = sum(
            1 for r in results if r.status == "ok" for c in r.cards if c.tier == "person"
        )
        gate_skip_paid = person_signal_count >= 2
        if on_event:
            on_event({"type": "stage", "name": "gap-filler gate", "status": "done",
                      "detail": f"{person_signal_count} person signals — paid rungs {'skipped' if gate_skip_paid else 'will run'}"})
        if not gate_skip_paid:
            fetcher_tasks.extend((f, f.fetch(prospect)) for f in rung1_fetchers)
    else:
        # Rung 1 (Always fires, free tier)
        fetcher_tasks.extend((f, f.fetch(prospect)) for f in rung1_fetchers)

    if gate_skip_paid:
        for rung_num, fetchers in ((1, rung1_fetchers), (2, rung2_fetchers), (3, rung3_fetchers), (4, rung4_fetchers)):
            for f in fetchers:
                results.append(SourceResult(
                    source=f.__class__.__name__,
                    rung=rung_num,
                    status="skipped",
                    reason="gap_filler: sufficient person signal from free rungs",
                    cards=[],
                    cost_usd=0.0,
                    elapsed_ms=0
                ))
    else:
        # 1. Budget check for Rung 2
        mtd_spend = get_mtd_spend()
        # Rung 2 projected cost is ~$0.002
        projected_spend = 0.002

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

        # Execute remaining rungs in parallel
        if on_event:
            on_event({"type": "stage", "name": "paid sources", "status": "running"})
        await _gather_results(fetcher_tasks, results, on_event=on_event)

    has_person_profile = False
    has_company_hiring = True   # ruling #7: job postings retired, never escalate for hiring
    discovered_linkedin_url = None
    
    for r in results:
        for card in r.cards:
            if card.tier == "person" and card.signal_type in ("profile", "person_mention"):
                has_person_profile = True
            if not discovered_linkedin_url and "linkedin.com/in/" in card.source_url:
                discovered_linkedin_url = card.source_url
                
    if discovered_linkedin_url and not prospect.linkedin_url:
        from dataclasses import replace
        prospect = replace(prospect, linkedin_url=discovered_linkedin_url)
    
    # Rung 3: LinkedIn Jobs (if no hiring), LinkedIn Profile (if no profile)
    if not gate_skip_paid:
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
    if gate_skip_paid:
        pass # already skipped with gap_filler reason above
    elif not total_has_cards or deep_mode:
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
    if on_event:
        on_event({"type": "stage", "name": "classifying signals", "status": "running"})
    classifier_result = await classify_social_signals(results)
    if on_event:
        on_event({"type": "stage", "name": "classifying signals", "status": "done"})
    if classifier_result.status == "failed":
        logger.warning(f"Social classification failed: {classifier_result.reason}")
    results = classifier_result.results
                
    return results

# One run gets one budget. Baseline for the prior build was p50 5.7s / max 24.5s;
# without a ceiling, ~7 LLM calls each paying their own retry ladder turned that
# into multi-minute hangs.
RUN_DEADLINE_SECONDS = 180.0


async def run_end_to_end_pipeline(prospect: Prospect, profile: str = "standard", settings: dict = None, on_event=None):
    """
    Instantiates fetchers based on profile and settings, runs the retrieval pipeline,
    and then processes the prospect through ranking, drafting, and verification.
    """
    from zara.utils.provider import set_deadline, clear_deadline
    _dl_token = set_deadline(float((settings or {}).get("deadline_seconds") or RUN_DEADLINE_SECONDS))
    try:
        return await _run_end_to_end(prospect, profile, settings, on_event)
    finally:
        clear_deadline(_dl_token)


async def _run_end_to_end(prospect: Prospect, profile: str, settings: dict, on_event):
    from zara.fetchers.ats import GreenhouseFetcher, LeverFetcher, AshbyFetcher, SmartRecruitersFetcher, RecruiteeFetcher
    from zara.fetchers.news import GoogleNewsFetcher
    from zara.fetchers.jina import JinaCompanySiteFetcher
    from zara.fetchers.tavily import TavilyFetcher
    from zara.fetchers.exa import ExaLinkedInFetcher, ExaNewsFetcher, ExaBlogFetcher, ExaEdgarFetcher, ExaYouTubeFetcher
    from zara.fetchers.apify import (
        ApifyLinkedInCompanyFetcher, ApifyLinkedInProfileFetcher,
        ApifyLinkedInPostsFetcher, ApifyTwitterFetcher, ApifyInstagramFetcher,
        ApifyTikTokFetcher, ApifyYouTubeFetcher, ApifyRedditFetcher,
        ApifyFacebookFetcher, ApifyProductHuntFetcher, ApifyGoogleMapsFetcher,
        ApifyGoogleSearchFetcher, ApifyG2CapterraFetcher, ApifyCrunchbaseFetcher
    )
    from zara.s2 import process_prospect
    from zara.utils.resolve import resolve_company_entity
    import dataclasses

    resolution = await resolve_company_entity(prospect.company)
    if resolution.resolved_company and resolution.resolved_company != prospect.company:
        prospect = dataclasses.replace(prospect, company=resolution.resolved_company)
    if resolution.domain and not prospect.company_domain:
        prospect = dataclasses.replace(prospect, company_domain=resolution.domain)

    # CompoundFetcher unwired 2026-08-25: `groq/compound` is agentic and its
    # server-side tool expansion 413s on every call -- 0/5 successes across every
    # recorded run, at ~9-12s of latency each. It also shares the Groq token
    # bucket the ranker needs.
    rung0 = [
        GreenhouseFetcher(), LeverFetcher(), AshbyFetcher(),
        SmartRecruitersFetcher(), RecruiteeFetcher(), GoogleNewsFetcher(),
        JinaCompanySiteFetcher()
    ]

    rung1 = [
        ExaLinkedInFetcher(), ExaNewsFetcher(), ExaBlogFetcher(),
        ExaEdgarFetcher(), ExaYouTubeFetcher(), TavilyFetcher()
    ]
    
    rung2 = []
    rung3 = []
    rung4 = []
    
    if profile in ["standard", "social", "deep"]:
        rung2.append(ApifyLinkedInCompanyFetcher())
        rung3.extend([ApifyLinkedInProfileFetcher()])
        rung4.append(ApifyLinkedInPostsFetcher())
        
    if profile in ["social", "deep"]:
        rung4.extend([ApifyTwitterFetcher(), ApifyYouTubeFetcher(), ApifyRedditFetcher(), ApifyInstagramFetcher()])
        
    if profile == "deep":
        rung4.extend([
            ApifyTikTokFetcher(), ApifyFacebookFetcher(), ApifyProductHuntFetcher(), 
            ApifyGoogleMapsFetcher(), ApifyGoogleSearchFetcher(),
            ApifyG2CapterraFetcher(), ApifyCrunchbaseFetcher()
        ])
    
    
    if settings:
        if not settings.get("use_ats", True):
            ats_names = {"GreenhouseFetcher", "LeverFetcher", "AshbyFetcher", "SmartRecruitersFetcher", "RecruiteeFetcher"}
            rung0 = [f for f in rung0 if type(f).__name__ not in ats_names]
        if not settings.get("use_exa", True):
            rung1 = []
        if not settings.get("use_apify", True):
            rung2 = []
            rung3 = []
            rung4 = []
            
    strictness = settings.get("strictness", "strict") if settings else "strict"
    
    results = await run_pipeline(
        prospect,
        rung0_fetchers=rung0,
        rung1_fetchers=rung1,
        rung2_fetchers=rung2,
        rung3_fetchers=rung3,
        rung4_fetchers=rung4,
        deep_mode=(profile == "deep"),
        gap_filler_gate=True,
        on_event=on_event
    )
    
    vp_override = settings.get("identity") if settings else None
    draft_res = await process_prospect(prospect, results, strictness=strictness, vp_override=vp_override, resolution=resolution, on_event=on_event)

    return results, draft_res
