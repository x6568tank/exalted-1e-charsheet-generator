#!/usr/bin/env bash
# Build the NiceGUI webapp as a standalone executable -> dist/ExaltedBuilder
#
# TWO PRODUCTS build from this tree, one script each:
#   ./linux.sh      ./linux-qt.sh       (Linux/macOS)
#   windows.bat     windows-qt.bat      (Windows)
# ⚠ Keep all FOUR in step — they differ only in the extras and the spec.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/python -m pip install -e ".[ui,desktop]"
.venv/bin/python -m PyInstaller pack/exalted-builder.spec
echo "Build complete: dist/ExaltedBuilder"
