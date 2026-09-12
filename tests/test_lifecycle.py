"""Tests for engine.lifecycle.lock_chargen — the freeze that pins Willpower's
virtue component and snapshots the chargen baseline.
"""

from exalted_builder.engine import derive, lifecycle
from exalted_builder.models.character import Character
from exalted_builder.models.rules import VirtueName as V


def _char() -> Character:
    c = Character(id="char.lock")
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 1})
    return c


def test_lock_freezes_state_and_wp_component():
    c = _char()
    assert c.chargen_locked is False
    lifecycle.lock_chargen(c)
    assert c.chargen_locked is True
    assert c.wp_virtue_component == 6                 # 3 + 3
    snap = c.chargen_snapshot
    assert snap is not None
    assert snap.wp_virtue_component == 6
    assert snap.essence_rating == c.essence_rating


def test_post_lock_virtue_gain_does_not_raise_willpower():
    c = _char()
    assert derive.willpower(c) == 6                   # pre-lock: live two-highest
    lifecycle.lock_chargen(c)
    # Raise a Virtue after the lock — derived Willpower must stay pinned at 6.
    c.virtues[V.VALOR] = 5
    assert derive.two_highest_virtues(c.virtues) == 8  # live value moved...
    assert derive.willpower(c) == 6                     # ...but Willpower did not


def test_unlock_reverts_the_lock_and_relives_willpower():
    c = _char()
    lifecycle.lock_chargen(c)
    c.virtues[V.VALOR] = 5                            # change while locked (Willpower stays 6)
    assert derive.willpower(c) == 6
    lifecycle.unlock_chargen(c)
    assert c.chargen_locked is False
    assert c.chargen_snapshot is None
    assert c.wp_virtue_component is None
    # Willpower now recomputes live from the two highest Virtues (3 + 5 = 8).
    assert derive.willpower(c) == 8


# --------------------------------------------------------------------------- #
# Unlock after XP — ruled 2026-09-12: allowed, with a warning
# --------------------------------------------------------------------------- #

def test_no_warning_when_no_xp_is_spent():
    from exalted_builder.ui import view
    assert view.unlock_warning(Character(id="c")) == ""


def test_the_warning_names_the_xp_spent_and_what_unlock_does():
    """`unlock_chargen` drops the snapshot and nothing else, so XP-bought dots become
    creation dots while the log still records them as spent."""
    from exalted_builder.models.character import XpEntry
    from exalted_builder.ui import view

    character = Character(id="c")
    character.xp_log.append(XpEntry(target="essence", from_rating=2, to_rating=3, cost=16))

    warning = view.unlock_warning(character)

    assert "16 XP" in warning and "creation" in warning
