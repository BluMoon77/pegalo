# Pégalo

Plain-text sticky notes for GNOME, in the dark BluMoon palette. *Pégalo* is
Spanish for "stick it".

Each note is its own small window. **Ctrl+V always pastes plain text**, so
nothing brought in from a web page or a document keeps its fonts and colors.
Notes can be written in Markdown and are shown rendered, but every note is
saved as an ordinary text file, exactly as typed.

## Requirements

Python 3 with GTK 4 (4.12 or newer) and libadwaita (1.5 or newer) through
PyGObject. Nothing to install with pip.

- **Ubuntu 24.04 and later** with the GNOME desktop already has all of it.
  Otherwise: `sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1`
- **Fedora:** `sudo dnf install python3-gobject gtk4 libadwaita`

## Install

```bash
git clone https://github.com/BluMoon77/pegalo.git
cd pegalo
./install.sh --autostart
```

The installer needs no sudo. It puts a launcher and an icon under
`~/.local/share`, and with `--autostart` an entry in `~/.config/autostart` so
your notes reopen when you log in. Leave the flag off if you don't want that.
Then look for Pégalo in the app grid.

The launcher runs the app straight from the folder you cloned, so keep that
folder where it is. To update, `git pull` in it; there is nothing to reinstall.

To remove the launcher, icon and autostart entry, run `./install.sh --uninstall`.
Your notes stay where they are.

### Coming from Stickies

Pégalo used to be called Stickies. Close every note first, so the old app
isn't running, then run `./install.sh` again. It removes the old launcher, and
the first start moves your notes from `~/.local/share/stickies/` to
`~/.local/share/pegalo/`.

## Use

| | |
|---|---|
| `+` or Ctrl+N | New note |
| Ctrl+E | Show the note's plain text, unrendered (again to switch back) |
| Trash icon | Delete the note (asks first if it has text) |
| Alt+F4 | Put the note away; clicking the launcher brings it back |
| Drag the top strip | Move the note |
| Right-click the launcher | New Note |

An empty note is discarded when it's closed. To keep a note above other
windows, use GNOME's own window menu (Alt+Space, then Always on Top).

## Markdown

Every line is shown rendered except the one you're typing on, and all of
them once you click away from the note. The markup characters disappear
rather than fade, and everything stays in one text color.

| You type | You see |
|---|---|
| `# Title`, `## Sub` | a bigger, bold heading |
| `**bold**`, `*italic*`, `~~struck~~` | **bold**, *italic*, ~~struck~~ |
| `` `code` `` and ```` ``` ```` blocks | monospace |
| `- item` | • item |
| `- [ ] task`, `- [x] task` | ☐ task, ☑ task (done ones dimmed) |
| `[text](url)` | text |
| `> quote` | an indented italic quote |
| `---` | a thin line |

Put the cursor on a line (click it, or use the arrow keys) and its markup
comes back for editing. The file on disk is always exactly what you typed;
rendering only changes how it looks.

## Where notes live

`~/.local/share/pegalo/`: one `<id>.txt` per note, plus `index.json` for each
note's size. They are ordinary text files, readable without the app.

## Known limits

- **Notes don't reopen where you left them.** GNOME on Wayland decides where
  windows go; apps can't place their own.
- **No tray icon.** GTK 4 has none. The launcher's New Note action covers it.

## Development

`pegalo.py` is the app. `markdown_render.py` finds the Markdown in a note and
has no GTK import, so its tests run anywhere:

```bash
python3 -m unittest test_markdown_render
```

## License

MIT. See [LICENSE](LICENSE).
