"""The landing page and the character pages of the hosted server: `server/home.py`.

PRODUCTION wiring: `tests/_auth_main.py` runs `server/main.build_server` and the
login gate. Section 5 piece 4; `docs/plans/vtt.md` sections 9.2 to 9.4 and the
rulings of 9.3a (2026-09-12).

⚠ `should_not_see` returns on the first check at which the text is absent. Each
absence here follows a `should_see` of something that the same render draws.
"""

from __future__ import annotations

import pytest
from nicegui.elements.timer import Timer
from nicegui.testing import User

pytest.importorskip("bcrypt")

from exalted_builder import custom_content, persistence, rules_db  # noqa: E402
from exalted_builder.engine import lifecycle  # noqa: E402
from exalted_builder.models.character import Character  # noqa: E402
from exalted_builder.server import db, home  # noqa: E402
from exalted_builder.server.characters import CharacterStore  # noqa: E402
from exalted_builder.server.rulesets import Rulesets  # noqa: E402
from exalted_builder.server.tables import TableStore  # noqa: E402

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
async def test_the_homebrew_tab_prints_no_server_path(user: User) -> None:
    """🐞 The desktop Custom page prints its library folder. On the server that is
    a path on the SERVER, and it shows the layout of the account folders."""
    from nicegui import ui as _ui

    await _sign_up(user, "Harmonious")
    texts = [e.text for e in user.client.elements.values() if isinstance(e, _ui.label)]

    assert "Custom content" in texts, "The Homebrew tab did not render."
    assert not [t for t in texts if str(state.ROOT) in t or "sessions" in t]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_top_bar_names_the_character_and_its_stage(user: User) -> None:
    """With several characters the splat alone does not tell the pages apart."""
    user_id = await _sign_up(user, "Harmonious")
    row = _store().create(user_id, Character(id="x", name="Named In The Bar", caste="dawn"))

    await user.open(home.character_url(row.id))

    await user.should_see("Named In The Bar")
    await user.should_see("Solar · Draft")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_only_the_lock_action_that_applies_is_shown(user: User) -> None:
    """A draft shows Finish & Lock and no Unlock; a campaign copy, which is locked,
    shows Unlock and no Finish & Lock. ⚠ `user.find` skips hidden elements, thus
    the buttons are read from the page."""

    def _marked(user: User, marker: str):
        return next(e for e in user.client.elements.values()
                    if marker in getattr(e, "_markers", []))

    user_id = await _sign_up(user, "Harmonious")
    store = _store()
    draft = store.create(user_id, Character(id="x", name="Drafted"))
    copy = store.make_copy(user_id, store.create(user_id, _locked("Based")).id)

    await user.open(home.character_url(draft.id))
    await user.should_see(marker="top-bar-save")
    lock, unlock = _marked(user, "top-bar-lock"), _marked(user, "top-bar-unlock")
    assert lock.visible and not unlock.visible

    await user.open(home.character_url(copy.id))
    await user.should_see("Campaign copy")
    lock, unlock = _marked(user, "top-bar-lock"), _marked(user, "top-bar-unlock")
    assert unlock.visible and not lock.visible


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_unlock_after_xp_warns_before_it_unlocks(user: User) -> None:
    """Ruled 2026-09-12: unlock after XP is allowed, with a warning."""
    from exalted_builder.models.character import XpEntry

    user_id = await _sign_up(user, "Harmonious")
    store = _store()
    copy = store.make_copy(user_id, store.create(user_id, _locked("Spent")).id)
    character = store.load(copy)
    character.xp_log.append(XpEntry(target="essence", from_rating=2, to_rating=3, cost=16))
    store.save(copy, character)

    await user.open(home.character_url(copy.id))
    await user.should_see("Campaign copy")
    user.find(marker="top-bar-unlock").click()
    await user.should_see("16 XP")
    assert state.REGISTRY.ctx_for(copy.id)["char"].chargen_locked, "Unlocked before the confirm."

    user.find(marker="unlock-confirm").click()
    await user.should_see(marker="top-bar-lock")
    assert not state.REGISTRY.ctx_for(copy.id)["char"].chargen_locked


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_character_page_has_no_custom_tab(user: User) -> None:
    """The homebrew library is on /home: it belongs to the account."""
    await _sign_up(user, "Harmonious")
    await _new_character(user)

    tabs = [e for e in user.client.elements.values()
            if type(e).__name__ == "Tab" and e.props.get("name") == "Custom"]
    assert tabs and not tabs[0].visible


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_party_page_is_not_on_the_server(user: User) -> None:
    await _sign_up(user, "Harmonious")

    response = await user.http_client.get("/gm", follow_redirects=False)

    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Save, auto-save and download on a character page
#
# Moved here from test_hosted_save.py and test_session_destinations.py on
# 2026-09-12, when the per-account builder they tested left the server. The
# properties are the same; the wiring is the production wiring again.
# --------------------------------------------------------------------------- #

# The text of the desktop's browser download dialog.
DOWNLOAD_PROMPT = "Downloads to your browser's download folder."


async def _new_character(user: User) -> dict:
    """Press New character on /home. Return the context of the new character."""
    await user.should_see(marker="home-new")
    before = set(state.REGISTRY.keys())
    user.find(marker="home-new").click()
    await user.should_see("Identity")
    (key,) = set(state.REGISTRY.keys()) - before
    return state.REGISTRY.ctx_for(key)


def _timers(user: User) -> list[Timer]:
    """The timers of the page of `user`. ⚠ Call `timer.callback()`; do not wait.
    `saving.AUTOSAVE_SECONDS` is a real debounce."""
    return [e for e in user.client.elements.values() if isinstance(e, Timer)]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_save_does_not_also_offer_a_download(user: User) -> None:
    """⚠ Keep the `should_see` before the `should_not_see`. It waits for the
    handler, and only then is the absence of the prompt meaningful."""
    await _sign_up(user, "Harmonious")
    await _new_character(user)

    user.find(marker="top-bar-save").click()
    await user.should_see("Saved")          # settles the handler; do not remove

    await user.should_not_see(DOWNLOAD_PROMPT)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_auto_save_timer_writes_the_character_file(user: User) -> None:
    """The page must CALL the auto-save. A correct mechanism with no call site is
    this project's usual defect. ⚠ The auto-save is quiet: assert the file."""
    await _sign_up(user, "Harmonious")
    ctx = await _new_character(user)

    ctx["char"].name = "AutoSavedName"
    assert _timers(user), "The page registered no timer."
    for timer in _timers(user):
        timer.callback()

    assert persistence.load_character(ctx["path"], absorb_custom=False).name == "AutoSavedName"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_two_accounts_auto_save_to_their_own_files(create_user) -> None:
    """🐞 Section 3.7: the auto-save is the live caller that makes a shared
    destination reachable. Two accounts editing at once make two files."""
    a, b = create_user(), create_user()
    await _sign_up(a, "Harmonious")
    ctx_a = await _new_character(a)
    await _sign_up(b, "Radiant")
    ctx_b = await _new_character(b)
    ctx_a["char"].name, ctx_b["char"].name = "AccountAName", "AccountBName"

    for user in (a, b):
        for timer in _timers(user):
            timer.callback()

    assert ctx_a["path"] != ctx_b["path"]
    assert persistence.load_character(ctx_a["path"], absorb_custom=False).name == "AccountAName"
    assert persistence.load_character(ctx_b["path"], absorb_custom=False).name == "AccountBName"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_download_gives_the_character_and_keeps_the_save_target(user: User) -> None:
    """🐞 The trap of section 5.1c: the desktop download helpers move `ctx["path"]`
    to the downloaded name. On the server that moves the auto-save target."""
    await _sign_up(user, "Harmonious")
    ctx = await _new_character(user)
    path_before, dir_before = ctx["path"], ctx["dir"]
    ctx["char"].name = "DownloadedName"

    user.find(marker="top-bar-download").click()
    response = await user.download.next()

    assert persistence.character_from_json(response.text).name == "DownloadedName"
    assert (ctx["path"], ctx["dir"]) == (path_before, dir_before)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_character_page_takes_no_path_from_the_browser(user: User) -> None:
    """🐞 Closed 2026-09-12 (`beda3ec`): a Load dialog that took a server path let
    a player open and auto-save over the save of another account. A character
    page has no Load at all; import is on /home, by upload."""
    await _sign_up(user, "Harmonious")
    await _new_character(user)

    await user.should_see(marker="top-bar-save")
    await user.should_not_see(marker="top-bar-load")
    await user.should_not_see(marker="load-by-path")


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


# The shapes that broke a page before (preflight pass 3): casteless and Charmless
# (Mortal), no ability-castes (Lunar), and a sample of the other splats.
_SHAPES = [
    {"exalt_type": "Solar", "caste": "dawn"},
    {"exalt_type": "Mortal", "caste": "", "origin": "heroic", "essence_rating": 1},
    {"exalt_type": "Lunar", "caste": "full-moon"},
    {"exalt_type": "Dragon-Blooded", "caste": "air"},
    {"exalt_type": "Alchemical", "caste": "orichalcum"},
    {"exalt_type": "God-Blooded", "caste": "ghost-blooded"},
]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
@pytest.mark.parametrize("shape", _SHAPES, ids=lambda shape: shape["exalt_type"])
async def test_the_base_page_and_its_copy_render_for_each_shape(user: User, shape) -> None:
    user_id = await _sign_up(user, "Harmonious")
    character = Character(id="x", name="Shaped Hero", **shape)
    lifecycle.lock_chargen(character)
    base = _store().create(user_id, character)

    await user.open(home.character_url(base.id))
    await user.should_see(marker="base-note")
    await user.should_see("Shaped Hero")

    user.find(marker="base-copy").click()
    await user.should_see(marker="top-bar-save")


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
    rulesets = Rulesets(rules_db.load_ruleset("exalted_builder/data"), store,
                        TableStore(db_path=database, root=tmp_path / "sessions"))

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


# --------------------------------------------------------------------------- #
# A campaign copy (P3 step 5): the Storyteller grants XP and unlocks
# --------------------------------------------------------------------------- #


def _campaign_copy(player_id: int, name: str):
    """A table run by a second account, and a copy of `player_id` in it."""
    from exalted_builder.server.tables import TableStore

    st_id = db.create_user(state.DB, f"Storyteller{player_id}", state.PASSWORD)
    tables = TableStore(db_path=state.DB, root=state.ROOT)
    table = tables.create(st_id, "The Scarlet Gambit")
    base = _store().create(player_id, _locked(name))
    request = tables.request(player_id, table.join_code, base.id)
    return tables, table, tables.approve(st_id, request.id)


def _marked_all(user: User, marker: str) -> list:
    """Each element with `marker`, hidden or not. `user.find` skips hidden ones."""
    return [e for e in user.client.elements.values()
            if marker in getattr(e, "_markers", [])]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_campaign_copy_has_no_adjust_xp_downtime_or_unlock(user: User) -> None:
    """⚠ House bug type 3 (p3-tables.md section 12): Adjust XP lets the player set
    their own XP, and Unlock reopens creation. On a campaign copy the Storyteller
    does both (ruling 2, Q5, Q6). The discriminator is `table_id` in the database,
    which no control of the page edits. ⚠ Not built at all: a hidden button still
    has a handler."""
    user_id = await _sign_up(user, "Harmonious")
    _, _, copy = _campaign_copy(user_id, "Tabled")

    await user.open(home.character_url(copy.id))

    await user.should_see(marker="xp-by-storyteller")
    assert not _marked_all(user, "xp-adjust")
    assert not _marked_all(user, "xp-downtime")
    assert not _marked_all(user, "top-bar-unlock")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_solo_copy_keeps_adjust_xp_downtime_and_unlock(user: User) -> None:
    """The negative control of the case above: the same page, with no table."""
    user_id = await _sign_up(user, "Harmonious")
    store = _store()
    copy = store.make_copy(user_id, store.create(user_id, _locked("Solo")).id)

    await user.open(home.character_url(copy.id))

    await user.should_see(marker="xp-adjust")
    await user.should_see(marker="xp-downtime")
    assert _marked_all(user, "top-bar-unlock")
    assert not _marked_all(user, "xp-by-storyteller")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_copy_that_leaves_its_campaign_gets_adjust_xp_back(user: User) -> None:
    """Ruling 3: a leaver keeps each copy as a solo copy. The page reads `table_id`
    at each open, not once."""
    user_id = await _sign_up(user, "Harmonious")
    tables, table, copy = _campaign_copy(user_id, "Leaver")
    await user.open(home.character_url(copy.id))
    await user.should_see(marker="xp-by-storyteller")

    tables.leave(user_id, table.id)
    await user.open(home.character_url(copy.id))

    await user.should_see(marker="xp-adjust")
    assert _marked_all(user, "top-bar-unlock")


# --------------------------------------------------------------------------- #
# A campaign copy (P3 step 6): the Storyteller sets the house rules
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_campaign_copys_st_options_have_no_controls(user: User) -> None:
    """⚠ House bug type 3 (p3-tables.md section 5): a player who flips a TABLE-WIDE
    switch buys what the table forbids until the next load flips it back. Q2: the
    PER-CHARACTER permissions are the Storyteller's too. The discriminator is
    `table_id` in the database. ⚠ Not built at all, not disabled."""
    user_id = await _sign_up(user, "Harmonious")
    _, _, copy = _campaign_copy(user_id, "Tabled")
    await user.open(home.character_url(copy.id))

    user.find("ST Options").click()

    await user.should_see(marker="house-rules-by-campaign")
    await user.should_see("Magic for Everyone")
    assert not _marked_all(user, "house-rule-magic_for_everyone")
    assert not _marked_all(user, "house-rule-st_foreign_charms")
    assert not _marked_all(user, "house-rule-mf_change_method")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_solo_copys_st_options_keep_their_controls(user: User) -> None:
    """The negative control of the case above: the same tab, with no table."""
    user_id = await _sign_up(user, "Harmonious")
    store = _store()
    copy = store.make_copy(user_id, store.create(user_id, _locked("Solo")).id)
    await user.open(home.character_url(copy.id))

    user.find("ST Options").click()

    await user.should_see("Magic for Everyone")
    assert _marked_all(user, "house-rule-magic_for_everyone")
    assert _marked_all(user, "house-rule-st_foreign_charms")
    assert not _marked_all(user, "house-rules-by-campaign")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_copy_whose_file_disagrees_opens_with_the_table_rules(user: User) -> None:
    """Site 3 of section 5: the context factory. Whatever the file says, the page
    sees the table's values, and the file is put in step."""
    from exalted_builder.models.character import HouseRules

    user_id = await _sign_up(user, "Harmonious")
    tables, table, copy = _campaign_copy(user_id, "Drifted")
    tables.write_house_rules(table.id, HouseRules(magic_for_everyone=True,
                                                  mf_change_method="swap"))
    character = _store().load(copy)
    assert character.house_rules is None or not character.house_rules.magic_for_everyone

    await user.open(home.character_url(copy.id))
    await user.should_see(marker="xp-by-storyteller")

    held = state.REGISTRY.peek(copy.id)["char"]
    assert held.house_rules.magic_for_everyone is True
    assert held.house_rules.mf_change_method == "swap"
    assert _store().load(copy).house_rules.magic_for_everyone is True


# --------------------------------------------------------------------------- #
# A draft for a campaign (P3 step 6b)
# --------------------------------------------------------------------------- #


def _campaign_draft(player_id: int):
    """A table run by a second account, with `player_id` watching, and a draft of
    `player_id` for it."""
    from exalted_builder.server.tables import TableStore

    st_id = db.create_user(state.DB, f"Storyteller{player_id}", state.PASSWORD)
    tables = TableStore(db_path=state.DB, root=state.ROOT)
    table = tables.create(st_id, "The Scarlet Gambit")
    tables.approve(st_id, tables.request(player_id, table.join_code, None).id)
    return tables, table, st_id, tables.start_draft(player_id, table.id)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_campaign_draft_says_so_and_its_st_options_have_no_controls(
        user: User) -> None:
    """⚠ House bug type 3: the draft is built under the table's switches. A player
    who could flip them would build what the table forbids. The tag is a database
    row, which no control of the page edits."""
    user_id = await _sign_up(user, "Harmonious")
    _, _, _, draft = _campaign_draft(user_id)
    await user.open(home.character_url(draft.id))

    await user.should_see(marker="draft-for-campaign", content="The Scarlet Gambit")
    user.find("ST Options").click()
    await user.should_see(marker="house-rules-by-campaign")
    assert not _marked_all(user, "house-rule-magic_for_everyone")
    assert not _marked_all(user, "house-rule-st_foreign_charms")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_ordinary_draft_has_no_campaign_banner(user: User) -> None:
    """The negative control of the case above."""
    await _sign_up(user, "Harmonious")
    user.find(marker="home-new").click()
    await user.should_see("Identity")
    user.find("ST Options").click()
    await user.should_see("Magic for Everyone")
    assert _marked_all(user, "house-rule-magic_for_everyone")
    assert not _marked_all(user, "draft-for-campaign")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_draft_opens_with_the_table_rules(user: User) -> None:
    """Site 3 of section 5 covers a draft for the campaign too."""
    from exalted_builder.models.character import HouseRules

    user_id = await _sign_up(user, "Harmonious")
    tables, table, _, draft = _campaign_draft(user_id)
    tables.write_house_rules(table.id, HouseRules(restrict_chargen_ritual_level=True))

    await user.open(home.character_url(draft.id))
    await user.should_see(marker="draft-for-campaign")

    assert state.REGISTRY.peek(draft.id)["char"].house_rules.restrict_chargen_ritual_level


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_finish_and_lock_sends_a_campaign_draft_to_the_storyteller(
        user: User) -> None:
    user_id = await _sign_up(user, "Harmonious")
    tables, table, st_id, draft = _campaign_draft(user_id)
    await user.open(home.character_url(draft.id))
    await user.should_see(marker="draft-for-campaign")

    user.find(marker="top-bar-lock").click()

    await user.should_see(marker="base-note")
    (request,) = tables.pending(st_id, table.id)
    assert (request.user_id, request.base_id) == (user_id, draft.id)
    assert tables.draft_table(draft.id) is None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_home_names_the_campaign_of_a_draft(user: User) -> None:
    user_id = await _sign_up(user, "Harmonious")
    _campaign_draft(user_id)
    await user.open(home.HOME_PATH)
    await user.should_see("For The Scarlet Gambit")
