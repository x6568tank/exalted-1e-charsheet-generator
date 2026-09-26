"""
server/quota.py — the disk limit of each account folder on the hosted server.

The human set the limit on 2026-09-11: 10 MB for each person, and on 2026-09-25
50 MB for each campaign folder. A character file is
some kilobytes.

`FolderQuota` is a write guard for `persistence.atomic_write`. Each write of the
server goes through that function: Save, the auto-save, the save of a tab, Save
party, and each write to the homebrew library. Thus one check covers each write
site, and each new one.

The homebrew library of an account is `<account folder>/custom`, thus the limit
of the account covers it. See hosting-state-model.md section 5.3.

⚠ The check applies to paths inside the session root only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

QUOTA_BYTES = 10 * 1024 * 1024

# The limit of each campaign folder. The human set it on 2026-09-25: 50 MB, for
# the maps of the board (docs/plans/p4-board.md).
TABLE_QUOTA_BYTES = 50 * 1024 * 1024

# The name of a table folder starts with this. `TableStore.table_dir` makes it.
# A table folder has the limit `table_limit`.
TABLE_FOLDER_PREFIX = "table-"


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
    """Refuse a write that makes a folder of `root` larger than its limit.

    The folder is the first path component below `root`: one account folder, with
    the limit `limit`, or one campaign folder, with the limit `table_limit`.
    """

    root: Path
    limit: int = QUOTA_BYTES
    table_limit: int = TABLE_QUOTA_BYTES

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
        campaign = parts[0].startswith(TABLE_FOLDER_PREFIX)
        limit = self.table_limit if campaign else self.limit
        if used + size > limit:
            owner = "This campaign" if campaign else "This account"
            raise QuotaExceeded(
                f"{owner} has no space left: {used / 2**20:.1f} MB of "
                f"{limit / 2**20:.1f} MB used. Ask the server admin to remove "
                "old files.")
