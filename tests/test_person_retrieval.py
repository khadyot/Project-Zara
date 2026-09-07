"""Retrieval has to actually look for the person.

Found 2026-09-07 by researching Prajit Nanu (Nium) by hand and comparing. The
open web carried an April 2026 interview in which he argues about settlement
infrastructure, almost word for word one of the `silent_breaks` observables. The
product retrieved 40 cards and none of them was it. The only `authored` card in
the run was a 592-day-old LinkedIn post asking his followers what he should write
about.

Three causes, all of them in what we ask rather than in how we score:

  * GoogleNews, a free rung-0 source, queried the COMPANY only. The person's name
    never entered the request, and person tier was assigned retroactively if a
    surname happened to appear in a headline about something else.
  * That fed a second failure. The gap-filler gate decides whether to spend money
    on the paid rungs by counting person-tier cards from rung 0, and rung 0 is
    GoogleNews plus Jina, which is always company tier. The gate protecting spend
    on person signal was driven by a query that could not produce person signal.
  * Parallel's person query carried no category terms, so nothing in the plan ever
    looked for the person arguing about the category -- the exact thing the pains
    were rewritten in September to credit.

No network calls: these check the strings we send, not what comes back.
"""
import pytest

from zara.models import Prospect


PROSPECT = Prospect("Prajit Nanu", "Nium", title="Co-Founder & CEO",
                    company_domain="nium.com")


# --------------------------------------------------------------------------
# Google News, the free source the gate depends on.
# --------------------------------------------------------------------------

def _news_queries(prospect, monkeypatch):
    """The query strings GoogleNewsFetcher actually puts on the wire.

    Driven through the real fetch() with the HTTP client stubbed, rather than by
    re-deriving the strings here -- a test that rebuilds the query it is checking
    passes whatever the fetcher does.
    """
    import asyncio
    import urllib.parse

    import zara.fetchers.news as news

    seen = []

    class _Resp:
        text = ""

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, timeout=None):
            seen.append(urllib.parse.unquote(url.split("?q=", 1)[1].split("&")[0]))
            return _Resp()

    monkeypatch.setattr(news.httpx, "AsyncClient", lambda *a, **k: _Client())
    monkeypatch.setattr(news.feedparser, "parse", lambda _t: type("F", (), {"bozo": 0, "entries": []})())
    asyncio.run(news.GoogleNewsFetcher().fetch(prospect))
    return seen


def test_google_news_asks_about_the_person_by_name(monkeypatch):
    """The whole point. Until this existed, rung 0 could not produce person tier
    except by accident, and the gap-filler gate counted person signal from a
    source structurally incapable of producing it."""
    queries = _news_queries(PROSPECT, monkeypatch)
    assert any("Prajit Nanu" in q for q in queries), (
        f"the person's name never reaches Google News: {queries}"
    )


def test_google_news_still_asks_about_the_company(monkeypatch):
    """Adding the person angle must not cost the company angle. Most datable
    evidence comes from the company query."""
    queries = _news_queries(PROSPECT, monkeypatch)
    assert any("Nium" in q and "Prajit Nanu" not in q for q in queries)
    assert len(queries) == 2, f"expected a company angle and a person angle: {queries}"


def test_google_news_person_query_survives_a_prospect_with_no_name(monkeypatch):
    """Company-only prospects are legitimate input. The person query must drop
    out rather than search for an empty quoted string."""
    queries = _news_queries(Prospect("", "Nium"), monkeypatch)
    assert len(queries) == 1
    assert '""' not in queries[0]


# --------------------------------------------------------------------------
# The gate threshold is a named thing that can be argued with.
# --------------------------------------------------------------------------

def test_the_gap_filler_threshold_is_named():
    """It was an inline `>= 2` deciding whether to spend money."""
    from zara.orchestrator import PERSON_SIGNAL_FLOOR

    assert PERSON_SIGNAL_FLOOR >= 2, (
        "one person-tier card is a single point of failure: a namesake, a "
        "directory row and a colleague's post all read as person tier at "
        "retrieval time and only fail later, in the ranker"
    )


# --------------------------------------------------------------------------
# Exa: neural engine, so stop handing it keyword idiom.
# --------------------------------------------------------------------------

def test_no_exa_query_uses_keyword_or_idiom():
    """queries.py:1-11 records this as a known defect fixed for Parallel and left
    standing in Exa: `OR` handed to a neural engine is embedded as literal text,
    not parsed as an operator."""
    import inspect

    import zara.fetchers.exa as exa

    offenders = []
    for name in dir(exa):
        cls = getattr(exa, name)
        if not (isinstance(cls, type) and name.endswith("Fetcher")):
            continue
        fetch = getattr(cls, "fetch", None)
        if fetch is None or not callable(fetch):
            continue
        for line in inspect.getsource(fetch).splitlines():
            if "query = " in line and " OR " in line:
                offenders.append(f"{name}: {line.strip()}")
    assert not offenders, "keyword OR idiom sent to a neural engine:\n" + "\n".join(offenders)


def test_person_scoped_exa_fetchers_get_more_than_two_results():
    """The first LinkedIn result is nearly always the profile page, which
    _is_directory_row demotes to `database`. At two results that leaves exactly
    one usable slot for the person's actual words."""
    from zara.fetchers.exa import (ExaLinkedInFetcher, ExaNewsFetcher,
                                   ExaYouTubeFetcher)

    assert ExaLinkedInFetcher.num_results > 2
    assert ExaYouTubeFetcher.num_results > 2
    # Company angles are unchanged: one good press release is enough there, and
    # rung 1 latency is paid on every run.
    assert ExaNewsFetcher.num_results == 2


# --------------------------------------------------------------------------
# Parallel: the only open-web person query in the product.
# --------------------------------------------------------------------------

def test_the_person_query_carries_the_category_vocabulary():
    """Retrieval and scoring were asking for different things. The pains credit
    "the prospect publicly arguing about payment rails, settlement, or
    reconciliation infrastructure"; the person query looked only for the name."""
    from zara.fetchers.queries import build_query_plan

    vp = {"retrieval": {"search_terms": ["reconciliation", "month-end close",
                                         "ERP migration"]}}
    _, queries = build_query_plan(PROSPECT, vp)
    person_q = next(q for q in queries if "Prajit Nanu" in q)
    assert "reconciliation" in person_q, (
        "the person query has no category vocabulary, so it can only find that "
        "the person exists, not that they are arguing about what we sell"
    )


def test_the_person_query_stays_short_enough_to_match():
    """Ten results across three queries is the whole Parallel allowance. A long
    tail of weak terms dilutes the name that actually has to match."""
    from zara.fetchers.queries import build_query_plan

    vp = {"retrieval": {"search_terms": ["reconciliation", "month-end close",
                                         "ERP migration", "payment operations",
                                         "billing"]}}
    _, queries = build_query_plan(PROSPECT, vp)
    person_q = next(q for q in queries if "Prajit Nanu" in q)
    assert "payment operations" not in person_q and "billing" not in person_q, (
        "all five search terms reached the person query; two is the budget"
    )


def test_the_company_angles_keep_their_full_vocabulary():
    """Narrowing the person query must not narrow the company one, which is
    where the pain-shaped search actually pays off today."""
    from zara.fetchers.queries import build_query_plan

    vp = {"retrieval": {"search_terms": ["reconciliation", "month-end close",
                                         "ERP migration", "payment operations",
                                         "billing"]}}
    _, queries = build_query_plan(PROSPECT, vp)
    assert any("billing" in q and "Prajit Nanu" not in q for q in queries)
