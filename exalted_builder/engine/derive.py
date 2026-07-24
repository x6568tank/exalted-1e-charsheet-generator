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


def willpower(character: Character) -> int:
    """Permanent Willpower = the Virtue component + any purchased dots.

    Pre-lock the Virtue component tracks the current two highest Virtues; once
    chargen is locked it is the frozen `wp_virtue_component`, so raising a Virtue
    afterward does not raise Willpower.
    """
    return wp_virtue_component(character) + character.willpower_purchased


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


def _breeding_bonus(character: Character, name: str, table: list[int]) -> int:
    """The additive pool bonus from a Background-derived term (DB Breeding): look up
    the character's rating in `name` and index `table` (clamped to its length). Returns
    0 when the Background is absent or the table is empty."""
    if not name or not table:
        return 0
    rating = max((b.rating for b in character.backgrounds
                  if b.name.strip().lower() == name.strip().lower()), default=0)
    return table[min(rating, len(table) - 1)]


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
    empty tables."""
    spec = ruleset.exalt_for(character.exalt_type).essence
    essence = character.essence_rating
    wp = willpower(character)
    breeding_p = _breeding_bonus(character, spec.breeding_background, spec.breeding_personal)
    breeding_pp = _breeding_bonus(character, spec.breeding_background, spec.breeding_peripheral)
    personal = (essence * spec.personal_essence_coeff
                + wp * spec.personal_willpower_coeff
                + breeding_p)
    peripheral = (essence * spec.peripheral_essence_coeff
                  + wp * spec.peripheral_willpower_coeff
                  + (_peripheral_virtue_term(spec.peripheral_virtue_mode, character.virtues)
                     * spec.peripheral_virtue_coeff)
                  + breeding_pp)
    return personal, peripheral


def health_track(character: Character) -> list[HealthLevelView]:
    """The base wound levels plus any Charm-granted bonus levels, ordered from
    least to most severe (0, -1, -2, -4), with Incapacitated last. Bonus levels
    of equal penalty follow the base levels they share a tier with."""
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
    # Curses remove a level of the given penalty (a base level first).
    for hl in character.health_bonus_levels:
        if hl.removed:
            idx = next((i for i, lv in enumerate(levels) if lv.penalty == hl.penalty), None)
            if idx is not None:
                levels.pop(idx)
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
        willpower=willpower(character),
        wp_from_virtues=wp_virtue_component(character),
        essence_personal=personal,
        essence_peripheral=peripheral,
        health_levels=health_track(character),
        soak=soak(character, ruleset),
    )
