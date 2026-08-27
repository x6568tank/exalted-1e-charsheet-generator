#!/usr/bin/env bash
# Build a standalone executable. Two products from one tree:
#   ./linux.sh          the NiceGUI webapp build  -> dist/ExaltedBuilder
#   ./linux.sh qt       the native PySide6 build  -> dist/ExaltedBuilderQt
# windows.bat is the line-for-line equivalent; keep the two in step.
set -euo pipefail
cd "$(dirname "$0")"

TARGET="${1:-web}"

python3 -m venv .venv
case "$TARGET" in
  qt)
    .venv/bin/python -m pip install -e ".[qt,desktop]"
    .venv/bin/python -m PyInstaller pack/exalted-builder-qt.spec
    echo "Build complete: dist/ExaltedBuilderQt"
    ;;
  web)
    .venv/bin/python -m pip install -e ".[ui,desktop]"
    .venv/bin/python -m PyInstaller pack/exalted-builder.spec
    echo "Build complete: dist/ExaltedBuilder"
    ;;
  *)
    echo "usage: $0 [web|qt]" >&2
    exit 2
    ;;
esac
