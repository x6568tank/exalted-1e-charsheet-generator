"""
tests/test_merit_postlock.py — Merit legality after the lock.

`merit_issues` used to be called from exactly one place, `validate_chargen`, while
`buy_merit` / `gain_flaw` / `drop_merit` all work post-lock. Found by the preflight
of 2026-08-17: the split made the phase visible, because `merit_issues` landed in
the chargen-only module.

Two separate jobs, and they are not the same shape:

  * **The buy path** must bar what it cannot undo. `tier_barred_exalt_types`,
    `thaumaturges_only`, the trait prerequisites and the point limits were all
    checked at chargen and not at purchase, and the tier was validated against the
    GENERIC cost menu rather than the character's own.
  * **The drift gates** must re-run post-lock as WARNINGS (human's ruling
    2026-08-17). Three of the gates measure something that can change after the
    purchase — an artifact lost, a Background dropped, a trait cursed down — and a
    character then holds a benefit they no longer qualify for.

⚠ The frozen-choice gates (splat, caste, origin, tier) deliberately do NOT re-run.
They cannot drift, so re-checking them post-lock only creates noise.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import advancement, lifecycle, validate
from exalted_builder.models.character import (
    BackgroundEntry, Character, MeritFlawPurchase as MP)
from exalted_builder.models.rules import AbilityName, AttributeName

DATA_DIR = Path(exalted_builder.__file__).parent / "data"

# Real catalogue entries, chosen for the field each one exercises.
ANATHEMA = "mf.known-anathema"          # points_limits: max, against Influence
HIDDEN_MANSE = "mf.hidden-manse"        # trait_prerequisites: Manse 1
DIVINATION = "mf.alternative-divination"  # max_purchases_from_trait: Occult
OATHBOUND = "thaum.oathbound-magic"     # thaumaturges_only


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _solar(**kw) -> Character:
    c = Character(id="c.pl", name="Drift", exalt_type="Solar", caste="dawn",
                  essence_rating=2)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _codes(issues) -> set[str]:
    return {i.code for i in issues}


def _by_code(issues, code):
    return [i for i in issues if i.code == code]


# --------------------------------------------------------------------------- #
# The drift gates, post-lock
# --------------------------------------------------------------------------- #

def test_a_points_limit_that_lapses_after_the_lock_is_warned_about(rs):
    """Known Anathema may not be worth more points than Influence. Bought legally at
    Influence 2, then the story takes the Influence away."""
    c = _solar(backgrounds=[BackgroundEntry(name="Influence", rating=2)],
               merits_flaws=[MP(merit_id=ANATHEMA, tier="2")])
    lifecycle.lock_chargen(c, rs)
    assert not _by_code(validate.validate(rs, c), "merit-points-above-background"), \
        "premise: legal at the lock"

    c.backgrounds = []                      # the story takes it away
    found = _by_code(validate.validate(rs, c), "merit-points-above-background")
    assert found, "a lapsed point limit must be reported post-lock"
    assert found[0].severity == "warning", "the story may create this; not an error"


def test_the_post_lock_pass_reads_LIVE_backgrounds_not_the_snapshot(rs):
    """The premise the test above depends on, asserted separately so it cannot rot.

    ⚠ The chargen path reads the frozen snapshot on purpose. If the post-lock pass
    did too it would re-check the values as they were AT the lock and never fire —
    the check would exist and do nothing, which is the whole bug class this file
    is about."""
    c = _solar(backgrounds=[BackgroundEntry(name="Influence", rating=2)],
               merits_flaws=[MP(merit_id=ANATHEMA, tier="2")])
    lifecycle.lock_chargen(c, rs)
    c.backgrounds = []

    assert c.chargen_snapshot is not None
    snap_influence = [b for b in c.chargen_snapshot.backgrounds
                      if b.name.lower() == "influence"]
    assert snap_influence and snap_influence[0].rating == 2, \
        "premise: the snapshot still holds the Influence that was dropped live"
    assert _by_code(validate.validate(rs, c), "merit-points-above-background")


def test_a_trait_prerequisite_that_lapses_after_the_lock_is_warned_about(rs):
    """Hidden Manse requires Manse 1. The Manse is destroyed in play."""
    c = _solar(backgrounds=[BackgroundEntry(name="Manse", rating=2)],
               merits_flaws=[MP(merit_id=HIDDEN_MANSE)])
    lifecycle.lock_chargen(c, rs)
    assert not _by_code(validate.validate(rs, c), "merit-trait-prerequisite"), \
        "premise: legal at the lock"

    c.backgrounds = []
    found = _by_code(validate.validate(rs, c), "merit-trait-prerequisite")
    assert found and found[0].severity == "warning"


def test_the_repeat_trait_cap_is_currently_unreachable(rs):
    """⚠ A DOCUMENTED GAP, not a passing feature. `max_purchases_from_trait` is
    authored on exactly one entry, and that entry is not marked `repeatable_by` — so
    a second copy is already illegal as `merit-repeated` and the trait cap can never
    be the thing that binds.

    p.17 prints Alternative Divination as repeatable ("may not purchase this Merit
    more times than their Occult rating"), so the DATA looks wrong rather than the
    code. Flagged to the rules authority 2026-08-17; not fixed here, because marking
    an entry repeatable is a rules change.

    The post-lock pass includes the gate anyway, so it starts working the day the
    data is corrected. This test asserts the gap so it cannot be forgotten.
    """
    definition = rs.merits_flaws[DIVINATION]
    assert definition.max_purchases_from_trait == "Occult"
    assert not definition.repeatable_by, (
        "Alternative Divination became repeatable — delete this test and write the "
        "real drift test it was standing in for")


# --------------------------------------------------------------------------- #
# What must NOT re-run
# --------------------------------------------------------------------------- #

def test_frozen_choice_gates_do_not_re_run_post_lock(rs):
    """The negative control, and the reason `post_lock` is a SUBSET rather than the
    whole function. Splat, caste and origin freeze at the lock, so a Merit that was
    legal stays legal — re-reporting it is noise, not a finding."""
    c = _solar(merits_flaws=[MP(merit_id=ANATHEMA, tier="2")],
               backgrounds=[BackgroundEntry(name="Influence", rating=5)])
    lifecycle.lock_chargen(c, rs)
    c.exalt_type = "Lunar"                  # only reachable by editing a save by hand

    codes = _codes(validate.validate(rs, c))
    assert "merit-wrong-splat" not in codes
    assert "merit-barred-splat" not in codes
    assert "merit-barred-caste" not in codes
    assert "merit-wrong-origin" not in codes


def test_an_unlocked_character_gets_no_post_lock_merit_pass(rs):
    """`validate` runs on both sides; the merit pass inside it is gated on the lock,
    exactly like the Background one beside it."""
    c = _solar(merits_flaws=[MP(merit_id=ANATHEMA, tier="2")])
    assert not c.chargen_locked
    assert not _by_code(validate.validate(rs, c), "merit-points-above-background")


def test_chargen_merit_issues_are_unchanged(rs):
    """The chargen path must be untouched by all of this: still errors, still the
    full gate set."""
    c = _solar(merits_flaws=[MP(merit_id=ANATHEMA, tier="2")])
    found = _by_code(validate.merit_issues(rs, c), "merit-points-above-background")
    assert found, "no Influence at all -> the limit is 0 and 2 points exceed it"
    assert found[0].severity == "error"


# --------------------------------------------------------------------------- #
# The buy path
# --------------------------------------------------------------------------- #

def _locked_with_xp(rs, **kw) -> Character:
    c = _solar(**kw)
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    return c


def test_gain_flaw_refuses_a_thaumaturges_only_entry_without_thaumaturgy(rs):
    """Checked at chargen and not at purchase, so XP walked straight past it.

    ⚠ Oathbound Magic is a FLAW, so this exercises `gain_flaw` — which had the same
    gap and the same generic-cost_options bug as `buy_merit`. Both go through the
    one gate helper now."""
    c = _locked_with_xp(rs)
    # A tier is required before any other gate can be evaluated, so name one — the
    # point of this test is the thaumaturgy bar, not the tier bar.
    with pytest.raises(advancement.AdvancementError, match="thaumaturg"):
        advancement.gain_flaw(rs, c, OATHBOUND, tier="minor")


def test_buy_merit_refuses_an_unmet_trait_prerequisite(rs):
    c = _locked_with_xp(rs)                 # no Manse Background
    # ⚠ match on the RULE, not on "Manse" — the merit is itself called Hidden Manse,
    # so a name-shaped regex passes on the unrelated "needs one of ['1','2']" error.
    with pytest.raises(advancement.AdvancementError, match="requires"):
        advancement.buy_merit(rs, c, HIDDEN_MANSE, tier="1")


def test_buy_merit_allows_the_same_merit_once_the_prerequisite_is_met(rs):
    """The bar must not become "never buyable" — the positive control."""
    c = _locked_with_xp(rs, backgrounds=[BackgroundEntry(name="Manse", rating=2)])
    entry = advancement.buy_merit(rs, c, HIDDEN_MANSE, tier="1")
    assert entry is not None
    assert HIDDEN_MANSE in [p.merit_id for p in c.merits_flaws]


def test_buy_merit_refuses_a_points_limit_it_would_exceed(rs):
    """Known Anathema at 2 points with no Influence at all."""
    c = _locked_with_xp(rs)
    with pytest.raises(advancement.AdvancementError):
        advancement.buy_merit(rs, c, ANATHEMA, tier="2")


def test_buy_merit_prices_the_tier_against_the_characters_own_menu(rs):
    """`buy_merit` validated the tier against the GENERIC `cost_options`, so a tier
    that exists for some other splat passed and then priced at nothing.

    Prodigy's tiers are keyed by exalt_type; a Solar's menu is not the Dragon-King
    one."""
    prodigy = rs.merits_flaws["mf.prodigy"]
    own = set(validate.merit_cost_options(prodigy, "Solar", "dawn"))
    generic = set(prodigy.cost_options)
    foreign = sorted(generic - own)
    if not foreign:
        pytest.skip("no tier exists that is generic-but-not-Solar")
    c = _locked_with_xp(rs)
    with pytest.raises(advancement.AdvancementError):
        advancement.buy_merit(rs, c, "mf.prodigy", tier=foreign[0])
