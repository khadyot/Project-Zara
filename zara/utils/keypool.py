"""The set of Groq credentials, and whose turn it is.

Groq's free tier is per KEY, not per account: 8,000 tokens/minute and 200,000
tokens/day each. One prospect costs ~16k tokens across ~4 calls, which is 1.3x the
per-minute bucket -- so a single key spends ~45 seconds of every run asleep on a
429, and runs out of day after about twelve prospects.

Holding several keys fixes both, but only if they are used differently for each
problem:

  ROUND-ROBIN per call spreads a run's calls across keys so the per-minute bucket
  is never the binding constraint. This is what removes the stall.
  ROTATE-ON-429 moves to the next key the moment one says no, and sleeps only when
  every key has said no. This is what removes the ceiling.

Nothing here ever logs, prints, or returns a key for display. `count()` is the
only thing callers should show a human.
"""
import itertools
import os
import threading

# GROQ_API_KEY_2 .. GROQ_API_KEY_10, plus a comma-separated GROQ_API_KEYS.
_MAX_NUMBERED = 10

_lock = threading.Lock()
_counter = itertools.count()


def groq_keys() -> list[str]:
    """Every configured Groq key, in a stable order, deduplicated.

    Order matters only for reproducibility: the primary key stays first so a
    single-key setup behaves exactly as it did before this module existed.
    """
    found: list[str] = []

    primary = (os.environ.get("GROQ_API_KEY") or "").strip()
    if primary:
        found.append(primary)

    for chunk in (os.environ.get("GROQ_API_KEYS") or "").split(","):
        chunk = chunk.strip()
        if chunk:
            found.append(chunk)

    for i in range(2, _MAX_NUMBERED + 1):
        extra = (os.environ.get(f"GROQ_API_KEY_{i}") or "").strip()
        if extra:
            found.append(extra)

    seen = set()
    ordered = []
    for k in found:
        if k not in seen:
            seen.add(k)
            ordered.append(k)
    return ordered


def count() -> int:
    """How many keys are pooled. Safe to display; a count is not a credential."""
    return len(groq_keys())


def next_start() -> int:
    """The index this call should begin at, advancing round-robin.

    Thread-safe because Streamlit reruns and asyncio.gather both reach this from
    more than one place at once, and two calls starting on the same key is
    precisely the collision the pool exists to avoid.
    """
    with _lock:
        return next(_counter)


def reset():
    """Restart the rotation. For tests only."""
    global _counter
    with _lock:
        _counter = itertools.count()


def groq_key_sources() -> list[tuple[str, str]]:
    """(env var name, key) for each pooled credential, deduplicated, in rotation
    order. The NAME is safe to display; the key is for callers that must probe."""
    found: list[tuple[str, str]] = []

    primary = (os.environ.get("GROQ_API_KEY") or "").strip()
    if primary:
        found.append(("GROQ_API_KEY", primary))

    for idx, chunk in enumerate((os.environ.get("GROQ_API_KEYS") or "").split(","), start=1):
        chunk = chunk.strip()
        if chunk:
            found.append((f"GROQ_API_KEYS[{idx}]", chunk))

    for i in range(2, _MAX_NUMBERED + 1):
        extra = (os.environ.get(f"GROQ_API_KEY_{i}") or "").strip()
        if extra:
            found.append((f"GROQ_API_KEY_{i}", extra))

    seen = set()
    out = []
    for name, k in found:
        if k not in seen:
            seen.add(k)
            out.append((name, k))
    return out
