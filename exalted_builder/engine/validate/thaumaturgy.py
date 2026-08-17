"""
engine/validate/thaumaturgy.py — Arts, Sciences, Rituals and Formulas.

Thaumaturgy is NOT a splat: it is a cross-splat capability layer that any character
except the Fair Folk may hold, so this module is reachable from every splat's sheet.
Ghosts are the edge case — they may hold it and may never use it.

Owns the purchase enumeration (`thaum_purchases` and the ONE `_thaum_purchases_from`
that both sides of the lock go through), the BP costing, the four `*_locked_reason`
helpers the UI greys controls with, and the two issue functions.

⚠ The Science costs (5/7 BP, 7/current×6 XP) are the ONLY values in the build with
no printed page behind them — the printed tables omit Sciences entirely, and the
rates were supplied by the human on 2026-07-29.

⚠ Every Storyteller toggle lives on `HouseRules`, including the two optional p.113
chargen caps read here. Fields are marked TABLE-WIDE or PER-CHARACTER in comments
only, and a party-wide "apply to all" control may only touch the former.

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


# "Magic for Everyone" (p.115) covers "rituals, formulas or procedures of no more
# than level 3". Not in a cost table — it is a limit on an optional grant rather
# than a rate, so it has no natural home in costs_bonus.json.
_MAGIC_FOR_EVERYONE_MAX_LEVEL = 3


# The two optional ST chargen restrictions of p.113: "no more than three-dot rituals
# and/or the third level of knowledge in any Science". Off unless the table turns
# them on -- see HouseRules.restrict_chargen_*.
_ST_CHARGEN_RITUAL_CAP = 3


_ST_CHARGEN_SCIENCE_CAP = 3


class ThaumPurchase(BaseModel):
    """One thaumaturgic thing a character bought, in a shape both currencies price.

    The Charm-pick enumeration's sibling, and for the same reason: four
    heterogeneous purchasables (Arts, Art specialties, Sciences, rituals, formulas)
    live on five different lists, and each of the BP breakdown, the XP audit and the
    UI would otherwise walk all five and special-case each. They are enumerated once
    here and priced once in `thaum_purchase_bp_costs`.

    `level` is the ritual's or formula's level, or the Science's rating; 0 where the
    kind has none. `orientations` is how many regional versions are owned — the
    first is included in the base price and each further one costs a flat point
    (p.124), which is the whole reason a ritual is not a bare id.

    Every kind is priced. Sciences briefly were not — the published cost tables have
    no Science row — but that is a printing error Grabowski cleared up later, and the
    rate came from the rules authority (5/7 BP, 7/rating×6 XP).
    """
    kind: str                  # art | specialty | science | ritual | formula
    key: str                   # catalogue id, or "art_id:name" for a specialty
    label: str                 # display-ready
    level: int = 0
    orientations: int = 1
    narrowed: bool = False


def thaum_purchases(ruleset: RuleSet, character: Character) -> list[ThaumPurchase]:
    """Everything the character has bought in thaumaturgy RIGHT NOW, in sheet order:
    Arts, Art specialties, Sciences, rituals, formulas.

    This is what the UI must consume instead of reading the five `ThaumaturgyState`
    lists. Unresolvable ids are still yielded, with the raw id as the label, so a
    stale save shows the problem rather than dropping a row.
    """
    return _thaum_purchases_from(ruleset, thaum_state(character))


def chargen_thaum_purchases(ruleset: RuleSet, character: Character) -> list[ThaumPurchase]:
    """`thaum_purchases` over the traits chargen accounting reads: the frozen
    snapshot once locked, else the live state."""
    snap = character.chargen_snapshot
    state = (snap.thaumaturgy or ThaumaturgyState()) if snap else thaum_state(character)
    return _thaum_purchases_from(ruleset, state)


def thaum_ritual_level(ruleset: RuleSet, entry: RitualEntry) -> int:
    """A ritual entry's level, from the catalogue when it references one and from the
    inline fields when it is custom (rituals are catalogue + custom by decision)."""
    ritual = ruleset.thaum_rituals.get(entry.ritual_id) if entry.ritual_id else None
    return ritual.level if ritual is not None else entry.level


def thaum_formula_level(ruleset: RuleSet, entry: FormulaEntry) -> int:
    formula = ruleset.thaum_formulas.get(entry.formula_id) if entry.formula_id else None
    return formula.level if formula is not None else entry.level


def _thaum_purchases_from(ruleset: RuleSet, state: ThaumaturgyState) -> list[ThaumPurchase]:
    """Build the purchase list from an explicit state, so the same enumeration serves
    both the live character and the chargen snapshot."""
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
    """`Name (level N; North, Realm)` — orientation is display state as well as
    accounting state, since which versions are owned is what the player reads back."""
    regions = ", ".join(o.value for o in orientations)
    return f"{name} (level {level}; {regions})" if regions else f"{name} (level {level})"


def magic_for_everyone_grant(ruleset: RuleSet, character: Character) -> int:
    """How many thaumaturgy purchases this character gets FREE at creation under the
    optional "Magic for Everyone" rule (p.115): "one ritual, one formula or procedure
    or knowledge of one aspect for every two dots in Occult".

    0 unless the table has switched the rule on. Occult is read from the chargen
    source, so the allowance is fixed at creation — **raising Occult with XP does not
    earn more free picks** (rules-authority call, human 2026-07-29). Post-lock that
    happens for free: the snapshot holds chargen Occult.
    """
    if not chargen_house_rules(character).magic_for_everyone:
        return 0
    abilities, crafts = _chargen_source(character)[1], _chargen_source(character)[2]
    occult = abilities.get(AbilityName.OCCULT, 0)
    return occult // 2


def magic_for_everyone_eligible(ruleset: RuleSet, purchase: ThaumPurchase) -> bool:
    """Whether `purchase` is the kind of thing the free grant may cover.

    The rule is explicit about its own limits: "rituals, formulas or procedures of no
    more than level 3, and only specialties in Arts, not the Arts themselves (so a
    non-thaumaturge could chose to learn how to ward off ghosts, but not the Art of
    Warding)". So Arts and Sciences are never free.

    "knowledge of one aspect" means a PRINTED aspect, so a player-invented narrower
    specialty is not eligible — it is not one of the things the book enumerates.
    (The sidebar's parenthetical "along with any appropriate specialties" is
    deliberately unimplemented: the rules authority could not determine what it
    means, human 2026-07-29. Do not guess at it.)
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
    """The bonus-point price of each purchase, in purchase order — parallel to
    `purchases`, so the UI can render a priced row per purchase. A Science's figure
    is the whole ladder up to its rating, since chargen holds a rating rather than a
    sequence of purchases.

    `free_picks` is the "Magic for Everyone" allowance. It zeroes that many ELIGIBLE
    purchases, dearest first — the player-favourable assignment this module already
    uses everywhere a free pool meets mixed rates. The player does not tag which
    purchases were free; the engine computes it, per the standing decision that
    current state is canonical and the accounting is derived.
    """
    # Deferred import: costs.py imports this module, so a top-level import here would
    # cycle. The thaum_* rate functions depend on nothing in validate, hence safe.
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


def thaum_art_locked_reason(ruleset: RuleSet, character: Character, art_id: str) -> str:
    """Why the Art `art_id` may not be trained right now, or "" if it may be."""
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
    """Why this specialty may not be bought, or "" if it may be.

    Owning the parent Art is NOT a requirement and must never become one (p.116
    footnote, stated three times). Only a PRINTED aspect can be gated at all: a
    player-invented specialty matches no aspect and is therefore always open.
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
    """Why a level-`level` ritual may not be learned, or "" if it may be. Level is
    passed rather than an id so a custom ritual is gated identically to a catalogue
    one — the Occult rule is stated about the level, not the entry (p.148)."""
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
    """Why this Science may not gain its NEXT dot, or "" if it may.

    The forward-looking counterpart of the `max_rating` check in
    `thaumaturgy_issues`: that one asks whether a held rating is in range, this asks
    whether one more dot is buyable. The ceiling is the Science's OWN `max_rating`
    (Alchemy 6), never the project's usual 5 — see rules.ScienceLevel.
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
    """Legality of a thaumaturgic holding. Called from `validate_chargen` against the
    chargen state; safe to call on the live state too.

    The gates the source actually states:
      * Ghosts hold thaumaturgy but may never use it (p.114) — a flag, not a bar, so
        this is an info Issue and never blocks a purchase (rules-authority call 1).
      * The Fair Folk cannot learn it at all (p.114) — `thaumaturgy_usable` False.
      * "a thaumaturge must have an Occult score equal to or higher than the
        ritual's level" (p.148).
      * An Art's `min_occult`, and Summoning's per-aspect minima.
      * A Science may not exceed its own `max_rating` (Alchemy 6, the rest 5).

    Deliberately NOT gated: owning an Art is not required to buy a specialty in it
    (p.116 footnote, stated three times). Do not add that check.
    """
    issues: list[Issue] = []
    occult = ability_rating(character, AbilityName.OCCULT)
    exalt = ruleset.exalt_for(character.exalt_type)
    purchases = _thaum_purchases_from(ruleset, state)

    # Announced BEFORE the no-purchases early return: under "Magic for Everyone" the
    # allowance applies to every starting character, so the one who has bought no
    # thaumaturgy at all is exactly the one who needs telling it is there. Silent at
    # Occult 0-1, where the allowance is zero, and in every game without the toggle.
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
        # A printed aspect carries its own Occult minimum (Summoning alone). A
        # player-invented specialty matches no aspect and is ungated.
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
        # chargen=False: the p.113 cap is a creation-time restriction and belongs to
        # thaumaturgy_chargen_issues, which reports it with its own code.
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
    """The two OPTIONAL chargen restrictions of p.113, each switched on separately:
    "Storytellers may choose to restrict starting characters to no more than
    three-dot rituals and/or the third level of knowledge in any Science."

    Separate from `thaumaturgy_issues` because these are creation-time only — they
    cap what may be BOUGHT at chargen, not what may ever be known. A character who
    legitimately raises a Science past 3 with XP must not start failing this check,
    so it is only ever called with the chargen state, from `validate_chargen`.
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
