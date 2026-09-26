"""Initiative for the whole table: `server/table_initiative.py` (P3 step 9).

The gate of P3 (`docs/plans/p3-tables.md` sections 9 and 15.4). Rulings, human,
2026-09-24:

  * The player sets the weapon in hand on YOU PLAY. It is saved on the copy
    (`PlayState.in_hand`). The rating reads it. The default is unarmed.
  * The Storyteller rolls from a checklist of each player copy, each NPC and each
    roster entry, all ticked.
  * The result goes to the Log. Each combatant is named there, an enemy NPC too
    (human, 2026-09-25).
  * Ties break on Dexterity + Wits, else "tied". A roster entry with no Base
    initiative cannot roll.

⚠ The server rolls the d10 (`engine.dice.roll`). The browser sends keys only.
"""

from __future__ import annotations

from pathlib import Path
import random

import pytest

from exalted_builder import rules_db
from exalted_builder.engine import lifecycle
from exalted_builder.models.adversary import ALLY, ENEMY, Adversary
from exalted_builder.models.character import Character, PlayState, Weapon
from exalted_builder.models.rules import AttributeName
from exalted_builder.server import db
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.rulesets import Rulesets
from exalted_builder.server.session import SessionRegistry
from exalted_builder.server.table_initiative import TableInitiative
from exalted_builder.server.table_log import TableLog, TableLogError
from exalted_builder.server.table_roster import TableRoster
from exalted_builder.server.tables import TableStore, TableStoreError
from exalted_builder.ui import view as viewmod

ST, ALICE, BOB, WATCHER, STRANGER = 1, 2, 3, 4, 5

_DATA = Path(__file__).resolve().parents[1] / "exalted_builder" / "data"


@pytest.fixture(scope="module")
def book():
    return rules_db.load_ruleset(_DATA)


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
    return SessionRegistry(factory=lambda key: {"char": store.load(store.row(key))})


def _locked(name: str, dex: int = 3, wits: int = 2, weapons=()) -> Character:
    character = Character(id="x", name=name, caste="dawn")
    character.attributes[AttributeName.DEXTERITY] = dex
    character.attributes[AttributeName.WITS] = wits
    character.weapons = list(weapons)
    lifecycle.lock_chargen(character)
    return character


@pytest.fixture
def table(tables: TableStore, store: CharacterStore):
    """Alice brings Ashes (Dex 4 + Wits 3, a Daiklave), Bob brings Gearheart
    (Dex 2 + Wits 2), and a member watches."""
    table = tables.create(ST, "The Scarlet Gambit")
    ashes = _locked("Ashes", 4, 3, [Weapon(name="Knife", speed=1),
                                    Weapon(name="Daiklave", speed=3)])
    for user, character in ((ALICE, ashes), (BOB, _locked("Gearheart", 2, 2))):
        base = store.create(user, character)
        tables.approve(ST, tables.request(user, table.join_code, base.id).id)
    tables.approve(ST, tables.request(WATCHER, table.join_code, None).id)
    return table


@pytest.fixture
def the_log(tables: TableStore) -> TableLog:
    return TableLog(tables)


@pytest.fixture
def roster(tables: TableStore) -> TableRoster:
    return TableRoster(tables)


@pytest.fixture
def init(tables, store, book, sessions, roster, the_log) -> TableInitiative:
    return TableInitiative(tables, store, Rulesets(book, store, tables), sessions,
                           roster, the_log)


def _copy(tables, store, table, name):
    (row,) = [r for r in tables.characters(table.id) if store.load(r).name == name]
    return row


def _npc(tables, store, table, name, side, dex=5, wits=5):
    tables.bring(ST, table.id, store.create(ST, _locked(name, dex, wits)).id, side=side)
    return _copy(tables, store, table, name)


def _entry(roster, table, name, side, base_initiative, **kw):
    party = roster.party(ST, table.id)
    entry = Adversary(id=f"adv.{name.lower()}", name=name, side=side,
                      base_initiative=base_initiative, **kw)
    party.adversaries.append(entry)
    roster.save(ST, table.id)
    return entry


class _Faces(random.Random):
    """An rng whose `randint` gives the faces in order."""

    def __init__(self, *faces: int) -> None:
        super().__init__(0)
        self.faces = list(faces)

    def randint(self, a: int, b: int) -> int:
        return self.faces.pop(0)


# --------------------------------------------------------------------------- #
# The weapon in hand (PlayState.in_hand)
# --------------------------------------------------------------------------- #


def test_the_weapon_in_hand_is_saved_and_unarmed_by_default(store, tables, table):
    row = _copy(tables, store, table, "Ashes")
    character = store.load(row)
    assert (character.play or PlayState()).in_hand == ""
    assert viewmod.wielded_index(character) is None

    from exalted_builder.engine import play as engineplay
    engineplay.set_in_hand(character, "Daiklave")
    store.save(row, character)
    again = store.load(row)
    assert again.play.in_hand == "Daiklave"
    assert viewmod.wielded_index(again) == 1


def test_a_weapon_in_hand_that_is_gone_is_unarmed():
    character = _locked("Ashes", weapons=[Weapon(name="Knife", speed=1)])
    character.play = PlayState(in_hand="Daiklave")
    assert viewmod.wielded_index(character) is None


# --------------------------------------------------------------------------- #
# The combatants
# --------------------------------------------------------------------------- #


def test_the_combatants_are_the_party_the_npcs_and_the_roster(
        init, tables, store, table, roster):
    _npc(tables, store, table, "Bandit Lord", ENEMY)
    _npc(tables, store, table, "Old Friend", ALLY)
    _entry(roster, table, "Bandit", ENEMY, 6)
    _entry(roster, table, "Guard", ALLY, 4)
    _entry(roster, table, "Beast", ENEMY, None)

    got = {c.name: c for c in init.combatants(ST, table.id)}
    assert set(got) == {"Ashes", "Gearheart", "Bandit Lord", "Old Friend", "Bandit",
                        "Guard", "Beast"}
    assert got["Ashes"].group == "party" and got["Gearheart"].group == "party"
    assert got["Bandit Lord"].group == ENEMY and got["Old Friend"].group == ALLY
    assert got["Bandit"].group == ENEMY and got["Guard"].group == ALLY
    assert got["Ashes"].rating == 7 and got["Ashes"].weapon == ""
    assert got["Bandit"].rating == 6
    assert got["Beast"].rating is None


def test_the_rating_reads_the_weapon_in_hand(init, tables, store, table):
    row = _copy(tables, store, table, "Ashes")
    character = store.load(row)
    character.play = PlayState(in_hand="Daiklave")
    store.save(row, character)
    (ashes,) = [c for c in init.combatants(ST, table.id) if c.name == "Ashes"]
    assert (ashes.rating, ashes.weapon) == (10, "Daiklave")


def test_the_rating_reads_the_live_context_of_an_open_copy(
        init, tables, store, table, sessions):
    """A player who sets the weapon on YOU PLAY changes the live object. The roll
    must see it before the next save."""
    row = _copy(tables, store, table, "Ashes")
    sessions.ctx_for(row.id)["char"].play = PlayState(in_hand="Knife")
    (ashes,) = [c for c in init.combatants(ST, table.id) if c.name == "Ashes"]
    assert ashes.rating == 8


def test_only_the_storyteller_gets_the_combatants_and_rolls(init, table):
    for user in (ALICE, WATCHER, STRANGER):
        with pytest.raises(TableStoreError):
            init.combatants(user, table.id)
        with pytest.raises(TableStoreError):
            init.roll(user, table.id, ["char:x"])


# --------------------------------------------------------------------------- #
# The roll
# --------------------------------------------------------------------------- #


def test_the_roll_posts_the_order_to_the_log(init, tables, store, table, the_log, roster):
    _entry(roster, table, "Bandit", ENEMY, 6)
    keys = [c.key for c in init.combatants(ST, table.id)]
    # Ashes 7, Gearheart 4, Bandit 6 — in the order of the combatants.
    entry = init.roll(ST, table.id, keys, rng=_Faces(2, 9, 5))

    assert the_log.entries(table.id)[-1] == entry
    assert entry.user_id == ST and entry.roll is None
    lines = entry.initiative
    assert [(ln.name, ln.total, ln.rating, ln.d10) for ln in lines] == [
        ("Gearheart", 13, 4, 9), ("Bandit", 11, 6, 5), ("Ashes", 9, 7, 2)]
    assert [ln.group for ln in lines] == ["party", ENEMY, "party"]


def test_the_d10_comes_from_the_dice_roller(init, table, monkeypatch):
    """⚠ The server rolls. A test that the face is the face of `dice.roll`."""
    from exalted_builder.engine import dice
    calls = []
    real = dice.roll

    def spy(count, *args, **kw):
        calls.append(count)
        return real(count, *args, **kw)

    monkeypatch.setattr(dice, "roll", spy)
    keys = [c.key for c in init.combatants(ST, table.id)]
    init.roll(ST, table.id, keys, rng=_Faces(3, 4))
    assert calls == [1, 1]


def test_an_unticked_combatant_does_not_roll(init, table):
    (ashes,) = [c for c in init.combatants(ST, table.id) if c.name == "Ashes"]
    entry = init.roll(ST, table.id, [ashes.key], rng=_Faces(5))
    assert [ln.name for ln in entry.initiative] == ["Ashes"]


def test_each_combatant_is_named_in_the_log(init, tables, store, table, roster):
    """Human, 2026-09-25: an enemy NPC is named to the players in the turn order.
    This replaces the step-8 "Enemy" name for initiative only."""
    _npc(tables, store, table, "Bandit Lord", ENEMY)
    _npc(tables, store, table, "Assassin", ENEMY)
    _npc(tables, store, table, "Old Friend", ALLY)
    _entry(roster, table, "Bandit", ENEMY, 6)
    keys = [c.key for c in init.combatants(ST, table.id)
            if c.group != "party"]
    entry = init.roll(ST, table.id, keys, rng=_Faces(1, 1, 1, 1))
    assert {ln.name for ln in entry.initiative} == {
        "Bandit Lord", "Assassin", "Old Friend", "Bandit"}


def test_an_npc_with_no_side_is_named_in_the_log(init, tables, store, table):
    """Step 8: an NPC with no side entry is an enemy. It is named."""
    tables.bring(ST, table.id, store.create(ST, _locked("Stranger", 3, 3)).id)
    row = _copy(tables, store, table, "Stranger")
    entry = init.roll(ST, table.id, [f"char:{row.id}"], rng=_Faces(1))
    assert [(ln.name, ln.group) for ln in entry.initiative] == [("Stranger", ENEMY)]


def test_a_tie_breaks_on_dexterity_plus_wits(init, tables, store, table, roster):
    # The d10s go in the order of the keys. Old Friend: rating 2 (Dex 1 + Wits 1).
    row = _npc(tables, store, table, "Old Friend", ALLY, dex=1, wits=1)
    ashes = _copy(tables, store, table, "Ashes")
    entry = init.roll(ST, table.id, [f"char:{row.id}", f"char:{ashes.id}"],
                      rng=_Faces(10, 5))
    # Old Friend 2 + 10 = 12; Ashes 7 + 5 = 12. Ashes has the higher Dex + Wits.
    assert [(ln.name, ln.total, ln.tied) for ln in entry.initiative] == [
        ("Ashes", 12, False), ("Old Friend", 12, False)]


def test_a_roster_entry_uses_its_printed_dexterity_and_wits_for_a_tie(
        init, tables, store, table, roster):
    _entry(roster, table, "Guard", ALLY, 7, attributes={"dexterity": 4, "wits": 3})
    _entry(roster, table, "Beast", ALLY, 7, attributes={"dexterity": 4})
    _entry(roster, table, "Scout", ALLY, 7, attributes={"dexterity": 5, "wits": 4})
    keys = [c.key for c in init.combatants(ST, table.id) if c.name in ("Ashes", "Scout")]
    entry = init.roll(ST, table.id, keys, rng=_Faces(5, 5))
    assert [(ln.name, ln.tied) for ln in entry.initiative] == [
        ("Scout", False), ("Ashes", False)]               # Dex + Wits 9 beats 7

    keys = [c.key for c in init.combatants(ST, table.id) if c.name in ("Ashes", "Guard")]
    entry = init.roll(ST, table.id, keys, rng=_Faces(5, 5))
    assert all(ln.tied for ln in entry.initiative)        # 7 = 7 on Dex + Wits too

    keys = [c.key for c in init.combatants(ST, table.id) if c.name in ("Beast", "Gearheart")]
    entry = init.roll(ST, table.id, keys, rng=_Faces(8, 5))   # Gearheart 4+8, Beast 7+5
    assert all(ln.tied for ln in entry.initiative)        # Beast has no Wits


def test_a_roster_entry_with_no_base_initiative_does_not_roll(init, table, roster):
    beast = _entry(roster, table, "Beast", ENEMY, None)
    with pytest.raises(TableLogError):
        init.roll(ST, table.id, [f"adv:{beast.id}"])


def test_no_tick_is_refused_and_posts_nothing(init, table, the_log):
    with pytest.raises(TableLogError):
        init.roll(ST, table.id, [])
    with pytest.raises(TableLogError):
        init.roll(ST, table.id, ["char:not-in-the-table", "adv:nothing"])
    assert the_log.entries(table.id) == []


def test_a_key_of_a_character_outside_the_table_does_not_roll(
        init, tables, store, table):
    """The browser names the keys. A copy of another table is not a combatant."""
    other = tables.create(ST, "Another")
    base = store.create(ALICE, _locked("Elsewhere"))
    tables.approve(ST, tables.request(ALICE, other.join_code, base.id).id)
    (row,) = tables.characters(other.id)
    ashes = _copy(tables, store, table, "Ashes")
    entry = init.roll(ST, table.id, [f"char:{row.id}", f"char:{ashes.id}"],
                      rng=_Faces(4, 4))
    assert [ln.name for ln in entry.initiative] == ["Ashes"]


def test_the_initiative_entry_reads_back_from_the_file(init, table, the_log):
    keys = [c.key for c in init.combatants(ST, table.id)]
    entry = init.roll(ST, table.id, keys, rng=_Faces(2, 2))
    assert TableLog(the_log.tables).entries(table.id)[-1] == entry


# --------------------------------------------------------------------------- #
# The Storyteller's adjustments (human, 2026-09-25)
#
# Charms that change initiative are not modelled (decision 0008). The Storyteller
# types a bonus for one roll in the dialog, and ticks "first" for a Charm that
# acts before everyone. Two or more "first" entries go in the normal order.
# --------------------------------------------------------------------------- #


def _keys(init, table, *names):
    by_name = {c.name: c.key for c in init.combatants(ST, table.id)}
    return [by_name[n] for n in names]


def test_a_bonus_is_added_to_the_total_and_kept_in_the_line(init, table):
    ashes, gear = _keys(init, table, "Ashes", "Gearheart")
    entry = init.roll(ST, table.id, [ashes, gear], bonus={gear: 5}, rng=_Faces(3, 3))
    assert [(ln.name, ln.rating, ln.bonus, ln.d10, ln.total)
            for ln in entry.initiative] == [("Gearheart", 4, 5, 3, 12),
                                            ("Ashes", 7, 0, 3, 10)]


def test_a_first_entry_goes_first_and_is_marked(init, table):
    ashes, gear = _keys(init, table, "Ashes", "Gearheart")
    entry = init.roll(ST, table.id, [ashes, gear], first={gear}, rng=_Faces(10, 1))
    assert [(ln.name, ln.first) for ln in entry.initiative] == [
        ("Gearheart", True), ("Ashes", False)]


def test_two_first_entries_go_in_the_normal_order(init, table, roster):
    _entry(roster, table, "Bandit", ENEMY, 6)
    ashes, gear, bandit = _keys(init, table, "Ashes", "Gearheart", "Bandit")
    entry = init.roll(ST, table.id, [ashes, gear, bandit], first={gear, bandit},
                      rng=_Faces(10, 1, 1))
    assert [ln.name for ln in entry.initiative] == ["Bandit", "Gearheart", "Ashes"]


def test_a_bonus_or_a_first_of_a_key_that_does_not_roll_does_nothing(init, table):
    ashes, gear = _keys(init, table, "Ashes", "Gearheart")
    entry = init.roll(ST, table.id, [ashes], bonus={gear: 9, "adv:nothing": 3},
                      first={gear, "adv:nothing"}, rng=_Faces(1))
    assert [(ln.name, ln.bonus, ln.first) for ln in entry.initiative] == [
        ("Ashes", 0, False)]


@pytest.mark.parametrize("bad", [100, -100, 1.5, "3", True])
def test_a_bonus_that_is_not_a_small_whole_number_is_refused(init, table, the_log, bad):
    (ashes,) = _keys(init, table, "Ashes")
    with pytest.raises(TableLogError):
        init.roll(ST, table.id, [ashes], bonus={ashes: bad})
    assert the_log.entries(table.id) == []


def test_a_bonus_and_a_first_read_back_from_the_file(init, table, the_log):
    ashes, gear = _keys(init, table, "Ashes", "Gearheart")
    entry = init.roll(ST, table.id, [ashes, gear], bonus={ashes: -2}, first={gear},
                      rng=_Faces(2, 2))
    assert TableLog(the_log.tables).entries(table.id)[-1] == entry
