"""The roster, the NPC sides and the notes of a campaign.

Step 8 of the build order in `docs/plans/p3-tables.md` section 15.4:
`server/table_roster.py` (R4, R6, R7, R8), the sides of the NPCs in
`server/tables.py` (human, 2026-09-24: the Storyteller picks the side when the NPC
is added), and `server/table_notes.py` (Q8, Q9).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from exalted_builder.engine import adversaries as adv
from exalted_builder.engine import lifecycle
from exalted_builder.models.adversary import ALLY, ENEMY, Adversary
from exalted_builder.models.character import Character, Damage
from exalted_builder.models.party import Party
from exalted_builder.server import db
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.table_notes import MAX_NOTES, TableNotes, TableNotesError
from exalted_builder.server.table_roster import TableRoster
from exalted_builder.server.tables import TableStore, TableStoreError
from exalted_builder.ui import view as viewmod

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


def _characters(tables: TableStore) -> CharacterStore:
    return CharacterStore(db_path=tables.db_path, root=tables.root)


def _base(tables: TableStore, owner: int, name: str):
    character = Character(id="x", name=name, caste="dawn")
    lifecycle.lock_chargen(character)
    return _characters(tables).create(owner, character)


@pytest.fixture
def table(tables: TableStore):
    """A table with a player who brings a character and a member who watches."""
    table = tables.create(ST, "The Scarlet Gambit")
    for user, base_id in ((PLAYER, _base(tables, PLAYER, "Ashes").id), (WATCHER, None)):
        tables.approve(ST, tables.request(user, table.join_code, base_id).id)
    return table


@pytest.fixture
def roster(tables: TableStore) -> TableRoster:
    return TableRoster(tables)


def _npc(tables: TableStore, table, side=None, name="Bandit Lord"):
    """Bring a base of the Storyteller into `table` with `side`. Return the copy."""
    tables.bring(ST, table.id, _base(tables, ST, name).id, side=side)
    (row,) = [r for r in tables.characters(table.id) if r.owner_id == ST
              and _characters(tables).load(r).name == name]
    return row


# --------------------------------------------------------------------------- #
# The model
# --------------------------------------------------------------------------- #


def test_an_entry_is_an_enemy_by_default_and_an_old_roster_loads_as_enemies() -> None:
    assert Adversary(id="a").side == ENEMY
    old = Party.model_validate({"id": "p", "adversaries": [{"id": "adv.1", "name": "X"}]})
    assert old.adversaries[0].side == ENEMY


def test_a_duplicate_keeps_the_side() -> None:
    party = Party(id="p", adversaries=[Adversary(id="adv.1", name="Guard", side=ALLY)])
    assert adv.duplicate(party, 0).side == ALLY


# --------------------------------------------------------------------------- #
# The projection (R7)
# --------------------------------------------------------------------------- #


def test_the_ally_view_has_the_name_and_the_health_track_only() -> None:
    a = Adversary(id="adv.1", name="Guard", side=ALLY, health_levels=[0, -1, adv.INCAPACITATED],
                  damage=[Damage.LETHAL], willpower=7, essence=3, notes="secret plan",
                  charms="Heaven Thunder Hammer")
    view = viewmod.ally_view(a)
    assert view.name == "Guard"
    assert [(b.label, b.mark) for b in view.boxes] == [
        ("0", Damage.LETHAL), ("-1", None), ("Incap", None)]
    assert set(vars(view)) == {"key", "name", "boxes"}


# --------------------------------------------------------------------------- #
# The roster
# --------------------------------------------------------------------------- #


def test_the_storyteller_changes_the_live_roster_and_save_writes_it(
        tables: TableStore, table, roster: TableRoster) -> None:
    party = roster.party(ST, table.id)
    entry = adv.add_blank(party, name="Bandit")
    entry.side = ALLY
    before = roster.version(table.id)
    roster.save(ST, table.id)

    assert roster.version(table.id) == before + 1
    (saved,) = json.loads(roster.path(table.id).read_text())
    assert (saved["name"], saved["side"]) == ("Bandit", ALLY)
    # A second store reads the file: a new process.
    assert TableRoster(tables).party(ST, table.id).adversaries[0].name == "Bandit"


def test_the_two_devices_of_the_storyteller_share_one_roster(
        table, roster: TableRoster) -> None:
    assert roster.party(ST, table.id) is roster.party(ST, table.id)


@pytest.mark.parametrize("user", [PLAYER, WATCHER, STRANGER])
def test_only_the_storyteller_gets_the_roster_and_saves_it(
        table, roster: TableRoster, user: int) -> None:
    with pytest.raises(TableStoreError):
        roster.party(user, table.id)
    with pytest.raises(TableStoreError):
        roster.save(user, table.id)


def test_a_member_gets_the_allies_as_projections_and_never_an_enemy(
        table, roster: TableRoster) -> None:
    party = roster.party(ST, table.id)
    adv.add_blank(party, name="Hidden Assassin")
    ally = adv.add_blank(party, name="Loyal Guard")
    ally.side = ALLY
    roster.save(ST, table.id)

    for user in (PLAYER, WATCHER, ST):
        allies = roster.allies(user, table.id)
        assert [a.name for a in allies] == ["Loyal Guard"]
        assert all(isinstance(a, viewmod.AllyView) for a in allies)
    assert roster.allies(STRANGER, table.id) == []


def test_a_roster_that_does_not_read_is_empty(tables, table, roster: TableRoster) -> None:
    roster.path(table.id).parent.mkdir(parents=True, exist_ok=True)
    roster.path(table.id).write_text("{not json")
    assert roster.party(ST, table.id).adversaries == []


def test_a_deleted_table_forgets_the_live_roster(tables, table, roster: TableRoster) -> None:
    roster.party(ST, table.id)
    tables.delete(ST, table.id)
    with pytest.raises(TableStoreError):
        roster.save(ST, table.id)
    assert table.id not in roster._live


# --------------------------------------------------------------------------- #
# The sides of the NPCs (human, 2026-09-24)
# --------------------------------------------------------------------------- #


def test_the_storyteller_picks_the_side_when_bringing_an_npc(tables, table) -> None:
    ally = _npc(tables, table, side=ALLY, name="Friendly Sage")
    enemy = _npc(tables, table, side=ENEMY, name="Bandit Lord")
    assert tables.npc_side(table.id, ally.id) == ALLY
    assert tables.npc_side(table.id, enemy.id) == ENEMY
    # The side of the base is given to the copy, and does not stay.
    assert set(tables.npc_sides(table.id)) == {ally.id, enemy.id}


def test_an_npc_with_no_side_is_an_enemy(tables, table) -> None:
    assert tables.npc_side(table.id, _npc(tables, table).id) == ENEMY


def test_a_draft_of_the_storyteller_keeps_its_side_until_the_lock(tables, table) -> None:
    draft = tables.start_draft(ST, table.id, side=ALLY)
    characters = _characters(tables)
    character = characters.load(draft)
    character.name = "Drafted Ally"
    lifecycle.lock_chargen(character)
    characters.save(draft, character)
    tables.send_draft(ST, draft.id)

    (copy,) = [r for r in tables.characters(table.id) if r.owner_id == ST]
    assert tables.npc_side(table.id, copy.id) == ALLY
    assert draft.id not in tables.npc_sides(table.id)


def test_a_player_cannot_pick_a_side(tables, table) -> None:
    base = _base(tables, PLAYER, "Second")
    with pytest.raises(TableStoreError):
        tables.bring(PLAYER, table.id, base.id, side=ALLY)
    with pytest.raises(TableStoreError):
        tables.start_draft(PLAYER, table.id, side=ALLY)
    assert tables.npc_sides(table.id) == {}


def test_the_storyteller_switches_the_side_of_an_npc(tables, table) -> None:
    npc = _npc(tables, table, side=ENEMY)
    tables.set_npc_side(ST, table.id, npc.id, ALLY)
    assert tables.npc_side(table.id, npc.id) == ALLY


def test_the_switch_refuses_a_player_a_player_character_and_a_bad_side(
        tables, table) -> None:
    npc = _npc(tables, table)
    (player_copy,) = [r for r in tables.characters(table.id) if r.owner_id == PLAYER]
    with pytest.raises(TableStoreError):
        tables.set_npc_side(PLAYER, table.id, npc.id, ALLY)
    with pytest.raises(TableStoreError):
        tables.set_npc_side(ST, table.id, player_copy.id, ALLY)
    with pytest.raises(TableStoreError):
        tables.set_npc_side(ST, table.id, npc.id, "neutral")
    assert tables.npc_side(table.id, npc.id) == ENEMY


# --------------------------------------------------------------------------- #
# The notes (Q8, Q9)
# --------------------------------------------------------------------------- #


def test_each_member_reads_only_their_own_notes(tables, table) -> None:
    notes = TableNotes(tables)
    notes.write(PLAYER, table.id, "The sage lies.")
    notes.write(ST, table.id, "The sage is the villain.")

    assert notes.read(PLAYER, table.id) == "The sage lies."
    assert notes.read(ST, table.id) == "The sage is the villain."
    assert notes.read(WATCHER, table.id) == ""
    assert notes.read(STRANGER, table.id) == ""


def test_a_stranger_cannot_write_notes_and_a_long_text_is_refused(tables, table) -> None:
    notes = TableNotes(tables)
    with pytest.raises(TableNotesError):
        notes.write(STRANGER, table.id, "hello")
    with pytest.raises(TableNotesError):
        notes.write(PLAYER, table.id, "x" * (MAX_NOTES + 1))
    assert not tables.notes_path(table.id, STRANGER).exists()


def test_a_leave_and_a_removal_delete_the_notes_of_that_member(tables, table) -> None:
    notes = TableNotes(tables)
    notes.write(PLAYER, table.id, "mine")
    notes.write(WATCHER, table.id, "theirs")
    notes.write(ST, table.id, "the ST's")

    tables.leave(PLAYER, table.id)
    tables.remove(ST, table.id, WATCHER)

    assert not tables.notes_path(table.id, PLAYER).exists()
    assert not tables.notes_path(table.id, WATCHER).exists()
    assert notes.read(ST, table.id) == "the ST's"
