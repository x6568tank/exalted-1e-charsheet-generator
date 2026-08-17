"""
engine/validate/illuminated.py — the Cult of the Illuminated: Camps and Callings.

An alt-origin for Solars and Dragon-Blooded. The character picks a Camp and a Calling;
the Calling grants Charms and sets Ability minimums.

⚠ `camp_for` searches EVERY camp while `camps_for` searches only the character's. A UI
select whose value resolves against a global table while its options are scoped is a
build-time crash waiting for a second owner to exist — which is what shipping Cult
Dragon-Blooded did.

⚠ The Cult prints its OWN Artifact Background, so catalogue entries must be keyed by
ID, not name. A name matches both the Cult's copy and the corebook's, and the
displacement rule then hands the wrong splat the reworked one.

⚠ Cult Abyssals are deferred indefinitely (human, 2026-08-14) — 56 Charms would need
human-approved mappings. Not a gap; do not propose it.
"""

from __future__ import annotations

from ...models.rules import RuleSet
from ._base import Issue, ability_rating
from .charms import _charm_name, charm_ability_shortfalls


def camp_for(ruleset, character):
    """The character's TrainingCamp, or None. `camp` is only meaningful for an origin
    whose budget sets `requires_camp` (Cult of the Illuminated, p.89), but a stray id
    still resolves here — legality is `check_camp_and_calling`'s job."""
    return ruleset.camps.get(character.camp) if character.camp else None


def calling_for(ruleset, character):
    """The character's Calling, or None."""
    return ruleset.callings.get(character.calling) if character.calling else None


def calling_abilities(ruleset, character) -> set:
    """The Abilities the character's Calling discounts (p.90). NOT Favored Abilities —
    the discount stacks with the Caste/Favoured one, so the two sets stay separate and
    a Calling Ability does NOT count toward the Caste/Favoured dot minimum."""
    calling = calling_for(ruleset, character)
    return set(calling.abilities) if calling else set()


def calling_charm_ids(ruleset, character) -> set:
    """The Charm ids the character's Calling discounts."""
    calling = calling_for(ruleset, character)
    return set(calling.charms) if calling else set()


def is_calling_charm(ruleset, character, charm) -> bool:
    charm_id = getattr(charm, "id", charm)
    return charm_id in calling_charm_ids(ruleset, character)


def camp_min_abilities(ruleset, character) -> list:
    """The Ability floors imposed by the character's training camp (p.89), unioned
    into the chargen minimums exactly as the caste's own are. Suppressed by the same
    `ignore_caste_min_abilities` switch, on the grounds that an origin declaring
    itself free of required Ability scores means all of them."""
    camp = camp_for(ruleset, character)
    return list(camp.required_min_abilities) if camp else []


def granted_charm_ids(ruleset, character) -> list[str]:
    """Every Charm the character holds for free from their camp package (p.90).

    Read off `character.granted_charms`, which is the RESOLVED list (the camp's fixed
    grants plus the player's choices). These are granted, not picked: they must never
    count against the Charm pool or the Caste/Favoured Charm minimum."""
    return list(character.granted_charms)


def check_camp_and_calling(ruleset, character) -> list[Issue]:
    """Camp/Calling legality (Cult of the Illuminated, p.89-93). Data-driven off the
    budget's `requires_camp`/`requires_calling`, so no splat or origin is named here."""
    issues: list[Issue] = []
    budgets = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)

    if budgets.requires_camp:
        camp = camp_for(ruleset, character)
        if camp is None:
            issues.append(Issue(
                code="camp-required",
                message="This origin requires a training camp; none is set."
                        if not character.camp else
                        f"Unknown training camp {character.camp!r}.",
            ))
        elif camp.exalt_type != character.exalt_type or (
                camp.origin and camp.origin != character.origin):
            issues.append(Issue(
                code="camp-wrong-origin", where=camp.id,
                message=f"Training camp {camp.label!r} belongs to "
                        f"{camp.exalt_type}/{camp.origin or 'any'}, not "
                        f"{character.exalt_type}/{character.origin or 'any'}.",
            ))
    elif character.camp:
        issues.append(Issue(
            code="camp-not-supported", where=character.camp,
            message="This origin has no training camps, but one is set.",
        ))

    if budgets.requires_calling:
        calling = calling_for(ruleset, character)
        if calling is None:
            issues.append(Issue(
                code="calling-required",
                message="This origin requires a Calling; none is set."
                        if not character.calling else
                        f"Unknown Calling {character.calling!r}.",
            ))
        # A Calling belongs to ONE camp (p.90-92): the Tabernacle's three are not on
        # offer at Kether Rock.
        elif character.camp and calling.camp and calling.camp != character.camp:
            issues.append(Issue(
                code="calling-wrong-camp", where=calling.id,
                message=f"Calling {calling.label!r} is offered by {calling.camp!r}, "
                        f"not by {character.camp!r}.",
            ))
    elif character.calling:
        issues.append(Issue(
            code="calling-not-supported", where=character.calling,
            message="This origin has no Callings, but one is set.",
        ))

    return issues


def default_camp_and_calling(ruleset, character) -> tuple[str, str, list[str]]:
    """The (camp id, calling id, granted Charm ids) a character of this splat/origin
    should default to — the first camp offered, its first Calling, and that camp's
    automatic grants. All three empty when the origin has no camps.

    Lives here rather than in the editor because "which camp is legal, and what does it
    hand you" is a rules question, and the UI is meant to contain no game logic. It also
    makes the behaviour testable without driving a browser: picking the Illuminated
    origin has to leave the character LEGAL, not merely leave three more dropdowns to
    fill in.

    Keeps a camp/Calling the character already has if it is still valid, so re-running
    this is idempotent and never silently discards a player's choice."""
    camps = ruleset.camps_for(character.exalt_type, character.origin)
    if not camps:
        return "", "", []

    camp = next((c for c in camps if c.id == character.camp), camps[0])
    callings = ruleset.callings_for(camp.id)
    calling = next((c.id for c in callings if c.id == character.calling),
                   callings[0].id if callings else "")

    granted = list(camp.granted_charms)
    if camp.id == character.camp:
        # Same camp: preserve whatever the player already resolved for each choice, and
        # only top up the fixed grants.
        granted = list(dict.fromkeys(granted + list(character.granted_charms)))
    return camp.id, calling, granted


def granted_charm_issues(ruleset, character) -> list[Issue]:
    """Whether `character.granted_charms` is a legal resolution of the camp's free-Charm
    package (p.90): every fixed grant present, each choice resolved, nothing extra, and
    the character meeting each granted Charm's own minima ("As usual, the Solar must
    meet the minimum requirements to gain these Charms")."""
    issues: list[Issue] = []
    camp = camp_for(ruleset, character)
    granted = list(character.granted_charms)

    if camp is None:
        if granted:
            issues.append(Issue(
                code="granted-charm-not-supported",
                message="Granted Charms are set, but the character has no training camp.",
            ))
        return issues

    seen = set()
    for cid in granted:
        if cid not in ruleset.charms:
            issues.append(Issue(code="granted-charm-unknown", where=cid,
                                message=f"Unknown Charm {cid!r} in the camp package."))
        if cid in seen:
            issues.append(Issue(code="granted-charm-duplicate", where=cid,
                                message=f"Charm {cid!r} is granted twice."))
        seen.add(cid)

    remaining = list(granted)
    for cid in camp.granted_charms:
        if cid in remaining:
            remaining.remove(cid)
        else:
            issues.append(Issue(
                code="granted-charm-missing", where=cid,
                message=f"{camp.label} grants {_charm_name(ruleset, cid)} to every "
                        f"graduate; it is not in the character's granted Charms.",
            ))

    for choice in camp.granted_charm_choices:
        if choice.fixed_sets:
            # Exactly one whole printed set, all-or-nothing.
            match = next((grp for grp in choice.fixed_sets
                          if all(c in remaining for c in grp)), None)
            if match is None:
                issues.append(Issue(
                    code="granted-charm-choice-unresolved", where=choice.label,
                    message=f"{camp.label}: {choice.label} — none of the "
                            f"{len(choice.fixed_sets)} options is fully taken.",
                ))
            else:
                for cid in match:
                    remaining.remove(cid)
        elif choice.from_categories:
            # `pick` Charms, all from ONE of the listed categories.
            by_cat: dict[str, list[str]] = {}
            for cid in remaining:
                charm = ruleset.charms.get(cid)
                if charm is not None and charm.category in choice.from_categories:
                    by_cat.setdefault(charm.category, []).append(cid)
            chosen = next((cat for cat, ids in by_cat.items() if len(ids) >= choice.pick), None)
            if chosen is None:
                issues.append(Issue(
                    code="granted-charm-choice-unresolved", where=choice.label,
                    message=f"{camp.label}: {choice.label} — needs {choice.pick} Charm(s) "
                            f"from ONE of {', '.join(choice.from_categories)}.",
                ))
            else:
                if len(by_cat) > 1:
                    issues.append(Issue(
                        code="granted-charm-choice-mixed", where=choice.label,
                        message=f"{camp.label}: {choice.label} — the Charms must all come "
                                f"from ONE style; found "
                                f"{', '.join(sorted(by_cat))}.",
                    ))
                for cid in by_cat[chosen][:choice.pick]:
                    remaining.remove(cid)
        else:
            # A flat pool: `pick` Charms from anywhere in it, in any combination
            # (Cult p.96, the Dragon-Blooded Tabernacle package). No cross-style
            # complaint is possible here — mixing IS the shape — so the only failure
            # is the wrong COUNT, and an over-count leaves the surplus in `remaining`
            # to be reported as granted-charm-extra like any other stray id.
            pool = set(choice.pool_charm_ids(ruleset.charms))
            taken = [cid for cid in remaining if cid in pool]
            if len(taken) < choice.pick:
                issues.append(Issue(
                    code="granted-charm-choice-unresolved", where=choice.label,
                    message=f"{camp.label}: {choice.label} — needs {choice.pick} "
                            f"Charm(s) from the package's list; {len(taken)} taken.",
                ))
            for cid in taken[:choice.pick]:
                remaining.remove(cid)

    for cid in remaining:
        issues.append(Issue(
            code="granted-charm-extra", where=cid,
            message=f"{_charm_name(ruleset, cid)} is not part of {camp.label}'s package.",
        ))

    # The character must still qualify for what they were given.
    for cid in granted:
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue
        ok, why = _granted_charm_minima_met(ruleset, character, charm)
        if not ok:
            issues.append(Issue(code="granted-charm-minimum", where=cid, message=why))

    return issues


def _granted_charm_minima_met(ruleset, character, charm) -> tuple[bool, str]:
    """A granted Charm is exempt from the Charm POOL, not from its own requirements
    (p.90). Prerequisites are deliberately NOT checked: the package hands out Charms
    like Iron Skin Concentration whose own tree the character has not climbed, and the
    page grants them outright."""
    short = charm_ability_shortfalls(character, charm)
    if short:
        label, want, have = short[0]
        return False, (f"{charm.name} is granted by the camp but requires "
                       f"{label} {want}; character has {have}.")
    if character.essence_rating < charm.min_essence:
        return False, (f"{charm.name} is granted by the camp but requires Essence "
                       f"{charm.min_essence}; character has {character.essence_rating}.")
    return True, ""
