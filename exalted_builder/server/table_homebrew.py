"""
server/table_homebrew.py — the proposals of homebrew to a campaign.

Step 7 of `docs/plans/p3-tables.md` section 14 (ruled 2026-09-23). A member picks a
row of their own library and proposes it. The Storyteller approves it (the row goes
into the homebrew of the table) or rejects it (the proposal goes).

The proposals of a table are in `<table folder>/homebrew_requests.json`. A proposal
holds a COPY of the rows. Thus an edit to the library after the proposal does not
change what the Storyteller approves.

⚠ Each operation checks the role with `TableStore.access`, here in the store. A
page that shows a button only to the Storyteller is not a check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path

from .. import custom_content
from ..persistence import atomic_write
from .characters import CharacterStore
from .tables import CARRIED_KINDS, STORYTELLER, TableStore, library_rows

log = logging.getLogger(__name__)

PROPOSALS_FILE = "homebrew_requests.json"


class TableHomebrewError(ValueError):
    """An operation that the store refuses. The message is safe to show to the user."""


@dataclass(frozen=True)
class Proposal:
    """One proposal. `rows` are the rows to add: the row, and for a Charm each
    homebrew prerequisite that the table does not have."""

    id: int
    user_id: int
    kind: str
    row_id: str
    rows: list[dict] = field(default_factory=list)
    # True for a proposal of the Storyteller of the table: it is added at once.
    approved: bool = False

    @property
    def names(self) -> list[str]:
        return [str(row.get("name") or row.get("id")) for row in self.rows]


class TableHomebrew:
    """The proposals of homebrew of each table of `tables`."""

    def __init__(self, tables: TableStore) -> None:
        self.tables = tables

    # ---- reads -------------------------------------------------------------- #

    def proposals(self, st_id: int, table_id: str) -> list[Proposal]:
        """Return the proposals of `table_id`, oldest first. Refuse all but the
        Storyteller."""
        self._require_storyteller(st_id, table_id)
        return self._read(table_id)

    def proposals_by(self, user_id: int, table_id: str) -> list[Proposal]:
        """Return the proposals of `user_id` in `table_id`. A non-member gets none."""
        if self.tables.access(user_id, table_id) is None:
            return []
        return [p for p in self._read(table_id) if p.user_id == user_id]

    # ---- writes ------------------------------------------------------------- #

    def propose(self, user_id: int, table_id: str, kind: str, row_id: str) -> Proposal:
        """Propose the `kind` row `row_id` of the library of `user_id` to `table_id`.
        Return the proposal.

        Refuse a non-member, a row that is not in the library, a row whose id the
        table has, and a second proposal of one row. Approve a proposal of the
        Storyteller at once.
        """
        if kind not in CARRIED_KINDS:
            raise TableHomebrewError(f"Not a kind of homebrew: {kind!r}")
        if self.tables.access(user_id, table_id) is None:
            raise TableHomebrewError("You are not in this campaign.")
        mine = library_rows(kind, self._library(user_id))
        if row_id not in mine:
            raise TableHomebrewError("That is not in your homebrew library.")
        have = library_rows(kind, self.tables.homebrew_dir(table_id))
        if row_id in have:
            raise TableHomebrewError(
                f"The campaign already has {have[row_id].get('name') or row_id}.")
        proposals = self._read(table_id)
        if any(p.user_id == user_id and p.kind == kind and p.row_id == row_id
               for p in proposals):
            raise TableHomebrewError("That proposal is already waiting for the "
                                     "Storyteller.")
        rows = self._closure(kind, mine, have, row_id)
        proposal = Proposal(id=max((p.id for p in proposals), default=0) + 1,
                            user_id=user_id, kind=kind, row_id=row_id, rows=rows)
        self._write(table_id, proposals + [proposal])
        if self.tables.access(user_id, table_id) == STORYTELLER:
            self.approve(user_id, table_id, proposal.id)
            return Proposal(proposal.id, user_id, kind, row_id, rows, approved=True)
        return proposal

    def approve(self, st_id: int, table_id: str, proposal_id: int) -> Proposal:
        """Add the rows of proposal `proposal_id` to the homebrew of `table_id`, and
        delete the proposal. Return it. Refuse all but the Storyteller.

        The row of the table wins an id clash: the Storyteller wrote it after the
        proposal.
        """
        self._require_storyteller(st_id, table_id)
        proposal = self._find(table_id, proposal_id)
        if custom_content.add_rows(proposal.kind, proposal.rows,
                                   custom_dir=self.tables.homebrew_dir(table_id)):
            self.tables.homebrew_changed(table_id)
        self._drop(table_id, proposal_id)
        return proposal

    def reject(self, st_id: int, table_id: str, proposal_id: int) -> None:
        """Delete proposal `proposal_id`. Refuse all but the Storyteller."""
        self._require_storyteller(st_id, table_id)
        self._find(table_id, proposal_id)
        self._drop(table_id, proposal_id)

    def withdraw(self, user_id: int, table_id: str, proposal_id: int) -> bool:
        """Delete proposal `proposal_id` of `user_id`. Return False if it is not a
        proposal of that user."""
        if self.tables.access(user_id, table_id) is None:
            return False
        found = [p for p in self._read(table_id) if p.id == proposal_id]
        if not found or found[0].user_id != user_id:
            return False
        self._drop(table_id, proposal_id)
        return True

    # ---- helpers ------------------------------------------------------------ #

    def _library(self, user_id: int) -> Path:
        return CharacterStore(db_path=self.tables.db_path,
                              root=self.tables.root).custom_dir(user_id)

    @staticmethod
    def _closure(kind: str, mine: dict[str, dict], have: dict[str, dict],
                 row_id: str) -> list[dict]:
        """Return the row `row_id` and each homebrew prerequisite in `mine` that
        is not in `have`. Only a Charm has prerequisites."""
        if kind != "charms":
            return [mine[row_id]]
        return [row for row in custom_content.closure_rows(mine, {row_id})
                if row["id"] not in have]

    def _require_storyteller(self, user_id: int, table_id: str) -> None:
        if self.tables.access(user_id, table_id) != STORYTELLER:
            raise TableHomebrewError("Only the Storyteller of this campaign can do that.")

    def _path(self, table_id: str) -> Path:
        return self.tables.table_dir(table_id) / PROPOSALS_FILE

    def _read(self, table_id: str) -> list[Proposal]:
        path = self._path(table_id)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return [Proposal(id=int(p["id"]), user_id=int(p["user_id"]),
                             kind=str(p["kind"]), row_id=str(p["row_id"]),
                             rows=list(p["rows"])) for p in raw]
        except FileNotFoundError:
            return []
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("The homebrew proposals %s do not read: %s", path, exc)
            return []

    def _write(self, table_id: str, proposals: list[Proposal]) -> None:
        atomic_write(self._path(table_id), json.dumps(
            [{"id": p.id, "user_id": p.user_id, "kind": p.kind, "row_id": p.row_id,
              "rows": p.rows}
             for p in proposals], indent=2) + "\n")

    def _find(self, table_id: str, proposal_id: int) -> Proposal:
        for proposal in self._read(table_id):
            if proposal.id == proposal_id:
                return proposal
        raise TableHomebrewError("That proposal no longer exists.")

    def _drop(self, table_id: str, proposal_id: int) -> None:
        self._write(table_id, [p for p in self._read(table_id) if p.id != proposal_id])
