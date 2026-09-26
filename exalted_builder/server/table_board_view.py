"""
server/table_board_view.py — the board in the centre of `/table/<id>`.

Steps 2 and 3 of the build order in `docs/plans/p4-board.md` section 6:

  * `board_head_html` inlines the vendored Konva and `server/board.js`. No CDN.
  * `BoardSession` is the board of one open page. It takes the intents of the
    canvas (put, delete, front, back, sync), writes them through
    `server/table_board.py`, and gives the result to `BoardHub`.
  * `BoardHub` holds each open session of each table. A change goes to each of
    them at once: a push, not the poll of the page (section 3).
  * `BoardPanel` draws the toolbar and the stage, and asks for the text of a
    token or a text object.

⚠ Decision 0020. This module and `board.js` never import the engine and never
name the model of the table. `tests/test_table_board.py` greps both. A token
label is what the person types in the dialog here; nothing fills it.

⚠ Commitments, not motion (vtt.md section 0). The canvas sends a stroke when
the pen lifts and a token when it is dropped.

⚠ Each intent is checked again in `TableBoard`: the access, the spectator, the
Storyteller. The mode that the canvas gets is for the display only.

⚠ One commit path. Each change of the board goes through `BoardSession._commit`
or `BoardSession._publish`, and each of them calls the hub. A change that skips
them shows on one screen only.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
import json
import logging
from pathlib import Path
import secrets

from nicegui import ui

from ..ui.assets import konva_source
from .quota import QuotaExceeded
from .table_board import (MAX_LABEL, MAX_TEXT, BoardState, TableBoard,
                          TableBoardError)

log = logging.getLogger(__name__)

BOARD_EVENT = "exboard"
BOARD_JS = Path(__file__).with_name("board.js")

# The largest upload that the picker accepts. The server encodes it again, and
# the result has the cap `table_board.MAX_BACKGROUND_BYTES`. ⚠ The browser applies
# this limit (see `server/home.py` MAX_IMPORT_BYTES).
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

# The tools of the toolbar: key, icon, tooltip.
TOOLS = (
    ("select", "near_me", "Select, move and resize"),
    ("pen", "draw", "Pen"),
    ("line", "horizontal_rule", "Line"),
    ("arrow", "north_east", "Arrow"),
    ("rect", "crop_square", "Rectangle"),
    ("ellipse", "circle", "Ellipse"),
    ("text", "title", "Text"),
    ("token", "radio_button_checked", "Token"),
    ("eraser", "cleaning_services", "Eraser"),
)

COLOURS = ("#1f2937", "#b91c1c", "#c2410c", "#a16207", "#15803d", "#1d4ed8",
           "#7e22ce", "#ffffff")
WIDTHS = (("Thin", 2), ("Medium", 4), ("Thick", 8))

TOKEN_RADIUS = 24
TEXT_SIZE = 24


@lru_cache(maxsize=1)
def board_head_html() -> str:
    """Return the <script> tags of Konva and of the canvas, with the source inline."""
    canvas = BOARD_JS.read_text(encoding="utf-8")
    return f"<script>{konva_source()}</script><script>{canvas}</script>"


def background_url(table_id: str, stamp: int) -> str:
    """Return the address of the background image of `table_id`."""
    return f"/table/{table_id}/board-background?v={stamp}"


def new_object_id() -> str:
    """Return a new object id."""
    return "p" + secrets.token_hex(6)


class BoardHub:
    """The open sessions of each table. One hub for the process."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[BoardSession]] = {}

    def subscribe(self, session: BoardSession) -> None:
        self._sessions.setdefault(session.table_id, []).append(session)

    def unsubscribe(self, session: BoardSession) -> None:
        sessions = self._sessions.get(session.table_id, [])
        if session in sessions:
            sessions.remove(session)
        if not sessions:
            self._sessions.pop(session.table_id, None)

    def sessions(self, table_id: str) -> list[BoardSession]:
        return list(self._sessions.get(table_id, []))

    def broadcast(self, table_id: str, message: dict) -> None:
        """Give `message` to each open session of `table_id`, in the order of the
        subscriptions."""
        for session in self.sessions(table_id):
            session.deliver(message)


class BoardSession:
    """The board of one open page. It has no NiceGUI call; `deliver` and `notify`
    are the page's.

    `spectating` tells if the page watches now. `deliver` sends one message to
    the canvas of this page. `notify` shows a message to the person.
    """

    def __init__(self, board: TableBoard, hub: BoardHub, table_id: str, user_id: int,
                 *, is_st: bool, spectating: Callable[[], bool],
                 deliver: Callable[[dict], None],
                 notify: Callable[[str], None] = lambda _text: None) -> None:
        self.board = board
        self.hub = hub
        self.table_id = table_id
        self.user_id = user_id
        self.is_st = is_st
        self.spectating = spectating
        self._deliver = deliver
        self.notify = notify
        self.edit = not spectating()

    # ---- the messages ------------------------------------------------------- #

    def deliver(self, message: dict) -> None:
        """Send `message` to the canvas. A closed page gives an error; log it."""
        try:
            self._deliver(message)
        except Exception:  # noqa: BLE001 — one closed page must not stop the rest.
            log.warning("A board message did not reach a page", exc_info=True)

    def mode_message(self) -> dict:
        return {"type": "mode", "edit": self.edit, "st": self.is_st}

    def snapshot_message(self) -> dict:
        return snapshot_message(self.table_id, self.board.state(self.user_id,
                                                                self.table_id))

    def sync_mode(self) -> bool:
        """Send the mode again if it changed. Return True if it changed."""
        edit = not self.spectating()
        if edit == self.edit:
            return False
        self.edit = edit
        self.deliver(self.mode_message())
        return True

    # ---- the intents -------------------------------------------------------- #

    def handle(self, args: object) -> dict | None:
        """Do the intent `args` of the canvas. Return an "ask" intent for the
        panel, else None.

        A refused intent shows its message, and the canvas gets the board again.
        """
        if not isinstance(args, dict):
            return None
        op = args.get("op")
        try:
            if op == "put":
                self.put(args.get("obj"))
            elif op == "delete":
                self.delete(str(args.get("id") or ""))
            elif op in ("front", "back"):
                self.restack(str(args.get("id") or ""), front=op == "front")
            elif op == "sync":
                self.deliver(self.snapshot_message())
            elif op == "ask":
                return args
        except (TableBoardError, QuotaExceeded) as exc:
            self.refused(str(exc))
        return None

    def refused(self, text: str) -> None:
        self.notify(text)
        try:
            self.deliver(self.snapshot_message())
        except TableBoardError:
            pass

    def put(self, data: object) -> None:
        state = self.board.put(self.user_id, self.table_id, data,
                               spectating=self.spectating())
        object_id = data["id"] if isinstance(data, dict) else None
        (item,) = [o for o in state.objects if o["id"] == object_id]
        self._commit(state, {"op": "put", "obj": item})

    def delete(self, object_id: str) -> None:
        before = self.board.version(self.table_id)
        state = self.board.delete(self.user_id, self.table_id, object_id,
                                  spectating=self.spectating())
        if state.version != before:
            self._commit(state, {"op": "delete", "id": object_id})

    def restack(self, object_id: str, *, front: bool) -> None:
        change = self.board.to_front if front else self.board.to_back
        before = self.board.version(self.table_id)
        state = change(self.user_id, self.table_id, object_id,
                       spectating=self.spectating())
        if state.version != before:
            self._commit(state, {"op": "order", "ids": [o["id"] for o in state.objects]})

    def clear(self) -> None:
        self._publish(self.board.clear(self.user_id, self.table_id))

    def set_background(self, raw: bytes) -> None:
        self._publish(self.board.set_background(self.user_id, self.table_id, raw))

    def remove_background(self) -> None:
        self._publish(self.board.remove_background(self.user_id, self.table_id))

    def _commit(self, state: BoardState, change: dict) -> None:
        """Give one change at `state.version` to each open page of the table."""
        self.hub.broadcast(self.table_id, {"type": "op", "version": state.version}
                           | change)

    def _publish(self, state: BoardState) -> None:
        """Give the whole board at `state` to each open page of the table."""
        self.hub.broadcast(self.table_id, snapshot_message(self.table_id, state))


def snapshot_message(table_id: str, state: BoardState) -> dict:
    """Return the message that replaces the whole board on a canvas."""
    background = state.background
    return {
        "type": "snapshot",
        "version": state.version,
        "objects": list(state.objects),
        "background": None if background is None else {
            "url": background_url(table_id, background.stamp),
            "width": background.width, "height": background.height},
    }


class BoardPanel:
    """The board of one page: the toolbar and the stage. Make it in the page
    function, and build it with `build`.

    `spectating` tells if the page watches now. The page asks it at each intent.
    """

    def __init__(self, board: TableBoard, hub: BoardHub, table_id: str, user_id: int,
                 *, is_st: bool, spectating: Callable[[], bool], pal) -> None:
        # ⚠ The client of THIS page. A change of a different page runs in the
        # context of that page, thus `ui.run_javascript` there reaches the wrong one.
        client = ui.context.client
        self.client = client

        def deliver(message: dict) -> None:
            client.run_javascript(f"ExBoard.receive({json.dumps(message)})")

        def notify(text: str) -> None:
            with client:
                ui.notify(text, type="warning")

        self.session = BoardSession(board, hub, table_id, user_id, is_st=is_st,
                                    spectating=spectating, deliver=deliver,
                                    notify=notify)
        self.pal = pal
        self.tool = "select"
        self.colour = COLOURS[0]
        self.width = WIDTHS[0][1]
        self.fill = False
        self._connects = 0

    def build(self) -> None:
        """Draw the board. Subscribe the session to the hub, and unsubscribe it
        when the client goes."""
        ui.add_head_html(board_head_html())
        with ui.column().classes("w-full flex-1 gap-0 rounded overflow-hidden").style(
                "border:1px solid #d6c7a1;background:#fffdf7").mark("table-board"):
            self.toolbar = ui.row().classes(
                "w-full items-center gap-1 px-2 py-1 flex-wrap").style(
                "border-bottom:1px solid #d6c7a1;background:#faf3e2")
            self.stage = ui.element("div").classes(
                "relative w-full flex-1 min-h-[20rem]").mark("board-stage")
            self.dialog_host = ui.element("div")
        self.draw_toolbar()

        ui.on(BOARD_EVENT, lambda e: self.on_event(e.args))
        self.session.hub.subscribe(self.session)
        self.client.on_delete(self.close)
        self.client.on_connect(self._on_connect)
        self.remount()

    def _on_connect(self) -> None:
        """Send the board again at a reconnect: a message can be lost. The first
        connect gets the mount of `build`."""
        self._connects += 1
        if self._connects > 1:
            with self.client:
                self.remount()

    def remount(self) -> None:
        self.session.edit = not self.session.spectating()
        try:
            snapshot = self.session.snapshot_message()
        except TableBoardError:
            return
        ui.run_javascript(
            f"ExBoard.mount({json.dumps(f'c{self.stage.id}')}, "
            f"{json.dumps(self.session.mode_message())}, {json.dumps(snapshot)}); "
            f"ExBoard.style({json.dumps(self.colour)}, {self.width}, "
            f"{json.dumps(self.fill)}); ExBoard.setTool({json.dumps(self.tool)});")

    def close(self) -> None:
        self.session.hub.unsubscribe(self.session)

    def sync_mode(self) -> None:
        """Send the mode again if the page began or stopped to watch."""
        if self.session.sync_mode():
            if not self.session.edit:
                self.tool = "select"
            self.draw_toolbar()

    # ---- the toolbar -------------------------------------------------------- #

    def draw_toolbar(self) -> None:
        self.toolbar.clear()
        with self.toolbar:
            ui.label("BOARD").classes("text-xs font-bold tracking-widest opacity-50 pr-2")
            if not self.session.edit:
                ui.label("You are watching.").classes("text-xs italic opacity-60") \
                    .mark("board-watching")
                ui.space()
                self._fit_button()
                return
            for key, icon, tip in TOOLS:
                active = key == self.tool
                with ui.button(icon=icon, on_click=lambda k=key: self.set_tool(k)).props(
                        "dense flat round size=sm" + (f" color={self.pal.button}"
                                                      if active else " color=grey-8")
                        ).classes("bg-black/10" if active else "").mark(f"board-tool-{key}"):
                    ui.tooltip(tip)
            ui.separator().props("vertical")
            for colour in COLOURS:
                ring = "3px solid #111" if colour == self.colour else "1px solid #0004"
                ui.element("div").classes("w-5 h-5 rounded-full cursor-pointer shrink-0") \
                    .style(f"background:{colour};border:{ring}").on(
                    "click", lambda c=colour: self.set_style(colour=c)).mark(
                    f"board-colour-{colour[1:]}")
            ui.select({w: name for name, w in WIDTHS}, value=self.width,
                      on_change=lambda e: self.set_style(width=e.value)).props(
                "dense borderless options-dense").classes("w-20 text-xs").mark(
                "board-width")
            ui.checkbox("Fill", value=self.fill,
                        on_change=lambda e: self.set_style(fill=e.value)).props(
                "dense size=xs").classes("text-xs").mark("board-fill")
            ui.separator().props("vertical")
            for command, icon, tip in (("delete", "delete", "Delete the selection"),
                                       ("front", "flip_to_front", "Bring to front"),
                                       ("back", "flip_to_back", "Send to back")):
                with ui.button(icon=icon, on_click=lambda c=command: ui.run_javascript(
                        f"ExBoard.command({json.dumps(c)})")).props(
                        "dense flat round size=sm color=grey-8").mark(f"board-{command}"):
                    ui.tooltip(tip)
            ui.space()
            self._fit_button()
            if self.session.is_st:
                self._st_tools()

    def _fit_button(self) -> None:
        with ui.button(icon="fit_screen",
                       on_click=lambda: ui.run_javascript("ExBoard.command('fit')")).props(
                "dense flat round size=sm color=grey-8").mark("board-fit"):
            ui.tooltip("Fit the board to the view")

    def _st_tools(self) -> None:
        upload = ui.upload(auto_upload=True, on_upload=self._on_upload,
                           max_file_size=MAX_UPLOAD_BYTES,
                           on_rejected=lambda: ui.notify(
                               f"The limit for an upload is "
                               f"{MAX_UPLOAD_BYTES // 2**20} MB.", type="warning")
                           ).props("accept=image/png,image/jpeg,image/webp,image/gif") \
            .classes("hidden").mark("board-upload")
        with ui.button(icon="more_vert").props("dense flat round size=sm color=grey-8") \
                .mark("board-st-menu"):
            with ui.menu():
                ui.menu_item("Set the background…",
                             on_click=lambda: upload.run_method("pickFiles")).mark(
                    "board-set-background")
                ui.menu_item("Remove the background",
                             on_click=self._confirm_remove_background).mark(
                    "board-remove-background")
                ui.menu_item("Clear the board…", on_click=self._confirm_clear).mark(
                    "board-clear")

    def set_tool(self, tool: str) -> None:
        self.tool = tool
        ui.run_javascript(f"ExBoard.setTool({json.dumps(tool)})")
        self.draw_toolbar()

    def set_style(self, *, colour: str | None = None, width: int | None = None,
                  fill: bool | None = None) -> None:
        if colour is not None:
            self.colour = colour
        if width is not None:
            self.width = int(width)
        if fill is not None:
            self.fill = bool(fill)
        ui.run_javascript(f"ExBoard.style({json.dumps(self.colour)}, {self.width}, "
                          f"{json.dumps(self.fill)})")
        if colour is not None:
            self.draw_toolbar()

    # ---- the events --------------------------------------------------------- #

    def on_event(self, args: object) -> None:
        ask = self.session.handle(args)
        if ask is not None and self.session.edit:
            self.ask(ask)

    def ask(self, args: dict) -> None:
        """Open the dialog for the text of a new or an old token or text object."""
        existing = None
        if args.get("id"):
            try:
                objects = self.session.board.state(self.session.user_id,
                                                   self.session.table_id).objects
            except TableBoardError:
                return
            found = [o for o in objects if o["id"] == args["id"]]
            if not found or found[0]["kind"] not in ("token", "text"):
                return
            existing = found[0]
            kind = existing["kind"]
        else:
            kind = args.get("kind")
            if kind not in ("token", "text"):
                return
        field = "label" if kind == "token" else "text"
        limit = MAX_LABEL if kind == "token" else MAX_TEXT
        with self.dialog_host, ui.dialog() as dialog, ui.card().classes("min-w-[20rem]"):
            ui.label("Token label" if kind == "token" else "Text").classes(
                "text-base font-bold")
            box = ui.input(value=existing[field] if existing else "",
                           placeholder="Type a label" if kind == "token"
                           else "Type the text").props(
                f"autofocus maxlength={limit}").classes("w-full").mark("board-ask-text")

            def done(typed: object = None) -> None:
                text = ((typed if isinstance(typed, str) and typed else box.value)
                        or "").strip()
                if existing is not None:
                    data = dict(existing) | {field: text}
                elif kind == "token":
                    data = {"kind": "token", "id": new_object_id(),
                            "x": args.get("x"), "y": args.get("y"), "r": TOKEN_RADIUS,
                            "colour": self.colour, "label": text}
                else:
                    data = {"kind": "text", "id": new_object_id(),
                            "x": args.get("x"), "y": args.get("y"), "size": TEXT_SIZE,
                            "colour": self.colour, "text": text}
                dialog.close()
                try:
                    self.session.put(data)
                except (TableBoardError, QuotaExceeded) as exc:
                    self.session.refused(str(exc))

            # ⚠ The key event carries the text. Enter can reach the server before
            # the last value update of the box, and `box.value` is then empty.
            box.on("keydown.enter", lambda e: done(e.args),
                   js_handler="(e) => emit(e.target.value)")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("OK", on_click=lambda: done()).props(f"color={self.pal.button}").mark(
                    "board-ask-ok")
        dialog.open()

    def _confirm(self, title: str, body: str, action: str, run: Callable[[], None],
                 marker: str) -> None:
        with self.dialog_host, ui.dialog() as dialog, ui.card():
            ui.label(title).classes("text-base font-bold")
            ui.label(body).classes("text-sm")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                def go() -> None:
                    dialog.close()
                    try:
                        run()
                    except (TableBoardError, QuotaExceeded) as exc:
                        ui.notify(str(exc), type="warning")

                ui.button(action, on_click=go).props("color=negative").mark(marker)
        dialog.open()

    def _confirm_clear(self) -> None:
        self._confirm("Clear the board?",
                      "This removes every drawing, text and token for everyone. The "
                      "background stays.", "Clear", self.session.clear,
                      "board-clear-confirm")

    def _confirm_remove_background(self) -> None:
        self._confirm("Remove the background?",
                      "The image is deleted from the campaign.", "Remove",
                      self.session.remove_background, "board-remove-background-confirm")

    async def _on_upload(self, e) -> None:
        raw = await e.file.read()
        try:
            self.session.set_background(raw)
        except (TableBoardError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
