import time
import httpx
import feedparser
import urllib.parse
from zara.models import Prospect, SourceResult, SignalCard
from bs4 import BeautifulSoup

CONTEXT_TERMS = "company OR startup OR funding OR CEO OR revenue OR platform OR software OR hires OR launches"
NOISE_PATTERNS = [
    "highway", "interstate", " i-", "off-ramp", "on-ramp", "exit ramp",
    "police", "crash", "accident", "homicide", "weather", "traffic",
    "bridge", "lane", "road", "construction",
]
AMBIGUOUS_NAMES = ("ramp", "beam", "trail", "summit", "atlas", "cascade", "zen")
BIZ_TERMS = (
    "ceo", "funding", "startup", "software", "app", "platform", "series",
    "million", "billion", "revenue", "hires", "launch", "acquisition",
)


def _looks_like_noise(title: str, company: str) -> bool:
    t = title.lower()
    if any(p in t for p in NOISE_PATTERNS):
        return True
    if company.lower() in AMBIGUOUS_NAMES:
        return not any(w in t for w in BIZ_TERMS)
    return False


class GoogleNewsFetcher:
    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()

        query = f'"{prospect.company}" AND ({CONTEXT_TERMS})'
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10.0)

            feed = feedparser.parse(resp.text)

            if feed.bozo and hasattr(feed, 'bozo_exception'):
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
            for entry in entries[:10]:
                title = entry.get('title', '')
                if _looks_like_noise(title, prospect.company):
                    continue
                desc_text = ""
                if hasattr(entry, 'description'):
                    soup = BeautifulSoup(entry.description, "html.parser")
                    desc_text = soup.get_text(separator=' ', strip=True)

                last_name = prospect.person_name.split()[-1] if prospect.person_name else ""
                tier = "person" if last_name and last_name.lower() in (title + " " + desc_text).lower() else "company"

                cards.append(SignalCard(
                    claim=f"In the news: {title}",
                    signal_type="news",
                    source_url=entry.get("link", url),
                    published_date=entry.get("published", None),
                    snippet=desc_text[:1000],
                    tier=tier,
                    source="GoogleNewsRSS"
                ))
                if len(cards) >= 6:
                    break

            if not cards:
                return SourceResult(
                    source="GoogleNewsRSS", rung=0, status="empty", reason="only noise matched",
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )

            return SourceResult(
                source="GoogleNewsRSS", rung=0, status="ok", reason=None,
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )

        except Exception as e:
            return SourceResult(
                source="GoogleNewsRSS", rung=0, status="failed", reason=str(e),
                cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )
