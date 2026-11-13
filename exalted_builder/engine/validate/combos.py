"""
engine/validate/combos.py — Combo legality.

A Combo is a named bundle of Charms bought as one purchase. `combo_issues` checks one,
`validate_combos` checks every Combo held, `eligible_combo_charms` is what the picker
offers.

⚠ Combo legality is one of the corners 1e leaves ambiguous and errata'd. The human is
the rules authority; do not tighten a rule here from inference.
"""

from __future__ import annotations

from ...models.character import Character
from ...models.rules import CharmType, RuleSet
from .. import paths as paths_mod
from ._base import Issue
from .charms import is_martial_arts_charm


# Only Charms of instant duration may be Comboed (core p.213). Compared against
# Charm.duration, whose instant value is the model default "Instant".
_COMBO_DURATION = "Instant"


# Castes that can mix Ability-based and Attribute-based Charms in one Combo (Lunars
# p.122): Solar Eclipse and Abyssal Moonshadow only. Composition only: the p.122
# dice-pool cap of a mixed Combo is out of scope (decision 0008).
_MIXED_COMBO_CASTES = {"eclipse", "moonshadow"}


def combo_issues(ruleset: RuleSet, character: Character, combo) -> list[Issue]:
    """Legality findings for a single Combo (core pp.213-214): two or more *known*
    Charms of instant duration, no Charm twice, at most one Simple and at most one
    Extra Action Charm. `where` is the Combo's name. The picker uses this per-Combo;
    validate_combos aggregates it over the character."""
    issues: list[Issue] = []
    # The Dragon-King Path powers are Combo members (p.177 "Dragon Kings may purchase
    # and use Combos normally") — their virtual Charm rows resolve via ruleset.charms
    # in the loop below, so the only change is folding them into the "known" set.
    known = set(character.charms) | set(paths_mod.path_power_ids(ruleset, character))
    where = combo.name or "(unnamed combo)"
    # A splat barred from Combos outright (the dead — E:Ab p.234, "The dead may never
    # learn Combos and so may never use more than one Charm per turn"). Reported first
    # and alone: every other finding below is about how this Combo is BUILT, which is
    # noise for a character who may not have one at all.
    if not ruleset.exalt_for(character.exalt_type).combos_available:
        return [Issue(
            code="combo-splat-barred", where=where,
            message=(f"{ruleset.exalt_for(character.exalt_type).label} characters may "
                     f"never learn Combos (E:Ab p.234)."),
        )]
    if len(combo.charm_ids) < 2:
        issues.append(Issue(
            code="combo-too-small", where=where,
            message=f"Combo {where!r} has {len(combo.charm_ids)} Charm(s); a Combo "
                    "must combine at least two.",
        ))
    seen: set[str] = set()
    simple = extra_action = 0
    has_attribute_charm = has_ability_charm = False
    for cid in combo.charm_ids:
        if cid in seen:
            issues.append(Issue(
                code="combo-duplicate-charm", where=where,
                message=f"Combo {where!r} includes {cid!r} more than once; a Combo "
                        "may not repeat a Charm.",
            ))
            continue
        seen.add(cid)
        if cid not in known:
            issues.append(Issue(
                code="combo-unknown-charm", where=where,
                message=f"Combo {where!r} includes {cid!r}, which the character "
                        "does not know.",
            ))
            continue
        charm = ruleset.charms.get(cid)
        if charm is None:                 # known id absent from the set: check_references reports it
            continue
        if charm.duration != _COMBO_DURATION:
            issues.append(Issue(
                code="combo-non-instant", where=where,
                message=f"Combo {where!r}: {charm.name} has {charm.duration} duration; "
                        "Combos may only contain instant-duration Charms.",
            ))
        if charm.type == CharmType.SIMPLE:
            simple += 1
        elif charm.type == CharmType.EXTRA_ACTION:
            extra_action += 1
        if charm.min_attribute:
            has_attribute_charm = True
        else:
            has_ability_charm = True
    if simple > 1:
        issues.append(Issue(
            code="combo-multiple-simple", where=where,
            message=f"Combo {where!r} has {simple} Simple Charms; a Combo may "
                    "contain at most one.",
        ))
    if extra_action > 1:
        issues.append(Issue(
            code="combo-multiple-extra-action", where=where,
            message=f"Combo {where!r} has {extra_action} Extra Action Charms; a "
                    "Combo may contain at most one.",
        ))
    if (has_attribute_charm and has_ability_charm
            and character.caste not in _MIXED_COMBO_CASTES):
        issues.append(Issue(
            code="combo-mixed-attribute-ability", where=where,
            message=f"Combo {where!r} mixes an Attribute-based Charm with an "
                    "Ability-based Charm; only Solar Eclipse and Abyssal "
                    "Moonshadow Charms may cross the two systems in one Combo.",
        ))
    return issues


def eligible_combo_charms(ruleset: RuleSet, character: Character) -> list[str]:
    """Return the ids of known Charms that can go in a Combo: instant duration (core
    p.213). The Charm list order, then the instant Path powers (p.177)."""
    out: list[str] = []
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm is not None and charm.duration == _COMBO_DURATION:
            out.append(cid)
    for cid in paths_mod.path_power_ids(ruleset, character):
        charm = ruleset.charms.get(cid)
        if charm is not None and charm.duration == _COMBO_DURATION:
            out.append(cid)
    return out


def validate_combos(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of every Combo the character holds (core pp.213-214). The
    Storyteller veto of specific Combos and the in-play activation rules are out of
    scope here; the bonus-point cost is accounted in validate_chargen. Operates on
    the character's current Charms/Combos (like the other reference checks)."""
    issues: list[Issue] = []
    for combo in character.combos:
        issues += combo_issues(ruleset, character, combo)
    return issues
