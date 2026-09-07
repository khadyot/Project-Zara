"""Age has to keep mattering.

Written after a live run put a 2022 press release at the top of a decision card
while a post the prospect had written that month sat below it. The old curve was
`<=180d 1.0 / <=365d 0.95 / <=730d 0.85 / older 0.75`, and the defect was the last
bucket: 0.75 applied identically at 731 days and at 10,000 days, so relevance
stopped decaying entirely after two years.
"""
import pytest
from zara.ranker import (_compute_relevance, recency_multiplier,
                         RECENCY_FLOOR, RECENCY_UNDATED, RECENCY_HALF_LIFE_DAYS)

PW = {"authored": 4, "attributed": 3, "colleague_authored": 2.5,
      "company_action": 2, "database": 1}


def rel(pain, prox, days):
    return _compute_relevance(pain, prox, days, PW)


def test_a_2022_press_release_loses_to_a_post_from_this_month():
    """The exact ordering that was wrong on screen."""
    stale = rel(0.9, "company_action", 1400)
    fresh = rel(0.3, "authored", 30)
    assert stale < fresh, f"stale {stale:.3f} still beats fresh {fresh:.3f}"


def test_a_2019_story_loses_to_this_months_company_news():
    assert rel(0.9, "company_action", 2500) < rel(0.6, "company_action", 30)


def test_decay_does_not_flatten_after_two_years():
    """The actual bug: two very different ages scoring the same."""
    assert recency_multiplier(731) > recency_multiplier(1400) > recency_multiplier(2500)


def test_monotonic_and_bounded():
    prev = 2.0
    for d in [0, 30, 90, 180, 365, 730, 1095, 2000, 5000, 20000]:
        m = recency_multiplier(d)
        assert m <= prev, f"went up at {d}d"
        assert RECENCY_FLOOR <= m <= 1.0
        prev = m


def test_never_reaches_zero():
    """Compass I: an ancient card must still win when it is all there is."""
    assert recency_multiplier(10**6) >= RECENCY_FLOOR > 0


def test_half_life_means_what_it_says():
    assert recency_multiplier(int(RECENCY_HALF_LIFE_DAYS)) == pytest.approx(0.5, abs=0.01)


def test_undated_sits_between_knowing_fresh_and_knowing_ancient():
    """Not knowing is worse than good news and better than bad news."""
    assert recency_multiplier(90) > RECENCY_UNDATED > recency_multiplier(1095)
    assert recency_multiplier(None) == RECENCY_UNDATED


def test_the_hero_prospect_still_wins_by_a_wider_margin():
    """Chermaine's own post (186d) vs the company news that competed with it (286d).

    Pinned because a recency change is exactly the kind of edit that fixes the
    reported bug and silently costs the demo its best run.
    """
    hers = rel(0.9, "authored", 186)
    theirs = rel(0.9, "company_action", 286)
    assert hers > theirs
    assert hers / theirs > 2.0


def test_a_two_year_old_own_hire_card_loses_to_fresh_company_news():
    """Belt and braces behind the own-appointment guardrail."""
    assert rel(0.9, "authored", 655) < rel(0.8, "company_action", 153)
