"""
server/table_st.py — the operations of the Storyteller on the copies of a campaign.

Step 5 of the build order in `docs/plans/p3-tables.md` section 15.4. The design is
section 6 (ruled: the Storyteller grants XP) and Q6 (ruled 2026-09-12: on a campaign
copy, unlocking is up to the Storyteller):

  * Grant XP: an amount and a note, to one copy or to each copy in the table. It
    calls `advancement.add_xp`. A negative amount corrects an over-grant.
  * The award log, `<table folder>/awards.json`: when, who, how much, the note and
    the copies. `xp_earned` is a number only. The log gives the reason for it.
  * Each grant posts one line to the Log of the table.
  * Unlock: `lifecycle.unlock_chargen` on one copy in the table.

⚠ A copy that has a live context gets the change on THAT object, and the file is
saved from it. A write to the file behind an open page is lost at the next
auto-save of that page. Read the context with `peek`: this module never builds a
context for the character of another account (section 8).

⚠ Each operation asks `TableStore.access`. A page that shows the ST tab only to
the Storyteller is not a check. The browser names the copy, thus each operation
also asks that the copy is in the table.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import time

from ..engine import advancement, lifecycle
from ..models.character import Character
from ..persistence import atomic_write
from .characters import CharacterRow, CharacterStore
from .quota import QuotaExceeded
from .session import SessionRegistry
from .table_log import MAX_TEXT, TableLog, TableLogError
from .tables import STORYTELLER, TableStore, TableStoreError

log = logging.getLogger(__name__)

AWARDS_FILE = "awards.json"

# Design choices, reversible (p3-tables.md section 14, step 5).
MAX_GRANT = 1000
MAX_NOTE = 200

COPY_GONE = "That character is no longer in this campaign."


@dataclass(frozen=True)
class Recipient:
    """One copy of an award. `name` is the name of the character at the grant."""

    character_id: str
    name: str


@dataclass(frozen=True)
class Award:
    """One grant of XP. `user_id` is the Storyteller. `at` is epoch seconds."""

    id: int
    user_id: int
    at: float
    amount: int
    note: str
    recipients: tuple[Recipient, ...]


@dataclass(frozen=True)
class GrantResult:
    """The award, and the names of the copies that could not be saved."""

    award: Award
    failed: tuple[str, ...]


def _award_from(data: dict) -> Award:
    return Award(
        id=int(data["id"]), user_id=int(data["user_id"]), at=float(data["at"]),
        amount=int(data["amount"]), note=str(data.get("note") or ""),
        recipients=tuple(Recipient(character_id=str(r["character_id"]),
                                   name=str(r["name"])) for r in data["recipients"]))


def _name(character: Character) -> str:
    return character.name or "(unnamed)"


class TableStoryteller:
    """Grant XP to the copies of each table of `tables`, and unlock them.

    `store` holds the copies. `sessions` is the character registry of
    `server/home.py`. `log` gets one line for each grant.
    """

    def __init__(self, tables: TableStore, store: CharacterStore,
                 sessions: SessionRegistry, log: TableLog) -> None:
        self.tables = tables
        self.store = store
        self.sessions = sessions
        self.log = log

    def awards_path(self, table_id: str) -> Path:
        """Return the path of the award log of `table_id`. Raise `ValueError` for a
        malformed id."""
        return self.tables.table_dir(table_id) / AWARDS_FILE

    # ---- reads -------------------------------------------------------------- #

    def awards(self, table_id: str) -> list[Award]:
        """Return the awards of `table_id`, the oldest first. Do not check the access.

        An absent file gives no awards. A file that does not read gives no awards,
        and a warning in the server log.
        """
        path = self.awards_path(table_id)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        try:
            return [_award_from(item) for item in json.loads(raw)]
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("The award log %s does not read: %s", path, exc)
            return []

    # ---- Grant XP ----------------------------------------------------------- #

    def grant_xp(self, st_id: int, table_id: str, amount: int, note: str = "",
                 character_ids: list[str] | None = None) -> GrantResult:
        """Add `amount` XP to each copy of `character_ids`, or to each copy in the
        table for None. Record the award and post it to the Log. Return the result.

        Refuse all but the Storyteller, an amount of 0 or past `MAX_GRANT`, a note
        past `MAX_NOTE`, a copy that is not in the table, and a table with no copy.

        A copy that cannot be saved keeps its old XP and is in `failed`. If no copy
        gets the grant, refuse. ⚠ If the award log cannot be written, each copy
        goes back to its old XP and the error propagates.
        """
        self._require_storyteller(st_id, table_id)
        if not isinstance(amount, int) or amount == 0 or abs(amount) > MAX_GRANT:
            raise TableStoreError(
                f"Type an amount of XP from -{MAX_GRANT} to {MAX_GRANT}, not 0.")
        note = (note or "").strip()
        if len(note) > MAX_NOTE:
            raise TableStoreError(f"A note can have {MAX_NOTE} characters at most.")
        rows = self._rows(table_id, character_ids)
        if not rows:
            raise TableStoreError("There is no character in this campaign.")

        granted: list[tuple[CharacterRow, Character, int]] = []
        failed: list[str] = []
        for row in rows:
            character = self._character(row)
            if character is None:
                failed.append(row.id)
                continue
            before = character.xp_earned
            advancement.add_xp(character, amount)
            try:
                self.store.save(row, character)
            except (QuotaExceeded, OSError):
                character.xp_earned = before
                failed.append(_name(character))
                continue
            granted.append((row, character, before))
        if not granted:
            raise TableStoreError("No XP was granted: " + ", ".join(failed) + ".")

        try:
            award = self._append_award(table_id, st_id, amount, note, tuple(
                Recipient(character_id=row.id, name=_name(character))
                for row, character, _ in granted))
        except Exception:
            self._restore(granted)
            raise
        self._post(st_id, table_id, award)
        return GrantResult(award=award, failed=tuple(failed))

    def _append_award(self, table_id: str, st_id: int, amount: int, note: str,
                      recipients: tuple[Recipient, ...]) -> Award:
        """Add one award. Its id is one more than the id of the newest award.

        ⚠ The quota of the table folder applies (`atomic_write`). Its error propagates.
        """
        awards = self.awards(table_id)
        award = Award(id=(awards[-1].id + 1) if awards else 1, user_id=st_id,
                      at=time.time(), amount=amount, note=note, recipients=recipients)
        atomic_write(self.awards_path(table_id), json.dumps(
            [asdict(a) for a in awards + [award]], ensure_ascii=False))
        return award

    def _restore(self, granted: list[tuple[CharacterRow, Character, int]]) -> None:
        """Put the old XP back on each object of `granted`, and save it."""
        for row, character, before in granted:
            character.xp_earned = before
            try:
                self.store.save(row, character)
            except (QuotaExceeded, OSError) as exc:
                log.warning("Could not restore the XP of %s: %s", row.id, exc)

    def _post(self, st_id: int, table_id: str, award: Award) -> None:
        """Post the award to the Log. A post that fails leaves the award as it is."""
        text = (f"{award.amount:+d} XP to "
                + ", ".join(r.name for r in award.recipients)
                + (f" — {award.note}" if award.note else ""))
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT - 1] + "…"
        try:
            self.log.post(st_id, table_id, text)
        except (TableLogError, QuotaExceeded) as exc:
            log.warning("Could not post the award %s to the Log: %s", award.id, exc)

    # ---- Unlock ------------------------------------------------------------- #

    def unlock(self, st_id: int, table_id: str, character_id: str) -> None:
        """Unlock the copy `character_id` with `lifecycle.unlock_chargen`, and save it.

        Refuse all but the Storyteller, a copy that is not in the table, and a copy
        that is not locked. ⚠ The page warns first if the copy spent XP
        (`view.unlock_warning`).
        """
        self._require_storyteller(st_id, table_id)
        (row,) = self._rows(table_id, [character_id])
        character = self._character(row)
        if character is None:
            raise TableStoreError("That character does not read.")
        if not character.chargen_locked:
            raise TableStoreError("That character is not locked.")
        lifecycle.unlock_chargen(character)
        self.store.save(row, character)

    # ---- helpers ------------------------------------------------------------ #

    def _require_storyteller(self, user_id: int, table_id: str) -> None:
        if self.tables.access(user_id, table_id) != STORYTELLER:
            raise TableStoreError("Only the Storyteller of this campaign can do that.")

    def _rows(self, table_id: str, character_ids: list[str] | None) -> list[CharacterRow]:
        """Return the copies of `character_ids` in `table_id`, or each copy for None.
        Refuse an id that is not a copy in the table."""
        rows = self.tables.characters(table_id)
        if character_ids is None:
            return rows
        by_id = {row.id: row for row in rows}
        missing = [c for c in character_ids if c not in by_id]
        if missing:
            raise TableStoreError(COPY_GONE)
        return [by_id[c] for c in dict.fromkeys(character_ids)]

    def _character(self, row: CharacterRow) -> Character | None:
        """Return the live object of `row` if a page holds one, else the file. ⚠
        `peek`, never `ctx_for`. Return None for a file that does not read."""
        ctx = self.sessions.peek(row.id)
        if ctx is not None:
            return ctx["char"]
        try:
            return self.store.load(row)
        except Exception:                           # noqa: BLE001 - report it as failed
            log.warning("The character %s does not read.", row.id)
            return None
