"""Tests for engine.advancement — post-lock XP transitions, undo, and the XP audit.

A locked Dawn Solar with some XP earned is advanced; the trait change, the log row,
and the running available-XP must all stay consistent, and undo must reverse them.
"""

import pytest

from exalted_builder.engine import advancement, derive, lifecycle
from exalted_builder.models.character import Character, Specialty
from exalted_builder.models.rules import (
    AbilityName,
    AttributeName,
    CasteDefinition,
    Charm,
    CharmType,
    CharmVariant,
    RuleSet,
    Spell,
    SpellCircle,
    VirtueName,
)

A, AT, V = AbilityName, AttributeName, VirtueName


def _ruleset() -> RuleSet:
    castes = {"dawn": CasteDefinition(
        id="dawn", label="Dawn",
        caste_abilities=[A.ARCHERY, A.BRAWL, A.MARTIAL_ARTS, A.MELEE, A.THROWN])}
    charms = {
        "base": Charm(id="base", name="Base Charm", category="melee",
                      type=CharmType.SIMPLE, min_ability=1, min_essence=1),
        "follow": Charm(id="follow", name="Follow Up", category="melee",
                        type=CharmType.REFLEXIVE, min_ability=2, min_essence=1,
                        prerequisites=[["base"]]),
        "sorcery": Charm(id="sorcery", name="Terrestrial Circle Sorcery", category="occult",
                         type=CharmType.PERMANENT, min_ability=1, min_essence=1,
                         grants_circle=SpellCircle.TERRESTRIAL),
        "solar.endurance.ox-body-technique": Charm(
            id="solar.endurance.ox-body-technique", name="Ox-Body Technique",
            category="endurance", type=CharmType.SPECIAL, min_ability=1, min_essence=1,
            repeatable_cap_ability="endurance",
            variants=[
                CharmVariant(key="one-zero", label="One -0", health_levels=[0]),
                CharmVariant(key="two-one", label="Two -1", health_levels=[-1, -1]),
            ]),
    }
    spells = {"frost": Spell(id="frost", name="Frost", circle=SpellCircle.TERRESTRIAL)}
    return RuleSet(castes=castes, charms=charms, spells=spells)


def _locked(xp: int = 50) -> Character:
    c = Character(id="char.xp", caste="dawn")
    c.favored_abilities = [A.OCCULT, A.DODGE, A.ATHLETICS, A.RESISTANCE, A.ENDURANCE]
    c.attributes[AT.DEXTERITY] = 3
    c.abilities[A.MELEE] = 2
    c.abilities[A.OCCULT] = 1                               # so the Sorcery Charm is learnable
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 1})
    lifecycle.lock_chargen(c)
    c.xp_earned = xp
    return c


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #

def test_cannot_spend_before_lock():
    rs = _ruleset()
    c = Character(id="char.x", caste="dawn")
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_attribute(rs, c, AT.DEXTERITY)


def test_cannot_overspend():
    rs, c = _ruleset(), _locked(xp=1)
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_attribute(rs, c, AT.DEXTERITY)   # Dex 3 -> 4 costs 12 > 1
    assert c.attributes[AT.DEXTERITY] == 3                 # unchanged on failure
    assert c.xp_log == []


def test_cannot_raise_past_five():
    rs, c = _ruleset(), _locked()
    c.abilities[A.MELEE] = 5
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_ability(rs, c, A.MELEE)


# --------------------------------------------------------------------------- #
# Raises: trait + log + accounting
# --------------------------------------------------------------------------- #

def test_raise_attribute_applies_and_logs():
    rs, c = _ruleset(), _locked()
    entry = advancement.raise_attribute(rs, c, AT.DEXTERITY)
    assert c.attributes[AT.DEXTERITY] == 4
    assert entry.cost == 12 and entry.from_rating == 3 and entry.to_rating == 4
    assert advancement.xp_spent(c) == 12
    assert advancement.xp_available(c) == 38


def test_raise_favored_ability_is_discounted():
    rs, c = _ruleset(), _locked()
    c.abilities[A.OCCULT] = 2                               # Occult is Favoured
    entry = advancement.raise_ability(rs, c, A.OCCULT)
    assert entry.cost == 3                                  # 2 x 2 - 1
    assert c.abilities[A.OCCULT] == 3


def test_raise_willpower_increments_purchased_not_virtue_component():
    rs, c = _ruleset(), _locked()
    before = derive.willpower(c)
    entry = advancement.raise_willpower(rs, c)
    assert entry.cost == before * 2
    assert derive.willpower(c) == before + 1
    assert c.willpower_purchased == 1


# --------------------------------------------------------------------------- #
# New traits
# --------------------------------------------------------------------------- #

def test_learn_charm_requires_prerequisites():
    rs, c = _ruleset(), _locked()
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, "follow")           # needs 'base' first
    advancement.learn_charm(rs, c, "base")
    advancement.learn_charm(rs, c, "follow")               # now legal
    assert c.charms == ["base", "follow"]
    # base: Melee is Caste -> 8; follow likewise -> 8
    assert advancement.xp_spent(c) == 16


def test_learn_spell_requires_circle_charm():
    rs, c = _ruleset(), _locked()
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_spell(rs, c, "frost")            # no Sorcery Charm yet
    advancement.learn_charm(rs, c, "sorcery")
    entry = advancement.learn_spell(rs, c, "frost")
    assert "frost" in c.spells
    assert entry.cost == 8                                  # Occult favoured -> discounted


def test_add_combo_must_be_legal_and_costs_min_abilities():
    rs, c = _ruleset(), _locked()
    advancement.learn_charm(rs, c, "base")
    advancement.learn_charm(rs, c, "follow")
    entry = advancement.add_combo(rs, c, "Twin", ["base", "follow"])
    assert entry.cost == 1 + 2                              # min_ability 1 + 2
    assert len(c.combos) == 1


# --------------------------------------------------------------------------- #
# Ox-Body Technique (repeatable, variant menu)
# --------------------------------------------------------------------------- #

OX = "solar.endurance.ox-body-technique"


def test_learn_ox_body_adds_purchase_levels_and_costs_charm_xp():
    rs, c = _ruleset(), _locked(xp=20)
    c.abilities[A.ENDURANCE] = 2
    entry = advancement.learn_ox_body(rs, c, "two-one")
    assert entry.cost == 8                                  # Endurance favoured -> new_charm_favored_caste
    assert len(c.ox_body) == 1 and c.ox_body[0].variant == "two-one"
    assert c.ox_body[0].health_levels == [-1, -1]
    # the two -1 levels show up on the derived health track
    assert sum(1 for h in derive.health_track(c) if h.penalty == -1 and h.source) == 2


def test_ox_body_capped_at_endurance_dots():
    rs, c = _ruleset(), _locked(xp=99)
    c.abilities[A.ENDURANCE] = 2
    advancement.learn_ox_body(rs, c, "one-zero")
    advancement.learn_ox_body(rs, c, "one-zero")
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_ox_body(rs, c, "one-zero")       # 3rd exceeds Endurance 2
    assert len(c.ox_body) == 2


def test_ox_body_unknown_variant_raises():
    rs, c = _ruleset(), _locked()
    c.abilities[A.ENDURANCE] = 1
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_ox_body(rs, c, "nope")
    assert c.ox_body == []


def test_undo_ox_body_removes_last_purchase_and_refunds():
    rs, c = _ruleset(), _locked(xp=20)
    c.abilities[A.ENDURANCE] = 2
    advancement.learn_ox_body(rs, c, "one-zero")
    advancement.learn_ox_body(rs, c, "two-one")
    advancement.undo_last(rs, c)
    assert [p.variant for p in c.ox_body] == ["one-zero"]
    assert advancement.xp_available(c) == 12               # 20 - 8 (one purchase left)


def test_ox_body_purchases_pass_the_xp_audit():
    rs, c = _ruleset(), _locked(xp=20)
    c.abilities[A.ENDURANCE] = 1
    advancement.learn_ox_body(rs, c, "one-zero")
    codes = {i.code for i in advancement.validate_xp(rs, c)}
    assert "xp-cost-mismatch" not in codes and "xp-overspent" not in codes


def test_check_ox_body_flags_over_cap_and_bad_variant():
    from exalted_builder.engine import validate
    from exalted_builder.models.character import OxBodyPurchase
    rs, c = _ruleset(), _locked()
    c.abilities[A.ENDURANCE] = 1
    c.ox_body = [OxBodyPurchase(variant="one-zero", health_levels=[0]),
                 OxBodyPurchase(variant="ghost", health_levels=[0])]   # 2 > cap 1, + bad key
    codes = {i.code for i in validate.check_ox_body(rs, c)}
    assert "ox-body-over-cap" in codes and "ox-body-bad-variant" in codes


# --------------------------------------------------------------------------- #
# Undo (LIFO)
# --------------------------------------------------------------------------- #

def test_undo_reverses_trait_and_refunds():
    rs, c = _ruleset(), _locked()
    advancement.raise_attribute(rs, c, AT.DEXTERITY)
    assert advancement.xp_spent(c) == 12
    undone = advancement.undo_last(rs, c)
    assert undone.target == "attributes.dexterity"
    assert c.attributes[AT.DEXTERITY] == 3                 # reverted
    assert c.xp_log == [] and advancement.xp_spent(c) == 0


def test_undo_charm_removes_it():
    rs, c = _ruleset(), _locked()
    advancement.learn_charm(rs, c, "base")
    advancement.undo_last(rs, c)
    assert c.charms == []


def test_undo_on_empty_log_raises():
    rs, c = _ruleset(), _locked()
    with pytest.raises(advancement.AdvancementError):
        advancement.undo_last(rs, c)


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #

def test_validate_xp_is_silent_before_lock():
    rs = _ruleset()
    c = Character(id="char.x", caste="dawn")
    assert advancement.validate_xp(rs, c) == []


def test_validate_xp_flags_overspend():
    rs, c = _ruleset(), _locked(xp=10)
    advancement.add_xp(c, 5)                                # 15 earned
    advancement.raise_attribute(rs, c, AT.DEXTERITY)       # 12 spent, ok
    c.xp_earned = 5                                         # hand-edit below the spend
    codes = {i.code for i in advancement.validate_xp(rs, c)}
    assert "xp-overspent" in codes


def test_validate_xp_flags_cost_tampering():
    rs, c = _ruleset(), _locked()
    advancement.raise_attribute(rs, c, AT.DEXTERITY)
    c.xp_log[-1].cost = 1                                   # tampered row
    codes = {i.code for i in advancement.validate_xp(rs, c)}
    assert "xp-cost-mismatch" in codes


def test_validate_xp_summary_reports_available():
    rs, c = _ruleset(), _locked(xp=20)
    advancement.raise_attribute(rs, c, AT.DEXTERITY)       # 12
    summary = next(i for i in advancement.validate_xp(rs, c) if i.code == "xp-summary")
    assert "12 of 20" in summary.message and "8 available" in summary.message


# --------------------------------------------------------------------------- #
# Permanent reductions (curses / Charm costs) — free, logged, undoable
# --------------------------------------------------------------------------- #

def test_lower_attribute_is_free_and_logged():
    rs, c = _ruleset(), _locked(xp=10)
    advancement.lower_attribute(c, AT.DEXTERITY, "wasting curse")
    assert c.attributes[AT.DEXTERITY] == 2                  # 3 -> 2
    row = c.xp_log[-1]
    assert (row.from_rating, row.to_rating, row.cost) == (3, 2, 0)
    assert row.detail == "wasting curse"
    assert advancement.xp_available(c) == 10               # no XP spent or refunded


def test_reduction_passes_the_xp_audit():
    rs, c = _ruleset(), _locked(xp=10)
    advancement.lower_attribute(c, AT.DEXTERITY, "curse")
    codes = {i.code for i in advancement.validate_xp(rs, c)}
    assert "xp-cost-mismatch" not in codes                 # a 0-cost reduction is expected at 0


def test_lower_floors_guard_the_minimum():
    rs, c = _ruleset(), _locked()
    c.attributes[AT.STRENGTH] = 1
    with pytest.raises(advancement.AdvancementError):
        advancement.lower_attribute(c, AT.STRENGTH)        # already at 1


def test_lower_willpower_can_drop_below_virtue_component():
    rs, c = _ruleset(), _locked()
    start = derive.willpower(c)                             # = two highest Virtues (3+3 = 6)
    for _ in range(start - 1):                              # curse it all the way down to 1
        advancement.lower_willpower(c, "soul-eroding curse")
    assert derive.willpower(c) == 1
    assert c.willpower_purchased < 0                        # net-negative below the Virtue floor
    with pytest.raises(advancement.AdvancementError):
        advancement.lower_willpower(c)                      # floored at 1


def test_undo_reverses_a_willpower_reduction():
    rs, c = _ruleset(), _locked()
    start = derive.willpower(c)
    advancement.lower_willpower(c, "curse")
    assert derive.willpower(c) == start - 1
    advancement.undo_last(rs, c)
    assert derive.willpower(c) == start                    # restored exactly
    assert c.xp_log == []


def test_undo_reverses_an_attribute_reduction():
    rs, c = _ruleset(), _locked()
    advancement.lower_attribute(c, AT.DEXTERITY, "curse")   # 3 -> 2
    advancement.undo_last(rs, c)
    assert c.attributes[AT.DEXTERITY] == 3
    assert c.xp_log == []


# --------------------------------------------------------------------------- #
# Decision 0013 groundwork: the two primitives the merged trait surface needs.
#
# `refundable_depth` decides what the downward-click dialog OFFERS (never whether a
# click does anything — see the decision record). `raise_to` is the stepper behind an
# upward click on a dot track.
# --------------------------------------------------------------------------- #

def test_refundable_depth_is_zero_with_an_empty_log():
    _rs, c = _ruleset(), _locked()
    assert advancement.refundable_depth(c, "attributes.dexterity") == 0


def test_refundable_depth_counts_consecutive_raises_of_that_trait():
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_attribute(rs, c, AT.DEXTERITY)      # 3 -> 4
    advancement.raise_attribute(rs, c, AT.DEXTERITY)      # 4 -> 5
    assert advancement.refundable_depth(c, "attributes.dexterity") == 2


def test_refundable_depth_stops_at_an_interrupting_purchase():
    """Undo is LIFO across the WHOLE log, not per trait. A Dexterity raise buried
    under an Ability purchase is not refundable without unwinding that Ability first,
    and the dialog must not offer it."""
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_attribute(rs, c, AT.DEXTERITY)
    advancement.raise_ability(rs, c, A.MELEE)
    assert advancement.refundable_depth(c, "attributes.dexterity") == 0
    assert advancement.refundable_depth(c, "abilities.melee") == 1


def test_refundable_depth_ignores_a_trait_never_raised():
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_attribute(rs, c, AT.DEXTERITY)
    assert advancement.refundable_depth(c, "attributes.strength") == 0


def test_a_reduction_at_the_tail_is_not_refundable():
    """A curse row shares the log with purchases but is not one: it refunds nothing,
    so a downward click above it is a REDUCE, not an undo. Distinguished by direction
    (to_rating < from_rating), not by cost — a withheld-Charm purchase also costs 0."""
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_attribute(rs, c, AT.DEXTERITY)
    advancement.lower_attribute(c, AT.DEXTERITY, "a curse")
    assert advancement.refundable_depth(c, "attributes.dexterity") == 0


# ---- raise_to (the stepper) ------------------------------------------------ #

def test_raise_to_logs_one_row_per_dot_at_escalating_prices():
    """The whole point of looping the existing step function: each dot is priced from
    the LIVE rating, so 3->5 is not two identical charges."""
    rs, c = _ruleset(), _locked(xp=200)
    entries = advancement.raise_to(rs, c, "attributes.dexterity", 5)
    assert [(e.from_rating, e.to_rating) for e in entries] == [(3, 4), (4, 5)]
    assert entries[0].cost < entries[1].cost          # current x 4
    assert c.attributes[AT.DEXTERITY] == 5
    assert advancement.xp_spent(c) == sum(e.cost for e in entries)


def test_raise_to_refuses_the_whole_click_when_only_part_is_affordable():
    """A half-applied click is the failure mode this exists to prevent: the player
    asked for 5 and must not silently land on 4 with their XP gone."""
    rs, c = _ruleset(), _locked(xp=200)
    one = advancement.costs.attribute_step(rs, c, 3, AT.DEXTERITY)
    c.xp_earned = one + 1                              # enough for the first dot only
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_to(rs, c, "attributes.dexterity", 5)
    assert c.attributes[AT.DEXTERITY] == 3             # nothing moved
    assert c.xp_log == []                              # and nothing was logged


def test_raise_to_refuses_the_whole_click_when_a_later_dot_is_illegal():
    """Affordability is not the only per-step gate — the cap is one too. A click that
    ends above the ceiling must not buy the dots below it on the way."""
    rs, c = _ruleset(), _locked(xp=500)
    c.abilities[A.MELEE] = 3
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_to(rs, c, "abilities.melee", 7)
    assert c.abilities[A.MELEE] == 3
    assert c.xp_log == []


def test_raise_to_is_a_no_op_at_or_below_the_current_rating():
    """Downward is not this function's job — it belongs to the dialog, which chooses
    between undo and reduce. Silently refunding here would pick one."""
    rs, c = _ruleset(), _locked(xp=200)
    assert advancement.raise_to(rs, c, "attributes.dexterity", 3) == []
    assert advancement.raise_to(rs, c, "attributes.dexterity", 1) == []
    assert c.attributes[AT.DEXTERITY] == 3
    assert c.xp_log == []


@pytest.mark.parametrize("target,attr,expected", [
    ("abilities.melee", None, 3),
    ("virtues.valor", None, 3),
    ("essence", None, 3),
])
def test_raise_to_routes_every_dot_tracked_target(target, attr, expected):
    """The four targets that ARE dot tracks in the editor. Willpower is deliberately
    absent: it is a number input, not a track (decision 0005 pins its Virtue half)."""
    rs, c = _ruleset(), _locked(xp=500)
    entries = advancement.raise_to(rs, c, target, expected)
    assert entries and entries[-1].to_rating == expected


def test_raise_to_rejects_an_unknown_target():
    rs, c = _ruleset(), _locked(xp=200)
    with pytest.raises(advancement.AdvancementError, match="willpower"):
        advancement.raise_to(rs, c, "willpower", 5)


# ---- the two downward branches (the dialog's, one function each) ----------- #

def test_refund_to_unwinds_exactly_the_dots_asked_for():
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_to(rs, c, "attributes.dexterity", 5)     # 3 -> 5, two rows
    spent = advancement.xp_spent(c)
    advancement.refund_to(rs, c, "attributes.dexterity", 4)    # give back one
    assert c.attributes[AT.DEXTERITY] == 4
    assert advancement.xp_spent(c) < spent
    assert advancement.refundable_depth(c, "attributes.dexterity") == 1


def test_refund_to_refuses_what_the_tail_cannot_give_back():
    """The guard that makes `refundable_depth` load-bearing rather than advisory: a
    raise buried under another purchase is not refundable, and asking anyway must
    fail loudly rather than unwinding the innocent purchase on top of it."""
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_attribute(rs, c, AT.DEXTERITY)
    advancement.raise_ability(rs, c, A.MELEE)
    melee = c.abilities[A.MELEE]
    with pytest.raises(advancement.AdvancementError):
        advancement.refund_to(rs, c, "attributes.dexterity", 3)
    assert c.attributes[AT.DEXTERITY] == 4
    assert c.abilities[A.MELEE] == melee            # the purchase on top is untouched


def test_lower_to_logs_one_reduction_per_dot_and_refunds_nothing():
    rs, c = _ruleset(), _locked(xp=200)
    advancement.lower_to(c, "attributes.dexterity", 1, "a curse")
    assert c.attributes[AT.DEXTERITY] == 1
    assert advancement.xp_spent(c) == 0                        # reductions are free
    assert [e.detail for e in c.xp_log] == ["a curse", "a curse"]


def test_lower_to_may_go_below_the_chargen_snapshot():
    """The difference from refund that matters: a curse is not bounded by what was
    bought. Dexterity 3 was a chargen dot, and a curse can still take it."""
    rs, c = _ruleset(), _locked(xp=200)
    assert advancement.refundable_depth(c, "attributes.dexterity") == 0
    advancement.lower_to(c, "attributes.dexterity", 2, "a curse")
    assert c.attributes[AT.DEXTERITY] == 2


def test_lower_to_refuses_the_whole_click_at_the_floor():
    rs, c = _ruleset(), _locked(xp=200)
    with pytest.raises(advancement.AdvancementError):
        advancement.lower_to(c, "attributes.dexterity", 0, "a curse")   # floor is 1
    assert c.attributes[AT.DEXTERITY] == 3
    assert c.xp_log == []


def test_lower_to_is_a_no_op_at_or_above_the_current_rating():
    rs, c = _ruleset(), _locked(xp=200)
    assert advancement.lower_to(c, "attributes.dexterity", 3, "x") == []
    assert advancement.lower_to(c, "attributes.dexterity", 5, "x") == []
    assert c.xp_log == []


# --------------------------------------------------------------------------- #
# The merged surface, rendered (decision 0013 / P1)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_builds_post_lock(user) -> None:
    """The editor has only ever been rendered pre-lock, so every post-lock branch in
    it is new and unbuilt. Until P2 puts the Edit tab back on the locked tab bar this
    route is the only thing that would catch a build-time crash in the buy path."""
    await user.open('/editor-locked')
    await user.should_see("Attributes")
    await user.should_see("Virtues")
    await user.should_see("Essence")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_downward_dialog_offers_both_branches_when_both_are_legal(user) -> None:
    """Decision 0013's core gesture. A dot bought with XP can be taken back OR cursed
    away, and the dialog must name both, with the refund's actual value."""
    await user.open('/editor-lower-both')
    await user.should_see("Lower by 1 dot")
    await user.should_see("Undo purchase")
    await user.should_see("Permanent loss")
    await user.should_see("reason")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_downward_dialog_explains_an_unrefundable_dot(user) -> None:
    """A chargen dot with no purchase on top: there is nothing to refund, and saying
    so beats a greyed button with no reason given. The curse branch stays live —
    that is the whole difference between the two."""
    await user.open('/editor-lower-curse-only')
    await user.should_see("Permanent loss")
    await user.should_see("last-in-first-out")


# ---- detail-carrying dot tracks: Crafts and Colleges (P2) ------------------ #
# These are the two tracks where "not owned" and "owned at 1" are one gesture but two
# different engine operations at two different prices.

def test_raise_to_learns_a_craft_it_does_not_own_yet():
    rs, c = _ruleset(), _locked(xp=200)
    entries = advancement.raise_to(rs, c, "crafts", 3, detail="Smithing")
    assert [(e.from_rating, e.to_rating) for e in entries] == [(0, 1), (1, 2), (2, 3)]
    assert [(cr.focus, cr.rating) for cr in c.crafts] == [("Smithing", 3)]
    # the first dot is the flat "new ability" price, the rest are scaled
    assert entries[0].cost != entries[2].cost


def test_two_crafts_do_not_share_a_refund_tail():
    """`detail` is what keeps them apart. Without it, buying Smithing then Tailoring
    would make Smithing look refundable — it is the same log target."""
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_to(rs, c, "crafts", 1, detail="Smithing")
    advancement.raise_to(rs, c, "crafts", 1, detail="Tailoring")
    assert advancement.refundable_depth(c, "crafts", "Smithing") == 0
    assert advancement.refundable_depth(c, "crafts", "Tailoring") == 1


def test_refunding_a_craft_removes_it_when_it_goes_back_to_zero():
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_to(rs, c, "crafts", 2, detail="Smithing")
    advancement.refund_to(rs, c, "crafts", 0, detail="Smithing")
    assert c.crafts == []
    assert advancement.xp_spent(c) == 0


def test_a_craft_reduction_refunds_nothing():
    """Superseded 2026-07-31: Crafts CAN be reduced now (human — "a misclick can
    always happen"). What stays true is that a reduction is not a refund: the dots go
    and the experience does not come back. `refund_to` is the path that returns XP."""
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_to(rs, c, "crafts", 2, detail="Smithing")
    spent = advancement.xp_spent(c)
    advancement.lower_to(c, "crafts", 1, "misclick", "Smithing")
    assert advancement.xp_spent(c) == spent


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_locked_editor_shows_experience_not_bonus_points(user) -> None:
    """P2: the chargen budget headers and the bonus-point card are frozen history once
    locked — showing them beside dots that now cost XP names the wrong currency."""
    await user.open('/editor-locked')
    await user.should_see("Experience")
    await user.should_see("XP available")
    await user.should_not_see("Bonus Points")
    # the Attribute panel header drops its 8/6/4 chargen pool
    await user.should_not_see("prioritise")


# ---- P3: the in-play sticky column ---------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_in_play_column_leads_with_experience_and_a_read_only_log(user) -> None:
    """Adjust XP on top, the log below it, and NO validation card on a clean
    character — the layout the human asked for."""
    await user.open('/column-clean')
    await user.should_see("Adjust XP")
    await user.should_see("XP available")
    await user.should_see("No XP spent yet.")
    await user.should_not_see("Live Validation")
    await user.should_not_see("Bonus Points")
    # nothing is wrong, so the validation card is not on the page at all
    await user.should_not_see("Validation")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_demoted_validation_card_still_appears_when_it_matters(user) -> None:
    """The reason validation was demoted rather than deleted. A curse that drops an
    Ability below a known Charm's requirement is a real post-lock finding, and the
    downward-click dialog is what makes it easy to cause — hiding it outright would
    blind the player exactly where the new gesture can hurt them."""
    await user.open('/column-broken')
    await user.should_see("Validation")
    await user.should_see("requires melee 2")
    # ...still below the ledger, not above it
    await user.should_see("Adjust XP")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_chargen_column_is_unchanged(user) -> None:
    """The other side of the same refreshable. Pre-lock must still lead with Live
    Validation and carry the bonus-point card."""
    await user.open('/custom')
    await user.should_see("Live Validation")
    await user.should_see("Bonus Points")
    await user.should_not_see("Adjust XP")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_undo_names_the_purchase_it_will_reverse_and_reverses_it(user) -> None:
    """The control that stops a read-only log from stranding every non-trait
    purchase. "Undo" alone would be a guess; it names the row."""
    await user.open('/column-undo')
    label = "Undo last: Charm: Excellent Strike"
    await user.should_see(label)
    await user.should_see("earned 100 · spent 8")     # Melee is Caste -> 8
    user.find(label).click()
    await user.should_see("earned 100 · spent 0")
    await user.should_see("No XP spent yet.")
    await user.should_not_see(label)                  # nothing left to undo


# ---- chargen choices are frozen at the lock (P3) --------------------------- #
# Making Edit a both-sides tab exposed every free setter on it to a locked character.
# The dot tracks became steppers; these controls are not traits to buy at all — they
# set the RATES every later purchase is priced at.

def _disabled_labels(user) -> set[str]:
    """Labels of every disabled select on the page."""
    from nicegui.elements.select import Select
    return {el.props.get("label") for el in user.client.elements.values()
            if isinstance(el, Select) and el.props.get("disable")}


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_chargen_choices_are_frozen_once_locked(user) -> None:
    """Re-picking Favoured Abilities in play would silently re-rate every future
    purchase; changing caste, Exalt type or origin would swap the budget row the
    snapshot was written from. Reported by the human at the browser, 2026-07-31."""
    await user.open('/identity-frozen')
    frozen = _disabled_labels(user)
    assert "Favored abilities (pick 5)" in frozen
    assert "Exalt type" in frozen
    assert "Caste" in frozen
    assert "Origin" in frozen
    assert "Training camp" in frozen
    assert "Calling" in frozen
    # Nature joined them 2026-07-31 (human): no XP effect, but it is True Paragon's
    # prerequisite, so changing it in play invalidates a held Merit after the fact.
    assert "Nature" in frozen
    # ...and the panel says WHY, so a greyed control is not a mystery
    await user.should_see("fixed at the lock")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_none_of_them_are_frozen_during_chargen(user) -> None:
    """The other half: freezing must not leak backwards into the tab's day job."""
    await user.open('/identity-open')
    assert _disabled_labels(user) == set()
    await user.should_not_see("fixed at the lock")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_descriptive_identity_fields_stay_editable_in_play(user) -> None:
    """Freezing is aimed at what PRICES things, not at the character sheet's prose.
    Renaming a character in play is normal — persistence even derives the filename
    from it."""
    from nicegui.elements.input import Input
    await user.open('/identity-frozen')
    editable = {el.props.get("label") for el in user.client.elements.values()
                if isinstance(el, Input) and not el.props.get("disable")}
    assert {"Name", "Concept"} <= editable


# ---- P3 rehoming: the cards that lived only on the XP tab ------------------ #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_willpower_gets_explicit_controls_in_play(user) -> None:
    """Willpower cannot be a dot track — decision 0005 pins its Virtue component, so
    only `willpower_purchased` moves and pips would misrepresent the total. It keeps
    the explicit pair decision 0013 promised it."""
    await user.open('/editor-locked')
    await user.should_see("Willpower")
    await user.should_not_see("Willpower purchased")     # the chargen control is gone


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_specialties_are_bought_not_appended_in_play(user) -> None:
    """Appending a blank row and editing it in place is a chargen gesture; post-lock
    the row would already have cost XP before it had a name."""
    await user.open('/editor-locked')
    await user.should_see("Specialty in")               # the named+priced buy form
    await user.should_not_see("Add specialty")          # the free append is gone


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_permanent_resonance_and_withheld_credits_have_a_home(user) -> None:
    """Both cards existed ONLY on the XP tab. Deleting that tab without moving them
    would have silently removed Death's Taint's whole play-time mechanic."""
    await user.open('/rehomed')
    await user.should_see("Permanent Resonance")
    await user.should_see("Gain (free)")
    await user.should_see("Shed")
    # Weak Essence's banked chargen Charms, beside the XP accounting
    await user.should_see("withheld Charm(s) in reserve")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_resonance_panel_is_absent_during_chargen_and_for_other_splats(user) -> None:
    await user.open('/identity-open')                    # a Solar, unlocked
    await user.should_not_see("Permanent Resonance")
    await user.open('/editor-locked')                    # a Solar, locked
    await user.should_not_see("Permanent Resonance")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
@pytest.mark.parametrize("route", ['/editor-locked-mortal', '/editor-locked-alchemical'])
async def test_the_merged_editor_builds_for_the_awkward_splats(user, route) -> None:
    """P5 render matrix. A Mortal has no castes and no Charms; an Alchemical picks
    Favored ATTRIBUTES rather than Abilities. Both are shapes that have crashed or
    blanked an editor before, and the editor had never been rendered post-lock at all
    until decision 0013."""
    await user.open(route)
    await user.should_see("Attributes")
    await user.should_see("Experience")        # the in-play column built
    await user.should_see("fixed at the lock")  # the freeze notice built


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_mortals_favored_picks_are_frozen_too(user) -> None:
    """A heroic mortal's single Favoured Ability is an ST toggle rather than a budget,
    so it comes through a different code path than every other splat's."""
    await user.open('/editor-locked-mortal')
    from nicegui.elements.select import Select
    labels = {el.props.get("label") for el in user.client.elements.values()
              if isinstance(el, Select) and not el.props.get("disable")}
    assert not any(str(l).startswith("Favored") for l in labels)


# ---- P4: the ledger's read-only copy on the sheet -------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_sheet_prints_the_xp_ledger(user) -> None:
    await user.open('/sheet-ledger')
    await user.should_see("Experience")
    await user.should_see("Charm: Excellent Strike")
    await user.should_see("earned 100")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_sheet_ledger_carries_no_controls(user) -> None:
    """The constraint that shaped P4: `render_sheet` takes only a SheetView — no
    ruleset, no character, no callbacks — and the GM party screen and every render
    test depend on it. A ledger with working buttons would have been the first thing
    to break that, so the sheet's copy is history and the live one stays on Edit."""
    await user.open('/sheet-ledger')
    await user.should_not_see("Adjust XP")
    await user.should_not_see("Undo last")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_chargen_sheet_has_no_experience_section(user) -> None:
    """Empty pre-lock by construction, but suppressed explicitly: an "Experience"
    heading with nothing under it reads as a bug on a character still being built."""
    await user.open('/sheet-desc')
    await user.should_not_see("No XP spent yet.")


def test_build_sheet_view_carries_the_ledger_without_a_character(rs=None):
    """The purity contract itself, asserted on the dataclass rather than through a
    page: everything the sheet needs to print the ledger is IN the SheetView."""
    from dataclasses import fields
    from exalted_builder.ui import view as viewmod
    names = {f.name for f in fields(viewmod.SheetView)}
    assert {"xp_earned", "xp_spent", "xp_available", "xp_log"} <= names


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_merged_editor_builds_for_a_lunar(user) -> None:
    """Lunar castes carry no caste-Abilities, so the Ability panel groups differently
    from every other splat — a shape that has blanked panels before."""
    await user.open('/editor-locked-lunar')
    await user.should_see("Abilities")
    await user.should_see("Experience")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_merged_editor_builds_with_off_catalogue_gear_and_nature(user) -> None:
    """`ui.select` raises at BUILD time when its value is not among its options, and
    the freeze now wraps several selects — a frozen select still has to build with
    whatever the save happens to hold."""
    await user.open('/editor-locked-odd')
    # Weapons and armour moved to the Gear tab (2026-08-13); the frozen SELECTS this
    # test is really about — Nature, caste, origin — stayed on Edit.
    await user.open('/editor-locked-odd-gear')
    await user.should_see("Grandpa's Axe")
    await user.should_see("Scrap Plate")
    await user.open('/editor-locked-odd')
    await user.should_see("Not In The Catalog")


# ---- Crafts and Colleges can be reduced (human, 2026-07-31) ---------------- #
# Not a printed rule — a usability one: "a misclick can always happen", and undo is
# LIFO so it cannot always reach the mistake. These are the escape hatch.

def test_a_craft_can_be_reduced():
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_to(rs, c, "crafts", 3, detail="Smithing")
    advancement.lower_to(c, "crafts", 1, "misclick", "Smithing")
    assert [(cr.focus, cr.rating) for cr in c.crafts] == [("Smithing", 1)]
    # a reduction refunds nothing — the XP for those dots stays spent
    assert advancement.xp_spent(c) == sum(e.cost for e in c.xp_log)


def test_reducing_a_craft_to_zero_removes_it():
    """Rating 0 is not a state a Craft has — `learn_craft` starts it at 1 and the
    focus is the identity. Matches what `refund_to` already does."""
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_to(rs, c, "crafts", 2, detail="Smithing")
    advancement.lower_to(c, "crafts", 0, "misclick", "Smithing")
    assert c.crafts == []


def test_reducing_a_craft_never_touches_a_different_one():
    """`detail` is the identity. A lowerer that looked the row up by TARGET alone
    would find the first Craft in the list and quietly reduce the wrong one."""
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_to(rs, c, "crafts", 2, detail="Smithing")
    advancement.raise_to(rs, c, "crafts", 2, detail="Tailoring")
    advancement.lower_to(c, "crafts", 1, "misclick", "Tailoring")
    assert [(cr.focus, cr.rating) for cr in c.crafts] == [("Smithing", 2), ("Tailoring", 1)]


# ---- specialties: instances, not ratings (human, 2026-07-31) --------------- #
# "You don't raise specialties, you just take the same one multiple times, and you can
# only have 3 specialties per ability — you can have Melee 4 with two specialties in
# swords and one in parrying, but you can't buy two dots of sword specialties."
# So: every specialty is worth 1, duplicates are how you stack, and the cap is 3 rows
# per Ability (not per name).

def test_a_specialty_is_always_worth_one():
    rs, c = _ruleset(), _locked(xp=200)
    advancement.add_specialty(rs, c, A.MELEE, "Swords")
    assert [s.rating for s in c.specialties] == [1]


def test_the_same_specialty_may_be_taken_more_than_once():
    """That is the stacking mechanism — two rows, not one row at 2."""
    rs, c = _ruleset(), _locked(xp=200)
    advancement.add_specialty(rs, c, A.MELEE, "Swords")
    advancement.add_specialty(rs, c, A.MELEE, "Swords")
    assert [(s.name, s.rating) for s in c.specialties] == [("Swords", 1), ("Swords", 1)]


def test_three_specialties_per_ability_is_the_cap():
    """The human's own example: Melee with two Swords and one Parrying is legal and
    full. Counted per ABILITY, not per name."""
    rs, c = _ruleset(), _locked(xp=200)
    advancement.add_specialty(rs, c, A.MELEE, "Swords")
    advancement.add_specialty(rs, c, A.MELEE, "Swords")
    advancement.add_specialty(rs, c, A.MELEE, "Parrying")
    with pytest.raises(advancement.AdvancementError, match="three"):
        advancement.add_specialty(rs, c, A.MELEE, "Feints")
    assert len(c.specialties) == 3
    # ...and the cap is per ability, so another Ability is untouched by it
    advancement.add_specialty(rs, c, A.OCCULT, "Spirits")
    assert len(c.specialties) == 4


def test_validation_flags_an_over_capped_ability(rs=None):
    """Chargen has no `add_specialty` gate — the editor writes the list directly — so
    the cap has to be a validation rule too, not only an advancement guard."""
    from exalted_builder.engine import validate as v
    rs = _ruleset()
    c = Character(id="c", caste="dawn")
    c.specialties = [Specialty(ability=A.MELEE, name=n, rating=1)
                     for n in ("a", "b", "c", "d")]
    codes = [i.code for i in v.validate(rs, c)]
    assert "specialty-cap" in codes


def test_validation_flags_a_rating_above_one(rs=None):
    """A legacy save (or a hand-edit) can still hold one; the loader splits them, but
    validation says so rather than silently pricing a thing that cannot exist."""
    from exalted_builder.engine import validate as v
    rs = _ruleset()
    c = Character(id="c", caste="dawn")
    c.specialties = [Specialty(ability=A.MELEE, name="Swords", rating=2)]
    assert "specialty-rating" in [i.code for i in v.validate(rs, c)]


def test_a_legacy_rated_specialty_is_split_into_instances_on_load(tmp_path):
    """Mechanically identical (a rating-2 Swords WAS two dice) and it makes every
    later rule — the cap, the BP sum, the buy path — see one shape."""
    from exalted_builder import persistence
    p = tmp_path / "legacy.character.json"
    p.write_text('{"id": "l", "name": "Legacy", "caste": "dawn", "specialties": '
                 '[{"ability": "melee", "name": "Daiklaves", "rating": 3}]}',
                 encoding="utf-8")
    c = persistence.load_character(p)
    assert [(s.name, s.rating) for s in c.specialties] == [
        ("Daiklaves", 1), ("Daiklaves", 1), ("Daiklaves", 1)]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_specialty_panel_has_no_rating_control(user) -> None:
    """The UI half of the same ruling. A dot track here would offer a rating that does
    not exist — and it was the one dot track left as a free setter in play, which is
    now moot rather than deferred."""
    await user.open('/editor-locked')
    await user.should_see("max 3 per Ability")
    await user.should_see("take one twice to stack it")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_retargeting_a_specialty_row_clears_the_stale_cap_error(user) -> None:
    """The reported bug: three Melee + three Dodge + one Awareness specialty read back
    as "Melee has 4 specialties". The MODEL was right; the sticky issues column was
    stale. `add_spec` appends the row on Melee and calls `changed()`, so the transient
    over-cap error renders — and the row's Ability select used to write the model
    WITHOUT re-running validation, leaving that error on screen forever."""
    from nicegui.elements.select import Select
    await user.open('/specialty-retarget')
    await user.should_see("4 specialties")
    spec_selects = [el for el in user.client.elements.values()
                    if isinstance(el, Select) and isinstance(el.options, dict)
                    and set(el.options) == set(A)]
    spec_selects[-1].set_value(A.DODGE)
    await user.should_not_see("4 specialties")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_virtue_flaw_offers_the_books_samples_for_that_virtue(user) -> None:
    """core pp.131-133 print ten sample Flaws and the build had none of them — the
    player typed free text where the book prints a named list. The dropdown is keyed to
    the FLAWED Virtue: offering a Compassion Flaw beside a flawed Valor would be
    offering a pick p.131 does not allow."""
    from nicegui.elements.select import Select
    await user.open('/virtue-flaw')
    await user.should_see("Virtue Flaw")
    sel = next(e for e in user.client.elements.values()
               if isinstance(e, Select)
               and "Sample Flaw" in (e.props.get("label") or ""))
    assert set(sel.options.values()) == {"Berserk Anger", "Foolhardy Contempt"}
    # Picking one fills the free-text description with the printed text and surfaces
    # the Limit Break Condition beside it.
    sel.set_value("virtue-flaw.berserk-anger")
    await user.should_see("he simply loses all control")
    await user.should_see("Limit Break: The character is insulted")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_changing_the_flawed_virtue_reloads_the_sample_flaws(user) -> None:
    """Found in the browser: the sample list kept offering the OLD Virtue's Flaws until
    the player picked one from it — the list was wrong exactly while it was being read.
    `changed()` redraws only the sticky side column; this dropdown is built from the
    flawed Virtue and needs the body rebuilt."""
    from nicegui.elements.select import Select
    await user.open('/virtue-flaw')

    def _samples():
        sel = [e for e in user.client.elements.values()
               if isinstance(e, Select) and "Sample Flaw" in (e.props.get("label") or "")]
        assert sel, "no sample-Flaw dropdown on the page"
        return set(sel[-1].options.values())

    assert _samples() == {"Berserk Anger", "Foolhardy Contempt"}       # Valor
    virtue_sel = next(e for e in user.client.elements.values()
                      if isinstance(e, Select)
                      and e.props.get("label") == "Flawed Virtue")
    virtue_sel.set_value(VirtueName.COMPASSION)
    # Poll: a select's OPTIONS are props, not page text, so `should_see` cannot wait on
    # them and the rebuild is async.
    import asyncio
    expected = {"Compassionate Martyrdom", "Heart of Tears", "Red Rage of Compassion"}
    for _ in range(100):
        if _samples() == expected:
            break
        await asyncio.sleep(0.02)
    assert _samples() == expected
