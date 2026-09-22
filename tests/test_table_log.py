"""The Log of a campaign: `server/table_log.py`.

Step 4 of the build order in `docs/plans/p3-tables.md` section 15.4. The design is
section 15.3: `log.json` in the table folder, the server rolls, a roll takes the
text as its caption, the newest 500 entries, 1,000 characters for a text, and each
member (the Storyteller and a spectator too) can post.
"""

from __future__ import annotations

import json
from pathlib import Path
import random

import pytest

from exalted_builder import persistence
from exalted_builder.engine import dice, lifecycle
from exalted_builder.models.character import Character
from exalted_builder.server import db, table_log
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.quota import FolderQuota, QuotaExceeded
from exalted_builder.server.table_log import TableLog, TableLogError
from exalted_builder.server.tables import TableStore

ST, PLAYER, WATCHER, STRANGER = 1, 2, 3, 4


@pytest.fixture
def tables(tmp_path: Path) -> TableStore:
    path = tmp_path / "accounts" / "exalted.db"
    db.init_db(path)
    with db.connect(path) as connection:
        connection.executemany(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'x')",
            [(ST, "storyteller"), (PLAYER, "player"), (WATCHER, "watcher"),
             (STRANGER, "stranger")])
    return TableStore(db_path=path, root=tmp_path / "sessions")


@pytest.fixture
def table(tables: TableStore):
    """A table with a player who brings a character and a member who watches."""
    table = tables.create(ST, "The Scarlet Gambit")
    characters = CharacterStore(db_path=tables.db_path, root=tables.root)
    base = Character(id="x", name="Ashes", caste="dawn")
    lifecycle.lock_chargen(base)
    for user, base_id in ((PLAYER, characters.create(PLAYER, base).id), (WATCHER, None)):
        tables.approve(ST, tables.request(user, table.join_code, base_id).id)
    return table


@pytest.fixture
def the_log(tables: TableStore) -> TableLog:
    return TableLog(tables)


# --------------------------------------------------------------------------- #
# Messages
# --------------------------------------------------------------------------- #


def test_a_message_is_kept_in_the_table_folder(the_log: TableLog, tables, table) -> None:
    entry = the_log.post(PLAYER, table.id, "  The doors grind open.  ")

    assert the_log.path(table.id) == tables.table_dir(table.id) / "log.json"
    assert (entry.id, entry.user_id, entry.text, entry.roll) == (
        1, PLAYER, "The doors grind open.", None)
    assert the_log.entries(table.id) == [entry]


def test_entries_are_in_time_order_with_rising_ids(the_log: TableLog, table) -> None:
    for user, text in ((ST, "one"), (PLAYER, "two"), (WATCHER, "three")):
        the_log.post(user, table.id, text)

    entries = the_log.entries(table.id)
    assert [(e.id, e.user_id, e.text) for e in entries] == [
        (1, ST, "one"), (2, PLAYER, "two"), (3, WATCHER, "three")]
    assert the_log.version(table.id) == 3


def test_a_table_with_no_log_has_no_entries(the_log: TableLog, table) -> None:
    assert the_log.entries(table.id) == []
    assert the_log.version(table.id) == 0


def test_the_entry_holds_the_account_id_not_the_name(the_log: TableLog, table) -> None:
    """The page gets the name at render, thus a rename shows in old entries."""
    the_log.post(PLAYER, table.id, "hello")

    (stored,) = json.loads(the_log.path(table.id).read_text())
    assert stored["user_id"] == PLAYER
    assert "player" not in json.dumps(stored)


def test_an_empty_message_is_refused(the_log: TableLog, table) -> None:
    with pytest.raises(TableLogError):
        the_log.post(PLAYER, table.id, "   ")
    assert not the_log.path(table.id).exists()


def test_a_text_has_a_thousand_characters_at_most(the_log: TableLog, table) -> None:
    the_log.post(PLAYER, table.id, "x" * table_log.MAX_TEXT)

    with pytest.raises(TableLogError):
        the_log.post(PLAYER, table.id, "x" * (table_log.MAX_TEXT + 1))
    with pytest.raises(TableLogError):
        the_log.roll(PLAYER, table.id, 3, "x" * (table_log.MAX_TEXT + 1))
    assert the_log.version(table.id) == 1


def test_the_log_keeps_the_newest_500(the_log: TableLog, table) -> None:
    for n in range(table_log.MAX_ENTRIES + 1):
        the_log.post(PLAYER, table.id, f"message {n}")

    entries = the_log.entries(table.id)
    assert len(entries) == table_log.MAX_ENTRIES
    assert entries[0].text == "message 1"
    assert entries[-1].text == f"message {table_log.MAX_ENTRIES}"
    assert entries[-1].id == table_log.MAX_ENTRIES + 1


def test_the_version_moves_when_a_full_log_takes_an_entry(the_log: TableLog, table) -> None:
    """⚠ A full log keeps its length, thus the poll cannot compare lengths."""
    for n in range(table_log.MAX_ENTRIES):
        the_log.post(PLAYER, table.id, f"m{n:03}")
    before = the_log.version(table.id)

    the_log.post(PLAYER, table.id, "m999")

    assert the_log.version(table.id) != before


def test_a_log_that_does_not_read_gives_no_entries(the_log: TableLog, table) -> None:
    the_log.path(table.id).write_text("{not json")

    assert the_log.entries(table.id) == []


# --------------------------------------------------------------------------- #
# Who can post
# --------------------------------------------------------------------------- #


def test_the_storyteller_a_player_and_a_watcher_can_post(the_log: TableLog, table) -> None:
    for user in (ST, PLAYER, WATCHER):
        the_log.post(user, table.id, "here")
        the_log.roll(user, table.id, 2)

    assert len(the_log.entries(table.id)) == 6


def test_a_stranger_cannot_post_or_roll(the_log: TableLog, table) -> None:
    with pytest.raises(TableLogError):
        the_log.post(STRANGER, table.id, "hello")
    with pytest.raises(TableLogError):
        the_log.roll(STRANGER, table.id, 3)
    assert not the_log.path(table.id).exists()


def test_a_removed_member_cannot_post(the_log: TableLog, tables, table) -> None:
    tables.remove(ST, table.id, PLAYER)

    with pytest.raises(TableLogError):
        the_log.post(PLAYER, table.id, "still here?")


def test_a_malformed_table_id_touches_no_path(the_log: TableLog) -> None:
    with pytest.raises((TableLogError, ValueError)):
        the_log.post(PLAYER, "../user-2", "hello")


# --------------------------------------------------------------------------- #
# Rolls
# --------------------------------------------------------------------------- #


def test_the_server_rolls_the_dice(the_log: TableLog, table) -> None:
    """The faces come from `dice.roll`. No call takes faces from the caller."""
    expected = dice.roll(8, rng=random.Random(42))

    entry = the_log.roll(PLAYER, table.id, 8, "I swing at the bandit",
                         rng=random.Random(42))

    assert entry.text == "I swing at the bandit"
    assert entry.roll is not None
    assert (entry.roll.count, entry.roll.faces, entry.roll.successes, entry.roll.botch) == (
        8, expected.faces, expected.successes, expected.botch)
    assert entry.roll.summary == expected.summary
    assert the_log.entries(table.id) == [entry]


def test_a_roll_needs_no_caption(the_log: TableLog, table) -> None:
    entry = the_log.roll(PLAYER, table.id, 1)

    assert entry.text == "" and entry.roll is not None and len(entry.roll.faces) == 1


@pytest.mark.parametrize("count", [0, -1, dice.MAX_DICE + 1])
def test_a_count_out_of_range_is_refused(the_log: TableLog, table, count: int) -> None:
    with pytest.raises(TableLogError):
        the_log.roll(PLAYER, table.id, count)


def test_a_botch_reads_back_as_a_botch(the_log: TableLog, table) -> None:
    class Ones(random.Random):
        def randint(self, a, b):
            return 1

    the_log.roll(PLAYER, table.id, 3, rng=Ones())

    (entry,) = the_log.entries(table.id)
    assert entry.roll is not None
    assert (entry.roll.faces, entry.roll.botch, entry.roll.summary) == (
        (1, 1, 1), True, "Botch")


# --------------------------------------------------------------------------- #
# The folder
# --------------------------------------------------------------------------- #


def test_the_quota_of_the_table_folder_applies(the_log: TableLog, tables, table) -> None:
    persistence.set_write_guard(FolderQuota(tables.root, limit=10))
    try:
        with pytest.raises(QuotaExceeded):
            the_log.post(PLAYER, table.id, "a message longer than ten bytes")
    finally:
        persistence.set_write_guard(None)
    assert not the_log.path(table.id).exists()


def test_a_deleted_campaign_takes_its_log(the_log: TableLog, tables, table) -> None:
    the_log.post(PLAYER, table.id, "hello")

    tables.delete(ST, table.id)

    assert not the_log.path(table.id).exists()
