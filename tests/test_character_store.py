"""The characters of the hosted server: `server/characters.py`.

Section 5 piece 4 of `docs/plans/hosting-state-model.md`, and the layout of
`docs/plans/vtt.md` sections 9.2, 9.3 and 9.3a. The human's rulings:

  * a character is a FILE in the account folder, named by its id, plus a DB row;
  * an account has several characters: drafts, bases, and campaign copies;
  * a copy is made from a LOCKED base, and it records the base;
  * a delete leaves the copies of a base, which then show that the base is gone.

⚠ Each case uses `store.custom_dir`, never the default library. The hosted server
refuses the default (`custom_content.require_explicit_dir`), and one case runs
with that switch on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from exalted_builder import custom_content, persistence
from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character
from exalted_builder.server import db
from exalted_builder.server.characters import CharacterStore, CharacterStoreError


@pytest.fixture
def store(tmp_path: Path) -> CharacterStore:
    """A store with two accounts, ids 1 and 2. No bcrypt: the rows go in by SQL."""
    database = tmp_path / "accounts" / "exalted.db"
    db.init_db(database)
    with db.connect(database) as connection:
        connection.executemany(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'x')",
            [(1, "alpha"), (2, "beta")])
    return CharacterStore(db_path=database, root=tmp_path / "sessions")


def _locked(name: str = "Base") -> Character:
    character = Character(id="char.aaaaaaaaaaaa", name=name, caste="dawn")
    lifecycle.lock_chargen(character)
    return character


# --------------------------------------------------------------------------- #
# Create, read, list
# --------------------------------------------------------------------------- #


def test_a_new_character_is_a_file_in_the_account_folder(store: CharacterStore) -> None:
    row = store.create(1, Character(id="char.aaaaaaaaaaaa", name="Harmonious Jade"))

    path = store.path_for(row)
    assert path == store.account_dir(1) / "characters" / f"{row.id}.character.json"
    assert persistence.load_character(path, absorb_custom=False).name == "Harmonious Jade"
    assert (row.owner_id, row.is_copy, row.base_id, row.table_id) == (1, False, None, None)


def test_create_gives_a_new_id_each_time(store: CharacterStore) -> None:
    """An upload keeps the id of its file. Two accounts that upload one file must
    not collide, and one account that uploads it twice gets two characters."""
    character = Character(id="char.aaaaaaaaaaaa", name="Twice")

    first, second = store.create(1, character), store.create(1, character)

    assert len({first.id, second.id, character.id}) == 3
    assert store.load(first).id == first.id


def test_the_file_name_is_the_id_not_the_name(store: CharacterStore) -> None:
    """A rename must not move the file. The DB row points at the id."""
    row = store.create(1, Character(id="char.aaaaaaaaaaaa", name="Before"))

    assert "Before" not in store.path_for(row).name


def test_an_account_lists_its_own_characters_only(store: CharacterStore) -> None:
    mine = [store.create(1, Character(id="x", name=n)).id for n in ("One", "Two")]
    store.create(2, Character(id="x", name="Theirs"))

    assert [row.id for row in store.list_for(1)] == mine


# --------------------------------------------------------------------------- #
# Ownership — the authorisation check is the store's, not the page's
# --------------------------------------------------------------------------- #


def test_another_accounts_character_is_not_owned(store: CharacterStore) -> None:
    theirs = store.create(2, Character(id="x", name="Theirs"))

    assert store.owned(1, theirs.id) is None
    assert store.owned(2, theirs.id) == theirs


@pytest.mark.parametrize("hostile", [
    "../user-2/characters/char.aaaaaaaaaaaa", "char.AAAAAAAAAAAA", "char.aaa",
    "", "/etc/passwd", "char.aaaaaaaaaaaa/../x"])
def test_a_malformed_id_is_refused(store: CharacterStore, hostile: str) -> None:
    """A URL gives the id. It is checked before the DB and before a path."""
    assert store.owned(1, hostile) is None
    assert store.row(hostile) is None


def test_a_malformed_id_never_reaches_the_database(tmp_path: Path) -> None:
    """The case above passes by the DB alone: no row has a hostile id. This one
    shows the shape check runs first. The database path cannot be opened, thus a
    lookup raises."""
    closed = CharacterStore(db_path=tmp_path / "no-such-folder" / "x.db", root=tmp_path)

    assert closed.row("../user-2/characters/x") is None
    with pytest.raises(Exception):
        closed.row("char.aaaaaaaaaaaa")


# --------------------------------------------------------------------------- #
# The base and the campaign copy (section 9.2)
# --------------------------------------------------------------------------- #


def test_a_copy_of_a_locked_base_records_the_base(store: CharacterStore) -> None:
    base = store.create(1, _locked())

    copy = store.make_copy(1, base.id)

    assert (copy.is_copy, copy.base_id, copy.owner_id) == (True, base.id, 1)
    assert copy.id != base.id
    copied = store.load(copy)
    assert copied.id == copy.id and copied.name == "Base"
    assert copied.chargen_snapshot is not None


def test_a_copy_moves_on_its_own(store: CharacterStore) -> None:
    """Nothing is shared after the copy (section 9.2)."""
    base = store.create(1, _locked())
    copy = store.make_copy(1, base.id)

    copied = store.load(copy)
    copied.name = "Changed"
    store.save(copy, copied)

    assert store.load(base).name == "Base"


def test_an_unlocked_character_cannot_be_copied(store: CharacterStore) -> None:
    """A base is a LOCKED character with an empty log (section 9.2)."""
    draft = store.create(1, Character(id="x", name="Draft"))

    with pytest.raises(CharacterStoreError):
        store.make_copy(1, draft.id)


def test_a_copy_cannot_be_the_base_of_a_copy(store: CharacterStore) -> None:
    """XP belongs to a copy. A copy of a copy would carry that XP as its start."""
    copy = store.make_copy(1, store.create(1, _locked()).id)

    with pytest.raises(CharacterStoreError):
        store.make_copy(1, copy.id)


def test_another_accounts_base_cannot_be_copied(store: CharacterStore) -> None:
    theirs = store.create(2, _locked())

    with pytest.raises(CharacterStoreError):
        store.make_copy(1, theirs.id)


# --------------------------------------------------------------------------- #
# Delete (ruled 2026-09-12: with a confirm, and the copies survive)
# --------------------------------------------------------------------------- #


def test_delete_removes_the_row_and_the_file(store: CharacterStore) -> None:
    row = store.create(1, Character(id="x", name="Gone"))
    path = store.path_for(row)

    assert store.delete(1, row.id) is True

    assert store.owned(1, row.id) is None
    assert not path.exists()


def test_a_copy_survives_the_delete_of_its_base(store: CharacterStore) -> None:
    base = store.create(1, _locked())
    copy = store.make_copy(1, base.id)

    store.delete(1, base.id)

    survivor = store.owned(1, copy.id)
    assert survivor is not None and survivor.is_copy and survivor.base_id is None
    assert store.load(survivor).name == "Base"


def test_another_accounts_character_cannot_be_deleted(store: CharacterStore) -> None:
    theirs = store.create(2, Character(id="x", name="Theirs"))

    assert store.delete(1, theirs.id) is False
    assert store.path_for(theirs).exists()


# --------------------------------------------------------------------------- #
# The homebrew of the account
# --------------------------------------------------------------------------- #


def test_the_library_of_an_account_is_in_its_folder(store: CharacterStore) -> None:
    assert store.custom_dir(1) == store.account_dir(1) / "custom"
    assert store.account_dir(1) != store.account_dir(2)


def test_a_save_carries_the_homebrew_of_the_account(store: CharacterStore) -> None:
    """With the hosted switch on, as on the server. A store call that used the
    default library raises here."""
    custom_content.save_charm(
        {"id": "custom.house-strike", "name": "House Strike", "category": "melee",
         "type": "Supplemental"}, custom_dir=store.custom_dir(1))
    character = Character(id="x", name="Brewer")
    character.charms.append("custom.house-strike")

    custom_content.require_explicit_dir(True)
    try:
        row = store.create(1, character)
        base = store.create(1, _locked())
        store.make_copy(1, base.id)
    finally:
        custom_content.require_explicit_dir(False)

    carried = store.load(row).custom_definitions
    assert [r["id"] for r in carried["charms"]] == ["custom.house-strike"]
