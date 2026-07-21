#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/python -m pip install -e ".[ui,desktop]"
.venv/bin/python -m PyInstaller pack/exalted-builder.spec

echo "Build complete: dist/ExaltedBuilder"
