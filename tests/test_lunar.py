"""Lunar chargen foundation: exercises the shipped Lunar data (exalts.json,
chargen_budgets.json, costs_bonus.json/costs_xp.json, the four Castes) and the
Attribute-keyed Charm machinery Lunars use instead of Ability-keyed Charms
(p.90-93, p.108, p.122), plus the shipped Charm cascades as they're authored
(Charms chapter, p.118-193) — one cascade at a time, tested as each lands.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import advancement, derive, lifecycle, validate
from exalted_builder.models.character import (AnimalForm, BeastmanGiftPurchase,
                                             Character, Combo)
from exalted_builder.models.rules import AbilityName as A
from exalted_builder.models.rules import AttributeName as AT
from exalted_builder.models.rules import VirtueName as V
from exalted_builder.models.rules import Charm, CharmType, SpellCircle
from exalted_builder.ui import view

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _codes(issues, code):
    return [i for i in issues if i.code == code]


def _lunar(caste="full-moon", origin="") -> Character:
    """A Full Moon (by default) Lunar that meets the Society ability minimums
    (Survival ●●, a combat Ability ●) and required-Favored rule (Survival)."""
    c = Character(id="lunar.test", exalt_type="Lunar", caste=caste, origin=origin)
    c.favored_abilities = [A.SURVIVAL, A.ATHLETICS, A.AWARENESS, A.DODGE, A.STEALTH]
    c.attributes.update({
        AT.STRENGTH: 5, AT.DEXTERITY: 5, AT.STAMINA: 4,        # Physical spend = 11
        AT.CHARISMA: 1, AT.MANIPULATION: 1, AT.APPEARANCE: 1,  # Social spend = 0
        AT.PERCEPTION: 3, AT.INTELLIGENCE: 1, AT.WITS: 1,      # Mental spend = 2
    })
    c.abilities.update({
        A.SURVIVAL: 2, A.MELEE: 1,                              # required minimums
        A.ATHLETICS: 1, A.AWARENESS: 1, A.DODGE: 1, A.STEALTH: 1,
    })
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 2, V.TEMPERANCE: 4, V.VALOR: 1})
    c.essence_rating = 2
    return c


def _maxed_lunar(caste="full-moon", origin="") -> Character:
    """A Lunar with every Attribute at 5 — for prerequisite-CHAIN sanity checks
    (does the whole cascade resolve?) where the point is graph correctness, not
    chargen-budget realism."""
    c = _lunar(caste=caste, origin=origin)
    c.attributes.update({a: 5 for a in AT})
    return c


def _attr_bp(rs, c) -> int:
    line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                if l.domain == "Attributes")
    return line.points


def _charm_bp(rs, c) -> int:
    line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                if l.domain == "Charms & Spells")
    return line.points


# --- shipped exalts.json row ------------------------------------------------ #

def test_lunar_exalt_definition(rs):
    ed = rs.exalt_for("Lunar")
    assert ed.tier == "Celestial"
    assert ed.essence.personal_essence_coeff == 1
    assert ed.essence.personal_willpower_coeff == 2
    assert ed.essence.peripheral_essence_coeff == 4
    assert ed.essence.peripheral_willpower_coeff == 2
    assert ed.essence.peripheral_virtue_mode == "highest"
    assert ed.essence.peripheral_virtue_coeff == 4
    assert ed.magic_track == "sorcery"
    assert ed.highest_magic_circle_id == "Celestial"


def test_lunar_bars_celestial_circle_sorcery_at_chargen(rs):
    # Lunars/Sidereals (Celestial Exalted) reach sorcery up to the Celestial Circle
    # and necromancy up to Shadowlands (rules-authority confirmed) — unlike Solar's
    # single-circle-track bar, this splat has TWO sorcery circles below the bar
    # (Terrestrial, Celestial), so barring the top one still leaves chargen sorcery
    # reachable, same shape as the Solar Circle bar.
    c = _lunar()
    assert validate.chargen_barred_circle(rs, c) == SpellCircle.CELESTIAL


def test_lunar_essence_pools_from_shipped_exalt(rs):
    c = _lunar()
    # WP = 6 (two highest: Temperance 4 + Compassion 3 = 7 -> wait, computed below).
    wp = derive.willpower(c)
    highest_virtue = max(c.virtues.values())
    assert (wp, highest_virtue) == (7, 4)          # WP = Temperance 4 + Compassion 3
    # Personal = Essence + WP*2 = 2 + 14 = 16; Peripheral = Essence*4 + WP*2 + highest*4
    assert derive.essence_pools(rs, c) == (2 + wp * 2, 2 * 4 + wp * 2 + highest_virtue * 4)


# --- shipped castes ---------------------------------------------------------- #

def test_lunar_castes_use_attributes_not_abilities(rs):
    fm = rs.castes["full-moon"]
    assert fm.caste_attributes == [AT.STRENGTH, AT.DEXTERITY, AT.STAMINA]
    assert fm.caste_abilities == []
    nm = rs.castes["no-moon"]
    assert nm.caste_attributes == [AT.PERCEPTION, AT.INTELLIGENCE, AT.WITS]
    casteless = rs.castes["casteless"]
    assert casteless.caste_attributes == [] and casteless.caste_abilities == []


# --- chargen budgets: Society vs Casteless ---------------------------------- #

def test_lunar_budget_society_vs_casteless(rs):
    society = rs.budgets_for("Lunar")
    casteless = rs.budgets_for("Lunar", "casteless")
    assert society.attribute_pools == (9, 7, 5)
    assert casteless.attribute_pools == (8, 6, 4)
    assert society.charm_count == 8 and casteless.charm_count == 6
    assert society.charm_min_caste_favored == 4 and casteless.charm_min_caste_favored == 0
    assert len(society.required_min_abilities) == 2
    assert casteless.required_min_abilities == []
    assert society.required_favored == [A.SURVIVAL] == casteless.required_favored


def test_lunar_bonus_costs(rs):
    bc = rs.bonus_costs_for("Lunar")
    assert (bc.attribute, bc.attribute_caste_favored) == (4, 3)
    assert (bc.charm, bc.charm_favored_caste) == (7, 5)


def test_lunar_xp_costs(rs):
    xc = rs.xp_costs_for("Lunar")
    assert (xc.new_charm, xc.new_charm_favored_caste) == (15, 12)
    # Solar untouched
    assert rs.xp_costs_for("Solar").new_charm == 10


# --- required Ability minimums (Society only) ------------------------------- #

def test_lunar_society_minimums_satisfied(rs):
    c = _lunar()
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") == []


def test_lunar_society_missing_survival_minimum_flagged(rs):
    c = _lunar()
    c.abilities[A.SURVIVAL] = 1                    # needs Survival ●●
    issues = _codes(validate.validate_chargen(rs, c), "required-min-ability")
    assert issues and issues[0].where == "survival"


def test_lunar_society_missing_combat_ability_flagged(rs):
    c = _lunar()
    c.abilities[A.MELEE] = 0                       # drop the only combat Ability
    issues = _codes(validate.validate_chargen(rs, c), "required-min-ability")
    assert len(issues) == 1
    assert issues[0].where != "survival"


def test_lunar_casteless_has_no_ability_minimums(rs):
    c = _lunar(caste="casteless", origin="casteless")
    c.abilities[A.SURVIVAL] = 0
    c.abilities[A.MELEE] = 0
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") == []


# --- required Favored (Survival always Favored) ----------------------------- #

def test_survival_must_be_favored(rs):
    c = _lunar()
    c.favored_abilities = [A.ATHLETICS, A.AWARENESS, A.DODGE, A.STEALTH, A.MELEE]  # no Survival
    issues = _codes(validate.validate_chargen(rs, c), "required-favored-ability")
    assert issues and issues[0].where == "survival"


# --- Casteless origin/caste coupling ---------------------------------------- #

def test_casteless_origin_and_caste_must_match(rs):
    c = _lunar(caste="casteless", origin="")        # Casteless caste, Society origin
    assert _codes(validate.validate(rs, c), "lunar-casteless-mismatch") != []
    c2 = _lunar(caste="full-moon", origin="casteless")  # Society caste, Casteless origin
    assert _codes(validate.validate(rs, c2), "lunar-casteless-mismatch") != []
    c3 = _lunar(caste="casteless", origin="casteless")
    assert _codes(validate.validate(rs, c3), "lunar-casteless-mismatch") == []
    c4 = _lunar(caste="full-moon", origin="")
    assert _codes(validate.validate(rs, c4), "lunar-casteless-mismatch") == []


# --- Attribute-category caste-favored BP discount --------------------------- #

def test_full_moon_gets_the_caste_discount_on_physical_overflow(rs):
    c = _lunar(caste="full-moon")           # Physical spend 11, pool 9 -> 2 overflow
    assert _attr_bp(rs, c) == 2 * 3          # attribute_caste_favored rate


def test_no_moon_pays_full_rate_for_the_same_physical_overflow(rs):
    c = _lunar(caste="no-moon")             # Mental is No Moon's favored category, not Physical
    assert _attr_bp(rs, c) == 2 * 4          # plain `attribute` rate


def test_casteless_has_no_attribute_discount_at_all(rs):
    c = _lunar(caste="casteless", origin="casteless")
    # Casteless pool is (8,6,4); spends sorted [11,2,0] -> overflow vs pools (8,6,4):
    # (11-8)=3, (2-6)<0, (0-4)<0 -> 3 dots over, all at the flat rate (no caste category).
    assert _attr_bp(rs, c) == 3 * 4


# --- Attribute-keyed ("min_attribute") Charm caste-favored-ness ------------- #

def _strength_charm(cid: str) -> Charm:
    return Charm(id=cid, name=cid, category="shapeshifting", exalt_type="Lunar",
                 min_attribute="strength", type=CharmType.SIMPLE, min_ability=1, min_essence=1)


def test_attribute_charm_favored_category_by_caste(rs):
    charm = _strength_charm("lunar.test.strength-charm")
    fm_cat = validate._caste_favored_attribute_category(rs, _lunar(caste="full-moon"))
    nm_cat = validate._caste_favored_attribute_category(rs, _lunar(caste="no-moon"))
    cl_cat = validate._caste_favored_attribute_category(
        rs, _lunar(caste="casteless", origin="casteless"))
    assert fm_cat == "Physical" and nm_cat == "Mental" and cl_cat is None
    # Strength (Physical) is caste-favored for Full Moon, not for No Moon or Casteless.
    assert validate._charm_attribute_caste_favored(charm, fm_cat) is True
    assert validate._charm_attribute_caste_favored(charm, nm_cat) is False
    assert validate._charm_attribute_caste_favored(charm, cl_cat) is False


def test_attribute_charm_discount_wired_into_bonus_point_breakdown(rs):
    # End-to-end: 8 filler non-Favored/non-Caste Charms (cost 7 each) fill the free
    # 8-Charm pool (the priciest picks are absorbed free); the 9th, Attribute-keyed
    # Strength Charm is Caste-favored for a Full Moon and is what's left to pay for,
    # so it must price at the discounted rate (5), not the plain one (7).
    charm = _strength_charm("lunar.test.strength-charm-bp")
    fillers = {
        f"lunar.test.filler-{i}": Charm(
            id=f"lunar.test.filler-{i}", name=f"filler-{i}", category="bureaucracy",
            exalt_type="Lunar", type=CharmType.SIMPLE, min_ability=1, min_essence=1)
        for i in range(8)
    }
    rs2 = rs.model_copy(update={"charms": {**rs.charms, charm.id: charm, **fillers}})
    c = _lunar(caste="full-moon")
    c.charms = [charm.id, *fillers.keys()]
    assert _charm_bp(rs2, c) == 5


# --- PlayState Renown/Face are ST-adjudicated, untouched by validation ------ #

def test_renown_and_face_do_not_enter_validation(rs):
    from exalted_builder.models.character import PlayState
    c = _lunar()
    c.play = PlayState(renown={"succor": 40, "mettle": 0, "cunning": 15, "glory": 5}, face=3)
    # Playing with Renown/Face must not perturb chargen or general validation.
    before = {i.code for i in validate.validate_chargen(rs, c)}
    c.play.renown["succor"] = 100
    after = {i.code for i in validate.validate_chargen(rs, c)}
    assert before == after


# --- shipped Shapeshifting cascade (real data, Charms p.118-132) ------------ #

def test_shipped_shapeshifting_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "shapeshifting"]
    assert len(charms) == 17
    for c in charms:
        assert c.min_attribute        # every Shapeshifting Charm is Attribute-keyed
        assert c.min_ability > 0 or c.id == "lunar.shapeshifting.finding-the-spirits-shape"


def test_shapeshifting_root_has_no_prerequisites(rs):
    root = rs.charms["lunar.shapeshifting.finding-the-spirits-shape"]
    assert root.prerequisites == []
    assert (root.min_attribute, root.min_ability) == ("charisma", 2)


def test_shapeshifting_ox_body_equivalent_charm_gates_charisma(rs):
    # Deadly Beastman Transformation is not repeatable (that's a Body Enhancement
    # Charm, not authored yet) — just confirm the prerequisite chain resolves and
    # its Attribute gate is Charisma, matching its place in the cascade.
    charm = rs.charms["lunar.shapeshifting.deadly-beastman-transformation"]
    assert charm.min_attribute == "charisma"
    assert charm.prerequisites == [["lunar.shapeshifting.finding-the-spirits-shape"]]


def test_preys_skin_disguise_requires_all_three_shape_charms(rs):
    # AND-of-OR with three single-id groups: all three are required (p.129 lists
    # them by comma with no "or" — the engine's flat-list convention is AND).
    charm = rs.charms["lunar.shapeshifting.preys-skin-disguise"]
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 3                            # Prey's Skin Disguise needs Essence 3
    c.charms = [
        "lunar.shapeshifting.finding-the-spirits-shape",
        "lunar.shapeshifting.towering-beast-form",
        "lunar.shapeshifting.humble-mouse-shape",
        "lunar.shapeshifting.shaping-the-ideal-form",
        # deliberately missing many-faced-moon-transformation
    ]
    assert validate.meets_charm_requirements(rs, c, charm) is False
    c.charms.append("lunar.shapeshifting.many-faced-moon-transformation")
    assert validate.meets_charm_requirements(rs, c, charm) is True
    c.charms.append(charm.id)
    assert validate.check_charm_prerequisites(rs, c) == []


def test_shapeshifting_charm_costs_from_the_page(rs):
    fss = rs.charms["lunar.shapeshifting.finding-the-spirits-shape"]
    assert fss.cost.motes == 1
    dbt = rs.charms["lunar.shapeshifting.deadly-beastman-transformation"]
    assert dbt.cost.motes == 5
    wlt = rs.charms["lunar.shapeshifting.wondrous-lunar-transformation"]
    assert (wlt.cost.motes, wlt.cost.willpower, wlt.cost.health) == (5, 1, 1)
    tbf = rs.charms["lunar.shapeshifting.towering-beast-form"]
    assert tbf.cost.motes == 0 and tbf.cost.raw == "None"


# --- shipped Body Enhancement cascade (real data, Charms p.132-136) --------- #

def test_shipped_body_enhancement_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "body_enhancement"]
    assert len(charms) == 11
    for c in charms:
        assert c.min_attribute


def test_lunar_ox_body_is_stamina_keyed_and_repeatable(rs):
    # Unlike Solar/DB/Abyssal (Endurance, an Ability), the Lunar Ox-Body-equivalent
    # Charm caps on Stamina — an ATTRIBUTE (p.132) — so ox_body_cap must resolve
    # AttributeName, not just AbilityName.
    ox = rs.charms["lunar.endurance.ox-body-technique"]
    assert ox.repeatable_cap_ability == "stamina"
    by_key = {v.key: v.health_levels for v in ox.variants}
    assert by_key == {"two-minus-one": [-1, -1], "four-minus-two": [-2, -2, -2, -2]}
    assert validate.ox_body_charm_id(rs, _lunar()) == "lunar.endurance.ox-body-technique"


def test_lunar_ox_body_cap_reads_stamina_attribute(rs):
    c = _lunar()
    c.attributes[AT.STAMINA] = 4
    assert validate.ox_body_cap(rs, c) == 4


def test_lunar_ox_body_caste_favored_via_attribute_category(rs):
    # Stamina is Physical -> Caste-favored for a Full Moon, not for a No Moon.
    fm_cat = validate._caste_favored_attribute_category(rs, _lunar(caste="full-moon"))
    nm_cat = validate._caste_favored_attribute_category(rs, _lunar(caste="no-moon"))
    ox = rs.charms["lunar.endurance.ox-body-technique"]
    assert validate._charm_attribute_caste_favored(ox, fm_cat) is True
    assert validate._charm_attribute_caste_favored(ox, nm_cat) is False


def test_body_enhancement_prerequisite_chain_resolves(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.shapeshifting.finding-the-spirits-shape",
        "lunar.shapeshifting.shaping-the-ideal-form",
        "lunar.body-enhancement.crouching-tiger-exercise",
        "lunar.body-enhancement.moonsilver-monkey-exercise",
        "lunar.body-enhancement.regaining-breath-exercise",
        "lunar.body-enhancement.breath-drinking-executioner-attack",
        "lunar.body-enhancement.predator-grace-method",
        "lunar.body-enhancement.panther-stride-stance",
        "lunar.body-enhancement.cat-falling-attitude",
        "lunar.body-enhancement.tree-dwelling-jaguar-claws",
        "lunar.body-enhancement.flying-tiger-technique",
        "lunar.body-enhancement.cat-paw-climbing-style",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


# --- shipped Unarmed Combat cascade (real data, Charms p.136-143) ----------- #

def test_shipped_unarmed_combat_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "unarmed_combat"]
    for c in charms:
        assert c.min_attribute


def test_unarmed_combat_root_has_no_prerequisites(rs):
    root = rs.charms["lunar.unarmed-combat.body-weapon-technique"]
    assert root.prerequisites == []
    assert (root.min_attribute, root.min_ability) == ("strength", 1)


def test_coiled_cobra_stance_requires_both_prerequisites(rs):
    # AND-of-OR with two single-id groups (p.137 lists them by comma, no "or").
    charm = rs.charms["lunar.unarmed-combat.coiled-cobra-stance"]
    assert charm.prerequisites == [
        ["lunar.unarmed-combat.snake-body-technique"],
        ["lunar.unarmed-combat.deadly-viper-strike"],
    ]
    c = _lunar(caste="full-moon")
    c.essence_rating = 3
    c.charms = [
        "lunar.unarmed-combat.body-weapon-technique",
        "lunar.unarmed-combat.sinuous-striking-grace",
        "lunar.unarmed-combat.snake-body-technique",
        # deliberately missing Deadly Viper Strike's own chain
    ]
    assert validate.meets_charm_requirements(rs, c, charm) is False
    c.charms += [
        "lunar.unarmed-combat.deadly-claw-blow",
        "lunar.unarmed-combat.adder-fang-method",
        "lunar.unarmed-combat.deadly-viper-strike",
    ]
    assert validate.meets_charm_requirements(rs, c, charm) is True


def test_unarmed_combat_iii_tentacle_branch_resolves(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.unarmed-combat.body-weapon-technique",
        "lunar.unarmed-combat.monkey-arm-style",
        "lunar.unarmed-combat.startling-tentacle-attack",
        "lunar.unarmed-combat.grasping-pseudopod-method",
        "lunar.unarmed-combat.tentacle-spear-strike",
        "lunar.unarmed-combat.weapon-snatching-coils",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


def test_lunar_ox_body_cap_reads_stamina_not_endurance_ability(rs):
    # Regression: Endurance (the Ability) sits unused at 0 for a Lunar; the cap
    # must come from Stamina, not silently resolve to 0 via the wrong trait.
    c = _lunar()
    c.abilities[A.ENDURANCE] = 0
    c.attributes[AT.STAMINA] = 3
    assert validate.ox_body_cap(rs, c) == 3


def test_shipped_unarmed_combat_cascade_grew_to_37(rs):
    # Unarmed Combat IV-VI (grappling, charging, and armor-defeating sub-trees)
    # extend the same "unarmed_combat" category, all still rooted at Body Weapon
    # Technique.
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "unarmed_combat"]
    assert len(charms) == 37
    roots = [c for c in charms if c.prerequisites == []]
    assert {c.id for c in roots} == {"lunar.unarmed-combat.body-weapon-technique"}


def test_body_breaking_kata_requires_both_prerequisites(rs):
    charm = rs.charms["lunar.unarmed-combat.body-breaking-kata"]
    assert charm.prerequisites == [
        ["lunar.unarmed-combat.bull-head-technique"],
        ["lunar.unarmed-combat.subduing-the-honored-foe"],
    ]


def test_grappling_and_armor_defeating_chains_resolve(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.unarmed-combat.body-weapon-technique",
        "lunar.unarmed-combat.bear-embrace-method",
        "lunar.unarmed-combat.spine-breaking-technique",
        "lunar.unarmed-combat.mighty-bear-crush",
        "lunar.unarmed-combat.throat-baring-hold",
        "lunar.unarmed-combat.hyena-jaw-technique",
        "lunar.unarmed-combat.cunning-porcupine-defense",
        "lunar.unarmed-combat.ossife-shard-shot",
        "lunar.unarmed-combat.angry-rhino-charge",
        "lunar.unarmed-combat.bull-head-technique",
        "lunar.unarmed-combat.subduing-the-honored-foe",
        "lunar.unarmed-combat.foot-confusing-buffet",
        "lunar.unarmed-combat.body-breaking-kata",
        "lunar.unarmed-combat.door-breaking-method",
        "lunar.unarmed-combat.hunters-eye-technique",
        "lunar.unarmed-combat.armor-rending-claw-fist",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


def test_throat_baring_hold_and_hyena_jaw_have_distinct_descriptions(rs):
    # Regression: an earlier draft accidentally duplicated Hyena Jaw Technique's
    # description onto Throat-Baring Hold (the source page prints Hyena Jaw's
    # body text above both headers, an unusual layout that's easy to misattribute).
    tbh = rs.charms["lunar.unarmed-combat.throat-baring-hold"]
    hjt = rs.charms["lunar.unarmed-combat.hyena-jaw-technique"]
    assert tbh.description != hjt.description
    assert "hold attack" in tbh.description
    assert "clamp his jaws" in hjt.description


# --- shipped Melee Combat cascade (real data, Charms p.149-156) ------------- #

def test_shipped_melee_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "melee"]
    assert len(charms) == 26
    for c in charms:
        assert c.min_attribute
    roots = [c for c in charms if c.prerequisites == []]
    assert {c.id for c in roots} == {"lunar.melee.sensing-the-deadly-flow"}


def test_insidious_moonsilver_shard_requires_both_prerequisites(rs):
    charm = rs.charms["lunar.melee.insidious-moonsilver-shard"]
    assert charm.prerequisites == [
        ["lunar.melee.surprising-moonsilver-deformation"],
        ["lunar.melee.deadly-moonsilver-affinity"],
    ]


def test_melee_cascade_prerequisite_chain_resolves(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.melee.sensing-the-deadly-flow",
        "lunar.melee.striking-mospid-method",
        "lunar.melee.ferocious-biting-sword",
        "lunar.melee.dance-of-the-living-blade",
        "lunar.melee.twisting-surprise-attack",
        "lunar.melee.irresistible-storm-attack",
        "lunar.melee.spinning-blade-attack",
        "lunar.melee.lightning-sword-method",
        "lunar.melee.dust-devil-advance",
        "lunar.melee.foe-driving-attack",
        "lunar.melee.monkey-paw-advantage",
        "lunar.melee.surprising-gibbon-attack",
        "lunar.melee.weapon-clutching-method",
        "lunar.melee.twisting-monkey-wrist",
        "lunar.melee.tiger-claw-swat",
        "lunar.melee.knowing-weapon-technique",
        "lunar.melee.scar-making-blow",
        "lunar.melee.ferocious-avalanche-technique",
        "lunar.melee.thunderclap-method",
        "lunar.melee.limb-maiming-flourish",
        "lunar.melee.weapon-fusion-method",
        "lunar.melee.weapon-shaping-prana",
        "lunar.melee.stunning-moonsilver-blow",
        "lunar.melee.surprising-moonsilver-deformation",
        "lunar.melee.deadly-moonsilver-affinity",
        "lunar.melee.insidious-moonsilver-shard",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


def test_melee_category_gates_on_attribute_not_melee_ability(rs):
    # Regression: "melee" is coincidentally also a valid AbilityName, so
    # min_attribute must take priority over the category-derived Ability check
    # — a Lunar Melee Charm gates on Dexterity/Strength/etc., never on the
    # character's Melee Ability rating, even though the two share a spelling.
    charm = rs.charms["lunar.melee.sensing-the-deadly-flow"]
    assert charm.min_attribute == "dexterity" and charm.min_ability == 2
    c = _lunar(caste="full-moon")
    c.abilities[A.MELEE] = 0            # Melee Ability irrelevant to this Charm
    c.attributes[AT.DEXTERITY] = 2      # meets the Attribute minimum exactly
    assert validate.meets_charm_requirements(rs, c, charm) is True
    c.attributes[AT.DEXTERITY] = 1
    assert validate.meets_charm_requirements(rs, c, charm) is False


# --- shipped Ranged Combat cascade (real data, Charms p.156-160) ------------ #

def test_shipped_ranged_combat_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "ranged_combat"]
    assert len(charms) == 17
    for c in charms:
        assert c.min_attribute
    roots = [c for c in charms if c.prerequisites == []]
    assert {c.id for c in roots} == {"lunar.ranged-combat.eagle-eye-advantage"}


def test_arrow_shaping_method_crosses_into_shapeshifting_cascade(rs):
    # A cross-category prerequisite: Arrow-Shaping Method needs a Shapeshifting
    # Charm (Shaping the Once-Living Form) AND a Ranged Combat one — the AND-of-OR
    # graph doesn't care which cascade file a prerequisite id lives in.
    charm = rs.charms["lunar.ranged-combat.arrow-shaping-method"]
    assert charm.prerequisites == [
        ["lunar.shapeshifting.shaping-the-once-living-form"],
        ["lunar.ranged-combat.natures-harmony-advantage"],
    ]
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.shapeshifting.finding-the-spirits-shape",
        "lunar.shapeshifting.shaping-the-ideal-form",
        "lunar.shapeshifting.lunar-blood-reshaping-technique",
        "lunar.shapeshifting.shaping-the-once-living-form",
        "lunar.ranged-combat.eagle-eye-advantage",
        "lunar.ranged-combat.natures-harmony-advantage",
        "lunar.ranged-combat.arrow-shaping-method",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


def test_ranged_combat_cascade_prerequisite_chain_resolves(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.ranged-combat.eagle-eye-advantage",
        "lunar.ranged-combat.natures-harmony-advantage",
        "lunar.ranged-combat.knowing-the-arrows-path",
        "lunar.ranged-combat.two-target-method",
        "lunar.ranged-combat.silver-waterfall-technique",
        "lunar.ranged-combat.rain-of-feathered-doom",
        "lunar.ranged-combat.skillful-ricochet-attack",
        "lunar.ranged-combat.finding-the-needles-eye",
        "lunar.ranged-combat.arrow-breaking-shot",
        "lunar.ranged-combat.wolf-eye-advantage",
        "lunar.ranged-combat.wind-wings-carry-technique",
        "lunar.ranged-combat.bow-bending-method",
        "lunar.ranged-combat.body-pinning-style",
        "lunar.ranged-combat.deadly-assassins-shot",
        "lunar.ranged-combat.lightning-stroke-attack",
        "lunar.ranged-combat.riding-the-secret-wind",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


# --- shipped Defensive cascade (real data, Charms p.161-167) ---------------- #

def test_shipped_defensive_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "defensive"]
    assert len(charms) == 21
    for c in charms:
        assert c.min_attribute
    # Three independent sub-trees (Defensive I/II/III), each its own root.
    roots = {c.id for c in charms if c.prerequisites == []}
    assert roots == {
        "lunar.defensive.steel-paw-style",
        "lunar.defensive.bowing-reed-technique",
        "lunar.defensive.hide-toughening-essence",
    }


def test_soak_boosting_defensive_charms_stay_text_only(rs):
    # Confirmed decision: Rugged Hide-style soak Charms (Hide-Toughening Essence,
    # Armor-Forming Technique, Scales of the Dragon, Invulnerable Moonsilver
    # Carapace) do NOT feed engine.derive.soak() — no splat's Charms do. Their
    # soak numbers live only in description text, same as every other splat's
    # combat-flavored Charms.
    c = _lunar(caste="full-moon")
    c.charms = [
        "lunar.defensive.hide-toughening-essence",
        "lunar.defensive.armor-forming-technique",
    ]
    before = derive.soak(c)
    c.charms.append("lunar.defensive.scales-of-the-dragon")
    after = derive.soak(c)
    assert before == after


def test_running_through_the_herd_requires_both_prerequisites(rs):
    charm = rs.charms["lunar.defensive.running-through-the-herd"]
    assert charm.prerequisites == [
        ["lunar.defensive.flowing-body-evasion"],
        ["lunar.defensive.pack-saving-method"],
    ]


def test_defensive_cascade_prerequisite_chain_resolves(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.defensive.steel-paw-style",
        "lunar.defensive.ground-denying-defense",
        "lunar.defensive.golden-tiger-block",
        "lunar.defensive.feline-guard-technique",
        "lunar.defensive.wary-swallow-method",
        "lunar.defensive.den-mother-method",
        "lunar.defensive.crouching-tiger-stance",
        "lunar.defensive.bowing-reed-technique",
        "lunar.defensive.bending-before-the-storm",
        "lunar.defensive.wind-dancing-method",
        "lunar.defensive.serpent-eye-defense",
        "lunar.defensive.unmoving-bear-defense",
        "lunar.defensive.foot-trapping-counter",
        "lunar.defensive.flowing-body-evasion",
        "lunar.defensive.pack-saving-method",
        "lunar.defensive.running-through-the-herd",
        "lunar.defensive.hide-toughening-essence",
        "lunar.defensive.armor-forming-technique",
        "lunar.defensive.limb-shielding-growth",
        "lunar.defensive.scales-of-the-dragon",
        "lunar.defensive.invulnerable-moonsilver-carapace",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


# --- shipped Survival and Healing cascade (real data, Charms p.168-173) ---- #

def test_shipped_survival_and_healing_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "survival_and_healing"]
    assert len(charms) == 22
    for c in charms:
        assert c.min_attribute
    roots = {c.id for c in charms if c.prerequisites == []}
    assert roots == {
        "lunar.survival-and-healing.beast-instinct-method",
        "lunar.survival-and-healing.pain-numbing-prana",
        "lunar.survival-and-healing.infection-resisting-method",
    }


def test_wolf_endurance_and_mothers_touch_require_both_prerequisites(rs):
    wolf = rs.charms["lunar.survival-and-healing.wolf-endurance-method"]
    assert wolf.prerequisites == [
        ["lunar.survival-and-healing.food-scenting-method"],
        ["lunar.survival-and-healing.water-providing-technique"],
    ]
    mothers = rs.charms["lunar.survival-and-healing.mothers-touch"]
    assert mothers.prerequisites == [
        ["lunar.survival-and-healing.halting-the-scarlet-flow"],
        ["lunar.survival-and-healing.lick-wound"],
    ]


def test_survival_and_healing_prerequisite_chain_resolves(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.survival-and-healing.beast-instinct-method",
        "lunar.survival-and-healing.whale-breath-technique",
        "lunar.survival-and-healing.gill-breathing-technique",
        "lunar.survival-and-healing.sealskin-endurance",
        "lunar.survival-and-healing.heat-adapting-method",
        "lunar.survival-and-healing.fire-walking-prana",
        "lunar.survival-and-healing.unerring-den-finding-sense",
        "lunar.survival-and-healing.food-scenting-method",
        "lunar.survival-and-healing.water-providing-technique",
        "lunar.survival-and-healing.wolf-endurance-method",
        "lunar.survival-and-healing.bear-sleep-technique",
        "lunar.survival-and-healing.fortitude-of-the-aurochs",
        "lunar.survival-and-healing.ever-waking-method",
        "lunar.survival-and-healing.pain-numbing-prana",
        "lunar.survival-and-healing.will-of-the-stoic-warrior",
        "lunar.survival-and-healing.lunas-fortitude",
        "lunar.survival-and-healing.infection-resisting-method",
        "lunar.survival-and-healing.disease-purging-essence",
        "lunar.survival-and-healing.bruise-relief-technique",
        "lunar.survival-and-healing.lick-wound",
        "lunar.survival-and-healing.halting-the-scarlet-flow",
        "lunar.survival-and-healing.mothers-touch",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


# --- shipped Perception cascade (real data, Charms p.174-181) ------------- #

def test_shipped_perception_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "perception"]
    assert len(charms) == 27
    for c in charms:
        assert c.min_attribute
    roots = {c.id for c in charms if c.prerequisites == []}
    assert roots == {"lunar.perception.sense-sharpening-change"}


def test_sense_borrowing_method_requires_both_prerequisites(rs):
    # Cross-tree: needs its own root (Sense-Sharpening Change) AND a charm from
    # the Interaction and Knowledge tree (Pack-Forming Presence, p.189) — two
    # separate AND groups, same shape as Harmony With Reality Technique's
    # cross-tree pull from Shapeshifting.
    charm = rs.charms["lunar.perception.sense-borrowing-method"]
    assert charm.prerequisites == [
        ["lunar.perception.sense-sharpening-change"],
        ["lunar.interaction-and-knowledge.pack-forming-presence"],
    ]


def test_perception_cascade_prerequisite_chain_resolves(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.perception.sense-sharpening-change",
        "lunar.interaction-and-knowledge.unspeaking-aura-of-dread",
        "lunar.interaction-and-knowledge.beast-calming-method",
        "lunar.interaction-and-knowledge.pack-forming-presence",
        "lunar.perception.sense-borrowing-method",
        "lunar.perception.heightened-sight-method",
        "lunar.perception.heightened-hearing-and-touch-method",
        "lunar.perception.heightened-smell-and-taste-method",
        "lunar.perception.ever-wary-fox-technique",
        "lunar.perception.observed-prey-instinct",
        "lunar.perception.weather-scenting-method",
        "lunar.perception.unerring-earth-direction-sense",
        "lunar.perception.moonsilver-scenting-sense",
        "lunar.perception.wyld-sensing-instincts",
        "lunar.perception.resisting-the-lure-of-madness",
        "lunar.perception.wyld-object-appraisal-method",
        "lunar.shapeshifting.finding-the-spirits-shape",
        "lunar.shapeshifting.towering-beast-form",
        "lunar.shapeshifting.humble-mouse-shape",
        "lunar.shapeshifting.shaping-the-ideal-form",
        "lunar.shapeshifting.many-faced-moon-transformation",
        "lunar.shapeshifting.preys-skin-disguise",
        "lunar.shapeshifting.lunar-blood-reshaping-technique",
        "lunar.shapeshifting.wondrous-lunar-transformation",
        "lunar.perception.harmony-with-reality-technique",
        "lunar.perception.ritual-of-lunar-stability",
        "lunar.perception.fish-eye-technique",
        "lunar.perception.night-is-day",
        "lunar.perception.perceiving-the-hidden-world",
        "lunar.perception.rabbit-ear-method",
        "lunar.perception.comprehending-ears-meditation",
        "lunar.perception.seeing-without-looking",
        "lunar.perception.calls-of-the-human-prey",
        "lunar.perception.feral-ears-metamorphosis",
        "lunar.perception.blood-kin-sense",
        "lunar.perception.blood-on-the-wind",
        "lunar.perception.emotion-revealing-scent",
        "lunar.perception.truth-scenting-method",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


# --- shipped Stealth cascade (real data, Charms p.182-183) ---------------- #

def test_shipped_stealth_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "stealth"]
    assert len(charms) == 6
    for c in charms:
        assert c.min_attribute
    roots = {c.id for c in charms if c.prerequisites == []}
    assert roots == {"lunar.stealth.stealthy-fox-method"}


def test_stealth_cascade_prerequisite_chain_resolves(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.stealth.stealthy-fox-method",
        "lunar.stealth.chameleon-skin-disguise",
        "lunar.stealth.object-concealing-method",
        "lunar.stealth.ally-concealing-method",
        "lunar.stealth.traceless-passage-technique",
        "lunar.stealth.track-sweeping-essence",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


# --- shipped Interaction and Knowledge cascade (real data, p.183-191) ----- #

def test_shipped_interaction_and_knowledge_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "interaction_and_knowledge"]
    assert len(charms) == 24
    for c in charms:
        assert c.min_attribute
    roots = {c.id for c in charms if c.prerequisites == []}
    assert roots == {
        "lunar.interaction-and-knowledge.tale-spinning-mastery",
        "lunar.interaction-and-knowledge.unspeaking-aura-of-dread",
        "lunar.interaction-and-knowledge.brotherhood-of-lake-and-river",
    }


def test_interaction_and_knowledge_cascade_prerequisite_chain_resolves(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.interaction-and-knowledge.tale-spinning-mastery",
        "lunar.interaction-and-knowledge.lore-speaking-method",
        "lunar.interaction-and-knowledge.divining-the-hidden-truth",
        "lunar.interaction-and-knowledge.lion-roar-method",
        "lunar.interaction-and-knowledge.wind-speaking-method",
        "lunar.interaction-and-knowledge.river-of-words",
        "lunar.interaction-and-knowledge.emotion-shaping-technique",
        "lunar.interaction-and-knowledge.crowd-inciting-method",
        "lunar.interaction-and-knowledge.crowd-calming-pronouncement",
        "lunar.interaction-and-knowledge.courage-building-address",
        "lunar.interaction-and-knowledge.glorious-battle-presence",
        "lunar.interaction-and-knowledge.foe-taunting-utterance",
        "lunar.interaction-and-knowledge.glib-tongue-technique",
        "lunar.interaction-and-knowledge.imposing-presence-attitude",
        "lunar.interaction-and-knowledge.fearful-lunar-form",
        "lunar.interaction-and-knowledge.mind-blanking-fear-technique",
        "lunar.interaction-and-knowledge.unspeaking-aura-of-dread",
        "lunar.interaction-and-knowledge.beast-calming-method",
        "lunar.interaction-and-knowledge.pack-forming-presence",
        "lunar.interaction-and-knowledge.attention-demanding-presence",
        "lunar.interaction-and-knowledge.animal-magnetism",
        "lunar.interaction-and-knowledge.brotherhood-of-lake-and-river",
        "lunar.interaction-and-knowledge.blood-singing-instincts",
        "lunar.interaction-and-knowledge.pack-calling-cry",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


# --- shipped Spirit cascade (real data, Charms p.191-192) ----------------- #

def test_shipped_spirit_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "spirit"]
    assert len(charms) == 4
    for c in charms:
        assert c.min_attribute
    roots = {c.id for c in charms if c.prerequisites == []}
    assert roots == {"lunar.spirit.spirit-scenting-technique"}


def test_spirit_cascade_prerequisite_chain_resolves(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.spirit.spirit-scenting-technique",
        "lunar.spirit.pulse-of-the-invisible",
        "lunar.spirit.devil-restraining-grip",
        "lunar.spirit.spirit-maiming-essence-attack",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


# --- shipped Sorcery cascade (real data, Charms p.192-193) ---------------- #

def test_shipped_sorcery_cascade_counts(rs):
    charms = [c for c in rs.charms.values()
              if c.exalt_type == "Lunar" and c.category == "sorcery"]
    assert len(charms) == 5
    for c in charms:
        assert c.min_attribute
    roots = {c.id for c in charms if c.prerequisites == []}
    assert roots == {
        "lunar.sorcery.form-fixing-method",
        "lunar.sorcery.terrestrial-circle-sorcery",
    }


def test_celestial_circle_sorcery_requires_both_prerequisites(rs):
    charm = rs.charms["lunar.sorcery.celestial-circle-sorcery"]
    assert charm.prerequisites == [
        ["lunar.sorcery.terrestrial-circle-sorcery"],
        ["lunar.sorcery.moonsilver-shaping-rite"],
    ]


def test_sorcery_cascade_prerequisite_chain_resolves(rs):
    c = _maxed_lunar(caste="full-moon")
    c.essence_rating = 4
    c.charms = [
        "lunar.sorcery.form-fixing-method",
        "lunar.sorcery.tattoo-cutting-wisdom",
        "lunar.sorcery.moonsilver-shaping-rite",
        "lunar.sorcery.terrestrial-circle-sorcery",
        "lunar.sorcery.celestial-circle-sorcery",
    ]
    assert validate.check_charm_prerequisites(rs, c) == []


def test_sorcery_charms_grant_expected_circles(rs):
    assert rs.charms["lunar.sorcery.terrestrial-circle-sorcery"].grants_circle == SpellCircle.TERRESTRIAL
    assert rs.charms["lunar.sorcery.celestial-circle-sorcery"].grants_circle == SpellCircle.CELESTIAL


# --- picker/view display of Attribute-keyed requirements -------------------- #

def test_charm_detail_shows_attribute_not_colliding_ability_name(rs):
    # lunar.melee.sensing-the-deadly-flow gates on Dexterity 2 (min_attribute),
    # not Melee 2 — its `category` ("melee") happens to also be a valid
    # AbilityName, which is exactly the collision build_charm_detail must not
    # fall into (see validate._min_trait_rating's docstring for the same trap).
    c = _lunar(caste="full-moon")
    detail = view.build_charm_detail(rs, c, "lunar.melee.sensing-the-deadly-flow")
    assert detail is not None
    assert "Dexterity 2" in detail.requirement
    assert "Melee" not in detail.requirement


def test_charm_detail_still_shows_ability_requirement_for_ability_keyed_charm(rs):
    # Sanity check the fix didn't break the ordinary Ability-keyed path (Solar
    # Charms have no min_attribute at all).
    c = _lunar(caste="full-moon")
    detail = view.build_charm_detail(rs, c, "solar.occult.terrestrial-circle-sorcery")
    assert detail is not None
    assert "Occult 3" in detail.requirement


# --- Lunar Combos (p.122) --------------------------------------------------- #

def test_two_native_attribute_charms_combo_freely(rs):
    # "A Lunar can place Charms associated with any of the different Attributes
    # into Combos without restriction" — no caste needed, just two Attribute
    # Charms of compatible type/duration.
    c = _lunar(caste="full-moon")
    c.charms = [
        "lunar.melee.sensing-the-deadly-flow",              # Supplemental, Dexterity
        "lunar.interaction-and-knowledge.imposing-presence-attitude",  # Supplemental, Charisma
    ]
    c.combos = [Combo(name="Test", charm_ids=list(c.charms))]
    codes = {i.code for i in validate.validate_combos(rs, c)}
    assert "combo-mixed-attribute-ability" not in codes


def test_lunar_cannot_mix_native_attribute_charm_with_a_celestial_martial_art(rs):
    # A No Moon can learn Five-Dragon Style (open_to_tiers: [Celestial], and
    # Lunar is a Celestial-tier splat) same as any other Celestial Exalt, but
    # that Charm is Ability-keyed (Martial Arts) — mixing it with a native
    # Attribute Charm in one Combo is the case p.122 reserves for Solar Eclipse
    # / Abyssal Moonshadow only, and Lunar castes aren't in that set.
    c = _lunar(caste="no-moon")
    c.charms = [
        "lunar.melee.sensing-the-deadly-flow",
        "dragonblooded.martial-arts.five-dragon-claw",
    ]
    c.combos = [Combo(name="Test", charm_ids=list(c.charms))]
    codes = {i.code for i in validate.validate_combos(rs, c)}
    assert "combo-mixed-attribute-ability" in codes


# --- Deadly Beastman Transformation Gifts (p.124-127) ----------------------- #

def _locked_lunar(caste="full-moon", xp=200, essence=2) -> Character:
    c = _lunar(caste=caste)
    c.essence_rating = essence
    lifecycle.lock_chargen(c)
    c.xp_earned = xp
    return c


def test_gift_charm_shape(rs):
    charm = rs.charms["lunar.shapeshifting.deadly-beastman-transformation"]
    assert charm.repeatable_cap_ability == "essence"
    assert charm.variant_picks_first_purchase == 2
    assert charm.variant_picks_per_purchase == 1
    assert len(charm.variants) == 19
    assert validate.gift_charm_id(rs, _lunar()) == charm.id
    assert validate.gift_charm(rs, _lunar()).id == charm.id


def test_gift_repeat_caps(rs):
    charm = rs.charms["lunar.shapeshifting.deadly-beastman-transformation"]
    by_key = {v.key: v.max_purchases for v in charm.variants}
    assert by_key["bestial-reflexes"] == 2
    assert by_key["enhanced-senses"] == 2
    # Lightning Speed does NOT repeat, unlike an earlier (wrong) draft claimed.
    assert by_key["lightning-speed"] == 1
    assert by_key["horrifying-might"] == 1


def test_gift_prerequisite_chain(rs):
    charm = rs.charms["lunar.shapeshifting.deadly-beastman-transformation"]
    by_key = {v.key: v.prerequisites for v in charm.variants}
    assert by_key["spider-foot-climbing"] == [["bestial-reflexes", "lightning-speed"]]
    assert by_key["glue-foot-climbing"] == [["spider-foot-climbing"]]
    assert by_key["arm-array"] == [["gift-of-hands"]]
    assert by_key["wound-knitting-power"] == [["resilience-of-nature"]]
    assert by_key["terrifying-bestial-visage"] == [["fearsome-appearance"]]
    assert by_key["impenetrable-beast-armor"] == [["rugged-hide"]]
    assert by_key["deadly-breath"] == [["poison-bite"]]
    assert by_key["ghost-sight"] == [["enhanced-senses"]]
    assert by_key["savage-moonsilver-talons"] == [["terrible-beast-claws"]]
    roots = {k for k, p in by_key.items() if not p}
    assert roots == {
        "horrifying-might", "bestial-reflexes", "lightning-speed", "gift-of-hands",
        "terrible-beast-claws", "resilience-of-nature", "fearsome-appearance",
        "rugged-hide", "poison-bite", "enhanced-senses",
    }


def test_gift_purchase_cap_reads_essence(rs):
    c = _lunar()
    c.essence_rating = 3
    assert validate.gift_purchase_cap(rs, c) == 3


def test_gifts_per_purchase_first_then_steady(rs):
    charm = rs.charms["lunar.shapeshifting.deadly-beastman-transformation"]
    assert validate.gifts_per_purchase(charm, 0) == 2
    assert validate.gifts_per_purchase(charm, 1) == 1
    assert validate.gifts_per_purchase(charm, 4) == 1


def test_learn_gift_first_purchase_grants_two_and_costs_charm_xp(rs):
    c = _locked_lunar()
    entry = advancement.learn_gift(rs, c, ["bestial-reflexes", "gift-of-hands"])
    assert len(c.beastman_gifts) == 1
    assert c.beastman_gifts[0].gifts == ["bestial-reflexes", "gift-of-hands"]
    # Charisma (Deadly Beastman Transformation's min_attribute) is Physical for
    # Full Moon -> NOT Caste-favored (Full Moon favors Physical, Charisma is
    # Social) -> full new_charm rate.
    assert entry.cost == rs.xp_costs_for("Lunar").new_charm


def test_learn_gift_wrong_count_raises(rs):
    c = _locked_lunar()
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_gift(rs, c, ["bestial-reflexes"])   # first purchase needs 2


def test_learn_gift_missing_prerequisite_raises(rs):
    c = _locked_lunar()
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_gift(rs, c, ["glue-foot-climbing", "gift-of-hands"])


def test_learn_gift_prerequisite_satisfied_within_same_purchase(rs):
    # p.124: a purchase's Gifts are all applied together, so a Gift may satisfy
    # another Gift's prerequisite from within the SAME purchase.
    c = _locked_lunar()
    entry = advancement.learn_gift(rs, c, ["bestial-reflexes", "spider-foot-climbing"])
    assert c.beastman_gifts[0].gifts == ["bestial-reflexes", "spider-foot-climbing"]
    assert entry.cost > 0


def test_learn_gift_over_repeat_cap_raises(rs):
    c = _locked_lunar(essence=4)
    advancement.learn_gift(rs, c, ["bestial-reflexes", "gift-of-hands"])
    advancement.learn_gift(rs, c, ["bestial-reflexes"])       # 2nd Bestial Reflexes: OK
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_gift(rs, c, ["bestial-reflexes"])   # 3rd: over max_purchases


def test_learn_gift_over_essence_cap_raises(rs):
    c = _locked_lunar(essence=2)
    advancement.learn_gift(rs, c, ["bestial-reflexes", "gift-of-hands"])
    advancement.learn_gift(rs, c, ["resilience-of-nature"])
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_gift(rs, c, ["rugged-hide"])        # 3rd exceeds Essence 2


def test_undo_gift_removes_last_purchase_and_refunds(rs):
    c = _locked_lunar()
    advancement.learn_gift(rs, c, ["bestial-reflexes", "gift-of-hands"])
    before = advancement.xp_available(c)
    advancement.learn_gift(rs, c, ["resilience-of-nature"])
    advancement.undo_last(rs, c)
    assert [p.gifts for p in c.beastman_gifts] == [["bestial-reflexes", "gift-of-hands"]]
    assert advancement.xp_available(c) == before


def test_gift_purchases_pass_the_xp_audit(rs):
    c = _locked_lunar()
    advancement.learn_gift(rs, c, ["bestial-reflexes", "gift-of-hands"])
    codes = {i.code for i in advancement.validate_xp(rs, c)}
    assert "xp-cost-mismatch" not in codes and "xp-overspent" not in codes


def test_check_beastman_gifts_flags_over_cap_wrong_count_and_bad_variant(rs):
    c = _lunar()
    c.essence_rating = 1
    c.beastman_gifts = [
        BeastmanGiftPurchase(gifts=["bestial-reflexes", "gift-of-hands"]),
        BeastmanGiftPurchase(gifts=["nope"]),                 # over cap AND bad variant
    ]
    codes = {i.code for i in validate.check_beastman_gifts(rs, c)}
    assert "beastman-gift-over-cap" in codes
    assert "beastman-gift-bad-variant" in codes


def test_check_beastman_gifts_flags_wrong_pick_count(rs):
    c = _lunar()
    c.essence_rating = 3
    c.beastman_gifts = [BeastmanGiftPurchase(gifts=["bestial-reflexes"])]  # needs 2
    codes = {i.code for i in validate.check_beastman_gifts(rs, c)}
    assert "beastman-gift-wrong-count" in codes


def test_lunar_attribute_charm_gets_favored_caste_xp_discount(rs):
    # Regression for the costs.charm_cost bug found while wiring Gifts: it only
    # checked category-as-Ability, so every Lunar Charm was always charged the
    # full (non-favored) rate. A Full Moon's Caste Attributes are Physical, and
    # lunar.melee.sensing-the-deadly-flow gates on Dexterity (Physical) -> should
    # get the favored-caste discount.
    from exalted_builder.engine import costs
    c = _locked_lunar(caste="full-moon")
    charm = rs.charms["lunar.melee.sensing-the-deadly-flow"]
    assert costs.charm_cost(rs, c, charm) == rs.xp_costs_for("Lunar").new_charm_favored_caste
    c2 = _locked_lunar(caste="no-moon")
    assert costs.charm_cost(rs, c2, charm) == rs.xp_costs_for("Lunar").new_charm


def test_lunar_xp_essence_and_caste_attribute_from_shipped_table(rs):
    """Lunar XP costs (splatbook p.251): Essence current x9 (not the x8 default),
    and a Caste Attribute costs (current x4) - 1 while a non-Caste Attribute is the
    flat x4. A Full Moon's Caste Attributes are Physical (Str/Dex/Sta)."""
    from exalted_builder.engine import costs
    c = _locked_lunar(caste="full-moon")
    assert costs.essence_step(rs, c, 3) == 27                     # 3 x 9
    assert costs.attribute_step(rs, c, 3, AT.STRENGTH) == 11      # Caste Attribute: 3 x 4 - 1
    assert costs.attribute_step(rs, c, 3, AT.CHARISMA) == 12      # non-Caste: 3 x 4
    # Casteless has no Caste Attributes, so nothing gets the discount.
    cl = _lunar(caste="casteless", origin="casteless")
    assert costs.attribute_step(rs, cl, 3, AT.STRENGTH) == 12


def test_lunar_spell_xp_is_per_circle_with_no_moon_discount(rs):
    """Lunar spell XP (p.251): Terrestrial 12, Celestial 15, each −2 for a No Moon
    caste. The discount is caste-based, NOT the Occult-Caste/Favoured axis, so a
    non-No-Moon Lunar pays full even with Occult favoured."""
    from exalted_builder.engine import costs
    terr = next(s for s in rs.spells.values() if s.circle == SpellCircle.TERRESTRIAL)
    cel = next(s for s in rs.spells.values() if s.circle == SpellCircle.CELESTIAL)
    no_moon = _lunar(caste="no-moon")
    assert costs.spell_cost(rs, no_moon, terr) == 10        # 12 − 2
    assert costs.spell_cost(rs, no_moon, cel) == 13         # 15 − 2
    full_moon = _lunar(caste="full-moon")
    full_moon.favored_abilities = [A.OCCULT, A.SURVIVAL, A.ATHLETICS, A.AWARENESS, A.DODGE]
    assert costs.spell_cost(rs, full_moon, terr) == 12      # no No-Moon discount despite Occult favoured
    assert costs.spell_cost(rs, full_moon, cel) == 15


def test_gift_charm_graph_node_state_tracks_beastman_gifts_not_charms(rs):
    # Mirrors ox_body's graph-node special case (view.build_charm_graph): the
    # Gift-granting Charm's node state must read character.beastman_gifts, not
    # character.charms, since a purchase never lands in the latter.
    c = _lunar(caste="full-moon")
    c.attributes[AT.CHARISMA] = 2           # Deadly Beastman Transformation needs Charisma 2
    c.charms = ["lunar.shapeshifting.finding-the-spirits-shape"]
    gift_id = "lunar.shapeshifting.deadly-beastman-transformation"
    graph = view.build_charm_graph(rs, c, "shapeshifting")
    node = next(n for n in graph.nodes if n.id == gift_id)
    assert node.state == "available"
    c.beastman_gifts = [BeastmanGiftPurchase(gifts=["bestial-reflexes", "gift-of-hands"])]
    graph = view.build_charm_graph(rs, c, "shapeshifting")
    node = next(n for n in graph.nodes if n.id == gift_id)
    assert node.state == "owned"


def test_body_enhancement_graph_pulls_in_cross_category_prerequisites(rs):
    # The Lunars p.132/p.135 draw Body Enhancement as three separate trees, all
    # rooted in Shapeshifting's Finding the Spirit's Shape -> Shaping the Ideal
    # Form, and the sourcebook's own diagram boxes include those two foreign
    # Charms. Before this, build_charm_graph dropped every out-of-category
    # prerequisite edge, so the three branch roots had no parent AND no
    # prerequisite-free status either: Cytoscape got a pile of disconnected
    # nodes and laid the whole category out as one long line.
    c = _lunar(caste="full-moon")
    graph = view.build_charm_graph(rs, c, "body_enhancement")

    external = {n.id for n in graph.nodes if n.external}
    assert external == {"lunar.shapeshifting.finding-the-spirits-shape",
                        "lunar.shapeshifting.shaping-the-ideal-form"}

    edges = set(graph.edges)
    shaping = "lunar.shapeshifting.shaping-the-ideal-form"
    assert ("lunar.shapeshifting.finding-the-spirits-shape", shaping) in edges
    # the three branch roots hanging off Shaping the Ideal Form (p.132, p.135)
    for branch in ("crouching-tiger-exercise", "moonsilver-monkey-exercise",
                   "predator-grace-method", "tree-dwelling-jaguar-claws"):
        assert (shaping, f"lunar.body-enhancement.{branch}") in edges

    # Only genuinely parentless nodes are layout roots now; every in-category
    # Charm except Ox-Body (which has no prerequisite at all) hangs off something.
    assert set(graph.roots) == {"lunar.endurance.ox-body-technique",
                                "lunar.shapeshifting.finding-the-spirits-shape"}


def test_charm_graph_marks_only_foreign_charms_external(rs):
    # A category with no cross-tree prerequisites must be unchanged: no external
    # nodes, and its roots are exactly its prerequisite-free Charms.
    graph = view.build_charm_graph(rs, _lunar(caste="full-moon"), "unarmed_combat")
    assert not [n for n in graph.nodes if n.external]
    assert set(graph.roots) == {c.id for c in rs.charms.values()
                                if c.category == "unarmed_combat" and not c.prerequisites}


def test_lunar_ability_roster_is_not_grouped_by_caste(rs):
    # The Lunars p.90: "Lunars have no Caste Abilities, and Abilities are not
    # divided along caste lines" — their castes carry caste_attributes instead.
    # Grouping the Ability roster by caste therefore produced NOTHING for a Lunar,
    # leaving the editor's Abilities panel and the sheet's Abilities block blank.
    # They fall back to the default War / Life / Wisdom grouping printed on the
    # canonical 1e Lunar sheet (images/Lunar/character sheet.png).
    groups = view.ability_group_defs(rs, "Lunar")
    assert [label for label, _ in groups] == ["War", "Life", "Wisdom"]
    assert [len(abilities) for _, abilities in groups] == [10, 10, 5]
    listed = [a for _, abilities in groups for a in abilities]
    assert sorted(listed, key=lambda a: a.value) == sorted(A, key=lambda a: a.value)
    assert A.MARTIAL_ARTS in dict(groups)["War"]
    assert A.CRAFT in dict(groups)["Life"]
    assert A.OCCULT in dict(groups)["Wisdom"]

    rows = view.build_sheet_view(rs, _lunar(caste="full-moon")).ability_groups
    assert [label for label, _ in rows] == ["War", "Life", "Wisdom"]
    assert sum(len(r) for _, r in rows) >= len(list(A))


def test_ability_caste_splats_still_group_by_caste(rs):
    groups = view.ability_group_defs(rs, "Solar")
    assert [label for label, _ in groups] == ["Dawn", "Zenith", "Twilight", "Night", "Eclipse"]
    assert all(len(abilities) == 5 for _, abilities in groups)


def test_form_library_is_free_form_and_never_validated(rs):
    # The Form Library is a narrative record (Totem + the animal shapes taken), not
    # a rated trait: no cost, no cap, no reference into the RuleSet. It must not
    # affect chargen legality or the XP audit at all.
    c = _lunar(caste="full-moon")
    before = [i.code for i in validate.validate(rs, c)]
    before_chargen = [i.code for i in validate.validate_chargen(rs, c)]

    c.totem = "Grey Wolf"
    c.animal_forms = [AnimalForm(name="Grey Wolf", notes="totem; taken at the Silver Pact"),
                      AnimalForm(name="Hawk"), AnimalForm(name="River Otter")]

    assert [i.code for i in validate.validate(rs, c)] == before
    assert [i.code for i in validate.validate_chargen(rs, c)] == before_chargen

    locked = _locked_lunar(caste="full-moon")
    locked.totem = "Tiger"
    locked.animal_forms = [AnimalForm(name="Tiger")]
    assert not [i for i in advancement.validate_xp(rs, locked) if i.code == "xp-overspend"]


def test_form_library_round_trips_and_old_saves_default_it(tmp_path):
    from exalted_builder import persistence
    c = _lunar(caste="changing-moon")
    c.totem = "Raven"
    c.animal_forms = [AnimalForm(name="Raven", notes="messenger form")]
    path = tmp_path / "f.character.json"
    persistence.save_character(c, path)
    back = persistence.load_character(path)
    assert back.totem == "Raven"
    assert [(f.name, f.notes) for f in back.animal_forms] == [("Raven", "messenger form")]

    # a save written before the Form Library existed still loads
    legacy = Character(id="old", name="Old", exalt_type="Lunar", caste="no-moon")
    assert legacy.totem == "" and legacy.animal_forms == []


def test_form_library_is_data_gated_to_splats_that_have_one(rs):
    # ui/picker offers the Form Library page off ExaltDefinition.form_library, so a
    # later shapeshifting splat opts in as data rather than by a code change.
    assert rs.exalt_for("Lunar").form_library is True
    for other in ("Solar", "Dragon-Blooded", "Abyssal"):
        assert rs.exalt_for(other).form_library is False


def test_sheet_view_exposes_the_form_library(rs):
    c = _lunar(caste="full-moon")
    c.totem = "Snow Leopard"
    c.animal_forms = [AnimalForm(name="Snow Leopard"), AnimalForm(name="Ibex", notes="mountain")]
    sv = view.build_sheet_view(rs, c)
    assert sv.totem == "Snow Leopard"
    assert sv.animal_forms == [("Snow Leopard", ""), ("Ibex", "mountain")]


def test_sheet_lists_beastman_gift_purchases_as_charm_rows(rs):
    # Regression: Deadly Beastman Transformation lives on character.beastman_gifts,
    # not character.charms, so the sheet's `for cid in character.charms` loop skipped
    # it entirely — a bought DBT simply did not appear. Ox-Body already had this
    # special case; the Gift Charm needs the identical one.
    c = _lunar(caste="full-moon")
    c.attributes[AT.CHARISMA] = 2
    c.charms = ["lunar.shapeshifting.finding-the-spirits-shape"]
    assert not [r for r in view.build_sheet_view(rs, c).charms
                if "Beastman" in r.name]

    c.beastman_gifts = [BeastmanGiftPurchase(gifts=["bestial-reflexes", "gift-of-hands"]),
                        BeastmanGiftPurchase(gifts=["lightning-speed"])]
    rows = [r for r in view.build_sheet_view(rs, c).charms if "Beastman" in r.name]
    assert len(rows) == 2                      # one row per PURCHASE, not per Gift
    assert "Bestial Reflexes" in rows[0].name and "Gift of Hands" in rows[0].name
    assert "Lightning Speed" in rows[1].name


def test_xp_log_labels_a_gift_purchase_by_its_gifts(rs):
    # The XP-log presenter had no beastman_gifts branch, so a bought DBT showed the
    # raw target string ("beastman_gifts") instead of a readable label.
    c = _locked_lunar(caste="full-moon")
    c.attributes[AT.CHARISMA] = 2
    c.charms = ["lunar.shapeshifting.finding-the-spirits-shape"]
    c.xp_earned = 100
    advancement.learn_gift(rs, c, ["bestial-reflexes", "gift-of-hands"])
    label = view.build_xp_log(rs, c)[-1].label
    assert label != "beastman_gifts"
    assert "Bestial Reflexes" in label and "Gift of Hands" in label
