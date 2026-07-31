"""
engine/derive.py — pure derivations: (RuleSet, Character) -> computed traits.

Everything here is a pure function of the rules and a character: no I/O, no
mutation, no UI. These derive the values a sheet shows but a save file does not
store, because they are fully determined by stored traits:

  * Willpower      — sum of the two highest Virtues (frozen at lock so post-
                     creation Virtue gains can't raise it), plus any purchased.
  * Essence pools  — Solar Personal / Peripheral motes.
  * Health track   — the fixed base levels plus Charm-granted bonus levels.

Soak (Exalted 1e core, pp. 231-232):
  * Bashing soak    = Stamina + armour bashing soak.
  * Lethal soak     = floor(Stamina / 2) + armour lethal soak, BUT only magical
                      beings (Exalted, manifested spirits, Fair Folk) add the
                      half-Stamina; mortals rely on armour alone for lethal.
  * Aggravated soak = armour lethal soak only. "A character can never soak
                      aggravated damage with her Stamina, even if she is a
                      magical being." Armour protects as it does against lethal.
The "raw damage can never be reduced below 1 by soak" rule is damage resolution,
not a soak score, so it is not applied here.

The "may not start Willpower above 8 unless two Virtues are >= 4" rule is a
*legality* constraint, not a derivation: it lives in engine.validate. Derivation
reports the raw computed value.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from ..models.character import Armor, Character, Weapon
from ..models.rules import AttributeName, MagicalMaterial, RuleSet, VirtueName

# The fixed Exalted health track: -0/-1/-1/-2/-2/-4/Incapacitated. Penalties for
# the wound-penalty levels; the Incapacitated level has no dice penalty and is
# rendered separately. Charm-granted bonus levels (Ox-Body, etc.) are merged in.
BASE_WOUND_PENALTIES: tuple[int, ...] = (0, -1, -1, -2, -2, -4)


class HealthLevelView(BaseModel):
    """One row of the derived health track. `penalty` is None for the
    Incapacitated level. `source` is '' for the base track or a Charm id for a
    bonus level."""
    penalty: Optional[int]
    incapacitated: bool = False
    source: str = ""


class SoakView(BaseModel):
    """Per-damage-type soak totals plus the natural/armour breakdown a sheet
    shows. Aggravated has no natural component by rule."""
    bashing: int
    lethal: int
    aggravated: int
    natural_bashing: int           # Stamina
    natural_lethal: int            # floor(Stamina/2), magical beings only
    armor_bashing: int
    armor_lethal: int


class DerivedTraits(BaseModel):
    """Computed, non-stored traits for display and for the engine to reason
    about."""
    willpower: int                 # total permanent Willpower
    wp_from_virtues: int           # the two-highest-Virtues component used
    essence_personal: int
    essence_peripheral: int
    # The two pools are ONE pool, all of it Peripheral (Beacon of Power). Personal is
    # then 0 by rule rather than by arithmetic, which a sheet must be able to tell
    # apart: "Personal 0" alone reads as a bug.
    essence_single_pool: bool
    health_levels: list[HealthLevelView]
    soak: SoakView


# --- Clarity (Alchemical, CH2 p.69-71) -------------------------------------- #
# The Alchemical replacement for Limit. It has two halves that behave differently,
# and only one of them belongs here:
#
#   PERMANENT Clarity is fully determined by stored traits — one dot per dot of
#   Essence above 5, plus one for each installed Charm that grants it (p.69). It is
#   therefore DERIVED, exactly like the health track or the Essence pools, and never
#   stored. That also makes p.70's "removing these conditions immediately removes the
#   appropriate amount of permanent Clarity" free: uninstall the Charm or drop the
#   Essence and the dots go with it, with no bookkeeping.
#
#   TEMPORARY Clarity is pure Storyteller adjudication (suppressing Virtues, weeks
#   without human contact, Compassion rolls after a scene). It lives on PlayState with
#   Limit and Renown, and nothing here computes it.
#
# The effects table below is DISPLAY ONLY. The dice penalties and bonuses are reported
# as printed text so a sheet can show which band applies; nothing applies them to a
# roll, the same scope line combat/attack derivation sits behind.

CLARITY_MAX = 10                   # "cannot ever exceed 10 under any circumstances"

# (upper bound of band, label, printed effects) — p.70-71, in ascending order.
CLARITY_BANDS: tuple[tuple[int, str, str], ...] = (
    (2, "0-2",
     "No sign of emotional dissociation or alien thought. As pleasant to deal with "
     "as her Social Attributes and Abilities allow."),
    (4, "3-4",
     "Colder and more callous. -1 die to Social rolls (except intimidation) with "
     "sentient/feeling beings, +1 die with Autochthonian deities, automata and "
     "Alchemicals of equal or greater Clarity; -1 die to all Compassion rolls."),
    (7, "5-7",
     "Notably inhuman: clipped, laconic, efficient. The Social penalty/bonus and the "
     "Compassion penalty rise to 2 dice."),
    (9, "8-9",
     "Humanity is a distant memory; courtesy is simulated without feeling. Social and "
     "Compassion penalties/bonuses rise to 3 dice. +1 die to Mental Attribute or "
     "Temperance rolls involving memory recall, analytical deduction or dispassionate "
     "self-control, as the Storyteller allows."),
    (10, "10",
     "Aloof and utterly alien; amoral though not malicious. Social penalty/bonus rises "
     "to 4 dice and she automatically FAILS all Compassion rolls. +2 dice to the "
     "cognitive and Temperance rolls described for Clarity 8-9."),
)


class ClarityView(BaseModel):
    """The Clarity picture for a sheet: the derived permanent half with its sources
    itemised, the tracked temporary half, and the band the total falls in."""
    permanent: int
    temporary: int
    total: int                     # permanent + temporary, capped at CLARITY_MAX
    sources: list[tuple[str, int]]  # (label, dots) making up `permanent`
    band: str                      # "5-7"
    effects: str                   # the printed effects for that band

    @property
    def capped(self) -> bool:
        """True when permanent + temporary was clipped by the hard 10 ceiling."""
        return self.permanent + self.temporary > CLARITY_MAX


def clarity_band(total: int) -> tuple[str, str]:
    """The (label, effects) band `total` falls in (p.70-71)."""
    for bound, label, effects in CLARITY_BANDS:
        if total <= bound:
            return label, effects
    return CLARITY_BANDS[-1][1], CLARITY_BANDS[-1][2]


def uses_clarity(ruleset: RuleSet, character: Character) -> bool:
    """Whether Clarity applies to this character. Data-driven: a splat uses Clarity if
    any Charm it can hold grants permanent Clarity would be too loose, so this asks the
    ExaltDefinition instead — see `ExaltDefinition.clarity`."""
    exalt = ruleset.exalt_for(character.exalt_type)
    return bool(exalt and exalt.clarity)


def limit_label(ruleset: RuleSet, character: Character) -> str:
    """What this character's splat calls its Limit track — "Paradox" for a Sidereal
    (p.253), "Limit" for everyone else. A rename only: the mechanic, the 0-10 range
    and the break threshold are identical, which is why this is one string on the
    ExaltDefinition rather than a second track."""
    exalt = ruleset.exalt_for(character.exalt_type)
    return (exalt.limit_label if exalt and exalt.limit_label else "Limit")


def limit_max(ruleset: RuleSet, character: Character) -> int:
    """The maximum of this character's Limit / Paradox / Resonance track.

    Ordinarily the constant 10 — the triage's ruling 5 is that this is a constant rather
    than something derived, so there is exactly one Flaw that moves it: Greater Curse
    "reduces their maximum Limit pool by one dot per point invested in the Flaw, to a
    maximum reduction of five dots" (p.40), which makes Limit Break arrive sooner.

    Play-state (decision 0006): read by the tracker and the sheet, never by chargen
    validation or the XP audit.
    """
    from . import merits                                   # merits imports validate
    effects = merits.merits_and_flaws_calc(ruleset, character)
    return merits.LIMIT_MAX if effects.limit_max is None else effects.limit_max


def permanent_limit_cap(ruleset: RuleSet, character: Character) -> int:
    """The ceiling on PERMANENT Resonance — "Characters may not have a permanent
    Resonance higher than their Essence" (p.41). 0 for a character without the Flaw,
    which is also what the field should read for them."""
    from . import merits
    effects = merits.merits_and_flaws_calc(ruleset, character)
    if effects.permanent_limit_start is None:
        return 0
    return character.essence_rating


def permanent_limit_start(ruleset: RuleSet, character: Character) -> int:
    """The permanent Resonance the character BEGAN play with, bought with Death's Taint
    ("Characters who actually start with this greater taint add one additional bonus
    point per dot", p.41). 0 without the Flaw, and 0 with its base four-point version.

    Distinct from `Character.limit_permanent`, which is where it stands NOW — the Flaw
    buys a starting rating, and play moves it from there through the XP ledger."""
    from . import merits
    effects = merits.merits_and_flaws_calc(ruleset, character)
    return effects.permanent_limit_start or 0


def luck_pools(ruleset: RuleSet, character: Character) -> tuple[int, int]:
    """(luck, bad luck) — the two pools Lucky and Unlucky create, which exist only
    because those entries do. A character may hold both: "characters may be
    simultaneously Lucky and Unlucky" (p.39), and the two do not cancel here because
    the player and the Storyteller spend them independently.

    SPENDING them is rerolling, which is decision 0009 and stays out. These are
    counters for the tracker to display and nothing more."""
    from . import merits
    effects = merits.merits_and_flaws_calc(ruleset, character)
    return effects.luck_pool, effects.bad_luck_pool


def has_virtue_flaw(ruleset: RuleSet, character: Character) -> bool:
    """Whether this character's splat has a Virtue Flaw at all. False for the
    Dragon-Blooded, Sidereals and Alchemicals — see `ExaltDefinition.has_virtue_flaw`.
    Note this is NOT the same question as whether the splat has a Limit track: a
    Sidereal has Paradox but no flawed Virtue."""
    exalt = ruleset.exalt_for(character.exalt_type)
    return bool(exalt and exalt.has_virtue_flaw)


def permanent_clarity(ruleset: RuleSet, character: Character) -> list[tuple[str, int]]:
    """The itemised sources of permanent Clarity (p.69): one dot per dot of Essence
    above 5, plus one per installed Charm that grants it. Reads the character's LIVE
    installed Charms, so a vat refit that sheds such a Charm sheds its dots too."""
    sources: list[tuple[str, int]] = []
    over = max(0, character.essence_rating - 5)
    if over:
        sources.append((f"Essence {character.essence_rating}", over))
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm is not None and charm.permanent_clarity:
            sources.append((charm.name, charm.permanent_clarity))
    return sources


def clarity(ruleset: RuleSet, character: Character) -> ClarityView:
    """The full Clarity view: derived permanent + tracked temporary, capped at 10."""
    sources = permanent_clarity(ruleset, character)
    perm = sum(dots for _label, dots in sources)
    temp = character.play.clarity_temporary if character.play is not None else 0
    total = min(CLARITY_MAX, perm + temp)
    label, effects = clarity_band(total)
    return ClarityView(permanent=perm, temporary=temp, total=total,
                       sources=sources, band=label, effects=effects)


def two_highest_virtues(virtues: dict[VirtueName, int]) -> int:
    """Sum of the two highest Virtue ratings — the Willpower component at chargen."""
    ordered = sorted(virtues.values(), reverse=True)
    return sum(ordered[:2])


def willpower(character: Character, ruleset: Optional[RuleSet] = None) -> int:
    """Permanent Willpower = the Virtue component + purchased dots − any forfeited.

    Pre-lock the Virtue component tracks the current two highest Virtues; once
    chargen is locked it is the frozen `wp_virtue_component`, so raising a Virtue
    afterward does not raise Willpower.

    `ruleset` is optional and only ever subtracts: the Weak-Willed Flaw sells permanent
    Willpower dots for bonus points, and without a RuleSet there is no way to know a
    Flaw is held. Every caller that has one should pass it — the same optional-ruleset
    shape `soak` already uses. Floored at zero; the floors that actually apply (4 for
    the Exalted, 2 otherwise) are validated at chargen rather than clamped here, so a
    sheet below them reports rather than silently corrects.
    """
    total = wp_virtue_component(character) + character.willpower_purchased
    if ruleset is not None:
        from . import merits
        total -= merits.merits_and_flaws_calc(ruleset, character).forfeited_willpower_dots
    return max(0, total)


def wp_virtue_component(character: Character) -> int:
    if character.wp_virtue_component is not None:
        return character.wp_virtue_component
    return two_highest_virtues(character.virtues)


def _peripheral_virtue_term(mode: str, virtues: dict[VirtueName, int]) -> int:
    """The Virtue contribution to the Peripheral pool for a splat: all four Virtues
    (Solar), the two highest only (Dragon-Blooded, p.152), the single highest only
    (Lunar, p.91 — scaled separately by EssencePoolSpec.peripheral_virtue_coeff), or
    none."""
    if mode == "all":
        return sum(virtues.values())
    if mode == "two_highest":
        return two_highest_virtues(virtues)
    if mode == "highest":
        return max(virtues.values(), default=0)
    return 0


def _named_virtue_term(spec, virtues: dict[VirtueName, int]) -> int:
    """A single NAMED Virtue added flat to the Personal pool — the "+ Conviction" in
    the unlocked mortal's pool (PG p.114). Zero for every splat that names none, which
    is all of them; an unrecognised name contributes nothing rather than raising, so a
    typo in the data degrades to a wrong number rather than a crash the loader would
    not have caught."""
    if not spec.personal_named_virtue:
        return 0
    try:
        virtue = VirtueName(spec.personal_named_virtue)
    except ValueError:
        return 0
    return virtues.get(virtue, 0) * spec.personal_named_virtue_coeff


def _breeding_rating(character: Character, name: str, override: Optional[int]) -> int:
    """The character's effective rating in the pool-feeding Background, which a Merit
    may raise above the one they bought (Legendary Breeding). `override` is
    MeritEffects.breeding_rating_override, and wins outright when set."""
    if override is not None:
        return override
    return max((b.rating for b in character.backgrounds
                if b.name.strip().lower() == name.strip().lower()), default=0)


def _breeding_bonus(character: Character, name: str, table: list[int],
                    override: Optional[int] = None) -> int:
    """The additive pool bonus from a Background-derived term (DB Breeding): look up
    the character's rating in `name` and index `table` (clamped to its length). Returns
    0 when the Background is absent or the table is empty."""
    if not name or not table:
        return 0
    return table[min(_breeding_rating(character, name, override), len(table) - 1)]


def essence_pool_is_merged(ruleset: RuleSet, character: Character) -> bool:
    """Are the two Essence pools a single Peripheral pool (Beacon of Power)? Separate
    from `essence_pools` because that returns motes and this is about their SHAPE — a
    sheet showing "Personal 0" needs to know whether it is reporting a rule or a
    character with no Essence at all."""
    from . import merits as _merits
    return _merits.merits_and_flaws_calc(ruleset, character).essence_single_pool


def essence_pools(ruleset: RuleSet, character: Character) -> tuple[int, int]:
    """(personal, peripheral) motes, from the character's Exalt-type formula
    (RuleSet.exalt_for → EssencePoolSpec), a pure data lookup rather than a per-splat
    branch.

      * Solar (core p.104):    Personal = Essence×3 + Willpower;
                               Peripheral = Essence×7 + Willpower + ΣVirtues.
      * Dragon-Blooded (p.152): Personal = Essence + Willpower (+Breeding);
                               Peripheral = Essence×4 + Willpower + (two highest
                               Virtues) (+Breeding).
      * Lunar (p.91):          Personal = Essence + Willpower×2;
                               Peripheral = Essence×4 + Willpower×2 + (highest
                               Virtue × 4).

    The Breeding term (p.158-159) is a flat per-rating bonus added to BOTH pools,
    keyed off the character's Breeding Background rating; splats without it carry
    empty tables.

    Merits reshape all three of those parts (A5), and never by naming themselves here:
    they can UNLOCK a pool a splat does not have (mortals: "they lack an Essence pool,
    either Peripheral or Personal", PG p.114 — `ExaltDefinition.unlocked_essence`
    replaces the empty default spec), raise the effective Breeding rating, and MERGE the
    two pools into one Peripheral pool. Which Merits do any of that is engine.merits'
    business, not this function's — see decision 0011."""
    # Import locally: engine.merits imports the models only, but keeping this out
    # of the module header avoids a derive <-> merits cycle if merits ever needs
    # a derivation of its own.
    from . import merits as _merits
    effects = _merits.merits_and_flaws_calc(ruleset, character)
    exalt = ruleset.exalt_for(character.exalt_type)
    spec = exalt.essence
    if exalt.unlocked_essence is not None and effects.essence_pool_unlocked:
        spec = exalt.unlocked_essence
    essence = character.essence_rating
    wp = willpower(character, ruleset)
    override = effects.breeding_rating_override
    breeding_p = _breeding_bonus(character, spec.breeding_background,
                                 spec.breeding_personal, override)
    breeding_pp = _breeding_bonus(character, spec.breeding_background,
                                  spec.breeding_peripheral, override)
    personal = (essence * spec.personal_essence_coeff
                + wp * spec.personal_willpower_coeff
                + _named_virtue_term(spec, character.virtues)
                + (_peripheral_virtue_term(spec.personal_virtue_mode, character.virtues)
                   * spec.personal_virtue_coeff)
                + breeding_p)
    peripheral = (essence * spec.peripheral_essence_coeff
                  + wp * spec.peripheral_willpower_coeff
                  + (_peripheral_virtue_term(spec.peripheral_virtue_mode, character.virtues)
                     * spec.peripheral_virtue_coeff)
                  + breeding_pp)
    if effects.essence_single_pool:
        # "a single Essence pool equal to the sum of their Personal and Peripheral
        # Essence, all of which is considered Peripheral" (p.41). Merged AFTER both
        # are computed, so every term above still contributes exactly what it did.
        peripheral += personal
        personal = 0
    return personal, peripheral


def health_track(character: Character,
                 ruleset: Optional[RuleSet] = None) -> list[HealthLevelView]:
    """The base wound levels plus any Charm-granted bonus levels, ordered from
    least to most severe (0, -1, -2, -4), with Incapacitated last. Bonus levels
    of equal penalty follow the base levels they share a tier with.

    `ruleset` is optional and only Merits & Flaws need it: Large Size grants levels and
    Small takes one away, the first sources of a health level in this build that are not
    Charms. Without a RuleSet there is no way to know a Merit is held, so the track is
    the Charm-only one — the same optional-ruleset shape `soak` and `willpower` use.
    """
    levels = [HealthLevelView(penalty=p) for p in BASE_WOUND_PENALTIES]
    levels += [
        HealthLevelView(penalty=hl.penalty, source=hl.source_charm)
        for hl in character.health_bonus_levels if not hl.removed
    ]
    # Ox-Body Technique purchases: each chosen package's levels (stored inline).
    levels += [
        HealthLevelView(penalty=p, source="Ox-Body Technique")
        for purchase in character.ox_body for p in purchase.health_levels
    ]
    effects = None
    if ruleset is not None:
        from . import merits
        effects = merits.merits_and_flaws_calc(ruleset, character)
        levels += [HealthLevelView(penalty=penalty, source=label)
                   for penalty, label in effects.health_levels_granted]

    def _remove(penalty: int) -> None:
        """Drop one level of this penalty, base first — base levels lead the list, so
        first-match is what 'base first' means here."""
        idx = next((i for i, lv in enumerate(levels) if lv.penalty == penalty), None)
        if idx is not None:
            levels.pop(idx)

    # Curses remove a level of the given penalty (a base level first).
    for hl in character.health_bonus_levels:
        if hl.removed:
            _remove(hl.penalty)
    # Flaws do the same — Small "costs her one -1 health level" (p.32).
    for penalty in (effects.health_levels_removed if effects else ()):
        _remove(penalty)
    # Stable sort by severity: 0 first (highest penalty value), -4 last.
    levels.sort(key=lambda lv: lv.penalty, reverse=True)
    levels.append(HealthLevelView(penalty=None, incapacitated=True))
    return levels


def applied_material(
    ruleset: RuleSet, character: Character, item: Weapon | Armor
) -> Optional[MagicalMaterial]:
    """The magical material whose bonus applies to `item` for this character, or
    None. A material's bonus applies only when the item names a known material AND
    that material resonates with the character's Exalt type (core p.341): an
    orichalcum daiklave aids a Solar, but a jade one does not."""
    key = getattr(item, "material", "")
    if not key:
        return None
    mat = ruleset.material_catalog.get(key)
    if mat is None or mat.exalt_type != character.exalt_type:
        return None
    return mat


def effective_weapon(ruleset: RuleSet, character: Character, weapon: Weapon) -> Weapon:
    """A copy of `weapon` with its magical-material bonus folded into the stats —
    applied only when the wielder's Exalt type matches the material (p.341).
    Mundane weapons and non-matching wielders return an unmodified copy."""
    mat = applied_material(ruleset, character, weapon)
    if mat is None:
        return weapon.model_copy()
    return weapon.model_copy(update={
        "speed": weapon.speed + mat.weapon_speed,
        "accuracy": weapon.accuracy + mat.weapon_accuracy,
        "damage": weapon.damage + mat.weapon_damage,
        "defense": weapon.defense + mat.weapon_defense,
    })


def effective_armor(ruleset: RuleSet, character: Character, armor: Armor) -> Armor:
    """A copy of `armor` with its magical-material bonus folded in, gated on the
    wearer's Exalt type matching the material (p.341)."""
    mat = applied_material(ruleset, character, armor)
    if mat is None:
        return armor.model_copy()
    return armor.model_copy(update={
        "soak_lethal": armor.soak_lethal + mat.armor_soak_lethal,
        "soak_bashing": armor.soak_bashing + mat.armor_soak_bashing,
        "mobility_penalty": 0 if mat.armor_negate_mobility_penalty else armor.mobility_penalty,
        "fatigue": 0 if mat.armor_negate_fatigue else armor.fatigue,
    })


def soak(character: Character, ruleset: Optional[RuleSet] = None) -> SoakView:
    """Per-damage-type soak (bashing / lethal / aggravated), Exalted 1e pp.231-232.

    Armour soak is summed across all worn pieces (the model permits several; the
    common case is one suit). Only magical beings add half-Stamina to lethal soak;
    aggravated never benefits from Stamina. Mortals (exalt_type "Mortal") get no
    Stamina contribution to lethal. When `ruleset` is given, magical-material
    bonuses are folded into the armour soak via effective_armor (Exalt-gated)."""
    stamina = character.attributes[AttributeName.STAMINA]
    pieces = (
        [effective_armor(ruleset, character, a) for a in character.armor]
        if ruleset is not None else character.armor
    )
    armor_bashing = sum(a.soak_bashing for a in pieces)
    armor_lethal = sum(a.soak_lethal for a in pieces)

    magical_being = character.exalt_type != "Mortal"
    natural_bashing = stamina
    natural_lethal = stamina // 2 if magical_being else 0

    return SoakView(
        bashing=natural_bashing + armor_bashing,
        lethal=natural_lethal + armor_lethal,
        aggravated=armor_lethal,           # armour only; never Stamina
        natural_bashing=natural_bashing,
        natural_lethal=natural_lethal,
        armor_bashing=armor_bashing,
        armor_lethal=armor_lethal,
    )


def derive(ruleset: RuleSet, character: Character) -> DerivedTraits:
    """Bundle the implemented derivations."""
    personal, peripheral = essence_pools(ruleset, character)
    return DerivedTraits(
        willpower=willpower(character, ruleset),
        wp_from_virtues=wp_virtue_component(character),
        essence_personal=personal,
        essence_peripheral=peripheral,
        essence_single_pool=essence_pool_is_merged(ruleset, character),
        health_levels=health_track(character, ruleset),
        soak=soak(character, ruleset),
    )
