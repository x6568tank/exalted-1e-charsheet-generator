"""
engine/validate/castes.py — which traits a character's caste makes caste/favoured.

The Ability answer and the Attribute answer are separate functions: most splats
favour Abilities, while the Lunars favour an Attribute CATEGORY instead.

⚠ `_caste_favored_attribute_category` returns None for every splat that favours
Abilities. Callers must handle None rather than assume a category exists.

⚠ A splat with no castes is normal, not misconfiguration — mortals, Ghosts and the
Fae-Blooded are casteless. Ask `splat_has_castes` before demanding caste minimums,
or every mortal sheet carries a spurious error.

⚠ May import `_base` only, never a sibling domain module.
"""

from __future__ import annotations

from ...models.character import Character
from ...models.rules import AbilityName, AttributeName, RuleSet
from ._base import _attribute_category


def splat_has_castes(ruleset: RuleSet, exalt_type: str) -> bool:
    """Whether any caste in the RuleSet belongs to `exalt_type`.

    False for the casteless splats, which "do not select a caste" (core p.103).
    ⚠ True for Lunars: they HAVE castes that merely carry no Caste Abilities, so the
    missing-caste check still applies to them.
    """
    return any(cd.exalt_type == exalt_type for cd in ruleset.castes.values())


def _caste_favored(ruleset: RuleSet, character: Character) -> tuple[set, set] | None:
    """(caste_abilities, favored_abilities) as sets, or None when the caste is not in
    the RuleSet — the caller then reports it and skips caste-dependent checks.

    A Lunar caste yields an empty caste_abilities set (p.90); its discount is
    Attribute-keyed, via `_caste_favored_attribute_category`.
    """
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None:
        return None
    return set(caste_def.caste_abilities), set(character.favored_abilities)


def _caste_favored_attribute_category(ruleset: RuleSet, character: Character) -> str | None:
    """The Attribute category a Lunar's caste favours, or None for any caste with no
    Caste Attributes (every non-Lunar caste, and Lunar Casteless, p.108).

    A Lunar caste's three Caste Attributes are always exactly one whole category
    (p.90-91), so the category of the first one is the answer.
    """
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None or not caste_def.caste_attributes:
        return None
    return _attribute_category(caste_def.caste_attributes[0])


def _caste_favored_attribute_sets(ruleset: RuleSet, character: Character
                                   ) -> tuple[set, set, set]:
    """(caste, favored, remaining) Attribute sets for a caste_favored-mode splat
    (Alchemical, p.60), partitioning all nine Attributes disjointly.

    Caste comes from the caste; favored is the player's picks MINUS any that are also
    Caste; remaining is the rest. ⚠ That subtraction matters: the Caste/Favoured
    overlap is illegal and reported elsewhere, but the accounting here must not
    double-count it. An unknown caste yields an empty caste set.
    """
    caste_def = ruleset.castes.get(character.caste)
    caste = set(caste_def.caste_attributes) if caste_def else set()
    favored = set(character.favored_attributes) - caste
    remaining = set(AttributeName) - caste - favored
    return caste, favored, remaining


def caste_attributes(ruleset: RuleSet, character: Character) -> set[AttributeName]:
    """The character's Caste Attributes (Lunar, p.90-91), empty for a caste with
    none — the set that earns the Caste-Attribute XP/BP discount."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None:
        return set()
    return set(caste_def.caste_attributes)


def _caste_favored_attr_names(ruleset: RuleSet, character: Character) -> set:
    """The Attributes a caste_favored-mode splat (Alchemical) counts as Caste-or-
    Favoured for Charm keying: the caste's Caste Attributes plus the player's Favoured
    Attributes. Empty for category-mode splats.

    ⚠ Empty vs. non-empty IS the mode discriminator for callers: non-empty means match
    a Charm on a SPECIFIC attribute, empty means match on the category instead.
    """
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    if b.attribute_mode != "caste_favored":
        return set()
    caste_def = ruleset.castes.get(character.caste)
    caste = set(caste_def.caste_attributes) if caste_def else set()
    return caste | set(character.favored_attributes)


def caste_favored_abilities(ruleset: RuleSet, character: Character) -> set[AbilityName]:
    """Caste ∪ Favoured abilities — the set that earns the discount on Ability, Charm
    and spell costs, both at chargen and on XP. Falls back to the Favoured set alone
    when the caste is unknown to the RuleSet."""
    cf = _caste_favored(ruleset, character)
    if cf is None:
        return set(character.favored_abilities)
    caste_abilities, favored = cf
    return caste_abilities | favored
