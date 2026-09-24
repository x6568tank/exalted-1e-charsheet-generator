"""
server/table_roster.py — the adversary roster of a campaign.

Step 8 of the build order in `docs/plans/p3-tables.md` section 15.4. The design is
section 15.3 (rulings R4, R6, R7 and R8, 2026-09-22):

  * One roster for each table, in `<table folder>/adversaries.json`: a list of
    `Adversary`.
  * Each entry has a side (`Adversary.side`). An enemy is for the Storyteller only.
    A player gets an ally as a name and a health track (`view.ally_view`).
  * The Storyteller alone changes the roster and marks its trackers.

⚠ The Storyteller gets the LIVE roster (`party`): one `Party` object for each table,
in this store. The two devices of the Storyteller change the same object. Each
change then calls `save`. The engine operations of `engine/adversaries.py` take a
`Party`, thus the roster is a `Party` with no members.

⚠ A player never gets an `Adversary`. `allies` gives projections only. An element
that is hidden with CSS still goes to the browser.

⚠ Each call asks `TableStore.access`. A page that shows the roster only to the
Storyteller is not a check.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from ..models.adversary import ALLY, Adversary
from ..models.party import Party
from ..persistence import atomic_write
from ..ui import view as viewmod
from .tables import STORYTELLER, TableStore, TableStoreError

log = logging.getLogger(__name__)

ROSTER_FILE = "adversaries.json"


class TableRoster:
    """Read and write the roster of each table of `tables`."""

    def __init__(self, tables: TableStore) -> None:
        self.tables = tables
        self._live: dict[str, Party] = {}
        self._versions: dict[str, int] = {}

    def path(self, table_id: str) -> Path:
        """Return the path of the roster of `table_id`. Raise `ValueError` for a
        malformed id."""
        return self.tables.table_dir(table_id) / ROSTER_FILE

    # ---- reads -------------------------------------------------------------- #

    def party(self, st_id: int, table_id: str) -> Party:
        """Return the live roster of `table_id` for its Storyteller `st_id`.

        Refuse all but the Storyteller. ⚠ Call `save` after each change.
        """
        self._require_storyteller(st_id, table_id)
        return self._roster(table_id)

    def allies(self, user_id: int, table_id: str) -> list[viewmod.AllyView]:
        """Return the allies of the roster of `table_id` as projections, in the order
        of the roster. Give an empty list to a user with no access."""
        if self.tables.access(user_id, table_id) is None:
            return []
        return [viewmod.ally_view(a) for a in self._roster(table_id).adversaries
                if a.side == ALLY]

    def version(self, table_id: str) -> int:
        """Return a number that changes at each `save` of the roster of `table_id`.
        The poll compares it."""
        return self._versions.get(table_id, 0)

    # ---- writes ------------------------------------------------------------- #

    def save(self, st_id: int, table_id: str) -> None:
        """Write the live roster of `table_id` to its file.

        Refuse all but the Storyteller, and forget the live roster of a table that
        the Storyteller cannot reach now. ⚠ The quota of the table folder applies
        (`atomic_write`). Its error propagates.
        """
        try:
            self._require_storyteller(st_id, table_id)
        except TableStoreError:
            self._live.pop(table_id, None)
            raise
        party = self._roster(table_id)
        self._versions[table_id] = self.version(table_id) + 1
        atomic_write(self.path(table_id), json.dumps(
            [a.model_dump(mode="json") for a in party.adversaries], ensure_ascii=False))

    # ---- helpers ------------------------------------------------------------ #

    def _roster(self, table_id: str) -> Party:
        """Return the live roster of `table_id`. Read it from the file if it is absent.

        An absent file gives an empty roster. A file that does not read gives an
        empty roster, and a warning in the server log.
        """
        party = self._live.get(table_id)
        if party is not None:
            return party
        path = self.path(table_id)
        adversaries: list[Adversary] = []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            adversaries = [Adversary.model_validate(item) for item in raw]
        except FileNotFoundError:
            pass
        except (ValueError, TypeError, ValidationError) as exc:
            log.warning("The roster %s does not read: %s", path, exc)
        party = Party(id=table_id, adversaries=adversaries)
        self._live[table_id] = party
        return party

    def _require_storyteller(self, user_id: int, table_id: str) -> None:
        if self.tables.access(user_id, table_id) != STORYTELLER:
            raise TableStoreError("Only the Storyteller of this campaign can do that.")
