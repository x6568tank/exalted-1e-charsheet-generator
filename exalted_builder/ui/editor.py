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
from ..engine import derive, merits, validate
from ..models.character import (
    Armor, BackgroundEntry, Character, CollegeRating, CraftRating, HealthLevel,
    MeritFlawPurchase, Specialty, VirtueFlaw, Weapon)

_BASE_HEALTH = {0: 1, -1: 2, -2: 2, -4: 1}   # base levels per penalty tier


def _health_total(character: Character, penalty: int) -> int:
    """Effective number of health levels at a tier: base + added - removed."""
    delta = sum((-1 if hl.removed else 1)
                for hl in character.health_bonus_levels if hl.penalty == penalty)
    return max(0, _BASE_HEALTH.get(penalty, 0) + delta)
from ..models.rules import AbilityName, AttributeName, RuleSet, VirtueName
from . import theme
from . import view as viewmod

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "exalted_builder" / "data"
_EXAMPLE = _REPO_ROOT / "examples" / "ashes-of-dawn.character.json"

# Presentation-only: intra-splat chargen origins to offer per Exalt type, and their
# display labels. The origin *value* drives ruleset.budgets_for (keyed "<exalt>" for
# the first/default origin and "<exalt>:<origin>" for the rest); all the budget
# numbers live in chargen_budgets.json — this map is just which choices to show.
_SPLAT_ORIGINS: dict[str, dict[str, str]] = {
    # A Solar trained by the Cult of the Illuminated has a different initiation
    # entirely (p.89): 30 Abilities, 9 Backgrounds, 8 Charms, Essence 3, plus a
    # training camp and a Calling. "standard" has no `Solar:standard` budget row, so
    # it falls back to the plain "Solar" row — the same trick "dynastic" and "loyal"
    # use below.
    "Solar": {"standard": "Standard", "illuminated": "Cult of the Illuminated"},
    # The Outcaste book adds four Dragon-Blooded origins on top of the core two. Each
    # varies by UPBRINGING as well — see _ORIGIN_UPBRINGINGS below, which is the second
    # dropdown; the origin decides Backgrounds/Charms/Virtues, the upbringing decides
    # the Ability budget and its minimums.
    "Dragon-Blooded": {
        "dynastic": "Dynastic", "outcaste": "Outcaste",
        "lookshy": "Lookshy (Seventh Legion)",
        "forest-witch": "Forest Witch",
        "lost-egg": "Lost Egg",
        "pirate": "Pirate (Eos and Ossissa)",
    },
    # Abyssal Backgrounds depend on standing with the Deathlord: 13 dots for a loyal
    # deathknight, 5 for a fugitive/renegade (p.122). First key is the default
    # (plain "Abyssal" budget row); "fugitive" maps to "Abyssal:fugitive".
    "Abyssal": {"loyal": "Loyal Deathknight", "fugitive": "Fugitive"},
    # Unlike the above two, Lunar "casteless" is coupled to the Caste field itself,
    # not independent of it (engine.validate.check_lunar_casteless_consistency) — the
    # editor doesn't yet auto-sync the Caste dropdown when this is picked, so choosing
    # "Casteless" here also requires setting Caste to Casteless, or validation flags it.
    "Lunar": {"society": "Society (Silver Pact)", "casteless": "Casteless"},
    # A ronin Sidereal evaded the Celestial Hierarchy entirely (p.100): 25 abilities,
    # 7 backgrounds from a fixed list, 8 Charms with no Sidereal Martial Arts, no
    # Colleges and no Ability minimums. Independent of the Caste field (a ronin still
    # has a Caste), unlike Lunar's casteless.
    "Sidereal": {"hierarchy": "Celestial Hierarchy", "ronin": "Ronin"},
    # Core p.103 draws one line through the mortal rules: a heroic mortal gets 6/4/3
    # Attributes and 22 Ability dots, an ordinary one 4/3/3 and 16. Everything else on
    # the page (5 Backgrounds, no Charms, Essence 1, 21 bonus points) is shared, which
    # is why this is an origin and not two splats. "heroic" is the default and so has
    # no `Mortal:heroic` row — it falls back to the plain "Mortal" row, the same trick
    # "dynastic" and "loyal" use above.
    "Mortal": {"heroic": "Heroic Mortal", "ordinary": "Ordinary Mortal"},
}

# The second axis, keyed by "<exalt_type>:<origin>". Only origins that HAVE variants
# appear here, and the first key of each is the origin's own default (it has no
# ":<upbringing>" budget row, so it falls back to the origin row — the same trick the
# origins above use against the splat row). The Outcaste book is the only source of
# these so far; every other splat has no entry and so gets no second dropdown.
_ORIGIN_UPBRINGINGS: dict[str, dict[str, str]] = {
    # p.68: a Lookshy Terrestrial who was not raised there trades the 35 Ability dots
    # and the Lookshy minimums for 25/10, but keeps the 13 Backgrounds and 6 Charms.
    "Dragon-Blooded:lookshy": {
        "": "Born in Lookshy", "foreign": "Raised elsewhere"},
    # p.132: an ex-Dynast keeps the Realm schooling; other outcastes get 25 dots; one
    # raised by Oreithyia also buys Virtues and Essence cheaper (p.133).
    "Dragon-Blooded:forest-witch": {
        "": "Ex-Dynast", "outcaste": "Outcaste", "oreithyia": "Raised by Oreithyia"},
    # p.159: three Realm cases plus the Threshold, which is the only one that drops
    # the Aspect/Favored minimum to 10.
    "Dragon-Blooded:lost-egg": {
        "": "Realm, lower-class birth",
        "graduate": "Pasiap's Stair / Cloister of Wisdom",
        "patrician": "Patrician-born",
        "threshold": "Threshold outcaste"},
    # p.96: Dynast or born outcaste; both need Sail.
    "Dragon-Blooded:pirate": {"": "Dynast", "outcaste": "Born outcaste"},
}


def upbringing_options(exalt_type: str, origin: str) -> dict[str, str]:
    """The upbringing choices for this splat/origin, or {} when it has none (which is
    every splat but the Outcaste-book Dragon-Blooded). The UI renders the second
    dropdown only when this is non-empty, so no other splat grows a control."""
    return _ORIGIN_UPBRINGINGS.get(f"{exalt_type}:{origin}", {})


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


# Quasar's QSelect renders each dropdown entry through its scoped `option` slot. The
# default slot shows the label alone, so a catalog description has nowhere to appear;
# this replaces it with the same item plus a QTooltip. `props` is the scope variable
# NiceGUI exposes to a slot template.
_OPTION_TOOLTIP_SLOT = """
<q-item v-bind="props.itemProps">
  <q-item-section>
    <q-item-label>{{ props.opt.label }}</q-item-label>
  </q-item-section>
  <q-tooltip v-if="props.opt.description"
             anchor="center right" self="center left"
             class="text-body2"
             style="max-width:32rem; white-space:normal">
    {{ props.opt.description }}
  </q-tooltip>
</q-item>
"""


class DescribedSelect(ui.select):
    """A ``ui.select`` whose dropdown entries carry a hover tooltip with the catalog
    description of the option, so the text authored in ``data/`` is actually readable
    where you choose from it.

    NiceGUI builds each option as ``{'value': <index>, 'label': <name>}``. The
    description has to be injected into that dict for the `option` slot to render it,
    and it cannot simply be assigned after construction: ``Element._props`` is an
    observable dict, so writing to it schedules an update, and
    ``ChoiceElement.update()`` rebuilds ``options`` from the labels — silently
    discarding the descriptions. Overriding ``_update_options`` instead re-applies
    them every time the options are (re)built, including after ``set_options``.

    Descriptions are keyed by option NAME. A name with no description gets no
    tooltip, so an off-catalog custom entry (folded in by `_opts_with`) is harmless."""

    def __init__(self, options, *, descriptions: dict[str, str], **kwargs) -> None:
        self._descriptions = descriptions or {}
        super().__init__(options, **kwargs)
        self.add_slot("option", _OPTION_TOOLTIP_SLOT)

    def _update_options(self) -> None:
        super()._update_options()
        # `_labels` is what super() built the option dicts from, so it lines up 1:1.
        described = []
        for option, name in zip(self._props["options"], self._labels):
            text = self._descriptions.get(str(name), "")
            described.append({**option, "description": text} if text else option)
        with self._props.suspend_updates():      # we are already inside an update
            self._props["options"] = described


def build_editor(ruleset: RuleSet, character: Character, save_path: Path,
                 *, with_header: bool = True, on_theme_change=None) -> None:
    """Render the whole editor for `character`. Pure-ish wiring: every control
    mutates the Character and refreshes the live readout. With `with_header=False`
    the title/Save bar is omitted (the embedding app provides one). `on_theme_change`
    (if given) is called after the Exalt type changes so an embedding app can re-paint
    its own chrome (header bar / page background) to the new splat's palette."""
    pal = theme.palette(character.exalt_type)

    # ---- live readout (recomputes the engine each refresh) ---------------- #
    @ui.refreshable
    def readout() -> None:
        view = viewmod.build_sheet_view(ruleset, character)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        errors = [i for i in view.issues if i.severity == "error"]
        ui.label(bp).classes("text-sm font-semibold").style(f"color:{pal.accent}")
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
        ui.label("Bonus Points").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
        color = "#b91c1c" if bd.over_budget else "#15803d"
        ui.label(f"{bd.total} / {bd.available} spent").classes("text-sm font-semibold").style(f"color:{color}")
        ui.separator()
        for line in bd.lines:
            muted = "" if line.points else "text-gray-400"
            with ui.row().classes("w-full justify-between no-wrap items-baseline"):
                ui.label(line.domain).classes(f"text-xs {muted}")
                ui.label(str(line.points)).classes(f"text-xs {muted}")

    # ---- live tally of ability dots spent (updates on every dot click) ----- #
    @ui.refreshable
    def ability_tally() -> None:
        b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
        spent = (sum(v for a, v in character.abilities.items() if a != AbilityName.CRAFT)
                 + sum(cr.rating for cr in character.crafts))
        over = spent > b.ability_dots
        ui.label(f"{spent} / {b.ability_dots} dots spent").classes(
            "text-xs font-semibold").style(
            f"color:{'#b91c1c' if over else pal.accent}")

    def changed() -> None:
        readout.refresh()
        bp_log.refresh()
        ability_tally.refresh()

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
                       .classes("cursor-pointer").style(f"color:{pal.accent}")
                       .on("click", lambda e, i=i: click(i)))

        def click(i: int) -> None:
            cur = get()
            new = i - 1 if i == cur else i      # click the current top pip to step down
            setv(max(lo, min(hi, new)))
            show.refresh()
            changed()

        show()

    def panel(title: str):
        card = ui.card().classes(f"w-full p-3 {pal.card_soft}")
        with card:
            ui.label(title).classes("text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
        return card

    # ---- the editor body (refreshes on structural changes) ---------------- #
    @ui.refreshable
    def body() -> None:
        caste_def = ruleset.castes.get(character.caste)
        caste_abilities = set(caste_def.caste_abilities) if caste_def else set()
        caste_attributes = set(caste_def.caste_attributes) if caste_def else set()
        # Alchemical allocates Attributes to Caste/Favored/remaining SETS, not to
        # prioritised categories, and its Favored slot is Attributes, not Abilities.
        cf_attr_mode = viewmod.uses_caste_favored_attributes(ruleset, character)
        favored_attrs = set(character.favored_attributes)
        # chargen budget for THIS character (splat + origin), so panel headers show
        # the right numbers (Solar 8/6/4·25; DB Dynastic 7/6/4·35, Outcaste ·25).
        b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
        ap = "/".join(str(p) for p in b.attribute_pools)
        # splats name the caste slot differently: Solar "Caste", Dragon-Blooded "Aspect"
        exalt_def = ruleset.exalt_for(character.exalt_type)
        caste_noun = exalt_def.caste_noun
        # Whether the SPLAT has castes at all, as opposed to this character having an
        # unrecognised one — the two want different UI (see the caste-info box below).
        splat_has_castes = any(cd.exalt_type == character.exalt_type
                               for cd in ruleset.castes.values())

        # caste-info box (left) + identity fields (right). The BP-spend log lives in
        # the right-hand sticky column under Live Validation, not here.
        with ui.row().classes("w-full gap-2 no-wrap items-stretch"):
            with ui.card().classes(f"w-72 flex-none p-3 {pal.card_soft} gap-1"):
                if caste_def:
                    ui.label(f"{caste_def.label} {caste_noun}").classes(
                        "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                    if caste_def.description:
                        ui.label(caste_def.description).classes("text-xs")
                    # A caste sets caste_abilities OR caste_attributes, never both —
                    # Lunars have no Caste Abilities at all (The Lunars p.90).
                    if caste_def.caste_attributes:
                        ui.label(f"{caste_noun} Attributes: " + ", ".join(
                            _label(a.value) for a in caste_def.caste_attributes)).classes("text-xs italic")
                    elif caste_def.caste_abilities:
                        ui.label(f"{caste_noun} Abilities: " + ", ".join(
                            _label(a.value) for a in caste_def.caste_abilities)).classes("text-xs italic")
                    if caste_def.anima_powers:
                        ui.separator()
                        ui.label("Anima Power").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                        ui.label(caste_def.anima_powers).classes("text-xs")
                elif splat_has_castes:
                    ui.label("Unknown caste").classes("text-xs text-gray-500")
                else:
                    # Not an error for this splat — mortals have no caste to be
                    # unknown. The box keeps its place in the row so the identity
                    # fields beside it don't jump width between splats.
                    ui.label(exalt_def.label).classes(
                        "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                    ui.label("Not one of the Chosen — no caste, no Charms, "
                             "Essence 1.").classes("text-xs")

            with ui.column().classes("flex-1 gap-2 min-w-0"):
                with panel("Identity"):
                    with ui.row().classes("w-full gap-3 no-wrap"):
                        ui.input("Name", value=character.name,
                                 on_change=lambda e: (setattr(character, "name", e.value), changed())).classes("flex-1")
                        ui.input("Concept", value=character.concept,
                                 on_change=lambda e: setattr(character, "concept", e.value)).classes("flex-1")
                    # Wraps (no `no-wrap`) so the identity controls flow onto a second
                    # line rather than squashing to truncated labels ("C…"); each gets
                    # a min width so its label always shows in full.
                    _field = "flex-1 min-w-[10rem]"
                    with ui.row().classes("w-full gap-3 items-end"):
                        exalt_opts = {ex.id: ex.label for ex in ruleset.exalts.values()}
                        exalt_opts.setdefault(character.exalt_type, character.exalt_type)
                        ui.select(exalt_opts, label="Exalt type", value=character.exalt_type,
                                  on_change=lambda e: set_exalt_type(e.value)).classes(_field)
                        caste_opts = {cd.id: cd.label for cd in ruleset.castes.values()
                                      if cd.exalt_type == character.exalt_type}
                        # A splat with NO castes at all doesn't get the control: mortals
                        # "select Nature as normal but do not select a caste" (core p.103).
                        # Distinct from Lunar, who HAS castes that carry no caste-abilities.
                        if caste_opts:
                            # keep the current caste selectable even if off-splat (NiceGUI 3.x
                            # ui.select raises if value ∉ options — see the select-value gotcha)
                            caste_opts.setdefault(character.caste, character.caste)
                            ui.select(caste_opts, label=caste_noun, value=character.caste,
                                      on_change=lambda e: set_caste(e.value)).classes(_field)
                        origins = _SPLAT_ORIGINS.get(character.exalt_type)
                        if origins:
                            ui.select(origins, label="Origin",
                                      value=character.origin or next(iter(origins)),
                                      on_change=lambda e: set_origin(e.value)).classes(_field)
                            # Second axis, and only for the origins that have one — see
                            # _ORIGIN_UPBRINGINGS. Everything else renders exactly as before.
                            ups = upbringing_options(
                                character.exalt_type, character.origin or next(iter(origins)))
                            if ups:
                                ui.select(ups, label="Upbringing",
                                          value=character.upbringing if character.upbringing in ups
                                          else next(iter(ups)),
                                          on_change=lambda e: set_upbringing(e.value)).classes(_field)
                        nature_names = [n.name for n in ruleset.nature_catalog.values()]
                        ui.select(_opts_with(nature_names, character.nature), label="Nature",
                                  value=character.nature or None,
                                  with_input=True, new_value_mode="add-unique",
                                  on_change=lambda e: setattr(character, "nature", e.value or "")).classes(_field)
                        ui.input("Anima", value=character.anima,
                                 on_change=lambda e: setattr(character, "anima", e.value)).classes(_field)
                    # Favored ABILITIES (most splats) or Favored ATTRIBUTES (Alchemical,
                    # p.60) — a splat has one or the other. `favored_count` is 0 for a
                    # caste_favored splat, so the abilities picker hides itself there.
                    # Asked of the engine rather than the budget row because a heroic
                    # mortal's single Favoured Ability is an ST toggle, not a budget.
                    fav_n = validate.favored_ability_count(ruleset, character)
                    if fav_n:
                        ui.select({a: _label(a.value) for a in AbilityName},
                                  label=f"Favored abilities (pick {fav_n})",
                                  value=list(character.favored_abilities), multiple=True,
                                  on_change=lambda e: set_favored(e.value)).classes("w-full").props("use-chips")
                    if cf_attr_mode:
                        ui.select({a: _label(a.value) for a in AttributeName},
                                  label=f"Favored Attributes (pick {b.attribute_favored_count})",
                                  value=list(character.favored_attributes), multiple=True,
                                  on_change=lambda e: set_favored_attributes(e.value)).classes("w-full").props("use-chips")

        # Training camp + Calling (Cult of the Illuminated, p.89-93). Its own full-width
        # panel between Identity and Attributes rather than inside the caste-info card:
        # that row is `items-stretch`, so a tall left column stretches the whole row and
        # leaves a gap under the shorter Identity panel. Rendered only when the ORIGIN
        # uses camps, so no other splat grows an empty panel.
        camp_view = viewmod.build_camp_view(ruleset, character)
        if camp_view is not None:
            with panel("Training Camp & Calling"):
                with ui.row().classes("w-full gap-3 items-start"):
                    # left: the camp, its floors and its free-Charm package
                    with ui.column().classes("flex-1 gap-1 min-w-0"):
                        ui.select({cid: label for cid, label in camp_view.camp_options},
                                  label="Training camp", value=camp_view.camp_id or None,
                                  on_change=lambda e: set_camp(e.value)).classes("w-full")
                        if camp_view.camp_description:
                            ui.label(camp_view.camp_description).classes("text-xs")
                        if camp_view.minimums:
                            ui.label("Required Abilities: " + " · ".join(
                                camp_view.minimums)).classes("text-xs italic")
                        if camp_view.granted_fixed:
                            ui.label("Free Charms: " + ", ".join(
                                n for _, n in camp_view.granted_fixed)).classes("text-xs italic")
                        for idx, choice in enumerate(camp_view.choices):
                            suffix = f" (pick {choice.pick})" if choice.is_category_choice else ""
                            # An option the page offers but `data/` cannot yet satisfy stays
                            # LISTED — hiding it would misrepresent the rulebook — but is
                            # marked, and set_camp_choice refuses it rather than assigning
                            # nothing and blanking the control.
                            opts = {o.key: (o.label if o.available
                                            else f"{o.label} — {o.reason}")
                                    for o in choice.options}
                            ui.select(opts, label=choice.label + suffix,
                                      value=choice.chosen_key or None,
                                      on_change=lambda e, i=idx: set_camp_choice(i, e.value)
                                      ).classes("w-full")
                            # Picking the style is only half the choice — the package is
                            # "two Charms from ONE of four martial arts" (p.90), so the
                            # player chooses WHICH. Multi-select, capped at `pick`.
                            if choice.charm_options:
                                copts = {o.charm_id: (o.label if o.meets_minimums
                                                      else f"{o.label} — {o.reason}")
                                         for o in choice.charm_options}
                                ui.select(copts, multiple=True,
                                          label=f"Which {choice.pick}?",
                                          value=list(choice.chosen_charm_ids),
                                          on_change=lambda e, i=idx: set_camp_choice_charms(
                                              i, list(e.value or []))
                                          ).props("use-chips").classes("w-full")
                    # right: the Calling and what it discounts
                    with ui.column().classes("flex-1 gap-1 min-w-0"):
                        if camp_view.calling_options:
                            ui.select({cid: label for cid, label in camp_view.calling_options},
                                      label="Calling", value=camp_view.calling_id or None,
                                      on_change=lambda e: set_calling(e.value)).classes("w-full")
                            if camp_view.calling_description:
                                ui.label(camp_view.calling_description).classes("text-xs")
                            if camp_view.calling_abilities:
                                ui.label("✧ Calling Abilities: " + ", ".join(
                                    camp_view.calling_abilities)).classes("text-xs italic")
                            if camp_view.calling_charms:
                                ui.label(f"✧ {len(camp_view.calling_charms)} Calling Charms — "
                                         f"discounted at chargen and in play").classes("text-xs italic")

        # attributes
        attr_header = viewmod.attribute_budget_summary(ruleset, character) or f"prioritise {ap}"
        with panel(f"Attributes ({attr_header})"):
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
                                # Caste Attributes (●) are the parallel to other splats'
                                # Caste Abilities (Lunar p.90); an Alchemical also marks
                                # its player-chosen Favored Attributes (✦, p.60).
                                mark = "●" if a in caste_attributes else ("✦" if a in favored_attrs else "")
                                ui.label(mark).classes("text-xs w-3").style(f"color:{pal.accent}")
                                ui.label(_label(a.value)).classes("text-sm w-28")
                                # update this column's tally live as its dots change
                                dots(lambda a=a: character.attributes[a],
                                     lambda v, a=a, upd=show_spent: (
                                         character.attributes.__setitem__(a, v), upd()),
                                     1, 5)

        # abilities (by ability-caste group)
        with panel(f"Abilities ({b.ability_dots} dots; ≥{b.ability_min_caste_favored} caste/favoured; ≤{b.ability_cap_pre_bp} each pre-bonus)"):
            ability_tally()
            groups = viewmod.ability_group_defs(ruleset, character.exalt_type)
            calling_marks = viewmod.calling_ability_marks(ruleset, character)
            for start in range(0, len(groups), 3):
                with ui.row().classes("w-full gap-2 no-wrap"):
                    for group_label, abilities in groups[start:start + 3]:
                        with ui.column().classes("flex-1 gap-1"):
                            if group_label:
                                ui.label(group_label).classes("text-xs font-semibold").style(f"color:{pal.accent}")
                            for a in abilities:
                                # ● Caste · ✦ Favoured · ✧ Calling. An Ability can be
                                # both Caste/Favoured AND a Calling Ability — the two
                                # discounts stack (p.90) — so the marks concatenate
                                # rather than one winning.
                                mark = "●" if a in caste_abilities else ("✦" if a in character.favored_abilities else "")
                                if a in calling_marks:
                                    mark += "✧"
                                with ui.row().classes("w-full items-center gap-1 no-wrap"):
                                    ui.label(mark).classes("text-xs w-3").style(f"color:{pal.accent}")
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

        # backgrounds — autofill list is splat-aware (DB gain Breeding/Connections,
        # lose Contacts/Influence/Followers; see RuleSet.backgrounds_for).
        bg_catalog = ruleset.backgrounds_for(character.exalt_type)
        bg_names = [b.name for b in bg_catalog]
        bg_descriptions = {b.name: b.description for b in bg_catalog}
        with panel(f"Backgrounds ({b.background_dots} dots; ≤{b.background_cap_pre_bp} pre-bonus)"):
            for idx, bg in enumerate(character.backgrounds):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    (DescribedSelect(_opts_with(bg_names, bg.name), descriptions=bg_descriptions,
                                     value=bg.name or None, label="Background",
                                     with_input=True, new_value_mode="add-unique",
                                     on_change=lambda e, bg=bg: setattr(bg, "name", e.value or ""))
                     .classes("flex-1"))
                    ui.input(value=bg.note, placeholder="note",
                             on_change=lambda e, bg=bg: setattr(bg, "note", e.value)).classes("flex-1")
                    dots(lambda bg=bg: bg.rating, lambda v, bg=bg: setattr(bg, "rating", v), 0, 5)
                    ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_bg(idx)).props("flat dense round")
            ui.button("Add background", icon="add", on_click=add_bg).props("flat dense")

        # Merits & Flaws. Shown only when the rule set ships any (decision 0011: the
        # data file is optional). A MERIT costs bonus points; a FLAW grants them, which
        # is why the header reports the grant separately rather than as a negative.
        if ruleset.merits_flaws:
            # Label carries the sign so a Flaw reads as a grant, not a charge; a
            # variable-cost entry shows its range instead of a single number.
            def _merit_label(m) -> str:
                if m.cost_options:
                    lo, hi = min(m.cost_options.values()), max(m.cost_options.values())
                    price = f"{lo}-{hi}"
                else:
                    price = str(m.cost)
                sign = "−" if m.kind == "merit" else "+"
                return f"{m.name}  ({sign}{price} {m.category or m.kind})"

            merit_opts = {m.id: _merit_label(m) for m in sorted(
                ruleset.merits_flaws.values(),
                key=lambda m: (m.kind != "merit", m.name))}
            eff = merits.merits_and_flaws_calc(ruleset, character)
            spent = validate.merit_bonus_point_cost(ruleset, character)
            grant = eff.bonus_point_grant
            header = f"Merits & Flaws (−{spent} BP"
            header += f", +{grant} from Flaws)" if grant else ")"
            with panel(header):
                for idx, mp in enumerate(character.merits_flaws):
                    definition = ruleset.merits_flaws.get(mp.merit_id)
                    with ui.row().classes("w-full items-center gap-2 no-wrap"):
                        # An off-catalogue id (a save opened without its data) stays
                        # selectable rather than 500ing the select — the same guard the
                        # caste and college dropdowns use.
                        row_opts = dict(merit_opts)
                        row_opts.setdefault(mp.merit_id, mp.merit_id)
                        ui.select(row_opts, value=mp.merit_id, label="Merit / Flaw",
                                  on_change=lambda e, mp=mp: set_merit(mp, e.value)
                                  ).classes("flex-1").props("dense")
                        # Tier only for a variable-cost entry (Oathbound Magic).
                        if definition is not None and definition.cost_options:
                            ui.select({t: f"{t.title()} ({v})"
                                       for t, v in definition.cost_options.items()},
                                      value=mp.tier or None, label="Oath",
                                      on_change=lambda e, mp=mp: (setattr(mp, "tier", e.value or ""),
                                                                  body.refresh(), changed())
                                      ).classes("w-40").props("dense")
                            # Arena drives the same-arena stacking reduction (p.122);
                            # free text, because the page's list is examples, not a set.
                            ui.input(value=mp.arena, placeholder="arena (combat, food…)",
                                     on_change=lambda e, mp=mp: (setattr(mp, "arena", e.value),
                                                                 body.refresh(), changed())
                                     ).classes("w-40").props("dense")
                        ui.input(value=mp.detail,
                                 placeholder=(definition.repeatable_by if definition
                                              and definition.repeatable_by else "note"),
                                 on_change=lambda e, mp=mp: (setattr(mp, "detail", e.value),
                                                             changed())).classes("flex-1").props("dense")
                        ui.button(icon="delete",
                                  on_click=lambda e=None, idx=idx: remove_merit(idx)
                                  ).props("flat dense round")
                    if definition is not None:
                        # The printed cost line always shows: a few qualifiers cannot
                        # be priced by the engine (a per-caste rate, a relative one),
                        # so the ST must be able to see what the book actually says.
                        if definition.cost_note:
                            ui.label(definition.cost_note).classes(
                                "text-xs font-mono opacity-60 pl-1")
                        if definition.exalt_types:
                            ui.label("Restricted to: " + ", ".join(definition.exalt_types)
                                     ).classes("text-xs italic opacity-70 pl-1")
                        if definition.description:
                            ui.label(definition.description).classes("text-xs opacity-70 pl-1")
                ui.button("Add merit / flaw", icon="add", on_click=add_merit).props("flat dense")
                # Say which held Merits this build treats as narrative, rather than
                # letting a player wonder why nothing changed.
                if eff.narrative_only:
                    names = ", ".join(sorted(
                        ruleset.merits_flaws[m].name for m in eff.narrative_only
                        if m in ruleset.merits_flaws))
                    if names:
                        ui.label(f"Narrative only in this build: {names}."
                                 ).classes("text-xs italic opacity-70")

        # Astrological Colleges (Sidereal) — a rated Advantage with its own pool.
        # Shown only for splats that ship colleges (b.college_dots > 0). Options are
        # grouped by house label, and the character's own Maiden's house is marked ★.
        if b.college_dots > 0 and ruleset.colleges:
            own_house = character.caste
            college_opts = {
                col.id: (f"{'★ ' if col.house == own_house else ''}{col.name}"
                         f"  ·  {col.house_label}")
                for col in ruleset.colleges.values()
            }
            own_dots = sum(cr.rating for cr in character.colleges
                           if (c := ruleset.colleges.get(cr.college_id)) and c.house == own_house)
            with panel(f"Astrological Colleges ({b.college_dots} dots; ≥{b.college_min_own_house} "
                       f"in your Maiden's ★ house — have {own_dots}; ≤{b.college_cap_pre_bp} pre-bonus)"):
                for idx, cr in enumerate(character.colleges):
                    # guard an off-catalog id (old save) so the select never 500s
                    row_opts = (college_opts if cr.college_id in college_opts
                                else {**college_opts, cr.college_id: cr.college_id})
                    with ui.row().classes("w-full items-center gap-2 no-wrap"):
                        ui.select(row_opts, value=cr.college_id,
                                  on_change=lambda e, cr=cr: (setattr(cr, "college_id", e.value), changed())
                                  ).classes("flex-1")
                        dots(lambda cr=cr: cr.rating, lambda v, cr=cr: setattr(cr, "rating", v), 0, 5)
                        ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_college(idx)
                                  ).props("flat dense round")
                ui.button("Add college", icon="add", on_click=add_college).props("flat dense")

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
                    with ui.column().classes(f"w-full gap-1 border-b border-{pal.fam}-900/10 pb-1"):
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
                    with ui.column().classes(f"w-full gap-1 border-b border-{pal.fam}-900/10 pb-1"):
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

        # virtue flaw + bonus health levels (e.g. Ox-Body Technique). The Virtue Flaw
        # half is splat-gated: the Dragon-Blooded, Sidereals and Alchemicals have none.
        with ui.row().classes("w-full gap-2 no-wrap items-start"):
            if derive.has_virtue_flaw(ruleset, character):
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

        # charms/spells (read-only here; the picker is the next slice).
        # Alchemical pays for Slots, not picks — show occupancy; every other splat
        # counts picks via the engine's canonical enumeration (Ox-Body / Beastman
        # purchases live outside character.charms, so counting by hand undercounts).
        _slots = viewmod.charm_slot_budget(ruleset, character)
        if _slots is not None:
            _charm_hdr = (f"Charm Slots {_slots.installed}/{_slots.general + _slots.dedicated} "
                          f"(G {_slots.general} · D {_slots.dedicated})")
        else:
            _charm_hdr = f"Charms ({validate.charm_pick_count(ruleset, character)})"
        with panel(f"{_charm_hdr} & Spells ({len(character.spells)}) — edit via the picker"):
            view = viewmod.build_sheet_view(ruleset, character)
            for c in view.charms:
                ui.label(f"{c.name} · {c.category}").classes("text-xs")
            for s in view.spells:
                ui.label(f"{s.name} · {s.circle}").classes("text-xs")

    # ---- structural mutators (refresh body + readout) --------------------- #
    def set_exalt_type(value: str) -> None:
        nonlocal pal
        character.exalt_type = value
        pal = theme.palette(value)          # re-theme the editor body for the new splat
        # keep the caste coherent with the new splat: if the current caste doesn't
        # belong to it, switch to that splat's first caste (if the splat has any).
        valid = [cd.id for cd in ruleset.castes.values() if cd.exalt_type == value]
        if character.caste not in valid:
            # Clearing (not keeping) is what a CASTELESS splat needs: switching a Dawn
            # Solar to Mortal must not leave "dawn" behind, or the mortal silently
            # keeps a Solar caste's Abilities discounted.
            character.caste = valid[0] if valid else ""
        # keep the origin coherent: default to the splat's first origin, or clear it
        # for splats that have no intra-splat origin variants.
        origins = _SPLAT_ORIGINS.get(value)
        character.origin = next(iter(origins)) if origins else ""
        # ...and pull Essence into the new splat's legal chargen range. A Solar sits at
        # 2, a mortal is pinned at 1 and an Illuminated Solar starts at 3, so without
        # this the sheet carries an essence-below-start / above-cap error from the
        # instant the splat is switched, for a value the player never chose.
        nb = ruleset.budgets_for(value, character.origin, character.upbringing)
        if character.essence_rating < nb.essence_start:
            character.essence_rating = nb.essence_start
        elif nb.essence_start_cap and character.essence_rating > nb.essence_start_cap:
            character.essence_rating = nb.essence_start
        # ...and drop any training camp/Calling, which belong to the OLD origin. Without
        # this, switching away from an Illuminated Solar leaves a stale camp id behind
        # and validation reports camp-not-supported.
        _reset_camp_for_origin()
        body.refresh(); changed()
        if on_theme_change is not None:     # let the embedding app re-theme its chrome
            on_theme_change()

    def set_caste(value: str) -> None:
        character.caste = value
        body.refresh(); changed()

    def set_origin(value: str) -> None:
        character.origin = value
        # Upbringing is scoped to the origin, so a stale one would silently resolve
        # against the wrong row (or, worse, a coincidentally-named one on the new
        # origin). Clear it back to the origin's default whenever the origin changes.
        character.upbringing = ""
        # Camps/Callings belong to an origin. Switching origin invalidates them, and a
        # stale camp id would trip camp-wrong-origin; default to the first camp offered
        # (and its first Calling) so the character stays legal by construction.
        _reset_camp_for_origin()
        body.refresh(); changed()

    def set_upbringing(value: str) -> None:
        character.upbringing = value
        body.refresh(); changed()

    def _reset_camp_for_origin() -> None:
        """Re-seed camp/Calling/grants for the current origin. The rule lives in the
        engine (validate.default_camp_and_calling) — this just applies it."""
        camp, calling, granted = validate.default_camp_and_calling(ruleset, character)
        character.camp, character.calling = camp, calling
        character.granted_charms = granted

    def set_camp(value: str, refresh: bool = True) -> None:
        """Pick a training camp. The camp determines both the Calling list and the free
        Charm package, so changing it clears any Calling and granted Charms that
        belonged to the old one and re-seeds the fixed grants."""
        character.camp = value
        camp = ruleset.camps.get(value)
        callings = ruleset.callings_for(value)
        if character.calling not in {c.id for c in callings}:
            character.calling = callings[0].id if callings else ""
        # Fixed grants are automatic; the player still resolves each choice.
        character.granted_charms = list(camp.granted_charms) if camp else []
        if refresh:
            body.refresh(); changed()

    def set_calling(value: str) -> None:
        character.calling = value
        body.refresh(); changed()

    def set_camp_choice(choice_index: int, key: str) -> None:
        """Resolve one granted-Charm choice. Replaces whatever was previously selected
        for THAT choice, leaving the fixed grants and the other choices alone."""
        camp = ruleset.camps.get(character.camp)
        if camp is None or choice_index >= len(camp.granted_charm_choices):
            return
        cv = viewmod.build_camp_view(ruleset, character)
        cview = cv.choices[choice_index]
        picked = next((o for o in cview.options if o.key == key), None)
        if picked is None:
            return
        if not picked.available:
            # Refuse, and say why. Previously this fell through and assigned an empty
            # list, which cleared the control and looked like the dropdown was broken.
            ui.notify(f"{picked.label} is not selectable — {picked.reason}.",
                      type="warning")
            body.refresh()          # snap the select back to the real selection
            return
        old = next((o.charm_ids for o in cview.options if o.key == cview.chosen_key), [])
        new = list(picked.charm_ids)
        choice = camp.granted_charm_choices[choice_index]
        if choice.from_categories:
            # A category choice takes `pick` Charms from the chosen style. Seed the
            # lowest-requirement ones so the default is as reachable as possible; the
            # player swaps individual Charms in the picker.
            pool = sorted((c for c in ruleset.charms.values() if c.id in new),
                          key=lambda c: (c.min_ability, c.min_essence, c.name))
            new = [c.id for c in pool[:choice.pick]]
        keep = [cid for cid in character.granted_charms if cid not in old]
        character.granted_charms = keep + [cid for cid in new if cid not in keep]
        body.refresh(); changed()

    def set_camp_choice_charms(choice_index: int, ids: list[str]) -> None:
        """Set WHICH Charms a category choice grants, within the already-chosen style.

        The style select seeds a reachable default; this is how the player changes it.
        Over-picking is refused rather than silently truncated — the package is exactly
        `pick` Charms and quietly dropping one would misreport the grant. Under-picking
        is allowed through so the control can be emptied and refilled; the engine's
        `granted-charm-missing` issue covers the incomplete state."""
        camp = ruleset.camps.get(character.camp)
        if camp is None or choice_index >= len(camp.granted_charm_choices):
            return
        cview = viewmod.build_camp_view(ruleset, character).choices[choice_index]
        allowed = {o.charm_id for o in cview.charm_options}
        chosen = [cid for cid in ids if cid in allowed]
        if len(chosen) > cview.pick:
            ui.notify(f"{cview.label} grants only {cview.pick} Charm(s) — "
                      f"deselect one first.", type="warning")
            body.refresh()          # snap the control back to the real selection
            return
        # Replace this choice's Charms, leaving the fixed grants and any other choice
        # untouched: drop everything from THIS style, then add the new selection.
        keep = [cid for cid in character.granted_charms if cid not in allowed]
        character.granted_charms = keep + chosen
        body.refresh(); changed()

    def set_favored(values: list[AbilityName]) -> None:
        character.favored_abilities = list(values)
        body.refresh(); changed()

    def set_favored_attributes(values: list[AttributeName]) -> None:
        character.favored_attributes = list(values)
        body.refresh(); changed()

    def add_bg() -> None:
        character.backgrounds.append(BackgroundEntry(name="", rating=1))
        body.refresh(); changed()

    def remove_bg(idx: int) -> None:
        del character.backgrounds[idx]
        body.refresh(); changed()

    def add_merit() -> None:
        # Default to the cheapest Merit so a fresh row is always a legal selection.
        first = min((m for m in ruleset.merits_flaws.values()),
                    key=lambda m: (m.kind != "merit", m.cost, m.name), default=None)
        if first is None:
            return
        character.merits_flaws.append(
            MeritFlawPurchase(merit_id=first.id,
                              tier=next(iter(first.cost_options), "") if first.cost_options else ""))
        body.refresh(); changed()

    def set_merit(mp: MeritFlawPurchase, merit_id: str) -> None:
        mp.merit_id = merit_id
        # The old tier belongs to the old Merit; reset it to the new one's first
        # option (or clear it) so a variable-cost row is never left on a dead tier.
        definition = ruleset.merits_flaws.get(merit_id)
        mp.tier = (next(iter(definition.cost_options), "")
                   if definition and definition.cost_options else "")
        body.refresh(); changed()

    def remove_merit(idx: int) -> None:
        del character.merits_flaws[idx]
        body.refresh(); changed()

    def add_college() -> None:
        # default to the first college of the character's own Maiden's house, so a
        # fresh row already counts toward the ≥4-own-house minimum.
        own = next((cid for cid, col in ruleset.colleges.items()
                    if col.house == character.caste), None)
        first = own or next(iter(ruleset.colleges), "")
        character.colleges.append(CollegeRating(college_id=first, rating=1))
        body.refresh(); changed()

    def remove_college(idx: int) -> None:
        del character.colleges[idx]
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
        ui.add_head_html(pal.head_style())
    with ui.row().classes("w-full max-w-7xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            if with_header:
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Chargen Editor").classes("text-xl font-bold")
                    ui.button("Save", icon="save", on_click=save).props(f"color={pal.button}")
            body()
        with ui.column().classes("w-80 gap-2 sticky top-4"):
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                ui.label("Live Validation").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                readout()
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                bp_log()


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
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
