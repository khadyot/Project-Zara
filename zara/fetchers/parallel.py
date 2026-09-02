"""Parallel Search — one call, several queries, ten results with LLM-ready excerpts.

Parallel takes an `objective` (what we are actually trying to learn) alongside the
literal `search_queries`, which is the part Exa never got: our Exa calls send
keyword `OR` strings to a neural engine, where the operator is embedded as text
rather than parsed.

Billed per REQUEST, not per query, so two or three queries cost one SKU
(`usage: [{'name': 'sku_search', 'count': 1}]` on a two-query call). That is why
the whole plan goes in one call rather than one fetcher per query.
"""
import os
import time

import httpx

from zara.models import Prospect, SignalCard, SourceResult

ENDPOINT = "https://api.parallel.ai/v1/search"

# $1 per 1,000 requests on turbo/fast. Basic/advanced is $5 per 1,000 -- the cheap
# figure quoted around this API is the fast tier only.
COST_PER_REQUEST = {"turbo": 0.001, "fast": 0.001, "base": 0.005, "advanced": 0.005}


class ParallelSearchFetcher:
    """One request carrying the whole query plan."""

    def __init__(self, objective: str | None = None, queries: list[str] | None = None,
                 source_name: str = "ParallelSearch", rung: int = 1,
                 mode: str = "fast"):
        # Both default to None so the product path derives its plan from
        # value_prop at fetch time, while the bake-off can pin an explicit plan and
        # compare engines rather than prompts.
        self.objective = objective
        self.queries = queries
        self.source_name = source_name
        self.rung = rung
        self.mode = mode

    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()
        cost = COST_PER_REQUEST.get(self.mode, 0.005)

        def done(status, reason, cards, spend=0.0):
            return SourceResult(
                source=self.source_name, rung=self.rung, status=status, reason=reason,
                cards=cards, cost_usd=spend, elapsed_ms=int((time.time() - start) * 1000),
            )

        api_key = os.environ.get("PARALLEL_API_KEY")
        if not api_key:
            return done("skipped", "no PARALLEL_API_KEY", [])

        objective, queries = self.objective, self.queries
        if objective is None or queries is None:
            from zara.utils.config import load_value_prop
            from zara.fetchers.queries import build_query_plan
            try:
                vp = load_value_prop()
            except Exception:
                vp = {}
            built_objective, built_queries = build_query_plan(prospect, vp)
            objective = objective if objective is not None else built_objective
            queries = queries if queries is not None else built_queries
        if not queries:
            return done("skipped", "no query could be built for this prospect", [])

        # Result count is not settable on /v1/search: sending `max_results` is
        # rejected outright with `extra_forbidden`, not ignored. Ten is the default
        # and the whole allowance.
        payload = {
            "objective": objective,
            "search_queries": queries,
            "mode": self.mode,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    ENDPOINT, json=payload,
                    headers={"x-api-key": api_key, "Content-Type": "application/json"},
                )
            if r.status_code != 200:
                return done("failed", f"HTTP {r.status_code}: {r.text[:160]}", [])
            data = r.json()
        except Exception as e:
            return done("failed", f"{type(e).__name__}: {e}", [])

        last_name = (prospect.person_name or "").split()[-1] if prospect.person_name else ""
        cards = []
        for res in data.get("results") or []:
            url = res.get("url") or ""
            title = res.get("title") or ""
            snippet = "\n\n".join(e for e in (res.get("excerpts") or []) if e).strip()
            if not snippet:
                continue
            is_person = bool(last_name) and last_name.lower() in f"{title} {snippet}".lower()
            cards.append(SignalCard(
                claim=title or f"Result from {self.source_name}",
                signal_type="person_mention" if is_person else "news",
                source_url=url,
                # Already `YYYY-MM-DD` or null; _compute_recency reads it directly.
                published_date=res.get("publish_date") or None,
                snippet=snippet[:4000],
                tier="person" if is_person else "company",
                source=self.source_name,
            ))

        if not cards:
            return done("empty", "no results with excerpts", [], cost)
        return done("ok", None, cards, cost)
