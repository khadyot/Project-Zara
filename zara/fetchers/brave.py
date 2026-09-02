"""Brave Search LLM Context — dense pre-extracted passages instead of headlines.

Brave returns `grounding.generic[]` (url, title, snippets[]) plus a parallel
`sources{url: {...}}` map carrying `age`. The two must be joined on the URL: the
dates live only in `sources`, and the text lives only in `grounding`.

`age` is NOT guaranteed, whatever the vendor summary says. Measured on 2026-09-02:
a news query returned the full four-format array
`['Friday, April 03, 2026', '2026-04-03', '152 days ago', '<ISO 8601>']`, while a
person query returned `[]` on every result. So the ISO date is a real improvement
where the content is genuinely dated, and absent otherwise -- which is what
`_compute_recency` already handles by returning None.
"""
import os
import time

import httpx

from zara.models import Prospect, SignalCard, SourceResult

ENDPOINT = "https://api.search.brave.com/res/v1/llm/context"

# $5.00 per 1,000 requests, single Search plan rate across web/news/llm-context.
COST_PER_REQUEST = 0.005


def _published(age) -> str | None:
    """The ISO 8601 stamp if Brave gave one, else the plain date, else nothing.

    Order matters: index 3 keeps the time of day, index 1 is `YYYY-MM-DD`.
    `_compute_recency` parses both. An empty list is a real answer -- undated --
    and must stay None rather than becoming a guess.
    """
    if not isinstance(age, (list, tuple)) or not age:
        return None
    if len(age) >= 4 and age[3]:
        return str(age[3])
    if len(age) >= 2 and age[1]:
        return str(age[1])
    return None


class BraveContextFetcher:
    """One query, one SourceResult. The caller owns the query and the labelling."""

    def __init__(self, query: str, source_name: str = "BraveContext",
                 rung: int = 1, count: int = 10, signal_type: str = "news"):
        self.query = query
        self.source_name = source_name
        self.rung = rung
        self.count = count
        self.signal_type = signal_type

    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()

        def done(status, reason, cards, cost=0.0):
            return SourceResult(
                source=self.source_name, rung=self.rung, status=status, reason=reason,
                cards=cards, cost_usd=cost, elapsed_ms=int((time.time() - start) * 1000),
            )

        api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return done("skipped", "no BRAVE_SEARCH_API_KEY", [])

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.get(
                    ENDPOINT,
                    params={"q": self.query, "count": self.count},
                    headers={"Accept": "application/json",
                             "X-Subscription-Token": api_key},
                )
            # A 200 wrapping an error body is `failed`, not `empty` (Compass VII).
            if r.status_code != 200:
                return done("failed", f"HTTP {r.status_code}: {r.text[:160]}", [])
            data = r.json()
        except Exception as e:
            return done("failed", f"{type(e).__name__}: {e}", [])

        generic = (data.get("grounding") or {}).get("generic") or []
        sources = data.get("sources") or {}
        last_name = (prospect.person_name or "").split()[-1] if prospect.person_name else ""

        cards = []
        for item in generic:
            url = item.get("url") or ""
            title = item.get("title") or ""
            # ONE card per URL. One card per snippet would file three or four
            # near-identical cards against the same story, which then compete for
            # the ten-slot card_cap and get culled noisily by the swap test.
            snippet = "\n\n".join(s for s in (item.get("snippets") or []) if s).strip()
            if not snippet:
                continue
            meta = sources.get(url) or {}
            # Tier is inferred, never asserted. A fetcher that hardcodes
            # tier="company" can never reach `authored` and can never satisfy the
            # gap-filler gate -- it is structurally incapable of helping the one
            # tier that is scarce.
            is_person = bool(last_name) and last_name.lower() in f"{title} {snippet}".lower()
            cards.append(SignalCard(
                claim=title or f"Result from {self.source_name}",
                signal_type="person_mention" if is_person else self.signal_type,
                source_url=url,
                published_date=_published(meta.get("age")),
                snippet=snippet[:4000],
                tier="person" if is_person else "company",
                source=self.source_name,
            ))

        if not cards:
            return done("empty", "no grounding chunks returned", [], COST_PER_REQUEST)
        return done("ok", None, cards, COST_PER_REQUEST)
