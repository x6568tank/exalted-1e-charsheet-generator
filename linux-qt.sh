#!/usr/bin/env bash
# Build the native PySide6 app as a standalone executable -> dist/ExaltedBuilderQt
#
# TWO PRODUCTS build from this tree, one script each:
#   ./linux.sh      ./linux-qt.sh       (Linux/macOS)
#   windows.bat     windows-qt.bat      (Windows)
# ⚠ Keep all FOUR in step — they differ only in the extras and the spec.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/python -m pip install -e ".[qt,desktop]"
.venv/bin/python -m PyInstaller pack/exalted-builder-qt.spec
echo "Build complete: dist/ExaltedBuilderQt"
