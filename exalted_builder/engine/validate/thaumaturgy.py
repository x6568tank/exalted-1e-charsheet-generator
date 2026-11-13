"""
engine/validate/thaumaturgy.py — Arts, Sciences, Rituals and Formulas.

A layer, not a splat: each sheet can reach it. The purchase enumeration, the BP
costs, the four `*_locked_reason` helpers for the UI, and the two issue functions.

⚠ Ghosts may HOLD thaumaturgy and may never USE it.

⚠ The Science costs (5/7 BP, 7/current×6 XP) have no printed page (human's ruling).
Do not "correct" them.

⚠ Each Storyteller toggle is on `HouseRules`, including the two optional p.113 chargen
caps read here. A control that applies a value to all characters can change
TABLE-WIDE fields only.

⚠ p.116 Step Four errata: the pool is "5 in addition to recorded KNOWLEDGE", not
Inheritance.
"""

from __future__ import annotations

from pydantic import BaseModel

from ...models.character import Character, FormulaEntry, HouseRules, RitualEntry, ThaumaturgyState
from ...models.rules import AbilityName, RuleSet
from .. import merits
from ._base import (
    Issue, _chargen_source, ability_rating, chargen_house_rules, thaum_state)


# "Magic for Everyone" (p.115): rituals, formulas or procedures of level 3 at most. A
# limit on a grant, not a rate.
_MAGIC_FOR_EVERYONE_MAX_LEVEL = 3


# The two optional chargen caps of p.113. See HouseRules.restrict_chargen_*.
_ST_CHARGEN_RITUAL_CAP = 3


_ST_CHARGEN_SCIENCE_CAP = 3


class ThaumPurchase(BaseModel):
    """One thaumaturgic purchase, in a shape that both currencies price.

    One enumeration of the five lists, for the BP breakdown, the XP audit and the UI.

    `level`: the ritual or formula level, or the Science rating; 0 for other kinds.
    `orientations`: the owned regional versions. Each version after the first costs
    1 point (p.124).

    ⚠ EVERY kind is priced, Sciences included (human's ruling).
    """
    kind: str                  # art | specialty | science | ritual | formula
    key: str                   # catalogue id, or "art_id:name" for a specialty
    label: str                 # display-ready
    level: int = 0
    orientations: int = 1
    narrowed: bool = False


def thaum_purchases(ruleset: RuleSet, character: Character) -> list[ThaumPurchase]:
    """Return each thaumaturgy purchase of the character NOW, in sheet order: Arts,
    Art specialties, Sciences, rituals, formulas.

    The UI must read this, not the five `ThaumaturgyState` lists. An unknown id is
    returned with the id as its label.
    """
    return _thaum_purchases_from(ruleset, thaum_state(character))


def chargen_thaum_purchases(ruleset: RuleSet, character: Character) -> list[ThaumPurchase]:
    """Return `thaum_purchases` over the chargen source: the snapshot when locked,
    else the live state."""
    snap = character.chargen_snapshot
    state = (snap.thaumaturgy or ThaumaturgyState()) if snap else thaum_state(character)
    return _thaum_purchases_from(ruleset, state)


def thaum_ritual_level(ruleset: RuleSet, entry: RitualEntry) -> int:
    """Return the level of a ritual entry: from the catalogue, or from the inline
    fields of a custom ritual."""
    ritual = ruleset.thaum_rituals.get(entry.ritual_id) if entry.ritual_id else None
    return ritual.level if ritual is not None else entry.level


def thaum_formula_level(ruleset: RuleSet, entry: FormulaEntry) -> int:
    formula = ruleset.thaum_formulas.get(entry.formula_id) if entry.formula_id else None
    return formula.level if formula is not None else entry.level


def _thaum_purchases_from(ruleset: RuleSet, state: ThaumaturgyState) -> list[ThaumPurchase]:
    """Return the purchase list of `state` (live or snapshot)."""
    out: list[ThaumPurchase] = []

    for art_id in state.arts:
        art = ruleset.thaum_arts.get(art_id)
        out.append(ThaumPurchase(kind="art", key=art_id,
                                 label=art.name if art else art_id))

    for spec in state.art_specialties:
        art = ruleset.thaum_arts.get(spec.art_id)
        art_name = art.name if art else spec.art_id
        out.append(ThaumPurchase(
            kind="specialty", key=f"{spec.art_id}:{spec.name}",
            label=f"{art_name} ({spec.name})", narrowed=spec.narrowed))

    for sci in state.sciences:
        if sci.rating <= 0:
            continue
        science = ruleset.thaum_sciences.get(sci.science_id)
        out.append(ThaumPurchase(
            kind="science", key=sci.science_id,
            label=f"{science.name if science else sci.science_id} {sci.rating}",
            level=sci.rating))

    for entry in state.rituals:
        ritual = ruleset.thaum_rituals.get(entry.ritual_id) if entry.ritual_id else None
        name = ritual.name if ritual is not None else (entry.name or entry.ritual_id)
        level = thaum_ritual_level(ruleset, entry)
        out.append(ThaumPurchase(
            kind="ritual", key=entry.ritual_id or entry.name,
            label=_thaum_label(name, level, entry.orientations),
            level=level, orientations=len(entry.orientations)))

    for entry in state.formulas:
        formula = ruleset.thaum_formulas.get(entry.formula_id) if entry.formula_id else None
        name = formula.name if formula is not None else (entry.name or entry.formula_id)
        level = thaum_formula_level(ruleset, entry)
        out.append(ThaumPurchase(
            kind="formula", key=entry.formula_id or entry.name,
            label=_thaum_label(name, level, entry.orientations),
            level=level, orientations=len(entry.orientations)))

    return out


def _thaum_label(name: str, level: int, orientations: list) -> str:
    """Return `Name (level N; North, Realm)`. The orientations show which versions are
    owned."""
    regions = ", ".join(o.value for o in orientations)
    return f"{name} (level {level}; {regions})" if regions else f"{name} (level {level})"


def magic_for_everyone_grant(ruleset: RuleSet, character: Character) -> int:
    """Return the free thaumaturgy purchases at creation under the optional "Magic
    for Everyone" rule (p.115): one per two dots of Occult.

    0 unless the rule is on. Occult comes from the chargen source: **XP Occult does
    not give more free picks** (human's ruling).
    """
    if not chargen_house_rules(character).magic_for_everyone:
        return 0
    abilities, crafts = _chargen_source(character)[1], _chargen_source(character)[2]
    occult = abilities.get(AbilityName.OCCULT, 0)
    return occult // 2


def magic_for_everyone_eligible(ruleset: RuleSet, purchase: ThaumPurchase) -> bool:
    """Return True if the Magic for Everyone grant can cover `purchase` (p.115):
    rituals, formulas or procedures of level 3 at most, and specialties. Never an Art
    or a Science.

    ⚠ "knowledge of one aspect" means a PRINTED aspect, so a player-invented narrower
    specialty is not eligible.

    ⚠ "along with any appropriate specialties" is NOT implemented: its meaning is not
    known. Do not guess at it.
    """
    if purchase.kind in ("art", "science"):
        return False
    if purchase.kind == "specialty":
        art_id, _, name = purchase.key.partition(":")
        art = ruleset.thaum_arts.get(art_id)
        return art is not None and any(
            a.name.casefold() == name.casefold() for a in art.aspects)
    return purchase.level <= _MAGIC_FOR_EVERYONE_MAX_LEVEL


def thaum_purchase_bp_costs(ruleset: RuleSet, character: Character,
                            purchases: list[ThaumPurchase],
                            free_picks: int = 0) -> list[int]:
    """Return the bonus-point price of each purchase, in order (parallel to
    `purchases`). A Science price is its whole ladder up to the rating.

    `free_picks` (Magic for Everyone) sets that many ELIGIBLE purchases to 0, the most
    expensive first. The engine assigns them (decision 0003).
    """
    # Local import: costs.py imports this module.
    from .. import costs

    out: list[int] = []
    for p in purchases:
        if p.kind == "art":
            out.append(costs.thaum_art_bp(ruleset, character))
        elif p.kind == "specialty":
            out.append(costs.thaum_specialty_bp(ruleset, character, narrowed=p.narrowed))
        elif p.kind == "science":
            out.append(costs.thaum_science_bp(ruleset, character, p.level))
        elif p.kind == "ritual":
            out.append(costs.thaum_ritual_bp(ruleset, character, p.level, p.orientations))
        elif p.kind == "formula":
            out.append(costs.thaum_formula_bp(ruleset, character, p.orientations))
        else:
            out.append(0)

    if free_picks > 0:
        eligible = [i for i, p in enumerate(purchases)
                    if magic_for_everyone_eligible(ruleset, p)]
        for i in sorted(eligible, key=lambda i: out[i], reverse=True)[:free_picks]:
            out[i] = 0
    return out


# --------------------------------------------------------------------------- #
# Per-purchase gates.
#
# `thaumaturgy_issues` checks what the character HOLDS. These functions check one
# purchase NOW. The reason strings are the issue messages: the UI greys a row for the
# reason the validator gives.
#
# `chargen=True` adds the two optional p.113 creation caps.


def thaum_art_locked_reason(ruleset: RuleSet, character: Character, art_id: str) -> str:
    """Return why the Art `art_id` cannot be trained now, or "" if it can."""
    art = ruleset.thaum_arts.get(art_id)
    if art is None:
        return f"Art {art_id} is not in the rule set."
    occult = ability_rating(character, AbilityName.OCCULT)
    if occult < art.min_occult:
        return (f"The Art of {art.name} needs Occult {art.min_occult}; "
                f"character has {occult}.")
    return ""


def thaum_aspect_locked_reason(ruleset: RuleSet, character: Character,
                               art_id: str, aspect_name: str) -> str:
    """Return why this specialty cannot be bought, or "" if it can.

    ⚠ The parent Art is NOT required (p.116). Only a PRINTED aspect can be gated. A
    player-invented specialty is always open.
    """
    art = ruleset.thaum_arts.get(art_id)
    if art is None:
        return f"Art {art_id} is not in the rule set."
    aspect = next((a for a in art.aspects
                   if a.name.casefold() == aspect_name.casefold()), None)
    if aspect is None:
        return ""
    occult = ability_rating(character, AbilityName.OCCULT)
    if occult < aspect.min_occult:
        return (f"{art.name} ({aspect.name}) needs Occult "
                f"{aspect.min_occult}; character has {occult}.")
    return ""


def thaum_ritual_locked_reason(ruleset: RuleSet, character: Character, level: int,
                               *, chargen: bool = False) -> str:
    """Return why a ritual of `level` cannot be learned, or "" if it can. Takes the
    level, thus a custom ritual has the same gate (p.148)."""
    occult = ability_rating(character, AbilityName.OCCULT)
    if occult < level:
        return (f"A level-{level} ritual needs Occult {level}; "
                f"character has {occult} (p.148).")
    if (chargen and level > _ST_CHARGEN_RITUAL_CAP
            and chargen_house_rules(character).restrict_chargen_ritual_level):
        return (f"This table restricts starting characters to rituals of "
                f"level {_ST_CHARGEN_RITUAL_CAP} or lower (p.113); this "
                f"one is level {level}.")
    return ""


def thaum_science_raise_reason(ruleset: RuleSet, character: Character,
                               science_id: str, *, chargen: bool = False) -> str:
    """Return why this Science cannot get its NEXT dot, or "" if it can. The ceiling
    is the `max_rating` of the Science (see rules.ScienceLevel).
    """
    science = ruleset.thaum_sciences.get(science_id)
    if science is None:
        return f"Science {science_id} is not in the rule set."
    held = next((s for s in thaum_state(character).sciences
                 if s.science_id == science_id), None)
    rating = held.rating if held is not None else 0
    if rating >= science.max_rating:
        return f"{science.name} is already at {science.max_rating}, its maximum."
    if (chargen and rating >= _ST_CHARGEN_SCIENCE_CAP
            and chargen_house_rules(character).restrict_chargen_science_rating):
        return (f"This table restricts starting characters to "
                f"{_ST_CHARGEN_SCIENCE_CAP} dots in any Science (p.113).")
    return ""


def thaumaturgy_issues(ruleset: RuleSet, character: Character,
                       state: ThaumaturgyState) -> list["Issue"]:
    """Return the issues of a thaumaturgic holding. `validate_chargen` calls it with
    the chargen state. It is safe on the live state.

    The printed gates:
      * Ghosts hold thaumaturgy but may never use it (p.114);
      * the Fair Folk cannot learn it at all (p.114) — `thaumaturgy_usable` False;
      * "a thaumaturge must have an Occult score equal to or higher than the ritual's
        level" (p.148);
      * an Art's `min_occult`, and Summoning's per-aspect minima;
      * a Science cannot exceed its own `max_rating`.

    ⚠ The ghost rule is a FLAG, not a bar: an info Issue that must never block a
    purchase (human's ruling).

    ⚠ Owning an Art is deliberately NOT required to buy a specialty in it (p.116
    footnote, stated three times). Do not add that check.
    """
    issues: list[Issue] = []
    occult = ability_rating(character, AbilityName.OCCULT)
    exalt = ruleset.exalt_for(character.exalt_type)
    purchases = _thaum_purchases_from(ruleset, state)

    # Before the early return: a character with no purchases needs to know about the
    # Magic for Everyone grant. Silent if the grant is 0.
    grant = magic_for_everyone_grant(ruleset, character)
    if grant:
        issues.append(Issue(
            code="magic-for-everyone-grant", severity="info",
            message=f"Magic for Everyone: {grant} free ritual(s), formula(s) or "
                    f"printed aspect(s) at creation, from Occult {occult}. "
                    f"Rituals and formulas are limited to level "
                    f"{_MAGIC_FOR_EVERYONE_MAX_LEVEL}; Arts and Sciences are never free.",
        ))

    if not purchases:
        return issues

    if not exalt.thaumaturgy_usable:      # exalt_for never returns None
        issues.append(Issue(
            code="thaum-unusable", where=character.exalt_type,
            message=f"{character.exalt_type} may hold thaumaturgy but can never "
                    "use it (Player's Guide p.114).", severity="info",
        ))

    for art_id in state.arts:
        if art_id not in ruleset.thaum_arts:
            issues.append(Issue(code="unknown-thaum-art", where=art_id,
                                message=f"Art {art_id} is not in the rule set."))
            continue
        reason = thaum_art_locked_reason(ruleset, character, art_id)
        if reason:
            issues.append(Issue(code="thaum-art-occult", where=art_id, message=reason))

    for spec in state.art_specialties:
        art = ruleset.thaum_arts.get(spec.art_id)
        if art is None:
            issues.append(Issue(
                code="unknown-thaum-art", where=spec.art_id,
                message=f"Specialty {spec.name!r} names Art {spec.art_id}, "
                        "which is not in the rule set."))
            continue
        # Only a printed aspect has an Occult minimum (Summoning).
        reason = thaum_aspect_locked_reason(ruleset, character, spec.art_id, spec.name)
        if reason:
            issues.append(Issue(
                code="thaum-aspect-occult", where=f"{spec.art_id}:{spec.name}",
                message=reason))
        if spec.narrowed and not art.aspect_narrowing:
            issues.append(Issue(
                code="thaum-narrowing-unavailable", where=f"{spec.art_id}:{spec.name}",
                message=f"Only Summoning allows an aspect to be further limited for "
                        f"half cost (p.127); {art.name} does not.",
            ))

    for sci in state.sciences:
        science = ruleset.thaum_sciences.get(sci.science_id)
        if science is None:
            issues.append(Issue(code="unknown-thaum-science", where=sci.science_id,
                                message=f"Science {sci.science_id} is not in the rule set."))
        elif sci.rating > science.max_rating:
            issues.append(Issue(
                code="thaum-science-range", where=sci.science_id,
                message=f"{science.name} is {sci.rating}; its maximum is "
                        f"{science.max_rating}.",
            ))

    for entry in state.rituals:
        if entry.ritual_id and entry.ritual_id not in ruleset.thaum_rituals:
            issues.append(Issue(code="unknown-thaum-ritual", where=entry.ritual_id,
                                message=f"Ritual {entry.ritual_id} is not in the rule set."))
            continue
        level = thaum_ritual_level(ruleset, entry)
        # chargen=False: thaumaturgy_chargen_issues reports the p.113 cap.
        reason = thaum_ritual_locked_reason(ruleset, character, level)
        if reason:
            issues.append(Issue(
                code="thaum-ritual-occult", where=entry.ritual_id or entry.name,
                message=reason))

    for entry in state.formulas:
        if entry.formula_id and entry.formula_id not in ruleset.thaum_formulas:
            issues.append(Issue(
                code="unknown-thaum-formula", where=entry.formula_id,
                message=f"Formula {entry.formula_id} is not in the rule set."))

    return issues


def thaumaturgy_chargen_issues(ruleset: RuleSet, character: Character,
                               state: ThaumaturgyState) -> list["Issue"]:
    """Return the issues of the two optional chargen caps of p.113.

    Creation only: XP can raise a Science above 3 later. Called only with the chargen
    state, from `validate_chargen`.
    """
    issues: list[Issue] = []
    rules = chargen_house_rules(character)

    if rules.restrict_chargen_ritual_level:
        for entry in state.rituals:
            level = thaum_ritual_level(ruleset, entry)
            if level > _ST_CHARGEN_RITUAL_CAP:
                issues.append(Issue(
                    code="thaum-ritual-chargen-cap", where=entry.ritual_id or entry.name,
                    message=f"This table restricts starting characters to rituals of "
                            f"level {_ST_CHARGEN_RITUAL_CAP} or lower (p.113); this "
                            f"one is level {level}.",
                ))

    if rules.restrict_chargen_science_rating:
        for sci in state.sciences:
            if sci.rating > _ST_CHARGEN_SCIENCE_CAP:
                science = ruleset.thaum_sciences.get(sci.science_id)
                issues.append(Issue(
                    code="thaum-science-chargen-cap", where=sci.science_id,
                    message=f"This table restricts starting characters to "
                            f"{_ST_CHARGEN_SCIENCE_CAP} dots in any Science (p.113); "
                            f"{science.name if science else sci.science_id} is "
                            f"{sci.rating}.",
                ))
    return issues
