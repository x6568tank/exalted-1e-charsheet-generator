"""The Storyteller's operations on the copies of a campaign: `server/table_st.py`.

Step 5 of the build order in `docs/plans/p3-tables.md` section 15.4. The design is
section 6 (Grant XP and the award log) and Q6 (on a campaign copy, unlocking is up
to the Storyteller).

⚠ Trap section 12, "XP grant written behind an open page": a copy that has a live
context gets the grant on THAT object. A write to the file behind an open page is
lost at the next auto-save of that page.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from exalted_builder import persistence
from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character, XpEntry
from exalted_builder.server import db, table_st
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.quota import FolderQuota, QuotaExceeded
from exalted_builder.server.session import SessionRegistry
from exalted_builder.server.table_log import TableLog
from exalted_builder.server.table_st import TableStoryteller
from exalted_builder.server.tables import TableStore, TableStoreError

ST, ALICE, BOB, WATCHER, STRANGER = 1, 2, 3, 4, 5


@pytest.fixture
def tables(tmp_path: Path) -> TableStore:
    path = tmp_path / "accounts" / "exalted.db"
    db.init_db(path)
    with db.connect(path) as connection:
        connection.executemany(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'x')",
            [(ST, "storyteller"), (ALICE, "alice"), (BOB, "bob"), (WATCHER, "watcher"),
             (STRANGER, "stranger")])
    return TableStore(db_path=path, root=tmp_path / "sessions")


@pytest.fixture
def store(tables: TableStore) -> CharacterStore:
    return CharacterStore(db_path=tables.db_path, root=tables.root)


@pytest.fixture
def sessions(store: CharacterStore) -> SessionRegistry:
    """A character registry whose context holds the loaded character, as the
    factory of `server/home.py` does."""
    return SessionRegistry(factory=lambda key: {"char": store.load(store.row(key))})


def _locked(name: str) -> Character:
    character = Character(id="x", name=name, caste="dawn")
    lifecycle.lock_chargen(character)
    return character


@pytest.fixture
def table(tables: TableStore, store: CharacterStore):
    """A table with two players who each bring a character, and a watcher."""
    table = tables.create(ST, "The Scarlet Gambit")
    for user, name in ((ALICE, "Ashes"), (BOB, "Gearheart")):
        base = store.create(user, _locked(name))
        tables.approve(ST, tables.request(user, table.join_code, base.id).id)
    tables.approve(ST, tables.request(WATCHER, table.join_code, None).id)
    return table


@pytest.fixture
def the_log(tables: TableStore) -> TableLog:
    return TableLog(tables)


@pytest.fixture
def st(tables, store, sessions, the_log) -> TableStoryteller:
    return TableStoryteller(tables, store, sessions, the_log)


def _copies(tables: TableStore, table) -> dict[str, object]:
    """The copies of `table`, keyed by the name of the character."""
    store = CharacterStore(db_path=tables.db_path, root=tables.root)
    return {store.load(row).name: row for row in tables.characters(table.id)}


# --------------------------------------------------------------------------- #
# Grant XP
# --------------------------------------------------------------------------- #


def test_a_grant_to_all_reaches_each_copy_in_the_table(st, tables, store, table) -> None:
    result = st.grant_xp(ST, table.id, 5, "The Gambit, session 1")

    copies = _copies(tables, table)
    assert {name: store.load(row).xp_earned for name, row in copies.items()} == {
        "Ashes": 5, "Gearheart": 5}
    assert result.failed == ()
    assert [r.name for r in result.award.recipients] == ["Ashes", "Gearheart"]


def test_a_grant_to_one_copy_leaves_the_others(st, tables, store, table) -> None:
    copies = _copies(tables, table)

    st.grant_xp(ST, table.id, 3, "", [copies["Gearheart"].id])

    assert store.load(copies["Gearheart"]).xp_earned == 3
    assert store.load(copies["Ashes"]).xp_earned == 0


def test_a_grant_goes_on_the_object_that_the_open_page_holds(
        st, tables, store, sessions, table) -> None:
    """⚠ Trap section 12. The page's auto-save writes `ctx["char"]`. A grant that
    wrote only the file is lost at that save."""
    row = _copies(tables, table)["Ashes"]
    held = sessions.ctx_for(row.id)["char"]

    st.grant_xp(ST, table.id, 4, "", [row.id])

    assert sessions.peek(row.id)["char"] is held
    assert held.xp_earned == 4
    # The file too: the page can be closed, and the registry has no save on eviction.
    assert store.load(row).xp_earned == 4


def test_a_grant_builds_no_context(st, tables, sessions, table) -> None:
    """A context for another account's character is a live object that its owner's
    page does not share (section 8)."""
    st.grant_xp(ST, table.id, 2, "")

    assert len(sessions) == 0


def test_a_negative_grant_corrects_and_stops_at_zero(st, tables, store, table) -> None:
    row = _copies(tables, table)["Ashes"]
    st.grant_xp(ST, table.id, 5, "", [row.id])

    st.grant_xp(ST, table.id, -2, "Over-granted", [row.id])
    assert store.load(row).xp_earned == 3
    st.grant_xp(ST, table.id, -10, "", [row.id])
    assert store.load(row).xp_earned == 0


@pytest.mark.parametrize("user", [ALICE, WATCHER, STRANGER])
def test_only_the_storyteller_grants(st, tables, store, table, user) -> None:
    with pytest.raises(TableStoreError, match="Only the Storyteller"):
        st.grant_xp(user, table.id, 5, "")

    assert all(store.load(row).xp_earned == 0 for row in tables.characters(table.id))
    assert st.awards(table.id) == []


@pytest.mark.parametrize("amount", [0, table_st.MAX_GRANT + 1, -table_st.MAX_GRANT - 1])
def test_an_amount_out_of_range_grants_nothing(st, tables, store, table, amount) -> None:
    with pytest.raises(TableStoreError):
        st.grant_xp(ST, table.id, amount, "")

    assert all(store.load(row).xp_earned == 0 for row in tables.characters(table.id))


def test_a_note_that_is_too_long_grants_nothing(st, tables, store, table) -> None:
    with pytest.raises(TableStoreError):
        st.grant_xp(ST, table.id, 1, "x" * (table_st.MAX_NOTE + 1))

    assert st.awards(table.id) == []


def test_a_copy_outside_the_table_is_refused(st, tables, store, table) -> None:
    """The browser names the copy. A copy of another table, or a solo copy, is not
    the Storyteller's."""
    solo = store.make_copy(ALICE, store.create(ALICE, _locked("Solo")).id)

    with pytest.raises(TableStoreError, match="no longer in this campaign"):
        st.grant_xp(ST, table.id, 5, "", [solo.id])

    assert store.load(solo).xp_earned == 0
    assert all(store.load(row).xp_earned == 0 for row in tables.characters(table.id))


def test_a_table_with_no_characters_refuses_a_grant(st, tables) -> None:
    empty = tables.create(ST, "Empty")

    with pytest.raises(TableStoreError):
        st.grant_xp(ST, empty.id, 5, "")


# --------------------------------------------------------------------------- #
# The award log
# --------------------------------------------------------------------------- #


def test_the_award_log_records_who_how_much_and_why(st, tables, table) -> None:
    first = st.grant_xp(ST, table.id, 5, "  Session 1  ").award
    second = st.grant_xp(ST, table.id, -1, "").award

    assert st.awards_path(table.id) == tables.table_dir(table.id) / "awards.json"
    assert st.awards(table.id) == [first, second]
    assert (first.id, first.user_id, first.amount, first.note) == (1, ST, 5, "Session 1")
    assert second.id == 2
    raw = json.loads(st.awards_path(table.id).read_text(encoding="utf-8"))
    assert raw[0]["recipients"][0]["name"] == "Ashes"


def test_a_grant_posts_one_line_to_the_log(st, the_log, table) -> None:
    st.grant_xp(ST, table.id, 5, "Session 1")

    (entry,) = the_log.entries(table.id)
    assert entry.user_id == ST
    assert entry.text == "+5 XP to Ashes, Gearheart — Session 1"


def test_the_log_line_of_a_grant_does_not_name_an_enemy_npc(
        st, tables, store, the_log, table) -> None:
    """Each member reads the Log. The award log keeps each name (step 8)."""
    for name, side in (("Hidden Assassin", "enemy"), ("Friendly Sage", "ally")):
        tables.bring(ST, table.id, store.create(ST, _locked(name)).id, side=side)
    copies = _copies(tables, table)

    award = st.grant_xp(ST, table.id, 3, "", [copies[n].id for n in (
        "Ashes", "Hidden Assassin", "Friendly Sage")]).award
    st.grant_xp(ST, table.id, 1, "", [copies["Hidden Assassin"].id])

    assert [e.text for e in the_log.entries(table.id)] == [
        "+3 XP to Ashes, Friendly Sage"]
    assert "Hidden Assassin" in [r.name for r in award.recipients]


def test_a_grant_with_no_note_posts_no_dash(st, tables, the_log, table) -> None:
    st.grant_xp(ST, table.id, -2, "", [_copies(tables, table)["Ashes"].id])

    assert the_log.entries(table.id)[0].text == "-2 XP to Ashes"


def test_a_copy_that_cannot_save_is_reported_and_not_granted(
        st, tables, store, sessions, table, monkeypatch) -> None:
    """A full account refuses the save of its character. The other copy gets its
    grant, and the live object of the refused one keeps its old XP."""
    copies = _copies(tables, table)
    held = sessions.ctx_for(copies["Ashes"].id)["char"]
    real_save = CharacterStore.save

    def save(self, row, character):
        if row.id == copies["Ashes"].id:
            raise QuotaExceeded("This account has no space left.")
        real_save(self, row, character)

    monkeypatch.setattr(CharacterStore, "save", save)
    result = st.grant_xp(ST, table.id, 5, "")

    assert result.failed == ("Ashes",)
    assert [r.name for r in result.award.recipients] == ["Gearheart"]
    assert held.xp_earned == 0
    assert store.load(copies["Gearheart"]).xp_earned == 5


def test_a_full_table_folder_grants_nothing(st, tables, store, sessions, table) -> None:
    """The award log is written after the copies. When it cannot be written, each
    copy goes back to its old XP, the live object too."""
    row = _copies(tables, table)["Ashes"]
    held = sessions.ctx_for(row.id)["char"]
    table_dir = tables.table_dir(table.id).resolve()
    real_guard = FolderQuota(tables.root)

    def guard(path: Path, size: int) -> None:
        if path.resolve().is_relative_to(table_dir):
            raise QuotaExceeded("This campaign has no space left.")
        real_guard(path, size)

    persistence.set_write_guard(guard)
    try:
        with pytest.raises(QuotaExceeded):
            st.grant_xp(ST, table.id, 5, "")
    finally:
        persistence.set_write_guard(None)

    assert held.xp_earned == 0
    assert all(store.load(r).xp_earned == 0 for r in tables.characters(table.id))
    assert not st.awards_path(table.id).exists()


def test_a_deleted_campaign_takes_its_awards(st, tables, table) -> None:
    st.grant_xp(ST, table.id, 5, "")

    tables.delete(ST, table.id)

    assert not st.awards_path(table.id).exists()


# --------------------------------------------------------------------------- #
# Unlock (Q6)
# --------------------------------------------------------------------------- #


def test_the_storyteller_unlocks_the_object_that_the_open_page_holds(
        st, tables, store, sessions, table) -> None:
    row = _copies(tables, table)["Ashes"]
    held = sessions.ctx_for(row.id)["char"]

    st.unlock(ST, table.id, row.id)

    assert not held.chargen_locked
    assert not store.load(row).chargen_locked


def test_an_unlock_with_no_page_open_is_saved(st, tables, store, sessions, table) -> None:
    row = _copies(tables, table)["Gearheart"]

    st.unlock(ST, table.id, row.id)

    assert not store.load(row).chargen_locked
    assert len(sessions) == 0


@pytest.mark.parametrize("user", [ALICE, WATCHER, STRANGER])
def test_only_the_storyteller_unlocks(st, tables, store, table, user) -> None:
    row = _copies(tables, table)["Ashes"]

    with pytest.raises(TableStoreError, match="Only the Storyteller"):
        st.unlock(user, table.id, row.id)

    assert store.load(row).chargen_locked


def test_an_unlock_outside_the_table_is_refused(st, tables, store, table) -> None:
    solo = store.make_copy(ALICE, store.create(ALICE, _locked("Solo")).id)

    with pytest.raises(TableStoreError, match="no longer in this campaign"):
        st.unlock(ST, table.id, solo.id)

    assert store.load(solo).chargen_locked


def test_an_unlocked_copy_is_not_unlocked_again(st, tables, store, table) -> None:
    row = _copies(tables, table)["Ashes"]
    st.unlock(ST, table.id, row.id)

    with pytest.raises(TableStoreError, match="not locked"):
        st.unlock(ST, table.id, row.id)


def test_an_unlock_after_xp_keeps_the_xp_log(st, tables, store, table) -> None:
    """Ruled 2026-09-12: an Unlock after XP is allowed. The table view warns first."""
    row = _copies(tables, table)["Ashes"]
    character = store.load(row)
    character.xp_log.append(XpEntry(target="essence", from_rating=2, to_rating=3, cost=16))
    store.save(row, character)

    st.unlock(ST, table.id, row.id)

    assert len(store.load(row).xp_log) == 1


def test_an_empty_list_is_refused(st, tables, store, table) -> None:
    """An empty list is "nobody", not "everyone" (the None of the argument)."""
    with pytest.raises(TableStoreError, match="Tick at least one"):
        st.grant_xp(ST, table.id, 5, "", [])
    assert all(store.load(r).xp_earned == 0 for r in tables.characters(table.id))
