import time
import os
import asyncio
import httpx
from zara.models import Prospect, SourceResult, SignalCard
from zara.utils import budget

TAVILY_URL = "https://api.tavily.com/search"


class TavilyFetcher:
    """Paid gap-filler. Fires only when free rungs + Exa yield thin person signal.
    Hard-gated by the monthly credit budget with per-prospect query caps."""

    def __init__(self, force: bool = False):
        self.force = force

    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()

        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return self._result("skipped", "no TAVILY_API_KEY", [], start)

        try:
            n_queries = budget.queries_allowed("tavily")
        except Exception:
            n_queries = 0
        if n_queries < 1:
            return self._result(
                "skipped",
                "tavily budget exhausted — free sources only",
                [], start,
            )

        last_name = prospect.person_name.split()[-1] if prospect.person_name else ""
        query_plan = [
            (f'"{prospect.person_name}" {prospect.company}', "person", "person_mention"),
            (f'"{prospect.company}" news funding announcement 2026', "company", "news"),
        ]
        if prospect.title:
            query_plan.append((f'"{prospect.company}" "{prospect.title}" priorities', "company", "news"))
        query_plan = query_plan[:n_queries]

        async def run_query(query: str, tier: str, signal_type: str):
            try:
                budget.check_and_increment("tavily", 1)
            except budget.BudgetExhausted:
                return None
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    r = await client.post(
                        TAVILY_URL,
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"query": query, "max_results": 4},
                    )
                    r.raise_for_status()
                    return r.json().get("results", [])
            except Exception:
                budget.refund_credits("tavily", 1)
                raise

        outcomes = await asyncio.gather(
            *(run_query(q, tier, st) for q, tier, st in query_plan),
            return_exceptions=True,
        )

        cards: list[SignalCard] = []
        errors: list[str] = []
        for (query, tier, signal_type), out in zip(query_plan, outcomes):
            if isinstance(out, Exception):
                errors.append(f"{type(out).__name__}: {out}")
            elif out is None:
                continue
            else:
                for res in out:
                    title = res.get("title", "")
                    content = res.get("content", "")[:1200]
                    if last_name and last_name.lower() in (title + content).lower():
                        tier_final, st_final = "person", "person_mention"
                    else:
                        tier_final, st_final = tier, signal_type
                    cards.append(SignalCard(
                        claim=title or "Tavily result",
                        signal_type=st_final,
                        source_url=res.get("url", ""),
                        published_date=res.get("published_date"),
                        snippet=content,
                        tier=tier_final,
                        source="Tavily",
                    ))

        elapsed = int((time.time() - start) * 1000)
        if errors and not cards:
            return self._result("failed", "; ".join(errors), [], start)
        if not cards:
            return self._result("empty", "no results", [], start)
        return self._result("ok", None, cards, start)

    def _result(self, status, reason, cards, start) -> SourceResult:
        return SourceResult(
            source="Tavily", rung=1, status=status, reason=reason,
            cards=cards, cost_usd=0.0,
            elapsed_ms=int((time.time() - start) * 1000),
        )
