"""
engine/advancement/audit.py — the XP log audit: the expected cost of each row,
and `validate_xp`.
"""

from __future__ import annotations

from .. import costs, merits, validate
from ...models.character import Character, XpEntry
from ...models.rules import AbilityName, AttributeName, RuleSet, VirtueName

from ._base import xp_available, xp_spent


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #

def _expected_cost(ruleset: RuleSet, character: Character, entry: XpEntry) -> int | None:
    """Recompute what `entry` should have cost from the XP table, or None when it
    cannot be priced (e.g. an id no longer in the rule set)."""
    domain, _, key = entry.target.partition(".")
    frm = entry.from_rating
    # Permanent Resonance is priced per DIRECTION and must be tested before the generic
    # reduction rule below, which would otherwise make the five-point shed free.
    if domain == validate.PERMANENT_RESONANCE_TARGET:
        if frm is not None and entry.to_rating is not None and entry.to_rating < frm:
            return merits.PERMANENT_RESONANCE_SHED_XP      # shed: five XP and a Harrowing
        return 0                                          # gained: inflicted, not bought
    # A permanent reduction (curse / Charm cost) is free and refunds no XP.
    if frm is not None and entry.to_rating is not None and entry.to_rating < frm:
        return 0
    if domain == "attributes" and frm is not None:
        attr = AttributeName(key) if key else None
        return costs.attribute_step(ruleset, character, frm, attr)
    if domain == "abilities" and frm is not None:
        return costs.ability_step(ruleset, character, AbilityName(key), frm)
    if domain == "crafts" and frm is not None:
        return costs.ability_step(ruleset, character, AbilityName.CRAFT, frm)
    if domain == "colleges" and frm is not None:
        return (costs.college_new_cost(ruleset, character) if frm <= 0
                else costs.college_step(ruleset, character, frm))
    if domain == "virtues" and frm is not None:
        return costs.virtue_step(ruleset, character, frm,
                                 VirtueName(key) if key else None)
    if domain == "willpower" and frm is not None:
        return costs.willpower_step(ruleset, character, frm)
    if domain == "essence" and frm is not None:
        return costs.essence_step(ruleset, character, frm)
    if domain == validate.WITHHELD_CHARM_TARGET:
        # Paid with a banked chargen pick, not XP. Free by rule, so the table rate must
        # not be re-applied here.
        return 0
    if domain in ("charms", "crossover_charms"):
        charm = ruleset.charms.get(entry.detail)
        return costs.charm_cost(ruleset, character, charm) if charm else None
    if domain == "elemental_powers":
        power = ruleset.elemental_powers.get(entry.detail)
        return costs.elemental_power_xp(ruleset, character, power) if power else None
    if domain == "spells":
        spell = ruleset.spells.get(entry.detail)
        return costs.spell_cost(ruleset, character, spell) if spell else None
    if domain == "charm_slots":
        return costs.charm_slot_cost(ruleset, character, dedicated=(key == "dedicated"))
    if domain == "charm_slot_upgrade":
        return costs.charm_slot_upgrade_cost(ruleset, character)
    if domain == "retainer_charms":
        return costs.retainer_charm_cost(ruleset, character)
    if domain == "specialties":
        return costs.specialty_cost(ruleset, character)
    if domain == "combos":
        combo = next((c for c in character.combos if c.name == entry.detail), None)
        return costs.combo_cost(ruleset, combo.charm_ids) if combo else None
    if domain == "arrays":
        array = next((a for a in character.arrays if a.name == entry.detail), None)
        return costs.array_cost(ruleset, array.charm_ids) if array else None
    if domain == "ox_body":
        return costs.ox_body_cost(ruleset, character)
    if domain == "ox_body_slot":
        return costs.charm_slot_cost(ruleset, character, dedicated=(key == "dedicated"))
    if domain == "martial_arts":
        return costs.martial_arts_charm_cost(ruleset, character)
    if domain == "beastman_gifts":
        return costs.gift_cost(ruleset, character)
    if domain == "variant_purchases":
        cid, _, _keys = entry.detail.partition(":")
        return costs.variant_purchase_cost(ruleset, character, ruleset.charms.get(cid))
    if domain == "submodules":
        cid, _, k = entry.detail.partition(":")
        definition = validate.submodule_def(ruleset, cid, k)
        return definition.xp_cost if definition is not None else None
    if domain == "thaum_arts":
        return costs.thaum_art_xp(ruleset, character)
    if domain == "thaum_specialties":
        # `narrowed` halves the price and cannot change after purchase, so reading it
        # back off the character re-prices the row exactly.
        art_id, _, name = entry.detail.partition(":")
        state = validate.thaum_state(character)
        spec = next((s for s in state.art_specialties
                     if s.art_id == art_id and s.name == name), None)
        return costs.thaum_specialty_xp(ruleset, character,
                                        narrowed=bool(spec and spec.narrowed))
    if domain == "thaum_sciences" and frm is not None:
        return costs.thaum_science_step_xp(ruleset, character, frm)
    if domain == "thaum_rituals" and entry.to_rating is not None:
        # Level rides on the log row, so a custom ritual (absent from the catalogue)
        # and a catalogue one re-price identically. One orientation per row by
        # construction — extra versions are their own rows.
        return costs.thaum_ritual_xp(ruleset, character, entry.to_rating, 1)
    if domain == "thaum_formulas":
        return costs.thaum_formula_xp(ruleset, character, 1)
    if domain == "thaum_orientations":
        return costs.thaum_orientation_xp(ruleset, character)
    return None


def validate_xp(ruleset: RuleSet, character: Character) -> list[validate.Issue]:
    """Audit the XP log of a locked character: no overspend, and each row priced at
    the table rate. Pure (returns Issues; mutates nothing). Empty for an unlocked
    character — XP is a post-lock concern."""
    if not character.chargen_locked or character.chargen_snapshot is None:
        return []
    issues: list[validate.Issue] = []
    spent = xp_spent(character)
    if spent > character.xp_earned:
        issues.append(validate.Issue(
            code="xp-overspent",
            message=f"Spent {spent} XP but only {character.xp_earned} earned.",
        ))
    for entry in character.xp_log:
        expected = _expected_cost(ruleset, character, entry)
        if expected is not None and expected != entry.cost:
            issues.append(validate.Issue(
                code="xp-cost-mismatch", where=entry.target,
                message=(f"{entry.target}: logged {entry.cost} XP, "
                         f"table rate is {expected}."),
            ))
    issues.append(validate.Issue(
        code="xp-summary", severity="info",
        message=f"{spent} of {character.xp_earned} XP spent "
                f"({xp_available(character)} available).",
    ))
    return issues
