"""
engine/pools.py — BASE dice pools (decision 0016).

The number of dice for a roll, from trait values on the sheet: Dexterity + Melee +
weapon accuracy, a Virtue check, a Willpower check.

⚠ **Never return a bare number.** Decision 0008 rejected a static attack line: it
looks authoritative and is wrong when a Charm fires. 0016 permits the arithmetic only
as an ITEMISED BREAKDOWN of labelled lines plus a list of what it leaves out. Do not
collapse `PoolBreakdown` to one integer.

Out of scope:

* Rolling, of any kind (decision 0009 — untouched by 0016).
* Damage, soak-versus-attack, opposed rolls, initiative — anything needing a
  second party or a result (0008).
* **Charm dice.** They need the ACTIVE Charms, which are play state (decision 0006).
* Storyteller modifiers: stunts, difficulty, range, multiple-action splitting,
  environment.

⚠ `base_pool` NEVER reads `Character.play`. The caller passes the wound penalty.
`wound_penalty()` is the separate play-state read.

The traits of each roll are DATA: `data/dice_pools.json` → `rules.RollDefinition`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..models.character import Character, Specialty, Weapon
from ..models.rules import (
    AbilityName, AttributeName, PoolKind, RollDefinition, RuleSet, VirtueName,
    WeaponStat)
from . import derive

# The caveats shown with each pool (the 0008 mitigation). A surface that renders
# `total` must render these.
EXCLUDES: tuple[str, ...] = (
    "Charm dice — no Charm effect is modelled here (they need activation state).",
    "Stunt dice, and any Storyteller-awarded bonus.",
    "Difficulty, and situational penalties: range, cover, multiple actions.",
    "Willpower spent for an automatic success (that is a success, not a die).",
)


@dataclass(frozen=True)
class PoolLine:
    """One labelled contribution. `value` is signed: a penalty is a negative line.

    `short` is the abbreviated label ("dex", "acc", "wnd"). A surface must show a
    value with one of the two labels.
    """
    label: str
    value: int
    note: str = ""
    short: str = ""


@dataclass(frozen=True)
class PoolBreakdown:
    """A base pool, itemised. `total` is the sum of `lines` only."""
    roll: str
    lines: tuple[PoolLine, ...]
    total: int
    excludes: tuple[str, ...] = EXCLUDES
    notes: str = ""

    @property
    def below_one(self) -> bool:
        """Return True if the penalties take the pool below one die.

        ⚠ The total is NOT floored. The corebook floors only range penalties (p.229).
        The Storyteller decides the result.
        """
        return self.total < 1

    @property
    def summary(self) -> str:
        """Return the arithmetic on one line: 'Dexterity 4 + Melee 3 + Short sword
        (accuracy) 2 = 9'."""
        parts = [f"{ln.label} {ln.value:+d}" for ln in self.lines]
        return f"{' '.join(parts).lstrip('+').strip()} = {self.total}"

    @property
    def compact(self) -> str:
        """Return the abbreviated arithmetic, WITHOUT the total: '+4 dex +3 melee +2
        acc -1 wnd -2 ftg'. Still itemised, as decision 0016 requires."""
        return " ".join(f"{ln.value:+d} {ln.short or ln.label.lower()}"
                        for ln in self.lines)


@dataclass(frozen=True)
class SpecialtyOption:
    """One specialty as the calculator offers it: a NAME and the dice it is worth.

    ⚠ Not a `Specialty` row. A specialty is an INSTANCE, not a rated trait (human's
    ruling): `Character.specialties` has one row per instance (p.134). This type sums
    the instances by name: Daiklaves taken two times is one option worth +2.
    """
    ability: object                       # AbilityName
    name: str
    dice: int


def specialties_for(character: Character, roll: RollDefinition) -> list[SpecialtyOption]:
    """Return the specialties that can apply to `roll`, one per NAME, worth one die
    per instance (core p.134). Empty for a roll with no Ability."""
    if roll.kind is not PoolKind.ATTRIBUTE_ABILITY:
        return []
    dice: dict[str, int] = {}
    for s in character.specialties:
        if s.ability == roll.ability:
            dice[s.name] = dice.get(s.name, 0) + s.rating
    return [SpecialtyOption(roll.ability, name, n) for name, n in dice.items()]


def weapon_minimum_shortfall(character: Character, weapon: Weapon) -> int:
    """Return the dots that the wielder is short across the weapon minima, as a
    positive count (core p.327: -1 to speed, attack and defense per dot).
    """
    short = 0
    short += max(0, weapon.min_strength - character.attributes[AttributeName.STRENGTH])
    short += max(0, weapon.min_dexterity - character.attributes[AttributeName.DEXTERITY])
    if weapon.min_martial_arts:
        short += max(0, weapon.min_martial_arts
                     - character.abilities.get(AbilityName.MARTIAL_ARTS, 0))
    return short


# The five Abilities of an attack, and the catalogue tag of each. The other tags
# ("blade", "artifact", "ranged") do not name a roll.
_WEAPON_ABILITY_TAGS = {
    "archery": AbilityName.ARCHERY, "brawl": AbilityName.BRAWL,
    "martial_arts": AbilityName.MARTIAL_ARTS, "melee": AbilityName.MELEE,
    "thrown": AbilityName.THROWN,
}


def weapon_abilities(ruleset: RuleSet, weapon: Weapon) -> Optional[set]:
    """Return the Abilities that this weapon is used with, or None if unknown.

    The owned `Weapon` is an inline copy with no tags (decision 0007): the name is
    matched to the catalogue. A homebrew or renamed weapon gives None.

    ⚠ None means "unknown", NOT "none". A caller must treat None as "applies".
    """
    entry = next((w for w in ruleset.weapon_catalog.values() if w.name == weapon.name),
                 None)
    if entry is None:
        return None
    abilities = {_WEAPON_ABILITY_TAGS[t] for t in entry.tags
                 if t in _WEAPON_ABILITY_TAGS}
    return abilities or None


def weapon_applies(ruleset: RuleSet, weapon: Weapon, roll: RollDefinition) -> bool:
    """Return True if the accuracy/defense of `weapon` belongs in the pool of
    `roll`."""
    if roll.weapon_stat is WeaponStat.NONE:
        return False
    abilities = weapon_abilities(ruleset, weapon)
    return abilities is None or roll.ability in abilities


def mobility_penalty(ruleset: RuleSet, character: Character) -> list[tuple[str, int]]:
    """Return the mobility penalty of each worn piece as (name, positive points),
    after the material pass (moonsilver negates it for a Lunar, p.345).

    ⚠ `Armor.mobility_penalty` is stored negative, but the player can type either
    sign. The magnitude is used: it never adds dice.

    `RollDefinition.mobility_applies` decides if the penalty applies (p.332).
    """
    out = []
    for a in character.armor:
        eff = derive.effective_armor(ruleset, character, a)
        if eff.mobility_penalty:
            out.append((a.name or "Armour", abs(eff.mobility_penalty)))
    return out


def wound_penalty(ruleset: RuleSet, character: Character) -> tuple[int, str]:
    """Return the penalty of the deepest MARKED health box, as (signed value, label).

    ⚠ The only play-state read here. `base_pool` does NOT call it. It never creates
    `Character.play`.

    Returns (0, "") when undamaged, and (0, "Incapacitated") for the Incapacitated
    level, which has no dice penalty.
    """
    play = character.play
    if play is None or not any(m is not None for m in play.health):
        return 0, ""
    track = derive.health_track(character, ruleset)
    deepest = None
    for box, mark in zip(track, play.health):
        if mark is not None:
            deepest = box
    if deepest is None:
        return 0, ""
    if deepest.incapacitated:
        return 0, "Incapacitated"
    return deepest.penalty or 0, str(deepest.penalty)


def fatigue_penalty(character: Character) -> int:
    """Return the armor-fatigue penalty as a SIGNED value (-2 for two points), core
    p.332.

    A play-state read, as `wound_penalty`. `base_pool` does not call it. It never
    creates `Character.play`. The Storyteller adds and removes the points.
    """
    play = character.play
    return -play.fatigue if play is not None else 0


def custom_roll(attribute, ability, *, mobility_applies: bool = False) -> RollDefinition:
    """Return a RollDefinition for any Attribute + Ability. `source` is empty: no page
    lists these rolls.

    `mobility_applies` defaults FALSE: p.332 leaves other actions to the Storyteller,
    thus the player decides.
    """
    return RollDefinition(
        id=f"custom:{getattr(attribute, 'value', attribute)}+{getattr(ability, 'value', ability)}",
        name=f"{_titled(attribute)} + {_titled(ability)}",
        kind=PoolKind.ATTRIBUTE_ABILITY,
        category="Custom",
        attribute=attribute,
        ability=ability,
        mobility_applies=mobility_applies,
    )


def base_pool(ruleset: RuleSet,
              character: Character,
              roll: RollDefinition,
              *,
              weapon: Optional[Weapon] = None,
              virtue: Optional[VirtueName] = None,
              specialty: Optional[SpecialtyOption] = None,
              include_mobility: bool = True,
              wound_penalty: int = 0,
              fatigue_penalty: int = 0) -> PoolBreakdown:
    """Return the itemised BASE pool for `roll`.

    `wound_penalty` and `fatigue_penalty` are SIGNED values from the caller (-2, not
    2). `include_mobility` and a 0 penalty are the toggles of decision 0016: each
    penalty is a separate line that the player can switch off.

    ⚠ A row with `wound_applies=False` drops the wound line (p.233). The gate is HERE,
    not in the UI: each caller gets it.
    """
    lines: list[PoolLine] = []

    # --- the base term ----------------------------------------------------- #
    if roll.kind is PoolKind.ATTRIBUTE_ABILITY:
        lines.append(PoolLine(_titled(roll.attribute),
                              character.attributes[roll.attribute],
                              short=_ATTR_SHORT[roll.attribute]))
        lines.append(PoolLine(_titled(roll.ability),
                              character.abilities.get(roll.ability, 0),
                              short=roll.ability.value.replace("_", " ")))
    elif roll.kind is PoolKind.VIRTUE:
        if virtue is None:
            raise ValueError(f"roll {roll.id!r} is a Virtue check — name the Virtue.")
        lines.append(PoolLine(_titled(virtue), character.virtues.get(virtue, 0),
                              short=virtue.value))
    elif roll.kind is PoolKind.WILLPOWER:
        # p.88: the PERMANENT Willpower (the derivation), not the temporary track.
        lines.append(PoolLine("Willpower (permanent)",
                              derive.willpower(character, ruleset), short="wp"))
    else:                                   # pragma: no cover - enum is exhaustive
        raise ValueError(f"unknown pool kind {roll.kind!r}")

    # --- specialty (core p.134: one extra die per instance) ---------------- #
    if specialty is not None:
        if roll.kind is not PoolKind.ATTRIBUTE_ABILITY or specialty.ability != roll.ability:
            raise ValueError(
                f"specialty {specialty.name!r} is on {specialty.ability}, which "
                f"roll {roll.id!r} does not use.")
        lines.append(PoolLine(f"{specialty.name} (specialty)", specialty.dice,
                              short="spec"))

    # --- the weapon (p.327) ------------------------------------------------ #
    if weapon is not None and roll.weapon_stat is not WeaponStat.NONE:
        eff = derive.effective_weapon(ruleset, character, weapon)
        stat = eff.accuracy if roll.weapon_stat is WeaponStat.ACCURACY else eff.defense
        name = weapon.name or "Weapon"
        lines.append(PoolLine(f"{name} ({roll.weapon_stat.value})", stat,
                              short=roll.weapon_stat.value[:3]))
        shortfall = weapon_minimum_shortfall(character, weapon)
        if shortfall:
            lines.append(PoolLine(f"{name} (minimums not met)", -shortfall,
                                  "one die per dot short of the weapon's minima (p.327)",
                                  short="min"))

    # --- armour mobility (p.332), when this roll takes it ------------------ #
    if include_mobility and roll.mobility_applies:
        for name, points in mobility_penalty(ruleset, character):
            lines.append(PoolLine(f"{name} (mobility)", -points, short="mob"))

    # --- wound penalty, caller-supplied ------------------------------------ #
    if wound_penalty and roll.wound_applies:
        lines.append(PoolLine("Wound penalty", wound_penalty, short="wnd"))

    # --- accumulated armour fatigue (p.332): "-1 penalty to all actions" ---- #
    # No per-roll gate. The p.233 exemption names wound penalties only.
    if fatigue_penalty:
        lines.append(PoolLine("Fatigue", fatigue_penalty,
                              "accumulated armour fatigue (p.332)", short="ftg"))

    return PoolBreakdown(roll=roll.name, lines=tuple(lines),
                         total=sum(ln.value for ln in lines), notes=roll.notes)


# Three-letter Attribute abbreviations for the compact line. A table, not a slice:
# a slice gives collisions.
_ATTR_SHORT = {
    AttributeName.STRENGTH: "str", AttributeName.DEXTERITY: "dex",
    AttributeName.STAMINA: "sta", AttributeName.CHARISMA: "cha",
    AttributeName.MANIPULATION: "manip", AttributeName.APPEARANCE: "app",
    AttributeName.PERCEPTION: "perc", AttributeName.INTELLIGENCE: "int",
    AttributeName.WITS: "wits",
}


def _titled(name) -> str:
    """Return the display form of a snake_case enum: 'martial_arts' → 'Martial
    Arts'."""
    return str(getattr(name, "value", name)).replace("_", " ").title()
