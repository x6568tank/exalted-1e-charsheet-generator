"""
engine/validate/alchemical.py — Charm Slots, Arrays and Submodules.

The Alchemical Exalted install Charms into a fixed number of Slots rather than learning
them outright, group them into Arrays, and buy Submodules hanging off an installed
Charm. This module owns Array and Submodule legality and the installation mote cost.

⚠ Slot COUNTING lives in `charms.py` with the rest of the Charm economy, not here.
`_installation_motes` is the back-edge `charms.charm_slot_usage` reaches for, which is
why that call is deferred to call time.
"""

from __future__ import annotations

from ...models.character import Character
from ...models.rules import AttributeName, RuleSet
from ._base import Issue
from .charms import charm_occupies_slot, meets_charm_requirements, uses_charm_slots


def eligible_array_charms(ruleset: RuleSet, character: Character) -> list[str]:
    """Ids of the character's known Charms that may legally be linked into an Array
    (p.89) — Attribute-based and `arrayable`, which excludes the Ability-based
    supernatural martial arts and the Weaving Engines. Order follows the character's
    Charm list. This is the Array counterpart of `eligible_combo_charms`: it does NOT
    exclude Charms already sitting in an Array (`validate_arrays` reports reuse), so
    the caller decides whether to offer them again."""
    out: list[str] = []
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm is not None and charm.min_attribute and charm.arrayable:
            out.append(cid)
    return out


def array_issues(ruleset: RuleSet, character: Character, array) -> list[Issue]:
    """Legality findings for a single Alchemical Array (p.89): two or more *known*
    Charms, no Charm twice, and every member Attribute-based (supernatural martial
    arts, which are Ability-based, may not join). The instant-duration / one-Simple
    limits are NOT checked here — they bound the integrated Combos an Array grants,
    not the Array itself. `where` is the Array's name."""
    issues: list[Issue] = []
    known = set(character.charms)
    where = array.name or "(unnamed array)"
    if len(array.charm_ids) < 2:
        issues.append(Issue(
            code="array-too-small", where=where,
            message=f"Array {where!r} has {len(array.charm_ids)} Charm(s); an Array "
                    "must link at least two.",
        ))
    seen: set[str] = set()
    for cid in array.charm_ids:
        if cid in seen:
            issues.append(Issue(
                code="array-duplicate-charm", where=where,
                message=f"Array {where!r} includes {cid!r} more than once; link a "
                        "second copy of the Charm into a separate Array instead.",
            ))
            continue
        seen.add(cid)
        if cid not in known:
            issues.append(Issue(
                code="array-unknown-charm", where=where,
                message=f"Array {where!r} includes {cid!r}, which the character "
                        "does not know.",
            ))
            continue
        charm = ruleset.charms.get(cid)
        if charm is None:                 # known id absent from the set: check_references reports it
            continue
        if not charm.min_attribute:
            issues.append(Issue(
                code="array-non-attribute-charm", where=where,
                message=f"Array {where!r}: {charm.name} is not Attribute-based; only "
                        "Attribute-based Charms may be linked into an Array (this "
                        "excludes supernatural martial arts).",
            ))
        elif not charm.arrayable:
            issues.append(Issue(
                code="array-charm-not-arrayable", where=where,
                message=f"Array {where!r}: {charm.name} may not be placed in an Array.",
            ))
    return issues


def validate_arrays(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of every Array the character holds (p.89). Adds two cross-Array
    rules to the per-Array checks: only a Charm-Slot splat may build Arrays (p.90 —
    Eclipse/Moonshadow may not), and a Charm may sit in at most one Array unless
    bought again (there is only one copy of each id on the character)."""
    issues: list[Issue] = []
    if not character.arrays:
        return issues
    slots = uses_charm_slots(ruleset, character)
    seen_charms: set[str] = set()
    for array in character.arrays:
        where = array.name or "(unnamed array)"
        if not slots:
            issues.append(Issue(
                code="array-not-supported", where=where,
                message=f"Array {where!r}: only Alchemical Exalted build Arrays "
                        "(Eclipse and Moonshadow Caste may not, p.90).",
            ))
        issues += array_issues(ruleset, character, array)
        for cid in set(array.charm_ids):
            if cid in seen_charms:
                issues.append(Issue(
                    code="array-charm-reused", where=where,
                    message=f"Array {where!r} reuses {cid!r}, already linked into "
                            "another Array; a Charm may join only one Array unless "
                            "purchased again.",
                ))
            seen_charms.add(cid)
    return issues


def submodule_def(ruleset: RuleSet, charm_id: str, key: str):
    """The rules.Submodule with `key` on Charm `charm_id`, or None if either the
    Charm or the key is absent."""
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        return None
    return next((s for s in charm.submodules if s.key == key), None)


def owns_submodule(character: Character, charm_id: str, key: str) -> bool:
    """Whether the character has already purchased this submodule."""
    return any(s.charm_id == charm_id and s.key == key for s in character.submodules)


def submodule_block_reason(ruleset: RuleSet, character: Character,
                           charm_id: str, key: str) -> str:
    """Why this submodule cannot be purchased right now — "" when it can. The same
    gates `validate_submodules` and `advancement.learn_submodule` apply (parent Charm
    installed, own Essence and Attribute minimums), phrased for the picker so the UI
    never re-derives them. Says nothing about affordability: BP and XP are the
    caller's budget question, not a legality one."""
    definition = submodule_def(ruleset, charm_id, key)
    if definition is None:
        return "No such submodule."
    if owns_submodule(character, charm_id, key):
        return "Already purchased."
    if charm_id not in character.charms:
        charm = ruleset.charms.get(charm_id)
        return f"Install {charm.name if charm else charm_id} first."
    if character.essence_rating < definition.min_essence:
        return f"Requires Essence {definition.min_essence}."
    if definition.min_attribute:
        try:
            attr = AttributeName(definition.min_attribute)
        except ValueError:
            return f"Unknown Attribute {definition.min_attribute!r}."
        if character.attributes.get(attr, 0) < definition.min_attribute_rating:
            return (f"Requires {definition.min_attribute.title()} "
                    f"{definition.min_attribute_rating}.")
    return ""


def validate_submodules(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of every purchased submodule (p.89): its parent Charm must exist and
    be known, the key must be a real submodule of that Charm, no submodule bought
    twice, and the character must meet the submodule's own Essence / Attribute
    minimums. Used for both chargen (BP) and post-lock (XP) purchases."""
    issues: list[Issue] = []
    seen: set[tuple[str, str]] = set()
    known = set(character.charms)
    for sub in character.submodules:
        where = f"{sub.charm_id}:{sub.key}"
        pair = (sub.charm_id, sub.key)
        if pair in seen:
            issues.append(Issue(
                code="submodule-duplicate", where=where,
                message=f"Submodule {where!r} is purchased more than once.",
            ))
            continue
        seen.add(pair)
        charm = ruleset.charms.get(sub.charm_id)
        if charm is None:
            issues.append(Issue(
                code="submodule-unknown-charm", where=where,
                message=f"Submodule {where!r} names Charm {sub.charm_id!r}, which is "
                        "not in the rule set.",
            ))
            continue
        definition = submodule_def(ruleset, sub.charm_id, sub.key)
        if definition is None:
            issues.append(Issue(
                code="submodule-unknown", where=where,
                message=f"{charm.name} has no submodule {sub.key!r}.",
            ))
            continue
        if sub.charm_id not in known:
            issues.append(Issue(
                code="submodule-charm-not-known", where=where,
                message=f"Submodule {definition.name}: its Charm {charm.name} is not "
                        "known/installed.",
            ))
        if character.essence_rating < definition.min_essence:
            issues.append(Issue(
                code="submodule-essence", where=where,
                message=f"Submodule {definition.name} requires Essence "
                        f"{definition.min_essence}; has {character.essence_rating}.",
            ))
        if definition.min_attribute:
            try:
                attr = AttributeName(definition.min_attribute)
            except ValueError:
                attr = None
            have = character.attributes.get(attr, 0) if attr is not None else 0
            if have < definition.min_attribute_rating:
                issues.append(Issue(
                    code="submodule-attribute", where=where,
                    message=f"Submodule {definition.name} requires "
                            f"{definition.min_attribute} {definition.min_attribute_rating}; "
                            f"has {have}.",
                ))
    return issues


def array_installation_motes(ruleset: RuleSet, charm_ids) -> int:
    """The combined installation cost of one Array's member Charms (p.89):
    three-fourths of their summed cost, rounded up. Public so the UI can show an
    Array's mote saving using the same arithmetic the chargen check applies."""
    total = sum(ruleset.charms[cid].installation_cost
                for cid in charm_ids if cid in ruleset.charms)
    return (3 * total + 3) // 4              # ceil(3/4 * total)


def _installation_motes(ruleset: RuleSet, charm_ids, arrays) -> int:
    """Total Personal Essence committed to install `charm_ids`, applying the Array
    discount (p.89): a Charm inside an Array contributes to that Array's combined
    installation cost, which is three-fourths of the sum, rounded up; a Charm in no
    Array contributes its own full installation cost."""
    array_of: dict[str, int] = {}
    for i, arr in enumerate(arrays):
        for cid in arr.charm_ids:
            array_of.setdefault(cid, i)      # first Array wins (reuse is flagged elsewhere)
    loose = 0
    grouped: dict[int, list[str]] = {}
    for cid in charm_ids:
        if cid not in ruleset.charms:
            continue
        if cid in array_of:
            grouped.setdefault(array_of[cid], []).append(cid)
        else:
            loose += ruleset.charms[cid].installation_cost
    return loose + sum(array_installation_motes(ruleset, ids)
                       for ids in grouped.values())
