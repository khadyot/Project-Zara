"""Match each sentence of a draft back to the card it came from.

The draft and its evidence sat in two different panels, so checking a claim meant
reading the email, opening the audit trail, finding the card and comparing by eye.
A reviewer who has to do that for every sentence will stop doing it by the third
prospect, and an unchecked claim is the failure this project exists to prevent.

Deterministic on purpose: content-word overlap between the sentence and the card,
no model call. It costs nothing to run and it cannot itself hallucinate a source.

It also does not cite everything, which is the point. The mechanism sentence and
the ask are ours, not the evidence's, and leaving them unmarked says so. A missing
marker means "we are asserting this", not "we forgot".
"""
import re

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

_STOP = {
    "that", "this", "with", "from", "your", "their", "they", "them", "have", "has",
    "been", "were", "will", "would", "could", "should", "about", "which", "when",
    "what", "into", "than", "then", "there", "here", "some", "most", "more", "such",
    "each", "many", "much", "also", "just", "like", "over", "under", "after",
    "before", "because", "while", "where", "these", "those", "team", "teams",
    "company", "companies", "work", "working", "across", "without", "within",
}

# Below this share of the sentence's content words appearing in the card, the
# match is coincidence. Tuned so "ShipMonk opened an apparel-specific fulfillment
# center" matches its news card and a generic line about reconciliation matches
# nothing.
_MIN_OVERLAP = 0.34
_MIN_HITS = 2


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9\-']+", (text or "").lower())
    return {w for w in words if len(w) >= 4 and w not in _STOP}


def split_sentences(text: str) -> list[str]:
    """Sentences, keeping the greeting and sign-off as their own lines."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        out.extend(s.strip() for s in _SENT_SPLIT.split(line) if s.strip())
    return out


def _card_words(card) -> set[str]:
    return _content_words(f"{getattr(card, 'claim', '')} {getattr(card, 'snippet', '')[:800]}")


def attribute(draft_text: str, cards, winning_card=None) -> tuple[list[tuple[str, int | None]], list]:
    """Return (sentences with a 1-based source number or None, sources used).

    `cards` are SignalCards. The winning card is tried first and wins ties: it is
    the one the draft was actually written from, so when two cards carry the same
    story it should be the one the reviewer is sent to.
    """
    cards = [c for c in (cards or []) if getattr(c, "claim", None)]
    if winning_card is not None:
        cards = [winning_card] + [c for c in cards if c is not winning_card]

    prepared = [(c, _card_words(c)) for c in cards]
    sources: list = []
    marked: list[tuple[str, int | None]] = []

    for sentence in split_sentences(draft_text):
        words = _content_words(sentence)
        best, best_score = None, 0.0
        if words:
            for card, cwords in prepared:
                hits = len(words & cwords)
                if hits < _MIN_HITS:
                    continue
                score = hits / len(words)
                if score > best_score:
                    best, best_score = card, score
        if best is not None and best_score >= _MIN_OVERLAP:
            if best not in sources:
                sources.append(best)
            marked.append((sentence, sources.index(best) + 1))
        else:
            marked.append((sentence, None))

    return marked, sources
