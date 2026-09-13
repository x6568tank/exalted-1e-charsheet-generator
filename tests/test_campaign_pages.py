"""The campaign pages of the hosted server: `server/campaigns.py`.

Step 2 of the build order in `docs/plans/p3-tables.md`: the Campaigns section of
`/home` (new, join with a code and a base or to watch, pending, withdraw) and the
bare `/table/<id>` page with the request list of the Storyteller.

PRODUCTION wiring: `tests/_auth_main.py` runs `server/main.build_server` and the
login gate.

⚠ `access()` is the check, in the page body. A page that hides a control is not
a check. The store refuses each Storyteller operation again.

⚠ `should_not_see` returns on the first check at which the text is absent. Each
absence here follows a `should_see` of something that the same render draws.
"""

from __future__ import annotations

import pytest
from nicegui.testing import User

pytest.importorskip("bcrypt")

from exalted_builder.engine import lifecycle  # noqa: E402
from exalted_builder.models.character import Character  # noqa: E402
from exalted_builder.server import campaigns, db, home  # noqa: E402
from exalted_builder.server.characters import CharacterStore  # noqa: E402
from exalted_builder.server.tables import TableStore  # noqa: E402

from . import _auth_state as state  # noqa: E402

MAIN = "tests/_auth_main.py"


def _characters() -> CharacterStore:
    return CharacterStore(db_path=state.DB, root=state.ROOT)


def _tables() -> TableStore:
    return TableStore(db_path=state.DB, root=state.ROOT)


async def _sign_up(user: User, username: str) -> int:
    """Make an account through the page. Return its id."""
    await user.open("/signup")
    user.find(marker="signup-username").type(username)
    user.find(marker="signup-password").type(state.PASSWORD)
    user.find(marker="signup-confirm").type(state.PASSWORD)
    user.find(marker="signup-submit").click()
    await user.should_see(marker="home-new")
    return db.authenticate(state.DB, username, state.PASSWORD)


def _base(owner: int, name: str = "Based Zenith"):
    character = Character(id="x", name=name, caste="dawn")
    lifecycle.lock_chargen(character)
    return _characters().create(owner, character)


def _set(user: User, marker: str, value) -> None:
    """Set the value of the one element with `marker`."""
    (element,) = user.find(marker=marker).elements
    element.value = value


def _member(table, user_id: int, base_id: str | None = None):
    """Make `user_id` a member of `table` through the store."""
    tables = _tables()
    request = tables.request(user_id, table.join_code, base_id)
    return tables.approve(table.storyteller_id, request.id)


# --------------------------------------------------------------------------- #
# /home — the Campaigns section
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_home_has_a_campaigns_section(user: User) -> None:
    await _sign_up(user, "Harmonious")

    await user.should_see("CAMPAIGNS (0)")
    await user.should_see(marker="home-new-campaign")
    await user.should_see(marker="home-join")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_new_campaign_makes_it_and_opens_its_page(user: User) -> None:
    user_id = await _sign_up(user, "Harmonious")

    user.find(marker="home-new-campaign").click()
    user.find(marker="campaign-name").type("The Scarlet Gambit")
    user.find(marker="campaign-create").click()

    await user.should_see(marker="table-code")
    (table,) = _tables().for_user(user_id)
    assert table.storyteller_id == user_id and table.name == "The Scarlet Gambit"
    await user.should_see(table.join_code)

    await user.open(home.HOME_PATH)
    await user.should_see("CAMPAIGNS (1)")
    await user.should_see("The Scarlet Gambit")
    await user.should_see(marker=f"home-campaign-{table.id}")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_campaign_with_no_name_is_refused_on_the_page(user: User) -> None:
    user_id = await _sign_up(user, "Harmonious")

    user.find(marker="home-new-campaign").click()
    user.find(marker="campaign-create").click()

    await user.should_see("A campaign needs a name.")
    assert _tables().for_user(user_id) == []


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_join_with_a_base_makes_a_request_and_shows_it_waiting(create_user) -> None:
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "The Scarlet Gambit")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    base = _base(player_id)
    await player.open(home.HOME_PATH)

    player.find(marker="home-join").click()
    player.find(marker="join-code").type(table.join_code.lower())
    _set(player, "join-base", base.id)
    player.find(marker="join-send").click()

    await player.should_see("WAITING FOR THE STORYTELLER (1)")
    await player.should_see("The Scarlet Gambit")
    (request,) = _tables().requests_by(player_id)
    assert (request.table_id, request.base_id) == (table.id, base.id)
    assert _tables().access(player_id, table.id) is None, "A request gave access."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_join_to_watch_brings_no_base(create_user) -> None:
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Watched")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    _base(player_id)
    await player.open(home.HOME_PATH)

    player.find(marker="home-join").click()
    player.find(marker="join-code").type(table.join_code)
    _set(player, "join-base", campaigns.WATCH)
    player.find(marker="join-send").click()

    await player.should_see("WAITING FOR THE STORYTELLER (1)")
    (request,) = _tables().requests_by(player_id)
    assert request.base_id is None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_join_form_offers_bases_only(user: User) -> None:
    """A draft and a copy cannot join (section 9.2); the store refuses them too."""
    user_id = await _sign_up(user, "Harmonious")
    base = _base(user_id, "Based One")
    _characters().create(user_id, Character(id="x", name="Drafted One"))
    copy = _characters().make_copy(user_id, base.id)
    await user.open(home.HOME_PATH)

    user.find(marker="home-join").click()

    (select,) = user.find(marker="join-base").elements
    assert set(select.options) == {base.id, campaigns.WATCH}
    assert copy.id not in select.options


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_wrong_code_is_refused_on_the_page(user: User) -> None:
    user_id = await _sign_up(user, "Harmonious")

    user.find(marker="home-join").click()
    user.find(marker="join-code").type("ZZZZZZ")
    _set(user, "join-base", campaigns.WATCH)
    user.find(marker="join-send").click()

    await user.should_see("There is no campaign with that code.")
    assert _tables().requests_by(user_id) == []


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_base_card_opens_the_join_form_with_that_base(create_user) -> None:
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Shortcut")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    _base(player_id, "Not This One")
    base = _base(player_id, "This One")
    await player.open(home.HOME_PATH)

    player.find(marker=f"home-join-with-{base.id}").click()
    player.find(marker="join-code").type(table.join_code)
    player.find(marker="join-send").click()

    await player.should_see("WAITING FOR THE STORYTELLER (1)")
    (request,) = _tables().requests_by(player_id)
    assert request.base_id == base.id


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_withdraw_cancels_one_request_and_keeps_the_membership(create_user) -> None:
    """🐞 `leave` would take a member out. Withdraw cancels the one request."""
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Second thoughts")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    _member(table, player_id)
    request = _tables().request(player_id, table.join_code, _base(player_id).id)
    await player.open(home.HOME_PATH)
    await player.should_see("WAITING FOR THE STORYTELLER (1)")

    player.find(marker=f"home-withdraw-{request.id}").click()

    await player.should_see("CAMPAIGNS (1)")
    await player.should_not_see("WAITING FOR THE STORYTELLER")
    assert _tables().requests_by(player_id) == []
    assert _tables().access(player_id, table.id) == "member"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_card_shows_the_code_and_the_waiting_count(
        create_user) -> None:
    st = create_user()
    st_id = await _sign_up(st, "Harmonious")
    table = _tables().create(st_id, "Counted")
    player = create_user()
    _tables().request(await _sign_up(player, "Radiant"), table.join_code, None)

    await st.open(home.HOME_PATH)

    await st.should_see(table.join_code)
    await st.should_see("1 request waiting")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_copy_in_a_campaign_names_the_campaign(create_user) -> None:
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "The Scarlet Gambit")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    _member(table, player_id, _base(player_id).id)

    await player.open(home.HOME_PATH)

    await player.should_see("In The Scarlet Gambit")
    await player.should_see("Your characters: Based Zenith")


# --------------------------------------------------------------------------- #
# /table/<id>
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_sees_each_request_and_what_it_carries(create_user) -> None:
    """Section 4, consent: the Storyteller sees the homebrew that a base carries."""
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Consent")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    base = _base(player_id)
    character = _characters().load(base)
    character.custom_definitions = {"charms": [{"id": "custom.fang",
                                                "name": "Homebrewed Fang"}]}
    # ⚠ Write the file directly. `save` refreshes `custom_definitions` from the
    # library and drops a row that nothing references.
    _characters().path_for(base).write_text(character.model_dump_json())
    _tables().request(player_id, table.join_code, base.id)

    await st.open(campaigns.table_url(table.id))

    await st.should_see("REQUESTS (1)")
    await st.should_see("Radiant")
    await st.should_see("Based Zenith")
    await st.should_see("Homebrewed Fang")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_approve_makes_the_copy_in_the_table(create_user) -> None:
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "The Scarlet Gambit")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    base = _base(player_id)
    request = _tables().request(player_id, table.join_code, base.id)
    await st.open(campaigns.table_url(table.id))

    st.find(marker=f"table-approve-{request.id}").click()

    await st.should_see("REQUESTS (0)")
    (copy,) = _tables().characters(table.id)
    assert (copy.owner_id, copy.base_id, copy.is_copy) == (player_id, base.id, True)
    assert _tables().access(player_id, table.id) == "member"
    assert not (_tables().table_dir(table.id) / "custom").exists(), (
        "An approval wrote into the homebrew layer of the table.")
    await st.should_see("Based Zenith")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_table_page_renders_copies_of_each_shape(create_user) -> None:
    """Preflight pass 3: a casteless splat (Mortal), a splat with no ability castes
    (Lunar), and a copy whose file does not read."""
    st = create_user()
    st_id = await _sign_up(st, "Harmonious")
    table = _tables().create(st_id, "Shapes")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    for shape in ({"exalt_type": "Mortal", "caste": "", "origin": "heroic",
                   "essence_rating": 1, "name": "Mortal Hero"},
                  {"exalt_type": "Lunar", "caste": "full-moon", "name": "Lunar Hero"}):
        character = Character(id="x", **shape)
        lifecycle.lock_chargen(character)
        _member(table, player_id, _characters().create(player_id, character).id)
    broken = _member(table, player_id, _base(player_id, "Broken").id)
    _characters().path_for(broken).write_text("{not json")

    await st.open(campaigns.table_url(table.id))

    await st.should_see("CHARACTERS (3)")
    await st.should_see("Mortal Hero")
    await st.should_see("Lunar · Full Moon")
    await st.should_see(f"(unreadable: {broken.id})")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_reject_deletes_the_request(create_user) -> None:
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "No")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    request = _tables().request(player_id, table.join_code, None)
    await st.open(campaigns.table_url(table.id))

    st.find(marker=f"table-reject-{request.id}").click()

    await st.should_see("REQUESTS (0)")
    assert _tables().requests_by(player_id) == []
    assert _tables().access(player_id, table.id) is None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_request_withdrawn_meanwhile_does_not_break_the_page(create_user) -> None:
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Gone")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    request = _tables().request(player_id, table.join_code, None)
    await st.open(campaigns.table_url(table.id))
    await st.should_see("REQUESTS (1)")
    _tables().withdraw(player_id, request.id)

    st.find(marker=f"table-approve-{request.id}").click()

    await st.should_see("That request no longer exists.")
    assert _tables().access(player_id, table.id) is None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_member_sees_the_campaign_and_no_requests_or_code(create_user) -> None:
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Members only")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    _member(table, player_id, _base(player_id).id)

    await player.open(campaigns.table_url(table.id))

    await player.should_see(marker="table-title")
    await player.should_see("Members only")
    await player.should_see("Based Zenith")
    await player.should_not_see(table.join_code)
    await player.should_not_see(marker="table-requests")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_non_member_and_a_requester_get_no_campaign(create_user) -> None:
    """⚠ The check is `access()` in the page body. A pending request gives no access."""
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Private Gambit")
    asker = create_user()
    _tables().request(await _sign_up(asker, "Radiant"), table.join_code, None)
    stranger = create_user()
    await _sign_up(stranger, "Stranger")

    for user in (asker, stranger):
        await user.open(campaigns.table_url(table.id))
        await user.should_see(marker="table-not-found")
        await user.should_not_see("Private Gambit")
        await user.should_not_see(table.join_code)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_unknown_campaign_gets_the_same_answer(user: User) -> None:
    await _sign_up(user, "Harmonious")

    # ⚠ No "../" case: the HTTP client resolves it before the request.
    for hostile in ("table.000000000000", "table.XYZ", "x"):
        await user.open(campaigns.table_url(hostile))
        await user.should_see(marker="table-not-found")


# --------------------------------------------------------------------------- #
# The summary of carried homebrew (a pure helper)
# --------------------------------------------------------------------------- #


def test_carried_summary_names_each_row() -> None:
    character = Character(id="x", custom_definitions={
        "charms": [{"id": "custom.a", "name": "Fang"}, {"id": "custom.b", "name": "Claw"}],
        "spells": [{"id": "custom.c", "name": "Ember"}]})

    assert campaigns.carried_summary(character) == (
        "Carries homebrew: 2 Charms (Fang, Claw); 1 spell (Ember)")


def test_carried_summary_is_none_for_no_homebrew() -> None:
    assert campaigns.carried_summary(Character(id="x")) is None
