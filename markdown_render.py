"""Where the Markdown is in a note, as character ranges: no GTK, so it can be
tested anywhere.

pegalo.py uses this to show a note rendered without ever changing its text.
Formatting becomes text tags, the markup characters (**, #, `) are hidden with
an invisible tag, and a list marker is left in place but drawn over with a
symbol, so the buffer and the saved file stay exactly what was typed.

parse() returns one Line per line of the note. Offsets are character offsets
within that line, which match GTK's character offsets (both count code points).
"""

import re
from typing import NamedTuple

FENCE   = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+")
RULE    = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
TASK    = re.compile(r"^\s*([-*+]) (\[([ xX])\])\s")
BULLET  = re.compile(r"^\s*([-*+])\s")
QUOTE   = re.compile(r"^\s*>+\s?")

# Inline spans: group 2 is the content and everything around it is markup.
CODE = re.compile(r"(`+)(.+?)\1")
INLINE = [
    (re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1"), "bold"),
    (re.compile(r"(?<![*\w])(\*)(?=[^\s*])(.+?)(?<=[^\s*])\*(?![*\w])"), "italic"),
    (re.compile(r"(?<![_\w])(_)(?=[^\s_])(.+?)(?<=[^\s_])_(?![_\w])"), "italic"),
    (re.compile(r"(~~)(?=\S)(.+?)(?<=\S)~~"), "strike"),
    (re.compile(r"(\[)([^\]]+)\]\([^)\s]+\)"), "link"),
]


class Line(NamedTuple):
    styles: list    # (start, end, tag): formatting, shown whether or not rendered
    hidden: list    # (start, end): markup that disappears when rendered
    glyph: tuple    # (start, end, kind) drawn over with a symbol, or None


def parse(text):
    lines = []
    in_fence = False
    for line in text.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            lines.append(Line([], [(0, len(line))], None))
        elif in_fence:
            lines.append(Line([(0, len(line), "code")], [], None))
        else:
            lines.append(_parse_line(line))
    return lines


def _parse_line(line):
    styles, hidden, glyph = [], [], None
    n = len(line)
    if m := HEADING.match(line):
        styles.append((0, n, f"h{min(len(m.group(1)), 3)}"))
        hidden.append((0, m.end()))
    elif RULE.match(line):
        return Line([], [], (0, n, "rule"))
    elif m := TASK.match(line):
        done = m.group(3) in "xX"
        # The box is drawn over all of "- [ ]". Nothing before it is hidden:
        # GTK 4.14 misplaces a position that follows hidden text on its line.
        glyph = (m.start(1), m.end(2), "done" if done else "todo")
        if done:
            styles.append((m.end(2), n, "done"))
    elif m := BULLET.match(line):
        glyph = (m.start(1), m.end(1), "bullet")
    elif m := QUOTE.match(line):
        styles.append((0, n, "quote"))
        hidden.append((0, m.end()))
    _parse_inline(line, styles, hidden)
    return Line(styles, hidden, glyph)


def _parse_inline(line, styles, hidden):
    code = []
    for m in CODE.finditer(line):
        code.append((m.start(), m.end()))
        _span(m, "code", styles, hidden)
    for pattern, name in INLINE:
        for m in pattern.finditer(line):
            # Markdown inside `code` is literal.
            if not any(s < m.end() and m.start() < e for s, e in code):
                _span(m, name, styles, hidden)


def _span(m, name, styles, hidden):
    if name != "link":  # a link shows as plain text, in the one text color
        styles.append((m.start(2), m.end(2), name))
    hidden.append((m.start(), m.start(2)))
    hidden.append((m.end(2), m.end()))
