"""The campaigns of the hosted server: `server/tables.py`.

Step 1 of the build order in `docs/plans/p3-tables.md`: the store, the schema, the
join codes and the throttle on the join form. No UI. The rulings are `vtt.md`
section 9.10:

  * a join is a code plus the approval of the Storyteller;
  * a copy of the base is made at approval, in the table;
  * a leaver keeps the copy as a solo copy, and so does each member at a delete;
  * a code has six characters and no expiry; the Storyteller can replace it;
  * the table has a folder of its own;
  * a member can watch (no base), and can bring several characters.

⚠ `access` is the authorisation check. Each Storyteller operation checks it in the
store, thus a page that forgets to hide a button cannot open the operation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character
from exalted_builder.server import db, tables
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.tables import TableStore, TableStoreError

ST, PLAYER, OTHER = 1, 2, 3


@pytest.fixture
def database(tmp_path: Path) -> Path:
    """A database with three accounts. No bcrypt: the rows go in by SQL."""
    path = tmp_path / "accounts" / "exalted.db"
    db.init_db(path)
    with db.connect(path) as connection:
        connection.executemany(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'x')",
            [(ST, "storyteller"), (PLAYER, "player"), (OTHER, "other")])
    return path


@pytest.fixture
def store(database: Path, tmp_path: Path) -> TableStore:
    return TableStore(db_path=database, root=tmp_path / "sessions")


@pytest.fixture
def characters(store: TableStore) -> CharacterStore:
    return CharacterStore(db_path=store.db_path, root=store.root)


def _base(characters: CharacterStore, owner: int, name: str = "Base"):
    character = Character(id="x", name=name, caste="dawn")
    lifecycle.lock_chargen(character)
    return characters.create(owner, character)


def _member(store: TableStore, table, user: int, base_id: str | None = None):
    """Make `user` a member of `table` by the request and the approval. The
    Storyteller's own request is approved at once."""
    request = store.request(user, table.join_code, base_id)
    if request.approved:
        return next(row for row in store.characters(table.id) if row.base_id == base_id)
    return store.approve(ST, request.id)


# --------------------------------------------------------------------------- #
# Create, and the join code (section 2.3)
# --------------------------------------------------------------------------- #


def test_create_makes_the_row_the_folder_and_the_code(store: TableStore) -> None:
    table = store.create(ST, "  The Scarlet Gambit  ")

    assert tables.TABLE_ID.fullmatch(table.id)
    assert (table.name, table.storyteller_id) == ("The Scarlet Gambit", ST)
    assert store.table_dir(table.id).is_dir()
    assert store.table(table.id) == table


def test_the_table_folder_is_a_first_folder_below_the_root(store: TableStore) -> None:
    """The quota counts the first folder below the root. Thus a table has its own
    limit, separate from each account (section 2.2)."""
    table = store.create(ST, "Quota")

    folder = store.table_dir(table.id)
    assert folder.parent == store.root
    assert folder.name != CharacterStore(store.db_path, store.root).account_dir(ST).name


def test_a_campaign_needs_a_name(store: TableStore) -> None:
    with pytest.raises(TableStoreError):
        store.create(ST, "   ")


def test_a_join_code_has_six_characters_with_no_look_alikes() -> None:
    codes = {tables.new_join_code() for _ in range(200)}

    assert all(len(code) == 6 for code in codes)
    assert not set("".join(codes)) & set("0O1IL")
    assert set("".join(codes)) <= set(tables.CODE_ALPHABET)
    assert len(codes) > 190


def test_a_code_clash_draws_again(store: TableStore, monkeypatch) -> None:
    first = store.create(ST, "First")
    drawn = iter([first.join_code, "ABCDEF"])
    monkeypatch.setattr(tables, "new_join_code", lambda: next(drawn))

    second = store.create(ST, "Second")

    assert second.join_code == "ABCDEF"


def test_a_code_is_found_in_any_case_and_with_spaces(store: TableStore) -> None:
    table = store.create(ST, "Case")

    request = store.request(PLAYER, f"  {table.join_code.lower()} ", None)

    assert request.table_id == table.id


def test_a_new_code_replaces_the_old(store: TableStore) -> None:
    table = store.create(ST, "Leaked")
    old = table.join_code

    new = store.new_code(ST, table.id)

    assert new != old and store.table(table.id).join_code == new
    with pytest.raises(TableStoreError):
        store.request(PLAYER, old, None)
    assert store.request(PLAYER, new, None).table_id == table.id


def test_only_the_storyteller_makes_a_new_code(store: TableStore) -> None:
    table = store.create(ST, "Mine")
    _member(store, table, PLAYER)

    with pytest.raises(TableStoreError):
        store.new_code(PLAYER, table.id)
    assert store.table(table.id).join_code == table.join_code


# --------------------------------------------------------------------------- #
# Access — the authorisation check
# --------------------------------------------------------------------------- #


def test_access_names_the_role(store: TableStore) -> None:
    table = store.create(ST, "Roles")
    _member(store, table, PLAYER)

    assert store.access(ST, table.id) == "storyteller"
    assert store.access(PLAYER, table.id) == "member"
    assert store.access(OTHER, table.id) is None


def test_a_pending_request_gives_no_access(store: TableStore) -> None:
    """A leaked code yields a request, not access (section 2.3)."""
    table = store.create(ST, "Pending")
    store.request(OTHER, table.join_code, None)

    assert store.access(OTHER, table.id) is None


@pytest.mark.parametrize("hostile", [
    "../user-2", "table.AAAAAAAAAAAA", "table.aaa", "", "/etc", "char.aaaaaaaaaaaa"])
def test_a_malformed_table_id_is_refused(store: TableStore, hostile: str) -> None:
    assert store.access(ST, hostile) is None
    assert store.table(hostile) is None


def test_a_malformed_table_id_never_reaches_the_database(tmp_path: Path) -> None:
    """The case above passes by the DB alone. This one shows that the shape check
    runs first: the database cannot be opened, thus a lookup raises."""
    closed = TableStore(db_path=tmp_path / "no-such-folder" / "x.db", root=tmp_path)

    assert closed.access(ST, "../user-2") is None
    with pytest.raises(Exception):
        closed.access(ST, "table.aaaaaaaaaaaa")


def test_for_user_lists_the_tables_run_and_joined(store: TableStore) -> None:
    run = store.create(ST, "Run")
    joined = store.create(OTHER, "Joined")
    store.create(OTHER, "Not mine")
    _member_of(store, joined, PLAYER, storyteller=OTHER)
    _member_of(store, run, PLAYER, storyteller=ST)

    assert [t.id for t in store.for_user(ST)] == [run.id]
    assert [t.id for t in store.for_user(PLAYER)] == [run.id, joined.id]


def _member_of(store: TableStore, table, user: int, *, storyteller: int) -> None:
    request = store.request(user, table.join_code, None)
    store.approve(storyteller, request.id)


# --------------------------------------------------------------------------- #
# Request — the refusals (section 3)
# --------------------------------------------------------------------------- #


def test_an_unknown_code_is_refused(store: TableStore) -> None:
    store.create(ST, "Real")

    with pytest.raises(TableStoreError):
        store.request(PLAYER, "ZZZZZZ", None)


def test_a_request_can_bring_a_base(store: TableStore, characters) -> None:
    table = store.create(ST, "Bring")
    base = _base(characters, PLAYER)

    request = store.request(PLAYER, table.join_code, base.id)

    assert (request.user_id, request.base_id) == (PLAYER, base.id)
    assert [r.id for r in store.pending(ST, table.id)] == [request.id]


def test_another_accounts_base_is_refused(store: TableStore, characters) -> None:
    table = store.create(ST, "Theft")
    theirs = _base(characters, OTHER)

    with pytest.raises(TableStoreError):
        store.request(PLAYER, table.join_code, theirs.id)


def test_an_unlocked_base_is_refused(store: TableStore, characters) -> None:
    table = store.create(ST, "Draft")
    draft = characters.create(PLAYER, Character(id="x", name="Draft"))

    with pytest.raises(TableStoreError):
        store.request(PLAYER, table.join_code, draft.id)


def test_a_copy_as_the_base_is_refused(store: TableStore, characters) -> None:
    """XP belongs to a copy. A copy brought as a base would carry its XP in."""
    table = store.create(ST, "Copy")
    copy = characters.make_copy(PLAYER, _base(characters, PLAYER).id)

    with pytest.raises(TableStoreError):
        store.request(PLAYER, table.join_code, copy.id)


def test_a_duplicate_pending_request_is_refused(store: TableStore, characters) -> None:
    table = store.create(ST, "Twice")
    base = _base(characters, PLAYER)
    store.request(PLAYER, table.join_code, base.id)

    with pytest.raises(TableStoreError):
        store.request(PLAYER, table.join_code, base.id)


def test_a_duplicate_pending_watch_request_is_refused(store: TableStore) -> None:
    """`base_id IS NULL` needs its own comparison: NULL = NULL is not true in SQL."""
    table = store.create(ST, "Watch twice")
    store.request(PLAYER, table.join_code, None)

    with pytest.raises(TableStoreError):
        store.request(PLAYER, table.join_code, None)


def test_a_member_cannot_ask_to_watch_again(store: TableStore) -> None:
    table = store.create(ST, "Already")
    _member(store, table, PLAYER)

    with pytest.raises(TableStoreError):
        store.request(PLAYER, table.join_code, None)
    with pytest.raises(TableStoreError):
        store.request(ST, table.join_code, None)


def test_a_member_can_bring_another_character(store: TableStore, characters) -> None:
    """Ruled: several characters for each member (section 9.10)."""
    table = store.create(ST, "Two")
    first, second = _base(characters, PLAYER, "One"), _base(characters, PLAYER, "Two")
    _member(store, table, PLAYER, first.id)

    _member(store, table, PLAYER, second.id)

    names = sorted(characters.load(row).name for row in store.characters(table.id))
    assert names == ["One", "Two"]


def test_the_storyteller_can_bring_a_character(store: TableStore, characters) -> None:
    """Q4, answered 2026-09-12: allow it. It needs nothing of its own."""
    table = store.create(ST, "GMPC")
    base = _base(characters, ST)

    _member(store, table, ST, base.id)

    assert [row.owner_id for row in store.characters(table.id)] == [ST]
    assert store.access(ST, table.id) == "storyteller"


# --------------------------------------------------------------------------- #
# The throttle on the join form (section 2.3)
# --------------------------------------------------------------------------- #


def test_the_join_form_is_rate_limited(database: Path, tmp_path: Path) -> None:
    now = [0.0]
    store = TableStore(db_path=database, root=tmp_path / "sessions",
                       throttle=tables.JoinThrottle(clock=lambda: now[0]))
    table = store.create(ST, "Guarded")

    for _ in range(tables.JoinThrottle.FREE_ATTEMPTS):
        with pytest.raises(TableStoreError):
            store.request(PLAYER, "ZZZZZZ", None)

    with pytest.raises(TableStoreError, match="Wait"):
        store.request(PLAYER, table.join_code, None)
    assert store.pending(ST, table.id) == []

    now[0] += tables.JoinThrottle.FIRST_COOLDOWN + 1
    assert store.request(PLAYER, table.join_code, None).table_id == table.id


def test_a_correct_code_does_not_clear_the_count(database: Path, tmp_path: Path) -> None:
    """The count is keyed by the account that asks. That account can know a real
    code: its own campaign's. If a correct code cleared the count, it could guess
    four, clear with its own code, and guess four again, with no end."""
    store = TableStore(db_path=database, root=tmp_path / "sessions",
                       throttle=tables.JoinThrottle(clock=lambda: 0.0))
    own = store.create(PLAYER, "My own")

    for _ in range(tables.JoinThrottle.FREE_ATTEMPTS - 1):
        with pytest.raises(TableStoreError):
            store.request(PLAYER, "ZZZZZZ", None)
    with pytest.raises(TableStoreError):
        store.request(PLAYER, own.join_code, None)  # counted, then refused: own table

    with pytest.raises(TableStoreError, match="Wait"):
        store.request(PLAYER, "ZZZZZZ", None)


def test_the_count_is_per_account(database: Path, tmp_path: Path) -> None:
    store = TableStore(db_path=database, root=tmp_path / "sessions",
                       throttle=tables.JoinThrottle(clock=lambda: 0.0))
    table = store.create(ST, "Separate")
    for _ in range(tables.JoinThrottle.FREE_ATTEMPTS):
        with pytest.raises(TableStoreError):
            store.request(PLAYER, "ZZZZZZ", None)

    assert store.request(OTHER, table.join_code, None).table_id == table.id


# --------------------------------------------------------------------------- #
# Approve and reject
# --------------------------------------------------------------------------- #


def test_approval_makes_the_membership_and_the_copy(store: TableStore,
                                                   characters) -> None:
    table = store.create(ST, "Approve")
    base = _base(characters, PLAYER, "Jade")
    request = store.request(PLAYER, table.join_code, base.id)

    copy = store.approve(ST, request.id)

    assert store.access(PLAYER, table.id) == "member"
    assert (copy.owner_id, copy.is_copy, copy.base_id, copy.table_id) == (
        PLAYER, True, base.id, table.id)
    assert characters.row(copy.id) == copy
    assert characters.load(copy).name == "Jade"
    assert store.pending(ST, table.id) == []


def test_the_copy_is_in_the_owners_folder(store: TableStore, characters) -> None:
    """A table folder never holds a character (section 2.2)."""
    table = store.create(ST, "Folders")
    copy = _member(store, table, PLAYER, _base(characters, PLAYER).id)

    assert characters.path_for(copy).is_relative_to(characters.account_dir(PLAYER))
    assert not any(store.table_dir(table.id).rglob("*.character.json"))


def test_approval_of_a_watch_request_makes_no_copy(store: TableStore) -> None:
    table = store.create(ST, "Watch")

    assert _member(store, table, PLAYER) is None
    assert store.access(PLAYER, table.id) == "member"
    assert store.characters(table.id) == []


def test_approval_does_not_absorb_homebrew_into_the_table(store: TableStore,
                                                         characters) -> None:
    """Section 4: nothing reaches the table layer as a side effect of a join."""
    from exalted_builder import custom_content

    custom_content.save_charm(
        {"id": "custom.house-strike", "name": "House Strike", "category": "melee",
         "type": "Supplemental"}, custom_dir=characters.custom_dir(PLAYER))
    character = Character(id="x", name="Brewer", caste="dawn")
    character.charms.append("custom.house-strike")
    lifecycle.lock_chargen(character)
    base = characters.create(PLAYER, character)
    table = store.create(ST, "Clean")

    copy = _member(store, table, PLAYER, base.id)

    carried = characters.load(copy).custom_definitions
    assert [r["id"] for r in carried["charms"]] == ["custom.house-strike"]
    assert not any(store.table_dir(table.id).rglob("*"))


def test_only_the_storyteller_approves(store: TableStore, characters) -> None:
    table = store.create(ST, "Gate")
    _member(store, table, PLAYER)
    request = store.request(OTHER, table.join_code, _base(characters, OTHER).id)

    for intruder in (PLAYER, OTHER):
        with pytest.raises(TableStoreError):
            store.approve(intruder, request.id)

    assert store.access(OTHER, table.id) is None
    assert store.characters(table.id) == []


def test_the_storyteller_of_another_table_cannot_approve(store: TableStore) -> None:
    """The check is the storyteller of THIS request's table, not any storyteller."""
    mine = store.create(ST, "Mine")
    store.create(OTHER, "Theirs")
    request = store.request(PLAYER, mine.join_code, None)

    with pytest.raises(TableStoreError):
        store.approve(OTHER, request.id)
    assert store.access(PLAYER, mine.id) is None


def test_an_unknown_request_is_refused(store: TableStore) -> None:
    with pytest.raises(TableStoreError):
        store.approve(ST, 999)


def test_a_base_unlocked_after_the_request_is_refused(store: TableStore,
                                                     characters) -> None:
    table = store.create(ST, "Changed")
    base = _base(characters, PLAYER)
    request = store.request(PLAYER, table.join_code, base.id)
    unlocked = characters.load(base)
    lifecycle.unlock_chargen(unlocked)
    characters.save(base, unlocked)

    with pytest.raises(TableStoreError):
        store.approve(ST, request.id)
    assert store.access(PLAYER, table.id) is None


def test_a_deleted_base_takes_its_request_with_it(store: TableStore, characters) -> None:
    table = store.create(ST, "Gone")
    base = _base(characters, PLAYER)
    store.request(PLAYER, table.join_code, base.id)

    characters.delete(PLAYER, base.id)

    assert store.pending(ST, table.id) == []


def test_reject_deletes_the_request(store: TableStore) -> None:
    table = store.create(ST, "No")
    request = store.request(PLAYER, table.join_code, None)

    store.reject(ST, request.id)

    assert store.pending(ST, table.id) == []
    assert store.access(PLAYER, table.id) is None


def test_only_the_storyteller_rejects(store: TableStore) -> None:
    table = store.create(ST, "Keep")
    request = store.request(PLAYER, table.join_code, None)

    with pytest.raises(TableStoreError):
        store.reject(PLAYER, request.id)
    assert [r.id for r in store.pending(ST, table.id)] == [request.id]


def test_only_the_storyteller_sees_the_requests(store: TableStore) -> None:
    table = store.create(ST, "Private")
    _member(store, table, PLAYER)
    store.request(OTHER, table.join_code, None)

    with pytest.raises(TableStoreError):
        store.pending(PLAYER, table.id)


def test_a_user_sees_their_own_pending_requests(store: TableStore) -> None:
    table = store.create(ST, "Mine pending")
    request = store.request(PLAYER, table.join_code, None)
    store.request(OTHER, table.join_code, None)

    assert [r.id for r in store.requests_by(PLAYER)] == [request.id]


# --------------------------------------------------------------------------- #
# Leave, remove, delete (section 10)
# --------------------------------------------------------------------------- #


def test_a_leaver_keeps_the_copy_as_solo(store: TableStore, characters) -> None:
    table = store.create(ST, "Leave")
    copy = _member(store, table, PLAYER, _base(characters, PLAYER).id)

    assert store.leave(PLAYER, table.id) is True

    assert store.access(PLAYER, table.id) is None
    kept = characters.owned(PLAYER, copy.id)
    assert kept is not None and kept.is_copy and kept.table_id is None
    assert characters.path_for(kept).is_file()
    assert store.characters(table.id) == []


def test_leaving_clears_only_the_leavers_copies(store: TableStore, characters) -> None:
    table = store.create(ST, "Others stay")
    mine = _member(store, table, PLAYER, _base(characters, PLAYER).id)
    theirs = _member(store, table, OTHER, _base(characters, OTHER).id)
    elsewhere = store.create(ST, "Elsewhere")
    other_table = _member(store, elsewhere, PLAYER, _base(characters, PLAYER).id)

    store.leave(PLAYER, table.id)

    assert characters.row(mine.id).table_id is None
    assert characters.row(theirs.id).table_id == table.id
    assert characters.row(other_table.id).table_id == elsewhere.id


def test_leaving_deletes_the_leavers_pending_requests(store: TableStore,
                                                     characters) -> None:
    table = store.create(ST, "Pending leave")
    _member(store, table, PLAYER)
    store.request(PLAYER, table.join_code, _base(characters, PLAYER).id)
    kept = store.request(OTHER, table.join_code, None)

    store.leave(PLAYER, table.id)

    assert [r.id for r in store.pending(ST, table.id)] == [kept.id]


def test_leave_withdraws_a_pending_request_of_a_non_member(store: TableStore) -> None:
    table = store.create(ST, "Withdraw")
    store.request(PLAYER, table.join_code, None)

    assert store.leave(PLAYER, table.id) is False
    assert store.pending(ST, table.id) == []


def test_withdraw_deletes_one_request_and_keeps_the_membership(store: TableStore,
                                                                characters) -> None:
    """🐞 `leave` is NOT a withdraw for a member: it takes the member out. A member
    who asked to bring a second character withdraws that one request only."""
    table = store.create(ST, "Second thoughts")
    _member(store, table, PLAYER)
    first = store.request(PLAYER, table.join_code, _base(characters, PLAYER, "One").id)
    second = store.request(PLAYER, table.join_code, _base(characters, PLAYER, "Two").id)

    assert store.withdraw(PLAYER, first.id) is True

    assert store.access(PLAYER, table.id) == "member"
    assert [r.id for r in store.pending(ST, table.id)] == [second.id]


def test_withdraw_refuses_the_request_of_another_account(store: TableStore) -> None:
    table = store.create(ST, "Not yours to withdraw")
    request = store.request(PLAYER, table.join_code, None)

    assert store.withdraw(OTHER, request.id) is False
    assert store.withdraw(ST, request.id) is False

    assert [r.id for r in store.pending(ST, table.id)] == [request.id]


def test_members_lists_the_members_and_not_the_storyteller(store: TableStore) -> None:
    """The Storyteller is not a row in `memberships` (section 2.1)."""
    table = store.create(ST, "Headcount")
    _member(store, table, PLAYER)
    _member(store, table, OTHER)
    store.leave(OTHER, table.id)
    _member(store, store.create(ST, "Elsewhere"), OTHER)

    assert store.members(table.id) == [PLAYER]
    assert store.members("../table") == []


def test_the_storyteller_cannot_leave(store: TableStore) -> None:
    table = store.create(ST, "Captain")

    with pytest.raises(TableStoreError):
        store.leave(ST, table.id)
    assert store.access(ST, table.id) == "storyteller"


def test_the_storyteller_removes_a_member(store: TableStore, characters) -> None:
    table = store.create(ST, "Remove")
    copy = _member(store, table, PLAYER, _base(characters, PLAYER).id)

    assert store.remove(ST, table.id, PLAYER) is True

    assert store.access(PLAYER, table.id) is None
    assert characters.row(copy.id).table_id is None


def test_only_the_storyteller_removes(store: TableStore) -> None:
    table = store.create(ST, "Coup")
    _member(store, table, PLAYER)
    _member(store, table, OTHER)

    with pytest.raises(TableStoreError):
        store.remove(PLAYER, table.id, OTHER)
    assert store.access(OTHER, table.id) == "member"


def test_the_storyteller_cannot_remove_themselves(store: TableStore) -> None:
    table = store.create(ST, "Self")

    with pytest.raises(TableStoreError):
        store.remove(ST, table.id, ST)


def test_delete_makes_every_copy_solo(store: TableStore, characters) -> None:
    """Q3, answered 2026-09-12: yes, the same rule as leaving."""
    table = store.create(ST, "End")
    copies = [_member(store, table, user, _base(characters, user).id)
              for user in (PLAYER, OTHER, ST)]
    store.request(OTHER, table.join_code, _base(characters, OTHER, "Second").id)
    (store.table_dir(table.id) / "notes.json").write_text("{}")

    assert store.delete(ST, table.id) is True

    assert store.table(table.id) is None
    assert not store.table_dir(table.id).exists()
    assert store.for_user(PLAYER) == [] and store.requests_by(OTHER) == []
    for copy in copies:
        kept = characters.row(copy.id)
        assert kept is not None and kept.table_id is None
        assert characters.path_for(kept).is_file()


def test_only_the_storyteller_deletes(store: TableStore) -> None:
    table = store.create(ST, "Survive")
    _member(store, table, PLAYER)

    for intruder in (PLAYER, OTHER):
        assert store.delete(intruder, table.id) is False
    assert store.table(table.id) is not None
    assert store.table_dir(table.id).is_dir()


def test_delete_of_a_malformed_id_touches_no_folder(store: TableStore) -> None:
    """The folder comes from the id. A hostile id must not reach `rmtree`."""
    victim = store.root / "user-2"
    victim.mkdir(parents=True)

    assert store.delete(ST, "../user-2") is False
    assert victim.is_dir()


def test_characters_lists_the_copies_with_owners(store: TableStore, characters) -> None:
    table = store.create(ST, "Roster")
    one = _member(store, table, PLAYER, _base(characters, PLAYER).id)
    two = _member(store, table, OTHER, _base(characters, OTHER).id)
    characters.make_copy(PLAYER, _base(characters, PLAYER).id)  # solo, not listed

    assert [(r.id, r.owner_id) for r in store.characters(table.id)] == [
        (one.id, PLAYER), (two.id, OTHER)]
