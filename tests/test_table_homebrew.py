"""The homebrew of a campaign: the store half.

Step 7 of `docs/plans/p3-tables.md` section 14 (ruled 2026-09-23):

  * A campaign copy sees the book and the homebrew of the campaign. Not the library
    of its owner (Q1).
  * Each row enters the campaign through the Storyteller: the approval of a
    character adds the homebrew it carries; a member proposes a row of their
    library and the Storyteller approves it; the Storyteller writes a row.
  * The campaign wins an id clash.

⚠ The side door (found 2026-09-23): each save of a copy took its carried rows from
the library of the owner. Thus an edit at home changed the copy with no
Storyteller.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from exalted_builder import custom_content
from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character
from exalted_builder.server import db
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.table_homebrew import TableHomebrew, TableHomebrewError
from exalted_builder.server.tables import TableStore, TableStoreError

ST, ALICE, BOB, STRANGER = 1, 2, 3, 4


@pytest.fixture
def tables(tmp_path: Path) -> TableStore:
    path = tmp_path / "accounts" / "exalted.db"
    db.init_db(path)
    with db.connect(path) as connection:
        connection.executemany(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'x')",
            [(ST, "storyteller"), (ALICE, "alice"), (BOB, "bob"),
             (STRANGER, "stranger")])
    return TableStore(db_path=path, root=tmp_path / "sessions")


@pytest.fixture
def store(tables: TableStore) -> CharacterStore:
    return CharacterStore(db_path=tables.db_path, root=tables.root)


@pytest.fixture
def homebrew(tables: TableStore) -> TableHomebrew:
    return TableHomebrew(tables)


@pytest.fixture
def table(tables: TableStore):
    """A table that ALICE and BOB watch."""
    table = tables.create(ST, "The Scarlet Gambit")
    for user in (ALICE, BOB):
        tables.approve(ST, tables.request(user, table.join_code, None).id)
    return table


def _charm(cid: str, **over) -> dict:
    row = {"id": cid, "name": cid.replace("custom.", "").title(), "category": "melee",
           "type": "Supplemental", "min_ability": 1, "min_essence": 1}
    row.update(over)
    return row


def _author(folder: Path, *rows: dict) -> None:
    for row in rows:
        custom_content.save_charm(row, custom_dir=folder)


def _base(store: CharacterStore, user: int, *charm_ids: str) -> str:
    character = Character(id="x", name="Ashes", caste="dawn",
                          charms=list(charm_ids))
    lifecycle.lock_chargen(character)
    return store.create(user, character).id


def _campaign_names(tables: TableStore, table_id: str) -> dict[str, str]:
    folder = tables.homebrew_dir(table_id)
    return {r["id"]: r["name"] for r in custom_content.library_charms(folder)}


def _carried(store: CharacterStore, row) -> dict[str, str]:
    data = json.loads(store.path_for(row).read_text())
    return {r["id"]: r["name"]
            for r in data.get("custom_definitions", {}).get("charms", [])}


def _join(tables: TableStore, user: int, table, base_id: str):
    return tables.approve(ST, tables.bring(user, table.id, base_id).id)


# --------------------------------------------------------------------------- #
# 1. Approval adds the carried homebrew
# --------------------------------------------------------------------------- #


def test_approval_adds_the_carried_homebrew(tables, store, table) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.fang"))
    base = _base(store, ALICE, "custom.fang")

    _join(tables, ALICE, table, base)

    assert _campaign_names(tables, table.id) == {"custom.fang": "Fang"}


def test_a_request_adds_nothing_before_the_approval(tables, store, table) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.fang"))
    base = _base(store, ALICE, "custom.fang")

    request = tables.bring(ALICE, table.id, base)
    tables.reject(ST, request.id)

    assert _campaign_names(tables, table.id) == {}


def test_the_campaign_wins_a_clash(tables, store, table) -> None:
    _author(tables.homebrew_dir(table.id), _charm("custom.fang", name="Campaign Fang"))
    _author(store.custom_dir(ALICE), _charm("custom.fang", name="Alice Fang"))
    base = _base(store, ALICE, "custom.fang")

    copy = _join(tables, ALICE, table, base)

    assert _campaign_names(tables, table.id) == {"custom.fang": "Campaign Fang"}
    # The copy carries the version of the campaign, which is the one it uses.
    assert _carried(store, copy) == {"custom.fang": "Campaign Fang"}


def test_the_preview_names_what_the_approval_adds(tables, store, table) -> None:
    _author(tables.homebrew_dir(table.id), _charm("custom.same"),
            _charm("custom.clash", name="Campaign Clash"))
    _author(store.custom_dir(ALICE), _charm("custom.new"), _charm("custom.same"),
            _charm("custom.clash", name="Alice Clash"))
    base = _base(store, ALICE, "custom.new", "custom.same", "custom.clash")
    request = tables.bring(ALICE, table.id, base)

    preview = tables.homebrew_preview(ST, request.id)

    assert preview.adds == ["New"]
    assert preview.differs == ["Alice Clash"]


def test_only_the_storyteller_previews(tables, store, table) -> None:
    base = _base(store, ALICE)
    request = tables.bring(ALICE, table.id, base)

    with pytest.raises(TableStoreError):
        tables.homebrew_preview(ALICE, request.id)


# --------------------------------------------------------------------------- #
# 2. The side door: a copy takes its homebrew from the campaign
# --------------------------------------------------------------------------- #


def test_an_edit_at_home_does_not_reach_the_copy(tables, store, table) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.fang", name="Fang"))
    base = _base(store, ALICE, "custom.fang")
    copy = _join(tables, ALICE, table, base)

    _author(store.custom_dir(ALICE), _charm("custom.fang", name="Better Fang"))
    store.save(copy, store.load(copy))

    assert _carried(store, copy) == {"custom.fang": "Fang"}


def test_a_solo_character_takes_its_homebrew_from_the_library(store) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.fang", name="Fang"))
    base_id = _base(store, ALICE, "custom.fang")
    row = store.row(base_id)

    _author(store.custom_dir(ALICE), _charm("custom.fang", name="Better Fang"))
    store.save(row, store.load(row))

    assert _carried(store, row) == {"custom.fang": "Better Fang"}


def test_the_homebrew_folder_of_a_copy_is_the_campaign(tables, store, table) -> None:
    base = _base(store, ALICE)
    copy = _join(tables, ALICE, table, base)

    assert store.homebrew_dir(copy) == tables.homebrew_dir(table.id)
    assert store.homebrew_dir(store.row(base)) == store.custom_dir(ALICE)


# --------------------------------------------------------------------------- #
# 3. A copy that becomes solo keeps its homebrew
# --------------------------------------------------------------------------- #


def _campaign_charm_copy(tables, store, table, user=ALICE):
    _author(tables.homebrew_dir(table.id), _charm("custom.oath"))
    # A draft for the campaign buys a Charm of the campaign.
    base = _base(store, user, "custom.oath")
    return _join(tables, user, table, base)


def test_a_leaver_keeps_the_homebrew_of_the_copy(tables, store, table) -> None:
    copy = _campaign_charm_copy(tables, store, table)

    tables.leave(ALICE, table.id)

    mine = {r["id"] for r in custom_content.library_charms(store.custom_dir(ALICE))}
    assert "custom.oath" in mine
    assert _carried(store, store.row(copy.id)) == {"custom.oath": "Oath"}


def test_a_removed_member_keeps_the_homebrew(tables, store, table) -> None:
    _campaign_charm_copy(tables, store, table)

    tables.remove(ST, table.id, ALICE)

    mine = {r["id"] for r in custom_content.library_charms(store.custom_dir(ALICE))}
    assert "custom.oath" in mine


def test_a_deleted_campaign_leaves_its_homebrew_with_each_copy(tables, store,
                                                               table) -> None:
    _campaign_charm_copy(tables, store, table)

    tables.delete(ST, table.id)

    mine = {r["id"] for r in custom_content.library_charms(store.custom_dir(ALICE))}
    assert "custom.oath" in mine


def test_the_library_of_the_leaver_wins_a_clash(tables, store, table) -> None:
    copy = _campaign_charm_copy(tables, store, table)
    _author(store.custom_dir(ALICE), _charm("custom.oath", name="My Oath"))

    tables.leave(ALICE, table.id)

    names = {r["id"]: r["name"]
             for r in custom_content.library_charms(store.custom_dir(ALICE))}
    assert names["custom.oath"] == "My Oath"
    assert copy is not None


def test_a_member_with_no_copy_gets_nothing(tables, store, table) -> None:
    _author(tables.homebrew_dir(table.id), _charm("custom.oath"))

    tables.leave(BOB, table.id)

    assert custom_content.library_charms(store.custom_dir(BOB)) == []


# --------------------------------------------------------------------------- #
# 4. Proposals
# --------------------------------------------------------------------------- #


def test_a_member_proposes_a_row_of_their_library(homebrew, store, tables,
                                                  table) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.fang"))

    proposal = homebrew.propose(ALICE, table.id, "charms", "custom.fang")

    assert [p.id for p in homebrew.proposals(ST, table.id)] == [proposal.id]
    assert proposal.names == ["Fang"]
    # Nothing is in the campaign before the approval.
    assert _campaign_names(tables, table.id) == {}


def test_a_proposal_brings_its_homebrew_prerequisites(homebrew, store, tables,
                                                      table) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.root"),
            _charm("custom.leaf", prerequisites=[["custom.root"]]))

    proposal = homebrew.propose(ALICE, table.id, "charms", "custom.leaf")
    homebrew.approve(ST, table.id, proposal.id)

    assert set(_campaign_names(tables, table.id)) == {"custom.root", "custom.leaf"}


def test_approval_adds_the_row_and_ends_the_proposal(homebrew, store, tables,
                                                     table) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.fang"))
    proposal = homebrew.propose(ALICE, table.id, "charms", "custom.fang")

    homebrew.approve(ST, table.id, proposal.id)

    assert _campaign_names(tables, table.id) == {"custom.fang": "Fang"}
    assert homebrew.proposals(ST, table.id) == []


def test_rejection_adds_nothing(homebrew, store, tables, table) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.fang"))
    proposal = homebrew.propose(ALICE, table.id, "charms", "custom.fang")

    homebrew.reject(ST, table.id, proposal.id)

    assert _campaign_names(tables, table.id) == {}
    assert homebrew.proposals(ST, table.id) == []


def test_a_spell_can_be_proposed(homebrew, store, tables, table) -> None:
    # A spell needs a Charm that grants its circle, and the book has one.
    custom_content.save_spell({"id": "custom.ember", "name": "Ember",
                               "circle": "Terrestrial"}, custom_dir=store.custom_dir(ALICE))
    proposal = homebrew.propose(ALICE, table.id, "spells", "custom.ember")

    homebrew.approve(ST, table.id, proposal.id)

    rows = custom_content.library_spells(tables.homebrew_dir(table.id))
    assert [r["id"] for r in rows] == ["custom.ember"]


@pytest.mark.parametrize("user", [ALICE, BOB])
def test_only_the_storyteller_approves_or_rejects(homebrew, store, table, user) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.fang"))
    proposal = homebrew.propose(ALICE, table.id, "charms", "custom.fang")

    with pytest.raises(TableHomebrewError):
        homebrew.approve(user, table.id, proposal.id)
    with pytest.raises(TableHomebrewError):
        homebrew.reject(user, table.id, proposal.id)
    with pytest.raises(TableHomebrewError):
        homebrew.proposals(user, table.id)


def test_a_stranger_cannot_propose(homebrew, store, table) -> None:
    _author(store.custom_dir(STRANGER), _charm("custom.fang"))

    with pytest.raises(TableHomebrewError):
        homebrew.propose(STRANGER, table.id, "charms", "custom.fang")


def test_a_row_not_in_the_library_cannot_be_proposed(homebrew, store, table) -> None:
    _author(store.custom_dir(BOB), _charm("custom.fang"))

    with pytest.raises(TableHomebrewError):
        homebrew.propose(ALICE, table.id, "charms", "custom.fang")


def test_a_row_the_campaign_has_cannot_be_proposed(homebrew, store, tables,
                                                   table) -> None:
    _author(tables.homebrew_dir(table.id), _charm("custom.fang"))
    _author(store.custom_dir(ALICE), _charm("custom.fang", name="Alice Fang"))

    with pytest.raises(TableHomebrewError):
        homebrew.propose(ALICE, table.id, "charms", "custom.fang")


def test_a_second_proposal_of_the_same_row_is_refused(homebrew, store, table) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.fang"))
    homebrew.propose(ALICE, table.id, "charms", "custom.fang")

    with pytest.raises(TableHomebrewError):
        homebrew.propose(ALICE, table.id, "charms", "custom.fang")


def test_the_proposal_is_a_copy_of_the_row(homebrew, store, tables, table) -> None:
    """An edit to the library after the proposal does not change what the ST saw."""
    _author(store.custom_dir(ALICE), _charm("custom.fang", name="Fang"))
    proposal = homebrew.propose(ALICE, table.id, "charms", "custom.fang")
    _author(store.custom_dir(ALICE), _charm("custom.fang", name="Better Fang"))

    homebrew.approve(ST, table.id, proposal.id)

    assert _campaign_names(tables, table.id) == {"custom.fang": "Fang"}


def test_a_member_withdraws_their_own_proposal(homebrew, store, table) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.fang"))
    proposal = homebrew.propose(ALICE, table.id, "charms", "custom.fang")

    assert homebrew.withdraw(BOB, table.id, proposal.id) is False
    assert homebrew.withdraw(ALICE, table.id, proposal.id) is True
    assert homebrew.proposals(ST, table.id) == []


def test_a_member_sees_their_own_proposals(homebrew, store, table) -> None:
    _author(store.custom_dir(ALICE), _charm("custom.fang"))
    _author(store.custom_dir(BOB), _charm("custom.claw"))
    homebrew.propose(ALICE, table.id, "charms", "custom.fang")
    homebrew.propose(BOB, table.id, "charms", "custom.claw")

    assert [p.names for p in homebrew.proposals_by(ALICE, table.id)] == [["Fang"]]


def test_the_storytellers_proposal_is_approved_at_once(homebrew, store, tables,
                                                       table) -> None:
    _author(store.custom_dir(ST), _charm("custom.fang"))

    proposal = homebrew.propose(ST, table.id, "charms", "custom.fang")

    assert proposal.approved is True
    assert _campaign_names(tables, table.id) == {"custom.fang": "Fang"}
    assert homebrew.proposals(ST, table.id) == []


def test_an_approval_after_a_clash_keeps_the_campaign_row(homebrew, store, tables,
                                                          table) -> None:
    """The ST authored the same id after the proposal: the campaign wins."""
    _author(store.custom_dir(ALICE), _charm("custom.fang", name="Alice Fang"))
    proposal = homebrew.propose(ALICE, table.id, "charms", "custom.fang")
    _author(tables.homebrew_dir(table.id), _charm("custom.fang", name="ST Fang"))

    homebrew.approve(ST, table.id, proposal.id)

    assert _campaign_names(tables, table.id) == {"custom.fang": "ST Fang"}
