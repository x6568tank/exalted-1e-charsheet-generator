"""The Pools tab of the table view: `server/table_view.py`.

The human asked on 2026-09-25 for the base dice pools at the table, as a third tab
beside Log and Notes, and ruled the same day which characters the Storyteller picks
from: the Storyteller's full-sheet NPCs and each player's character. A player sees the
pools of the copy that they open as, and nothing of any other character.

The tab lays out `ui/play.dice_pool_sidebar` and `custom_pool_panel`. It computes
nothing (decision 0016), and no row rolls itself (decision 0019).

PRODUCTION wiring: `tests/_auth_main.py`.
"""

from __future__ import annotations

import pytest

pytest.importorskip("bcrypt")

from exalted_builder.server import chrome  # noqa: E402

from .test_table_view import (MAIN, _POLL_RETRIES, _base, _campaign, _member,  # noqa: E402
                              _one, _sign_up, _tables)


async def _with_npc(create_user):
    """A campaign with two players, and a full-sheet NPC of the Storyteller."""
    st, st_id, table, players = await _campaign(create_user, "Ashes of Dawn", "Gearheart")
    _tables().bring(st_id, table.id, _base(st_id, "Gamemaster's Own").id)
    (npc,) = [r for r in _tables().characters(table.id) if r.owner_id == st_id]
    return st, table, players, npc


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_player_sees_the_pools_of_the_copy_they_open_as(create_user) -> None:
    _, _, table, [(player, _, _), _other] = await _campaign(
        create_user, "Ashes of Dawn", "Gearheart")

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="tab-pools")
    await player.should_see(marker="pools-name", content="Ashes of Dawn")
    await player.should_see("Dodge")
    await player.should_see("DICE POOLS")
    await player.should_see("no row rolls itself")
    await player.should_not_see(marker="pools-pick")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_player_gets_no_pools_of_anyone_else(create_user) -> None:
    """The ruling: the player's own copy only. The NPC and the other player are not
    in the page, not even as a hidden option."""
    st, table, [(player, _, _), _other], npc = await _with_npc(create_user)

    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="pools-name", content="Ashes of Dawn")

    names = [e.text for e in player.find(marker="pools-name").elements]
    assert names == ["Ashes of Dawn"]
    assert not list(_marked(player, "pools-pick"))


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_picks_an_npc_or_a_player(create_user) -> None:
    st, table, [(_, _, ashes), (_, _, gear)], npc = await _with_npc(create_user)

    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="pools-pick")

    pick = _one(st, "pools-pick")
    assert set(pick.options) == {npc.id, ashes.id, gear.id}

    pick.set_value(gear.id)
    await st.should_see(marker="pools-name", content="Gearheart")
    pick = _one(st, "pools-pick")
    pick.set_value(npc.id)
    await st.should_see(marker="pools-name", content="Gamemaster's Own")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_wound_on_the_table_moves_the_pools(create_user) -> None:
    """The tab reads the same live character that YOU PLAY marks."""
    _, _, table, [(player, _, _)] = await _campaign(create_user, "Ashes of Dawn")
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="pools-name", content="Ashes of Dawn")

    player.find(marker="you-health-0").click()
    player.find(marker="you-health-1").click()

    await player.should_see("Wound penalty (-1)", retries=_POLL_RETRIES)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_sees_a_player_wound_at_the_next_poll(create_user) -> None:
    st, table, [(player, _, ashes), _other], _npc = await _with_npc(create_user)
    await st.open(chrome.table_url(table.id))
    _one(st, "pools-pick").set_value(ashes.id)
    await st.should_see(marker="pools-name", content="Ashes of Dawn")
    await player.open(chrome.table_url(table.id))

    player.find(marker="you-health-0").click()
    player.find(marker="you-health-1").click()

    await st.should_see("Wound penalty (-1)", retries=_POLL_RETRIES)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_member_with_no_character_is_told_so(create_user) -> None:
    _, _, table, _ = await _campaign(create_user)
    watcher = create_user()
    _member(table, await _sign_up(watcher, "Watcher"))

    await watcher.open(chrome.table_url(table.id))

    await watcher.should_see(marker="pools-empty")


def _marked(user, marker: str):
    return user.find(marker=marker).elements if _exists(user, marker) else []


def _exists(user, marker: str) -> bool:
    try:
        user.find(marker=marker).elements
    except AssertionError:
        return False
    return True
