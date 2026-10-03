# Pégalo — instructions for Claude

Plain-text sticky notes for GNOME: `pegalo.py`, GTK 4 + libadwaita through
PyGObject, plus `markdown_render.py` (no GTK; tested by
`python3 -m unittest test_markdown_render`). Read `README.md` and `pegalo.py`
first. The app was called Stickies before.

## Rules

- **No new dependencies.** Python standard library plus PyGObject (GTK 4,
  libadwaita, Pango, GLib) only. No pip packages, no WebKit.
- **The note file stays exactly what was typed.** `<id>.txt` on disk is the
  source of truth and must never be rewritten by rendering.
- **Work on a branch and open a pull request; never commit to `main`.** The
  maintainer tries the branch on the desktop, and not merging is the undo.
  Push after every commit.
- **Commit messages** end with:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  and PR descriptions end with:
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
- Match the existing code: short functions, comments that say *why*, the
  BluMoon palette constants at the top of `pegalo.py`. US English.
- Refer to people gender-neutrally (they/them) in anything you write.
- Report honestly what you could and couldn't verify. A cloud session has no
  desktop, so say plainly which parts still have to be checked by eye.
- **Don't add GitHub-only machinery** (Actions, workflows, GitHub-specific
  config). GitHub isn't necessarily this repository's permanent home.
