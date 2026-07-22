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


def lock_chargen(character: Character) -> Character:
    """Freeze chargen: snapshot traits and pin the Willpower virtue component.
    Idempotent in effect, but re-locking re-snapshots current state."""
    wp_component = derive.two_highest_virtues(character.virtues)
    character.chargen_snapshot = ChargenSnapshot(
        attributes=dict(character.attributes),
        abilities=dict(character.abilities),
        crafts=[c.model_copy() for c in character.crafts],
        virtues=dict(character.virtues),
        specialties=list(character.specialties),
        backgrounds=list(character.backgrounds),
        charms=list(character.charms),
        spells=list(character.spells),
        combos=[c.model_copy(deep=True) for c in character.combos],
        ox_body=[p.model_copy(deep=True) for p in character.ox_body],
        beastman_gifts=[p.model_copy(deep=True) for p in character.beastman_gifts],
        essence_rating=character.essence_rating,
        willpower_purchased=character.willpower_purchased,
        wp_virtue_component=wp_component,
    )
    character.wp_virtue_component = wp_component
    character.chargen_locked = True
    return character


def unlock_chargen(character: Character) -> Character:
    """Reverse lock_chargen so chargen is editable again: drop the snapshot and the
    pinned Willpower virtue component (Willpower then recomputes live from the two
    highest Virtues). No XP layer exists yet; if one is added, unlocking after XP
    has been spent will need an explicit policy."""
    character.chargen_snapshot = None
    character.wp_virtue_component = None
    character.chargen_locked = False
    return character
