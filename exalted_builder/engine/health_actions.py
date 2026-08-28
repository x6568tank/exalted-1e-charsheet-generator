"""
engine/health_actions.py — reading and setting the per-tier health-level count.

Input: a Character and a wound penalty tier (0, -1, -2, -4). Output: `level_total`
returns the effective number of levels at that tier; `set_level_total` rewrites
`character.health_bonus_levels` for that tier so the effective total becomes the
number asked for. Mechanism: the printed track (derive.BASE_WOUND_PENALTIES) is the
baseline, and the character's bonus list carries only the DELTA from it — added levels
above base, `removed=True` levels below.

This is `engine/gear_actions.py`'s shape applied to the health track, and for the same
reason: two shells now drive this edit (`ui/editor.py` and `qt/editor.py`), and a
shell-local copy in each is a rules bug waiting to happen.

⚠ **The stored list is a DELTA, not the track.** A tier showing its printed count holds
no entries at all, so an empty `health_bonus_levels` means "unmodified", never "no
health levels". Anything that reads the list directly to count a track will undercount
by the whole printed baseline — `derive.health_track` is the function that assembles
the real track.

⚠ **Levels below base are stored, not deleted.** A curse that takes a level away adds a
`removed=True` entry rather than removing a printed one, because the printed track is
not in the character at all — there is nothing to delete.
"""

from __future__ import annotations

from collections import Counter

from ..models.character import Character, HealthLevel
from . import derive

# The printed track's level count at each wound penalty (core p.104's seven levels,
# less Incapacitated, which is not a tier the player edits).
BASE_COUNTS: dict[int, int] = dict(Counter(derive.BASE_WOUND_PENALTIES))

# The tiers an editor offers, most to least healthy.
EDITABLE_TIERS: tuple[int, ...] = (0, -1, -2, -4)

# What a hand-edited level records as its source, so the sheet can tell a typed level
# from one a Charm granted.
_ADDED_SOURCE = "Bonus"
_REMOVED_SOURCE = "Curse"


def level_total(character: Character, penalty: int) -> int:
    """The effective number of health levels at a tier: base + added - removed."""
    delta = sum((-1 if hl.removed else 1)
                for hl in character.health_bonus_levels if hl.penalty == penalty)
    return max(0, BASE_COUNTS.get(penalty, 0) + delta)


def set_level_total(character: Character, penalty: int, total: int) -> None:
    """Rewrite one tier so `level_total` reports `total`, leaving every other tier's
    entries untouched. Above base the difference is stored as added levels, below it as
    `removed=True` levels."""
    base_n = BASE_COUNTS.get(penalty, 0)
    kept = [hl for hl in character.health_bonus_levels if hl.penalty != penalty]
    if total > base_n:
        kept += [HealthLevel(penalty=penalty, source_charm=_ADDED_SOURCE)
                 for _ in range(total - base_n)]
    elif total < base_n:
        kept += [HealthLevel(penalty=penalty, source_charm=_REMOVED_SOURCE, removed=True)
                 for _ in range(base_n - total)]
    character.health_bonus_levels = kept
