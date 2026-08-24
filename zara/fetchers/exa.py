import time
import os
import asyncio
import urllib.parse as urlparse
from exa_py import Exa
from youtube_transcript_api import YouTubeTranscriptApi
from zara.models import Prospect, SourceResult, SignalCard

class ExaBaseFetcher:
    def __init__(self, include_domains=None):
        self.exa = Exa(os.getenv("EXA_API_KEY")) if os.getenv("EXA_API_KEY") else None
        self.include_domains = include_domains

    def _get_skipped_missing_token(self, source: str, rung: int) -> SourceResult:
        return SourceResult(
            source=source, rung=rung, status="skipped", reason="no EXA_API_KEY", 
            cards=[], cost_usd=0.0, elapsed_ms=0
        )

    async def _search_exa(self, query: str, source_name: str, rung: int, signal_type: str, tier: str) -> SourceResult:
        start = time.time()
        
        if not self.exa:
            return self._get_skipped_missing_token(source_name, rung=rung)
            
        try:
            kwargs = {
                "type": "auto",
                "num_results": 2
            }
            if self.include_domains:
                # Validate domains (Exa expects valid URLs/domains, not raw text with spaces)
                valid_domains = [d for d in self.include_domains if " " not in d and "." in d]
                if not valid_domains and self.include_domains:
                    return SourceResult(
                        source=source_name, rung=rung, status="skipped", reason="invalid domains provided", 
                        cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                    )
                if valid_domains:
                    kwargs["include_domains"] = valid_domains

            response = await asyncio.to_thread(
                self.exa.search_and_contents,
                query,
                **kwargs
            )
            
            if not response.results:
                return SourceResult(
                    source=source_name, rung=rung, status="empty", reason="no results", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            cards = []
            for res in response.results:
                snippet = res.text[:1500] if res.text else ""
                cards.append(SignalCard(
                    claim=f"Mentioned on: {res.title or 'Unknown'}",
                    signal_type=signal_type,
                    source_url=res.url,
                    published_date=res.published_date,
                    snippet=snippet,
                    tier=tier,
                    source=source_name
                ))
                
            return SourceResult(
                source=source_name, rung=rung, status="ok", reason=None, 
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )
            
        except Exception as e:
            return SourceResult(
                source=source_name, rung=rung, status="failed", reason=str(e), 
                cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )

class ExaLinkedInFetcher(ExaBaseFetcher):
    def __init__(self):
        super().__init__(include_domains=["linkedin.com"])
        
    async def fetch(self, prospect: Prospect) -> SourceResult:
        query = f"{prospect.person_name} {prospect.company}"
        # LinkedIn profile / authored posts are person_mention or profile
        return await self._search_exa(query, "ExaLinkedIn", 1, "profile", "person")

class ExaNewsFetcher(ExaBaseFetcher):
    def __init__(self):
        super().__init__(include_domains=["techcrunch.com", "forbes.com", "wsj.com", "bloomberg.com", "reuters.com", "cnbc.com", "ft.com"])
        
    async def fetch(self, prospect: Prospect) -> SourceResult:
        query = f"{prospect.company} news OR launch OR funding"
        return await self._search_exa(query, "ExaNews", 1, "news", "company")

class ExaBlogFetcher(ExaBaseFetcher):
    def __init__(self):
        super().__init__()
        
    async def fetch(self, prospect: Prospect) -> SourceResult:
        self.include_domains = [prospect.company_domain] if prospect.company_domain else []
        if not self.include_domains:
            return SourceResult(source="ExaBlog", rung=1, status="empty", reason="no domain", cards=[], cost_usd=0.0, elapsed_ms=0)
        query = f"{prospect.company} product launch OR news"
        return await self._search_exa(query, "ExaBlog", 1, "news", "company")

class ExaEdgarFetcher(ExaBaseFetcher):
    def __init__(self):
        super().__init__(include_domains=["sec.gov"])
        
    async def fetch(self, prospect: Prospect) -> SourceResult:
        query = f"{prospect.company} 8-K OR funding"
        return await self._search_exa(query, "ExaEdgar", 1, "news", "company")

class ExaYouTubeFetcher(ExaBaseFetcher):
    def __init__(self):
        super().__init__(include_domains=["youtube.com"])
        
    async def fetch(self, prospect: Prospect) -> SourceResult:
        query = f"{prospect.person_name} {prospect.company} talk OR interview"
        res = await self._search_exa(query, "ExaYouTube", 1, "social", "person")
        
        # Now supplement the cards with transcripts if possible
        if res.status == "ok":
            for card in res.cards:
                try:
                    # extract video ID
                    parsed = urlparse.urlparse(card.source_url)
                    video_id = urlparse.parse_qs(parsed.query).get("v")
                    if video_id:
                        transcript_list = await asyncio.to_thread(YouTubeTranscriptApi.get_transcript, video_id[0])
                        # concatenate text
                        text = " ".join([t['text'] for t in transcript_list])
                        if text:
                            card.snippet = text[:1500]
                except Exception:
                    pass
        return res
