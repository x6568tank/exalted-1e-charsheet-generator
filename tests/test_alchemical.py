"""Alchemical chargen foundation: exercises the shipped Alchemical data
(exalts.json, chargen_budgets.json, costs_bonus.json, the five Castes) and the
new caste_favored Attribute-budget machinery Alchemicals use instead of the
category-prioritized pools every other splat uses (Character Creation & Traits,
p.58-64).

Scope note: this is the chargen foundation only. The Charm Slot system
(General/Dedicated slots) and the Alchemical Charm catalogue wait on the Charm
rules chapter (p.88-91), which has not landed yet — so nothing here exercises
Charms, and charm_min_caste_favored is deliberately 0 in the data.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import (advancement, costs, derive, lifecycle, refit,
                                    validate)
from exalted_builder.models.character import (Array, BackgroundEntry, Character,
                                             PlayState,
                                             SubmodulePurchase)
from exalted_builder.models.rules import AbilityName as A
from exalted_builder.models.rules import AttributeName as AT
from exalted_builder.models.rules import VirtueName as V

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _codes(issues, code):
    return [i for i in issues if i.code == code]


def _alchemical(caste="orichalcum") -> Character:
    """A legal Orichalcum Caste Alchemical that spends exactly its free budget
    (0 bonus points): Caste Attributes 9 dots (min 2 each), 3 Favored Attributes
    6 dots, remaining 4 dots; 23 Ability dots (cap 3, no Caste/Favored abilities);
    13 Background dots; 5 Virtue dots. No Charms (the slot system is deferred)."""
    c = Character(id="alch.test", exalt_type="Alchemical", caste=caste)
    # Orichalcum Caste Attributes: Strength/Charisma/Intelligence (9 dots, each >=2)
    c.attributes.update({
        AT.STRENGTH: 5, AT.CHARISMA: 4, AT.INTELLIGENCE: 3,   # caste spend = 4+3+2 = 9
        AT.DEXTERITY: 3, AT.STAMINA: 3, AT.PERCEPTION: 3,     # favored spend = 2+2+2 = 6
        AT.MANIPULATION: 3, AT.APPEARANCE: 2, AT.WITS: 2,     # remaining spend = 2+1+1 = 4
    })
    c.favored_attributes = [AT.DEXTERITY, AT.STAMINA, AT.PERCEPTION]
    c.favored_abilities = []                                   # Alchemicals have none
    c.abilities.update({
        A.MELEE: 3, A.DODGE: 3, A.ATHLETICS: 3, A.AWARENESS: 3,
        A.LORE: 3, A.OCCULT: 3, A.PRESENCE: 3, A.BUREAUCRACY: 2,   # = 23
    })
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 1})  # spend 5
    # Class ••• is automatic for every Alchemical (CH2 p.66), so the minimum-rating
    # rule requires it even on an otherwise-bare fixture. It spends 3 of the 13
    # Background dots, which are free, so the build still costs 0 bonus points.
    c.backgrounds = [BackgroundEntry(name="Class", rating=3)]
    c.essence_rating = 2
    return c


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

def test_alchemical_exalt_and_castes_load(rs):
    assert "Alchemical" in rs.exalts
    castes = {c for c, d in rs.castes.items() if d.exalt_type == "Alchemical"}
    assert castes == {"orichalcum", "moonsilver", "jade", "starmetal", "soulsteel"}
    # Every Alchemical caste has Caste Attributes, no Caste Abilities.
    for cid in castes:
        cd = rs.castes[cid]
        assert len(cd.caste_attributes) == 3
        assert not cd.caste_abilities


def test_alchemical_budget_is_caste_favored_mode(rs):
    b = rs.budgets_for("Alchemical")
    assert b.attribute_mode == "caste_favored"
    assert tuple(b.attribute_pools) == (9, 6, 4)
    assert b.attribute_favored_count == 3
    assert b.attribute_caste_min == 2
    assert b.ability_dots == 23
    assert b.favored_count == 0            # no Favored Abilities


def test_essence_pools_alchemical_formula(rs):
    # Personal = Essence*3 + WP; Peripheral = Essence*5 + WP*3 + highestVirtue*2.
    c = _alchemical()
    # WP = two highest Virtues = 3 + 3 = 6; highest Virtue = 3; Essence = 2.
    personal, peripheral = derive.essence_pools(rs, c)
    assert personal == 2 * 3 + 6              # 12
    assert peripheral == 2 * 5 + 6 * 3 + 3 * 2  # 10 + 18 + 6 = 34


# --------------------------------------------------------------------------- #
# Chargen legality
# --------------------------------------------------------------------------- #

def test_valid_alchemical_spends_zero_bonus_points(rs):
    c = _alchemical()
    issues = validate.validate_chargen(rs, c)
    bp = validate.bonus_point_breakdown(rs, c)
    assert bp.total == 0, [(l.domain, l.points) for l in bp.lines]
    assert not [i for i in issues if i.severity == "error"], \
        [(i.code, i.message) for i in issues if i.severity == "error"]


def test_caste_attribute_below_minimum_flagged(rs):
    c = _alchemical()
    # Drop Intelligence (a Caste Attribute) to 1, move its dots to Strength.
    c.attributes[AT.INTELLIGENCE] = 1
    c.attributes[AT.STRENGTH] = 7
    issues = validate.validate_chargen(rs, c)
    flagged = _codes(issues, "caste-attribute-min")
    assert flagged and flagged[0].where == "intelligence"


def test_wrong_favored_attribute_count_flagged(rs):
    c = _alchemical()
    c.favored_attributes = [AT.DEXTERITY, AT.STAMINA]     # only 2, need 3
    assert _codes(validate.validate_chargen(rs, c), "favored-attribute-count")


def test_favored_attribute_overlapping_caste_flagged(rs):
    c = _alchemical()
    # Strength is a Caste Attribute for Orichalcum; it may not also be Favored.
    c.favored_attributes = [AT.STRENGTH, AT.DEXTERITY, AT.STAMINA]
    assert _codes(validate.validate_chargen(rs, c), "favored-attribute-overlaps-caste")


def test_overspending_caste_attributes_costs_discounted_rate(rs):
    c = _alchemical()
    # One extra dot in the Caste set (Charisma 4 -> 5): 1 dot over the 9 pool,
    # charged the discounted Caste/Favored rate of 3 BP.
    c.attributes[AT.CHARISMA] = 5
    bp = validate.bonus_point_breakdown(rs, c)
    attr_line = next(l for l in bp.lines if l.domain == "Attributes")
    assert attr_line.points == 3


def test_overspending_remaining_attributes_costs_full_rate(rs):
    c = _alchemical()
    # One extra dot in the remaining set (Wits 2 -> 3): 1 dot over the 4 pool,
    # charged the full non-favored rate of 4 BP.
    c.attributes[AT.WITS] = 3
    bp = validate.bonus_point_breakdown(rs, c)
    attr_line = next(l for l in bp.lines if l.domain == "Attributes")
    assert attr_line.points == 4


def test_favored_attributes_get_discounted_overspend(rs):
    c = _alchemical()
    # One extra dot in the Favored set (Perception 3 -> 4): over the 6 pool,
    # charged the discounted rate of 3 (Favored Attributes share the discount).
    c.attributes[AT.PERCEPTION] = 4
    bp = validate.bonus_point_breakdown(rs, c)
    attr_line = next(l for l in bp.lines if l.domain == "Attributes")
    assert attr_line.points == 3


# --------------------------------------------------------------------------- #
# Backgrounds (CH2 p.65-69)
# --------------------------------------------------------------------------- #
# The Alchemical is the FIRST splat whose Backgrounds carry real chargen mechanics;
# for every other splat they stay soft free text and `background_rules` is empty.

def _bg(c, **ratings):
    c.backgrounds = [BackgroundEntry(name=n, rating=r) for n, r in ratings.items()]
    return c


def test_alchemical_backgrounds_are_in_the_catalog(rs):
    catalog = {b.id: b for b in rs.backgrounds_for("Alchemical")}
    assert "background.class" in catalog and "background.vats" in catalog
    # Both are Alchemical-only and must not leak into another splat's picker.
    solar = {b.id for b in rs.backgrounds_for("Solar")}
    assert "background.class" not in solar and "background.vats" not in solar


def test_other_splats_have_no_background_mechanics(rs):
    """The rules are opt-in per splat; nothing may change for anyone else.

    The loyal Abyssal is the second splat to opt in (E:Ab p.131 budgets the Artifact
    Background), so it is checked separately below rather than listed here — but its
    rule must be budget_tiers ONLY, since none of the Alchemical chargen mechanics
    this module tests apply to it."""
    for splat in ("Solar", "Lunar"):
        assert rs.budgets_for(splat).background_rules == {}
    # The loyal Abyssal and the Dragon-Blooded both opted in for the Artifact
    # Background (E:Ab p.131's budget table; "twice the dots' worth" respectively), and
    # neither may pick up any of the Alchemical chargen mechanics this module tests.
    for splat in ("Abyssal", "Dragon-Blooded"):
        rules = rs.budgets_for(splat).background_rules
        assert set(rules) == {"artifact"}
        rule = rules["artifact"]
        assert (rule.min_rating, rule.requires, rule.max_rating,
                rule.expensive_above, rule.free_rating) == (0, "", 0, 0, 0)
    assert rs.budgets_for("Abyssal").background_rules["artifact"].budget_tiers
    assert rs.budgets_for("Dragon-Blooded").background_rules["artifact"].rating_per_dot == 2


def test_class_is_automatic_at_three(rs):
    c = _bg(_alchemical(), Class=3)
    assert not _codes(validate.validate_chargen(rs, c), "background-below-minimum")
    c = _bg(_alchemical(), Class=2)
    assert _codes(validate.validate_chargen(rs, c), "background-below-minimum")


def test_backing_requires_class_three(rs):
    c = _bg(_alchemical(), Class=3, Backing=2)
    assert not _codes(validate.validate_chargen(rs, c), "background-requires")
    # Class 3 is the gate; a lower Class fails Backing as well as its own minimum.
    c = _bg(_alchemical(), Class=1, Backing=2)
    assert _codes(validate.validate_chargen(rs, c), "background-requires")
    # No Backing at all: the prerequisite is moot, not violated.
    c = _bg(_alchemical(), Class=1)
    assert not _codes(validate.validate_chargen(rs, c), "background-requires")


def test_artifact_may_exceed_three_without_bonus_points(rs):
    """"Only Artifact may be higher than 3 without bonus points" (p.61) — for any
    other Background the 4th and 5th dot cost bonus points."""
    c = _bg(_alchemical(), Class=3, Artifact=5)          # 3 + 2 + 2 = 7 pool dots
    assert validate.bonus_point_breakdown(rs, c).total == 0
    c = _bg(_alchemical(), Class=3, Vats=5)              # 2 dots above the cap
    line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                if l.domain == "Backgrounds")
    assert line.points == 2 * rs.bonus_costs_for("Alchemical").background_above_3


def test_artifact_fourth_and_fifth_dots_cost_two_pool_dots_each(rs):
    """"The fourth and fifth dot still cost two (2) dots each" (p.65)."""
    assert validate.background_pool_dots(
        validate.background_rule(rs.budgets_for("Alchemical"), "Artifact"), 3) == 3
    assert validate.background_pool_dots(
        validate.background_rule(rs.budgets_for("Alchemical"), "Artifact"), 4) == 5
    assert validate.background_pool_dots(
        validate.background_rule(rs.budgets_for("Alchemical"), "Artifact"), 5) == 7
    # Artifact 5 eats SEVEN of the 13 dots, not five: Class 3 + Artifact 7 + Vats 3
    # exactly fills the pool.
    c = _bg(_alchemical(), Class=3, Artifact=5, Vats=3)
    assert validate.bonus_point_breakdown(rs, c).total == 0
    # One more dot overflows the pool, charged at the flat per-dot rate (1) — which is
    # a different charge from exceeding the cap-3 rule (background_above_3, 2).
    c = _bg(_alchemical(), Class=3, Artifact=5, Vats=3, Allies=1)
    assert validate.bonus_point_breakdown(rs, c).total == rs.bonus_costs_for(
        "Alchemical").background


def test_background_rules_are_matched_case_insensitively(rs):
    """BackgroundEntry.name is free text, so the lookup must not be brittle."""
    c = _bg(_alchemical(), **{"class": 3})
    assert not _codes(validate.validate_chargen(rs, c), "background-below-minimum")


# --------------------------------------------------------------------------- #
# Charm Slot system (p.88-89)
# --------------------------------------------------------------------------- #
# Orichalcum Caste Attributes = Strength/Charisma/Intelligence; the _alchemical()
# fixture Favors Dexterity/Stamina/Perception. So a Charm keyed to any of those six
# is Caste/Favored (fits a Dedicated Slot); one keyed to Manipulation/Appearance/
# Wits is not (needs a General Slot).
CF_CHARMS = [
    "alchemical.general.transitory-augmentation-of-strength",      # Str (Caste)
    "alchemical.general.transitory-augmentation-of-charisma",      # Cha (Caste)
    "alchemical.general.transitory-augmentation-of-intelligence",  # Int (Caste)
    "alchemical.general.transitory-augmentation-of-dexterity",     # Dex (Favored)
    "alchemical.general.transitory-augmentation-of-stamina",       # Sta (Favored)
    "alchemical.general.transitory-augmentation-of-perception",    # Per (Favored)
]
NONCF_CHARMS = [
    "alchemical.general.transitory-augmentation-of-manipulation",
    "alchemical.general.transitory-augmentation-of-appearance",
    "alchemical.general.transitory-augmentation-of-wits",
    "alchemical.general.sustained-augmentation-of-manipulation",
    "alchemical.general.sustained-augmentation-of-appearance",
]


def test_charm_keying_caste_favored_vs_general(rs):
    c = _alchemical()
    cf_set = set()                                 # no Caste/Favored ABILITIES
    caste_fav = validate._caste_favored_attr_names(rs, c)
    str_charm = rs.charms[CF_CHARMS[0]]
    wits_charm = rs.charms["alchemical.general.transitory-augmentation-of-wits"]
    assert validate._charm_is_caste_favored(str_charm, cf_set, None, caste_fav)
    assert not validate._charm_is_caste_favored(wits_charm, cf_set, None, caste_fav)


def test_valid_eight_charm_build_fills_slots_zero_bp(rs):
    c = _alchemical()
    # 4 Caste/Favored (fill the 4 Dedicated Slots) + 4 non-CF (fill 4 General).
    c.charms = CF_CHARMS[:4] + NONCF_CHARMS[:4]
    issues = validate.validate_chargen(rs, c)
    bp = validate.bonus_point_breakdown(rs, c)
    charm_line = next(l for l in bp.lines if l.domain == "Charms & Spells")
    assert charm_line.points == 0                  # 8 Charms fill the 8 free Slots
    assert not [i for i in issues if i.severity == "error"], \
        [(i.code, i.message) for i in issues if i.severity == "error"]


def test_too_many_noncf_charms_needs_general_slots(rs):
    c = _alchemical()
    # 5 non-CF Charms but only 4 General Slots.
    c.charms = NONCF_CHARMS[:5] + CF_CHARMS[:3]    # 8 total (fits slots), but 5 non-CF
    assert _codes(validate.validate_chargen(rs, c), "charm-noncf-exceeds-general-slots")


def test_too_many_charms_exceeds_total_slots(rs):
    c = _alchemical()
    c.charms = CF_CHARMS[:5] + NONCF_CHARMS[:4]    # 9 Charms, only 8 Slots
    assert _codes(validate.validate_chargen(rs, c), "charm-exceeds-slots")


def test_buying_extra_general_slot_costs_six_bp(rs):
    c = _alchemical()
    c.general_charm_slots = 5                       # one extra General Slot
    charm_line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                      if l.domain == "Charms & Spells")
    assert charm_line.points == 6


def test_buying_extra_dedicated_slot_costs_five_bp(rs):
    c = _alchemical()
    c.dedicated_charm_slots = 5                     # one extra Dedicated Slot
    charm_line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                      if l.domain == "Charms & Spells")
    assert charm_line.points == 5


def test_installation_cost_capped_by_personal_pool(rs):
    c = _alchemical()
    # Enough Dedicated Slots and Caste/Favored Charms that committed installation
    # motes exceed the Personal pool (Essence 2 -> Personal = 2*3 + WP 6 = 12).
    thirteen = [f"alchemical.general.{p}-augmentation-of-{a}"
                for p in ("transitory", "sustained")
                for a in ("strength", "charisma", "intelligence",
                          "dexterity", "stamina", "perception")]  # 12 Caste/Favored
    thirteen.append("alchemical.close-combat.accelerated-response-system")  # 13th (Dex, CF)
    c.charms = thirteen                             # 13 Charms * 1 mote install = 13 > 12
    c.dedicated_charm_slots = 13                    # so slot count itself isn't the blocker
    assert _codes(validate.validate_chargen(rs, c), "charm-installation-over-personal")


# --------------------------------------------------------------------------- #
# Arrays (p.89)
# --------------------------------------------------------------------------- #

def _valid_alchemical_with_charms(rs) -> Character:
    c = _alchemical()
    c.charms = CF_CHARMS[:4] + NONCF_CHARMS[:4]
    return c


# Two Attribute-keyed Charms with a NON-ZERO minimum Attribute rating (Wits 3 and
# Dexterity 3, CH3 p.90), so an Array built from them has a real XP price. The root
# Augmentations rate 1-2, and CF_CHARMS are the Transitory roots, so a price built
# from those alone would not catch a cost function that always returned 0.
_RATED_ARRAY_CHARMS = (
    "alchemical.close-combat.tactical-analysis-engrams",       # Minimum Wits: 3
    "alchemical.close-combat.accelerated-response-system",     # Minimum Dexterity: 3
)


def test_valid_array_costs_one_bp_per_charm(rs):
    c = _valid_alchemical_with_charms(rs)
    c.arrays = [Array(name="Reflex Suite", charm_ids=CF_CHARMS[:3])]  # 3 Charms
    bp = validate.bonus_point_breakdown(rs, c)
    array_line = next(l for l in bp.lines if l.domain == "Arrays")
    assert array_line.points == 3
    assert not [i for i in validate.validate_arrays(rs, c) if i.severity == "error"]


def test_arrays_line_absent_for_non_slot_splats(rs):
    c = _alchemical()
    domains = {l.domain for l in validate.bonus_point_breakdown(rs, c).lines}
    assert "Arrays" in domains                       # Alchemical shows it (even at 0)
    solar = Character(id="s", exalt_type="Solar", caste="dawn")
    solar_domains = {l.domain for l in validate.bonus_point_breakdown(rs, solar).lines}
    assert "Arrays" not in solar_domains


def test_array_too_small_flagged(rs):
    c = _valid_alchemical_with_charms(rs)
    c.arrays = [Array(name="Lonely", charm_ids=[CF_CHARMS[0]])]
    assert _codes(validate.validate_arrays(rs, c), "array-too-small")


def test_array_with_unknown_charm_flagged(rs):
    c = _valid_alchemical_with_charms(rs)
    # A Charm not among the character's known Charms.
    c.arrays = [Array(name="Ghost", charm_ids=[CF_CHARMS[0], CF_CHARMS[5]])]
    assert _codes(validate.validate_arrays(rs, c), "array-unknown-charm")


def test_array_rejects_ability_based_charm(rs):
    c = _valid_alchemical_with_charms(rs)
    # Splice in an Ability-based (non-Attribute) Charm the array can't legally hold.
    ability_charm = "solar.archery.wise-arrow"
    c.charms = c.charms + [ability_charm]
    arr = Array(name="Bad", charm_ids=[CF_CHARMS[0], ability_charm])
    assert _codes(validate.array_issues(rs, c, arr), "array-non-attribute-charm")


def test_arrays_barred_for_non_alchemical(rs):
    solar = Character(id="s", exalt_type="Solar", caste="dawn")
    solar.charms = ["solar.melee.example-base-charm", "solar.melee.fire-and-stones-strike"]
    solar.arrays = [Array(name="Nope", charm_ids=solar.charms)]
    assert _codes(validate.validate_arrays(rs, solar), "array-not-supported")


def test_charm_reused_across_arrays_flagged(rs):
    c = _valid_alchemical_with_charms(rs)
    shared = CF_CHARMS[0]
    c.arrays = [
        Array(name="A", charm_ids=[shared, CF_CHARMS[1]]),
        Array(name="B", charm_ids=[shared, NONCF_CHARMS[0]]),
    ]
    assert _codes(validate.validate_arrays(rs, c), "array-charm-reused")


def test_weaving_engine_cannot_be_arrayed(rs):
    c = _alchemical()
    weave = ["alchemical.essence-and-weaving.man-machine-weaving-engine",
             "alchemical.essence-and-weaving.auxiliary-essence-storage-unit"]
    c.charms = weave
    c.arrays = [Array(name="Forbidden", charm_ids=weave)]
    assert _codes(validate.validate_arrays(rs, c), "array-charm-not-arrayable")


def test_array_reduces_installation_cost_to_three_quarters(rs):
    c = _valid_alchemical_with_charms(rs)
    four = CF_CHARMS[:4]                              # 4 Charms, 1 mote install each = 4
    assert validate._installation_motes(rs, four, []) == 4
    arr = [Array(name="Quad", charm_ids=four)]
    assert validate._installation_motes(rs, four, arr) == 3   # ceil(3/4 * 4) = 3


def test_every_attribute_keyed_charm_carries_its_minimum_rating(rs):
    """Every Alchemical Charm prints a 'Minimum <Attribute>: N' line (CH3), and that
    N lives in min_ability — min_attribute only NAMES the trait. A missing rating is
    silently invisible twice over: the Charm gates on nothing, and Arrays built from
    it price at 0 XP (their cost IS the sum of these ratings, p.89). Every one of the
    120 Attribute-keyed Charms shipped with min_ability 0 until 2026-07-23."""
    alch = [c for c in rs.charms.values() if c.exalt_type == "Alchemical"]
    missing = [c.id for c in alch if c.min_attribute and c.min_ability <= 0]
    assert not missing, missing
    # Spot-checks straight off the page, one per shape of source entry.
    def rating(cid):
        return rs.charms[cid].min_ability
    assert rating("alchemical.close-combat.tactical-analysis-engrams") == 3   # plain
    assert rating("alchemical.close-combat.limb-extension-armatures") == 3    # "Minimums"
    assert rating("alchemical.sensory-and-spiritual.tympanal-receptor-upgrade") == 3
    assert rating("alchemical.general.transitory-augmentation-of-wits") == 1  # template
    assert rating("alchemical.general.sustained-augmentation-of-wits") == 2   # template
    assert rating("alchemical.might-and-mobility.steam-inured-frame") == 4    # (Element)
    assert rating("alchemical.close-combat.material-synthesis-wave-emitter-jade") == 3
    # The chapter's only above-5 minimum; reachable because Sustained Augmentation
    # raises that Attribute's maximum by a dot (p.92).
    assert rating("alchemical.essence-and-weaving.god-machine-weaving-engine") == 6


def test_attribute_minimum_actually_gates_charm_learning(rs):
    """The rating is not decoration: a character below it cannot take the Charm."""
    c = _alchemical()
    charm = rs.charms["alchemical.close-combat.tactical-analysis-engrams"]   # Wits 3
    c.charms = ["alchemical.general.transitory-augmentation-of-wits"]        # prereq met
    c.essence_rating = 2
    c.attributes[AT.WITS] = 2
    assert not validate.meets_charm_requirements(rs, c, charm)
    c.attributes[AT.WITS] = 3
    assert validate.meets_charm_requirements(rs, c, charm)


def test_array_installation_motes_is_the_public_three_quarters_rule(rs):
    """The public helper the UI reads must agree with the chargen check's arithmetic —
    they are the same code path, so a divergence is impossible by construction."""
    four = CF_CHARMS[:4]
    assert validate.array_installation_motes(rs, four) == 3
    assert (validate.array_installation_motes(rs, four)
            == validate._installation_motes(rs, four, [Array(name="Q", charm_ids=four)]))


def test_eligible_array_charms_excludes_ability_based_and_unarrayable(rs):
    c = _valid_alchemical_with_charms(rs)
    weave = "alchemical.essence-and-weaving.man-machine-weaving-engine"
    ability_charm = "solar.archery.wise-arrow"
    c.charms = c.charms + [weave, ability_charm]
    eligible = validate.eligible_array_charms(rs, c)
    assert CF_CHARMS[0] in eligible
    assert weave not in eligible                     # arrayable=False
    assert ability_charm not in eligible             # Ability-based, not Attribute-based


# --- Arrays post-lock (XP = sum of minimum Attribute ratings, p.89) --------- #

def test_add_array_costs_sum_of_min_attribute_ratings(rs):
    c = _locked_alch(rs)
    # Dynamic Reaction Enhancement System and Accelerated Response System both gate on
    # a rated Attribute, so the Array has a non-zero price (unlike the rating-0 roots).
    c.charms = list(_RATED_ARRAY_CHARMS)
    expected = sum(rs.charms[cid].min_ability for cid in _RATED_ARRAY_CHARMS)
    assert expected > 0
    assert costs.array_cost(rs, list(_RATED_ARRAY_CHARMS)) == expected
    before = advancement.xp_available(c)
    advancement.add_array(rs, c, "Reflex Suite", list(_RATED_ARRAY_CHARMS))
    assert [a.name for a in c.arrays] == ["Reflex Suite"]
    assert advancement.xp_available(c) == before - expected
    # the audit re-derives the price and agrees with what was charged
    assert not [i for i in advancement.validate_xp(rs, c) if i.severity == "error"]


def test_add_array_undo_removes_it_and_refunds(rs):
    c = _locked_alch(rs)
    c.charms = list(_RATED_ARRAY_CHARMS)
    before = advancement.xp_available(c)
    advancement.add_array(rs, c, "Reflex Suite", list(_RATED_ARRAY_CHARMS))
    advancement.undo_last(rs, c)
    assert c.arrays == []
    assert advancement.xp_available(c) == before


def test_add_array_rejects_reusing_a_linked_charm(rs):
    """A Charm may join only one Array — the post-lock path must enforce the
    cross-Array rule too, not just the per-Array one."""
    c = _locked_alch(rs)
    c.charms = list(_RATED_ARRAY_CHARMS)
    advancement.add_array(rs, c, "First", list(_RATED_ARRAY_CHARMS))
    with pytest.raises(advancement.AdvancementError, match="already linked"):
        advancement.add_array(rs, c, "Second", list(_RATED_ARRAY_CHARMS))


def test_add_array_rejects_illegal_set(rs):
    c = _locked_alch(rs)
    c.charms = list(_RATED_ARRAY_CHARMS)
    with pytest.raises(advancement.AdvancementError, match="at least two"):
        advancement.add_array(rs, c, "Lonely", [_RATED_ARRAY_CHARMS[0]])


def test_add_array_barred_for_a_non_slot_splat(rs):
    """Eclipse/Moonshadow may not build Arrays (p.90) even once they hold Alchemical
    Charms through the crossover rule."""
    solar = Character(id="s", exalt_type="Solar", caste="eclipse")
    solar.charms = ["solar.melee.example-base-charm", "solar.melee.fire-and-stones-strike"]
    lifecycle.lock_chargen(solar)
    solar.xp_earned = 100
    with pytest.raises(advancement.AdvancementError, match="Alchemical"):
        advancement.add_array(rs, solar, "Nope", list(solar.charms))


# --------------------------------------------------------------------------- #
# Submodules (p.89)
# --------------------------------------------------------------------------- #
_POLYMODAL = "alchemical.close-combat.polymodal-joint-bearings"
_DEX_AUG = "alchemical.general.transitory-augmentation-of-dexterity"


def _with_submodule(rs) -> Character:
    """A valid Alchemical who knows Polymodal Joint Bearings (+ its prereq) with
    Wits 3 (the omnidextrous submodule needs Wits 3+), owning that submodule."""
    c = _alchemical()
    c.attributes[AT.WITS] = 3
    c.charms = [_DEX_AUG, _POLYMODAL]
    c.submodules = [SubmodulePurchase(charm_id=_POLYMODAL, key="omnidextrous")]
    return c


def test_submodule_data_loads(rs):
    charm = rs.charms[_POLYMODAL]
    assert len(charm.submodules) == 1
    sub = charm.submodules[0]
    assert (sub.key, sub.bp_cost, sub.xp_cost) == ("omnidextrous", 2, 6)
    assert (sub.min_attribute, sub.min_attribute_rating) == ("wits", 3)


def test_valid_submodule_costs_its_bp(rs):
    c = _with_submodule(rs)
    assert not [i for i in validate.validate_submodules(rs, c) if i.severity == "error"]
    sub_line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                    if l.domain == "Submodules")
    assert sub_line.points == 2


def test_submodule_line_absent_for_non_slot_splats(rs):
    solar = Character(id="s", exalt_type="Solar", caste="dawn")
    domains = {l.domain for l in validate.bonus_point_breakdown(rs, solar).lines}
    assert "Submodules" not in domains and "Arrays" not in domains


def test_submodule_requires_known_parent_charm(rs):
    c = _with_submodule(rs)
    c.charms = [_DEX_AUG]                          # Polymodal no longer known
    assert _codes(validate.validate_submodules(rs, c), "submodule-charm-not-known")


def test_submodule_unknown_key_flagged(rs):
    c = _with_submodule(rs)
    c.submodules = [SubmodulePurchase(charm_id=_POLYMODAL, key="nonexistent")]
    assert _codes(validate.validate_submodules(rs, c), "submodule-unknown")


def test_submodule_attribute_gate_enforced(rs):
    c = _with_submodule(rs)
    c.attributes[AT.WITS] = 2                      # below the omnidextrous Wits 3 gate
    assert _codes(validate.validate_submodules(rs, c), "submodule-attribute")


def test_submodule_duplicate_flagged(rs):
    c = _with_submodule(rs)
    c.submodules = c.submodules + [SubmodulePurchase(charm_id=_POLYMODAL, key="omnidextrous")]
    assert _codes(validate.validate_submodules(rs, c), "submodule-duplicate")


def test_learn_submodule_post_lock_then_undo(rs):
    c = _with_submodule(rs)
    c.submodules = []                              # buy it post-lock instead
    lifecycle.lock_chargen(c)
    c.xp_earned = 20
    entry = advancement.learn_submodule(rs, c, _POLYMODAL, "omnidextrous")
    assert entry.cost == 6                         # the submodule's xp_cost
    assert c.submodules and c.submodules[0].key == "omnidextrous"
    assert not [i for i in advancement.validate_xp(rs, c) if i.severity == "error"]
    advancement.undo_last(rs, c)
    assert not c.submodules and not c.xp_log


def test_submodule_block_reason_walks_each_gate_in_turn(rs):
    """The picker's one source of submodule eligibility. Reasons must clear in order:
    parent Charm installed, then the submodule's own Attribute minimum."""
    parent = "alchemical.close-combat.polymodal-joint-bearings"
    key = rs.charms[parent].submodules[0].key
    c = _alchemical()
    assert "install" in validate.submodule_block_reason(rs, c, parent, key).lower()
    c.charms = [parent]
    c.attributes[AT.WITS] = 2                      # omnidextrous requires Wits 3
    assert "Wits 3" in validate.submodule_block_reason(rs, c, parent, key)
    c.attributes[AT.WITS] = 3
    assert validate.submodule_block_reason(rs, c, parent, key) == ""
    c.submodules = [SubmodulePurchase(charm_id=parent, key=key)]
    assert validate.submodule_block_reason(rs, c, parent, key) == "Already purchased."
    assert validate.owns_submodule(c, parent, key)


def test_submodule_rows_carry_both_prices_and_are_empty_for_plain_charms(rs):
    from exalted_builder.ui import view as viewmod
    parent = "alchemical.close-combat.polymodal-joint-bearings"
    c = _alchemical()
    c.charms = [parent]
    c.attributes[AT.WITS] = 3
    rows = viewmod.build_submodule_rows(rs, c, parent)
    assert len(rows) == 1
    row = rows[0]
    assert (row.bp_cost, row.xp_cost) == (2, 6)    # "2 bonus points or 6 experience"
    assert row.requirement == "Wits 3"
    assert row.available and not row.owned
    # Most Charms offer none, and the section must then render nothing at all.
    assert viewmod.build_submodule_rows(
        rs, c, "alchemical.close-combat.tactical-analysis-engrams") == []


# --------------------------------------------------------------------------- #
# Vat refit: Charm Slots <-> Panoply (p.88-89)
# --------------------------------------------------------------------------- #

def _refit_char(rs) -> Character:
    """An Alchemical wearing four Caste/Favored Charms, with four Slots of each kind."""
    c = _alchemical()
    c.charms = list(CF_CHARMS[:4])
    return c


def test_slot_load_reports_live_wear_not_the_chargen_snapshot(rs):
    """The refit picture must follow character.charms as it changes. validate's
    charm_slot_usage deliberately reads the frozen snapshot once locked (it answers
    "was this legally built?"); slot_load answers "what is worn right now"."""
    c = _refit_char(rs)
    lifecycle.lock_chargen(c)
    before = refit.slot_load(rs, c).installed
    refit.uninstall(rs, c, CF_CHARMS[0])
    assert refit.slot_load(rs, c).installed == before - 1
    # The chargen view is unmoved — the refit did not rewrite history.
    assert validate.charm_slot_usage(rs, c)[0] == before


def test_uninstall_moves_a_charm_to_the_panoply_and_install_moves_it_back(rs):
    c = _refit_char(rs)
    refit.uninstall(rs, c, CF_CHARMS[0])
    assert CF_CHARMS[0] not in c.charms and CF_CHARMS[0] in c.retainer_charms
    refit.install(rs, c, CF_CHARMS[0])
    assert CF_CHARMS[0] in c.charms and CF_CHARMS[0] not in c.retainer_charms


def test_refit_spends_no_experience_and_writes_no_log(rs):
    """A refit is play-state: the Charms are already paid for, so nothing is charged
    and the XP ledger must not gain a row."""
    c = _refit_char(rs)
    lifecycle.lock_chargen(c)
    c.xp_earned = 50
    before = advancement.xp_available(c)
    refit.uninstall(rs, c, CF_CHARMS[0])
    refit.install(rs, c, CF_CHARMS[0])
    assert advancement.xp_available(c) == before
    assert c.xp_log == []


def test_install_refused_when_no_slot_is_free(rs):
    c = _alchemical()
    c.charms = list(CF_CHARMS[:4]) + list(NONCF_CHARMS[:4])      # all 8 Slots full
    c.retainer_charms = [CF_CHARMS[4]]
    reason = refit.install_block_reason(rs, c, CF_CHARMS[4])
    assert "No free Charm Slot" in reason
    with pytest.raises(refit.RefitError, match="No free Charm Slot"):
        refit.install(rs, c, CF_CHARMS[4])


def test_non_caste_favored_charm_needs_a_general_slot_specifically(rs):
    """Dedicated Slots take only Caste/Favored Charms (p.88), so a free Slot is not
    enough on its own — it has to be a General one."""
    c = _alchemical()
    # All 4 General Slots used by non-C/F Charms; Dedicated Slots still free.
    c.charms = list(NONCF_CHARMS[:4])
    c.retainer_charms = [NONCF_CHARMS[4]]
    reason = refit.install_block_reason(rs, c, NONCF_CHARMS[4])
    assert "Dedicated" in reason
    # A Caste/Favored Charm fits those same free Dedicated Slots fine.
    c.retainer_charms.append(CF_CHARMS[0])
    assert refit.install_block_reason(rs, c, CF_CHARMS[0]) == ""


def test_uninstall_rejects_a_charm_that_is_not_installed(rs):
    c = _refit_char(rs)
    with pytest.raises(refit.RefitError, match="[Nn]ot installed"):
        refit.uninstall(rs, c, CF_CHARMS[5])


def test_supports_refit_covers_alchemicals_and_crossover_eclipses(rs):
    assert refit.supports_refit(rs, _alchemical())
    plain_solar = Character(id="s", exalt_type="Solar", caste="dawn")
    assert not refit.supports_refit(rs, plain_solar)
    # An Eclipse who crossed over holds Alchemical Charms in a Panoply, so they get
    # the manager even though they are not a Slot splat.
    eclipse = Character(id="e", exalt_type="Solar", caste="eclipse")
    assert not refit.supports_refit(rs, eclipse)
    eclipse.retainer_charms = [CF_CHARMS[0]]
    assert refit.supports_refit(rs, eclipse)


# --------------------------------------------------------------------------- #
# Clarity (CH2 p.69-71)
# --------------------------------------------------------------------------- #
# The Alchemical stand-in for Limit. Permanent Clarity is DERIVED (one dot per dot
# of Essence above 5, plus one per installed granting Charm); temporary Clarity is
# tracked on PlayState. Total is capped at 10 and never "breaks".

_CLARITY_CHARMS = [
    "alchemical.close-combat.hyperdextrous-tentacle-apparatus",
    "alchemical.might-and-mobility.insectile-locomotion-upgrade",
    "alchemical.social.transcendent-brutality-programming",
    "alchemical.cognitive.clarified-data-assimilator",
    "alchemical.essence-and-weaving.man-machine-weaving-engine",
    "alchemical.essence-and-weaving.god-machine-weaving-engine",
]


def test_only_alchemicals_use_clarity(rs):
    assert derive.uses_clarity(rs, _alchemical())
    assert not derive.uses_clarity(rs, Character(id="s", exalt_type="Solar", caste="dawn"))


def test_exactly_the_six_charms_grant_permanent_clarity(rs):
    granting = sorted(c.id for c in rs.charms.values() if c.permanent_clarity)
    assert granting == sorted(_CLARITY_CHARMS)
    assert all(rs.charms[cid].permanent_clarity == 1 for cid in _CLARITY_CHARMS)


def test_permanent_clarity_is_essence_above_five_plus_charms(rs):
    c = _alchemical()
    c.essence_rating = 5
    assert derive.clarity(rs, c).permanent == 0        # nothing at Essence 5
    c.essence_rating = 8                               # 3 dots above the fifth
    assert derive.clarity(rs, c).permanent == 3
    c.charms = [_CLARITY_CHARMS[0], _CLARITY_CHARMS[1]]
    v = derive.clarity(rs, c)
    assert v.permanent == 5
    assert ("Essence 8", 3) in v.sources


def test_temporary_clarity_comes_from_play_state(rs):
    c = _alchemical()
    assert derive.clarity(rs, c).temporary == 0        # no PlayState at all
    c.play = PlayState(clarity_temporary=4)
    v = derive.clarity(rs, c)
    assert (v.temporary, v.permanent, v.total) == (4, 0, 4)


def test_clarity_total_is_capped_at_ten(rs):
    """"The sum of permanent and temporary Clarity cannot ever exceed 10" (p.69)."""
    c = _alchemical()
    c.essence_rating = 12                              # 7 permanent
    c.play = PlayState(clarity_temporary=8)
    v = derive.clarity(rs, c)
    assert v.permanent == 7 and v.temporary == 8
    assert v.total == 10 and v.capped


def test_clarity_bands_match_the_printed_table(rs):
    assert derive.clarity_band(0)[0] == "0-2"
    assert derive.clarity_band(2)[0] == "0-2"
    assert derive.clarity_band(3)[0] == "3-4"
    assert derive.clarity_band(5)[0] == "5-7"
    assert derive.clarity_band(7)[0] == "5-7"
    assert derive.clarity_band(8)[0] == "8-9"
    assert derive.clarity_band(10)[0] == "10"


def test_removing_the_condition_removes_the_permanent_clarity(rs):
    """p.70: permanent Clarity cannot be lost while its conditions hold, but removing
    a condition removes the dots. Deriving from live traits gives this for free."""
    c = _alchemical()
    c.charms = [_CLARITY_CHARMS[3]]                    # Clarified Data Assimilator
    assert derive.clarity(rs, c).permanent == 1
    refit.uninstall(rs, c, _CLARITY_CHARMS[3])         # to the Panoply: no longer worn
    assert derive.clarity(rs, c).permanent == 0


def test_weaving_engines_can_never_be_uninstalled(rs):
    """CH3 p.141: "she cannot ever remove the Man-Machine Weaving Engine"."""
    engine = "alchemical.essence-and-weaving.man-machine-weaving-engine"
    c = _alchemical()
    c.charms = [engine]
    assert rs.charms[engine].permanent_install
    assert "never be removed" in refit.uninstall_block_reason(rs, c, engine)
    with pytest.raises(refit.RefitError, match="never be removed"):
        refit.uninstall(rs, c, engine)
    assert c.charms == [engine]                        # unchanged
    # An ordinary Charm is still freely refittable.
    c.charms.append(CF_CHARMS[0])
    assert refit.uninstall_block_reason(rs, c, CF_CHARMS[0]) == ""


def _maxed_alchemical(rs) -> Character:
    """An Alchemical with every Attribute at 6, high Essence, Martial Arts 2, who
    knows every Alchemical Charm — for prerequisite-CHAIN sanity (does the whole
    cascade resolve?), not chargen-budget realism. Essence 10 clears even municipal
    (Essence 8+) Charm minimums.

    Attributes are 6, not the usual 5 ceiling: God-Machine Weaving Engine requires
    Minimum Intelligence 6 (CH3 p.141 — the only above-5 minimum in the chapter), and
    that is legitimately reachable because Sustained Augmentation of (Attribute) raises
    that Attribute's maximum by one dot (p.92). This fixture knows all nine Sustained
    Augmentations, so all nine Attributes legitimately cap at 6 for it."""
    c = _alchemical()
    c.attributes.update({a: 6 for a in AT})
    c.essence_rating = 10
    c.abilities[A.MARTIAL_ARTS] = 2                 # Perfected Lotus Matrix gate
    c.charms = [cid for cid, ch in rs.charms.items() if ch.exalt_type == "Alchemical"]
    return c


# As categories are authored, their counts land here so the cascade test tracks growth.
_EXPECTED_CATEGORY_COUNTS = {
    "general": 18,
    "close_combat": 20,
    "ranged_combat": 11,
    "might_and_mobility": 18,
    "social": 12,
    "stealth_and_disguise": 9,
    "sensory_and_spiritual": 10,
    "medical": 11,
    "cognitive": 9,
    "essence_and_weaving": 3,
}


def test_alchemical_charm_cascade_resolves(rs):
    """Every Alchemical Charm's requirements (prereqs + min traits) resolve on a
    maxed Alchemical, and the aggregate prerequisite check finds no missing links.
    Grows as each category is authored."""
    by_cat: dict[str, int] = {}
    for ch in rs.charms.values():
        if ch.exalt_type == "Alchemical":
            by_cat[ch.category] = by_cat.get(ch.category, 0) + 1
    for cat, n in _EXPECTED_CATEGORY_COUNTS.items():
        assert by_cat.get(cat) == n, (cat, by_cat.get(cat))

    c = _maxed_alchemical(rs)
    for cid, ch in rs.charms.items():
        if ch.exalt_type == "Alchemical":
            assert validate.meets_charm_requirements(rs, c, ch), cid
    prereq_errs = [i for i in validate.check_charm_prerequisites(rs, c)
                   if i.severity == "error"]
    assert not prereq_errs, [(i.code, i.where) for i in prereq_errs]


def test_alchemical_ox_body_is_strain_resistant_chassis(rs):
    from exalted_builder.models.character import OxBodyPurchase
    c = _alchemical()
    ob = validate.ox_body_charm(rs, c)
    assert ob is not None and ob.id.endswith("strain-resistant-chassis-modification")
    base = len(derive.health_track(c))
    c.ox_body = [OxBodyPurchase(variant="three-minus-two", health_levels=[-2, -2, -2])]
    assert len(derive.health_track(c)) == base + 3   # the health-level package applied


def test_perfected_lotus_matrix_needs_general_slot(rs):
    # It has no min_attribute, so it can never be Caste/Favored -> not a Dedicated fit.
    c = _alchemical()
    plm = rs.charms["alchemical.close-combat.perfected-lotus-matrix"]
    caste_fav = validate._caste_favored_attr_names(rs, c)
    assert not validate._charm_is_caste_favored(plm, set(), None, caste_fav)


def test_learn_submodule_needs_known_charm(rs):
    c = _alchemical()
    c.charms = [_DEX_AUG]                          # Polymodal not known
    c.attributes[AT.WITS] = 3
    lifecycle.lock_chargen(c)
    c.xp_earned = 20
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_submodule(rs, c, _POLYMODAL, "omnidextrous")


# --------------------------------------------------------------------------- #
# Weaving protocols (Miracles of the Machine God, CH4)
# --------------------------------------------------------------------------- #

_MAN_ENGINE = "alchemical.essence-and-weaving.man-machine-weaving-engine"
_GOD_ENGINE = "alchemical.essence-and-weaving.god-machine-weaving-engine"
_MM_PROTOCOL = "spell.man-machine.binding-filament-system"
_GM_PROTOCOL = "spell.god-machine.destiny-optimizing-meditation"


def test_weaving_circles_loaded(rs):
    from exalted_builder.models.rules import SpellCircle, TRACK_CIRCLES
    mm = [s for s in rs.spells.values() if s.circle == SpellCircle.MAN_MACHINE]
    gm = [s for s in rs.spells.values() if s.circle == SpellCircle.GOD_MACHINE]
    assert len(mm) == 23 and len(gm) == 15                       # the 38 protocols
    assert TRACK_CIRCLES["weaving"] == (SpellCircle.MAN_MACHINE, SpellCircle.GOD_MACHINE)


def test_alchemical_magic_track_is_weaving(rs):
    ed = rs.exalt_for("Alchemical")
    assert ed.magic_track == "weaving"
    assert ed.highest_magic_circle_id == "God-Machine"           # barred at chargen


def test_weaving_circle_access_follows_installed_engine(rs):
    from exalted_builder.models.rules import SpellCircle
    # granted_circles = what the ACTUALLY installed engine(s) unlock.
    c = _alchemical()
    assert validate.granted_circles(rs, c) == set()              # no engine, no circle
    c.charms = [_MAN_ENGINE]
    assert validate.granted_circles(rs, c) == {SpellCircle.MAN_MACHINE}
    c.charms = [_MAN_ENGINE, _GOD_ENGINE]
    assert validate.granted_circles(rs, c) == {
        SpellCircle.MAN_MACHINE, SpellCircle.GOD_MACHINE}
    # accessible_circles is forward-looking (what the picker offers): an Alchemical
    # can always reach both weaving circles, since both engines are learnable natively.
    assert validate.accessible_circles(rs, _alchemical()) == {
        SpellCircle.MAN_MACHINE, SpellCircle.GOD_MACHINE}


def test_god_machine_barred_at_chargen(rs):
    from exalted_builder.models.rules import SpellCircle
    c = _alchemical()
    assert validate.chargen_barred_circle(rs, c) == SpellCircle.GOD_MACHINE
    c.charms = [_MAN_ENGINE, _GOD_ENGINE]
    gm = rs.spells[_GM_PROTOCOL]
    mm = rs.spells[_MM_PROTOCOL]
    assert not validate.meets_spell_requirements(rs, c, gm, chargen=True)   # top circle barred
    assert validate.meets_spell_requirements(rs, c, mm, chargen=True)       # lower circle open
    assert validate.meets_spell_requirements(rs, c, gm, chargen=False)      # post-lock reachable


def test_known_protocol_passes_spell_access(rs):
    c = _alchemical()
    c.charms = [_MAN_ENGINE]
    c.spells = [_MM_PROTOCOL]
    assert not [i for i in validate.check_spell_access(rs, c) if i.severity == "error"]
    # Without the engine the protocol has no granting Charm and is illegal.
    c.charms = []
    assert [i for i in validate.check_spell_access(rs, c) if i.severity == "error"]


def test_non_alchemical_cannot_learn_weaving_engine(rs):
    """CH4: 'Non-Alchemicals cannot learn weaving Charms.' Even a locked Eclipse
    (whose caste opens the p.127 generalist rule) is barred from the engines, so a
    foreign learner can never reach the weaving circles."""
    eclipse = Character(id="e", exalt_type="Solar", caste="eclipse")
    eclipse.chargen_locked = True                    # generalist rule fully open post-lock
    engine = rs.charms[_MAN_ENGINE]
    assert validate.foreign_charms_open(rs, eclipse)             # rule is otherwise open
    assert not validate.charm_learnable_by_splat(rs, eclipse, engine)
    # And if forced into their sheet it is flagged, never silently granting the circle.
    eclipse.charms = [_MAN_ENGINE]
    codes = [i.code for i in validate.check_splat_consistency(rs, eclipse)]
    assert "charm-wrong-splat" in codes
    assert validate.granted_circles(rs, eclipse) == {rs.charms[_MAN_ENGINE].grants_circle}
    # But an Eclipse who does NOT hold the engine can never reach it: accessible_circles
    # (forward-looking) excludes a weaving circle for a non-Alchemical, since the engine
    # is unlearnable for them.
    fresh = Character(id="e2", exalt_type="Solar", caste="eclipse")
    fresh.chargen_locked = True
    assert rs.charms[_MAN_ENGINE].grants_circle not in validate.accessible_circles(rs, fresh)


# --------------------------------------------------------------------------- #
# XP / advancement — trait costs (Autochthonians p.64)
# --------------------------------------------------------------------------- #

def test_attribute_xp_caste_favored_discount(rs):
    from exalted_builder.engine import costs
    c = _alchemical()   # Orichalcum: Caste Str/Cha/Int; Favored Dex/Sta/Per
    # Caste or Favored Attribute: (rating x 4) - 1; anything else: rating x 4.
    assert costs.attribute_step(rs, c, 3, AT.STRENGTH) == 3 * 4 - 1      # Caste
    assert costs.attribute_step(rs, c, 3, AT.DEXTERITY) == 3 * 4 - 1     # Favored
    assert costs.attribute_step(rs, c, 3, AT.MANIPULATION) == 3 * 4      # neither
    # A category-mode splat has no Caste/Favored Attributes, so none discount.
    solar = Character(id="s", exalt_type="Solar", caste="dawn")
    assert costs.attribute_step(rs, solar, 3, AT.STRENGTH) == 3 * 4


def test_essence_xp_is_rating_times_nine(rs):
    from exalted_builder.engine import costs
    c = _alchemical()
    assert costs.essence_step(rs, c, 2) == 2 * 9
    assert costs.essence_step(rs, c, 4) == 4 * 9


def test_raise_caste_attribute_logs_discounted_and_audits_clean(rs):
    c = _alchemical()
    lifecycle.lock_chargen(c)
    c.xp_earned = 100
    entry = advancement.raise_attribute(rs, c, AT.DEXTERITY)  # Favored, from 3
    assert entry.cost == 3 * 4 - 1
    e2 = advancement.raise_attribute(rs, c, AT.MANIPULATION)  # neither, from 3
    assert e2.cost == 3 * 4
    assert not [i for i in advancement.validate_xp(rs, c) if i.code == "xp-cost-mismatch"]


# --- Charm-Slot economy (p.64) --------------------------------------------- #

# Root Augmentations (no prereqs, Essence 2) keyed to specific Attributes: Dexterity
# is Favored in the fixture (fits a Dedicated Slot), Wits is neither (General only).
_DEX_ROOT = "alchemical.general.transitory-augmentation-of-dexterity"      # Favored
_WITS_ROOT = "alchemical.general.transitory-augmentation-of-wits"          # non-C/F
_STR_ROOT = "alchemical.general.transitory-augmentation-of-strength"       # Caste


def _locked_alch(rs, xp=100):
    c = _alchemical()
    lifecycle.lock_chargen(c)
    c.xp_earned = xp
    return c


def test_alchemical_learn_charm_directed_to_slots(rs):
    c = _locked_alch(rs)
    with pytest.raises(advancement.AdvancementError, match="Charm Slot"):
        advancement.learn_charm(rs, c, _DEX_ROOT)


def test_buy_general_slot_installs_charm_and_counts(rs):
    c = _locked_alch(rs)
    g0, d0, _, _ = validate.charm_slot_counts(rs, c)
    entry = advancement.buy_charm_slot(rs, c, dedicated=False, charm_id=_DEX_ROOT)
    assert entry.cost == 12
    assert _DEX_ROOT in c.charms
    g1, d1, _, _ = validate.charm_slot_counts(rs, c)
    assert (g1, d1) == (g0 + 1, d0)
    advancement.undo_last(rs, c)
    assert _DEX_ROOT not in c.charms
    assert validate.charm_slot_counts(rs, c)[:2] == (g0, d0)


def test_buy_dedicated_slot_requires_caste_favored_charm(rs):
    c = _locked_alch(rs)
    # A Wits-keyed Charm (Wits is neither Caste nor Favored here) can't fill a
    # Dedicated Slot.
    with pytest.raises(advancement.AdvancementError, match="Dedicated"):
        advancement.buy_charm_slot(rs, c, dedicated=True, charm_id=_WITS_ROOT)
    # The Dexterity-keyed root fits (Dexterity is Favored).
    entry = advancement.buy_charm_slot(rs, c, dedicated=True, charm_id=_DEX_ROOT)
    assert entry.cost == 10 and _DEX_ROOT in c.charms


def test_upgrade_dedicated_to_general(rs):
    c = _locked_alch(rs)
    g0, d0, _, _ = validate.charm_slot_counts(rs, c)
    entry = advancement.upgrade_charm_slot(rs, c)
    assert entry.cost == 2
    assert validate.charm_slot_counts(rs, c)[:2] == (g0 + 1, d0 - 1)
    advancement.undo_last(rs, c)
    assert validate.charm_slot_counts(rs, c)[:2] == (g0, d0)


def test_retainer_charm_is_owned_not_installed(rs):
    c = _locked_alch(rs)
    entry = advancement.learn_retainer_charm(rs, c, _DEX_ROOT)
    assert entry.cost == 6
    assert _DEX_ROOT in c.retainer_charms
    assert _DEX_ROOT not in c.charms            # Panoply, not a Slot
    # Can't also buy the same Charm into a Slot (already owned).
    with pytest.raises(advancement.AdvancementError, match="already owned"):
        advancement.buy_charm_slot(rs, c, dedicated=False, charm_id=_DEX_ROOT)
    advancement.undo_last(rs, c)
    assert _DEX_ROOT not in c.retainer_charms


def test_weaving_protocol_priced_by_circle_and_audits_clean(rs):
    c = _locked_alch(rs)
    # Install the Man-Machine Weaving Engine via a General Slot (Intelligence-keyed,
    # a Caste Attribute -> could be Dedicated too, but General is simplest here).
    c.attributes[AT.INTELLIGENCE] = 4          # engine needs Intelligence 4 / Essence 4
    c.essence_rating = 4
    advancement.buy_charm_slot(rs, c, dedicated=False, charm_id=_MAN_ENGINE)
    mm = advancement.learn_spell(rs, c, _MM_PROTOCOL)
    assert mm.cost == 12
    assert not [i for i in advancement.validate_xp(rs, c) if i.code == "xp-cost-mismatch"]


def test_slot_economy_full_audit_clean(rs):
    c = _locked_alch(rs, xp=200)
    advancement.buy_charm_slot(rs, c, dedicated=True, charm_id=_DEX_ROOT)
    advancement.learn_retainer_charm(rs, c, _STR_ROOT)
    advancement.upgrade_charm_slot(rs, c)
    mismatches = [i for i in advancement.validate_xp(rs, c) if i.code == "xp-cost-mismatch"]
    assert not mismatches, [i.message for i in mismatches]


# --- Ox-Body takes a Slot (user ruling: every Alchemical Charm occupies a Slot) --- #

def test_alchemical_ox_body_purchase_takes_a_slot(rs):
    c = _locked_alch(rs)                      # Essence 2 -> ox-body cap 2
    g0, d0, _, _ = validate.charm_slot_counts(rs, c)
    entry = advancement.learn_ox_body(rs, c, "two-minus-one")          # General Slot
    assert entry.cost == 12
    assert validate.charm_slot_counts(rs, c)[:2] == (g0 + 1, d0)
    assert len(c.ox_body) == 1
    assert not [i for i in advancement.validate_xp(rs, c) if i.code == "xp-cost-mismatch"]
    advancement.undo_last(rs, c)
    assert validate.charm_slot_counts(rs, c)[:2] == (g0, d0)
    assert not c.ox_body


def test_alchemical_ox_body_dedicated_slot_when_caste_favored(rs):
    c = _locked_alch(rs)
    # Strain Resistant Chassis is Stamina-keyed; Stamina is Favored -> fits Dedicated.
    entry = advancement.learn_ox_body(rs, c, "two-minus-one", dedicated=True)
    assert entry.cost == 10


def test_chargen_ox_body_counts_against_slots(rs):
    from exalted_builder.models.character import OxBodyPurchase
    c = _alchemical()                         # Essence 2 -> cap 2 Ox-Body purchases
    c.general_charm_slots = 0
    c.dedicated_charm_slots = 1               # exactly one Slot
    pkg = dict(variant="three-minus-two", health_levels=[-2, -2, -2])
    c.ox_body = [OxBodyPurchase(**pkg)]       # one purchase fills the one Dedicated Slot
    assert not [i for i in validate.validate_chargen(rs, c) if i.code == "charm-exceeds-slots"]
    c.ox_body.append(OxBodyPurchase(**pkg))   # a second has no Slot to occupy
    assert [i for i in validate.validate_chargen(rs, c) if i.code == "charm-exceeds-slots"]


# --- Martial Arts via Perfected Lotus Matrix (CH3 p.100) -------------------- #

_PLM = "alchemical.close-combat.perfected-lotus-matrix"
_MA_ROOT = "abyssal.martial-arts.essence-discerning-glance"   # Hungry Ghost root, Celestial


def test_martial_arts_needs_perfected_lotus_matrix(rs):
    c = _locked_alch(rs)
    c.abilities[A.MARTIAL_ARTS] = 3
    with pytest.raises(advancement.AdvancementError, match="Perfected Lotus Matrix"):
        advancement.learn_martial_arts_charm(rs, c, _MA_ROOT)


def test_martial_arts_via_plm_costs_11_and_uses_no_slot(rs):
    c = _locked_alch(rs)
    c.abilities[A.MARTIAL_ARTS] = 3
    c.charms = [_PLM]                          # Perfected Lotus Matrix installed
    entry = advancement.learn_martial_arts_charm(rs, c, _MA_ROOT)
    assert entry.cost == 11
    assert _MA_ROOT in c.charms
    ma = rs.charms[_MA_ROOT]
    assert not validate.charm_occupies_slot(rs, c, ma)          # stored in the Matrix
    assert validate.charm_matches_splat(c, ma, rs)              # not flagged wrong-splat
    assert not [i for i in validate.check_splat_consistency(rs, c)
                if i.code == "charm-wrong-splat"]
    assert not [i for i in advancement.validate_xp(rs, c) if i.code == "xp-cost-mismatch"]
    advancement.undo_last(rs, c)
    assert _MA_ROOT not in c.charms


def test_no_perfected_lotus_matrix_no_ma_access(rs):
    # Removing PLM revokes the tier match, so the MA style is no longer the char's splat.
    c = _locked_alch(rs)
    ma = rs.charms[_MA_ROOT]
    assert not validate.charm_matches_splat(c, ma, rs)          # no PLM -> no access


# --- Eclipse/Moonshadow <-> Alchemical crossover (p.90) --------------------- #

_ALCH_STR = "alchemical.general.transitory-augmentation-of-strength"   # Alchemical, root


def _eclipse(xp=100):
    """A locked Solar Eclipse (post-lock -> the generalist rule is fully open) able to
    meet a Strength-keyed root Alchemical Charm's requirements."""
    c = Character(id="ecl", exalt_type="Solar", caste="eclipse")
    c.attributes[AT.STRENGTH] = 3
    c.abilities[A.ATHLETICS] = 2
    c.essence_rating = 2
    lifecycle.lock_chargen(c)
    c.xp_earned = xp
    return c


def test_eclipse_learning_alchemical_charm_grants_general_slot(rs):
    c = _eclipse()
    g0 = c.general_charm_slots or 0
    entry = advancement.learn_charm(rs, c, _ALCH_STR)
    assert entry.cost == 20                              # foreign: Solar new_charm 10 x2
    assert _ALCH_STR in c.charms
    assert (c.general_charm_slots or 0) == g0 + 1        # gained a General Slot (p.90)
    assert not [i for i in advancement.validate_xp(rs, c) if i.code == "xp-cost-mismatch"]
    advancement.undo_last(rs, c)
    assert _ALCH_STR not in c.charms
    assert (c.general_charm_slots or 0) == g0            # Slot given back


def test_eclipse_panoply_costs_8_and_uses_no_slot(rs):
    c = _eclipse()
    g0 = c.general_charm_slots or 0
    entry = advancement.learn_retainer_charm(rs, c, _ALCH_STR)
    assert entry.cost == 8                               # crossover Panoply rate (p.90)
    assert _ALCH_STR in c.retainer_charms and _ALCH_STR not in c.charms
    assert (c.general_charm_slots or 0) == g0            # no Slot gained
    assert not [i for i in advancement.validate_xp(rs, c) if i.code == "xp-cost-mismatch"]


def test_eclipse_panoply_rejects_non_alchemical_charm(rs):
    c = _eclipse()
    with pytest.raises(advancement.AdvancementError, match="Alchemical Charm"):
        advancement.learn_retainer_charm(rs, c, "solar.athletics.graceful-crane-stance")


def test_eclipse_still_cannot_learn_weaving_engine(rs):
    # The crossover does not widen the no_foreign_learning bar (weaving stays Alchemical).
    c = _eclipse()
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, _MAN_ENGINE)


def test_non_crossover_splat_cannot_use_panoply(rs):
    # A plain Dawn Solar has no Panoply mechanic at all.
    c = Character(id="dawn", exalt_type="Solar", caste="dawn")
    c.essence_rating = 2
    lifecycle.lock_chargen(c)
    c.xp_earned = 100
    with pytest.raises(advancement.AdvancementError, match="Alchemical mechanic"):
        advancement.learn_retainer_charm(rs, c, _ALCH_STR)
