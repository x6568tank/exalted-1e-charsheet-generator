"""
ui/xp.py — NiceGUI post-lock XP advancement tab.

Spend experience after Finish & Lock: raise Attributes/Abilities/Virtues/Willpower/
Essence, learn Charms/spells, build Combos, add specialties — each priced by
engine.costs, applied by engine.advancement, and recorded in the append-only XP
log (undo is last-first). The chargen sheet stays the baseline (the snapshot);
this tab only adds to it. Zero game logic here: costs, legality and the log all
come from the engine.

Run:
    python -m exalted_builder.ui.xp [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..engine import advancement, costs, derive, validate
from ..models.character import Character
from ..models.rules import AbilityName, AttributeName, RuleSet, VirtueName
from . import view as viewmod

_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"
_EXAMPLE = _PKG.parent / "examples" / "ashes-of-dawn.character.json"
_ACCENT = "#8a5a1a"


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def build_xp(ruleset: RuleSet, character: Character, save_path: Path,
             *, with_header: bool = True) -> None:
    """Render the XP advancement tab. Inert until chargen is locked."""
    rs = ruleset
    # Selection + free-text state, kept in dicts so a panel refresh preserves it.
    sel: dict = {
        "attr": AttributeName.STRENGTH,
        "ability": AbilityName.MELEE,
        "virtue": VirtueName.COMPASSION,
        "charm": None,
        "spell": None,
        "spec_ability": AbilityName.MELEE,
        "spec_name": "",
        "combo_ids": [],
        "combo_name": "",
        "add_amount": 5,
        "focus": None,          # ("charm"|"spell", id) — what the detail panel describes
    }

    def _do(action) -> None:
        try:
            action()
        except advancement.AdvancementError as ex:
            ui.notify(str(ex), type="warning")
            return
        refresh_all()

    # ---- buy rows --------------------------------------------------------- #
    def _raise_row(label: str, options: dict, key: str, current: int, cost: int, action) -> None:
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            ui.label(label).classes("text-xs w-20")
            ui.select(options, value=sel[key],
                      on_change=lambda e, k=key: (sel.__setitem__(k, e.value), panel.refresh())
                      ).props("dense").classes("flex-1")
            if current >= 5:
                ui.label("max").classes("text-xs text-gray-400 w-24")
            else:
                ui.label(f"{current}→{current + 1}: {cost} XP").classes("text-xs w-24")
            btn = ui.button("Raise", on_click=lambda: _do(action)).props("dense color=brown")
            if current >= 5:
                btn.props("disable")

    @ui.refreshable
    def panel() -> None:
        if not character.chargen_locked:
            ui.label("Chargen is not locked yet. Press “Finish & Lock”, then spend XP here.").classes(
                "text-base text-amber-700 p-4")
            return

        # --- raise dotted traits ------------------------------------------ #
        with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30 gap-1"):
            ui.label("Raise a Trait").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")

            attr = sel["attr"]
            _raise_row("Attribute", {a: _label(a.value) for a in AttributeName}, "attr",
                       character.attributes[attr], costs.attribute_step(rs, character.attributes[attr]),
                       lambda: advancement.raise_attribute(rs, character, sel["attr"]))

            ab = sel["ability"]
            ab_cur = character.abilities.get(ab, 0)
            _raise_row("Ability", {a: _label(a.value) for a in AbilityName}, "ability",
                       ab_cur, costs.ability_step(rs, character, ab, ab_cur),
                       lambda: advancement.raise_ability(rs, character, sel["ability"]))

            v = sel["virtue"]
            _raise_row("Virtue", {x: _label(x.value) for x in VirtueName}, "virtue",
                       character.virtues[v], costs.virtue_step(rs, character.virtues[v]),
                       lambda: advancement.raise_virtue(rs, character, sel["virtue"]))

            wp = derive.willpower(character)
            ess = character.essence_rating
            with ui.row().classes("w-full items-center gap-4 no-wrap"):
                ui.button(f"Willpower {wp}→{wp + 1}  ·  {costs.willpower_step(rs, wp)} XP",
                          on_click=lambda: _do(lambda: advancement.raise_willpower(rs, character))).props(
                    "dense color=brown")
                ui.button(f"Essence {ess}→{ess + 1}  ·  {costs.essence_step(rs, ess)} XP",
                          on_click=lambda: _do(lambda: advancement.raise_essence(rs, character))).props(
                    "dense color=brown")

        # --- learn Charm / spell ------------------------------------------ #
        with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30 gap-1"):
            ui.label("Learn").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")

            learnable = sorted(
                (c for c in rs.charms.values()
                 if c.id not in character.charms and validate.meets_charm_requirements(rs, character, c)),
                key=lambda c: c.name)
            charm_opts = {c.id: f"{c.name} · {costs.charm_cost(rs, character, c)} XP" for c in learnable}
            # Clamp to a valid option: a just-learned id leaves the list, and a stale
            # value would crash the select on the next render.
            charm_value = sel["charm"] if sel["charm"] in charm_opts else None
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select(charm_opts, value=charm_value, with_input=True, label="Charm",
                          on_change=lambda e: (sel.__setitem__("charm", e.value),
                                               sel.__setitem__("focus", ("charm", e.value) if e.value else None),
                                               panel.refresh(), detail.refresh())
                          ).props("dense").classes("flex-1")
                ui.button("Learn Charm", on_click=lambda: _do(
                    lambda: (advancement.learn_charm(rs, character, sel["charm"]),
                             sel.update({"charm": None, "focus": None})))).props("dense color=brown")

            castable = sorted(
                (s for s in rs.spells.values()
                 if s.id not in character.spells
                 and validate.meets_spell_requirements(rs, character, s, chargen=False)),
                key=lambda s: s.name)
            spell_cost = costs.spell_cost(rs, character)
            spell_opts = {s.id: f"{s.name} · {spell_cost} XP" for s in castable}
            spell_value = sel["spell"] if sel["spell"] in spell_opts else None
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select(spell_opts, value=spell_value, with_input=True, label="Spell",
                          on_change=lambda e: (sel.__setitem__("spell", e.value),
                                               sel.__setitem__("focus", ("spell", e.value) if e.value else None),
                                               panel.refresh(), detail.refresh())
                          ).props("dense").classes("flex-1")
                ui.button("Learn Spell", on_click=lambda: _do(
                    lambda: (advancement.learn_spell(rs, character, sel["spell"]),
                             sel.update({"spell": None, "focus": None})))).props("dense color=brown")

        # --- specialty + combo -------------------------------------------- #
        with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30 gap-1"):
            ui.label("Add").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select({a: _label(a.value) for a in AbilityName}, value=sel["spec_ability"],
                          label="Specialty in",
                          on_change=lambda e: sel.__setitem__("spec_ability", e.value)).props("dense").classes("w-40")
                ui.input(value=sel["spec_name"], placeholder="specialty name",
                         on_change=lambda e: sel.__setitem__("spec_name", e.value)).props("dense").classes("flex-1")
                ui.label(f"{costs.specialty_cost(rs)} XP").classes("text-xs w-12")
                ui.button("Add Specialty", on_click=lambda: _do(
                    lambda: (advancement.add_specialty(rs, character, sel["spec_ability"], sel["spec_name"]),
                             sel.__setitem__("spec_name", "")))).props("dense color=brown")

            combo_charms = {cid: rs.charms[cid].name for cid in validate.eligible_combo_charms(rs, character)}
            combo_value = [cid for cid in sel["combo_ids"] if cid in combo_charms]
            combo_cost = costs.combo_cost(rs, combo_value)
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select(combo_charms, value=combo_value, multiple=True, label="Combo Charms",
                          on_change=lambda e: (sel.__setitem__("combo_ids", e.value), panel.refresh())
                          ).props("dense").classes("flex-1")
                ui.input(value=sel["combo_name"], placeholder="combo name",
                         on_change=lambda e: sel.__setitem__("combo_name", e.value)).props("dense").classes("w-40")
                ui.label(f"{combo_cost} XP").classes("text-xs w-12")
                ui.button("Add Combo", on_click=lambda: _do(
                    lambda: (advancement.add_combo(rs, character, sel["combo_name"], sel["combo_ids"]),
                             sel.update({"combo_ids": [], "combo_name": ""})))).props("dense color=brown")

    # ---- ledger (XP totals + log) ----------------------------------------- #
    @ui.refreshable
    def ledger() -> None:
        spent = advancement.xp_spent(character)
        available = advancement.xp_available(character)
        with ui.row().classes("w-full items-baseline gap-3"):
            ui.label(f"{available}").classes("text-2xl font-bold").style(
                f"color:{'#15803d' if available >= 0 else '#b91c1c'}")
            ui.label("XP available").classes("text-xs text-gray-600")
        ui.label(f"earned {character.xp_earned} · spent {spent}").classes("text-xs text-gray-600")
        with ui.row().classes("w-full items-center gap-1 no-wrap"):
            amount = ui.number(value=sel["add_amount"], min=1, format="%d").props("dense").classes("w-20")
            ui.button("Add XP", icon="add", on_click=lambda: (
                advancement.add_xp(character, int(amount.value or 0)), refresh_all())).props("dense color=brown")
        ui.separator()
        rows = viewmod.build_xp_log(rs, character)
        if not rows:
            ui.label("No XP spent yet.").classes("text-xs text-gray-400")
        last = len(rows) - 1
        for r in rows:
            with ui.row().classes("w-full items-center justify-between no-wrap gap-1"):
                ui.label(r.label).classes("text-xs")
                with ui.row().classes("items-center gap-1 no-wrap"):
                    ui.label(f"{r.cost} XP").classes("text-xs text-gray-600")
                    if r.index == last:
                        ui.button(icon="undo", on_click=lambda: _do_undo()).props(
                            "dense flat round size=sm color=negative").tooltip("Undo (last purchase)")

    def _do_undo() -> None:
        try:
            advancement.undo_last(rs, character)
        except advancement.AdvancementError as ex:
            ui.notify(str(ex), type="warning")
            return
        refresh_all()

    # ---- detail panel (describes the selected Charm / spell) -------------- #
    @ui.refreshable
    def detail() -> None:
        focus = sel.get("focus")
        if not focus:
            ui.label("Select a Charm or spell to see its details.").classes("text-xs text-gray-400")
            return
        kind, ident = focus
        if kind == "charm":
            d = viewmod.build_charm_detail(rs, character, ident)
            if d is None:
                ui.label("Unknown Charm.").classes("text-xs text-gray-400")
                return
            ui.label(d.name).classes("text-sm font-bold").style(f"color:{_ACCENT}")
            ui.label(f"{d.type} · {d.cost}").classes("text-xs text-gray-600")
            if d.description:
                ui.label(d.description).classes("text-xs")
            ui.separator()
            ui.label(f"Requires: {d.requirement}").classes("text-xs font-semibold")
            if d.prerequisite_groups:
                ui.label("Prerequisite Charms:").classes("text-xs font-semibold")
                for group in d.prerequisite_groups:
                    ui.label("• " + " or ".join(group)).classes("text-xs ml-2")
            else:
                ui.label("No prerequisite Charms.").classes("text-xs text-gray-500")
            ui.separator()
            if d.owned:
                ui.label("Already known.").classes("text-xs text-gray-500")
            else:
                ui.label(f"XP to learn: {costs.charm_cost(rs, character, rs.charms[ident])}").classes(
                    "text-xs font-semibold")
        else:
            d = viewmod.build_spell_detail(rs, character, ident)
            if d is None:
                ui.label("Unknown spell.").classes("text-xs text-gray-400")
                return
            ui.label(d.name).classes("text-sm font-bold").style(f"color:{_ACCENT}")
            ui.label(f"{d.circle} Circle · {d.cost}").classes("text-xs text-gray-600")
            if d.description:
                ui.label(d.description).classes("text-xs")
            ui.separator()
            if d.owned:
                ui.label("Already known.").classes("text-xs text-gray-500")
            else:
                ui.label(f"XP to learn: {costs.spell_cost(rs, character)}").classes("text-xs font-semibold")

    def refresh_all() -> None:
        panel.refresh()
        ledger.refresh()
        detail.refresh()

    def save() -> None:
        persistence.save_character(character, save_path)
        ui.notify(f"Saved to {save_path}", type="positive")

    # ---- layout ----------------------------------------------------------- #
    if with_header:
        ui.add_head_html("<style>body{background:#f7f1e3;color:#3a2e1f;}</style>")

    with ui.row().classes("w-full max-w-6xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            if with_header:
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Experience").classes("text-xl font-bold")
                    ui.button("Save", icon="save", on_click=save).props("color=brown")
            panel()
        with ui.column().classes("w-72 gap-2 sticky top-4"):
            with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30"):
                ui.label("Experience").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")
                ledger()
            with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30"):
                ui.label("Details").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")
                detail()


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e XP advancement")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset, character, path = load(args.character)

    @ui.page("/")
    def index() -> None:
        build_xp(ruleset, character, path)

    ui.run(title=f"Exalted 1e — XP: {character.name or path.stem}",
           reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
