"""
engine/validate/_base.py — primitives shared by every validation domain.

`Issue` (the return type of every check), the Physical/Social/Mental grouping, the
Ability-rating readers, and the snapshot-vs-live trait accessors.

⚠ Nothing here may import a sibling domain module. This is the bottom of the
package's import graph; a domain rule that drifts in makes the graph cyclic, and the
cycle surfaces as an import error at startup rather than a test failure.
"""

from __future__ import annotations

from pydantic import BaseModel

from ...models.character import Character, HouseRules, ThaumaturgyState
from ...models.rules import AbilityName, AttributeName, RuleSet
from .. import merits

# The Physical/Social/Mental membership grouping (core p.104). Which category
# receives which of the 8/6/4 pools is inferred from the spend, not stored here.
ATTRIBUTE_CATEGORIES: dict[str, tuple[AttributeName, ...]] = {
    "Physical": (AttributeName.STRENGTH, AttributeName.DEXTERITY, AttributeName.STAMINA),
    "Social": (AttributeName.CHARISMA, AttributeName.MANIPULATION, AttributeName.APPEARANCE),
    "Mental": (AttributeName.PERCEPTION, AttributeName.INTELLIGENCE, AttributeName.WITS),
}


def thaum_state(character: Character) -> ThaumaturgyState:
    """The character's thaumaturgy, or an empty state where it is None (old saves)."""
    return character.thaumaturgy or ThaumaturgyState()


class Issue(BaseModel):
    """One legality finding. `code` is a stable machine tag; `where` locates the
    offending trait (a Charm/Spell id, an ability name, etc.)."""
    code: str
    message: str
    where: str = ""
    severity: str = "error"        # "error" | "warning"


def craft_rating(character: Character) -> int:
    """The highest of the character's per-focus Craft instances, 0 if none
    (core p.136) — the rating a Craft Charm's minimum Ability is met by."""
    return max((c.rating for c in character.crafts), default=0)


def ability_rating(character: Character, ability: AbilityName) -> int:
    """The character's rating in `ability`, resolving Craft through `craft_rating`
    rather than the unused AbilityName.CRAFT dot."""
    if ability == AbilityName.CRAFT:
        return craft_rating(character)
    return character.abilities.get(ability, 0)


def _attribute_category(attr: AttributeName) -> str | None:
    """Which of Physical/Social/Mental `attr` belongs to; None if unmatched."""
    for cat, attrs in ATTRIBUTE_CATEGORIES.items():
        if attr in attrs:
            return cat
    return None


def _chargen_source(character: Character):
    """The traits chargen accounting reads — the frozen snapshot once locked, else
    the live pre-lock traits — as a flat tuple in a fixed order.

    ⚠ Chargen accounting must read THIS, never the live traits directly (decision
    0004). Reading live makes a post-lock XP purchase look like a chargen overspend.
    """
    snap = character.chargen_snapshot
    return (
        snap.attributes if snap else character.attributes,
        snap.abilities if snap else character.abilities,
        snap.crafts if snap else character.crafts,
        snap.virtues if snap else character.virtues,
        snap.backgrounds if snap else character.backgrounds,
        snap.specialties if snap else character.specialties,
        snap.charms if snap else character.charms,
        snap.spells if snap else character.spells,
        snap.combos if snap else character.combos,
        snap.ox_body if snap else character.ox_body,
        snap.essence_rating if snap else character.essence_rating,
        snap.willpower_purchased if snap else character.willpower_purchased,
        snap.beastman_gifts if snap else character.beastman_gifts,
        snap.arrays if snap else character.arrays,
        snap.submodules if snap else character.submodules,
        snap.colleges if snap else character.colleges,
        (snap.thaumaturgy or ThaumaturgyState()) if snap else thaum_state(character),
        snap.paths if snap else character.paths,
        snap.favored_path if snap else character.favored_path,
        snap.elemental_powers if snap else character.elemental_powers,
        # ⚠ APPENDED, never inserted: callers index this tuple positionally
        # (`src[6]`, `src[9]`, …), so a new element anywhere but the end silently
        # re-points every reader after it.
        snap.variant_purchases if snap else character.variant_purchases,
    )


def effective_budgets(ruleset: RuleSet, character: Character):
    """The splat's printed chargen budgets, adjusted by the trait-forfeit Merits and
    Flaws the character holds (PG pp.35-36).

    Ability and Virtue dots come DOWN (Callous, Unskilled, Weak-Willed sell chargen
    dots for bonus points); Background dots go UP (Heir Apparent's inheritance).
    Returns a COPY — the printed budget in `data/` is unchanged, so a caller may diff
    the two to show the player what was traded away.

    ⚠ Diminished Attributes is NOT applied here. Attribute pools are matched to
    categories by spend rather than declared, so that forfeit must come off the pool
    its category actually receives, where the two are zipped.
    `MeritEffects.forfeited_attribute_dots` carries it; nothing consumes it yet.
    """
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    effects = merits.merits_and_flaws_calc(ruleset, character)
    if not (effects.forfeited_ability_dots or effects.forfeited_virtue_dots
            or effects.bonus_background_dots):
        return b
    return b.model_copy(update={
        "ability_dots": max(0, b.ability_dots - effects.forfeited_ability_dots),
        "virtue_dots": max(0, b.virtue_dots - effects.forfeited_virtue_dots),
        "background_dots": b.background_dots + effects.bonus_background_dots,
    })


def chargen_house_rules(character: Character) -> HouseRules:
    """The table toggles chargen accounting reads — the frozen snapshot once locked,
    else the live setting, else the all-off default."""
    snap = character.chargen_snapshot
    if snap is not None:
        return snap.house_rules or HouseRules()
    return character.house_rules or HouseRules()
