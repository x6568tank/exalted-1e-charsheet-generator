"""The house rules of a campaign: `house_rules.json`, `apply_table_rules`, and the
Storyteller's switches in `server/table_st.py`.

Step 6 of the build order in `docs/plans/p3-tables.md` section 15.4. The design is
section 5, and Q2 (ruled 2026-09-12: the Storyteller sets the PER-CHARACTER
permissions of a campaign copy).

⚠ Section 5: the table's file is canonical, and each copy holds a synced copy.
`apply_table_rules` runs at three sites: at approval, on each copy when the ST
changes a switch, and in the character context factory. An overlay at the read
sites is the house bug, type 1.

⚠ Trap section 12, "written behind an open page": a copy that has a live context
gets the change on THAT object.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from exalted_builder import persistence
from exalted_builder.engine import lifecycle
from exalted_builder.engine.house_rule_actions import apply_table_rules
from exalted_builder.models.character import (
    TABLE_WIDE_HOUSE_RULES, Character, HouseRules)
from exalted_builder.server import db
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.quota import FolderQuota, QuotaExceeded
from exalted_builder.server.session import SessionRegistry
from exalted_builder.server.table_log import TableLog
from exalted_builder.server.table_st import TableStoryteller
from exalted_builder.server.tables import TableStore, TableStoreError
from exalted_builder.ui import view as viewmod

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


@pytest.fixture
def sessions(store: CharacterStore) -> SessionRegistry:
    return SessionRegistry(factory=lambda key: {"char": store.load(store.row(key))})


def _locked(name: str, rules: HouseRules | None = None) -> Character:
    character = Character(id="x", name=name, caste="dawn", house_rules=rules)
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
    store = CharacterStore(db_path=tables.db_path, root=tables.root)
    return {store.load(row).name: row for row in tables.characters(table.id)}


# --------------------------------------------------------------------------- #
# Which fields are TABLE-WIDE
# --------------------------------------------------------------------------- #


def test_the_table_wide_set_is_the_table_scope_of_the_st_tab(ruleset) -> None:
    """One list, two readers: the ST Options tab groups by scope, and the table
    syncs the TABLE-WIDE fields. If they disagree, a switch the tab calls
    "table-wide" is one the campaign never syncs."""
    rows = viewmod.build_house_rules(ruleset, Character(id="x"))
    assert {r.field for r in rows if r.scope == "table"} == TABLE_WIDE_HOUSE_RULES
    assert {r.field for r in rows} == set(HouseRules.model_fields)


def test_apply_overwrites_the_table_wide_fields_only() -> None:
    character = Character(id="x", house_rules=HouseRules(
        magic_for_everyone=False, mf_change_method="swap", st_foreign_charms=True,
        terrestrial_essence_transcendence=True))
    table_rules = HouseRules(magic_for_everyone=True, mf_change_method="backgrounds",
                             godblooded_inheritance_rating=3,
                             st_foreign_charms=False)   # PER-CHARACTER: ignored

    assert apply_table_rules(table_rules, character) is True

    rules = character.house_rules
    assert rules.magic_for_everyone is True
    assert rules.mf_change_method == "backgrounds"
    assert rules.godblooded_inheritance_rating == 3
    assert rules.st_foreign_charms is True, "A PER-CHARACTER field was overwritten."
    assert rules.terrestrial_essence_transcendence is True
    assert rules is not table_rules


def test_apply_to_a_character_with_no_house_rules_makes_them() -> None:
    character = Character(id="x")
    assert apply_table_rules(HouseRules(all_backgrounds_available=True), character)
    assert character.house_rules.all_backgrounds_available is True


def test_apply_reports_no_change_when_the_copy_agrees() -> None:
    character = Character(id="x", house_rules=HouseRules(magic_for_everyone=True))
    assert apply_table_rules(HouseRules(magic_for_everyone=True), character) is False


def test_apply_to_a_locked_character_leaves_the_snapshot() -> None:
    """The snapshot is the record of the creation. A table switch changes the live
    rules; chargen accounting reads the snapshot (`chargen_house_rules`)."""
    character = _locked("Ashes")
    apply_table_rules(HouseRules(restrict_chargen_ritual_level=True), character)
    assert character.house_rules.restrict_chargen_ritual_level is True
    assert character.chargen_snapshot.house_rules is None


# --------------------------------------------------------------------------- #
# The file
# --------------------------------------------------------------------------- #


def test_a_new_table_has_the_default_rules(tables, table) -> None:
    assert tables.house_rules(table.id) == HouseRules()


def test_the_rules_are_written_to_the_table_folder(tables, table) -> None:
    tables.write_house_rules(table.id, HouseRules(magic_for_everyone=True))
    assert (tables.table_dir(table.id) / "house_rules.json").exists()
    assert tables.house_rules(table.id).magic_for_everyone is True


def test_a_file_that_does_not_read_gives_the_default(tables, table) -> None:
    (tables.table_dir(table.id) / "house_rules.json").write_text("{nope", encoding="utf-8")
    assert tables.house_rules(table.id) == HouseRules()


def test_only_the_table_wide_fields_are_written(tables, table) -> None:
    """The table's file holds the TABLE-WIDE fields. A PER-CHARACTER value in it
    would read as a table value that nothing syncs."""
    tables.write_house_rules(table.id, HouseRules(st_foreign_charms=True,
                                                  magic_for_everyone=True))
    text = (tables.table_dir(table.id) / "house_rules.json").read_text(encoding="utf-8")
    assert "st_foreign_charms" not in text
    assert tables.house_rules(table.id).st_foreign_charms is False


# --------------------------------------------------------------------------- #
# Site 1: approval
# --------------------------------------------------------------------------- #


def test_approval_gives_the_copy_the_table_rules(tables, store) -> None:
    table = tables.create(ST, "The Scarlet Gambit")
    tables.write_house_rules(table.id, HouseRules(mf_change_method="swap",
                                                  all_backgrounds_available=True))
    base = store.create(ALICE, _locked("Ashes", HouseRules(st_foreign_charms=True)))

    copy = tables.approve(ST, tables.request(ALICE, table.join_code, base.id).id)

    rules = store.load(copy).house_rules
    assert rules.mf_change_method == "swap"
    assert rules.all_backgrounds_available is True
    assert rules.st_foreign_charms is True, "The base's permission was lost."
    assert store.load(base).house_rules.mf_change_method == "experience", \
        "The base was changed."


# --------------------------------------------------------------------------- #
# Site 2: the Storyteller's switch
# --------------------------------------------------------------------------- #


def test_a_table_switch_reaches_each_copy_and_the_file(st, tables, store, table) -> None:
    result = st.set_table_rule(ST, table.id, "magic_for_everyone", True)

    assert result == ()
    assert tables.house_rules(table.id).magic_for_everyone is True
    assert {name: store.load(row).house_rules.magic_for_everyone
            for name, row in _copies(tables, table).items()} == {
        "Ashes": True, "Gearheart": True}


def test_a_table_switch_goes_on_the_object_that_the_open_page_holds(
        st, tables, store, sessions, table) -> None:
    row = _copies(tables, table)["Ashes"]
    held = sessions.ctx_for(row.id)["char"]

    st.set_table_rule(ST, table.id, "all_backgrounds_available", True)

    assert sessions.peek(row.id)["char"] is held
    assert held.house_rules.all_backgrounds_available is True
    assert store.load(row).house_rules.all_backgrounds_available is True


def test_a_table_switch_builds_no_context(st, tables, sessions, table) -> None:
    st.set_table_rule(ST, table.id, "magic_for_everyone", True)
    assert all(sessions.peek(row.id) is None for row in tables.characters(table.id))


def test_the_select_rules_are_coerced(st, tables, table) -> None:
    st.set_table_rule(ST, table.id, "godblooded_inheritance_rating", "3")
    assert tables.house_rules(table.id).godblooded_inheritance_rating == 3
    st.set_table_rule(ST, table.id, "godblooded_inheritance_rating", "per-character")
    assert tables.house_rules(table.id).godblooded_inheritance_rating is None
    st.set_table_rule(ST, table.id, "mf_change_method", "swap")
    assert tables.house_rules(table.id).mf_change_method == "swap"


@pytest.mark.parametrize("user", [ALICE, WATCHER, 99])
def test_only_the_storyteller_sets_a_table_switch(st, tables, store, table, user) -> None:
    with pytest.raises(TableStoreError):
        st.set_table_rule(user, table.id, "magic_for_everyone", True)
    assert tables.house_rules(table.id).magic_for_everyone is False
    assert not any(store.load(row).house_rules and
                   store.load(row).house_rules.magic_for_everyone
                   for row in tables.characters(table.id))


def test_a_per_character_field_is_not_a_table_switch(st, tables, store, table) -> None:
    with pytest.raises(TableStoreError):
        st.set_table_rule(ST, table.id, "st_foreign_charms", True)
    assert not any(store.load(row).house_rules and
                   store.load(row).house_rules.st_foreign_charms
                   for row in tables.characters(table.id))


def test_an_unknown_field_is_refused(st, table) -> None:
    with pytest.raises(TableStoreError):
        st.set_table_rule(ST, table.id, "no_such_rule", True)


def test_a_table_switch_posts_to_the_log(st, the_log, table) -> None:
    st.set_table_rule(ST, table.id, "magic_for_everyone", True)
    (entry,) = the_log.entries(table.id)
    assert entry.user_id == ST
    assert entry.text == "House rule: Magic for Everyone — On"


def test_a_copy_that_cannot_be_saved_is_named(
        st, tables, store, table, monkeypatch) -> None:
    """The other copies get the switch. The failed copy is named; its next load
    takes the table's value (site 3)."""
    row = _copies(tables, table)["Gearheart"]
    real_save = CharacterStore.save

    def save(self, target, character):
        if target.id == row.id:
            raise QuotaExceeded("This account has no space left.")
        real_save(self, target, character)

    monkeypatch.setattr(CharacterStore, "save", save)
    failed = st.set_table_rule(ST, table.id, "magic_for_everyone", True)
    monkeypatch.undo()

    assert failed == ("Gearheart",)
    assert tables.house_rules(table.id).magic_for_everyone is True
    assert store.load(_copies(tables, table)["Ashes"]).house_rules.magic_for_everyone


def test_a_full_table_folder_changes_nothing(st, tables, store, sessions, table) -> None:
    """The file is written first. If it cannot be, no copy changes."""
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
            st.set_table_rule(ST, table.id, "magic_for_everyone", True)
    finally:
        persistence.set_write_guard(None)

    assert held.house_rules is None or not held.house_rules.magic_for_everyone
    assert tables.house_rules(table.id).magic_for_everyone is False
    assert not any(store.load(row).house_rules and
                   store.load(row).house_rules.magic_for_everyone
                   for row in tables.characters(table.id))


# --------------------------------------------------------------------------- #
# Q2: the PER-CHARACTER permissions
# --------------------------------------------------------------------------- #


def test_the_storyteller_grants_one_copy_a_permission(st, tables, store, table) -> None:
    copies = _copies(tables, table)

    st.set_character_rule(ST, table.id, copies["Ashes"].id, "st_foreign_charms", True)

    assert store.load(copies["Ashes"]).house_rules.st_foreign_charms is True
    other = store.load(copies["Gearheart"]).house_rules
    assert other is None or other.st_foreign_charms is False


def test_a_permission_goes_on_the_object_that_the_open_page_holds(
        st, tables, store, sessions, table) -> None:
    row = _copies(tables, table)["Ashes"]
    held = sessions.ctx_for(row.id)["char"]

    st.set_character_rule(ST, table.id, row.id, "terrestrial_essence_transcendence", True)

    assert held.house_rules.terrestrial_essence_transcendence is True
    assert store.load(row).house_rules.terrestrial_essence_transcendence is True


@pytest.mark.parametrize("user", [ALICE, WATCHER, 99])
def test_only_the_storyteller_grants_a_permission(st, tables, store, table, user) -> None:
    """Q2: the owner too is refused — the player may not grant themself."""
    row = _copies(tables, table)["Ashes"]
    with pytest.raises(TableStoreError):
        st.set_character_rule(user, table.id, row.id, "st_foreign_charms", True)
    rules = store.load(row).house_rules
    assert rules is None or rules.st_foreign_charms is False


def test_a_table_wide_field_is_not_a_permission(st, tables, store, table) -> None:
    """A TABLE-WIDE field set on one copy would drift, and site 3 flips it back."""
    row = _copies(tables, table)["Ashes"]
    with pytest.raises(TableStoreError):
        st.set_character_rule(ST, table.id, row.id, "magic_for_everyone", True)


def test_a_permission_for_a_copy_in_another_table_is_refused(
        st, tables, store, table) -> None:
    other = tables.create(ST, "Another")
    base = store.create(ALICE, _locked("Elsewhere"))
    copy = tables.approve(ST, tables.request(ALICE, other.join_code, base.id).id)
    with pytest.raises(TableStoreError):
        st.set_character_rule(ST, table.id, copy.id, "st_foreign_charms", True)
    rules = store.load(copy).house_rules
    assert rules is None or rules.st_foreign_charms is False
