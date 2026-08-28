"""Turning machine strings into things a human can read on a screen.

None of this is cleanup for its own sake. The Draft page was rendering a
300-character Google News redirect URL, a full httpx exception including the
MDN link it appends, and card claims still wearing the `In the news:` prefix
their fetcher stamped on them. All three are correct as data and unreadable as
interface.

These functions are PRESENTATION ONLY. They must never be written back onto a
model object. `card.claim` in particular feeds deterministic scoring --
`hay = f"{card.claim} {card.snippet}".lower()` in ranker.py -- so editing the
stored value would move the shortlist, and a moved shortlist changes downstream
prompt text and every fixture hash that depends on it.

Kept free of Streamlit imports, for the same reason zara/ui/auth.py is: a
module that cannot be imported without starting a Streamlit runtime is a module
nothing can test.
"""
import re

# What the fetchers stamp on the front of a title. `news.py` writes
# "In the news: {title}", `exa.py` writes "Mentioned on: {title}".
_CLAIM_PREFIXES = ("In the news:", "Mentioned on:")

# httpx ends every HTTPStatusError with this and a docs link. It is the single
# largest source of noise in the Sources panel.
_HTTPX_TAIL = "For more information check:"

_URL_RE = re.compile(r"https?://\S+")
# httpx phrases it as: Client error '413 ...' for url 'https://...'. Removing the
# bare URL alone strands the preposition and an unmatched quote.
_FOR_URL_RE = re.compile(r"\s*for url\s*['\"][^'\"]*['\"]", re.I)
_WS_RE = re.compile(r"\s+")


def _truncate(text: str, limit: int) -> str:
    """Cut on a word boundary when there is one nearby, else hard-cut."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    space = cut.rfind(" ")
    # Only honour the word boundary if it is not throwing away most of the line.
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,.;:-") + "…"


def clean_claim(text: str | None, limit: int = 72) -> str:
    """A card's claim as a person would read it: no fetcher prefix, one line."""
    if not text:
        return ""
    out = _WS_RE.sub(" ", str(text)).strip()
    for p in _CLAIM_PREFIXES:
        if out.lower().startswith(p.lower()):
            out = out[len(p):].strip()
            break
    return _truncate(out, limit)


def short_reason(text: str | None, limit: int = 90) -> str:
    """A failure reason that fits on a row.

    Keeps the part that says what went wrong and drops the parts that only a
    stack trace wants: the docs link httpx appends, any bare URL, and every
    line after the first.
    """
    if not text:
        return ""
    out = str(text)
    head = out.split(_HTTPX_TAIL, 1)[0]
    out = (head or out).splitlines()[0] if (head or out).splitlines() else ""
    out = _FOR_URL_RE.sub("", out)
    out = _URL_RE.sub("", out)
    out = _WS_RE.sub(" ", out).strip().rstrip(" ,.;:-")
    # Removing a clause can strand an opening quote with no partner.
    if out.count("'") % 2:
        out += "'" 
    return _truncate(out, limit)


def link_label(url: str | None, limit: int = 48) -> str:
    """Readable link text: the host, plus a hint of the path when it says anything.

    Google News redirect URLs are ~300 characters of base64 and carry no
    meaning at all, so for those the host alone is the honest label.
    """
    if not url:
        return ""
    raw = str(url).strip()
    body = re.sub(r"^[a-z]+://", "", raw, flags=re.I)
    host, _, path = body.partition("/")
    host = host.lstrip("www.") if host.startswith("www.") else host
    path = path.split("?", 1)[0].strip("/")
    # Deep or opaque paths are identifiers, not titles -- the host is the only
    # part a reader gets anything from, so do not spend a line on the rest.
    if not path or path.count("/") >= 2 or len(path) > 24:
        return host
    return _truncate(f"{host}/{path}", limit)
