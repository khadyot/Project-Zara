import re
from dataclasses import dataclass
from typing import Literal

import httpx

CORP_SUFFIXES = [
    "inc", "inc.", "llc", "ltd", "ltd.", "corp", "corp.", "co.", "co",
    "company", "technologies", "technology", "labs", "holdings", "group",
    "solutions", "systems", "software",
]

TYPO_HINT_PATTERN = re.compile(r"[0-9]")


@dataclass(frozen=True)
class ResolutionInfo:
    input_company: str
    resolved_company: str
    domain: str | None
    method: Literal["normalized_only", "search_resolved"]
    candidates_considered: int


def normalize_company(raw: str) -> str:
    name = raw.strip()
    name = re.sub(r"\s+", " ", name)
    words = name.split(" ")
    while len(words) > 1 and words[-1].lower().rstrip(".") in [s.rstrip(".") for s in CORP_SUFFIXES]:
        words = words[:-1]
    return " ".join(words).strip()


def slug_variants(name: str) -> list[str]:
    base = normalize_company(name).lower()
    if not base:
        return []
    variants = [
        base.replace(" ", ""),
        base.replace(" ", "-"),
        base.replace(" ", "_"),
        base.replace("'", ""),
        base.replace(" ", "").replace(".", ""),
    ]
    return list(dict.fromkeys(v for v in variants if v))


def domain_variants(name: str) -> list[str]:
    base = normalize_company(name).lower().replace(" ", "").replace("'", "").replace(".", "")
    if not base:
        return []
    return [
        f"{base}.com",
        f"{base.replace(' ', '')}.io",
        f"get{base}.com",
        f"{base}hq.com",
    ]


async def resolve_company_entity(raw_company: str) -> ResolutionInfo:
    """Degrade, never refuse: try search-backed resolution, fall back to pure normalization."""
    normalized = normalize_company(raw_company)
    if not normalized:
        normalized = raw_company.strip() or "unknown"

    import os
    tavily_key = os.environ.get("TAVILY_API_KEY")
    # The suffix condition that used to sit here (`normalized != raw_company.strip()`)
    # meant the lookup only ran when normalize_company had actually stripped
    # something, so every company typed without an Inc/LLC/Ltd never got a domain
    # at all -- which is most of them.
    if tavily_key:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    "https://api.tavily.com/search",
                    headers={"Authorization": f"Bearer {tavily_key}"},
                    # Eight, not three. Removing the suffix gate above let this
                    # code run at last and it still returned domain=None, because
                    # the top three hits for a company name are aggregator profiles
                    # -- Episode Six resolved to preqin.com, builtin.com and
                    # linkedin.com, none of which contain "episodesix". The real
                    # homepage sits below them. Measured 2026-09-02: at n=3 both
                    # Episode Six and ShipMonk fail, at n=8 both resolve.
                    json={"query": f"{normalized} company official website", "max_results": 8},
                )
                r.raise_for_status()
                for res in r.json().get("results", []):
                    url = res.get("url", "")
                    m = re.match(r"https?://(?:www\.)?([a-z0-9.-]+\.[a-z]{2,})", url, re.I)
                    if m:
                        dom = m.group(1).lower()
                        base = normalized.lower().replace(" ", "")
                        if base and (base in dom or dom.split(".")[0] == base.split(" ")[0]):
                            return ResolutionInfo(
                                input_company=raw_company,
                                resolved_company=normalized,
                                domain=dom,
                                method="search_resolved",
                                candidates_considered=len(r.json().get("results", [])),
                            )
        except Exception:
            pass

    return ResolutionInfo(
        input_company=raw_company,
        resolved_company=normalized,
        domain=None,
        method="normalized_only",
        candidates_considered=0,
    )
