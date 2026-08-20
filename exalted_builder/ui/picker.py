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
recent purchase from the Edit tab's Experience card.

No game logic here: the toggle asks engine.validate.meets_charm_requirements, prices
come from engine.costs, and node states come from the engine. Cytoscape is VENDORED
(`ui/assets.cytoscape_head_html` inlines `ui/vendor/cytoscape.min.js`), so the picker
works offline and in a packaged build — never add a CDN dependency here.

Run:
    python -m exalted_builder.ui.picker [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..engine import advancement, costs, paths as engine_paths, refit, validate
from ..models.character import (AnimalForm, BeastmanGiftPurchase, Character,
                                OxBodyPurchase, PathRating, SubmodulePurchase)
from ..models.rules import Orientation, RuleSet, circle_kind
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
        # Homebrew from the user's custom library: keeps its owned/available/locked
        # fill (the state still matters) but takes a violet double border, matching
        # the ✎ marker the sheet and the detail card use. Listed AFTER .external so a
        # custom external prerequisite still reads as custom.
        {"selector": "node.custom", "style": {
            "border-color": "#6d28d9", "border-width": 4, "border-style": "double"}},
        {"selector": "edge", "style": {
            "width": 2, "line-color": "#9ca3af", "target-arrow-color": "#9ca3af",
            "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 1.1}},
    ]


def _node_classes(n: viewmod.CharmNode) -> str:
    """The Cytoscape class list for one node. ONE definition on purpose: the graph is
    built once and then repainted by `classes()`, which replaces the whole list, so
    two copies of this logic means a repaint silently drops whatever the second copy
    forgot (it has happened once already, with `external`)."""
    return " ".join([n.state] + ["external"] * n.external + ["custom"] * n.custom)


def _elements(graph: viewmod.CharmGraph) -> list[dict]:
    # A Charm gated only on breadth ("any 3 Occult Charms") has no edge to draw, so its
    # requirement goes into the node label — otherwise it sits among the roots looking
    # like an entry-level pick.
    nodes = [{"data": {"id": n.id,
                       "label": (f"{n.label}\n({n.count_requirement})"
                                 if n.count_requirement else n.label)},
              "classes": _node_classes(n)}
             for n in graph.nodes]
    edges = [{"data": {"id": f"{s}__{t}", "source": s, "target": t}} for s, t in graph.edges]
    return nodes + edges


# --------------------------------------------------------------------------- #
# Thaumaturgy purchases — RE-EXPORTS from engine/thaum_actions.py
#
# They are game logic (they mutate the save and dispatch on the lock) and import no
# nicegui, so they do not live in the UI layer. Re-exported here because
# `picker.buy_thaum_art(...)` is the call shape used by build_picker below, by
# tests/_ui_main.py and by tests/test_thaumaturgy_ui.py.
#
# ⚠ They raise `advancement.AdvancementError`, which build_picker catches to turn a
# refusal into a notification. Keep it that way.
# --------------------------------------------------------------------------- #

from ..engine.thaum_actions import (  # noqa: F401  (re-export for existing callers)
    add_thaum_orientation, buy_custom_ritual, buy_thaum_art, buy_thaum_entry,
    buy_thaum_specialty, drop_thaum_art, drop_thaum_entry, drop_thaum_specialty,
    find_thaum_entry, lower_thaum_science, raise_thaum_science, thaum_state_of)


def build_picker(ruleset: RuleSet, character: Character, save_path: Path,
                 *, with_header: bool = True, register_events: bool = True,
                 initial_group: str = "", initial_category: str = ""):
    """Render the picker. Returns its `toggle(charm_id)` so an embedding app can
    own a single charm_toggle event handler (set register_events=False then).
    with_header=False omits the title/Save bar and the head <script> (the host
    app supplies Cytoscape).

    `initial_group` opens the picker on one of its other pages — 'spells', 'thaum',
    'styles', 'forms', 'panoply' — instead of the Charm trees. Ignored when this
    character has no such page, so a caller may pass one unconditionally.
    `initial_category` opens a Charm-tree page on one particular tree, and is
    likewise ignored unless that category is actually on offer to this character."""
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
            # ⚠ The AUTHORED style name wins, exactly as it does on the Charm detail
            # card and the preamble panel. Title-casing the slug is only a fallback,
            # and it is wrong for any style whose printed name is not its slug:
            # `praying-mantis` is printed "Mantis Style" (Caste Book: Eclipse p.73),
            # and `.title()` does not repair the hyphen either.
            #
            # ⚠ ONE label generator, `view._style_label` — a second copy here is how
            # the panel and the dropdown came to disagree about the same style on the
            # same screen. Defer to it, then strip the " Style" suffix the dropdown's
            # own format does not carry.
            name = viewmod._style_label(cat, ruleset).removesuffix(" Style")
            return f"{base.replace('_', ' ').title()}: {name}"
        return cat.replace("_", " ").title()

    # A toggle splits the picker into three pages: the ability Charm trees, the
    # martial-arts trees, and the spell list. Every `martial_arts:*` category goes
    # on the Martial Arts page — including the enlightenment tree
    # ('martial_arts:enlightenment'), which is the Dragon-Path initiation rather
    # than a style, but is martial arts and is looked for among them.
    # The ghost Arcanoi paths get their own page, like Thaumaturgy's — they are not
    # Abilities and grouping them there would put "Shifting Ghost-Clay Path" in a
    # dropdown of Ability names (human, 2026-08-01).
    #
    # ⚠ Identified by `min_virtue`, never by a hardcoded list of category strings:
    # being Virtue-keyed is what MAKES a Charm an Arcanos, so a new path (or another
    # Virtue-keyed splat) needs no edit here.
    #
    # ...except the spirit Charms. The God/Demon-Blooded catalogue is ALSO
    # Virtue-keyed (same `min_virtue` axis as the Arcanoi) but is a different Charm
    # class — spirit Charms, not Arcanoi. Without the exalt_type exclusion the
    # God/Demon-Blooded picker's whole catalogue would sit under an "Arcanoi" page
    # and the sheet would label each held spirit Charm "Arcanoi". The Arcanoi are
    # authored for Ghost/God-Blooded; the spirit Charms carry exalt_type "Spirit".
    _arcanoi_categories = {c.category for c in ruleset.charms.values()
                           if c.min_virtue and c.exalt_type != "Spirit"}

    def _group_of(cat: str) -> str:
        if cat.startswith("martial_arts:"):
            return "styles"
        # Resolve the raw category before any `:virtue` split, mirroring the
        # `martial_arts:` prefix test above. `view.virtue_split` refuses to split
        # ghost paths (their Virtue minimums are per-entry gates, not an organizing
        # axis), so no ghost category reaches here as a sub-key today — this guard is
        # the belt-and-braces that keeps a future Virtue-keyed arcanos category on
        # the Arcanoi page rather than falling through to "abilities".
        # `spirit_templates:*` deliberately falls through: the spirit Charms are
        # excluded from `_arcanoi_categories` and belong on the Charms page.
        if cat.split(":", 1)[0] in _arcanoi_categories:
            return "arcanoi"
        return "abilities"

    def _visible_category_options(group: str | None = None) -> dict[str, str]:
        """Category-dropdown options for the CURRENT character state: the categories
        of the SELECTED splat's page in the selected group, minus any a rule hides
        right now. The only such rule today is the Dragon-Blooded Dragon-Path gate
        (DB p241) — the elemental Dragon styles appear only once both enlightenment
        Charms (Spirit Sight + Spirit Walking) are known. That gate is the *character's*
        own, so it does not follow them onto a foreign splat's page: an Eclipse
        learning Dragon-style Charms needs a tutor, not the Immaculate initiation."""
        want = state["group"] if group is None else group
        # A category whose Charms span several Virtues (the spirit Charms) is split
        # into one entry per Virtue so each gets its own tree -- see view.virtue_split.
        cats = sorted(
            sub for cat in {c.category for c in ruleset.charms.values()
                            if viewmod.charm_on_splat_page(ruleset, character, c, state["splat"])
                            and validate.category_available(ruleset, character, c.category)
                            and _group_of(c.category) == want}
            for sub in (viewmod.virtue_split(ruleset, cat) or [cat]))
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

    # The spirit Charms live under ONE data category but span all four Virtues; the
    # picker presents them as four trees (one per Virtue, see view.virtue_split), so
    # the category list is expanded the same way -- otherwise _start would land on the
    # un-split 'spirit_templates', which is not an option the dropdown offers.
    _all_categories = sorted(
        sub for cat in {c.category for c in ruleset.charms.values()
                        if validate.charm_matches_splat(character, c, ruleset)}
        for sub in (viewmod.virtue_split(ruleset, cat) or [cat]))
    _start = ("melee" if "melee" in _all_categories
              else (_all_categories[0] if _all_categories else ""))
    state = {"category": _start, "group": _group_of(_start) if _start else "abilities",
             "circle": "", "splat": character.exalt_type,
             # Thaumaturgy page: which sub-tab, the orientation new rituals and
             # formulas are learned in, and the not-yet-bought narrowing intents
             # keyed "art_id:aspect" (see set_thaum_narrow).
             "thaum_tab": "arts", "orientation": Orientation.REALM.value,
             "thaum_narrow": {}}
    _has_abilities = any(_group_of(c) == "abilities" for c in _all_categories)
    _has_styles = any(_group_of(c) == "styles" for c in _all_categories)
    _has_arcanoi = any(_group_of(c) == "arcanoi" for c in _all_categories)
    # Which circles this character could ever reach is fixed by their splat's Occult
    # tree, so the Spells page — and its Circle dropdown — either exists for them or
    # never does. Ordered globally (sorcery Terrestrial→Solar, then necromancy
    # Shadowlands→Void); an Abyssal reaches both tracks, a plain Solar only sorcery.
    _spell_circles = [ce for ce in viewmod.CIRCLE_DISPLAY_ORDER
                      if ce.value in {r.circle for r in viewmod.build_spell_picker(ruleset, character)}]
    _has_spells = bool(_spell_circles)
    _exalt_def = ruleset.exalt_for(character.exalt_type)
    _has_forms = bool(_exalt_def and _exalt_def.form_library)
    # ⚠ Each page exists only when this character has categories IN THAT GROUP. Asking
    # `_all_categories` instead is true for a splat with Charms of ANY kind, which gives
    # a ghost an Abilities page listing nothing — and an empty Charm-tree page is not
    # merely blank: its Category dropdown raises outright when its options are empty,
    # taking the whole picker down with it (adding-a-splat.md trap #3).
    GROUPS: dict[str, str] = {}
    if _has_abilities:
        # Labelled "Charms", not "Abilities" (human, 2026-08-01) — so the tab bar reads
        # Charms > Charms, the default page taking the section's name while its
        # siblings are named for what makes them special.
        #
        # The old label was not merely redundant, it was WRONG for two splats: this
        # page holds the splat's own main Charm trees whatever they are keyed to, and
        # Lunar's are Attribute-keyed while Alchemical's are mixed. A Lunar player
        # clicking "Abilities" got twelve Attribute-keyed trees.
        #
        # The GROUP KEY stays "abilities" — it is an identifier that `_group_of`,
        # `_GRAPH_GROUPS` and the page state all key off, and renaming it would touch
        # game-facing logic to change a caption.
        GROUPS["abilities"] = "Charms"
    if _has_styles:
        GROUPS["styles"] = "Martial Arts"
    if _has_arcanoi:
        GROUPS["arcanoi"] = "Arcanoi"
    if _has_spells:
        GROUPS["spells"] = "Spells"
        state["circle"] = _spell_circles[0].value
    if _has_forms:
        GROUPS["forms"] = "Form Library"
    # Thaumaturgy is cross-splat and unconditional: p.114 makes it available to every
    # splat that ships today (the dead may hold but not use it, which the page says
    # rather than hides; only the Fair Folk are barred, and they are not playable).
    GROUPS["thaum"] = "Thaumaturgy"
    # The Slot/Panoply manager, for a Charm-Slot splat or an Eclipse who crossed over.
    _has_panoply = refit.supports_refit(ruleset, character)
    if _has_panoply:
        GROUPS["panoply"] = "Vat Refit"
    # The Dragon-King Paths page: a rated-track subsystem with its own pool — not
    # Charms at all (PG pp.175-177). Shown only for a splat that ships paths.
    if ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing).path_dots > 0:
        GROUPS["paths"] = "Paths"
    # The Elemental Powers page (Core p.296 + GoD p.56, PG p.68): a Charm-like
    # catalogue open to Elemental-origin God-Blooded only — "descendents of elementals
    # draw on the innate powers of their heritage". Every other origin/splat's tab bar
    # is unchanged.
    if validate.elemental_powers_available(ruleset, character):
        GROUPS["elemental"] = "Elemental Powers"

    # The Alchemical "general" category (the 18 Augmentation templates) renders as two
    # per-type pop-ups instead of an 18-node graph. None for every other splat.
    _augment_category = viewmod.augmentation_category(ruleset, character)

    def _is_augment_page() -> bool:
        """True when the current page is the collapsed Augmentation view (Alchemical
        'general'), which replaces the Cytoscape canvas with two pop-up cards."""
        return (_augment_category is not None and state["group"] == "abilities"
                and state["category"] == _augment_category)

    # Every group that renders the Charm-tree canvas and owns the category dropdown.
    # ⚠ Named ONCE. Hardcoding the set at its four use sites means a new page added to
    # three of them renders as a blank tab at the fourth.
    _GRAPH_GROUPS = ("abilities", "styles", "arcanoi")

    def _is_graph_page() -> bool:
        """The Charm-tree groups (Abilities / Martial Arts / Arcanoi) own the category
        dropdown; the Spells and Form Library groups render a plain panel in its place.
        The Augmentation category is still an Abilities page (so it keeps the dropdown)
        but swaps the CANVAS for pop-up cards — see _is_augment_page."""
        return state["group"] in _GRAPH_GROUPS

    # `state["group"]` defaulted to "abilities" before GROUPS was known. If this splat
    # has no Charm-tree page, land on whatever its first real page is (Thaumaturgy for
    # a mortal) rather than a group that does not exist.
    if state["group"] not in GROUPS:
        state["group"] = next(iter(GROUPS))

    # Open on a page other than the Charm trees, when the caller asked for one and
    # this character has it. Applied here rather than at `state` because the page
    # list is not known until GROUPS is complete.
    if initial_group and initial_group in GROUPS:
        state["group"] = initial_group
        if _is_graph_page():
            # A Charm-tree page needs a category that exists in it, or the dropdown
            # would render a value outside its own options.
            options = _visible_category_options()
            # ⚠ `initial_category` is honoured ONLY if it is genuinely on offer for
            # this character. A caller-supplied value that is not in the options is
            # the `ui.select` build-time crash that blanks every sibling tab
            # (adding-a-splat.md trap #3) — so it falls back rather than trusting
            # the caller.
            if initial_category and initial_category in options:
                state["category"] = initial_category
            else:
                state["category"] = next(iter(options), state["category"])

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
        b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
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
            ui.label("Undo a purchase in the Experience card on the Edit tab."
                     ).classes("text-xs text-gray-500")
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
                # Charm pick from the shared pool, exactly as engine.validate prices them.
                # They live on their own lists, so the count comes from the engine's
                # canonical enumeration rather than from adding lists up here.
                charm_picks = validate.charm_pick_count(ruleset, character)
                noun = ruleset.exalt_for(character.exalt_type).charm_noun
                ui.label(f"{noun}: {charm_picks} · Spells: {len(character.spells)}").classes(
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
        # Homebrew is called out wherever a Charm is read, not only on the sheet: a
        # player picking Charms should know which of them no book backs up.
        if d.custom:
            ui.label("✎ Custom (homebrew) Charm — not from a rulebook").classes(
                "text-xs font-semibold text-violet-700")
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
            # A generic repeatable Charm is owned-but-not-full while the copy count
            # is under its trait cap — offer another purchase alongside Remove (the
            # Mountain Folk Satiation / Stone-Still, CH6 pp.245-246).
            _charm = ruleset.charms.get(d.id)
            _cap = validate._repeatable_purchase_cap(_charm, character) if _charm else 0
            if _cap and character.charms.count(d.id) < _cap:
                ui.button("Add another", icon="add",
                          on_click=lambda: add_another(d.id)).props("dense color=positive")
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
                        # Post-lock the only refund is last-first undo on the Edit tab,
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
    # The Gifts (p.126-127) have their own prerequisite chains, which is far
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
            # say so rather than implying the listed ones are the whole rule.
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
                      "Edit tab to give it back.", type="info")
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
    def style_panel() -> None:
        """The style-level text above a martial-arts tree: its printed `Type:`, its
        prose, and the "Weapons and Armor" rules that never had anywhere to live
        (docs/plans/martial-arts-styles.md).

        Renders NOTHING when the selected category is not an authored style — the
        documented absences, and permanently so for a homebrew style. An empty panel
        on every other category would be worse than no panel, the same rule the
        sheet's conditional panels follow.
        """
        style = viewmod.style_for_category(ruleset, state["category"])
        if style is None or not _is_graph_page():
            return
        # ⚠ Both of these are conditional because a book may print NEITHER a `Type:`
        # line nor prose, and a homebrew style has neither by default
        # (docs/status/martial-arts-styles.md). Interpolating them
        # unconditionally gives "Air Dragon Style — " with a dangling em-dash above
        # an empty label. Same rule the printed sheet follows: nothing is rendered as
        # nothing, never as an empty box.
        with ui.expansion(style.heading).classes(
                f"w-full {pal.card_soft} rounded").props("dense"):
            with ui.column().classes("w-full gap-2 p-2"):
                # `whitespace-pre-line` or NiceGUI eats the paragraph breaks —
                # see docs/status/backgrounds.md, which learned this the hard way.
                if style.preamble:
                    ui.label(style.preamble).classes(
                        "text-sm whitespace-pre-line").style("max-width:60rem")
                for rule in style.mechanics:
                    with ui.row().classes("w-full items-start gap-2 no-wrap"):
                        ui.icon("gavel", size="0.9rem").classes("mt-1").style(
                            f"color:{pal.accent}")
                        ui.label(rule).classes("text-sm flex-1")
                if style.source_label:
                    ui.label(style.source_label).classes("text-xs text-gray-500 italic")

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

    # ---- Thaumaturgy (Player's Guide CH3) --------------------------------- #
    # A cross-splat capability layer, not a splat: every shipped splat may hold it
    # (p.114), so this page is on every character's picker. Four sub-tabs because an
    # Art (binary), a Science (rated, on a sparse ladder), a ritual (levelled) and a
    # formula (flat rate) are four different mechanical shapes that one flat list
    # would fight — see docs/status/thaumaturgy.md.
    #
    # Every gate, price and label comes from view.build_thaum_picker, which asks the
    # engine; nothing here decides legality. Purchases edit the chargen lists before
    # the lock and go through engine.advancement after it, exactly like spells.

    THAUM_TABS = {"arts": "Arts", "sciences": "Sciences",
                  "rituals": "Rituals", "formulas": "Formulas"}

    def _thaum_changed() -> None:
        thaum_panel.refresh()
        readout.refresh()

    def _thaum_do(action) -> None:
        """Run one purchase or drop and report it. The module-level thaum_* functions
        own the state change and raise on refusal; this only surfaces the outcome."""
        try:
            ui.notify(action(), type="positive")
        except advancement.AdvancementError as ex:
            ui.notify(str(ex), type="warning")
            return
        _thaum_changed()

    def _no_thaum_drop() -> None:
        ui.notify("Bought with experience — undo it on the Edit tab.", type="info")

    def set_thaum_tab(value: str) -> None:
        if not value or value == state["thaum_tab"]:
            return                      # the echo from rebuilding the tab bar
        state["thaum_tab"] = value
        thaum_panel.refresh()

    def set_orientation(value: str) -> None:
        """The regional version new rituals and formulas are learned in (p.124).
        One page-level choice rather than a control per row: a thaumaturge learns in
        the tradition they were taught, so it is a mode, not a per-purchase decision."""
        state["orientation"] = value
        thaum_panel.refresh()

    def _orientation() -> Orientation:
        return Orientation(state["orientation"])

    def set_thaum_narrow(art_id: str, name: str, value: bool) -> None:
        """Remember the intent to narrow an aspect before it is bought. Narrowing is
        Summoning's alone (p.127) and halves the cost, so it must be decided at
        purchase time — `ArtSpecialty.narrowed` is stored, not inferred."""
        state["thaum_narrow"][f"{art_id}:{name}"] = bool(value)

    def toggle_thaum_art(row) -> None:
        if row.owned and in_play():
            _no_thaum_drop()
        elif row.owned:
            _thaum_do(lambda: drop_thaum_art(ruleset, character, row.id))
        else:
            _thaum_do(lambda: buy_thaum_art(ruleset, character, row.id))

    def toggle_thaum_specialty(row) -> None:
        if row.owned and in_play():
            _no_thaum_drop()
        elif row.owned:
            _thaum_do(lambda: drop_thaum_specialty(character, row.art_id, row.name))
        else:
            _thaum_do(lambda: buy_thaum_specialty(
                ruleset, character, row.art_id, row.name,
                narrowed=bool(state["thaum_narrow"].get(f"{row.art_id}:{row.name}"))))

    def add_custom_specialty(art_id: str, name: str) -> None:
        _thaum_do(lambda: buy_thaum_specialty(ruleset, character, art_id, name))

    def raise_science(row) -> None:
        _thaum_do(lambda: raise_thaum_science(ruleset, character, row.id))

    def lower_science(row) -> None:
        if in_play():
            _no_thaum_drop()
            return
        _thaum_do(lambda: lower_thaum_science(ruleset, character, row.id))

    def toggle_thaum_entry(row) -> None:
        if row.owned and in_play():
            _no_thaum_drop()
        elif row.owned:
            _thaum_do(lambda: drop_thaum_entry(character, row.kind, row.key))
        else:
            _thaum_do(lambda: buy_thaum_entry(
                ruleset, character, row.kind, row.key, _orientation()))

    def add_orientation(row, value: str) -> None:
        _thaum_do(lambda: add_thaum_orientation(
            ruleset, character, row.kind, row.key, Orientation(value)))

    def add_custom_ritual(name: str, level) -> None:
        _thaum_do(lambda: buy_custom_ritual(
            ruleset, character, name, level, _orientation()))

    def _thaum_price_label(price: int, currency: str) -> str:
        return f"{price} {currency}"

    def _thaum_buy_button(*, owned: bool, available: bool, reason: str,
                          price: int, currency: str, on_add, on_drop) -> None:
        """One purchase control, in whichever of the three states a row can be in:
        owned (droppable at chargen, frozen in play), available (priced), or locked
        (the engine's reason on the tooltip)."""
        if owned:
            if in_play():
                ui.label("owned").classes("text-xs text-gray-500 w-20 text-right")
            else:
                ui.button(icon="remove", on_click=lambda _=None: on_drop()).props(
                    "flat dense round color=grey").tooltip("Drop")
        elif available:
            ui.button(_thaum_price_label(price, currency),
                      on_click=lambda _=None: on_add()).props(
                f"dense unelevated color={pal.button}")
        else:
            ui.button(icon="lock", on_click=lambda _=None: ui.notify(
                reason, type="warning")).props("flat dense round color=grey") \
                .tooltip(reason)

    @ui.refreshable
    def thaum_panel() -> None:
        if state["group"] != "thaum":
            return
        v = viewmod.build_thaum_picker(ruleset, character)
        with ui.card().classes(f"w-full p-3 gap-3 {pal.card}"):
            # ---- header: sub-tabs, orientation, what it costs --------------- #
            with ui.row().classes("w-full items-center gap-3 no-wrap"):
                # Real ui.tabs rather than a ui.toggle: four named sub-pages is what
                # tabs are for, and unlike a toggle's options each tab is its own
                # element — which is also the only way a click on one is reachable.
                with ui.tabs(value=state["thaum_tab"],
                             on_change=lambda e: set_thaum_tab(e.value)) \
                        .props("dense no-caps").style(f"color:{pal.accent}"):
                    for _key, _label in THAUM_TABS.items():
                        ui.tab(_key, label=_label)
                ui.space()
                if state["thaum_tab"] in ("rituals", "formulas"):
                    ui.select({o.value: o.value for o in Orientation},
                              value=state["orientation"], label="Learn as",
                              on_change=lambda e: set_orientation(e.value)) \
                        .classes("w-36").tooltip(
                        "The regional tradition a new ritual or formula is learned "
                        "in (p.124). Further versions cost a flat point each.")
                ui.label(f"Occult {v.occult}").classes("text-xs text-gray-500")
            if not v.usable:
                ui.label(v.usable_note).classes("text-xs italic text-amber-700")
            if v.free_note:
                ui.label(v.free_note).classes("text-xs italic").style(
                    f"color:{pal.accent}")
            ui.separator()

            if state["thaum_tab"] == "arts":
                _thaum_arts(v)
            elif state["thaum_tab"] == "sciences":
                _thaum_sciences(v)
            else:
                _thaum_entries_ui(v, state["thaum_tab"][:-1])   # 'rituals' -> 'ritual'

            # ---- what has been bought -------------------------------------- #
            # Straight off the engine's canonical enumeration, priced by it, so the
            # free-grant zeroes shown here are the ones actually charged. Deliberately
            # not recomputed from the rows above — that is the whole point of the
            # enumeration existing.
            if v.owned:
                ui.separator()
                with ui.row().classes("w-full items-baseline gap-2"):
                    ui.label("Bought").classes(
                        "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
                    ui.label(f"{v.total} {v.currency} total").classes(
                        "text-xs text-gray-600")
                for row in v.owned:
                    with ui.row().classes("w-full items-center gap-2 no-wrap"):
                        ui.label(row.label).classes("text-xs flex-1 truncate")
                        if row.free:
                            ui.label("free").classes("text-xs italic").style(
                                f"color:{pal.accent}")
                        ui.label(f"{row.cost} {v.currency}").classes(
                            "text-xs font-mono text-gray-600 w-16 text-right")

    # ---- Elemental Powers (Core p.296 + GoD p.56, PG p.68) ------------------ #
    # A Charm-like catalogue for Elemental-origin God-Blooded: 7 BP each chargen,
    # 14 XP in play ("learned in play for a number of experience points equal to
    # double its bonus point value"). Every gate and price comes from the engine;
    # purchases edit the chargen list before the lock and go through
    # engine.advancement after it, exactly like spells.
    def _elemental_buy_button(row) -> None:
        if in_play():
            if row.owned:
                ui.button(icon="check").props(
                    "dense flat round size=sm disable").tooltip("Known")
                return
            if not row.available:
                ui.button(icon="lock").props(
                    "dense flat round size=sm disable").tooltip(row.reason)
                return
            btn = ui.button(icon="shopping_cart",
                            on_click=lambda _=None, rid=row.id: toggle_elemental_power(rid)) \
                .props("dense flat round size=sm color=positive")
            if _afford(row.price):
                btn.tooltip(f"Buy · {row.price} XP")
            else:
                btn.props("disable").tooltip(
                    f"{row.price} XP — only {advancement.xp_available(character)} available")
        elif row.owned:
            ui.button(icon="remove",
                      on_click=lambda _=None, rid=row.id: toggle_elemental_power(rid)) \
                .props("dense flat round size=sm color=negative")
        elif row.available:
            ui.button(icon="add",
                      on_click=lambda _=None, rid=row.id: toggle_elemental_power(rid)) \
                .props("dense flat round size=sm color=positive")
        else:
            ui.button(icon="lock").props("dense flat round size=sm disable").tooltip(row.reason)

    def toggle_elemental_power(power_id: str) -> None:
        if in_play():
            power = ruleset.elemental_powers.get(power_id)
            if power is None:
                return
            if not _buy(lambda: advancement.learn_elemental_power(
                    ruleset, character, power_id)):
                return
            ui.notify(f"Learned {power.name} — {costs.elemental_power_xp(ruleset, character, power)} XP",
                      type="positive")
        elif power_id in character.elemental_powers:
            character.elemental_powers.remove(power_id)
            ui.notify(f"Dropped {ruleset.elemental_powers[power_id].name}", type="info")
        else:
            power = ruleset.elemental_powers.get(power_id)
            if power is None:
                return
            if validate.meets_elemental_power_requirements(ruleset, character, power):
                character.elemental_powers.append(power_id)
                ui.notify(f"Learned {power.name}", type="positive")
            else:
                reason = "; ".join(validate.elemental_power_shortfalls(
                    ruleset, character, power))
                ui.notify(f"{power.name}: {reason}", type="warning")
                return
        elemental_panel.refresh()
        readout.refresh()

    @ui.refreshable
    def elemental_panel() -> None:
        if state["group"] != "elemental":
            return
        v = viewmod.build_elemental_power_picker(ruleset, character)
        with ui.card().classes(f"w-full p-3 gap-3 {pal.card}"):
            with ui.row().classes("w-full items-baseline gap-3"):
                ui.label("Elemental Powers").classes(
                    "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                if in_play():
                    caption = "14 XP each in play (7 bonus points doubled, PG p.68)."
                else:
                    caption = "7 bonus points each (PG p.68)."
                ui.label(caption).classes("text-xs text-gray-500")
            with ui.column().classes("w-full gap-0"):
                for r in v.powers:
                    locked = not r.owned and not r.available
                    with ui.row().classes("w-full items-start no-wrap gap-2 py-1"):
                        _elemental_buy_button(r)
                        with ui.column().classes("flex-1 min-w-0 gap-0"):
                            with ui.row().classes("items-baseline gap-2 no-wrap"):
                                ui.label(r.name).classes(
                                    "text-sm " + ("text-gray-400" if locked else "font-medium"))
                                ui.label(f"Requires {r.requires}").classes(
                                    "text-xs text-gray-400")
                            if r.activation:
                                ui.label(r.activation).classes("text-xs italic text-gray-500")
                            if r.description:
                                ui.label(r.description).classes("text-xs text-gray-500")
                            if locked:
                                ui.label(r.reason).classes("text-xs text-amber-700 italic")
            # What this character has bought, straight off the engine's enumeration.
            if v.owned:
                ui.separator()
                with ui.row().classes("w-full items-baseline gap-2"):
                    ui.label("Owned").classes(
                        "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
                    ui.label(f"{v.total} {v.currency} total").classes(
                        "text-xs text-gray-600")
                for r in v.owned:
                    with ui.row().classes("w-full items-center gap-2 no-wrap"):
                        ui.label(r.name).classes("text-xs flex-1 truncate")
                        ui.label(f"{r.price} {v.currency}").classes(
                            "text-xs font-mono text-gray-600 w-16 text-right")

    def _thaum_arts(v) -> None:
        for art in v.arts:
            with ui.expansion(art.name).classes("w-full").props("dense"):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.label(f"Occult {art.min_occult}"
                             f"{' · ' + art.roll if art.roll else ''}"
                             f"{' · ' + art.cost_text if art.cost_text else ''}"
                             ).classes("text-xs text-gray-600 flex-1")
                    _thaum_buy_button(
                        owned=art.owned, available=art.available, reason=art.reason,
                        price=art.price, currency=v.currency,
                        on_add=lambda a=art: toggle_thaum_art(a),
                        on_drop=lambda a=art: toggle_thaum_art(a))
                if art.owned:
                    ui.label("Trained: +2 dice to attempts in this Art.").classes(
                        "text-xs").style(f"color:{pal.accent}")
                if art.description:
                    ui.label(art.description).classes("text-xs text-gray-600")
                ui.label("Specialties — +1 die each, at most two applied to any one "
                         "roll. The Art itself is not required to buy one (p.126).") \
                    .classes("text-xs text-gray-500 mt-1")
                for spec in art.specialties:
                    with ui.row().classes("w-full items-center gap-2 no-wrap"):
                        label = spec.name if spec.printed else f"{spec.name} (custom)"
                        ui.label(label).classes("text-xs flex-1 truncate").tooltip(
                            spec.description or "")
                        if spec.min_occult:
                            ui.label(f"Occult {spec.min_occult}").classes(
                                "text-xs text-gray-400")
                        if spec.narrowed:
                            ui.label("narrowed").classes("text-xs italic").style(
                                f"color:{pal.accent}")
                        elif art.allows_narrowing and not spec.owned and spec.printed:
                            # Summoning alone (p.127): narrowing halves the cost and
                            # is recorded on the sheet, so it is chosen before buying.
                            ui.checkbox(
                                "narrow",
                                value=bool(state["thaum_narrow"].get(
                                    f"{spec.art_id}:{spec.name}")),
                                on_change=lambda e, s=spec: set_thaum_narrow(
                                    s.art_id, s.name, e.value)) \
                                .props(f"dense color={pal.button}").tooltip(
                                "Further limit this aspect (e.g. 'War Gods') for half "
                                "cost, noted on the sheet (p.127).")
                        _thaum_buy_button(
                            owned=spec.owned, available=spec.available,
                            reason=spec.reason, price=spec.price, currency=v.currency,
                            on_add=lambda s=spec: toggle_thaum_specialty(s),
                            on_drop=lambda s=spec: toggle_thaum_specialty(s))
                # Player-invented specialties are explicitly invited (p.126).
                with ui.row().classes("w-full items-center gap-2 no-wrap mt-1"):
                    custom = ui.input(placeholder="Own specialty, e.g. Local Fair Folk") \
                        .props("dense outlined").classes("flex-1")
                    ui.button("Add", on_click=lambda _=None, a=art, c=custom: (
                        add_custom_specialty(a.id, c.value), c.set_value(""))) \
                        .props(f"dense flat color={pal.button}")

    def _thaum_sciences(v) -> None:
        for sci in v.sciences:
            with ui.expansion(f"{sci.name}  {'●' * sci.rating}"
                              f"{'○' * (sci.max_rating - sci.rating)}") \
                    .classes("w-full").props("dense"):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.label(f"{sci.rating} / {sci.max_rating}"
                             f"{' · ' + sci.roll if sci.roll else ''}"
                             f"{' · ' + sci.cost_text if sci.cost_text else ''}"
                             ).classes("text-xs text-gray-600 flex-1")
                    if sci.rating and not in_play():
                        ui.button(icon="remove",
                                  on_click=lambda _=None, s=sci: lower_science(s)) \
                            .props("flat dense round color=grey").tooltip("Lower")
                    if sci.can_raise:
                        ui.button(f"+1 · {sci.next_price} {v.currency}",
                                  on_click=lambda _=None, s=sci: raise_science(s)) \
                            .props(f"dense unelevated color={pal.button}")
                    else:
                        ui.button(icon="lock", on_click=lambda _=None, s=sci: ui.notify(
                            s.reason, type="warning")).props(
                            "flat dense round color=grey").tooltip(sci.reason)
                for extra in ((sci.time, "Time"), (sci.duration, "Duration")):
                    if extra[0]:
                        ui.label(f"{extra[1]}: {extra[0]}").classes(
                            "text-xs text-gray-600")
                if sci.description:
                    ui.label(sci.description).classes("text-xs text-gray-600")
                # Rendered 1..max_rating, so Alchemy's undescribed five-dot rung shows
                # as an empty rung instead of pulling the six-dot text down (p.136).
                for rung in sci.levels:
                    held = rung.rating <= sci.rating
                    text = rung.description or "(no description printed at this level)"
                    with ui.row().classes("w-full items-start gap-2 no-wrap"):
                        ui.label("●" * rung.rating).classes(
                            "text-xs font-mono w-16").style(
                            f"color:{pal.accent if held else '#9ca3af'}")
                        ui.label(text).classes(
                            f"text-xs flex-1 {'' if rung.description else 'italic'} "
                            f"{'text-gray-700' if held else 'text-gray-400'}")

    def _thaum_entries_ui(v, kind: str) -> None:
        rows = v.rituals if kind == "ritual" else v.formulas
        if kind == "ritual":
            ui.label("A thaumaturge must have Occult equal to the ritual's level "
                     "(p.148).").classes("text-xs text-gray-500")
        else:
            ui.label("Formulas and procedures are a flat point each, whatever their "
                     "level.").classes("text-xs text-gray-500")
        for row in rows:
            with ui.column().classes("w-full gap-0"):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.label(f"{row.name}").classes("text-sm flex-1 truncate")
                    ui.label(f"level {row.level}").classes("text-xs text-gray-500")
                    if row.custom:
                        ui.label("custom").classes("text-xs italic text-gray-400")
                    if row.owned:
                        ui.label(", ".join(row.orientations)).classes(
                            "text-xs").style(f"color:{pal.accent}")
                        remaining = [o.value for o in Orientation
                                     if o.value not in row.orientations]
                        if remaining:
                            with ui.button(icon="add_location_alt").props(
                                    "flat dense round color=grey").tooltip(
                                    f"Add another regional version — "
                                    f"{row.orientation_price} {v.currency}"):
                                with ui.menu():
                                    for value in remaining:
                                        ui.menu_item(
                                            value,
                                            lambda _=None, r=row, o=value:
                                                add_orientation(r, o))
                    _thaum_buy_button(
                        owned=row.owned, available=row.available, reason=row.reason,
                        price=row.price, currency=v.currency,
                        on_add=lambda r=row: toggle_thaum_entry(r),
                        on_drop=lambda r=row: toggle_thaum_entry(r))
                for label, value in row.detail:
                    ui.label(f"{label}: {value}").classes("text-xs text-gray-600")
                if row.description:
                    ui.label(row.description).classes("text-xs text-gray-500")
                ui.separator()
        if kind == "ritual":
            # Catalogue + custom by decision: the chapter prints five rituals and
            # expects STs to write more (p.148).
            with ui.row().classes("w-full items-center gap-2 no-wrap mt-1"):
                name = ui.input(placeholder="Custom ritual name").props(
                    "dense outlined").classes("flex-1")
                level = ui.number(label="Level", value=1, min=1, max=5,
                                  format="%d").props("dense outlined").classes("w-24")
                ui.button("Add ritual", on_click=lambda _=None, n=name, l=level: (
                    add_custom_ritual(n.value, l.value), n.set_value(""))) \
                    .props(f"dense flat color={pal.button}")

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

    # ---- Dragon-King Paths (PG pp.175-177) ---------------------------------- #
    # A rated-track subsystem with its own chargen pool, NOT Charms: each Path is
    # rated 1-6 (learned in fixed order, gated by Essence), and each dot grants that
    # level's power. Pre-lock the rating is a free setter into character.paths;
    # post-lock it becomes XP +/- via advancement. The breed's two element Paths are
    # auto-favoured (★) and the player chooses one more (✚) from the other eight.

    def _set_path_rating(pid: str, rating: int) -> None:
        """Pre-lock free setter into character.paths (validation via validate_chargen)."""
        existing = next((p for p in character.paths if p.path_id == pid), None)
        if rating <= 0:
            if existing:
                character.paths.remove(existing)
        elif existing:
            existing.rating = rating
        else:
            character.paths.append(PathRating(path_id=pid, rating=rating))
        paths_panel.refresh(); readout.refresh()

    def _path_adv(pid: str, direction: int) -> None:
        """Post-lock XP raise/lower of one Path dot."""
        def action() -> None:
            if direction > 0:
                if any(p.path_id == pid for p in character.paths):
                    advancement.raise_path(ruleset, character, pid)
                else:
                    advancement.learn_path(ruleset, character, pid)
            else:
                advancement.lower_path(ruleset, character, pid)
        if _buy(action):
            paths_panel.refresh(); readout.refresh()

    @ui.refreshable
    def paths_panel() -> None:
        if state["group"] != "paths":
            return
        b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
        ratings = {p.path_id: p.rating for p in character.paths}
        breed_el = engine_paths.breed_element(ruleset, character)
        breed_path_ids = {p.id for p in ruleset.paths.values() if p.element == breed_el}
        fav_opts = {p.id: p.name for p in ruleset.paths.values() if p.id not in breed_path_ids}
        with ui.card().classes(f"w-full p-3 gap-2 {pal.card}"):
            with ui.row().classes("w-full items-baseline gap-3"):
                ui.label("Paths of Prehuman Mastery").classes(
                    "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                ui.label(f"{b.path_dots} free dots · ≥{b.path_min_breed_favored} from "
                         f"Breed/Favoured Paths · none above {b.path_cap_pre_bp} without "
                         "bonus points").classes("text-xs text-gray-500")
            with ui.row().classes("w-full items-center gap-3"):
                ui.label("Favoured Path").classes("text-xs font-semibold")
                if in_play():
                    chosen = ruleset.paths.get(character.favored_path)
                    ui.label(chosen.name if chosen else "—").classes("text-xs text-gray-600")
                else:
                    # Trap #3 guard: a saved `favored_path` that is one of the breed's
                    # two (an illegal-but-possible state) must not be a value the select
                    # cannot offer — a ui.select whose value is absent from its options
                    # raises at BUILD time and takes every sibling tab with it.
                    _fav_opts = {**{"": "— none —"}, **fav_opts}
                    _fav_opts.setdefault(character.favored_path or "",
                                         character.favored_path or "— none —")
                    ui.select(_fav_opts,
                              value=character.favored_path or "", label="Favoured Path",
                              on_change=lambda e: (setattr(character, "favored_path",
                                                           e.value or ""),
                                                   paths_panel.refresh(),
                                                   readout.refresh())).classes("w-56")
                ui.label("★ breed · ✚ your choice").classes("text-xs text-gray-400 italic")
            ui.separator()
            for path in ruleset.paths.values():
                rating = ratings.get(path.id, 0)
                marker = "★ " if (path.element and path.element == breed_el) \
                    else ("✚ " if path.id == character.favored_path else "")
                with ui.row().classes("w-full items-center gap-3 no-wrap"):
                    ui.label(f"{marker}{path.name}").classes("text-sm font-semibold flex-1")
                    ui.label(path.element_label).classes("text-xs text-gray-400 w-12")
                    if in_play():
                        with ui.row().classes("items-center gap-1"):
                            ui.button(icon="remove", on_click=lambda pid=path.id:
                                      _path_adv(pid, -1)).props(f"dense flat round color={pal.button}")
                            ui.label(str(rating)).classes("text-sm font-mono w-6 text-center")
                            ui.button(icon="add", on_click=lambda pid=path.id:
                                      _path_adv(pid, +1)).props(f"dense flat round color={pal.button}")
                    else:
                        ui.select({str(i): str(i) for i in range(0, 7)},
                                  value=str(rating), label="",
                                  on_change=lambda e, pid=path.id:
                                  _set_path_rating(pid, int(e.value))).classes("w-16")
                if rating:
                    # `pl-5` (padding) not `ml-5` (margin): a `w-full` column with a
                    # margin is 100% + margin wide and overruns the card. The label
                    # gets an explicit wrap style — `overflow-wrap: anywhere` breaks
                    # even inside long runs, which the prose needs.
                    with ui.column().classes("w-full gap-0 pl-5 min-w-0"):
                        for power in path.powers[:rating]:
                            with ui.column().classes("w-full gap-0 min-w-0"):
                                ui.label(f"• {power.name} — {power.duration}").classes(
                                    "text-xs font-semibold")
                                if power.text:
                                    ui.label(power.text).classes(
                                        "text-xs text-gray-600 mb-1").style(
                                        "overflow-wrap:anywhere; word-break:break-word")

    # ---- Augmentation pop-ups (Alchemical 'general') ---------------------- #
    # The 18 Augmentation Charms stay distinct ids (other Charms name a specific one
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
                  + 'Could not load Cytoscape (the bundled copy failed to '
                  + 'initialise).</div>';
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
        # `classes()` replaces the whole class list, so the repaint must send the FULL
        # list (state + external + custom), not just the state — see _node_classes.
        states = {n.id: _node_classes(n) for n in graph.nodes}
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
                # A generic repeatable Charm (Mountain Folk Satiation / Stone-Still,
                # CH6 pp.245-246) is picked once per purchase, up to its trait cap.
                cap = validate._repeatable_purchase_cap(charm, character)
                if cap and character.charms.count(charm_id) >= cap:
                    ui.notify(f"{charm.name}: already bought {cap} times — its maximum.",
                              type="warning")
                    return
                character.charms.append(charm_id)
                ui.notify(f"Learned {charm.name}", type="positive")
            else:
                ui.notify(f"{charm.name}: prerequisites not met", type="warning")
                return
        update_graph()
        detail.refresh()
        spells_panel.refresh()        # a new/removed Sorcery Charm changes spell access
        _refresh_categories()         # learning/dropping DB enlightenment reveals/hides Dragon styles

    def add_another(charm_id: str) -> None:
        """Pre-lock: buy ONE MORE copy of a generic repeatable Charm the character
        already owns (the Mountain Folk Essence Satiation Method / Stone-Still Lungs,
        CH6 pp.245-246). Owned-but-under-cap is the one case `toggle` cannot express —
        it would REMOVE, not append — so the detail card's "Add another" calls this.
        The cap is enforced here, mirroring toggle's append branch."""
        if in_play():
            return
        charm = ruleset.charms.get(charm_id)
        if charm is None or not validate.meets_charm_requirements(ruleset, character, charm):
            ui.notify(f"{charm.name}: prerequisites not met", type="warning")
            return
        cap = validate._repeatable_purchase_cap(charm, character)
        if cap and character.charms.count(charm_id) >= cap:
            ui.notify(f"{charm.name}: already bought {cap} times — its maximum.",
                      type="warning")
            return
        character.charms.append(charm_id)
        ui.notify(f"Learned {charm.name}", type="positive")
        update_graph()
        detail.refresh()
        spells_panel.refresh()
        _refresh_categories()

    def buy_charm(charm_id: str) -> bool:
        """Post-lock half of `toggle`: spend XP on a Charm. Known Charms are not
        droppable here — a purchase is undone from the XP ledger, which keeps the
        append-only log and the traits in step."""
        charm = ruleset.charms.get(charm_id)
        if charm is None:
            return False
        if charm_id in character.charms:
            ui.notify(f"{charm.name} is already known — undo the purchase on the "
                      "Edit tab to give it back.", type="info")
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
        style_panel.refresh()
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
        if _is_graph_page() and not _visible_category_options():
            # Fall back to whichever OTHER graph page this character actually has —
            # naming "abilities" outright strands a splat that has no Abilities page
            # (a ghost has only Arcanoi and Martial Arts).
            other = next((g for g in _GRAPH_GROUPS
                          if g in GROUPS and g != state["group"]), "")
            if other:
                set_group(other)        # re-enters here for the categories below
                return
        opts = _visible_category_options()
        first = next(iter(opts), "")
        sel = widgets.get("category")
        if sel is not None:
            sel.set_options(opts, value=first)
        if first:
            set_category(first)
        _apply_group()                  # the Martial Arts page may have just vanished

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
        paths_panel.refresh()
        thaum_panel.refresh()
        elemental_panel.refresh()

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
            other = next((g for g in _GRAPH_GROUPS
                          if g in GROUPS and g != state["group"]), "")
            if other:
                set_group(other)
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
        # `min-w-0` lets this column shrink below its content's intrinsic width — a
        # flex item defaults to min-width:auto, so the long Path-power prose would
        # otherwise force the whole picker row to overflow the viewport no matter how
        # the text itself is told to wrap.
        with ui.column().classes("flex-1 gap-2 min-w-0"):
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
                        # The Storyteller permission itself now lives on the ST Options
                        # tab with the other table toggles (human's call, 2026-07-29);
                        # what stays here is the Splat dropdown it unlocks, plus a
                        # pointer for the player who wonders why the dropdown is empty.
                        if not in_play() and not _foreign_open():
                            ui.label("ST permission needed — see the ST Options tab") \
                                .classes("text-xs italic").style(f"color:{pal.accent}") \
                                .tooltip("An Eclipse or Moonshadow may not START play "
                                         "knowing another Exalt type's Charms without "
                                         "Storyteller permission (p.127).")
                        widgets["splat"] = ui.select(
                            _splat_options(), value=state["splat"], label="Splat",
                            on_change=lambda e: set_splat(e.value)).classes("w-40")
                        widgets["splat"].set_visibility(len(_splat_options()) > 1)
                    # Seeded from the Charm-tree group even when the picker opened on
                    # another page: the dropdown is HIDDEN there but still built, and
                    # a NiceGUI select whose value is absent from its options raises
                    # at build time. `state["category"]` always belongs to _start's
                    # group, so that is the group to offer.
                    _cat_opts = _visible_category_options(
                        state["group"] if _is_graph_page() else _group_of(_start))
                    # Belt and braces: the value must be among the options or ui.select
                    # raises at BUILD time, killing every sibling tab on the page (this
                    # is how a mortal blanked Abilities *and* Thaumaturgy at once). The
                    # page-level guard above should mean this never fires, but a select
                    # that can take the whole picker down does not get to be clever.
                    _cat_opts.setdefault(state["category"], _pretty(state["category"]))
                    widgets["category"] = ui.select(
                        _cat_opts, value=state["category"], label="Category",
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
            style_panel()
            # A real element (not ui.html, whose inline style gets sanitised away),
            # with an explicit DOM id for Cytoscape to mount into.
            widgets["graph"] = (ui.element("div").props("id=charm-graph")
                                .style(f"height:720px;width:100%;border:1px solid {pal.graph_border};"
                                       f"border-radius:8px;background:{pal.node_bg}"))
            # The Spells, Form Library, Augmentation and Thaumaturgy pages render
            # here, in place of the graph.
            spells_panel()
            forms_panel()
            augment_panel()
            panoply_panel()
            paths_panel()
            thaum_panel()
            elemental_panel()
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
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
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
