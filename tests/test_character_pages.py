"""The landing page and the character pages of the hosted server: `server/home.py`.

PRODUCTION wiring: `tests/_auth_main.py` runs `server/main.build_server` and the
login gate. Section 5 piece 4; `docs/plans/vtt.md` sections 9.2 to 9.4 and the
rulings of 9.3a (2026-09-12).

⚠ `should_not_see` returns on the first check at which the text is absent. Each
absence here follows a `should_see` of something that the same render draws.
"""

from __future__ import annotations

import pytest
from nicegui.testing import User

pytest.importorskip("bcrypt")

from exalted_builder import custom_content, persistence, rules_db  # noqa: E402
from exalted_builder.engine import lifecycle  # noqa: E402
from exalted_builder.models.character import Character  # noqa: E402
from exalted_builder.server import db, home  # noqa: E402
from exalted_builder.server.characters import CharacterStore  # noqa: E402

from . import _auth_state as state  # noqa: E402

MAIN = "tests/_auth_main.py"


def _store() -> CharacterStore:
    return CharacterStore(db_path=state.DB, root=state.ROOT)


async def _sign_up(user: User, username: str) -> int:
    """Make an account through the page. Return its id."""
    await user.open("/signup")
    user.find(marker="signup-username").type(username)
    user.find(marker="signup-password").type(state.PASSWORD)
    user.find(marker="signup-confirm").type(state.PASSWORD)
    user.find(marker="signup-submit").click()
    await user.should_see(marker="home-new")
    return db.authenticate(state.DB, username, state.PASSWORD)


def _locked(name: str) -> Character:
    character = Character(id="x", name=name, caste="dawn")
    lifecycle.lock_chargen(character)
    return character


# --------------------------------------------------------------------------- #
# /home
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_login_lands_on_the_character_list(user: User) -> None:
    """Section 9.4: `/home` is the landing page, not the builder."""
    await _sign_up(user, "Harmonious")

    await user.should_see("CHARACTERS (0)")
    await user.should_not_see("Identity")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_list_shows_drafts_bases_and_copies(user: User) -> None:
    user_id = await _sign_up(user, "Harmonious")
    store = _store()
    store.create(user_id, Character(id="x", name="Drafted Dawn"))
    base = store.create(user_id, _locked("Based Zenith"))
    store.make_copy(user_id, base.id)

    await user.open(home.HOME_PATH)

    await user.should_see("Drafted Dawn")
    await user.should_see("Draft")
    await user.should_see("Base")
    await user.should_see("Copy of Based Zenith")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_new_character_opens_its_own_page(user: User) -> None:
    user_id = await _sign_up(user, "Harmonious")

    user.find(marker="home-new").click()
    await user.should_see("Identity")

    (row,) = _store().list_for(user_id)
    ctx = state.REGISTRY.ctx_for(row.id)
    assert ctx["path"] == _store().path_for(row)
    assert ctx["custom_dir"] == _store().custom_dir(user_id)

    ctx["char"].name = "Saved Through The Page"
    user.find(marker="top-bar-save").click()
    await user.should_see("Saved")
    assert _store().load(row).name == "Saved Through The Page"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_character_page_has_home_and_no_party_new_or_load(user: User) -> None:
    """Party is hidden until P3 (ruled 2026-09-12). New and Load are on /home."""
    await _sign_up(user, "Harmonious")
    user.find(marker="home-new").click()

    await user.should_see(marker="top-bar-home")
    await user.should_see(marker="top-bar-save")
    await user.should_not_see(marker="top-bar-party")
    await user.should_not_see(marker="top-bar-new")
    await user.should_not_see(marker="top-bar-load")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_party_page_is_not_on_the_server(user: User) -> None:
    await _sign_up(user, "Harmonious")

    response = await user.http_client.get("/gm", follow_redirects=False)

    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Ownership
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_another_accounts_character_is_not_found(create_user) -> None:
    """⚠ The check is in the page, before the registry. The factory loads any
    row by id, thus a page that skipped `owned` would open the character."""
    owner = create_user()
    owner_id = await _sign_up(owner, "Harmonious")
    theirs = _store().create(owner_id, Character(id="x", name="Not Yours"))

    intruder = create_user()
    await _sign_up(intruder, "Radiant")
    await intruder.open(home.character_url(theirs.id))

    await intruder.should_see(marker="not-found")
    await intruder.should_not_see("Not Yours")
    assert theirs.id not in state.REGISTRY, "A context was made for another account."


# --------------------------------------------------------------------------- #
# Draft -> base -> copy (section 9.2)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_finish_and_lock_turns_a_draft_into_a_base(user: User) -> None:
    user_id = await _sign_up(user, "Harmonious")
    user.find(marker="home-new").click()
    await user.should_see("Identity")

    user.find(marker="top-bar-lock").click()

    await user.should_see(marker="base-note")
    (row,) = _store().list_for(user_id)
    assert _store().load(row).chargen_locked, "The lock was not saved."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_base_page_has_no_editing_tabs(user: User) -> None:
    """A base takes no XP. The page draws the sheet and no builder."""
    user_id = await _sign_up(user, "Harmonious")
    base = _store().create(user_id, _locked("Based Zenith"))

    await user.open(home.character_url(base.id))

    await user.should_see(marker="base-note")
    await user.should_not_see(marker="top-bar-save")
    await user.should_not_see(marker="top-bar-lock")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_base_makes_a_copy_that_opens_in_the_builder(user: User) -> None:
    user_id = await _sign_up(user, "Harmonious")
    base = _store().create(user_id, _locked("Based Zenith"))
    await user.open(home.character_url(base.id))
    await user.should_see(marker="base-note")

    user.find(marker="base-copy").click()

    await user.should_see(marker="top-bar-save")
    copies = [row for row in _store().list_for(user_id) if row.is_copy]
    assert [(c.base_id, _store().load(c).name) for c in copies] == [(base.id, "Based Zenith")]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_unlock_returns_a_base_to_the_builder(user: User) -> None:
    user_id = await _sign_up(user, "Harmonious")
    base = _store().create(user_id, _locked("Based Zenith"))
    await user.open(home.character_url(base.id))
    await user.should_see(marker="base-note")

    user.find(marker="base-unlock").click()

    await user.should_see(marker="top-bar-lock")
    assert not _store().load(base).chargen_locked


# --------------------------------------------------------------------------- #
# Delete (ruled: with a confirm, and the copies survive)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_delete_asks_and_keeps_the_copies(user: User) -> None:
    user_id = await _sign_up(user, "Harmonious")
    store = _store()
    base = store.create(user_id, _locked("Based Zenith"))
    copy = store.make_copy(user_id, base.id)
    await user.open(home.HOME_PATH)
    await user.should_see("Copy of Based Zenith")

    user.find(marker=f"home-delete-{base.id}").click()
    await user.should_see("Delete Based Zenith?")
    assert store.owned(user_id, base.id) is not None, "Deleted before the confirm."
    user.find(marker="home-confirm-delete").click()

    await user.should_see("Its base is deleted")
    assert store.owned(user_id, base.id) is None
    assert store.owned(user_id, copy.id) is not None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_open_page_of_a_deleted_character_does_not_write_it_again(
        create_user) -> None:
    """⚠ The auto-save of an open page writes to `ctx["path"]`. After a delete that
    write must fail. If it does not, the file comes back with no row."""
    laptop = create_user()
    user_id = await _sign_up(laptop, "Harmonious")
    laptop.find(marker="home-new").click()
    await laptop.should_see("Identity")
    (row,) = _store().list_for(user_id)
    ctx = state.REGISTRY.ctx_for(row.id)

    phone = create_user()
    await phone.open("/login")
    phone.find(marker="login-username").type("Harmonious")
    phone.find(marker="login-password").type(state.PASSWORD)
    phone.find(marker="login-submit").click()
    await phone.should_see(marker=f"home-delete-{row.id}")
    phone.find(marker=f"home-delete-{row.id}").click()
    phone.find(marker="home-confirm-delete").click()
    await phone.should_see("CHARACTERS (0)")

    ctx["char"].name = "Written After The Delete"
    laptop.find(marker="top-bar-save").click()
    await laptop.should_see("Save failed")
    assert not _store().path_for(row).exists()


# --------------------------------------------------------------------------- #
# Import (no harness can drive an upload; the page calls this function)
# --------------------------------------------------------------------------- #


def test_import_makes_a_new_character_and_takes_its_homebrew(tmp_path) -> None:
    database = tmp_path / "exalted.db"
    db.init_db(database)
    with db.connect(database) as connection:
        connection.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'a', 'x')")
    store = CharacterStore(db_path=database, root=tmp_path / "sessions")
    rulesets = home.AccountRulesets(rules_db.load_ruleset("exalted_builder/data"), store)

    source = Character(id="char.aaaaaaaaaaaa", name="Travelling Brewer")
    source.charms.append("custom.road-strike")
    source.custom_definitions = {"charms": [
        {"id": "custom.road-strike", "name": "Road Strike", "category": "melee",
         "type": "Supplemental"}]}

    custom_content.require_explicit_dir(True)
    try:
        row, added = home.import_character(store, rulesets, 1,
                                           persistence.character_to_json(source))
    finally:
        custom_content.require_explicit_dir(False)

    assert added == ["custom.road-strike"]
    assert row.id != source.id
    assert store.load(row).name == "Travelling Brewer"
    assert "custom.road-strike" in rulesets.for_account(1).charms
