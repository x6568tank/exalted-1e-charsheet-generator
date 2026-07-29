"""The generalist rule — Solar Eclipse (core p.127) and Abyssal Moonshadow
(Abyssals p.146), which print it in the same words.

    "Finally, the Eclipse Caste Solars are talented generalists. Provided they
    have a willing tutor, they may learn the Charms of other types of Exalted,
    and even of spirits. Such Charms cost double the normal experience to learn
    (usually 20 points) and use. Eclipse Caste characters may not start the game
    knowing the Charms of other such beings without Storyteller permission."

    "Also, Abyssals of the Moonshadow Caste are talented generalists. Provided
    they have willing tutors, they may learn the Charms of other types of Exalted
    and even of spirits (including ghosts). Such Charms cost double the normal
    experience to learn (usually 20 points) and use. Moonshadow Caste characters
    may not start the game knowing the Charms of other such beings without the
    Storyteller's permission."

Modelled as data, not a caste check in code: `CasteDefinition.foreign_charms` +
`foreign_charm_xp_multiplier`. That paid off — the Moonshadow half (2026-07-29)
was three keys in castes.json and ZERO engine, UI or pricing changes; every
Moonshadow test below reaches the same code paths as its Eclipse twin. The
chargen half of the rule is `Character.house_rules.st_foreign_charms` (it moved
onto HouseRules when the Storyteller options were gathered; a legacy top-level
`st_foreign_charms` key is still migrated forward on load).

Rules-authority calls baked in here (see CLAUDE.md):
  * Full Caste/Favored treatment — the discount applies FIRST, then the doubling.
  * The other splat's *internal* gates (the DB Dragon-Path enlightenment pair) do
    NOT bind a foreign learner; ordinary prerequisites and trait minimums do.
  * Chargen pricing is unchanged: a foreign Charm takes a Charm pick, or normal
    bonus points. Only the XP economy doubles.
  * The doubled cost "to use" (motes) is play-time math and is not modelled.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import advancement, costs, validate
from exalted_builder.models.character import Character, HouseRules
from exalted_builder.models.rules import AbilityName, AttributeName
from exalted_builder.ui import view as viewmod

DATA_DIR = Path(exalted_builder.__file__).parent / "data"

# A Dragon-Blooded Charm with no prerequisites, and an Abyssal one, to learn as a
# foreigner. A Solar Charm and the Celestial-tier Hungry Ghost style act as the
# "native, must not double" controls.
_HUNGRY_GHOST = "abyssal.martial-arts.essence-discerning-glance"
_SOLAR_MELEE = "solar.melee.fire-and-stones-strike"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _eclipse(**kw) -> Character:
    c = Character(id="x", exalt_type="Solar", caste="eclipse", essence_rating=5, **kw)
    c.abilities = {a: 5 for a in AbilityName}
    return c


def _dawn() -> Character:
    c = Character(id="x", exalt_type="Solar", caste="dawn", essence_rating=5)
    c.abilities = {a: 5 for a in AbilityName}
    return c


def _moonshadow(**kw) -> Character:
    c = Character(id="x", exalt_type="Abyssal", caste="moonshadow", essence_rating=5, **kw)
    c.abilities = {a: 5 for a in AbilityName}
    # Attributes too: the nearest foreign splat to reach for is Lunar, whose Charms
    # gate on min_attribute rather than min_ability.
    c.attributes = {a: 5 for a in AttributeName}
    return c


def _dusk() -> Character:
    """The Abyssal control: same splat, no generalist privilege."""
    c = Character(id="x", exalt_type="Abyssal", caste="dusk", essence_rating=5)
    c.abilities = {a: 5 for a in AbilityName}
    return c


def _foreign_charm(rs, splat: str):
    """A prerequisite-free Charm of `splat` whose trait minimums a maxed sheet meets."""
    for c in sorted(rs.charms.values(), key=lambda c: c.id):
        if c.exalt_type == splat and not c.prerequisites and not c.open_to_tiers \
                and not c.open_to_all and not c.variants:
            return c
    raise AssertionError(f"no rootless {splat} Charm in the data set")


# --- the data ---------------------------------------------------------------- #

def test_only_the_two_generalist_castes_carry_the_privilege(rs):
    """Eclipse (core p.127) and its Abyssal mirror the Moonshadow (Abyssals p.146,
    read from `images/Abyssal/Traits/145-146.png`): "Abyssals of the Moonshadow Caste
    are talented generalists … Such Charms cost double the normal experience to learn
    (usually 20 points) and use. Moonshadow Caste characters may not start the game
    knowing the Charms of other such beings without the Storyteller's permission." —
    word for word the same rule, so it is the same two data fields and no new code."""
    for cid in ("eclipse", "moonshadow"):
        assert rs.castes[cid].foreign_charms is True, cid
        assert rs.castes[cid].foreign_charm_xp_multiplier == 2, cid
        # Autochthonians p.90 names both castes for the Panoply crossover rate.
        assert rs.castes[cid].foreign_panoply_charm_xp == 8, cid
    for cid, caste in rs.castes.items():
        if cid not in ("eclipse", "moonshadow"):
            assert caste.foreign_charms is False, cid


# --- who may learn what ------------------------------------------------------ #

def test_dawn_cannot_reach_another_splats_charms(rs):
    char = _dawn()
    db = _foreign_charm(rs, "Dragon-Blooded")
    assert validate.foreign_charms_open(rs, char) is False
    assert validate.charm_learnable_by_splat(rs, char, db) is False


def test_eclipse_needs_st_permission_before_the_lock(rs):
    char = _eclipse()
    db = _foreign_charm(rs, "Dragon-Blooded")
    assert validate.foreign_charms_open(rs, char) is False
    assert validate.charm_learnable_by_splat(rs, char, db) is False

    char.house_rules = HouseRules(st_foreign_charms=True)
    assert validate.foreign_charms_open(rs, char) is True
    assert validate.charm_learnable_by_splat(rs, char, db) is True


def test_permission_is_moot_after_the_lock(rs):
    """Post-lock the rule asks only for a willing tutor, which is narrative."""
    char = _eclipse(chargen_locked=True)
    assert validate.foreign_charms_permitted(char) is False
    assert validate.foreign_charms_open(rs, char) is True


def test_unpermitted_foreign_charm_is_its_own_issue_not_wrong_splat(rs):
    char = _eclipse()
    char.charms = [_foreign_charm(rs, "Abyssal").id]
    codes = {i.code for i in validate.check_splat_consistency(rs, char)}
    assert codes == {"charm-foreign-no-st-permission"}

    char.house_rules = HouseRules(st_foreign_charms=True)
    assert validate.check_splat_consistency(rs, char) == []


def test_non_eclipse_still_gets_charm_wrong_splat(rs):
    char = _dawn()
    char.charms = [_foreign_charm(rs, "Abyssal").id]
    codes = {i.code for i in validate.check_splat_consistency(rs, char)}
    assert codes == {"charm-wrong-splat"}


# --- pricing ----------------------------------------------------------------- #

def test_foreign_charm_costs_double(rs):
    """p.127's "usually 20 points" — the undiscounted Solar rate is 10. Compared
    against the XP table rather than another character, because a Dawn's own Caste
    Abilities would discount the same Charm and hide the multiplier."""
    char = _eclipse(chargen_locked=True)
    xp = rs.xp_costs_for("Solar")
    db = _foreign_charm(rs, "Dragon-Blooded")
    assert AbilityName(db.category) not in validate.caste_favored_abilities(rs, char)
    assert costs.charm_cost(rs, char, db) == xp.new_charm * 2 == 20
    # ...and a native Charm is untouched by the privilege.
    assert costs.charm_cost(rs, char, rs.charms[_SOLAR_MELEE]) == xp.new_charm


def test_caste_favored_discount_applies_before_the_doubling(rs):
    """Full C/F treatment: discount first, multiplier last. Socialize is an Eclipse
    caste Ability, so a foreign Socialize-keyed Charm is 8 x 2, not 10 x 2."""
    char = _eclipse(chargen_locked=True)
    xp = rs.xp_costs_for("Solar")
    assert xp.new_charm_favored_caste < xp.new_charm      # the discount is real
    foreign_favored = next(
        c for c in rs.charms.values()
        if c.exalt_type == "Abyssal" and c.category == AbilityName.SOCIALIZE.value)
    assert costs.charm_cost(rs, char, foreign_favored) == xp.new_charm_favored_caste * 2


def test_cross_tier_style_is_native_and_never_doubles(rs):
    """Hungry Ghost Style is nominally Abyssal but open to every Celestial, so an
    Eclipse learns it natively at the ordinary price — the exact case that made
    is_foreign_charm take the RuleSet."""
    char = _eclipse(chargen_locked=True)
    hg = rs.charms[_HUNGRY_GHOST]
    assert validate.is_foreign_charm(rs, char, hg) is False
    # Martial Arts is not an Eclipse Caste Ability, so the undiscounted rate, once.
    assert costs.charm_cost(rs, char, hg) == rs.xp_costs_for("Solar").new_charm


# --- buying it --------------------------------------------------------------- #

def test_advancement_buys_a_foreign_charm_at_the_doubled_price(rs):
    char = _eclipse(chargen_locked=True, xp_earned=100)
    db = _foreign_charm(rs, "Dragon-Blooded")
    entry = advancement.learn_charm(rs, char, db.id)
    assert db.id in char.charms
    assert entry.cost == costs.charm_cost(rs, char, db) == rs.xp_costs_for("Solar").new_charm * 2


def test_advancement_refuses_a_foreign_charm_for_a_dawn(rs):
    char = _dawn()
    char.chargen_locked, char.xp_earned = True, 100
    db = _foreign_charm(rs, "Dragon-Blooded")
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, char, db.id)


def test_db_dragon_path_gate_does_not_bind_a_foreign_learner(rs):
    """Rules-authority call: the other splat's internal gates do not follow the
    Charm. A Dragon-Blooded needs Spirit Sight + Spirit Walking before any elemental
    Dragon style opens; an Eclipse with a tutor does not."""
    char = _eclipse(chargen_locked=True, xp_earned=200)
    dragon_style = next(
        c for c in sorted(rs.charms.values(), key=lambda c: c.id)
        if validate._is_dragon_path_style(c.category) and not c.prerequisites)
    assert validate.category_available(rs, char, dragon_style.category) is True
    assert validate.meets_charm_requirements(rs, char, dragon_style) is True
    advancement.learn_charm(rs, char, dragon_style.id)


# --- the picker's splat pages ------------------------------------------------ #

def test_splat_page_filter_leaves_the_native_page_identical(rs):
    """The native page must be exactly charm_matches_splat, for every character —
    otherwise adding the dropdown silently changes every existing splat's picker."""
    for char in (_dawn(), _eclipse(st_foreign_charms=True)):
        for c in rs.charms.values():
            assert viewmod.charm_on_splat_page(rs, char, c, "") is \
                validate.charm_matches_splat(char, c, rs)
            assert viewmod.charm_on_splat_page(rs, char, c, char.exalt_type) is \
                validate.charm_matches_splat(char, c, rs)


def test_foreign_page_is_empty_without_the_privilege(rs):
    char = _eclipse()          # no ST permission yet
    assert not any(viewmod.charm_on_splat_page(rs, char, c, "Lunar")
                   for c in rs.charms.values())


def test_foreign_page_shows_that_splats_charms_and_no_duplicates(rs):
    char = _eclipse(st_foreign_charms=True)
    on_abyssal = [c for c in rs.charms.values()
                  if viewmod.charm_on_splat_page(rs, char, c, "Abyssal")]
    assert on_abyssal
    assert all(c.exalt_type == "Abyssal" for c in on_abyssal)
    # Hungry Ghost Style is Abyssal-authored but sits on the Eclipse's NATIVE page;
    # it must not also appear on the Abyssal page.
    assert _HUNGRY_GHOST not in {c.id for c in on_abyssal}


def test_foreign_graph_is_that_splats_tree_only(rs):
    char = _eclipse(st_foreign_charms=True)
    graph = viewmod.build_charm_graph(rs, char, "melee", "Abyssal")
    assert graph.nodes
    assert all(n.id.startswith("abyssal.") for n in graph.nodes)
    # ...and the same category on the native page is untouched.
    native = viewmod.build_charm_graph(rs, char, "melee")
    assert all(n.id.startswith("solar.") for n in native.nodes)


def test_charm_detail_flags_a_foreign_charm(rs):
    char = _eclipse(st_foreign_charms=True)
    db = _foreign_charm(rs, "Dragon-Blooded")
    assert viewmod.build_charm_detail(rs, char, db.id).foreign_splat == "Dragon-Blooded"
    assert viewmod.build_charm_detail(rs, char, _SOLAR_MELEE).foreign_splat == ""


# --- the Abyssal mirror: Moonshadow Caste (Abyssals p.146) ------------------- #
# Every rule below is the Eclipse's, reached through the same code paths with no
# Abyssal branch anywhere — which is the point of modelling it as caste data.

def test_moonshadow_needs_st_permission_before_the_lock(rs):
    char = _moonshadow()
    lunar = _foreign_charm(rs, "Lunar")
    assert validate.foreign_charms_open(rs, char) is False
    assert validate.charm_learnable_by_splat(rs, char, lunar) is False

    char.house_rules = HouseRules(st_foreign_charms=True)
    assert validate.foreign_charms_open(rs, char) is True
    assert validate.charm_learnable_by_splat(rs, char, lunar) is True


def test_dusk_cannot_reach_another_splats_charms(rs):
    """The privilege is the Moonshadow's, not the Abyssals'."""
    char = _dusk()
    assert validate.foreign_charms_open(rs, char) is False
    assert validate.charm_learnable_by_splat(rs, char, _foreign_charm(rs, "Lunar")) is False


def test_moonshadow_foreign_charm_costs_double(rs):
    """p.146's "double the normal experience to learn (usually 20 points)" — the
    undiscounted Abyssal rate is 10, so a foreign Charm outside the caste's Abilities
    is 20, and a native Abyssal Charm is untouched."""
    char = _moonshadow(chargen_locked=True)
    xp = rs.xp_costs_for("Abyssal")
    lunar = _foreign_charm(rs, "Lunar")
    assert costs.charm_cost(rs, char, lunar) == xp.new_charm * 2 == 20
    native = next(c for c in sorted(rs.charms.values(), key=lambda c: c.id)
                  if c.exalt_type == "Abyssal" and c.category == AbilityName.MELEE.value)
    assert costs.charm_cost(rs, char, native) == xp.new_charm


def test_moonshadow_caste_discount_applies_before_the_doubling(rs):
    """Same ordering as the Eclipse: discount first, multiplier last. Socialize is a
    Moonshadow Caste Ability."""
    char = _moonshadow(chargen_locked=True)
    xp = rs.xp_costs_for("Abyssal")
    foreign_favored = next(
        c for c in sorted(rs.charms.values(), key=lambda c: c.id)
        if c.exalt_type == "Solar" and c.category == AbilityName.SOCIALIZE.value)
    assert costs.charm_cost(rs, char, foreign_favored) == xp.new_charm_favored_caste * 2


def test_advancement_buys_a_foreign_charm_for_a_moonshadow(rs):
    char = _moonshadow(chargen_locked=True, xp_earned=100)
    lunar = _foreign_charm(rs, "Lunar")
    entry = advancement.learn_charm(rs, char, lunar.id)
    assert lunar.id in char.charms
    assert entry.cost == rs.xp_costs_for("Abyssal").new_charm * 2


def test_unpermitted_foreign_charm_is_its_own_issue_for_a_moonshadow(rs):
    char = _moonshadow()
    char.charms = [_foreign_charm(rs, "Lunar").id]
    assert {i.code for i in validate.check_splat_consistency(rs, char)} == \
        {"charm-foreign-no-st-permission"}
    char.house_rules = HouseRules(st_foreign_charms=True)
    assert validate.check_splat_consistency(rs, char) == []


def test_moonshadow_gets_the_alchemical_panoply_crossover_rate(rs):
    """Autochthonians p.90 names both generalist castes, so the Panoply path (add the
    Alchemical Charm to the Panoply instead of taking a General Slot with it) prices
    at the flat 8 for a Moonshadow exactly as for an Eclipse."""
    char = _moonshadow(chargen_locked=True)
    alchemical = _foreign_charm(rs, "Alchemical")
    assert validate.crossover_alchemical_charm(rs, char, alchemical) is True
    assert validate.crossover_panoply_xp(rs, char) == 8
    # ...and the other path (take the Charm with a General Slot) is still the
    # doubled rate, so the Panoply rate is an alternative and not a replacement.
    assert costs.charm_cost(rs, char, alchemical) == rs.xp_costs_for("Abyssal").new_charm * 2


def test_the_picker_offers_a_moonshadow_the_foreign_splat_pages(rs):
    char = _moonshadow(st_foreign_charms=True)
    on_solar = [c for c in rs.charms.values()
                if viewmod.charm_on_splat_page(rs, char, c, "Solar")]
    assert on_solar and all(c.exalt_type == "Solar" for c in on_solar)
    assert viewmod.build_charm_detail(
        rs, char, _SOLAR_MELEE).foreign_splat == "Solar"
