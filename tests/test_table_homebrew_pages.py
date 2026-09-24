"""The pages of the homebrew of a campaign: the request card, the Homebrew page
`/table/<id>/custom`, the proposals in the ST tab, and the Gear tab of a copy.

Step 7 of `docs/plans/p3-tables.md` section 14 (ruled 2026-09-23).

PRODUCTION wiring: `tests/_auth_main.py` runs `server/main.build_server` and the
login gate.

⚠ `should_not_see` returns on the first check at which the text is absent. Each
absence here follows a `should_see` of something that the same render draws.
"""

from __future__ import annotations

import pytest
from nicegui.testing import User

pytest.importorskip("bcrypt")

from exalted_builder import custom_content  # noqa: E402
from exalted_builder.engine import lifecycle  # noqa: E402
from exalted_builder.models.character import Character, Weapon  # noqa: E402
from exalted_builder.server import chrome, db, table_custom  # noqa: E402
from exalted_builder.server.characters import CharacterStore  # noqa: E402
from exalted_builder.server.table_homebrew import TableHomebrew  # noqa: E402
from exalted_builder.server.tables import TableStore  # noqa: E402

from . import _auth_state as state  # noqa: E402

MAIN = "tests/_auth_main.py"


def _characters() -> CharacterStore:
    return CharacterStore(db_path=state.DB, root=state.ROOT)


def _tables() -> TableStore:
    return TableStore(db_path=state.DB, root=state.ROOT)


async def _sign_up(user: User, username: str) -> int:
    await user.open("/signup")
    user.find(marker="signup-username").type(username)
    user.find(marker="signup-password").type(state.PASSWORD)
    user.find(marker="signup-confirm").type(state.PASSWORD)
    user.find(marker="signup-submit").click()
    await user.should_see(marker="home-new")
    return db.authenticate(state.DB, username, state.PASSWORD)


def _charm(cid: str, **over) -> dict:
    row = {"id": cid, "name": cid.replace("custom.", "").title(), "category": "melee",
           "type": "Supplemental", "min_ability": 1, "min_essence": 1,
           "description": f"The text of {cid}."}
    row.update(over)
    return row


def _base(owner: int, name: str, *charm_ids: str, **shape):
    character = Character(id="x", name=name, caste="dawn", charms=list(charm_ids),
                          **shape)
    lifecycle.lock_chargen(character)
    return _characters().create(owner, character)


def _entry_text(user: User) -> str:
    """Return the text of the one open homebrew pop-up. `should_see` with a marker
    matches the text of the marked card only, and the card has its text in
    children."""
    (card,) = user.find(marker="homebrew-entry").elements
    return "\n".join(text for element in card.descendants()
                     if (text := getattr(element, "text", "")))


async def _campaign(create_user):
    """An ST and one watching player. Return (st, st id, table, player, player id)."""
    st = create_user()
    st_id = await _sign_up(st, "Harmonious")
    player = create_user()
    player_id = await _sign_up(player, "Player0")
    table = _tables().create(st_id, "The Scarlet Gambit")
    tables = _tables()
    tables.approve(st_id, tables.request(player_id, table.join_code, None).id)
    return st, st_id, table, player, player_id


# --------------------------------------------------------------------------- #
# The request card
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_request_card_names_what_the_approval_adds(create_user) -> None:
    st, st_id, table, _, player_id = await _campaign(create_user)
    tables = _tables()
    custom_content.save_charm(_charm("custom.fang"),
                              custom_dir=_characters().custom_dir(player_id))
    custom_content.save_charm(_charm("custom.oath", name="Campaign Oath"),
                              custom_dir=tables.homebrew_dir(table.id))
    custom_content.save_charm(_charm("custom.oath", name="Player Oath"),
                              custom_dir=_characters().custom_dir(player_id))
    request = tables.bring(player_id, table.id,
                           _base(player_id, "Ashes", "custom.fang", "custom.oath").id)

    await st.open(chrome.table_url(table.id))

    await st.should_see(marker=f"table-request-adds-{request.id}",
                        content="Approving adds to the campaign homebrew: Fang")
    await st.should_see(marker=f"table-request-differs-{request.id}",
                        content="Player Oath")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_views_the_requested_character(create_user) -> None:
    """The human, 2026-09-24: the Storyteller sees the character before approving."""
    st, _, table, _, player_id = await _campaign(create_user)
    request = _tables().bring(player_id, table.id,
                              _base(player_id, "Ashes", concept="Wandering Sword").id)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"table-request-{request.id}")
    await st.should_see(marker=f"table-request-view-{request.id}")

    st.find(marker=f"table-request-view-{request.id}").click()

    await st.should_see(marker=f"table-request-sheet-{request.id}")
    await st.should_see("Concept: Wandering Sword")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_views_a_carried_row_as_the_player_has_it(create_user) -> None:
    """The pop-up shows the CARRIED row. For a clash that is the player's version,
    not the campaign's, thus the two names discriminate."""
    st, _, table, _, player_id = await _campaign(create_user)
    custom_content.save_charm(_charm("custom.oath", name="Campaign Oath"),
                              custom_dir=_tables().homebrew_dir(table.id))
    custom_content.save_charm(_charm("custom.oath", name="Player Oath",
                                     description="The oath as the player wrote it."),
                              custom_dir=_characters().custom_dir(player_id))
    request = _tables().bring(player_id, table.id,
                              _base(player_id, "Ashes", "custom.oath").id)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"table-request-{request.id}")

    st.find(marker=f"table-request-row-view-{request.id}-custom.oath").click()

    await st.should_see(marker="homebrew-entry")
    text = _entry_text(st)
    assert "Player Oath" in text and "Campaign Oath" not in text
    assert "The oath as the player wrote it." in text
    assert "Type: Supplemental" in text


# --------------------------------------------------------------------------- #
# The Homebrew page
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_stranger_gets_nothing(create_user) -> None:
    _, _, table, _, _ = await _campaign(create_user)
    stranger = create_user()
    await _sign_up(stranger, "Stranger")

    await stranger.open(table_custom.custom_url(table.id))

    await stranger.should_see(marker="table-not-found")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_gets_the_editor(create_user) -> None:
    st, _, table, _, _ = await _campaign(create_user)
    custom_content.save_charm(_charm("custom.oath"),
                              custom_dir=_tables().homebrew_dir(table.id))

    await st.open(table_custom.custom_url(table.id))

    await st.should_see(marker="custom-export")
    await st.should_see("Oath")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_editor_is_not_in_a_narrow_column(create_user) -> None:
    """🐞 Click-through, 2026-09-24. The editor is one row that does not wrap: two
    cards of 24 and 26 rem and the form. A 64 rem column left the form about
    13 rem. `/home` gives the editor the full width; this page must too."""
    st, _, table, _, _ = await _campaign(create_user)
    await st.open(table_custom.custom_url(table.id))
    await st.should_see(marker="custom-name")

    (field,) = st.find(marker="custom-name").elements
    element = field
    while element.parent_slot is not None:
        element = element.parent_slot.parent
        assert not any(c.startswith("max-w-") for c in element.classes), (
            f"The editor is in a column of limited width: {element.classes}")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_member_reads_the_homebrew_of_the_campaign(create_user) -> None:
    _, _, table, player, _ = await _campaign(create_user)
    custom_content.save_charm(_charm("custom.oath"),
                              custom_dir=_tables().homebrew_dir(table.id))

    await player.open(table_custom.custom_url(table.id))

    await player.should_see(marker="table-homebrew-row-custom.oath", content="Oath")
    await player.should_see("The text of custom.oath.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_member_writes_to_their_library_and_then_proposes(create_user) -> None:
    """The human, 2026-09-24: a player writes a new row on this page. The row goes
    to the library of the player, not to the campaign. It is then offered for a
    proposal, with no return to `/home`."""
    _, _, table, player, player_id = await _campaign(create_user)

    await player.open(table_custom.custom_url(table.id))
    await _author_in_the_form(player, "Bright Fang")

    await player.should_see(marker="table-propose-charms-custom.bright-fang")
    mine = custom_content.library_charms(_characters().custom_dir(player_id))
    assert "custom.bright-fang" in {row["id"] for row in mine}
    campaign = custom_content.library_charms(_tables().homebrew_dir(table.id))
    assert "custom.bright-fang" not in {row["id"] for row in campaign}, (
        "The member's editor wrote to the campaign.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_table_view_links_to_the_homebrew_page(create_user) -> None:
    _, _, table, player, _ = await _campaign(create_user)

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="table-homebrew")


# --------------------------------------------------------------------------- #
# Proposals
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_views_a_proposed_row(create_user) -> None:
    """The pop-up shows the COPY that the proposal holds, thus an edit to the
    library after the proposal does not reach it."""
    st, st_id, table, _, player_id = await _campaign(create_user)
    library = _characters().custom_dir(player_id)
    custom_content.save_charm(_charm("custom.fang", description="As proposed."),
                              custom_dir=library)
    proposal = TableHomebrew(_tables()).propose(player_id, table.id, "charms",
                                                "custom.fang")
    custom_content.save_charm(_charm("custom.fang", description="Edited later."),
                              custom_dir=library)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"table-proposal-{proposal.id}")

    st.find(marker=f"table-proposal-view-{proposal.id}-custom.fang").click()

    await st.should_see(marker="homebrew-entry")
    text = _entry_text(st)
    assert "As proposed." in text
    assert "Edited later." not in text


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_member_proposes_and_the_storyteller_approves(create_user) -> None:
    st, st_id, table, player, player_id = await _campaign(create_user)
    custom_content.save_charm(_charm("custom.fang"),
                              custom_dir=_characters().custom_dir(player_id))

    await player.open(table_custom.custom_url(table.id))
    player.find(marker="table-propose-charms-custom.fang").click()
    await player.should_see(marker="table-my-proposals")
    await player.should_see("Fang · waits for the Storyteller")

    [proposal] = TableHomebrew(_tables()).proposals(st_id, table.id)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"table-proposal-{proposal.id}")
    await st.should_see("Proposes: Fang")
    st.find(marker=f"table-proposal-approve-{proposal.id}").click()

    folder = _tables().homebrew_dir(table.id)
    assert [r["id"] for r in custom_content.library_charms(folder)] == ["custom.fang"]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_rejects_a_proposal(create_user) -> None:
    st, st_id, table, _, player_id = await _campaign(create_user)
    custom_content.save_charm(_charm("custom.fang"),
                              custom_dir=_characters().custom_dir(player_id))
    homebrew = TableHomebrew(_tables())
    proposal = homebrew.propose(player_id, table.id, "charms", "custom.fang")

    await st.open(chrome.table_url(table.id))
    st.find(marker=f"table-proposal-reject-{proposal.id}").click()

    assert homebrew.proposals(st_id, table.id) == []
    assert custom_content.library_charms(_tables().homebrew_dir(table.id)) == []


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_row_the_campaign_has_is_not_offered(create_user) -> None:
    _, _, table, player, player_id = await _campaign(create_user)
    custom_content.save_charm(_charm("custom.fang"),
                              custom_dir=_characters().custom_dir(player_id))
    custom_content.save_charm(_charm("custom.claw"),
                              custom_dir=_characters().custom_dir(player_id))
    custom_content.save_charm(_charm("custom.fang"),
                              custom_dir=_tables().homebrew_dir(table.id))

    await player.open(table_custom.custom_url(table.id))

    await player.should_see(marker="table-propose-charms-custom.claw")
    await player.should_not_see(marker="table-propose-charms-custom.fang")


# --------------------------------------------------------------------------- #
# The Gear tab of a campaign copy has no library
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_campaign_copy_has_no_save_to_library(create_user) -> None:
    st, st_id, table, player, player_id = await _campaign(create_user)
    tables = _tables()
    weapon = Weapon(name="Old Sword", speed=5, accuracy=1, damage=3, defense=1)
    copy = tables.approve(st_id, tables.bring(
        player_id, table.id, _base(player_id, "Ashes", weapons=[weapon]).id).id)
    solo = _characters().make_copy(player_id, _base(player_id, "Solo",
                                                    weapons=[weapon]).id)

    await player.open(chrome.character_url(solo.id))
    player.find("Gear").click()
    await player.should_see(marker="save-to-library")

    await player.open(chrome.character_url(copy.id))
    player.find("Gear").click()
    await player.should_see("Old Sword")
    await player.should_not_see(marker="save-to-library")


# --------------------------------------------------------------------------- #
# The context factory: which RuleSet a character page holds
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_copy_page_holds_the_campaign_rules_not_the_library(create_user) -> None:
    """Q1: no. And a save of the page takes its homebrew from the campaign."""
    _, st_id, table, player, player_id = await _campaign(create_user)
    tables = _tables()
    custom_content.save_charm(_charm("custom.oath"),
                              custom_dir=tables.homebrew_dir(table.id))
    custom_content.save_charm(_charm("custom.mine"),
                              custom_dir=_characters().custom_dir(player_id))
    copy = tables.approve(st_id, tables.bring(player_id, table.id,
                                              _base(player_id, "Ashes").id).id)

    await player.open(chrome.character_url(copy.id))
    await player.should_see("Ashes")

    ctx = state.REGISTRY.peek(copy.id)
    assert "custom.oath" in ctx["ruleset"].charms
    assert "custom.mine" not in ctx["ruleset"].charms
    assert ctx["custom_dir"] == tables.homebrew_dir(table.id)
    assert ctx["library_dir"] is None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_draft_page_holds_the_campaign_rules_and_the_library(create_user) -> None:
    _, _, table, player, player_id = await _campaign(create_user)
    tables = _tables()
    custom_content.save_charm(_charm("custom.oath"),
                              custom_dir=tables.homebrew_dir(table.id))
    custom_content.save_charm(_charm("custom.mine"),
                              custom_dir=_characters().custom_dir(player_id))
    draft = tables.start_draft(player_id, table.id)

    await player.open(chrome.character_url(draft.id))
    await player.should_see(marker="draft-for-campaign")

    ctx = state.REGISTRY.peek(draft.id)
    assert {"custom.oath", "custom.mine"} <= set(ctx["ruleset"].charms)
    assert ctx["library_dir"] == _characters().custom_dir(player_id)


# --------------------------------------------------------------------------- #
# A save on a Custom page reaches a draft for a campaign. ⚠ The draft holds a
# stack of two folders; a reload of one folder would drop the other.
# --------------------------------------------------------------------------- #


async def _author_in_the_form(user: User, name: str) -> None:
    user.find(marker="custom-name").type(name)
    user.find(marker="custom-save").click()


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storytellers_save_reaches_a_draft(create_user) -> None:
    st, _, table, player, player_id = await _campaign(create_user)
    custom_content.save_charm(_charm("custom.mine"),
                              custom_dir=_characters().custom_dir(player_id))
    draft = _tables().start_draft(player_id, table.id)
    await player.open(chrome.character_url(draft.id))
    await player.should_see(marker="draft-for-campaign")

    await st.open(table_custom.custom_url(table.id))
    await _author_in_the_form(st, "Storm Oath")
    await st.should_see("Storm Oath")

    charms = state.REGISTRY.peek(draft.id)["ruleset"].charms
    assert {"custom.storm-oath", "custom.mine"} <= set(charms)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_save_on_home_reaches_a_draft(create_user) -> None:
    _, _, table, player, player_id = await _campaign(create_user)
    custom_content.save_charm(_charm("custom.oath"),
                              custom_dir=_tables().homebrew_dir(table.id))
    draft = _tables().start_draft(player_id, table.id)
    await player.open(chrome.character_url(draft.id))
    await player.should_see(marker="draft-for-campaign")

    await player.open("/home")
    player.find("Homebrew").click()
    await _author_in_the_form(player, "Quiet Step")
    await player.should_see("Quiet Step")

    charms = state.REGISTRY.peek(draft.id)["ruleset"].charms
    assert {"custom.quiet-step", "custom.oath"} <= set(charms)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_save_to_library_on_a_draft_keeps_the_campaign_layer(create_user) -> None:
    _, _, table, player, player_id = await _campaign(create_user)
    tables = _tables()
    custom_content.save_charm(_charm("custom.oath"),
                              custom_dir=tables.homebrew_dir(table.id))
    draft = tables.start_draft(player_id, table.id)
    store = _characters()
    character = store.load(draft)
    character.weapons.append(Weapon(name="Old Sword", speed=5, damage=3))
    store.save(draft, character)

    await player.open(chrome.character_url(draft.id))
    player.find("Gear").click()
    await player.should_see(marker="save-to-library")
    player.find(marker="save-to-library").click()

    rules = state.REGISTRY.peek(draft.id)["ruleset"]
    assert any(w.name == "Old Sword" for w in rules.weapon_catalog.values())
    assert "custom.oath" in rules.charms
