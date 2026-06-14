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

from ..models.character import Character
from ..models.rules import AttributeName, RuleSet, VirtueName

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


def essence_pools(character: Character) -> tuple[int, int]:
    """(personal, peripheral) motes. Solar only — other Exalt types use different
    coefficients and are not yet in scope.

    Solar Personal    = Essence x 3 + Willpower
    Solar Peripheral  = Essence x 7 + Willpower + sum of Virtues
    """
    if character.exalt_type != "Solar":
        raise NotImplementedError(
            f"Essence-pool formula for exalt_type={character.exalt_type!r} is not "
            "yet defined; only Solar is in scope. Provide the rulebook page first."
        )
    essence = character.essence_rating
    wp = willpower(character)
    personal = essence * 3 + wp
    peripheral = essence * 7 + wp + sum(character.virtues.values())
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


def soak(character: Character) -> SoakView:
    """Per-damage-type soak (bashing / lethal / aggravated), Exalted 1e pp.231-232.

    Armour soak is summed across all worn pieces (the model permits several; the
    common case is one suit). Only magical beings add half-Stamina to lethal soak;
    aggravated never benefits from Stamina. Mortals (exalt_type "Mortal") get no
    Stamina contribution to lethal.
    """
    stamina = character.attributes[AttributeName.STAMINA]
    armor_bashing = sum(a.soak_bashing for a in character.armor)
    armor_lethal = sum(a.soak_lethal for a in character.armor)

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
    personal, peripheral = essence_pools(character)
    return DerivedTraits(
        willpower=willpower(character),
        wp_from_virtues=wp_virtue_component(character),
        essence_personal=personal,
        essence_peripheral=peripheral,
        health_levels=health_track(character),
        soak=soak(character),
    )
