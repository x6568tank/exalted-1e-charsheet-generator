"""
engine/validate/castes.py — which traits a character's caste makes caste/favoured.

A bottom-of-graph module like `_base`, split out because two domains need it and
neither owns it: `charms` (is this Charm caste/favoured, hence cheaper and eligible
for the ≥5 chargen minimum) and the chargen budgets (the same question for
Attributes and Abilities).

The Ability answer and the Attribute answer are deliberately separate functions.
Most splats favour Abilities; the Lunars favour an Attribute CATEGORY
(Physical/Social/Mental) instead, so `_caste_favored_attribute_category` returns
None for everyone else and callers must handle that rather than assume a category
exists.

⚠ A splat with no castes at all is normal, not an error — mortals, Ghosts and the
Fae-Blooded are casteless, and `splat_has_castes` is how the budget code asks
before demanding caste minimums.

⚠ May import `_base` only. Nothing here may import a sibling domain module.
"""

from __future__ import annotations

from ...models.character import Character
from ...models.rules import AbilityName, AttributeName, RuleSet
from ._base import _attribute_category


def splat_has_castes(ruleset: RuleSet, exalt_type: str) -> bool:
    """Does this splat have any castes to choose from? False only for the casteless
    splats — mortals "select Nature as normal but do not select a caste" (core p.103).
    Distinct from a Lunar, who HAS castes that simply carry no Caste Abilities: a
    Lunar caste row exists, so this is True for them and the missing-caste check
    still applies. Data-driven, so the next casteless splat needs no code."""
    return any(cd.exalt_type == exalt_type for cd in ruleset.castes.values())


def _caste_favored(ruleset: RuleSet, character: Character) -> tuple[set, set] | None:
    """(caste_abilities, favored_abilities) as sets, or None if the caste is not
    in the RuleSet (caller emits an issue and skips caste-dependent checks). For a
    Lunar caste (caste_attributes set, caste_abilities empty — p.90), the caste
    contributes no Ability discount here; its discount is Attribute-keyed and
    handled separately by `_caste_favored_attribute_category`."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None:
        return None
    return set(caste_def.caste_abilities), set(character.favored_abilities)


def _caste_favored_attribute_category(ruleset: RuleSet, character: Character) -> str | None:
    """The Attribute category (Physical/Social/Mental) a Lunar's caste favors, or
    None for a caste with no Caste Attributes (every non-Lunar caste, and the
    Lunar Casteless caste, p.108). Full Moon/Changing Moon/No Moon's three Caste
    Attributes are always exactly one whole ATTRIBUTE_CATEGORIES group (p.90-91),
    so the category of any one of them is the caste's favored category."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None or not caste_def.caste_attributes:
        return None
    return _attribute_category(caste_def.caste_attributes[0])


def _caste_favored_attribute_sets(ruleset: RuleSet, character: Character
                                   ) -> tuple[set, set, set]:
    """(caste, favored, remaining) Attribute sets for a caste_favored-mode splat
    (Alchemical, p.60), partitioning all nine Attributes disjointly. Caste
    Attributes come from the caste; Favored are the player's chosen ones with any
    that also happen to be Caste removed (that overlap is illegal and flagged
    separately, but the accounting must not double-count); remaining is everything
    else. An unknown caste yields an empty caste set (validate emits unknown-caste)."""
    caste_def = ruleset.castes.get(character.caste)
    caste = set(caste_def.caste_attributes) if caste_def else set()
    favored = set(character.favored_attributes) - caste
    remaining = set(AttributeName) - caste - favored
    return caste, favored, remaining


def caste_attributes(ruleset: RuleSet, character: Character) -> set[AttributeName]:
    """The character's Caste Attributes (Lunar, p.90-91), or an empty set for a
    caste with none (every non-Lunar caste and the Lunar Casteless caste). This is
    the set that earns the Caste-Attribute XP/BP discount, the Attribute parallel
    to `caste_favored_abilities`."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None:
        return set()
    return set(caste_def.caste_attributes)


def _caste_favored_attr_names(ruleset: RuleSet, character: Character) -> set:
    """The set of AttributeName a caste_favored-mode splat (Alchemical) counts as
    Caste-or-Favored for the purpose of Charm keying — the caste's Caste Attributes
    plus the player's Favored Attributes. Empty for category-mode splats (Lunar/
    Solar/...), which is also the discriminator: a non-empty set means caste_favored
    mode, so a Charm's Caste/Favored-ness is a SPECIFIC-attribute match rather than
    the category match category-mode splats use."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    if b.attribute_mode != "caste_favored":
        return set()
    caste_def = ruleset.castes.get(character.caste)
    caste = set(caste_def.caste_attributes) if caste_def else set()
    return caste | set(character.favored_attributes)


def caste_favored_abilities(ruleset: RuleSet, character: Character) -> set[AbilityName]:
    """The character's Caste ∪ Favoured abilities — the set that earns the discount
    on Ability/Charm/spell costs. Falls back to just the Favoured set if the caste
    is unknown to the RuleSet. Shared by chargen and XP costing."""
    cf = _caste_favored(ruleset, character)
    if cf is None:
        return set(character.favored_abilities)
    caste_abilities, favored = cf
    return caste_abilities | favored
