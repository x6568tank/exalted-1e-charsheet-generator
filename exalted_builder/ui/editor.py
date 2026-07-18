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
from ..engine import derive, validate
from ..models.character import (
    Armor, BackgroundEntry, Character, CraftRating, HealthLevel, Specialty,
    VirtueFlaw, Weapon)

_BASE_HEALTH = {0: 1, -1: 2, -2: 2, -4: 1}   # base levels per penalty tier


def _health_total(character: Character, penalty: int) -> int:
    """Effective number of health levels at a tier: base + added - removed."""
    delta = sum((-1 if hl.removed else 1)
                for hl in character.health_bonus_levels if hl.penalty == penalty)
    return max(0, _BASE_HEALTH.get(penalty, 0) + delta)
from ..models.rules import AbilityName, RuleSet, VirtueName
from . import view as viewmod

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "exalted_builder" / "data"
_EXAMPLE = _REPO_ROOT / "examples" / "ashes-of-dawn.character.json"
_ACCENT = "#8a5a1a"

# Presentation-only: intra-splat chargen origins to offer per Exalt type, and their
# display labels. The origin *value* drives ruleset.budgets_for (keyed "<exalt>" for
# the first/default origin and "<exalt>:<origin>" for the rest); all the budget
# numbers live in chargen_budgets.json — this map is just which choices to show.
_SPLAT_ORIGINS: dict[str, dict[str, str]] = {
    "Dragon-Blooded": {"dynastic": "Dynastic", "outcaste": "Outcaste"},
}


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def _opts_with(names: list[str], current: str | None) -> list[str]:
    """Options for an add-unique select that always contain the current value.

    NiceGUI 3.x raises ``ValueError: Invalid value`` if a select is constructed
    with a ``value`` not present in its options, so a custom (off-catalog) name
    typed into one of these comboboxes would crash on the next render/reload.
    Folding the current value into the option list keeps that custom entry legal."""
    if current and current not in names:
        return [*names, current]
    return names


def build_editor(ruleset: RuleSet, character: Character, save_path: Path,
                 *, with_header: bool = True) -> None:
    """Render the whole editor for `character`. Pure-ish wiring: every control
    mutates the Character and refreshes the live readout. With `with_header=False`
    the title/Save bar is omitted (the embedding app provides one)."""

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

    # ---- bonus-point spend log (per-domain; lives under the caste box) ----- #
    @ui.refreshable
    def bp_log() -> None:
        bd = validate.bonus_point_breakdown(ruleset, character)
        ui.label("Bonus Points").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")
        color = "#b91c1c" if bd.over_budget else "#15803d"
        ui.label(f"{bd.total} / {bd.available} spent").classes("text-sm font-semibold").style(f"color:{color}")
        ui.separator()
        for line in bd.lines:
            muted = "" if line.points else "text-gray-400"
            with ui.row().classes("w-full justify-between no-wrap items-baseline"):
                ui.label(line.domain).classes(f"text-xs {muted}")
                ui.label(str(line.points)).classes(f"text-xs {muted}")

    def changed() -> None:
        readout.refresh()
        bp_log.refresh()

    # ---- a clickable dot-track rating control ----------------------------- #
    def dots(get, setv, lo: int, hi: int):
        @ui.refreshable
        def show() -> None:
            v = get()
            top = max(hi, v)            # always show enough pips to step a too-high value down
            with ui.row().classes("gap-0 items-center no-wrap"):
                for i in range(1, top + 1):
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
        # chargen budget for THIS character (splat + origin), so panel headers show
        # the right numbers (Solar 8/6/4·25; DB Dynastic 7/6/4·35, Outcaste ·25).
        b = ruleset.budgets_for(character.exalt_type, character.origin)
        ap = "/".join(str(p) for p in b.attribute_pools)

        # caste-info box (left) + identity fields (right). The BP-spend log lives in
        # the right-hand sticky column under Live Validation, not here.
        with ui.row().classes("w-full gap-2 no-wrap items-stretch"):
            with ui.card().classes("w-72 flex-none p-3 bg-amber-50/40 border border-amber-900/20 gap-1"):
                if caste_def:
                    ui.label(f"{caste_def.label} Caste").classes(
                        "text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")
                    if caste_def.description:
                        ui.label(caste_def.description).classes("text-xs")
                    ui.label("Caste Abilities: " + ", ".join(
                        _label(a.value) for a in caste_def.caste_abilities)).classes("text-xs italic")
                    if caste_def.anima_powers:
                        ui.separator()
                        ui.label("Anima Power").classes("text-xs font-semibold").style(f"color:{_ACCENT}")
                        ui.label(caste_def.anima_powers).classes("text-xs")
                else:
                    ui.label("Unknown caste").classes("text-xs text-gray-500")
            with ui.column().classes("flex-1 gap-2 min-w-0"):
                with panel("Identity"):
                    with ui.row().classes("w-full gap-3 no-wrap"):
                        ui.input("Name", value=character.name,
                                 on_change=lambda e: (setattr(character, "name", e.value), changed())).classes("flex-1")
                        ui.input("Concept", value=character.concept,
                                 on_change=lambda e: setattr(character, "concept", e.value)).classes("flex-1")
                    with ui.row().classes("w-full gap-3 no-wrap items-end"):
                        exalt_opts = {ex.id: ex.label for ex in ruleset.exalts.values()}
                        exalt_opts.setdefault(character.exalt_type, character.exalt_type)
                        ui.select(exalt_opts, label="Exalt type", value=character.exalt_type,
                                  on_change=lambda e: set_exalt_type(e.value)).classes("flex-1")
                        caste_opts = {cd.id: cd.label for cd in ruleset.castes.values()
                                      if cd.exalt_type == character.exalt_type}
                        # keep the current caste selectable even if off-splat (NiceGUI 3.x
                        # ui.select raises if value ∉ options — see the select-value gotcha)
                        caste_opts.setdefault(character.caste, character.caste)
                        ui.select(caste_opts, label="Caste", value=character.caste,
                                  on_change=lambda e: set_caste(e.value)).classes("flex-1")
                        origins = _SPLAT_ORIGINS.get(character.exalt_type)
                        if origins:
                            ui.select(origins, label="Origin",
                                      value=character.origin or next(iter(origins)),
                                      on_change=lambda e: set_origin(e.value)).classes("flex-1")
                        nature_names = [n.name for n in ruleset.nature_catalog.values()]
                        ui.select(_opts_with(nature_names, character.nature), label="Nature",
                                  value=character.nature or None,
                                  with_input=True, new_value_mode="add-unique",
                                  on_change=lambda e: setattr(character, "nature", e.value or "")).classes("flex-1")
                        ui.input("Anima", value=character.anima,
                                 on_change=lambda e: setattr(character, "anima", e.value)).classes("flex-1")
                    ui.select({a: _label(a.value) for a in AbilityName}, label=f"Favored abilities (pick {b.favored_count})",
                              value=list(character.favored_abilities), multiple=True,
                              on_change=lambda e: set_favored(e.value)).classes("w-full").props("use-chips")

        # attributes
        with panel(f"Attributes (prioritise {ap})"):
            with ui.row().classes("w-full gap-2 no-wrap"):
                for category, members in validate.ATTRIBUTE_CATEGORIES.items():
                    with ui.column().classes("flex-1 gap-1"):
                        spent_label = ui.label().classes("text-xs font-semibold")

                        def show_spent(label=spent_label, members=members, category=category):
                            spent = sum(character.attributes[a] - 1 for a in members)
                            label.set_text(f"{category} — {spent} spent")

                        show_spent()
                        for a in members:
                            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                                ui.label(_label(a.value)).classes("text-sm w-28")
                                # update this column's tally live as its dots change
                                dots(lambda a=a: character.attributes[a],
                                     lambda v, a=a, upd=show_spent: (
                                         character.attributes.__setitem__(a, v), upd()),
                                     1, 5)

        # abilities (by ability-caste group)
        with panel(f"Abilities ({b.ability_dots} dots; ≥{b.ability_min_caste_favored} caste/favoured; ≤{b.ability_cap_pre_bp} each pre-bonus)"):
            groups = [(cd.label, cd.caste_abilities) for cd in ruleset.castes.values()
                      if cd.exalt_type == character.exalt_type]
            for start in range(0, len(groups), 3):
                with ui.row().classes("w-full gap-2 no-wrap"):
                    for group_label, abilities in groups[start:start + 3]:
                        with ui.column().classes("flex-1 gap-1"):
                            ui.label(group_label).classes("text-xs font-semibold").style(f"color:{_ACCENT}")
                            for a in abilities:
                                mark = "●" if a in caste_abilities else ("✦" if a in character.favored_abilities else "")
                                with ui.row().classes("w-full items-center gap-1 no-wrap"):
                                    ui.label(mark).classes("text-xs w-3").style(f"color:{_ACCENT}")
                                    if a == AbilityName.CRAFT:
                                        # Craft is per-focus (p.136) — edited in its own panel below.
                                        ui.label("Craft").classes("text-sm flex-1 truncate")
                                        ui.label("↓ per-focus").classes("text-xs text-gray-400")
                                        continue
                                    ui.label(_label(a.value)).classes("text-sm flex-1 truncate")
                                    dots(lambda a=a: character.abilities[a],
                                         lambda v, a=a: character.abilities.__setitem__(a, v), 0, 5)

        # crafts — each focus is its own rated Ability (core p.136)
        craft_cf = AbilityName.CRAFT in caste_abilities or AbilityName.CRAFT in character.favored_abilities
        cf_tag = " · Caste/Favoured" if craft_cf else ""
        with panel(f"Crafts (each focus a separate Ability{cf_tag})"):
            for idx, cr in enumerate(character.crafts):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.input(value=cr.focus, placeholder="craft (e.g. Smithing)",
                             on_change=lambda e, cr=cr: (setattr(cr, "focus", e.value), changed())).classes("flex-1")
                    dots(lambda cr=cr: cr.rating, lambda v, cr=cr: setattr(cr, "rating", v), 0, 5)
                    ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_craft(idx)).props("flat dense round")
            ui.button("Add craft", icon="add", on_click=add_craft).props("flat dense")

        # virtues + essence + willpower
        with ui.row().classes("w-full gap-2 no-wrap items-start"):
            with panel(f"Virtues ({b.virtue_dots} dots; ≤{b.virtue_cap_pre_bp} pre-bonus)").classes("flex-1"):
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
        bg_names = [b.name for b in ruleset.background_catalog.values()]
        with panel(f"Backgrounds ({b.background_dots} dots; ≤{b.background_cap_pre_bp} pre-bonus)"):
            for idx, bg in enumerate(character.backgrounds):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    (ui.select(_opts_with(bg_names, bg.name), value=bg.name or None, label="Background",
                               with_input=True, new_value_mode="add-unique",
                               on_change=lambda e, bg=bg: setattr(bg, "name", e.value or ""))
                     .classes("flex-1"))
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

        # equipment — inline copies; the catalog autofills, then every stat is
        # editable per item (custom or tweaked artifact/masterwork). Each item's
        # numbers live behind an "Edit stats" expander; the summary updates live.
        armor_names = [a.name for a in ruleset.armor_catalog.values()]
        weapon_names = [w.name for w in ruleset.weapon_catalog.values()]
        # "" = mundane; material bonuses apply only for the matching Exalt (p.341).
        material_opts = {"": "— none —"} | {
            m.id: m.name for m in ruleset.material_catalog.values()}

        def _weapon_summary(wp) -> str:
            eff = derive.effective_weapon(ruleset, character, wp)
            mat = derive.applied_material(ruleset, character, wp)
            tag = f"  ◈ {mat.name}" if mat else ""
            return f"Acc{eff.accuracy:+d} Dmg{eff.damage:+d}{eff.damage_type} Def{eff.defense:+d} Spd{eff.speed:+d}{tag}"

        def _armor_summary(ar) -> str:
            eff = derive.effective_armor(ruleset, character, ar)
            mat = derive.applied_material(ruleset, character, ar)
            tag = f"  ◈ {mat.name}" if mat else ""
            return f"Soak {eff.soak_lethal}L/{eff.soak_bashing}B  Mob{eff.mobility_penalty:+d} Ftg{eff.fatigue}{tag}"

        def material_select(item, sm_label, sm_fn):
            def _on(e, item=item, sm_label=sm_label, sm_fn=sm_fn):
                setattr(item, "material", e.value or "")
                sm_label.set_text(sm_fn(item))
                changed()
            ui.select(material_opts, value=item.material or "", label="Material",
                      on_change=_on).classes("w-40").props("dense")

        def stat_num(item, attr, label, sm_label, sm_fn, *, signed=False):
            def _on(e, item=item, attr=attr, sm_label=sm_label, sm_fn=sm_fn):
                setattr(item, attr, int(e.value or 0))
                sm_label.set_text(sm_fn(item))
                changed()
            kwargs = {} if signed else {"min": 0}
            ui.number(label=label, value=getattr(item, attr), format="%d",
                      on_change=_on, **kwargs).classes("w-20").props("dense")

        with ui.row().classes("w-full gap-2 no-wrap items-start"):
            with panel("Armor (sets soak)").classes("flex-1"):
                for idx, ar in enumerate(character.armor):
                    with ui.column().classes("w-full gap-1 border-b border-amber-900/10 pb-1"):
                        with ui.row().classes("w-full items-center gap-2 no-wrap"):
                            ui.select(_opts_with(armor_names, ar.name), value=ar.name or None,
                                      with_input=True,
                                      new_value_mode="add-unique", label="Armor",
                                      on_change=lambda e, idx=idx: set_armor(idx, e.value)).classes("flex-1")
                            asm = ui.label(_armor_summary(ar)).classes("text-xs")
                            ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_item("armor", idx)).props("flat dense round")
                        with ui.expansion("Edit stats", icon="tune").classes("w-full"):
                            with ui.row().classes("w-full gap-2 flex-wrap"):
                                stat_num(ar, "soak_lethal", "Soak L", asm, _armor_summary)
                                stat_num(ar, "soak_bashing", "Soak B", asm, _armor_summary)
                                stat_num(ar, "mobility_penalty", "Mob", asm, _armor_summary, signed=True)
                                stat_num(ar, "fatigue", "Ftg", asm, _armor_summary)
                                stat_num(ar, "artifact_rating", "Art", asm, _armor_summary)
                                stat_num(ar, "attunement", "Attune", asm, _armor_summary)
                                stat_num(ar, "resources_cost", "Res", asm, _armor_summary)
                                material_select(ar, asm, _armor_summary)
                ui.button("Add armor", icon="add", on_click=lambda: add_item("armor")).props("flat dense")
            with panel("Weapons").classes("flex-1"):
                for idx, wp in enumerate(character.weapons):
                    with ui.column().classes("w-full gap-1 border-b border-amber-900/10 pb-1"):
                        with ui.row().classes("w-full items-center gap-2 no-wrap"):
                            ui.select(_opts_with(weapon_names, wp.name), value=wp.name or None,
                                      with_input=True,
                                      new_value_mode="add-unique", label="Weapon",
                                      on_change=lambda e, idx=idx: set_weapon(idx, e.value)).classes("flex-1")
                            wsm = ui.label(_weapon_summary(wp)).classes("text-xs")
                            ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_item("weapons", idx)).props("flat dense round")
                        with ui.expansion("Edit stats", icon="tune").classes("w-full"):
                            with ui.row().classes("w-full gap-2 flex-wrap"):
                                stat_num(wp, "speed", "Spd", wsm, _weapon_summary, signed=True)
                                stat_num(wp, "accuracy", "Acc", wsm, _weapon_summary, signed=True)
                                stat_num(wp, "damage", "Dmg", wsm, _weapon_summary, signed=True)
                                ui.select(["L", "B"], value=wp.damage_type or "L", label="Type",
                                          on_change=lambda e, wp=wp, wsm=wsm: (setattr(wp, "damage_type", e.value or "L"),
                                                                              wsm.set_text(_weapon_summary(wp)), changed())
                                          ).classes("w-16").props("dense")
                                stat_num(wp, "defense", "Def", wsm, _weapon_summary, signed=True)
                                stat_num(wp, "rate", "Rate", wsm, _weapon_summary)
                                stat_num(wp, "range", "Rng", wsm, _weapon_summary)
                            with ui.row().classes("w-full gap-2 flex-wrap"):
                                stat_num(wp, "min_strength", "Min Str", wsm, _weapon_summary)
                                stat_num(wp, "min_dexterity", "Min Dex", wsm, _weapon_summary)
                                stat_num(wp, "min_martial_arts", "Min MA", wsm, _weapon_summary)
                                stat_num(wp, "max_strength", "Max Str", wsm, _weapon_summary)
                                stat_num(wp, "artifact_rating", "Art", wsm, _weapon_summary)
                                stat_num(wp, "attunement", "Attune", wsm, _weapon_summary)
                                stat_num(wp, "resources_cost", "Res", wsm, _weapon_summary)
                                material_select(wp, wsm, _weapon_summary)
                            ui.input("Notes", value=wp.notes,
                                     on_change=lambda e, wp=wp: (setattr(wp, "notes", e.value), changed())).classes("w-full").props("dense")
                ui.button("Add weapon", icon="add", on_click=lambda: add_item("weapons")).props("flat dense")

        # virtue flaw + bonus health levels (e.g. Ox-Body Technique)
        with ui.row().classes("w-full gap-2 no-wrap items-start"):
            with panel("Virtue Flaw").classes("flex-1"):
                vf = character.virtue_flaw
                ui.select({v: _label(v.value) for v in VirtueName}, label="Flawed Virtue",
                          value=vf.virtue if vf else None,
                          on_change=lambda e: set_virtue_flaw_virtue(e.value)).classes("w-full")
                ui.input("Description", value=vf.description if vf else "",
                         on_change=lambda e: set_virtue_flaw_desc(e.value)).classes("w-full")
            with panel("Bonus health levels per tier (charms raise, curses lower)").classes("flex-1"):
                with ui.row().classes("w-full gap-3 no-wrap"):
                    for p in (0, -1, -2, -4):
                        total = _health_total(character, p)
                        ui.number(label=("-0" if p == 0 else str(p)), value=total, min=0, max=20, format="%d",
                                  on_change=lambda e, p=p: set_health_total(p, int(e.value or 0))).classes("w-16")

        # charms/spells (read-only here; the picker is the next slice)
        with panel(f"Charms ({len(character.charms) + len(character.ox_body)}) & Spells ({len(character.spells)}) — edit via the picker"):
            view = viewmod.build_sheet_view(ruleset, character)
            for c in view.charms:
                ui.label(f"{c.name} · {c.category}").classes("text-xs")
            for s in view.spells:
                ui.label(f"{s.name} · {s.circle}").classes("text-xs")

    # ---- structural mutators (refresh body + readout) --------------------- #
    def set_exalt_type(value: str) -> None:
        character.exalt_type = value
        # keep the caste coherent with the new splat: if the current caste doesn't
        # belong to it, switch to that splat's first caste (if the splat has any).
        valid = [cd.id for cd in ruleset.castes.values() if cd.exalt_type == value]
        if character.caste not in valid and valid:
            character.caste = valid[0]
        # keep the origin coherent: default to the splat's first origin, or clear it
        # for splats that have no intra-splat origin variants.
        origins = _SPLAT_ORIGINS.get(value)
        character.origin = next(iter(origins)) if origins else ""
        body.refresh(); changed()

    def set_caste(value: str) -> None:
        character.caste = value
        body.refresh(); changed()

    def set_origin(value: str) -> None:
        character.origin = value
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

    def add_craft() -> None:
        character.crafts.append(CraftRating(focus="", rating=1))
        body.refresh(); changed()

    def remove_craft(idx: int) -> None:
        del character.crafts[idx]
        body.refresh(); changed()

    def add_spec() -> None:
        character.specialties.append(Specialty(ability=AbilityName.MELEE, name="", rating=1))
        body.refresh(); changed()

    def remove_spec(idx: int) -> None:
        del character.specialties[idx]
        body.refresh(); changed()

    # equipment / health-level / virtue-flaw mutators
    def add_item(field: str) -> None:
        factory = {"armor": lambda: Armor(name=""), "weapons": lambda: Weapon(name="")}[field]
        getattr(character, field).append(factory())
        body.refresh(); changed()

    def set_health_total(penalty: int, total: int) -> None:
        # Rebuild this tier: add bonus levels above base, or removed levels below it.
        base_n = _BASE_HEALTH.get(penalty, 0)
        kept = [hl for hl in character.health_bonus_levels if hl.penalty != penalty]
        if total > base_n:
            kept += [HealthLevel(penalty=penalty, source_charm="Bonus")
                     for _ in range(total - base_n)]
        elif total < base_n:
            kept += [HealthLevel(penalty=penalty, source_charm="Curse", removed=True)
                     for _ in range(base_n - total)]
        character.health_bonus_levels = kept
        changed()

    def remove_item(field: str, idx: int) -> None:
        del getattr(character, field)[idx]
        body.refresh(); changed()

    def set_armor(idx: int, name: str) -> None:
        # A catalog match autofills (overwrites) the stats; a custom name just
        # renames the item, preserving any stats already typed for it.
        entry = next((a for a in ruleset.armor_catalog.values() if a.name == name), None)
        if entry:
            character.armor[idx] = Armor(
                name=entry.name, soak_lethal=entry.soak_lethal, soak_bashing=entry.soak_bashing,
                mobility_penalty=entry.mobility_penalty, fatigue=entry.fatigue,
                artifact_rating=entry.artifact_rating, attunement=entry.attunement,
                resources_cost=entry.resources_cost)
        else:
            character.armor[idx].name = name or ""
        body.refresh(); changed()

    def set_weapon(idx: int, name: str) -> None:
        e = next((w for w in ruleset.weapon_catalog.values() if w.name == name), None)
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
        body.refresh(); changed()

    def set_virtue_flaw_virtue(virtue: VirtueName) -> None:
        desc = character.virtue_flaw.description if character.virtue_flaw else ""
        character.virtue_flaw = VirtueFlaw(virtue=virtue, description=desc)
        changed()

    def set_virtue_flaw_desc(text: str) -> None:
        if character.virtue_flaw is None:
            character.virtue_flaw = VirtueFlaw(virtue=VirtueName.COMPASSION, description=text)
        else:
            character.virtue_flaw.description = text

    def save() -> None:
        persistence.save_character(character, save_path)
        ui.notify(f"Saved to {save_path}", type="positive")

    # ---- layout: editor on the left, sticky readout on the right ---------- #
    if with_header:
        ui.add_head_html("<style>body{background:#f7f1e3;color:#3a2e1f;}</style>")
    with ui.row().classes("w-full max-w-7xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            if with_header:
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Chargen Editor").classes("text-xl font-bold")
                    ui.button("Save", icon="save", on_click=save).props("color=brown")
            body()
        with ui.column().classes("w-80 gap-2 sticky top-4"):
            with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30"):
                ui.label("Live Validation").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")
                readout()
            with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30"):
                bp_log()


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
