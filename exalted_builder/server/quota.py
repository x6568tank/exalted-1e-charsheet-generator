"""
server/quota.py — the disk limit of each account folder on the hosted server.

The human set the limit on 2026-09-11: 10 MB for each person. A character file is
some kilobytes.

`FolderQuota` is a write guard for `persistence.atomic_write`. Each write of the
server goes through that function: Save, the auto-save, the save of a tab and Save
party. Thus one check covers each write site, and each new one.

⚠ The check applies to paths inside the session root only. The homebrew library is
outside it and is one library for the process. Section 5.3 records that.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

QUOTA_BYTES = 10 * 1024 * 1024


class QuotaExceeded(Exception):
    """A write that makes an account folder larger than its limit. The message is
    safe to show to the user."""


def folder_size(folder: Path) -> int:
    """Return the total size in bytes of the files in `folder` and below it."""
    if not folder.is_dir():
        return 0
    return sum(entry.stat().st_size for entry in folder.rglob("*") if entry.is_file())


@dataclass(frozen=True)
class FolderQuota:
    """Refuse a write that makes a folder of `root` larger than `limit` bytes.

    The folder is the first path component below `root`: one account folder.
    """

    root: Path
    limit: int = QUOTA_BYTES

    def __call__(self, path: Path, size: int) -> None:
        """Raise `QuotaExceeded` if a write of `size` bytes to `path` is over the limit.

        A write that replaces a file frees the size of that file. Do nothing for a
        path outside `root`.
        """
        root = self.root.resolve()
        target = path.resolve()
        try:
            parts = target.relative_to(root).parts
        except ValueError:
            return
        if len(parts) < 2:
            return
        replaced = target.stat().st_size if target.is_file() else 0
        used = folder_size(root / parts[0]) - replaced
        if used + size > self.limit:
            raise QuotaExceeded(
                f"This account has no space left: {used / 2**20:.1f} MB of "
                f"{self.limit / 2**20:.1f} MB used. Ask the server admin to remove "
                "old files.")
