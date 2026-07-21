"""
ui/combos.py — NiceGUI Combo builder.

Assembles Combos from the character's *known* Charms (core pp.213-214). Each Combo
names a set of instant-duration Charms used together in one turn; starting play
with one costs bonus points equal to its number of Charms. Zero game logic here:
the eligible-Charm pool and the per-Combo legality come from engine.validate via
view.build_combo_view; this module only mutates the Character and renders.

**Two modes, like the Charms tab.** At chargen a Combo is assembled in place —
created empty, members added and removed, priced in bonus points. Once chargen is
locked a Combo is *bought whole*: engine.advancement.add_combo prices it (Σ member
min_ability, p.213), checks its legality and logs it in one go, so the in-play form
composes the whole Combo first and buys it with one button. Bought Combos are then
fixed — undo the purchase on the XP tab to take one back.

Run:
    python -m exalted_builder.ui.combos [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..engine import advancement, costs, validate
from ..models.character import Character, Combo
from ..models.rules import RuleSet
from . import theme
from . import view as viewmod

_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"
_EXAMPLE = _PKG.parent / "examples" / "ashes-of-dawn.character.json"


def build_combos(ruleset: RuleSet, character: Character, save_path: Path,
                 *, with_header: bool = True) -> None:
    """Render the Combo builder for `character`. With `with_header=False` the
    title/Save bar is omitted (the embedding app provides one)."""
    pal = theme.palette(character.exalt_type)
    # In-play composition state: the Combo being assembled before it is bought.
    draft: dict = {"ids": [], "name": ""}

    def in_play() -> bool:
        """True once chargen is locked: Combos are bought whole with XP."""
        return character.chargen_locked

    # ---- live readout ----------------------------------------------------- #
    @ui.refreshable
    def readout() -> None:
        view = viewmod.build_sheet_view(ruleset, character)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        errors = [i for i in view.issues if i.severity == "error"]
        if in_play():
            available = advancement.xp_available(character)
            ui.label(f"{available} XP available").classes("text-sm font-bold").style(
                f"color:{'#15803d' if available >= 0 else '#b91c1c'}")
            ui.label(f"earned {character.xp_earned} · spent {advancement.xp_spent(character)}"
                     ).classes("text-xs text-gray-600")
            ui.label("Undo a purchase on the XP tab.").classes("text-xs text-gray-500")
        else:
            ui.label(bp).classes("text-sm font-semibold").style(f"color:{pal.accent}")
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

    def buy_combo() -> None:
        """Buy the drafted Combo with XP (in play). engine.advancement prices it,
        rejects an illegal set, and logs it — all or nothing."""
        try:
            advancement.add_combo(ruleset, character, draft["name"], list(draft["ids"]))
        except advancement.AdvancementError as ex:
            ui.notify(str(ex), type="warning")
            return
        ui.notify(f"Bought {draft['name'] or 'Combo'} — "
                  f"{costs.combo_cost(ruleset, draft['ids'])} XP", type="positive")
        draft.update({"ids": [], "name": ""})
        refresh()

    def refresh() -> None:
        combos_panel.refresh()
        readout.refresh()

    # ---- buy form (in play) ----------------------------------------------- #
    def buy_form() -> None:
        """Compose a whole Combo, then buy it. Unlike the chargen builder there is no
        empty-Combo state: the engine prices and validates the finished set."""
        eligible = {cid: ruleset.charms[cid].name
                    for cid in validate.eligible_combo_charms(ruleset, character)}
        draft["ids"] = [cid for cid in draft["ids"] if cid in eligible]
        cost = costs.combo_cost(ruleset, draft["ids"])
        if not eligible:
            ui.label("No instant-duration Charms known yet — buy Charms on the "
                     "Charms tab before building Combos.").classes("text-sm text-amber-700")
            return
        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            ui.label("Buy a Combo").classes("text-sm font-bold tracking-widest").style(
                f"color:{pal.accent}")
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select(eligible, value=draft["ids"], multiple=True, label="Charms",
                          on_change=lambda e: (draft.__setitem__("ids", e.value), refresh())
                          ).props("dense").classes("flex-1")
                ui.input(value=draft["name"], placeholder="combo name",
                         on_change=lambda e: draft.__setitem__("name", e.value)
                         ).props("dense").classes("w-40")
                ui.label(f"{cost} XP").classes("text-xs w-12")
                btn = ui.button("Buy Combo", icon="shopping_cart",
                                on_click=buy_combo).props(f"dense color={pal.button}")
                if cost > advancement.xp_available(character):
                    btn.props("disable")
            ui.label("A Combo costs the sum of its Charms' minimum Ability ratings "
                     "(p.213).").classes("text-xs text-gray-500")

    # ---- the combo list --------------------------------------------------- #
    @ui.refreshable
    def combos_panel() -> None:
        v = viewmod.build_combo_view(ruleset, character)
        if in_play():
            buy_form()
        else:
            if not v.addable:
                ui.label("No instant-duration Charms known yet — learn Charms on the "
                         "Charms tab before building Combos.").classes("text-sm text-amber-700")

            with ui.row().classes("items-end gap-2"):
                new_name = ui.input("New Combo name").classes("w-64")
                ui.button("Add Combo", icon="add",
                          on_click=lambda: add_combo(new_name.value)).props(f"color={pal.button}")
            ui.label(f"Combos cost {v.total_cost} bonus point(s) "
                     "(1 per Charm).").classes("text-xs text-gray-600")

        if not v.combos:
            ui.label("No Combos yet.").classes("text-sm text-gray-400 mt-2")
            return

        for crow in v.combos:
            in_combo = {m.id for m in crow.members}
            options = {m.id: f"{m.name} · {m.type}" for m in v.addable if m.id not in in_combo}
            with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
                with ui.row().classes("w-full items-center justify-between no-wrap"):
                    if in_play():        # a bought Combo is fixed; undo it on the XP tab
                        ui.label(crow.name).classes("text-sm font-bold").style(f"color:{pal.accent}")
                    else:
                        ui.input(value=crow.name,
                                 on_change=lambda e, i=crow.index: rename(i, e.value)).props(
                            "dense").classes("text-sm font-bold").style(f"color:{pal.accent}")
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        # The bonus-point price is a chargen fact; in play the Combo has
                        # already been paid for (its XP price is on the ledger).
                        ui.label(f"{len(crow.members)} Charms" if in_play()
                                 else f"{crow.cost} BP").classes("text-xs text-gray-600")
                        if not in_play():
                            ui.button(icon="delete", on_click=lambda _=None, i=crow.index: remove_combo(i)).props(
                                "dense flat round size=sm color=negative").tooltip("Delete Combo")

                if crow.members:
                    for m in crow.members:
                        with ui.row().classes("w-full items-center justify-between no-wrap gap-1 pl-2"):
                            ui.label(f"{m.name}").classes("text-xs")
                            with ui.row().classes("items-center gap-2 no-wrap"):
                                ui.label(m.type).classes("text-xs text-gray-500")
                                if not in_play():
                                    ui.button(icon="remove",
                                              on_click=lambda _=None, i=crow.index, cid=m.id: remove_member(i, cid)).props(
                                        "dense flat round size=sm color=negative")
                elif not in_play():
                    ui.label("(empty — add Charms below)").classes("text-xs text-gray-400 pl-2")

                if not in_play():
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
        ui.add_head_html(pal.head_style())

    with ui.row().classes("w-full max-w-5xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                if with_header:
                    ui.label("Combo Builder").classes("text-xl font-bold")
                ui.label("A Combo combines two or more known instant-duration Charms "
                         "(at most one Simple, at most one Extra Action).").classes(
                    "text-xs text-gray-500")
                if with_header:
                    ui.button("Save", icon="save", on_click=save).props(f"color={pal.button}")
            combos_panel()
        with ui.column().classes("w-64 gap-2 sticky top-4"):
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                ui.label("Live Validation").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
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
