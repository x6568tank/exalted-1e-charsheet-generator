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
  * The ST tools are step 5: Grant XP and Unlock (`server/table_st.py`), remove
    member, new code and delete campaign. A member leaves from the ⋮ menu.
  * The house rules are step 6 (section 5, Q2): the TABLE-WIDE switches in the ST
    tab, and the PER-CHARACTER permissions of each copy in a dialog.
  * Add a character is step 6b (section 14): a member brings a locked base, or
    creates a draft for the campaign. The ST tab lists the drafts.
  * The homebrew of the campaign is step 7 (section 14): the Homebrew button opens
    `server/table_custom.py`. The request card says what an approval adds, and the
    ST tab lists the HOMEBREW REQUESTS.
  * The roster is step 8 (section 15.3): ALLIES and ENEMIES below PARTY. The
    Storyteller sees the full card of each entry and each NPC, with the Enemy / Ally
    switch. A player sees each ally as a name and a health track, and no enemy.
    The Notes tab holds the private notes of the viewer (Q8, Q9).

⚠ The page of a player is built from `view.AllyView` for each ally, and gets
nothing of an enemy. An element that is hidden with CSS still goes to the browser.
An NPC is a character of the Storyteller (`is_npc`), thus THE OTHERS never holds one.

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
from dataclasses import dataclass, replace
import time

from nicegui import app, ui

from ..engine import derive, dice, play as engineplay, validate
from ..models.adversary import ALLY, ENEMY, Adversary
from ..models.character import Character, HouseRules, PlayState
from ..models.party import Party
from ..models.rules import RuleSet
from ..ui import adversaries as adversaries_mod
from ..ui import play as play_mod
from ..ui import saving, theme
from ..ui import view as viewmod
from . import auth, chrome, db, nav
from .characters import CharacterRow, CharacterStore
from .quota import QuotaExceeded
from .rulesets import Rulesets
from .session import SessionRegistry
from .table_custom import custom_url, register_table_custom
from .table_homebrew import TableHomebrew, TableHomebrewError
from .table_log import MAX_TEXT, LogEntry, TableLog, TableLogError
from .table_notes import MAX_NOTES, TableNotes, TableNotesError
from .table_roster import TableRoster
from .table_st import MAX_GRANT, MAX_NOTE, Award, TableStoryteller
from .tables import STORYTELLER, TableRow, TableStore, TableStoreError

TABLE_PATH = chrome.TABLE_PATH

# The interval of the poll, in seconds. One poll reads the database and one file
# status for each character, thus it costs little.
POLL_SECONDS = 2.0

# The value of "Open as" for a viewer who opens the campaign with no character.
SPECTATE = "spectate"

# The number of awards that the ST tab shows, the newest first. A design choice.
AWARDS_SHOWN = 10

_GOLD, _WHITE, _BORDER = play_mod._GOLD, play_mod._WHITE, play_mod._BORDER
_MARK_COLOR = play_mod._MARK_COLOR

GONE = "You are no longer in this campaign."
COPY_GONE = "That character is no longer in this campaign."


def _username(tables: TableStore, user_id: int) -> str:
    return db.username_for(tables.db_path, user_id) or "(a deleted account)"


def _open_as_key(table_id: str) -> str:
    """The key in `app.storage.user` of the "Open as" choice for `table_id`."""
    return f"table-open-as:{table_id}"


def register_table_page(tables: TableStore, store: CharacterStore, rulesets: Rulesets,
                        sessions: SessionRegistry,
                        current_user_id: Callable[[], int | None],
                        log: TableLog, catalog: dict[str, Adversary] | None = None) -> None:
    """Register `/table/<id>` and `/table/<id>/custom`.

    `rulesets` gives the RuleSet of a character that has no live context. `sessions`
    is the character registry of `server/home.py`. `current_user_id` returns the
    account of the request. `log` reads and writes the Log of each table. `catalog`
    is the adversary templates (`rules_db.load_adversary_catalog`).
    """
    storyteller = TableStoryteller(tables, store, sessions, log)
    homebrew = TableHomebrew(tables)
    # ⚠ ONE roster store for the process: it holds the live roster of each table.
    roster = TableRoster(tables)
    notes = TableNotes(tables)
    register_table_custom(tables, store, rulesets, homebrew, current_user_id)

    @ui.page(TABLE_PATH + "/{table_id}")
    def table_page(table_id: str) -> None:
        user_id = chrome.require_account(current_user_id)
        # ⚠ Before anything that reads the table.
        role = tables.access(user_id, table_id)
        table = tables.table(table_id) if role is not None else None
        if table is None:
            chrome.table_not_found()
            return
        _TableView(tables, store, rulesets, sessions, log, storyteller, homebrew,
                   user_id, table, roster=roster, notes=notes,
                   catalog=catalog or {}).build()


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

    def __init__(self, tables: TableStore, store: CharacterStore, rulesets: Rulesets,
                 sessions: SessionRegistry, log: TableLog,
                 storyteller: TableStoryteller, homebrew: TableHomebrew, user_id: int,
                 table: TableRow, *, roster: TableRoster, notes: TableNotes,
                 catalog: dict[str, Adversary]) -> None:
        self.tables = tables
        self.roster = roster
        self.notes = notes
        self.catalog = catalog
        self.log = log
        self.storyteller = storyteller
        self.homebrew = homebrew
        self.store = store
        # A copy with no live context reads under the homebrew of the campaign.
        self.rulesets = rulesets
        self.ruleset = rulesets.for_table(table.id)
        self.sessions = sessions
        self.user_id = user_id
        self.table = table
        self.is_st = table.storyteller_id == user_id
        self.pal = theme.palette(None)
        self.gone = False
        self._structure = None
        self._digests: dict[str, object] = {}
        self._sides_key = None
        self._log_version = None
        # The keys of the compact cards that show their stats: "adv:<id>", "npc:<id>".
        self._expanded: set[str] = set()

    # ---- reads -------------------------------------------------------------- #

    def copies(self) -> list[CharacterRow]:
        return self.tables.characters(self.table.id)

    def mine(self, copies: list[CharacterRow]) -> list[CharacterRow]:
        return [row for row in copies if row.owner_id == self.user_id]

    def is_npc(self, row: CharacterRow) -> bool:
        """True for a character of the Storyteller of the table: an NPC (human,
        2026-09-22). ⚠ Keyed on the owner, which the page cannot edit."""
        return row.owner_id == self.table.storyteller_id

    def party_rows(self, copies: list[CharacterRow]) -> list[CharacterRow]:
        """Return the copies of the players: each copy that is not an NPC."""
        return [row for row in copies if not self.is_npc(row)]

    def npcs(self, copies: list[CharacterRow]) -> list[CharacterRow]:
        return [row for row in copies if self.is_npc(row)]

    def sides_key(self, copies: list[CharacterRow]):
        """What decides ALLIES and ENEMIES: the roster, the sides and each NPC."""
        chosen = self.chosen(copies)
        chosen_id = chosen.id if chosen is not None else None
        return (self.roster.version(self.table.id),
                tuple(sorted(self.tables.npc_sides(self.table.id).items())),
                tuple((row.id, self.digest(row)) for row in self.npcs(copies)
                      if row.id != chosen_id),
                chosen_id)

    def chosen(self, copies: list[CharacterRow]) -> CharacterRow | None:
        """Return the copy that the viewer opens as, or None to spectate. For the
        Storyteller, None is the Storyteller view.

        The choice is in `app.storage.user`. A choice that is not a copy of the
        viewer in the table gives the first copy of the viewer. ⚠ The Storyteller
        with no choice gets the Storyteller view (human, 2026-09-24): an NPC in YOU
        PLAY has no switch, and the other NPCs lose their live controls.
        """
        mine = self.mine(copies)
        stored = app.storage.user.get(_open_as_key(self.table.id))
        if stored == SPECTATE or (self.is_st and stored is None):
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
            return _Shown(row, self.store.load(row), self.ruleset)
        except Exception:                           # noqa: BLE001 - show it as unreadable
            return _Shown(row, None, self.ruleset)

    def read_own(self, row: CharacterRow) -> _Shown:
        """Read the copy that the viewer opens as, through its live context. Build
        the context if it is absent: the viewer owns the character."""
        try:
            ctx = self.sessions.ctx_for(row.id)
        except Exception:                           # noqa: BLE001 - the factory could not read it
            return _Shown(row, None, self.ruleset)
        return _Shown(row, ctx["char"], ctx["ruleset"])

    def digest(self, row: CharacterRow):
        ctx = self.sessions.peek(row.id)
        if ctx is not None:
            return saving.character_digest(ctx["char"])
        return _file_digest(self.store, row)

    def structure(self, copies: list[CharacterRow]):
        """What decides the layout: the copies, the members and the requests."""
        pending = (tuple(r.id for r in self.tables.pending(self.user_id, self.table.id))
                   + tuple(f"homebrew-{p.id}" for p in
                           self.homebrew.proposals(self.user_id, self.table.id))
                   if self.is_st else ())
        drafts = (tuple(r.id for r in self.tables.drafts(self.table.id))
                  if self.is_st else ())
        return (tuple(row.id for row in copies), tuple(self.tables.members(self.table.id)),
                pending, drafts)

    # ---- the page ----------------------------------------------------------- #

    def build(self) -> None:
        pal = self.pal
        ui.query("body").style(f"background:{pal.bg};color:{pal.ink}")
        # The page holds work in progress, thus the wiki opens in a new tab.
        drawer = chrome.nav_drawer(pal, live=True)
        with ui.header().classes("items-center justify-between px-4 py-1").style(
                f"background:{pal.accent}"):
            with ui.row().classes("items-center gap-1 no-wrap min-w-0"):
                chrome.menu_button(drawer)
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
                self.sides = ui.column().classes("w-full gap-2")
            with ui.element("div").classes("flex-1 min-w-0 min-h-[16rem] flex flex-col"):
                self._board()
            with ui.element("div").classes(
                    "w-full md:w-[19rem] md:shrink-0 flex flex-col gap-1 md:overflow-y-auto"):
                self._right_rail()

            # ⚠ The dialogs of the roster go here. A dialog in an element that a
            # repaint clears is deleted, and the poll repaints the rails.
            self.dialog_host = ui.element("div")

        copies = self.copies()
        self._structure = self.structure(copies)
        self._draw_top(copies)
        self._draw_rail(copies)
        self._draw_sides(copies)
        ui.timer(POLL_SECONDS, self.poll)

    def refresh_all(self) -> None:
        copies = self.copies()
        self._structure = self.structure(copies)
        self._draw_top(copies)
        self._draw_rail(copies)
        self._draw_sides(copies)
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
        players = self.party_rows(copies)
        chosen = self.chosen(copies)
        shown = players + ([chosen] if chosen is not None and self.is_npc(chosen) else [])
        if {row.id: self.digest(row) for row in shown} != self._digests:
            self._draw_rail(copies)
        if self.sides_key(copies) != self._sides_key:
            self._draw_sides(copies)

    # ---- the top bar -------------------------------------------------------- #

    def _draw_top(self, copies: list[CharacterRow]) -> None:
        self.top_right.clear()
        with self.top_right:
            mine = self.mine(copies)
            if mine:
                chosen = self.chosen(copies)
                characters = {row.id: self.read(row).character for row in mine}
                options = {SPECTATE: "Storyteller"} if self.is_st else {}
                options |= {row_id: "Open as: " + (c.name if c is not None and c.name
                                                   else "(unnamed)")
                            for row_id, c in characters.items()}
                if not self.is_st:
                    options[SPECTATE] = "Spectate"
                ui.select(options, value=chosen.id if chosen else SPECTATE,
                          on_change=lambda e: self._open_as(e.value)).props(
                    "dense dark borderless options-dense").classes(
                    "text-white w-56").mark("table-open-as")
            with ui.button(icon="construction",
                           on_click=lambda: ui.navigate.to(custom_url(self.table.id))
                           ).props("flat round color=white").mark("table-homebrew"):
                ui.tooltip("Campaign homebrew")
            if self.is_st:
                count = (len(self.tables.pending(self.user_id, self.table.id))
                         + len(self.homebrew.proposals(self.user_id, self.table.id)))
                with ui.button(icon="how_to_reg",
                               on_click=lambda: self.tabs.set_value("st")).props(
                        "flat round color=white").mark("table-requests-button"):
                    if count:
                        ui.badge(str(count), color="red").props("floating").mark(
                            "table-requests-badge")
                    ui.tooltip("Requests")
            with ui.button(icon="more_vert").props("flat round color=white"):
                with ui.menu():
                    if not self.is_st:
                        ui.menu_item("Leave campaign", on_click=self._confirm_leave) \
                            .mark("table-leave")
                    ui.menu_item(nav.logout_label(auth.current_username()),
                                 on_click=lambda: ui.navigate.to("/logout")) \
                        .mark("top-bar-logout")

    def _open_as(self, value: str) -> None:
        app.storage.user[_open_as_key(self.table.id)] = value
        copies = self.copies()
        self._draw_rail(copies)
        self._draw_sides(copies)

    # ---- the left rail ------------------------------------------------------ #

    def _draw_rail(self, copies: list[CharacterRow]) -> None:
        """Draw PARTY: YOU PLAY, then THE OTHERS. Record the digest of each copy
        that PARTY shows.

        ⚠ THE OTHERS holds the copies of the players only. An NPC is in ALLIES or
        ENEMIES (`_draw_sides`). The Storyteller can open as an NPC: YOU PLAY.
        """
        pal = self.pal
        chosen = self.chosen(copies)
        players = self.party_rows(copies)
        self.rail.clear()
        with self.rail:
            with ui.row().classes("w-full items-center justify-between no-wrap"):
                chrome.section_label(pal, "PARTY", len(players))
                ui.button("Add a character", icon="person_add",
                          on_click=self._add_character).props(
                    "flat dense no-caps size=sm").mark("table-add-character")
            if not players and chosen is None:
                ui.label("No characters yet. An approved request that brings a "
                         "character puts its campaign copy here.").classes(
                    "text-sm opacity-70")
            if chosen is not None:
                _heading(pal, "YOU PLAY")
                self._you_play(self.read_own(chosen))
            others = [row for row in players if chosen is None or row.id != chosen.id]
            if others and chosen is not None:
                _heading(pal, "THE OTHERS")
            for row in others:
                _other_row(self.read(row), _username(self.tables, row.owner_id),
                           mine=row.owner_id == self.user_id, npc=False)
        shown = players + ([chosen] if chosen is not None and self.is_npc(chosen) else [])
        self._digests = {row.id: self.digest(row) for row in shown}

    # ---- ALLIES and ENEMIES ------------------------------------------------- #

    def _draw_sides(self, copies: list[CharacterRow]) -> None:
        """Draw ALLIES and ENEMIES. Record what decides them (`sides_key`)."""
        self._sides_key = self.sides_key(copies)
        self.sides.clear()
        with self.sides:
            if self.is_st:
                self._st_sides(copies)
            else:
                self._player_allies(copies)

    def _player_allies(self, copies: list[CharacterRow]) -> None:
        """ALLIES for a player: a name and a health track for each ally (R7).

        ⚠ Build each row from a `view.AllyView`. Nothing of an enemy is read here.
        """
        sides = self.tables.npc_sides(self.table.id)
        views = []
        for row in self.npcs(copies):
            if sides.get(row.id, ENEMY) != ALLY:
                continue
            shown = self.read(row)
            if shown.character is not None:
                views.append(viewmod.character_ally_view(shown.ruleset, shown.character,
                                                         row.id))
        views += self.roster.allies(self.user_id, self.table.id)
        if not views:
            return
        with ui.column().classes("w-full gap-1").mark("table-allies"):
            _heading(self.pal, f"ALLIES ({len(views)})")
            for view in views:
                _ally_row(view, self.pal)

    def _st_sides(self, copies: list[CharacterRow]) -> None:
        """ALLIES and ENEMIES for the Storyteller: each NPC as a read-only row and
        each roster entry as its full card, each with the Enemy / Ally switch."""
        chosen = self.chosen(copies)
        sides = self.tables.npc_sides(self.table.id)
        npcs = [row for row in self.npcs(copies) if chosen is None or row.id != chosen.id]
        party = self._party()
        for side, title in ((ALLY, "ALLIES"), (ENEMY, "ENEMIES")):
            rows = [row for row in npcs if sides.get(row.id, ENEMY) == side]
            entries = [(i, a) for i, a in enumerate(party.adversaries) if a.side == side]
            with ui.column().classes("w-full gap-2").mark(f"table-{side}"):
                with ui.row().classes("w-full items-center justify-between no-wrap"):
                    _heading(self.pal, f"{title} ({len(rows) + len(entries)})")
                    ui.button(icon="add", on_click=lambda _=None, s=side:
                              self._add_entry(s)).props(
                        "flat dense round size=sm").mark(f"table-add-{side}").tooltip(
                        "Add from the catalogue")
                if not rows and not entries:
                    ui.label("Players see each ally as a name and a health track."
                             if side == ALLY else "Only you see the enemies.").classes(
                        "text-xs opacity-60")
                for row in rows:
                    self._npc_row(row, side)
                for index, entry in entries:
                    key = f"adv:{entry.id}"
                    adversaries_mod.roster_card(
                        self.ruleset, self._party, index, entry, self.pal,
                        self._roster_changed, dialog_host=self.dialog_host,
                        expanded=key in self._expanded,
                        on_toggle=lambda k=key: self._toggle(k),
                        extra=lambda e=entry: _side_switch(
                            e.side, f"adv-side-{e.id}",
                            lambda value, i=e.id: self._set_entry_side(i, value)))

    def _toggle(self, key: str) -> None:
        """Show or hide the stats of the compact card `key`."""
        self._expanded ^= {key}
        self._draw_sides(self.copies())

    def _npc_row(self, row: CharacterRow, side: str) -> None:
        """One NPC in ALLIES or ENEMIES for the Storyteller: the switch, and the live
        controls of YOU PLAY. A compact row has the health boxes and one line of
        Willpower and motes. ⚠ The Storyteller owns the NPC: R3 does not apply."""
        key = f"npc:{row.id}"
        expanded = key in self._expanded

        def header() -> None:
            _side_switch(side, f"npc-side-{row.id}",
                         lambda value: self._set_npc_side(row.id, value))
            ui.button(icon="expand_less" if expanded else "expand_more",
                      on_click=lambda: self._toggle(key)).props(
                "flat dense round size=sm").mark(f"npc-toggle-{row.id}").tooltip(
                "Hide the trackers" if expanded else "Show the trackers")

        self._you_play(self.read_own(row), prefix=f"npc-{row.id}", extra=header,
                       compact=not expanded, outline=False)

    def _party(self) -> Party:
        """Return the live roster. ⚠ A viewer who is not the Storyteller now gets an
        empty roster that no file holds: a change to it goes nowhere."""
        try:
            return self.roster.party(self.user_id, self.table.id)
        except TableStoreError:
            return Party(id=self.table.id)

    def _roster_changed(self) -> None:
        """Save the live roster, and draw ALLIES and ENEMIES. Each change of the
        roster calls this."""
        try:
            self.roster.save(self.user_id, self.table.id)
        except (TableStoreError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
        self._draw_sides(self.copies())

    def _add_entry(self, side: str) -> None:
        if not self._still_storyteller():
            return

        def adjust(entry: Adversary) -> None:
            entry.side = side

        # ⚠ A closed dialog stays in its element. One dialog at a time.
        self.dialog_host.clear()
        with self.dialog_host:
            adversaries_mod.open_add_dialog(
                self.ruleset, self.catalog, self._party, self._roster_changed,
                adjust=adjust, title="Add an ally" if side == ALLY else "Add an enemy",
                pal=self.pal)

    def _set_entry_side(self, entry_id: str, side: str) -> None:
        if not self._still_storyteller():
            return
        for entry in self._party().adversaries:
            if entry.id == entry_id:
                entry.side = side
        self._roster_changed()

    def _set_npc_side(self, character_id: str, side: str) -> None:
        if not self._still_storyteller():
            return
        try:
            self.tables.set_npc_side(self.user_id, self.table.id, character_id, side)
        except (TableStoreError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
        self._draw_sides(self.copies())

    def _add_character(self) -> None:
        """A dialog: bring one of the viewer's locked bases, or create a character
        for the campaign (section 14, step 6b). Each goes to the Storyteller."""
        bases = {}
        for row in self.store.list_for(self.user_id):
            if row.is_copy:
                continue
            try:
                character = self.store.load(row)
            except Exception:                       # noqa: BLE001 - skip a file that does not read
                continue
            if character.chargen_locked:
                bases[row.id] = character.name or "(unnamed)"
        with ui.dialog() as dialog, ui.card().classes(
                f"w-[28rem] max-w-full p-4 gap-2 {self.pal.card_solid}"):
            ui.label("Add a character").classes("text-base font-bold")
            side = None
            if self.is_st:
                # The Storyteller picks the side of an NPC here (human, 2026-09-24).
                ui.label("Your characters are NPCs. Players see an ally as a name "
                         "and a health track, and do not see an enemy.").classes("text-xs")
                side = ui.toggle({ENEMY: "Enemy", ALLY: "Ally"}, value=ENEMY).props(
                    "dense no-caps").mark("add-character-side")
            else:
                ui.label("The Storyteller approves each character. An approval makes "
                         "a campaign copy.").classes("text-xs")
            if bases:
                choice = ui.select(bases, value=next(iter(bases)),
                                   label="Bring a finished character").classes(
                    "w-full").mark("add-character-base")
                ui.button("Add" if self.is_st else "Send request", icon="send",
                          on_click=lambda: self._bring(
                              dialog, choice.value, side.value if side else None)).props(
                    f"dense no-caps color={self.pal.button}").mark("add-character-send")
            else:
                ui.label("You have no finished character to bring.").classes(
                    "text-sm opacity-70")
            ui.separator()
            ui.label("Or make one for this campaign. It is built under the house "
                     "rules of the campaign, and Finish & Lock sends it to the "
                     "Storyteller.").classes("text-xs")
            ui.button("Create a character", icon="note_add",
                      on_click=lambda: self._create(
                          dialog, side.value if side else None)).props(
                f"outline dense no-caps color={self.pal.button}").mark(
                "add-character-create")
            with ui.row().classes("w-full justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
        dialog.open()

    def _bring(self, dialog, base_id: str | None, side: str | None = None) -> None:
        try:
            request = self.tables.bring(self.user_id, self.table.id, base_id, side=side)
        except TableStoreError as exc:
            ui.notify(str(exc), type="warning")
            return
        dialog.close()
        ui.notify("Added to the campaign." if request.approved else
                  "Request sent. It waits for the Storyteller.",
                  type="positive" if request.approved else "info")
        self.refresh_all()

    def _create(self, dialog, side: str | None = None) -> None:
        try:
            row = self.tables.start_draft(self.user_id, self.table.id, side=side)
        except (TableStoreError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
            return
        dialog.close()
        ui.navigate.to(chrome.character_url(row.id))

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
        copies = self.copies()
        self._draw_rail(copies)
        if self.is_npc(row):
            self._draw_sides(copies)

    def _you_play(self, shown: _Shown, *, prefix: str = "you",
                  extra: Callable[[], None] | None = None, compact: bool = False,
                  outline: bool = True) -> None:
        """The copy of the viewer, with live controls (R2).

        `prefix` starts each marker. `extra` draws more controls in the header.
        `compact` draws the health boxes and one line of Willpower and motes only.
        """
        row, character = shown.row, shown.character
        with ui.column().classes("w-full gap-0").mark(f"{prefix}-play"):
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
                    f"outline:2px solid {cpal.accent}" if outline else ""):
                ui.element("div").classes("w-1 self-stretch").style(
                    f"background:{cpal.accent}")
                with ui.column().classes("gap-1.5 px-2 py-2 min-w-0 flex-1"):
                    with ui.row().classes(
                            "w-full items-baseline justify-between no-wrap gap-2"):
                        ui.label(cv.name).classes("text-sm font-bold truncate").style(
                            f"color:{cpal.accent}").mark(f"{prefix}-name")
                        if self.is_npc(row) and extra is None:
                            _npc_badge(cpal, f"npc-badge-{prefix}")
                        ui.space()
                        with ui.link(target=chrome.character_url(row.id)).mark(
                                f"{prefix}-open-sheet"):
                            ui.icon("open_in_new", size="1rem").style(
                                f"color:{cpal.accent}")
                            ui.tooltip("Open the sheet")
                        if extra is not None:
                            extra()
                    ui.label(cv.identity_line).classes("text-xs opacity-70 truncate -mt-1.5")

                    _heading(cpal, "HEALTH · penalty "
                             + viewmod.worst_penalty(cv.play, marks))
                    with ui.row().classes("gap-0.5"):
                        for i, (health, mark) in enumerate(zip(cv.play.health_boxes, marks)):
                            box = _health_box(mark, cpal, 1.35, health.label,
                                              f"{prefix}-health-label-{i}").mark(
                                f"{prefix}-health-{i}")
                            box.classes("cursor-pointer select-none").on(
                                "click", lambda _=None, i=i: act(
                                    lambda c: engineplay.cycle_mark(c, i, n)))

                    spent_p, spent_pp = viewmod.spent_motes(cv.play, cur)
                    if compact:
                        _pool_line(cv.play, cur, spent_p, spent_pp).classes(
                            "text-xs").mark(f"{prefix}-line")
                        return
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
                            _mote_bar(label, f"{prefix}-motes-{key}", spent, cap, self.pal,
                                      lambda value, f=field, c=cap: act(
                                          lambda ch: engineplay.set_motes(ch, f, value, c)))
                    for note in (viewmod.committed_note(cv.play, compact=True),
                                 viewmod.free_motes_note(cv.play)):
                        if note:
                            ui.label(note).classes("text-xs opacity-70").mark(
                                f"{prefix}-motes-note")

                    wp_max = cv.play.willpower_max
                    wp_left = wp_max - cur.willpower_spent
                    # A click on box i leaves i dots. A click on the first empty box
                    # fills it again (`engine.play.set_count`).
                    _track(f"WP {wp_left}/{wp_max}", f"{prefix}-wp", wp_max, wp_left,
                           lambda i: act(lambda c: engineplay.set_count(
                               c, "willpower_spent", wp_max - i, wp_max)))
                    if derive.uses_clarity(shown.ruleset, character):
                        clarity = derive.clarity(shown.ruleset, character)
                        _track(f"Clarity {clarity.total}/{derive.CLARITY_MAX} "
                               f"({clarity.permanent} perm) · band {clarity.band}",
                               f"{prefix}-clarity", derive.CLARITY_MAX,
                               cur.clarity_temporary,
                               lambda i: act(lambda c: engineplay.set_count(
                                   c, "clarity_temporary", i + 1, derive.CLARITY_MAX)))
                        ui.label(clarity.effects).classes("text-xs opacity-70").mark(
                            f"{prefix}-clarity-effects")
                    else:
                        # ⚠ `derive.limit_max`, not 10: Greater Curse (p.40) and
                        # permanent Resonance shorten the track.
                        lim = derive.limit_label(shown.ruleset, character)
                        lim_max = derive.limit_max(shown.ruleset, character)
                        broken = f" — {lim.upper()} BREAK" if cur.limit >= lim_max else ""
                        _track(f"{lim} {cur.limit}/{lim_max}{broken}", f"{prefix}-limit",
                               lim_max, cur.limit,
                               lambda i: act(lambda c: engineplay.set_count(
                                   c, "limit", i + 1, lim_max)))

                    # Accumulated armour fatigue (p.332). A counter with no maximum.
                    # It shows for a character with armour, or with points left.
                    if character.armor or cur.fatigue:
                        _fatigue(cur.fatigue, cv.play.fatigue_difficulties, self.pal,
                                 prefix,
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
                self._notes_panel()
                self.members_panel = ui.column().classes("w-full gap-1")
                self._draw_members(self.copies())
            if self.is_st:
                with ui.tab_panel("st").classes("p-0 gap-2"):
                    self.st_panel = ui.column().classes("w-full gap-2")
                    self._draw_st()

    # ---- the notes ---------------------------------------------------------- #

    def _notes_panel(self) -> None:
        """MY NOTES: the private notes of the viewer (Q8, Q9). ⚠ The store keys them
        on the account of the page, never on a value from the browser."""
        with ui.column().classes("w-full gap-1").mark("table-notes"):
            _heading(self.pal, "MY NOTES")
            ui.label("Only you can read these, the Storyteller too.").classes(
                "text-xs opacity-60")
            ui.textarea(placeholder="Plans, names, loose ends…",
                        value=self.notes.read(self.user_id, self.table.id),
                        on_change=lambda e: self._write_notes(e.value)).props(
                f"outlined autogrow maxlength={MAX_NOTES}").classes("w-full").mark(
                "table-notes-text")

    def _write_notes(self, text: str | None) -> None:
        if self.gone:
            return
        try:
            self.notes.write(self.user_id, self.table.id, text or "")
        except TableNotesError as exc:
            ui.notify(str(exc), type="warning")
            if self.tables.access(self.user_id, self.table.id) is None:
                self.stop()
        except QuotaExceeded as exc:
            ui.notify(str(exc), type="negative")

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
        """Draw the ST tab: the join code, the requests, Grant XP and the awards, the
        members, the characters, and Delete campaign."""
        pal = self.pal
        copies = self.copies()
        self.st_panel.clear()
        with self.st_panel:
            with ui.column().classes("w-full gap-0").mark("table-code"):
                _heading(pal, "JOIN CODE")
                with ui.row().classes("w-full items-center justify-between no-wrap"):
                    ui.label(self.table.join_code).classes(
                        "text-2xl font-mono font-bold").mark("table-code-text")
                    ui.button("New code", icon="autorenew",
                              on_click=self._confirm_new_code).props(
                        "flat dense no-caps size=sm").mark("st-new-code")
                ui.label("Give this code to your players. You approve each request "
                         "below.").classes("text-xs opacity-70")
            _requests(self.tables, self.store, self.rulesets, self.user_id, self.table,
                      self._approve, self._reject)
            self._proposals()
            self._grant_form(copies)
            self._awards()
            self._house_rules()
            self._st_members(copies)
            self._st_characters(copies)
            self._st_drafts()
            ui.separator()
            ui.button("Delete campaign", icon="delete_forever",
                      on_click=self._confirm_delete).props(
                "flat dense no-caps color=negative").mark("st-delete")

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

    # ---- homebrew requests -------------------------------------------------- #

    def _proposals(self) -> None:
        """HOMEBREW REQUESTS: the rows that members propose from their libraries
        (step 7). Approve adds them to the homebrew of the campaign."""
        pal = self.pal
        proposals = self.homebrew.proposals(self.user_id, self.table.id)
        with ui.column().classes("w-full gap-2").mark("table-proposals"):
            _heading(pal, f"HOMEBREW REQUESTS ({len(proposals)})")
            if not proposals:
                ui.label("No homebrew is waiting.").classes("text-sm opacity-70")
            for proposal in proposals:
                with ui.card().classes(f"w-full px-2 py-1.5 gap-0 {pal.card_soft}").mark(
                        f"table-proposal-{proposal.id}"):
                    ui.label(_username(self.tables, proposal.user_id)).classes(
                        "text-sm font-bold")
                    ui.label("Proposes: " + ", ".join(proposal.names)).classes("text-xs")
                    _row_buttons(self.rulesets.for_table(self.table.id), proposal.kind,
                                 proposal.rows, f"table-proposal-view-{proposal.id}")
                    with ui.row().classes("gap-1 justify-end w-full"):
                        ui.button("Approve", icon="check",
                                  on_click=lambda _=None, p=proposal.id:
                                  self._approve_proposal(p)).props(
                            f"dense no-caps size=sm color={pal.button}").mark(
                            f"table-proposal-approve-{proposal.id}")
                        ui.button("Reject", icon="close",
                                  on_click=lambda _=None, p=proposal.id:
                                  self._reject_proposal(p)).props(
                            "flat dense no-caps size=sm color=negative").mark(
                            f"table-proposal-reject-{proposal.id}")

    def _approve_proposal(self, proposal_id: int) -> None:
        if not self._still_storyteller():
            return
        try:
            self.homebrew.approve(self.user_id, self.table.id, proposal_id)
        except (TableHomebrewError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
        else:
            ui.notify("Added to the campaign homebrew.", type="positive")
        self.refresh_all()

    def _reject_proposal(self, proposal_id: int) -> None:
        if not self._still_storyteller():
            return
        try:
            self.homebrew.reject(self.user_id, self.table.id, proposal_id)
        except TableHomebrewError as exc:
            ui.notify(str(exc), type="warning")
        self.refresh_all()

    def _reject(self, request_id: int) -> None:
        if not self._still_storyteller():
            return
        try:
            self.tables.reject(self.user_id, request_id)
        except TableStoreError as exc:
            ui.notify(str(exc), type="warning")
        self.refresh_all()

    # ---- Grant XP ----------------------------------------------------------- #

    def _grant_form(self, copies: list[CharacterRow]) -> None:
        """Grant XP: an amount, a note, and a checkbox for each copy, each ticked at
        the start (section 6; the checkboxes: human, 2026-09-22).

        ⚠ The grant names the ticked copies. A copy that joins after the draw is not
        in the list, thus it gets nothing that the Storyteller did not see.
        """
        pal = self.pal
        with ui.column().classes("w-full gap-1").mark("st-grant-form"):
            _heading(pal, "GRANT XP")
            if not copies:
                ui.label("No characters yet.").classes("text-sm opacity-70")
                return
            with ui.row().classes("w-full items-center no-wrap gap-1"):
                amount = ui.number("XP", value=None, min=-MAX_GRANT, max=MAX_GRANT,
                                   format="%d").props("dense outlined").classes(
                    "w-20").mark("st-grant-amount")
                note = ui.input(placeholder="Why? (shown in the Log)").props(
                    f"dense outlined maxlength={MAX_NOTE}").classes(
                    "flex-1 min-w-0").mark("st-grant-note")
            ticks = {}
            with ui.column().classes("w-full gap-0"):
                for row in copies:
                    # An NPC starts unticked (human, 2026-09-22).
                    npc = self.is_npc(row)
                    ticks[row.id] = ui.checkbox(
                        f"{self._copy_name(row)} · "
                        + ("NPC" if npc else _username(self.tables, row.owner_id)),
                        value=not npc).props(f"dense color={pal.button}").classes(
                        "text-sm").mark(f"st-grant-to-{row.id}")
            ui.button("Grant", icon="add", on_click=lambda: self._grant(
                amount.value, note.value,
                [copy_id for copy_id, box in ticks.items() if box.value])).props(
                f"dense no-caps color={pal.button}").mark("st-grant")
            ui.label("Untick a character to leave it out. A negative amount corrects "
                     "an over-grant.").classes("text-xs opacity-60")

    def _grant(self, value, note: str | None, character_ids: list[str]) -> None:
        if not self._still_storyteller():
            return
        amount = int(value) if value is not None and float(value).is_integer() else 0
        try:
            result = self.storyteller.grant_xp(self.user_id, self.table.id, amount,
                                               note or "", character_ids)
        except (TableStoreError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
            return
        names = ", ".join(r.name for r in result.award.recipients)
        ui.notify(f"{result.award.amount:+d} XP to {names}.", type="positive")
        if result.failed:
            ui.notify("Not granted, the file could not be saved: "
                      + ", ".join(result.failed), type="negative")
        self._draw_st()
        self._draw_log()

    def _awards(self) -> None:
        """The newest `AWARDS_SHOWN` awards, the newest first."""
        awards = self.storyteller.awards(self.table.id)
        if not awards:
            return
        with ui.column().classes("w-full gap-0").mark("st-awards"):
            _heading(self.pal, f"AWARDS ({len(awards)})")
            for award in reversed(awards[-AWARDS_SHOWN:]):
                _award_row(award)

    # ---- house rules -------------------------------------------------------- #

    def _house_rules(self) -> None:
        """HOUSE RULES: the TABLE-WIDE switches of the campaign (section 5)."""
        pal = self.pal
        rows = viewmod.build_table_house_rules(self.tables.house_rules(self.table.id))
        with ui.column().classes("w-full gap-1").mark("st-house-rules"):
            _heading(pal, "HOUSE RULES")
            ui.label("These apply to each character in the campaign. A creation rule "
                     "reaches a locked character only if you unlock it.").classes(
                "text-xs opacity-70")
            for row in rows:
                _rule_control(row, pal, f"st-rule-{row.field}",
                              lambda value, f=row.field: self._set_table_rule(f, value))

    def _set_table_rule(self, field: str, value) -> None:
        if not self._still_storyteller():
            return
        try:
            failed = self.storyteller.set_table_rule(self.user_id, self.table.id,
                                                     field, value)
        except (TableStoreError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
            self._draw_st()
            return
        if failed:
            ui.notify("Not changed, the file could not be saved: " + ", ".join(failed)
                      + ". It changes when the character opens again.", type="negative")
        self._draw_log()

    def _permissions(self, row: CharacterRow) -> None:
        """A dialog with the PER-CHARACTER permissions of the copy `row` (Q2)."""
        shown = self.read(row)
        if shown.character is None:
            return
        name = self._copy_name(row)
        rows = [r for r in viewmod.build_house_rules(shown.ruleset, shown.character)
                if r.scope == "character"]
        with ui.dialog() as dialog, ui.card().classes(
                f"w-[30rem] max-w-full p-4 gap-2 {self.pal.card_solid}").mark(
                "st-permissions-dialog"):
            ui.label(f"Permissions of {name}").classes("text-base font-bold")
            for rule in rows:
                _rule_control(rule, self.pal, f"st-permission-{rule.field}",
                              lambda value, f=rule.field, n=name, lab=rule.label:
                              self._set_character_rule(row.id, n, f, lab, value))
                if rule.note:
                    ui.label(rule.note).classes("text-xs italic opacity-70 -mt-1")
            with ui.row().classes("w-full justify-end"):
                ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

    def _set_character_rule(self, character_id: str, name: str, field: str,
                            label: str, value) -> None:
        if not self._still_storyteller():
            return
        try:
            self.storyteller.set_character_rule(self.user_id, self.table.id,
                                                character_id, field, value)
        except (TableStoreError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
            return
        ui.notify(f"{name}: {label} — {'On' if value else 'Off'}", type="positive")

    # ---- members and characters --------------------------------------------- #

    def _st_members(self, copies: list[CharacterRow]) -> None:
        """MEMBERS, each with Remove."""
        pal = self.pal
        members = self.tables.members(self.table.id)
        with ui.column().classes("w-full gap-0").mark("st-members"):
            _heading(pal, f"MEMBERS ({len(members)})")
            if not members:
                ui.label("No members yet.").classes("text-sm opacity-70")
            for member in members:
                name = _username(self.tables, member)
                count = sum(1 for row in copies if row.owner_id == member)
                with ui.row().classes("w-full items-center justify-between no-wrap").mark(
                        f"st-member-{member}"):
                    ui.label(name + ("" if count else " · watching")).classes(
                        "text-sm truncate min-w-0")
                    ui.button(icon="person_remove",
                              on_click=lambda _=None, m=member, n=name, c=count:
                              self._confirm_remove(m, n, c)).props(
                        "flat dense round size=sm color=negative").mark(
                        f"st-remove-{member}").tooltip("Remove from the campaign")

    def _st_characters(self, copies: list[CharacterRow]) -> None:
        """CHARACTERS, each locked one with Unlock (Q6)."""
        if not copies:
            return
        with ui.column().classes("w-full gap-0").mark("st-characters"):
            _heading(self.pal, f"CHARACTERS ({len(copies)})")
            for row in copies:
                character = self.read(row).character
                with ui.row().classes("w-full items-center justify-between no-wrap").mark(
                        f"st-copy-{row.id}"):
                    ui.label(f"{self._copy_name(row)} · "
                             f"{_username(self.tables, row.owner_id)}").classes(
                        "text-sm truncate min-w-0")
                    if self.is_npc(row):
                        _npc_badge(self.pal, f"npc-badge-{row.id}")
                    ui.space()
                    if character is not None:
                        ui.button(icon="tune",
                                  on_click=lambda _=None, r=row: self._permissions(r)
                                  ).props("flat dense round size=sm").mark(
                            f"st-permissions-{row.id}").tooltip(
                            "Permissions of this character")
                    if character is not None and character.chargen_locked:
                        ui.button(icon="lock_open",
                                  on_click=lambda _=None, r=row: self._confirm_unlock(r)
                                  ).props("flat dense round size=sm").mark(
                            f"st-unlock-{row.id}").tooltip("Unlock character creation")
                    elif character is not None:
                        ui.label("unlocked").classes("text-xs opacity-60")

    def _st_drafts(self) -> None:
        """BEING MADE: the drafts for the campaign, each with its permissions (Q2).
        A draft takes no XP and has no Unlock."""
        drafts = self.tables.drafts(self.table.id)
        if not drafts:
            return
        with ui.column().classes("w-full gap-0").mark("st-drafts"):
            _heading(self.pal, f"BEING MADE ({len(drafts)})")
            for row in drafts:
                with ui.row().classes("w-full items-center justify-between no-wrap").mark(
                        f"st-draft-{row.id}"):
                    ui.label(f"{self._copy_name(row)} · "
                             f"{_username(self.tables, row.owner_id)}").classes(
                        "text-sm truncate min-w-0")
                    if self.is_npc(row):
                        _npc_badge(self.pal, f"npc-badge-{row.id}")
                    ui.space()
                    ui.button(icon="tune",
                              on_click=lambda _=None, r=row: self._permissions(r)
                              ).props("flat dense round size=sm").mark(
                        f"st-permissions-{row.id}").tooltip(
                        "Permissions of this character")

    def _copy_name(self, row: CharacterRow) -> str:
        character = self.read(row).character
        return (character.name or "(unnamed)") if character is not None else row.id

    # ---- the confirms ------------------------------------------------------- #

    def _confirm(self, title: str, body: str, action: str, marker: str,
                 on_confirm: Callable[[], None]) -> None:
        """Open a dialog with `title`, `body`, Cancel and `action`."""
        with ui.dialog() as dialog, ui.card().classes(
                f"w-[26rem] p-4 gap-2 {self.pal.card_solid}"):
            ui.label(title).classes("text-base font-bold")
            ui.label(body).classes("text-sm").mark(f"{marker}-body")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                def confirm() -> None:
                    dialog.close()
                    on_confirm()

                ui.button(action, on_click=confirm, color="negative").mark(marker)
        dialog.open()

    def _confirm_new_code(self) -> None:
        self._confirm("Make a new join code?",
                      "The old code stops working. A request that is waiting stays.",
                      "New code", "st-new-code-confirm", self._new_code)

    def _new_code(self) -> None:
        if not self._still_storyteller():
            return
        code = self.tables.new_code(self.user_id, self.table.id)
        self.table = replace(self.table, join_code=code)
        self._draw_st()

    def _confirm_remove(self, member: int, name: str, count: int) -> None:
        body = (f"{name} leaves the campaign." + (
            f" Their {count} character{'s' if count != 1 else ''} in it become solo "
            "copies, with their XP." if count else ""))
        self._confirm(f"Remove {name}?", body, "Remove", "st-remove-confirm",
                      lambda: self._remove(member))

    def _remove(self, member: int) -> None:
        if not self._still_storyteller():
            return
        try:
            self.tables.remove(self.user_id, self.table.id, member)
        except TableStoreError as exc:
            ui.notify(str(exc), type="warning")
        self.refresh_all()

    def _confirm_unlock(self, row: CharacterRow) -> None:
        character = self.read(row).character
        name = self._copy_name(row)
        warning = viewmod.unlock_warning(character) if character is not None else ""
        body = warning or (f"The player of {name} can then change its creation, and "
                           "locks it again when it is done.")
        self._confirm(f"Unlock {name}?", body, "Unlock", "st-unlock-confirm",
                      lambda: self._unlock(row.id))

    def _unlock(self, character_id: str) -> None:
        if not self._still_storyteller():
            return
        try:
            self.storyteller.unlock(self.user_id, self.table.id, character_id)
        except (TableStoreError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
        else:
            ui.notify("Unlocked. The player sees it when the character page opens "
                      "again.", type="positive")
        self._draw_st()

    def _confirm_delete(self) -> None:
        members = len(self.tables.members(self.table.id))
        self._confirm(
            f"Delete {self.table.name}?",
            f"It has {members} member{'s' if members != 1 else ''}. Each character in "
            "it becomes a solo copy, with its XP. The Log and the awards are deleted. "
            "This cannot be undone.",
            "Delete", "st-delete-confirm", self._delete)

    def _delete(self) -> None:
        if not self._still_storyteller():
            return
        self.tables.delete(self.user_id, self.table.id)
        self.gone = True
        ui.navigate.to(chrome.HOME_PATH)

    def _confirm_leave(self) -> None:
        count = len(self.mine(self.copies()))
        body = ("You leave the campaign." + (
            f" Your {count} character{'s' if count != 1 else ''} in it become solo "
            "copies, with their XP." if count else ""))
        self._confirm(f"Leave {self.table.name}?", body, "Leave", "table-leave-confirm",
                      self._leave)

    def _leave(self) -> None:
        try:
            self.tables.leave(self.user_id, self.table.id)
        except TableStoreError as exc:
            ui.notify(str(exc), type="warning")
            return
        self.gone = True
        ui.navigate.to(chrome.HOME_PATH)


# --------------------------------------------------------------------------- #
# Widgets
# --------------------------------------------------------------------------- #


def _rule_control(row: viewmod.HouseRuleRow, pal, marker: str,
                  on_change: Callable[[object], None]) -> None:
    """One house rule: a select for a rule with options, else a checkbox. The
    description is the tooltip."""
    tip = f"{row.description} ({row.citation})"
    if row.options:
        ui.label(row.label).classes("text-sm").tooltip(tip)
        ui.select(row.options, value=row.value,
                  on_change=lambda e: on_change(e.value)).props(
            "dense outlined options-dense").classes("w-full").mark(marker)
    else:
        ui.checkbox(row.label, value=row.value,
                    on_change=lambda e: on_change(e.value)).props(
            f"dense color={pal.button}").classes("text-sm").mark(marker).tooltip(tip)


def _npc_badge(pal, marker: str) -> None:
    """The NPC badge of a character of the Storyteller."""
    ui.badge("NPC").props("outline").classes("text-[10px] shrink-0").style(
        f"color:{pal.accent}").mark(marker)


def _heading(pal, text: str) -> None:
    ui.label(text).classes("text-xs font-bold tracking-widest").style(
        f"color:{pal.accent}")


def _health_box(mark, pal, size: float, label: str, label_marker: str) -> ui.label:
    """One health box with its label above it: the penalty, or "Incap"
    (`PlayHealthBox.label`). Return the box. The box shows the mark, and has no handler.
    """
    with ui.column().classes("items-center gap-0"):
        ui.label(label).classes("opacity-60 leading-none whitespace-nowrap").style(
            f"font-size:{max(0.5, size * 0.42):.2f}rem").mark(label_marker)
        return _box(mark, pal, size)


def _box(mark, pal, size: float) -> ui.label:
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


def _pool_line(play, cur: PlayState, spent_p: int, spent_pp: int) -> ui.label:
    """One line of Willpower and motes left, as THE OTHERS shows them."""
    bits = [f"WP {play.willpower_max - cur.willpower_spent}/{play.willpower_max}"]
    if play.single_pool:
        bits.append(f"Motes {play.peripheral_max - spent_pp}/{play.peripheral_max}")
    elif play.personal_max or play.peripheral_max:
        bits.append(f"Motes {play.personal_max - spent_p}/{play.personal_max} · "
                    f"{play.peripheral_max - spent_pp}/{play.peripheral_max}")
    return ui.label("  ·  ".join(bits))


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


def _fatigue(points: int, difficulties: list[str], pal, prefix: str,
             step: Callable[[int], None]) -> None:
    """The armour fatigue counter, with − and +. `step` takes −1 or +1.
    `difficulties` names the fatigue roll difficulty of each worn piece. `prefix`
    starts each marker."""
    with ui.row().classes("w-full items-center no-wrap gap-1"):
        text = f"Fatigue {points}" + (f" (-{points} to all actions)" if points else "")
        ui.label(text).classes("text-xs shrink-0").mark(f"{prefix}-fatigue-label")
        ui.button(icon="remove", on_click=lambda: step(-1)).props(
            f"flat dense round size=xs color={pal.button}").mark(f"{prefix}-fatigue-minus")
        ui.button(icon="add", on_click=lambda: step(1)).props(
            f"flat dense round size=xs color={pal.button}").mark(f"{prefix}-fatigue-plus")
        if difficulties:
            ui.label("Roll difficulty: " + ", ".join(difficulties)).classes(
                "text-xs opacity-70 truncate")


def _mote_bar(label: str, key: str, spent: int, cap: int, pal,
              set_spent: Callable[[int], None]) -> None:
    """One pool as a bar of what is left, with − and + at its ends. A click on the
    bar opens a box: type an amount, then Spend, Regain or Full.

    `set_spent` takes the new number of spent motes. The engine clamps it. `key`
    starts each marker, for example "you-motes-peripheral".
    """
    left = cap - spent
    pct = 0 if cap == 0 else 100 * left / cap
    with ui.row().classes("w-full items-center no-wrap gap-1"):
        ui.label(label).classes("text-xs w-16 shrink-0")
        ui.button(icon="remove", on_click=lambda: set_spent(spent + 1)).props(
            f"flat dense round size=xs color={pal.button}").mark(
            f"{key}-minus").tooltip("Spend 1")
        with ui.element("div").classes("relative flex-1 cursor-pointer rounded").style(
                f"height:1.25rem;border:1px solid {_BORDER};background:{_WHITE}"):
            ui.element("div").classes("absolute inset-y-0 left-0 rounded-sm").style(
                f"width:{pct}%;background:{_GOLD}")
            ui.label(f"{left}/{cap}").classes(
                "absolute inset-0 text-center text-xs font-bold").style(
                "line-height:1.2rem").mark(f"{key}-left")
            ui.tooltip("Click to spend or regain an amount")
            with ui.menu().props("anchor='bottom middle' self='top middle'") as menu:
                with ui.column().classes("p-2 gap-1"):
                    amount = ui.number(f"{label}", value=None, min=0, format="%d").props(
                        "dense outlined autofocus").classes("w-32").mark(
                        f"{key}-amount")

                    def apply(sign: int) -> None:
                        menu.close()
                        set_spent(spent + sign * int(amount.value or 0))

                    amount.on("keydown.enter", lambda: apply(1))
                    with ui.row().classes("gap-1 no-wrap"):
                        ui.button("Spend", on_click=lambda: apply(1)).props(
                            f"dense no-caps size=sm color={pal.button}").mark(
                            f"{key}-spend")
                        ui.button("Regain", on_click=lambda: apply(-1)).props(
                            "dense no-caps size=sm outline").mark(f"{key}-regain")
                        ui.button("Full", on_click=lambda: (menu.close(), set_spent(0))) \
                            .props("dense no-caps size=sm flat").mark(f"{key}-full")
        ui.button(icon="add", on_click=lambda: set_spent(spent - 1)).props(
            f"flat dense round size=xs color={pal.button}").mark(
            f"{key}-plus").tooltip("Regain 1")


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


def _award_row(award: Award) -> None:
    """One award: the amount, the copies, the note and the date."""
    with ui.column().classes("w-full gap-0 py-0.5").mark(f"st-award-{award.id}"):
        with ui.row().classes("w-full items-baseline gap-1 no-wrap min-w-0"):
            ui.label(f"{award.amount:+d} XP").classes("text-sm font-bold shrink-0")
            ui.label(", ".join(r.name for r in award.recipients)).classes(
                "text-xs truncate min-w-0")
            ui.space()
            ui.label(time.strftime("%d %b %H:%M", time.localtime(award.at))).classes(
                "text-xs opacity-40 shrink-0")
        if award.note:
            ui.label(award.note).classes("text-xs opacity-70 break-words")


def _other_row(shown: _Shown, player: str, *, mine: bool, npc: bool,
               extra: Callable[[], None] | None = None) -> None:
    """One copy that the viewer does not play now, read-only (R3): the name, the
    player, the identity line, the health strip, the motes and the Willpower.
    `extra` draws more controls at the end of the row.

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
                if npc:
                    _npc_badge(cpal, f"npc-badge-{row.id}")
                ui.space()
                ui.label(player + (" (you)" if mine else "")).classes(
                    "text-xs opacity-60 shrink-0")
            ui.label(cv.identity_line).classes("text-xs opacity-70 truncate -mt-1")
            with ui.row().classes("gap-0.5"):
                for i, (health, mark) in enumerate(zip(cv.play.health_boxes, marks)):
                    _health_box(mark, cpal, 0.95, health.label,
                                f"other-health-label-{row.id}-{i}").mark(
                        f"other-health-{row.id}-{i}")
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
            if extra is not None:
                extra()


def _side_switch(value: str, marker: str, on_change: Callable[[str], None]) -> None:
    """The Enemy / Ally switch of an NPC or a roster entry (R6)."""
    ui.toggle({ENEMY: "Enemy", ALLY: "Ally"}, value=value,
              on_change=lambda e: on_change(e.value)).props(
        "dense no-caps size=sm").mark(marker)


def _ally_row(view: viewmod.AllyView, pal) -> None:
    """One ally on the page of a player: the name and the health track (R7).

    ⚠ `view` is all that this row reads. No stat of the ally reaches the page.
    """
    with ui.column().classes("w-full gap-0.5 px-2 py-1.5 rounded").style(
            "background:#00000008").mark(f"ally-{view.key}"):
        ui.label(view.name).classes("text-sm font-bold truncate").style(
            f"color:{pal.accent}")
        with ui.row().classes("gap-0.5"):
            for i, box in enumerate(view.boxes):
                _health_box(box.mark, pal, 0.95, box.label,
                            f"ally-health-label-{view.key}-{i}").mark(
                    f"ally-health-{view.key}-{i}")


def _requests(tables: TableStore, store: CharacterStore, rulesets: Rulesets, user_id: int,
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
                    character = _request_base(store, rulesets.for_table(table.id), base,
                                              tables.house_rules(table.id),
                                              f"table-request-rules-{request.id}")
                    _request_homebrew(tables.homebrew_preview(user_id, request.id),
                                      request.id)
                    if character is not None:
                        _request_views(rulesets, table, base, character, request.id)
                with ui.row().classes("gap-1 justify-end w-full"):
                    ui.button("Approve", icon="check",
                              on_click=lambda _=None, r=request.id: approve(r)).props(
                        f"dense no-caps size=sm color={pal.button}").mark(
                        f"table-approve-{request.id}")
                    ui.button("Reject", icon="close",
                              on_click=lambda _=None, r=request.id: reject(r)).props(
                        "flat dense no-caps size=sm color=negative").mark(
                        f"table-reject-{request.id}")


def _row_buttons(ruleset: RuleSet, kind: str, rows: list[dict], marker: str) -> None:
    """Draw one line for each row of `rows`: its name and a View button. The button
    opens the row. Its mark is `marker` and the id of the row."""
    for row in rows:
        row_id = str(row.get("id") or "")
        if not row_id:
            continue
        with ui.row().classes("w-full items-center gap-1 no-wrap"):
            ui.label(str(row.get("name") or row_id)).classes("text-xs truncate min-w-0")
            ui.button("View", icon="visibility",
                      on_click=lambda _=None, i=row_id: chrome.homebrew_dialog(
                          ruleset, kind, rows, i)).props(
                "flat dense no-caps size=sm").mark(f"{marker}-{row_id}")


def _request_homebrew(preview, request_id: int) -> None:
    """Draw what the approval of a request adds to the homebrew of the campaign, and
    each carried row that differs from the row of the campaign (step 7)."""
    if preview.adds:
        ui.label("Approving adds to the campaign homebrew: "
                 + ", ".join(preview.adds)).classes("text-xs").mark(
            f"table-request-adds-{request_id}")
    if preview.differs:
        ui.label("Different from the campaign's version, which stays: "
                 + ", ".join(preview.differs)).classes(
            "text-xs font-bold text-amber-800").mark(f"table-request-differs-{request_id}")


def _request_views(rulesets: Rulesets, table: TableRow, base: CharacterRow,
                   character: Character, request_id: int) -> None:
    """Draw the View character button, and one View button for each homebrew row
    that the base carries (human, 2026-09-24).

    The sheet uses the RuleSet of the base, thus it shows the base as its owner
    sees it. A carried row shows the copy that the base holds.
    """
    carried = character.custom_definitions or {}
    table_rules = rulesets.for_table(table.id)
    for kind in ("charms", "spells", "rituals"):
        if carried.get(kind):
            _row_buttons(table_rules, kind, carried[kind],
                         f"table-request-row-view-{request_id}")
    ui.button("View character", icon="description",
              on_click=lambda: chrome.sheet_dialog(
                  rulesets.for_row(base), character, f"table-request-sheet-{request_id}")
              ).props("flat dense no-caps size=sm").mark(f"table-request-view-{request_id}")


def _request_base(store: CharacterStore, ruleset: RuleSet, base: CharacterRow,
                  table_rules: HouseRules, marker: str) -> Character | None:
    """Draw what a request brings: the base, and the TABLE-WIDE house rules under
    which it was made, where they differ from the table's (human, 2026-09-22). The
    copy keeps its creation rules unless the Storyteller unlocks it.

    Return the character of the base, or None if its file does not read."""
    shown = chrome.entry(store, ruleset, base)
    ui.label(f"Asks to bring {shown.name} ({shown.kind}).").classes("text-xs opacity-80")
    try:
        character = store.load(base)
    except Exception:                               # noqa: BLE001 - the entry says unreadable
        return None
    differences = viewmod.house_rule_differences(
        validate.chargen_house_rules(character), table_rules)
    if differences:
        with ui.column().classes("w-full gap-0 pt-1"):
            ui.label("ST house rules are different on this character").classes(
                "text-xs font-bold text-amber-800").mark(marker)
            for line in differences:
                ui.label(line).classes("text-xs")
    return character
