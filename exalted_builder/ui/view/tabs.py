"""
ui/view/tabs.py — the tab set of a character, and the tab that a stage of the
character shows.
"""

from __future__ import annotations



_TABS = ("Edit", "Gear", "Advantages", "Charms", "Combos", "Play", "ST",
         "Custom", "Sheet")


def visible_tabs(locked: bool, *, combos: bool = True) -> tuple[str, ...]:
    """The tabs for a character at this stage of its life.

    **Edit is on the bar on BOTH sides of the lock** (decision 0013), as are Charms,
    Combos and Advantages. The dot tracks change MODE rather than being replaced: free
    setters pre-lock, steppers that spend XP post-lock.

    ⚠ There is no XP tab, and splitting one back out is how these traits come to be
    implemented twice and disagree — a hardcoded trait ceiling on a separate XP surface
    makes Legendary Attribute unbuyable there while chargen honours it. Everything an
    XP tab would hold lives beside the thing it acts on: traits on the dot tracks, the
    ledger and Adjust XP in Edit's sticky column, permanent Resonance and the
    withheld-Charm note beside their traits, Crafts/Colleges/Specialties/equipment on
    the panels that already exist here.

    Play is locked-only. The tracker overlays spent motes, marked health and Willpower
    onto capacities derived from the finished character, and every one of those moves
    while chargen is still open — a half-built character's track is a set of boxes that
    change under the player. It is also the tab most likely to mislead: play-state is
    validation-isolated (decision 0006) and never enters chargen, so marks made before
    the lock silently mean nothing to the point accounting.
    """
    hidden = {"Play"} if not locked else set()
    # A splat that may never learn Combos and builds no Arrays either (ghosts, E:Ab
    # p.234) loses the tab rather than being given an empty one that refuses every
    # attempt. Asked of `view.has_combos_tab` by the caller, so the rule lives with
    # the engine and this stays a pure function of two booleans.
    if not combos:
        hidden.add("Combos")
    return tuple(t for t in _TABS if t not in hidden)


def resolve_tab(name: str, locked: bool, *, combos: bool = True) -> str:
    """`name`, or a sensible landing tab when locking/unlocking just hid it.

    Edit survives the lock now, so it is the answer in both directions — a player who
    locks while editing traits stays where they were, looking at the same dots, which
    is the point of the merge.
    """
    if name in visible_tabs(locked, combos=combos):
        return name
    return "Edit"
