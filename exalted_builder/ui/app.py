"""
ui/app.py — NiceGUI read-only character sheet.

A thin renderer: it loads a RuleSet and a Character, asks ui.view to build the
display model, and lays it out. No game logic lives here. Run with:

    python -m exalted_builder.ui.app [path/to/foo.character.json]

With no argument it loads the bundled example character.
"""

from __future__ import annotations

import sys
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..models.character import Character
from ..models.rules import RuleSet
from . import view as viewmod

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "exalted_builder" / "data"
_EXAMPLE = _REPO_ROOT / "examples" / "ashes-of-dawn.character.json"


def _section(title: str):
    card = ui.card().classes("w-full")
    with card:
        ui.label(title).classes("text-lg font-bold text-amber-800")
    return card


def _trait_line(row: viewmod.TraitRow) -> str:
    mark = " ●" if row.caste else (" ✦" if row.favored else "")
    return f"{row.label}: {row.value}{mark}"


def render_sheet(view: viewmod.SheetView) -> None:
    with ui.column().classes("w-full max-w-5xl mx-auto gap-4"):
        # --- header ---
        with ui.card().classes("w-full"):
            ui.label(view.name).classes("text-2xl font-bold")
            ui.label(f"{view.caste} Caste {view.exalt_type}"
                     f"{' · ' + view.concept if view.concept else ''}").classes("text-sm text-gray-600")
            meta = " · ".join(p for p in [
                f"Player: {view.player}" if view.player else "",
                f"Nature: {view.nature}" if view.nature else "",
                f"Essence {view.essence_rating}",
                "CHARGEN LOCKED" if view.chargen_locked else "in creation",
            ] if p)
            ui.label(meta).classes("text-xs text-gray-500")

        # --- derived summary strip ---
        with ui.row().classes("w-full gap-4"):
            for label, val in [
                ("Willpower", view.willpower),
                ("Personal Essence", view.essence_personal),
                ("Peripheral Essence", view.essence_peripheral),
            ]:
                with ui.card().classes("flex-1 items-center"):
                    ui.label(str(val)).classes("text-2xl font-bold text-amber-800")
                    ui.label(label).classes("text-xs text-gray-600")

        # --- attributes / abilities / virtues+derived ---
        with ui.row().classes("w-full gap-4 items-start"):
            with _section("Attributes").classes("flex-1"):
                for category, rows in view.attributes:
                    ui.label(category).classes("text-sm font-semibold mt-1")
                    for r in rows:
                        ui.label(_trait_line(r)).classes("text-sm ml-2")

            with _section("Abilities").classes("flex-1"):
                ui.label("● caste  ✦ favored").classes("text-xs text-gray-400")
                for r in view.abilities:
                    cls = "text-sm" + (" font-semibold" if r.caste or r.favored else " text-gray-600")
                    ui.label(_trait_line(r)).classes(cls)

            with ui.column().classes("flex-1 gap-4"):
                with _section("Virtues"):
                    for r in view.virtues:
                        ui.label(_trait_line(r)).classes("text-sm ml-2")
                with _section("Soak"):
                    s = view.soak
                    ui.label(f"Bashing: {s.bashing}  (Stamina {s.natural_bashing} + armor {s.armor_bashing})").classes("text-sm")
                    ui.label(f"Lethal: {s.lethal}  (½Stamina {s.natural_lethal} + armor {s.armor_lethal})").classes("text-sm")
                    ui.label(f"Aggravated: {s.aggravated}  (armor only)").classes("text-sm")
                with _section("Health"):
                    ui.label("  ".join(view.health)).classes("text-sm font-mono")

        # --- advantages ---
        with ui.row().classes("w-full gap-4 items-start"):
            with _section("Backgrounds").classes("flex-1"):
                if not view.backgrounds:
                    ui.label("none").classes("text-sm text-gray-400")
                for name, rating, note in view.backgrounds:
                    suffix = f" — {note}" if note else ""
                    ui.label(f"{name}: {rating}{suffix}").classes("text-sm")

            with _section("Specialties").classes("flex-1"):
                if not view.specialties:
                    ui.label("none").classes("text-sm text-gray-400")
                for ability, name, rating in view.specialties:
                    ui.label(f"{ability} — {name}: {rating}").classes("text-sm")

        # --- charms / spells ---
        with ui.row().classes("w-full gap-4 items-start"):
            with _section(f"Charms ({len(view.charms)})").classes("flex-1"):
                if not view.charms:
                    ui.label("none").classes("text-sm text-gray-400")
                for name, category in view.charms:
                    ui.label(f"{name}  ·  {category}").classes("text-sm")

            with _section(f"Spells ({len(view.spells)})").classes("flex-1"):
                if not view.spells:
                    ui.label("none").classes("text-sm text-gray-400")
                for name, circle in view.spells:
                    ui.label(f"{name}  ·  {circle}").classes("text-sm")

        # --- equipment ---
        with _section("Equipment"):
            for w in view.weapons:
                art = f"  [Artifact {w.artifact_rating}, attune {w.attunement}m]" if w.artifact_rating else ""
                rng = f", range {w.range}" if w.range else ""
                ui.label(f"⚔ {w.name}: Spd {w.speed:+d}, Acc {w.accuracy:+d}, "
                         f"Dmg {w.damage:+d}{w.damage_type}, Def {w.defense:+d}{rng}{art}").classes("text-sm")
            for a in view.armor:
                art = f"  [Artifact {a.artifact_rating}, attune {a.attunement}m]" if a.artifact_rating else ""
                ui.label(f"🛡 {a.name}: Soak {a.soak_lethal}L/{a.soak_bashing}B, "
                         f"Mobility {a.mobility_penalty:+d}, Fatigue {a.fatigue}{art}").classes("text-sm")
            if not view.weapons and not view.armor:
                ui.label("none").classes("text-sm text-gray-400")

        # --- validation ---
        errors = [i for i in view.issues if i.severity == "error"]
        with _section(f"Validation — {'OK' if not errors else str(len(errors)) + ' error(s)'}"):
            for issue in view.issues:
                color = {"error": "text-red-600", "warning": "text-amber-600"}.get(issue.severity, "text-gray-500")
                ui.label(f"[{issue.severity}] {issue.message}").classes(f"text-sm {color}")


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character]:
    ruleset = rules_db.load_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    ruleset, character = load(arg)
    view = viewmod.build_sheet_view(ruleset, character)

    @ui.page("/")
    def index() -> None:
        render_sheet(view)

    ui.run(title=f"Exalted 1e — {view.name}", reload=False, show=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
