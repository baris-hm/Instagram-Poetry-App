"""Simple, replaceable rules for dividing Turkish poems into slides.

The prototype treats a blank line as a stanza boundary and never merges two
stanzas. Long stanzas are split into groups of ``lines_per_slide`` lines. This
is deliberately conservative: future language-aware or layout-aware policies
can replace this module without affecting the HTTP or browser layers.
"""

from __future__ import annotations

import re

DEFAULT_LINES_PER_SLIDE = 4
MAX_BENT_SLIDES = 9
BENT_LINE_COUNTS = {5, 6, 7}
_STANZA_BREAK = re.compile(r"\n\s*\n+")


def poem_lines(poem: str) -> list[str]:
    """Return every non-empty poem line in its original order."""

    if not isinstance(poem, str):
        raise TypeError("poem must be a string")
    normalized = poem.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    return [line.strip() for line in normalized.split("\n") if line.strip()]


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


def divide_bent_poem(
    poem: str,
    *,
    mode: str | int = "automatic",
    slide_count: int = MAX_BENT_SLIDES,
) -> list[list[str]]:
    """Divide a poem for Bent view while preserving the order of its lines.

    Automatic mode balances the lines across at most nine non-empty slides and
    puts the extra lines on the final slides. Fixed modes chunk the poem into
    groups of five, six, or seven lines.
    """

    if slide_count < 1:
        raise ValueError("slide_count must be at least 1")

    lines = poem_lines(poem)
    if not lines:
        return []

    if mode == "automatic":
        base_size, remainder = divmod(len(lines), slide_count)
        sizes = [base_size] * (slide_count - remainder) + [base_size + 1] * remainder
    elif isinstance(mode, int) and not isinstance(mode, bool) and mode in BENT_LINE_COUNTS:
        sizes = [mode] * (len(lines) // mode)
        if len(lines) % mode:
            sizes.append(len(lines) % mode)
    else:
        raise ValueError("Bent mode must be automatic, 5, 6, or 7")

    slides: list[list[str]] = []
    line_index = 0
    for size in sizes:
        if size:
            slides.append(lines[line_index : line_index + size])
            line_index += size
    return slides
