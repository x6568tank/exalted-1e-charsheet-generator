"""
engine/play.py — the in-play tracker's mutators.

Input: a character and a field or box index. Output: `Character.play` mutated in
place. Mechanism: each function reads or creates the `PlayState` and clamps the value
it is given; nothing here derives a capacity — the health-track shape, the Essence
pools and permanent Willpower all come from `engine.derive` via `view.build_play_view`,
and this layer only overlays the player's fill-state onto them.

Moved out of `ui/play.py` on 2026-08-22 (tier 3 of the `ui/` audit) so both shells
drive one copy, in `engine/charm_actions.py`'s and `engine/gear_actions.py`'s shape.

⚠ **This is a DUMB tracker and must stay one.** No auto mote-accounting, no
damage-wrapping rules, no auto-healing — the Storyteller stays in control. The clamps
below are the only arithmetic here, and they exist to keep a stored number inside the
capacity the sheet displays, not to enforce a printed rule.

⚠ **decision 0006 — play-state is validation-isolated.** Nothing in
`engine/validate/` may import this module or read `Character.play`: play-state never
reaches chargen, the XP audit, or a permanent derivation. `tests/test_play_state.py`
asserts the import direction, so a future convenience import fails loudly rather than
quietly making a marked health box change what a character may legally buy.
"""

from __future__ import annotations

from ..models.character import Character, Damage, PlayState

# The cycle a health box steps through on each click: empty → / → x → * → empty.
MARK_CYCLE: list[Damage | None] = [None, Damage.BASHING, Damage.LETHAL,
                                   Damage.AGGRAVATED]


def play_state(character: Character) -> PlayState:
    """The character's play-state, created on first edit so a never-played character
    keeps a clean save until the tracker is actually used."""
    if character.play is None:
        character.play = PlayState()
    return character.play


def normalize_health(character: Character, n: int) -> list[Damage | None]:
    """Pad/trim the stored marks to the current health-track length (Ox-Body or a
    curse bought later changes the box count). Returns the live list."""
    h = play_state(character).health
    if len(h) < n:
        h += [None] * (n - len(h))
    elif len(h) > n:
        del h[n:]
    return h


def cycle_mark(character: Character, i: int, n: int) -> None:
    """Step health box `i` to the next mark: empty → / → x → * → empty."""
    h = normalize_health(character, n)
    h[i] = MARK_CYCLE[(MARK_CYCLE.index(h[i]) + 1) % len(MARK_CYCLE)]


def set_motes(character: Character, field: str, value, cap: int) -> None:
    """Set a motes-spent field, clamped to 0..cap."""
    setattr(play_state(character), field, max(0, min(cap, int(value or 0))))


def set_fatigue(character: Character, value) -> None:
    """Set the accumulated armour-fatigue points (p.332). No upper clamp: the rule
    prints no maximum, and the penalty keeps accruing on every failed roll."""
    play_state(character).fatigue = max(0, int(value or 0))


def set_count(character: Character, field: str, clicked: int, cap: int) -> None:
    """Dot-track click: clicking the top filled box clears it, else fill up to it."""
    cur = getattr(play_state(character), field)
    setattr(play_state(character), field,
            max(0, min(cap, clicked - 1 if clicked == cur else clicked)))


def clear_damage(character: Character) -> None:
    """Wipe every health mark. A convenience for "the scene ended", not a healing
    rule — nothing here knows how long a level takes to heal."""
    play_state(character).health = []


def clear_motes(character: Character) -> None:
    """Reset the spent-mote fields to full.

    ⚠ MOTES ONLY. Willpower, health and Limit recover on their own terms (Storyteller
    discretion), so the tracker does not bulk-reset them — a "clear everything" button
    would be the tracker deciding a recovery rule, which is exactly what it must not do.
    """
    state = play_state(character)
    state.motes_personal_spent = 0
    state.motes_peripheral_spent = 0
