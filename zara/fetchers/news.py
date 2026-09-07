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


def _rss_url(query: str) -> str:
    return ("https://news.google.com/rss/search?q="
            + urllib.parse.quote(query)
            + "&hl=en-US&gl=US&ceid=US:en")


class GoogleNewsFetcher:
    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()

        # TWO queries, not one. Until 2026-09-07 this asked only about the
        # company, so the prospect's name never entered the request and person
        # tier was assigned retroactively, if the surname happened to turn up in
        # a headline that was not about them.
        #
        # That mattered far beyond this fetcher. The gap-filler gate in
        # orchestrator.py decides whether to spend money on the paid rungs by
        # counting person-tier cards from rung 0, and rung 0 is this plus Jina,
        # which is always company tier. So the gate protecting spend on person
        # signal was driven entirely by a query that could not produce person
        # signal. On the Prajit Nanu / Nium run the only `authored` card in 40
        # was a 592-day-old LinkedIn post.
        #
        # The person query is deliberately bare -- name and company, nothing
        # else. Google News is a keyword index, and every extra term narrows a
        # result set that is already thin for anyone who is not a public figure.
        queries = [f'"{prospect.company}" AND ({CONTEXT_TERMS})']
        if (prospect.person_name or "").strip():
            queries.append(f'"{prospect.person_name}" "{prospect.company}"')

        url = _rss_url(queries[0])

        try:
            entries = []
            seen_links = set()
            bozo_reason = None
            async with httpx.AsyncClient() as client:
                for q in queries:
                    try:
                        resp = await client.get(_rss_url(q), timeout=10.0)
                    except Exception as e:
                        # One angle failing is not the fetcher failing. Only an
                        # empty-handed return is reported as a failure below.
                        bozo_reason = bozo_reason or str(e)
                        continue
                    feed = feedparser.parse(resp.text)
                    if feed.bozo and hasattr(feed, "bozo_exception"):
                        bozo_reason = bozo_reason or str(feed.bozo_exception)
                        continue
                    for entry in feed.entries[:10]:
                        link = entry.get("link", "")
                        if link and link in seen_links:
                            continue
                        seen_links.add(link)
                        entries.append(entry)

            if not entries:
                return SourceResult(
                    source="GoogleNewsRSS", rung=0,
                    status="failed" if bozo_reason else "empty",
                    reason=bozo_reason or "no news found",
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )

            cards = []
            for entry in entries:
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
                # Was 6, sized when there was one query. Two angles need room
                # for both, or the company query fills the quota before the
                # person query is read at all -- which would leave the gate
                # counting person signal that never got a slot.
                if len(cards) >= 10:
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
