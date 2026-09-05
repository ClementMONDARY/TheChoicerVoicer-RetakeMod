#!/bin/sh
# Double-clickable in most file managers if marked executable (chmod +x Install.sh).
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "Python 3 was not found on this system."
    echo "Install it with your distro's package manager, e.g.:"
    echo "  sudo apt install python3      (Debian/Ubuntu)"
    echo "  sudo dnf install python3      (Fedora)"
    echo "  sudo pacman -S python         (Arch)"
    echo "then run this again."
    read -r _ignored
    exit 1
fi

"$PY" install_mod.py "$@"
echo
echo "Press Enter to close."
read -r _ignored
