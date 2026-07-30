"""
ui/storyteller.py — the "ST Options" tab: the table's optional-rule switches.

These are Storyteller choices, not character traits and not rulebook data, so they
live on `Character.house_rules` (the `Character.play` precedent — an optional
sub-document, so old saves load with it None). This tab is the only place they are
edited.

Two things make it different from every other editing tab:

  * **The toggles are frozen at lock.** They change how chargen is PRICED, so
    flipping one after the fact would retroactively re-price a locked chargen. The
    tab therefore goes read-only once chargen is locked, and points at Unlock as
    the way to change one — the same route as any other chargen correction.
  * **Scope matters.** Table-wide rules apply to the whole game; the foreign-Charm
    permission is granted to one character. The split is shown here so a future
    party-wide "apply to all" control has something honest to key off. The scope
    labels come from `view.build_house_rules`, not from this renderer.

No game logic lives here: what each toggle means, whether it currently bites, and
how much "Magic for Everyone" is granting all come from the engine through
ui.view.

Run:
    python -m exalted_builder.ui.storyteller [path/to/foo.character.json]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..models.character import Character, HouseRules
from ..models.rules import RuleSet
from . import theme
from . import view as viewmod

_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"
_EXAMPLE = _PKG.parent / "examples" / "ashes-of-dawn.character.json"

_SCOPE_LABEL = {
    "table": ("Table-wide", "Applies to the whole game — every character at this "
                            "table should have it set the same way."),
    "character": ("This character", "A permission granted to this one character."),
}


def house_rules(character: Character) -> HouseRules:
    """The character's HouseRules, created on first edit so a character whose table
    uses no optional rules keeps a clean save."""
    if character.house_rules is None:
        character.house_rules = HouseRules()
    return character.house_rules


def set_rule(character: Character, field: str, value: bool) -> None:
    """Set one toggle. Pure state; the caller refreshes. Guarded against unknown
    field names so a renamed field fails loudly here rather than silently writing an
    attribute nothing reads."""
    if field not in HouseRules.model_fields:
        raise KeyError(f"{field!r} is not a HouseRules field")
    setattr(house_rules(character), field, bool(value))


def build_storyteller(ruleset: RuleSet, character: Character, save_path: Path,
                      *, with_header: bool = True) -> None:
    pal = theme.palette(character.exalt_type)
    locked = character.chargen_locked

    @ui.refreshable
    def body() -> None:
        rows = viewmod.build_house_rules(ruleset, character)
        with ui.column().classes("w-full max-w-3xl mx-auto gap-3"):
            if locked:
                with ui.card().classes("w-full p-3 bg-amber-50 border border-amber-300"):
                    ui.label("Chargen is locked — these are read-only.").classes(
                        "text-sm font-semibold text-amber-800")
                    ui.label(
                        "The settings below change how bonus points are spent, and "
                        "they were frozen into the chargen snapshot at lock. Changing "
                        "one now would re-price a chargen that has already been "
                        "signed off. Use Unlock on the XP tab to reopen chargen if a "
                        "table rule really did change."
                    ).classes("text-xs text-amber-700")

            for scope in ("table", "character"):
                scoped = [r for r in rows if r.scope == scope]
                if not scoped:
                    continue
                title, blurb = _SCOPE_LABEL[scope]
                ui.label(title.upper()).classes(
                    "text-xs font-bold tracking-widest mt-2").style(f"color:{pal.accent}")
                ui.label(blurb).classes("text-xs text-gray-500 -mt-1")
                for row in scoped:
                    _rule_card(row)

    def _rule_card(row: viewmod.HouseRuleRow) -> None:
        with ui.card().classes(f"w-full p-3 gap-1 {pal.card_soft}"):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                if row.options:
                    # A multiple-choice rule (M&F change method) renders as a select
                    # rather than a checkbox — same card, same lock behaviour.
                    ui.label(row.label).classes("text-sm font-medium")
                    sel = ui.select(
                        row.options, value=row.value,
                        on_change=lambda e, f=row.field: _toggle(f, e.value),
                    ).props("dense outlined").classes("min-w-[22rem]")
                    sel.set_enabled(not locked)
                else:
                    box = ui.checkbox(
                        row.label, value=row.value,
                        on_change=lambda e, f=row.field: _toggle(f, e.value),
                    ).props(f"dense color={pal.button}")
                    box.set_enabled(not locked)
                ui.space()
                ui.label(row.citation).classes("text-xs text-gray-400 whitespace-nowrap")
            ui.label(row.description).classes("text-xs text-gray-600")
            if row.note:
                ui.label(row.note).classes("text-xs italic").style(f"color:{pal.accent}")

    def _toggle(field: str, value: bool) -> None:
        set_rule(character, field, value)
        body.refresh()

    if with_header:
        ui.add_head_html(pal.head_style())
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Storyteller options").classes("text-lg font-bold").style(
                f"color:{pal.accent}")
            ui.button("Save", icon="save",
                      on_click=lambda: _save(character, save_path)).props(
                f"color={pal.button}")
    body()


def _save(character: Character, save_path: Path) -> None:
    persistence.save_character(character, save_path)
    ui.notify(f"Saved {save_path.name}", type="positive")


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e Storyteller options")
    parser.add_argument("character", nargs="?",
                        help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset, character, path = load(args.character)

    @ui.page("/")
    def index() -> None:
        build_storyteller(ruleset, character, path)

    ui.run(title=f"Exalted 1e — ST options: {character.name or path.stem}",
           reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
