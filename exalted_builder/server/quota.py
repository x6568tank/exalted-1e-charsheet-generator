"""
server/quota.py — the disk limit of each account folder on the hosted server.

The limits are 10 MB for each account folder and 50 MB for each campaign folder
(human's ruling).

`FolderQuota` also keeps `MIN_FREE_BYTES` free on the disk of the root. The limits
are per folder, and the number of accounts has no limit. The root is a bind mount,
thus a full disk is the disk of the host.

`FolderQuota` is a write guard for `persistence.atomic_write`. Each write of the
server goes through that function: Save, the auto-save, the save of a tab, Save
party, and each write to the homebrew library. Thus one check covers each write
site, and each new one.

The homebrew library of an account is `<account folder>/custom`, thus the limit
of the account covers it. See hosting-state-model.md section 5.3.

⚠ The check applies to paths inside the session root only.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import db

QUOTA_BYTES = 10 * 1024 * 1024

# The limit of each campaign folder, for the maps of the board (human's ruling,
# docs/plans/p4-board.md).
TABLE_QUOTA_BYTES = 50 * 1024 * 1024

# The free space that each write leaves on the disk of the root (human's choice,
# 2026-10-10).
MIN_FREE_BYTES = 1024 ** 3

# The name of a table folder starts with this. `TableStore.table_dir` makes it.
# A table folder has the limit `table_limit`.
TABLE_FOLDER_PREFIX = "table-"

# The name of an account folder: this, then the account id.
# `CharacterStore.account_dir` makes it.
ACCOUNT_FOLDER_PREFIX = "user-"


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
    """Refuse a write that makes a folder of `root` larger than its limit, or that
    leaves less than `min_free` bytes free on the disk.

    The folder is the first path component below `root`: one account folder, with
    the limit `limit`, or one campaign folder, with the limit `table_limit`.
    """

    root: Path
    limit: int = QUOTA_BYTES
    table_limit: int = TABLE_QUOTA_BYTES
    min_free: int = MIN_FREE_BYTES
    # The account database. With it, a write into the folder of a deleted account is
    # refused. ⚠ The operator deletes from another process, and an open page of the
    # account can still save. See docs/plans/account-management.md.
    db_path: Path | None = None

    def __call__(self, path: Path, size: int) -> None:
        """Raise `QuotaExceeded` if a write of `size` bytes to `path` is over the limit.

        Also raise it if the write leaves less than `min_free` bytes free on the
        disk. A write that replaces a file frees the size of that file. Do nothing
        for a path outside `root`.
        """
        root = self.root.resolve()
        target = path.resolve()
        try:
            parts = target.relative_to(root).parts
        except ValueError:
            return
        if len(parts) < 2:
            return
        if self.db_path is not None and parts[0].startswith(ACCOUNT_FOLDER_PREFIX):
            self._refuse_deleted(parts[0])
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
        # ⚠ The root can be absent before the first save. Measure its nearest
        # parent that exists.
        disk = next(folder for folder in (root, *root.parents) if folder.exists())
        if shutil.disk_usage(disk).free - size < self.min_free:
            raise QuotaExceeded(
                "The server is out of space. Nothing is saved. Tell the server admin.")

    def _refuse_deleted(self, folder: str) -> None:
        """Raise `QuotaExceeded` if `folder` is the folder of a deleted account."""
        suffix = folder[len(ACCOUNT_FOLDER_PREFIX):]
        if suffix.isdigit() and db.username_for(self.db_path, int(suffix)) is None:
            raise QuotaExceeded("This account is deleted. Nothing is saved.")
