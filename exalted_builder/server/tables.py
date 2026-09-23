"""
server/tables.py — the campaigns (the `Table`) of the hosted server.

Step 1 of the build order in `docs/plans/p3-tables.md`. The design is that file,
sections 2 and 3. The rulings are `docs/plans/vtt.md` section 9.10 (human,
2026-09-12):

  * A join is a code plus the approval of the Storyteller. A request that brings a
    base makes a campaign copy at approval. A request with no base is a watcher.
  * A code has six characters and no expiry. The Storyteller can replace it.
  * A leaver keeps each copy as a solo copy. A delete of the table does the same
    for each member.
  * The table has a folder of its own, `<root>/table-<hex>/`. A table folder never
    holds a character. A copy stays in the folder of its owner.

⚠ `access` is the authorisation check, as `CharacterStore.owned` is for a
character. Each Storyteller operation checks the role here, in the store. A page
that shows a button only to the Storyteller is not a check.

⚠ The Storyteller is not a row in `memberships`. `tables.storyteller_id` is the one
place that holds the role.

⚠ `characters.table_id` has no foreign key. SQLite cannot add one to an existing
column. This store clears the column at each leave, removal and delete.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
import re
import secrets
import shutil
import sqlite3

from . import db
from .characters import CharacterRow, CharacterStore, CharacterStoreError, is_locked
from .quota import TABLE_FOLDER_PREFIX
from .throttle import LoginThrottle

# The shape of a table id. A URL gives the id, thus the store refuses each other
# shape before it reads the DB or makes a path.
TABLE_ID = re.compile(r"table\.([0-9a-f]{12})")

# No 0, O, 1, I or L. 31 characters, thus 31**6 codes (about 887 million).
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
_CODE_TRIES = 20

STORYTELLER = "storyteller"
MEMBER = "member"


class TableStoreError(ValueError):
    """An operation that the store refuses. The message is safe to show to the user."""


class JoinThrottle(LoginThrottle):
    """The rate limit of the join form, keyed by the account that asks.

    ⚠ Each attempt counts, also an attempt with a correct code. Do not call
    `succeeded`. The account can know a correct code, the code of its own table.
    If a correct code cleared the count, the account could guess without limit.
    """


@dataclass(frozen=True)
class TableRow:
    """One row of the `tables` table."""

    id: str
    name: str
    storyteller_id: int
    join_code: str


@dataclass(frozen=True)
class JoinRequest:
    """One row of the `join_requests` table. `base_id` None is a request to watch."""

    id: int
    table_id: str
    user_id: int
    base_id: str | None


def new_join_code() -> str:
    """Return a random join code of `CODE_LENGTH` characters from `CODE_ALPHABET`."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalise_code(code: str) -> str:
    """Return `code` in upper case, with the whitespace removed."""
    return "".join((code or "").split()).upper()


@dataclass(frozen=True)
class TableStore:
    """The campaigns: the rows in `db_path`, the table folders below `root`."""

    db_path: Path
    root: Path
    throttle: JoinThrottle = field(default_factory=JoinThrottle, compare=False,
                                   repr=False)

    # ---- paths -------------------------------------------------------------- #

    def table_dir(self, table_id: str) -> Path:
        """Return the folder of table `table_id`. The quota applies to this folder.

        Raise `ValueError` for a malformed id.
        """
        match = TABLE_ID.fullmatch(table_id or "")
        if match is None:
            raise ValueError(f"Not a table id: {table_id!r}")
        return self.root / f"{TABLE_FOLDER_PREFIX}{match.group(1)}"

    def _characters(self) -> CharacterStore:
        return CharacterStore(db_path=self.db_path, root=self.root)

    # ---- reads -------------------------------------------------------------- #

    def table(self, table_id: str) -> TableRow | None:
        """Return the row of `table_id`, or None. Do not check the access."""
        if not TABLE_ID.fullmatch(table_id or ""):
            return None
        with closing(db.connect(self.db_path)) as connection:
            found = connection.execute(
                "SELECT id, name, storyteller_id, join_code FROM tables WHERE id = ?",
                (table_id,)).fetchone()
        return None if found is None else TableRow(*found)

    def access(self, user_id: int, table_id: str) -> str | None:
        """Return `STORYTELLER`, `MEMBER` or None: the role of `user_id` in `table_id`.

        A pending request gives no access. A malformed id gives None before the DB.
        """
        if not TABLE_ID.fullmatch(table_id or ""):
            return None
        with closing(db.connect(self.db_path)) as connection:
            found = connection.execute(
                "SELECT storyteller_id FROM tables WHERE id = ?", (table_id,)).fetchone()
            if found is None:
                return None
            if found[0] == user_id:
                return STORYTELLER
            member = connection.execute(
                "SELECT 1 FROM memberships WHERE table_id = ? AND user_id = ?",
                (table_id, user_id)).fetchone()
        return MEMBER if member is not None else None

    def for_user(self, user_id: int) -> list[TableRow]:
        """Return the tables that `user_id` runs or is a member of, oldest first."""
        with closing(db.connect(self.db_path)) as connection:
            rows = connection.execute(
                "SELECT id, name, storyteller_id, join_code FROM tables "
                "WHERE storyteller_id = ? OR id IN "
                "(SELECT table_id FROM memberships WHERE user_id = ?) "
                "ORDER BY created_at, rowid", (user_id, user_id)).fetchall()
        return [TableRow(*found) for found in rows]

    def characters(self, table_id: str) -> list[CharacterRow]:
        """Return the campaign copies in `table_id`, oldest first. Do not check the
        access: the caller calls `access` first."""
        if not TABLE_ID.fullmatch(table_id or ""):
            return []
        with closing(db.connect(self.db_path)) as connection:
            rows = connection.execute(
                "SELECT id FROM characters WHERE table_id = ? ORDER BY created_at, rowid",
                (table_id,)).fetchall()
        store = self._characters()
        return [row for (character_id,) in rows
                if (row := store.row(character_id)) is not None]

    def members(self, table_id: str) -> list[int]:
        """Return the user ids of the members of `table_id`, oldest first. The
        Storyteller is not a member. Do not check the access."""
        if not TABLE_ID.fullmatch(table_id or ""):
            return []
        with closing(db.connect(self.db_path)) as connection:
            rows = connection.execute(
                "SELECT user_id FROM memberships WHERE table_id = ? "
                "ORDER BY joined_at, rowid", (table_id,)).fetchall()
        return [user_id for (user_id,) in rows]

    def pending(self, st_id: int, table_id: str) -> list[JoinRequest]:
        """Return the requests of `table_id`, oldest first. Refuse all but the
        Storyteller."""
        self._require_storyteller(st_id, table_id)
        return self._requests("table_id = ?", (table_id,))

    def requests_by(self, user_id: int) -> list[JoinRequest]:
        """Return the requests that `user_id` made, oldest first."""
        return self._requests("user_id = ?", (user_id,))

    # ---- operations --------------------------------------------------------- #

    def create(self, st_id: int, name: str) -> TableRow:
        """Make a table that `st_id` runs: the row, the folder and a join code.

        Draw the code again on a clash with an existing code.
        """
        name = name.strip()
        if not name:
            raise TableStoreError("A campaign needs a name.")
        table_id = f"table.{secrets.token_hex(6)}"
        for _ in range(_CODE_TRIES):
            code = new_join_code()
            try:
                with closing(db.connect(self.db_path)) as connection, connection:
                    connection.execute(
                        "INSERT INTO tables (id, name, storyteller_id, join_code) "
                        "VALUES (?, ?, ?, ?)", (table_id, name, st_id, code))
                break
            except sqlite3.IntegrityError:
                continue
        else:  # pragma: no cover - 20 clashes in a row do not occur
            raise TableStoreError("Could not make a join code. Try again.")
        self.table_dir(table_id).mkdir(parents=True, exist_ok=True)
        return TableRow(id=table_id, name=name, storyteller_id=st_id, join_code=code)

    def new_code(self, st_id: int, table_id: str) -> str:
        """Replace the join code of `table_id` and return the new code. The old code
        stops working. Refuse all but the Storyteller."""
        self._require_storyteller(st_id, table_id)
        for _ in range(_CODE_TRIES):
            code = new_join_code()
            try:
                with closing(db.connect(self.db_path)) as connection, connection:
                    connection.execute(
                        "UPDATE tables SET join_code = ? WHERE id = ?", (code, table_id))
                return code
            except sqlite3.IntegrityError:
                continue
        raise TableStoreError("Could not make a join code. Try again.")  # pragma: no cover

    def request(self, user_id: int, code: str, base_id: str | None) -> JoinRequest:
        """Ask to join the table of `code`, with the base `base_id` or to watch.

        Count the attempt in `throttle` first. Refuse an unknown code, a base that
        `user_id` does not own, an unlocked base, a copy, a duplicate pending
        request, and a request to watch from a user who already has access.
        """
        wait = self.throttle.begin(str(user_id))
        if wait:
            raise TableStoreError(
                f"Too many tries. Wait {int(wait) + 1} seconds and try again.")
        code = normalise_code(code)
        with closing(db.connect(self.db_path)) as connection:
            found = connection.execute(
                "SELECT id FROM tables WHERE join_code = ?", (code,)).fetchone()
        if found is None:
            raise TableStoreError("There is no campaign with that code.")
        table_id = found[0]

        if base_id is None:
            if self.access(user_id, table_id) is not None:
                raise TableStoreError("You are already in this campaign.")
        else:
            self._check_base(user_id, base_id)

        with closing(db.connect(self.db_path)) as connection, connection:
            duplicate = connection.execute(
                "SELECT 1 FROM join_requests WHERE table_id = ? AND user_id = ? "
                "AND base_id IS ?", (table_id, user_id, base_id)).fetchone()
            if duplicate is not None:
                raise TableStoreError("That request is already waiting for the "
                                      "Storyteller.")
            cursor = connection.execute(
                "INSERT INTO join_requests (table_id, user_id, base_id) VALUES (?, ?, ?)",
                (table_id, user_id, base_id))
        return JoinRequest(id=int(cursor.lastrowid), table_id=table_id,
                           user_id=user_id, base_id=base_id)

    def approve(self, st_id: int, request_id: int) -> CharacterRow | None:
        """Accept request `request_id`. Return the campaign copy, or None for a
        request to watch.

        Make the membership if it is absent, and the copy of the base in the table.
        Refuse all but the Storyteller of the table of the request. ⚠ Do not import
        the homebrew of the base into the table (p3-tables.md section 4).
        """
        request = self._request(request_id)
        self._require_storyteller(st_id, request.table_id)
        copy = None
        if request.base_id is not None:
            try:
                copy = self._characters().make_copy(
                    request.user_id, request.base_id, table_id=request.table_id)
            except CharacterStoreError as exc:
                raise TableStoreError(str(exc)) from exc
        with closing(db.connect(self.db_path)) as connection, connection:
            if request.user_id != st_id:
                connection.execute(
                    "INSERT OR IGNORE INTO memberships (table_id, user_id) VALUES (?, ?)",
                    (request.table_id, request.user_id))
            connection.execute("DELETE FROM join_requests WHERE id = ?", (request.id,))
        return copy

    def reject(self, st_id: int, request_id: int) -> None:
        """Delete request `request_id`. Refuse all but the Storyteller of its table."""
        request = self._request(request_id)
        self._require_storyteller(st_id, request.table_id)
        with closing(db.connect(self.db_path)) as connection, connection:
            connection.execute("DELETE FROM join_requests WHERE id = ?", (request.id,))

    def withdraw(self, user_id: int, request_id: int) -> bool:
        """Delete request `request_id` if `user_id` made it. Return False if not.

        ⚠ Use this, not `leave`, to cancel one request. `leave` also ends the
        membership of a member who asked to bring another character.
        """
        with closing(db.connect(self.db_path)) as connection, connection:
            cursor = connection.execute(
                "DELETE FROM join_requests WHERE id = ? AND user_id = ?",
                (int(request_id), user_id))
        return cursor.rowcount == 1

    def leave(self, user_id: int, table_id: str) -> bool:
        """Take `user_id` out of `table_id`. Return False if it was not a member.

        Each copy of the user in the table becomes a solo copy. Delete the pending
        requests of the user for the table. Refuse the Storyteller.
        """
        if self.access(user_id, table_id) == STORYTELLER:
            raise TableStoreError("The Storyteller cannot leave. Delete the campaign.")
        return self._drop_member(user_id, table_id)

    def remove(self, st_id: int, table_id: str, user_id: int) -> bool:
        """Take member `user_id` out of `table_id`, as `leave` does. Return False if it
        was not a member. Refuse all but the Storyteller, and the Storyteller."""
        self._require_storyteller(st_id, table_id)
        if user_id == st_id:
            raise TableStoreError("The Storyteller cannot leave. Delete the campaign.")
        return self._drop_member(user_id, table_id)

    def delete(self, st_id: int, table_id: str) -> bool:
        """Delete `table_id`: the rows, the requests and the folder. Return False if
        `st_id` is not its Storyteller. Each copy in the table becomes a solo copy."""
        if self.access(st_id, table_id) != STORYTELLER:
            return False
        with closing(db.connect(self.db_path)) as connection, connection:
            connection.execute(
                "UPDATE characters SET table_id = NULL WHERE table_id = ?", (table_id,))
            connection.execute("DELETE FROM tables WHERE id = ?", (table_id,))
        shutil.rmtree(self.table_dir(table_id), ignore_errors=True)
        return True

    # ---- helpers ------------------------------------------------------------ #

    def _require_storyteller(self, user_id: int, table_id: str) -> None:
        if self.access(user_id, table_id) != STORYTELLER:
            raise TableStoreError("Only the Storyteller of this campaign can do that.")

    def _check_base(self, user_id: int, base_id: str) -> None:
        store = self._characters()
        base = store.owned(user_id, base_id)
        if base is None:
            raise TableStoreError("That character is not yours.")
        if base.is_copy:
            raise TableStoreError("Bring a base character, not a campaign copy.")
        if not is_locked(store.load(base)):
            raise TableStoreError("Finish and lock the character before you bring it.")

    def _request(self, request_id: int) -> JoinRequest:
        found = self._requests("id = ?", (int(request_id),))
        if not found:
            raise TableStoreError("That request no longer exists.")
        return found[0]

    def _requests(self, where: str, args: tuple) -> list[JoinRequest]:
        with closing(db.connect(self.db_path)) as connection:
            rows = connection.execute(
                "SELECT id, table_id, user_id, base_id FROM join_requests "
                f"WHERE {where} ORDER BY created_at, id", args).fetchall()
        return [JoinRequest(*found) for found in rows]

    def _drop_member(self, user_id: int, table_id: str) -> bool:
        if not TABLE_ID.fullmatch(table_id or ""):
            return False
        with closing(db.connect(self.db_path)) as connection, connection:
            cursor = connection.execute(
                "DELETE FROM memberships WHERE table_id = ? AND user_id = ?",
                (table_id, user_id))
            connection.execute(
                "UPDATE characters SET table_id = NULL "
                "WHERE table_id = ? AND owner_id = ?", (table_id, user_id))
            connection.execute(
                "DELETE FROM join_requests WHERE table_id = ? AND user_id = ?",
                (table_id, user_id))
        return cursor.rowcount == 1
