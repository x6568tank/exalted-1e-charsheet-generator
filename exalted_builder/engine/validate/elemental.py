"""
engine/validate/elemental.py — Dragon-Blooded Elemental Powers.

A rated subsystem gated on the character's Aspect. `elemental_powers_available` says
whether the character has the subsystem at all, `legal_elemental_powers` is what the
picker offers, and `elemental_power_issues` validates what they hold.

⚠ `elemental_power_issues` runs on BOTH sides of the lock and reads the LIVE
`character.elemental_powers`, not the snapshot: powers are bought in play as well as
at creation, so the snapshot only ever holds the chargen picks and a snapshot-only
read would go dead at the lock.
"""

from __future__ import annotations

from ...models.character import Character
from ...models.rules import RuleSet
from .. import merits
from ._base import Issue, ability_rating


def elemental_powers_available(ruleset: RuleSet, character: Character) -> bool:
    """Whether the elemental-powers catalogue is open to this character at all — the
    Elemental-origin God-Blooded gate (PG p.68, "descendents of elementals draw on the
    innate powers of their heritage"). The UI reads this to decide whether the picker
    page exists; every requirement check starts from it too.

    The gate is CASTE-level, not just splat-and-origin: the retired Merit's printed
    restriction barred every heritage but god-blooded (`barred_castes`), and "Elemental"
    is only an origin option on the god-blooded row — so a hand-edited save with
    `caste="demon-blooded"` + `origin="Elemental"` must NOT open the catalogue. `origin`
    alone is not enough; a stray origin string could pass it."""
    return (character.exalt_type == "God-Blooded"
            and character.caste == "god-blooded"
            and character.origin == "Elemental")


def legal_elemental_powers(ruleset: RuleSet, character: Character) -> list[str]:
    """The Elemental Powers a heritage change leaves the character able to hold.
    The catalogue belongs to the Elemental origin alone (see elemental_powers_available),
    so any structural switch away from it orphans every held power — the picker tab
    vanishes, the BP breakdown keeps charging, and validation errors with no UI path to
    remove them. The editor reads this after a heritage/caste/origin switch and drops
    whatever it no longer authorizes (the same shape as default_camp_and_calling: the
    engine decides, the UI applies)."""
    return list(character.elemental_powers) if elemental_powers_available(ruleset, character) else []


def meets_elemental_power_requirements(ruleset: RuleSet, character: Character, power) -> bool:
    """Whether the character could legally learn `power` right now: Elemental origin,
    min Essence, and every Merit in `required_merits` held. The forward-looking
    counterpart of elemental_power_issues, used by the picker to decide which powers
    are selectable. Ownership is excluded exactly as meets_charm_requirements excludes
    it — the caller checks "already owned" separately."""
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
    """Legality of the character's elemental powers (PG p.68): an unknown id, an
    origin that bars them, Essence below minimum, or a missing required Merit.
    Mirrors merit_issues — structural only, and what a power DOES is descriptive
    text, not modelled mechanics (decision 0008)."""
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
