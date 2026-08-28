import asyncio
import json
import os
import argparse
from zara.models import Prospect

def obj_to_dict(obj):
    if hasattr(obj, "__dataclass_fields__"):
        return {k: obj_to_dict(getattr(obj, k)) for k in obj.__dataclass_fields__}
    elif isinstance(obj, list):
        return [obj_to_dict(i) for i in obj]
    else:
        return obj

async def main():
    parser = argparse.ArgumentParser(description="Create a snapshot of fetcher results for a prospect.")
    parser.add_argument("--company", type=str, required=True, help="Company name")
    parser.add_argument("--name", type=str, required=True,
                        help="Prospect's full name. Person-tier retrieval searches for it, and "
                             "the drafter and ranker prompts interpolate it, so a snapshot is "
                             "only valid for the name it was recorded under.")
    parser.add_argument("--title", type=str, default=None, help="Role, optional")
    parser.add_argument("--domain", type=str, default=None, help="Company domain, optional")
    parser.add_argument("--out", type=str, required=True, help="Output file path for the snapshot JSON")
    args = parser.parse_args()

    # This used to be Prospect("Test", args.company), hardcoded. Every snapshot in
    # tests/fixtures was therefore recorded while searching for a person called
    # "Test", which is why not one of them carries a person-authored hook: the
    # person tier had no name to look for. Running it with --company "thin prospect"
    # is also how a basketball interview ended up as a logistics prospect's lead.
    prospect = Prospect(args.name, args.company, title=args.title,
                        company_domain=args.domain)
    
    from zara.fetchers.ats import GreenhouseFetcher, LeverFetcher, AshbyFetcher, SmartRecruitersFetcher, RecruiteeFetcher
    from zara.fetchers.news import GoogleNewsFetcher
    from zara.fetchers.compound import CompoundFetcher
    from zara.fetchers.jina import JinaCompanySiteFetcher
    from zara.fetchers.tavily import TavilyFetcher
    from zara.fetchers.exa import ExaLinkedInFetcher, ExaNewsFetcher, ExaBlogFetcher, ExaEdgarFetcher, ExaYouTubeFetcher

    fetchers = [
        GreenhouseFetcher(), LeverFetcher(), AshbyFetcher(),
        SmartRecruitersFetcher(), RecruiteeFetcher(), GoogleNewsFetcher(),
        CompoundFetcher(), JinaCompanySiteFetcher(),
        ExaLinkedInFetcher(), ExaNewsFetcher(), ExaBlogFetcher(),
        ExaEdgarFetcher(), ExaYouTubeFetcher(), TavilyFetcher()
    ]
    
    print(f"Running {len(fetchers)} Rung-0/1 fetchers for {args.company}...")
    
    tasks = [f.fetch(prospect) for f in fetchers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    valid_results = []
    for f, res in zip(fetchers, results):
        if isinstance(res, Exception):
            print(f"Fetcher {f.__class__.__name__} hard failed: {res}")
            # Do NOT flatten failed to empty. Keep it as failed.
            from zara.models import SourceResult
            valid_results.append(SourceResult(
                source=f.__class__.__name__,
                rung=0, # approximating since it's a mix
                status="failed",
                reason=f"{type(res).__name__}: {res}",
                cards=[],
                cost_usd=0.0,
                elapsed_ms=0
            ))
        else:
            valid_results.append(res)
    
    snapshot = {"prospect": args.company, "person_name": args.name,
                "results": obj_to_dict(valid_results)}
    
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"Snapshot saved to {args.out}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(".env.local")
    asyncio.run(main())
