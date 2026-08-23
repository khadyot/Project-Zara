import time
import httpx
from zara.models import Prospect, SourceResult, SignalCard
from zara.utils.resolve import domain_variants

JINA_URL = "https://r.jina.ai/"


class JinaCompanySiteFetcher:
    """Company homepage positioning via Jina Reader. Free, keyless, rung-0."""

    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()

        domains = []
        if prospect.company_domain:
            domains.append(prospect.company_domain)
        domains.extend(domain_variants(prospect.company))

        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                for domain in domains:
                    r = await client.get(f"{JINA_URL}https://{domain}", headers={"Accept": "text/plain"})
                    if r.status_code == 200 and len(r.text) > 300:
                        card = SignalCard(
                            claim=f"{prospect.company} website positioning",
                            signal_type="firmographic",
                            source_url=f"https://{domain}",
                            published_date=None,
                            snippet=r.text[:2000],
                            tier="company",
                            source="Jina",
                        )
                        return SourceResult(
                            source="Jina", rung=0, status="ok", reason=None,
                            cards=[card], cost_usd=0.0,
                            elapsed_ms=int((time.time() - start)*1000),
                        )
        except Exception as e:
            return SourceResult(
                source="Jina", rung=0, status="failed", reason=str(e),
                cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000),
            )

        return SourceResult(
            source="Jina", rung=0, status="empty", reason="no reachable company domain",
            cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000),
        )
