"""
build_info.py — the line that names the build: the commit and its date.

The deploy writes `BUILD_COMMIT` beside this file: "<short hash> <date>". A dev
machine has no such file, thus the line comes from `git`. See
`docs/deploy/homeserver.md`.

⚠ `pyproject.toml` holds a version that nothing changes. Do not show it: it names
no build.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

STAMP_FILE = Path(__file__).with_name("BUILD_COMMIT")


def _from_git() -> str:
    """Return "<short hash> <date>" of the checkout that holds this file, or ""."""
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(__file__).parent), "log", "-1",
             "--format=%h %cs"],
            capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


@lru_cache(maxsize=1)
def label() -> str:
    """Return "Build <hash> · <date>", or "" when no source names the build.

    Read `STAMP_FILE` first. If it is absent or empty, ask `git`. Keep the result for
    the life of the process.
    """
    try:
        stamp = STAMP_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        stamp = ""
    stamp = stamp or _from_git()
    if not stamp:
        return ""
    commit, _, date = stamp.partition(" ")
    return f"Build {commit} · {date}" if date else f"Build {commit}"
