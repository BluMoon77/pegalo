#!/usr/bin/env python3
"""Pégalo — plain-text sticky notes for GNOME. ("Pégalo": stick it.)

Each note is its own small window in the BluMoon palette. Text is plain only:
GtkTextView accepts nothing but plain text from other apps, so Ctrl+V never
brings formatting in. Markdown is shown rendered on every line but the one
being edited (markdown_render.py), and is saved exactly as typed. Notes
autosave to ~/.local/share/pegalo/ as one <id>.txt per note plus index.json
for size, so they stay readable without this app.

Uses only the Python standard library and PyGObject (GTK 4 + libadwaita),
which ship with Ubuntu's GNOME desktop. Nothing to pip-install.

Usage:
    pegalo.py              reopen every saved note (or a fresh one if none)
    pegalo.py --new        open a new note
    pegalo.py --autostart  open saved notes; do nothing if there are none
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Graphene, Gtk, Pango  # noqa: E402

from markdown_render import parse  # noqa: E402

APP_ID = "local.blumoon.Pegalo"

DATA_DIR = Path(
    os.environ.get("PEGALO_DIR")
    or Path(GLib.get_user_data_dir()) / "pegalo"
)
# Where notes lived when the app was called Stickies.
OLD_DATA_DIR = Path(GLib.get_user_data_dir()) / "stickies"
INDEX = DATA_DIR / "index.json"

# One look, the BluMoon palette (the comments give its CSS names). A dark page
# with a moonlight strip along the top, so a note still reads as a note on a
# dark desktop rather than as just another window.
BG_PAGE   = "#171c26"   # --bg-page
BG_HEADER = "#111621"   # --bg-side
LINE      = "#26303f"   # --line
TEXT      = "#e2e8f2"   # --text
TEXT_3    = "#7a8798"   # --text-3
ACCENT    = "#5cbde8"   # --accent (moonlight)
ACCENT_HI = "#8fd6f5"   # --accent-hi
ACCENT_IN = "#1c458d"   # --accent-in
DEFAULT_SIZE = (260, 260)
FONT_PT = 11.5

# Rendered Markdown keeps to the one text color: headings are only bigger and
# bold, and nothing is accent-colored. (A first try that colored everything
# and left the markup faded was too busy to read.)
TAGS = {
    "h1":     dict(weight=Pango.Weight.BOLD, scale=1.35),
    "h2":     dict(weight=Pango.Weight.BOLD, scale=1.18),
    "h3":     dict(weight=Pango.Weight.BOLD, scale=1.05),
    "bold":   dict(weight=Pango.Weight.BOLD),
    "italic": dict(style=Pango.Style.ITALIC),
    "strike": dict(strikethrough=True),
    "code":   dict(family="monospace"),
    "quote":  dict(style=Pango.Style.ITALIC, left_margin=28),
    "done":   dict(foreground=TEXT_3),
    # Last, so they win over the rest: markup that disappears, and list
    # markers kept for their width but drawn over with GLYPHS. GTK ignores
    # the alpha of a tag's color, so "ghost" is the page color instead.
    "hidden": dict(invisible=True),
    "ghost":  dict(foreground=BG_PAGE),
}
GLYPHS = {"bullet": "•", "todo": "☐", "done": "☑"}

SAVE_DELAY_MS = 400

CSS = f"""
window.note {{
    background-color: {BG_PAGE};
    color: {TEXT};
    border-top: 3px solid {ACCENT};
}}
window.note textview,
window.note textview text {{
    background-color: transparent;
    color: {TEXT};
    caret-color: {ACCENT_HI};
    font-size: {FONT_PT}pt;
}}
window.note textview text selection {{ background-color: {ACCENT_IN}; color: {TEXT}; }}
window.note scrolledwindow undershoot {{ background: none; }}
.note-header {{
    background-color: {BG_HEADER};
    border-bottom: 1px solid {LINE};
    min-height: 28px; padding: 0 4px;
}}
.note-header button {{
    color: {TEXT_3};
    min-height: 24px; min-width: 24px; padding: 0;
}}
.note-header button:hover {{ color: {ACCENT}; background-color: alpha({ACCENT}, 0.10); }}
"""


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def _write_atomic(path, text):
    # Write-then-rename, so a crash mid-save never leaves a half-written note.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class Store:
    def __init__(self):
        # Notes from before the rename move over once, in a single rename, so
        # nothing is copied and nothing is left half-moved.
        if "PEGALO_DIR" not in os.environ and OLD_DATA_DIR.is_dir() and not DATA_DIR.exists():
            OLD_DATA_DIR.rename(DATA_DIR)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            self.meta = json.loads(INDEX.read_text(encoding="utf-8"))["notes"]
        except (FileNotFoundError, ValueError, KeyError):
            self.meta = {}
        # Pick up any .txt that lost its index entry (e.g. index deleted by hand).
        for f in DATA_DIR.glob("*.txt"):
            self.meta.setdefault(f.stem, {})

    def ids(self):
        return sorted(self.meta, key=lambda i: self.meta[i].get("created", 0))

    def new_id(self):
        nid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.meta[nid] = {"created": time.time()}
        return nid

    def text(self, nid):
        try:
            return (DATA_DIR / f"{nid}.txt").read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def save(self, nid, text, **meta):
        self.meta.setdefault(nid, {}).update(meta)
        _write_atomic(DATA_DIR / f"{nid}.txt", text)
        self._save_index()

    def delete(self, nid):
        self.meta.pop(nid, None)
        (DATA_DIR / f"{nid}.txt").unlink(missing_ok=True)
        self._save_index()

    def _save_index(self):
        _write_atomic(INDEX, json.dumps({"notes": self.meta}, indent=2))


# ---------------------------------------------------------------------------
# The note's text view: Markdown rendered except where you are typing
# ---------------------------------------------------------------------------
class NoteView(Gtk.TextView):
    """Shows Markdown rendered on every line except the cursor's (or the
    selection's), which shows the markup so it can be edited. When the note
    isn't the active window, every line is rendered.

    Only tags change, never the text, so saving and undo never see the
    rendering. Ctrl+E switches to plain text and back.
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self.plain = False
        self.editing = True
        self._raw = None      # (first, last) line showing its markup
        self._glyphs = []     # (start, end, kind) buffer offsets to draw over
        self._idle = None
        b = self.get_buffer()
        for name, props in TAGS.items():
            b.create_tag(name, **props)
        b.connect("changed", lambda *_: self._schedule())
        b.connect("mark-set", self._on_mark_set)
        # Hidden text is left out of what GTK copies, so the copied lines
        # must show their markup first. Selected lines already do, unless
        # the selection was made a moment ago; catch up before GTK copies.
        self.connect("copy-clipboard", lambda *_: self._restyle())
        self.connect("cut-clipboard", lambda *_: self._restyle())

    def set_editing(self, editing):
        self.editing = editing
        self._schedule()

    def toggle_plain(self):
        self.plain = not self.plain
        self._schedule()

    def _on_mark_set(self, buf, _it, mark):
        if mark in (buf.get_insert(), buf.get_selection_bound()):
            if self._raw_lines() != self._raw:
                self._schedule()

    def _schedule(self):
        # Ahead of GTK's relayout and redraw, so a new line is never drawn
        # unstyled for a frame, and glyphs never drawn at stale offsets.
        if self._idle is None:
            self._idle = GLib.idle_add(self._restyle, priority=GLib.PRIORITY_HIGH_IDLE)

    def _raw_lines(self):
        b = self.get_buffer()
        ins = b.get_iter_at_mark(b.get_insert())
        sel = b.get_iter_at_mark(b.get_selection_bound())
        # Away from the note, a selection still shows its markup so that a
        # middle-click paste elsewhere gets the whole text.
        if not self.editing and ins.equal(sel):
            return None
        lines = sorted((ins.get_line(), sel.get_line()))
        return lines[0], lines[1]

    def _restyle(self):
        if self._idle is not None:
            GLib.source_remove(self._idle)
            self._idle = None
        b = self.get_buffer()
        start, end = b.get_bounds()
        b.remove_all_tags(start, end)
        self._glyphs = []
        self._raw = self._raw_lines()
        if not self.plain:
            first, last = self._raw or (-1, -1)
            off = 0
            text = b.get_text(start, end, True)
            for n, (line, info) in enumerate(zip(text.split("\n"), parse(text))):
                for s, e, tag in info.styles:
                    self._tag(tag, off + s, off + e)
                if info.hang:
                    self._tag(self._hang_tag(line[:info.hang]), off, off + len(line))
                if not first <= n <= last:
                    for s, e in info.hidden:
                        self._tag("hidden", off + s, off + e)
                    if info.glyph:
                        s, e, kind = info.glyph
                        self._tag("ghost", off + s, off + e)
                        self._glyphs.append((off + s, off + e, kind))
                off += len(line) + 1
        self.queue_draw()
        return GLib.SOURCE_REMOVE

    def _hang_tag(self, prefix):
        # A hanging indent: the first line starts at the margin as usual and
        # the lines it wraps onto start under the item's text. The marker is
        # the same characters rendered or not (glyphs draw over them), so
        # one tag per marker width covers both.
        layout = self.create_pango_layout(prefix)
        # The widget's own font isn't the note's: CSS sets that on the text.
        font = layout.get_context().get_font_description()
        font.set_size(int(FONT_PT * Pango.SCALE))
        layout.set_font_description(font)
        width = layout.get_pixel_size()[0]
        name = f"hang-{width}"
        if not self.get_buffer().get_tag_table().lookup(name):
            # A negative indent hangs every line but the first by that much.
            self.get_buffer().create_tag(name, indent=-width)
        return name

    def _tag(self, name, start, end):
        b = self.get_buffer()
        b.apply_tag_by_name(name, b.get_iter_at_offset(start), b.get_iter_at_offset(end))

    def do_snapshot_layer(self, layer, snapshot):
        if layer != Gtk.TextViewLayer.ABOVE_TEXT:
            return
        b = self.get_buffer()
        for start, end, kind in self._glyphs:
            a = self.get_iter_location(b.get_iter_at_offset(start))
            z = self.get_iter_location(b.get_iter_at_offset(end))
            if kind == "rule":
                vis = self.get_visible_rect()
                width = vis.x + vis.width - self.get_right_margin() - a.x
                rect = Graphene.Rect().init(a.x, a.y + a.height // 2, width, 1)
                snapshot.append_color(_rgba(TEXT_3), rect)
                continue
            layout = self.create_pango_layout(GLYPHS[kind])
            w, h = layout.get_pixel_size()
            snapshot.save()
            # Centered on the characters it stands in for.
            snapshot.translate(Graphene.Point().init(
                a.x + (z.x - a.x - w) / 2, a.y + (a.height - h) / 2))
            snapshot.append_layout(layout, _rgba(TEXT_3 if kind == "done" else TEXT))
            snapshot.restore()


def _rgba(spec):
    c = Gdk.RGBA()
    c.parse(spec)
    return c


# ---------------------------------------------------------------------------
# A note window
# ---------------------------------------------------------------------------
class Note(Adw.ApplicationWindow):
    def __init__(self, app, store, nid):
        super().__init__(application=app)
        self.store = store
        self.nid = nid
        meta = store.meta.get(nid, {})
        self._save_source = None

        self.add_css_class("note")
        self.set_default_size(meta.get("width", DEFAULT_SIZE[0]),
                              meta.get("height", DEFAULT_SIZE[1]))
        self.set_size_request(160, 120)

        # Header strip: the whole thing is a drag handle (WindowHandle), with
        # small buttons that stay dim until hovered so the text stays the focus.
        header = Gtk.Box(spacing=2)
        header.add_css_class("note-header")

        new_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="New note (Ctrl+N)")
        new_btn.add_css_class("flat")
        new_btn.set_valign(Gtk.Align.CENTER)
        new_btn.connect("clicked", lambda *_: app.new_note())
        header.append(new_btn)

        header.append(Gtk.Box(hexpand=True))

        del_btn = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Delete note")
        del_btn.add_css_class("flat")
        del_btn.set_valign(Gtk.Align.CENTER)
        del_btn.connect("clicked", self._on_delete)
        header.append(del_btn)

        handle = Gtk.WindowHandle(child=header)

        self.view = NoteView(
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            left_margin=12, right_margin=12, top_margin=8, bottom_margin=12,
        )
        self.buffer = self.view.get_buffer()
        self.buffer.set_text(store.text(nid))
        self.buffer.place_cursor(self.buffer.get_end_iter())
        self.buffer.connect("changed", self._on_changed)

        scroller = Gtk.ScrolledWindow(child=self.view, vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(handle)
        box.append(scroller)
        self.set_content(box)

        self._update_title()
        self.connect("notify::default-width", lambda *_: self._schedule_save())
        self.connect("notify::default-height", lambda *_: self._schedule_save())
        self.connect("close-request", self._on_close)
        # Rendered all the way through once you click away from the note.
        self.connect("notify::is-active",
                     lambda *_: self.view.set_editing(self.is_active()))
        plain = Gio.SimpleAction.new("plain", None)
        plain.connect("activate", lambda *_: self.view.toggle_plain())
        self.add_action(plain)
        self.view.grab_focus()

    # -- saving ---------------------------------------------------------------
    def text(self):
        b = self.buffer
        # True: include the markup hidden by rendering. It is part of the note.
        return b.get_text(b.get_start_iter(), b.get_end_iter(), True)

    def _update_title(self):
        # Shown in Alt+Tab and the overview, where every note otherwise looks alike.
        first = self.text().strip().split("\n", 1)[0][:40]
        self.set_title(first or "Note")

    def _on_changed(self, _buf):
        self._update_title()
        self._schedule_save()

    def _schedule_save(self):
        if self._save_source:
            GLib.source_remove(self._save_source)
        self._save_source = GLib.timeout_add(SAVE_DELAY_MS, self._save_timeout)

    def _save_timeout(self):
        self._save_source = None
        self.save_now()
        return GLib.SOURCE_REMOVE

    def save_now(self):
        if self._save_source:
            GLib.source_remove(self._save_source)
            self._save_source = None
        if self.nid is None:  # already deleted
            return
        self.store.save(self.nid, self.text(),
                        width=self.get_width() or self.get_default_size()[0],
                        height=self.get_height() or self.get_default_size()[1])

    # -- closing / deleting -------------------------------------------------
    def _on_close(self, _win):
        # Closing (Alt+F4) just puts the note away; it comes back next launch.
        # An empty note isn't worth keeping, so it goes.
        if not self.text().strip():
            self._delete_now()
        else:
            self.save_now()
        return False

    def _on_delete(self, _btn):
        if not self.text().strip():
            self._delete_now()
            self.destroy()
            return
        dlg = Adw.AlertDialog(heading="Delete this note?",
                              body="Its text will be gone for good.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("delete", "Delete")
        dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("cancel")
        dlg.set_close_response("cancel")
        dlg.connect("response", self._on_delete_response)
        dlg.present(self)

    def _on_delete_response(self, _dlg, response):
        if response == "delete":
            self._delete_now()
            self.destroy()

    def _delete_now(self):
        if self._save_source:
            GLib.source_remove(self._save_source)
            self._save_source = None
        if self.nid is not None:
            self.store.delete(self.nid)
            self.nid = None


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class Pegalo(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.store = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.store = Store()
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        new = Gio.SimpleAction.new("new-note", None)
        new.connect("activate", lambda *_: self.new_note())
        self.add_action(new)
        self.set_accels_for_action("app.new-note", ["<Control>n"])
        self.set_accels_for_action("win.plain", ["<Control>e"])

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        if "--new" in args:
            self.new_note()
        elif "--autostart" in args:
            self._open_saved()
        else:
            # The launcher reopens every saved note, including ones put away
            # with Alt+F4 while the app kept running — that is the only way
            # back to a closed note.
            self._open_saved()
            if not self.get_windows():
                self.new_note()
            for w in self.get_windows():
                w.present()
        return 0

    def _open_saved(self):
        open_ids = {w.nid for w in self.get_windows() if isinstance(w, Note)}
        for nid in self.store.ids():
            if nid in open_ids:
                continue
            # A blank note left open at logout still has an index entry; drop it.
            # (Only closed ones: an open blank note is one being written now.)
            if not self.store.text(nid).strip():
                self.store.delete(nid)
                continue
            Note(self, self.store, nid).present()

    def new_note(self):
        nid = self.store.new_id()
        note = Note(self, self.store, nid)
        note.present()
        return note


def main():
    return Pegalo().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
