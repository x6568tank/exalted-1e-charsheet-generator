"""
engine/pools.py — BASE dice pools (decision 0016).

The one number a player at the table wants that the sheet can already answer:
*how many dice do I pick up?* Dexterity + Melee + the daiklave's accuracy, a
Virtue check, a Willpower check — all of it trait arithmetic over values that are
already on the sheet.

⚠ **What this module must never become.** Decision 0008 rejected an attack line,
and its stated reason was that a static one "looks authoritative and is wrong the
moment a Charm fires". 0016 reopened only the arithmetic, and the mitigation it
accepted is presentational and therefore load-bearing: the output is an ITEMISED
BREAKDOWN of labelled contributions plus an explicit list of what it leaves out —
never a bare number. A future change that collapses `PoolBreakdown` to one integer
re-creates exactly the thing 0008 rejected.

Out of scope, and none of it belongs here later:

* Rolling, of any kind (decision 0009 — untouched by 0016).
* Damage, soak-versus-attack, opposed rolls, initiative — anything needing a
  second party or a result (0008).
* **Charm dice.** They need to know which Charms are ACTIVE, which is play-state,
  and play-state is validation-isolated (decision 0006).
* Storyteller modifiers: stunts, difficulty, range, multiple-action splitting,
  environment.

Play-state isolation, concretely: `base_pool` NEVER reads `Character.play`. The
wound penalty is a caller-supplied integer, and `wound_penalty()` — the one
function here that touches play-state — is a separate read the UI calls and hands
back in. That keeps the pool a pure function of (RuleSet, Character, choices) and
keeps the one play-state read visible at the call site instead of buried.

Which traits compose a given roll is DATA, off the printed page like any other
game value: `data/dice_pools.json` → `rules.RollDefinition`. This module adds up
what the row names and knows nothing about any particular roll.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..models.character import Character, Specialty, Weapon
from ..models.rules import (
    AbilityName, AttributeName, PoolKind, RollDefinition, RuleSet, VirtueName,
    WeaponStat)
from . import derive

# The standing caveats, shown with every pool. This is the 0008 mitigation in
# data form — if a surface renders `total` it must also render these.
EXCLUDES: tuple[str, ...] = (
    "Charm dice — no Charm effect is modelled here (they need activation state).",
    "Stunt dice, and any Storyteller-awarded bonus.",
    "Difficulty, and situational penalties: range, cover, multiple actions.",
    "Willpower spent for an automatic success (that is a success, not a die).",
)


@dataclass(frozen=True)
class PoolLine:
    """One labelled contribution. `value` is signed — penalties are negative lines,
    never a silent subtraction from the total.

    `short` is the same term abbreviated for a one-line breakdown ("dex", "acc",
    "wnd"), where the full label would not fit. It is a rendering convenience and
    carries no information the label does not — a surface may use either, and must
    never show a value without one of them.
    """
    label: str
    value: int
    note: str = ""
    short: str = ""


@dataclass(frozen=True)
class PoolBreakdown:
    """A base pool, itemised. `total` is the sum of `lines` and nothing else, so
    the breakdown can always be checked against the number it produced."""
    roll: str
    lines: tuple[PoolLine, ...]
    total: int
    excludes: tuple[str, ...] = EXCLUDES
    notes: str = ""

    @property
    def below_one(self) -> bool:
        """The penalties have taken the pool under a single die.

        ⚠ The total is NOT floored, deliberately. The corebook floors exactly one
        thing — range penalties, which "can never reduce a character's dice pool
        below 1" (p.229) — and prints no general rule, so clamping every pool at 0
        or 1 would be inventing one. The arithmetic is reported honestly and the
        surface says the pool has gone under; what happens next is the Storyteller's.
        """
        return self.total < 1

    @property
    def summary(self) -> str:
        """'Dexterity 4 + Melee 3 + Short sword (accuracy) 2 = 9' — the arithmetic
        spelled out, for a surface that wants one line."""
        parts = [f"{ln.label} {ln.value:+d}" for ln in self.lines]
        return f"{' '.join(parts).lstrip('+').strip()} = {self.total}"

    @property
    def compact(self) -> str:
        """'+4 dex +3 melee +2 acc -1 wnd -2 ftg' — the same arithmetic abbreviated
        to fit one narrow line, WITHOUT the total (a caller showing this alongside a
        big number would otherwise print it twice).

        Still itemised, which is the point: this is a shorter breakdown, not a bare
        number, so it satisfies what decision 0016 requires of any pool surface."""
        return " ".join(f"{ln.value:+d} {ln.short or ln.label.lower()}"
                        for ln in self.lines)


@dataclass(frozen=True)
class SpecialtyOption:
    """One specialty as the calculator offers it: a NAME and the dice it is worth.

    ⚠ Not a `Specialty` row, and that is the whole point. A specialty is an
    INSTANCE, not a rated trait (ruling 2026-07-31) — `Character.specialties` holds
    one row per instance, and the loader SPLITS a legacy `rating: 2` into two rows
    of 1. "Characters may take the same specialty more than once to increase the
    bonus" (p.134), so a swordsman who took Daiklaves twice rolls +2, not +1. That
    only comes out right if the instances are summed by name — offering the raw rows
    gives the player two identical entries worth one die each and silently
    under-counts the pool.
    """
    ability: object                       # AbilityName
    name: str
    dice: int


def specialties_for(character: Character, roll: RollDefinition) -> list[SpecialtyOption]:
    """The specialties that could apply to `roll`, one entry per NAME, each worth
    one die per instance held (core p.134). Empty for a roll with no Ability."""
    if roll.kind is not PoolKind.ATTRIBUTE_ABILITY:
        return []
    dice: dict[str, int] = {}
    for s in character.specialties:
        if s.ability == roll.ability:
            dice[s.name] = dice.get(s.name, 0) + s.rating
    return [SpecialtyOption(roll.ability, name, n) for name, n in dice.items()]


def weapon_minimum_shortfall(character: Character, weapon: Weapon) -> int:
    """How many dots the wielder is short across the weapon's minima, as a
    positive count (core p.327: "For each dot the character is missing from any
    minimum, she subtracts 1 from the speed, attack and defense of the weapon").

    Character-derived, so it belongs in the base pool — unlike range or cover.
    """
    short = 0
    short += max(0, weapon.min_strength - character.attributes[AttributeName.STRENGTH])
    short += max(0, weapon.min_dexterity - character.attributes[AttributeName.DEXTERITY])
    if weapon.min_martial_arts:
        short += max(0, weapon.min_martial_arts
                     - character.abilities.get(AbilityName.MARTIAL_ARTS, 0))
    return short


# The five Abilities that govern an attack, and the catalogue tag that names each.
# Only these five are Abilities — `weapons.json` also tags shape and provenance
# ("blade", "impact", "spear", "artifact", "ranged"), which say nothing about which
# roll the weapon is used with.
_WEAPON_ABILITY_TAGS = {
    "archery": AbilityName.ARCHERY, "brawl": AbilityName.BRAWL,
    "martial_arts": AbilityName.MARTIAL_ARTS, "melee": AbilityName.MELEE,
    "thrown": AbilityName.THROWN,
}


def weapon_abilities(ruleset: RuleSet, weapon: Weapon) -> Optional[set]:
    """Which Abilities this weapon is used with, or None when that is unknown.

    The character's `Weapon` is an INLINE COPY (decision 0007) and carries no tags,
    so the Ability is recovered by matching the name back to the catalogue. A
    homebrew or renamed weapon matches nothing and returns None.

    ⚠ None means "unknown", NOT "none of them" — a custom weapon must keep working
    on every attack roll. Callers that narrow on this must treat None as "applies",
    or the first thing a player writes their own name on stops adding its accuracy.
    """
    entry = next((w for w in ruleset.weapon_catalog.values() if w.name == weapon.name),
                 None)
    if entry is None:
        return None
    abilities = {_WEAPON_ABILITY_TAGS[t] for t in entry.tags
                 if t in _WEAPON_ABILITY_TAGS}
    return abilities or None


def weapon_applies(ruleset: RuleSet, weapon: Weapon, roll: RollDefinition) -> bool:
    """Whether `weapon`'s accuracy/defense belongs in `roll`'s pool. A daiklave's
    accuracy has no business in an Archery pool, and a surface that lists every roll
    at once will show exactly that unless it asks."""
    if roll.weapon_stat is WeaponStat.NONE:
        return False
    abilities = weapon_abilities(ruleset, weapon)
    return abilities is None or roll.ability in abilities


def mobility_penalty(ruleset: RuleSet, character: Character) -> list[tuple[str, int]]:
    """Each worn piece's mobility penalty as (name, positive points), after the
    magical-material pass — moonsilver negates it outright for a Lunar (p.345), so
    a raw read of `Armor.mobility_penalty` would be wrong for the one splat most
    likely to be wearing moonsilver.

    ⚠ `Armor.mobility_penalty` is stored ALREADY SIGNED and negative in the
    catalogue (a buff jacket is -1), but the field is hand-editable and a player may
    type either sign. The magnitude is taken, as engine.adversaries already does:
    a mobility value is a penalty in every case, and must never add dice.

    Whether the penalty APPLIES is the roll's business, not this function's:
    p.332 says it "doesn't normally apply to attack and parry rolls, but does apply
    to dodge rolls and Athletics rolls for feats that require whole-body agility",
    which is why `RollDefinition.mobility_applies` is a per-row fact off the page.
    """
    out = []
    for a in character.armor:
        eff = derive.effective_armor(ruleset, character, a)
        if eff.mobility_penalty:
            out.append((a.name or "Armour", abs(eff.mobility_penalty)))
    return out


def wound_penalty(ruleset: RuleSet, character: Character) -> tuple[int, str]:
    """The dice penalty of the deepest MARKED health box, as (signed value, label).

    ⚠ The only play-state read in this module, and it is deliberately NOT called by
    `base_pool` — see the module docstring. It never creates `Character.play`, so
    reading it leaves a never-played character's save clean.

    Returns (0, "") when undamaged, and (0, "Incapacitated") when the deepest mark
    is on the Incapacitated level, which carries no dice penalty of its own: a
    character there is not taking dice actions at all, and that is the Storyteller's
    call, not a subtraction.
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
    """The accumulated armour-fatigue penalty as a SIGNED value (-2 for two points),
    core p.332.

    A play-state read, like `wound_penalty`, and deliberately not called by
    `base_pool` for the same reason. It never creates `Character.play`.

    Nothing here adds or removes a point: gaining one needs a failed Stamina +
    Endurance roll (the app does not roll — decision 0009) and shedding one needs
    eight hours of rest out of the armour (the app does not track in-game time).
    Both are the Storyteller's, and the counter is a dumb manual tracker.
    """
    play = character.play
    return -play.fatigue if play is not None else 0


def custom_roll(attribute, ability, *, mobility_applies: bool = False) -> RollDefinition:
    """A RollDefinition for an arbitrary Attribute + Ability the player names.

    The catalogue covers the rolls the corebook spells out; the rest of 1e is
    "roll Attribute + Ability" for whatever the table is doing, and there is no
    printed roster of those to author. This builds the row on the fly instead of
    inventing catalogue entries — the arithmetic is identical, and nothing here
    claims a page it does not have (`source` is left empty for that reason).

    `mobility_applies` defaults FALSE: p.332 names dodge and whole-body Athletics
    feats, and adds that the Storyteller "can also apply this penalty to anything
    else she deems becomes more difficult in 20 or more pounds of protective gear".
    That is a per-action judgement, so it is the caller's (the player's) to make,
    not a default this function guesses.
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
    """The itemised BASE pool for `roll`.

    `wound_penalty` and `fatigue_penalty` are caller-supplied SIGNED values (pass
    -2, not 2) — see the module docstring on why this module will not read them off
    the character itself. `include_mobility` and passing 0 for either penalty are
    the toggles decision 0016 asks for: the penalties render as separate, labelled
    lines the player can switch off, rather than being folded silently into the
    total.

    ⚠ A roll whose row sets `wound_applies=False` drops the wound line even when a
    penalty is passed in. That gate is HERE and not in the UI on purpose: it is a
    printed rule (p.233), and a rule enforced only by a caller is one that stops
    running the moment a second caller appears.
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
        # p.88: dice actions using Willpower use the PERMANENT score (the dots),
        # not the temporary track — so this is the derivation, not play-state.
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
    # "All actions" is unqualified, so unlike mobility this carries no per-roll
    # gate — including onto the resist-infection roll, whose printed exemption
    # names wound penalties and nothing else.
    if fatigue_penalty:
        lines.append(PoolLine("Fatigue", fatigue_penalty,
                              "accumulated armour fatigue (p.332)", short="ftg"))

    return PoolBreakdown(roll=roll.name, lines=tuple(lines),
                         total=sum(ln.value for ln in lines), notes=roll.notes)


# Three-letter Attribute abbreviations for the compact line. Spelled out rather
# than sliced, because "manipulation"[:3] and "medicine"[:3] would both be "man"/"med"
# and Appearance/Athletics would collide the same way — an abbreviation table is
# cheaper than a collision nobody notices.
_ATTR_SHORT = {
    AttributeName.STRENGTH: "str", AttributeName.DEXTERITY: "dex",
    AttributeName.STAMINA: "sta", AttributeName.CHARISMA: "cha",
    AttributeName.MANIPULATION: "manip", AttributeName.APPEARANCE: "app",
    AttributeName.PERCEPTION: "perc", AttributeName.INTELLIGENCE: "int",
    AttributeName.WITS: "wits",
}


def _titled(name) -> str:
    """'martial_arts' → 'Martial Arts'. The enums store snake_case; a pool line is
    read by a human."""
    return str(getattr(name, "value", name)).replace("_", " ").title()
