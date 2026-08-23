import os
import time
import json
import asyncio
from apify_client import ApifyClient
from zara.models import Prospect, SourceResult, SignalCard

class ApifyBaseFetcher:
    def __init__(self):
        self.token = os.getenv("APIFY_API_TOKEN")
        self.client = ApifyClient(self.token) if self.token else None

    async def _run_actor(self, actor_id: str, run_input: dict, source_name: str, rung: int, projected_cost: float, tier: str, signal_type: str) -> SourceResult:
        start = time.time()
        
        # Check for fixtures
        fixture_path = f"tests/fixtures/apify/{actor_id.replace('/', '_')}.json"
        if os.getenv("USE_FIXTURES") == "1" and os.path.exists(fixture_path):
            with open(fixture_path, "r") as f:
                items = json.load(f)
            return SourceResult(
                source=source_name, rung=rung, status="ok", reason=None, 
                cards=self._parse_items(items, source_name, tier, signal_type), 
                cost_usd=projected_cost, elapsed_ms=int((time.time() - start)*1000)
            )

        if not self.client:
            return SourceResult(source=source_name, rung=rung, status="skipped", reason="no APIFY_API_TOKEN", cards=[], cost_usd=0.0, elapsed_ms=0)
            
        try:
            run = await asyncio.to_thread(
                self.client.actor(actor_id).call, run_input=run_input
            )
            dataset_id = run.default_dataset_id
            dataset_items = await asyncio.to_thread(
                self.client.dataset(dataset_id).list_items
            )
            
            # Save fixture
            os.makedirs("tests/fixtures/apify", exist_ok=True)
            with open(fixture_path, "w") as f:
                json.dump(dataset_items.items, f, indent=2)
                
            return SourceResult(
                source=source_name, rung=rung, status="ok", reason=None, 
                cards=self._parse_items(dataset_items.items, source_name, tier, signal_type), 
                cost_usd=projected_cost, elapsed_ms=int((time.time() - start)*1000)
            )
        except Exception as e:
            return SourceResult(source=source_name, rung=rung, status="failed", reason=str(e), cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000))
            
    def _parse_items(self, items: list, source_name: str, tier: str, signal_type: str) -> list[SignalCard]:
        cards = []
        for i, item in enumerate(items[:5]):
            snippet = json.dumps(item)[:1500] # Fallback parser
            cards.append(SignalCard(
                claim=f"Data from {source_name}",
                signal_type=signal_type,
                source_url=item.get("url", ""),
                published_date=None,
                snippet=snippet,
                tier=tier,
                source=source_name
            ))
        return cards

# ---------------------------------------------------------
# RUNG 2: Firmographics
# ---------------------------------------------------------
class ApifyLinkedInCompanyFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"urls": [f"https://www.linkedin.com/company/{prospect.company_domain.split('.')[0] if prospect.company_domain else prospect.company}"]}
        return await self._run_actor("harvestapi/linkedin-company", run_input, "ApifyLinkedInCompany", 2, 0.004, "company", "firmographic")

# ---------------------------------------------------------
# RUNG 3: Profile & Jobs
# ---------------------------------------------------------
class ApifyLinkedInProfileFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        if not prospect.linkedin_url:
            return SourceResult(source="ApifyLinkedInProfile", rung=3, status="skipped", reason="No LinkedIn URL", cards=[], cost_usd=0.0, elapsed_ms=0)
        run_input = {"urls": [prospect.linkedin_url]}
        return await self._run_actor("supreme_coder/linkedin-profile-scraper", run_input, "ApifyLinkedInProfile", 3, 0.003, "person", "profile")

class ApifyLinkedInJobsFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"companyNames": [prospect.company]}
        return await self._run_actor("curious_coder/linkedin-jobs-scraper", run_input, "ApifyLinkedInJobs", 3, 0.004, "company", "hiring")

# ---------------------------------------------------------
# RUNG 4: Deep Search (The rest of the 16 actors)
# ---------------------------------------------------------
class ApifyLinkedInPostsFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        if not prospect.linkedin_url:
            return SourceResult(source="ApifyLinkedInPosts", rung=4, status="skipped", reason="No LinkedIn URL", cards=[], cost_usd=0.0, elapsed_ms=0)
        run_input = {"urls": [prospect.linkedin_url]}
        return await self._run_actor("harvestapi/linkedin-profile-posts", run_input, "ApifyLinkedInPosts", 4, 0.004, "person", "social")

class ApifyTwitterFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"twitterHandles": [prospect.person_name.replace(" ", "")]} # Guessed
        return await self._run_actor("clappi/x-twitter-profile-scraper", run_input, "ApifyTwitter", 4, 0.004, "person", "social")

class ApifyInstagramFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"search": prospect.company}
        return await self._run_actor("apify/instagram-scraper", run_input, "ApifyInstagram", 4, 0.005, "company", "social")

class ApifyTikTokFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"profiles": [prospect.company.replace(" ", "")]}
        return await self._run_actor("clockworks/tiktok-scraper", run_input, "ApifyTikTok", 4, 0.005, "company", "social")

class ApifyYouTubeFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"searchKeywords": f"{prospect.person_name} {prospect.company}"}
        return await self._run_actor("streamers/youtube-scraper", run_input, "ApifyYouTube", 4, 0.005, "company", "social")

class ApifyRedditFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"searches": [prospect.company]}
        return await self._run_actor("harshmaur/reddit-scraper", run_input, "ApifyReddit", 4, 0.004, "company", "social")

class ApifyFacebookFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"startUrls": [{"url": f"https://www.facebook.com/{prospect.company.replace(' ', '')}"}]}
        return await self._run_actor("apify/facebook-pages-scraper", run_input, "ApifyFacebook", 4, 0.004, "company", "social")

class ApifyProductHuntFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"search": prospect.company}
        return await self._run_actor("maximedupre/product-hunt-scraper", run_input, "ApifyProductHunt", 4, 0.004, "company", "news")

class ApifyGoogleMapsFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"searchStringsArray": [prospect.company]}
        return await self._run_actor("compass/crawler-google-places", run_input, "ApifyGoogleMaps", 4, 0.004, "company", "firmographic")

class ApifyGoogleSearchFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"queries": f"{prospect.person_name} {prospect.company}", "resultsPerPage": 2}
        return await self._run_actor("apify/google-search-scraper", run_input, "ApifyGoogleSearch", 4, 0.005, "company", "news")

class ApifyIndeedFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"queries": [prospect.company]}
        return await self._run_actor("misceres/indeed-scraper", run_input, "ApifyIndeed", 4, 0.004, "company", "hiring")

class ApifyG2CapterraFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"queries": [prospect.company]}
        return await self._run_actor("zen-studio/software-review-scraper", run_input, "ApifyG2Capterra", 4, 0.004, "company", "firmographic")

class ApifyCrunchbaseFetcher(ApifyBaseFetcher):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        run_input = {"queries": [prospect.company]}
        return await self._run_actor("pratikdani/crunchbase-companies-bulk-scraper-no-cookies", run_input, "ApifyCrunchbase", 4, 0.004, "company", "firmographic")
