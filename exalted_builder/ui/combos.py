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
fixed — undo the purchase in the Edit tab's Experience card to take one back.

Run:
    python -m exalted_builder.ui.combos [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..engine import advancement, combo_actions, costs, validate
from ..models.character import Character
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
    # In-play composition state: the Combo (or Array) being assembled before it is bought.
    draft: dict = {"ids": [], "name": ""}
    # A Charm-Slot splat (Alchemical) builds Arrays INSTEAD of Combos (p.89-90), so
    # this tab renders one system or the other. The flag is the engine's, not a splat
    # name check, so a later Slot splat needs no change here.
    arrays = viewmod.uses_arrays(ruleset, character)

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
            ui.label("Undo a purchase in the Experience card on the Edit tab."
                     ).classes("text-xs text-gray-500")
        else:
            ui.label(bp).classes("text-sm font-semibold").style(f"color:{pal.accent}")
        ui.label("✓ Legal" if not errors else f"✗ {len(errors)} error(s)").classes(
            "text-sm font-bold").style("color:#15803d" if not errors else "color:#b91c1c")

    # ---- mutations -------------------------------------------------------- #
    # ⚠ These are one-line wrappers over `engine.combo_actions` and must STAY that way.
    # They were the real implementations until 2026-08-27, which is why the native shell
    # could not reach them — the mutations are game logic and belong in the engine.
    def add_combo(name: str) -> None:
        combo_actions.add_combo(character, name)
        refresh()

    def remove_combo(index: int) -> None:
        combo_actions.remove_combo(character, index)
        refresh()

    def add_member(index: int, charm_id: str) -> None:
        combo_actions.add_combo_member(character, index, charm_id)
        refresh()

    def remove_member(index: int, charm_id: str) -> None:
        combo_actions.remove_combo_member(character, index, charm_id)
        refresh()

    def rename(index: int, value: str) -> None:        # no full refresh: keep input focus
        combo_actions.rename_combo(character, index, value)
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
        (arrays_panel if arrays else combos_panel).refresh()
        readout.refresh()

    # ---- Arrays (Alchemical, p.89) ---------------------------------------- #
    # An Array is the Charm-Slot splats' analogue of a Combo: it links Attribute-based
    # Charms into a permanent pattern, priced 1 BP per Charm at chargen or Σ minimum
    # Attribute ratings in XP, and cuts their combined installation cost to
    # three-fourths. The two systems are mutually exclusive per splat (see
    # view.uses_arrays), so this tab renders one or the other, never both.
    # Wrappers, as above — see `engine/combo_actions.py`.
    def add_array(name: str) -> None:
        combo_actions.add_array(character, name)
        refresh()

    def remove_array(index: int) -> None:
        combo_actions.remove_array(character, index)
        refresh()

    def add_array_member(index: int, charm_id: str) -> None:
        combo_actions.add_array_member(character, index, charm_id)
        refresh()

    def remove_array_member(index: int, charm_id: str) -> None:
        combo_actions.remove_array_member(character, index, charm_id)
        refresh()

    def rename_array(index: int, value: str) -> None:   # no full refresh: keep focus
        combo_actions.rename_array(character, index, value)
        readout.refresh()

    def buy_array() -> None:
        """Buy the drafted Array with XP (in play). engine.advancement prices it,
        rejects an illegal or Charm-reusing set, and logs it — all or nothing."""
        try:
            advancement.add_array(ruleset, character, draft["name"], list(draft["ids"]))
        except advancement.AdvancementError as ex:
            ui.notify(str(ex), type="warning")
            return
        ui.notify(f"Bought {draft['name'] or 'Array'} — "
                  f"{costs.array_cost(ruleset, draft['ids'])} XP", type="positive")
        draft.update({"ids": [], "name": ""})
        refresh()

    def buy_array_form() -> None:
        """Compose a whole Array, then buy it — the same buy-whole shape Combos use
        in play. Charms already linked into an Array are left out of the pool: the
        engine refuses to reuse one, so offering it would only produce a rejection."""
        linked = combo_actions.linked_array_charms(character)
        eligible = {cid: ruleset.charms[cid].name
                    for cid in validate.eligible_array_charms(ruleset, character)
                    if cid not in linked}
        draft["ids"] = [cid for cid in draft["ids"] if cid in eligible]
        cost = costs.array_cost(ruleset, draft["ids"])
        if not eligible:
            ui.label("No unlinked Attribute-based Charms — install Charms on the "
                     "Charms tab before building Arrays.").classes("text-sm text-amber-700")
            return
        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            ui.label("Buy an Array").classes("text-sm font-bold tracking-widest").style(
                f"color:{pal.accent}")
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select(eligible, value=draft["ids"], multiple=True, label="Charms",
                          on_change=lambda e: (draft.__setitem__("ids", e.value), refresh())
                          ).props("dense").classes("flex-1")
                ui.input(value=draft["name"], placeholder="array name",
                         on_change=lambda e: draft.__setitem__("name", e.value)
                         ).props("dense").classes("w-40")
                ui.label(f"{cost} XP").classes("text-xs w-12")
                btn = ui.button("Buy Array", icon="shopping_cart",
                                on_click=buy_array).props(f"dense color={pal.button}")
                if cost > advancement.xp_available(character):
                    btn.props("disable")
            ui.label("An Array costs the sum of its Charms' minimum Attribute ratings "
                     "(p.89).").classes("text-xs text-gray-500")

    @ui.refreshable
    def arrays_panel() -> None:
        v = viewmod.build_array_view(ruleset, character)
        if in_play():
            buy_array_form()
        else:
            if not v.addable:
                ui.label("No Attribute-based Charms installed yet — install Charms on "
                         "the Charms tab before building Arrays.").classes(
                    "text-sm text-amber-700")
            with ui.row().classes("items-end gap-2"):
                new_name = ui.input("New Array name").classes("w-64")
                ui.button("Add Array", icon="add",
                          on_click=lambda: add_array(new_name.value)).props(f"color={pal.button}")
            ui.label(f"Arrays cost {v.total_cost} bonus point(s) "
                     "(1 per Charm).").classes("text-xs text-gray-600")

        if not v.arrays:
            ui.label("No Arrays yet.").classes("text-sm text-gray-400 mt-2")
            return

        linked = combo_actions.linked_array_charms(character)
        for arow in v.arrays:
            in_array = {m.id for m in arow.members}
            # A Charm may join only one Array, so the pool excludes every linked
            # Charm — not merely the ones already in THIS Array.
            options = {m.id: f"{m.name} · {m.attribute} {m.rating}"
                       for m in v.addable if m.id not in linked}
            with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
                with ui.row().classes("w-full items-center justify-between no-wrap"):
                    if in_play():      # a bought Array is fixed; undo it on the Edit tab
                        ui.label(arow.name).classes("text-sm font-bold").style(
                            f"color:{pal.accent}")
                    else:
                        ui.input(value=arow.name,
                                 on_change=lambda e, i=arow.index: rename_array(i, e.value)).props(
                            "dense").classes("text-sm font-bold").style(f"color:{pal.accent}")
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        ui.label(f"{len(arow.members)} Charms" if in_play()
                                 else f"{arow.cost} BP").classes("text-xs text-gray-600")
                        if not in_play():
                            ui.button(icon="delete",
                                      on_click=lambda _=None, i=arow.index: remove_array(i)).props(
                                "dense flat round size=sm color=negative").tooltip("Delete Array")

                if arow.members:
                    for m in arow.members:
                        with ui.row().classes("w-full items-center justify-between no-wrap gap-1 pl-2"):
                            ui.label(m.name).classes("text-xs")
                            with ui.row().classes("items-center gap-2 no-wrap"):
                                ui.label(f"{m.attribute} {m.rating}").classes(
                                    "text-xs text-gray-500")
                                if not in_play():
                                    ui.button(icon="remove",
                                              on_click=lambda _=None, i=arow.index, cid=m.id:
                                              remove_array_member(i, cid)).props(
                                        "dense flat round size=sm color=negative")
                elif not in_play():
                    ui.label("(empty — add Charms below)").classes("text-xs text-gray-400 pl-2")

                # The installation discount is the mechanical point of an Array, so
                # show what this one actually saves in committed Personal Essence.
                if arow.install_loose:
                    ui.label(f"Installs for {arow.install_arrayed}m instead of "
                             f"{arow.install_loose}m — saves {arow.install_saving}m "
                             "committed Essence.").classes("text-xs text-gray-600 pl-2")

                if not in_play():
                    ui.select(options, label="Add Charm", with_input=True,
                              on_change=lambda e, i=arow.index: add_array_member(i, e.value)).props(
                        "dense").classes("w-full")

                for msg in arow.issues:
                    ui.label(f"• {msg}").classes("text-xs text-red-600")

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
                    if in_play():        # a bought Combo is fixed; undo it on the Edit tab
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
                    ui.label("Array Builder" if arrays else "Combo Builder").classes(
                        "text-xl font-bold")
                ui.label("An Array links two or more installed Attribute-based Charms "
                         "into a permanent pattern, cutting their combined installation "
                         "cost to three-fourths." if arrays else
                         "A Combo combines two or more known instant-duration Charms "
                         "(at most one Simple, at most one Extra Action).").classes(
                    "text-xs text-gray-500")
                if with_header:
                    ui.button("Save", icon="save", on_click=save).props(f"color={pal.button}")
            if arrays:
                arrays_panel()
            else:
                combos_panel()
        with ui.column().classes("w-64 gap-2 sticky top-4"):
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                ui.label("Live Validation").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                readout()


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
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
