import time
import httpx
import feedparser
import urllib.parse
from zara.models import Prospect, SourceResult, SignalCard
from bs4 import BeautifulSoup

class GoogleNewsFetcher:
    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()
        
        # Google News RSS expects URL encoded query
        query = f'"{prospect.company}"'
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        
        try:
            async with httpx.AsyncClient(verify=False) as client:
                resp = await client.get(url, timeout=10.0)
            
            feed = feedparser.parse(resp.text)
            
            if feed.bozo and hasattr(feed, 'bozo_exception'):
                # parsing error
                return SourceResult(
                    source="GoogleNewsRSS", rung=0, status="failed", reason=str(feed.bozo_exception), 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
            
            entries = feed.entries
            if not entries:
                return SourceResult(
                    source="GoogleNewsRSS", rung=0, status="empty", reason="no news found", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
            
            cards = []
            for entry in entries[:3]: # top 3 news items
                # parse description HTML if present to keep it verbatim but strip tags
                desc_text = ""
                if hasattr(entry, 'description'):
                    soup = BeautifulSoup(entry.description, "html.parser")
                    desc_text = soup.get_text(separator=' ', strip=True)
                
                cards.append(SignalCard(
                    claim=f"In the news: {entry.get('title', 'Unknown')}",
                    signal_type="news",
                    source_url=entry.get("link", url),
                    published_date=entry.get("published", None),
                    snippet=desc_text[:1000],
                    tier="company",
                    source="GoogleNewsRSS"
                ))
            
            return SourceResult(
                source="GoogleNewsRSS", rung=0, status="ok", reason=None, 
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )
            
        except Exception as e:
            return SourceResult(
                source="GoogleNewsRSS", rung=0, status="failed", reason=str(e), 
                cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )
