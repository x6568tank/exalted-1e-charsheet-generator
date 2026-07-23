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
from exalted_builder.engine import advancement, derive, lifecycle, validate
from exalted_builder.models.character import Array, Character, SubmodulePurchase
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
    c.backgrounds = []
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


def _maxed_alchemical(rs) -> Character:
    """An Alchemical with every Attribute at 5, high Essence, Martial Arts 2, who
    knows every Alchemical Charm — for prerequisite-CHAIN sanity (does the whole
    cascade resolve?), not chargen-budget realism. Essence 10 clears even municipal
    (Essence 8+) Charm minimums."""
    c = _alchemical()
    c.attributes.update({a: 5 for a in AT})
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
