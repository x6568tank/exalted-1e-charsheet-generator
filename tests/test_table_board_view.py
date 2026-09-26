"""The board on the table view: `server/table_board_view.py`.

Steps 2 and 3 of the build order in `docs/plans/p4-board.md` section 6. The session
takes the intents of the canvas, writes them through `TableBoard`, and the hub
gives each change to each open page of the table.

The session tests use fake pages: `deliver` records each message. The page tests
use PRODUCTION wiring (`tests/_auth_main.py`). ⚠ The User harness runs no
JavaScript, thus the canvas is out of reach here. The click-through covers it.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character
from exalted_builder.server import db
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.table_board import TableBoard
from exalted_builder.server.table_board_view import (BoardHub, BoardSession,
                                                     board_head_html)
from exalted_builder.server.tables import TableStore

ST, PLAYER, WATCHER, STRANGER = 1, 2, 3, 4


@pytest.fixture
def tables(tmp_path: Path) -> TableStore:
    path = tmp_path / "accounts" / "exalted.db"
    db.init_db(path)
    with db.connect(path) as connection:
        connection.executemany(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'x')",
            [(ST, "storyteller"), (PLAYER, "player"), (WATCHER, "watcher"),
             (STRANGER, "stranger")])
    return TableStore(db_path=path, root=tmp_path / "sessions")


@pytest.fixture
def table(tables: TableStore):
    table = tables.create(ST, "The Scarlet Gambit")
    characters = CharacterStore(db_path=tables.db_path, root=tables.root)
    base = Character(id="x", name="Ashes", caste="dawn")
    lifecycle.lock_chargen(base)
    for user, base_id in ((PLAYER, characters.create(PLAYER, base).id), (WATCHER, None)):
        tables.approve(ST, tables.request(user, table.join_code, base_id).id)
    return table


class Page:
    """A fake open page: it records each message and each notice."""

    def __init__(self, board: TableBoard, hub: BoardHub, table_id: str, user_id: int,
                 *, is_st: bool = False, spectating: bool = False) -> None:
        self.messages: list[dict] = []
        self.notices: list[str] = []
        self.watching = spectating
        self.session = BoardSession(board, hub, table_id, user_id, is_st=is_st,
                                    spectating=lambda: self.watching,
                                    deliver=self.messages.append,
                                    notify=self.notices.append)
        hub.subscribe(self.session)

    def types(self) -> list[str]:
        return [m["type"] for m in self.messages]


@pytest.fixture
def pages(tables: TableStore, table):
    board = TableBoard(tables)
    hub = BoardHub()
    return (Page(board, hub, table.id, ST, is_st=True),
            Page(board, hub, table.id, PLAYER),
            Page(board, hub, table.id, WATCHER, spectating=True))


def token(object_id: str = "t1", **overrides) -> dict:
    return {"kind": "token", "id": object_id, "x": 10, "y": 10, "r": 20,
            "colour": "#aa3322", "label": "Ashes"} | overrides


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 16), "blue").save(buffer, "PNG")
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# The fan-out: one commit path, and each intent reaches each page
# --------------------------------------------------------------------------- #


def test_a_put_reaches_each_open_page_with_its_version(pages) -> None:
    st, player, watcher = pages

    player.session.handle({"op": "put", "obj": token()})

    for page in pages:
        assert page.messages == [{"type": "op", "version": 1, "op": "put",
                                  "obj": token() | {"x": 10.0, "y": 10.0, "r": 20.0}}]


def test_a_delete_and_a_restack_reach_each_open_page(pages) -> None:
    st, player, watcher = pages
    player.session.handle({"op": "put", "obj": token("a")})
    st.session.handle({"op": "put", "obj": token("b")})

    st.session.handle({"op": "front", "id": "a"})
    player.session.handle({"op": "delete", "id": "b"})

    for page in pages:
        assert page.messages[2] == {"type": "op", "version": 3, "op": "order",
                                    "ids": ["b", "a"]}
        assert page.messages[3] == {"type": "op", "version": 4, "op": "delete", "id": "b"}


def test_a_change_that_changes_nothing_goes_nowhere(pages) -> None:
    st, player, _ = pages
    player.session.handle({"op": "put", "obj": token()})
    player.session.handle({"op": "delete", "id": "gone"})
    player.session.handle({"op": "back", "id": "t1"})  # One object: no move.
    player.session.handle({"op": "front", "id": "gone"})
    assert [len(p.messages) for p in pages] == [1, 1, 1]


def test_the_storyteller_clears_and_each_page_gets_the_board(pages) -> None:
    st, player, watcher = pages
    player.session.handle({"op": "put", "obj": token()})

    st.session.clear()

    for page in pages:
        assert page.messages[-1] == {"type": "snapshot", "version": 2, "objects": [],
                                     "background": None}


def test_a_background_reaches_each_page_with_its_address(pages, table) -> None:
    st, player, _ = pages
    player.session.handle({"op": "put", "obj": token()})

    st.session.set_background(png_bytes())

    for page in pages:
        assert page.messages[-1]["background"] == {
            "url": f"/table/{table.id}/board-background?v=2", "width": 32, "height": 16}
    # A later change of an object keeps the address, thus the image stays cached.
    player.session.handle({"op": "put", "obj": token(x=50)})
    assert st.session.snapshot_message()["background"]["url"].endswith("?v=2")


def test_a_refused_intent_tells_the_person_and_resends_the_board(pages) -> None:
    st, player, watcher = pages
    player.session.handle({"op": "put", "obj": token()})

    player.session.handle({"op": "put", "obj": token("t2", character_id="x")})

    assert player.notices == ["That drawing is not valid."]
    assert player.messages[-1]["type"] == "snapshot"
    assert [len(p.messages) for p in (st, watcher)] == [1, 1]


def test_a_spectator_is_refused_at_each_intent(pages) -> None:
    """Q1. The mode of the canvas is for the display. The session asks again."""
    st, player, watcher = pages
    player.session.handle({"op": "put", "obj": token()})

    for intent in ({"op": "put", "obj": token("t2")}, {"op": "delete", "id": "t1"},
                   {"op": "front", "id": "t1"}, {"op": "back", "id": "t1"}):
        watcher.session.handle(intent)

    assert watcher.notices == ["A spectator watches the board."] * 4
    assert [len(p.messages) for p in (st, player)] == [1, 1]


def test_a_player_cannot_clear_or_set_the_background(pages) -> None:
    from exalted_builder.server.table_board import TableBoardError

    _, player, _ = pages
    for change in (player.session.clear, lambda: player.session.set_background(png_bytes()),
                   player.session.remove_background):
        with pytest.raises(TableBoardError):
            change()


def test_sync_gives_the_board_to_the_one_page_that_asked(pages) -> None:
    st, player, watcher = pages
    player.session.handle({"op": "put", "obj": token()})

    watcher.session.handle({"op": "sync"})

    assert watcher.types() == ["op", "snapshot"]
    assert [len(p.messages) for p in (st, player)] == [1, 1]


def test_an_ask_goes_to_the_panel_and_writes_nothing(pages) -> None:
    _, player, _ = pages
    ask = {"op": "ask", "kind": "token", "x": 1, "y": 2}
    assert player.session.handle(ask) == ask
    assert [len(p.messages) for p in pages] == [0, 0, 0]


@pytest.mark.parametrize("junk", [None, "put", [], {"op": "explode"}, {"op": "put"},
                                  {"op": "delete"}])
def test_a_malformed_intent_writes_nothing(pages, junk) -> None:
    _, player, _ = pages
    player.session.handle(junk)
    assert player.session.board.version(player.session.table_id) == 0
    assert [p.messages for p in pages[::2]] == [[], []]


def test_the_mode_goes_again_when_the_page_starts_to_watch(pages) -> None:
    _, player, _ = pages
    assert player.session.sync_mode() is False

    player.watching = True

    assert player.session.sync_mode() is True
    assert player.messages[-1] == {"type": "mode", "edit": False, "st": False}
    assert player.session.sync_mode() is False


def test_a_page_that_closes_gets_nothing_more(tables, table) -> None:
    board, hub = TableBoard(tables), BoardHub()
    one = Page(board, hub, table.id, PLAYER)
    two = Page(board, hub, table.id, ST, is_st=True)
    hub.unsubscribe(one.session)

    two.session.handle({"op": "put", "obj": token()})

    assert (len(one.messages), len(two.messages)) == (0, 1)


def test_a_page_that_fails_does_not_stop_the_others(tables, table) -> None:
    board, hub = TableBoard(tables), BoardHub()
    broken = BoardSession(board, hub, table.id, ST, is_st=True, spectating=lambda: False,
                          deliver=lambda _m: (_ for _ in ()).throw(RuntimeError("gone")))
    hub.subscribe(broken)
    other = Page(board, hub, table.id, PLAYER)

    other.session.handle({"op": "put", "obj": token()})

    assert len(other.messages) == 1


def test_a_different_table_hears_nothing(tables, table) -> None:
    board, hub = TableBoard(tables), BoardHub()
    elsewhere = tables.create(ST, "Elsewhere")
    here = Page(board, hub, table.id, PLAYER)
    there = Page(board, hub, elsewhere.id, ST, is_st=True)

    here.session.handle({"op": "put", "obj": token()})

    assert (len(here.messages), len(there.messages)) == (1, 0)


def test_the_head_inlines_konva_and_the_canvas() -> None:
    html = board_head_html()
    assert "Konva JavaScript Framework" in html
    assert "window.ExBoard" in html
    assert "src=" not in html.split("<script>")[0]


# --------------------------------------------------------------------------- #
# The page (PRODUCTION wiring)
# --------------------------------------------------------------------------- #

nicegui_testing = pytest.importorskip("nicegui.testing")
pytest.importorskip("bcrypt")

from exalted_builder.server import chrome  # noqa: E402

from . import _auth_state as state  # noqa: E402
from .test_table_view import MAIN, _campaign, _member, _sign_up, _tables  # noqa: E402


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_player_gets_the_tools_and_no_storyteller_menu(create_user) -> None:
    _, _, table, [(player, _, _)] = await _campaign(create_user, "Ashes of Dawn")

    await player.open(chrome.table_url(table.id))

    await player.should_see(marker="table-board")
    await player.should_see(marker="board-stage")
    for tool in ("select", "pen", "line", "arrow", "rect", "ellipse", "text", "token",
                 "eraser"):
        await player.should_see(marker=f"board-tool-{tool}")
    await player.should_see(marker="board-delete")
    await player.should_not_see(marker="board-st-menu")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_storyteller_gets_the_menu(create_user) -> None:
    st, _, table, _ = await _campaign(create_user, "Ashes of Dawn")

    await st.open(chrome.table_url(table.id))

    await st.should_see(marker="board-tool-pen")
    await st.should_see(marker="board-st-menu")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_spectator_watches_with_no_tools(create_user) -> None:
    _, _, table, _ = await _campaign(create_user)
    watcher = create_user()
    _member(table, await _sign_up(watcher, "Watcher"))

    await watcher.open(chrome.table_url(table.id))

    await watcher.should_see(marker="board-watching")
    await watcher.should_see(marker="board-fit")
    await watcher.should_not_see(marker="board-tool-pen")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_background_is_served_to_a_member_and_to_no_one_else(
        create_user) -> None:
    st, st_id, table, [(player, _, _)] = await _campaign(create_user, "Ashes of Dawn")
    stranger = create_user()
    await _sign_up(stranger, "Stranger")
    board = TableBoard(_tables())
    address = f"/table/{table.id}/board-background"

    response = await player.http_client.get(address)
    assert response.status_code == 404  # No background yet.

    board.set_background(st_id, table.id, png_bytes())

    response = await player.http_client.get(address)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(response.content)).size == (32, 16)

    response = await stranger.http_client.get(address)
    assert response.status_code == 404


def _active(user, marker: str) -> bool:
    (element,) = user.find(marker=marker).elements
    return "bg-black/10" in element.classes


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_colour_picks_the_pen_from_select_and_the_eraser(create_user) -> None:
    """The human, 2026-09-25: switching a colour switches to the pen. A drawing tool
    that is active stays: a red rectangle is a reason to pick red."""
    _, _, table, [(player, _, _)] = await _campaign(create_user, "Ashes of Dawn")
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="board-tool-select")
    assert _active(player, "board-tool-select")

    player.find(marker="board-colour-b91c1c").click()
    assert _active(player, "board-tool-pen")

    player.find(marker="board-tool-eraser").click()
    player.find(marker="board-colour-1d4ed8").click()
    assert _active(player, "board-tool-pen")

    player.find(marker="board-tool-rect").click()
    player.find(marker="board-colour-15803d").click()
    assert _active(player, "board-tool-rect")


def test_a_group_move_is_one_message_to_each_page(pages) -> None:
    st, player, watcher = pages
    for name in "ab":
        player.session.handle({"op": "put", "obj": token(name)})

    player.session.handle({"op": "put_many", "objs": [token("a", x=5), token("b", x=6)]})

    for page in pages:
        last = page.messages[-1]
        assert (last["op"], last["version"]) == ("put_many", 3)
        assert [(o["id"], o["x"]) for o in last["objs"]] == [("a", 5.0), ("b", 6.0)]


def test_a_group_delete_and_restack_are_one_message_each(pages) -> None:
    st, player, watcher = pages
    for name in "abc":
        player.session.handle({"op": "put", "obj": token(name)})

    player.session.handle({"op": "back", "ids": ["c", "b"]})
    player.session.handle({"op": "delete", "ids": ["a", "c"]})

    for page in pages:
        assert page.messages[-2] == {"type": "op", "version": 4, "op": "order",
                                     "ids": ["b", "c", "a"]}
        assert page.messages[-1] == {"type": "op", "version": 5, "op": "delete_many",
                                     "ids": ["a", "c"]}


@pytest.mark.parametrize("junk", [{"op": "put_many"}, {"op": "put_many", "objs": "x"},
                                  {"op": "delete", "ids": "ab"},
                                  {"op": "front", "ids": [1, 2]}])
def test_a_malformed_group_intent_writes_nothing(pages, junk) -> None:
    _, player, _ = pages
    player.session.handle(junk)
    assert player.session.board.version(player.session.table_id) == 0
