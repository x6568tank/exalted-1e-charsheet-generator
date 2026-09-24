"""
server/rulesets.py — the RuleSet that each character of the hosted server sees.

Step 7 of `docs/plans/p3-tables.md` section 14 (ruled 2026-09-23):

  * A solo character: the book, then the library of its owner.
  * A campaign copy: the book, then the homebrew of the campaign. Not the library of
    its owner (Q1).
  * A draft for a campaign: the book, the homebrew of the campaign, then the library
    of its owner. The campaign wins an id clash.

Each RuleSet is made on first use and kept. A reload changes it in place, thus each
page that holds it sees the change at once.

⚠ A reload gives the full stack of folders. `rules_db.reload_custom_layer` with one
folder deletes the rows of each other folder of the stack.
"""

from __future__ import annotations

from pathlib import Path

from .. import rules_db
from ..models.rules import RuleSet
from .characters import CharacterRow, CharacterStore
from .tables import TableStore


class Rulesets:
    """The kept RuleSets of each account, each table and each draft for a table."""

    def __init__(self, book: RuleSet, store: CharacterStore, tables: TableStore) -> None:
        self._book = book
        self._store = store
        self._tables = tables
        self._accounts: dict[int, RuleSet] = {}
        self._tables_rules: dict[str, RuleSet] = {}
        self._drafts: dict[tuple[str, int], RuleSet] = {}
        tables.homebrew_listeners.append(self._table_changed)
        tables.library_listeners.append(self._account_changed)

    # ---- reads -------------------------------------------------------------- #

    def for_account(self, user_id: int) -> RuleSet:
        """Return the RuleSet of account `user_id`: the book and its library."""
        if user_id not in self._accounts:
            self._accounts[user_id] = rules_db.with_custom_layers(
                self._book, self._account_stack(user_id))
        return self._accounts[user_id]

    def for_table(self, table_id: str) -> RuleSet:
        """Return the RuleSet of the copies of `table_id`: the book and the homebrew
        of the table. Raise `ValueError` for a malformed id."""
        if table_id not in self._tables_rules:
            self._tables_rules[table_id] = rules_db.with_custom_layers(
                self._book, self._table_stack(table_id))
        return self._tables_rules[table_id]

    def for_draft(self, table_id: str, user_id: int) -> RuleSet:
        """Return the RuleSet of a draft of `user_id` for `table_id`."""
        key = (table_id, user_id)
        if key not in self._drafts:
            self._drafts[key] = rules_db.with_custom_layers(
                self._book, self._draft_stack(*key))
        return self._drafts[key]

    def for_row(self, row: CharacterRow) -> RuleSet:
        """Return the RuleSet of the character of `row`."""
        if row.table_id is not None:
            return self.for_table(row.table_id)
        draft_for = self._tables.draft_table(row.id)
        if draft_for is not None:
            return self.for_draft(draft_for, row.owner_id)
        return self.for_account(row.owner_id)

    # ---- reloads ------------------------------------------------------------ #

    def reload_account(self, user_id: int) -> list[str]:
        """Re-read the library of `user_id` into each kept RuleSet that has it.
        Return the problems of the RuleSet of the account."""
        for (table_id, owner), rules in self._drafts.items():
            if owner == user_id:
                rules_db.reload_custom_layers(rules, self._draft_stack(table_id, owner))
        return rules_db.reload_custom_layers(self.for_account(user_id),
                                             self._account_stack(user_id))

    def reload_table(self, table_id: str) -> list[str]:
        """Re-read the homebrew of `table_id` into each kept RuleSet that has it.
        Return the problems of the RuleSet of the table."""
        for (draft_table, owner), rules in self._drafts.items():
            if draft_table == table_id:
                rules_db.reload_custom_layers(rules, self._draft_stack(table_id, owner))
        return rules_db.reload_custom_layers(self.for_table(table_id),
                                             self._table_stack(table_id))

    def _table_changed(self, table_id: str) -> None:
        # Reload a kept RuleSet only. A table that no page reads makes none.
        if table_id in self._tables_rules or any(k[0] == table_id for k in self._drafts):
            self.reload_table(table_id)

    def _account_changed(self, user_id: int) -> None:
        if user_id in self._accounts or any(k[1] == user_id for k in self._drafts):
            self.reload_account(user_id)

    # ---- stacks ------------------------------------------------------------- #

    def _account_stack(self, user_id: int) -> list[Path]:
        return [self._store.custom_dir(user_id)]

    def _table_stack(self, table_id: str) -> list[Path]:
        return [self._tables.homebrew_dir(table_id)]

    def _draft_stack(self, table_id: str, user_id: int) -> list[Path]:
        return self._table_stack(table_id) + self._account_stack(user_id)
