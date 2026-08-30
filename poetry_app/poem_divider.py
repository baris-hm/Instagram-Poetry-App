"""Simple, replaceable rules for dividing Turkish poems into slides.

The prototype treats a blank line as a stanza boundary and never merges two
stanzas. Long stanzas are split into groups of ``lines_per_slide`` lines. This
is deliberately conservative: future language-aware or layout-aware policies
can replace this module without affecting the HTTP or browser layers.
"""

from __future__ import annotations

import re

DEFAULT_LINES_PER_SLIDE = 4
_STANZA_BREAK = re.compile(r"\n\s*\n+")


def divide_poem(
    poem: str,
    *,
    lines_per_slide: int = DEFAULT_LINES_PER_SLIDE,
) -> list[list[str]]:
    """Return poem lines grouped into carousel slides.

    Whitespace around each line is removed, repeated blank lines count as one
    stanza break, and empty stanzas are ignored.

    Args:
        poem: Raw poem text.
        lines_per_slide: Maximum number of lines from one stanza on a slide.

    Raises:
        TypeError: If ``poem`` is not text.
        ValueError: If ``lines_per_slide`` is less than one.
    """

    if not isinstance(poem, str):
        raise TypeError("poem must be a string")
    if lines_per_slide < 1:
        raise ValueError("lines_per_slide must be at least 1")

    normalized = poem.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    slides: list[list[str]] = []
    for stanza in _STANZA_BREAK.split(normalized):
        lines = [line.strip() for line in stanza.split("\n") if line.strip()]
        slides.extend(
            lines[index : index + lines_per_slide]
            for index in range(0, len(lines), lines_per_slide)
        )

    return slides

