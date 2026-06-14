"""
ui/builder.py — the unified Exalted 1e builder app.

Stitches the three views over one in-memory Character: an Edit tab (the editable
sheet), a Charms tab (the Cytoscape charm-tree picker), and a Sheet tab (the
read-only / locked viewer). A top bar provides Save, Load, and Finish & Lock.

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

from .. import persistence, rules_db
from ..engine import lifecycle, validate
from ..models.character import Character
from ..models.rules import RuleSet
from . import app as sheet_app
from . import combos as combos_mod
from . import editor, picker
from . import view as viewmod
from . import xp as xp_mod
from .assets import cytoscape_head_html

# Package-relative so it resolves in a dev checkout and a packaged (PyInstaller)
# build alike: builder.py lives in exalted_builder/ui/, so data is one level up.
_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"
_ACCENT = "#8a5a1a"

_TABS = ("Edit", "Charms", "Combos", "XP", "Sheet")
_CHARGEN_TABS = ("Edit", "Charms", "Combos")     # editing these is disabled once locked


def _native_window():
    """The pywebview window when running as a native desktop app (``--native``),
    else None — in which case the browser upload/download fallback is used."""
    return getattr(app.native, "main_window", None)


class _NullDialog:
    """A no-op stand-in so the native Open path can reuse `do_load`, which closes a
    dialog after loading; the native OS dialog has already closed itself."""
    def close(self) -> None:
        pass


def build_app(ruleset: RuleSet, character: Character, save_path: Path) -> None:
    # Mutable context so Load/New can swap the character without losing closures.
    # `dir` is the folder saves land in; the filename is derived from the
    # character's name at save time, so renaming the character renames its file.
    ctx = {"char": character, "path": save_path, "dir": Path(save_path).parent}
    state: dict = {"tab": "Edit", "select": None}

    ui.add_head_html(cytoscape_head_html())
    ui.add_head_html("<style>body{background:#f7f1e3;color:#3a2e1f;}</style>")

    # One charm_select handler for the whole app; dispatch to the picker's current
    # select (set whenever the Charms tab builds).
    ui.on("charm_select", lambda e: state["select"](e.args["id"]) if state["select"] else None)

    @ui.refreshable
    def content() -> None:
        char, path = ctx["char"], ctx["path"]
        # Once locked, the chargen tabs are read-only — advancement is the XP tab's
        # job, and editing the baseline would desync the snapshot.
        if state["tab"] in _CHARGEN_TABS and char.chargen_locked:
            _locked_notice()
            return
        if state["tab"] == "Edit":
            editor.build_editor(ruleset, char, path, with_header=False)
        elif state["tab"] == "Charms":
            state["select"] = picker.build_picker(
                ruleset, char, path, with_header=False, register_events=False)
        elif state["tab"] == "Combos":
            combos_mod.build_combos(ruleset, char, path, with_header=False)
        elif state["tab"] == "XP":
            xp_mod.build_xp(ruleset, char, path, with_header=False)
        else:
            sheet_app.render_sheet(viewmod.build_sheet_view(ruleset, char))

    def _locked_notice() -> None:
        with ui.card().classes("max-w-xl mx-auto mt-8 p-4 bg-amber-50/60 border border-amber-900/30 gap-2"):
            ui.label("Chargen is locked").classes("text-lg font-bold").style(f"color:{_ACCENT}")
            ui.label("Spend experience in the XP tab, or press Unlock to edit chargen "
                     "again (that clears the XP baseline).").classes("text-sm")
            with ui.row().classes("gap-2"):
                ui.button("Go to XP", icon="bolt", on_click=lambda: select_tab("XP")).props("color=brown")
                ui.button("Unlock", icon="lock_open", on_click=unlock).props("flat color=brown")

    def select_tab(name: str) -> None:
        state["tab"] = name
        content.refresh()

    async def save() -> None:
        """Native desktop window -> the OS "Save As" dialog (choose folder + name);
        plain browser -> a filename prompt, then a download to the browser's download
        folder. Both default the name to the character (overridable)."""
        win = _native_window()
        default_name = persistence.suggested_filename(ctx["char"])
        if win is not None:
            import webview                              # only present in native mode
            chosen = await win.create_file_dialog(
                webview.SAVE_DIALOG, directory=str(ctx["dir"]), save_filename=default_name)
            if not chosen:                              # cancelled
                return
            target = Path(chosen if isinstance(chosen, str) else chosen[0])
            persistence.save_character(ctx["char"], target)
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
                          on_click=lambda: _browser_download(name_input.value, dialog)).props("color=brown")
        dialog.open()

    def _browser_download(name: str, dialog) -> None:
        filename = persistence.normalize_save_filename(name, ctx["char"])
        ui.download.content(persistence.character_to_json(ctx["char"]).encode("utf-8"), filename)
        ctx["path"] = ctx["dir"] / filename
        dialog.close()
        ui.notify(f"Downloading {filename}", type="positive")

    def _apply_loaded(loaded: Character, path: Path | None, source_label: str) -> None:
        """Swap in a freshly loaded character. With a real path, future saves land
        beside it; for an uploaded file (no path) they default to the save dir."""
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
            loaded = persistence.load_character(path_str)
        except Exception as ex:                       # noqa: BLE001 - surface any load error to the user
            ui.notify(f"Load failed: {ex}", type="negative")
            return
        dialog.close()
        _apply_loaded(loaded, Path(path_str), Path(path_str).stem)

    def _on_upload(e) -> None:
        try:
            loaded = persistence.character_from_json(e.content.read().decode("utf-8"))
        except Exception as ex:                       # noqa: BLE001 - surface any parse/validation error
            ui.notify(f"Load failed: {ex}", type="negative")
            return
        _apply_loaded(loaded, None, e.name)

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
                ui.button("New character", on_click=lambda: new_character(dialog)).props("color=brown")
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
            import webview                              # only present in native mode
            chosen = await win.create_file_dialog(
                webview.OPEN_DIALOG, directory=str(ctx["dir"]), allow_multiple=False,
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
                      on_upload=lambda e: (_on_upload(e), dialog.close())).classes("w-96")
            ui.label("…or load by path:").classes("text-xs text-gray-600 mt-2")
            path_input = ui.input("Path to .character.json", value=str(ctx["path"])).classes("w-96")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Load path", on_click=lambda: do_load(path_input.value, dialog)).props("color=brown")
        dialog.open()

    def finish() -> None:
        errors = [i for i in validate.validate_chargen(ruleset, ctx["char"]) if i.severity == "error"]
        lifecycle.lock_chargen(ctx["char"])
        if errors:
            ui.notify(f"Locked with {len(errors)} unresolved error(s) — see the Sheet", type="warning")
        else:
            ui.notify("Chargen finished and locked", type="positive")
        select_tab("Sheet")

    # ---- top bar + tabs --------------------------------------------------- #
    with ui.header().classes("items-center justify-between px-4").style(f"background:{_ACCENT}"):
        ui.label("Exalted 1e — Solar Builder").classes("text-lg font-bold text-white")
        with ui.row().classes("items-center gap-2"):
            ui.button("New", icon="note_add", on_click=confirm_new).props("flat color=white")
            ui.button("Save", icon="save", on_click=save).props("flat color=white")
            ui.button("Load", icon="folder_open", on_click=open_load).props("flat color=white")
            ui.button("Finish & Lock", icon="lock", on_click=finish).props("flat color=white")
            ui.button("Unlock", icon="lock_open", on_click=unlock).props("flat color=white")

    with ui.tabs(value="Edit").classes("w-full") as tab_bar:
        ui.tab("Edit", icon="edit")
        ui.tab("Charms", icon="account_tree")
        ui.tab("Combos", icon="bolt")
        ui.tab("XP", icon="trending_up")
        ui.tab("Sheet", icon="description")
    tab_bar.on_value_change(lambda e: select_tab(e.value))

    content()


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    """Load the rule set and the starting character. With a path, open that file;
    with none, start on a blank new character whose save lands next to the
    executable (see persistence.default_save_dir). The bundled example is no longer
    auto-loaded — open it via the path argument or the Load dialog."""
    ruleset = rules_db.load_ruleset(_DATA_DIR)
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

    @ui.page("/")
    def index() -> None:
        build_app(ruleset, character, path)

    if args.native:
        ui.run(title="Exalted 1e — Solar Builder", reload=False, native=True, window_size=(1280, 900))
    else:
        ui.run(title="Exalted 1e — Solar Builder", reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
