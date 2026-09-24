"""
ui/adversaries.py — the Storyteller's adversary roster, rendered on the party page.

The other half of `/gm`: the extras, beasts and NPCs the GM is running *against*
the party, beside the player characters they are fighting. Cards are the same
shape as the character cards next to them — a compact stat readout with live
trackers — but the entries behind them are `Adversary`, not `Character`, so
there is no sheet, no builder button and no lock.

Scope, deliberately: a list, the printed stats, and primitive trackers. This is
not a second character builder. Nothing here validates, prices or locks anything,
because an adversary is never built to a budget.

Two interactions carry the whole feature:

  * **Add** — from a catalogue template (a starting point the GM then edits) or
    blank. The instant a template is instantiated the copy is independent; the
    catalogue row is never written back to.
  * **Duplicate** — five bandits off one row, each with its own health track.
    Without it the GM is back to hand-copying, which is the thing this replaces.

Every computed number comes from engine.adversaries; this module draws widgets and
nothing else. The free-text trait/attack codec and the card's stat-line wording live
outside the UI layer and are re-exported here — see the re-export block below.
"""

from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui

from ..engine import adversaries as adv
from ..models.adversary import Adversary
from ..models.party import Party
from ..models.rules import Damage, RuleSet
from . import catalogue as cataloguemod
from . import theme
from . import view as viewmod

# Same swatch as the Play tab's boxes — one damage tracker to learn, not two.
_GOLD = "#f6e3b4"
_WHITE = "#ffffff"
_BORDER = "#d6b98c"
_MARK_COLOR = {
    Damage.BASHING: "#374151",
    Damage.LETHAL: "#b91c1c",
    Damage.AGGRAVATED: "#6b21a8",
}

_ATTRIBUTES = ["strength", "dexterity", "stamina", "charisma", "manipulation",
               "appearance", "perception", "intelligence", "wits"]
_VIRTUES = ["compassion", "conviction", "temperance", "valor"]


# --------------------------------------------------------------------------- #
# Ids, the trait/attack codec and the card presenters — RE-EXPORTS
#
# None of these touch the toolkit, so none of them live here: `next_id`,
# `_copy_name` and the `parse_traits`/`trait_line` + `parse_attacks`/`attack_line`
# codec pairs belong to `engine/adversaries.py` (beside `expand_health`/
# `format_health`); `summary_line` and `trait_map_line` are presenters and belong to
# `view.py`.
#
# ⚠ Re-exported, not re-implemented: these names are the call shape used below and by
# `tests/test_adversaries_ui.py`.
# --------------------------------------------------------------------------- #

from ..engine.adversaries import (  # noqa: F401  (re-export for existing callers)
    _copy_name, attack_line, category_line, next_id, parse_attacks, parse_categories,
    parse_traits, trait_line)
from .view import summary_line, trait_map_line  # noqa: F401  (re-export)


# --------------------------------------------------------------------------- #
# Trackers
# --------------------------------------------------------------------------- #

def _health_box(a: Adversary, i: int, mark: Optional[Damage], pal: theme.Palette,
                on_change: Callable[[], None]) -> None:
    """One clickable health box, labelled with its wound penalty. Same cycle and
    the same colours as ui.play.health_box, which drives the character cards."""
    with ui.column().classes("items-center gap-0"):
        ui.label(adv.level_label(a.health_levels[i])).classes(
            "text-gray-500").style("font-size:0.6rem")
        sym = _MARK_COLOR[mark] if mark else pal.accent
        box = ui.label(mark.value if mark else "").classes("cursor-pointer select-none")
        box.style(f"width:1.75rem;height:1.75rem;line-height:1.75rem;text-align:center;"
                  f"font-weight:700;border-radius:4px;border:1px solid {_BORDER};"
                  f"background:{_GOLD if mark else _WHITE};color:{sym};")
        # Marked so the render tests can click a specific box: these carry no text
        # (an unmarked box is empty by definition) and so cannot be found by content.
        box.mark(f"adv-health-{a.id}-{i}")
        box.on("click", lambda: (adv.cycle_mark(a, i), on_change()))


def _count_box(a: Adversary, i: int, filled: bool, field: str, cap: int,
               on_change: Callable[[], None]) -> None:
    """One box of a plain spent-count track (temporary Willpower)."""
    def click() -> None:
        adv.set_count(a, field, i, cap)
        on_change()

    box = ui.label("").classes("cursor-pointer select-none")
    box.style(f"width:1.25rem;height:1.25rem;border-radius:4px;border:1px solid {_BORDER};"
              f"background:{_GOLD if filled else _WHITE};")
    box.on("click", click)


# --------------------------------------------------------------------------- #
# The editor dialog
# --------------------------------------------------------------------------- #

def _catalogue_button(ruleset: RuleSet, pal: theme.Palette, kind: str, title: str,
                      field, *, trait: bool = False) -> None:
    """An "add from catalogue" button that writes picked NAMES into `field`.

    `field` is the NiceGUI input/textarea the roster edits; the pick is appended to
    its live value, so a GM can pick some and type the rest in the same box. `trait`
    selects the codec-safe append for the two rated lines (Abilities, Backgrounds)
    over the prose append the three free-text lines take.

    ⚠ Nothing is validated, filtered by splat, or checked against a prerequisite —
    see the note in `view.adversary_picker_rows`. The dialog stays OPEN across picks
    because these fields take a dozen entries at a time.
    """
    rows, group_of = viewmod.adversary_picker_rows(ruleset, kind)
    names = viewmod.picker_names(rows)

    def _pick(key) -> None:
        name = names.get(key)
        if not name:
            return
        field.value = (adv.append_trait(field.value or "", name) if trait
                       else adv.append_prose(field.value or "", name))

    def _open() -> None:
        cataloguemod.catalogue_dialog(
            pal, title, rows, _pick,
            allow_custom=False, keep_open=True,
            # 1,861 Charms is too many DOM rows for one open; the filter still
            # reaches every one of them.
            render_cap=True,
            group_of=group_of or None,
            subtitle="Nothing here is checked against prerequisites, minimums or "
                     "splat — this is the Storyteller's roster.")

    ui.button("Add from catalogue", icon="menu_book", on_click=_open
              ).props("flat dense").classes("text-xs").mark(f"adv-pick-{kind}")


def edit_dialog(ruleset: RuleSet, a: Adversary, on_save: Callable[[], None],
                pal: Optional[theme.Palette] = None) -> None:
    """Edit every printed field of one entry.

    Deliberately a flat form of plain inputs rather than the builder's dot
    tracks: these values are typed off a page or invented on the spot, never
    bought, so a stepper with a cap would be lying about what governs them.
    """
    # The roster hands its own palette down; the fallback keeps the dialog usable
    # for a caller that has none (the render tests open it directly).
    pal = pal or theme.palette(None)
    armor_labels = {"": "(none)"} | {arm.id: arm.name for arm in adv.armor_options(ruleset)}
    shield_labels = {"": "(none)"} | {s.id: s.name for s in adv.shield_options(ruleset)}

    with ui.dialog() as dialog, ui.card().classes(f"w-full max-w-3xl gap-2 {pal.card_solid}"):
        ui.label("Edit adversary").classes("text-lg font-bold")

        with ui.row().classes("w-full gap-2 no-wrap"):
            name = ui.input("Name", value=a.name).props("dense outlined").classes("grow")
            category = ui.input("Categories", value=adv.category_line(a.categories)).props(
                "dense outlined").classes("w-64").tooltip(
                "Free text, comma-separated — Extra, Beast, Spirit, whatever groups "
                "your roster. An entry is filed under every one of them.")
        with ui.row().classes("w-full gap-2 no-wrap"):
            nature = ui.input("Nature", value=a.nature).props("dense outlined").classes("grow")
            caste = ui.input("Caste / Aspect", value=a.caste).props(
                "dense outlined").classes("grow")

        # --- traits -------------------------------------------------------- #
        ui.label("ATTRIBUTES").classes("text-xs font-bold tracking-widest mt-2")
        ui.label("Leave a box empty where the block prints nothing — a beast has "
                 "three of the nine, and 0 is not the same as absent.").classes(
            "text-xs text-gray-500")
        attr_inputs: dict[str, ui.number] = {}
        with ui.row().classes("w-full gap-1 flex-wrap"):
            for key in _ATTRIBUTES:
                attr_inputs[key] = ui.number(
                    key[:3].title(), value=a.attributes.get(key), min=0, format="%d"
                ).props("dense outlined").classes("w-20")

        ui.label("VIRTUES").classes("text-xs font-bold tracking-widest mt-2")
        virtue_inputs: dict[str, ui.number] = {}
        with ui.row().classes("w-full gap-1 flex-wrap"):
            for key in _VIRTUES:
                virtue_inputs[key] = ui.number(
                    key.title(), value=a.virtues.get(key), min=0, format="%d"
                ).props("dense outlined").classes("w-28")

        abilities = ui.input("Abilities", value=trait_line(a.abilities)).props(
            "dense outlined").classes("w-full").tooltip(
            "As printed: Melee 3 (Swords +2), Dodge 2, Awareness 1")
        _catalogue_button(ruleset, pal, "abilities", "Abilities", abilities, trait=True)
        backgrounds = ui.input("Backgrounds", value=trait_line(a.backgrounds)).props(
            "dense outlined").classes("w-full")
        _catalogue_button(ruleset, pal, "backgrounds", "Backgrounds", backgrounds,
                          trait=True)

        # --- combat -------------------------------------------------------- #
        ui.label("COMBAT").classes("text-xs font-bold tracking-widest mt-2")
        with ui.row().classes("w-full gap-2 no-wrap items-center"):
            init = ui.number("Base initiative", value=a.base_initiative, min=0,
                             format="%d").props("dense outlined").classes("w-36")
            combat_pool = ui.number("Combat pool", value=a.combat_pool, min=0,
                                    format="%d").props("dense outlined").classes(
                "w-32").tooltip(
                "Extras only: the one pool that stands in for every roll they "
                "make (p.241). Leave empty for anything with real traits.")
            dodge = ui.number("Dodge pool", value=a.dodge, min=0, format="%d").props(
                "dense outlined").classes("w-32").tooltip(
                "Leave empty if the creature does not dodge at all")
            soak_l = ui.number("Natural soak L", value=a.soak_lethal, min=0,
                               format="%d").props("dense outlined").classes("w-32")
            soak_b = ui.number("Natural soak B", value=a.soak_bashing, min=0,
                               format="%d").props("dense outlined").classes("w-32")
        armor = ui.select(armor_labels, value=a.armor_id if a.armor_id in armor_labels else "",
                          label="Armour").props("dense outlined").classes("w-full").tooltip(
            "Mundane armour only. Adds to natural soak; its mobility penalty "
            "comes off the dodge pool automatically.")
        shield = ui.select(shield_labels,
                           value=a.shield_id if a.shield_id in shield_labels else "",
                           label="Shield").props("dense outlined").classes("w-full").tooltip(
            "Shields give no soak. They add their mobility penalty on top of the "
            "armour's, and make the bearer harder to hit (p.335).")

        ui.label("Attacks — one per line, as printed: "
                 "Bite: Speed 6 Accuracy 7 Damage 1L Defense 5").classes(
            "text-xs text-gray-500 mt-2")
        attacks = ui.textarea(
            value="\n".join(attack_line(x) for x in a.attacks)).props(
            "outlined dense autogrow").classes("w-full text-sm")

        # --- pools --------------------------------------------------------- #
        ui.label("POOLS").classes("text-xs font-bold tracking-widest mt-2")
        with ui.row().classes("w-full gap-2 no-wrap"):
            wp = ui.number("Willpower", value=a.willpower, min=0, format="%d").props(
                "dense outlined").classes("w-32")
            ess = ui.number("Essence", value=a.essence, min=0, format="%d").props(
                "dense outlined").classes("w-28")
            pool = ui.number("Essence pool", value=a.essence_pool, min=0,
                             format="%d").props("dense outlined").classes("w-32").tooltip(
                "A spirit's single pool. Leave 0 for an Exalt and use the two below.")
        with ui.row().classes("w-full gap-2 no-wrap"):
            personal = ui.number("Personal", value=a.personal_essence, min=0,
                                 format="%d").props("dense outlined").classes("w-32")
            peripheral = ui.number("Peripheral", value=a.peripheral_essence, min=0,
                                   format="%d").props("dense outlined").classes("w-32")
            materialize = ui.number("Cost to materialize", value=a.cost_to_materialize,
                                    min=0, format="%d").props("dense outlined").classes("w-44")
            dematerialize = ui.number("Cost to dematerialize",
                                      value=a.cost_to_dematerialize, min=0,
                                      format="%d").props("dense outlined").classes(
                "w-48").tooltip("Elementals pay this instead — their natural state "
                                "is the physical one (p.295).")

        health = ui.input("Health levels",
                          value=adv.format_health(a.health_levels)).props(
            "dense outlined").classes("w-full").tooltip(
            "As printed, repeats allowed: -0/-1 x 7/-2 x 12/-4/Incap")

        # --- prose ---------------------------------------------------------- #
        # Charms and Spells are free text on purpose: the book prints "All Solar
        # Charms the Storyteller cares to give him", which is not a list of ids.
        powers = ui.textarea("Powers", value=a.powers).props(
            "outlined dense autogrow").classes("w-full text-sm").tooltip(
            "The separate Powers line ghosts and elementals print — "
            "\"Materialize, Measure the Wind\"")
        _catalogue_button(ruleset, pal, "powers", "Powers", powers)
        charms = ui.textarea("Charms", value=a.charms).props(
            "outlined dense autogrow").classes("w-full text-sm")
        _catalogue_button(ruleset, pal, "charms", "Charms", charms)
        spells = ui.textarea("Spells", value=a.spells).props(
            "outlined dense autogrow").classes("w-full text-sm")
        _catalogue_button(ruleset, pal, "spells", "Spells", spells)
        notes = ui.textarea("Other notes", value=a.notes).props(
            "outlined dense autogrow").classes("w-full text-sm")

        def commit() -> None:
            a.name = name.value or ""
            a.categories = adv.parse_categories(category.value or "")
            a.nature = nature.value or ""
            a.caste = caste.value or ""
            a.attributes = {k: int(w.value) for k, w in attr_inputs.items()
                            if w.value not in (None, "")}
            a.virtues = {k: int(w.value) for k, w in virtue_inputs.items()
                         if w.value not in (None, "")}
            a.abilities = parse_traits(abilities.value)
            a.backgrounds = parse_traits(backgrounds.value)
            a.base_initiative = None if init.value in (None, "") else int(init.value)
            a.combat_pool = (None if combat_pool.value in (None, "")
                             else int(combat_pool.value))
            a.dodge = None if dodge.value in (None, "") else int(dodge.value)
            a.soak_lethal = int(soak_l.value or 0)
            a.soak_bashing = int(soak_b.value or 0)
            a.armor_id = armor.value or ""
            a.shield_id = shield.value or ""
            a.attacks = parse_attacks(attacks.value)
            a.willpower = int(wp.value or 0)
            a.essence = int(ess.value or 0)
            a.essence_pool = int(pool.value or 0)
            a.personal_essence = int(personal.value or 0)
            a.peripheral_essence = int(peripheral.value or 0)
            a.cost_to_materialize = int(materialize.value or 0)
            a.cost_to_dematerialize = int(dematerialize.value or 0)
            a.health_levels = adv.expand_health(health.value or "")
            a.powers = powers.value or ""
            a.charms = charms.value or ""
            a.spells = spells.value or ""
            a.notes = notes.value or ""
            # Marks are positional; re-length them against whatever the track is now.
            adv.normalize_damage(a)
            dialog.close()
            on_save()

        with ui.row().classes("justify-end w-full gap-2 mt-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Save", icon="check", on_click=commit).props("color=primary")
    dialog.open()


# --------------------------------------------------------------------------- #
# The roster
# --------------------------------------------------------------------------- #

def open_add_dialog(ruleset: RuleSet, catalog: dict[str, Adversary],
                    party_of: Callable[[], Party], refresh: Callable[[], None], *,
                    adjust: Optional[Callable[[Adversary], None]] = None,
                    title: str = "Add an adversary",
                    pal: Optional[theme.Palette] = None) -> None:
    """Open the dialog that adds an entry to the roster of `party_of()`: from a
    catalogue template, or blank. Call `adjust` on the new entry, then `refresh`.

    ⚠ The add goes through `engine.adversaries`. The native Party window runs the
    same operation.
    """
    def added(entry: Adversary, message: str, kind: str) -> None:
        if adjust is not None:
            adjust(entry)
        refresh()
        ui.notify(message, type=kind)

    def add_blank(dialog) -> None:
        dialog.close()
        added(adv.add_blank(party_of()),
              "Added a blank adversary — use Edit to fill it in", "positive")

    def add_from_template(template: Adversary, dialog) -> None:
        dialog.close()
        entry = adv.add_from_template(party_of(), template)
        added(entry, f"Added {entry.name}", "positive")

    pal = pal or theme.palette(None)
    templates = sorted(catalog.values(), key=lambda t: (adv.category_label(t), t.name))
    with ui.dialog() as dialog, ui.card().classes(f"w-full max-w-2xl gap-2 {pal.card_solid}"):
        ui.label(title).classes("text-lg font-bold")
        if templates:
            ui.label("Pick a template to start from — you get an editable copy, "
                     "and the catalogue entry is untouched.").classes(
                "text-xs text-gray-600")
            search = ui.input(placeholder="Filter…").props(
                "dense outlined clearable").classes("w-full")

            @ui.refreshable
            def rows() -> None:
                needle = (search.value or "").lower()
                shown = [t for t in templates
                         if needle in t.name.lower()
                         or needle in adv.category_label(t).lower()]
                with ui.column().classes("w-full gap-1 max-h-96 overflow-y-auto"):
                    for template in shown:
                        # The whole row is the click target (a bare button
                        # could not hold the two-line summary), so it carries
                        # the marker the render tests select it by.
                        with ui.row().classes(
                                "w-full items-center justify-between no-wrap "
                                "hover:bg-black/5 rounded px-2 py-1 cursor-pointer"
                        ).mark(f"adv-tpl-{template.id}").on(
                                "click", lambda t=template: add_from_template(t, dialog)):
                            with ui.column().classes("gap-0 min-w-0"):
                                ui.label(template.name).classes(
                                    "text-sm font-semibold truncate")
                                ui.label(summary_line(ruleset, template)).classes(
                                    "text-xs text-gray-600 truncate")
                            ui.label(adv.category_label(template)).classes(
                                "text-xs text-gray-500 shrink-0")
                    if not shown:
                        ui.label("Nothing matches.").classes(
                            "text-sm text-gray-500 p-2")

            search.on_value_change(rows.refresh)
            rows()
            ui.separator()
        ui.button("Add a blank adversary", icon="note_add",
                  on_click=lambda: add_blank(dialog)).props("flat").mark("adv-add-blank")
        with ui.row().classes("justify-end w-full"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
    dialog.open()


def roster_card(ruleset: RuleSet, party_of: Callable[[], Party], index: int,
                a: Adversary, pal: theme.Palette, refresh: Callable[[], None], *,
                extra: Optional[Callable[[], None]] = None,
                dialog_host=None, expanded: Optional[bool] = None,
                on_toggle: Optional[Callable[[], None]] = None) -> None:
    """Draw the card of entry `index` of the roster of `party_of()`: the stats, the
    trackers, and Reset, Duplicate, Edit and Remove. Call `refresh` after each change.

    `expanded` None draws the full card (the Party page). True or False draws the
    compact card of a narrow rail: the name, the health boxes and one line of
    Willpower and motes, and a chevron that calls `on_toggle`. An expanded compact
    card adds the full stats, the trackers and the buttons.

    `extra` draws more controls: in the header of a compact card, else at the end
    of the card. `dialog_host` is the element that holds the Edit dialog. ⚠ Give
    one that is not cleared by `refresh`: a dialog in a cleared element is deleted.
    The host holds one dialog at a time: Edit clears it first, because a closed
    dialog stays in its element.
    """
    def duplicate() -> None:
        adv.duplicate(party_of(), index)
        refresh()

    def remove() -> None:
        gone = adv.remove(party_of(), index)
        refresh()
        ui.notify(f"Removed {gone}", type="warning")

    def clear_damage() -> None:
        adv.reset_tracking(party_of().adversaries[index])
        refresh()

    def edit() -> None:
        if dialog_host is None:
            edit_dialog(ruleset, a, refresh, pal)
            return
        dialog_host.clear()
        with dialog_host:
            edit_dialog(ruleset, a, refresh, pal)

    marks = adv.normalize_damage(a)
    compact = expanded is not None
    mote_cap = adv.mote_cap(a)
    identity = "  ·  ".join(x for x in (adv.category_label(a), a.nature, a.caste) if x)

    def health() -> None:
        if not a.health_levels:
            return
        penalty = adv.worst_penalty(a)
        shown = ("none" if penalty is None
                 else "Incap" if penalty == adv.INCAPACITATED else str(penalty))
        ui.label(f"HEALTH  ·  penalty {shown}").classes(
            "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
        with ui.row().classes("gap-1 flex-wrap items-end"):
            for i in range(len(a.health_levels)):
                _health_box(a, i, marks[i], pal, refresh)

    with ui.card().classes(f"w-full {'p-2 gap-1' if compact else 'p-3 gap-2'} "
                           f"{pal.card_soft}").mark(f"adv-card-{a.id}"):
        if compact:
            with ui.row().classes("w-full items-center no-wrap gap-1"):
                with ui.column().classes("gap-0 min-w-0 flex-1"):
                    ui.label(a.name or "(unnamed)").classes(
                        "text-sm font-bold truncate").style(f"color:{pal.accent}")
                    if identity:
                        ui.label(identity).classes("text-xs text-gray-600 truncate")
                if extra is not None:
                    extra()
                ui.button(icon="expand_less" if expanded else "expand_more",
                          on_click=on_toggle).props("flat dense round size=sm").mark(
                    f"adv-toggle-{a.id}").tooltip(
                    "Hide the stats" if expanded else "Show the stats")
            health()
            if not expanded:
                bits = []
                if a.willpower:
                    bits.append(f"WP {a.willpower - a.willpower_spent}/{a.willpower}")
                if mote_cap:
                    bits.append(f"Motes {max(0, mote_cap - a.motes_spent)}/{mote_cap}")
                if bits:
                    ui.label("  ·  ".join(bits)).classes("text-xs text-gray-700").mark(
                        f"adv-line-{a.id}")
                return
            ui.label(summary_line(ruleset, a)).classes("text-xs text-gray-700")
        else:
            with ui.row().classes("w-full items-start justify-between no-wrap"):
                with ui.column().classes("gap-0 min-w-0"):
                    ui.label(a.name or "(unnamed)").classes(
                        "text-base font-bold truncate").style(f"color:{pal.accent}")
                    if identity:
                        ui.label(identity).classes("text-xs text-gray-600 truncate")
                ui.label(summary_line(ruleset, a)).classes(
                    "text-xs text-gray-700 text-right shrink-0")
            health()

        if a.willpower:
            ui.label(f"WILLPOWER  ({a.willpower - a.willpower_spent}/{a.willpower})"
                     ).classes("text-xs font-bold tracking-widest").style(
                f"color:{pal.accent}")
            with ui.row().classes("gap-1 flex-wrap"):
                for i in range(a.willpower):
                    _count_box(a, i, i < a.willpower_spent, "willpower_spent",
                               a.willpower, refresh)

        # One mote counter, whichever pool shape the entry uses. A spirit's
        # single pool and an Exalt's Personal+Peripheral both spend downward;
        # splitting the tracker in two would be tracking for its own sake.
        if mote_cap:
            shape = ("pool" if a.essence_pool
                     else f"{a.personal_essence} personal + {a.peripheral_essence} peripheral")
            with ui.row().classes("items-center gap-2"):
                ui.number("Motes spent", value=a.motes_spent, min=0, max=mote_cap,
                          format="%d",
                          on_change=lambda e, x=a: (
                              adv.set_motes_spent(x, e.value),
                              refresh())).props("dense outlined").classes("w-32")
                ui.label(f"{max(0, mote_cap - a.motes_spent)}/{mote_cap} left "
                         f"({shape})").classes("text-xs text-gray-600")

        for label, values, order in (("", a.attributes, _ATTRIBUTES),
                                     ("Virtues: ", a.virtues, _VIRTUES)):
            line = trait_map_line(values, order)
            if line:
                ui.label(label + line).classes("text-xs text-gray-600")
        for atk in a.attacks:
            ui.label(attack_line(atk)).classes("text-xs text-gray-700")
        if a.abilities:
            ui.label(trait_line(a.abilities)).classes("text-xs text-gray-600")
        if a.backgrounds:
            ui.label(f"Backgrounds: {trait_line(a.backgrounds)}").classes(
                "text-xs text-gray-600")
        for label, prose in (("Powers", a.powers), ("Charms", a.charms),
                             ("Spells", a.spells)):
            if prose:
                ui.label(f"{label}: {prose}").classes("text-xs text-gray-600")
        if a.notes:
            ui.label(a.notes).classes("text-xs text-gray-600 italic")

        # Icon-only buttons, so each is marked for the render tests.
        with ui.row().classes("gap-1 justify-end w-full items-center"):
            if extra is not None and not compact:
                extra()
                ui.space()
            ui.button(icon="restart_alt", on_click=clear_damage
                      ).props("flat dense").tooltip(
                "Clear damage and spent pools").mark(f"adv-reset-{a.id}")
            ui.button(icon="content_copy", on_click=duplicate
                      ).props("flat dense").tooltip(
                "Duplicate — a separate tracker").mark(f"adv-dup-{a.id}")
            ui.button(icon="edit", on_click=edit
                      ).props("flat dense").tooltip("Edit stats").mark(f"adv-edit-{a.id}")
            ui.button(icon="delete", on_click=remove).props(
                "flat dense color=red").tooltip(
                "Remove from roster").mark(f"adv-del-{a.id}")


def build_roster(ruleset: RuleSet, catalog: dict[str, Adversary],
                 party_of: Callable[[], Party], pal: theme.Palette,
                 refresh: Callable[[], None]) -> None:
    """Render the whole adversary section.

    `party_of` is a callable rather than a Party so the section survives the page
    swapping the bundle underneath it (New party / Load party), exactly as the
    character grid does.

    `catalog` is passed in rather than read off the RuleSet on purpose. The
    templates are book data, but they are not *rules*: they take no part in
    prerequisite resolution or load-time link-checking, which is what a RuleSet
    is for. Keeping them out also keeps models/rules.py from having to import the
    character-domain Adversary, which would be a cycle."""
    party = party_of()

    # ---- section ----------------------------------------------------------- #
    with ui.row().classes("w-full items-center gap-2 mt-4"):
        ui.label("ADVERSARIES").classes("text-xs font-bold tracking-widest").style(
            f"color:{pal.accent}")
        ui.label(f"({len(party.adversaries)})").classes("text-xs text-gray-500")
        ui.space()
        ui.button("Add adversary", icon="pest_control_rodent",
                  on_click=lambda: open_add_dialog(ruleset, catalog, party_of, refresh,
                                                   pal=pal)
                  ).props("flat")

    if not party.adversaries:
        with ui.card().classes("w-full p-4 items-center"):
            ui.label("No adversaries yet.").classes("text-sm font-bold")
            ui.label("Add extras, beasts or NPCs to track them alongside the party."
                     ).classes("text-xs text-gray-600")
        return

    with ui.grid().classes("w-full gap-3").style(
            "grid-template-columns:repeat(auto-fit,minmax(20rem,1fr))"):
        for index, entry in enumerate(party.adversaries):
            roster_card(ruleset, party_of, index, entry, pal, refresh)
