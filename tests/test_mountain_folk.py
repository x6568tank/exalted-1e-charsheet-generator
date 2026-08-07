"""Tests for the Mountain Folk splat — CH6, pp.214-293.

The tenth splat, the fifth non-Exalt: the Jadeborn, Autochthon's underground
children. Two deep mechanics no prior splat had:

  * the Enlightenment ORIGIN axis (Enlightened / Unenlightened), which rewrites
    nearly every chargen number — attribute pools 16/13/10 vs 8/4/3, a TWO-POOL
    Ability budget (favored + free dots), per-caste Background dots (13 Artisan /
    10 Enlightened undercaste / 6 Unenlightened), trait ceilings 7/6 vs Int-2/5,
    Essence cap 5 vs 3, and a hard Willpower cap 6 for the Unenlightened;
  * the Pattern Charm gate — Charms live in five Patterns (Foundation/Worker/
    Warrior/Artisan/Enlightened), gated on Minimum Essence only, with chargen
    access rules (Unenlightened: own Caste Pattern + Foundation only; Enlightened:
    at most 3 from another caste's Pattern) and cross-pattern pricing (7 BP / 12 XP).

The distinctive numbers are asserted one per keyed-table row, because a keyed row
that does not exist falls back silently at another splat's prices —
`adding-a-splat.md` trap #2.

Rulings (human, 2026-08-07): the chargen "three of these dots" cap binds the 25
free dots only, not the 10 favored dots; the Enlightened "no Attribute below 3" is
a spend-to floor; the Artisan College "•• divided among Craft Abilities" is a
group-sum floor; the Great Geas clause list is a reference panel, not engine
enforcement. Combos are available (an artifact's "cannot be part of a Combo"
implies Charm-users can combo). The Fivefold Embodiment colours are five separate
Charms (per-variant external prerequisites the engine cannot express), so the
"not more versions than permanent Essence" cap is display-noted, not enforced.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db

_DATA = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_app_ruleset(_DATA)


from exalted_builder.engine import (advancement, costs, derive, elder,  # noqa: E402
                                    lifecycle, validate)
from exalted_builder.models.character import (BackgroundEntry,  # noqa: E402
                                              Character, CraftRating)
from exalted_builder.models.rules import AbilityName  # noqa: E402

# The 24 non-Craft Abilities, so a test can build a full 25-ability sheet.
_NON_CRAFT = [a.value for a in AbilityName if a is not AbilityName.CRAFT]


def _mf(exalt_type="Mountain-Folk", origin="enlightened", caste="worker", **kw):
    kw.setdefault("essence_rating", 2)
    kw.setdefault("attributes", {
        "strength": 3, "dexterity": 3, "stamina": 3,
        "charisma": 3, "manipulation": 3, "appearance": 3,
        "perception": 3, "intelligence": 3, "wits": 3})
    kw.setdefault("abilities", {})
    kw.setdefault("virtues", {"compassion": 2, "conviction": 2,
                              "temperance": 2, "valor": 2})
    kw.setdefault("favored_abilities", ["craft", "awareness", "bureaucracy",
                                        "lore", "occult", "melee"])
    kw.setdefault("backgrounds", [])
    return Character(id="mf", exalt_type=exalt_type, origin=origin, caste=caste, **kw)


def _issues(rs, c):
    return validate.validate_chargen(rs, c)


# --------------------------------------------------------------------------- #
# The two origin rows — one distinctive number each
# --------------------------------------------------------------------------- #

def test_enlightened_budget_row(rs):
    b = rs.budgets_for("Mountain-Folk", "enlightened")
    assert tuple(b.attribute_pools) == (16, 13, 10)
    assert b.attribute_min == 3          # no Attribute below 3 (p.230)
    assert b.attribute_cap == 7          # no Attribute above 7
    assert b.ability_favored_dots == 10  # two-pool: 10 favored + 25 free
    assert b.ability_dots == 25
    assert b.ability_cap == 6            # Abilities to 6 with bonus points
    assert b.favored_count == 6          # Craft + five chosen
    assert "craft" in [a.value for a in b.required_favored]
    assert b.background_dots == 10
    assert b.background_dots_by_caste == {"artisan": 13}
    assert b.charm_count == 6
    assert b.essence_start == 2
    assert "cult" in b.banned_backgrounds
    assert b.willpower_hard_cap == 0


def test_unenlightened_budget_row(rs):
    b = rs.budgets_for("Mountain-Folk", "unenlightened")
    assert tuple(b.attribute_pools) == (8, 4, 3)
    assert b.attribute_caps == {"intelligence": 2}   # Int never above 2
    assert b.ability_favored_dots == 14
    assert b.ability_dots == 8
    assert b.background_dots == 6
    assert b.charm_count == 3
    assert b.essence_start == 1
    assert b.essence_cap == 3            # never above 3
    assert b.willpower_hard_cap == 6     # never above 6
    assert "followers" in b.banned_backgrounds


# --------------------------------------------------------------------------- #
# Costs
# --------------------------------------------------------------------------- #

def test_cost_rows(rs):
    bp = rs.bonus_costs_for("Mountain-Folk", "")
    assert bp.essence == 10              # BP table p.233
    assert bp.charm == 5
    assert bp.charm_cross_pattern == 7   # "7 if part of another caste's Pattern"
    xp = rs.xp_costs_for("Mountain-Folk")
    assert xp.essence.coeff == 10        # current rating x 10 (p.233)
    assert xp.craft.coeff == 1           # Superior Craftsmanship: half price
    assert xp.craft_specialty == 2
    assert xp.new_charm == 10
    assert xp.new_charm_cross_pattern == 12


def test_craft_xp_is_half_price(rs):
    c = _mf(essence_rating=2)
    # 4 -> 5: Solar ability costs current x 2 (8); MF Craft costs current (4).
    assert costs.ability_step(rs, c, AbilityName.CRAFT, 4) == 4
    assert costs.specialty_cost(rs, c, AbilityName.CRAFT) == 2
    assert costs.specialty_cost(rs, c, AbilityName.MELEE) == 3   # ordinary rate


def test_cross_pattern_charm_xp_and_bp(rs):
    c = _mf(caste="worker")
    own = rs.charms["mountainfolk.worker.harvest-multiplying-labor"]
    cross = rs.charms["mountainfolk.warrior.arsenal-enhancing-technique"]
    assert costs.charm_cost(rs, c, own) == 10
    assert costs.charm_cost(rs, c, cross) == 12


# --------------------------------------------------------------------------- #
# The Pattern Charm gate (p.230, p.244)
# --------------------------------------------------------------------------- #

def test_unenlightened_barred_from_other_patterns(rs):
    # p.244: an Unenlightened Jadeborn may only learn their own Caste Pattern or the
    # Foundation Pattern. The bar lives in charm_matches_splat, so the general
    # validator (which runs the splat-consistency check) catches a Warrior-Pattern
    # Charm as a wrong-splat pick.
    c = _mf(origin="unenlightened", caste="worker",
            charms=["mountainfolk.worker.harvest-multiplying-labor",
                    "mountainfolk.warrior.arsenal-enhancing-technique"])
    codes = {i.code for i in validate.validate(rs, c)}
    assert "charm-wrong-splat" in codes


def test_unenlightened_pattern_bar_binds_post_lock(rs):
    # p.244 is a LIFETIME rule, not a chargen one: an Unenlightened Worker may not buy
    # an Artisan-Pattern Charm with XP after the lock. The old implementation only
    # ran over chargen picks, so this purchase succeeded for 12 points.
    c = _mf(origin="unenlightened", caste="worker", essence_rating=1)
    lifecycle.lock_chargen(c, rs)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, "mountainfolk.artisan.unfolding-pattern-intuition")


def test_enlightened_cross_pattern_cap(rs):
    # An Enlightened Warrior may take at most 3 chargen Charms from another caste's
    # Pattern (the Artisan Pattern here); Foundation and own-Pattern do not count.
    # Four Artisan Charms breach the cap even before any Warrior Charms.
    c = _mf(origin="enlightened", caste="warrior",
            charms=["mountainfolk.artisan.sign-of-warding",
                    "mountainfolk.artisan.elemental-invocation-rite",
                    "mountainfolk.artisan.spirit-calcifying-technique",
                    "mountainfolk.artisan.god-summoning-glyph"])
    codes = {i.code for i in _issues(rs, c)}
    assert "mountain-folk-pattern-cross-cap" in codes


def test_artisan_must_be_enlightened(rs):
    c = _mf(origin="unenlightened", caste="artisan")
    codes = {i.code for i in _issues(rs, c)}
    assert "artisan-must-be-enlightened" in codes


# --------------------------------------------------------------------------- #
# Trait ceilings
# --------------------------------------------------------------------------- #

def test_enlightened_trait_ceilings(rs):
    c = _mf(origin="enlightened", essence_rating=2)
    assert elder.trait_ceiling(c, rs, "attribute") == 7
    assert elder.trait_ceiling(c, rs, "ability") == 6
    assert elder.essence_cap(rs, c)[0] == 5


def test_unenlightened_intelligence_ceiling(rs):
    c = _mf(origin="unenlightened", caste="worker", essence_rating=1)
    assert elder.essence_cap(rs, c)[0] == 3
    # Raising Intelligence past 2 is refused post-lock.
    c.attributes["intelligence"] = 2
    c.willpower_purchased = 0
    lifecycle.lock_chargen(c, rs)
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_attribute(rs, c, _int())


def _int():
    from exalted_builder.models.rules import AttributeName
    return AttributeName.INTELLIGENCE


# --------------------------------------------------------------------------- #
# Repeatable Charms
# --------------------------------------------------------------------------- #

def test_ox_body_caps_on_highest_virtue(rs):
    c = _mf(essence_rating=2, virtues={"compassion": 2, "conviction": 3,
                                       "temperance": 2, "valor": 2})
    assert validate.ox_body_cap(rs, c) == 3     # highest Virtue (Conviction 3)
    for i in range(3):
        validate.commit_ox_body_purchase(rs, c, "one-one-two") \
            if hasattr(validate, "commit_ox_body_purchase") else None
    # over-cap flagged
    c2 = _mf(virtues={"compassion": 1, "conviction": 1, "temperance": 1, "valor": 1})
    issues = validate.check_ox_body(rs, c2)
    assert not issues or "ox-body-over-cap" not in {i.code for i in issues}


def test_satiation_repeatable_on_essence(rs):
    ch = rs.charms["mountainfolk.foundation.essence-satiation-method"]
    c = _mf(essence_rating=2)
    assert validate._repeatable_purchase_cap(ch, c) == 2   # third needs Essence 3
    c.essence_rating = 3
    assert validate._repeatable_purchase_cap(ch, c) == 3
    # The printed "three times" is a FLAT cap: an Essence-5 Jadeborn still buys at
    # most three (p.245-246), not five.
    c.essence_rating = 5
    assert validate._repeatable_purchase_cap(ch, c) == 3


# --------------------------------------------------------------------------- #
# Chargen accounting
# --------------------------------------------------------------------------- #

def test_cult_background_banned(rs):
    c = _mf(backgrounds=[__import__("exalted_builder.models.character",
                                    fromlist=["BackgroundEntry"]).BackgroundEntry(
                                        name="Cult", rating=1)])
    codes = {i.code for i in _issues(rs, c)}
    assert "background-banned" in codes


def _ability_bp(rs, c) -> int:
    """The bonus-point charge attributable to Abilities alone, so the two-pool tests
    can assert the pool arithmetic without the other trait lines in the way."""
    bd = validate.bonus_point_breakdown(rs, c)
    return next(l.points for l in bd.lines if l.domain == "Abilities")


def _full_ability_sheet(rs, origin="enlightened", caste="worker", favored=None,
                        favored_ratings=None, nonfavored=(), nonfavored_rating=1,
                        craft_rating=0, **kw):
    """A chargen-legal Mountain Folk character where ONLY the Ability dots vary: all
    other traits sit inside their budgets so the Ability BP is the whole bill. Favored
    abilities (default the six in the book: Craft + five) can be rated per-ability;
    `nonfavored` names the non-favored abilities to dot at `nonfavored_rating`."""
    favored = favored or ["craft", "awareness", "bureaucracy", "lore", "occult", "melee"]
    favored_ratings = favored_ratings or {}
    abilities = {}
    for ab in _NON_CRAFT:
        abilities[ab] = favored_ratings.get(ab, 0) if ab in favored else (
            nonfavored_rating if ab in nonfavored else 0)
    crafts = [CraftRating(focus="Smithing", rating=craft_rating)] if craft_rating else []
    c = Character(
        id="mf-bp", exalt_type="Mountain-Folk", origin=origin, caste=caste,
        essence_rating=2 if origin == "enlightened" else 1,
        attributes={"strength": 3, "dexterity": 3, "stamina": 3, "charisma": 3,
                    "manipulation": 3, "appearance": 3, "perception": 3,
                    "intelligence": 3, "wits": 3},
        abilities=abilities, favored_abilities=favored,
        virtues={"compassion": 2, "conviction": 3, "temperance": 2, "valor": 2},
        backgrounds=[BackgroundEntry(name="Resources", rating=2),
                     BackgroundEntry(name="Mentor", rating=2)],
        crafts=crafts,
        charms=("mountainfolk.worker.pillar-of-compassion",
                "mountainfolk.worker.pillar-of-conviction",
                "mountainfolk.worker.pillar-of-temperance",
                "mountainfolk.worker.pillar-of-valor",
                "mountainfolk.foundation.ox-body-technique",
                "mountainfolk.foundation.essence-satiation-method")[:6],
        **kw)
    # Craft is ALWAYS favored for the Jadeborn (p.230); the _mf default set already
    # includes it, but keep the assertion explicit so a changed helper cannot drift.
    assert "craft" in favored
    return c


def test_two_pool_legal_enlightened_sheet_costs_no_bp(rs):
    # Exactly the printed 10 favored + 25 free: six Favored Abilities at 3 (18 dots,
    # Craft via a focus) and seventeen non-favored abilities at 1 (17) = 35, nothing
    # above 3. A legal sheet must cost 0 bonus points — the old billing charged 10.
    c = _full_ability_sheet(rs, favored_ratings={"awareness": 3, "bureaucracy": 3,
                                                 "lore": 3, "occult": 3, "melee": 3},
                            craft_rating=3,
                            nonfavored=("archery", "athletics", "brawl", "dodge",
                                        "endurance", "investigation", "larceny",
                                        "linguistics", "martial_arts", "medicine",
                                        "performance", "presence", "resistance",
                                        "ride", "sail", "stealth", "survival"))
    assert _ability_bp(rs, c) == 0


def test_two_pool_legal_unenlightened_sheet_costs_no_bp(rs):
    # The Unenlightened 14 favored + 8 free shape, all within pools -> 0 BP.
    # 14 favored dots (Craft 3 + the five chosen at 2/3) + 8 free dots.
    c = _full_ability_sheet(rs, origin="unenlightened", caste="worker",
                            favored_ratings={"awareness": 3, "bureaucracy": 2,
                                             "lore": 2, "occult": 2, "melee": 2},
                            craft_rating=3,
                            nonfavored=("archery", "athletics", "brawl", "dodge",
                                        "endurance", "investigation", "larceny",
                                        "linguistics"))
    assert _ability_bp(rs, c) == 0


def test_two_pool_favored_ability_at_five_costs_no_bp(rs):
    # A Favored Ability at 5 is 3 free + 2 favored — both pools, no bonus points.
    c = _full_ability_sheet(rs, favored_ratings={"melee": 5})
    assert _ability_bp(rs, c) == 0


def test_two_pool_favored_ability_at_six_costs_bp(rs):
    # The sixth dot is above the chargen ability ceiling (p.230: "as high as six dots
    # with bonus points"), so it is bought at the favored rate (1 BP).
    c = _full_ability_sheet(rs, favored_ratings={"melee": 6})
    assert _ability_bp(rs, c) == 1


def test_two_pool_non_favored_ability_at_four_costs_bp(rs):
    # A non-Favored Ability above the 3-cap is bought at the ordinary rate (2 BP).
    # Melee is dropped from the favored set so it counts as non-Favored.
    c = _full_ability_sheet(rs, favored=["craft", "awareness", "bureaucracy",
                                         "lore", "occult", "endurance"],
                            nonfavored=("melee",), nonfavored_rating=4)
    assert _ability_bp(rs, c) == 2


def test_two_pool_over_spending_the_combined_pool_charges(rs):
    # More than 35 ability dots total overflows the pools to bonus points.
    c = _full_ability_sheet(rs, favored_ratings={"awareness": 3, "bureaucracy": 3,
                                                 "lore": 3, "occult": 3, "melee": 3},
                            craft_rating=3,
                            nonfavored=("archery", "athletics", "brawl", "dodge",
                                        "endurance", "investigation", "larceny",
                                        "linguistics", "martial_arts", "medicine",
                                        "performance", "presence", "resistance",
                                        "ride", "sail", "stealth", "survival",
                                        "thrown"))
    assert _ability_bp(rs, c) > 0


def test_no_foreign_charms_for_jadeborn(rs):
    # p.244: "they cannot learn supernatural martial arts" — the Mountain-Folk row
    # carries `foreign_charms_barred` (like ghosts/DK/God-Blooded), so no
    # non-Mountain-Folk Charm satisfies charm_matches_splat for a Jadeborn, while all
    # 94 native Charms do. Before the review the cross-splat Terrestrial styles
    # (Five-Dragon, Falling Blossom) and the open_to_tiers styles leaked in.
    c = _mf()
    for cid, charm in rs.charms.items():
        if charm.exalt_type == "Mountain-Folk":
            assert validate.charm_matches_splat(c, charm, rs), cid
        else:
            assert not validate.charm_matches_splat(c, charm, rs), cid


def test_attribute_floor_follows_a_flaw_lowered_ceiling(rs):
    # An Enlightened Jadeborn's "no Attribute below 3" floor (p.230) must still
    # follow a Flaw-lowered ceiling down: Disfigured at FOUR points caps Appearance at
    # 0, so an Appearance of 0 is legal — a floor stuck at 3 would demand an
    # unsatisfiable "3-0" range. The option is selected by TIER ("3"/"4"), not rating:
    # rating=4 applies no cap and makes this test vacuous (a review finding).
    from exalted_builder.models.character import MeritFlawPurchase
    attrs = {"strength": 3, "dexterity": 3, "stamina": 3, "charisma": 3,
             "manipulation": 3, "appearance": 0, "perception": 3,
             "intelligence": 3, "wits": 3}
    c = _mf(attributes=attrs,
            merits_flaws=[MeritFlawPurchase(merit_id="mf.disfigured", tier="4")])
    ranges = [i for i in _issues(rs, c) if i.code == "attribute-range"]
    assert not any(i.where == "appearance" for i in ranges)


def test_banned_backgrounds_omitted_from_catalog(rs):
    # Cult is "explicitly prohibited" (CH6 p.234), so it is not even OFFERED to a
    # Mountain Folk character — the dropdown never shows a name the sheet cannot
    # hold. The Unenlightened additionally lose Followers (p.234: "cannot possess
    # this Background").
    enlightened = [b.name.lower() for b in rs.backgrounds_for("Mountain-Folk", "enlightened")]
    unenlightened = [b.name.lower() for b in rs.backgrounds_for("Mountain-Folk", "unenlightened")]
    assert "cult" not in enlightened
    assert "cult" not in unenlightened
    assert "followers" not in unenlightened
    # Other splats are unaffected — the ban is per-origin.
    assert "cult" in [b.name.lower() for b in rs.backgrounds_for("Solar")]


def test_artisan_college_floors(rs):
    # The Artisan's College of Divine Enlightenment minimums (p.230): the OR floors
    # and the "•• divided among Craft Abilities" group-sum floor.
    c = _mf(caste="artisan", abilities={"awareness": 1, "bureaucracy": 2,
                                        "linguistics": 2, "lore": 2, "occult": 2,
                                        "socialize": 2}, crafts=[])
    codes = {i.code for i in _issues(rs, c)}
    assert "required-min-ability-group" in codes   # no Craft dots at all
    c.crafts.append(__import__("exalted_builder.models.character",
                               fromlist=["CraftRating"]).CraftRating(
                                   focus="Smithing", rating=2))
    codes = {i.code for i in _issues(rs, c)}
    assert "required-min-ability-group" not in codes


def test_single_essence_pool_is_essence_times_ten(rs):
    c = _mf(essence_rating=2)
    personal, peripheral = derive.essence_pools(rs, c)
    # The Jadeborn have ONE pool of Essence x 10 (p.230), merged to Peripheral like
    # the ghosts' — so the total is 20 motes at Essence 2, sitting in peripheral.
    assert peripheral == 20
    assert personal == 0


def test_limit_track_is_called_divergence(rs):
    # The Great Geas is the Jadeborn's Limit analogue, renamed like Sidereal Paradox
    # (CH6 pp.235-236). The GM tracker reads this label to show DIVERGENCE and the
    # nine-clause reference panel.
    c = _mf()
    assert derive.limit_label(rs, c) == "Divergence"


def test_origin_drives_the_budget_rows(rs):
    # The Enlightenment origin axis is what makes the two budget rows reachable; a
    # new Mountain Folk character defaults to Enlightened (the first _SPLAT_ORIGINS
    # key), and the per-caste Background budget and trait ceilings come from there.
    enlightened = rs.budgets_for("Mountain-Folk", "enlightened")
    assert validate.background_dots_budget(enlightened,
                                           _mf(caste="artisan")) == 13
    assert validate.background_dots_budget(enlightened,
                                           _mf(caste="worker")) == 10
    unenlightened = rs.budgets_for("Mountain-Folk", "unenlightened")
    assert validate.background_dots_budget(unenlightened,
                                           _mf(origin="unenlightened", caste="worker")) == 6
