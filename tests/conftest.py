"""Suite-wide setup.

The clock is pinned here. Card ages are interpolated into the drafter and hook
prompts, fixtures are keyed on the prompt hash, so an unpinned clock expires the
whole fixture set every time an age ticks over midnight -- which is exactly what
happened on 2026-08-26, when 6 tests went red overnight with no code change and
the failure surfaced as a missing fixture hash rather than as a date problem.

ZARA_NOW is set to the instant the fixtures were recorded, so replayed ages match
the recorded ones exactly and no re-recording is needed. If you deliberately
re-record the fixture set, move this pin to the new recording date.
"""
import os

import pytest

from zara.ranker import FIXTURE_CLOCK


@pytest.fixture(autouse=True)
def _pin_clock(monkeypatch):
    monkeypatch.setenv("ZARA_NOW", FIXTURE_CLOCK)
