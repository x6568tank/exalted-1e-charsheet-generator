"""
engine/merits.py — the ONE place Merits & Flaws have mechanical effects.

**Decision 0011**: this module calculates every mechanical effect of a Merit or
Flaw, in one calculation.

  * `rules.MeritFlaw` is INERT DATA: printed text, cost, prerequisites. A Merit with
    no mechanical effect needs a data row only.
  * `merits_and_flaws_calc` maps the Merits that a character HOLDS to a
    `MeritEffects` value. It is the only function that knows a Merit id.
  * All other modules read `MeritEffects` fields. **No caller anywhere may branch on
    a Merit id.** For a new effect, add a FIELD here. Do not add a lookup there.

`MeritEffects` is keyed by EFFECT, not by Merit.

Sources: the general M&F chapter and the Thaumaturgy Merits (Player's Guide
pp.120-122). See docs/status/merits-flaws.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models.character import Character
from ..models.rules import AbilityName, AttributeName, MeritFlaw, RuleSet, SpellCircle, VirtueName

# --------------------------------------------------------------------------- #
# The ids this module knows. Nothing outside engine/merits.py may name these.
# --------------------------------------------------------------------------- #

# PG p.16: the maximum bonus points from Flaws. p.17 applies the same cap to XP.
FLAW_POINT_CAP = 10


def inheritance_rating(character: Character) -> int:
    """Return the God-Blooded Inheritance rating (Player's Guide p.61): the index
    into `ChargenBudgets.inheritance_bonus_points` / `inheritance_flaw_cap`.

    Always the Inheritance Background rating of the character. The Storyteller option
    sets the free dots only (human's ruling)."""
    return max((bg.rating for bg in character.backgrounds
                if bg.name.strip().lower() == "inheritance"), default=0)


def inheritance_free_rating(ruleset: RuleSet, character: Character) -> int:
    """Return the free dots of the Inheritance Background (human's ruling).

    Return HouseRules.godblooded_inheritance_rating if set (p.61). Else return the
    budget `free_rating` of the Inheritance Background. The rating does not change.

    ⚠ Reads the frozen snapshot once locked, as `validate.chargen_house_rules` does. A
    campaign changes the live value on a locked copy (p3-tables.md section 5)."""
    snap = character.chargen_snapshot
    rules = snap.house_rules if snap is not None else character.house_rules
    granted = rules.godblooded_inheritance_rating if rules is not None else None
    if granted is not None:
        return granted
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    rule = b.background_rules.get("inheritance")
    return rule.free_rating if rule is not None else 0


ESSENCE_AWARENESS = "thaum.essence-awareness"
ESSENCE_MASTERY = "thaum.essence-mastery"
# God-Blooded (PG p.66): opens the Essence pool of the heritage.
AWAKENED_ESSENCE = "mf.awakened-essence"
# Attunement for a non-Exalt: mortal (PG p.120) and God-Blooded (PG p.66). See
# `MeritEffects.no_magical_material_bonus`.
# God-Blooded (PG p.67). See `MeritEffects.essence_pool_split_thirds`.
AURA_OF_POWER = "mf.aura-of-power"
MAGICAL_ATTUNEMENT_MORTAL = "thaum.magical-attunement"
MAGICAL_ATTUNEMENT_GODBLOODED = "mf.magical-attunement"
# PG p.234, ghosts only. One Terrestrial Martial Arts Charm per point.
FIGHTER_IN_LIFE = "mf.fighter-in-life"
OATHBOUND_MAGIC = "thaum.oathbound-magic"
HOLY_MIEN = "thaum.holy-mien"
# Fae-Blooded (PG p.74): the attuned Virtue costs as a FAVORED trait. The purchase
# `detail` names the Virtue.
FAE_VIRTUE_ATTUNEMENT = "mf.fae-virtue-attunement"
# PG p.121: Holy Mien grants Priest (p.24) at one point, and the seven-point level
# costs six.
PRIEST = "mf.priest"

# Spirit Walking opens Celestial Martial Arts. Essence Mastery does not grant it
# (human's ruling). Its prerequisite Spirit Sight stays legal.
# ⚠ Spirit Walking is `open_to_all`, thus the tier rules do not bar it.
SPIRIT_WALKING = "dragonblooded.martial-arts.spirit-walking"

# The four trait-forfeit Flaws (PG pp.35-36, p.20), and the bonus points for each
# dot given up. The rate converts the point value back to dots.
DIMINISHED_ATTRIBUTES = "mf.diminished-attributes"
CALLOUS = "mf.callous"
UNSKILLED = "mf.unskilled"
WEAK_WILLED = "mf.weak-willed"

# Health levels (A2), by tier (p.20, p.32).
LARGE_SIZE = "mf.large-size"
SMALL = "mf.small"

_LARGE_SIZE_LEVELS: dict[str, tuple[int, ...]] = {"4": (0,), "6": (0, -1)}
_SMALL_REMOVES: tuple[int, ...] = (-1,)

# Trait caps (A3). These entries change the cap of 5 for one character.
LEGENDARY_ATTRIBUTE = "mf.legendary-attribute"
TRUE_PARAGON = "mf.true-paragon"
DISFIGURED = "mf.disfigured"
WEAK_ESSENCE = "mf.weak-essence"

DOT_MAX = 5                        # the universal trait cap these entries depart from

# Disfigured (p.33): a cap of 0 also makes the trait unraisable.
_DISFIGURED_APPEARANCE_CAPS: dict[str, int] = {"3": 1, "4": 0}
# ⚠ Keyed by AttributeName.value, which is LOWERCASE. Normalize each key.
APPEARANCE = "appearance"

# True Paragon (p.22): Virtue cap 6. It requires the Paragon Nature, which Callous
# bars.
TRUE_PARAGON_VIRTUE_CAP = 6

# Weak Essence (p.41): starting Essence 1.
WEAK_ESSENCE_START = 1
# The Flaw banks up to five Charm PICKS with no XP cost (human's ruling).
WEAK_ESSENCE_CHARM_CREDITS = 5

_FORFEIT_RATES = {
    DIMINISHED_ATTRIBUTES: 3,      # "three points for every Physical Attribute dot"
    CALLOUS: 2,                    # "two bonus points for every dot of Virtues"
    UNSKILLED: 1,                  # "one bonus point for every dot of Abilities"
    WEAK_WILLED: 1,                # "one bonus point for every dot of permanent Willpower"
}

# Callous (p.35): the Flaw ends at 9 Virtue dots.
CALLOUS_EXPIRY_VIRTUE_DOTS = 9
CALLOUS_WILLPOWER_MARGIN = 1
PARAGON_NATURE = "Paragon"

# Weak-Willed (p.36): the Willpower floors.
WEAK_WILLED_FLOOR_EXALTED = 4
WEAK_WILLED_FLOOR_MORTAL = 2

# Backgrounds (A6). One entry adds to the chargen Background pool. One restricts
# the Backgrounds. Damaged Artifact, Known Anathema and Debt limit their own points:
# that is catalogue data (`MeritFlaw.points_limits`), checked by validate.
HEIR_APPARENT = "mf.heir-apparent"
INNOCUOUS = "mf.innocuous"

# Damaged Artifact also has a derived effect. See MeritEffects.damaged_artifacts.
DAMAGED_ARTIFACT = "mf.damaged-artifact"

# PG p.38: soak lost on both tracks, by points of the Flaw (human's ruling).
# ⚠ None = no soak at all ("presently useless"). It is not a subtraction.
DAMAGED_ARTIFACT_SOAK: dict[int, int | None] = {1: 1, 2: 3, 3: None}

# Heir Apparent (p.24).
HEIR_APPARENT_DOTS_PER_POINT = 2
HEIR_APPARENT_MAX_POINTS = 5
HEIR_APPARENT_MAX_STIPULATIONS = 3

# Innocuous, four-point version only (p.22). The two-point version is dice.
# The page lists some Backgrounds and says "or any other". The human's ruling adds:
#   capped at 2 — Backing, Connections, Retainers, Renown, Liege.
#   barred — Reputation, Influence.
# Names are lowercased because Backgrounds are free text, matched by name and never by id.
INNOCUOUS_VEILED_TIER = "4"
_INNOCUOUS_CAPS: dict[str, int] = {
    "allies": 2, "contacts": 2, "mentor": 2,          # named on the page
    "backing": 2, "connections": 2, "retainers": 2,   # human's ruling
    "liege": 2, "renown": 2,
}
_INNOCUOUS_BARRED: frozenset[str] = frozenset(
    {"followers", "henchmen", "henchman", "cult", "command",   # named on the page
     "reputation", "influence"})                               # human's ruling

# Play-state pools and tracks (A7). ⚠ Decision 0006: chargen validation and the XP
# audit must NEVER read these.
LUCKY = "mf.lucky"
UNLUCKY = "mf.unlucky"
GREATER_CURSE = "mf.greater-curse"
DEATH_TAINT = "mf.death-taint"

# The maximum of the Limit/Paradox/Resonance track: the constant 10.
LIMIT_MAX = 10
# Greater Curse (p.40).
GREATER_CURSE_MAX_REDUCTION = 5

# Lucky (p.27): the Sidereal adjustment.
SIDEREAL = "Sidereal"
SIDEREAL_LUCK_BONUS = 2
SIDEREAL_LUCK_MAX = 5
SIDEREAL_LUCK_MIN = 3

# Death's Taint (p.41): starting permanent Resonance = points - 4.
DEATH_TAINT_BASE_POINTS = 4
# p.41: the XP to remove one dot of permanent Resonance.
PERMANENT_RESONANCE_SHED_XP = 5

# Essence-pool shape (A5).
LEGENDARY_BREEDING = "mf.legendary-breeding"
BEACON_OF_POWER = "mf.beacon-of-power"

# Legendary Breeding (p.28; E:DB, p. 158): Breeding rating 6. The motes come from the
# rating-6 row of the Breeding table in data/exalts.json. The Breeding 5 requirement
# is in `MeritFlaw.trait_prerequisites`.
LEGENDARY_BREEDING_RATING = 6


@dataclass(frozen=True)
class MeritEffects:
    """The effects of the Merits and Flaws of a character.

    Each default is the value for a character with no Merits.
    """

    # --- Essence ----------------------------------------------------------- #
    # PG p.114: the character can use an Essence pool. True for each Exalt.
    essence_pool_unlocked: bool = False
    # The access is unrestricted (Essence Mastery). Essence Awareness gives partial
    # access. The split is not modelled (decision 0009).
    essence_pool_unrestricted: bool = False
    # PG p.120, PG p.66: the character never gets a Magical Material bonus.
    # ⚠ Without this flag the result is correct by accident: no material has the
    # `exalt_type` "Mortal" or "God-Blooded" (the house bug, type 2).
    no_magical_material_bonus: bool = False
    # Aura of Power (PG p.67): one third of the pool is Personal (rounded down), two
    # thirds Peripheral. Never set with `essence_single_pool`.
    # ⚠ It must override the splat `single_essence_pool`.
    # `derive.essence_pool_is_merged` checks it first. The split uses the TOTAL.
    essence_pool_split_thirds: bool = False
    # Merit ids that count as HELD for the `prerequisites` of another entry. Awakened
    # Essence counts as Essence Awareness and Essence Mastery (human's ruling).
    #
    # ⚠ A SUBSTITUTION for a gate, not a grant. `open_charm_categories` does not
    # change (see `true-not-applicable-is-not-a-condition`).
    #
    # ⚠ The only way a caller learns about a substitution. `merit_checks` adds this
    # set to the held ids. The UI tests membership.
    prerequisites_satisfied: frozenset[str] = frozenset()
    # PG p.114: overrides ExaltDefinition.essence_cap. None = no override.
    essence_cap_override: int | None = None
    # The effective rating of EssencePoolSpec.breeding_background. None = the
    # purchased rating.
    breeding_rating_override: int | None = None
    # Beacon of Power (p.41): Personal becomes 0, all motes are Peripheral. The pools
    # are calculated first, then merged.
    essence_single_pool: bool = False

    # --- Magic access ------------------------------------------------------ #
    # Charm categories opened to a Charmless splat, and the Charms barred in them.
    # validate.charm_matches_splat reads both. `barred_charm_ids` wins.
    open_charm_categories: frozenset[str] = frozenset()
    barred_charm_ids: frozenset[str] = frozenset()
    # Bar the Immaculate Order Charms in an opened category (human's ruling).
    bar_immaculate_charms: bool = False
    # PG p.234 (Fighter in Life): Terrestrial Martial Arts Charms at the Arcanos cost,
    # not the p.234 rate. One per point.
    # ⚠ A count, not access. `ExaltDefinition.terrestrial_martial_arts` gives access.
    terrestrial_ma_picks: int = 0
    # Spell circles granted with no initiation Charm.
    granted_circles: frozenset[SpellCircle] = frozenset()

    # --- Points ------------------------------------------------------------ #
    # Bonus points from Flaws, after the Oathbound stacking reduction, CLAMPED to
    # FLAW_POINT_CAP.
    bonus_point_grant: int = 0
    # The value before the cap, for the UI.
    flaw_points_raw: int = 0

    # --- Trait caps -------------------------------------------------------- #
    # Attribute ceilings that replace 5, keyed by AttributeName.value. One field for
    # a raise and a reduction. Absent = 5.
    attribute_caps: dict[str, int] = field(default_factory=dict)
    # True Paragon (p.22): the Virtue ceiling. None = 5. The Willpower maximum of 10
    # does not change.
    virtue_cap: int | None = None
    # Weak Essence (p.41): the starting Essence. None = the splat value.
    essence_start_override: int | None = None
    # --- Cost repricing (A4) ------------------------------------------------ #
    # Brigid's Heir (p.30). Flags, not multipliers: the Charm half has an exemption.
    # Callers use `adjust_charm_cost`.
    charm_cost_doubled: bool = False
    spell_cost_halved: bool = False

    # --- Favored Abilities / Virtues (A4) ------------------------------------ #
    # Prodigy (p.21): extra Favored Abilities. Added to `validate.favored_ability_count`.
    extra_favored_abilities: int = 0
    # Virtue Attunement (PG p.74): Virtues that cost as FAVORED, by VirtueName.value.
    # Read by the Virtue BP and XP cost functions.
    favored_virtues: frozenset[str] = frozenset()
    # {`AbilityName.value`: XP subtracted per dot} (Prodigy). One entry per Ability:
    # two purchases for one Ability do not stack.
    ability_xp_discount: dict[str, int] = field(default_factory=dict)

    # The maximum Charm picks that a Flaw banks for use after the lock. The real count
    # is `validate.withheld_charm_credits`. 0 = no such Flaw.
    charm_credits_max: int = 0
    # Display NAMES of held entries whose Nature requirement fails (True Paragon).
    nature_requirement_unmet: tuple[str, ...] = ()

    # --- Health track ------------------------------------------------------ #
    # Levels added, as (wound penalty, source label). The label is the Merit name.
    health_levels_granted: tuple[tuple[int, str], ...] = ()
    # Levels removed, one per entry (Small). A base level goes first.
    health_levels_removed: tuple[int, ...] = ()

    # --- Chargen budget forfeits ------------------------------------------- #
    # The four forfeit Flaws give up chargen dots. `flaw_points` grants their bonus
    # points. These fields reduce the budget, as a delta on the printed budget.
    # Dots = points // rate.
    forfeited_ability_dots: int = 0
    forfeited_virtue_dots: int = 0
    forfeited_willpower_dots: int = 0
    # {"Physical" | "Social" | "Mental": dots} (p.36). The purchase `detail` names the
    # category.
    forfeited_attribute_dots: dict[str, int] = field(default_factory=dict)
    # Callous (p.35): the maximum starting Willpower above the two highest Virtues.
    # ⚠ None is not 0. The one exception to decision 0005 (human's ruling).
    willpower_virtue_margin: int | None = None
    # Callous: the Virtue component of Willpower follows the current Virtues after
    # the lock. ⚠ The margin field above does nothing after the lock.
    willpower_tracks_virtues: bool = False
    # Weak-Willed: the starting Willpower floor. 0 = no floor.
    willpower_floor: int = 0
    # Natures that a held Flaw bars (p.35).
    barred_natures: frozenset[str] = frozenset()

    # --- Backgrounds (A6) ---------------------------------------------------- #
    # Heir Apparent (p.24): dots added to the chargen Background pool, as a delta.
    bonus_background_dots: int = 0
    # Background dots that can go above `background_cap_pre_bp` with no bonus points.
    # Applied to the most expensive above-cap dots. Never more than the Merit grants.
    background_cap_exempt_dots: int = 0
    # Ceilings by lowercased Background NAME. Absent = 5.
    background_caps: dict[str, int] = field(default_factory=dict)
    # Backgrounds barred, lowercased names.
    barred_backgrounds: frozenset[str] = frozenset()

    # --- Play-state pools and tracks (A7) ------------------------------------ #
    # ⚠ PLAY-STATE (decision 0006). Chargen validation and the XP audit never read
    # this block.
    #
    # Lucky (p.27). 0 = not held.
    luck_pool: int = 0
    # Unlucky (p.39). Stored positive. A character can hold Lucky and Unlucky.
    bad_luck_pool: int = 0
    # Greater Curse (p.40): the track maximum. None = 10.
    limit_max: int | None = None
    # Death's Taint: the starting permanent Resonance. ⚠ None = not held. 0 = held
    # with no starting Resonance.
    permanent_limit_start: int | None = None

    # --- Damaged artifacts (PG p.38) ---------------------------------------- #
    # Points of Damaged Artifact by `engine.artifacts` item key ("armor:soulsteel
    # articulated plate").
    #
    # Only the armor soak effect is derived (`derive.soak`). The weapon effects are
    # out of scope (decision 0008). See DAMAGED_ARTIFACT_SOAK (human's ruling).
    damaged_artifacts: dict[str, int] = field(default_factory=dict)

    # --- Cross-Merit effects ----------------------------------------------- #
    # Merits held free because another Merit grants them (Holy Mien -> Priest).
    granted_merits: frozenset[str] = frozenset()
    # Price overrides, {merit_id: {tier: points}}. validate.merit_points reads them
    # first.
    merit_cost_overrides: dict[str, dict[str, int]] = field(default_factory=dict)

    # --- Bookkeeping ------------------------------------------------------- #
    # Ids that produced no effect, for the UI.
    narrative_only: tuple[str, ...] = ()


def _held(ruleset: RuleSet, character: Character) -> list[tuple[MeritFlaw, object]]:
    """Return (definition, purchase) for each held Merit that resolves in the
    RuleSet. Skip an unknown id: validate reports it."""
    out = []
    for purchase in character.merits_flaws:
        definition = ruleset.merits_flaws.get(purchase.merit_id)
        if definition is not None:
            out.append((definition, purchase))
    return out


def merit_ids_held(character: Character) -> set[str]:
    """Return the ids of all held Merits, resolved or not. Use this function to ask
    if a character holds a Merit (decision 0011)."""
    return {p.merit_id for p in character.merits_flaws}


def oathbound_bonus_points(character: Character, ruleset: RuleSet) -> int:
    """Return the bonus points of Oathbound Magic, after the stacking rule (PG p.122).

    In one arena, each oath after the first loses (oaths in that arena - 1) points.
    The highest-value oath keeps its full value. The floor is 0. A blank arena is its
    own arena.
    """
    by_arena: dict[str, list[int]] = {}
    for definition, purchase in _held(ruleset, character):
        if definition.id != OATHBOUND_MAGIC:
            continue
        value = definition.cost_options.get(purchase.tier, 0)
        key = purchase.arena or f"\0{id(purchase)}"      # blank arena = its own bucket
        by_arena.setdefault(key, []).append(value)

    total = 0
    for values in by_arena.values():
        penalty = len(values) - 1                       # 0 for a lone oath
        # The highest-value oath keeps its value. The others pay the penalty.
        for i, value in enumerate(sorted(values, reverse=True)):
            total += value if i == 0 else max(0, value - penalty)
    return total


def flaw_points(ruleset: RuleSet, character: Character) -> int:
    """Return the bonus points of all held FLAWS, before the cap (PG p.16).

    Oathbound points count toward the cap. ⚠ Not modelled: the rule that oath points
    must buy the Traits of the oath. There is one bonus-point pool.
    """
    total = oathbound_bonus_points(character, ruleset)
    for definition, purchase in _held(ruleset, character):
        from .validate import effective_merit_kind, merit_points   # validate imports merits
        if definition.id == OATHBOUND_MAGIC:
            continue
        if effective_merit_kind(definition, purchase) != "flaw":
            continue
        total += merit_points(definition, purchase, character.exalt_type,
                              character.caste)
    return total


def forfeit_rate(definition) -> int | None:
    """Return the bonus points per dot given up, or None for a Flaw that is not a
    forfeit Flaw.

    The editor collects DOTS (human's ruling) and stores
    `dots x forfeit_rate(d)` in `MeritFlawPurchase.points`.
    """
    return _FORFEIT_RATES.get(definition.id)


def forfeit_trait_label(definition) -> str:
    """Return the trait that a forfeit dot buys back, for the editor label. Return
    "" for other entries."""
    return {DIMINISHED_ATTRIBUTES: "Attribute", CALLOUS: "Virtue",
            UNSKILLED: "Ability", WEAK_WILLED: "Willpower"}.get(definition.id, "")


def uses_arena(definition) -> bool:
    """Return True if `MeritFlawPurchase.arena` applies to this entry (p.122).
    ⚠ Gate the editor arena box on this, not on a tier menu."""
    return definition.id == OATHBOUND_MAGIC


def detail_choices(definition) -> tuple[str, ...]:
    """Return the permitted values of `MeritFlawPurchase.detail` for this entry.
    Return () for free text.

    ⚠ Free text breaks these entries:

      * Diminished Attributes — the Attribute category (p.36). A typo becomes a
        fourth category.
      * Legendary Attribute — the Attribute. A bad value makes the Merit inert.

    Display strings. The caller stores them as given. Downstream matching ignores
    case.
    """
    if definition.id == DIMINISHED_ATTRIBUTES:
        return ("Physical", "Mental", "Social")
    if definition.id == LEGENDARY_ATTRIBUTE:
        return tuple(a.value.title() for a in AttributeName)
    if definition.id == PRODIGY:
        # The Ability of this purchase. One per purchase. Craft is excluded: it is
        # per focus (core p.136).
        return tuple(a.value.title() for a in AbilityName if a != AbilityName.CRAFT)
    if definition.id == FAE_VIRTUE_ATTUNEMENT:
        # PG p.74: the attuned Virtue. ⚠ A typo would disable the discount.
        return tuple(v.value.title() for v in VirtueName)
    return ()


def _forfeited_dots(ruleset: RuleSet, character: Character) -> dict[str, int]:
    """Return {merit_id: dots given up} for each held forfeit Flaw: points // rate.

    Rounds DOWN, thus a bad value cannot give budget.
    """
    from .validate import merit_points                    # validate imports merits

    out: dict[str, int] = {}
    for definition, purchase in _held(ruleset, character):
        rate = _FORFEIT_RATES.get(definition.id)
        if rate is None:
            continue
        points = merit_points(definition, purchase, character.exalt_type, character.caste)
        out[definition.id] = out.get(definition.id, 0) + max(0, points) // rate
    return out


def _attribute_forfeits(ruleset: RuleSet, character: Character) -> dict[str, int]:
    """Return the Diminished Attributes dots by category (p.36). The category is in
    `MeritFlawPurchase.detail`. The default is Physical: validate reports the
    omission.
    """
    from .validate import merit_points

    out: dict[str, int] = {}
    for definition, purchase in _held(ruleset, character):
        if definition.id != DIMINISHED_ATTRIBUTES:
            continue
        points = merit_points(definition, purchase, character.exalt_type, character.caste)
        category = (purchase.detail or "").strip().title() or "Physical"
        out[category] = out.get(category, 0) + max(0, points) // _FORFEIT_RATES[definition.id]
    return out


def merits_and_flaws_calc(ruleset: RuleSet, character: Character) -> MeritEffects:
    """Return the MeritEffects of `character`. The one M&F calculation.

    A splat with an Essence pool keeps it. A splat whose
    `ExaltDefinition.essence.personal_essence_coeff` is zero needs a Merit to unlock
    its pool.
    """
    exalt = ruleset.exalt_for(character.exalt_type)
    has_native_pool = bool(exalt.essence.personal_essence_coeff
                           or exalt.essence.personal_willpower_coeff)
    raw_flaw_points = flaw_points(ruleset, character)
    # God-Blooded p.61: `inheritance_flaw_cap` replaces FLAW_POINT_CAP. Index 0 is 0
    # (human's ruling).
    flaw_cap = FLAW_POINT_CAP
    budgets = ruleset.budgets_for(character.exalt_type, character.origin,
                                  character.upbringing)
    if budgets.inheritance_flaw_cap:
        rating = min(inheritance_rating(character), len(budgets.inheritance_flaw_cap) - 1)
        flaw_cap = budgets.inheritance_flaw_cap[rating]

    held_ids = {d.id for d, _p in _held(ruleset, character)}
    effects_from: set[str] = set()

    # --- Virtue Attunement (PG p.74, Fae-Blooded) ---------------------------- #
    # The Virtue name in `detail` matches VirtueName with any case.
    favored_virtues = frozenset(
        VirtueName(purchase.detail.strip().lower()).value
        for _d, purchase in _held(ruleset, character)
        if purchase.merit_id == FAE_VIRTUE_ATTUNEMENT
        and purchase.detail.strip().lower() in {v.value for v in VirtueName})

    # --- Essence Awareness / Mastery / Awakened Essence -------------------- #
    awareness = ESSENCE_AWARENESS in held_ids
    mastery = ESSENCE_MASTERY in held_ids
    awakened = AWAKENED_ESSENCE in held_ids
    if awareness or mastery or awakened:
        effects_from.update(
            {ESSENCE_AWARENESS, ESSENCE_MASTERY, AWAKENED_ESSENCE} & held_ids)

    open_categories: frozenset[str] = frozenset()
    barred: frozenset[str] = frozenset()
    circles: frozenset[SpellCircle] = frozenset()
    cap_override: int | None = None
    bar_immaculate = False

    if mastery:
        # PG p.121: Terrestrial Martial Arts, except the Charm that opens Celestial.
        open_categories = frozenset({"martial_arts"})
        barred = frozenset({SPIRIT_WALKING})
        bar_immaculate = True
        # Terrestrial circle only (human's ruling). ⚠ It replaces the initiation
        # Charm, thus only a splat with no Charms gets it.
        if not exalt.charms_available:
            circles = frozenset({SpellCircle.TERRESTRIAL})
        # ⚠ Do not LOWER an Exalt's cap (0 = uncapped) to 3.
        if exalt.essence_cap and exalt.essence_cap < 3:
            cap_override = 3

    if awakened:
        # God-Blooded (PG p.66): a full pool, set by the heritage. It permits
        # Essence 2/3. Charm access comes from heritage_traits.charm_access.
        if exalt.essence_cap and exalt.essence_cap < 3:
            cap_override = 3

    # --- Trait caps -------------------------------------------------------- #
    attribute_caps: dict[str, int] = {}
    virtue_cap: int | None = None
    essence_start_override: int | None = None
    charm_credits_max = 0
    charm_cost_doubled = False
    spell_cost_halved = False
    extra_favored = 0
    nature_unmet: list[str] = []
    aptitude_abilities: dict[str, int] = {}
    breeding_override: int | None = None
    single_pool = False
    bonus_background_dots = 0
    background_cap_exempt = 0
    background_caps: dict[str, int] = {}
    barred_backgrounds: set[str] = set()
    luck_pool = 0
    bad_luck_pool = 0
    limit_max: int | None = None
    permanent_limit_start: int | None = None
    from .validate import merit_points                        # validate imports merits
    for definition, purchase in _held(ruleset, character):
        if definition.id == LEGENDARY_ATTRIBUTE:
            # p.20: one dot above the normal limit. ⚠ This does not add an
            # Essence-scaled cap for other characters.
            trait = (purchase.detail or "").strip().lower()   # AttributeName.value
            if trait:
                cap = max(DOT_MAX, character.essence_rating) + 1
                attribute_caps[trait] = max(attribute_caps.get(trait, 0), cap)
                effects_from.add(definition.id)
        elif definition.id == DISFIGURED:
            cap = _DISFIGURED_APPEARANCE_CAPS.get(purchase.tier)
            if cap is not None:
                # The LOWEST cap wins.
                current = attribute_caps.get(APPEARANCE)
                attribute_caps[APPEARANCE] = cap if current is None else min(current, cap)
                effects_from.add(definition.id)
        elif definition.id == TRUE_PARAGON:
            virtue_cap = TRUE_PARAGON_VIRTUE_CAP
            if character.nature != PARAGON_NATURE:
                nature_unmet.append(definition.name)
            effects_from.add(definition.id)
        elif definition.id == BRIGIDS_HEIR:
            charm_cost_doubled = True
            spell_cost_halved = True
            effects_from.add(definition.id)
        elif definition.id == PRODIGY:
            # Only the halves that grant a Favored Ability raise the count.
            if purchase.tier in PRODIGY_GRANTS_FAVORED:
                extra_favored += 1
            if purchase.tier in PRODIGY_GRANTS_APTITUDE and purchase.detail.strip():
                aptitude_abilities[purchase.detail.strip().casefold()] = \
                    PRODIGY_APTITUDE_XP_DISCOUNT
            effects_from.add(definition.id)
        elif definition.id == WEAK_ESSENCE:
            essence_start_override = WEAK_ESSENCE_START
            charm_credits_max = WEAK_ESSENCE_CHARM_CREDITS
            effects_from.add(definition.id)
        elif definition.id == LEGENDARY_BREEDING:
            # The highest rating wins.
            breeding_override = max(breeding_override or 0, LEGENDARY_BREEDING_RATING)
            effects_from.add(definition.id)
        elif definition.id == BEACON_OF_POWER:
            single_pool = True
            effects_from.add(definition.id)
        elif definition.id == HEIR_APPARENT:
            # p.24: five points maximum.
            points = min(HEIR_APPARENT_MAX_POINTS,
                         merit_points(definition, purchase, character.exalt_type,
                                      character.caste))
            stipulations = min(HEIR_APPARENT_MAX_STIPULATIONS,
                               max(0, purchase.stipulations))
            dots = max(0, points) * HEIR_APPARENT_DOTS_PER_POINT + stipulations
            bonus_background_dots += dots
            # Each granted dot can exceed the rating-3 cap.
            background_cap_exempt += dots
            effects_from.add(definition.id)
        elif definition.id == LUCKY:
            points = merit_points(definition, purchase, character.exalt_type,
                                  character.caste)
            if character.exalt_type == SIDEREAL:
            # p.27: the Sidereal pool is points + 2, between 3 and 5.
                luck_pool += min(SIDEREAL_LUCK_MAX,
                                 max(SIDEREAL_LUCK_MIN, points + SIDEREAL_LUCK_BONUS))
            else:
                luck_pool += max(0, points)
            effects_from.add(definition.id)
        elif definition.id == UNLUCKY:
            bad_luck_pool += max(0, merit_points(definition, purchase,
                                                 character.exalt_type, character.caste))
            effects_from.add(definition.id)
        elif definition.id == GREATER_CURSE:
            points = merit_points(definition, purchase, character.exalt_type,
                                  character.caste)
            reduction = min(GREATER_CURSE_MAX_REDUCTION, max(0, points))
            # The lowest maximum wins.
            lowered = LIMIT_MAX - reduction
            limit_max = lowered if limit_max is None else min(limit_max, lowered)
            effects_from.add(definition.id)
        elif definition.id == DEATH_TAINT:
            # points = 4 base + 1 per starting dot.
            points = merit_points(definition, purchase, character.exalt_type,
                                  character.caste)
            start = max(0, points - DEATH_TAINT_BASE_POINTS)
            permanent_limit_start = (start if permanent_limit_start is None
                                     else permanent_limit_start + start)
            effects_from.add(definition.id)
        elif definition.id == INNOCUOUS and purchase.tier == INNOCUOUS_VEILED_TIER:
            for name, cap in _INNOCUOUS_CAPS.items():
                current = background_caps.get(name)
                background_caps[name] = cap if current is None else min(current, cap)
            barred_backgrounds |= _INNOCUOUS_BARRED
            effects_from.add(definition.id)

    # --- Health levels ----------------------------------------------------- #
    granted_levels: list[tuple[int, str]] = []
    removed_levels: list[int] = []
    for definition, purchase in _held(ruleset, character):
        if definition.id == LARGE_SIZE:
            # An unknown tier grants nothing. Validate reports it.
            for penalty in _LARGE_SIZE_LEVELS.get(purchase.tier, ()):
                granted_levels.append((penalty, definition.name))
            effects_from.add(definition.id)
        elif definition.id == SMALL:
            removed_levels.extend(_SMALL_REMOVES)
            effects_from.add(definition.id)

    # --- The trait-forfeit Flaws ------------------------------------------- #
    forfeits = _forfeited_dots(ruleset, character)
    effects_from.update(forfeits.keys() & held_ids)

    callous_dots = forfeits.get(CALLOUS, 0)
    virtue_total = sum(character.virtues.values())
    # Callous ends at 9 Virtue dots. ⚠ Its bonus points are not refunded.
    callous_active = CALLOUS in held_ids and virtue_total < CALLOUS_EXPIRY_VIRTUE_DOTS

    willpower_floor = 0
    if WEAK_WILLED in held_ids:
        willpower_floor = (WEAK_WILLED_FLOOR_MORTAL
                           if (not has_native_pool or CALLOUS in held_ids)
                           else WEAK_WILLED_FLOOR_EXALTED)

    # Holy Mien grants Priest.
    granted_merits: frozenset[str] = frozenset()
    cost_overrides: dict[str, dict[str, int]] = {}
    if HOLY_MIEN in held_ids and PRIEST in ruleset.merits_flaws:
        granted_merits = frozenset({PRIEST})
        cost_overrides = {PRIEST: {"1": 0, "7": 6}}
        effects_from.add(HOLY_MIEN)

    # Damaged Artifact, by the item of each purchase. Two purchases on one item: the
    # higher value wins. A purchase with no item is skipped: validate reports it.
    damaged: dict[str, int] = {}
    for definition, purchase in _held(ruleset, character):
        if definition.id != DAMAGED_ARTIFACT:
            continue
        key = purchase.artifact_key
        points = merit_points(definition, purchase, character.exalt_type,
                              character.caste)
        if key and points > 0:
            damaged[key] = max(damaged.get(key, 0), points)

    return MeritEffects(
        damaged_artifacts=damaged,
        attribute_caps=attribute_caps,
        virtue_cap=virtue_cap,
        essence_start_override=essence_start_override,
        charm_credits_max=charm_credits_max,
        charm_cost_doubled=charm_cost_doubled,
        spell_cost_halved=spell_cost_halved,
        extra_favored_abilities=extra_favored,
        ability_xp_discount=dict(aptitude_abilities),
        favored_virtues=favored_virtues,
        nature_requirement_unmet=tuple(nature_unmet),
        health_levels_granted=tuple(granted_levels),
        health_levels_removed=tuple(removed_levels),
        forfeited_ability_dots=forfeits.get(UNSKILLED, 0),
        forfeited_virtue_dots=callous_dots,
        forfeited_willpower_dots=forfeits.get(WEAK_WILLED, 0),
        forfeited_attribute_dots=_attribute_forfeits(ruleset, character),
        willpower_virtue_margin=CALLOUS_WILLPOWER_MARGIN if callous_active else None,
        willpower_tracks_virtues=callous_active,
        willpower_floor=willpower_floor,
        barred_natures=frozenset({PARAGON_NATURE}) if callous_active else frozenset(),
        bonus_background_dots=bonus_background_dots,
        background_cap_exempt_dots=background_cap_exempt,
        background_caps=background_caps,
        barred_backgrounds=frozenset(barred_backgrounds),
        luck_pool=luck_pool,
        bad_luck_pool=bad_luck_pool,
        limit_max=limit_max,
        permanent_limit_start=permanent_limit_start,
        granted_merits=granted_merits,
        merit_cost_overrides=cost_overrides,
        essence_pool_unlocked=has_native_pool or awareness or mastery or awakened,
        essence_pool_unrestricted=has_native_pool or mastery or awakened,
        no_magical_material_bonus=(MAGICAL_ATTUNEMENT_MORTAL in held_ids
                                   or MAGICAL_ATTUNEMENT_GODBLOODED in held_ids),
        essence_pool_split_thirds=AURA_OF_POWER in held_ids,
        # Awakened Essence substitutes for both mortal Essence Merits. No splat test:
        # `exalt_types` restricts the Merit.
        prerequisites_satisfied=(frozenset({ESSENCE_AWARENESS, ESSENCE_MASTERY})
                                 if awakened else frozenset()),
        essence_cap_override=cap_override,
        breeding_rating_override=breeding_override,
        essence_single_pool=single_pool,
        terrestrial_ma_picks=sum(
            mp.points for mp in character.merits_flaws
            if mp.merit_id == FIGHTER_IN_LIFE and mp.points > 0),
        open_charm_categories=open_categories,
        barred_charm_ids=barred,
        bar_immaculate_charms=bar_immaculate,
        granted_circles=circles,
        bonus_point_grant=min(raw_flaw_points, flaw_cap),
        flaw_points_raw=raw_flaw_points,
        narrative_only=tuple(sorted(
            held_ids - effects_from - {OATHBOUND_MAGIC})),
    )


# --------------------------------------------------------------------------- #
# Cost adjustment (A4). Brigid's Heir has an exemption for each Charm, thus it is a
# function, not a field. Callers pass a cost and get one back.
# --------------------------------------------------------------------------- #

BRIGIDS_HEIR = "mf.brigid-s-heir"
PRODIGY = "mf.prodigy"
# Prodigy tiers by meaning, not price. ⚠ Two tiers cost 2 points, thus a price
# cannot identify the tier.
PRODIGY_GRANTS_FAVORED = ("favored", "favored_aptitude")
PRODIGY_GRANTS_APTITUDE = ("aptitude", "favored_aptitude")
# p.21: subtracted after the rate (costs.ability_step). The bonus die is out of scope.
PRODIGY_APTITUDE_XP_DISCOUNT = 2

# p.21: the maximum Favored Abilities.
PRODIGY_FAVORED_CAP = 5

# Charms exempt from Brigid's Heir, by splat. Cached: the closure walks all
# prerequisites.
_BRIGID_EXEMPT_CACHE: dict[tuple[int, str], frozenset[str]] = {}


def _terrestrial_sorcery_line(ruleset: RuleSet, character: Character) -> frozenset[str]:
    """Return the Charm ids exempt from Brigid's Heir (p.30).

    The initiation Charm is the Charm whose `grants_circle` is Terrestrial. Three
    groups:

      * the initiation Charm,
      * its direct prerequisites,
      * each Charm whose transitive prerequisites include it.

    ⚠ The page names only the second and third groups. The first is an inference
    (human's ruling). Do NOT cite it as precedent. To use the literal reading, remove
    `tcs_id` from the union below.
    """
    key = (id(ruleset), character.exalt_type)
    cached = _BRIGID_EXEMPT_CACHE.get(key)
    if cached is not None:
        return cached

    exempt: set[str] = set()
    from .validate import ox_body_charm_id
    ox = ox_body_charm_id(ruleset, character)
    if ox:
        exempt.add(ox)

    tcs_ids = {cid for cid, charm in ruleset.charms.items()
               if charm.grants_circle == SpellCircle.TERRESTRIAL}
    for tcs_id in tcs_ids:
        exempt.add(tcs_id)                                  # by inference — see above
        tcs = ruleset.charms[tcs_id]
        for group in tcs.prerequisites:                     # AND-of-OR: flatten
            exempt.update(group)
    # Charms whose prerequisite closure reaches an initiation Charm.
    for cid, charm in ruleset.charms.items():
        seen: set[str] = set()
        stack = [p for group in charm.prerequisites for p in group]
        while stack:
            pid = stack.pop()
            if pid in seen:
                continue
            seen.add(pid)
            if pid in tcs_ids:
                exempt.add(cid)
                break
            prereq = ruleset.charms.get(pid)
            if prereq is not None:
                stack.extend(p for group in prereq.prerequisites for p in group)

    result = frozenset(exempt)
    _BRIGID_EXEMPT_CACHE[key] = result
    return result


def adjust_charm_cost(ruleset: RuleSet, character: Character, charm, cost: int) -> int:
    """Return `cost` after a Merit that reprices Charms (Brigid's Heir, p.30)."""
    if not merits_and_flaws_calc(ruleset, character).charm_cost_doubled:
        return cost
    if charm is not None and charm.id in _terrestrial_sorcery_line(ruleset, character):
        return cost
    return cost * 2


def adjust_spell_cost(ruleset: RuleSet, character: Character, cost: int) -> int:
    """Return `cost` after a Merit that reprices spells (Brigid's Heir, p.30).

    ⚠ The page does not say how an odd cost halves. Rounded DOWN. No printed cost is
    odd now.
    """
    if not merits_and_flaws_calc(ruleset, character).spell_cost_halved:
        return cost
    return cost // 2
