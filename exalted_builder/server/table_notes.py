"""
server/table_notes.py — the notes of each member of a campaign.

Step 8 of the build order in `docs/plans/p3-tables.md` section 15.4. The design is
section 15.6 (Q8 and Q9, ruled 2026-09-22):

  * Each member has one text in each table, the Storyteller too. The file is
    `<table folder>/notes/<user id>.json` (`TableStore.notes_path`).
  * The notes are private. Only the writer reads them, and the Storyteller does not.
  * A leave or a removal deletes the notes of the member (`TableStore`).

⚠ Each call takes the account from the server, never from the page. The key of the
file is that account. No call takes the id of a different account.
"""

from __future__ import annotations

import json
import logging

from ..persistence import atomic_write
from .tables import TableStore

log = logging.getLogger(__name__)

# A design choice, reversible.
MAX_NOTES = 20_000


class TableNotesError(ValueError):
    """A write that the store refuses. The message is safe to show to the user."""


class TableNotes:
    """Read and write the notes of each member of each table of `tables`."""

    def __init__(self, tables: TableStore) -> None:
        self.tables = tables

    def read(self, user_id: int, table_id: str) -> str:
        """Return the notes of `user_id` in `table_id`.

        Give "" to a user with no access, for an absent file, and for a file that
        does not read. A file that does not read also gives a warning in the server
        log.
        """
        if self.tables.access(user_id, table_id) is None:
            return ""
        path = self.tables.notes_path(table_id, user_id)
        try:
            return str(json.loads(path.read_text(encoding="utf-8"))["text"])
        except FileNotFoundError:
            return ""
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("The notes %s do not read: %s", path, exc)
            return ""

    def write(self, user_id: int, table_id: str, text: str) -> None:
        """Write `text` as the notes of `user_id` in `table_id`.

        Refuse a user with no access, and a text of more than `MAX_NOTES`
        characters. ⚠ The quota of the table folder applies (`atomic_write`). Its
        error propagates.
        """
        if self.tables.access(user_id, table_id) is None:
            raise TableNotesError("You are not in this campaign.")
        text = text or ""
        if len(text) > MAX_NOTES:
            raise TableNotesError(f"Notes can have {MAX_NOTES:,} characters at most.")
        path = self.tables.notes_path(table_id, user_id)
        atomic_write(path, json.dumps({"text": text}, ensure_ascii=False))
