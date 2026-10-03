#!/bin/sh
# Install Pégalo for the current user: launcher, icon and (optionally) autostart.
# No sudo: everything goes under ~/.local and ~/.config. The launcher points at
# this checkout, so a `git pull` updates the app with no reinstall.
#
#   ./install.sh               launcher + icon
#   ./install.sh --autostart   also reopen notes at login
#   ./install.sh --uninstall   remove all three (notes in ~/.local/share/pegalo stay)
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ID=local.blumoon.Pegalo
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
AUTO="$HOME/.config/autostart"

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$APPS/$ID.desktop" "$ICONS/$ID.svg" "$AUTO/$ID.desktop"
    echo "Removed. Notes are still in ~/.local/share/pegalo/."
    exit 0
fi

mkdir -p "$APPS" "$ICONS"
cp "$HERE/$ID.svg" "$ICONS/$ID.svg"

# The file name must match APP_ID in pegalo.py, or GNOME won't group the
# note windows under this launcher's icon.
cat > "$APPS/$ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Pégalo
Comment=Plain-text sticky notes
Exec=python3 $HERE/pegalo.py
Icon=$ID
Categories=Utility;
StartupNotify=true
Actions=new-note;

[Desktop Action new-note]
Name=New Note
Exec=python3 $HERE/pegalo.py --new
DESKTOP

if [ "${1:-}" = "--autostart" ]; then
    mkdir -p "$AUTO"
    cat > "$AUTO/$ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Pégalo
Exec=python3 $HERE/pegalo.py --autostart
Icon=$ID
X-GNOME-Autostart-enabled=true
DESKTOP
fi

update-desktop-database "$APPS" 2>/dev/null || true
# If ~/.local/share/icons/hicolor has an icon-theme.cache (other apps leave
# one), GTK trusts it and never sees an icon added after it was built. Rebuild.
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
echo "Installed. Look for Pégalo in the app grid."
