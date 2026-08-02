"""Tests for the God-Blooded splat — Phase A: core chargen + the Ghost-Blooded
heritage (Player's Guide CH2). The load-bearing tests are the per-heritage
Charm-access matrix through the BUY path, not the constants: a rule that is
implemented but never runs where it matters is this build's most-repeated bug,
and charm access is where a Ghost-Blooded goes wrong quietly.
See docs/status/godblooded.md."""

from pathlib import Path

import pytest
from pydantic import ValidationError

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import advancement, costs, derive, lifecycle, merits, validate
from exalted_builder.models.character import (
    BackgroundEntry, Character, Combo, HouseRules, MeritFlawPurchase as MP,
    OxBodyPurchase)
from exalted_builder.models.rules import AbilityName, SpellCircle, VirtueName

DATA_DIR = Path(exalted_builder.__file__).parent / "data"

AWAKENED = "mf.awakened-essence"
ARCANOS = "ghost.savage-ghost-tamer.taste-the-demon-wind"
FOREIGN = "solar.melee.fire-and-stones-strike"
FIVE_DRAGON = "dragonblooded.martial-arts.five-dragon-form"
HUNGRY_GHOST = "abyssal.martial-arts.hungry-ghost-form"
INITIATION = "solar.occult.terrestrial-circle-sorcery"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _gb(**kw) -> Character:
    c = Character(id="gb", name="Sighing Willow", exalt_type="God-Blooded",
                  caste="ghost-blooded", essence_rating=1)
    # WP = two highest Virtues = 3 + 2 = 5; sum of Virtues = 9.
    c.virtues = {VirtueName.COMPASSION: 2, VirtueName.CONVICTION: 3,
                 VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 2}
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _codes(issues, code):
    return [i for i in issues if i.code == code]


# --------------------------------------------------------------------------- #
# The budget row (pp.47-50)
# --------------------------------------------------------------------------- #

def test_the_godblooded_budget_is_the_printed_one(rs):
    b = rs.budgets_for("God-Blooded", "", "")
    assert b.attribute_pools == (6, 4, 3)
    assert b.ability_dots == 22
    assert b.ability_min_caste_favored == 1
    assert b.ability_cap_pre_bp == 3
    assert b.favored_count == 1
    assert b.background_dots == 6
    assert b.background_cap_pre_bp == 3
    assert b.charm_count == 0
    assert b.virtue_dots == 5
    assert b.essence_start == 1
    assert b.essence_start_cap == 3
    assert b.bonus_points == 21
    assert b.inheritance_bonus_points == [0, 6, 12, 18, 24, 30]
    assert b.inheritance_flaw_cap == [0, 10, 15, 15, 20, 20]


def test_heritage_is_the_caste_axis(rs):
    """Human ruling 2026-08-02: the five heritages are the Godblooded CASTE slot, not
    an origin. `caste_noun: "Heritage"` and a heritage_traits block on the caste."""
    assert rs.exalt_for("God-Blooded").caste_noun == "Heritage"
    h = rs.castes["ghost-blooded"].heritage_traits
    assert h.charm_access == ["Ghost"]
    assert h.magic_track == "necromancy"
    # the Ghost-Blooded pool (p.66): personal coeffs only, one merged pool.
    assert h.unlocked_essence.personal_essence_coeff == 5
    assert h.unlocked_essence.personal_willpower_coeff == 2
    assert h.unlocked_essence.personal_virtue_mode == "all"
    assert rs.exalt_for("God-Blooded").single_essence_pool is True


def test_godblooded_has_no_combos_ever(rs):
    c = _gb()
    c.combos = [Combo(name="Twin Fang", charm_ids=[])]
    assert any(i.code == "combo-splat-barred"
               for i in validate.combo_issues(rs, c, c.combos[0]))


# --------------------------------------------------------------------------- #
# Inheritance (p.61): a Background that resizes the BP pool and Flaw cap
# --------------------------------------------------------------------------- #

def test_inheritance_rating_adds_to_the_bonus_pool(rs):
    assert validate.bonus_point_breakdown(rs, _gb()).available == 21
    thin = _gb(backgrounds=[BackgroundEntry(name="Inheritance", rating=1)])
    assert validate.bonus_point_breakdown(rs, thin).available == 21 + 6
    notable = _gb(backgrounds=[BackgroundEntry(name="Inheritance", rating=3)])
    assert validate.bonus_point_breakdown(rs, notable).available == 21 + 18
    divine = _gb(backgrounds=[BackgroundEntry(name="Inheritance", rating=5)])
    assert validate.bonus_point_breakdown(rs, divine).available == 21 + 30


def test_inheritance_is_assigned_not_bought_and_required(rs):
    """p.61: the ST assigns a consistent rating; it costs nothing from the 6-dot
    pool (free_rating 5), and by ruling a God-Blooded must take at least one dot."""
    rule = rs.budgets_for("God-Blooded", "", "").background_rules["inheritance"]
    assert rule.min_rating == 1 and rule.free_rating == 5 and rule.max_rating == 5
    assert validate.validate_chargen(rs, _gb())  # no Inheritance -> an issue


def test_inheritance_raises_the_flaw_cap(rs):
    """The Flaw cap is 10 normally, 15/15/20/20 at Inheritance 2-5 (p.61). With 13
    points of Flaws the cap is what bites, so the grant must be 10 at rating 1 and
    the full 13 at rating 3."""
    flaws = [MP(merit_id=d.id, points=d.cost)
             for d in rs.merits_flaws.values()
             if d.kind == "flaw" and d.cost][:5]
    assert sum(p.points for p in flaws) >= 13
    low = _gb(backgrounds=[BackgroundEntry(name="Inheritance", rating=1)],
              merits_flaws=flaws)
    assert merits.merits_and_flaws_calc(rs, low).bonus_point_grant == 10
    high = _gb(backgrounds=[BackgroundEntry(name="Inheritance", rating=3)],
               merits_flaws=flaws)
    assert merits.merits_and_flaws_calc(rs, high).bonus_point_grant == 13


# --------------------------------------------------------------------------- #
# Inheritance as an ST option (p.61: "the Storyteller assigns a consistent rating")
# --------------------------------------------------------------------------- #

def test_st_inheritance_rating_sets_the_free_dots_not_the_pool(rs):
    """Human ruling 2026-08-02: the ST option is how many Inheritance dots are FREE,
    never the rating itself. The bonus points follow the character's SHEET background —
    a character at Inheritance 4 gets the +24 for THAT rating whether or not the ST
    grants four; the ST option only decides whether the dots cost anything."""
    granted = _gb(backgrounds=[BackgroundEntry(name="Inheritance", rating=4)])
    granted.house_rules = HouseRules(godblooded_inheritance_rating=4)
    assert validate.bonus_point_breakdown(rs, granted).available == 21 + 24   # sheet 4
    capped = _gb(backgrounds=[BackgroundEntry(name="Inheritance", rating=4)])
    capped.house_rules = HouseRules(godblooded_inheritance_rating=1)
    assert validate.bonus_point_breakdown(rs, capped).available == 21 + 24    # ST doesn't cut the pool


def test_st_inheritance_rating_waives_the_above_cap_bp(rs):
    """The complaint this fixes: Inheritance 4 with the ST option at 4 still charged two
    bonus points for the fourth dot (above the pre-BP cap of 3). The free grant must
    waive the above-cap BP too — the dot that sits above the cap is still within the
    free dots."""
    four = _gb(backgrounds=[BackgroundEntry(name="Inheritance", rating=4)])
    four.house_rules = HouseRules(godblooded_inheritance_rating=4)
    # four free dots: nothing from the pool, nothing above cap -> no BP for Inheritance
    _within, above = validate.background_pool_spend(
        rs, four, rs.budgets_for("God-Blooded", "", ""), four.backgrounds)
    assert above == [] and _within == 0
    # the same Inheritance with the ST at 2: dots 1-2 free, 3 from the pool, 4 above-cap
    two = _gb(backgrounds=[BackgroundEntry(name="Inheritance", rating=4)])
    two.house_rules = HouseRules(godblooded_inheritance_rating=2)
    _w, a = validate.background_pool_spend(
        rs, two, rs.budgets_for("God-Blooded", "", ""), two.backgrounds)
    assert a == [2] and _w == 1   # the 4th dot costs the two-point above-cap rate


def test_st_inheritance_rating_unset_uses_the_character_dots(rs):
    """The default (None) keeps per-character behaviour: the character's own
    Inheritance dots drive the pool. Old saves load with house_rules None."""
    c = _gb(backgrounds=[BackgroundEntry(name="Inheritance", rating=3)])
    assert validate.bonus_point_breakdown(rs, c).available == 21 + 18


def test_st_inheritance_rating_must_be_one_to_five(rs):
    HouseRules(godblooded_inheritance_rating=None)   # per-character, the default
    HouseRules(godblooded_inheritance_rating=1)
    HouseRules(godblooded_inheritance_rating=5)
    for bad in (0, 6):
        with pytest.raises(ValidationError):
            HouseRules(godblooded_inheritance_rating=bad)


def test_st_inheritance_rating_freezes_into_the_snapshot(rs):
    """An accounting toggle like the rest: frozen at lock, or flipping it post-lock
    would re-price a locked chargen's bonus points."""
    c = _gb(backgrounds=[BackgroundEntry(name="Inheritance", rating=1)])
    c.house_rules = HouseRules(godblooded_inheritance_rating=4)
    lifecycle.lock_chargen(c, rs)
    assert c.chargen_snapshot.house_rules.godblooded_inheritance_rating == 4


# --------------------------------------------------------------------------- #
# Essence: no pool without Awakened Essence; the heritage formula once unlocked
# --------------------------------------------------------------------------- #

def test_no_pool_without_awakened_essence(rs):
    assert derive.essence_pools(rs, _gb()) == (0, 0)


def test_awakened_essence_unlocks_the_heritage_pool(rs):
    c = _gb(merits_flaws=[MP(merit_id=AWAKENED)])
    # Ghost-Blooded (p.66): (Essence x 5) + (Willpower x 2) + (sum of Virtues).
    # 1x5 + 5x2 + 9 = 24. One merged pool -> (0, 24).
    assert derive.essence_pools(rs, c) == (0, 24)


def test_awakened_essence_raises_the_essence_cap_to_three(rs):
    """Essence 2 requires the Merit (p.48); without it the cap 1 holds, with it the
    chargen cap is 3 and the life cap is 3."""
    over = _gb(essence_rating=2)
    assert _codes(validate.validate_chargen(rs, over), "magic-requires-awakened-essence")
    ok = _gb(merits_flaws=[MP(merit_id=AWAKENED)], essence_rating=3)
    assert not _codes(validate.validate_chargen(rs, ok), "magic-requires-awakened-essence")
    assert not _codes(validate.validate_chargen(rs, ok), "essence-above-chargen-cap")


# --------------------------------------------------------------------------- #
# Charm access — the load-bearing tests
# --------------------------------------------------------------------------- #

def test_a_ghost_blooded_learns_arcanoi(rs):
    c = _gb(merits_flaws=[MP(merit_id=AWAKENED)])
    assert validate.charm_matches_splat(c, rs.charms[ARCANOS], rs)
    assert validate.charm_learnable_by_splat(rs, c, rs.charms[ARCANOS])


def test_a_ghost_blooded_cannot_learn_another_splats_charms(rs):
    c = _gb(merits_flaws=[MP(merit_id=AWAKENED)])
    assert not validate.charm_matches_splat(c, rs.charms[FOREIGN], rs)
    assert not validate.charm_learnable_by_splat(rs, c, rs.charms[FOREIGN])


def test_terrestrial_martial_arts_yes_celestial_no(rs):
    """p.47 / p.234: God-Blooded may learn only Terrestrial styles."""
    c = _gb(merits_flaws=[MP(merit_id=AWAKENED)])
    assert validate.charm_matches_splat(c, rs.charms[FIVE_DRAGON], rs)
    assert not validate.charm_matches_splat(c, rs.charms[HUNGRY_GHOST], rs)


def test_the_st_foreign_charms_house_rule_does_not_open_other_splats(rs):
    """The generalist privilege is a second route to another splat's Charms, and a
    bar enforced on only one of two routes is this build's most-repeated bug. The
    heritage bar must be restated in charm_learnable_by_splat, so even the house
    rule cannot walk it past."""
    c = _gb(merits_flaws=[MP(merit_id=AWAKENED)])
    c.house_rules = HouseRules(st_foreign_charms=True)
    assert not validate.charm_learnable_by_splat(rs, c, rs.charms[FOREIGN])


def test_the_buy_path_learns_an_arcanos(rs):
    c = _gb(merits_flaws=[MP(merit_id=AWAKENED)])
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    advancement.learn_charm(rs, c, ARCANOS)
    assert ARCANOS in c.charms


def test_the_buy_path_refuses_a_charm_without_awakened_essence(rs):
    """p.49: only God-Blooded with the Awakened Essence Merit may purchase magical
    Traits. The Merit is the gate on the BUY path, not just the picker."""
    c = _gb()
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError, match="Awakened Essence"):
        advancement.learn_charm(rs, c, ARCANOS)


def test_chargen_flags_magic_without_awakened_essence(rs):
    c = _gb(merits_flaws=[MP(merit_id=AWAKENED)])
    c.charms = [ARCANOS]
    c.spells = []
    c.essence_rating = 3
    stripped = c.model_copy(update={"merits_flaws": []})
    assert _codes(validate.validate_chargen(rs, stripped), "magic-requires-awakened-essence")
    assert not _codes(validate.validate_chargen(rs, c), "magic-requires-awakened-essence")


# --------------------------------------------------------------------------- #
# The Death-in-Life Path Arcanoi (pp.84-85)
# --------------------------------------------------------------------------- #

def test_death_in_life_prerequisite_chain(rs):
    c = _gb(merits_flaws=[MP(merit_id=AWAKENED)], essence_rating=3)
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 500)
    trans = "godblooded.death-in-life.transubstantiation-of-flesh"
    lower = "godblooded.death-in-life.lower-soul-ascendant"
    wraith = "godblooded.death-in-life.wraith-form-transformation"
    sojourn = "godblooded.death-in-life.restless-spirit-sojourn"
    # Nothing is known yet, so every dependent Arcanos is refused.
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, lower)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, wraith)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, sojourn)
    # Transubstantiation unlocks the lower half; Wraith Form unlocks the other branch.
    advancement.learn_charm(rs, c, trans)
    advancement.learn_charm(rs, c, wraith)
    advancement.learn_charm(rs, c, lower)
    advancement.learn_charm(rs, c, sojourn)


# --------------------------------------------------------------------------- #
# The cost tables (p.49-50)
# --------------------------------------------------------------------------- #

def test_the_bonus_point_table_is_the_printed_one(rs):
    bp = rs.bonus_costs_for("God-Blooded")
    assert bp.attribute == 4
    assert bp.ability == 2
    assert bp.ability_favored_caste == 1
    assert bp.background == 1
    assert bp.virtue == 3
    assert bp.willpower == 2
    assert bp.essence_by_rating == {2: 5, 3: 15}
    assert bp.charm == 7
    assert bp.charm_favored_caste == 7
    assert bp.magic_charm == 10


def test_the_experience_table_is_the_printed_one(rs):
    xp = rs.xp_costs_for("God-Blooded")
    assert xp.attribute.coeff == 4
    assert xp.ability.coeff == 2
    assert xp.virtue.coeff == 3
    assert xp.willpower.coeff == 2
    assert xp.essence.coeff == 12
    assert xp.new_charm == 15
    assert xp.new_charm_favored_caste == 15
    assert xp.new_magic_charm == 25
    assert xp.new_martial_arts_charm == 15


def test_essence_bp_is_flat_by_destination(rs):
    c = _gb(essence_rating=3)
    lines = [l.points for l in validate.bonus_point_breakdown(rs, c).lines
             if l.domain == "Essence"]
    assert lines == [15]


def test_magic_initiation_charms_cost_10_bp_and_25_xp(rs):
    c = _gb(merits_flaws=[MP(merit_id=AWAKENED)], essence_rating=3)
    init = rs.charms[INITIATION]
    assert costs.charm_cost(rs, c, init) == 25
    assert costs.charm_cost(rs, c, rs.charms[ARCANOS]) == 15
    # BP: the initiation Charm prices at magic_charm 10; an ordinary Arcanos at 7.
    c.charms = [INITIATION]
    assert validate.charm_pick_bp_costs(rs, c, validate.charm_picks(rs, c)) == [10]
    c2 = _gb(merits_flaws=[MP(merit_id=AWAKENED)])
    c2.charms = [ARCANOS]
    assert validate.charm_pick_bp_costs(rs, c2, validate.charm_picks(rs, c2)) == [7]


def test_a_ghost_blooded_reaches_shadowlands_necromancy(rs):
    """p.48: Ghost-Blooded learn Shadowlands Circle Necromancy (NOT Terrestrial
    Sorcery), and the initiation is a real Charm they buy at the magic rate. The
    greater circles stay out of reach via the Essence 3 cap."""
    init = "godblooded.general-arcanoi.shadowlands-circle-necromancy"
    c = _gb(merits_flaws=[MP(merit_id=AWAKENED)], essence_rating=3,
            abilities={AbilityName.OCCULT: 5})
    # Their own copy of the initiation is natively reachable; the Solar sorcery one is
    # another splat's Charm and stays locked.
    assert validate.charm_matches_splat(c, rs.charms[init], rs)
    assert not validate.charm_matches_splat(c, rs.charms[INITIATION], rs)
    # Holding it opens the Shadowlands circle, and a spell of that circle is learnable.
    c.charms = [init]
    assert SpellCircle.SHADOWLANDS in validate.granted_circles(rs, c)
    sid = next(s.id for s in rs.spells.values()
               if s.circle == SpellCircle.SHADOWLANDS)
    assert validate.meets_spell_requirements(rs, c, rs.spells[sid], chargen=True)
    # Priced at the magic rate.
    assert costs.charm_cost(rs, c, rs.charms[init]) == 25
    assert validate.charm_pick_bp_costs(rs, c, validate.charm_picks(rs, c)) == [10]
    # The Occult 5 gate (p.48) is the extra_min_abilities; a Ghost-Blooded with
    # Occult 2 is refused on the buy path.
    low = _gb(merits_flaws=[MP(merit_id=AWAKENED)], essence_rating=3,
              abilities={AbilityName.OCCULT: 2})
    lifecycle.lock_chargen(low, rs)
    advancement.add_xp(low, 500)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, low, init)


# --------------------------------------------------------------------------- #
# Ox-Body (p.83): two -2 levels, capped by Conviction
# --------------------------------------------------------------------------- #

def test_ox_body_is_two_minus_two_levels_capped_by_conviction(rs):
    ox = rs.exalt_for("God-Blooded").ox_body_charm_id
    assert ox == "godblooded.general-arcanoi.ox-body-technique"
    c = _gb(merits_flaws=[MP(merit_id=AWAKENED)], essence_rating=2)
    # Conviction 3 -> at most 3 purchases.
    assert validate._repeatable_purchase_cap(rs.charms[ox], c) == 3
    c.ox_body = [OxBodyPurchase(variant="two-minus-two", health_levels=[-2, -2])]
    hl = derive.health_track(c)
    assert sum(1 for lv in hl if lv.penalty == -2) == 4   # base two + the purchase's two


# --------------------------------------------------------------------------- #
# Half-Caste (Phase B): the parent-Exalt axis
# --------------------------------------------------------------------------- #

def _hc(parent: str, **kw) -> Character:
    c = Character(id="hc", name="Golden Child", exalt_type="God-Blooded",
                  caste="half-caste", origin=parent, essence_rating=2)
    c.virtues = {VirtueName.COMPASSION: 2, VirtueName.CONVICTION: 3,
                 VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 2}
    c.merits_flaws = [MP(merit_id=AWAKENED)]
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_half_caste_heritage_is_parent_keyed(rs):
    h = rs.castes["half-caste"].heritage_traits
    assert h.charm_access_parent is True
    assert h.attribute_pools == (6, 5, 4)              # prose p.47; the p.50 6/5/3 is a typo
    assert h.gift_charm_ids == {"Lunar": "lunar.shapeshifting.deadly-beastman-transformation"}
    assert h.gift_caps == {"Lunar": 2}
    assert "solar.melee.heavenly-guardian-defense" in h.barred_charm_ids


def test_the_half_caste_bar_list_is_human_ruled(rs):
    """p.47 makes the ST the final arbiter of the no-perfect/persistent bar, and the
    human ruled it 2026-08-02 (review brief #2): the 8 God-Blooded Arcanoi, the 7
    Maiden-approval charms, the 16 clearly-perfect/persistent defenses, plus the three
    borderline calls (Snake Head Defense, Smoke Obscuring Effect, Blade of the Battle
    Maiden) stay; the retaliation/conduit/terrain/mote charms go. Pinning the ruling so
    the list cannot silently drift."""
    bar = set(rs.castes["half-caste"].heritage_traits.barred_charm_ids)
    assert len(bar) == 34
    # the five charms the human cut (not perfect or scene-length defenses)
    assert not {"lunar.unarmed-combat.cunning-porcupine-defense",
                "sidereal.dodge.trouble-reduction-strategy",
                "sidereal.dodge.neighborhood-relocation-scheme",
                "sidereal.melee.perfection-of-the-visionary-warrior",
                "sidereal.violet-bier-of-sorrows.joy-in-adversity-stance"} & bar
    # the three borderline calls the human KEPT
    assert {"lunar.unarmed-combat.snake-head-defense",
            "dragonblooded.dodge.smoke-obscuring-effect",
            "sidereal.violet-bier-of-sorrows.blade-of-the-battle-maiden"} <= bar
    # all seven Maiden-approval charms stay barred (p.47 rule #3)
    assert {"sidereal.bureaucracy.terminal-sanction",
            "sidereal.bureaucracy.underling-invisibility-practice",
            "sidereal.craft.elemental-vision",
            "sidereal.occult.mark-of-exaltation",
            "sidereal.occult.incite-decorum",
            "sidereal.occult.innocuous-maneuver",
            "sidereal.stealth.walking-outside-fate"} <= bar


def test_a_half_caste_learns_only_their_parents_charms(rs):
    sol = _hc("Solar")
    assert validate.heritage_charm_access(rs, sol) == frozenset({"Solar"})
    assert validate.charm_matches_splat(sol, rs.charms["solar.melee.fire-and-stones-strike"], rs)
    assert not validate.charm_matches_splat(
        sol, rs.charms["lunar.shapeshifting.finding-the-spirits-shape"], rs)
    assert not validate.charm_matches_splat(
        sol, rs.charms["abyssal.melee.incomparable-sentinel-stance"], rs)
    lun = _hc("Lunar")
    assert validate.heritage_charm_access(rs, lun) == frozenset({"Lunar"})
    assert validate.charm_matches_splat(
        lun, rs.charms["lunar.shapeshifting.finding-the-spirits-shape"], rs)


def test_a_half_caste_uses_their_parents_ox_body_and_not_the_godblooded_arcanoi(rs):
    """A Half-Caste learns their PARENT's Charms, so the God-Blooded's own Arcanoi
    (the spirit/ghost Ox-Body, the necromancy initiation, the Death-in-Life path) are
    barred — which is also what keeps the Arcanoi tab off their picker. Their Ox-Body
    is the parent's."""
    sol = _hc("Solar")
    assert validate.ox_body_charm_id(rs, sol) == "solar.endurance.ox-body-technique"
    assert not validate.charm_matches_splat(
        sol, rs.charms["godblooded.general-arcanoi.ox-body-technique"], rs)
    assert not validate.charm_matches_splat(
        sol, rs.charms["godblooded.general-arcanoi.shadowlands-circle-necromancy"], rs)
    assert not validate.charm_matches_splat(
        sol, rs.charms["godblooded.death-in-life.transubstantiation-of-flesh"], rs)
    # the ghost-blooded heritage keeps all of them
    gb = _gb(merits_flaws=[MP(merit_id=AWAKENED)])
    assert validate.ox_body_charm_id(rs, gb) == "godblooded.general-arcanoi.ox-body-technique"
    assert validate.charm_matches_splat(
        gb, rs.charms["godblooded.general-arcanoi.shadowlands-circle-necromancy"], rs)


def test_a_solar_half_caste_reaches_terrestrial_sorcery_but_not_celestial(rs):
    c = _hc("Solar", essence_rating=3, abilities={AbilityName.OCCULT: 3})
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 300)
    advancement.learn_charm(rs, c, "solar.occult.terrestrial-circle-sorcery")
    # The greater circles need Essence 4+ and a Half-Caste caps at 3 (p.48).
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, "solar.occult.celestial-circle-sorcery")


def test_half_caste_are_barred_from_perfect_and_persistent_defenses(rs):
    """p.47: "may not master any Charms that provide a perfect defense or persistent
    scene-length defense." The bar is heritage-level and bites on the buy path even
    for a Charm that IS the parent's catalogue."""
    c = _hc("Solar", essence_rating=2)
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 300)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, "solar.melee.heavenly-guardian-defense")
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, "solar.melee.fivefold-bulwark-stance")


def test_a_sidereal_half_caste_is_barred_from_maiden_approval_charms(rs):
    c = _hc("Sidereal", essence_rating=2)
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 300)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, "sidereal.occult.mark-of-exaltation")


def test_a_lunar_half_caste_may_take_two_forms(rs):
    lun = _hc("Lunar")
    assert validate.gift_charm_id(rs, lun) == "lunar.shapeshifting.deadly-beastman-transformation"
    assert validate.gift_purchase_cap(rs, lun) == 2          # p.47, not the Essence cap
    sol = _hc("Solar")
    assert validate.gift_charm_id(rs, sol) == ""             # no gift economy for a Solar parent


def test_half_caste_attribute_pools_are_six_five_four(rs):
    assert validate.effective_attribute_pools(rs, _hc("Solar")) == (6, 5, 4)
    # a Ghost-Blooded keeps the 6/4/3 base — the override is heritage-specific.
    assert validate.effective_attribute_pools(rs, _gb()) == (6, 4, 3)


def test_half_caste_pool_is_essence_five_plus_virtues(rs):
    c = _hc("Solar")
    # (Essence x 5) + (sum of Virtues), no Willpower term (p.66): 2x5 + 9 = 19.
    assert derive.essence_pools(rs, c) == (0, 19)


def test_a_half_caste_must_choose_a_parent(rs):
    empty = _hc("")
    assert _codes(validate.validate_chargen(rs, empty), "heritage-requires-origin")


# --------------------------------------------------------------------------- #
# The pages build (NiceGUI render matrix — routes in tests/_ui_main.py)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_builds_for_a_ghost_blooded(user) -> None:
    await user.open('/godblooded-editor')
    await user.should_see("Sighing Willow")
    await user.should_see("Ghost-Blooded")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_sheet_builds_for_a_ghost_blooded(user) -> None:
    await user.open('/godblooded-sheet')
    await user.should_see("Sighing Willow")
    # A merged pool names itself rather than showing "Personal 0".
    await user.should_see("Single pool")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_advantages_tab_builds_for_a_ghost_blooded(user) -> None:
    await user.open('/godblooded-advantages')
    await user.should_see("Inheritance")
    await user.should_see("Awakened Essence")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_picker_builds_for_a_ghost_blooded(user) -> None:
    # The picker must BUILD for a heritage with no ability-castes and no native
    # Charms (its Arcanoi come from the borrowed Ghost catalogue) — the ui.select
    # crash class that blanked two tabs for the mortal splat.
    await user.open('/godblooded-picker')
    await user.should_see("Charm Details")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_builds_for_a_half_caste(user) -> None:
    await user.open('/godblooded-halfcaste-editor')
    await user.should_see("Golden Child")
    await user.should_see("Half-Caste")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_picker_builds_for_a_half_caste(user) -> None:
    # A Half-Caste's Charm page shows their parent's catalogue — the picker must
    # build with a cross-splat access rule and the parent origin.
    await user.open('/godblooded-halfcaste-picker')
    await user.should_see("Charm Details")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_builds_for_a_fae_blooded(user) -> None:
    # The Fae-Blooded rides the origin axis (Noble/Commoner) and holds glamour
    # Merits rather than Charms — the editor must build with no charm access.
    await user.open('/godblooded-fae-editor')
    await user.should_see("Sidhe-Spun")
    await user.should_see("Fae-Blooded")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_picker_builds_for_a_fae_blooded(user) -> None:
    # A Fae-Blooded's picker must BUILD despite no charm access at all (not even a
    # borrowed catalogue) — the same blank-tab class as the Charmless mortal.
    await user.open('/godblooded-fae-picker')
    await user.should_see("Charm Details")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_advantages_tab_builds_for_a_fae_blooded(user) -> None:
    await user.open('/godblooded-fae-advantages')
    await user.should_see("Wyld Sense")
    await user.should_see("Virtue Attunement")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_sheet_builds_for_a_fae_blooded(user) -> None:
    await user.open('/godblooded-fae-sheet')
    await user.should_see("Sidhe-Spun")
    await user.should_see("Single pool")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_advantages_tab_builds_for_a_commoner_with_two_attunements(user) -> None:
    # A Commoner holding two Virtue Attunements is illegal (p.74); the tab must render
    # the refusal, not crash on the row (the reported "immediate error").
    await user.open('/godblooded-fae-commoner-2x-advantages')
    await user.should_see("Virtue Attunement")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_builds_for_a_fae_blooded_with_a_stale_origin(user) -> None:
    # Review Fix 1: a Fae-Blooded saved with another heritage's origin ("Solar") must
    # render — the Origin select folds the stale value in rather than raising
    # ValueError on a value that is not among Noble/Commoner.
    await user.open('/godblooded-fae-stale-origin-editor')
    await user.should_see("Mis-Saved Changeling")
    await user.should_see("Origin")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_builds_for_a_fae_blooded_with_a_blank_origin(user) -> None:
    await user.open('/godblooded-fae-no-origin-editor')
    await user.should_see("Originless Changeling")
    await user.should_see("Origin")


# --------------------------------------------------------------------------- #
# The summoning bar (p.48)
# --------------------------------------------------------------------------- #
# "No God-Blood can learn spells to summon and bind elementals or demons, as the
# workings of these spells are designed to operate in conjunction with certain
# privileges of the Exalted." Circle access cannot express this — the barred spells
# sit inside Circles a God-Blood legitimately holds — so it is a spell-id bar on the
# ExaltDefinition, checked on BOTH routes to the permission.

SUMMON_DEMON = "spell.terrestrial.demon-of-the-first-circle"
SUMMON_ELEMENTAL = "spell.terrestrial.summon-elemental"
SUMMON_GHOST = "spell.shadowlands.summon-ghost"


def _sorcerous_half_caste(rs) -> Character:
    """A Solar Half-Caste who HAS the Terrestrial initiation — so Circle access is
    satisfied and only the summoning bar can stop the spell."""
    c = _gb(caste="half-caste", origin="Solar", essence_rating=3)
    c.charms = [INITIATION]
    assert SpellCircle.TERRESTRIAL in validate.granted_circles(rs, c)
    return c


def test_a_godblooded_may_never_learn_summoning_spells(rs):
    c = _sorcerous_half_caste(rs)
    for sid in (SUMMON_DEMON, SUMMON_ELEMENTAL):
        spell = rs.spells[sid]
        assert not validate.meets_spell_requirements(rs, c, spell, chargen=True)
        assert not validate.meets_spell_requirements(rs, c, spell, chargen=False)


def test_the_summoning_bar_is_enforced_on_the_buy_path_too(rs):
    # The picker route and the XP route are two ways to the same permission; a bar
    # on only one of them is this build's most-repeated bug.
    c = _sorcerous_half_caste(rs)
    c.merits_flaws = [MP(merit_id=AWAKENED)]     # past the pool gate, so only the bar bites
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_spell(rs, c, SUMMON_DEMON)


def test_a_hand_edited_summoning_spell_is_reported(rs):
    c = _sorcerous_half_caste(rs)
    c.spells = [SUMMON_DEMON]
    assert _codes(validate.check_spell_access(rs, c), "spell-barred")


def test_summon_ghost_is_not_barred(rs):
    # The bar names elementals and demons ONLY. Summon Ghost is a Shadowlands spell
    # the Ghost-Blooded necromancy path is entitled to, and must survive the bar.
    assert SUMMON_GHOST not in rs.exalt_for("God-Blooded").barred_spell_ids


def test_no_other_splat_has_a_spell_bar(rs):
    for eid, ex in rs.exalts.items():
        assert bool(ex.barred_spell_ids) is (eid == "God-Blooded"), eid


# --------------------------------------------------------------------------- #
# The magic track (p.48)
# --------------------------------------------------------------------------- #
# "Terrestrial Circle Sorcery is available to all the remaining heritages save
# Ghost-Blooded and Abyssal Half-Caste. Conversely, only these heritages may learn
# Shadowlands Circle Necromancy."
#
# Charm ACCESS alone does not express this. A Ghost-Blooded lands on necromancy by
# accident — the Ghost catalogue holds no sorcery — but an Abyssal Half-Caste borrows
# a catalogue holding BOTH, and a Solar Half-Caste's holds Shadowlands Necromancy.
# Those two were live violations until the track bar was wired.

def _reachable_circles(rs, caste, origin=""):
    """The circles a heritage can actually be initiated into at its Essence cap of 3.
    Greater circles need Essence 4+ and are barred by the cap, not by the track."""
    c = _gb(caste=caste, origin=origin, essence_rating=3)
    return {ch.grants_circle for ch in rs.charms.values()
            if ch.grants_circle and ch.min_essence <= 3
            and validate.charm_learnable_by_splat(rs, c, ch)}


def test_ghost_blooded_get_necromancy_and_never_sorcery(rs):
    assert _reachable_circles(rs, "ghost-blooded") == {SpellCircle.SHADOWLANDS}


def test_only_the_abyssal_half_caste_gets_necromancy(rs):
    """The parent decides the track, not the heritage — so this is keyed per parent."""
    assert _reachable_circles(rs, "half-caste", "Abyssal") == {SpellCircle.SHADOWLANDS}
    for parent in ("Solar", "Dragon-Blooded", "Lunar", "Sidereal"):
        assert _reachable_circles(rs, "half-caste", parent) == {SpellCircle.TERRESTRIAL}, parent


def test_the_track_bar_is_enforced_on_the_buy_path_too(rs):
    c = _gb(caste="half-caste", origin="Abyssal", essence_rating=3,
            merits_flaws=[MP(merit_id=AWAKENED)])
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, "abyssal.occult.terrestrial-circle-sorcery")


def test_the_track_bar_only_touches_initiation_charms(rs):
    """It restricts which magic a heritage may UNLOCK, never ordinary Charms."""
    c = _gb(caste="half-caste", origin="Abyssal")
    ordinary = rs.charms["abyssal.melee.incomparable-sentinel-stance"]
    assert not validate.heritage_bars_initiation(rs, c, ordinary)


def test_a_heritage_without_a_track_bars_nothing(rs):
    c = _gb(caste="half-caste", origin="")
    assert validate.heritage_magic_track(rs, c) == ""
    for ch in rs.charms.values():
        if ch.grants_circle:
            assert not validate.heritage_bars_initiation(rs, c, ch)


# --------------------------------------------------------------------------- #
# Fae-Blooded (Phase D): glamour Merits, Ess x 8 pool, no Charms, no spells
# --------------------------------------------------------------------------- #
# PG p.47 "The children of the Fair Folk do not use Charms, but instead, wield gifts
# of glamour"; p.48 "All God-Blooded with the Awakened Essence Merit apart from
# Fae-Blooded may also learn to cast spells"; p.66 pool = (Essence x 8); the
# Noble/Commoner origin axis (human 2026-08-02) gates the powers on pp.73-79.

def _fb(origin="Noble", **kw) -> Character:
    c = Character(id="fb", name="Sidhe-Spun", exalt_type="God-Blooded",
                  caste="fae-blooded", origin=origin, essence_rating=2)
    c.virtues = {VirtueName.COMPASSION: 2, VirtueName.CONVICTION: 3,
                 VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 2}
    c.merits_flaws = [MP(merit_id=AWAKENED)]
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_the_fae_blooded_heritage_row(rs):
    h = rs.castes["fae-blooded"].heritage_traits
    assert h.origin_options == ["Noble", "Commoner"]
    assert h.magic_track == "none"            # the third state: no spell initiation
    assert h.charm_access == []               # glamour, not Charms
    assert h.unlocked_essence.personal_essence_coeff == 8   # (Essence x 8), p.66
    assert h.unlocked_essence.personal_willpower_coeff == 0
    # "no Charms" is a FLAG, not the deny-list of the God-Blooded's own Arcanoi — a
    # ninth Arcanos, authored for God/Demon-Blooded later, must be closed the day it
    # lands rather than need its id added here.
    assert h.charms_available is False
    assert h.barred_charm_ids == []


def test_fae_blooded_pool_is_essence_times_eight(rs):
    """(Essence x 8), no Willpower or Virtue term: 2 x 8 = 16."""
    c = _fb()
    assert derive.essence_pools(rs, c) == (0, 16)


def test_fae_blooded_has_no_charm_access(rs):
    c = _fb()
    # no borrowed catalogue, and the God-Blooded's own Arcanoi are heritage-barred
    assert validate.heritage_charm_access(rs, c) == frozenset()
    assert not validate.charm_matches_splat(c, rs.charms["ghost.savage-ghost-tamer.taste-the-demon-wind"], rs)
    assert not validate.charm_matches_splat(c, rs.charms[ARCANOS], rs)
    # ...but the p.234 Terrestrial martial arts still open (same as a ghost)
    assert validate.charm_matches_splat(c, rs.charms[FIVE_DRAGON], rs)


def test_a_fae_blooded_cannot_hold_a_charm_authored_for_a_later_heritage(rs):
    """Review note: the Fae-Blooded's no-Charms is a FLAG (charms_available False), not
    the eight-Arcanoi deny-list — so a God-Blooded Charm authored for God/Demon-Blooded
    later (their spirit Charms) is closed for a Fae-Blooded the day it lands, with no
    list to update."""
    c = _fb()
    base = rs.charms["godblooded.death-in-life.transubstantiation-of-flesh"]
    new = base.model_copy(update={"id": "godblooded.death-in-life.never-before-seen"})
    assert new.id not in rs.castes["fae-blooded"].heritage_traits.barred_charm_ids
    assert not validate.charm_matches_splat(c, new, rs)
    assert not validate.charm_learnable_by_splat(rs, c, new)


def test_a_fae_blooded_holding_a_godblooded_arcanos_is_barred_not_wrong_splat(rs):
    """Review: a Fae-Blooded holding a God-Blooded Arcanos IS God-Blooded — the
    refusal is a heritage bar (p.47 "do not use Charms"), not a splat mismatch. So
    neither the validation issue nor the buy-path error may claim "another Exalt type"
    for a character who is exactly that type."""
    c = _fb()
    c.charms = ["godblooded.death-in-life.transubstantiation-of-flesh"]
    wrong = [i for i in validate.check_splat_consistency(rs, c)
             if i.code == "charm-wrong-splat"]
    assert wrong and "barred for this character" in wrong[0].message
    assert "not the character's Exalt type" not in wrong[0].message
    # the buy path (a character who does NOT already hold it) says the same thing
    buyer = _fb()
    lifecycle.lock_chargen(buyer, rs)
    advancement.add_xp(buyer, 200)
    with pytest.raises(advancement.AdvancementError) as exc:
        advancement.learn_charm(rs, buyer, "godblooded.death-in-life.transubstantiation-of-flesh")
    assert "barred for this character" in str(exc.value)
    assert "another Exalt type" not in str(exc.value)


def test_fae_blooded_cannot_initiate_into_any_spell_circle(rs):
    """The Phase C trap, now a rule: magic_track "" would mean NO restriction, which is
    the opposite of a Fae-Blooded — so "none" bars every initiation in BOTH gates
    (p.48: "All God-Blooded with the Awakened Essence Merit apart from Fae-Blooded may
    also learn to cast spells")."""
    c = _fb()
    sorc = rs.charms[INITIATION]                                  # Terrestrial Sorcery
    necro = rs.charms["godblooded.general-arcanoi.shadowlands-circle-necromancy"]
    assert validate.heritage_magic_track(rs, c) == "none"
    assert not validate.charm_matches_splat(c, sorc, rs)
    assert not validate.charm_matches_splat(c, necro, rs)
    assert not validate.charm_learnable_by_splat(rs, c, sorc)
    assert not validate.charm_learnable_by_splat(rs, c, necro)
    # the buy path refuses too
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 300)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, sorc.id)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, necro.id)


def test_the_glamour_merits_are_fae_blooded_only(rs):
    wyld_sense = rs.merits_flaws["mf.fae-wyld-sense"]
    assert validate.merit_available_to(wyld_sense, "God-Blooded", "fae-blooded")
    assert not validate.merit_available_to(wyld_sense, "God-Blooded", "ghost-blooded")
    assert not validate.merit_available_to(wyld_sense, "Solar", "dawn")


def test_fae_prince_of_chaos_requires_a_noble_origin(rs):
    m = rs.merits_flaws["mf.fae-prince-of-chaos"]
    assert validate.merit_available_to(m, "God-Blooded", "fae-blooded", origin="Noble")
    assert not validate.merit_available_to(m, "God-Blooded", "fae-blooded", origin="Commoner")
    c = _fb(origin="Commoner")
    c.merits_flaws.append(MP(merit_id="mf.fae-prince-of-chaos"))
    assert _codes(validate.validate_chargen(rs, c), "merit-wrong-origin")
    # the prereq chain resolves: Transcendent Dream Shape is itself noble-only
    tds = rs.merits_flaws["mf.fae-transcendent-dream-shape"]
    assert tds.required_origins == ["Noble"]


def test_fae_goblin_body_requires_a_commoner_origin(rs):
    m = rs.merits_flaws["mf.fae-goblin-body"]
    assert m.variable_cost
    assert validate.merit_available_to(m, "God-Blooded", "fae-blooded", origin="Commoner")
    assert not validate.merit_available_to(m, "God-Blooded", "fae-blooded", origin="Noble")


def test_a_fae_blooded_must_choose_a_nobility(rs):
    empty = _fb(origin="")
    assert _codes(validate.validate_chargen(rs, empty), "heritage-requires-origin")


def test_a_fae_blooded_with_another_heritages_origin_is_reported(rs):
    """Review Fix 5: an origin that is not one of the heritage's options — a Fae-Blooded
    carrying the Half-Caste's "Solar" parent — is a DISTINCT issue (heritage-foreign-
    origin), so the stale value is visible rather than merely fatal in the editor."""
    c = _fb(origin="Solar")
    assert _codes(validate.validate_chargen(rs, c), "heritage-foreign-origin")
    assert not _codes(validate.validate_chargen(rs, c), "heritage-requires-origin")


def test_virtue_attunement_prices_the_attuned_virtue_at_two_bp(rs):
    """PG p.74: the attuned Virtue "may be increased for a cost of two bonus points per
    dot" instead of three. The attuned dots draw on the free pool LAST, so the discount
    lands on as many of their PRICED dots as possible: with the pool short by two dots,
    and Compassion — attuned — carrying two of the overflow, it saves two bonus points.
    (The code-review fix flipped this from -1: the old code drained the free pool with
    the attuned dots first, discounting the fewest possible.)"""
    base = _fb()
    base.virtues = {VirtueName.COMPASSION: 4, VirtueName.CONVICTION: 3,
                    VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 2}
    attuned = _fb()
    attuned.virtues = dict(base.virtues)
    attuned.merits_flaws.append(MP(merit_id="mf.fae-virtue-attunement", detail="compassion"))
    vb = lambda ch: next(l.points for l in validate.bonus_point_breakdown(rs, ch).lines
                         if l.domain == "Virtues")
    assert vb(attuned) == vb(base) - 2
    # The same shortfall entirely below the pre-BP cap: no above-cap dot soaks the
    # overflow, so both priced dots land on the attuned Compassion — a two-dot discount
    # where the old code charged nothing at all.
    base2 = _fb()
    base2.virtues = {VirtueName.COMPASSION: 3, VirtueName.CONVICTION: 3,
                     VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 3}
    attuned2 = _fb()
    attuned2.virtues = dict(base2.virtues)
    attuned2.merits_flaws.append(MP(merit_id="mf.fae-virtue-attunement", detail="compassion"))
    assert vb(attuned2) == vb(base2) - 2


def test_virtue_attunement_prices_the_attuned_virtue_at_x2_xp(rs):
    """...or (current rating x 2) experience points instead of x3."""
    c = _fb()
    c.merits_flaws.append(MP(merit_id="mf.fae-virtue-attunement", detail="compassion"))
    assert costs.virtue_step(rs, c, 3, VirtueName.COMPASSION) == 6    # 3 x 2
    assert costs.virtue_step(rs, c, 3, VirtueName.CONVICTION) == 9    # 3 x 3, not attuned
    assert costs.virtue_step(rs, c, 3) == 9                           # no name = no discount


def test_virtue_attunement_is_once_for_a_commoner_twice_for_a_noble(rs):
    """PG p.74: "may only purchase this Merit once. Children of fairy nobles may
    purchase this Merit up to twice" — nobility rides the Origin axis (human
    2026-08-02), so a Noble Fae-Blooded may attune two Virtues, a Commoner one."""
    m = rs.merits_flaws["mf.fae-virtue-attunement"]
    assert m.repeatable_by == "virtue"
    assert m.max_purchases_by_origin == {"Noble": 2, "Commoner": 1}
    noble = _fb(origin="Noble")
    noble.merits_flaws += [MP(merit_id="mf.fae-virtue-attunement", detail="compassion"),
                           MP(merit_id="mf.fae-virtue-attunement", detail="valor")]
    assert not _codes(validate.validate_chargen(rs, noble), "merit-repeats-above-origin")
    assert not _codes(validate.validate_chargen(rs, noble), "merit-repeated")
    commoner = _fb(origin="Commoner")
    commoner.merits_flaws += [MP(merit_id="mf.fae-virtue-attunement", detail="compassion"),
                              MP(merit_id="mf.fae-virtue-attunement", detail="valor")]
    assert _codes(validate.validate_chargen(rs, commoner), "merit-repeats-above-origin")
    overloaded = _fb(origin="Noble")
    overloaded.merits_flaws += [MP(merit_id="mf.fae-virtue-attunement", detail="compassion"),
                                MP(merit_id="mf.fae-virtue-attunement", detail="valor"),
                                MP(merit_id="mf.fae-virtue-attunement", detail="temperance")]
    assert _codes(validate.validate_chargen(rs, overloaded), "merit-repeats-above-origin")


def test_a_commoner_cannot_buy_a_second_virtue_attunement_with_xp(rs):
    """The origin cap holds on the buy path too — a Commoner must not pay XP for a
    second copy past what validate refuses."""
    c = _fb(origin="Commoner", merits_flaws=[MP(merit_id="mf.fae-virtue-attunement",
                                                detail="compassion")])
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 300)
    with pytest.raises(advancement.AdvancementError, match="at most 1 time"):
        advancement.buy_merit(rs, c, "mf.fae-virtue-attunement", detail="valor")
