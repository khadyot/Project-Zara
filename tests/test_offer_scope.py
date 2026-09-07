"""Nothing in the verifier checked what the draft said about US.

Both halves were scoped away from it, and neither by accident:

  * `pass1_grounding` extracts numbers, URLs, quotes and proper nouns and checks
    each against the evidence list. The imported words come FROM the prospect's
    own material, so they are in the evidence and they ground perfectly.
  * `pass2_llm_judge` is told, in its own prompt, to check facts "ABOUT THE
    PROSPECT OR THEIR COMPANY", and explicitly that "the sender's value
    proposition ... must not be flagged".

So a sender overclaim was whitelisted twice, and it happened twice. Flexport's
draft said we "run frontier models to generate pricing predictions". After WHAT
WE DO was rewritten to name a real mechanism, the Nium draft of 2026-09-07 said
we "reconcile fiat and crypto entries" and passed clean.

check_offer_scope is the sibling of check_attribution: both catch a false
statement that contains no ungrounded token, which is the only kind the rest of
the verifier structurally cannot see.
"""
import pytest

from zara.models import (Prospect, RankedCard, RankedProspect, SignalCard)


VP = {
    "product": ("We connect the systems finance and ops already run on, match records "
                "across them, and surface the exceptions a person needs to decide"),
    "sender_name": "Khadyot",
    "sender_company": "Zamp",
    "pains": [{"id": "silent_breaks",
               "statement": "Payment, ledger, and bank reconciliation breaks silently "
                            "and surfaces late"}],
}


def _prospect(snippet, claim="Prajit Nanu on the acquisition"):
    card = SignalCard(claim=claim, signal_type="news",
                      source_url="https://www.linkedin.com/posts/prajitnanu_x",
                      published_date="2026-07-08T00:00:00Z", snippet=snippet,
                      tier="person", source="ExaLinkedIn")
    rc = RankedCard(card=card, pain_match=None, proximity="authored",
                    recency_days=60, score=0.5, excluded=None)
    return RankedProspect(prospect=Prospect("Prajit Nanu", "Nium", "Co-Founder & CEO"),
                          cards=[rc], icp_fit="fit", winning_card=rc, winning_score=0.5)


NIUM_EVIDENCE = ("We did a thing. Today we acquired a crypto company. Cypher brings "
                 "stablecoin and crypto wallet issuing to our fiat payment network.")


# --------------------------------------------------------------------------
# The failures it exists for.
# --------------------------------------------------------------------------

def test_it_blocks_the_sentence_from_the_live_nium_run():
    """Verbatim paragraph 3 from the 2026-09-07 run, which passed clean."""
    from zara.verifier import check_offer_scope

    draft = ("Hi Prajit,\n\nI'm Khadyot from Zamp.\n\n"
             "We pull data from your existing platforms, reconcile fiat and crypto "
             "entries, and flag mismatches, reducing repetitive manual checks.\n\n"
             "Best,\nKhadyot")
    findings = check_offer_scope(draft, _prospect(NIUM_EVIDENCE), VP)
    assert findings, "the crypto claim was not caught"
    assert "crypto" in findings[0]


def test_it_blocks_the_flexport_shape_too():
    """The same defect a fortnight earlier, in a different domain. A rule that
    only knew about crypto would be a patch, not a fix."""
    from zara.verifier import check_offer_scope

    evidence = ("Introducing AI-powered pricing for ocean freight at Flexport. We run "
                "frontier models to generate pricing predictions for every lane.")
    draft = ("Hi Ryan,\n\nI'm Khadyot from Zamp.\n\n"
             "We run frontier models to generate pricing predictions across your "
             "lanes.\n\nBest,\nKhadyot")
    assert check_offer_scope(draft, _prospect(evidence), VP)


# --------------------------------------------------------------------------
# It must not fire on ordinary, honest drafts.
# --------------------------------------------------------------------------

def test_a_draft_that_stays_inside_what_we_do_passes():
    from zara.verifier import check_offer_scope

    draft = ("Hi Prajit,\n\nI'm Khadyot from Zamp. We connect the systems finance and "
             "ops already run on, match records across them, and surface the "
             "exceptions a person needs to decide.\n\n"
             "We match records across those systems and surface the exceptions "
             "someone has to decide on.\n\nBest,\nKhadyot")
    assert check_offer_scope(draft, _prospect(NIUM_EVIDENCE), VP) == []


def test_naming_their_work_is_allowed_when_we_are_not_the_subject():
    """The email is supposed to be about them. Only sentences whose subject is
    "we" or "our" describe our capabilities, and only those are checked."""
    from zara.verifier import check_offer_scope

    draft = ("Hi Prajit,\n\nI'm Khadyot from Zamp.\n\n"
             "I read your post about acquiring the crypto company. I imagine keeping "
             "records aligned across those systems can become increasingly "
             "time-consuming.\n\n"
             "We match records across the systems you already run and surface the "
             "exceptions.\n\nBest,\nKhadyot")
    assert check_offer_scope(draft, _prospect(NIUM_EVIDENCE), VP) == []


def test_the_prospects_own_name_and_company_are_never_an_import():
    """"We" sentences may name who we are writing to."""
    from zara.verifier import check_offer_scope

    draft = "We match records across the systems Nium already runs."
    assert check_offer_scope(draft, _prospect(NIUM_EVIDENCE), VP) == []


def test_it_does_not_fire_on_vocabulary_we_ourselves_use():
    """"reconciliation" is in the pain statement, so a draft using it is speaking
    our language, not borrowing theirs."""
    from zara.verifier import check_offer_scope

    ev = "Nium says reconciliation across ledger and bank systems surfaces late."
    draft = "We match records across those systems so reconciliation breaks surface early."
    assert check_offer_scope(draft, _prospect(ev), VP) == []


# --------------------------------------------------------------------------
# It has to be wired in, not merely defined.
# --------------------------------------------------------------------------

def test_the_check_actually_runs_inside_verify_draft():
    """A check nobody calls is documentation."""
    import inspect

    from zara.verifier import verify_draft

    assert "check_offer_scope" in inspect.getsource(verify_draft)
