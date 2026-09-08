"""The demo prefill table has to match what was actually recorded.

Name, company and title all reach the prompts, the prompts are hashed, and the
hash is the fixture key -- so a wrong value here is a FileNotFoundError during a
demo, not a slightly different draft.
"""
import glob

from zara.ui import demo_cast


def test_every_cast_slug_has_a_snapshot_on_disk():
    slugs = {demo_cast.slug_for_path(p) for p in glob.glob("tests/fixtures/*_snapshot.json")}
    for d in demo_cast.CAST:
        assert d.slug in slugs, f"{d.slug} is prefilled but has no snapshot file"


def test_riley_chen_has_no_title():
    """The run store has the crash: the same prospect with a title fails."""
    riley = demo_cast.for_snapshot("tests/fixtures/no_signal_snapshot.json")
    assert riley.title is None


def test_lookup_takes_a_path_or_a_slug():
    a = demo_cast.for_snapshot("tests/fixtures/shipmonk_snapshot.json")
    b = demo_cast.for_snapshot("shipmonk")
    assert a == b
    assert (a.person_name, a.company, a.title) == ("Devin Weil", "ShipMonk", "Chief Financial Officer")


def test_unrecorded_snapshot_prefills_nothing():
    """Guessing a plausible name is worse than leaving the field empty."""
    assert demo_cast.for_snapshot("tests/fixtures/midwest3pl_snapshot.json") is None
    assert demo_cast.for_snapshot(None) is None


def test_demo_set_order_matches_the_recording_script():
    """scripts/record_new_demo.py replays this order, and the repetition check
    makes the order load-bearing."""
    assert [d.slug for d in demo_cast.CAST if d.in_demo_set] == [
        "shipmonk", "episodesix", "no_signal",
    ]
