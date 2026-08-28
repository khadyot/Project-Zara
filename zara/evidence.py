"""Strip fetcher scaffolding off a snippet so the model sees the actual content.

Exa returns LinkedIn posts as markdown with a fixed preamble: a `#` header that
repeats the post's first line, then a profile-bio block, then `---`, then the post
itself, then engagement counts. That preamble is generated furniture, not evidence.

Measured on the real fixtures: of the 400 characters the drafter used to read from
Chermaine Hu's card, roughly 290 were header and bio ("11 years 6 months of total
professional experience. Based in Austin, Texas"), the window cut mid-URL, and the
only substantive sentence in it was her headline -- printed twice, once in the
header and once in the body. The model quoted her own line back at her because it
was the only thing there. Four rounds of prompt patches were spent on that symptom.

This removes scaffolding only. It never rewrites or summarises: the words that
survive are the source's own, which is what `# VERBATIM from source` in models.py
requires.
"""
import re

# [label](https://...) -> label. The URL is noise to a writer and a temptation to
# a model that has been told to be specific.
_MD_LINK = re.compile(r"\[([^\]\[]+)\]\((?:https?|mailto)[^)]*\)")

# "**Keith Smith**: Founder, CEO and President at Payouts Network for 10 years ..."
# Exa emits this bio for the post's AUTHOR, which is why it so often describes
# somebody other than the prospect.
_BIO_LINE = re.compile(
    r"^\*\*[^*]+\*\*:\s.*?(?:\byears?\b|\bexperience\b|\bBased in\b).*$",
    re.M,
)

# Everything from these headings on is metadata about the post, not the post.
_TAIL = re.compile(r"\n##\s*(?:Engagement|Comments|Reactions)\b.*", re.S | re.I)

_BLANKS = re.compile(r"\n{3,}")


def clean_snippet(snippet: str) -> str:
    """The evidence with fetcher furniture removed. Never paraphrases."""
    if not snippet:
        return ""
    text = snippet.replace("\r\n", "\n")

    # The `---` rule is what makes this reliable rather than heuristic: Exa puts it
    # between the generated preamble and the real post, so everything before the
    # first one is furniture by construction. Only trust it when there is something
    # left afterwards -- a card whose body is empty is better shown whole than blanked.
    parts = re.split(r"\n-{3,}\n", text, maxsplit=1)
    if len(parts) == 2 and len(parts[1].strip()) >= 80:
        text = parts[1]
    elif text.lstrip().startswith("# "):
        # No separator. Drop the `#` header only when the body repeats it, which is
        # the duplication case; otherwise the header may be the only content there is.
        head, _, rest = text.lstrip()[2:].partition("\n")
        probe = head.split("|")[0].strip()[:40]
        if probe and probe.lower() in rest.lower():
            text = rest

    text = _TAIL.sub("", text)
    text = _BIO_LINE.sub("", text)
    text = _MD_LINK.sub(r"\1", text)
    return _BLANKS.sub("\n\n", text).strip()
