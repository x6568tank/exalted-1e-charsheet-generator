"""
ui/view/sheet.py — the character sheet view model, `build_sheet_view`, and the
sheet helpers that the shells also read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from ...engine import (advancement, artifacts as artifactsmod, derive,
                       merits as meritsmod, paths as engine_paths, validate)
from ...engine.labels import _label
from ...models.character import Armor, Character, Weapon
from ...models.rules import (AbilityName, AttributeName, BackgroundType, RuleSet,
                             VirtueName)

from ._base import (CharmRow, PathPowerRow, PathRow, SpellRow, TraitRow,
                    _charm_description, _cost_str, _health_label, source_label)
from .xp_log import XpLogRow, build_xp_log


@dataclass
class SheetView:
    # identity / concept
    name: str
    player: str
    caste: str
    caste_noun: str          # what this splat calls the caste slot ("Caste"/"Aspect")
    exalt_type: str
    concept: str
    nature: str
    anima: str
    # free-fill biography (human 2026-08-21) — (label, value) pairs, empty ones dropped
    biography: list[tuple[str, str]]
    # Lunar Form Library (narrative only — see models.character.AnimalForm)
    totem: str
    animal_forms: list[tuple[str, str]]               # (animal, notes)
    essence_rating: int
    # traits
    attributes: list[tuple[str, list[TraitRow]]]      # (category, rows), ordered
    ability_groups: list[tuple[str, list[TraitRow]]]  # (ability-caste, rows), Dawn..Eclipse
    virtues: list[TraitRow]
    # derived
    willpower: int
    essence_personal: int
    essence_peripheral: int
    # Personal is 0 by RULE, not by arithmetic (Beacon of Power) — read it through
    # `essence_pool_label`, which is what both the sheet and the editor display.
    essence_single_pool: bool
    # Motes drawable without a Willpower roll (Essence Awareness), or None when the
    # whole pool is. Also read through `essence_pool_label`.
    essence_free: Optional[int]
    soak: derive.SoakView
    health: list[str]                                 # formatted level labels
    # advantages / gear
    backgrounds: list[tuple[str, int, str]]           # (name, rating, note)
    # Individually rated artifacts (E:Ab p.131), as (name, rating, note, damaged,
    # attunement) — every one the character owns, folded from the standalone list AND
    # from artifact weapons and armour, so the sheet's combined total matches the one
    # the budget check reads. `damaged` is points of Damaged Artifact against that item,
    # 0 for sound ones. `attunement` is `attunement_mark`'s output — the pre-formatted
    # "attuned · 5m", or "" for an item that is not attuned or has no printed cost.
    # Empty for the many characters who own none, which drops the panel.
    artifacts: list[tuple[str, int, str, int, str]]
    # (name, printed cost with sign, detail, "merit"|"flaw"|"either", tooltip) — the
    # sign carries the direction so a Flaw never reads as something the character paid
    # for. The tooltip is the printed cost line plus the rules text: the sheet has no
    # room to show it inline, but a Merit whose text you cannot read is just a word.
    merits_flaws: list[tuple[str, str, str, str, str]]
    # Astrological Colleges (Sidereal, p.98). (name, rating, house_label, own_house)
    # — `own_house` marks a College of the character's own Maiden, the ones the
    # chargen floor counts. Empty for every splat that ships no colleges.
    colleges: list[tuple[str, int, str, bool]]
    # Thaumaturgy (Player's Guide CH3) as (section, item labels) — Arts, Specialties,
    # Sciences, Rituals, Formulas. Cross-splat, so this may be non-empty on any
    # character; empty (and the panel absent) for anyone who bought none.
    thaumaturgy: list[tuple[str, list[str]]]
    thaumaturgy_note: str                             # "" unless the splat may not use it
    specialties: list[tuple[str, str, int]]           # (ability label, name, rating)
    charms: list[CharmRow]
    # The same charm holdings grouped by subsystem — (label, rows) for "Charms",
    # "Arcanoi" (Ghost), "Gifts" (Lunar), "Ox-Body Technique" — so the sheet can head
    # each panel the way the picker's tabs do instead of one undifferentiated list.
    # `charms` above stays the flat concatenation (the GM party view and tests read it).
    charm_sections: list[tuple[str, list[CharmRow]]]
    # Dragon-King Paths of Prehuman Mastery — one row per owned Path, rated 1-6, with
    # the powers its dots grant. Empty for every splat that ships no paths.
    paths: list[PathRow]
    # Combos the character holds — (name, resolved member names, cost = member count).
    # Empty for characters with none; the sheet renders the panel only when non-empty.
    combos: list[tuple[str, list[str], int]]
    spells: list[SpellRow]
    weapons: list[Weapon]
    armor: list[Armor]
    # status / misc
    virtue_flaw: Optional[str]
    experience: int
    issues: list[validate.Issue]
    chargen_locked: bool
    # The XP ledger, as HISTORY. `app.render_sheet` takes only this dataclass — no
    # ruleset, no character, no callbacks — and the GM party screen and the render
    # tests depend on that purity, so the sheet's copy of the ledger is a printout and
    # the live one (Adjust XP, Undo) stays on the Edit tab where the buying happens.
    # Empty pre-lock: there is nothing spent yet and a chargen sheet should not imply
    # otherwise. See decision 0013.
    xp_earned: int = 0
    xp_spent: int = 0
    xp_available: int = 0
    xp_log: list[XpLogRow] = field(default_factory=list)
    # --- Ghosts only (E:Ab p.126-127) --------------------------------------- #
    # Empty for every other splat, which is what keeps the panels off their sheets.
    fetters: list[tuple[str, int, str]] = field(default_factory=list)   # name, rating, note
    fetter_cap: int = 0                               # Willpower + Essence (p.127)
    # (virtue, name, rating) — each Passion belongs to the Virtue whose pool it draws on.
    passions: list[tuple[str, str, int]] = field(default_factory=list)
    # (virtue, distributed, pool) per Virtue. DERIVED from the CURRENT Virtues on both
    # sides of the lock, never snapshotted: p.283 says Passions rise whenever the
    # Virtues do, so a sheet that froze this would go stale the first time a locked
    # ghost bought a Virtue.
    passion_pools: list[tuple[str, int, int]] = field(default_factory=list)
    # Dragon-King breed innate weapons (PG pp.167-174) as (name, speed, accuracy,
    # damage, damage_type, defense) — the printed Spd/Acc/Dmg/Def table. Display-only,
    # decision 0008 keeps attack derivation out. Empty for every splat whose caste has
    # no `breed_traits`, which drops the section from their sheet.
    breed_weapons: list[tuple[str, int, int, int, str, int]] = field(default_factory=list)
    # Elemental Powers (PG p.68) — the Charm-like learnable powers of an
    # Elemental-origin God-Blooded, as CharmRow-shaped rows (category = the power's
    # class). They also get their own headed section inside `charm_sections`, so the
    # Charms & Sorcery band heads them like Arcanoi/Gifts. Empty for every splat that
    # ships no powers, which drops the section from their sheet. Kept off the flat
    # `charms` concatenation — tests and the GM party view read that and pin its count.
    elemental_powers: list[CharmRow] = field(default_factory=list)

    def essence_pool_label(self) -> str:
        """The Essence pools as one line. A merged pool is named as one rather than
        shown as "Personal 0", which reads as a character with no Essence at all, and
        a partly-unlocked one says how much of it is reachable without a Willpower
        roll — a mortal with Essence Awareness owns the whole pool but may only draw
        on a third of it freely, and a bare total would overstate what he can spend."""
        if self.essence_single_pool:
            base = f"Single pool {self.essence_peripheral} (all Peripheral)"
        else:
            base = (f"Personal {self.essence_personal}"
                    f"  ·  Peripheral {self.essence_peripheral}")
        if self.essence_free is None:
            return base
        return f"{base}  ·  {self.essence_free} without a Willpower roll"


# The DEFAULT Ability grouping, for splats whose Abilities are not divided along
# caste lines: War / Life / Wisdom, as printed on the canonical 1e Lunar character
# sheet (images/Lunar/character sheet.png). This is a sheet-layout convention, not
# a rule — nothing mechanical keys off which of the three an Ability sits in, so it
# lives here in the presenter rather than in data/. Splats that DO have ability
# castes (Solar, Dragon-Blooded, Abyssal) override it with their caste grouping.
DEFAULT_ABILITY_GROUPS: tuple[tuple[str, tuple[AbilityName, ...]], ...] = (
    ("War", (AbilityName.ARCHERY, AbilityName.ATHLETICS, AbilityName.AWARENESS,
             AbilityName.BRAWL, AbilityName.DODGE, AbilityName.ENDURANCE,
             AbilityName.MARTIAL_ARTS, AbilityName.MELEE, AbilityName.RESISTANCE,
             AbilityName.THROWN)),
    ("Life", (AbilityName.CRAFT, AbilityName.LARCENY, AbilityName.LINGUISTICS,
              AbilityName.PERFORMANCE, AbilityName.PRESENCE, AbilityName.RIDE,
              AbilityName.SAIL, AbilityName.SOCIALIZE, AbilityName.STEALTH,
              AbilityName.SURVIVAL)),
    ("Wisdom", (AbilityName.BUREAUCRACY, AbilityName.INVESTIGATION, AbilityName.LORE,
                AbilityName.MEDICINE, AbilityName.OCCULT)),
)


def repeatable_cap_trait(charm) -> tuple[str, str]:
    """`(trait label, unit noun)` naming what limits a repeatable Charm's purchases,
    e.g. ("Endurance", "dot") or ("Essence", "point"). ("", "") if not repeatable.

    Never hardcode the trait in UI copy: it varies by splat even for the SAME Charm.
    Ox-Body caps on Endurance for Solar/Dragon-Blooded/Abyssal but on **Stamina** for
    Lunar (The Lunars p.132, "once per dot of human-form Stamina"), and Deadly
    Beastman Transformation caps on Essence (p.124), which is neither an Ability nor
    an Attribute. This mirrors engine.validate._repeatable_purchase_cap, which
    resolves the same field to the actual number.

    The UNIT comes from engine.validate.repeatable_cap_unit — engine.charm_actions
    words the same "once per <unit> of <trait>" refusal, and the pair had been derived
    in two places. Only the trait LABEL is local, so it gets `_label`'s display
    formatting rather than the engine's plainer one."""
    name = getattr(charm, "repeatable_cap_ability", "") if charm else ""
    if not name:
        return ("", "")
    unit = validate.repeatable_cap_unit(charm)
    return ("Essence", unit) if name == "essence" else (_label(name), unit)


def merit_rows(ruleset: RuleSet, character: Character
               ) -> list[tuple[str, str, str, str, str]]:
    """The Merits & Flaws block for a sheet. An unresolvable id is SHOWN with a warning
    marker rather than dropped — the same graceful treatment unknown Charm ids get,
    since a save opened without its data set should say so, not quietly shrink."""
    rows: list[tuple[str, str, str, str, str]] = []
    for mp in character.merits_flaws:
        # A player-authored "Custom" row (2026-08-10): display-only, no mechanical
        # effect — render it by its name rather than as a missing-data warning. The
        # discriminator is the EMPTY merit_id, not custom_name's truthiness: the name
        # is player-editable and may be blanked, but the row must still read as custom
        # (see the chargen-row comment in ui/advantages.py).
        if not mp.merit_id:
            rows.append((mp.custom_name or "Custom", "", mp.detail, "merit",
                         "Custom — no printed effect."))
            continue
        definition = ruleset.merits_flaws.get(mp.merit_id)
        if definition is None:
            rows.append((f"⚠ {mp.merit_id}", "?", mp.detail, "merit",
                         "Not in the rule set — the data that defined it is missing."))
            continue
        points = (definition.cost_options.get(mp.tier, 0)
                  if definition.cost_options else definition.cost)
        sign = "−" if definition.kind == "merit" else "+"
        name = definition.name + (f" ({mp.tier})" if mp.tier else "")
        detail = " · ".join(x for x in (mp.arena, mp.detail) if x)
        tooltip = " ".join(x for x in (definition.cost_note, definition.description) if x)
        rows.append((name, f"{sign}{points}", detail, definition.kind, tooltip))
    return rows


def merit_tier_label(tier: str) -> str:
    """A tier key rendered readably. A key is either a bare point value ("4") or a
    semantic name ("favored_aptitude"); both come back as display text."""
    return tier.replace("_", " + ").title() if not tier.isdigit() else tier.title()


def merit_option_label(definition) -> str:
    """One catalogue entry as a menu line — "Name  (−4 supernatural)". The sign says
    which way the transaction runs (a Flaw PAYS), and a variable-cost entry shows its
    range rather than a single number."""
    sign = "−" if definition.kind == "merit" else "+"
    return (f"{definition.name}  ({sign}{merit_price(definition)} "
            f"{definition.category or definition.kind})")


def merit_price(definition) -> str:
    """Return the point value of a Merit or a Flaw: "3", or "1-3" for an entry with
    cost options."""
    if definition.cost_options:
        lo, hi = min(definition.cost_options.values()), max(definition.cost_options.values())
        return f"{lo}-{hi}"
    return str(definition.cost)


def default_merit_tier(definition, exalt_type: str, caste: str) -> str:
    """The tier a fresh row of `definition` should open on: the first this SPLAT may
    choose, not merely the first authored. "" for an entry with no tier menu.

    ⚠ Prodigy's menu leads with `favored`, which four splats are barred from, so
    opening on the first authored tier hands a Solar a row that flags itself
    immediately."""
    if definition is None or not definition.cost_options:
        return ""
    return next(iter(validate.merit_tiers_available(definition, exalt_type, caste)), "")


def ability_group_defs(ruleset: RuleSet, exalt_type: str) -> list[tuple[str, list[AbilityName]]]:
    """How to lay the Ability roster out in columns, for the sheet and the editor.

    Ability-caste splats (Solar, Dragon-Blooded, Abyssal) group by caste, which is
    how their character sheets print. Lunars have no Caste Abilities at all and
    "Abilities are not divided along caste lines" (The Lunars p.90), so their
    castes carry `caste_attributes` instead and grouping by caste yields NOTHING.
    Those splats fall back to `DEFAULT_ABILITY_GROUPS` (War / Life / Wisdom).

    A splat whose castes list only PART of the roster falls back the same way. The
    Dragon-Kings' four breeds each name three BREED abilities (12 total), but a DK
    buys 25 dots across all 25 abilities (PG CH4) — grouping by breed would drop the
    other 13 from the sheet and editor entirely. Solar/DB/Abyssal castes partition
    the whole roster (5 × 5 = 25), so they keep their caste columns; the breed
    abilities are still marked ● by the caste markers, exactly as a caste ability is."""
    groups = [(cd.label, list(cd.caste_abilities)) for cd in ruleset.castes.values()
              if cd.exalt_type == exalt_type and cd.caste_abilities]
    if groups and {a for _, abilities in groups for a in abilities} >= set(AbilityName):
        return groups
    return [(label, list(abilities)) for label, abilities in DEFAULT_ABILITY_GROUPS]


@dataclass
class StyleView:
    """The style-level text above a martial-arts Charm tree — the preamble the
    `martial_arts:<slug>` categories always implied (docs/plans/martial-arts-
    styles.md). Presentation only: `tier` is the printed `Type:` word and NOTHING
    reads it to decide access, which is still the Charms' business."""
    name: str
    tier: str                 # printed "Type:" — DISPLAY ONLY
    preamble: str
    mechanics: list[str]
    source_label: str         # "Player's Guide p.239", "" when unattributed

    @property
    def heading(self) -> str:
        """The panel's title. `tier` is optional — most books print no `Type:` line
        — so interpolating it unconditionally yields "Air Dragon Style — " with a
        dangling separator.

        Derived HERE rather than inline in `ui/picker.py` for two reasons: CLAUDE.md
        asks for derived state in the presenter so the Qt port carries it over, and
        it gives the tier-less case a home that can be unit-tested with a synthetic
        StyleView. That second reason is load-bearing — every style in the catalogue
        now has a tier, so there is no real subject left to point a render test at,
        and a control with no subject silently stops testing anything.
        """
        return f"{self.name} — {self.tier}" if self.tier else self.name


def style_for_category(ruleset: RuleSet, category: str) -> Optional[StyleView]:
    """The authored style for a `martial_arts:*` category, or None.

    None is an ordinary answer, not an error: a category with no authored style
    (`martial_arts:enlightenment`, which is the Dragon-Path initiation tree rather
    than a style) returns None, and a homebrew style has no page to have a preamble
    from. A caller must render nothing rather than an empty panel.

    ⚠ A returned StyleView can still have an EMPTY `tier` or an empty `preamble` —
    only the Player's Guide prints both. Callers must treat each field as optional
    rather than assuming a non-None style is a fully populated one.
    """
    if not category or not category.startswith("martial_arts:"):
        return None
    for style in ruleset.martial_arts_styles.values():
        if style.category != category:
            continue
        return StyleView(name=style.name, tier=style.tier, preamble=style.preamble,
                         mechanics=list(style.mechanics),
                         source_label=source_label(style.source))
    return None


def specialty_groups(character: Character,
                     ability: AbilityName) -> list[tuple[str, int]]:
    """One Ability's specialties as [(name, how many times taken)], first-seen order.

    ⚠ A specialty is an INSTANCE, not a rated trait (human, 2026-07-31): "you don't
    raise specialties, you just take the same one multiple times". So the COUNT is the
    stacking, and a group of two is two `Specialty` rows on the character — never one
    row rated 2. A renderer showing "Swords ×2" is describing two instances; anything
    that writes back must add or drop whole instances.

    Unnamed rows are kept (they group under ""), because chargen appends a blank row and
    the player names it afterwards — dropping them here would make a fresh row vanish.
    """
    counts: dict[str, int] = {}
    for sp in character.specialties:
        if sp.ability == ability:
            counts[sp.name] = counts.get(sp.name, 0) + 1
    return list(counts.items())


def calling_ability_marks(ruleset: RuleSet, character: Character) -> set:
    """The Ability names the Calling discounts, for the editor's ✦ marks. A separate
    set from the Caste/Favoured one on purpose: an Ability can be both, and the two
    discounts stack (p.90)."""
    return validate.calling_abilities(ruleset, character)


def is_calling_charm(ruleset: RuleSet, character: Character, charm_id: str) -> bool:
    """Whether the picker should mark this Charm as a discounted Calling Charm."""
    return charm_id in validate.calling_charm_ids(ruleset, character)


def granted_charm_rows(ruleset: RuleSet, character: Character) -> list[CharmRow]:
    """The camp's free Charms, as sheet rows. Kept separate from the picked Charms so
    the sheet can label them "granted" — they cost no BP and no XP."""
    rows: list[CharmRow] = []
    for cid in character.granted_charms:
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue
        rows.append(CharmRow(
            name=charm.name, category=_label(charm.category.split(":")[-1]),
            cost=_cost_str(charm.cost), duration=charm.duration,
            description=_charm_description(charm)))
    return rows


def uses_caste_favored_attributes(ruleset: RuleSet, character: Character) -> bool:
    """Whether this splat allocates Attributes to Caste/Favored/remaining SETS
    (Alchemical, p.60) rather than prioritising Physical/Social/Mental categories.
    The editor uses it to switch the Attribute panel between the two layouts."""
    return ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing).attribute_mode == "caste_favored"


def attribute_budget_summary(ruleset: RuleSet, character: Character) -> Optional[str]:
    """A one-line set-based Attribute budget readout for a caste_favored-mode splat
    ('Caste 9 (min 2 each) · Favored 6 · Other 4'), or None for category-mode splats
    (whose panel header shows the prioritised pools instead)."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    if b.attribute_mode != "caste_favored":
        return None
    caste, favored, other = b.attribute_pools
    return (f"Caste {caste} (min {b.attribute_caste_min} each) · "
            f"Favored {favored} · Other {other}")


@dataclass
class SlotBudget:
    """Alchemical Charm-Slot occupancy, for the picker/sheet readout. `installed`
    Charms occupy Slots (each Ox-Body purchase counts; PLM Martial Arts Charms do
    not); `noncf` of them are non-Caste/Favored and so need a General Slot; committed
    installation `motes` must fit the `personal` Essence pool (p.62)."""
    general: int
    dedicated: int
    installed: int
    noncf: int
    motes: int
    personal: int

    @property
    def over_slots(self) -> bool:
        return self.installed > self.general + self.dedicated

    @property
    def over_general(self) -> bool:
        return self.noncf > self.general

    @property
    def over_personal(self) -> bool:
        return self.motes > self.personal


def charm_slot_budget(ruleset: RuleSet, character: Character) -> Optional[SlotBudget]:
    """The Charm-Slot occupancy for a slot-splat (Alchemical), or None for the per-pick
    splats. Everything comes from the engine — the same `charm_slot_usage` the chargen
    check consumes — so the readout can never disagree with validation."""
    if not validate.uses_charm_slots(ruleset, character):
        return None
    g, d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
    installed, noncf, motes = validate.charm_slot_usage(ruleset, character)
    return SlotBudget(g, d, installed, noncf, motes,
                      derive.charm_installation_pool(ruleset, character))


def attunement_mark(motes: int, attuned: bool) -> str:
    """The sheet's marker for an attuned item — "attuned · 5m", or "" for one that is
    not attuned or carries no printed cost.

    ONE helper for all three sheet surfaces (screen, Qt, PDF), for the same reason the
    Play tab's clamp and note are single helpers: three copies of a wording drift, and
    the last time a display fact was taught to one formatter and not its siblings the
    panel and the dropdown printed two different names for one style.

    `motes` is the EFFECTIVE cost `derive.attunement_cost` returns, already doubled
    where the wielder is not a user of the item's material — the sheet prints what this
    character actually commits, not the catalogue's printed figure.

    ⚠ The pools beside it are still the FULL ones. Only the Play tab subtracts a
    commitment (a deliberate split, `status/rated-artifacts.md`), so this marker is the
    sheet's only account of where those motes went.
    """
    if not attuned or motes <= 0:
        return ""
    return f"attuned · {motes}m"


def _artifact_rows(ruleset: RuleSet, character: Character
                   ) -> list[tuple[str, int, str, int, str]]:
    """Every rated artifact for the sheet, as (name, rating, source label, damage,
    attunement mark).

    Reads `engine.artifacts.artifact_items` rather than `character.artifacts` so an
    artifact daiklave appears here as well as in the weapons table — the p.131 budget
    counts it, so a sheet that omitted it would disagree with the validator about what
    the character owns.

    The damage figure comes from `MeritEffects`, not from any Merit id: this module
    may not name one (decision 0011).
    """
    damaged = meritsmod.merits_and_flaws_calc(ruleset, character).damaged_artifacts
    return [(i.name, i.rating,
             "" if i.source == artifactsmod.SOURCE_ARTIFACT else i.source,
             damaged.get(i.key, 0),
             attunement_mark(derive.attunement_cost(ruleset, character, i), i.attuned))
            for i in artifactsmod.artifact_items(character)]


# The book prints the zero rung as "x"; "○" reads as an empty dot beside the filled
# ones and does not collide with the em dashes the ladder text itself uses.
_DOTS = ["○", "•", "••", "•••", "••••", "•••••"]


def background_rung(catalog: Sequence[BackgroundType], name: str, rating: int) -> str:
    """What the book says this RATING of this Background gets you — the one rung of
    `BackgroundType.ladder` the character actually holds, rendered "••• Three major
    contacts and…".

    `catalog` is the character's OWN filtered catalogue (`RuleSet.backgrounds_for`),
    not the whole `background_catalog`, and that is load-bearing rather than
    convenience: several Background NAMES belong to two splats with different printed
    text — a Dragon-Blooded's Connections is not a Sidereal's (Sidereals p.106), and
    Celestial Manse / Salary / Savant are printed for both the Dragon-Kings (PG p.176)
    and the Sidereals. `BackgroundEntry` stores a name, not an id, so a search over
    every splat's entries would hand a Sidereal the Dragon-King's rungs. Searching
    only what this character can actually take makes the name unambiguous.

    Backgrounds are free text, so an unknown name, an untranscribed ladder and a
    rating off the 0-5 scale all return "" and the caller simply shows nothing."""
    bg = next((b for b in catalog if b.name == name), None)
    if bg is None or not bg.ladder or not 0 <= rating < len(bg.ladder):
        return ""
    return f"{_DOTS[rating]} {bg.ladder[rating]}"


def background_ladder(catalog: Sequence[BackgroundType], name: str) -> list[tuple[str, str]]:
    """The WHOLE printed ladder as (dots, text) pairs, for the catalogue dialog's
    full-description panel — where the reader is choosing a rating rather than
    holding one. Same splat-filtered `catalog` as `background_rung`, for the same
    duplicate-name reason. Empty for a Background whose ladder is not transcribed."""
    bg = next((b for b in catalog if b.name == name), None)
    return [(_DOTS[i], text) for i, text in enumerate(bg.ladder)] if bg else []


def college_rows(ruleset: RuleSet, character: Character) -> list[tuple[str, int, str, bool]]:
    """The character's Astrological Colleges as (name, rating, house_label, own_house),
    ordered own-Maiden first then by name — the chargen floor counts only the own-house
    dots (Sidereal, p.98), so those are what a reader checks first. A College id no
    longer in the RuleSet still renders, showing its raw id, rather than vanishing."""
    rows = []
    for cr in character.colleges:
        college = ruleset.colleges.get(cr.college_id)
        if college is None:
            rows.append((cr.college_id, cr.rating, "?", False))
        else:
            rows.append((college.name, cr.rating, college.house_label,
                         college.house == character.caste))
    return sorted(rows, key=lambda r: (not r[3], r[0]))


# The sheet's section order, and the ThaumPurchase.kind each draws from. Sections with
# nothing in them are dropped, so a character with only a couple of formulas gets one
# short line rather than five headings and four dashes.
_THAUM_SECTIONS = [("Arts", "art"), ("Specialties", "specialty"),
                   ("Sciences", "science"), ("Rituals", "ritual"),
                   ("Formulas", "formula")]


def thaumaturgy_rows(ruleset: RuleSet, character: Character) -> list[tuple[str, list[str]]]:
    """The character's thaumaturgy grouped for the sheet, from the engine's canonical
    enumeration — so a purchase can never appear on the picker and be missing here."""
    purchases = validate.thaum_purchases(ruleset, character)
    out = []
    for label, kind in _THAUM_SECTIONS:
        items = [p.label for p in purchases if p.kind == kind]
        if items:
            out.append((label, items))
    return out


def build_sheet_view(ruleset: RuleSet, character: Character) -> SheetView:
    d = derive.derive(ruleset, character)

    issues = list(validate.validate(ruleset, character))
    # Pre-lock, surface chargen budget/legality findings; post-lock, the XP audit.
    if not character.chargen_locked:
        issues += validate.validate_chargen(ruleset, character)
    else:
        issues += advancement.validate_xp(ruleset, character)

    own_caste = ruleset.castes.get(character.caste)
    own_caste_abilities = set(own_caste.caste_abilities) if own_caste else set()
    favored = set(character.favored_abilities)

    # Dragon-King breed attribute bonuses (PG pp.167-174): the breed grants free dots
    # ON TOP of the pool, so the sheet shows the EFFECTIVE value (stored + bonus) with
    # the bonus called out — a Pterok's Dexterity reads as its real 5, not the 3 it
    # cost to buy. Stored values stay what pools and validation read; this is display
    # only, and a no-op for every splat whose caste has no breed_traits.
    _breed_traits = own_caste.breed_traits if own_caste else None
    _breed_bonus = _breed_traits.attribute_bonuses if _breed_traits else {}

    def _attribute_row(a: AttributeName) -> TraitRow:
        bonus = _breed_bonus.get(a, 0)
        if bonus:
            return TraitRow(f"{_label(a.value)} (+{bonus} breed)",
                            character.attributes[a] + bonus)
        return TraitRow(_label(a.value), character.attributes[a])

    attributes = [
        (category, [_attribute_row(a) for a in members])
        for category, members in validate.ATTRIBUTE_CATEGORIES.items()
    ]

    # Abilities grouped by their ability-caste (Dawn..Eclipse), matching the sheet.
    # Craft is per-focus (core p.136): the single Craft slot expands into one row
    # per craft instance ("Craft (Smithing)"), or a single 0-rated row if none.
    ability_groups: list[tuple[str, list[TraitRow]]] = []
    for group_label, group_abilities in ability_group_defs(ruleset, character.exalt_type):
        rows: list[TraitRow] = []
        for a in group_abilities:
            cf_flags = dict(caste=a in own_caste_abilities, favored=a in favored)
            if a == AbilityName.CRAFT:
                if character.crafts:
                    rows += [TraitRow(f"Craft ({c.focus})", c.rating, **cf_flags)
                             for c in character.crafts]
                else:
                    rows.append(TraitRow("Craft", 0, **cf_flags))
            else:
                rows.append(TraitRow(_label(a.value), character.abilities.get(a, 0), **cf_flags))
        ability_groups.append((group_label, rows))

    virtues = [TraitRow(_label(v.value), character.virtues[v]) for v in VirtueName]

    # One row per Charm the character holds, from the single engine enumeration —
    # the sheet must NOT walk character.charms / .ox_body / .beastman_gifts /
    # .granted_charms itself. `charm_picks` already labels repeatable purchases with
    # their chosen variant(s) and tags granted Charms "(granted)".
    charms = []
    _sections: dict[str, list[CharmRow]] = {}

    def _section_label(pick, charm) -> str:
        """Which subsystem panel a charm pick belongs on — the same distinctions the
        picker's tabs draw. Gifts are the Lunar DBT list, Ox-Body its own repeatable
        purchase, Arcanoi are the Ghost/God-Blooded Virtue-keyed Charms (identified by
        `min_virtue` AND a non-Spirit exalt_type, exactly as the picker does — the
        spirit Charms are Virtue-keyed too but are a different class, not Arcanoi);
        everything else is an ordinary Charm."""
        if pick.source == "beastman_gifts":
            return "Gifts"
        if pick.source == "ox_body":
            return "Ox-Body Technique"
        if charm is not None and charm.min_virtue and charm.exalt_type != "Spirit":
            return "Arcanoi"
        return "Charms"

    for pick in validate.charm_picks(ruleset, character):
        charm = ruleset.charms.get(pick.charm_id)
        if charm is None:
            row = CharmRow(pick.label, "?", "—", "—", missing=True)
            charms.append(row)
            _sections.setdefault("Charms", []).append(row)
            continue
        # A repeatable purchase shows the Charm's own text rather than the
        # prerequisite-annotated one, and Ox-Body has no per-purchase activation cost.
        if pick.source in ("ox_body", "beastman_gifts"):
            cost = "—" if pick.source == "ox_body" else _cost_str(charm.cost)
            description = charm.description
        else:
            cost = _cost_str(charm.cost)
            description = _charm_description(charm)
        row = CharmRow(pick.label, charm.category, cost, charm.duration,
                       description, custom=charm.custom)
        charms.append(row)
        _sections.setdefault(_section_label(pick, charm), []).append(row)
    # Elemental Powers (PG p.68): the Charm-like learnable powers of an
    # Elemental-origin God-Blooded, their own headed section in the Charms & Sorcery
    # band exactly like Arcanoi/Gifts. Missing ids render as lost rows, mirroring the
    # missing-Charm handling above — a deleted custom power must not vanish silently.
    elemental_powers = []
    for pid in character.elemental_powers:
        power = ruleset.elemental_powers.get(pid)
        if power is None:
            elemental_powers.append(CharmRow(pid, "?", "—", "—", missing=True))
            continue
        elemental_powers.append(CharmRow(
            power.name, "Elemental Powers", "", "", power.description))
    if elemental_powers:
        _sections["Elemental Powers"] = elemental_powers
    # A character who holds no Charm of any kind still gets a "Charms (0)" panel —
    # the sheet has always said so, and the render tests pin it. Sections only appear
    # when they have rows (an empty Arcanoi panel must not sit on every sheet).
    charm_sections = list(_sections.items()) or [("Charms", [])]

    # Dragon-King Paths (PG pp.175-191): the rated-track truth, not the virtual Charm
    # projection. Only owned Paths appear; each lists the powers its rating grants.
    paths = []
    for path in ruleset.paths.values():
        rating = next((p.rating for p in character.paths if p.path_id == path.id), 0)
        if rating <= 0:
            continue
        if path.element and path.element == engine_paths.breed_element(ruleset, character):
            fav = "★"
        elif path.id == character.favored_path:
            fav = "✚"
        else:
            fav = ""
        paths.append(PathRow(
            name=path.name, element_label=path.element_label, favored=fav, rating=rating,
            powers=[PathPowerRow(p.dot, p.name, _cost_str(p.cost), p.type.value,
                                 p.duration, p.text)
                    for p in path.powers[:rating]],
        ))

    # Combos — member names resolve through ruleset.charms, which includes the
    # Dragon-King Path powers' virtual rows, so a DK Combo's members read as their
    # power names.
    combos = []
    for combo in character.combos:
        members = []
        for cid in combo.charm_ids:
            ch = ruleset.charms.get(cid)
            members.append(ch.name if ch else cid)
        combos.append((combo.name, members, len(combo.charm_ids)))
    spells = []
    for sid in character.spells:
        spell = ruleset.spells.get(sid)
        if spell is None:
            # Mirrors the missing-Charm row above: a spell whose definition has gone
            # (a deleted custom spell) must show as lost, not quietly vanish off the
            # sheet leaving the character looking like it never knew it.
            spells.append(SpellRow(sid, "?", "—", missing=True))
            continue
        spells.append(SpellRow(spell.name, spell.circle.value, _cost_str(spell.cost),
                               spell.description, custom=spell.custom))

    virtue_flaw = None
    if character.virtue_flaw:
        vf = character.virtue_flaw
        virtue_flaw = f"{_label(vf.virtue.value)}: {vf.description}" if vf.description else _label(vf.virtue.value)

    return SheetView(
        name=character.name or "(unnamed)",
        player=character.player,
        caste=own_caste.label if own_caste else character.caste,
        caste_noun=ruleset.exalt_for(character.exalt_type).caste_noun,
        exalt_type=character.exalt_type,
        concept=character.concept,
        nature=character.nature,
        anima=character.anima,
        biography=[(label, value) for label, value in (
            ("Sex", character.sex), ("Age", character.age),
            ("Eyes", character.eye_color), ("Hair", character.hair_color),
            ("Skin", character.skin_color), ("Height", character.height),
            ("Weight", character.weight), ("Description", character.description),
            ("Backstory", character.backstory), ("Notes", character.notes))
            if value],
        totem=character.totem,
        animal_forms=[(f.name, f.notes) for f in character.animal_forms],
        essence_rating=character.essence_rating,
        attributes=attributes,
        ability_groups=ability_groups,
        virtues=virtues,
        willpower=d.willpower,
        essence_personal=d.essence_personal,
        essence_peripheral=d.essence_peripheral,
        essence_single_pool=d.essence_single_pool,
        essence_free=d.essence_free,
        soak=d.soak,
        health=[_health_label(hl) for hl in d.health_levels],
        backgrounds=[(b.name, b.rating, b.note) for b in character.backgrounds],
        artifacts=_artifact_rows(ruleset, character),
        fetters=[(f.name, f.rating, f.note) for f in character.fetters],
        fetter_cap=(derive.fetter_cap(character, ruleset) if character.fetters else 0),
        passions=[(p.virtue.value.title(), p.name, p.rating)
                  for p in character.passions],
        passion_pools=([(v.value.title(),
                         derive.passion_pool(character)[v]
                         - derive.passion_dots_unspent(character)[v],
                         derive.passion_pool(character)[v])
                        for v in VirtueName if derive.passion_pool(character)[v]]
                       if character.passions else []),
        merits_flaws=merit_rows(ruleset, character),
        colleges=college_rows(ruleset, character),
        thaumaturgy=thaumaturgy_rows(ruleset, character),
        # The dead hold thaumaturgy but may never use it (p.114) — a note on the sheet,
        # not a bar, so the knowledge still reads as theirs.
        thaumaturgy_note=("" if ruleset.exalt_for(character.exalt_type).thaumaturgy_usable
                          else f"{character.exalt_type} may hold thaumaturgy but can "
                               "never use it (p.114)."),
        specialties=[(_label(s.ability.value), s.name, s.rating) for s in character.specialties],
        charms=charms,
        charm_sections=charm_sections,
        paths=paths,
        breed_weapons=[(w.name, w.speed, w.accuracy, w.damage, w.damage_type, w.defense)
                       for w in _breed_traits.innate_weapons] if _breed_traits else [],
        combos=combos,
        spells=spells,
        elemental_powers=elemental_powers,
        # Effective stats: material bonuses folded in, Exalt-gated (core p.341).
        weapons=[derive.effective_weapon(ruleset, character, w) for w in character.weapons],
        armor=[derive.effective_armor(ruleset, character, a) for a in character.armor],
        virtue_flaw=virtue_flaw,
        experience=character.xp_earned,
        issues=issues,
        chargen_locked=character.chargen_locked,
        xp_earned=character.xp_earned,
        xp_spent=advancement.xp_spent(character),
        xp_available=advancement.xp_available(character),
        # Pre-lock the log is empty by construction, but say so explicitly: a chargen
        # sheet showing an "Experience" section with nothing in it reads as a bug.
        xp_log=build_xp_log(ruleset, character) if character.chargen_locked else [],
    )
