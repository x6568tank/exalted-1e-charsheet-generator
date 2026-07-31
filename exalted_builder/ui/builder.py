"""
ui/builder.py — the unified Exalted 1e builder app.

Stitches the views over one in-memory Character: an Edit tab (the editable sheet),
a Charms tab (the Cytoscape charm-tree picker), a Combos tab, a Play tab, an ST
Options tab (the table's optional-rule switches) and a Sheet tab (the read-only
viewer). A top bar provides Save, Load, and Finish & Lock.

The tab bar tracks the character's stage. Edit and XP occupy one slot: Edit while
chargen is open, XP once it is locked (see `visible_tabs`). Charms and Combos are on
the bar throughout and change mode instead of going read-only — before the lock they
pick against the chargen budget, after it they buy with experience.

Only the active tab's content is mounted (a single refreshable area), which keeps
the Cytoscape container visible when it builds and avoids stale hidden canvases.
A single charm_toggle handler is registered here and dispatches to whatever the
picker last handed back, so rebuilding the picker never duplicates handlers.

Run:
    python -m exalted_builder.ui.builder [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import app, ui

from .. import custom_content, persistence, rules_db
from ..engine import lifecycle, validate
from ..models.character import Character
from ..models.party import Party
from ..models.rules import RuleSet
from . import app as sheet_app
from . import combos as combos_mod
from . import custom as custom_mod
from . import editor, picker, theme
from . import play as play_mod
from . import storyteller as st_mod
from . import view as viewmod
from . import xp as xp_mod
from .assets import cytoscape_head_html

# Package-relative so it resolves in a dev checkout and a packaged (PyInstaller)
# build alike: builder.py lives in exalted_builder/ui/, so data is one level up.
_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"

_TABS = ("Edit", "Charms", "Combos", "XP", "Play", "ST", "Custom", "Sheet")


def visible_tabs(locked: bool) -> tuple[str, ...]:
    """The tabs for a character at this stage of its life. Edit and XP are the same
    slot seen from two sides — chargen builds the baseline, XP spends against it —
    so exactly one of them is ever on the bar. Charms and Combos stay on both sides:
    they switch from picking (free, within the chargen budget) to buying (with XP).

    Play is locked-only. The tracker overlays spent motes, marked health and Willpower
    onto capacities derived from the finished character, and every one of those moves
    while chargen is still open — a half-built character's track is a set of boxes that
    change under the player. It is also the tab most likely to mislead: play-state is
    validation-isolated (decision 0006) and never enters chargen, so marks made before
    the lock silently mean nothing to the point accounting.
    """
    hidden = {"XP", "Play"} if not locked else {"Edit"}
    return tuple(t for t in _TABS if t not in hidden)


def resolve_tab(name: str, locked: bool) -> str:
    """`name`, or its counterpart when locking/unlocking just hid it."""
    if name in visible_tabs(locked):
        return name
    return "XP" if locked else "Edit"


def _native_window():
    """The pywebview window when running as a native desktop app (``--native``),
    else None — in which case the browser upload/download fallback is used."""
    return getattr(app.native, "main_window", None)


def _any_socket_connected(clients) -> bool:
    """True if any of `clients` holds a live browser socket. Pure (testable)."""
    return any(getattr(c, "has_socket_connection", False) for c in clients)


def any_tab_connected() -> bool:
    """True while at least one browser tab still has a live socket to the server.
    The packaged app uses this to decide whether to quit when a tab closes."""
    from nicegui import Client
    return _any_socket_connected(Client.instances.values())


def _dialog_type(kind: str):
    """The pywebview file-dialog selector for ``kind`` ('save'/'open'). Use the
    `FileDialog` IntEnum (pywebview 5+): the legacy `webview.SAVE_DIALOG`/`OPEN_DIALOG`
    module attributes are non-picklable Proxy objects, and NiceGUI forwards the call
    to its window subprocess through a multiprocessing queue — pickling a Proxy fails
    silently (the dialog never opens). The enum members pickle cleanly."""
    import webview
    fd = getattr(webview, "FileDialog", None)
    if fd is not None:
        return fd.SAVE if kind == "save" else fd.OPEN
    return 30 if kind == "save" else 10        # legacy pywebview int constants


class _NullDialog:
    """A no-op stand-in so the native Open path can reuse `do_load`, which closes a
    dialog after loading; the native OS dialog has already closed itself."""
    def close(self) -> None:
        pass


def make_context(character: Character, save_path: Path) -> dict:
    """The app's shared, mutable context. Held outside any one page so the builder
    ('/') and the GM party page ('/gm') work on the same objects — see
    `register_pages`.

    `char` is whichever character the builder is currently pointed at; `dir` is the
    folder saves land in (the filename is derived from the character's name at save
    time, so renaming the character renames its file). `party` is the GM roster and
    `member` the index within it that `char` came from, or None when editing a
    standalone character that is not in the party.
    """
    return {"char": character, "path": save_path, "dir": Path(save_path).parent,
            "party": Party(id="party.new"), "party_path": None, "member": None}


def open_member(ctx: dict, index: int) -> None:
    """Point the builder at party member `index`. The Character is shared by
    reference, not copied, so anything the builder edits mutates the party member
    in place and the card reflects it without any syncing code."""
    member = ctx["party"].members[index]
    ctx["char"] = member.character
    ctx["member"] = index
    ctx["path"] = ctx["dir"] / persistence.suggested_filename(member.character)


def close_member(ctx: dict) -> None:
    """Forget which party member the builder is pointed at. The character object
    itself is left alone — it is still in the party."""
    ctx["member"] = None


def build_app(ruleset: RuleSet, character: Character, save_path: Path,
              *, ctx: dict | None = None) -> None:
    """Render the single-character builder. `ctx` is the shared app context; when
    omitted (running this module standalone) a private one is created, so the
    builder still works with no party involved."""
    if ctx is None:
        ctx = make_context(character, save_path)
    state: dict = {"tab": "Edit", "select": None, "syncing": False}

    def _pal():
        """The palette for the current character's splat (red for Dragon-Blooded,
        gold for Solar). Re-derived on demand so loading/creating a character of a
        different splat re-themes the whole app."""
        return theme.palette(ctx["char"].exalt_type)

    ui.add_head_html(cytoscape_head_html())
    ui.add_head_html(_pal().head_style())

    # One charm_select handler for the whole app; dispatch to the picker's current
    # select (set whenever the Charms tab builds).
    ui.on("charm_select", lambda e: state["select"](e.args["id"]) if state["select"] else None)

    @ui.refreshable
    def content() -> None:
        char, path = ctx["char"], ctx["path"]
        _apply_chrome()          # keep the header/background in sync with the splat
        _sync_tabs()             # Edit ⇄ XP swap follows the lock
        if state["tab"] == "Edit":
            editor.build_editor(ruleset, char, path, with_header=False,
                                on_theme_change=_apply_chrome)
        elif state["tab"] == "Charms":
            state["select"] = picker.build_picker(
                ruleset, char, path, with_header=False, register_events=False)
        elif state["tab"] == "Combos":
            combos_mod.build_combos(ruleset, char, path, with_header=False)
        elif state["tab"] == "XP":
            xp_mod.build_xp(ruleset, char, path, with_header=False)
        elif state["tab"] == "Play":
            play_mod.build_play(ruleset, char, path, with_header=False)
        elif state["tab"] == "ST":
            st_mod.build_storyteller(ruleset, char, path, with_header=False)
        elif state["tab"] == "Custom":
            # Rule-set editing, not character editing: it takes no Character and is
            # the one tab whose edits outlive the open save. It mutates `ruleset` in
            # place, so every other tab sees new homebrew without a restart.
            custom_mod.build_custom(ruleset, with_header=False)
        else:
            sheet_app.render_sheet(viewmod.build_sheet_view(ruleset, char))

    def select_tab(name: str) -> None:
        state["tab"] = name
        content.refresh()

    def _on_tab_change(name: str) -> None:
        # _sync_tabs writes the bar's value itself, which fires this handler back at
        # us; that echo must not re-enter the refresh it came from.
        if not state["syncing"]:
            select_tab(name)

    async def save() -> None:
        """Native desktop window -> the OS "Save As" dialog (choose folder + name);
        plain browser -> a filename prompt, then a download to the browser's download
        folder. Both default the name to the character (overridable)."""
        win = _native_window()
        default_name = persistence.suggested_filename(ctx["char"])
        if win is not None:
            chosen = await win.create_file_dialog(
                _dialog_type("save"), directory=str(ctx["dir"]), save_filename=default_name)
            if not chosen:                              # cancelled
                return
            target = Path(chosen if isinstance(chosen, str) else chosen[0])
            try:
                persistence.save_character(ctx["char"], target)
            except Exception as ex:                     # noqa: BLE001 - surface write errors
                ui.notify(f"Save failed: {ex}", type="negative")
                return
            ctx["path"], ctx["dir"] = target, target.parent
            ui.notify(f"Saved to {target}", type="positive")
        else:
            _open_browser_save_dialog(default_name)

    def _open_browser_save_dialog(default_name: str) -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label("Save character").classes("text-lg font-bold")
            ui.label("Downloads to your browser's download folder.").classes("text-sm text-gray-600")
            name_input = ui.input("File name", value=default_name).classes("w-96")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Download", icon="download",
                          on_click=lambda: _browser_download(name_input.value, dialog)).props(f"color={_pal().button}")
        dialog.open()

    def _browser_download(name: str, dialog) -> None:
        filename = persistence.normalize_save_filename(name, ctx["char"])
        ui.download.content(persistence.character_to_json(ctx["char"]).encode("utf-8"), filename)
        ctx["path"] = ctx["dir"] / filename
        dialog.close()
        ui.notify(f"Downloading {filename}", type="positive")

    def _apply_loaded(loaded: Character, path: Path | None, source_label: str) -> None:
        """Swap in a freshly loaded character. With a real path, future saves land
        beside it; for an uploaded file (no path) they default to the save dir.

        The single funnel for every load, which is why the homebrew import happens
        here: a save from another table carries the definitions of the custom Charms
        it uses, and absorbing them into this machine's library is what makes those
        Charms resolve instead of showing as ⚠ rows. Both load paths pass
        `absorb_custom=False` so the count is still ours to report."""
        imported = custom_content.absorb_definitions(loaded)
        if imported:
            rules_db.reload_custom_layer(ruleset)
            ui.notify(f"Imported {len(imported)} homebrew definition(s) from this save",
                      type="info")
        ctx["char"] = loaded
        if path is not None:
            ctx["path"] = path
            ctx["dir"] = path.resolve().parent
        else:
            ctx["dir"] = persistence.default_save_dir()
            ctx["path"] = ctx["dir"] / persistence.suggested_filename(loaded)
        ui.notify(f"Loaded {loaded.name or source_label}", type="positive")
        select_tab("Sheet")

    def do_load(path_str: str, dialog) -> None:
        try:
            loaded = persistence.load_character(path_str, absorb_custom=False)
        except Exception as ex:                       # noqa: BLE001 - surface any load error to the user
            ui.notify(f"Load failed: {ex}", type="negative")
            return
        dialog.close()
        _apply_loaded(loaded, Path(path_str), Path(path_str).stem)

    async def _on_upload(e, dialog) -> None:
        # NiceGUI 3.x: the event carries a FileUpload at e.file (was e.content/e.name
        # in 2.x), and reading it is async.
        try:
            loaded = persistence.character_from_json(await e.file.text())
        except Exception as ex:                       # noqa: BLE001 - surface any parse/validation error
            ui.notify(f"Load failed: {ex}", type="negative")
            return
        dialog.close()
        _apply_loaded(loaded, None, e.file.name)

    def new_character(dialog=None) -> None:
        ctx["char"] = Character(id="char.new")
        ctx["dir"] = persistence.default_save_dir()
        ctx["path"] = ctx["dir"] / persistence.suggested_filename(ctx["char"])
        if dialog is not None:
            dialog.close()
        ui.notify("Started a new character", type="positive")
        select_tab("Edit")

    def confirm_new() -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label("Start a new character?").classes("text-lg font-bold")
            ui.label("Any unsaved changes to the current character will be lost.").classes("text-sm")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("New character", on_click=lambda: new_character(dialog)).props(f"color={_pal().button}")
        dialog.open()

    def unlock() -> None:
        if not ctx["char"].chargen_locked:
            ui.notify("Chargen is not locked.", type="info")
            return
        lifecycle.unlock_chargen(ctx["char"])
        ui.notify("Chargen unlocked — editable again.", type="positive")
        select_tab("Edit")

    async def open_load() -> None:
        """Native desktop window -> the OS "Open" dialog; plain browser -> a dialog
        with a file picker (upload) plus a path field as a fallback."""
        win = _native_window()
        if win is not None:
            chosen = await win.create_file_dialog(
                _dialog_type("open"), directory=str(ctx["dir"]), allow_multiple=False,
                file_types=("Character files (*.json)", "All files (*.*)"))
            if not chosen:                              # cancelled
                return
            path = chosen[0] if isinstance(chosen, (list, tuple)) else chosen
            do_load(path, _NullDialog())
        else:
            _open_browser_load_dialog()

    def _open_browser_load_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("gap-2"):
            ui.label("Load a character").classes("text-lg font-bold")
            ui.upload(label="Choose a .character.json file", auto_upload=True,
                      on_upload=lambda e: _on_upload(e, dialog)).classes("w-96")
            ui.label("…or load by path:").classes("text-xs text-gray-600 mt-2")
            path_input = ui.input("Path to .character.json", value=str(ctx["path"])).classes("w-96")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Load path", on_click=lambda: do_load(path_input.value, dialog)).props(f"color={_pal().button}")
        dialog.open()

    def finish() -> None:
        errors = [i for i in validate.validate_chargen(ruleset, ctx["char"]) if i.severity == "error"]
        lifecycle.lock_chargen(ctx["char"], ruleset)
        if errors:
            ui.notify(f"Locked with {len(errors)} unresolved error(s) — see the Sheet", type="warning")
        else:
            ui.notify("Chargen finished and locked", type="positive")
        select_tab("Sheet")

    # ---- top bar + tabs --------------------------------------------------- #
    def go_to_party() -> None:
        # Leaving the builder for the roster: stop pointing at a member, so a later
        # save/edit here isn't silently attributed to one.
        close_member(ctx)
        ui.navigate.to("/gm")

    with ui.header().classes("items-center justify-between px-4") as header_el:
        title_label = ui.label("Exalted 1e — Builder").classes("text-lg font-bold text-white")
        with ui.row().classes("items-center gap-2"):
            # Always present: the party page is where characters are ADDED to a
            # party, so gating this on a non-empty party would make an empty one
            # unreachable — the only way in would be typing the URL.
            ui.button("Party", icon="groups", on_click=go_to_party).props(
                "flat color=white").tooltip("Storyteller view — track the whole party at once")
            ui.button("New", icon="note_add", on_click=confirm_new).props("flat color=white")
            ui.button("Save", icon="save", on_click=save).props("flat color=white")
            ui.button("Load", icon="folder_open", on_click=open_load).props("flat color=white")
            ui.button("Finish & Lock", icon="lock", on_click=finish).props("flat color=white")
            ui.button("Unlock", icon="lock_open", on_click=unlock).props("flat color=white")

    def _apply_chrome() -> None:
        """Paint the header bar, title and page background from the current
        character's splat palette. Called on every content refresh, so switching
        tabs after changing the Exalt type re-themes the whole app."""
        pal = _pal()
        header_el.style(f"background:{pal.accent}")
        title_label.set_text(f"Exalted 1e — {pal.splat_label} Builder")
        ui.query("body").style(f"background:{pal.bg};color:{pal.ink}")
        # A Charm-Slot splat builds Arrays instead of Combos (p.89), so the tab is
        # relabelled for them. Only the LABEL changes — the tab keeps its "Combos"
        # name, so tab state, visibility and resolve_tab are untouched.
        tabs["Combos"].props(
            f'label={"Arrays" if viewmod.uses_arrays(ruleset, ctx["char"]) else "Combos"}')

    _ICONS = {"Edit": "edit", "Charms": "account_tree", "Combos": "bolt",
              "XP": "trending_up", "Play": "casino", "ST": "gavel",
              "Custom": "construction", "Sheet": "description"}
    # Tab names are identifiers (state, visible_tabs, resolve_tab all key off them);
    # where a name reads badly on the bar, the LABEL differs — see Combos/Arrays.
    _LABELS = {"ST": "ST Options"}
    with ui.tabs(value="Edit").classes("w-full") as tab_bar:
        tabs = {name: ui.tab(name, label=_LABELS.get(name, name), icon=_ICONS[name])
                for name in _TABS}
    tab_bar.on_value_change(lambda e: _on_tab_change(e.value))

    def _sync_tabs() -> None:
        """Show the tab bar for the character's stage: Edit while building, XP once
        locked. If the tab we are on is the one that just disappeared, land on its
        counterpart instead of rendering a tab that is no longer on the bar."""
        locked = ctx["char"].chargen_locked
        for name in _TABS:
            tabs[name].set_visibility(name in visible_tabs(locked))
        state["tab"] = resolve_tab(state["tab"], locked)
        if tab_bar.value != state["tab"]:
            state["syncing"] = True
            tab_bar.set_value(state["tab"])
            state["syncing"] = False

    content()


def register_pages(ruleset: RuleSet, ctx: dict) -> None:
    """Register the app's routes over one shared context: '/' the single-character
    builder, '/gm' the Storyteller's party page. Both close over the same ctx, so
    "Open in builder" and "back to Party" move between them without re-loading
    anything — the party member and the builder's character are one object.

    Both entry points (this module's main() and pack/run_app.py) call this, so the
    route set is declared exactly once.
    """
    # Imported here, not at module scope: ui/gm.py imports this module for the
    # shared context and the file-dialog helpers, so a top-level import would be
    # circular.
    from . import gm as gm_mod

    @ui.page("/")
    def index() -> None:
        build_app(ruleset, ctx["char"], ctx["path"], ctx=ctx)

    @ui.page("/gm")
    def party_page() -> None:
        gm_mod.build_gm(ruleset, ctx)


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    """Load the rule set and the starting character. With a path, open that file;
    with none, start on a blank new character whose save lands next to the
    executable (see persistence.default_save_dir). The bundled example is no longer
    auto-loaded — open it via the path argument or the Load dialog."""
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    if character_path:
        path = Path(character_path)
        character = persistence.load_character(path)
        return ruleset, character, path
    character = Character(id="char.new")
    path = persistence.default_save_dir() / persistence.suggested_filename(character)
    return ruleset, character, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e Solar builder (unified app)")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--native", action="store_true", help="run in a native desktop window")
    args = parser.parse_args()

    ruleset, character, path = load(args.character)
    register_pages(ruleset, make_context(character, path))

    if args.native:
        ui.run(title="Exalted 1e — Builder", reload=False, native=True, window_size=(1280, 900))
    else:
        ui.run(title="Exalted 1e — Builder", reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
