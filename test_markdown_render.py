"""Tests for markdown_render.py. Run: python3 -m unittest test_markdown_render"""

import unittest

from markdown_render import parse


def shown(line, info):
    """The line as it reads when rendered: hidden markup removed."""
    gone = set()
    for s, e in info.hidden:
        gone.update(range(s, e))
    return "".join(c for i, c in enumerate(line) if i not in gone)


def one(line):
    [info] = parse(line)
    return info


def styled(line, info, tag):
    return [line[s:e] for s, e, t in info.styles if t == tag]


class TestParse(unittest.TestCase):
    def check(self, line, expect_shown, **tags):
        info = one(line)
        self.assertEqual(shown(line, info), expect_shown)
        for tag, texts in tags.items():
            self.assertEqual(styled(line, info, tag), texts, tag)
        return info

    def test_one_line_per_line(self):
        text = "# a\n\n```\nx\n```\n- b"
        self.assertEqual(len(parse(text)), len(text.split("\n")))

    def test_headings(self):
        self.check("# Title", "Title", h1=["# Title"])
        self.check("## Sub", "Sub", h2=["## Sub"])
        self.check("#### Deep", "Deep", h3=["#### Deep"])
        self.check("#hashtag", "#hashtag", h1=[])

    def test_bold_and_italic(self):
        self.check("a **b** c", "a b c", bold=["b"])
        self.check("a __b__ c", "a b c", bold=["b"])
        self.check("a *b* c", "a b c", italic=["b"])
        self.check("a _b_ c", "a b c", italic=["b"])
        self.check("**b** and *i*", "b and i", bold=["b"], italic=["i"])

    def test_not_emphasis(self):
        self.check("snake_case_name", "snake_case_name", italic=[])
        self.check("2*3*4", "2*3*4", italic=[])
        self.check("a * b * c", "a * b * c", italic=[])

    def test_strike(self):
        self.check("~~gone~~ here", "gone here", strike=["gone"])

    def test_inline_code(self):
        self.check("run `ls -l` now", "run ls -l now", code=["ls -l"])

    def test_markdown_inside_code_is_literal(self):
        self.check("`**not bold**`", "**not bold**", code=["**not bold**"], bold=[])
        self.check("`a_b_c`", "a_b_c", italic=[])

    def test_link_shows_text_only(self):
        info = self.check("see [docs](https://x.y/z) ok", "see docs ok")
        self.assertEqual(info.styles, [])

    def test_glyphs_never_follow_hidden_text(self):
        # A glyph is placed with GTK positions, which go wrong after hidden
        # text on the same line, so nothing may be hidden before it.
        for line in ("- [x] **a**", "* `b`", "  - [ ] *c*"):
            info = one(line)
            self.assertTrue(all(s >= info.glyph[1] for s, _ in info.hidden), line)

    def test_bullets_keep_marker_for_glyph(self):
        for marker in "-*+":
            line = f"{marker} item"
            info = self.check(line, line)
            self.assertEqual(info.glyph, (0, 1, "bullet"))
        info = one("  - nested")
        self.assertEqual(info.glyph, (2, 3, "bullet"))

    def test_numbered_list_left_alone(self):
        info = self.check("1. first", "1. first")
        self.assertIsNone(info.glyph)

    def test_tasks(self):
        info = self.check("- [ ] todo", "- [ ] todo")
        self.assertEqual(info.glyph, (0, 5, "todo"))
        info = self.check("- [x] done", "- [x] done", done=[" done"])
        self.assertEqual(info.glyph, (0, 5, "done"))
        self.assertEqual(one("  * [ ] nested").glyph, (2, 7, "todo"))
        self.assertEqual(one("- [X] done").glyph[2], "done")

    def test_quote(self):
        self.check("> wise words", "wise words", quote=["> wise words"])
        self.check(">> deeper", "deeper")

    def test_rule(self):
        for line in ("---", "***", "- - -", "___"):
            info = one(line)
            self.assertEqual(info.glyph, (0, len(line), "rule"), line)

    def test_fences(self):
        lines = parse("```py\nx = **1**\n```\nafter **b**")
        self.assertEqual(lines[0].hidden, [(0, 5)])
        self.assertEqual(lines[1].styles, [(0, 9, "code")])
        self.assertEqual(lines[1].hidden, [])
        self.assertEqual(lines[2].hidden, [(0, 3)])
        self.assertEqual(styled("after **b**", lines[3], "bold"), ["b"])

    def test_unclosed_fence_runs_to_end(self):
        lines = parse("```\n# not a heading")
        self.assertEqual(lines[1].styles, [(0, 15, "code")])

    def test_blank_and_plain_lines(self):
        for line in ("", "just text", "   "):
            info = one(line)
            self.assertEqual((info.styles, info.hidden, info.glyph), ([], [], None))

    def test_formatting_inside_heading_and_task(self):
        self.check("# A **big** deal", "A big deal", bold=["big"])
        self.check("- [ ] buy `milk`", "- [ ] buy milk", code=["milk"])

    def test_non_ascii_offsets(self):
        self.check("café **olé** ✓", "café olé ✓", bold=["olé"])


if __name__ == "__main__":
    unittest.main()
