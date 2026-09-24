"""Which RuleSet each character of the hosted server sees: `server/rulesets.py`.

Step 7 of `docs/plans/p3-tables.md` section 14 (ruled 2026-09-23):

  * A solo character: the book and the library of its owner.
  * A campaign copy: the book and the homebrew of the campaign. NOT the library of
    its owner (Q1, 2026-09-12).
  * A draft for a campaign: the book, the homebrew of the campaign, then the library
    of its owner.

⚠ A reload of one layer must keep the others. See tests/test_custom_layers.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from exalted_builder import custom_content, rules_db
from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character
from exalted_builder.server import db
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.rulesets import Rulesets
from exalted_builder.server.tables import TableStore

ST, ALICE = 1, 2


@pytest.fixture(scope="module")
def book():
    return rules_db.load_ruleset("exalted_builder/data")


@pytest.fixture
def tables(tmp_path: Path) -> TableStore:
    path = tmp_path / "exalted.db"
    db.init_db(path)
    with db.connect(path) as connection:
        connection.executemany(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'x')",
            [(ST, "storyteller"), (ALICE, "alice")])
    return TableStore(db_path=path, root=tmp_path / "sessions")


@pytest.fixture
def store(tables) -> CharacterStore:
    return CharacterStore(db_path=tables.db_path, root=tables.root)


@pytest.fixture
def rulesets(book, store, tables) -> Rulesets:
    return Rulesets(book, store, tables)


@pytest.fixture
def table(tables):
    table = tables.create(ST, "The Scarlet Gambit")
    tables.approve(ST, tables.request(ALICE, table.join_code, None).id)
    return table


def _charm(cid: str) -> dict:
    return {"id": cid, "name": cid.replace("custom.", "").title(), "category": "melee",
            "type": "Supplemental", "min_ability": 1, "min_essence": 1}


def _author(folder: Path, cid: str) -> None:
    custom_content.save_charm(_charm(cid), custom_dir=folder)


def _copy(tables, store, table):
    character = Character(id="x", name="Ashes", caste="dawn")
    lifecycle.lock_chargen(character)
    base = store.create(ALICE, character)
    return tables.approve(ST, tables.bring(ALICE, table.id, base.id).id)


def test_a_solo_character_sees_its_owners_library(rulesets, store, tables,
                                                  table) -> None:
    _author(store.custom_dir(ALICE), "custom.mine")
    _author(tables.homebrew_dir(table.id), "custom.campaign")
    row = store.create(ALICE, Character(id="x", name="Solo"))

    charms = rulesets.for_row(row).charms

    assert "custom.mine" in charms
    assert "custom.campaign" not in charms


def test_a_campaign_copy_sees_the_campaign_not_the_library(rulesets, store, tables,
                                                           table) -> None:
    """Q1: no."""
    _author(store.custom_dir(ALICE), "custom.mine")
    _author(tables.homebrew_dir(table.id), "custom.campaign")
    copy = _copy(tables, store, table)

    charms = rulesets.for_row(copy).charms

    assert "custom.campaign" in charms
    assert "custom.mine" not in charms


def test_a_draft_for_a_campaign_sees_both(rulesets, store, tables, table) -> None:
    _author(store.custom_dir(ALICE), "custom.mine")
    _author(tables.homebrew_dir(table.id), "custom.campaign")
    draft = tables.start_draft(ALICE, table.id)

    charms = rulesets.for_row(draft).charms

    assert {"custom.mine", "custom.campaign"} <= set(charms)


def test_the_campaign_wins_a_clash_on_a_draft(rulesets, store, tables, table) -> None:
    """Ruled 2026-09-23: the campaign's version wins an id clash."""
    custom_content.save_charm(_charm("custom.oath") | {"name": "Campaign Oath"},
                              custom_dir=tables.homebrew_dir(table.id))
    custom_content.save_charm(_charm("custom.oath") | {"name": "My Oath"},
                              custom_dir=store.custom_dir(ALICE))
    draft = tables.start_draft(ALICE, table.id)

    assert rulesets.for_row(draft).charms["custom.oath"].name == "Campaign Oath"


def test_a_reload_of_the_campaign_reaches_its_copies_and_drafts(
        rulesets, store, tables, table) -> None:
    copy = _copy(tables, store, table)
    draft = tables.start_draft(ALICE, table.id)
    copy_rules, draft_rules = rulesets.for_row(copy), rulesets.for_row(draft)
    solo_rules = rulesets.for_account(ALICE)

    _author(tables.homebrew_dir(table.id), "custom.new")
    rulesets.reload_table(table.id)

    assert "custom.new" in copy_rules.charms
    assert "custom.new" in draft_rules.charms
    assert "custom.new" not in solo_rules.charms


def test_a_reload_of_the_library_reaches_drafts_not_copies(rulesets, store, tables,
                                                           table) -> None:
    copy = _copy(tables, store, table)
    draft = tables.start_draft(ALICE, table.id)
    copy_rules, draft_rules = rulesets.for_row(copy), rulesets.for_row(draft)
    _author(tables.homebrew_dir(table.id), "custom.campaign")
    rulesets.reload_table(table.id)

    _author(store.custom_dir(ALICE), "custom.mine")
    rulesets.reload_account(ALICE)

    assert "custom.mine" in rulesets.for_account(ALICE).charms
    # ⚠ The draft keeps the campaign layer after a reload of the library.
    assert {"custom.mine", "custom.campaign"} <= set(draft_rules.charms)
    assert "custom.mine" not in copy_rules.charms


def test_each_rule_set_is_kept(rulesets, store, tables, table) -> None:
    """The pages hold the object, and a reload changes it in place."""
    copy = _copy(tables, store, table)

    assert rulesets.for_row(copy) is rulesets.for_table(table.id)
    assert rulesets.for_table(table.id) is not rulesets.for_account(ALICE)


def test_the_book_does_not_change(rulesets, book, tables, table) -> None:
    _author(tables.homebrew_dir(table.id), "custom.campaign")

    rulesets.for_table(table.id)

    assert "custom.campaign" not in book.charms


# --------------------------------------------------------------------------- #
# The store tells the kept RuleSets of each write. ⚠ The approval of a request of
# the Storyteller runs inside the store, thus a reload in a page handler misses it.
# --------------------------------------------------------------------------- #


def test_an_approval_reaches_the_kept_rule_set(rulesets, store, tables, table) -> None:
    kept = rulesets.for_table(table.id)
    custom_content.save_charm(_charm("custom.fang"), custom_dir=store.custom_dir(ALICE))
    character = Character(id="x", name="Ashes", caste="dawn", charms=["custom.fang"])
    lifecycle.lock_chargen(character)
    base = store.create(ALICE, character)

    tables.approve(ST, tables.bring(ALICE, table.id, base.id).id)

    assert "custom.fang" in kept.charms


def test_the_storytellers_own_request_reaches_the_kept_rule_set(rulesets, store,
                                                                tables, table) -> None:
    kept = rulesets.for_table(table.id)
    custom_content.save_charm(_charm("custom.fang"), custom_dir=store.custom_dir(ST))
    character = Character(id="x", name="Villain", caste="dawn", charms=["custom.fang"])
    lifecycle.lock_chargen(character)
    base = store.create(ST, character)

    assert tables.bring(ST, table.id, base.id).approved

    assert "custom.fang" in kept.charms


def test_a_proposal_reaches_the_kept_rule_set(rulesets, store, tables, table) -> None:
    from exalted_builder.server.table_homebrew import TableHomebrew

    kept = rulesets.for_table(table.id)
    custom_content.save_charm(_charm("custom.fang"), custom_dir=store.custom_dir(ALICE))
    homebrew = TableHomebrew(tables)

    homebrew.approve(ST, table.id,
                     homebrew.propose(ALICE, table.id, "charms", "custom.fang").id)

    assert "custom.fang" in kept.charms


def test_a_leaver_sees_the_campaign_homebrew_in_their_library(rulesets, store, tables,
                                                              table) -> None:
    kept = rulesets.for_account(ALICE)
    _author(tables.homebrew_dir(table.id), "custom.oath")
    character = Character(id="x", name="Ashes", caste="dawn", charms=["custom.oath"])
    lifecycle.lock_chargen(character)
    base = store.create(ALICE, character)
    tables.approve(ST, tables.bring(ALICE, table.id, base.id).id)

    tables.leave(ALICE, table.id)

    assert "custom.oath" in kept.charms
