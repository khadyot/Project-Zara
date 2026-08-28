"""Cross-draft repetition check.

The drafter writes each email blind to every other email, so no instruction
inside its prompt can stop the set converging: "do not reuse a formula you would
reuse on the next prospect" asks the model to remember something it was never
shown. Four consecutive demo drafts proved it. Three of four opened move 3 with
"We build bots that"; all four closed with "schedule a ... call next week", two
of them character-identical. Every one of those drafts satisfied its prompt.

So the check lives outside the prompt. Drafts in a batch are compared to each
other on shared 4-word runs, and a collision feeds the existing FORMAT
regeneration path in s2 -- the same mechanism a bad word count already uses.

Only phrasing the writer *chose* counts. Word runs that came from the offer, the
CTA, the pain statement or the evidence were handed to it identically for every
prospect, so their repetition is not a tell and is registered as supplied first.

Ordering note: a batch is order-dependent by construction -- the first draft is
never asked to change, later ones are. Keep the prospect order in
scripts/record_new_demo.py fixed, or recorded fixtures will not line up.
"""
import re
from contextlib import contextmanager

NGRAM = 4

_WORD = re.compile(r"[a-z0-9']+")


def _norm_words(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def shingles(text: str) -> set[tuple[str, ...]]:
    """Every run of NGRAM consecutive words, normalized."""
    w = _norm_words(text)
    return {tuple(w[i:i + NGRAM]) for i in range(len(w) - NGRAM + 1)}


def body_of(draft_text: str) -> str:
    """The prose the writer composed: no greeting line, no signature line.

    Both are fixed by the prompt ("Hi <first name>," and "Sign: <sender>"), so
    leaving them in would report a collision on every pair of drafts ever
    written by the same sender.
    """
    lines = [ln.strip() for ln in (draft_text or "").splitlines() if ln.strip()]
    if lines and re.match(r"^(hi|hello|hey|dear)\b", lines[0], re.I):
        lines = lines[1:]
    # A signature is a short trailing line with no sentence punctuation.
    while lines and len(lines[-1].split()) <= 4 and not lines[-1].rstrip().endswith((".", "?", "!")):
        lines = lines[:-1]
    return " ".join(lines)


class DraftBatch:
    """Drafts written for one run, compared against each other."""

    def __init__(self) -> None:
        self._supplied: set[tuple[str, ...]] = set()
        self._seen: list[tuple[str, set[tuple[str, ...]]]] = []

    def register_supplied(self, *texts: str) -> None:
        """Word runs handed to the drafter, which repeat legitimately."""
        for t in texts:
            self._supplied |= shingles(t)

    def _chosen(self, draft_text: str, evidence: str = "") -> set[tuple[str, ...]]:
        # `evidence` is this prospect's own, so it is excluded here rather than
        # via register_supplied. Registering it would make it permanently
        # supplied for the whole batch, and a later draft that genuinely lifted
        # a phrase from THIS prospect's evidence would then go unreported.
        return shingles(body_of(draft_text)) - self._supplied - shingles(evidence)

    def check(self, draft_text: str, evidence: str = "") -> list[str]:
        """Feedback notes if this draft repeats an earlier one in the batch."""
        mine = self._chosen(draft_text, evidence)
        notes = []
        for label, theirs in self._seen:
            overlap = mine & theirs
            if not overlap:
                continue
            # Longest runs first: the most damning evidence, and the most useful
            # thing to hand back to the writer.
            worst = sorted(overlap, key=lambda g: (-len(g), g))[:3]
            phrases = ", ".join('"' + " ".join(g) + '"' for g in worst)
            notes.append(
                f"repeats the email already written for {label}: {phrases}. "
                "Rewrite the sentences containing these so the two emails share no "
                "phrasing. Do not swap single words: change the construction."
            )
        return notes

    def overlap_size(self, draft_text: str, evidence: str = "") -> int:
        """How many chosen word runs this draft shares with earlier ones. Lets a
        caller prefer a rewrite that repeats less, instead of discarding it for
        failing to repeat nothing."""
        mine = self._chosen(draft_text, evidence)
        return sum(len(mine & theirs) for _, theirs in self._seen)

    def record(self, label: str, draft_text: str, evidence: str = "") -> None:
        self._seen.append((label, self._chosen(draft_text, evidence)))


_ACTIVE: DraftBatch | None = None


def active() -> DraftBatch | None:
    """The batch in progress, or None. None means the check is off, which is the
    default: single runs have nothing to compare against, and the test suite must
    stay independent of the order its cases happen to execute in."""
    return _ACTIVE


@contextmanager
def batch():
    global _ACTIVE
    prev = _ACTIVE
    _ACTIVE = DraftBatch()
    try:
        yield _ACTIVE
    finally:
        _ACTIVE = prev


@contextmanager
def using(b: "DraftBatch"):
    """Run against a batch the caller owns and keeps.

    The app scores one prospect per run, so batch() -- which makes a fresh,
    empty batch -- can never fire there: there is nothing to compare against
    inside a single run. The comparison the app needs is against the OTHER
    prospects drafted in the same sitting, which means the batch has to outlive
    the run and live in st.session_state. Hence a batch supplied from outside.
    """
    global _ACTIVE
    prev = _ACTIVE
    _ACTIVE = b
    try:
        yield b
    finally:
        _ACTIVE = prev
