"""The delete of an account: `server/accounts.py`. `docs/plans/account-management.md`.

Rulings of 2026-09-26: the campaigns that the account runs are deleted, and each
other player keeps a solo copy; the username is freed; the id is never reused.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from exalted_builder import persistence
from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character
from exalted_builder.server import accounts, db
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.quota import FolderQuota, QuotaExceeded
from exalted_builder.server.session import SessionRegistry
from exalted_builder.server.tables import TableStore

ST, ALICE, BOB, WATCHER = 1, 2, 3, 4


@pytest.fixture
def tables(tmp_path: Path) -> TableStore:
    path = tmp_path / "accounts" / "exalted.db"
    db.init_db(path)
    with db.connect(path) as connection:
        connection.executemany(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'x')",
            [(ST, "storyteller"), (ALICE, "alice"), (BOB, "bob"), (WATCHER, "watcher")])
    return TableStore(db_path=path, root=tmp_path / "sessions")


@pytest.fixture
def store(tables: TableStore) -> CharacterStore:
    return CharacterStore(db_path=tables.db_path, root=tables.root)


def _locked(name: str) -> Character:
    character = Character(id="x", name=name, caste="dawn")
    lifecycle.lock_chargen(character)
    return character


@pytest.fixture
def table(tables: TableStore, store: CharacterStore):
    """A campaign of ST with two players who each bring a character, and a watcher."""
    table = tables.create(ST, "The Scarlet Gambit")
    for user, name in ((ALICE, "Ashes"), (BOB, "Gearheart")):
        base = store.create(user, _locked(name))
        tables.approve(ST, tables.request(user, table.join_code, base.id).id)
    tables.approve(ST, tables.request(WATCHER, table.join_code, None).id)
    return table


def _delete(tables, store, user_id, sessions=None) -> None:
    accounts.delete_account(user_id, characters=store, tables=tables, sessions=sessions)


def _names(store: CharacterStore, user_id: int) -> set[str]:
    return {store.load(row).name for row in store.list_for(user_id)}


# ---- a player -------------------------------------------------------------------- #


def test_a_deleted_player_loses_every_character_and_the_folder(tables, store, table) -> None:
    assert _names(store, ALICE) == {"Ashes"} and len(store.list_for(ALICE)) == 2

    _delete(tables, store, ALICE)

    assert store.list_for(ALICE) == []
    assert not store.account_dir(ALICE).exists()
    assert db.username_for(tables.db_path, ALICE) is None


def test_a_deleted_player_leaves_the_campaign_and_it_stays(tables, store, table) -> None:
    _delete(tables, store, ALICE)

    assert tables.table(table.id) is not None
    assert ALICE not in tables.members(table.id)
    assert [store.load(row).name for row in tables.characters(table.id)] == ["Gearheart"]


def test_the_other_accounts_keep_everything(tables, store, table) -> None:
    bob_rows = {row.id for row in store.list_for(BOB)}

    _delete(tables, store, ALICE)

    assert {row.id for row in store.list_for(BOB)} == bob_rows
    assert tables.access(ST, table.id) == "storyteller"
    assert db.username_for(tables.db_path, BOB) == "bob"


def test_the_notes_of_a_deleted_player_go(tables, store, table) -> None:
    notes = tables.notes_path(table.id, ALICE)
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text("{}", encoding="utf-8")
    bob_notes = tables.notes_path(table.id, BOB)
    bob_notes.write_text("{}", encoding="utf-8")

    _delete(tables, store, ALICE)

    assert not notes.exists()
    assert bob_notes.exists()


def test_the_pending_requests_of_a_deleted_player_go(tables, store) -> None:
    other = tables.create(ST, "Another Campaign")
    base = store.create(ALICE, _locked("Ashes"))
    tables.request(ALICE, other.join_code, base.id)
    assert tables.requests_by(ALICE)

    _delete(tables, store, ALICE)

    assert tables.requests_by(ALICE) == []


# ---- a Storyteller ------------------------------------------------------------------ #


def test_a_deleted_storyteller_deletes_the_campaign(tables, store, table) -> None:
    folder = tables.table_dir(table.id)
    folder.mkdir(parents=True, exist_ok=True)

    _delete(tables, store, ST)

    assert tables.table(table.id) is None
    assert not folder.exists()


def test_the_players_of_a_deleted_storyteller_keep_solo_copies(tables, store, table) -> None:
    """The ruling of p3-tables.md section 10, applied by the account delete."""
    _delete(tables, store, ST)

    for user, name in ((ALICE, "Ashes"), (BOB, "Gearheart")):
        copies = [row for row in store.list_for(user) if row.is_copy]
        assert [store.load(row).name for row in copies] == [name]
        assert copies[0].table_id is None


def test_campaigns_run_lists_each_campaign_with_its_member_count(tables, store, table) -> None:
    """The confirm dialog names each campaign that the delete removes."""
    tables.create(ST, "An Empty Campaign")

    assert accounts.campaigns_run(tables, ST) == [
        ("The Scarlet Gambit", 3), ("An Empty Campaign", 0)]
    assert accounts.campaigns_run(tables, ALICE) == []


# ---- live pages ------------------------------------------------------------------------ #


def test_an_open_page_does_not_write_a_character_back(tables, store, table) -> None:
    """⚠ The eviction auto-saves the context to `ctx["path"]`. Without the None, the
    file of a deleted character is made again."""
    written = []

    def evict(key: str, ctx: dict) -> None:
        if ctx["path"] is not None:
            written.append(key)
            ctx["path"].write_text("{}", encoding="utf-8")

    sessions = SessionRegistry(
        factory=lambda key: {"char": None, "path": store.path_for(store.row(key))},
        on_evict=evict)
    rows = store.list_for(ALICE)
    for row in rows:
        sessions.ctx_for(row.id)

    _delete(tables, store, ALICE, sessions)

    assert written == []
    assert all(row.id not in sessions for row in rows)
    assert not store.account_dir(ALICE).exists()


def test_the_guard_refuses_a_write_into_a_deleted_account(tables, store, table) -> None:
    """The operator deletes from another process, which cannot reach the sessions.
    The write guard then stops an open page of the account."""
    guard = FolderQuota(tables.root, db_path=tables.db_path)
    alice_file = store.account_dir(ALICE) / "characters" / "late.character.json"
    bob_file = store.account_dir(BOB) / "characters" / "late.character.json"
    guard(bob_file, 10)
    guard(alice_file, 10)   # the control: Alice is live

    _delete(tables, store, ALICE)

    with pytest.raises(QuotaExceeded, match="deleted"):
        guard(alice_file, 10)
    guard(bob_file, 10)
    guard(tables.table_dir(table.id) / "notes" / "2.json", 10)


def test_the_guard_reaches_every_hosted_write(tables, store, table) -> None:
    """The guard is on `persistence.atomic_write`, thus a save refuses too."""
    persistence.set_write_guard(FolderQuota(tables.root, db_path=tables.db_path))
    try:
        row = store.list_for(ALICE)[0]
        character = store.load(row)
        _delete(tables, store, ALICE)
        with pytest.raises(QuotaExceeded):
            store.save(row, character)
    finally:
        persistence.set_write_guard(None)
    assert not store.account_dir(ALICE).exists()
