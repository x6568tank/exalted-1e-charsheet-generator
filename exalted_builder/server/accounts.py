"""
server/accounts.py — the delete of an account. The `/account` page and the operator
command `server/users.py delete` both call `delete_account`.

The human ruled on 2026-09-26 (docs/plans/account-management.md):

  * Each campaign that the account runs is deleted by `TableStore.delete`. Each
    other player keeps a solo copy (p3-tables.md section 10).
  * The username is free after the delete.

⚠ The `users` row stays, as a tombstone (`db.tombstone_user`). `users.id` has no
AUTOINCREMENT, thus a removed newest row gives its id to the next signup, with the
log lines and the notes files of that id.
"""

from __future__ import annotations

from contextlib import closing
import shutil

from . import db
from .characters import CharacterStore
from .session import SessionRegistry
from .tables import STORYTELLER, TableStore


def campaigns_run(tables: TableStore, user_id: int) -> list[tuple[str, int]]:
    """Return the name and the member count of each campaign that `user_id` runs.

    The delete of the account deletes these campaigns. The confirm names them.
    """
    return [(row.name, len(tables.members(row.id))) for row in tables.for_user(user_id)
            if row.storyteller_id == user_id]


def delete_account(user_id: int, *, characters: CharacterStore, tables: TableStore,
                   sessions: SessionRegistry | None = None) -> None:
    """Delete account `user_id` and each thing that it owns. Keep its tombstone row.

    Delete each campaign that it runs, and leave each other campaign. Remove its
    notes, its requests, its characters and its folder. Stop each open page of its
    characters from writing again: give `sessions` when the server calls this.
    A second call does nothing more.
    """
    for row in tables.for_user(user_id):
        if tables.access(user_id, row.id) == STORYTELLER:
            tables.delete(user_id, row.id)
        else:
            tables.notes_path(row.id, user_id).unlink(missing_ok=True)
            tables.leave(user_id, row.id)
    with closing(db.connect(tables.db_path)) as connection, connection:
        connection.execute("DELETE FROM join_requests WHERE user_id = ?", (user_id,))
    for row in characters.list_for(user_id):
        # ⚠ An open page auto-saves to `ctx["path"]` at the eviction. Without the
        # None, that save makes the file again. See `server/home._delete`.
        if sessions is not None and row.id in sessions:
            sessions.ctx_for(row.id)["path"] = None
            sessions.discard(row.id)
        characters.delete(user_id, row.id)
    shutil.rmtree(characters.account_dir(user_id), ignore_errors=True)
    db.tombstone_user(tables.db_path, user_id)
