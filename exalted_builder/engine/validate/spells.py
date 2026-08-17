"""
engine/validate/spells.py — Sorcery and Necromancy circle access.

A known spell requires a known Charm granting its circle. `granted_circles` reads what
the character's Charms open, `accessible_circles` adds what the splat reaches natively,
`chargen_barred_circle` is the circle no character may enter during creation.

⚠ The circle a splat reaches comes from `ExaltDefinition.highest_magic_circle_id` — the
trap `docs/adding-a-splat.md` names first. A splat that omits it silently reaches
nothing.

⚠ Sorcery and Necromancy are SEPARATE ladders, not one. `TRACK_CIRCLES` holds both; a
character reaches their own circle and every one below it, never up (decision 0015).
"""

from __future__ import annotations

from ...models.character import Character
from ...models.rules import RuleSet, SpellCircle, TRACK_CIRCLES
from .. import merits
from ._base import Issue
from .charms import charm_matches_splat, meets_charm_requirements


def granted_circles(ruleset: RuleSet, character: Character) -> set[SpellCircle]:
    """The set of magic circles the character can cast in, taken from the
    `grants_circle` of every known initiation Charm PLUS any circle a Merit grants
    outright. Track-agnostic (sorcery or, later, necromancy) — the circle enum
    carries the distinction.

    The Merit half is not a convenience: a splat that may hold no Charms at all
    (mortals) can never satisfy the Charm half, so Essence Mastery's Terrestrial
    sorcery would be permanently unreachable without it. This is the function the
    *gates* use (meets_spell_requirements, check_spell_access), which is why the
    grant has to land here and not only in accessible_circles."""
    out = {
        ruleset.charms[cid].grants_circle
        for cid in character.charms
        if cid in ruleset.charms and ruleset.charms[cid].grants_circle is not None
    }
    out |= set(merits.merits_and_flaws_calc(ruleset, character).granted_circles)
    return out


def accessible_circles(ruleset: RuleSet, character: Character) -> set[SpellCircle]:
    """Every magic circle this character can reach — the circle granted by any
    initiation Charm they may learn (their own Exalt type, or an `open_to_all`
    Charm), unioned with circles already granted by known Charms.

    This is what the spell picker should show, and it is deliberately NOT the same
    as the Exalt's nominal `magic_track`: a splat whose Charm trees hold BOTH sorcery
    and necromancy initiations (Abyssals carry Terrestrial/Celestial Sorcery AND the
    three Necromancy circles) reaches both tracks, so its picker must too. Track is a
    display-ordering hint, not an access gate — the gate is the granting Charm."""
    # Merit-granted circles (mortals + Essence Mastery, capped at Terrestrial) arrive
    # through granted_circles, which is where the gates read them too. See engine.merits.
    out = granted_circles(ruleset, character)
    for charm in ruleset.charms.values():
        if charm.grants_circle is not None and charm_matches_splat(character, charm, ruleset):
            out.add(charm.grants_circle)
    return out


def chargen_barred_circle(ruleset: RuleSet, character: Character) -> SpellCircle | None:
    """The magic circle barred at character creation for this Exalt type, resolved
    from ExaltDefinition.highest_magic_circle_id (Solars: the Solar Circle, core
    p.100). Empty or unrecognised -> None (nothing barred at creation)."""
    cid = ruleset.exalt_for(character.exalt_type).highest_magic_circle_id
    try:
        return SpellCircle(cid) if cid else None
    except ValueError:
        return None


def meets_spell_requirements(ruleset: RuleSet, character: Character, spell,
                             *, chargen: bool = True) -> bool:
    """Whether the character could learn `spell` right now: a known Charm must grant
    its circle, and at chargen the Exalt type's highest circle is barred (Solars:
    Solar Circle, core p.100). Forward-looking counterpart to check_spell_access."""
    if spell.id in ruleset.exalt_for(character.exalt_type).barred_spell_ids:
        return False
    if chargen and spell.circle == chargen_barred_circle(ruleset, character):
        return False
    return spell.circle in granted_circles(ruleset, character)


def check_spell_access(ruleset: RuleSet, character: Character) -> list[Issue]:
    """A known Spell requires a known Charm whose `grants_circle` matches
    the Spell's circle.

    Exact-circle match is correct for 1e (core pp.191): the three initiation
    Charms form a prerequisite chain — Celestial Circle Sorcery requires
    Terrestrial, Solar requires Celestial — so a higher-circle sorcerer always
    also holds the lower Charms (enforced by check_charm_prerequisites) and can
    cast lower-circle spells through them. No separate circle-nesting rule is
    needed here; the prerequisite chain provides it.
    """
    granted = granted_circles(ruleset, character)
    barred = ruleset.exalt_for(character.exalt_type).barred_spell_ids
    issues: list[Issue] = []
    for sid in character.spells:
        spell = ruleset.spells.get(sid)
        if spell is None:
            continue
        # The splat-level spell bar, restated here as well as in
        # meets_spell_requirements: the picker route and the already-held route are
        # two ways to the same permission, and a bar on only one of them is this
        # build's most-repeated bug.
        if sid in barred:
            issues.append(Issue(
                code="spell-barred", where=sid,
                message=(f"{spell.name}: {ruleset.exalt_for(character.exalt_type).label} "
                         f"may never learn this spell."),
            ))
            continue
        if spell.circle not in granted:
            issues.append(Issue(
                code="spell-circle", where=sid,
                message=(f"{spell.name}: no known Charm grants the "
                         f"{spell.circle.value} circle."),
            ))
    return issues
