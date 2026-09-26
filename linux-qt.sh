#!/usr/bin/env bash
# Build the native PySide6 app as a standalone executable -> dist/ExaltedBuilderQt
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/python -m pip install -e ".[qt,desktop]"
.venv/bin/python -m PyInstaller pack/exalted-builder-qt.spec
echo "Build complete: dist/ExaltedBuilderQt"
