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

from nicegui import ui

from .. import persistence, rules_db
from ..engine import lifecycle, validate
from ..models.character import Character
from ..models.rules import RuleSet
from . import app as sheet_app
from . import combos as combos_mod
from . import editor, picker
from . import view as viewmod
from .assets import cytoscape_head_html

# Package-relative so it resolves in a dev checkout and a packaged (PyInstaller)
# build alike: builder.py lives in exalted_builder/ui/, so data is one level up.
_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"
_ACCENT = "#8a5a1a"

_TABS = ("Edit", "Charms", "Combos", "Sheet")


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
        if state["tab"] == "Edit":
            editor.build_editor(ruleset, char, path, with_header=False)
        elif state["tab"] == "Charms":
            state["select"] = picker.build_picker(
                ruleset, char, path, with_header=False, register_events=False)
        elif state["tab"] == "Combos":
            combos_mod.build_combos(ruleset, char, path, with_header=False)
        else:
            sheet_app.render_sheet(viewmod.build_sheet_view(ruleset, char))

    def select_tab(name: str) -> None:
        state["tab"] = name
        content.refresh()

    def save() -> None:
        # Always name the file after the character, in the working directory; this
        # picks up renames and avoids saving over a file the character was loaded
        # from under a different name.
        target = ctx["dir"] / persistence.suggested_filename(ctx["char"])
        persistence.save_character(ctx["char"], target)
        ctx["path"] = target
        ui.notify(f"Saved to {target}", type="positive")

    def do_load(path_str: str, dialog) -> None:
        try:
            loaded = persistence.load_character(path_str)
        except Exception as ex:                       # noqa: BLE001 - surface any load error to the user
            ui.notify(f"Load failed: {ex}", type="negative")
            return
        ctx["char"], ctx["path"] = loaded, Path(path_str)
        ctx["dir"] = Path(path_str).resolve().parent  # future saves land beside the loaded file
        dialog.close()
        ui.notify(f"Loaded {loaded.name or ctx['path'].stem}", type="positive")
        select_tab("Sheet")

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

    def open_load_dialog() -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label("Load a character").classes("text-lg font-bold")
            path_input = ui.input("Path to .character.json", value=str(ctx["path"])).classes("w-96")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Load", on_click=lambda: do_load(path_input.value, dialog)).props("color=brown")
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
            ui.button("Load", icon="folder_open", on_click=open_load_dialog).props("flat color=white")
            ui.button("Finish & Lock", icon="lock", on_click=finish).props("flat color=white")
            ui.button("Unlock", icon="lock_open", on_click=unlock).props("flat color=white")

    with ui.tabs(value="Edit").classes("w-full") as tab_bar:
        ui.tab("Edit", icon="edit")
        ui.tab("Charms", icon="account_tree")
        ui.tab("Combos", icon="bolt")
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
