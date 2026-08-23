"""
engine/lifecycle.py — chargen lifecycle transitions.

`lock_chargen` freezes the creation snapshot: it stores `wp_virtue_component` (the
two highest Virtues at lock) so post-creation Virtue gains can never raise
Willpower, and snapshots the current traits as the XP baseline. Pure apart from
mutating the passed Character; it does not judge legality — validate the chargen
first if you want to refuse an illegal lock.
"""

from __future__ import annotations

from ..models.character import ChargenSnapshot, Character
from . import derive


def lock_chargen(character: Character, ruleset=None) -> Character:
    """Freeze chargen: snapshot traits and pin the Willpower virtue component.
    Idempotent in effect, but re-locking re-snapshots current state.

    `ruleset` is OPTIONAL, the same shape `derive.willpower` and friends use: without
    one there is no way to see a Merit, so the one Flaw that sets a STARTING trait
    (Death's Taint, whose price above its base four points buys permanent Resonance)
    cannot be applied. Pass it wherever you can — the omission is silent, not a
    TypeError.
    """
    wp_component = derive.two_highest_virtues(character.virtues)
    character.chargen_snapshot = ChargenSnapshot(
        attributes=dict(character.attributes),
        abilities=dict(character.abilities),
        crafts=[c.model_copy() for c in character.crafts],
        colleges=[c.model_copy() for c in character.colleges],
        paths=[p.model_copy() for p in character.paths],
        favored_path=character.favored_path,
        virtues=dict(character.virtues),
        specialties=list(character.specialties),
        backgrounds=list(character.backgrounds),
        # Fetters freeze like any other bought trait. Passions deliberately do NOT
        # appear here — they are a live derivation of the Virtues on both sides of the
        # lock (E:Ab p.283), so a snapshot would be decision 0005's Willpower treatment
        # applied to a rule that says the opposite.
        fetters=[f.model_copy(deep=True) for f in character.fetters],
        # Merits bought at creation freeze with everything else, or the XP audit would
        # re-price them against a moving baseline (decision 0004).
        merits_flaws=[m.model_copy(deep=True) for m in character.merits_flaws],
        charms=list(character.charms),
        elemental_powers=list(character.elemental_powers),
        spells=list(character.spells),
        combos=[c.model_copy(deep=True) for c in character.combos],
        arrays=[a.model_copy(deep=True) for a in character.arrays],
        submodules=[s.model_copy(deep=True) for s in character.submodules],
        ox_body=[p.model_copy(deep=True) for p in character.ox_body],
        beastman_gifts=[p.model_copy(deep=True) for p in character.beastman_gifts],
        variant_purchases=[p.model_copy(deep=True)
                           for p in character.variant_purchases],
        # Deep-copied like every other purchasable collection, and left None when the
        # character has no thaumaturgy so an untouched save still round-trips to None.
        thaumaturgy=(character.thaumaturgy.model_copy(deep=True)
                     if character.thaumaturgy is not None else None),
        # Table toggles that change chargen accounting are frozen with the traits:
        # flipping one post-lock would otherwise re-price a locked chargen.
        house_rules=(character.house_rules.model_copy(deep=True)
                     if character.house_rules is not None else None),
        essence_rating=character.essence_rating,
        willpower_purchased=character.willpower_purchased,
        wp_virtue_component=wp_component,
    )
    character.wp_virtue_component = wp_component
    # Death's Taint buys a STARTING permanent Resonance out of its price — the only Flaw
    # that seeds a trait rather than bounding one. ⚠ Seeded HERE: lock is where chargen
    # values become the character's own, and deriving the value without writing it here
    # leaves the character starting at 0 with nothing reading it.
    #
    # Never overwrites a track the ledger has already moved: a re-lock after play would
    # otherwise undo a Harrowing or re-inflict a shed dot.
    if ruleset is not None and not _permanent_resonance_moved(character):
        character.limit_permanent = derive.permanent_limit_start(ruleset, character)
    character.chargen_locked = True
    return character


def _permanent_resonance_moved(character: Character) -> bool:
    """Whether the XP ledger has ever moved permanent Resonance for this character."""
    from .validate import PERMANENT_RESONANCE_TARGET
    return any(e.target == PERMANENT_RESONANCE_TARGET for e in character.xp_log)


def unlock_chargen(character: Character) -> Character:
    """Reverse lock_chargen so chargen is editable again: drop the snapshot and the
    pinned Willpower virtue component (Willpower then recomputes live from the two
    highest Virtues). No XP layer exists yet; if one is added, unlocking after XP
    has been spent will need an explicit policy."""
    character.chargen_snapshot = None
    character.wp_virtue_component = None
    character.chargen_locked = False
    return character
