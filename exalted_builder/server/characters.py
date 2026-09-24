"""
server/characters.py — the characters of each account on the hosted server.

Section 5 piece 4 of `docs/plans/hosting-state-model.md`. The layout is
`docs/plans/vtt.md` sections 9.2, 9.3 and 9.3a (human rulings, 2026-09-12):

  * A character is a FILE, `<root>/user-<id>/characters/<character id>.character.json`,
    plus a row in the `characters` table. The row holds the owner, the copy flag,
    the base of a copy and the table of a copy. The file holds all else.
  * A draft is an unlocked character. A base is a locked character that is not a
    copy. The lock state is in the file, thus the row does not repeat it.
  * A campaign copy is made from a locked base. It records the base. A delete of
    the base keeps the copy and clears its `base_id`.
  * The homebrew library of the account is `<root>/user-<id>/custom`.
  * A campaign copy takes its homebrew from the campaign, `<table folder>/custom`,
    not from the library of its owner (p3-tables.md section 14, step 7).

⚠ The ownership check is here, not in a page. `owned` returns None for the
character of another account and for a malformed id. A page that shows a
character must get it from `owned`.

⚠ Each save and load names the library of the account. The hosted server refuses
the default library. See `custom_content.require_explicit_dir`.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import re

from .. import persistence
from ..models.character import Character, new_character_id
from . import db
from .quota import TABLE_FOLDER_PREFIX

# The shape of `models.character.new_character_id`. A URL gives the id, thus the
# store refuses each other shape before it reads the DB or makes a path.
CHARACTER_ID = re.compile(r"char\.[0-9a-f]{12}")

# The shape of a table id. `TableStore.table_dir` uses it too.
TABLE_ID = re.compile(r"table\.([0-9a-f]{12})")

CHARACTERS_DIRNAME = "characters"
CUSTOM_DIRNAME = "custom"
SUFFIX = ".character.json"


def table_folder(root: Path, table_id: str) -> Path:
    """Return the folder of table `table_id` below `root`. Raise `ValueError` for a
    malformed id."""
    match = TABLE_ID.fullmatch(table_id or "")
    if match is None:
        raise ValueError(f"Not a table id: {table_id!r}")
    return root / f"{TABLE_FOLDER_PREFIX}{match.group(1)}"


class CharacterStoreError(ValueError):
    """An operation that the store refuses. The message is safe to show to the user."""


@dataclass(frozen=True)
class CharacterRow:
    """One row of the `characters` table."""

    id: str
    owner_id: int
    is_copy: bool
    base_id: str | None
    table_id: str | None


def is_locked(character: Character) -> bool:
    """Return True if the chargen of `character` is locked."""
    return character.chargen_locked


@dataclass(frozen=True)
class CharacterStore:
    """The characters of each account: the rows in `db_path`, the files below `root`."""

    db_path: Path
    root: Path

    # ---- paths -------------------------------------------------------------- #

    def account_dir(self, user_id: int) -> Path:
        """Return the folder of account `user_id`. The quota applies to this folder."""
        return self.root / f"user-{int(user_id)}"

    def custom_dir(self, user_id: int) -> Path:
        """Return the homebrew library of account `user_id`."""
        return self.account_dir(user_id) / CUSTOM_DIRNAME

    def homebrew_dir(self, row: CharacterRow) -> Path:
        """Return the folder from which a save of `row` copies its homebrew: the
        homebrew of its campaign for a campaign copy, else the library of the owner.

        ⚠ A copy that read the library of its owner changed at each save to follow
        an edit at home, with no Storyteller (p3-tables.md section 14, step 7).
        """
        if row.table_id is not None:
            return table_folder(self.root, row.table_id) / CUSTOM_DIRNAME
        return self.custom_dir(row.owner_id)

    def path_for(self, row: CharacterRow) -> Path:
        """Return the file of the character of `row`."""
        return self.account_dir(row.owner_id) / CHARACTERS_DIRNAME / f"{row.id}{SUFFIX}"

    # ---- rows --------------------------------------------------------------- #

    def row(self, character_id: str) -> CharacterRow | None:
        """Return the row of `character_id`, or None. Do not check the owner."""
        if not CHARACTER_ID.fullmatch(character_id or ""):
            return None
        with closing(db.connect(self.db_path)) as connection:
            found = connection.execute(
                "SELECT id, owner_id, is_copy, base_id, table_id FROM characters "
                "WHERE id = ?", (character_id,)).fetchone()
        return _row(found)

    def owned(self, user_id: int, character_id: str) -> CharacterRow | None:
        """Return the row of `character_id` if account `user_id` owns it, or None."""
        found = self.row(character_id)
        return found if found is not None and found.owner_id == user_id else None

    def list_for(self, user_id: int) -> list[CharacterRow]:
        """Return the rows of account `user_id`, oldest first."""
        with closing(db.connect(self.db_path)) as connection:
            rows = connection.execute(
                "SELECT id, owner_id, is_copy, base_id, table_id FROM characters "
                "WHERE owner_id = ? ORDER BY created_at, rowid", (user_id,)).fetchall()
        return [_row(found) for found in rows]

    # ---- files -------------------------------------------------------------- #

    def load(self, row: CharacterRow) -> Character:
        """Read the character of `row`. Do not import its homebrew."""
        return persistence.load_character(self.path_for(row), absorb_custom=False,
                                          custom_dir=self.custom_dir(row.owner_id))

    def save(self, row: CharacterRow, character: Character) -> None:
        """Write `character` to the file of `row`, with the homebrew of
        `homebrew_dir(row)`."""
        persistence.save_character(character, self.path_for(row),
                                   custom_dir=self.homebrew_dir(row))

    # ---- operations --------------------------------------------------------- #

    def create(self, user_id: int, character: Character) -> CharacterRow:
        """Store a copy of `character` as a new character of account `user_id`.

        The copy gets a new id. Thus an upload of one file by two accounts, or by
        one account twice, gives separate characters. The file is written first; a
        write that fails (the quota) leaves no row.
        """
        return self._add(user_id, character, is_copy=False, base_id=None)

    def make_copy(self, user_id: int, base_id: str,
                  table_id: str | None = None,
                  adjust: Callable[[Character], object] | None = None) -> CharacterRow:
        """Make a campaign copy of the base `base_id` of account `user_id`, in the
        table `table_id` or with no table. `adjust` changes the copy before the
        first save; the base does not change.

        Refuse a character of another account, an unlocked character, and a copy.
        A base is a locked character, and XP belongs to a copy (section 9.2).
        `server/tables.py` gives `table_id` at an approval, and checks the access.
        """
        base = self.owned(user_id, base_id)
        if base is None:
            raise CharacterStoreError("That character is not yours.")
        if base.is_copy:
            raise CharacterStoreError("A campaign copy cannot be the base of another copy.")
        character = self.load(base)
        if not is_locked(character):
            raise CharacterStoreError("Finish and lock the character before you make a copy.")
        return self._add(user_id, character, is_copy=True, base_id=base.id,
                         table_id=table_id, adjust=adjust)

    def delete(self, user_id: int, character_id: str) -> bool:
        """Delete the character `character_id` of account `user_id`. Return False
        if the account does not own it. The copies of a base stay, with no base."""
        row = self.owned(user_id, character_id)
        if row is None:
            return False
        with closing(db.connect(self.db_path)) as connection, connection:
            connection.execute("DELETE FROM characters WHERE id = ?", (row.id,))
        self.path_for(row).unlink(missing_ok=True)
        return True

    def _add(self, user_id: int, character: Character, *, is_copy: bool,
             base_id: str | None, table_id: str | None = None,
             adjust: Callable[[Character], object] | None = None) -> CharacterRow:
        new = character.model_copy(deep=True, update={"id": new_character_id()})
        if adjust is not None:
            adjust(new)
        row = CharacterRow(id=new.id, owner_id=user_id, is_copy=is_copy,
                           base_id=base_id, table_id=table_id)
        self.save(row, new)
        try:
            with closing(db.connect(self.db_path)) as connection, connection:
                connection.execute(
                    "INSERT INTO characters (id, owner_id, is_copy, base_id, table_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (row.id, user_id, int(is_copy), base_id, table_id))
        except Exception:
            self.path_for(row).unlink(missing_ok=True)
            raise
        return row


def _row(found) -> CharacterRow | None:
    if found is None:
        return None
    character_id, owner_id, is_copy, base_id, table_id = found
    return CharacterRow(id=character_id, owner_id=owner_id, is_copy=bool(is_copy),
                        base_id=base_id, table_id=table_id)
