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
async def test_enter_sends_the_text_that_the_key_event_carries(create_user) -> None:
    """🐞 2026-09-25: Enter can reach the server before the last value update of the
    box. The key event carries `e.target.value`, and the page posts that."""
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await player.open(chrome.table_url(table.id))

    # The box is still empty on the server; the browser sent the text with Enter.
    player.find(marker="log-text").trigger("keydown.enter", "Typed fast")

    await player.should_see(marker="log-body-1", content="Typed fast")


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


# --------------------------------------------------------------------------- #
# Step 5 — the ST tools, and Leave
# --------------------------------------------------------------------------- #


def _grant(st: User, amount: int, note: str = "", leave_out: tuple[str, ...] = ()) -> None:
    """Fill the Grant XP form of the ST tab, untick each copy of `leave_out`, and
    press Grant."""
    _one(st, "st-grant-amount").set_value(amount)
    _one(st, "st-grant-note").set_value(note)
    for copy_id in leave_out:
        _one(st, f"st-grant-to-{copy_id}").set_value(False)
    st.find(marker="st-grant").click()


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_grant_reaches_the_object_that_the_players_page_holds(create_user) -> None:
    """⚠ Trap section 12, "XP grant written behind an open page". The player's page
    is open first, thus the registry holds the object that its auto-save writes."""
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (player, _, copy), (_, _, other) = players
    await player.open(chrome.character_url(copy.id))
    held = state.REGISTRY.peek(copy.id)["char"]

    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-grant-form")
    _grant(st, 5, "Session one")

    await st.should_see(marker="st-award-1")
    await st.should_see("+5 XP to Ashes of Dawn, Gearheart — Session one")
    assert state.REGISTRY.peek(copy.id)["char"] is held
    assert held.xp_earned == 5
    assert _load(copy).xp_earned == 5
    assert _load(other).xp_earned == 5
    assert state.REGISTRY.peek(other.id) is None, "A context was built for a grant."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_unticked_character_gets_no_xp(create_user) -> None:
    """Human, 2026-09-22: each character is ticked at the start, and the ST unticks
    whoever is left out — an absent player, or the ST's own character."""
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart",
                                            "Third")
    (_, _, copy), (_, _, other), (_, _, third) = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-grant-form")
    assert _one(st, f"st-grant-to-{copy.id}").value is True

    _grant(st, 3, leave_out=(copy.id,))

    await st.should_see("+3 XP to Gearheart, Third")
    assert _load(other).xp_earned == 3 and _load(third).xp_earned == 3
    assert _load(copy).xp_earned == 0


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_grant_with_no_character_ticked_writes_nothing(create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (_, _, copy), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-grant-form")

    _grant(st, 5, leave_out=(copy.id,))

    await st.should_see("Tick at least one character")
    assert _load(copy).xp_earned == 0
    assert not (_tables().table_dir(table.id) / "awards.json").exists()


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_character_that_joins_after_the_form_is_drawn_is_not_granted(
        create_user) -> None:
    """The grant names the ticked characters. A copy that arrives between the draw
    and the click is not in the list, thus it gets nothing it was not shown."""
    st, st_id, table, players = await _campaign(create_user, "Ashes of Dawn")
    (_, _, copy), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-grant-form")
    late = _tables().characters(table.id)
    newcomer = create_user()
    newcomer_id = await _sign_up(newcomer, "Newcomer")
    arrived = _member(table, newcomer_id, _base(newcomer_id, "Late").id)
    assert len(_tables().characters(table.id)) == len(late) + 1

    _grant(st, 2)

    await st.should_see("+2 XP to Ashes of Dawn")
    assert _load(copy).xp_earned == 2
    assert _load(arrived).xp_earned == 0


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_grant_of_zero_writes_nothing(create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (_, _, copy), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-grant-form")

    _grant(st, 0)

    await st.should_see("not 0")
    assert _load(copy).xp_earned == 0
    assert not (_tables().table_dir(table.id) / "awards.json").exists()


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_players_see_the_grant_in_the_log(create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="log-empty")
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-grant-form")

    _grant(st, 2, "Good roleplay")

    await player.should_see("+2 XP to Ashes of Dawn — Good roleplay",
                            retries=_POLL_RETRIES)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_grant_after_the_campaign_is_deleted_writes_nothing(create_user) -> None:
    """⚠ The handler asks `access()` again. No await separates the delete and the
    click, thus the poll cannot run between them."""
    st, st_id, table, players = await _campaign(create_user, "Ashes of Dawn")
    (_, _, copy), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-grant-form")

    _tables().delete(st_id, table.id)
    _grant(st, 5)

    assert st.notify.contains("You are not the Storyteller of this campaign.")
    assert _load(copy).xp_earned == 0


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_removes_a_member(create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, player_id, copy), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="you-play")
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"st-member-{player_id}")

    st.find(marker=f"st-remove-{player_id}").click()
    await st.should_see(marker="st-remove-confirm-body", content="solo")
    st.find(marker="st-remove-confirm").click()

    await st.should_see("PARTY (0)")
    assert _tables().access(player_id, table.id) is None
    assert _characters().row(copy.id).table_id is None
    await player.should_see(marker="table-gone", retries=_POLL_RETRIES)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_member_leaves_from_the_menu(create_user) -> None:
    _, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, player_id, copy), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="you-play")

    player.find(marker="table-leave").click()
    await player.should_see(marker="table-leave-confirm-body", content="solo")
    player.find(marker="table-leave-confirm").click()

    await player.should_see(marker="home-new")
    assert _tables().access(player_id, table.id) is None
    assert _characters().row(copy.id).table_id is None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_has_no_leave(create_user) -> None:
    st, _, table, _ = await _campaign(create_user)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="top-bar-logout")
    # Preflight pass 3: the ST tab of a campaign with no characters builds.
    await st.should_see(marker="st-grant-form")
    await st.should_see(marker="st-delete")
    await st.should_see("MEMBERS (0)")

    await st.should_not_see(marker="table-leave")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_new_code_replaces_the_code(create_user) -> None:
    st, _, table, _ = await _campaign(create_user)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-code-text", content=table.join_code)

    st.find(marker="st-new-code").click()
    st.find(marker="st-new-code-confirm").click()

    code = _tables().table(table.id).join_code
    assert code != table.join_code
    await st.should_see(marker="table-code-text", content=code)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_delete_names_the_member_count_and_deletes(create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (player, _, copy), _ = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="you-play")
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-delete")

    st.find(marker="st-delete").click()
    await st.should_see(marker="st-delete-confirm-body", content="It has 2 members.")
    st.find(marker="st-delete-confirm").click()

    await st.should_see(marker="home-new")
    assert _tables().table(table.id) is None
    assert _characters().row(copy.id).table_id is None
    await player.should_see(marker="table-gone", retries=_POLL_RETRIES)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_unlocks_a_copy_after_a_warning(create_user) -> None:
    """Q6: on a campaign copy, unlocking is up to the Storyteller. Ruled 2026-09-12:
    an Unlock after XP is allowed, with a warning."""
    from exalted_builder.models.character import XpEntry

    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, copy), = players
    character = _load(copy)
    character.xp_log.append(XpEntry(target="essence", from_rating=2, to_rating=3, cost=16))
    _characters().save(copy, character)
    await player.open(chrome.character_url(copy.id))
    held = state.REGISTRY.peek(copy.id)["char"]
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"st-copy-{copy.id}")

    st.find(marker=f"st-unlock-{copy.id}").click()
    await st.should_see(marker="st-unlock-confirm-body", content="16 XP")
    assert held.chargen_locked, "Unlocked before the confirm."
    st.find(marker="st-unlock-confirm").click()

    await st.should_see("unlocked")
    assert not held.chargen_locked
    assert not _load(copy).chargen_locked


# --------------------------------------------------------------------------- #
# Step 6: the house rules
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_table_switch_reaches_the_object_that_the_players_page_holds(
        create_user) -> None:
    """Site 2 of p3-tables.md section 5, through the page. ⚠ Trap section 12: the
    player's page is open first, thus its auto-save writes the held object."""
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (player, _, copy), (_, _, other) = players
    await player.open(chrome.character_url(copy.id))
    held = state.REGISTRY.peek(copy.id)["char"]
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-house-rules")

    _one(st, "st-rule-magic_for_everyone").set_value(True)

    await st.should_see("House rule: Magic for Everyone — On")
    assert state.REGISTRY.peek(copy.id)["char"] is held
    assert held.house_rules.magic_for_everyone is True
    assert _load(other).house_rules.magic_for_everyone is True
    assert _tables().house_rules(table.id).magic_for_everyone is True
    assert state.REGISTRY.peek(other.id) is None, "A context was built for a switch."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_table_select_rule_is_set(create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (_, _, copy), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-house-rules")

    _one(st, "st-rule-godblooded_inheritance_rating").set_value("3")

    await st.should_see("House rule: God-Blooded Inheritance rating — 3 ••• Notable ancestry")
    assert _load(copy).house_rules.godblooded_inheritance_rating == 3


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_grants_one_character_a_permission(create_user) -> None:
    """Q2: the Storyteller sets the PER-CHARACTER permissions, one copy at a time."""
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (player, _, copy), (_, _, other) = players
    await player.open(chrome.character_url(copy.id))
    held = state.REGISTRY.peek(copy.id)["char"]
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"st-copy-{copy.id}")

    st.find(marker=f"st-permissions-{copy.id}").click()
    await st.should_see(marker="st-permission-st_foreign_charms")
    await st.should_see("May start play knowing foreign Charms")
    assert not _marked_all(st, "st-permission-magic_for_everyone")
    _one(st, "st-permission-st_foreign_charms").set_value(True)

    await st.should_see("Ashes of Dawn: May start play knowing foreign Charms — On")
    assert held.house_rules.st_foreign_charms is True
    assert _load(copy).house_rules.st_foreign_charms is True
    rules = _load(other).house_rules
    assert rules is None or rules.st_foreign_charms is False


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_player_has_no_house_rule_controls(create_user) -> None:
    """The ST tab is not built for a player. The store refuses them as well
    (`tests/test_table_rules.py`)."""
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, copy), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="table-members")

    assert not _marked_all(player, "st-house-rules")
    assert not _marked_all(player, "st-rule-magic_for_everyone")
    assert not _marked_all(player, f"st-permissions-{copy.id}")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_switch_after_the_campaign_is_deleted_writes_nothing(create_user) -> None:
    """The handler asks for the role again."""
    st, st_id, table, players = await _campaign(create_user, "Ashes of Dawn")
    (_, _, copy), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-house-rules")
    control = _one(st, "st-rule-magic_for_everyone")
    _tables().delete(st_id, table.id)

    control.set_value(True)

    rules = _load(copy).house_rules
    assert rules is None or not rules.magic_for_everyone


def _marked_all(user: User, marker: str) -> list:
    """Each element with `marker`, hidden or not. `user.find` skips hidden ones."""
    return [e for e in user.client.elements.values()
            if marker in getattr(e, "_markers", [])]


# --------------------------------------------------------------------------- #
# Step 6b: adding a character from the campaign
# --------------------------------------------------------------------------- #


async def _watcher(create_user, table):
    """A member of `table` who watches. Return (user, id)."""
    watcher = create_user()
    watcher_id = await _sign_up(watcher, "Watcher")
    _member(table, watcher_id)
    return watcher, watcher_id


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_watcher_brings_a_base_from_the_campaign(create_user) -> None:
    st, st_id, table, _ = await _campaign(create_user)
    watcher, watcher_id = await _watcher(create_user, table)
    base = _base(watcher_id, "Late Arrival")
    await watcher.open(chrome.table_url(table.id))

    watcher.find(marker="table-add-character").click()
    await watcher.should_see(marker="add-character-base")
    _one(watcher, "add-character-base").set_value(base.id)
    watcher.find(marker="add-character-send").click()

    await watcher.should_see("Request sent")
    (request,) = _tables().pending(st_id, table.id)
    assert (request.user_id, request.base_id) == (watcher_id, base.id)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_member_creates_a_character_for_the_campaign(create_user) -> None:
    st, st_id, table, _ = await _campaign(create_user)
    watcher, watcher_id = await _watcher(create_user, table)
    await watcher.open(chrome.table_url(table.id))

    watcher.find(marker="table-add-character").click()
    await watcher.should_see(marker="add-character-create")
    watcher.find(marker="add-character-create").click()

    await watcher.should_see(marker="draft-for-campaign")
    (draft,) = _tables().drafts(table.id)
    assert draft.owner_id == watcher_id


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_sees_a_draft_and_grants_it_a_permission(create_user) -> None:
    st, st_id, table, _ = await _campaign(create_user)
    watcher, watcher_id = await _watcher(create_user, table)
    draft = _tables().start_draft(watcher_id, table.id)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"st-draft-{draft.id}")
    assert not _marked_all(st, f"st-unlock-{draft.id}")

    st.find(marker=f"st-permissions-{draft.id}").click()
    await st.should_see(marker="st-permission-st_foreign_charms")
    _one(st, "st-permission-st_foreign_charms").set_value(True)

    await st.should_see("May start play knowing foreign Charms — On")
    assert _load(draft).house_rules.st_foreign_charms is True


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storytellers_own_character_joins_at_once(create_user) -> None:
    """Human, 2026-09-22: the Storyteller does not approve their own request."""
    st, st_id, table, _ = await _campaign(create_user)
    base = _base(st_id, "Gamemaster's Own")
    await st.open(chrome.table_url(table.id))

    st.find(marker="table-add-character").click()
    await st.should_see(marker="add-character-base")
    _one(st, "add-character-base").set_value(base.id)
    st.find(marker="add-character-send").click()

    await st.should_see("Added to the campaign.")
    assert _tables().pending(st_id, table.id) == []
    (copy,) = _tables().characters(table.id)
    assert copy.owner_id == st_id
    # The Storyteller view: the NPC is in ENEMIES, with its live controls.
    await st.should_see(marker=f"npc-{copy.id}-play", retries=_POLL_RETRIES)


# --------------------------------------------------------------------------- #
# The Storyteller's own characters are NPCs (human, 2026-09-22)
# --------------------------------------------------------------------------- #


async def _with_npc(create_user):
    """A campaign with one player, and a character of the Storyteller in it."""
    st, st_id, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, copy), = players
    _tables().bring(st_id, table.id, _base(st_id, "Gamemaster's Own").id)
    (npc,) = [r for r in _tables().characters(table.id) if r.owner_id == st_id]
    return st, table, player, copy, npc


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_player_gets_nothing_of_an_npc_with_no_side(create_user) -> None:
    """Step 8: an NPC with no side is an enemy. It reaches the page of a player as
    nothing at all, not as a hidden element."""
    st, table, player, copy, npc = await _with_npc(create_user)
    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="you-play")
    await player.should_see("PARTY (1)")
    assert "Gamemaster's Own" not in _page_text(player)
    assert not _marked_all(player, f"npc-badge-{npc.id}")
    assert not _marked_all(player, f"other-{npc.id}")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_sees_the_badge_in_you_play_and_the_st_tab(
        create_user) -> None:
    st, table, player, copy, npc = await _with_npc(create_user)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-open-as")
    _one(st, "table-open-as").set_value(npc.id)

    await st.should_see(marker="npc-badge-you")
    assert _marked_all(st, f"npc-badge-{npc.id}")
    assert not _marked_all(st, f"npc-badge-{copy.id}")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_npc_starts_unticked_in_grant_xp(create_user) -> None:
    st, table, player, copy, npc = await _with_npc(create_user)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-grant-form")

    assert _one(st, f"st-grant-to-{npc.id}").value is False
    assert _one(st, f"st-grant-to-{copy.id}").value is True
    _grant(st, 4)

    await st.should_see("+4 XP to Ashes of Dawn")
    assert _load(npc).xp_earned == 0
    assert _load(copy).xp_earned == 4


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_badge_is_keyed_on_the_owner_not_the_name(create_user) -> None:
    """A player's character named like an NPC is not one."""
    st, st_id, table, players = await _campaign(create_user, "NPC Gamemaster's Own")
    (player, _, copy), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"st-copy-{copy.id}")
    assert not _marked_all(st, f"npc-badge-{copy.id}")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_request_card_warns_of_different_house_rules(create_user) -> None:
    """Human, 2026-09-22: "ST house rules are different on this character". The
    base was priced under the rules frozen at its lock; the table's rules reach
    it only if the Storyteller unlocks the copy."""
    from exalted_builder.models.character import HouseRules

    st, st_id, table, _ = await _campaign(create_user)
    _tables().write_house_rules(table.id, HouseRules(magic_for_everyone=True))
    watcher, watcher_id = await _watcher(create_user, table)
    differs = _tables().bring(watcher_id, table.id, _base(watcher_id, "Differs").id)
    agrees = _tables().bring(watcher_id, table.id, _base(
        watcher_id, "Agrees", house_rules=HouseRules(magic_for_everyone=True)).id)
    await st.open(chrome.table_url(table.id))

    await st.should_see(marker=f"table-request-rules-{differs.id}",
                        content="ST house rules are different on this character")
    await st.should_see("Magic for Everyone: Off (campaign: On)")
    assert not _marked_all(st, f"table-request-rules-{agrees.id}")


# --------------------------------------------------------------------------- #
# Step 8: the roster on the table, the NPC sides and the notes
# --------------------------------------------------------------------------- #


async def _eventually(check) -> None:
    """Wait up to two polls for `check()` to be True."""
    import asyncio
    for _ in range(_POLL_RETRIES):
        if check():
            return
        await asyncio.sleep(0.1)
    assert check()


def _page_text(user: User) -> str:
    """Each text, value and prop of each element of the page of `user`, hidden or
    not: what the browser gets."""
    parts = []
    for element in user.client.elements.values():
        parts.append(str(getattr(element, "text", "") or ""))
        parts.append(str(getattr(element, "value", "") or ""))
        parts.append(" ".join(str(v) for v in element._props.values()))
    return "\n".join(parts)


async def _add_entry(st: User, side: str, template_id: str) -> str:
    """Add the catalogue template `template_id` on `side` through the page of the
    Storyteller. Return the id of the new entry."""
    before = {m for e in st.client.elements.values() for m in e._markers
              if m.startswith("adv-card-")}
    st.find(marker=f"table-add-{side}").click()
    await st.should_see(marker=f"adv-tpl-{template_id}")
    st.find(marker=f"adv-tpl-{template_id}").click()
    for _ in range(50):
        after = {m for e in st.client.elements.values() for m in e._markers
                 if m.startswith("adv-card-")}
        if after - before:
            (new,) = after - before
            return new.removeprefix("adv-card-")
        await st.should_see(marker=f"table-{side}")
    raise AssertionError("no entry was added")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_player_sees_an_ally_as_a_name_and_health_and_no_enemy(create_user) -> None:
    """R4 and R7. ⚠ The walk covers each element, hidden or not."""
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-enemy")
    enemy = await _add_entry(st, "enemy", "adv.heretic")
    ally = await _add_entry(st, "ally", "adv.bandit")
    await st.should_see(marker=f"adv-side-{ally}")

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker=f"ally-{ally}")
    await player.should_see("ALLIES (1)")
    text = _page_text(player)
    assert "Bandit" in text
    assert "Heretic" not in text
    # The stats of the ally stay with the Storyteller. ⚠ "Larceny 1" is the trait
    # line of the Bandit. A bare "Larceny" is also an option of the Ability select of
    # the player's own Pools tab (2026-09-25), which is not a leak.
    for stat in ("Init 6", "Short Sword", "buff jacket", "Soak", "Larceny 1"):
        assert stat not in text, stat
    assert not _marked_all(player, f"adv-card-{ally}")
    assert not _marked_all(player, f"adv-card-{enemy}")
    assert not _marked_all(player, "table-enemy")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_sees_both_sides_with_full_cards_and_switches(
        create_user) -> None:
    st, _, table, _ = await _campaign(create_user, "Ashes of Dawn")
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-enemy")
    enemy = await _add_entry(st, "enemy", "adv.heretic")

    await st.should_see("ENEMIES (1)")
    await st.should_see(marker=f"adv-card-{enemy}")
    assert _one(st, f"adv-side-{enemy}").value == "enemy"
    await st.should_see("ALLIES (0)")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_switch_moves_an_entry_and_the_player_sees_it_at_the_poll(
        create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-enemy")
    entry = await _add_entry(st, "enemy", "adv.heretic")
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="table-board")
    assert "Heretic" not in _page_text(player)

    _one(st, f"adv-side-{entry}").set_value("ally")

    await st.should_see("ALLIES (1)")
    await player.should_see(marker=f"ally-{entry}", retries=_POLL_RETRIES)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_mark_on_an_ally_reaches_the_player_at_the_poll(create_user) -> None:
    """R8: the Storyteller marks the ally. The player sees the mark."""
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-ally")
    entry = await _add_entry(st, "ally", "adv.bandit")
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker=f"ally-health-{entry}-0")
    assert _one(player, f"ally-health-{entry}-0").text == ""

    st.find(marker=f"adv-health-{entry}-0").click()

    await _eventually(lambda: _one(player, f"ally-health-{entry}-0").text == "/")
    # The ally row has no handler: a player cannot mark it.
    assert not _one(player, f"ally-health-{entry}-0")._event_listeners


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_roster_is_saved_in_the_table_folder(create_user) -> None:
    st, _, table, _ = await _campaign(create_user, "Ashes of Dawn")
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-ally")
    await _add_entry(st, "ally", "adv.bandit")

    import json as _json
    saved = _json.loads((_tables().table_dir(table.id) / "adversaries.json").read_text())
    assert [(a["name"], a["side"]) for a in saved] == [("Bandit", "ally")]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_edit_dialog_survives_a_repaint_of_the_roster(create_user) -> None:
    """The poll clears ALLIES and ENEMIES. A dialog in them would be deleted."""
    st, table, player, copy, npc = await _with_npc(create_user)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-enemy")
    entry = await _add_entry(st, "enemy", "adv.heretic")
    _one(st, "table-open-as").set_value(table_view.SPECTATE)
    await st.should_see(marker=f"npc-side-{npc.id}")
    st.find(marker=f"adv-toggle-{entry}").click()
    await st.should_see(marker=f"adv-edit-{entry}")
    st.find(marker=f"adv-edit-{entry}").click()
    await st.should_see("Edit adversary")

    # A second device of the Storyteller moves the NPC: the poll repaints.
    _tables().set_npc_side(table.storyteller_id, table.id, npc.id, "ally")
    await _eventually(lambda: _one(st, f"npc-side-{npc.id}").value == "ally")

    assert any(getattr(e, "text", "") == "Edit adversary"
               for e in st.client.elements.values())


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_ally_npc_reaches_a_player_as_a_name_and_health_only(create_user) -> None:
    st, table, player, copy, npc = await _with_npc(create_user)
    _tables().set_npc_side(table.storyteller_id, table.id, npc.id, "ally")

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker=f"ally-{npc.id}")
    assert _marked_all(player, f"ally-health-{npc.id}-0")
    assert not _marked_all(player, f"other-{npc.id}")
    assert not _marked_all(player, f"npc-badge-{npc.id}")
    # Nothing of the row of THE OTHERS: the identity line, the motes, the Willpower.
    ally = _one(player, f"ally-{npc.id}")
    texts = [getattr(e, "text", "") for e in ally.descendants()]
    assert not any(t.startswith(("WP ", "Motes ")) or "Dawn" in t for t in texts), texts


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_files_an_npc_by_side_and_switches_it(create_user) -> None:
    st, table, player, copy, npc = await _with_npc(create_user)
    # Open as the player character of nobody: the Storyteller spectates.
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-enemy")
    _one(st, "table-open-as").set_value(table_view.SPECTATE)
    await st.should_see(marker=f"npc-side-{npc.id}")
    assert any(f"npc-{npc.id}-play" in e._markers
               for e in _one(st, "table-enemy").descendants())

    _one(st, f"npc-side-{npc.id}").set_value("ally")

    await st.should_see("ALLIES (1)")
    assert _tables().npc_side(table.id, npc.id) == "ally"
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker=f"ally-{npc.id}")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_picks_the_side_when_adding_an_npc(create_user) -> None:
    """Human, 2026-09-24: "Switch when adding an NPC." """
    st, st_id, table, _ = await _campaign(create_user, "Ashes of Dawn")
    _base(st_id, "Friendly Sage")
    await st.open(chrome.table_url(table.id))
    st.find(marker="table-add-character").click()
    await st.should_see(marker="add-character-side")
    assert _one(st, "add-character-side").value == "enemy"

    _one(st, "add-character-side").set_value("ally")
    st.find(marker="add-character-send").click()

    await st.should_see("ALLIES (1)")
    (npc,) = [r for r in _tables().characters(table.id) if r.owner_id == st_id]
    assert _tables().npc_side(table.id, npc.id) == "ally"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_player_has_no_side_switch_when_adding(create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, player_id, _), = players
    _base(player_id, "Second")
    await player.open(chrome.table_url(table.id))
    player.find(marker="table-add-character").click()
    await player.should_see(marker="add-character-send")
    assert not _marked_all(player, "add-character-side")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_notes_are_kept_and_private(create_user) -> None:
    """Q8 and Q9: each member writes their own notes. The Storyteller does not read
    a player's notes."""
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="table-notes-text")
    _one(player, "table-notes-text").set_value("The sage lies.")

    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="table-notes-text")
    assert _one(player, "table-notes-text").value == "The sage lies."

    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-notes-text")
    assert _one(st, "table-notes-text").value == ""
    assert "The sage lies." not in _page_text(st)


# --------------------------------------------------------------------------- #
# Step 8 click-through: the Storyteller view, the compact cards (2026-09-24)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_opens_in_the_storyteller_view(create_user) -> None:
    """Human, 2026-09-24: "there's no way to 'view as ST'". The first choice of Open
    as is Storyteller, and it is the default. No NPC is in YOU PLAY."""
    st, table, player, copy, npc = await _with_npc(create_user)
    await st.open(chrome.table_url(table.id))

    await st.should_see(marker=f"npc-side-{npc.id}")
    select = _one(st, "table-open-as")
    assert select.value == table_view.SPECTATE
    assert list(select.options.values())[0] == "Storyteller"
    assert "Spectate" not in select.options.values()
    assert not _marked_all(st, "you-play")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_marks_an_npc_from_its_side(create_user) -> None:
    """The NPC rows of the Storyteller view have live controls, through the
    character registry, as YOU PLAY has."""
    st, table, player, copy, npc = await _with_npc(create_user)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"npc-{npc.id}-health-0")

    st.find(marker=f"npc-{npc.id}-health-0").click()

    await _eventually(lambda: _one(st, f"npc-{npc.id}-health-0").text != "")
    live = state.REGISTRY.peek(npc.id)["char"]
    assert live.play is not None and live.play.health[0] is not None
    assert _load(npc).play.health[0] is not None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_npc_row_is_compact_until_expanded(create_user) -> None:
    st, table, player, copy, npc = await _with_npc(create_user)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker=f"npc-{npc.id}-line")
    assert not _marked_all(st, f"npc-{npc.id}-wp-0")

    st.find(marker=f"npc-toggle-{npc.id}").click()

    await st.should_see(marker=f"npc-{npc.id}-wp-0")
    assert not _marked_all(st, f"npc-{npc.id}-line")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_roster_card_is_compact_until_expanded(create_user) -> None:
    st, _, table, _ = await _campaign(create_user, "Ashes of Dawn")
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-enemy")
    entry = await _add_entry(st, "enemy", "adv.bandit")
    await st.should_see(marker=f"adv-line-{entry}")
    assert "Short Sword" not in _page_text(st)
    assert not _marked_all(st, f"adv-edit-{entry}")
    # The health boxes stay live in a compact card.
    assert _marked_all(st, f"adv-health-{entry}-0")

    st.find(marker=f"adv-toggle-{entry}").click()

    await st.should_see(marker=f"adv-edit-{entry}")
    assert "Short Sword" in _page_text(st)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_roster_dialogs_have_the_colours_of_the_page(create_user) -> None:
    st, _, table, _ = await _campaign(create_user, "Ashes of Dawn")
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-enemy")
    solid = table_view.theme.palette(None).card_solid.split()

    st.find(marker="table-add-enemy").click()
    await st.should_see(marker="adv-add-blank")
    cards = [e for e in st.client.elements.values()
             if type(e).__name__ == "Card" and any(
                 "adv-add-blank" in d._markers for d in e.descendants())]
    assert cards and all(c in cards[0].classes for c in solid)


# --------------------------------------------------------------------------- #
# Step 9: initiative for the whole table (sections 9 and 15.4)
# --------------------------------------------------------------------------- #


def _log_rows(user: User, entry_id: int) -> list[str]:
    """The names of the turn order of the initiative entry `entry_id`, in order."""
    names = []
    for i in range(50):
        found = _marked_all(user, f"log-init-name-{entry_id}-{i}")
        if not found:
            break
        (element,) = found
        names.append(element.text)
    return names


async def _roll_initiative(st: User) -> int:
    """Open the dialog of the Storyteller and press Roll. Return the Log entry id."""
    st.find(marker="st-roll-initiative").click()
    await st.should_see(marker="init-roll")
    st.find(marker="init-roll").click()
    await _eventually(lambda: bool(st.find(marker="log-list").elements)
                      and any(m.startswith("log-initiative-")
                              for e in st.client.elements.values() for m in e._markers))
    ids = [int(m.removeprefix("log-initiative-")) for e in st.client.elements.values()
           for m in e._markers if m.startswith("log-initiative-")]
    return max(ids)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_weapon_in_hand_is_set_on_you_play_through_the_live_context(
        create_user) -> None:
    """⚠ Trap 15.5 row 1: the change goes to the object of the character page."""
    from exalted_builder.models.character import Weapon
    st = create_user()
    st_id = await _sign_up(st, "Harmonious")
    table = _tables().create(st_id, "The Scarlet Gambit")
    player = create_user()
    player_id = await _sign_up(player, "Player0")
    character = Character(id="x", name="Ashes", caste="dawn",
                          weapons=[Weapon(name="Daiklave", speed=3)])
    lifecycle.lock_chargen(character)
    copy = _member(table, player_id, _characters().create(player_id, character).id)
    await player.open(chrome.character_url(copy.id))
    held = state.REGISTRY.peek(copy.id)["char"]

    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="you-in-hand")
    unarmed = _one(player, "you-init").text
    _one(player, "you-in-hand").set_value("Daiklave")

    await _eventually(lambda: _one(player, "you-init").text != unarmed)
    assert held.play.in_hand == "Daiklave"
    assert _load(copy).play.in_hand == "Daiklave"
    assert int(_one(player, "you-init").text.split()[1]) == \
        int(unarmed.split()[1]) + 3
    assert state.REGISTRY.peek(copy.id)["char"] is held


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_rolls_initiative_and_each_member_sees_it_in_the_log(
        create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (player, _, _), _ = players
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="tab-log")
    await player.should_not_see(marker="st-roll-initiative")

    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-roll-initiative")
    entry = await _roll_initiative(st)

    assert sorted(_log_rows(st, entry)) == ["Ashes of Dawn", "Gearheart"]
    await player.should_see(marker=f"log-initiative-{entry}", retries=_POLL_RETRIES)
    assert sorted(_log_rows(player, entry)) == ["Ashes of Dawn", "Gearheart"]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_unticked_character_does_not_roll_and_stays_unticked(create_user) -> None:
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (_, _, ashes), (_, _, gear) = players
    await st.open(chrome.table_url(table.id))
    st.find(marker="st-roll-initiative").click()
    await st.should_see(marker="init-roll")
    assert _one(st, f"init-tick-char-{gear.id}").value is True
    _one(st, f"init-tick-char-{gear.id}").set_value(False)
    st.find(marker="init-roll").click()
    await _eventually(lambda: any(m.startswith("log-initiative-")
                                  for e in st.client.elements.values() for m in e._markers))
    (entry,) = [int(m.removeprefix("log-initiative-")) for e in st.client.elements.values()
                for m in e._markers if m.startswith("log-initiative-")]
    assert _log_rows(st, entry) == ["Ashes of Dawn"]

    st.find(marker="st-roll-initiative").click()
    await st.should_see(marker="init-roll")
    assert _one(st, f"init-tick-char-{gear.id}").value is False
    assert _one(st, f"init-tick-char-{ashes.id}").value is True


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_enemy_npc_is_named_to_a_player_with_no_breakdown(
        create_user) -> None:
    """Each combatant is named in the turn order (human, 2026-09-25).
    ⚠ The walk covers each element of the page of the player, hidden or not."""
    st, st_id, table, players = await _campaign(create_user, "Ashes of Dawn")
    (player, _, _), = players
    _tables().bring(st_id, table.id, _base(st_id, "The Bandit Lord").id, side="enemy")
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-enemy")
    await _add_entry(st, "enemy", "adv.heretic")
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="tab-log")

    entry = await _roll_initiative(st)

    assert sorted(_log_rows(st, entry)) == ["Ashes of Dawn", "Heretic", "The Bandit Lord"]
    await player.should_see(marker=f"log-initiative-{entry}", retries=_POLL_RETRIES)
    assert sorted(_log_rows(player, entry)) == ["Ashes of Dawn", "Heretic", "The Bandit Lord"]
    # The rating and the d10 of an enemy stay with the Storyteller. The party's show.
    import re
    arithmetic = re.compile(r"^-?\d+ \+ \d+$")
    for user, shown in ((player, {"Ashes of Dawn"}),
                        (st, {"Ashes of Dawn", "Heretic", "The Bandit Lord"})):
        for i, name in enumerate(_log_rows(user, entry)):
            (row,) = _marked_all(user, f"log-init-{entry}-{i}")
            texts = [c.text for c in row.descendants() if hasattr(c, "text")]
            assert any(arithmetic.match(t or "") for t in texts) == (name in shown), name


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_types_a_bonus_and_ticks_first_for_one_roll(
        create_user) -> None:
    """Human, 2026-09-25: a Charm bonus and a "me first" Charm are the Storyteller's,
    in the dialog, for this roll only. A player sees "first", not the bonus of an
    enemy."""
    st, _, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    (player, _, _), (_, _, gear) = players
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="table-enemy")
    await _add_entry(st, "enemy", "adv.heretic")
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="tab-log")

    st.find(marker="st-roll-initiative").click()
    await st.should_see(marker="init-roll")
    # The one roster entry.
    (heretic,) = {m.removeprefix("init-bonus-") for e in st.client.elements.values()
                  for m in e._markers if m.startswith("init-bonus-adv-")}
    _one(st, f"init-first-char-{gear.id}").set_value(True)
    _one(st, f"init-bonus-{heretic}").set_value(4)
    st.find(marker="init-roll").click()
    await _eventually(lambda: any(m.startswith("log-initiative-")
                                  for e in st.client.elements.values() for m in e._markers))
    (entry,) = [int(m.removeprefix("log-initiative-")) for e in st.client.elements.values()
                for m in e._markers if m.startswith("log-initiative-")]

    assert _log_rows(st, entry)[0] == "Gearheart"
    (line,) = [ln for ln in _log().entries(table.id)[-1].initiative if ln.name == "Heretic"]
    assert line.bonus == 4
    await player.should_see(marker=f"log-initiative-{entry}", retries=_POLL_RETRIES)
    assert _log_rows(player, entry)[0] == "Gearheart"
    assert _marked_all(player, f"log-init-first-{entry}-0")
    # The bonus of an enemy is its arithmetic: for the Storyteller only.
    assert f"{line.rating} +4 + {line.d10}" in _page_text(st)
    assert "+4 +" not in _page_text(player)

    # For this roll only.
    st.find(marker="st-roll-initiative").click()
    await st.should_see(marker="init-roll")
    assert _one(st, f"init-first-char-{gear.id}").value is False
    assert not _one(st, f"init-bonus-{heretic}").value
