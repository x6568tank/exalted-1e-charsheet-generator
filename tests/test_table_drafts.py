"""Adding a character from inside a campaign: `TableStore.bring` and the campaign
drafts.

Step 6b of `docs/plans/p3-tables.md` section 14 (ruled 2026-09-22):

  1. A member brings one of their locked bases: the join request, from the
     membership instead of the code.
  2. A member creates a character for the campaign: an ordinary draft, tagged for
     the table and built under its house rules. Finish & Lock sends the request.

⚠ The tag is a row in the database, not a field of the character: the page
cannot edit it (the house bug, type 3).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character, HouseRules
from exalted_builder.server import db
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.session import SessionRegistry
from exalted_builder.server.table_log import TableLog
from exalted_builder.server.table_st import TableStoryteller
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


def _locked(name: str) -> Character:
    character = Character(id="x", name=name, caste="dawn")
    lifecycle.lock_chargen(character)
    return character


@pytest.fixture
def table(tables: TableStore):
    """A table that ALICE watches."""
    table = tables.create(ST, "The Scarlet Gambit")
    tables.approve(ST, tables.request(ALICE, table.join_code, None).id)
    return table


# --------------------------------------------------------------------------- #
# 1. Bring a base
# --------------------------------------------------------------------------- #


def test_a_member_brings_a_base(tables, store, table) -> None:
    base = store.create(ALICE, _locked("Ashes"))

    request = tables.bring(ALICE, table.id, base.id)

    assert (request.table_id, request.user_id, request.base_id) == (
        table.id, ALICE, base.id)
    assert [r.id for r in tables.pending(ST, table.id)] == [request.id]


def test_the_storyteller_brings_a_base(tables, store, table) -> None:
    """Q4: the Storyteller may play a character in their own campaign."""
    base = store.create(ST, _locked("Gamemaster's Own"))
    assert tables.bring(ST, table.id, base.id).base_id == base.id


def test_a_stranger_cannot_bring_a_base(tables, store, table) -> None:
    base = store.create(STRANGER, _locked("Gatecrasher"))
    with pytest.raises(TableStoreError):
        tables.bring(STRANGER, table.id, base.id)
    assert tables.pending(ST, table.id) == []


@pytest.mark.parametrize("case", ["other account", "draft", "copy", "none"])
def test_bring_refuses_what_the_code_path_refuses(tables, store, table, case) -> None:
    if case == "other account":
        base_id = store.create(BOB, _locked("Not Hers")).id
    elif case == "draft":
        base_id = store.create(ALICE, Character(id="x", name="Unfinished")).id
    elif case == "copy":
        base_id = store.make_copy(ALICE, store.create(ALICE, _locked("B")).id).id
    else:
        base_id = None
    with pytest.raises(TableStoreError):
        tables.bring(ALICE, table.id, base_id)
    assert tables.pending(ST, table.id) == []


def test_bring_refuses_a_duplicate(tables, store, table) -> None:
    base = store.create(ALICE, _locked("Ashes"))
    tables.bring(ALICE, table.id, base.id)
    with pytest.raises(TableStoreError):
        tables.bring(ALICE, table.id, base.id)


def test_bring_is_not_throttled(tables, store, table) -> None:
    """The throttle protects the code. A member does not guess a code."""
    for n in range(12):
        tables.bring(ALICE, table.id, store.create(ALICE, _locked(f"C{n}")).id)
    assert len(tables.pending(ST, table.id)) == 12


# --------------------------------------------------------------------------- #
# 2. A draft for the campaign
# --------------------------------------------------------------------------- #


def test_a_member_starts_a_draft_under_the_table_rules(tables, store, table) -> None:
    tables.write_house_rules(table.id, HouseRules(magic_for_everyone=True))

    row = tables.start_draft(ALICE, table.id)

    assert row.owner_id == ALICE
    assert not row.is_copy and row.table_id is None
    character = store.load(row)
    assert not character.chargen_locked
    assert character.house_rules.magic_for_everyone is True
    assert tables.draft_table(row.id) == table.id
    assert [r.id for r in tables.drafts(table.id)] == [row.id]


def test_a_stranger_cannot_start_a_draft(tables, store, table) -> None:
    with pytest.raises(TableStoreError):
        tables.start_draft(STRANGER, table.id)
    assert store.list_for(STRANGER) == []


def test_an_ordinary_draft_is_not_tagged(tables, store, table) -> None:
    row = store.create(ALICE, Character(id="x"))
    assert tables.draft_table(row.id) is None


def test_a_locked_draft_is_sent_to_the_storyteller(tables, store, table) -> None:
    row = tables.start_draft(ALICE, table.id)
    character = store.load(row)
    lifecycle.lock_chargen(character)
    store.save(row, character)

    request = tables.send_draft(ALICE, row.id)

    assert (request.table_id, request.base_id) == (table.id, row.id)
    assert tables.draft_table(row.id) is None, "The tag stayed after the request."
    copy = tables.approve(ST, request.id)
    assert copy.table_id == table.id and copy.base_id == row.id


def test_an_unlocked_draft_is_not_sent(tables, store, table) -> None:
    row = tables.start_draft(ALICE, table.id)
    with pytest.raises(TableStoreError):
        tables.send_draft(ALICE, row.id)
    assert tables.draft_table(row.id) == table.id
    assert tables.pending(ST, table.id) == []


def test_send_draft_of_an_untagged_character_does_nothing(tables, store, table) -> None:
    row = store.create(ALICE, _locked("Solo"))
    assert tables.send_draft(ALICE, row.id) is None
    assert tables.pending(ST, table.id) == []


def test_send_draft_refuses_another_account(tables, store, table) -> None:
    row = tables.start_draft(ALICE, table.id)
    character = store.load(row)
    lifecycle.lock_chargen(character)
    store.save(row, character)
    assert tables.send_draft(BOB, row.id) is None
    assert tables.pending(ST, table.id) == []


def test_a_draft_of_a_member_who_left_is_not_sent(tables, store, table) -> None:
    row = tables.start_draft(ALICE, table.id)
    tables.leave(ALICE, table.id)

    assert tables.draft_table(row.id) is None
    assert store.load(row) is not None, "Leaving deleted the draft."


def test_a_deleted_campaign_untags_its_drafts(tables, store, table) -> None:
    row = tables.start_draft(ALICE, table.id)
    tables.delete(ST, table.id)
    assert tables.draft_table(row.id) is None
    assert store.row(row.id) is not None


def test_a_deleted_draft_takes_its_tag(tables, store, table) -> None:
    row = tables.start_draft(ALICE, table.id)
    store.delete(ALICE, row.id)
    assert tables.drafts(table.id) == []


# --------------------------------------------------------------------------- #
# The Storyteller and the drafts: the switches and the permissions reach them
# --------------------------------------------------------------------------- #


@pytest.fixture
def st(tables, store) -> TableStoryteller:
    sessions = SessionRegistry(factory=lambda key: {"char": store.load(store.row(key))})
    return TableStoryteller(tables, store, sessions, TableLog(tables))


def test_a_table_switch_reaches_a_draft(st, tables, store, table) -> None:
    row = tables.start_draft(ALICE, table.id)
    st.set_table_rule(ST, table.id, "restrict_chargen_ritual_level", True)
    assert store.load(row).house_rules.restrict_chargen_ritual_level is True


def test_the_storyteller_grants_a_draft_a_permission(st, tables, store, table) -> None:
    """Q2 at creation: a permission such as foreign Charms matters BEFORE the lock,
    thus the Storyteller must reach a draft."""
    row = tables.start_draft(ALICE, table.id)
    st.set_character_rule(ST, table.id, row.id, "st_foreign_charms", True)
    assert store.load(row).house_rules.st_foreign_charms is True


def test_the_player_cannot_grant_their_draft_a_permission(st, tables, store, table) -> None:
    row = tables.start_draft(ALICE, table.id)
    with pytest.raises(TableStoreError):
        st.set_character_rule(ALICE, table.id, row.id, "st_foreign_charms", True)


def test_grant_and_unlock_refuse_a_draft(st, tables, store, table) -> None:
    """⚠ A draft takes no XP: a base never does (section 9.2)."""
    row = tables.start_draft(ALICE, table.id)
    with pytest.raises(TableStoreError):
        st.grant_xp(ST, table.id, 5, "", [row.id])
    with pytest.raises(TableStoreError):
        st.unlock(ST, table.id, row.id)
    assert store.load(row).xp_earned == 0


# --------------------------------------------------------------------------- #
# The Storyteller's own character is approved at once (human, 2026-09-22)
# --------------------------------------------------------------------------- #


def test_the_storytellers_own_base_is_approved_at_once(tables, store, table) -> None:
    base = store.create(ST, _locked("Gamemaster's Own"))

    request = tables.bring(ST, table.id, base.id)

    assert request.approved
    assert tables.pending(ST, table.id) == []
    (copy,) = tables.characters(table.id)
    assert (copy.owner_id, copy.base_id) == (ST, base.id)


def test_the_storytellers_own_draft_is_approved_at_the_lock(tables, store, table) -> None:
    row = tables.start_draft(ST, table.id)
    character = store.load(row)
    lifecycle.lock_chargen(character)
    store.save(row, character)

    assert tables.send_draft(ST, row.id).approved
    assert tables.pending(ST, table.id) == []
    assert [c.base_id for c in tables.characters(table.id)] == [row.id]


def test_the_storyteller_joining_by_code_is_approved_at_once(tables, store, table) -> None:
    base = store.create(ST, _locked("By Code"))
    assert tables.request(ST, table.join_code, base.id).approved
    assert tables.pending(ST, table.id) == []


def test_a_players_request_still_waits(tables, store, table) -> None:
    """The negative control: only the Storyteller's own request skips the wait."""
    base = store.create(ALICE, _locked("Ashes"))
    request = tables.bring(ALICE, table.id, base.id)
    assert not request.approved
    assert [r.id for r in tables.pending(ST, table.id)] == [request.id]
    assert tables.characters(table.id) == []
