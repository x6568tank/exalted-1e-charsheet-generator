"""
server/tables.py — the campaigns (the `Table`) of the hosted server.

Step 1 of the build order in `docs/plans/p3-tables.md`. The design is that file,
sections 2 and 3. The rulings are `docs/plans/vtt.md` section 9.10 (human,
2026-09-12):

  * A join is a code plus the approval of the Storyteller. A request that brings a
    base makes a campaign copy at approval. A request with no base is a watcher.
  * A code has six characters and no expiry. The Storyteller can replace it.
  * A member can bring a base from the table page (`bring`), or start a draft for
    the table (`start_draft`); the lock of the draft sends the request
    (`send_draft`). p3-tables.md section 14, step 6b.
  * A leaver keeps each copy as a solo copy. A delete of the table does the same
    for each member.
  * The homebrew of the table is `<table folder>/custom`. The approval of a base
    adds the homebrew that the base carries. A copy that becomes solo puts its
    homebrew in the library of its owner. p3-tables.md section 14, step 7.
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

from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field, replace
import json
import logging
from pathlib import Path
import secrets
import shutil
import sqlite3

from .. import custom_content
from ..engine.house_rule_actions import apply_table_rules
from ..models.character import (
    TABLE_WIDE_HOUSE_RULES, Character, HouseRules, new_character_id)
from ..persistence import atomic_write
from . import db
from .characters import (
    CUSTOM_DIRNAME, TABLE_ID, CharacterRow, CharacterStore, CharacterStoreError, is_locked,
    table_folder)
from .quota import QuotaExceeded
from .throttle import LoginThrottle

log = logging.getLogger(__name__)

# The TABLE-WIDE house rules of a table, in its folder (p3-tables.md section 5).
HOUSE_RULES_FILE = "house_rules.json"

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
    # True for a request of the Storyteller of the table: it is approved at once,
    # and the row is gone (human, 2026-09-22).
    approved: bool = False


@dataclass(frozen=True)
class HomebrewPreview:
    """What the approval of a join request does to the homebrew of the table.

    `adds` names the rows that the approval adds. `differs` names the rows of the
    base that have the id of a row of the table and different content. The row of
    the table stays.
    """

    adds: list[str]
    differs: list[str]


# The kinds of homebrew that a character carries (`Character.custom_definitions`).
CARRIED_KINDS = ("charms", "spells", "rituals")

_LIBRARY_ROWS = {"charms": custom_content.library_charms,
                 "spells": custom_content.library_spells,
                 "rituals": custom_content.library_rituals}


def library_rows(kind: str, folder: Path) -> dict[str, dict]:
    """Return the `kind` rows of the library at `folder`, by id."""
    return {row["id"]: row for row in _LIBRARY_ROWS[kind](folder) if row.get("id")}


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
    # Called with a table id after a write to the homebrew of that table, and with
    # an account id after a write to the library of that account. `Rulesets` adds
    # its reloads. ⚠ The approval of a request of the Storyteller runs inside this
    # store, thus a reload in a page handler does not see it.
    homebrew_listeners: list[Callable[[str], object]] = field(
        default_factory=list, compare=False, repr=False)
    library_listeners: list[Callable[[int], object]] = field(
        default_factory=list, compare=False, repr=False)

    # ---- paths -------------------------------------------------------------- #

    def table_dir(self, table_id: str) -> Path:
        """Return the folder of table `table_id`. The quota applies to this folder.

        Raise `ValueError` for a malformed id.
        """
        return table_folder(self.root, table_id)

    def homebrew_dir(self, table_id: str) -> Path:
        """Return the homebrew of table `table_id`: a library in the shape of
        `custom_content`. Raise `ValueError` for a malformed id."""
        return self.table_dir(table_id) / CUSTOM_DIRNAME

    def _characters(self) -> CharacterStore:
        return CharacterStore(db_path=self.db_path, root=self.root)

    # ---- house rules -------------------------------------------------------- #

    def house_rules(self, table_id: str) -> HouseRules:
        """Return the TABLE-WIDE house rules of `table_id`. Do not check the access.

        The PER-CHARACTER fields have their defaults. An absent file gives the
        defaults. A file that does not read gives the defaults, and a warning in the
        server log.
        """
        path = self.table_dir(table_id) / HOUSE_RULES_FILE
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return HouseRules.model_validate(
                {k: v for k, v in raw.items() if k in TABLE_WIDE_HOUSE_RULES})
        except FileNotFoundError:
            return HouseRules()
        except (ValueError, AttributeError) as exc:
            log.warning("The house rules %s do not read: %s", path, exc)
            return HouseRules()

    def write_house_rules(self, table_id: str, rules: HouseRules) -> None:
        """Write the TABLE-WIDE fields of `rules` as the house rules of `table_id`. Do
        not check the access: `TableStoryteller.set_table_rule` does.

        ⚠ The quota of the table folder applies (`atomic_write`). Its error propagates.
        """
        atomic_write(self.table_dir(table_id) / HOUSE_RULES_FILE, json.dumps(
            rules.model_dump(include=set(TABLE_WIDE_HOUSE_RULES)), sort_keys=True))

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
        return self._insert_request(user_id, table_id, base_id)

    def bring(self, user_id: int, table_id: str, base_id: str) -> JoinRequest:
        """Ask to bring the base `base_id` into `table_id`, from the membership of
        `user_id` instead of the code. The Storyteller approves it as a join.

        Refuse a user with no access, and each base that `request` refuses. Do not
        count the attempt in `throttle`: a member does not guess a code.
        """
        if self.access(user_id, table_id) is None:
            raise TableStoreError("You are not in this campaign.")
        if base_id is None:
            raise TableStoreError("Pick a character to bring.")
        self._check_base(user_id, base_id)
        return self._insert_request(user_id, table_id, base_id)

    # ---- drafts for a campaign (section 14, step 6b) ------------------------ #

    def start_draft(self, user_id: int, table_id: str) -> CharacterRow:
        """Make a new draft of `user_id` for `table_id`, with the TABLE-WIDE house
        rules of the table. Return its row. Refuse a user with no access.

        The draft has no `table_id`: it is an ordinary character until its lock
        (`send_draft`) and the approval.
        """
        if self.access(user_id, table_id) is None:
            raise TableStoreError("You are not in this campaign.")
        character = Character(id=new_character_id())
        apply_table_rules(self.house_rules(table_id), character)
        row = self._characters().create(user_id, character)
        with closing(db.connect(self.db_path)) as connection, connection:
            connection.execute(
                "INSERT INTO campaign_drafts (character_id, table_id) VALUES (?, ?)",
                (row.id, table_id))
        return row

    def draft_table(self, character_id: str) -> str | None:
        """Return the table for which `character_id` is a draft, or None."""
        with closing(db.connect(self.db_path)) as connection:
            found = connection.execute(
                "SELECT table_id FROM campaign_drafts WHERE character_id = ?",
                (character_id,)).fetchone()
        return None if found is None else found[0]

    def drafts(self, table_id: str) -> list[CharacterRow]:
        """Return the drafts for `table_id`. Do not check the access."""
        with closing(db.connect(self.db_path)) as connection:
            rows = connection.execute(
                "SELECT character_id FROM campaign_drafts WHERE table_id = ? "
                "ORDER BY rowid", (table_id,)).fetchall()
        store = self._characters()
        return [row for (character_id,) in rows
                if (row := store.row(character_id)) is not None]

    def send_draft(self, user_id: int, character_id: str) -> JoinRequest | None:
        """Send the locked draft `character_id` of `user_id` to the Storyteller of
        its table as a join request, and delete the tag. Return the request, or None
        for a character that is not a draft of `user_id` for a table.

        Refuse an unlocked draft; the tag stays.
        """
        table_id = self.draft_table(character_id)
        if table_id is None or self._characters().owned(user_id, character_id) is None:
            return None
        self._check_base(user_id, character_id)
        request = self._insert_request(user_id, table_id, character_id)
        with closing(db.connect(self.db_path)) as connection, connection:
            connection.execute("DELETE FROM campaign_drafts WHERE character_id = ?",
                               (character_id,))
        return request

    def _insert_request(self, user_id: int, table_id: str,
                        base_id: str | None) -> JoinRequest:
        """Add a join request, and return it. Refuse a duplicate pending request.

        Approve a request of the Storyteller of the table at once.
        """
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
        request = JoinRequest(id=int(cursor.lastrowid), table_id=table_id,
                              user_id=user_id, base_id=base_id)
        if self.access(user_id, table_id) != STORYTELLER:
            return request
        # The Storyteller does not approve their own character (Q4). A failed
        # approval leaves the request in the list, to approve by hand.
        try:
            self.approve(user_id, request.id)
        except (TableStoreError, QuotaExceeded) as exc:
            log.warning("Could not approve the request %s at once: %s", request.id, exc)
            return request
        return replace(request, approved=True)

    def approve(self, st_id: int, request_id: int) -> CharacterRow | None:
        """Accept request `request_id`. Return the campaign copy, or None for a
        request to watch.

        Make the membership if it is absent, and the copy of the base in the table.
        Refuse all but the Storyteller of the table of the request.

        Add the homebrew that the base carries to the homebrew of the table. The row
        of the table wins an id clash (ruled 2026-09-23). ⚠ This is the only write
        of a join to the homebrew of the table, and the approval of the Storyteller
        is its consent.

        The copy gets the TABLE-WIDE house rules of the table (section 5, site 1).
        """
        request = self._request(request_id)
        self._require_storyteller(st_id, request.table_id)
        copy = None
        if request.base_id is not None:
            base = self._characters().owned(request.user_id, request.base_id)
            if base is not None and custom_content.absorb_definitions(
                    self._characters().load(base),
                    custom_dir=self.homebrew_dir(request.table_id)):
                self.homebrew_changed(request.table_id)
            try:
                copy = self._characters().make_copy(
                    request.user_id, request.base_id, table_id=request.table_id,
                    adjust=lambda character: apply_table_rules(
                        self.house_rules(request.table_id), character))
            except CharacterStoreError as exc:
                raise TableStoreError(str(exc)) from exc
        with closing(db.connect(self.db_path)) as connection, connection:
            if request.user_id != st_id:
                connection.execute(
                    "INSERT OR IGNORE INTO memberships (table_id, user_id) VALUES (?, ?)",
                    (request.table_id, request.user_id))
            connection.execute("DELETE FROM join_requests WHERE id = ?", (request.id,))
        return copy

    def homebrew_preview(self, st_id: int, request_id: int) -> HomebrewPreview:
        """Return what the approval of request `request_id` does to the homebrew of
        its table. Refuse all but the Storyteller of the table."""
        request = self._request(request_id)
        self._require_storyteller(st_id, request.table_id)
        adds: list[str] = []
        differs: list[str] = []
        store = self._characters()
        base = (store.owned(request.user_id, request.base_id)
                if request.base_id is not None else None)
        if base is None:
            return HomebrewPreview(adds, differs)
        carried = store.load(base).custom_definitions or {}
        folder = self.homebrew_dir(request.table_id)
        for kind in CARRIED_KINDS:
            have = library_rows(kind, folder)
            for row in carried.get(kind, []):
                if not isinstance(row, dict) or not row.get("id"):
                    continue
                name = str(row.get("name") or row["id"])
                if row["id"] not in have:
                    adds.append(name)
                elif have[row["id"]] != row:
                    differs.append(name)
        return HomebrewPreview(adds, differs)

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
        # ⚠ Before the folder goes: the homebrew of the table is in it.
        self._keep_homebrew(self.characters(table_id))
        with closing(db.connect(self.db_path)) as connection, connection:
            connection.execute(
                "UPDATE characters SET table_id = NULL WHERE table_id = ?", (table_id,))
            connection.execute("DELETE FROM tables WHERE id = ?", (table_id,))
        shutil.rmtree(self.table_dir(table_id), ignore_errors=True)
        return True

    def homebrew_changed(self, table_id: str) -> None:
        """Tell each listener that the homebrew of `table_id` changed."""
        for listener in self.homebrew_listeners:
            listener(table_id)

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

    def _keep_homebrew(self, rows: list[CharacterRow]) -> None:
        """Put the homebrew that each copy of `rows` carries into the library of its
        owner, before the copy becomes solo. The library wins an id clash.

        A full account keeps the copy without the rows, and the server log has a
        warning: a leave does not fail for a quota.
        """
        store = self._characters()
        for row in rows:
            try:
                added = custom_content.absorb_definitions(
                    store.load(row), custom_dir=store.custom_dir(row.owner_id))
            except (QuotaExceeded, OSError, ValueError) as exc:
                log.warning("Could not keep the homebrew of %s: %s", row.id, exc)
                continue
            if added:
                for listener in self.library_listeners:
                    listener(row.owner_id)

    def _drop_member(self, user_id: int, table_id: str) -> bool:
        if not TABLE_ID.fullmatch(table_id or ""):
            return False
        self._keep_homebrew([row for row in self.characters(table_id)
                             if row.owner_id == user_id])
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
            connection.execute(
                "DELETE FROM campaign_drafts WHERE table_id = ? AND character_id IN "
                "(SELECT id FROM characters WHERE owner_id = ?)", (table_id, user_id))
        return cursor.rowcount == 1
