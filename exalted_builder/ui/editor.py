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
from ..engine import advancement, costs, derive, elder, merits, validate
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
    # E:Ab p.126 and its "THE MUNDANE DEAD" sidebar: the heroic dead get 6/4/3
    # Attributes, 22 Ability dots, six Arcanoi and 21 bonus points; the mundane dead
    # 4/3/3, 16, two and 15. Everything else (Virtues, Essence 2, Fetters, the Essence
    # pool) is shared, which is why this is an origin and not two splats — the same
    # shape the mortal line above takes.
    #
    # Unlike every origin above it, "heroic" is NOT a bare default: ghosts also carry
    # an UPBRINGING, and `_keyed_row` only consults the ":origin:upbringing" key when
    # the origin is non-empty. See _ORIGIN_UPBRINGINGS.
    "Ghost": {"heroic": "Heroic Dead", "mundane": "Mundane Dead"},
    # The God-Blooded Half-Caste heritage (p.47): "learn the Charms of their parents",
    # where the parent's Exalt type IS the origin. Only the Half-Caste heritage uses it —
    # the origin select is gated on heritage_traits.charm_access_parent, so a Ghost-
    # Blooded never sees these. The values are the Exalt type strings themselves, so
    # validate.heritage_charm_access returns character.origin directly.
    # The God-Blooded have no entry HERE — their origin is HERITAGE-keyed
    # (`GodbloodedHeritage.origin_options`: the Half-Caste's five parents, the
    # Fae-Blooded's Noble/Commoner), read by `_origin_options` from the data.
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
    # E:Ab p.126: where the ghost is FROM decides the Background pool — "Ghosts from
    # areas that uphold the Immaculate Philosophy have five (5) dots to spend on
    # Backgrounds, while those from areas with active ancestor worship have eight (8)",
    # and an Immaculate-region ghost may not buy Ancestor Cult or Grave Goods above •.
    # Independent of heroic/mundane, so both origins carry it.
    "Ghost:heroic": {"": "Ancestor-worshipping region",
                     "immaculate": "Immaculate-dominated region"},
    "Ghost:mundane": {"": "Ancestor-worshipping region",
                      "immaculate": "Immaculate-dominated region"},
}


def _heritage_uses_origin(ruleset: RuleSet, character) -> bool:
    """Whether the character's heritage keys off the origin axis. Two God-Blooded
    heritages do: the Half-Caste's parent Exalt type (p.47) and the Fae-Blooded's
    Noble/Commoner (p.73-79). `GodbloodedHeritage.origin_options` is the single source
    — the editor renders the Origin dropdown from it."""
    cd = ruleset.castes.get(character.caste)
    return bool(cd is not None and cd.heritage_traits is not None
                and cd.heritage_traits.origin_options)


def _origin_options(ruleset: RuleSet, character) -> dict[str, str]:
    """The Origin dropdown options for this character: the splat's origins, EXCEPT
    the God-Blooded, whose origin is their HERITAGE's own axis — the Half-Caste's
    parent Exalt type, the Fae-Blooded's Noble/Commoner — and appears only for that
    heritage (a Ghost-Blooded never sees a meaningless Solar origin). Every other
    splat's origins are unconditional, so they render exactly as before."""
    if character.exalt_type == "God-Blooded":
        cd = ruleset.castes.get(character.caste)
        opts = cd.heritage_traits.origin_options if (
            cd is not None and cd.heritage_traits is not None) else []
        return {o: o for o in opts} if opts else {}
    return _SPLAT_ORIGINS.get(character.exalt_type, {})


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


# XP-log targets whose change moves OTHER rows' ceilings, so buying one has to rebuild
# the whole editor body rather than its own dot row. Module-level and named so the rule
# is greppable: the browser found it missing (human, 2026-07-31 — Essence clicked up to
# 6 but the Ability tracks kept five pips until the tab was left and re-entered).
#
# Essence is the only member: past 5 it IS the ceiling on every Ability and Attribute
# (engine.elder). Add a target here if a new rule makes one trait govern another's cap.
BODY_REBUILD_TARGETS = {"essence"}


def dot_track(pal, on_change=None, *, buy=None):
    """Build the clickable dot-track rating control, bound to a palette.

    Module-level and parameterised rather than a closure inside `build_editor`, because
    the Advantages tab needs the same control and copying it is how Backgrounds came to
    have two implementations in the first place. `on_change` fires after any click, for
    the caller's live readout.

    Returns `dots(get, setv, lo, hi, target=None)` — `get`/`setv` read and write the
    rating, and clicking the current top pip steps it back down.

    `buy` is decision 0013's post-lock mode: ONE track on both sides of the lock,
    pre-lock a free setter and post-lock a stepper that spends XP. It stays opt-in per
    CALL, not per control — a track only changes behaviour when the caller names a
    `target` (an `XpEntry` target like `attributes.strength`), so the Advantages tab's
    Background rows and the editor's rating controls that have no XP counterpart keep
    the free setter untouched. This control decides nothing: when both are present it
    hands the click to `buy` and does what it is told.
    """
    def dots(get, setv, lo: int, hi: int, target: str | None = None,
             detail: str = ""):
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
            new = max(lo, min(hi, i - 1 if i == cur else i))
            # Post-lock, the click is a purchase, a refund or a curse — never a write.
            # `buy` returns True when it has taken responsibility for it.
            if buy is not None and target is not None:
                if buy(target, cur, new, show.refresh, detail):
                    return
            setv(new)
            show.refresh()
            if on_change is not None:
                on_change()

        show()

    return dots


def panel_card(pal, title: str):
    """A soft-backed titled card — the editor's section container, shared with the
    Advantages tab for the same reason `dot_track` is."""
    card = ui.card().classes(f"w-full p-3 {pal.card_soft}")
    with card:
        ui.label(title).classes("text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
    return card


def build_editor(ruleset: RuleSet, character: Character, save_path: Path,
                 *, with_header: bool = True, on_theme_change=None):
    """Render the whole editor for `character`. Pure-ish wiring: every control
    mutates the Character and refreshes the live readout. With `with_header=False`
    the title/Save bar is omitted (the embedding app provides one). `on_theme_change`
    (if given) is called after the Exalt type changes so an embedding app can re-paint
    its own chrome (header bar / page background) to the new splat's palette.

    Returns the post-lock downward-click dialog opener, `(target, current, wanted,
    refresh)`, so tests can build it. Callers ignore it."""
    pal = theme.palette(character.exalt_type)

    # ---- live readout (recomputes the engine each refresh) ---------------- #
    # Plain builders, not individually refreshable: the whole sticky column is one
    # refreshable (`side_column`) because WHICH cards exist there changes at the lock.
    def readout() -> None:
        """The chargen column's card: the running bonus-point line, the derived pools
        a builder watches move, then the findings."""
        view = viewmod.build_sheet_view(ruleset, character)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        ui.label(bp).classes("text-sm font-semibold").style(f"color:{pal.accent}")
        with ui.row().classes("gap-4 text-sm"):
            ui.label(f"Willpower {view.willpower}")
            ui.label(view.essence_pool_label())
        ui.label(f"Soak  B{view.soak.bashing} / L{view.soak.lethal} / A{view.soak.aggravated}").classes("text-sm")
        ui.separator()
        _issues(view, "✓ Legal chargen")

    def _issues(view, ok_text: str) -> None:
        """Just the findings. Split out because the in-play card shows ONLY these —
        the derived pools belong to a character being built, and post-lock they live
        on the Sheet where they are not competing with a ledger for the eye."""
        errors = [i for i in view.issues if i.severity == "error"]
        status = ok_text if not errors else f"✗ {len(errors)} error(s)"
        ui.label(status).classes("text-sm font-bold").style(
            "color:#15803d" if not errors else "color:#b91c1c")
        for issue in view.issues:
            if issue.code in ("bonus-points", "xp-summary"):
                continue
            color = {"error": "text-red-600", "warning": "text-amber-600"}.get(issue.severity, "text-gray-500")
            ui.label(f"• {issue.message}").classes(f"text-xs {color}")

    # ---- bonus points (chargen) / experience (in play) --------------------- #
    # One card, two regimes — the same shape the dot tracks take. Bonus points stop
    # being a live budget at the lock (they are frozen into the ChargenSnapshot), so
    # showing a bonus-point tally beside dots that now cost XP would name the wrong
    # currency. The full ledger and Adjust XP arrive here in P3.
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

    def _do_trait(action) -> None:
        """Run a post-lock trait change that is NOT a dot click (Willpower, permanent
        Resonance), then rebuild — those controls display derived values that the
        change moves."""
        try:
            action()
        except advancement.AdvancementError as ex:
            ui.notify(str(ex), type="warning")
            return
        refresh_all()

    def _lower_willpower() -> None:
        """Willpower's half of the downward dialog. A one-field prompt rather than the
        two-branch one: there is no refund branch to offer, because Willpower has no
        dot track and so no upward click of its own to reverse — undo reaches it from
        the ledger instead."""
        with ui.dialog() as dialog, ui.card().classes(f"w-[26rem] p-4 gap-2 {pal.card_solid}"):
            ui.label("Permanent Willpower loss").classes("text-base font-bold")
            ui.label("Free, refunds no XP, logged and undoable. To take back a "
                     "PURCHASE instead, use Undo in the Experience card."
                     ).classes("text-xs text-gray-600")
            reason = ui.input(placeholder="reason (e.g. a curse)").props("dense").classes("w-full")

            def _go() -> None:
                try:
                    advancement.lower_willpower(character, reason.value.strip(), ruleset=ruleset)
                except advancement.AdvancementError as ex:
                    ui.notify(str(ex), type="warning")
                    return
                dialog.close()
                refresh_all()

            ui.button("Lower by 1", icon="trending_down", on_click=_go).props("dense outline")
        dialog.open()

    # ---- chargen choices are frozen at the lock --------------------------- #
    # Making Edit a both-sides tab (decision 0013) exposed every free setter on it to a
    # locked character, and some of them are not traits to be bought — they are the
    # chargen choices the whole point accounting is measured against. Re-picking
    # Favoured Abilities in play would silently re-rate every future purchase; changing
    # caste, Exalt type or origin would swap the budget row the snapshot was written
    # from. Decision 0004 already says chargen is a snapshot; this is that made visible.
    #
    # Applied per control rather than by hiding the panel, so the values stay READABLE
    # in play — which is what they are for.
    def _frozen(el):
        """Disable `el` once chargen is locked; pass it through untouched before."""
        if character.chargen_locked:
            el.props("disable")
        return el

    # ---- the sticky column, in play (decision 0013 / P3) ------------------ #
    # Post-lock the column is: what you can spend, what you spent it on, and only then
    # anything wrong. Pre-lock it is validation first, because a half-built character
    # is mostly a list of things not yet done.
    _adjust = {"amount": 5}

    def _do_undo() -> None:
        try:
            advancement.undo_last(ruleset, character)
        except advancement.AdvancementError as ex:
            ui.notify(str(ex), type="warning")
            return
        refresh_all()

    _downtime = {"years": 10}

    def _downtime_dialog() -> None:
        """The p.259 downtime calculator: years of skipped time → the experience it
        awards and the 4:3:2:1 split it must be spent across.

        A CALCULATOR that grants, never an enforcement — the split prints as advice and
        nothing downstream polices it (see engine.elder). Post-lock only, because it
        sits with the other XP controls and `Character.age` is post-lock only.

        Granting also ADVANCES THE AGE by the same years. The two are the same downtime,
        and letting them drift would let a player collect a century of maturation
        experience without ever reaching the century that raises their Essence ceiling.

        This is ALSO the only place age is set (2026-08-01). It was a second box in the
        Identity panel until the grant existed, and then it was a way to reach the same
        state by two routes that disagreed. Setting it here is still needed and is not
        the same gesture as granting: a character who was ALREADY ancient when play
        began did not earn that maturation experience at this table, so age is written
        immediately and the award is a separate, deliberate press.
        """
        with ui.dialog() as dialog, ui.card().classes("w-[28rem] gap-2"):
            ui.label("Downtime").classes("text-lg font-bold")
            ui.label("Annual experience for skipped years (Player's Guide p.259). The "
                     "award depends on the character's age, so a downtime that crosses "
                     "100, 250, 500 or 1,000 years changes rate partway."
                     ).classes("text-xs text-gray-600")

            @ui.refreshable
            def preview() -> None:
                award = elder.downtime_award(character.age, _downtime["years"])
                ui.label(f"Age {award.from_age} → {award.to_age}").classes(
                    "text-sm font-semibold")
                # The ceilings age has unlocked. This readout used to be a tooltip on
                # the Identity age box; it follows the control that replaced it, or the
                # one number that governs every track on the sheet would be settable
                # with nothing on screen saying what it did.
                caps = elder.elder_caps(ruleset, character)
                if caps.is_elder:
                    ui.label(f"Now: Essence up to {caps.essence}, Abilities and "
                             f"Attributes up to {caps.trait}."
                             ).classes("text-xs opacity-70")
                if caps.terrestrial_limited:
                    ui.label("Held at the Terrestrial ceiling of 7 — age alone would "
                             "allow more (ST Options can lift it).").classes(
                        "text-xs text-amber-700")
                unlocked = elder.essence_cap_for_age(award.to_age)
                if unlocked > caps.essence and not caps.terrestrial_limited:
                    ui.label(f"This downtime reaches Essence {unlocked}."
                             ).classes("text-xs font-semibold").style(
                        f"color:{pal.accent}")
                for band in award.bands:
                    span = (f"{band.from_age}" if band.years == 1
                            else f"{band.from_age}–{band.to_age}")
                    ui.label(f"age {span}: {band.years} yr × {band.rate} = "
                             f"{band.experience} XP").classes("text-xs font-mono opacity-70")
                ui.separator()
                ui.label(f"{award.total} XP").classes("text-xl font-bold").style(
                    f"color:{pal.accent}")
                if not award.total and _downtime["years"]:
                    # The chart starts at 100 years and the build never invents the rows
                    # below it. Say so, or a zero reads as a bug.
                    ui.label("The p.259 chart begins at 100 years of Exaltation — a "
                             "younger character earns no maturation experience from it. "
                             "Ordinary play awards are the Storyteller's."
                             ).classes("text-xs text-amber-700")
                for label, points in award.split:
                    with ui.row().classes("w-full justify-between no-wrap items-baseline"):
                        ui.label(label).classes("text-xs")
                        ui.label(str(points)).classes("text-xs font-semibold")
                ui.label("The split is what p.259 requires the experience be spent on. "
                         "It is printed as guidance — nothing here enforces it."
                         ).classes("text-xs italic opacity-60")

            def _set_years(value) -> None:
                _downtime["years"] = max(0, int(value or 0))
                preview.refresh()

            def _set_age(value) -> None:
                character.age = max(0, int(value or 0))
                preview.refresh()

            with ui.row().classes("w-full gap-2 no-wrap"):
                # Years of EXALTED existence, counted from the Exaltation — the elder
                # rules' only input (PG pp.258-259).
                age_field = ui.number("Exalted years so far", value=character.age, min=0,
                                      format="%d", on_change=lambda e: _set_age(e.value)
                                      ).props("dense").classes("flex-1")
                # The dot tracks' ceilings are built from age, so the body has to be
                # rebuilt when it moves — but on BLUR, not per keystroke: refreshing
                # mid-type would tear the field out from under someone typing "1000"
                # one digit at a time.
                age_field.on("blur", lambda _: refresh_all())
                ui.number("Years of downtime", value=_downtime["years"], min=0,
                          format="%d", on_change=lambda e: _set_years(e.value)
                          ).props("dense").classes("flex-1")
            preview()

            def _grant() -> None:
                award = elder.downtime_award(character.age, _downtime["years"])
                character.age = award.to_age
                advancement.add_xp(character, award.total)
                dialog.close()
                ui.notify(f"Granted {award.total} XP — age is now {award.to_age}.",
                          type="positive")
                refresh_all()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat dense")
                ui.button("Grant", icon="check", on_click=_grant
                          ).props(f"dense color={pal.button}")
        dialog.open()

    def xp_controls() -> None:
        """Adjust XP, and the one control the read-only log would otherwise strand.

        Traits are un-bought by clicking their dots down (the P1 dialog), but a Charm,
        Combo, spell, specialty or thaumaturgy purchase has no downward gesture of its
        own — the ledger's per-row undo button was the only way to reverse one. Keeping
        the log a printout means that button has to live here instead, and naming the
        row it will reverse is what stops "Undo" being a guess.
        """
        ui.label("Experience").classes("text-sm font-bold tracking-widest").style(
            f"color:{pal.accent}")
        with ui.row().classes("w-full items-center gap-1 no-wrap"):
            amount = ui.number(value=_adjust["amount"], format="%d").props("dense").classes("w-20")
            ui.button("Adjust XP", icon="add", on_click=lambda: (
                _adjust.__setitem__("amount", int(amount.value or 0)),
                advancement.add_xp(character, int(amount.value or 0)),
                changed())).props(f"dense color={pal.button}")
        ui.button("Downtime…", icon="hourglass_bottom", on_click=_downtime_dialog
                  ).props("dense flat size=sm").classes("w-full")
        rows = viewmod.build_xp_log(ruleset, character)
        if rows:
            ui.button(f"Undo last: {rows[-1].label}", icon="undo", on_click=_do_undo
                      ).props("dense flat size=sm color=negative").classes("w-full")
        # Chargen Charm picks banked by a Flaw (Weak Essence, p.41). Beside the XP
        # accounting rather than only on the Charms tab, because it is experience the
        # player does NOT have to spend — a number that belongs with the budget.
        granted, remaining = validate.withheld_charm_credits(ruleset, character)
        if granted:
            ui.label(f"{remaining} of {granted} withheld Charm(s) in reserve — the next "
                     f"{remaining or 'no'} cost no XP.").classes(
                "text-xs font-semibold").style(f"color:{pal.accent}")

    def xp_log_card() -> None:
        spent = advancement.xp_spent(character)
        available = advancement.xp_available(character)
        with ui.row().classes("w-full items-baseline gap-2"):
            ui.label(str(available)).classes("text-2xl font-bold").style(
                f"color:{'#15803d' if available >= 0 else '#b91c1c'}")
            ui.label("XP available").classes("text-xs text-gray-600")
        ui.label(f"earned {character.xp_earned} · spent {spent}").classes(
            "text-xs text-gray-600")
        ui.separator()
        rows = viewmod.build_xp_log(ruleset, character)
        if not rows:
            ui.label("No XP spent yet.").classes("text-xs text-gray-400")
        for r in rows:
            with ui.row().classes("w-full items-center justify-between no-wrap gap-1"):
                ui.label(r.label).classes("text-xs")
                ui.label(f"{r.cost} XP").classes("text-xs text-gray-600")

    @ui.refreshable
    def side_column() -> None:
        if character.chargen_locked:
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                xp_controls()
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                xp_log_card()
            # Validation is DEMOTED post-lock, not deleted. A clean character shows no
            # card at all — but a curse that drops an Ability below a known Charm's
            # requirement is a real post-lock finding (`charm-min-ability`), and the
            # downward dialog is what makes it easy to cause. Hiding it outright would
            # blind the player exactly where the new gesture can hurt them.
            view = viewmod.build_sheet_view(ruleset, character)
            if any(i.code != "xp-summary" for i in view.issues):
                with ui.card().classes(f"w-full p-3 {pal.card}"):
                    ui.label("Validation").classes(
                        "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                    _issues(view, "✓ Legal")
            return
        with ui.card().classes(f"w-full p-3 {pal.card}"):
            ui.label("Live Validation").classes(
                "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
            readout()
        with ui.card().classes(f"w-full p-3 {pal.card}"):
            bp_log()

    # ---- live tally of ability dots spent (updates on every dot click) ----- #
    @ui.refreshable
    def ability_tally() -> None:
        # effective_budgets, not budgets_for: a trait-forfeit Flaw (Unskilled, Callous)
        # sells free dots for bonus points, and the tally must count against what the
        # engine actually charges or the sheet contradicts its own validation.
        b = validate.effective_budgets(ruleset, character)
        # Only dots WITHIN the pre-bonus cap draw on the free pool. A dot above it is
        # bought with bonus points and never consumes one of the 25 (human's ruling,
        # 2026-07-31), which is exactly how the engine already prices them — see the
        # `within_by_tier` / `above_by_tier` split in validate.bonus_point_breakdown.
        # Summing raw ratings here made a character with one Ability at 4 read 25/25
        # while the engine still had a free dot unspent.
        cap = b.ability_cap_pre_bp
        spent = (sum(min(v, cap) for a, v in character.abilities.items()
                     if a != AbilityName.CRAFT)
                 + sum(min(cr.rating, cap) for cr in character.crafts))
        over = spent > b.ability_dots
        ui.label(f"{spent} / {b.ability_dots} dots spent").classes(
            "text-xs font-semibold").style(
            f"color:{'#b91c1c' if over else pal.accent}")

    def changed() -> None:
        side_column.refresh()
        ability_tally.refresh()

    def refresh_all() -> None:
        """A change that can move any trait on the page — undo is the only one, since
        it reverses a purchase the player made somewhere else entirely and the dot
        tracks have no idea which."""
        body.refresh()
        changed()

    # ---- post-lock buying (decision 0013) --------------------------------- #
    # The dot tracks are the trait surface on BOTH sides of the lock. Pre-lock they
    # are free setters against the chargen budget; post-lock a click is an XP
    # transaction and every one of them goes through engine.advancement. Nothing here
    # prices or gates anything — `raise_to`, `refund_to` and `lower_to` do, and each
    # validates the whole click before committing any of it.
    def _refresh_after(target: str, refresh) -> None:
        """Redraw what the change actually moved.

        A dot click normally only has to redraw its own row, and `refresh` is that
        row's. ESSENCE is the exception: it is the ceiling on every Ability and
        Attribute track once it passes 5 (engine.elder), so the pips those rows were
        built with are stale the moment it moves — the whole body has to rebuild.

        One or the other, never both: rebuilding the body replaces the very row
        `refresh` belongs to, and calling a refresher for a discarded element is how
        this control gets its "nothing happened" bugs.
        """
        if target in BODY_REBUILD_TARGETS:
            body.refresh()
        else:
            refresh()

    def _buy(target: str, current: int, wanted: int, refresh, detail: str = "") -> bool:
        """Handle a post-lock dot click. Returns False pre-lock, so the track falls
        through to its ordinary free-setter behaviour."""
        if not character.chargen_locked:
            return False
        if wanted > current:
            try:
                advancement.raise_to(ruleset, character, target, wanted, detail)
            except advancement.AdvancementError as ex:
                ui.notify(str(ex), type="warning")
            else:
                _refresh_after(target, refresh)
                changed()
            return True
        if wanted < current:
            _downward_dialog(target, current, wanted, refresh, detail)
        return True

    def _downward_dialog(target: str, current: int, wanted: int, refresh,
                         detail: str = "") -> None:
        """Ask which downward event this is. The application genuinely cannot infer
        it: taking XP back and suffering a curse both move the same dots, and they
        differ in price, in what they log and in how far down they may go.

        Refund is capped by `refundable_depth` — undo is LIFO across the WHOLE log,
        so a raise buried under a later purchase is not refundable here and the branch
        says so rather than silently unwinding the purchase on top of it.
        """
        dots_down = current - wanted
        depth = advancement.refundable_depth(character, target, detail)
        can_refund = depth >= dots_down
        # A curse reaches chargen dots, so its only limit is the trait's own floor —
        # asked of the engine by trying it on a throwaway copy rather than restated.
        try:
            advancement.lower_to(character.model_copy(deep=True), target, wanted,
                                 "probe", detail)
            can_reduce = True
        except advancement.AdvancementError:
            can_reduce = False
        if not can_refund and not can_reduce:
            ui.notify("Nothing to take back here — no recent purchase of this trait, "
                      "and it is already at its minimum.", type="info")
            return

        refund_xp = sum(e.cost for e in character.xp_log[len(character.xp_log) - dots_down:]) \
            if can_refund else 0
        noun = "dot" if dots_down == 1 else "dots"
        with ui.dialog() as dialog, ui.card().classes(f"w-[28rem] p-4 gap-2 {pal.card_solid}"):
            ui.label(f"Lower by {dots_down} {noun}").classes("text-base font-bold")
            ui.label("Taking experience back and suffering a permanent loss are "
                     "different events. Which is this?").classes("text-xs text-gray-600")

            def _do(action) -> None:
                try:
                    action()
                except advancement.AdvancementError as ex:
                    ui.notify(str(ex), type="warning")
                    return
                dialog.close()
                # Essence coming back DOWN lowers the same ceilings — a body rebuild
                # for the same reason as the raise. See _refresh_after.
                _refresh_after(target, refresh)
                changed()

            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                btn = ui.button(f"Undo purchase — refund {refund_xp} XP",
                                icon="undo",
                                on_click=lambda: _do(lambda: advancement.refund_to(
                                    ruleset, character, target, wanted, detail))
                                ).props(f"dense color={pal.button}").classes("flex-1")
                if not can_refund:
                    btn.props("disable")
            if not can_refund:
                ui.label(f"Only {depth} recent purchase(s) of this trait can be refunded — "
                         f"undo is last-in-first-out, so anything bought since must go "
                         f"first.").classes("text-xs italic text-gray-500")

            ui.separator()
            reason = ui.input(placeholder="reason (e.g. a curse, a Charm's permanent cost)"
                              ).props("dense").classes("w-full")
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                red = ui.button("Permanent loss — free, refunds no XP",
                                icon="trending_down",
                                on_click=lambda: _do(lambda: advancement.lower_to(
                                    character, target, wanted, reason.value.strip(), detail))
                                ).props("dense outline").classes("flex-1")
                if not can_reduce:
                    red.props("disable")
            ui.label("A permanent loss is logged and undoable, reaches chargen dots, "
                     "and gives back no experience.").classes("text-xs text-gray-500")
        dialog.open()

    # ---- shared controls (module-level; the Advantages tab uses the same) --- #
    dots = dot_track(pal, changed, buy=_buy)

    def panel(title: str):
        return panel_card(pal, title)

    # ---- the editor body (refreshes on structural changes) ---------------- #
    @ui.refreshable
    def body() -> None:
        # Which side of the lock this render is on. Read once per body build, not per
        # widget, so a single character cannot produce a half-chargen, half-XP page.
        locked = character.chargen_locked
        caste_def = ruleset.castes.get(character.caste)
        caste_abilities = set(caste_def.caste_abilities) if caste_def else set()
        caste_attributes = set(caste_def.caste_attributes) if caste_def else set()
        # Alchemical allocates Attributes to Caste/Favored/remaining SETS, not to
        # prioritised categories, and its Favored slot is Attributes, not Abilities.
        cf_attr_mode = viewmod.uses_caste_favored_attributes(ruleset, character)
        favored_attrs = set(character.favored_attributes)
        # chargen budget for THIS character (splat + origin), so panel headers show
        # the right numbers (Solar 8/6/4·25; DB Dynastic 7/6/4·35, Outcaste ·25).
        b = validate.effective_budgets(ruleset, character)
        # Trait ceilings a Merit or Flaw has moved, read once for the dot rows below.
        mf_effects = merits.merits_and_flaws_calc(ruleset, character)

        # Ceilings age has moved (Player's Guide pp.258-259), read once alongside the
        # Merit ones. Both are 5/5 for every character under 100 years of Exalted
        # existence, which is every character pre-lock — `Character.age` cannot be set
        # until then — so this changes nothing for an ordinary sheet.
        e_caps = elder.elder_caps(ruleset, character)

        def _attr_cap(a) -> int:
            return max(mf_effects.attribute_caps.get(a.value, merits.DOT_MAX),
                       e_caps.trait)

        virtue_cap = (mf_effects.virtue_cap if mf_effects.virtue_cap is not None
                      else merits.DOT_MAX)
        ap = "/".join(str(p) for p in validate.effective_attribute_pools(ruleset, character))
        # Attribute pools are matched to categories by SPEND, so a Diminished
        # Attributes forfeit cannot be folded into the printed 8/6/4 the way the
        # Ability and Virtue budgets can — name the shortfall alongside it instead.
        forfeited = merits.merits_and_flaws_calc(ruleset, character).forfeited_attribute_dots
        if forfeited:
            ap += " " + ", ".join(f"−{n} {cat}" for cat, n in sorted(forfeited.items()))
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
                    if locked:
                        ui.label("Caste, Exalt type, origin and Favoured picks are fixed "
                                 "at the lock — they set the rates every later purchase "
                                 "is priced at.").classes("text-xs italic text-gray-500")
                    with ui.row().classes("w-full gap-3 no-wrap"):
                        ui.input("Name", value=character.name,
                                 on_change=lambda e: (setattr(character, "name", e.value), changed())).classes("flex-1")
                        ui.input("Concept", value=character.concept,
                                 on_change=lambda e: setattr(character, "concept", e.value)).classes("flex-1")
                        # Exalted years used to be a box here. It moved into the
                        # Downtime dialog (2026-08-01, human's call): age and the
                        # maturation experience of PG p.259 are the same passage of
                        # time, and two controls for it invited them to drift — a
                        # player could age a century in Identity and collect the
                        # century's experience again from Downtime. One control now
                        # does both, and it is post-lock like the age itself.
                    # Wraps (no `no-wrap`) so the identity controls flow onto a second
                    # line rather than squashing to truncated labels ("C…"); each gets
                    # a min width so its label always shows in full.
                    _field = "flex-1 min-w-[10rem]"
                    with ui.row().classes("w-full gap-3 items-end"):
                        exalt_opts = {ex.id: ex.label for ex in ruleset.exalts.values()}
                        exalt_opts.setdefault(character.exalt_type, character.exalt_type)
                        _frozen(ui.select(exalt_opts, label="Exalt type", value=character.exalt_type,
                                  on_change=lambda e: set_exalt_type(e.value)).classes(_field))
                        caste_opts = {cd.id: cd.label for cd in ruleset.castes.values()
                                      if cd.exalt_type == character.exalt_type}
                        # A splat with NO castes at all doesn't get the control: mortals
                        # "select Nature as normal but do not select a caste" (core p.103).
                        # Distinct from Lunar, who HAS castes that carry no caste-abilities.
                        if caste_opts:
                            # keep the current caste selectable even if off-splat (NiceGUI 3.x
                            # ui.select raises if value ∉ options — see the select-value gotcha)
                            caste_opts.setdefault(character.caste, character.caste)
                            _frozen(ui.select(caste_opts, label=caste_noun, value=character.caste,
                                      on_change=lambda e: set_caste(e.value)).classes(_field))
                        origins = _origin_options(ruleset, character)
                        if origins:
                            # keep a STALE origin selectable (NiceGUI 3.x ui.select raises
                            # if value ∉ options — the same fold-in the caste select does a
                            # few lines up), so a Fae-Blooded saved with another heritage's
                            # "Solar" parent renders and is reported by
                            # heritage-foreign-origin instead of taking the editor down.
                            if (character.origin
                                    and character.origin not in origins):
                                origins = {**origins, character.origin: character.origin}
                            _frozen(ui.select(origins, label="Origin",
                                      value=character.origin or next(iter(origins)),
                                      on_change=lambda e: set_origin(e.value)).classes(_field))
                            # Second axis, and only for the origins that have one — see
                            # _ORIGIN_UPBRINGINGS. Everything else renders exactly as before.
                            ups = upbringing_options(
                                character.exalt_type, character.origin or next(iter(origins)))
                            if ups:
                                _frozen(ui.select(ups, label="Upbringing",
                                          value=character.upbringing if character.upbringing in ups
                                          else next(iter(ups)),
                                          on_change=lambda e: set_upbringing(e.value)).classes(_field))
                        nature_names = [n.name for n in ruleset.nature_catalog.values()]
                        # Frozen with the other chargen choices (human, rules authority,
                        # 2026-07-31). It has no XP effect, but it IS True Paragon's
                        # prerequisite, and a Nature changed in play would invalidate a
                        # held Merit after the fact.
                        _frozen(ui.select(_opts_with(nature_names, character.nature), label="Nature",
                                  value=character.nature or None,
                                  with_input=True, new_value_mode="add-unique",
                                  on_change=lambda e: (setattr(character, "nature", e.value or ""),
                                                       changed())).classes(_field))
                        ui.input("Anima", value=character.anima,
                                 on_change=lambda e: setattr(character, "anima", e.value)).classes(_field)
                    # Favored ABILITIES (most splats) or Favored ATTRIBUTES (Alchemical,
                    # p.60) — a splat has one or the other. `favored_count` is 0 for a
                    # caste_favored splat, so the abilities picker hides itself there.
                    # Asked of the engine rather than the budget row because a heroic
                    # mortal's single Favoured Ability is an ST toggle, not a budget.
                    fav_n = validate.favored_ability_count(ruleset, character)
                    if fav_n:
                        _frozen(ui.select({a: _label(a.value) for a in AbilityName},
                                  label=f"Favored abilities (pick {fav_n})",
                                  value=list(character.favored_abilities), multiple=True,
                                  on_change=lambda e: set_favored(e.value)).classes("w-full").props("use-chips"))
                    if cf_attr_mode:
                        _frozen(ui.select({a: _label(a.value) for a in AttributeName},
                                  label=f"Favored Attributes (pick {b.attribute_favored_count})",
                                  value=list(character.favored_attributes), multiple=True,
                                  on_change=lambda e: set_favored_attributes(e.value)).classes("w-full").props("use-chips"))

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
                        _frozen(ui.select({cid: label for cid, label in camp_view.camp_options},
                                  label="Training camp", value=camp_view.camp_id or None,
                                  on_change=lambda e: set_camp(e.value)).classes("w-full"))
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
                            _frozen(ui.select(opts, label=choice.label + suffix,
                                      value=choice.chosen_key or None,
                                      on_change=lambda e, i=idx: set_camp_choice(i, e.value)
                                      ).classes("w-full"))
                            # Picking the style is only half the choice — the package is
                            # "two Charms from ONE of four martial arts" (p.90), so the
                            # player chooses WHICH. Multi-select, capped at `pick`.
                            if choice.charm_options:
                                copts = {o.charm_id: (o.label if o.meets_minimums
                                                      else f"{o.label} — {o.reason}")
                                         for o in choice.charm_options}
                                _frozen(ui.select(copts, multiple=True,
                                          label=f"Which {choice.pick}?",
                                          value=list(choice.chosen_charm_ids),
                                          on_change=lambda e, i=idx: set_camp_choice_charms(
                                              i, list(e.value or []))
                                          ).props("use-chips").classes("w-full"))
                    # right: the Calling and what it discounts
                    with ui.column().classes("flex-1 gap-1 min-w-0"):
                        if camp_view.calling_options:
                            _frozen(ui.select({cid: label for cid, label in camp_view.calling_options},
                                      label="Calling", value=camp_view.calling_id or None,
                                      on_change=lambda e: set_calling(e.value)).classes("w-full"))
                            if camp_view.calling_description:
                                ui.label(camp_view.calling_description).classes("text-xs")
                            if camp_view.calling_abilities:
                                ui.label("✧ Calling Abilities: " + ", ".join(
                                    camp_view.calling_abilities)).classes("text-xs italic")
                            if camp_view.calling_charms:
                                ui.label(f"✧ {len(camp_view.calling_charms)} Calling Charms — "
                                         f"discounted at chargen and in play").classes("text-xs italic")

        # attributes
        # Post-lock the chargen pools are frozen history — the budget that governs a
        # click is experience, and a header still counting 8/6/4 would contradict the
        # dots beside it. Same for the Ability and Virtue panels below.
        attr_header = viewmod.attribute_budget_summary(ruleset, character) or f"prioritise {ap}"
        with panel("Attributes" if locked else f"Attributes ({attr_header})"):
            with ui.row().classes("w-full gap-2 no-wrap"):
                for category, members in validate.ATTRIBUTE_CATEGORIES.items():
                    with ui.column().classes("flex-1 gap-1"):
                        spent_label = ui.label().classes("text-xs font-semibold")

                        def show_spent(label=spent_label, members=members, category=category):
                            # Every Attribute starts at one free dot — UNLESS a Flaw
                            # caps it below that (Disfigured can put Appearance at 0),
                            # in which case there is no free dot to discount and the
                            # baseline is the cap. Subtracting a flat 1 made a legal
                            # Social row read "−1 spent".
                            spent = sum(character.attributes[a] - min(1, _attr_cap(a))
                                        for a in members)
                            label.set_text(f"{category} — {spent} spent")

                        if not locked:
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
                                # The dot row's ceiling is the trait's, not a flat 5:
                                # Legendary Attribute raises one Attribute and
                                # Disfigured lowers Appearance, and a cap the player
                                # cannot click to is a cap they cannot use.
                                dots(lambda a=a: character.attributes[a],
                                     lambda v, a=a, upd=show_spent: (
                                         character.attributes.__setitem__(a, v), upd()),
                                     min(1, _attr_cap(a)), _attr_cap(a),
                                     target=f"attributes.{a.value}")

        # abilities (by ability-caste group)
        with panel("Abilities" if locked else
                   f"Abilities ({b.ability_dots} dots; ≥{b.ability_min_caste_favored} caste/favoured; ≤{b.ability_cap_pre_bp} each pre-bonus)"):
            if not locked:
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
                                         lambda v, a=a: character.abilities.__setitem__(a, v),
                                         0, e_caps.trait,
                                         target=f"abilities.{a.value}")

        # crafts — each focus is its own rated Ability (core p.136)
        craft_cf = AbilityName.CRAFT in caste_abilities or AbilityName.CRAFT in character.favored_abilities
        cf_tag = " · Caste/Favoured" if craft_cf else ""
        with panel(f"Crafts (each focus a separate Ability{cf_tag})"):
            for idx, cr in enumerate(character.crafts):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.input(value=cr.focus, placeholder="craft (e.g. Smithing)",
                             on_change=lambda e, cr=cr: (setattr(cr, "focus", e.value), changed())).classes("flex-1")
                    dots(lambda cr=cr: cr.rating, lambda v, cr=cr: setattr(cr, "rating", v),
                         0, e_caps.trait, target="crafts", detail=cr.focus)
                    ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_craft(idx)).props("flat dense round")
            ui.button("Add craft", icon="add", on_click=add_craft).props("flat dense")

        # virtues + essence + willpower
        with ui.row().classes("w-full gap-2 no-wrap items-start"):
            with panel("Virtues" if locked else
                       f"Virtues ({b.virtue_dots} dots; ≤{b.virtue_cap_pre_bp} pre-bonus)").classes("flex-1"):
                for v in VirtueName:
                    with ui.row().classes("w-full items-center gap-2 no-wrap"):
                        ui.label(_label(v.value)).classes("text-sm w-28")
                        dots(lambda v=v: character.virtues[v],
                             lambda val, v=v: character.virtues.__setitem__(v, val),
                             1, virtue_cap, target=f"virtues.{v.value}")
            with panel("Essence & Willpower").classes("flex-1"):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.label("Essence").classes("text-sm w-28")
                    # The dot row runs to whatever AGE permits (p.259's chart), not a
                    # flat 5 — the same reasoning as the Attribute rows above: a
                    # ceiling the player cannot click to is a ceiling they cannot use.
                    # Pre-lock this is always 5, because age cannot be set until lock.
                    dots(lambda: character.essence_rating,
                         lambda v: setattr(character, "essence_rating", v),
                         1, e_caps.essence, target="essence")
                if locked:
                    # Willpower is the one reducible trait that is NOT a dot track and
                    # cannot become one: decision 0005 pins its Virtue component at the
                    # lock, so only `willpower_purchased` moves and a pip row would
                    # misrepresent the total. Decision 0013 keeps it an explicit pair.
                    wp = derive.willpower(character, ruleset)
                    with ui.row().classes("w-full items-center gap-2 no-wrap"):
                        ui.label(f"Willpower {wp}").classes("text-sm w-28")
                        ui.button(f"+1 · {costs.willpower_step(ruleset, character, wp)} XP",
                                  on_click=lambda: _do_trait(
                                      lambda: advancement.raise_willpower(ruleset, character))
                                  ).props(f"dense color={pal.button}")
                        ui.button(icon="arrow_downward",
                                  on_click=lambda: _lower_willpower()
                                  ).props("dense flat round color=negative").tooltip(
                            "Permanent loss (a curse) — free, refunds no XP")
                else:
                    ui.number("Willpower purchased", value=character.willpower_purchased, min=0, max=10, format="%d",
                              on_change=lambda e: (setattr(character, "willpower_purchased", int(e.value or 0)), changed())).classes("w-full")

        # Backgrounds and Merits & Flaws are NOT here — they live on the Advantages
        # tab (`ui/advantages.py`), which is on the bar on both sides of the lock. They
        # are one list edited under two budget regimes rather than a baseline that XP
        # spends against, and filing them under the Edit⇄XP split is what made each of
        # them exist twice. Do not move them back.

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
                        dots(lambda cr=cr: cr.rating, lambda v, cr=cr: setattr(cr, "rating", v), 0, 5,
                             target="colleges", detail=cr.college_id)
                        ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_college(idx)
                                  ).props("flat dense round")
                ui.button("Add college", icon="add", on_click=add_college).props("flat dense")

        # specialties
        # A specialty is an INSTANCE, not a rated trait (human, rules authority,
        # 2026-07-31): "you don't raise specialties, you just take the same one
        # multiple times, and you can only have 3 specialties per ability". So there is
        # no dot track here at all — taking Swords twice means two rows — and the cap
        # counts rows per Ability, which the header shows live.
        with panel("Specialties (max 3 per Ability; take one twice to stack it)"):
            # Post-lock a specialty is a PURCHASE, so it is named and priced up front
            # rather than appended blank and edited in place — an empty row would
            # already have cost XP. Existing rows go read-only for the same reason the
            # Charms tab's do: removal in play is undo, not deletion.
            for idx, sp in enumerate(character.specialties):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    if locked:
                        ui.label(f"{_label(sp.ability.value)} — {sp.name}").classes("text-sm flex-1")
                        continue
                    ui.select({a: _label(a.value) for a in AbilityName}, value=sp.ability,
                              on_change=lambda e, sp=sp: setattr(sp, "ability", e.value)).classes("flex-1")
                    ui.input(value=sp.name, placeholder="Specialty",
                             on_change=lambda e, sp=sp: setattr(sp, "name", e.value)).classes("flex-1")
                    ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_spec(idx)).props("flat dense round")
            if locked:
                _spec = {"ability": AbilityName.MELEE, "name": ""}
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.select({a: _label(a.value) for a in AbilityName},
                              value=_spec["ability"], label="Specialty in",
                              on_change=lambda e: _spec.__setitem__("ability", e.value)
                              ).props("dense").classes("w-40")
                    name_in = ui.input(placeholder="specialty name").props("dense").classes("flex-1")
                    ui.label(f"{costs.specialty_cost(ruleset, character)} XP").classes(
                        "text-xs w-12")
                    ui.button("Buy", icon="add", on_click=lambda: _do_trait(
                        lambda: advancement.add_specialty(
                            ruleset, character, _spec["ability"], name_in.value.strip()))
                        ).props(f"dense color={pal.button}")
            else:
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

        # Permanent Resonance / Limit (Death's Taint, PG p.41). Its own panel rather
        # than a dot track, because it moves in BOTH directions at DIFFERENT prices:
        # gaining is inflicted and free, shedding costs XP and a Harrowing. Locked-only
        # — it is a play-time trait — and shown only for a character who has the track
        # at all, which is asked of the engine so no Merit id is named here.
        perm_cap = derive.permanent_limit_cap(ruleset, character) if locked else 0
        if perm_cap:
            lim = derive.limit_label(ruleset, character)
            with panel(f"Permanent {lim}"):
                ui.label(f"{character.limit_permanent} of {perm_cap} (capped at Essence). "
                         f"Gained when the temporary track overflows; shed with a "
                         f"Harrowing.").classes("text-xs text-gray-600")
                _res = {"reason": ""}
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.input(placeholder="reason (e.g. Resonance overflowed)",
                             on_change=lambda e: _res.__setitem__("reason", e.value)
                             ).props("dense").classes("flex-1")
                    ui.button("Gain (free)", icon="arrow_upward",
                              on_click=lambda: _do_trait(
                                  lambda: advancement.gain_permanent_resonance(
                                      ruleset, character, _res["reason"].strip()))
                              ).props("dense color=negative")
                    ui.button(f"Shed ({merits.PERMANENT_RESONANCE_SHED_XP} XP)",
                              icon="arrow_downward",
                              on_click=lambda: _do_trait(
                                  lambda: advancement.shed_permanent_resonance(
                                      ruleset, character, _res["reason"].strip()))
                              ).props("dense")

        # virtue flaw + bonus health levels (e.g. Ox-Body Technique). The Virtue Flaw
        # half is splat-gated: the Dragon-Blooded, Sidereals and Alchemicals have none.
        with ui.row().classes("w-full gap-2 no-wrap items-start"):
            if derive.has_virtue_flaw(ruleset, character):
                with panel("Virtue Flaw").classes("flex-1"):
                    vf = character.virtue_flaw
                    _frozen(ui.select({v: _label(v.value) for v in VirtueName}, label="Flawed Virtue",
                              value=vf.virtue if vf else None,
                              on_change=lambda e: set_virtue_flaw_virtue(e.value)).classes("w-full"))
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
        # for splats that have no intra-splat origin variants. For the God-Blooded this
        # is HERITAGE-aware (`_origin_options` reads `heritage_traits.origin_options`):
        # switching to a Fae-Blooded must default to Noble, not the Solar parent that
        # `_SPLAT_ORIGINS` would hand a Ghost-Blooded.
        origins = _origin_options(ruleset, character)
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
        # The heritage determines the origin axis (`_origin_options` reads
        # `heritage_traits.origin_options`), so switching heritage can strand the OLD
        # heritage's origin — a Fae-Blooded's "Solar" parent, a Half-Caste's "Noble".
        # Re-seed it the same way set_exalt_type does, or ui.select raises ValueError
        # on a value that is not among the new heritage's options and the editor dies.
        # Changing the origin is what set_origin does, so when it actually changes,
        # finish the job the way set_origin does: clear the upbringing (scoped to the
        # origin) and re-seed camp/Calling (they belong to the origin) — a stale one
        # would resolve against the wrong row. Latent today (no splat has both castes
        # and an intra-splat origin that set_caste re-seeds) but a trap for the next
        # splat that does.
        origins = _origin_options(ruleset, character)
        if character.origin not in origins:
            character.origin = next(iter(origins)) if origins else ""
            character.upbringing = ""
            _reset_camp_for_origin()
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
        """A blank chargen row. The per-Ability cap is not enforced here — the row
        starts on Melee and the player retargets it, so blocking the ADD would block
        it on the wrong Ability. `validate.check_specialties` reports an over-capped
        Ability instead, which is also what covers a save that arrives over the cap."""
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
            side_column()

    # Returned so a test can open the post-lock downward dialog without simulating a
    # tap on a specific pip — the same trick `build_picker` uses to reach its detail
    # card. The dialog is the one part of decision 0013's trait surface that a render
    # test cannot otherwise build, and an unbuilt NiceGUI branch is this project's
    # most-repeated UI bug.
    return _downward_dialog


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
