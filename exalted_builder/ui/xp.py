"""
ui/xp.py — NiceGUI post-lock XP advancement tab.

Spend experience after Finish & Lock: raise (or curse-reduce) Attributes/Abilities/
Crafts/Virtues/Willpower/Essence, add specialties, and keep the ledger — each priced
by engine.costs, applied by engine.advancement, and recorded in the append-only XP
log (undo is last-first, and undo of ANY purchase happens here, wherever it was
bought). The chargen sheet stays the baseline (the snapshot); this tab only adds to
it. Zero game logic here: costs, legality and the log all come from the engine.

This tab takes the Edit tab's place on the bar once chargen locks. Charms, spells,
Ox-Body packages and Combos are deliberately NOT bought here — they are bought on
the Charms and Combos tabs, which switch from picking to buying at the same moment,
so a trait is always bought where it is browsed. Backgrounds and equipment are
free (story-driven, not XP-priced) and edited here directly.

Run:
    python -m exalted_builder.ui.xp [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..engine import advancement, costs, derive
from ..models.character import Armor, BackgroundEntry, Character, Weapon
from ..models.rules import AbilityName, AttributeName, RuleSet, VirtueName
from . import theme
from . import view as viewmod
from .editor import DescribedSelect, _opts_with

_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"
_EXAMPLE = _PKG.parent / "examples" / "ashes-of-dawn.character.json"


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def build_xp(ruleset: RuleSet, character: Character, save_path: Path,
             *, with_header: bool = True) -> None:
    """Render the XP advancement tab. Inert until chargen is locked."""
    rs = ruleset
    pal = theme.palette(character.exalt_type)
    # Selection + free-text state, kept in dicts so a panel refresh preserves it.
    sel: dict = {
        "attr": AttributeName.STRENGTH,
        "ability": AbilityName.MELEE,
        "virtue": VirtueName.COMPASSION,
        "spec_ability": AbilityName.MELEE,
        "spec_name": "",
        "craft_focus": None,
        "craft_new": "",
        "college_id": None,
        "college_new": None,
        "add_amount": 5,
        "lower_target": f"attr:{AttributeName.STRENGTH.value}",   # what to reduce
        "lower_reason": "",                                       # curse / charm-cost note
    }

    def _reduce() -> None:
        tgt, reason = sel["lower_target"], sel["lower_reason"].strip()
        kind, _, name = tgt.partition(":")
        if kind == "attr":
            advancement.lower_attribute(character, AttributeName(name), reason)
        elif kind == "ability":
            advancement.lower_ability(character, AbilityName(name), reason)
        elif kind == "virtue":
            advancement.lower_virtue(character, VirtueName(name), reason)
        elif kind == "willpower":
            advancement.lower_willpower(character, reason)
        elif kind == "essence":
            advancement.lower_essence(character, reason)

    def _do(action) -> None:
        try:
            action()
        except advancement.AdvancementError as ex:
            ui.notify(str(ex), type="warning")
            return
        refresh_all()

    def _add_bg() -> None:
        character.backgrounds.append(BackgroundEntry(name="", rating=1))
        panel.refresh()

    def _del_bg(idx: int) -> None:
        del character.backgrounds[idx]
        panel.refresh()

    # equipment edits are free (an inline copy, not an XP-priced trait): no cost, no log row.
    def _add_equip(field: str) -> None:
        factory = {"armor": lambda: Armor(name=""), "weapons": lambda: Weapon(name="")}[field]
        getattr(character, field).append(factory())
        panel.refresh()

    def _del_equip(field: str, idx: int) -> None:
        del getattr(character, field)[idx]
        panel.refresh()

    def _set_armor(idx: int, name: str) -> None:
        # Catalog match autofills; a custom name only renames (keeps typed stats).
        e = next((a for a in rs.armor_catalog.values() if a.name == name), None)
        if e:
            character.armor[idx] = Armor(
                name=e.name, soak_lethal=e.soak_lethal, soak_bashing=e.soak_bashing,
                mobility_penalty=e.mobility_penalty, fatigue=e.fatigue,
                artifact_rating=e.artifact_rating, attunement=e.attunement,
                resources_cost=e.resources_cost)
        else:
            character.armor[idx].name = name or ""
        panel.refresh()

    def _set_weapon(idx: int, name: str) -> None:
        e = next((w for w in rs.weapon_catalog.values() if w.name == name), None)
        if e:
            character.weapons[idx] = Weapon(
                name=e.name, speed=e.speed, accuracy=e.accuracy, damage=e.damage,
                damage_type=e.damage_type, defense=e.defense, rate=e.rate, range=e.range,
                min_strength=e.min_strength, min_dexterity=e.min_dexterity,
                min_martial_arts=e.min_martial_arts, max_strength=e.max_strength,
                artifact_rating=e.artifact_rating, attunement=e.attunement,
                resources_cost=e.resources_cost, notes=e.notes)
        else:
            character.weapons[idx].name = name or ""
        panel.refresh()

    # ---- buy rows --------------------------------------------------------- #
    def _raise_row(label: str, options: dict, key: str, current: int, cost: int, action,
                   cap: int = 5) -> None:
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            ui.label(label).classes("text-xs w-20")
            ui.select(options, value=sel[key],
                      on_change=lambda e, k=key: (sel.__setitem__(k, e.value), panel.refresh())
                      ).props("dense").classes("flex-1")
            if current >= cap:
                ui.label("max").classes("text-xs text-gray-400 w-24")
            else:
                ui.label(f"{current}→{current + 1}: {cost} XP").classes("text-xs w-24")
            btn = ui.button("Raise", on_click=lambda: _do(action)).props(f"dense color={pal.button}")
            if current >= cap:
                btn.props("disable")

    @ui.refreshable
    def panel() -> None:
        if not character.chargen_locked:
            ui.label("Chargen is not locked yet. Press “Finish & Lock”, then spend XP here.").classes(
                "text-base text-amber-700 p-4")
            return

        # --- raise dotted traits ------------------------------------------ #
        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            ui.label("Raise a Trait").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")

            attr = sel["attr"]
            _raise_row("Attribute", {a: _label(a.value) for a in AttributeName}, "attr",
                       character.attributes[attr], costs.attribute_step(rs, character, character.attributes[attr]),
                       lambda: advancement.raise_attribute(rs, character, sel["attr"]),
                       cap=5)

            ab = sel["ability"]
            ab_cur = character.abilities.get(ab, 0)
            # Craft is per-focus (p.136) and bought in its own card below, not here.
            _raise_row("Ability", {a: _label(a.value) for a in AbilityName if a != AbilityName.CRAFT},
                       "ability", ab_cur, costs.ability_step(rs, character, ab, ab_cur),
                       lambda: advancement.raise_ability(rs, character, sel["ability"]))

            v = sel["virtue"]
            _raise_row("Virtue", {x: _label(x.value) for x in VirtueName}, "virtue",
                       character.virtues[v], costs.virtue_step(rs, character, character.virtues[v]),
                       lambda: advancement.raise_virtue(rs, character, sel["virtue"]),
                       cap=5)

            wp = derive.willpower(character)
            ess = character.essence_rating
            with ui.row().classes("w-full items-center gap-4 no-wrap"):
                ui.button(f"Willpower {wp}→{wp + 1}  ·  {costs.willpower_step(rs, character, wp)} XP",
                          on_click=lambda: _do(lambda: advancement.raise_willpower(rs, character))).props(
                    f"dense color={pal.button}")
                ui.button(f"Essence {ess}→{ess + 1}  ·  {costs.essence_step(rs, character, ess)} XP",
                          on_click=lambda: _do(lambda: advancement.raise_essence(rs, character))).props(
                    f"dense color={pal.button}")

        # --- reduce a trait (curse / Charm cost; free, refunds no XP) ------ #
        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            ui.label("Reduce a Trait").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
            ui.label("For curses and permanent Charm costs — free, refunds no XP, "
                     "logged and undoable.").classes("text-xs text-gray-600")
            lower_opts: dict[str, str] = {}
            for a in AttributeName:
                lower_opts[f"attr:{a.value}"] = f"Attribute · {_label(a.value)} ({character.attributes[a]})"
            for ab in AbilityName:
                if ab == AbilityName.CRAFT:
                    continue
                lower_opts[f"ability:{ab.value}"] = f"Ability · {_label(ab.value)} ({character.abilities.get(ab, 0)})"
            for vir in VirtueName:
                lower_opts[f"virtue:{vir.value}"] = f"Virtue · {_label(vir.value)} ({character.virtues[vir]})"
            lower_opts["willpower"] = f"Willpower ({derive.willpower(character)})"
            lower_opts["essence"] = f"Essence ({character.essence_rating})"
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select(lower_opts, value=sel["lower_target"],
                          on_change=lambda e: (sel.__setitem__("lower_target", e.value), panel.refresh())
                          ).props("dense").classes("flex-1")
                ui.input(value=sel["lower_reason"], placeholder="reason (e.g. curse)",
                         on_change=lambda e: sel.__setitem__("lower_reason", e.value)
                         ).props("dense").classes("flex-1")
                ui.button("Reduce", icon="arrow_downward",
                          on_click=lambda: _do(_reduce)).props("dense color=negative")

        # --- specialty ----------------------------------------------------- #
        # Charms, spells, Ox-Body packages and Combos are NOT bought here: they are
        # bought in place, on the Charms and Combos tabs, which switch from picking to
        # buying once chargen locks. A specialty has no home tab of its own.
        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            ui.label("Add").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select({a: _label(a.value) for a in AbilityName}, value=sel["spec_ability"],
                          label="Specialty in",
                          on_change=lambda e: sel.__setitem__("spec_ability", e.value)).props("dense").classes("w-40")
                ui.input(value=sel["spec_name"], placeholder="specialty name",
                         on_change=lambda e: sel.__setitem__("spec_name", e.value)).props("dense").classes("flex-1")
                ui.label(f"{costs.specialty_cost(rs, character)} XP").classes("text-xs w-12")
                ui.button("Add Specialty", on_click=lambda: _do(
                    lambda: (advancement.add_specialty(rs, character, sel["spec_ability"], sel["spec_name"]),
                             sel.__setitem__("spec_name", "")))).props(f"dense color={pal.button}")
            ui.label("Charms, spells and Ox-Body are bought on the Charms tab; "
                     "Combos on the Combos tab.").classes("text-xs text-gray-500")

        # --- crafts: each focus is its own rated Ability (core p.136) ----- #
        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            ui.label("Crafts").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
            craft_opts = {c.focus: f"{c.focus} {c.rating}" for c in character.crafts}
            craft_value = sel["craft_focus"] if sel["craft_focus"] in craft_opts else None
            craft_cur = next((c.rating for c in character.crafts if c.focus == craft_value), None)
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select(craft_opts, value=craft_value, label="Raise craft",
                          on_change=lambda e: (sel.__setitem__("craft_focus", e.value), panel.refresh())
                          ).props("dense").classes("flex-1")
                if craft_cur is not None and craft_cur < 5:
                    cost = costs.ability_step(rs, character, AbilityName.CRAFT, craft_cur)
                    ui.label(f"{craft_cur}→{craft_cur + 1}: {cost} XP").classes("text-xs w-24")
                    ui.button("Raise", on_click=lambda: _do(
                        lambda: advancement.raise_craft(rs, character, sel["craft_focus"]))).props(f"dense color={pal.button}")
                elif craft_cur is not None:
                    ui.label("max").classes("text-xs text-gray-400 w-24")
            new_cost = costs.ability_step(rs, character, AbilityName.CRAFT, 0)
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.input(value=sel["craft_new"], placeholder="new craft (e.g. Smithing)",
                         on_change=lambda e: sel.__setitem__("craft_new", e.value)).props("dense").classes("flex-1")
                ui.label(f"{new_cost} XP").classes("text-xs w-12")
                ui.button("Learn Craft", on_click=lambda: _do(
                    lambda: (advancement.learn_craft(rs, character, sel["craft_new"]),
                             sel.__setitem__("craft_new", "")))).props(f"dense color={pal.button}")

        # --- Astrological Colleges (Sidereal, p.98/p.265) ------------------- #
        # Shown only for a splat that ships colleges, the same data gate the editor
        # uses (b.college_dots > 0) — not a splat-name check. Unlike Craft, a College
        # is picked from the catalog, so both rows are dropdowns; the "new" one lists
        # only Colleges not already known. ★ marks the character's own Maiden's house.
        if rs.budgets_for(character.exalt_type, character.origin, character.upbringing).college_dots > 0 and rs.colleges:
            with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
                ui.label("Astrological Colleges").classes(
                    "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                owned = {c.college_id: c.rating for c in character.colleges}

                def _college_label(cid: str) -> str:
                    col = rs.colleges.get(cid)
                    if col is None:
                        return cid
                    return f"{'★ ' if col.house == character.caste else ''}{col.name}"

                raise_opts = {cid: f"{_college_label(cid)} {r}" for cid, r in owned.items()}
                cur_id = sel["college_id"] if sel["college_id"] in raise_opts else None
                cur = owned.get(cur_id)
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.select(raise_opts, value=cur_id, label="Raise college",
                              on_change=lambda e: (sel.__setitem__("college_id", e.value), panel.refresh())
                              ).props("dense").classes("flex-1")
                    if cur is not None and cur < 5:
                        cost = costs.college_step(rs, character, cur)
                        ui.label(f"{cur}→{cur + 1}: {cost} XP").classes("text-xs w-24")
                        ui.button("Raise", on_click=lambda: _do(
                            lambda: advancement.raise_college(rs, character, sel["college_id"]))
                            ).props(f"dense color={pal.button}")
                    elif cur is not None:
                        ui.label("max").classes("text-xs text-gray-400 w-24")

                new_opts = {cid: _college_label(cid) for cid in rs.colleges if cid not in owned}
                new_value = sel["college_new"] if sel["college_new"] in new_opts else None
                new_cost = costs.college_new_cost(rs, character)
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.select(new_opts, value=new_value, label="New college",
                              on_change=lambda e: (sel.__setitem__("college_new", e.value), panel.refresh())
                              ).props("dense").classes("flex-1")
                    ui.label(f"{new_cost} XP").classes("text-xs w-12")
                    ui.button("Learn", on_click=lambda: _do(
                        lambda: (advancement.learn_college(rs, character, sel["college_new"]),
                                 sel.__setitem__("college_new", None)))
                        ).props(f"dense color={pal.button}")

        # --- backgrounds (free; story-driven, not an XP-priced trait) ------ #
        # Backgrounds change in play through the story (a Manse falls, an Ally is
        # made), not by spending XP. They are an editable current value here with
        # no XP cost and no log entry — like equipment, not like dotted traits.
        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            with ui.row().classes("w-full items-baseline gap-2"):
                ui.label("Backgrounds").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                ui.label("free — no XP").classes("text-xs text-gray-500")
            bg_catalog = rs.backgrounds_for(character.exalt_type)
            bg_names = [b.name for b in bg_catalog]
            bg_descriptions = {b.name: b.description for b in bg_catalog}
            for idx, bg in enumerate(character.backgrounds):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    DescribedSelect(_opts_with(bg_names, bg.name), descriptions=bg_descriptions,
                                    value=bg.name or None, label="Background",
                                    with_input=True, new_value_mode="add-unique",
                                    on_change=lambda e, bg=bg: setattr(bg, "name", e.value or "")
                                    ).props("dense").classes("flex-1")
                    ui.input(value=bg.note, placeholder="note",
                             on_change=lambda e, bg=bg: setattr(bg, "note", e.value)
                             ).props("dense").classes("flex-1")
                    ui.number(value=bg.rating, min=0, max=5, format="%d",
                              on_change=lambda e, bg=bg: setattr(bg, "rating", int(e.value or 0))
                              ).props("dense").classes("w-16")
                    ui.button(icon="delete", on_click=lambda e=None, idx=idx: _del_bg(idx)
                              ).props("flat dense round")
            ui.button("Add background", icon="add", on_click=_add_bg).props("flat dense")

        # --- equipment (free; inline copy, not an XP-priced trait) --------- #
        # Swap/edit weapons and armour post-lock at no XP cost. Mirrors the editor's
        # equipment panels; summaries show material-effective stats (Exalt-gated).
        material_opts = {"": "— none —"} | {m.id: m.name for m in rs.material_catalog.values()}
        armor_names = [a.name for a in rs.armor_catalog.values()]
        weapon_names = [w.name for w in rs.weapon_catalog.values()]

        def _wsum(wp) -> str:
            eff = derive.effective_weapon(rs, character, wp)
            mat = derive.applied_material(rs, character, wp)
            tag = f"  ◈ {mat.name}" if mat else ""
            return f"Acc{eff.accuracy:+d} Dmg{eff.damage:+d}{eff.damage_type} Def{eff.defense:+d} Spd{eff.speed:+d}{tag}"

        def _asum(ar) -> str:
            eff = derive.effective_armor(rs, character, ar)
            mat = derive.applied_material(rs, character, ar)
            tag = f"  ◈ {mat.name}" if mat else ""
            return f"Soak {eff.soak_lethal}L/{eff.soak_bashing}B  Mob{eff.mobility_penalty:+d} Ftg{eff.fatigue}{tag}"

        def _statnum(item, attr, label, sm, smfn, *, signed=False):
            def _on(e, item=item, attr=attr, sm=sm, smfn=smfn):
                setattr(item, attr, int(e.value or 0))
                sm.set_text(smfn(item))
            kwargs = {} if signed else {"min": 0}
            ui.number(label=label, value=getattr(item, attr), format="%d",
                      on_change=_on, **kwargs).classes("w-20").props("dense")

        def _matsel(item, sm, smfn):
            def _on(e, item=item, sm=sm, smfn=smfn):
                setattr(item, "material", e.value or "")
                sm.set_text(smfn(item))
            ui.select(material_opts, value=item.material or "", label="Material",
                      on_change=_on).classes("w-40").props("dense")

        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            with ui.row().classes("w-full items-baseline gap-2"):
                ui.label("Equipment").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                ui.label("free — no XP").classes("text-xs text-gray-500")
            with ui.row().classes("w-full gap-2 no-wrap items-start"):
                with ui.column().classes("flex-1 gap-1"):
                    ui.label("Armor").classes("text-xs font-semibold")
                    for idx, ar in enumerate(character.armor):
                        with ui.column().classes(f"w-full gap-1 border-b border-{pal.fam}-900/10 pb-1"):
                            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                                ui.select(_opts_with(armor_names, ar.name), value=ar.name or None,
                                          with_input=True,
                                          new_value_mode="add-unique", label="Armor",
                                          on_change=lambda e, idx=idx: _set_armor(idx, e.value)
                                          ).props("dense").classes("flex-1")
                                asm = ui.label(_asum(ar)).classes("text-xs")
                                ui.button(icon="delete", on_click=lambda e=None, idx=idx: _del_equip("armor", idx)
                                          ).props("flat dense round")
                            with ui.expansion("Edit stats", icon="tune").classes("w-full"):
                                with ui.row().classes("w-full gap-2 flex-wrap"):
                                    _statnum(ar, "soak_lethal", "Soak L", asm, _asum)
                                    _statnum(ar, "soak_bashing", "Soak B", asm, _asum)
                                    _statnum(ar, "mobility_penalty", "Mob", asm, _asum, signed=True)
                                    _statnum(ar, "fatigue", "Ftg", asm, _asum)
                                    _statnum(ar, "artifact_rating", "Art", asm, _asum)
                                    _statnum(ar, "attunement", "Attune", asm, _asum)
                                    _statnum(ar, "resources_cost", "Res", asm, _asum)
                                    _matsel(ar, asm, _asum)
                    ui.button("Add armor", icon="add", on_click=lambda: _add_equip("armor")).props("flat dense")
                with ui.column().classes("flex-1 gap-1"):
                    ui.label("Weapons").classes("text-xs font-semibold")
                    for idx, wp in enumerate(character.weapons):
                        with ui.column().classes(f"w-full gap-1 border-b border-{pal.fam}-900/10 pb-1"):
                            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                                ui.select(_opts_with(weapon_names, wp.name), value=wp.name or None,
                                          with_input=True,
                                          new_value_mode="add-unique", label="Weapon",
                                          on_change=lambda e, idx=idx: _set_weapon(idx, e.value)
                                          ).props("dense").classes("flex-1")
                                wsm = ui.label(_wsum(wp)).classes("text-xs")
                                ui.button(icon="delete", on_click=lambda e=None, idx=idx: _del_equip("weapons", idx)
                                          ).props("flat dense round")
                            with ui.expansion("Edit stats", icon="tune").classes("w-full"):
                                with ui.row().classes("w-full gap-2 flex-wrap"):
                                    _statnum(wp, "speed", "Spd", wsm, _wsum, signed=True)
                                    _statnum(wp, "accuracy", "Acc", wsm, _wsum, signed=True)
                                    _statnum(wp, "damage", "Dmg", wsm, _wsum, signed=True)
                                    ui.select(["L", "B"], value=wp.damage_type or "L", label="Type",
                                              on_change=lambda e, wp=wp, wsm=wsm: (
                                                  setattr(wp, "damage_type", e.value or "L"),
                                                  wsm.set_text(_wsum(wp)))).classes("w-16").props("dense")
                                    _statnum(wp, "defense", "Def", wsm, _wsum, signed=True)
                                    _statnum(wp, "rate", "Rate", wsm, _wsum)
                                    _statnum(wp, "range", "Rng", wsm, _wsum)
                                    _statnum(wp, "artifact_rating", "Art", wsm, _wsum)
                                    _statnum(wp, "attunement", "Attune", wsm, _wsum)
                                    _statnum(wp, "resources_cost", "Res", wsm, _wsum)
                                    _matsel(wp, wsm, _wsum)
                    ui.button("Add weapon", icon="add", on_click=lambda: _add_equip("weapons")).props("flat dense")

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
            amount = ui.number(value=sel["add_amount"], format="%d").props("dense").classes("w-20")
            ui.button("Adjust XP", icon="add", on_click=lambda: (
                advancement.add_xp(character, int(amount.value or 0)), refresh_all())).props(f"dense color={pal.button}")
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

    def refresh_all() -> None:
        panel.refresh()
        ledger.refresh()

    def save() -> None:
        persistence.save_character(character, save_path)
        ui.notify(f"Saved to {save_path}", type="positive")

    # ---- layout ----------------------------------------------------------- #
    if with_header:
        ui.add_head_html(pal.head_style())

    with ui.row().classes("w-full max-w-6xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            if with_header:
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Experience").classes("text-xl font-bold")
                    ui.button("Save", icon="save", on_click=save).props(f"color={pal.button}")
            panel()
        with ui.column().classes("w-72 gap-2 sticky top-4"):
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                ui.label("Experience").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                ledger()


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
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
