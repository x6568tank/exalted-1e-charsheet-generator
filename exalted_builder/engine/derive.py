"""
engine/derive.py — pure derivations: (RuleSet, Character) -> computed traits.

Each function is a pure function of the rules and a character: no I/O, no mutation,
no UI. The results are values that the sheet shows and the save does not store:

  * Willpower      — sum of the two highest Virtues (frozen at lock, decision
                     0005), plus the purchased dots.
  * Essence pools  — Personal / Peripheral motes.
  * Health track   — the base levels plus the bonus levels.

Soak (Exalted 1e core, pp. 231-232):
  * Bashing soak    = Stamina + armor bashing soak.
  * Lethal soak     = floor(Stamina / 2) + armor lethal soak. Only magical beings
                      add the half-Stamina.
  * Aggravated soak = armor lethal soak only. Stamina never soaks aggravated.
The "minimum 1 damage" rule is damage resolution. It is not applied here.

The starting Willpower cap is legality, in engine.validate. Derivation returns the
raw value.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from ..models.character import Armor, Character, Weapon
from ..models.rules import AttributeName, MagicalMaterial, RuleSet, VirtueName

# The base health track: -0/-1/-1/-2/-2/-4/Incapacitated. Incapacitated has no
# penalty and renders separately. Bonus levels are merged in.
BASE_WOUND_PENALTIES: tuple[int, ...] = (0, -1, -1, -2, -2, -4)


class HealthLevelView(BaseModel):
    """One row of the derived health track. `penalty` is None for Incapacitated.
    `source` is '' for a base level or a Charm id for a bonus level."""
    penalty: Optional[int]
    incapacitated: bool = False
    source: str = ""


class SoakView(BaseModel):
    """The soak totals by damage type, with the natural and armor parts.
    Aggravated has no natural part."""
    bashing: int
    lethal: int
    aggravated: int
    natural_bashing: int           # Stamina
    natural_lethal: int            # floor(Stamina/2), magical beings only
    armor_bashing: int
    armor_lethal: int


class DerivedTraits(BaseModel):
    """Computed traits for display and for the engine."""
    willpower: int                 # total permanent Willpower
    wp_from_virtues: int           # the two-highest-Virtues component used
    essence_personal: int
    essence_peripheral: int
    # The pools are one Peripheral pool (Beacon of Power). The sheet needs the flag:
    # "Personal 0" alone looks like a defect.
    essence_single_pool: bool
    # PG p.120: motes free of a Willpower roll. None = all. See
    # `essence_freely_accessible`. It does not reduce the totals.
    essence_free: Optional[int]
    health_levels: list[HealthLevelView]
    soak: SoakView


# --- Clarity (Alchemical, CH2 p.69-71) -------------------------------------- #
# Permanent Clarity: one dot per Essence dot above 5, plus one for each installed
# Charm that grants it (p.69). Derived, not stored: removal is automatic (p.70).
#
# Temporary Clarity: set by the Storyteller, on PlayState.
#
# The effects table is display text only. Nothing applies it to a roll.

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
    """The Clarity of a sheet: the permanent sources, the temporary value, and the
    band of the total."""
    permanent: int
    temporary: int
    total: int                     # permanent + temporary, capped at CLARITY_MAX
    sources: list[tuple[str, int]]  # (label, dots) making up `permanent`
    band: str                      # "5-7"
    effects: str                   # the printed effects for that band

    @property
    def capped(self) -> bool:
        """Return True if CLARITY_MAX clipped permanent + temporary."""
        return self.permanent + self.temporary > CLARITY_MAX


def clarity_band(total: int) -> tuple[str, str]:
    """Return the (label, effects) band of `total` (p.70-71)."""
    for bound, label, effects in CLARITY_BANDS:
        if total <= bound:
            return label, effects
    return CLARITY_BANDS[-1][1], CLARITY_BANDS[-1][2]


def uses_clarity(ruleset: RuleSet, character: Character) -> bool:
    """Return `ExaltDefinition.clarity`. ⚠ Read the splat flag. Do not infer it
    from the Charms."""
    exalt = ruleset.exalt_for(character.exalt_type)
    return bool(exalt and exalt.clarity)


def limit_label(ruleset: RuleSet, character: Character) -> str:
    """Return the name of the Limit track of the splat (p.253). Display only."""
    exalt = ruleset.exalt_for(character.exalt_type)
    return (exalt.limit_label if exalt and exalt.limit_label else "Limit")


def limit_max(ruleset: RuleSet, character: Character) -> int:
    """Return the maximum of the Limit / Paradox / Resonance track.

    The base is the constant 10. Two values subtract from it:

    * Greater Curse (p.40).
    * **Permanent Resonance uses track space** (p.41, human's ruling): 2 permanent
      gives a temporary maximum of 8.

    The floor is 0. Play state (decision 0006).
    """
    from . import merits                                   # merits imports validate
    effects = merits.merits_and_flaws_calc(ruleset, character)
    base = merits.LIMIT_MAX if effects.limit_max is None else effects.limit_max
    return max(0, base - character.limit_permanent)


def permanent_limit_cap(ruleset: RuleSet, character: Character) -> int:
    """Return the ceiling on permanent Resonance: Essence (p.41). 0 without the
    Flaw."""
    from . import merits
    effects = merits.merits_and_flaws_calc(ruleset, character)
    if effects.permanent_limit_start is None:
        return 0
    return character.essence_rating


def permanent_limit_start(ruleset: RuleSet, character: Character) -> int:
    """Return the permanent Resonance at the start of play, from Death's Taint (p.41).
    0 without the Flaw.

    `Character.limit_permanent` is the current value."""
    from . import merits
    effects = merits.merits_and_flaws_calc(ruleset, character)
    return effects.permanent_limit_start or 0


def luck_pools(ruleset: RuleSet, character: Character) -> tuple[int, int]:
    """Return (luck, bad luck) from Lucky and Unlucky (p.39). They do not cancel.
    Counters only: spending is dice (decision 0009)."""
    from . import merits
    effects = merits.merits_and_flaws_calc(ruleset, character)
    return effects.luck_pool, effects.bad_luck_pool


def has_virtue_flaw(ruleset: RuleSet, character: Character) -> bool:
    """Return `ExaltDefinition.has_virtue_flaw`. ⚠ Not the same as a Limit track:
    a Sidereal has Paradox and no Virtue Flaw."""
    exalt = ruleset.exalt_for(character.exalt_type)
    return bool(exalt and exalt.has_virtue_flaw)


def permanent_clarity(ruleset: RuleSet, character: Character) -> list[tuple[str, int]]:
    """Return the sources of permanent Clarity (p.69). Reads the LIVE installed
    Charms."""
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
    """Return the ClarityView: permanent + temporary, capped at 10."""
    sources = permanent_clarity(ruleset, character)
    perm = sum(dots for _label, dots in sources)
    temp = character.play.clarity_temporary if character.play is not None else 0
    total = min(CLARITY_MAX, perm + temp)
    label, effects = clarity_band(total)
    return ClarityView(permanent=perm, temporary=temp, total=total,
                       sources=sources, band=label, effects=effects)


def two_highest_virtues(virtues: dict[VirtueName, int]) -> int:
    """Return the sum of the two highest Virtue ratings."""
    ordered = sorted(virtues.values(), reverse=True)
    return sum(ordered[:2])


def willpower(character: Character, ruleset: Optional[RuleSet] = None) -> int:
    """Return permanent Willpower: the Virtue component + purchased - forfeited.

    Before the lock the Virtue component is the two highest Virtues. After the lock it
    is `wp_virtue_component` (decision 0005). Callous is the exception: the component
    follows the Virtues.

    ⚠ Without `ruleset` the result is incorrect for Callous and Weak-Willed. Pass it.
    The floor is 0. Validate checks the chargen floors.
    """
    virtue_part = wp_virtue_component(character)
    forfeited = 0
    if ruleset is not None:
        from . import merits
        effects = merits.merits_and_flaws_calc(ruleset, character)
        forfeited = effects.forfeited_willpower_dots
        # Callous: the exception to decision 0005.
        if effects.willpower_tracks_virtues:
            virtue_part = two_highest_virtues(character.virtues)
    return max(0, virtue_part + character.willpower_purchased - forfeited)


def wp_virtue_component(character: Character) -> int:
    if character.wp_virtue_component is not None:
        return character.wp_virtue_component
    return two_highest_virtues(character.virtues)


def _peripheral_virtue_term(mode: str, virtues: dict[VirtueName, int]) -> int:
    """Return the Virtue term of the Peripheral pool: all four Virtues, the two
    highest (p.152), the highest (p.91), or none."""
    if mode == "all":
        return sum(virtues.values())
    if mode == "two_highest":
        return two_highest_virtues(virtues)
    if mode == "highest":
        return max(virtues.values(), default=0)
    return 0


def _named_virtue_term(spec, virtues: dict[VirtueName, int]) -> int:
    """Return the NAMED Virtues added flat to the Personal pool (PG p.114, PG p.177).
    The sum of `personal_named_virtue` and `personal_named_virtues`, each times
    `personal_named_virtue_coeff`. An unknown name adds 0."""
    names = []
    if spec.personal_named_virtue:
        names.append(spec.personal_named_virtue)
    names.extend(spec.personal_named_virtues)
    total = 0
    for name in names:
        try:
            virtue = VirtueName(name)
        except ValueError:
            continue
        total += virtues.get(virtue, 0) * spec.personal_named_virtue_coeff
    return total


def _breeding_rating(character: Character, name: str, override: Optional[int]) -> int:
    """Return the effective rating of the pool Background. `override`
    (MeritEffects.breeding_rating_override) wins if set."""
    if override is not None:
        return override
    return max((b.rating for b in character.backgrounds
                if b.name.strip().lower() == name.strip().lower()), default=0)


def _breeding_bonus(character: Character, name: str, table: list[int],
                    override: Optional[int] = None) -> int:
    """Return the pool bonus of the Background `name`: `table` indexed by the rating,
    clamped to its length. 0 if the Background is absent or the table is empty."""
    if not name or not table:
        return 0
    return table[min(_breeding_rating(character, name, override), len(table) - 1)]


def essence_pool_is_merged(ruleset: RuleSet, character: Character) -> bool:
    """Return True if the two pools are one Peripheral pool.

    Three sources, one read site: Beacon of Power (p.41), the splat (E:Ab p.126,
    PG p.66), and Aura of Power, which splits (PG p.67). Ask here. Do not read a
    source directly.

    ⚠ The split is checked FIRST. A God-Blooded `single_essence_pool` is True, thus a
    splat check first disables Aura of Power.
    """
    from . import merits as _merits
    effects = _merits.merits_and_flaws_calc(ruleset, character)
    if effects.essence_pool_split_thirds:
        return False
    if ruleset.exalt_for(character.exalt_type).single_essence_pool:
        return True
    return effects.essence_single_pool


def essence_freely_accessible(ruleset: RuleSet, character: Character) -> Optional[int]:
    """Return the motes that the character can draw with no Willpower roll. Return
    None if the full pool is free.

    PG p.120: Essence Awareness gives one third. Essence Mastery (p.121) or a native
    pool gives all. The roll is not modelled (decision 0009). The value is a share of
    the WHOLE pool. It does not reduce the totals.

    ⚠ The page gives no rounding. Floor is used. Confirm with the rules authority.
    """
    from . import merits as _merits
    if _merits.merits_and_flaws_calc(ruleset, character).essence_pool_unrestricted:
        return None
    personal, peripheral = essence_pools(ruleset, character)
    return (personal + peripheral) // 3


def _heritage_traits(ruleset: RuleSet, character: Character):
    """Return `CasteDefinition.heritage_traits` of the character, or None (PG p.66)."""
    caste = ruleset.castes.get(character.caste)
    return caste.heritage_traits if caste is not None else None


def essence_pools(ruleset: RuleSet, character: Character) -> tuple[int, int]:
    """Return (personal, peripheral) motes from the EssencePoolSpec of the splat
    (RuleSet.exalt_for).

      * Solar (core p.104):    Personal = Essence×3 + Willpower;
                               Peripheral = Essence×7 + Willpower + ΣVirtues.
      * Dragon-Blooded (p.152): Personal = Essence + Willpower (+Breeding);
                               Peripheral = Essence×4 + Willpower + (two highest
                               Virtues) (+Breeding).
      * Lunar (p.91):          Personal = Essence + Willpower×2;
                               Peripheral = Essence×4 + Willpower×2 + (highest
                               Virtue × 4).

    Breeding (p.158-159) adds to both pools.

    Merits can unlock a pool (PG p.114: `ExaltDefinition.unlocked_essence`), raise
    the Breeding rating, and merge the pools (decision 0011)."""
    # A local import prevents a derive <-> merits cycle.
    from . import merits as _merits
    effects = _merits.merits_and_flaws_calc(ruleset, character)
    exalt = ruleset.exalt_for(character.exalt_type)
    spec = exalt.essence
    if effects.essence_pool_unlocked:
        heritage = _heritage_traits(ruleset, character)
        if heritage is not None and heritage.unlocked_essence is not None:
            # PG p.66: the formula of the heritage wins.
            spec = heritage.unlocked_essence
        elif exalt.unlocked_essence is not None:
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
    if essence_pool_is_merged(ruleset, character):
        # p.41: merged AFTER both pools are calculated.
        #
        # ⚠ Ask `essence_pool_is_merged`, not `effects`: a ghost's pool is merged by
        # the SPLAT. The Merit field gives the incorrect motes for a ghost.
        peripheral += personal
        personal = 0
    elif effects.essence_pool_split_thirds:
        # Aura of Power (PG p.67): one third Personal (rounded down), the remainder
        # Peripheral.
        #
        # ⚠ Split the TOTAL. A God-Blooded pool is all Personal: 31 becomes 10 + 21.
        total = personal + peripheral
        personal = total // 3
        peripheral = total - personal
    return personal, peripheral


def attunement_cost(ruleset: RuleSet, character: Character, item) -> int:
    """Return the motes that `item` costs THIS wielder to keep attuned.

    The printed cost, DOUBLED if the item's material belongs to a different Exalt type
    (human's ruling; `images/Dragonblooded/Aspects/Earth/CH 6 - Miracles of
    Pasaip.md`).

    `item` is an `artifacts.ArtifactItem`, not a stored row.

    ⚠ Not the same as `applied_material(...) is None`, which is also None for a
    MUNDANE item. A mundane item never doubles.

    ⚠ A character type with no resonant material (mortal, God-Blooded, ghost) pays
    the PRINTED cost (PG p.120, PG p.66; human's ruling).

    ⚠ Reads the CATALOGUE, not a Merit id (decision 0011).
    """
    if item.attunement <= 0:
        return 0
    mat = ruleset.material_catalog.get(item.material or "")
    if mat is None or mat.exalt_type == character.exalt_type:
        return item.attunement
    if not _has_a_resonant_material(ruleset, character):
        return item.attunement
    return item.attunement * 2


def _has_a_resonant_material(ruleset: RuleSet, character: Character) -> bool:
    """Return True if a magical material resonates with the Exalt type (core p.341)."""
    return any(m.exalt_type == character.exalt_type
               for m in ruleset.material_catalog.values())


def committed_attunement(ruleset: RuleSet, character: Character) -> dict:
    """Return the motes committed to attuned artifacts: `{"personal": n,
    "peripheral": n}`.

    Uses `artifacts.artifact_items`, thus a linked artifact and weapon row count one
    time, as for the p.131 budget. An unattuned item adds 0.

    ⚠ `Weapon.quantity` is NOT a multiplier (decision 0008). `ArtifactItem` does not
    carry it.

    ⚠ **A commitment to a pool that the character does not HAVE moves to the pool
    that the character has** (core pp.147-148). Examples: a merged pool (personal 0,
    p.41); a mortal (peripheral 0, and `attuned_pool` defaults to "peripheral").
    If neither pool exists, the cost stays on the stored pool.
    """
    from . import artifacts as artifactsmod

    out = {"personal": 0, "peripheral": 0}
    caps = dict(zip(("personal", "peripheral"), essence_pools(ruleset, character)))
    for item in artifactsmod.artifact_items(character):
        if not item.attuned:
            continue
        cost = attunement_cost(ruleset, character, item)
        if not cost:
            continue
        pool = item.attuned_pool if item.attuned_pool in out else "peripheral"
        other = "peripheral" if pool == "personal" else "personal"
        if caps[pool] == 0 and caps[other] > 0:
            pool = other
        out[pool] += cost
    return out


def charm_installation_pool(ruleset: RuleSet, character: Character) -> int:
    """Return the motes for Alchemical Charm installation (CH2 p.62): Personal, or
    the WHOLE pool if merged.

    ⚠ A merged pool has Personal 0 (p.41). Ask here. Do not use
    `essence_pools(...)[0]`."""
    personal, peripheral = essence_pools(ruleset, character)
    if essence_pool_is_merged(ruleset, character):
        return personal + peripheral
    return personal


def health_track(character: Character,
                 ruleset: Optional[RuleSet] = None) -> list[HealthLevelView]:
    """Return the base levels plus the bonus levels, from least to most severe
    (0, -1, -2, -4), with Incapacitated last.

    ⚠ Without `ruleset` the Merit levels (Large Size, Small) are missing. Pass it.
    """
    levels = [HealthLevelView(penalty=p) for p in BASE_WOUND_PENALTIES]
    levels += [
        HealthLevelView(penalty=hl.penalty, source=hl.source_charm)
        for hl in character.health_bonus_levels if not hl.removed
    ]
    # Ox-Body purchases: the inline levels of each package.
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
        # Dragon-King breed levels (PG pp.171/174).
        cd = ruleset.castes.get(character.caste)
        breed = cd.breed_traits if (cd and cd.breed_traits) else None
        if breed and breed.bonus_health_levels:
            levels += [HealthLevelView(penalty=p, source="Breed")
                       for p in breed.bonus_health_levels]

    def _remove(penalty: int) -> None:
        """Remove one level of `penalty`. Base levels are first in the list."""
        idx = next((i for i, lv in enumerate(levels) if lv.penalty == penalty), None)
        if idx is not None:
            levels.pop(idx)

    # Curses remove a level of the given penalty (a base level first).
    for hl in character.health_bonus_levels:
        if hl.removed:
            _remove(hl.penalty)
    # Flaws: Small (p.32).
    for penalty in (effects.health_levels_removed if effects else ()):
        _remove(penalty)
    # Stable sort by severity: 0 first (highest penalty value), -4 last.
    levels.sort(key=lambda lv: lv.penalty, reverse=True)
    levels.append(HealthLevelView(penalty=None, incapacitated=True))
    return levels


def applied_material(
    ruleset: RuleSet, character: Character, item: Weapon | Armor
) -> Optional[MagicalMaterial]:
    """Return the material whose bonus applies to `item` for this character, or None.
    The item must name a known material that resonates with the Exalt type (core
    p.341).

    ⚠ Return None if `MeritEffects.no_magical_material_bonus` is set (PG p.120, p.66;
    decision 0011). The exalt_type test also gives None for these characters, by
    accident (the house bug, type 2).
    """
    from . import merits as _merits
    key = getattr(item, "material", "")
    if not key:
        return None
    mat = ruleset.material_catalog.get(key)
    if mat is None or mat.exalt_type != character.exalt_type:
        return None
    if _merits.merits_and_flaws_calc(ruleset, character).no_magical_material_bonus:
        return None
    return mat


def effective_weapon(ruleset: RuleSet, character: Character, weapon: Weapon) -> Weapon:
    """Return a copy of `weapon` with the material bonus added, if the Exalt type
    matches (p.341)."""
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
    """Return a copy of `armor` with the material bonus added, if the Exalt type
    matches (p.341)."""
    mat = applied_material(ruleset, character, armor)
    if mat is None:
        return armor.model_copy()
    return armor.model_copy(update={
        "soak_lethal": armor.soak_lethal + mat.armor_soak_lethal,
        "soak_bashing": armor.soak_bashing + mat.armor_soak_bashing,
        "mobility_penalty": 0 if mat.armor_negate_mobility_penalty else armor.mobility_penalty,
        "fatigue": 0 if mat.armor_negate_fatigue else armor.fatigue,
    })


def damaged_armor(ruleset: RuleSet, character: Character, armor: Armor) -> Armor:
    """Return a copy of `armor` with the Damaged Artifact reduction (PG p.38).

    ⚠ Applied AFTER the material bonus. Else a material repairs the damage.

    The floor is 0. The three-point tier ("presently useless") sets both tracks to 0.
    """
    from . import artifacts, merits          # local: both import derive at module load
    effects = merits.merits_and_flaws_calc(ruleset, character)
    if not effects.damaged_artifacts:
        return armor.model_copy()
    key = artifacts.item_key(artifacts.SOURCE_ARMOR, armor.name)
    points = effects.damaged_artifacts.get(key)
    if not points:
        return armor.model_copy()
    lost = merits.DAMAGED_ARTIFACT_SOAK.get(points, 0)
    if lost is None:                          # "presently useless"
        return armor.model_copy(update={"soak_lethal": 0, "soak_bashing": 0})
    return armor.model_copy(update={
        "soak_lethal": max(0, armor.soak_lethal - lost),
        "soak_bashing": max(0, armor.soak_bashing - lost),
    })


def soak(character: Character, ruleset: Optional[RuleSet] = None) -> SoakView:
    """Return the soak by damage type (Exalted 1e pp.231-232).

    The armor soak is the sum of all worn pieces. The material bonus
    (effective_armor) and the Damaged Artifact reduction (damaged_armor) need
    `ruleset`.

    ⚠ Without `ruleset` the armor soak is incorrect, with no error. Pass it."""
    stamina = character.attributes[AttributeName.STAMINA]
    pieces = (
        [damaged_armor(ruleset, character, effective_armor(ruleset, character, a))
         for a in character.armor]
        if ruleset is not None else character.armor
    )
    armor_bashing = sum(a.soak_bashing for a in pieces)
    armor_lethal = sum(a.soak_lethal for a in pieces)

    # Dragon-Kings (PG p.165): innate armor adds to both natural values. Stamina adds
    # nothing to lethal. Without `ruleset` the innate armor is 0.
    breed = None
    if ruleset is not None:
        cd = ruleset.castes.get(character.caste)
        breed = cd.breed_traits if (cd and cd.breed_traits) else None
    innate_b = breed.innate_soak_bashing if breed else 0
    innate_l = breed.innate_soak_lethal if breed else 0

    # ExaltDefinition.stamina_adds_to_lethal_soak (p.165). With no ruleset, the
    # fallback is `exalt_type != "Mortal"`.
    add_sta = character.exalt_type != "Mortal"
    if ruleset is not None:
        ex = ruleset.exalts.get(character.exalt_type)
        if ex is not None:
            add_sta = ex.stamina_adds_to_lethal_soak

    natural_bashing = stamina + innate_b
    natural_lethal = innate_l + (stamina // 2 if add_sta else 0)

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
        essence_free=essence_freely_accessible(ruleset, character),
        health_levels=health_track(character, ruleset),
        soak=soak(character, ruleset),
    )


# --------------------------------------------------------------------------- #
# Ghost traits: Fetters and Passions (Exalted: The Abyssals p.126-127, p.283)
# These are derivations that apply on both sides of the lock.
# --------------------------------------------------------------------------- #

def passion_pool(character: Character) -> dict[VirtueName, int]:
    """Return the Passion dots that the character can distribute, by Virtue (p.126).

    ⚠ A LIVE DERIVATION, NOT A CHARGEN BUDGET (p.283, human's ruling). Reads the
    CURRENT Virtues. Do not use a ChargenSnapshot.
    """
    return {v: character.virtues.get(v, 0) for v in VirtueName}


def passion_dots_spent(character: Character) -> dict[VirtueName, int]:
    """Return the Passion dots distributed, by Virtue."""
    out: dict[VirtueName, int] = {v: 0 for v in VirtueName}
    for p in character.passions:
        out[p.virtue] = out.get(p.virtue, 0) + p.rating
    return out


def passion_dots_unspent(character: Character) -> dict[VirtueName, int]:
    """Return pool - spent, by Virtue. Not clamped: a negative value shows an
    overrun, which validate reports."""
    pool = passion_pool(character)
    spent = passion_dots_spent(character)
    return {v: pool[v] - spent[v] for v in VirtueName}


def fetter_dots_spent(character: Character) -> int:
    """Return the total dots of all Fetters."""
    return sum(f.rating for f in character.fetters)


def fetter_cap(character: Character, ruleset: Optional[RuleSet] = None) -> int:
    """Return the ceiling on TOTAL Fetter dots: Willpower + Essence (p.127, p.283).
    It applies on both sides of the lock.

    ⚠ Without `ruleset` a Flaw that sells Willpower dots is missing. Pass it.
    """
    return willpower(character, ruleset) + character.essence_rating
