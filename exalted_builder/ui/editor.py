"""
ui/editor.py — NiceGUI chargen editor.

Editable controls bound to a Character, with a live readout that re-runs the
engine (derive + validate_chargen) on every change: bonus-point tally, derived
pools, and the full validation panel. Zero game logic here — the UI mutates the
Character and asks the engine; legality is the engine's verdict. Save writes JSON
via persistence.

Charm/Spell editing is intentionally out of this first cut (the charm-tree picker
is the next slice); they show read-only with the counts validation cares about.

Run:
    python -m exalted_builder.ui.editor [path/to/foo.character.json] [--show] [--port N]
With no path it starts from the bundled example character.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..engine import validate
from ..models.character import BackgroundEntry, Character, Specialty
from ..models.rules import AbilityName, Caste, RuleSet, VirtueName
from . import view as viewmod

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "exalted_builder" / "data"
_EXAMPLE = _REPO_ROOT / "examples" / "ashes-of-dawn.character.json"
_ACCENT = "#8a5a1a"


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def build_editor(ruleset: RuleSet, character: Character, save_path: Path) -> None:
    """Render the whole editor for `character`. Pure-ish wiring: every control
    mutates the Character and refreshes the live readout."""

    # ---- live readout (recomputes the engine each refresh) ---------------- #
    @ui.refreshable
    def readout() -> None:
        view = viewmod.build_sheet_view(ruleset, character)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        errors = [i for i in view.issues if i.severity == "error"]
        ui.label(bp).classes("text-sm font-semibold").style(f"color:{_ACCENT}")
        with ui.row().classes("gap-4 text-sm"):
            ui.label(f"Willpower {view.willpower}")
            ui.label(f"Personal {view.essence_personal}")
            ui.label(f"Peripheral {view.essence_peripheral}")
        ui.label(f"Soak  B{view.soak.bashing} / L{view.soak.lethal} / A{view.soak.aggravated}").classes("text-sm")
        ui.separator()
        status = "✓ Legal chargen" if not errors else f"✗ {len(errors)} error(s)"
        ui.label(status).classes("text-sm font-bold").style(
            "color:#15803d" if not errors else "color:#b91c1c")
        for issue in view.issues:
            if issue.code == "bonus-points":
                continue
            color = {"error": "text-red-600", "warning": "text-amber-600"}.get(issue.severity, "text-gray-500")
            ui.label(f"• {issue.message}").classes(f"text-xs {color}")

    def changed() -> None:
        readout.refresh()

    # ---- a clickable dot-track rating control ----------------------------- #
    def dots(get, setv, lo: int, hi: int):
        @ui.refreshable
        def show() -> None:
            v = get()
            with ui.row().classes("gap-0 items-center no-wrap"):
                for i in range(1, hi + 1):
                    icon = "circle" if i <= v else "radio_button_unchecked"
                    (ui.icon(icon, size="1rem")
                       .classes("cursor-pointer").style(f"color:{_ACCENT}")
                       .on("click", lambda e, i=i: click(i)))

        def click(i: int) -> None:
            cur = get()
            new = i - 1 if i == cur else i      # click the current top pip to step down
            setv(max(lo, min(hi, new)))
            show.refresh()
            changed()

        show()

    def panel(title: str):
        card = ui.card().classes("w-full p-3 bg-amber-50/40 border border-amber-900/20")
        with card:
            ui.label(title).classes("text-xs font-bold tracking-widest").style(f"color:{_ACCENT}")
        return card

    # ---- the editor body (refreshes on structural changes) ---------------- #
    @ui.refreshable
    def body() -> None:
        caste_def = ruleset.castes.get(character.caste)
        caste_abilities = set(caste_def.caste_abilities) if caste_def else set()

        # identity
        with panel("Identity"):
            with ui.row().classes("w-full gap-3 no-wrap"):
                ui.input("Name", value=character.name,
                         on_change=lambda e: (setattr(character, "name", e.value), changed())).classes("flex-1")
                ui.input("Concept", value=character.concept,
                         on_change=lambda e: setattr(character, "concept", e.value)).classes("flex-1")
            with ui.row().classes("w-full gap-3 no-wrap items-end"):
                ui.select({c: c.value for c in Caste}, label="Caste", value=character.caste,
                          on_change=lambda e: set_caste(e.value)).classes("flex-1")
                ui.input("Nature", value=character.nature,
                         on_change=lambda e: setattr(character, "nature", e.value)).classes("flex-1")
                ui.input("Anima", value=character.anima,
                         on_change=lambda e: setattr(character, "anima", e.value)).classes("flex-1")
            ui.select({a: _label(a.value) for a in AbilityName}, label="Favored abilities (pick 5)",
                      value=list(character.favored_abilities), multiple=True,
                      on_change=lambda e: set_favored(e.value)).classes("w-full").props("use-chips")

        # attributes
        with panel("Attributes (prioritise 8 / 6 / 4)"):
            with ui.row().classes("w-full gap-2 no-wrap"):
                for category, members in validate.ATTRIBUTE_CATEGORIES.items():
                    with ui.column().classes("flex-1 gap-1"):
                        spent = sum(character.attributes[a] - 1 for a in members)
                        ui.label(f"{category} — {spent} spent").classes("text-xs font-semibold")
                        for a in members:
                            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                                ui.label(_label(a.value)).classes("text-sm w-28")
                                dots(lambda a=a: character.attributes[a],
                                     lambda v, a=a: character.attributes.__setitem__(a, v), 1, 5)

        # abilities (by ability-caste group)
        with panel("Abilities (25 dots; ≥10 caste/favoured; ≤3 each pre-bonus)"):
            groups = [(c, ruleset.castes[c].caste_abilities) for c in Caste if c in ruleset.castes]
            for start in range(0, len(groups), 3):
                with ui.row().classes("w-full gap-2 no-wrap"):
                    for caste, abilities in groups[start:start + 3]:
                        with ui.column().classes("flex-1 gap-1"):
                            ui.label(caste.value).classes("text-xs font-semibold").style(f"color:{_ACCENT}")
                            for a in abilities:
                                mark = "●" if a in caste_abilities else ("✦" if a in character.favored_abilities else "")
                                with ui.row().classes("w-full items-center gap-1 no-wrap"):
                                    ui.label(mark).classes("text-xs w-3").style(f"color:{_ACCENT}")
                                    ui.label(_label(a.value)).classes("text-sm flex-1 truncate")
                                    dots(lambda a=a: character.abilities[a],
                                         lambda v, a=a: character.abilities.__setitem__(a, v), 0, 5)

        # virtues + essence + willpower
        with ui.row().classes("w-full gap-2 no-wrap items-start"):
            with panel("Virtues (5 dots; ≤3 pre-bonus)").classes("flex-1"):
                for v in VirtueName:
                    with ui.row().classes("w-full items-center gap-2 no-wrap"):
                        ui.label(_label(v.value)).classes("text-sm w-28")
                        dots(lambda v=v: character.virtues[v],
                             lambda val, v=v: character.virtues.__setitem__(v, val), 1, 5)
            with panel("Essence & Willpower").classes("flex-1"):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.label("Essence").classes("text-sm w-28")
                    dots(lambda: character.essence_rating,
                         lambda v: setattr(character, "essence_rating", v), 1, 5)
                ui.number("Willpower purchased", value=character.willpower_purchased, min=0, max=10, format="%d",
                          on_change=lambda e: (setattr(character, "willpower_purchased", int(e.value or 0)), changed())).classes("w-full")

        # backgrounds
        with panel("Backgrounds (7 dots; ≤3 pre-bonus)"):
            for idx, bg in enumerate(character.backgrounds):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.input(value=bg.name, placeholder="Background",
                             on_change=lambda e, bg=bg: setattr(bg, "name", e.value)).classes("flex-1")
                    ui.input(value=bg.note, placeholder="note",
                             on_change=lambda e, bg=bg: setattr(bg, "note", e.value)).classes("flex-1")
                    dots(lambda bg=bg: bg.rating, lambda v, bg=bg: setattr(bg, "rating", v), 0, 5)
                    ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_bg(idx)).props("flat dense round")
            ui.button("Add background", icon="add", on_click=add_bg).props("flat dense")

        # specialties
        with panel("Specialties"):
            for idx, sp in enumerate(character.specialties):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.select({a: _label(a.value) for a in AbilityName}, value=sp.ability,
                              on_change=lambda e, sp=sp: setattr(sp, "ability", e.value)).classes("flex-1")
                    ui.input(value=sp.name, placeholder="Specialty",
                             on_change=lambda e, sp=sp: setattr(sp, "name", e.value)).classes("flex-1")
                    dots(lambda sp=sp: sp.rating, lambda v, sp=sp: setattr(sp, "rating", v), 1, 3)
                    ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_spec(idx)).props("flat dense round")
            ui.button("Add specialty", icon="add", on_click=add_spec).props("flat dense")

        # charms/spells (read-only here; the picker is the next slice)
        with panel(f"Charms ({len(character.charms)}) & Spells ({len(character.spells)}) — edit via the picker"):
            view = viewmod.build_sheet_view(ruleset, character)
            for c in view.charms:
                ui.label(f"{c.name} · {c.category}").classes("text-xs")
            for s in view.spells:
                ui.label(f"{s.name} · {s.circle}").classes("text-xs")

    # ---- structural mutators (refresh body + readout) --------------------- #
    def set_caste(value: Caste) -> None:
        character.caste = value
        body.refresh(); changed()

    def set_favored(values: list[AbilityName]) -> None:
        character.favored_abilities = list(values)
        body.refresh(); changed()

    def add_bg() -> None:
        character.backgrounds.append(BackgroundEntry(name="", rating=1))
        body.refresh(); changed()

    def remove_bg(idx: int) -> None:
        del character.backgrounds[idx]
        body.refresh(); changed()

    def add_spec() -> None:
        character.specialties.append(Specialty(ability=AbilityName.MELEE, name="", rating=1))
        body.refresh(); changed()

    def remove_spec(idx: int) -> None:
        del character.specialties[idx]
        body.refresh(); changed()

    def save() -> None:
        persistence.save_character(character, save_path)
        ui.notify(f"Saved to {save_path}", type="positive")

    # ---- layout: editor on the left, sticky readout on the right ---------- #
    ui.add_head_html("<style>body{background:#f7f1e3;color:#3a2e1f;}</style>")
    with ui.row().classes("w-full max-w-7xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Chargen Editor").classes("text-xl font-bold")
                ui.button("Save", icon="save", on_click=save).props("color=brown")
            body()
        with ui.column().classes("w-80 gap-2 sticky top-4"):
            with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30"):
                ui.label("Live Validation").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")
                readout()


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e chargen editor")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset, character, path = load(args.character)

    @ui.page("/")
    def index() -> None:
        build_editor(ruleset, character, path)

    ui.run(title=f"Exalted 1e — editing {character.name or path.stem}",
           reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
