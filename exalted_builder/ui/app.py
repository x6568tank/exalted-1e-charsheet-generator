"""
ui/app.py — NiceGUI read-only character sheet.

A thin renderer: it loads a RuleSet and a Character, asks ui.view to build the
display model, and lays it out to loosely follow the one-page Solar sheet —
dot-tracks for ratings, abilities grouped by ability-caste, an attributes row,
an advantages band, and a bottom band of Willpower / Health+Soak / Virtues +
Essence. No game logic lives here. Run with:

    python -m exalted_builder.ui.app [path/to/foo.character.json]

With no argument it loads the bundled example character.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..models.character import Character
from ..models.rules import RuleSet
from . import theme
from . import view as viewmod

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "exalted_builder" / "data"
_EXAMPLE = _REPO_ROOT / "examples" / "ashes-of-dawn.character.json"

# Module-scoped palette so the module-level render helpers (_heading, _trait_row,
# _panel …) can theme by splat. render_sheet sets it from the SheetView's exalt
# type before drawing anything, so it always reflects the character on screen.
pal = theme.palette(None)

# Likewise module-scoped: what this splat calls the caste slot ("Caste" / "Aspect").
# render_sheet sets it from the SheetView so _trait_row's marker tooltip matches.
caste_noun = "Caste"


def _dots(value: int, total: int = 5) -> str:
    """Filled/empty pips, e.g. 3 -> '●●●○○'. Values above `total` get a '+N'."""
    filled = min(max(value, 0), total)
    s = "●" * filled + "○" * (total - filled)
    if value > total:
        s += f" +{value - total}"
    return s


def _heading(text: str) -> None:
    with ui.row().classes("w-full items-center gap-2 mt-1"):
        ui.element("div").classes(f"flex-1 border-t border-{pal.fam}-900/40")
        ui.label(text.upper()).classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
        ui.element("div").classes(f"flex-1 border-t border-{pal.fam}-900/40")


def _panel():
    return ui.card().classes(f"w-full p-3 {pal.card_soft}")


def _trait_row(r: viewmod.TraitRow, dot_total: int = 5) -> None:
    with ui.row().classes("w-full items-center gap-1 no-wrap"):
        if r.caste:
            ui.label("●").classes("text-xs").style(f"color:{pal.accent}").tooltip(caste_noun)
        elif r.favored:
            ui.label("✦").classes("text-xs text-sky-700").tooltip("Favored")
        else:
            ui.label("").classes("w-3")
        ui.label(r.label).classes("text-sm flex-1 truncate")
        ui.label(_dots(r.value, dot_total)).classes("text-sm font-mono tracking-tight")


def _named_value(label: str, value: int, dot_total: int = 5) -> None:
    with ui.row().classes("w-full items-center gap-1 no-wrap"):
        ui.label(label).classes("text-sm flex-1")
        ui.label(_dots(value, dot_total)).classes("text-sm font-mono")


def render_sheet(view: viewmod.SheetView) -> None:
    global pal, caste_noun
    pal = theme.palette(view.exalt_type)
    caste_noun = view.caste_noun
    ui.add_head_html(pal.head_style())
    with ui.column().classes("w-full max-w-6xl mx-auto gap-2 p-4"):
        # --- header ------------------------------------------------------- #
        with _panel():
            with ui.row().classes("w-full justify-between items-start"):
                with ui.column().classes("gap-0"):
                    ui.label(view.name).classes("text-2xl font-bold")
                    ui.label(f"{view.caste} {view.caste_noun} {view.exalt_type}").style(f"color:{pal.accent}")
                with ui.column().classes("gap-0 text-right text-sm text-gray-600"):
                    if view.concept:
                        ui.label(f"Concept: {view.concept}")
                    if view.nature:
                        ui.label(f"Nature: {view.nature}")
                    ui.label("Chargen locked" if view.chargen_locked else "In creation")

        # --- attributes --------------------------------------------------- #
        _heading("Attributes")
        with ui.row().classes("w-full gap-2 items-stretch no-wrap"):
            for category, rows in view.attributes:
                with _panel().classes("flex-1"):
                    ui.label(category).classes("text-xs font-semibold text-center w-full").style(f"color:{pal.accent}")
                    for r in rows:
                        _trait_row(r)

        # --- abilities (grouped by ability-caste) ------------------------- #
        _heading("Abilities")
        ui.label(f"● {view.caste_noun.lower()} · ✦ favored").classes("text-xs text-gray-400 -mt-1")
        groups = view.ability_groups
        for chunk_start in range(0, len(groups), 3):
            with ui.row().classes("w-full gap-2 items-stretch no-wrap"):
                for group_label, rows in groups[chunk_start:chunk_start + 3]:
                    with _panel().classes("flex-1"):
                        ui.label(group_label).classes("text-xs font-semibold text-center w-full").style(f"color:{pal.accent}")
                        for r in rows:
                            _trait_row(r)

        # --- specialties + backgrounds ------------------------------------ #
        with ui.row().classes("w-full gap-2 items-stretch no-wrap"):
            with _panel().classes("flex-1"):
                ui.label("Backgrounds").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                if not view.backgrounds:
                    ui.label("—").classes("text-sm text-gray-400")
                for name, rating, note in view.backgrounds:
                    with ui.row().classes("w-full items-center gap-1 no-wrap"):
                        ui.label(f"{name}{' · ' + note if note else ''}").classes("text-sm flex-1 truncate")
                        ui.label(_dots(rating)).classes("text-sm font-mono")
            with _panel().classes("flex-1"):
                ui.label("Specialties").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                if not view.specialties:
                    ui.label("—").classes("text-sm text-gray-400")
                for ability, name, rating in view.specialties:
                    ui.label(f"{ability} — {name} ({rating})").classes("text-sm")

        # --- charms / spells ---------------------------------------------- #
        # Most characters are not sorcerers, so an empty Spells panel would sit there
        # taking half the band to say "—". Drop it entirely when there are no spells
        # and let Charms (already flex-1) have the width.
        _heading("Charms & Sorcery" if view.spells else "Charms")
        with ui.row().classes("w-full gap-2 items-start no-wrap"):
            with _panel().classes("flex-1"):
                ui.label(f"Charms ({len(view.charms)})").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                if not view.charms:
                    ui.label("—").classes("text-sm text-gray-400")
                for c in view.charms:
                    with ui.column().classes("w-full gap-0"):
                        with ui.row().classes("w-full items-center gap-2 no-wrap"):
                            ui.label(c.name).classes("text-sm flex-1 truncate")
                            ui.label(c.category).classes("text-xs text-gray-500")
                            ui.label(c.duration).classes("text-xs text-gray-500 w-24 text-right")
                            ui.label(c.cost).classes("text-xs font-mono text-gray-600 w-20 text-right")
                        if c.description:
                            ui.label(c.description).classes("text-xs text-gray-600 mb-1")
            if view.spells:
                with _panel().classes("flex-1"):
                    ui.label(f"Spells ({len(view.spells)})").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                    for s in view.spells:
                        with ui.column().classes("w-full gap-0"):
                            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                                ui.label(s.name).classes("text-sm flex-1 truncate")
                                ui.label(s.circle).classes("text-xs text-gray-500")
                                ui.label(s.cost).classes("text-xs font-mono text-gray-600 w-20 text-right")
                            if s.description:
                                ui.label(s.description).classes("text-xs text-gray-600 mb-1")

        # --- bottom band: gear | willpower+health | virtues+essence ------- #
        with ui.row().classes("w-full gap-2 items-stretch no-wrap"):
            # left: equipment + anima + virtue flaw
            with _panel().classes("flex-1"):
                ui.label("Equipment").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                for w in view.weapons:
                    art = f" · A{w.artifact_rating}/{w.attunement}m" if w.artifact_rating else ""
                    rng = f" · rng {w.range}" if w.range else ""
                    mat = f" · {w.material}" if w.material else ""
                    ui.label(f"⚔ {w.name}  Spd{w.speed:+d} Acc{w.accuracy:+d} "
                             f"Dmg{w.damage:+d}{w.damage_type} Def{w.defense:+d}{rng}{art}{mat}").classes("text-xs")
                for a in view.armor:
                    art = f" · A{a.artifact_rating}/{a.attunement}m" if a.artifact_rating else ""
                    mat = f" · {a.material}" if a.material else ""
                    ui.label(f"🛡 {a.name}  Soak {a.soak_lethal}L/{a.soak_bashing}B "
                             f"Mob{a.mobility_penalty:+d} Ftg{a.fatigue}{art}{mat}").classes("text-xs")
                if not view.weapons and not view.armor:
                    ui.label("—").classes("text-sm text-gray-400")
                if view.anima:
                    ui.separator()
                    ui.label("Anima").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                    ui.label(view.anima).classes("text-xs")
                if view.virtue_flaw:
                    ui.separator()
                    ui.label("Virtue Flaw").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                    ui.label(view.virtue_flaw).classes("text-xs")

            # center: willpower + health + soak
            with _panel().classes("flex-1"):
                ui.label("Willpower").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                ui.label(_dots(view.willpower, 10)).classes("text-sm font-mono")
                ui.separator()
                ui.label("Soak").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                s = view.soak
                ui.label(f"Bashing {s.bashing}  ·  Lethal {s.lethal}  ·  Aggravated {s.aggravated}").classes("text-sm")
                ui.label(f"(Stamina {s.natural_bashing}/{s.natural_lethal} + armor {s.armor_bashing}/{s.armor_lethal})").classes("text-xs text-gray-500")
                ui.separator()
                ui.label("Health").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                ui.label("  ".join(view.health)).classes("text-sm font-mono")

            # right: virtues + essence + experience
            with _panel().classes("flex-1"):
                ui.label("Virtues").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                for r in view.virtues:
                    _named_value(r.label, r.value)
                ui.separator()
                ui.label("Essence").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                _named_value("Rating", view.essence_rating)
                ui.label(f"Personal {view.essence_personal}  ·  Peripheral {view.essence_peripheral}").classes("text-sm")
                ui.separator()
                ui.label(f"Experience: {view.experience}").classes("text-xs")

        # --- validation --------------------------------------------------- #
        errors = [i for i in view.issues if i.severity == "error"]
        _heading(f"Validation — {'OK' if not errors else str(len(errors)) + ' error(s)'}")
        with _panel():
            for issue in view.issues:
                color = {"error": "text-red-600", "warning": "text-amber-600"}.get(issue.severity, "text-gray-500")
                ui.label(f"[{issue.severity}] {issue.message}").classes(f"text-sm {color}")


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character]:
    ruleset = rules_db.load_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e read-only character sheet")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true", help="open a browser automatically")
    args = parser.parse_args()

    ruleset, character = load(args.character)
    view = viewmod.build_sheet_view(ruleset, character)

    @ui.page("/")
    def index() -> None:
        render_sheet(view)

    ui.run(title=f"Exalted 1e — {view.name}", reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
