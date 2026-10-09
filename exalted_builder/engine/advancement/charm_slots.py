"""
engine/advancement/charm_slots.py — the Alchemical Charm-Slot economy after the
lock (Autochthonians p.64, p.89): slots, retainer Charms, and Submodules.
"""

from __future__ import annotations

from .. import costs, validate
from ...models.character import Character, SubmodulePurchase, XpEntry
from ...models.rules import AttributeName, RuleSet

from ._base import AdvancementError, _commit, _ensure_locked


# --------------------------------------------------------------------------- #
# Alchemical Charm-Slot economy (post-lock; Autochthonians p.64, p.89)
# --------------------------------------------------------------------------- #

def _require_slot_splat(ruleset: RuleSet, character: Character) -> None:
    if not validate.uses_charm_slots(ruleset, character):
        raise AdvancementError("Charm Slots are an Alchemical mechanic.")


def _installable_charm(ruleset: RuleSet, character: Character, charm_id: str):
    """Shared gate for a Charm the character is about to gain (Slot or Panoply): it
    exists, is not already owned (installed or on retainer), is learnable by the
    splat, and its requirements are met. Returns the Charm."""
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        raise AdvancementError(f"Unknown Charm {charm_id!r}.")
    if charm_id in character.charms or charm_id in character.retainer_charms:
        raise AdvancementError(f"{charm.name} is already owned.")
    if not validate.charm_learnable_by_splat(ruleset, character, charm):
        raise AdvancementError(
            f"{charm.name} belongs to another Exalt type ({validate.splat_of(charm)}).")
    if not validate.meets_charm_requirements(ruleset, character, charm):
        raise AdvancementError(f"{charm.name}: requirements not met.")
    return charm


def buy_charm_slot(ruleset: RuleSet, character: Character, *, dedicated: bool,
                   charm_id: str) -> XpEntry:
    """Buy one more Charm Slot (p.64): General (12) or Dedicated (10). The Slot comes
    with a free Charm of the player's choice that must fit the Slot — a Dedicated Slot
    holds only a Caste/Favored-Attribute Charm. The Charm is installed (added to
    `charms`); the Slot count is incremented."""
    _ensure_locked(character)
    _require_slot_splat(ruleset, character)
    charm = _installable_charm(ruleset, character, charm_id)
    if dedicated and not validate.charm_fits_dedicated_slot(ruleset, character, charm):
        raise AdvancementError(
            f"{charm.name} is not keyed to a Caste/Favored Attribute, so it cannot "
            f"fill a Dedicated Slot; buy a General Slot instead.")
    g, d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
    cost = costs.charm_slot_cost(ruleset, character, dedicated=dedicated)
    kind = "dedicated" if dedicated else "general"
    frm = d if dedicated else g
    entry = _commit(character, f"charm_slots.{kind}", charm_id, frm, frm + 1, cost)
    if dedicated:
        character.dedicated_charm_slots = d + 1
    else:
        character.general_charm_slots = g + 1
    character.charms.append(charm_id)
    return entry


def upgrade_charm_slot(ruleset: RuleSet, character: Character) -> XpEntry:
    """Upgrade one Dedicated Charm Slot to a General Slot (p.64, 2 XP). Requires a
    Dedicated Slot to exist."""
    _ensure_locked(character)
    _require_slot_splat(ruleset, character)
    g, d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
    if d <= 0:
        raise AdvancementError("No Dedicated Charm Slot to upgrade.")
    cost = costs.charm_slot_upgrade_cost(ruleset, character)
    # Ratings left None: this swaps two counts, not a single-trait change, and a
    # to<from would be misread as a free reduction by the audit.
    entry = _commit(character, "charm_slot_upgrade", "", None, None, cost)
    character.dedicated_charm_slots = d - 1
    character.general_charm_slots = g + 1
    return entry


def learn_retainer_charm(ruleset: RuleSet, character: Character, charm_id: str) -> XpEntry:
    """Buy one Panoply (retainer) Charm WITHOUT a Slot. A native Alchemical pays the
    flat 6 XP (p.64); an Eclipse/Moonshadow may instead add an Alchemical Charm to their
    Panoply through the crossover at their caste's flat rate (p.90, 8) as a cheaper
    alternative to a Slot. Either way the Charm is owned but not installed."""
    _ensure_locked(character)
    native = validate.uses_charm_slots(ruleset, character)
    crossover = validate.crossover_panoply_xp(ruleset, character) is not None
    if not native and not crossover:
        raise AdvancementError(
            "Panoply Charms are an Alchemical mechanic (or the Eclipse/Moonshadow "
            "Alchemical crossover, p.90).")
    charm = _installable_charm(ruleset, character, charm_id)
    # A crossover Panoply holds Alchemical Charms specifically (p.90).
    if not native and not validate.splat_uses_charm_slots(ruleset, validate.splat_of(charm)):
        raise AdvancementError(
            f"{charm.name} is not an Alchemical Charm; only Alchemical Charms go on the "
            f"crossover Panoply.")
    cost = costs.retainer_charm_cost(ruleset, character)
    entry = _commit(character, "retainer_charms", charm_id, None, None, cost)
    character.retainer_charms.append(charm_id)
    return entry


def learn_submodule(ruleset: RuleSet, character: Character,
                    charm_id: str, key: str) -> XpEntry:
    """Buy an Alchemical submodule (p.89) post-lock for its `xp_cost`. The parent
    Charm must be known and the submodule's own Essence/Attribute minimums met."""
    _ensure_locked(character)
    definition = validate.submodule_def(ruleset, charm_id, key)
    if definition is None:
        raise AdvancementError(f"No submodule {key!r} on Charm {charm_id!r}.")
    if charm_id not in character.charms:
        raise AdvancementError(f"Charm {charm_id!r} is not known; install it first.")
    if any(s.charm_id == charm_id and s.key == key for s in character.submodules):
        raise AdvancementError(f"Submodule {definition.name} is already owned.")
    if character.essence_rating < definition.min_essence:
        raise AdvancementError(
            f"{definition.name} requires Essence {definition.min_essence}.")
    if definition.min_attribute:
        attr = AttributeName(definition.min_attribute)
        if character.attributes.get(attr, 0) < definition.min_attribute_rating:
            raise AdvancementError(
                f"{definition.name} requires {definition.min_attribute} "
                f"{definition.min_attribute_rating}.")
    entry = _commit(character, "submodules", f"{charm_id}:{key}", None, None,
                    definition.xp_cost)
    character.submodules.append(SubmodulePurchase(charm_id=charm_id, key=key))
    return entry
