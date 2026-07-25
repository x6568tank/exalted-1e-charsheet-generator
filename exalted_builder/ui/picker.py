"""
ui/picker.py — NiceGUI charm-tree picker (Cytoscape).

Renders a Charm category's prerequisite graph with Cytoscape.js. Nodes are
colour-coded owned / available / locked (from view.build_charm_graph, which asks
the engine). Tapping a node toggles ownership: an available Charm is learned, an
owned one is dropped; locked Charms refuse with a notice. A live readout re-runs
validation on each change. Save writes JSON via persistence.

**Two modes, one picker.** Before Finish & Lock this is a chargen sheet: picks are
free and reversible, and the readout tallies them against the chargen pool. After the
lock it is a shop — Charms, spells and Ox-Body packages are bought through
engine.advancement (priced, legality-checked, appended to the XP log), the price
rides on the button, and nothing can be dropped: the only refund is undoing the most
recent purchase from the XP tab's ledger.

No game logic here: the toggle asks engine.validate.meets_charm_requirements, prices
come from engine.costs, and node states come from the engine. Cytoscape is loaded
from a CDN, so the browser needs network access.

Run:
    python -m exalted_builder.ui.picker [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..engine import advancement, costs, refit, validate
from ..models.character import (AnimalForm, BeastmanGiftPurchase, Character,
                                OxBodyPurchase, SubmodulePurchase)
from ..models.rules import RuleSet, circle_kind
from . import theme
from . import view as viewmod
from .assets import cytoscape_head_html

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "exalted_builder" / "data"
_EXAMPLE = _REPO_ROOT / "examples" / "ashes-of-dawn.character.json"


def _style(pal: theme.Palette) -> list[dict]:
    """Cytoscape stylesheet themed to `pal`. Uniform size/font for every node;
    owned / available / locked differ only by fill and border colour. Labels sit
    below the node on the parchment background, so the label outline is the page
    background and the owned fill is the splat accent (gold Solar / red DB)."""
    return [
        {"selector": "node", "style": {
            "label": "data(label)", "font-size": "14px", "font-weight": 600, "text-wrap": "wrap",
            "text-max-width": "130px", "text-valign": "bottom", "text-margin-y": 6,
            "text-outline-color": pal.bg, "text-outline-width": 3,
            "color": pal.ink, "width": 40, "height": 40,
            "background-color": "#cbd5e1", "border-width": 2, "border-color": "#94a3b8"}},
        {"selector": "node.owned", "style": {
            "background-color": pal.accent, "border-color": pal.accent_dark}},
        {"selector": "node.available", "style": {
            "background-color": "#86efac", "border-color": "#15803d", "border-width": 3}},
        {"selector": "node.locked", "style": {
            "background-color": "#e5e7eb", "border-color": "#cbd5e1"}},
        # Prerequisites pulled in from another category: same owned/available/locked
        # fill, but drawn smaller with a dashed border so it is obvious they are
        # context for this tree rather than members of it.
        {"selector": "node.external", "style": {
            "width": 30, "height": 30, "border-style": "dashed",
            "font-style": "italic", "font-weight": 400}},
        {"selector": "edge", "style": {
            "width": 2, "line-color": "#9ca3af", "target-arrow-color": "#9ca3af",
            "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 1.1}},
    ]


def _elements(graph: viewmod.CharmGraph) -> list[dict]:
    nodes = [{"data": {"id": n.id, "label": n.label},
              "classes": f"{n.state} external" if n.external else n.state}
             for n in graph.nodes]
    edges = [{"data": {"id": f"{s}__{t}", "source": s, "target": t}} for s, t in graph.edges]
    return nodes + edges


def build_picker(ruleset: RuleSet, character: Character, save_path: Path,
                 *, with_header: bool = True, register_events: bool = True):
    """Render the picker. Returns its `toggle(charm_id)` so an embedding app can
    own a single charm_toggle event handler (set register_events=False then).
    with_header=False omits the title/Save bar and the head <script> (the host
    app supplies Cytoscape)."""
    pal = theme.palette(character.exalt_type)

    def in_play() -> bool:
        """True once chargen is locked: picks become XP purchases (see the module
        docstring). Read live rather than captured, so the same picker is correct
        either side of a lock."""
        return character.chargen_locked

    def _buy(action) -> bool:
        """Run an engine.advancement purchase; surface its refusal (unaffordable,
        prerequisites, cap) as a notice. True when the character changed."""
        try:
            action()
        except advancement.AdvancementError as ex:
            ui.notify(str(ex), type="warning")
            return False
        return True

    def _afford(cost: int) -> bool:
        return cost <= advancement.xp_available(character)

    def _pretty(cat: str) -> str:
        if ":" in cat:                          # 'martial_arts:snake' -> 'Martial Arts: Snake'
            base, style = cat.split(":", 1)
            return f"{base.replace('_', ' ').title()}: {style.replace('_', ' ').title()}"
        return cat.replace("_", " ").title()

    # A toggle splits the picker into three pages: the ability Charm trees, the
    # martial-arts trees, and the spell list. Every `martial_arts:*` category goes
    # on the Martial Arts page — including the enlightenment tree
    # ('martial_arts:enlightenment'), which is the Dragon-Path initiation rather
    # than a style, but is martial arts and is looked for among them.
    def _group_of(cat: str) -> str:
        return "styles" if cat.startswith("martial_arts:") else "abilities"

    def _visible_category_options(group: str | None = None) -> dict[str, str]:
        """Category-dropdown options for the CURRENT character state: the categories
        of the SELECTED splat's page in the selected group, minus any a rule hides
        right now. The only such rule today is the Dragon-Blooded Dragon-Path gate
        (DB p241) — the elemental Dragon styles appear only once both enlightenment
        Charms (Spirit Sight + Spirit Walking) are known. That gate is the *character's*
        own, so it does not follow them onto a foreign splat's page: an Eclipse
        learning Dragon-style Charms needs a tutor, not the Immaculate initiation."""
        want = state["group"] if group is None else group
        cats = sorted({c.category for c in ruleset.charms.values()
                       if viewmod.charm_on_splat_page(ruleset, character, c, state["splat"])
                       and validate.category_available(ruleset, character, c.category)
                       and _group_of(c.category) == want})
        return {c: _pretty(c) for c in cats}

    # ---- Splat page (Eclipse generalist rule, core p.127) ------------------- #
    def _foreign_open() -> bool:
        return validate.foreign_charms_open(ruleset, character)

    def _splat_options() -> dict[str, str]:
        """The Splat dropdown's options: the character's own Exalt type always, plus —
        while the caste privilege is open — every other Exalt type with Charms to
        show. One entry means the dropdown is pointless and it stays hidden."""
        opts = {character.exalt_type: character.exalt_type}
        if _foreign_open():
            others = {c.exalt_type for c in ruleset.charms.values()
                      if c.exalt_type and c.exalt_type != character.exalt_type}
            opts.update({s: s for s in sorted(others)})
        return opts

    # The caste privilege is a property of the caste, so whether the Splat control
    # exists at all is fixed for this render; whether it OFFERS anything depends on
    # the Storyteller-permission flag, which is live pre-lock.
    _foreign_caste = validate.foreign_charms_caste(ruleset, character) is not None

    _all_categories = sorted({c.category for c in ruleset.charms.values()
                              if validate.charm_matches_splat(character, c, ruleset)})
    _start = ("melee" if "melee" in _all_categories
              else (_all_categories[0] if _all_categories else ""))
    state = {"category": _start, "group": _group_of(_start) if _start else "abilities",
             "circle": "", "splat": character.exalt_type}
    _has_styles = any(_group_of(c) == "styles" for c in _all_categories)
    # Which circles this character could ever reach is fixed by their splat's Occult
    # tree, so the Spells page — and its Circle dropdown — either exists for them or
    # never does. Ordered globally (sorcery Terrestrial→Solar, then necromancy
    # Shadowlands→Void); an Abyssal reaches both tracks, a plain Solar only sorcery.
    _spell_circles = [ce for ce in viewmod.CIRCLE_DISPLAY_ORDER
                      if ce.value in {r.circle for r in viewmod.build_spell_picker(ruleset, character)}]
    _has_spells = bool(_spell_circles)
    _exalt_def = ruleset.exalt_for(character.exalt_type)
    _has_forms = bool(_exalt_def and _exalt_def.form_library)
    GROUPS = {"abilities": "Abilities"}
    if _has_styles:
        GROUPS["styles"] = "Martial Arts"
    if _has_spells:
        GROUPS["spells"] = "Spells"
        state["circle"] = _spell_circles[0].value
    if _has_forms:
        GROUPS["forms"] = "Form Library"
    # The Slot/Panoply manager, for a Charm-Slot splat or an Eclipse who crossed over.
    _has_panoply = refit.supports_refit(ruleset, character)
    if _has_panoply:
        GROUPS["panoply"] = "Vat Refit"

    # The Alchemical "general" category (the 18 Augmentation templates) renders as two
    # per-type pop-ups instead of an 18-node graph. None for every other splat.
    _augment_category = viewmod.augmentation_category(ruleset, character)

    def _is_augment_page() -> bool:
        """True when the current page is the collapsed Augmentation view (Alchemical
        'general'), which replaces the Cytoscape canvas with two pop-up cards."""
        return (_augment_category is not None and state["group"] == "abilities"
                and state["category"] == _augment_category)

    def _is_graph_page() -> bool:
        """The Charm-tree groups (Abilities / Martial Arts) own the category dropdown;
        the Spells and Form Library groups render a plain panel in its place. The
        Augmentation category is still an Abilities page (so it keeps the dropdown) but
        swaps the CANVAS for pop-up cards — see _is_augment_page."""
        return state["group"] in ("abilities", "styles")
    widgets: dict = {}                          # holds the live group toggle + category <select>

    # ---- Immaculate-vs-standard chargen path banner (Dragon-Blooded) ------- #
    def _immaculate_path_banner() -> None:
        """For a Dragon-Blooded, spell out which chargen Charm path they are on.
        The Immaculate path is triggered by any *Immaculate* Charm — the five
        Dragon-style trees (Air/Earth/Fire/Water/Wood Dragon), NOT Martial Arts in
        general: Five-Dragon Style is Martial Arts but a normal Charm and does not
        switch paths. Counts come from the budget, never hardcoded."""
        if character.exalt_type != "Dragon-Blooded":
            return
        b = ruleset.budgets_for(character.exalt_type, character.origin)
        if validate.immaculate_martial_artist(ruleset, character):
            msg = (f"Immaculate path — {b.immaculate_charm_count} Charms from one "
                   f"Dragon style; Aspect/Favored minimum waived.")
        else:
            msg = (f"Standard path — {b.charm_count} Charms, ≥{b.charm_min_caste_favored} "
                   f"Aspect/Favored. Pick a Dragon-style (Immaculate) Charm to switch "
                   f"to the Immaculate path.")
        ui.label(msg).classes("text-xs italic").style(f"color:{pal.accent}")

    # ---- live readout ----------------------------------------------------- #
    @ui.refreshable
    def readout() -> None:
        view = viewmod.build_sheet_view(ruleset, character)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        errors = [i for i in view.issues if i.severity == "error"]
        if in_play():
            # In play the budget that matters is experience, not the chargen pool
            # (which the snapshot has frozen anyway).
            available = advancement.xp_available(character)
            ui.label(f"{available} XP available").classes("text-sm font-bold").style(
                f"color:{'#15803d' if available >= 0 else '#b91c1c'}")
            ui.label(f"earned {character.xp_earned} · spent {advancement.xp_spent(character)}"
                     ).classes("text-xs text-gray-600")
            ui.label("Undo a purchase on the XP tab.").classes("text-xs text-gray-500")
        else:
            slots = viewmod.charm_slot_budget(ruleset, character)
            if slots is not None:
                # Alchemical: you pay for SLOTS, not picks. Show occupancy + the two
                # ceilings the chargen check enforces (General-slot fit, install motes).
                over = slots.over_slots or slots.over_general
                ui.label(
                    f"Slots: {slots.installed}/{slots.general + slots.dedicated} used "
                    f"(General {slots.general} · Dedicated {slots.dedicated}) · "
                    f"Spells: {len(character.spells)}"
                ).classes("text-sm font-semibold").style(
                    f"color:{'#b91c1c' if over else pal.accent}")
                ui.label(
                    f"non-Caste/Favored {slots.noncf}/{slots.general} (General only) · "
                    f"install {slots.motes}/{slots.personal} Personal motes"
                ).classes("text-xs").style(
                    f"color:{'#b91c1c' if slots.over_personal else pal.accent}")
            else:
                # Each Ox-Body and each Deadly Beastman Transformation purchase consumes a
                # Charm pick from the shared pool, exactly as engine.validate prices them —
                # both live on their own lists, so neither is inside character.charms.
                charm_picks = (len(character.charms) + len(character.ox_body)
                               + len(character.beastman_gifts))
                ui.label(f"Charms: {charm_picks} · Spells: {len(character.spells)}").classes(
                    "text-sm font-semibold").style(f"color:{pal.accent}")
            _immaculate_path_banner()
            ui.label(bp).classes("text-xs text-gray-600")
        ui.separator()
        ui.label("✓ Legal" if not errors else f"✗ {len(errors)} error(s)").classes("text-sm font-bold").style(
            "color:#15803d" if not errors else "color:#b91c1c")
        for issue in view.issues:
            if issue.code == "bonus-points":
                continue
            color = {"error": "text-red-600", "warning": "text-amber-600"}.get(issue.severity, "text-gray-500")
            ui.label(f"• {issue.message}").classes(f"text-xs {color}")

    # ---- selected-charm detail panel -------------------------------------- #
    selected = {"id": None}

    @ui.refreshable
    def detail() -> None:
        if selected["id"] and selected["id"] == validate.ox_body_charm_id(ruleset, character):
            ox_body_detail()
            return
        if selected["id"] and selected["id"] == validate.gift_charm_id(ruleset, character):
            gift_detail()
            return
        d = viewmod.build_charm_detail(ruleset, character, selected["id"]) if selected["id"] else None
        if d is None:
            ui.label("Tap a charm to see its details.").classes("text-xs text-gray-400")
            return
        ui.label(d.name).classes("text-sm font-bold").style(f"color:{pal.accent}")
        ui.label(f"{d.type} · {d.cost}").classes("text-xs text-gray-600")
        _charm = ruleset.charms.get(d.id)
        if d.foreign_splat:
            ui.label(f"{d.foreign_splat} Charm — needs a willing tutor; costs double "
                     "to learn and to use (p.127)").classes("text-xs font-semibold") \
                .style(f"color:{pal.accent}")
        if _charm is not None and validate.is_immaculate_charm(_charm):
            ui.label("Immaculate Order Charm (Fivefold Dragon Method)").classes(
                "text-xs font-semibold").style(f"color:{pal.accent}")
        # A Calling Charm is discounted at both chargen and in play (p.90/p.102), so
        # the card says so where the price is shown.
        if viewmod.is_calling_charm(ruleset, character, d.id):
            ui.label("✧ Calling Charm — discounted").classes(
                "text-xs font-semibold").style(f"color:{pal.accent}")
        # Granted by the training camp: owned, but free — it cost no pick.
        if d.id in character.granted_charms:
            ui.label("Granted by your training camp — no Charm pick spent").classes(
                "text-xs font-semibold").style(f"color:{pal.accent}")
        if d.description:
            ui.label(d.description).classes("text-xs")
        ui.separator()
        ui.label(f"Requires: {d.requirement}").classes("text-xs font-semibold")
        if d.duration:
            ui.label(f"Duration: {d.duration}").classes("text-xs font-semibold")
        if d.prerequisite_groups:
            ui.label("Prerequisite Charms:").classes("text-xs font-semibold")
            for group in d.prerequisite_groups:
                ui.label("• " + " or ".join(group)).classes("text-xs ml-2")
        else:
            ui.label("No prerequisite Charms.").classes("text-xs text-gray-500")
        ui.separator()
        if in_play():
            _charm_buy_button(d)
        elif d.owned:
            ui.button("Remove", icon="remove", on_click=lambda: toggle(d.id)).props("dense color=negative")
        elif d.available:
            ui.button("Add", icon="add", on_click=lambda: toggle(d.id)).props("dense color=positive")
        else:
            ui.button("Add", icon="lock").props("dense disable").tooltip("Prerequisites not met")
        submodule_section(d.id)

    # ---- Submodules (Alchemical, p.89) ------------------------------------ #
    # A submodule permanently upgrades ONE Charm, so it is bought on that Charm's
    # detail card rather than from a catalogue. Dual cost: bonus points at chargen,
    # experience post-lock — the page prints both. Most Charms have none, in which
    # case this renders nothing at all.
    def add_submodule(charm_id: str, key: str) -> None:
        character.submodules.append(SubmodulePurchase(charm_id=charm_id, key=key))
        detail.refresh(); readout.refresh()      # spends BP: the budget readout moves

    def remove_submodule(charm_id: str, key: str) -> None:
        for i in range(len(character.submodules) - 1, -1, -1):
            s = character.submodules[i]
            if s.charm_id == charm_id and s.key == key:
                del character.submodules[i]
                break
        detail.refresh(); readout.refresh()

    def buy_submodule(charm_id: str, key: str) -> None:
        sub = validate.submodule_def(ruleset, charm_id, key)
        if not _buy(lambda: advancement.learn_submodule(ruleset, character, charm_id, key)):
            return
        ui.notify(f"Bought {sub.name} — {sub.xp_cost} XP", type="positive")
        detail.refresh(); readout.refresh()

    def submodule_section(charm_id: str) -> None:
        rows = viewmod.build_submodule_rows(ruleset, character, charm_id)
        if not rows:
            return
        ui.separator()
        ui.label("SUBMODULES").classes("text-xs font-bold tracking-widest").style(
            f"color:{pal.accent}")
        for r in rows:
            with ui.column().classes("w-full gap-0 mb-1"):
                with ui.row().classes("w-full items-center justify-between no-wrap gap-1"):
                    ui.label(r.name).classes("text-xs font-semibold")
                    ui.label(f"{r.xp_cost} XP" if in_play()
                             else f"{r.bp_cost} BP").classes("text-xs text-gray-600")
                if r.requirement:
                    ui.label(f"Requires {r.requirement}").classes("text-xs text-gray-500")
                if r.description:
                    ui.label(r.description).classes("text-xs text-gray-600")
                if r.owned:
                    if in_play():
                        # Post-lock the only refund is last-first undo on the XP tab,
                        # exactly as for Charms and Combos.
                        ui.label("Purchased.").classes("text-xs text-gray-500")
                    else:
                        ui.button("Remove", icon="remove",
                                  on_click=lambda _=None, c=r.charm_id, k=r.key:
                                  remove_submodule(c, k)).props("dense flat size=sm color=negative")
                elif r.block_reason:
                    ui.button("Add", icon="lock").props("dense flat size=sm disable").tooltip(
                        r.block_reason)
                    ui.label(r.block_reason).classes("text-xs text-amber-700")
                elif in_play():
                    btn = ui.button(f"Buy · {r.xp_cost} XP", icon="shopping_cart",
                                    on_click=lambda _=None, c=r.charm_id, k=r.key:
                                    buy_submodule(c, k)).props("dense flat size=sm color=positive")
                    if not _afford(r.xp_cost):
                        btn.props("disable")
                else:
                    ui.button("Add", icon="add",
                              on_click=lambda _=None, c=r.charm_id, k=r.key:
                              add_submodule(c, k)).props("dense flat size=sm color=positive")

    def _charm_buy_button(d) -> None:
        """The in-play detail-card action: buy at the engine's price. A known Charm
        offers no Remove — undo lives in the XP ledger, which owns the log."""
        if d.owned:
            ui.label("Known.").classes("text-xs text-gray-500")
            return
        charm = ruleset.charms.get(d.id)
        if charm is None:
            return
        cost = costs.charm_cost(ruleset, character, charm)
        if not d.available:
            ui.button(f"Buy · {cost} XP", icon="lock").props("dense disable").tooltip(
                "Prerequisites not met")
            return
        btn = ui.button(f"Buy · {cost} XP", icon="shopping_cart",
                        on_click=lambda: toggle(d.id)).props("dense color=positive")
        if not _afford(cost):
            btn.props("disable")
            ui.label(f"Only {advancement.xp_available(character)} XP available.").classes(
                "text-xs text-gray-500")

    def select(charm_id: str) -> None:
        selected["id"] = charm_id
        detail.refresh()

    # ---- Ox-Body Technique (repeatable, variant menu; chargen) ------------- #
    def add_ox_body(variant_key: str) -> None:
        charm = validate.ox_body_charm(ruleset, character)
        variant = next((v for v in charm.variants if v.key == variant_key), None) if charm else None
        if variant is None:
            return
        if in_play():
            cost = costs.ox_body_cost(ruleset, character)
            if not _buy(lambda: advancement.learn_ox_body(ruleset, character, variant_key)):
                return
            ui.notify(f"Bought Ox-Body Technique ({variant.label}) — {cost} XP", type="positive")
        else:
            if len(character.ox_body) >= validate.ox_body_cap(ruleset, character):
                trait, unit = viewmod.repeatable_cap_trait(charm)
                ui.notify(f"Ox-Body: already bought once per {unit} of {trait}.",
                          type="warning")
                return
            character.ox_body.append(
                OxBodyPurchase(variant=variant_key, health_levels=list(variant.health_levels)))
            ui.notify(f"Added Ox-Body Technique ({variant.label})", type="positive")
        detail.refresh(); update_graph()

    def remove_ox_body(index: int) -> None:
        if in_play():                     # bought with XP: undo it from the ledger
            return
        if 0 <= index < len(character.ox_body):
            del character.ox_body[index]
            detail.refresh(); update_graph()

    def ox_body_detail() -> None:
        charm = validate.ox_body_charm(ruleset, character)
        if charm is None:
            ui.label("Ox-Body Technique is not in the rule set.").classes("text-xs text-red-600")
            return
        cap = validate.ox_body_cap(ruleset, character)
        bought = len(character.ox_body)
        labels = {v.key: v.label for v in charm.variants}
        ui.label(charm.name).classes("text-sm font-bold").style(f"color:{pal.accent}")
        ui.label(charm.description).classes("text-xs")
        ui.separator()
        # Which trait caps the purchases is per-splat data, never a literal: Lunar
        # Ox-Body counts Stamina where every other splat counts Endurance (p.132).
        cap_trait, cap_unit = viewmod.repeatable_cap_trait(charm)
        ui.label(f"Bought {bought} / {cap}  ·  once per {cap_unit} of {cap_trait}").classes(
            "text-xs font-semibold")
        if bought:
            for i, p in enumerate(character.ox_body):
                with ui.row().classes("w-full items-center justify-between no-wrap gap-1"):
                    ui.label(f"• {labels.get(p.variant, p.variant)}").classes("text-xs")
                    if not in_play():     # in play, undo the purchase from the XP ledger
                        ui.button(icon="remove", on_click=lambda _=None, i=i: remove_ox_body(i)).props(
                            "dense flat round size=sm color=negative")
        ui.separator()
        ox_cost = costs.ox_body_cost(ruleset, character) if in_play() else 0
        ui.label(f"Buy a package  ·  {ox_cost} XP each:" if in_play()
                 else "Add a package:").classes("text-xs font-semibold")
        for v in charm.variants:
            label = f"{v.label}" if not in_play() else f"{v.label} · {ox_cost} XP"
            btn = ui.button(label, icon="add" if not in_play() else "shopping_cart",
                            on_click=lambda _=None, k=v.key: add_ox_body(k)).props("dense color=positive")
            if bought >= cap or (in_play() and not _afford(ox_cost)):
                btn.props("disable")
        if in_play() and bought < cap and not _afford(ox_cost):
            ui.label(f"Only {advancement.xp_available(character)} XP available.").classes(
                "text-xs text-gray-500")
        if bought >= cap:
            ui.label(f"Raise {cap_trait} to buy more." if cap else
                     f"Needs at least 1 {cap_unit} of {cap_trait}.").classes(
                "text-xs text-gray-500")

    # ---- Deadly Beastman Transformation Gifts (repeatable, multi-pick; Lunar) -- #
    # Each purchase grants a fixed number of Gift picks (2 first, 1 after, p.124).
    # There are 19 Gifts (p.126-127) with their own prerequisite chains, which is far
    # too much to cram into the sticky detail card the way Ox-Body's two variants fit:
    # the detail card just shows what has been bought and an Add button, and the
    # choosing happens in a dialog with room for every Gift's description.

    def remove_gift_purchase(index: int) -> None:
        if in_play():                     # bought with XP: undo it from the ledger
            return
        if 0 <= index < len(character.beastman_gifts):
            del character.beastman_gifts[index]
            detail.refresh(); update_graph()

    def commit_gift_purchase(keys: list[str]) -> bool:
        """Apply one purchase of the Gift Charm. True when the character changed."""
        if in_play():
            cost = costs.gift_cost(ruleset, character)
            if not _buy(lambda: advancement.learn_gift(ruleset, character, keys)):
                return False
            ui.notify(f"Bought Deadly Beastman Transformation ({', '.join(keys)}) — "
                      f"{cost} XP", type="positive")
        else:
            charm = validate.gift_charm(ruleset, character)
            cap = validate.gift_purchase_cap(ruleset, character)
            if charm is None or len(character.beastman_gifts) >= cap:
                trait, unit = viewmod.repeatable_cap_trait(charm)
                ui.notify(f"Deadly Beastman Transformation: already bought once per "
                          f"{unit} of {trait}.", type="warning")
                return False
            character.beastman_gifts.append(BeastmanGiftPurchase(gifts=keys))
            ui.notify(f"Added Deadly Beastman Transformation ({', '.join(keys)})",
                      type="positive")
        detail.refresh(); update_graph()
        return True

    def open_gift_dialog() -> None:
        """The Gift chooser: every Gift on p.126-127 as its own row — name, whether it
        repeats, its description, and (when it cannot be picked) the reason why. The
        selection is local to the dialog and only lands on the character on Confirm,
        so Cancel is a true cancel."""
        charm = validate.gift_charm(ruleset, character)
        if charm is None:
            return
        bought = len(character.beastman_gifts)
        needed = validate.gifts_per_purchase(charm, bought)
        known = validate.known_gift_keys(character)
        taken: dict[str, int] = {}
        for k in known:
            taken[k] = taken.get(k, 0) + 1
        labels = {v.key: v.label for v in charm.variants}
        selection: list[str] = []          # ordered, so the cascade prune is stable
        gift_xp = costs.gift_cost(ruleset, character) if in_play() else 0

        def _blocked(key_set: set[str], v) -> str:
            """Why Gift `v` cannot be picked, given `key_set` as the Gifts held; ''
            when it can. A Gift chosen in the SAME purchase satisfies a prerequisite
            (p.124), so key_set includes the pending selection."""
            if v.max_purchases - taken.get(v.key, 0) <= 0:
                return ("Already taken" if v.max_purchases == 1
                        else f"Taken {taken.get(v.key, 0)}/{v.max_purchases}")
            for group in v.prerequisites:
                if not any(g in key_set for g in group):
                    return "Requires " + " or ".join(labels.get(g, g) for g in group)
            return ""

        def _prune() -> None:
            """Unchecking a Gift must drop anything selected that depended on it —
            otherwise the dialog could confirm a chain whose root is gone."""
            changed = True
            while changed:
                changed = False
                for key in list(selection):
                    v = next(x for x in charm.variants if x.key == key)
                    held = set(known) | {k for k in selection if k != key}
                    if _blocked(held, v):
                        selection.remove(key)
                        changed = True

        def _flip(key: str, on: bool) -> None:
            if on:
                if key not in selection:
                    selection.append(key)
            else:
                if key in selection:
                    selection.remove(key)
                _prune()
            body.refresh()

        with ui.dialog() as dialog, ui.card().classes(
                f"w-[46rem] max-w-full p-4 gap-2 {pal.card_solid}"):
            ui.label(charm.name).classes("text-base font-bold tracking-widest").style(
                f"color:{pal.accent}")
            # p.126 heads the list "Sample Gifts … these are not the only possible
            # gifts": the roster is illustrative, and anything else is an ST call, so
            # say so rather than implying these 19 are the whole rule.
            ui.label("Sample Gifts (p.126-127) — the book's list is not exhaustive; "
                     "anything else is a Storyteller call.").classes("text-xs text-gray-500")

            @ui.refreshable
            def body() -> None:
                held = set(known) | set(selection)
                ui.label(f"Choose {needed} Gift{'s' if needed != 1 else ''} for this "
                         f"purchase — {len(selection)}/{needed} selected.").classes(
                    "text-xs font-semibold")
                with ui.column().classes("w-full gap-0 max-h-[55vh] overflow-y-auto pr-2"):
                    for v in charm.variants:
                        picked = v.key in selection
                        # A pending pick is judged WITHOUT itself, or it would read as
                        # its own prerequisite; unpicked ones see the full held set.
                        reason = _blocked(held - ({v.key} if picked else set()), v)
                        full = len(selection) >= needed
                        disabled = not picked and bool(reason or full)
                        with ui.row().classes("w-full items-start no-wrap gap-2 py-1"):
                            cb = ui.checkbox(
                                value=picked,
                                on_change=lambda e, k=v.key: _flip(k, e.value)).props("dense")
                            if disabled:
                                cb.props("disable")
                            with ui.column().classes("flex-1 min-w-0 gap-0"):
                                with ui.row().classes("items-baseline gap-2 no-wrap"):
                                    ui.label(v.label).classes(
                                        "text-sm " + ("text-gray-400" if disabled else "font-medium"))
                                    if v.max_purchases > 1:
                                        ui.label(f"repeatable ×{v.max_purchases}").classes(
                                            "text-xs text-gray-400")
                                    if reason:
                                        ui.label(reason).classes("text-xs text-amber-700 italic")
                                if v.description:
                                    ui.label(v.description).classes("text-xs text-gray-500")
                ui.separator()
                with ui.row().classes("w-full items-center justify-end gap-2 no-wrap"):
                    ui.button("Cancel", on_click=dialog.close).props("flat dense no-caps")
                    confirm = ui.button(
                        f"Buy · {gift_xp} XP" if in_play() else "Add",
                        icon="shopping_cart" if in_play() else "add",
                        on_click=lambda: (commit_gift_purchase(sorted(selection))
                                          and dialog.close())).props("dense no-caps color=positive")
                    if len(selection) != needed or (in_play() and not _afford(gift_xp)):
                        confirm.props("disable")

            body()
        dialog.open()

    def gift_detail() -> None:
        charm = validate.gift_charm(ruleset, character)
        if charm is None:
            ui.label("Deadly Beastman Transformation is not in the rule set.").classes(
                "text-xs text-red-600")
            return
        cap = validate.gift_purchase_cap(ruleset, character)
        bought = len(character.beastman_gifts)
        labels = {v.key: v.label for v in charm.variants}
        ui.label(charm.name).classes("text-sm font-bold").style(f"color:{pal.accent}")
        ui.label(charm.description).classes("text-xs")
        ui.separator()
        cap_trait, cap_unit = viewmod.repeatable_cap_trait(charm)
        ui.label(f"Bought {bought} / {cap}  ·  once per {cap_unit} of {cap_trait}").classes(
            "text-xs font-semibold")
        if not character.beastman_gifts:
            ui.label("No Gifts yet.").classes("text-xs text-gray-400")
        for i, p in enumerate(character.beastman_gifts):
            with ui.row().classes("w-full items-center justify-between no-wrap gap-1"):
                ui.label("• " + ", ".join(labels.get(k, k) for k in p.gifts)).classes("text-xs")
                if not in_play():
                    ui.button(icon="remove", on_click=lambda _=None, i=i: remove_gift_purchase(i)).props(
                        "dense flat round size=sm color=negative")
        ui.separator()
        if bought >= cap:
            ui.label(f"Raise {cap_trait} to buy more." if cap else
                     f"Needs at least 1 {cap_unit} of {cap_trait}.").classes(
                "text-xs text-gray-500")
            return
        needed = validate.gifts_per_purchase(charm, bought)
        gift_xp = costs.gift_cost(ruleset, character) if in_play() else 0
        add = ui.button(f"Add Gifts · {gift_xp} XP" if in_play() else "Add Gifts",
                        icon="add", on_click=open_gift_dialog).props("dense no-caps color=positive")
        if in_play() and not _afford(gift_xp):
            add.props("disable")
            ui.label(f"Only {advancement.xp_available(character)} XP available.").classes(
                "text-xs text-gray-500")
        ui.label(f"{needed} Gift{'s' if needed != 1 else ''} with this purchase "
                 f"({len(charm.variants)} to choose from, p.126-127).").classes(
            "text-xs text-gray-500")

    # ---- spell picker (spells share the Charm pool; core p.100) ----------- #
    def toggle_spell(spell_id: str) -> None:
        if in_play():
            if not buy_spell(spell_id):
                return
        elif spell_id in character.spells:
            character.spells.remove(spell_id)
            ui.notify(f"Dropped {ruleset.spells[spell_id].name}", type="info")
        else:
            spell = ruleset.spells.get(spell_id)
            if spell is None:
                return
            if validate.meets_spell_requirements(ruleset, character, spell):
                character.spells.append(spell_id)
                ui.notify(f"Learned {spell.name}", type="positive")
            else:
                ui.notify(f"{spell.name}: not available", type="warning")
                return
        spells_panel.refresh()
        readout.refresh()

    def buy_spell(spell_id: str) -> bool:
        """Post-lock half of `toggle_spell`: spend XP on a spell."""
        spell = ruleset.spells.get(spell_id)
        if spell is None:
            return False
        if spell_id in character.spells:
            ui.notify(f"{spell.name} is already known — undo the purchase on the "
                      "XP tab to give it back.", type="info")
            return False
        cost = costs.spell_cost(ruleset, character, spell)
        if not _buy(lambda: advancement.learn_spell(ruleset, character, spell_id)):
            return False
        ui.notify(f"Learned {spell.name} — {cost} XP", type="positive")
        return True

    def _spell_button(r) -> None:
        if in_play():
            _spell_buy_button(r)
            return
        if r.owned:
            ui.button(icon="remove", on_click=lambda _=None, sid=r.id: toggle_spell(sid)).props(
                "dense flat round size=sm color=negative")
        elif r.available:
            ui.button(icon="add", on_click=lambda _=None, sid=r.id: toggle_spell(sid)).props(
                "dense flat round size=sm color=positive")
        else:
            ui.button(icon="lock").props("dense flat round size=sm disable").tooltip(r.reason)

    def _spell_buy_button(r) -> None:
        """The in-play spell button: buy at the engine's price, or say why not."""
        if r.owned:
            ui.button(icon="check").props(
                "dense flat round size=sm disable").tooltip("Known")
            return
        if not r.available:
            ui.button(icon="lock").props("dense flat round size=sm disable").tooltip(r.reason)
            return
        cost = costs.spell_cost(ruleset, character, ruleset.spells.get(r.id))
        btn = ui.button(icon="shopping_cart",
                        on_click=lambda _=None, sid=r.id: toggle_spell(sid)).props(
            "dense flat round size=sm color=positive")
        if _afford(cost):
            btn.tooltip(f"Buy · {cost} XP")
        else:
            btn.props("disable").tooltip(
                f"{cost} XP — only {advancement.xp_available(character)} available")

    @ui.refreshable
    def spells_panel() -> None:
        # Spells share the Charm pool (p.100) and are gated on the Occult Sorcery /
        # Necromancy Charms, so they get their own page of the picker rather than a
        # cramped card under the Occult graph: the Circle dropdown chooses a circle,
        # and each spell is a full-width row — its name, its description on the line
        # below, and the add/remove/locked button. Rebuilt on every Charm change so
        # learning a Circle Charm immediately unlocks its spells.
        if state["group"] != "spells":
            return
        rows = [r for r in viewmod.build_spell_picker(ruleset, character)
                if r.circle == state["circle"]]
        if not rows:
            return
        # The Circle dropdown picks which one shows; the header names its track, since
        # an Abyssal's list spans sorcery AND necromancy circles (p.223).
        selected = next(ce for ce in viewmod.CIRCLE_DISPLAY_ORDER if ce.value == state["circle"])
        kind = circle_kind(selected)
        # Track name for the header, and the thing you learn to unlock it: sorcery/
        # necromancy have Circle-initiation Charms; Alchemical weaving has Weaving Engines.
        magic_noun = {"necromancy": "Necromancy", "weaving": "Weaving Protocols"}.get(kind, "Sorcery")
        unlock_noun = ("the matching Weaving Engine" if kind == "weaving"
                       else f"the matching Circle {magic_noun} Charm")
        # Per-circle cost: weaving protocols differ by circle (Man-Machine 12, God-Machine
        # 14), so price from a spell of the shown circle rather than the flat rate.
        circle_cost = costs.spell_cost(ruleset, character, ruleset.spells.get(rows[0].id))
        with ui.card().classes(f"w-full p-3 gap-3 {pal.card}"):
            with ui.row().classes("w-full items-baseline gap-3"):
                ui.label(magic_noun).classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                if in_play():
                    caption = f"{circle_cost} XP each; install {unlock_noun} to unlock it."
                elif kind == "weaving":
                    # Protocols don't take up Charm Slots (CH4); they are gated purely by
                    # having the Weaving Engine installed.
                    caption = f"Install {unlock_noun} to unlock these protocols."
                else:
                    caption = f"A spell takes a Charm pick (p.100); install {unlock_noun} to unlock it."
                ui.label(caption).classes("text-xs text-gray-500")
            owned = sum(1 for r in rows if r.owned)
            with ui.column().classes("w-full gap-0"):
                with ui.row().classes(f"w-full items-baseline gap-2 border-b {pal.rule}"):
                    ui.label(f"{state['circle']} Circle").classes(
                        "text-xs font-semibold").style(f"color:{pal.accent}")
                    ui.label(f"{owned}/{len(rows)} known").classes("text-xs text-gray-400")
                for r in rows:
                    locked = not r.owned and not r.available
                    with ui.row().classes("w-full items-start no-wrap gap-2 py-1"):
                        _spell_button(r)
                        with ui.column().classes("flex-1 min-w-0 gap-0"):
                            with ui.row().classes("items-baseline gap-2 no-wrap"):
                                ui.label(r.name).classes(
                                    "text-sm " + ("text-gray-400" if locked else "font-medium"))
                                if r.cost:
                                    ui.label(r.cost).classes("text-xs text-gray-400")
                            # Description inline, never on hover — and the lock reason
                            # ADDS a line rather than replacing it, since on a fresh
                            # character every spell is locked and would otherwise be
                            # undescribed.
                            if r.description:
                                ui.label(r.description).classes("text-xs text-gray-500")
                            if locked:
                                ui.label(r.reason).classes("text-xs text-amber-700 italic")

    # ---- Form Library ----------------------------------------------------- #
    def add_form() -> None:
        character.animal_forms.append(AnimalForm())
        forms_panel.refresh()

    def remove_form(index: int) -> None:
        del character.animal_forms[index]
        forms_panel.refresh()

    @ui.refreshable
    def forms_panel() -> None:
        """The Lunar Form Library: the character's Totem plus every animal shape they
        have taken. Entirely free-form — no cost, no cap, no validation, and it is
        never touched by the chargen budget or the XP audit. Which animals a Lunar
        has heart's blood for is a narrative record the Storyteller adjudicates, so
        this is a notepad, not a picker. Available pre- and post-lock alike, since
        forms are gained in play, not bought."""
        if state["group"] != "forms":
            return
        with ui.card().classes(f"w-full p-3 gap-3 {pal.card}"):
            with ui.row().classes("w-full items-baseline gap-3"):
                ui.label("Form Library").classes(
                    "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                ui.label("Narrative record — no cost, no limit checked here.").classes(
                    "text-xs text-gray-500")
            ui.input("Totem", value=character.totem,
                     on_change=lambda e: setattr(character, "totem", e.value)).classes("w-full")
            ui.separator()
            if not character.animal_forms:
                ui.label("No forms recorded yet.").classes("text-sm text-gray-400")
            for i, form in enumerate(character.animal_forms):
                with ui.row().classes("w-full items-center no-wrap gap-2"):
                    ui.input("Animal", value=form.name,
                             on_change=lambda e, f=form: setattr(f, "name", e.value)).classes("w-56")
                    ui.input("Notes", value=form.notes,
                             on_change=lambda e, f=form: setattr(f, "notes", e.value)).classes("flex-1")
                    ui.button(icon="delete", on_click=lambda _=None, i=i: remove_form(i)).props(
                        "dense flat round size=sm color=negative")
            ui.button("Add form", icon="add", on_click=add_form).props(
                f"dense flat no-caps color={pal.button}")

    # ---- Vat refit: Charm Slots vs the Panoply (Alchemical, p.88-89) ------- #
    # An Alchemical owns more Charms than they can wear. Installed Charms sit in Slots
    # and commit Personal Essence; the rest wait in the Panoply. This page moves them
    # between the two. Like the Form Library it is play-state — no BP, no XP, nothing
    # here reaches chargen validation or the XP audit — but unlike it, the move has
    # mechanical weight, so engine.refit checks Slot fit and committed Essence.
    def do_uninstall(charm_id: str) -> None:
        try:
            refit.uninstall(ruleset, character, charm_id)
        except refit.RefitError as ex:
            ui.notify(str(ex), type="warning")
            return
        panoply_panel.refresh(); readout.refresh()

    def do_install(charm_id: str) -> None:
        try:
            refit.install(ruleset, character, charm_id)
        except refit.RefitError as ex:
            ui.notify(str(ex), type="warning")
            return
        panoply_panel.refresh(); readout.refresh()

    def _refit_row(charm_id: str, *, installed: bool) -> None:
        charm = ruleset.charms.get(charm_id)
        name = charm.name if charm is not None else charm_id
        reason = (refit.uninstall_block_reason(ruleset, character, charm_id) if installed
                  else refit.install_block_reason(ruleset, character, charm_id))
        with ui.row().classes("w-full items-center justify-between no-wrap gap-2"):
            with ui.column().classes("flex-1 min-w-0 gap-0"):
                ui.label(name).classes("text-sm")
                bits = []
                if charm is not None:
                    if charm.min_attribute:
                        bits.append(f"{charm.min_attribute.title()} {charm.min_ability}")
                    if charm.installation_cost:
                        bits.append(f"{charm.installation_cost}m install")
                    if not validate.charm_fits_dedicated_slot(ruleset, character, charm):
                        bits.append("General Slot only")
                if bits:
                    ui.label(" · ".join(bits)).classes("text-xs text-gray-500")
                if reason:
                    ui.label(reason).classes("text-xs text-amber-700 italic")
            if installed and reason:
                ui.button("To Panoply", icon="lock").props(
                    "dense flat no-caps size=sm disable").tooltip(reason)
            elif installed:
                ui.button("To Panoply", icon="archive",
                          on_click=lambda _=None, c=charm_id: do_uninstall(c)).props(
                    "dense flat no-caps size=sm color=negative")
            elif reason:
                ui.button("Install", icon="lock").props(
                    "dense flat no-caps size=sm disable").tooltip(reason)
            else:
                ui.button("Install", icon="memory",
                          on_click=lambda _=None, c=charm_id: do_install(c)).props(
                    "dense flat no-caps size=sm color=positive")

    @ui.refreshable
    def panoply_panel() -> None:
        if state["group"] != "panoply":
            return
        load = refit.slot_load(ruleset, character)
        with ui.card().classes(f"w-full p-3 gap-2 {pal.card}"):
            with ui.row().classes("w-full items-baseline gap-3"):
                ui.label("Vat Refit").classes(
                    "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                ui.label("Swap Charms between your Slots and your Panoply. Costs "
                         "nothing — they are already bought.").classes(
                    "text-xs text-gray-500")
            with ui.row().classes("w-full items-baseline gap-4"):
                over = load.installed > load.total_slots or load.motes > load.personal
                ui.label(f"Slots {load.installed}/{load.total_slots} "
                         f"({load.general} General · {load.dedicated} Dedicated)").classes(
                    "text-xs font-semibold").style(
                    f"color:{'#b91c1c' if over else pal.accent}")
                ui.label(f"General used {load.noncf}/{load.general}").classes(
                    "text-xs text-gray-600")
                ui.label(f"Committed {load.motes}m of {load.personal}m Personal").classes(
                    "text-xs text-gray-600")
            if character.ox_body:
                # Ox-Body purchases occupy Slots but live on their own list, so they
                # count against the budget above yet cannot be swapped here.
                ui.label(f"{len(character.ox_body)} Strain Resistant Chassis purchase(s) "
                         "occupy Slots and are not refittable.").classes(
                    "text-xs text-gray-500 italic")
            ui.separator()
            ui.label("INSTALLED").classes("text-xs font-bold tracking-widest").style(
                f"color:{pal.accent}")
            slotted = [cid for cid in character.charms
                       if (ch := ruleset.charms.get(cid)) is not None
                       and validate.charm_occupies_slot(ruleset, character, ch)]
            if not slotted:
                ui.label("No Charms installed.").classes("text-sm text-gray-400")
            for cid in slotted:
                _refit_row(cid, installed=True)
            ui.separator()
            ui.label("PANOPLY").classes("text-xs font-bold tracking-widest").style(
                f"color:{pal.accent}")
            if not character.retainer_charms:
                ui.label("Panoply empty — nothing on retainer.").classes(
                    "text-sm text-gray-400")
            for cid in character.retainer_charms:
                _refit_row(cid, installed=False)

    # ---- Augmentation pop-ups (Alchemical 'general') ---------------------- #
    # The 18 Augmentation Charms stay distinct ids (82 other Charms name a specific one
    # as a prerequisite); the picker just collapses them into two per-type cards, each
    # opening a dialog to install/remove per Attribute — like the Deadly Beastman dialog.

    def toggle_augment(charm_id: str) -> None:
        """Install/remove one Augmentation (pre-lock only). Each is an independent Slot
        install, so this is an immediate add/remove, not a bundled purchase."""
        if in_play():
            return
        if charm_id in character.charms:
            blockers = validate.charms_depending_on(ruleset, character, charm_id)
            if blockers:
                ui.notify(f"{ruleset.charms[charm_id].name}: can't remove — needed by "
                          f"{', '.join(blockers)}", type="warning")
                return
            character.charms.remove(charm_id)
        else:
            character.charms.append(charm_id)
        augment_panel.refresh(); readout.refresh()

    def open_augment_dialog(group) -> None:
        """A checkbox per Attribute for one Augmentation type; toggling installs/removes
        it immediately (with the same removal-blocker guard the graph uses)."""
        with ui.dialog() as dialog, ui.card().classes(
                f"w-[34rem] max-w-full p-4 gap-2 {pal.card_solid}"):
            ui.label(group.title).classes("text-base font-bold tracking-widest").style(
                f"color:{pal.accent}")
            ui.label("Each installed Augmentation occupies a Charm Slot.").classes(
                "text-xs text-gray-500")

            @ui.refreshable
            def body() -> None:
                # Re-read the group each paint so install state and Slot budget update.
                grp = next((g for g in viewmod.build_augmentation_view(ruleset, character)
                            if g.title == group.title), group)
                with ui.column().classes("w-full gap-0 max-h-[55vh] overflow-y-auto pr-2"):
                    for e in grp.entries:
                        disabled = not e.owned and not e.available
                        with ui.row().classes("w-full items-start no-wrap gap-2 py-1"):
                            cb = ui.checkbox(
                                value=e.owned,
                                on_change=lambda _e, cid=e.charm_id: (
                                    toggle_augment(cid), body.refresh())).props("dense")
                            if disabled:
                                cb.props("disable")
                            with ui.column().classes("flex-1 min-w-0 gap-0"):
                                ui.label(e.attribute).classes(
                                    "text-sm " + ("text-gray-400" if disabled else "font-medium"))
                                if e.reason:
                                    ui.label(e.reason).classes("text-xs text-amber-700 italic")
                ui.separator()
                ui.button("Done", on_click=dialog.close).props("flat dense no-caps")

            body()
        dialog.open()

    @ui.refreshable
    def augment_panel() -> None:
        if not _is_augment_page():
            return
        groups = viewmod.build_augmentation_view(ruleset, character)
        with ui.column().classes("w-full gap-3"):
            ui.label("Two Augmentation templates, one per Attribute — each installed "
                     "copy takes a Charm Slot.").classes("text-xs text-gray-500")
            for g in groups:
                with ui.card().classes(f"w-full p-3 gap-1 {pal.card}"):
                    installed = [e.attribute for e in g.entries if e.owned]
                    with ui.row().classes("w-full items-center justify-between no-wrap"):
                        ui.label(g.title).classes("text-sm font-bold tracking-widest").style(
                            f"color:{pal.accent}")
                        if not in_play():
                            ui.button("Pick Attributes", icon="tune",
                                      on_click=lambda _=None, grp=g: open_augment_dialog(grp)).props(
                                f"dense no-caps color={pal.button}")
                    ui.label("Installed: " + ", ".join(installed) if installed
                             else "None installed.").classes(
                        "text-xs" + ("" if installed else " text-gray-400"))
            if in_play():
                ui.label("Buy Augmentations post-lock via the Charm-Slot flow (an "
                         "Augmentation occupies a Slot).").classes("text-xs text-gray-500")

    # ---- graph (re)build / update ---------------------------------------- #
    def init_graph() -> None:
        if _is_augment_page():
            return                      # the Augmentation page has no Cytoscape canvas
        graph = viewmod.build_charm_graph(ruleset, character, state["category"], state["splat"])
        ui.run_javascript(f"""
        (function() {{
          var tries = 0;
          function go() {{
            tries += 1;
            var el = document.getElementById('charm-graph');
            if (!window.cytoscape) {{
              if (tries > 100) {{
                if (el) el.innerHTML = '<div style="padding:1rem;color:#b91c1c">'
                  + 'Could not load Cytoscape from the CDN (offline?).</div>';
                return;
              }}
              return setTimeout(go, 50);
            }}
            // wait until the container is mounted AND visible (non-zero height),
            // so the graph never renders into a hidden/collapsed tab panel
            if (!el || el.offsetHeight === 0) {{
              if (tries > 200) return;
              return setTimeout(go, 50);
            }}
            if (window.cy) {{ window.cy.destroy(); }}
            window.cy = cytoscape({{
              container: el,
              elements: {json.dumps(_elements(graph))},
              style: {json.dumps(_style(pal))},
              pixelRatio: Math.max(2, window.devicePixelRatio || 1),
              wheelSensitivity: 0.25, minZoom: 0.3, maxZoom: 3, textureOnViewport: false,
            }});
            window.cy.on('tap', 'node', function(e) {{ emitEvent('charm_select', {{id: e.target.id()}}); }});
            var lay = window.cy.layout({{name: 'breadthfirst', directed: true,
              roots: {json.dumps(graph.roots)}, spacingFactor: 1.5, padding: 30,
              avoidOverlap: true, fit: false}});
            // Fit, but never zoom below a readable level — that is what blurred the
            // labels (they render at font-size x zoom). Overflow becomes pannable.
            lay.one('layoutstop', function() {{
              window.cy.fit(undefined, 30);
              if (window.cy.zoom() < 0.85) {{ window.cy.zoom(0.85); window.cy.center(); }}
            }});
            lay.run();
          }}
          go();
        }})();
        """)

    def update_graph() -> None:
        if _is_augment_page():
            augment_panel.refresh(); readout.refresh()
            return
        graph = viewmod.build_charm_graph(ruleset, character, state["category"], state["splat"])
        # `classes()` replaces the whole class list, so carry `external` along with
        # the state or a foreign prerequisite loses its dashed styling on any repaint.
        states = {n.id: f"{n.state} external" if n.external else n.state
                  for n in graph.nodes}
        ui.run_javascript(f"""
        if (window.cy) {{
          var s = {json.dumps(states)};
          Object.keys(s).forEach(function(id) {{
            var n = window.cy.getElementById(id);
            if (n) n.classes(s[id]);
          }});
        }}
        """)
        readout.refresh()

    def toggle(charm_id: str) -> None:
        if in_play():
            if not buy_charm(charm_id):
                return
        elif charm_id in character.charms:
            blockers = validate.charms_depending_on(ruleset, character, charm_id)
            if blockers:
                ui.notify(f"{ruleset.charms[charm_id].name}: can't remove — needed by "
                          f"{', '.join(blockers)}", type="warning")
                return
            character.charms.remove(charm_id)
            ui.notify(f"Removed {ruleset.charms[charm_id].name}", type="info")
        else:
            charm = ruleset.charms.get(charm_id)
            if charm is None:
                return
            if validate.meets_charm_requirements(ruleset, character, charm):
                character.charms.append(charm_id)
                ui.notify(f"Learned {charm.name}", type="positive")
            else:
                ui.notify(f"{charm.name}: prerequisites not met", type="warning")
                return
        update_graph()
        detail.refresh()
        spells_panel.refresh()        # a new/removed Sorcery Charm changes spell access
        _refresh_categories()         # learning/dropping DB enlightenment reveals/hides Dragon styles

    def buy_charm(charm_id: str) -> bool:
        """Post-lock half of `toggle`: spend XP on a Charm. Known Charms are not
        droppable here — a purchase is undone from the XP ledger, which keeps the
        append-only log and the traits in step."""
        charm = ruleset.charms.get(charm_id)
        if charm is None:
            return False
        if charm_id in character.charms:
            ui.notify(f"{charm.name} is already known — undo the purchase on the "
                      "XP tab to give it back.", type="info")
            return False
        cost = costs.charm_cost(ruleset, character, charm)
        if not _buy(lambda: advancement.learn_charm(ruleset, character, charm_id)):
            return False
        ui.notify(f"Learned {charm.name} — {cost} XP", type="positive")
        return True

    def set_category(value: str) -> None:
        state["category"] = value
        _apply_group()                # sync canvas-vs-Augmentation-cards for the new category
        if not _is_augment_page():
            init_graph()
        readout.refresh()

    def set_circle(value: str) -> None:
        state["circle"] = value
        spells_panel.refresh()

    def set_splat(value: str) -> None:
        """Switch the Charm pages to another Exalt type's trees (p.127). Category
        names collide across splats, so the current category is almost never valid on
        the new page — land on the new page's first category. A splat with no
        martial-arts trees (Lunar) would leave the Martial Arts page empty, so fall
        back to Abilities when the current group has nothing to show."""
        if value == state["splat"]:
            return
        state["splat"] = value
        if _is_graph_page() and not _visible_category_options() and state["group"] == "styles":
            set_group("abilities")      # re-enters here for the categories below
            return
        opts = _visible_category_options()
        first = next(iter(opts), "")
        sel = widgets.get("category")
        if sel is not None:
            sel.set_options(opts, value=first)
        if first:
            set_category(first)
        _apply_group()                  # the Martial Arts page may have just vanished

    def set_st_permission(value: bool) -> None:
        """The Storyteller-permission half of the p.127 rule, editable pre-lock only:
        without it a foreign Charm may not be known at the start of play, so the Splat
        dropdown offers nothing. Withdrawing permission snaps the picker back to the
        character's own splat — any foreign Charm already picked then shows up in the
        readout as a `charm-foreign-no-st-permission` issue rather than silently
        disappearing with the page it was picked on."""
        character.st_foreign_charms = bool(value)
        sel = widgets.get("splat")
        if sel is not None:
            opts = _splat_options()
            keep = state["splat"] if state["splat"] in opts else character.exalt_type
            sel.set_options(opts, value=keep)
            sel.set_visibility(len(opts) > 1 and _is_graph_page())
            set_splat(keep)
        readout.refresh()

    def _apply_group() -> None:
        """Show the graph furniture (category dropdown, legend, canvas, detail card)
        on the two Charm-tree pages and hide it on the Spells and Form Library pages,
        which are plain panels with no selected node to describe. The Circle dropdown
        swaps in for the Category one on the Spells page only."""
        graph_page = _is_graph_page()
        augment = _is_augment_page()
        # The category dropdown stays on any Charm-tree page (you navigate away from the
        # Augmentation view with it); the canvas/legend/detail hide on the Augmentation
        # page, which shows its own pop-up cards instead.
        if widgets.get("category") is not None:
            widgets["category"].set_visibility(graph_page)
        for key in ("legend", "graph", "detail_card"):
            widget = widgets.get(key)
            if widget is not None:
                widget.set_visibility(graph_page and not augment)
        # The Splat dropdown pages the Charm trees only — spells are gated by circle
        # and the Form Library is the character's own, so neither is splat-paged.
        if widgets.get("splat") is not None:
            widgets["splat"].set_visibility(graph_page and not augment and len(_splat_options()) > 1)
        if widgets.get("circle") is not None:
            widgets["circle"].set_visibility(state["group"] == "spells")
        spells_panel.refresh()
        forms_panel.refresh()
        augment_panel.refresh()
        panoply_panel.refresh()

    def set_group(value: str) -> None:
        """Switch between the ability pages, the martial-arts styles and the spell
        list, landing on the first category of the group."""
        if value == state["group"]:
            return
        state["group"] = value
        toggle = widgets.get("group")
        if toggle is not None:
            toggle.set_value(value)   # re-entrant call returns early (value == state)
        _apply_group()
        if not _is_graph_page():
            return
        opts = _visible_category_options()
        first = next(iter(opts), "")
        sel = widgets.get("category")
        if sel is not None:
            sel.set_options(opts, value=first)
        if first:
            set_category(first)      # rebuilds the graph into the now-visible canvas

    def _refresh_categories() -> None:
        """Re-evaluate the visible category dropdown after a Charm change. Learning both
        Dragon-Blooded enlightenment Charms reveals the elemental Dragon styles;
        dropping one hides them again (falling back to a still-visible style, or to the
        Abilities group if the whole styles group just vanished)."""
        sel = widgets.get("category")
        if sel is None or not _is_graph_page():
            return                     # only the graph pages own a category dropdown
        opts = _visible_category_options()
        if not opts:                   # every category in this group just got hidden
            set_group("abilities" if state["group"] == "styles" else "styles")
            return
        if state["category"] in opts:
            sel.set_options(opts, value=state["category"])
        else:                          # current style just got hidden — fall back
            fallback = next(iter(opts), "")
            sel.set_options(opts, value=fallback)
            set_category(fallback)

    def save() -> None:
        persistence.save_character(character, save_path)
        ui.notify(f"Saved to {save_path}", type="positive")

    if register_events:
        ui.on("charm_select", lambda e: select(e.args["id"]))

    # ---- layout ----------------------------------------------------------- #
    if with_header:
        ui.add_head_html(cytoscape_head_html())
        ui.add_head_html(pal.head_style())

    with ui.row().classes("w-full max-w-7xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                if with_header:
                    ui.label("Charm-Tree Picker").classes("text-xl font-bold")
                with ui.row().classes("items-center gap-2"):
                    if len(GROUPS) > 1:
                        widgets["group"] = ui.toggle(
                            GROUPS, value=state["group"],
                            on_change=lambda e: set_group(e.value)
                        ).props(f"no-caps dense unelevated toggle-color={pal.button}")
                    if _foreign_caste:
                        # Eclipse/Moonshadow only (CasteDefinition.foreign_charms).
                        # The checkbox is the chargen Storyteller permission and is
                        # meaningless post-lock, where a tutor is the only gate.
                        if not in_play():
                            ui.checkbox("ST permission", value=character.st_foreign_charms,
                                        on_change=lambda e: set_st_permission(e.value)) \
                                .props(f"dense color={pal.button}") \
                                .tooltip("Storyteller permission to START play knowing "
                                         "another Exalt type's Charms (p.127).")
                        widgets["splat"] = ui.select(
                            _splat_options(), value=state["splat"], label="Splat",
                            on_change=lambda e: set_splat(e.value)).classes("w-40")
                        widgets["splat"].set_visibility(len(_splat_options()) > 1)
                    widgets["category"] = ui.select(
                        _visible_category_options(), value=state["category"], label="Category",
                        on_change=lambda e: set_category(e.value)).classes("w-48")
                    if _has_spells:
                        widgets["circle"] = ui.select(
                            {ce.value: f"{ce.value} Circle" for ce in _spell_circles},
                            value=state["circle"], label="Circle",
                            on_change=lambda e: set_circle(e.value)).classes("w-48")
                        widgets["circle"].set_visibility(state["group"] == "spells")
                if with_header:
                    ui.button("Save", icon="save", on_click=save).props(f"color={pal.button}")
            widgets["legend"] = ui.row().classes("w-full gap-4 text-xs items-center justify-between")
            with widgets["legend"]:
                with ui.row().classes("gap-4 items-center"):
                    for color, text in [(pal.accent, "owned"), ("#15803d", "available"),
                                        ("#9ca3af", "locked (tap to see why)")]:
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("circle", size="0.7rem").style(f"color:{color}")
                            ui.label(text)
                ui.label("scroll to zoom · drag to pan").classes("text-gray-400 italic")
            # A real element (not ui.html, whose inline style gets sanitised away),
            # with an explicit DOM id for Cytoscape to mount into.
            widgets["graph"] = (ui.element("div").props("id=charm-graph")
                                .style(f"height:720px;width:100%;border:1px solid {pal.graph_border};"
                                       f"border-radius:8px;background:{pal.node_bg}"))
            # The Spells, Form Library and Augmentation pages render here, in place of
            # the graph.
            spells_panel()
            forms_panel()
            augment_panel()
            panoply_panel()
        with ui.column().classes("w-72 gap-2 sticky top-4"):
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                ui.label("Live Validation").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                readout()
            widgets["detail_card"] = ui.card().classes(f"w-full p-3 {pal.card}")
            with widgets["detail_card"]:
                ui.label("Charm Details").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                detail()

    # Sync initial canvas-vs-panel visibility (in case the character opens on the
    # Augmentation category or a Spells/Forms group), then defer the first graph build
    # until the client is connected and the div exists.
    _apply_group()
    ui.timer(0.1, init_graph, once=True)
    return select


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e charm-tree picker")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset, character, path = load(args.character)

    @ui.page("/")
    def index() -> None:
        build_picker(ruleset, character, path)

    ui.run(title=f"Exalted 1e — charms: {character.name or path.stem}",
           reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
