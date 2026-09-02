"""Query planning: what we ask the web, derived from what we sell.

The old fetchers hardcoded their queries as f-strings -- `f"{company} news OR
launch OR funding"` -- which put two things in the wrong place. The `OR` is
keyword-search idiom handed to a neural engine, where it is embedded as literal
text rather than parsed as an operator. And the pain vocabulary lived in Python,
so editing a pain in the Settings UI silently did not change what we searched for.

Retrieval vocabulary is policy. It belongs in value_prop.yaml next to the pains it
serves, for the same reason `never_reference` does: it has to be arguable without
touching code.
"""
from zara.models import Prospect

# Used when value_prop carries no `retrieval.search_terms`. Deliberately generic --
# a config that has not been filled in should still retrieve something, per
# Compass I, rather than searching for nothing.
_FALLBACK_TERMS = ["operations", "finance", "process automation"]


def _terms(value_prop: dict) -> list[str]:
    cfg = (value_prop or {}).get("retrieval") or {}
    terms = [str(t).strip() for t in (cfg.get("search_terms") or []) if str(t).strip()]
    return terms or _FALLBACK_TERMS


def build_query_plan(prospect: Prospect, value_prop: dict) -> tuple[str, list[str]]:
    """(objective, queries) for a provider that takes both.

    Three angles, and they are not interchangeable:

      1. the person in their own words -- the scarce tier, and the only one that
         can ever reach `authored`
      2. what the company did -- datable, and what most news retrieval is good at
      3. how they run the function we sell into -- the pain-shaped query, which is
         the only one that can surface evidence a generic company search misses

    The objective is what a neural engine actually ranks on; the queries are the
    literal strings. Providers that accept only queries can ignore the first
    element.
    """
    company = (prospect.company or "").strip()
    person = (prospect.person_name or "").strip()
    role = (prospect.title or "").strip()
    terms = _terms(value_prop)

    objective = (
        f"Recent public statements, interviews or posts by {person}"
        + (f" ({role})" if role else "")
        + f" at {company}, and announcements about {company} indicating "
        + ", ".join(terms[:4])
        + " workload. Prefer material the person authored or is quoted in."
    )

    queries = []
    if person and company:
        queries.append(f'"{person}" {company} interview podcast post')
    if company:
        queries.append(f'"{company}" announcement expansion funding launch')
        queries.append(f'"{company}" ' + " ".join(terms[:5]))
    return objective, [q for q in queries if q.strip()]
