"""
engine/validate/elemental.py — Dragon-Blooded Elemental Powers.

A rated subsystem gated on the character's Aspect. `elemental_powers_available` says
whether the character has the subsystem, `legal_elemental_powers` is what the picker
offers, `elemental_power_issues` validates what is held.

⚠ `elemental_power_issues` runs on BOTH sides of the lock and reads the LIVE
`character.elemental_powers`, never the snapshot. Powers are bought in play as well as
at creation, so the snapshot holds only the chargen picks and a snapshot read goes dead
at the lock.
"""

from __future__ import annotations

from ...models.character import Character
from ...models.rules import RuleSet
from .. import merits
from ._base import Issue, ability_rating


def elemental_powers_available(ruleset: RuleSet, character: Character) -> bool:
    """Return True if the elemental-powers catalogue is open: Elemental-origin
    God-Blooded (PG p.68). The UI uses it for the picker page.

    ⚠ Test the CASTE too, not only the origin: a stray origin string on a different
    heritage must not open the catalogue."""
    return (character.exalt_type == "God-Blooded"
            and character.caste == "god-blooded"
            and character.origin == "Elemental")


def legal_elemental_powers(ruleset: RuleSet, character: Character) -> list[str]:
    """Return the held Elemental Powers that the character can still hold after a
    heritage change. The editor drops the others: else they stay charged with no UI
    to remove them."""
    return list(character.elemental_powers) if elemental_powers_available(ruleset, character) else []


def meets_elemental_power_requirements(ruleset: RuleSet, character: Character, power) -> bool:
    """Return True if the character can learn `power` now: Elemental origin, min
    Essence, and each `required_merits` held. Ownership is not checked."""
    if not elemental_powers_available(ruleset, character):
        return False
    if character.essence_rating < power.min_essence:
        return False
    held = merits.merit_ids_held(character)
    return all(mid in held for mid in power.required_merits)


def elemental_power_shortfalls(ruleset: RuleSet, character: Character, power) -> list[str]:
    """Human-readable reasons `power` is not learnable right now; empty when it is.
    Used by the picker for the button tooltip."""
    out = []
    if not elemental_powers_available(ruleset, character):
        out.append("only Elemental-origin God-Blooded may learn elemental powers")
    if character.essence_rating < power.min_essence:
        out.append(f"requires Essence {power.min_essence}")
    held = merits.merit_ids_held(character)
    for mid in power.required_merits:
        if mid not in held:
            definition = ruleset.merits_flaws.get(mid)
            out.append(f"requires the {definition.name if definition else mid} Merit")
    return out


def elemental_power_issues(ruleset: RuleSet, character: Character,
                           power_ids: list[str]) -> list[Issue]:
    """Check the elemental powers (PG p.68): an unknown id, an origin that bars them,
    Essence below minimum, or a missing required Merit. Structural only: the effect of
    a power is text (decision 0008)."""
    issues: list[Issue] = []
    for pid in power_ids:
        power = ruleset.elemental_powers.get(pid)
        if power is None:
            # Unknown ids are check_references' job (the same split as unknown-charm /
            # unknown-spell): this function only reports legality for RESOLVED powers,
            # so a deleted/renamed power surfaces exactly one issue.
            continue
        if not elemental_powers_available(ruleset, character):
            issues.append(Issue(
                code="elemental-power-wrong-origin", where=pid,
                message=f"{power.name} is restricted to Elemental-origin God-Blooded; "
                        f"this character is a {character.origin or 'blank'} "
                        f"{character.exalt_type}.",
            ))
        if character.essence_rating < power.min_essence:
            issues.append(Issue(
                code="elemental-power-low-essence", where=pid,
                message=f"{power.name} requires Essence {power.min_essence}; "
                        f"this character has Essence {character.essence_rating}.",
            ))
        held = merits.merit_ids_held(character)
        for mid in power.required_merits:
            if mid not in held:
                definition = ruleset.merits_flaws.get(mid)
                issues.append(Issue(
                    code="elemental-power-missing-merit", where=pid,
                    message=f"{power.name} requires the "
                            f"{definition.name if definition else mid} Merit.",
                ))
    return issues
