"""
server/table_log.py — the Log of a campaign: messages and rolls in time order.

Step 4 of the build order in `docs/plans/p3-tables.md` section 15.4. The design is
section 15.3 (rulings R5, 2026-09-22):

  * One Log for each table, in `<table folder>/log.json`.
  * Each member can post, the Storyteller too. A member who spectates is a member.
  * A roll is a dice COUNT. If the text box holds text, the text is the caption of
    the roll. The app never names a roll (decision 0019).
  * The initiative roll of the table (step 9) is one entry with its turn order.
  * The file keeps the newest `MAX_ENTRIES` entries. A text has `MAX_TEXT`
    characters at most.

⚠ The server rolls the dice, in `roll`. A result that comes from the browser is a
claim of the browser. No call of this module takes faces.

⚠ Each write asks `TableStore.access`. A page that shows the text box only to a
member is not a check.

⚠ An entry holds the account id, not the username. The page gets the username when
it draws the entry, thus a rename shows in each old entry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import random
import time

from ..engine import dice
from ..persistence import atomic_write
from .tables import TableStore

log = logging.getLogger(__name__)

LOG_FILE = "log.json"

# Design choices, reversible (p3-tables.md section 15.3).
MAX_ENTRIES = 500
MAX_TEXT = 1000


class TableLogError(ValueError):
    """A post that the Log refuses. The message is safe to show to the user."""


@dataclass(frozen=True)
class LogRoll:
    """The dice of one roll. `faces` is in the order of the roll."""

    count: int
    faces: tuple[int, ...]
    successes: int
    botch: bool

    @property
    def summary(self) -> str:
        """Give the result as `dice.RollResult.summary` gives it."""
        if self.botch:
            return "Botch"
        if self.successes == 0:
            return "Failure"
        return f"{self.successes} success" + ("" if self.successes == 1 else "es")


@dataclass(frozen=True)
class InitiativeLine:
    """One combatant of an initiative roll, in the turn order.

    `name` is for each member, an enemy NPC too. `group` is "party", "ally" or
    "enemy". `bonus` and `first` are the adjustments of the Storyteller for this
    roll (`engine.initiative.TurnRoll`).
    """

    name: str
    group: str
    rating: int
    d10: int
    tied: bool = False
    bonus: int = 0
    first: bool = False

    @property
    def total(self) -> int:
        return self.rating + self.bonus + self.d10


@dataclass(frozen=True)
class LogEntry:
    """One entry of the Log. `roll` is None for a message. `at` is epoch seconds.

    For a roll, `text` is the caption, and it can be empty. `initiative` is the turn
    order of an initiative roll of the table, else None.
    """

    id: int
    user_id: int
    at: float
    text: str
    roll: LogRoll | None = None
    initiative: tuple[InitiativeLine, ...] | None = None


def _entry_from(data: dict) -> LogEntry:
    roll = data.get("roll")
    lines = data.get("initiative")
    return LogEntry(
        id=int(data["id"]), user_id=int(data["user_id"]), at=float(data["at"]),
        text=str(data.get("text") or ""),
        roll=None if roll is None else LogRoll(
            count=int(roll["count"]), faces=tuple(int(f) for f in roll["faces"]),
            successes=int(roll["successes"]), botch=bool(roll["botch"])),
        initiative=None if lines is None else tuple(
            InitiativeLine(name=str(ln["name"]), group=str(ln["group"]),
                           rating=int(ln["rating"]), d10=int(ln["d10"]),
                           tied=bool(ln.get("tied")), bonus=int(ln.get("bonus") or 0),
                           first=bool(ln.get("first")))
            for ln in lines))


class TableLog:
    """Read and write the Log of each table of `tables`."""

    def __init__(self, tables: TableStore) -> None:
        self.tables = tables

    def path(self, table_id: str) -> Path:
        """Return the path of the Log of `table_id`. Raise `ValueError` for a
        malformed id."""
        return self.tables.table_dir(table_id) / LOG_FILE

    # ---- reads -------------------------------------------------------------- #

    def entries(self, table_id: str) -> list[LogEntry]:
        """Return the entries of the Log, the oldest first.

        An absent file gives no entries. A file that does not read gives no
        entries, and a warning in the server log.
        """
        path = self.path(table_id)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        try:
            return [_entry_from(item) for item in json.loads(raw)]
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("The Log %s does not read: %s", path, exc)
            return []

    def version(self, table_id: str) -> int:
        """Return the id of the newest entry, or 0 for no entry. The poll compares it.

        ⚠ Not the modification time and the size of the file. When the Log is full,
        two writes in one clock step can give the same time and the same size.
        """
        entries = self.entries(table_id)
        return entries[-1].id if entries else 0

    # ---- writes ------------------------------------------------------------- #

    def post(self, user_id: int, table_id: str, text: str) -> LogEntry:
        """Add the message `text` of `user_id`. Return the entry.

        Refuse a viewer who is not a member, an empty text and a text that is too long.
        """
        self._require_member(user_id, table_id)
        text = _checked_text(text)
        if not text:
            raise TableLogError("Type a message first.")
        return self._append(table_id, user_id, text, None)

    def roll(self, user_id: int, table_id: str, count: int, caption: str = "", *,
             rng: random.Random | None = None) -> LogEntry:
        """Roll `count` dice for `user_id` with `engine.dice.roll`. Add the roll with
        the caption `caption`, which can be empty. Return the entry.

        The target number is 7, 10s count double and a 1 can botch (`dice.roll`).
        Refuse a viewer who is not a member, a count below 1 or above
        `dice.MAX_DICE`, and a caption that is too long. `rng` is for the tests.
        """
        self._require_member(user_id, table_id)
        caption = _checked_text(caption)
        if not isinstance(count, int) or not 1 <= count <= dice.MAX_DICE:
            raise TableLogError(f"Type a number of dice from 1 to {dice.MAX_DICE}.")
        result = dice.roll(count, rng=rng)
        return self._append(table_id, user_id, caption, LogRoll(
            count=count, faces=result.faces, successes=result.successes,
            botch=result.botch))

    def post_initiative(self, user_id: int, table_id: str,
                        lines: list[InitiativeLine]) -> LogEntry:
        """Add the turn order `lines` of an initiative roll. Return the entry.

        Refuse a viewer who is not a member, and no lines. ⚠ The caller rolls with
        `engine.dice.roll` and asks that `user_id` is the Storyteller.
        """
        self._require_member(user_id, table_id)
        if not lines:
            raise TableLogError("Tick at least one character that can roll.")
        return self._append(table_id, user_id, "", None, tuple(lines))

    def _require_member(self, user_id: int, table_id: str) -> None:
        if self.tables.access(user_id, table_id) is None:
            raise TableLogError("You are not in this campaign.")

    def _append(self, table_id: str, user_id: int, text: str,
                roll: LogRoll | None,
                initiative: tuple[InitiativeLine, ...] | None = None) -> LogEntry:
        """Add one entry, and keep the newest `MAX_ENTRIES`. The id of the entry is
        one more than the id of the newest entry.

        ⚠ The quota of the table folder applies (`atomic_write`). Its error propagates.
        """
        entries = self.entries(table_id)
        entry = LogEntry(id=(entries[-1].id + 1) if entries else 1, user_id=user_id,
                         at=time.time(), text=text, roll=roll, initiative=initiative)
        entries = (entries + [entry])[-MAX_ENTRIES:]
        atomic_write(self.path(table_id),
                     json.dumps([asdict(e) for e in entries], ensure_ascii=False))
        return entry


def _checked_text(text: str | None) -> str:
    """Return `text` without the spaces at its ends. Refuse more than `MAX_TEXT`
    characters."""
    text = (text or "").strip()
    if len(text) > MAX_TEXT:
        raise TableLogError(f"A message can have {MAX_TEXT:,} characters at most.")
    return text
