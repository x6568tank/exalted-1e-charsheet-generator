"""
ui/combos.py — NiceGUI Combo builder.

Assembles Combos from the character's *known* Charms (core pp.213-214). Each Combo
names a set of instant-duration Charms used together in one turn; starting play
with one costs bonus points equal to its number of Charms. Zero game logic here:
the eligible-Charm pool and the per-Combo legality come from engine.validate via
view.build_combo_view; this module only mutates the Character and renders.

Run:
    python -m exalted_builder.ui.combos [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..models.character import Character, Combo
from ..models.rules import RuleSet
from . import view as viewmod

_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"
_EXAMPLE = _PKG.parent / "examples" / "ashes-of-dawn.character.json"
_ACCENT = "#8a5a1a"


def build_combos(ruleset: RuleSet, character: Character, save_path: Path,
                 *, with_header: bool = True) -> None:
    """Render the Combo builder for `character`. With `with_header=False` the
    title/Save bar is omitted (the embedding app provides one)."""

    # ---- live readout ----------------------------------------------------- #
    @ui.refreshable
    def readout() -> None:
        view = viewmod.build_sheet_view(ruleset, character)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        errors = [i for i in view.issues if i.severity == "error"]
        ui.label(bp).classes("text-sm font-semibold").style(f"color:{_ACCENT}")
        ui.label("✓ Legal" if not errors else f"✗ {len(errors)} error(s)").classes(
            "text-sm font-bold").style("color:#15803d" if not errors else "color:#b91c1c")

    # ---- mutations -------------------------------------------------------- #
    def add_combo(name: str) -> None:
        label = name.strip() or f"Combo {len(character.combos) + 1}"
        character.combos.append(Combo(name=label, charm_ids=[]))
        refresh()

    def remove_combo(index: int) -> None:
        if 0 <= index < len(character.combos):
            del character.combos[index]
            refresh()

    def add_member(index: int, charm_id: str) -> None:
        if charm_id and 0 <= index < len(character.combos):
            character.combos[index].charm_ids.append(charm_id)
            refresh()

    def remove_member(index: int, charm_id: str) -> None:
        if 0 <= index < len(character.combos):
            ids = character.combos[index].charm_ids
            if charm_id in ids:
                ids.remove(charm_id)
            refresh()

    def rename(index: int, value: str) -> None:        # no full refresh: keep input focus
        if 0 <= index < len(character.combos):
            character.combos[index].name = value
            readout.refresh()

    def refresh() -> None:
        combos_panel.refresh()
        readout.refresh()

    # ---- the combo list --------------------------------------------------- #
    @ui.refreshable
    def combos_panel() -> None:
        v = viewmod.build_combo_view(ruleset, character)
        if not v.addable:
            ui.label("No instant-duration Charms known yet — learn Charms on the "
                     "Charms tab before building Combos.").classes("text-sm text-amber-700")

        with ui.row().classes("items-end gap-2"):
            new_name = ui.input("New Combo name").classes("w-64")
            ui.button("Add Combo", icon="add",
                      on_click=lambda: add_combo(new_name.value)).props("color=brown")
        ui.label(f"Combos cost {v.total_cost} bonus point(s) "
                 "(1 per Charm).").classes("text-xs text-gray-600")

        if not v.combos:
            ui.label("No Combos yet.").classes("text-sm text-gray-400 mt-2")
            return

        for crow in v.combos:
            in_combo = {m.id for m in crow.members}
            options = {m.id: f"{m.name} · {m.type}" for m in v.addable if m.id not in in_combo}
            with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30 gap-1"):
                with ui.row().classes("w-full items-center justify-between no-wrap"):
                    ui.input(value=crow.name,
                             on_change=lambda e, i=crow.index: rename(i, e.value)).props(
                        "dense").classes("text-sm font-bold").style(f"color:{_ACCENT}")
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        ui.label(f"{crow.cost} BP").classes("text-xs text-gray-600")
                        ui.button(icon="delete", on_click=lambda _=None, i=crow.index: remove_combo(i)).props(
                            "dense flat round size=sm color=negative").tooltip("Delete Combo")

                if crow.members:
                    for m in crow.members:
                        with ui.row().classes("w-full items-center justify-between no-wrap gap-1 pl-2"):
                            ui.label(f"{m.name}").classes("text-xs")
                            with ui.row().classes("items-center gap-2 no-wrap"):
                                ui.label(m.type).classes("text-xs text-gray-500")
                                ui.button(icon="remove",
                                          on_click=lambda _=None, i=crow.index, cid=m.id: remove_member(i, cid)).props(
                                    "dense flat round size=sm color=negative")
                else:
                    ui.label("(empty — add Charms below)").classes("text-xs text-gray-400 pl-2")

                ui.select(options, label="Add Charm", with_input=True,
                          on_change=lambda e, i=crow.index: add_member(i, e.value)).props(
                    "dense").classes("w-full")

                for msg in crow.issues:
                    ui.label(f"• {msg}").classes("text-xs text-red-600")

    def save() -> None:
        persistence.save_character(character, save_path)
        ui.notify(f"Saved to {save_path}", type="positive")

    # ---- layout ----------------------------------------------------------- #
    if with_header:
        ui.add_head_html("<style>body{background:#f7f1e3;color:#3a2e1f;}</style>")

    with ui.row().classes("w-full max-w-5xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                if with_header:
                    ui.label("Combo Builder").classes("text-xl font-bold")
                ui.label("A Combo combines two or more known instant-duration Charms "
                         "(at most one Simple, at most one Extra Action).").classes(
                    "text-xs text-gray-500")
                if with_header:
                    ui.button("Save", icon="save", on_click=save).props("color=brown")
            combos_panel()
        with ui.column().classes("w-64 gap-2 sticky top-4"):
            with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30"):
                ui.label("Live Validation").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")
                readout()


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e Combo builder")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset, character, path = load(args.character)

    @ui.page("/")
    def index() -> None:
        build_combos(ruleset, character, path)

    ui.run(title=f"Exalted 1e — combos: {character.name or path.stem}",
           reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
