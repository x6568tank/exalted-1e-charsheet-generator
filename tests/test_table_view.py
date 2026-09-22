"""The table view of the hosted server: `server/table_view.py`.

Step 3 of the build order in `docs/plans/p3-tables.md` section 15.4: layout A,
the top bar with Open as and Spectate, YOU PLAY with live controls through the
character registry, the others read-only, the right rail's tabs, the poll, and
the "no longer in this campaign" path.

PRODUCTION wiring: `tests/_auth_main.py` runs `server/main.build_server` and the
login gate. `state.REGISTRY` is the character registry of that server.

⚠ `should_not_see` returns on the first check at which the text is absent. Each
absence here follows a `should_see` of something that the same render draws.

⚠ The poll runs each `table_view.POLL_SECONDS`. A test that waits for it gives
`should_see` enough retries (`_POLL_RETRIES`, 0.1 s each).
"""

from __future__ import annotations

import pytest
from nicegui import ui
from nicegui.testing import User

pytest.importorskip("bcrypt")

from exalted_builder.engine import lifecycle  # noqa: E402
from exalted_builder.engine import play as engineplay  # noqa: E402
from exalted_builder.models.character import (  # noqa: E402
    Armor, Character, Damage, MeritFlawPurchase, PlayState)
from exalted_builder.server import chrome, db, table_log, table_view  # noqa: E402
from exalted_builder.server.characters import CharacterStore  # noqa: E402
from exalted_builder.server.tables import TableStore  # noqa: E402

from . import _auth_state as state  # noqa: E402

MAIN = "tests/_auth_main.py"

# Two polls, in retries of 0.1 s.
_POLL_RETRIES = int(table_view.POLL_SECONDS * 20) + 10


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


def _base(owner: int, name: str, **shape):
    character = Character(id="x", name=name, **({"caste": "dawn"} | shape))
    lifecycle.lock_chargen(character)
    return _characters().create(owner, character)


def _member(table, user_id: int, base_id: str | None = None):
    """Make `user_id` a member of `table` through the store. Return the copy or None."""
    tables = _tables()
    request = tables.request(user_id, table.join_code, base_id)
    return tables.approve(table.storyteller_id, request.id)


def _load(row) -> Character:
    return _characters().load(row)


def _one(user: User, marker: str):
    (element,) = user.find(marker=marker).elements
    return element


async def _campaign(create_user, *names: str):
    """An ST, and one player for each name in `names` who brings a base of that name.

    Return (st user, st id, table, [(player user, player id, copy row)]).
    """
    st = create_user()
    st_id = await _sign_up(st, "Harmonious")
    table = _tables().create(st_id, "The Scarlet Gambit")
    players = []
    for n, name in enumerate(names):
        player = create_user()
        player_id = await _sign_up(player, f"Player{n}")
        players.append((player, player_id, _member(table, player_id, _base(player_id, name).id)))
    return st, st_id, table, players


# --------------------------------------------------------------------------- #
# The layout
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_player_sees_you_play_the_others_the_board_and_two_tabs(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (player, _, mine), (_, _, theirs) = players

    await player.open(chrome.table_url(table.id))

    await player.should_see("PARTY (2)")
    await player.should_see(marker="you-name", content="Ashes of Dawn")
    await player.should_see(marker=f"other-{theirs.id}")
    await player.should_see("Gearheart")
    await player.should_see("Player1")
    await player.should_see(marker="table-board")
    await player.should_see(marker="tab-log")
    await player.should_see(marker="tab-notes")
    await player.should_not_see(marker="tab-st")
    await player.should_not_see(marker=f"other-{mine.id}")
    await player.should_not_see(table.join_code)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_has_the_st_tab_and_no_you_play(create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (_, _, copy), = players
    asker = create_user()
    _tables().request(await _sign_up(asker, "Asker"), table.join_code, None)

    await st.open(chrome.table_url(table.id))

    await st.should_see(marker="tab-st")
    await st.should_see(marker="table-code")
    await st.should_see(table.join_code)
    await st.should_see("REQUESTS (1)")
    await st.should_see(marker="table-requests-badge", content="1")
    await st.should_see(marker=f"other-{copy.id}")
    await st.should_not_see(marker="you-play")
    await st.should_not_see(marker="table-open-as")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_members_are_listed_with_the_storyteller_and_the_watchers(create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    watcher = create_user()
    _member(table, await _sign_up(watcher, "Watcher"))

    await watcher.open(chrome.table_url(table.id))

    await watcher.should_see(marker="table-members")
    await watcher.should_see("Harmonious · Storyteller")
    await watcher.should_see("Player0")
    await watcher.should_see("Watcher · watching")


# --------------------------------------------------------------------------- #
# YOU PLAY — the live controls (R2), through the live context
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_health_click_marks_the_object_that_the_character_page_holds(
        create_user) -> None:
    """⚠ Trap 15.5 row 1. The table page and `/character/<copy>` share one object.
    A write to the file behind an open page is lost at its next auto-save."""
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, copy), = players
    await player.open(chrome.character_url(copy.id))
    held = state.REGISTRY.peek(copy.id)["char"]

    await player.open(chrome.table_url(table.id))
    player.find(marker="you-health-0").click()

    await player.should_see(marker="you-health-0", content="/")
    assert state.REGISTRY.peek(copy.id)["char"] is held
    assert held.play.health[0] == Damage.BASHING
    assert _load(copy).play.health[0] == Damage.BASHING


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_health_click_with_no_character_page_open_is_saved(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, copy), = players
    await player.open(chrome.table_url(table.id))

    player.find(marker="you-health-1").click()
    player.find(marker="you-health-1").click()

    await player.should_see(marker="you-health-1", content="x")
    assert _load(copy).play.health[1] == Damage.LETHAL
    assert state.REGISTRY.peek(copy.id)["char"].play.health[1] == Damage.LETHAL


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_mote_bar_spends_and_regains(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, copy), = players
    await player.open(chrome.table_url(table.id))

    def spent() -> int:
        return _load(copy).play.motes_peripheral_spent

    player.find(marker="you-motes-peripheral-minus").click()
    await player.should_see(marker="you-motes-peripheral-left", content="19/20")
    assert spent() == 1

    player.find(marker="you-motes-peripheral-plus").click()
    await player.should_see(marker="you-motes-peripheral-left", content="20/20")
    assert spent() == 0

    _one(player, "you-motes-peripheral-amount").value = 7
    player.find(marker="you-motes-peripheral-spend").click()
    await player.should_see(marker="you-motes-peripheral-left", content="13/20")
    assert spent() == 7

    _one(player, "you-motes-peripheral-amount").value = 3
    player.find(marker="you-motes-peripheral-regain").click()
    await player.should_see(marker="you-motes-peripheral-left", content="16/20")
    assert spent() == 4

    player.find(marker="you-motes-peripheral-full").click()
    await player.should_see(marker="you-motes-peripheral-left", content="20/20")
    assert spent() == 0

    player.find(marker="you-motes-personal-minus").click()
    await player.should_see(marker="you-motes-personal-left", content="7/8")
    assert _load(copy).play.motes_personal_spent == 1


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_willpower_and_limit_tracks_click(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, copy), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="you-wp-label", content="2/2")

    # A click on the first box leaves no Willpower.
    player.find(marker="you-wp-0").click()
    await player.should_see(marker="you-wp-label", content="0/2")
    assert _load(copy).play.willpower_spent == 2

    player.find(marker="you-limit-2").click()
    await player.should_see(marker="you-limit-label", content="3/10")
    assert _load(copy).play.limit == 3


# --------------------------------------------------------------------------- #
# The others are read-only, for the Storyteller too (R3)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_cannot_mark_a_players_row(create_user) -> None:
    """⚠ Trap 15.5 row 2. No handler on a row that the viewer does not own. The ST
    page must also build no context for the character of another account."""
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (_, _, copy), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"other-health-{copy.id}-0")

    st.find(marker=f"other-health-{copy.id}-0").click()

    await st.should_see(marker=f"other-{copy.id}")
    assert _load(copy).play is None or not any(_load(copy).play.health)
    assert state.REGISTRY.peek(copy.id) is None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_player_cannot_mark_another_players_row(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (player, _, _), (_, _, theirs) = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker=f"other-health-{theirs.id}-0")

    player.find(marker=f"other-health-{theirs.id}-0").click()

    await player.should_see(marker="you-play")
    assert _load(theirs).play is None or not any(_load(theirs).play.health)
    assert state.REGISTRY.peek(theirs.id) is None


# --------------------------------------------------------------------------- #
# Open as, and Spectate
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_open_as_picks_the_character_and_is_remembered(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, player_id, first), = players
    second = _member(table, player_id, _base(player_id, "Second Sun").id)
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="you-name", content="Ashes of Dawn")
    await player.should_see(marker=f"other-{second.id}")

    _one(player, "table-open-as").value = second.id

    await player.should_see(marker="you-name", content="Second Sun")
    await player.should_see(marker=f"other-{first.id}")

    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="you-name", content="Second Sun")

    _one(player, "table-open-as").value = table_view.SPECTATE
    await player.should_see(marker=f"other-{second.id}")
    await player.should_not_see(marker="you-play")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_watcher_has_no_you_play_and_no_chooser(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (_, _, copy), = players
    watcher = create_user()
    _member(table, await _sign_up(watcher, "Watcher"))

    await watcher.open(chrome.table_url(table.id))

    await watcher.should_see(marker=f"other-{copy.id}")
    await watcher.should_not_see(marker="you-play")
    await watcher.should_not_see(marker="table-open-as")


# --------------------------------------------------------------------------- #
# The poll
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_poll_repaints_a_row_from_the_file(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (player, _, _), (_, _, theirs) = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker=f"other-health-{theirs.id}-0")

    character = _load(theirs)
    character.play = PlayState(health=[Damage.LETHAL])
    _characters().save(theirs, character)

    await player.should_see(marker=f"other-health-{theirs.id}-0", content="x",
                            retries=_POLL_RETRIES)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_poll_reads_an_open_context_before_the_file(create_user) -> None:
    """The owner's page holds changes that are not saved yet. The table shows them."""
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (_, _, copy), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"other-health-{copy.id}-0")

    live = state.REGISTRY.ctx_for(copy.id)["char"]
    engineplay.cycle_mark(live, 0, 7)

    await st.should_see(marker=f"other-health-{copy.id}-0", content="/",
                        retries=_POLL_RETRIES)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_poll_shows_a_new_character_and_request(create_user) -> None:
    st, st_id, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    newcomer_id = await _sign_up(create_user(), "Newcomer")
    await player.open(chrome.table_url(table.id))
    await st.open(chrome.table_url(table.id))
    await player.should_see("PARTY (1)")
    await st.should_see("REQUESTS (0)")

    request = _tables().request(newcomer_id, table.join_code,
                                _base(newcomer_id, "Late Arrival").id)
    await st.should_see("REQUESTS (1)", retries=_POLL_RETRIES)

    _tables().approve(st_id, request.id)
    await player.should_see("PARTY (2)", retries=_POLL_RETRIES)
    await player.should_see("Late Arrival")


# --------------------------------------------------------------------------- #
# No longer in this campaign
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_removed_member_sees_the_page_stop(create_user) -> None:
    _, st_id, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, player_id, _), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="you-play")

    _tables().remove(st_id, table.id, player_id)

    await player.should_see(marker="table-gone", retries=_POLL_RETRIES)
    await player.should_see("You are no longer in this campaign.")
    await player.should_not_see(marker="you-play")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_deleted_campaign_stops_the_storytellers_other_page(create_user) -> None:
    st, st_id, table, _ = await _campaign(create_user, "Ashes of Dawn")
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="tab-st")

    _tables().delete(st_id, table.id)

    await st.should_see(marker="table-gone", retries=_POLL_RETRIES)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_click_after_removal_changes_nothing(create_user) -> None:
    """⚠ The handler asks `access()` again. No await separates the removal and the
    click, thus the poll cannot run between them."""
    _, st_id, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, player_id, copy), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="you-health-0")

    _tables().remove(st_id, table.id, player_id)
    player.find(marker="you-health-0").click()

    # ⚠ Before any await: the poll draws the same words on the page.
    assert player.notify.contains(table_view.GONE)
    await player.should_see(marker="table-gone")
    assert _load(copy).play is None or not any(_load(copy).play.health)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_click_on_a_deleted_copy_changes_nothing(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, player_id, copy), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="you-health-0")

    _characters().delete(player_id, copy.id)
    player.find(marker="you-health-0").click()

    await player.should_see("That character is no longer in this campaign.")
    assert not _characters().path_for(copy).exists()


# --------------------------------------------------------------------------- #
# Shapes (preflight pass 3)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
@pytest.mark.parametrize("shape, sees, absent", [
    ({"exalt_type": "Mortal", "caste": "", "origin": "heroic", "essence_rating": 1},
     "you-limit-label", "you-motes-peripheral-left"),
    ({"exalt_type": "Alchemical", "caste": "orichalcum"},
     "you-clarity-label", "you-limit-label"),
    ({"exalt_type": "Sidereal", "caste": "journeys"}, "you-limit-label", None),
    ({"exalt_type": "Lunar", "caste": "full-moon"}, "you-motes-personal-left", None),
])
async def test_you_play_draws_each_shape(create_user, shape, sees, absent) -> None:
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Shapes")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    _member(table, player_id, _base(player_id, "Shaped", **shape).id)

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="you-name", content="Shaped")
    await player.should_see(marker=sees)
    if absent:
        await player.should_not_see(marker=absent)


_MORTAL = {"exalt_type": "Mortal", "caste": "", "origin": "heroic", "essence_rating": 2}


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
@pytest.mark.parametrize("merits, bars, absent, free", [
    # Essence Awareness: a Personal pool, one third of it free (PG p.114).
    (["thaum.essence-awareness"], {"personal": "7/7"}, "peripheral", True),
    (["mf.awakened-essence"], {"personal": "7/7"}, "peripheral", False),
    # Beacon of Power: one merged pool, drawn as the "All motes" bar.
    (["mf.awakened-essence", "mf.beacon-of-power"], {"peripheral": "7/7"},
     "personal", False),
    # Aura of Power: the pool divides into Personal and Peripheral.
    (["mf.awakened-essence", "mf.aura-of-power"],
     {"personal": "2/2", "peripheral": "5/5"}, None, False),
])
async def test_a_mortal_with_essence_merits_gets_the_bars_of_the_engine(
        create_user, merits, bars, absent, free) -> None:
    """A Mortal has no pool (PG p.114) until a Merit gives one. The bars follow the
    maxima of `build_play_view`; the page decides nothing."""
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Awakened")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    _member(table, player_id, _base(
        player_id, "Awakened", **_MORTAL,
        merits_flaws=[MeritFlawPurchase(merit_id=m) for m in merits]).id)

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="you-name", content="Awakened")
    for key, text in bars.items():
        await player.should_see(marker=f"you-motes-{key}-left", content=text)
    if absent:
        await player.should_not_see(marker=f"you-motes-{absent}-left")
    if free:
        await player.should_see(marker="you-motes-note",
                                content="may be spent freely")
    else:
        await player.should_not_see(marker="you-motes-note")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_limit_track_runs_to_the_derived_maximum(create_user) -> None:
    """Greater Curse lowers the maximum of Limit (p.40). The track reads
    `derive.limit_max`, never a constant 10, and names the Break at that maximum."""
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Cursed")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    copy = _member(table, player_id, _base(
        player_id, "Cursed", merits_flaws=[
            MeritFlawPurchase(merit_id="mf.greater-curse", tier="3")]).id)

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="you-limit-label", content="0/7")
    await player.should_see(marker="you-limit-6")
    await player.should_not_see(marker="you-limit-7")

    player.find(marker="you-limit-6").click()
    await player.should_see(marker="you-limit-label", content="BREAK")
    assert _load(copy).play.limit == 7


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_armour_fatigue_counts_up_and_down(create_user) -> None:
    """Accumulated armour fatigue (p.332) is a counter with no maximum. It shows for
    a character with armour, as on the Play tab."""
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, player_id, _), = players
    copy = _member(table, player_id, _base(player_id, "Armoured", armor=[
        Armor(name="Buff Jacket", soak_lethal=2, soak_bashing=3, fatigue=1)]).id)
    await player.open(chrome.table_url(table.id))
    _one(player, "table-open-as").value = copy.id
    await player.should_see(marker="you-fatigue-label", content="Fatigue 0")

    player.find(marker="you-fatigue-plus").click()
    await player.should_see(marker="you-fatigue-label", content="-1 to all actions")
    player.find(marker="you-fatigue-plus").click()
    assert _load(copy).play.fatigue == 2
    player.find(marker="you-fatigue-minus").click()
    await player.should_see(marker="you-fatigue-label", content="Fatigue 1")
    assert _load(copy).play.fatigue == 1


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_no_armour_and_no_fatigue_draws_no_counter(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="you-wp-label")
    await player.should_not_see(marker="you-fatigue-label")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_alchemical_sees_the_clarity_band(create_user) -> None:
    from pathlib import Path

    from exalted_builder import rules_db
    from exalted_builder.engine import derive
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Clear")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    copy = _member(table, player_id, _base(player_id, "Gear", exalt_type="Alchemical",
                                           caste="orichalcum").id)
    ruleset = rules_db.load_ruleset(Path(derive.__file__).resolve().parent.parent / "data")
    clarity = derive.clarity(ruleset, _load(copy))

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="you-clarity-label", content=f"band {clarity.band}")
    await player.should_see(marker="you-clarity-effects", content=clarity.effects[:30])


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_sidereal_track_is_named_paradox(create_user) -> None:
    st = create_user()
    table = _tables().create(await _sign_up(st, "Harmonious"), "Shapes")
    player = create_user()
    player_id = await _sign_up(player, "Radiant")
    _member(table, player_id, _base(player_id, "Shaped", exalt_type="Sidereal",
                                    caste="journeys").id)

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="you-limit-label", content="Paradox")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_unreadable_copy_does_not_break_the_page(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (player, _, mine), (_, _, theirs) = players
    _characters().path_for(mine).write_text("{not json")
    _characters().path_for(theirs).write_text("{not json")

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="you-play")
    await player.should_see(f"(unreadable: {mine.id})")
    await player.should_see(f"(unreadable: {theirs.id})")


# --------------------------------------------------------------------------- #
# The Log (step 4, section 15.3)
# --------------------------------------------------------------------------- #


def _log() -> table_log.TableLog:
    return table_log.TableLog(_tables())


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_message_reaches_the_other_members_by_the_poll(create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, player_id, _), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="log-send")
    await player.open(chrome.table_url(table.id))

    player.find(marker="log-text").type("The doors grind open.")
    player.find(marker="log-send").click()

    await player.should_see(marker="log-body-1", content="The doors grind open.")
    assert _one(player, "log-text").value == ""
    (entry,) = _log().entries(table.id)
    assert (entry.user_id, entry.text, entry.roll) == (player_id, "The doors grind open.",
                                                       None)
    await st.should_see(marker="log-body-1", content="The doors grind open.",
                        retries=_POLL_RETRIES)
    await st.should_see(marker="log-name-1", content="Player0")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_enter_in_the_text_box_sends(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await player.open(chrome.table_url(table.id))

    player.find(marker="log-text").type("Hello").trigger("keydown.enter")

    await player.should_see(marker="log-body-1", content="Hello")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_roll_takes_the_text_as_its_caption(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, player_id, _), = players
    await player.open(chrome.table_url(table.id))

    player.find(marker="log-text").type("I swing at the bandit")
    _one(player, "log-count").value = 8
    player.find(marker="log-roll").click()

    await player.should_see(marker="log-body-1", content="I swing at the bandit")
    (entry,) = _log().entries(table.id)
    assert entry.user_id == player_id and entry.text == "I swing at the bandit"
    assert entry.roll is not None and len(entry.roll.faces) == 8
    await player.should_see(marker="log-roll-1", content=f"8 dice → {entry.roll.summary}")
    assert _one(player, "log-text").value == ""
    # The count stays for the next roll.
    assert _one(player, "log-count").value == 8


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_roll_with_an_empty_box_has_no_caption(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await player.open(chrome.table_url(table.id))

    _one(player, "log-count").value = 3
    player.find(marker="log-roll").click()

    await player.should_see(marker="log-roll-1", content="3 dice →")
    (entry,) = _log().entries(table.id)
    assert entry.text == "" and entry.roll is not None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_count_out_of_range_writes_nothing(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="log-roll")

    _one(player, "log-count").value = 0
    player.find(marker="log-roll").click()

    await player.should_see("Type a number of dice from 1 to")
    assert _log().entries(table.id) == []


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_log_text_is_shown_as_text_not_markup(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await player.open(chrome.table_url(table.id))

    player.find(marker="log-text").type("<b>bold</b> <script>x()</script>")
    player.find(marker="log-send").click()

    await player.should_see("<b>bold</b> <script>x()</script>")
    for element in player.find("<b>bold</b>").elements:
        assert type(element) is ui.label


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_watcher_and_the_storyteller_can_post(create_user) -> None:
    st, st_id, table, _ = await _campaign(create_user)
    watcher = create_user()
    watcher_id = await _sign_up(watcher, "Watcher")
    _member(table, watcher_id)

    for n, (user, text) in enumerate(((watcher, "watching"), (st, "welcome")), 1):
        await user.open(chrome.table_url(table.id))
        user.find(marker="log-text").type(text)
        user.find(marker="log-send").click()
        await user.should_see(marker=f"log-body-{n}", content=text)

    assert [(e.user_id, e.text) for e in _log().entries(table.id)] == [
        (watcher_id, "watching"), (st_id, "welcome")]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_log_shows_older_entries_with_the_storyteller_starred(create_user) -> None:
    _, st_id, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    _log().post(st_id, table.id, "Three bandits look up.")

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="log-body-1", content="Three bandits look up.")
    await player.should_see(marker="log-name-1", content="Harmonious")
    await player.should_see(marker="log-star-1")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_post_after_removal_writes_nothing(create_user) -> None:
    _, st_id, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, player_id, _), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="log-send")

    _tables().remove(st_id, table.id, player_id)
    player.find(marker="log-text").type("still here?")
    player.find(marker="log-send").click()

    # ⚠ Before any await: the poll draws the same words on the page.
    assert player.notify.contains(table_view.GONE)
    await player.should_see(marker="table-gone")
    assert _log().entries(table.id) == []


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_poll_adds_new_entries_below_the_old(create_user) -> None:
    _, st_id, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="log-empty")

    _log().post(st_id, table.id, "first")
    await player.should_see(marker="log-body-1", content="first", retries=_POLL_RETRIES)
    await player.should_not_see(marker="log-empty")
    _log().roll(st_id, table.id, 1, "second")

    await player.should_see(marker="log-roll-2", content="1 die →", retries=_POLL_RETRIES)
    await player.should_see(marker="log-body-1", content="first")
    assert len(player.find(marker="log-body-1").elements) == 1


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_each_health_box_has_its_penalty_label(create_user) -> None:
    """The labels of the Play tab (`PlayHealthBox.label`), on YOU PLAY and on each
    row of THE OTHERS."""
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (player, _, _), (_, _, theirs) = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="you-play")

    expected = ["-0", "-1", "-1", "-2", "-2", "-4", "Incap"]
    for i, label in enumerate(expected):
        await player.should_see(marker=f"you-health-label-{i}", content=label)
        await player.should_see(marker=f"other-health-label-{theirs.id}-{i}", content=label)
    await player.should_not_see(marker=f"you-health-label-{len(expected)}")
