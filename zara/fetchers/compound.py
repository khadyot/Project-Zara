import time
import os
import asyncio
import httpx
from zara.models import Prospect, SourceResult, SignalCard

GROQ_COMPOUND_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_COMPOUND_MODEL = "groq/compound"


class _CapacitySkip(Exception):
    pass

SYSTEM_PROMPT = (
    "You are a research assistant. Search the web and report only concrete, "
    "recent, factual findings relevant to the query. No speculation. "
    "Format each finding as: TITLE: <short title> | URL: <source url if any> | "
    "FACT: <1-3 sentence factual summary>. List up to 5 findings. "
    "If you find nothing concrete, reply exactly: NO_RESULTS"
)


class CompoundFetcher:
    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return SourceResult(
                source="Compound", rung=0, status="skipped", reason="no GROQ_API_KEY",
                cards=[], cost_usd=0.0, elapsed_ms=0
            )

        queries = [
            (
                f'"{prospect.person_name}" {prospect.company} — recent news, interviews, '
                f"podcast appearances, talks, quotes, promotion, or career moves "
                f"in the last 12 months",
                "person",
                "person_mention",
            ),
            (
                f'"{prospect.company}" — recent company news: funding, product launches, '
                f"acquisitions, layoffs, expansion, leadership changes in the last 12 months",
                "company",
                "news",
            ),
        ]

        async def run_query(query: str, tier: str, signal_type: str) -> list[SignalCard]:
            try:
                text = await self._compound_search(query, api_key)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    raise _CapacitySkip("groq tpm budget consumed")
                raise
            if "NO_RESULTS" in text or not text:
                return []
            return self._parse(text, tier, signal_type)

        outcomes = await asyncio.gather(
            *(run_query(q, tier, st) for q, tier, st in queries),
            return_exceptions=True,
        )

        cards: list[SignalCard] = []
        errors: list[str] = []
        for out in outcomes:
            if isinstance(out, _CapacitySkip):
                return SourceResult(
                    source="Compound", rung=0, status="skipped", reason=f"model capacity: {out}",
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start) * 1000)
                )
            elif isinstance(out, Exception):
                errors.append(f"{type(out).__name__}: {out}")
            else:
                cards.extend(out)

        elapsed = int((time.time() - start) * 1000)

        if errors:
            return SourceResult(
                source="Compound", rung=0, status="failed", reason="; ".join(errors),
                cards=[], cost_usd=0.0, elapsed_ms=elapsed
            )

        if not cards:
            return SourceResult(
                source="Compound", rung=0, status="empty", reason="no results",
                cards=[], cost_usd=0.0, elapsed_ms=elapsed
            )

        return SourceResult(
            source="Compound", rung=0, status="ok", reason=None,
            cards=cards, cost_usd=0.0, elapsed_ms=elapsed
        )

    async def _compound_search(self, query: str, api_key: str) -> str:
        payload = {
            "model": GROQ_COMPOUND_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(GROQ_COMPOUND_URL, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()

    def _parse(self, text: str, tier: str, signal_type: str) -> list[SignalCard]:
        cards = []
        for block in text.split("\n"):
            block = block.strip()
            if not block or "TITLE:" not in block:
                continue
            title, url, fact = "", "", ""
            for part in block.split("|"):
                p = part.strip()
                if p.upper().startswith("TITLE:"):
                    title = p[6:].strip()
                elif p.upper().startswith("URL:"):
                    url = p[4:].strip()
                elif p.upper().startswith("FACT:"):
                    fact = p[5:].strip()
            if title:
                cards.append(SignalCard(
                    claim=title,
                    signal_type=signal_type,
                    source_url=url,
                    published_date=None,
                    snippet=fact or title,
                    tier=tier,
                    source="Compound",
                ))
        return cards[:5]
