"""Who each demo snapshot was recorded against.

A snapshot holds the retrieval for a company. The person is not in it: the
`prospect` key of most snapshot files is a bare company string, and the name,
company and title are typed into the app at run time. They are also load-bearing
-- all three go into the prompts, the prompts are hashed, and the hash is the
fixture key -- so a snapshot replayed against the wrong person is not a slightly
different demo, it is a FileNotFoundError in front of whoever is watching. The
run store has the evidence: `Riley Chen / Northwind Freight / Chief Financial
Officer` is a crash row, and the identical run with an empty title is an ok row.

That made the identities operator knowledge, kept in a cheat sheet and retyped by
hand. This is that table, in the one place both the app and the recording script
read it from.

Titles are exact, including the ampersand and the full "Chief Financial Officer"
rather than "CFO". `title=None` means the field is left empty, which is a
different recording from any title at all.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DemoIdentity:
    slug: str
    person_name: str
    company: str
    title: str | None
    in_demo_set: bool
    note: str = ""


# Order is load-bearing for recording: scripts/record_new_demo.py replays this
# list in order, and the repetition check compares each draft against the ones
# already drafted in the same batch, so reordering changes the prompts and
# therefore the hashes.
CAST: list[DemoIdentity] = [
    DemoIdentity("shipmonk", "Devin Weil", "ShipMonk", "Chief Financial Officer", True,
                 "guardrail catch: three breach cards excluded"),
    DemoIdentity("episodesix", "Chermaine Hu", "Episode Six",
                 "Co-Founder & Chief Financial Officer", True,
                 "hero run: person_authored, 173 days old"),
    DemoIdentity("no_signal", "Riley Chen", "Northwind Freight", None, True,
                 "honest failure: nothing found, and it says so. Title MUST be empty; "
                 "scripts/seed_demo_runs.py records this person with 'CFO' for the "
                 "history seed, which is a different recording and not the app path"),
    # Dropped from the demo set 2026-08-28, snapshots and fixtures kept on disk.
    DemoIdentity("payoutsnetwork", "Jon Anderson", "Payouts Network",
                 "Chief Financial Officer", False,
                 "dropped: winning card is the announcement of his own hire"),
    DemoIdentity("fulfyld", "AJ Khanijow", "Fulfyld",
                 "Founder & Chief Executive Officer", False,
                 "dropped: best surviving evidence is 665 days old"),
    # Recorded by scripts/seed_demo_runs.py to fill the Run History dashboard.
    # Invented people, public companies -- the stress corpus holds real names and
    # is gitignored because this repo is public.
    DemoIdentity("shipbob", "Alex Rivera", "ShipBob", "VP Finance", False,
                 "history seed only"),
    DemoIdentity("versapay", "Sam Okafor", "Versapay", "Controller", False,
                 "history seed only"),
    DemoIdentity("modern_treasury", "Jordan Ellis", "Modern Treasury",
                 "Director of Ops", False, "history seed only"),
    # midwest3pl and thin_prospect have snapshots but were never recorded against
    # a person on the app path, so there is nothing honest to prefill for them.
]

_BY_SLUG = {d.slug: d for d in CAST}


def slug_for_path(path: str) -> str:
    """`tests/fixtures/shipmonk_snapshot.json` -> `shipmonk`."""
    return path.rsplit("/", 1)[-1].replace("_snapshot.json", "")


def for_snapshot(path_or_slug: str | None) -> DemoIdentity | None:
    """The recorded identity for a snapshot, or None if there is not one.

    None is the honest answer for a snapshot nobody recorded a person against.
    Guessing a name here would put a plausible wrong value in the form, which is
    worse than an empty one.
    """
    if not path_or_slug:
        return None
    return _BY_SLUG.get(slug_for_path(path_or_slug))
