"""
server/table_view.py — `/table/<id>`, the table view of a campaign.

Step 3 of the build order in `docs/plans/p3-tables.md` section 15.4. The layout is
section 15.2 (shape A of `spikes/campaign_page/`):

  * The top bar: Home, the campaign, the role of the viewer, "Open as" for a
    viewer with a copy in the campaign, and the request badge of the Storyteller.
  * The left rail: PARTY. YOU PLAY is the copy that the viewer opens as, with live
    controls (R2). THE OTHERS are read-only for each viewer, the Storyteller too (R3).
  * The centre: the frame of the board (P4) and nothing else (Q7).
  * The right rail: the tabs Log, Notes and ST. The ST tab is for the Storyteller.
    The Log is step 4 (section 15.3): messages and rolls, in `server/table_log.py`.

⚠ `TableStore.access` is the check. The page calls it in the page body, before it
reads anything of the table. Each handler and each poll calls it again. A hidden
button is not a check.

⚠ YOU PLAY writes through the character registry: the SAME object that
`/character/<copy>` edits. A write to the file behind an open page is lost at the
next auto-save of that page. Only the owner gets a context. The page reads the
character of another account with `SessionRegistry.peek`, or from its file, and
never builds a context for it (section 8).

⚠ A poll, not a hook. The timer compares the rows, the members, the requests, a
digest of each character and the version of the Log. It repaints the part that moved.

⚠ The Log shows each text with `ui.label`. Never use `ui.html` or `ui.markdown`
there: a member types the text.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time

from nicegui import app, ui

from ..engine import derive, dice, play as engineplay
from ..models.character import Character, PlayState
from ..models.rules import RuleSet
from ..ui import play as play_mod
from ..ui import saving, theme
from ..ui import view as viewmod
from . import chrome, db
from .campaigns import carried_summary
from .characters import CharacterRow, CharacterStore
from .quota import QuotaExceeded
from .session import SessionRegistry
from .table_log import MAX_TEXT, LogEntry, TableLog, TableLogError
from .tables import STORYTELLER, TableRow, TableStore, TableStoreError

TABLE_PATH = chrome.TABLE_PATH

# The interval of the poll, in seconds. One poll reads the database and one file
# status for each character, thus it costs little.
POLL_SECONDS = 2.0

# The value of "Open as" for a viewer who opens the campaign with no character.
SPECTATE = "spectate"

_GOLD, _WHITE, _BORDER = play_mod._GOLD, play_mod._WHITE, play_mod._BORDER
_MARK_COLOR = play_mod._MARK_COLOR

GONE = "You are no longer in this campaign."
COPY_GONE = "That character is no longer in this campaign."


def _username(tables: TableStore, user_id: int) -> str:
    return db.username_for(tables.db_path, user_id) or "(a deleted account)"


def _open_as_key(table_id: str) -> str:
    """The key in `app.storage.user` of the "Open as" choice for `table_id`."""
    return f"table-open-as:{table_id}"


def register_table_page(tables: TableStore, store: CharacterStore, book: RuleSet,
                        sessions: SessionRegistry,
                        current_user_id: Callable[[], int | None],
                        log: TableLog) -> None:
    """Register `/table/<id>`.

    `book` gives the RuleSet of a character that has no live context. `sessions` is
    the character registry of `server/home.py`. `current_user_id` returns the
    account of the request. `log` reads and writes the Log of each table.
    """

    @ui.page(TABLE_PATH + "/{table_id}")
    def table_page(table_id: str) -> None:
        user_id = chrome.require_account(current_user_id)
        # ⚠ Before anything that reads the table.
        role = tables.access(user_id, table_id)
        table = tables.table(table_id) if role is not None else None
        if table is None:
            _not_found()
            return
        _TableView(tables, store, book, sessions, log, user_id, table).build()


def _not_found() -> None:
    """The answer for a campaign of which the account is not a member, and for
    one that is absent."""
    with chrome.header(theme.palette(None), "Exalted 1e"):
        chrome.home_button()
    ui.label("There is no such campaign.").classes("text-base p-4").mark("table-not-found")


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #


@dataclass
class _Shown:
    """One copy as the page reads it. `character` is None for a file that does
    not read."""

    row: CharacterRow
    character: Character | None
    ruleset: RuleSet


def _file_digest(store: CharacterStore, row: CharacterRow):
    try:
        status = store.path_for(row).stat()
    except OSError:
        return None
    return status.st_mtime_ns, status.st_size


class _TableView:
    """The page of one table for one account. Build it with `build`."""

    def __init__(self, tables: TableStore, store: CharacterStore, book: RuleSet,
                 sessions: SessionRegistry, log: TableLog, user_id: int,
                 table: TableRow) -> None:
        self.tables = tables
        self.log = log
        self.store = store
        self.book = book
        self.sessions = sessions
        self.user_id = user_id
        self.table = table
        self.is_st = table.storyteller_id == user_id
        self.pal = theme.palette(None)
        self.gone = False
        self._structure = None
        self._digests: dict[str, object] = {}
        self._log_version = None

    # ---- reads -------------------------------------------------------------- #

    def copies(self) -> list[CharacterRow]:
        return self.tables.characters(self.table.id)

    def mine(self, copies: list[CharacterRow]) -> list[CharacterRow]:
        return [row for row in copies if row.owner_id == self.user_id]

    def chosen(self, copies: list[CharacterRow]) -> CharacterRow | None:
        """Return the copy that the viewer opens as, or None to spectate.

        The choice is in `app.storage.user`. A choice that is not a copy of the
        viewer in the table gives the first copy of the viewer.
        """
        mine = self.mine(copies)
        stored = app.storage.user.get(_open_as_key(self.table.id))
        if stored == SPECTATE:
            return None
        for row in mine:
            if row.id == stored:
                return row
        return mine[0] if mine else None

    def read(self, row: CharacterRow) -> _Shown:
        """Read a copy with no context of its own: the live context if the owner has
        one open, else the file. ⚠ `peek`, never `ctx_for`."""
        ctx = self.sessions.peek(row.id)
        if ctx is not None:
            return _Shown(row, ctx["char"], ctx["ruleset"])
        try:
            return _Shown(row, self.store.load(row), self.book)
        except Exception:                           # noqa: BLE001 - show it as unreadable
            return _Shown(row, None, self.book)

    def read_own(self, row: CharacterRow) -> _Shown:
        """Read the copy that the viewer opens as, through its live context. Build
        the context if it is absent: the viewer owns the character."""
        try:
            ctx = self.sessions.ctx_for(row.id)
        except Exception:                           # noqa: BLE001 - the factory could not read it
            return _Shown(row, None, self.book)
        return _Shown(row, ctx["char"], ctx["ruleset"])

    def digest(self, row: CharacterRow):
        ctx = self.sessions.peek(row.id)
        if ctx is not None:
            return saving.character_digest(ctx["char"])
        return _file_digest(self.store, row)

    def structure(self, copies: list[CharacterRow]):
        """What decides the layout: the copies, the members and the requests."""
        pending = (tuple(r.id for r in self.tables.pending(self.user_id, self.table.id))
                   if self.is_st else ())
        return (tuple(row.id for row in copies), tuple(self.tables.members(self.table.id)),
                pending)

    # ---- the page ----------------------------------------------------------- #

    def build(self) -> None:
        pal = self.pal
        ui.query("body").style(f"background:{pal.bg};color:{pal.ink}")
        with ui.header().classes("items-center justify-between px-4 py-1").style(
                f"background:{pal.accent}"):
            with ui.row().classes("items-center gap-1 no-wrap min-w-0"):
                chrome.home_button()
                ui.label("›").classes("text-white/70")
                ui.label(self.table.name).classes(
                    "text-lg font-bold text-white truncate").mark("table-title")
                ui.label("Storyteller" if self.is_st else "Player").classes(
                    "text-xs text-white/80 pl-2").mark("table-role")
            self.top_right = ui.row().classes("items-center gap-2 no-wrap")

        self.main = ui.element("div").classes(
            "w-full flex flex-col md:flex-row gap-3 p-3 md:items-stretch "
            "md:h-[calc(100vh-56px)]")
        with self.main:
            with ui.element("div").classes(
                    "w-full md:w-[19rem] md:shrink-0 md:overflow-y-auto flex flex-col gap-2 "
                    "md:pr-1"):
                self.rail = ui.column().classes("w-full gap-2")
            with ui.element("div").classes("flex-1 min-w-0 min-h-[16rem] flex flex-col"):
                self._board()
            with ui.element("div").classes(
                    "w-full md:w-[19rem] md:shrink-0 flex flex-col gap-1 md:overflow-y-auto"):
                self._right_rail()

        copies = self.copies()
        self._structure = self.structure(copies)
        self._draw_top(copies)
        self._draw_rail(copies)
        ui.timer(POLL_SECONDS, self.poll)

    def refresh_all(self) -> None:
        copies = self.copies()
        self._structure = self.structure(copies)
        self._draw_top(copies)
        self._draw_rail(copies)
        self._draw_members(copies)
        if self.is_st:
            self._draw_st()

    def stop(self) -> None:
        """Replace the page with the answer for a viewer who is not a member now."""
        if self.gone:
            return
        self.gone = True
        self.top_right.clear()
        self.main.clear()
        with self.main:
            with ui.column().classes("p-4 gap-2").mark("table-gone"):
                ui.label(GONE).classes("text-base")
                ui.button("Home", icon="home",
                          on_click=lambda: ui.navigate.to(chrome.HOME_PATH)).props(
                    f"color={self.pal.button}")

    # ---- the poll ----------------------------------------------------------- #

    def poll(self) -> None:
        """Stop the page if the viewer is not a member now. Else repaint what moved."""
        if self.gone:
            return
        if self.tables.access(self.user_id, self.table.id) is None:
            self.stop()
            return
        if self.log.version(self.table.id) != self._log_version:
            self._draw_log()
        copies = self.copies()
        if self.structure(copies) != self._structure:
            self.refresh_all()
            return
        digests = {row.id: self.digest(row) for row in copies}
        if digests != self._digests:
            self._draw_rail(copies)

    # ---- the top bar -------------------------------------------------------- #

    def _draw_top(self, copies: list[CharacterRow]) -> None:
        self.top_right.clear()
        with self.top_right:
            mine = self.mine(copies)
            if mine:
                chosen = self.chosen(copies)
                characters = {row.id: self.read(row).character for row in mine}
                options = {row_id: "Open as: " + (c.name if c is not None and c.name
                                                  else "(unnamed)")
                           for row_id, c in characters.items()}
                options[SPECTATE] = "Spectate"
                ui.select(options, value=chosen.id if chosen else SPECTATE,
                          on_change=lambda e: self._open_as(e.value)).props(
                    "dense dark borderless options-dense").classes(
                    "text-white w-56").mark("table-open-as")
            if self.is_st:
                count = len(self.tables.pending(self.user_id, self.table.id))
                with ui.button(icon="how_to_reg",
                               on_click=lambda: self.tabs.set_value("st")).props(
                        "flat round color=white").mark("table-requests-button"):
                    if count:
                        ui.badge(str(count), color="red").props("floating").mark(
                            "table-requests-badge")
                    ui.tooltip("Join requests")
            with ui.button(icon="more_vert").props("flat round color=white"):
                with ui.menu():
                    ui.menu_item("Log out", on_click=lambda: ui.navigate.to("/logout")) \
                        .mark("top-bar-logout")

    def _open_as(self, value: str) -> None:
        app.storage.user[_open_as_key(self.table.id)] = value
        self._draw_rail(self.copies())

    # ---- the left rail ------------------------------------------------------ #

    def _draw_rail(self, copies: list[CharacterRow]) -> None:
        """Draw PARTY: YOU PLAY, then THE OTHERS. Record the digest of each copy."""
        pal = self.pal
        chosen = self.chosen(copies)
        self.rail.clear()
        with self.rail:
            chrome.section_label(pal, "PARTY", len(copies))
            if not copies:
                ui.label("No characters yet. An approved request that brings a "
                         "character puts its campaign copy here.").classes(
                    "text-sm opacity-70")
            if chosen is not None:
                _heading(pal, "YOU PLAY")
                self._you_play(self.read_own(chosen))
            others = [row for row in copies if chosen is None or row.id != chosen.id]
            if others and chosen is not None:
                _heading(pal, "THE OTHERS")
            for row in others:
                _other_row(self.read(row), _username(self.tables, row.owner_id),
                           mine=row.owner_id == self.user_id)
        self._digests = {row.id: self.digest(row) for row in copies}

    def _act(self, row_id: str, change: Callable[[Character], None]) -> None:
        """Apply `change` to the copy `row_id` of the viewer, and save it.

        ⚠ Ask `access()` again, and ask that the viewer still owns the copy and
        that it is still in the table. Change the object of the live context.
        """
        if self.tables.access(self.user_id, self.table.id) is None:
            ui.notify(GONE, type="warning")
            self.stop()
            return
        row = self.store.owned(self.user_id, row_id)
        if row is None or row.table_id != self.table.id:
            ui.notify(COPY_GONE, type="warning")
            self.refresh_all()
            return
        character = self.sessions.ctx_for(row.id)["char"]
        change(character)
        try:
            self.store.save(row, character)
        except QuotaExceeded as exc:
            ui.notify(str(exc), type="negative")
        self._draw_rail(self.copies())

    def _you_play(self, shown: _Shown) -> None:
        """The copy of the viewer, with live controls (R2)."""
        row, character = shown.row, shown.character
        with ui.column().classes("w-full gap-0").mark("you-play"):
            if character is None:
                ui.label(f"(unreadable: {row.id})").classes("text-sm opacity-70")
                return
            cv = viewmod.build_party_card_view(shown.ruleset, character)
            cpal = theme.palette(character.exalt_type)
            cur = character.play or PlayState()
            n = len(cv.play.health_boxes)
            marks = list(cur.health)[:n] + [None] * max(0, n - len(cur.health))
            act = lambda change: self._act(row.id, change)  # noqa: E731

            with ui.row().classes(
                    f"w-full no-wrap gap-0 rounded overflow-hidden {cpal.card_soft}").style(
                    f"outline:2px solid {cpal.accent}"):
                ui.element("div").classes("w-1 self-stretch").style(
                    f"background:{cpal.accent}")
                with ui.column().classes("gap-1.5 px-2 py-2 min-w-0 flex-1"):
                    with ui.row().classes(
                            "w-full items-baseline justify-between no-wrap gap-2"):
                        ui.label(cv.name).classes("text-sm font-bold truncate").style(
                            f"color:{cpal.accent}").mark("you-name")
                        with ui.link(target=chrome.character_url(row.id)).mark(
                                "you-open-sheet"):
                            ui.icon("open_in_new", size="1rem").style(
                                f"color:{cpal.accent}")
                            ui.tooltip("Open my sheet")
                    ui.label(cv.identity_line).classes("text-xs opacity-70 truncate -mt-1.5")

                    _heading(cpal, "HEALTH · penalty "
                             + viewmod.worst_penalty(cv.play, marks))
                    with ui.row().classes("gap-0.5"):
                        for i, mark in enumerate(marks):
                            box = _health_box(mark, cpal, 1.35).mark(f"you-health-{i}")
                            box.classes("cursor-pointer select-none").on(
                                "click", lambda _=None, i=i: act(
                                    lambda c: engineplay.cycle_mark(c, i, n)))

                    spent_p, spent_pp = viewmod.spent_motes(cv.play, cur)
                    pools = ([("All motes", "peripheral", "motes_peripheral_spent", spent_pp,
                               cv.play.peripheral_max, cv.play.committed_peripheral)]
                             if cv.play.single_pool else
                             [("Personal", "personal", "motes_personal_spent", spent_p,
                               cv.play.personal_max, cv.play.committed_personal),
                              ("Peripheral", "peripheral", "motes_peripheral_spent",
                               spent_pp, cv.play.peripheral_max,
                               cv.play.committed_peripheral)])
                    for label, key, field, spent, cap, committed in pools:
                        # A pool with no motes and none attuned is a pool that the
                        # splat does not have (a Mortal).
                        if cap or committed:
                            _mote_bar(label, key, spent, cap, self.pal,
                                      lambda value, f=field, c=cap: act(
                                          lambda ch: engineplay.set_motes(ch, f, value, c)))
                    for note in (viewmod.committed_note(cv.play, compact=True),
                                 viewmod.free_motes_note(cv.play)):
                        if note:
                            ui.label(note).classes("text-xs opacity-70").mark("you-motes-note")

                    wp_max = cv.play.willpower_max
                    wp_left = wp_max - cur.willpower_spent
                    # A click on box i leaves i dots. A click on the first empty box
                    # fills it again (`engine.play.set_count`).
                    _track(f"WP {wp_left}/{wp_max}", "you-wp", wp_max, wp_left,
                           lambda i: act(lambda c: engineplay.set_count(
                               c, "willpower_spent", wp_max - i, wp_max)))
                    if derive.uses_clarity(shown.ruleset, character):
                        clarity = derive.clarity(shown.ruleset, character)
                        _track(f"Clarity {clarity.total}/{derive.CLARITY_MAX} "
                               f"({clarity.permanent} perm) · band {clarity.band}",
                               "you-clarity", derive.CLARITY_MAX, cur.clarity_temporary,
                               lambda i: act(lambda c: engineplay.set_count(
                                   c, "clarity_temporary", i + 1, derive.CLARITY_MAX)))
                        ui.label(clarity.effects).classes("text-xs opacity-70").mark(
                            "you-clarity-effects")
                    else:
                        # ⚠ `derive.limit_max`, not 10: Greater Curse (p.40) and
                        # permanent Resonance shorten the track.
                        lim = derive.limit_label(shown.ruleset, character)
                        lim_max = derive.limit_max(shown.ruleset, character)
                        broken = f" — {lim.upper()} BREAK" if cur.limit >= lim_max else ""
                        _track(f"{lim} {cur.limit}/{lim_max}{broken}", "you-limit",
                               lim_max, cur.limit,
                               lambda i: act(lambda c: engineplay.set_count(
                                   c, "limit", i + 1, lim_max)))

                    # Accumulated armour fatigue (p.332). A counter with no maximum.
                    # It shows for a character with armour, or with points left.
                    if character.armor or cur.fatigue:
                        _fatigue(cur.fatigue, cv.play.fatigue_difficulties, self.pal,
                                 lambda step: act(lambda c: engineplay.set_fatigue(
                                     c, engineplay.play_state(c).fatigue + step)))

    # ---- the centre --------------------------------------------------------- #

    def _board(self) -> None:
        """The frame of the board (P4). Q7: nothing else is in the centre before P4."""
        with ui.column().classes("w-full flex-1 gap-0 rounded overflow-hidden").style(
                f"border:1px solid {_BORDER};background:#fffdf7").mark("table-board"):
            with ui.row().classes("w-full items-center px-2 py-1").style(
                    f"border-bottom:1px solid {_BORDER};background:#faf3e2"):
                ui.label("BOARD").classes("text-xs font-bold tracking-widest opacity-50")
            with ui.element("div").classes(
                    "relative w-full flex-1 flex items-center justify-center").style(
                    "background-image:linear-gradient(#0000000d 1px,transparent 1px),"
                    "linear-gradient(90deg,#0000000d 1px,transparent 1px);"
                    "background-size:40px 40px"):
                ui.label("The board comes next.").classes("text-sm italic opacity-50")

    # ---- the right rail ----------------------------------------------------- #

    def _right_rail(self) -> None:
        with ui.tabs(value="log").props("dense no-caps align=left").classes(
                "w-full") as tabs:
            ui.tab("log", label="Log").mark("tab-log")
            ui.tab("notes", label="Notes").mark("tab-notes")
            if self.is_st:
                ui.tab("st", label="ST").mark("tab-st")
        self.tabs = tabs
        with ui.tab_panels(tabs, value="log", animated=False).classes(
                "w-full bg-transparent"):
            with ui.tab_panel("log").classes("p-0 gap-1"):
                self._log_panel()
            with ui.tab_panel("notes").classes("p-0 gap-2"):
                self.members_panel = ui.column().classes("w-full gap-1")
                self._draw_members(self.copies())
            if self.is_st:
                with ui.tab_panel("st").classes("p-0 gap-2"):
                    self.st_panel = ui.column().classes("w-full gap-2")
                    self._draw_st()

    # ---- the Log ------------------------------------------------------------ #

    def _log_panel(self) -> None:
        """The Log (R5): the entries, a text box, a dice count, Roll and Send."""
        pal = self.pal
        # ⚠ A scroll area needs a height that is fixed. The rail has no fixed height.
        self.log_area = ui.scroll_area().classes(
            "w-full h-[55vh] md:h-[calc(100vh-15rem)]").mark("log-area")
        with self.log_area:
            self.log_list = ui.column().classes("w-full gap-1").mark("log-list")
        with ui.column().classes("w-full gap-1 pt-1").style(
                f"border-top:1px solid {_BORDER}"):
            self.log_text = ui.input(
                placeholder="Say something, or caption a roll…").props(
                f"dense outlined maxlength={MAX_TEXT}").classes("w-full").mark("log-text")
            self.log_text.on("keydown.enter", self._send)
            with ui.row().classes("w-full items-center no-wrap gap-1"):
                # ⚠ Decision 0019: the player types the count. Nothing fills it from
                # a pool, and the Log never names a roll.
                self.log_count = ui.number(
                    "Dice", value=None, min=1, max=dice.MAX_DICE, format="%d").props(
                    "dense outlined").classes("w-20").mark("log-count")
                ui.button("Roll", icon="casino", on_click=self._roll).props(
                    f"dense no-caps color={pal.button}").mark("log-roll").tooltip(
                    "Roll the dice. The text in the box, if any, is the caption.")
                ui.space()
                ui.button(icon="send", on_click=self._send).props(
                    f"flat dense round color={pal.button}").mark("log-send").tooltip(
                    "Send (Enter)")
        self._draw_log()

    def _draw_log(self) -> None:
        """Draw the entries of the Log, the oldest first, and scroll to the newest.

        If entries are on the page, add only the entries that are newer. Else draw
        all of them.
        """
        entries = self.log.entries(self.table.id)
        shown = self._log_version or 0
        self._log_version = entries[-1].id if entries else 0
        names: dict[int, str] = {}
        if shown and entries and entries[-1].id >= shown:
            entries = [entry for entry in entries if entry.id > shown]
        else:
            self.log_list.clear()
        with self.log_list:
            if not entries and not shown:
                ui.label("Nothing yet. Messages and rolls show here, for each "
                         "member.").classes("text-sm opacity-70").mark("log-empty")
            for entry in entries:
                if entry.user_id not in names:
                    names[entry.user_id] = _username(self.tables, entry.user_id)
                _log_entry(entry, names[entry.user_id], self.pal,
                           mine=entry.user_id == self.user_id,
                           storyteller=entry.user_id == self.table.storyteller_id)
        self.log_area.scroll_to(percent=1.0)

    def _log_write(self, write: Callable[[], LogEntry]) -> None:
        """Call `write`, clear the text box and draw the Log.

        ⚠ Ask `access()` first. The store asks again, but the page must stop here.
        """
        if self.gone:
            return
        if self.tables.access(self.user_id, self.table.id) is None:
            ui.notify(GONE, type="warning")
            self.stop()
            return
        try:
            write()
        except (TableLogError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
            return
        self.log_text.set_value("")
        self._draw_log()

    def _send(self) -> None:
        text = self.log_text.value or ""
        if not text.strip():
            return
        self._log_write(lambda: self.log.post(self.user_id, self.table.id, text))

    def _roll(self) -> None:
        value = self.log_count.value
        count = int(value) if value is not None and float(value).is_integer() else 0
        self._log_write(lambda: self.log.roll(
            self.user_id, self.table.id, count, self.log_text.value or ""))

    def _draw_members(self, copies: list[CharacterRow]) -> None:
        """Draw MEMBERS: the Storyteller, the players, and the members who watch."""
        pal = self.pal
        members = self.tables.members(self.table.id)
        players = {row.owner_id for row in copies}
        self.members_panel.clear()
        with self.members_panel:
            with ui.column().classes("w-full gap-1").mark("table-members"):
                _heading(pal, f"MEMBERS ({len(members) + 1})")
                with ui.row().classes("gap-1"):
                    ui.chip(f"{_username(self.tables, self.table.storyteller_id)} · "
                            "Storyteller", icon="star").props("outline dense")
                    for member in members:
                        name = _username(self.tables, member)
                        if member in players:
                            ui.chip(name, icon="person").props("outline dense")
                        else:
                            ui.chip(f"{name} · watching", icon="visibility").props(
                                "outline dense")

    def _draw_st(self) -> None:
        """Draw the ST tab: the join code and the requests."""
        pal = self.pal
        self.st_panel.clear()
        with self.st_panel:
            with ui.column().classes("w-full gap-0").mark("table-code"):
                _heading(pal, "JOIN CODE")
                ui.label(self.table.join_code).classes("text-2xl font-mono font-bold")
                ui.label("Give this code to your players. You approve each request "
                         "below.").classes("text-xs opacity-70")
            _requests(self.tables, self.store, self.book, self.user_id, self.table,
                      self._approve, self._reject)

    def _still_storyteller(self) -> bool:
        """⚠ Each handler asks again. The Storyteller can delete the campaign on a
        second device while this page is open."""
        if self.tables.access(self.user_id, self.table.id) == STORYTELLER:
            return True
        ui.notify("You are not the Storyteller of this campaign.", type="negative")
        return False

    def _approve(self, request_id: int) -> None:
        if not self._still_storyteller():
            return
        try:
            self.tables.approve(self.user_id, request_id)
        except (TableStoreError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
        else:
            ui.notify("Approved.", type="positive")
        self.refresh_all()

    def _reject(self, request_id: int) -> None:
        if not self._still_storyteller():
            return
        try:
            self.tables.reject(self.user_id, request_id)
        except TableStoreError as exc:
            ui.notify(str(exc), type="warning")
        self.refresh_all()


# --------------------------------------------------------------------------- #
# Widgets
# --------------------------------------------------------------------------- #


def _heading(pal, text: str) -> None:
    ui.label(text).classes("text-xs font-bold tracking-widest").style(
        f"color:{pal.accent}")


def _health_box(mark, pal, size: float) -> ui.label:
    """One health box. It shows the mark, and has no handler."""
    return ui.label(mark.value if mark else "").style(
        f"width:{size}rem;height:{size}rem;line-height:{size}rem;text-align:center;"
        f"font-size:{size * 0.6}rem;font-weight:700;border-radius:3px;"
        f"border:1px solid {_BORDER};background:{_GOLD if mark else _WHITE};"
        f"color:{_MARK_COLOR[mark] if mark else pal.accent}")


def _dots(filled: int, total: int, size: float) -> list[ui.element]:
    boxes = []
    with ui.row().classes("gap-0.5 no-wrap"):
        for i in range(total):
            boxes.append(ui.element("div").style(
                f"width:{size}rem;height:{size}rem;border-radius:2px;"
                f"border:1px solid {_BORDER};background:{_GOLD if i < filled else _WHITE}"))
    return boxes


def _track(label: str, marker: str, total: int, filled: int,
           on_click: Callable[[int], None]) -> None:
    """A dot track with a label. A click on box i calls `on_click(i)`."""
    with ui.row().classes("w-full items-center no-wrap gap-1"):
        ui.label(label).classes("text-xs shrink-0").mark(f"{marker}-label")
        with ui.row().classes("gap-0.5 flex-wrap"):
            for i in range(total):
                ui.element("div").classes("cursor-pointer select-none").style(
                    f"width:.9rem;height:.9rem;border-radius:2px;"
                    f"border:1px solid {_BORDER};"
                    f"background:{_GOLD if i < filled else _WHITE}").mark(
                    f"{marker}-{i}").on("click", lambda _=None, i=i: on_click(i))


def _fatigue(points: int, difficulties: list[str], pal,
             step: Callable[[int], None]) -> None:
    """The armour fatigue counter, with − and +. `step` takes −1 or +1.
    `difficulties` names the fatigue roll difficulty of each worn piece."""
    with ui.row().classes("w-full items-center no-wrap gap-1"):
        text = f"Fatigue {points}" + (f" (-{points} to all actions)" if points else "")
        ui.label(text).classes("text-xs shrink-0").mark("you-fatigue-label")
        ui.button(icon="remove", on_click=lambda: step(-1)).props(
            f"flat dense round size=xs color={pal.button}").mark("you-fatigue-minus")
        ui.button(icon="add", on_click=lambda: step(1)).props(
            f"flat dense round size=xs color={pal.button}").mark("you-fatigue-plus")
        if difficulties:
            ui.label("Roll difficulty: " + ", ".join(difficulties)).classes(
                "text-xs opacity-70 truncate")


def _mote_bar(label: str, key: str, spent: int, cap: int, pal,
              set_spent: Callable[[int], None]) -> None:
    """One pool as a bar of what is left, with − and + at its ends. A click on the
    bar opens a box: type an amount, then Spend, Regain or Full.

    `set_spent` takes the new number of spent motes. The engine clamps it.
    """
    left = cap - spent
    pct = 0 if cap == 0 else 100 * left / cap
    with ui.row().classes("w-full items-center no-wrap gap-1"):
        ui.label(label).classes("text-xs w-16 shrink-0")
        ui.button(icon="remove", on_click=lambda: set_spent(spent + 1)).props(
            f"flat dense round size=xs color={pal.button}").mark(
            f"you-motes-{key}-minus").tooltip("Spend 1")
        with ui.element("div").classes("relative flex-1 cursor-pointer rounded").style(
                f"height:1.25rem;border:1px solid {_BORDER};background:{_WHITE}"):
            ui.element("div").classes("absolute inset-y-0 left-0 rounded-sm").style(
                f"width:{pct}%;background:{_GOLD}")
            ui.label(f"{left}/{cap}").classes(
                "absolute inset-0 text-center text-xs font-bold").style(
                "line-height:1.2rem").mark(f"you-motes-{key}-left")
            ui.tooltip("Click to spend or regain an amount")
            with ui.menu().props("anchor='bottom middle' self='top middle'") as menu:
                with ui.column().classes("p-2 gap-1"):
                    amount = ui.number(f"{label}", value=None, min=0, format="%d").props(
                        "dense outlined autofocus").classes("w-32").mark(
                        f"you-motes-{key}-amount")

                    def apply(sign: int) -> None:
                        menu.close()
                        set_spent(spent + sign * int(amount.value or 0))

                    amount.on("keydown.enter", lambda: apply(1))
                    with ui.row().classes("gap-1 no-wrap"):
                        ui.button("Spend", on_click=lambda: apply(1)).props(
                            f"dense no-caps size=sm color={pal.button}").mark(
                            f"you-motes-{key}-spend")
                        ui.button("Regain", on_click=lambda: apply(-1)).props(
                            "dense no-caps size=sm outline").mark(f"you-motes-{key}-regain")
                        ui.button("Full", on_click=lambda: (menu.close(), set_spent(0))) \
                            .props("dense no-caps size=sm flat").mark(f"you-motes-{key}-full")
        ui.button(icon="add", on_click=lambda: set_spent(spent - 1)).props(
            f"flat dense round size=xs color={pal.button}").mark(
            f"you-motes-{key}-plus").tooltip("Regain 1")


def _log_entry(entry: LogEntry, name: str, pal, *, mine: bool, storyteller: bool) -> None:
    """One entry of the Log: the name, the time, the text, and the dice of a roll.

    ⚠ `ui.label` only. A member types the text.
    """
    with ui.column().classes("w-full gap-0 px-2 py-1 rounded").style(
            f"background:{'#c9a22722' if mine else 'transparent'}").mark(
            f"log-entry-{entry.id}"):
        with ui.row().classes("w-full items-baseline gap-1 no-wrap min-w-0"):
            ui.label(name).classes("text-xs font-bold truncate min-w-0").style(
                f"color:{pal.accent if storyteller else pal.ink}").mark(
                f"log-name-{entry.id}")
            if storyteller:
                ui.icon("star", size="0.7rem").style(f"color:{pal.accent}").mark(
                    f"log-star-{entry.id}")
            ui.label(time.strftime("%H:%M", time.localtime(entry.at))).classes(
                "text-xs opacity-40 shrink-0")
        if entry.text:
            ui.label(entry.text).classes(
                "text-sm leading-snug whitespace-pre-wrap break-words").mark(
                f"log-body-{entry.id}")
        if entry.roll is not None:
            with ui.row().classes("items-center gap-1 no-wrap"):
                ui.icon("casino", size="1rem").style(f"color:{pal.accent}")
                ui.label(f"{entry.roll.count} {'die' if entry.roll.count == 1 else 'dice'}"
                         f" → {entry.roll.summary}").classes(
                    "text-sm font-bold").mark(f"log-roll-{entry.id}")
            ui.label(" ".join(str(f) for f in sorted(entry.roll.faces, reverse=True))
                     ).classes("text-xs font-mono opacity-60 break-words").mark(
                f"log-faces-{entry.id}")


def _other_row(shown: _Shown, player: str, *, mine: bool) -> None:
    """One copy that the viewer does not play now, read-only (R3): the name, the
    player, the identity line, the health strip, the motes and the Willpower.

    ⚠ No element here has a handler. The Storyteller cannot mark a player's row.
    """
    row, character = shown.row, shown.character
    if character is None:
        with ui.row().classes("w-full px-2 py-1.5 rounded").style(
                "background:#00000008").mark(f"other-{row.id}"):
            ui.label(f"(unreadable: {row.id})").classes("text-sm opacity-70")
        return
    cv = viewmod.build_party_card_view(shown.ruleset, character)
    cpal = theme.palette(character.exalt_type)
    cur = character.play or PlayState()
    n = len(cv.play.health_boxes)
    marks = list(cur.health)[:n] + [None] * max(0, n - len(cur.health))
    with ui.row().classes(
            f"w-full no-wrap gap-0 rounded overflow-hidden {cpal.card_soft}").mark(
            f"other-{row.id}"):
        ui.element("div").classes("w-1 self-stretch").style(f"background:{cpal.accent}")
        with ui.column().classes("gap-1 px-2 py-1.5 min-w-0 flex-1"):
            with ui.row().classes("w-full items-baseline justify-between no-wrap gap-2"):
                ui.label(cv.name).classes("text-sm font-bold truncate").style(
                    f"color:{cpal.accent}")
                ui.label(player + (" (you)" if mine else "")).classes(
                    "text-xs opacity-60 shrink-0")
            ui.label(cv.identity_line).classes("text-xs opacity-70 truncate -mt-1")
            with ui.row().classes("gap-0.5"):
                for i, mark in enumerate(marks):
                    _health_box(mark, cpal, 0.95).mark(f"other-health-{row.id}-{i}")
            spent_p, spent_pp = viewmod.spent_motes(cv.play, cur)
            wp_left = cv.play.willpower_max - cur.willpower_spent
            with ui.row().classes("items-center gap-x-3 gap-y-0 text-xs"):
                if cv.play.single_pool:
                    ui.label(f"Motes {cv.play.peripheral_max - spent_pp}/"
                             f"{cv.play.peripheral_max}")
                elif cv.play.personal_max or cv.play.peripheral_max:
                    ui.label(f"Motes {cv.play.personal_max - spent_p}/"
                             f"{cv.play.personal_max} · "
                             f"{cv.play.peripheral_max - spent_pp}/"
                             f"{cv.play.peripheral_max}")
                with ui.row().classes("items-center gap-1 no-wrap"):
                    ui.label(f"WP {wp_left}/{cv.play.willpower_max}")
                    _dots(wp_left, cv.play.willpower_max, 0.7)


def _requests(tables: TableStore, store: CharacterStore, book: RuleSet, user_id: int,
              table: TableRow, approve: Callable[[int], None],
              reject: Callable[[int], None]) -> None:
    """Draw the requests of `table` for its Storyteller, with what each base carries."""
    pal = theme.palette(None)
    requests = tables.pending(user_id, table.id)
    with ui.column().classes("w-full gap-2").mark("table-requests"):
        _heading(pal, f"REQUESTS ({len(requests)})")
        if not requests:
            ui.label("No requests are waiting.").classes("text-sm opacity-70")
        for request in requests:
            who = _username(tables, request.user_id)
            base = store.row(request.base_id) if request.base_id else None
            with ui.card().classes(f"w-full px-2 py-1.5 gap-0 {pal.card_soft}").mark(
                    f"table-request-{request.id}"):
                ui.label(who).classes("text-sm font-bold")
                if base is None:
                    ui.label("Asks to watch.").classes("text-xs opacity-80")
                else:
                    _request_base(store, book, base)
                with ui.row().classes("gap-1 justify-end w-full"):
                    ui.button("Approve", icon="check",
                              on_click=lambda _=None, r=request.id: approve(r)).props(
                        f"dense no-caps size=sm color={pal.button}").mark(
                        f"table-approve-{request.id}")
                    ui.button("Reject", icon="close",
                              on_click=lambda _=None, r=request.id: reject(r)).props(
                        "flat dense no-caps size=sm color=negative").mark(
                        f"table-reject-{request.id}")


def _request_base(store: CharacterStore, book: RuleSet, base: CharacterRow) -> None:
    """Draw what a request brings: the base and the homebrew that it carries."""
    shown = chrome.entry(store, book, base)
    ui.label(f"Asks to bring {shown.name} ({shown.kind}).").classes("text-xs opacity-80")
    try:
        summary = carried_summary(store.load(base))
    except Exception:                               # noqa: BLE001 - the entry says unreadable
        summary = None
    if summary:
        ui.label(summary).classes("text-xs")
