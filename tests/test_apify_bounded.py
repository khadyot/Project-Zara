"""Retrieval must be bounded, and a timeout is `failed`, not `empty`.

Measured 2026-09-07: ApifyLinkedInCompanyFetcher held one run for 1,988 seconds
while Apify's own log showed the actor SUCCEEDED at 13.5s. RUN_DEADLINE_SECONDS
was 180 and did nothing, because remaining_time() was read only by the model
provider -- so the "run deadline" bounded the LLM calls and left every fetcher in
the pipeline unbounded.
"""
import asyncio
import pytest
from unittest.mock import patch, MagicMock

from zara.fetchers.apify import ApifyBaseFetcher, APIFY_ACTOR_TIMEOUT


@pytest.mark.asyncio
async def test_actor_that_never_returns_is_bounded_and_reported_failed():
    f = ApifyBaseFetcher()
    # `.actor(id)` is evaluated before to_thread is ever called, so the client has
    # to be shaped like one; only the blocking call itself is replaced below.
    f.client = MagicMock()

    async def _hang(*a, **k):
        await asyncio.sleep(30)

    with patch("zara.fetchers.apify.asyncio.to_thread", new=_hang), \
         patch("zara.fetchers.apify.remaining_time", return_value=0.05):
        res = await asyncio.wait_for(
            f._run_actor("actor/x", {}, "ApifyTest", 2, 0.0, "company", "news"),
            timeout=5,            # the test itself must not hang
        )

    assert res.status == "failed", res.status
    assert "timeout" in (res.reason or "").lower()
    assert res.cards == []
    # `empty` would assert we looked and found nothing. We never got to look.
    assert res.status != "empty"


def test_ceiling_exists_and_is_sane():
    assert 0 < APIFY_ACTOR_TIMEOUT <= 120


def test_llm_fixtures_are_only_written_while_recording(tmp_path, monkeypatch):
    """A production run must not edit the test corpus.

    _record_fixture fired after every live response regardless of context, so the
    deployed app wrote into tests/fixtures/ on every run and could overwrite a
    recording the suite replays.
    """
    import os
    from zara.utils import provider

    monkeypatch.chdir(tmp_path)
    (tmp_path / "tests" / "fixtures").mkdir(parents=True)

    def wrote():
        return list((tmp_path / "tests" / "fixtures").glob("*.json"))

    for mode, should_write in (("", False), ("1", False), ("fill", True)):
        for f in wrote():
            f.unlink()
        if mode:
            monkeypatch.setenv("USE_FIXTURES", mode)
        else:
            monkeypatch.delenv("USE_FIXTURES", raising=False)
        provider._record_fixture("p", "s", '{"a":1}', {"prompt_tokens": 1, "completion_tokens": 1})
        assert bool(wrote()) is should_write, f"USE_FIXTURES={mode!r} wrote={bool(wrote())}"
