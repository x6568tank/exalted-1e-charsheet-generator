"""Tests for engine.validate.validate_chargen — the chargen budget predicates and
bonus-point accounting (Exalted 1e core pp.104-105).

Centre of gravity is a fully-built, *legal* Dawn Solar that spends exactly its
free budgets and zero bonus points; the illegal cases each perturb one rule.
"""

import pytest

from exalted_builder.engine import validate
from exalted_builder.models.character import (
    BackgroundEntry,
    Character,
    ChargenSnapshot,
    Combo,
    Specialty,
)
from exalted_builder.models.rules import (
    AbilityName,
    AttributeName,
    CasteDefinition,
    Charm,
    CharmType,
    RuleSet,
    Spell,
    SpellCircle,
    VirtueName,
)

A = AbilityName
AT = AttributeName
V = VirtueName


def _ruleset() -> RuleSet:
    castes = {
        "dawn": CasteDefinition(
            id="dawn", label="Dawn",
            caste_abilities=[A.ARCHERY, A.BRAWL, A.MARTIAL_ARTS, A.MELEE, A.THROWN],
        ),
    }
    # Ten Charms: five in Caste/Favoured abilities, five not.
    cats = ["melee", "archery", "awareness", "dodge", "athletics",   # caste/favoured
            "lore", "occult", "survival", "medicine", "craft"]       # other
    charms = {
        f"c-{cat}": Charm(id=f"c-{cat}", name=cat.title(), category=cat,
                          type=CharmType.SIMPLE, min_ability=1, min_essence=1)
        for cat in cats
    }
    spells = {
        "s-terr": Spell(id="s-terr", name="Terrestrial Spell", circle=SpellCircle.TERRESTRIAL),
        "s-cele": Spell(id="s-cele", name="Celestial Spell", circle=SpellCircle.CELESTIAL),
        "s-solar": Spell(id="s-solar", name="Solar Spell", circle=SpellCircle.SOLAR),
    }
    return RuleSet(castes=castes, charms=charms, spells=spells)


def _legal_solar() -> Character:
    c = Character(id="char.legal", caste="dawn")
    c.favored_abilities = [A.AWARENESS, A.DODGE, A.ATHLETICS, A.RESISTANCE, A.ENDURANCE]

    # Attributes: Physical +8, Social +6, Mental +4 (all over a base of 1).
    c.attributes.update({
        AT.STRENGTH: 5, AT.DEXTERITY: 4, AT.STAMINA: 2,        # Physical = 8
        AT.CHARISMA: 4, AT.MANIPULATION: 3, AT.APPEARANCE: 2,  # Social = 6
        AT.PERCEPTION: 3, AT.INTELLIGENCE: 2, AT.WITS: 2,      # Mental = 4
    })

    # Abilities: 25 dots, 18 Caste/Favoured, 7 other; none above 3.
    c.abilities.update({
        A.MELEE: 3, A.ARCHERY: 3, A.BRAWL: 1, A.MARTIAL_ARTS: 1, A.THROWN: 1,   # caste 9
        A.AWARENESS: 3, A.DODGE: 3, A.ATHLETICS: 1, A.RESISTANCE: 1, A.ENDURANCE: 1,  # fav 9
        A.LORE: 3, A.OCCULT: 2, A.SURVIVAL: 2,                                   # other 7
    })

    c.backgrounds = [
        BackgroundEntry(name="Artifact", rating=3),
        BackgroundEntry(name="Manse", rating=2),
        BackgroundEntry(name="Resources", rating=2),
    ]
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 1})

    c.charms = [f"c-{cat}" for cat in
                ["melee", "archery", "awareness", "dodge", "athletics",
                 "lore", "occult", "survival", "medicine", "craft"]]
    c.essence_rating = 2
    return c


def _errors(issues):
    return [i for i in issues if i.severity == "error"]


def _bp(issues):
    info = next(i for i in issues if i.code == "bonus-points")
    return info.message


# --------------------------------------------------------------------------- #
# The legal baseline
# --------------------------------------------------------------------------- #

def test_legal_solar_spends_no_bonus_points():
    rs, c = _ruleset(), _legal_solar()
    issues = validate.validate_chargen(rs, c)
    assert _errors(issues) == []
    assert "0 of 15" in _bp(issues)


def test_ox_body_purchase_counts_as_an_extra_charm_pick():
    rs, c = _ruleset(), _legal_solar()
    # 10 Charm picks already fill the free pool; an Ox-Body purchase is an 11th pick
    # gated on Endurance (Favoured here) -> the cheapest extra costs 4 BP.
    from exalted_builder.models.character import OxBodyPurchase
    c.ox_body = [OxBodyPurchase(variant="one-zero", health_levels=[0])]
    assert "4 of 15" in _bp(validate.validate_chargen(rs, c))


# --------------------------------------------------------------------------- #
# Favoured-ability rules
# --------------------------------------------------------------------------- #

def test_favored_must_number_five():
    rs, c = _ruleset(), _legal_solar()
    c.favored_abilities = c.favored_abilities[:4]
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "favored-count" in codes


def test_favored_may_not_overlap_caste():
    rs, c = _ruleset(), _legal_solar()
    c.favored_abilities = [A.MELEE, A.DODGE, A.ATHLETICS, A.RESISTANCE, A.ENDURANCE]
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "favored-overlaps-caste" in codes


def test_favored_ability_needs_a_dot():
    rs, c = _ruleset(), _legal_solar()
    c.abilities[A.ENDURANCE] = 0          # a Favoured ability left at zero
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "favored-needs-dot" in codes


# --------------------------------------------------------------------------- #
# Bonus-point spend breakdown (the chargen BP-spend log)
# --------------------------------------------------------------------------- #

def _line(bd, domain):
    return next(line.points for line in bd.lines if line.domain == domain)


def test_breakdown_is_all_zero_for_the_legal_baseline():
    rs, c = _ruleset(), _legal_solar()
    bd = validate.bonus_point_breakdown(rs, c)
    assert bd.total == 0 and not bd.over_budget
    assert all(line.points == 0 for line in bd.lines)
    assert {line.domain for line in bd.lines} == {
        "Attributes", "Abilities", "Backgrounds", "Virtues", "Charms & Spells",
        "Combos", "Specialties", "Willpower", "Essence",
    }


def test_breakdown_total_matches_validate_info_message():
    rs, c = _ruleset(), _legal_solar()
    c.attributes[AT.STAMINA] = 4          # Physical now +10 vs an 8 pool -> 2 over @4 BP
    bd = validate.bonus_point_breakdown(rs, c)
    assert _line(bd, "Attributes") == 8   # 2 dots over the pool, 4 BP each
    assert bd.total == 8
    assert "8 of 15" in _bp(validate.validate_chargen(rs, c))


def test_breakdown_isolates_per_domain_spend():
    rs, c = _ruleset(), _legal_solar()
    c.essence_rating = 3                  # one dot of Essence over the start of 2 -> 7 BP
    bd = validate.bonus_point_breakdown(rs, c)
    assert _line(bd, "Essence") == 7
    assert _line(bd, "Attributes") == 0
    assert bd.total == 7


# --------------------------------------------------------------------------- #
# Ability / Charm Caste-Favoured minimums
# --------------------------------------------------------------------------- #

def test_ten_ability_dots_must_be_caste_favored():
    rs, c = _ruleset(), _legal_solar()
    # Move dots off Caste/Favoured abilities so fewer than 10 remain there.
    c.abilities.update({A.MELEE: 0, A.ARCHERY: 0, A.AWARENESS: 0, A.DODGE: 0})
    c.abilities.update({A.LORE: 3, A.OCCULT: 3, A.SURVIVAL: 3, A.MEDICINE: 2})
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "ability-caste-favored-min" in codes


def test_five_charms_must_be_caste_favored():
    rs, c = _ruleset(), _legal_solar()
    # Swap a Caste/Favoured Charm for another non-Caste/Favoured one.
    c.charms = [f"c-{cat}" for cat in
                ["melee", "archery", "awareness", "dodge",            # only 4 c/f
                 "lore", "occult", "survival", "medicine", "craft", "c-extra-occult"]]
    rs.charms["c-extra-occult"] = Charm(id="c-extra-occult", name="X", category="occult",
                                        type=CharmType.SIMPLE, min_ability=1, min_essence=1)
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "charm-caste-favored-min" in codes


# --------------------------------------------------------------------------- #
# Spells at chargen (core p.100): a spell takes a Charm pick (1:1), costs the
# same as a Charm in BP, gets the in-caste discount when Occult is Caste/Favoured,
# and no Solar Circle spells may be taken at creation.
# --------------------------------------------------------------------------- #

def test_spell_swapped_for_a_charm_stays_in_budget():
    rs, c = _ruleset(), _legal_solar()
    # Drop a (non-Caste/Favoured) Charm and take a spell in its place: 9 + 1 = 10.
    c.charms = c.charms[:-1]
    c.spells = ["s-terr"]
    issues = validate.validate_chargen(rs, c)
    assert _errors(issues) == []
    assert "0 of 15" in _bp(issues)


def test_eleventh_pick_as_spell_consumes_the_charm_pool():
    rs, c = _ruleset(), _legal_solar()
    # Ten Charms plus a spell = 11 picks; one extra is paid from the shared pool.
    # Cheapest-first (as for Charms) charges it at the Caste/Favoured rate: 4 BP.
    c.spells = ["s-terr"]
    issues = validate.validate_chargen(rs, c)
    assert _errors(issues) == []
    assert "4 of 15" in _bp(issues)


def test_solar_circle_spell_forbidden_at_chargen():
    rs, c = _ruleset(), _legal_solar()
    c.charms = c.charms[:-1]
    c.spells = ["s-solar"]
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "spell-top-circle-chargen" in codes


def test_spell_counts_toward_caste_favored_minimum_when_occult_favored():
    rs, c = _ruleset(), _legal_solar()
    c.favored_abilities = [A.OCCULT, A.DODGE, A.ATHLETICS, A.RESISTANCE, A.ENDURANCE]
    c.abilities[A.OCCULT] = 1             # favoured ability needs a dot
    # Only 4 Caste/Favoured *Charms* (melee, archery, dodge, athletics), plus one
    # Occult spell -> 5 Caste/Favoured picks, meeting the minimum.
    c.charms = [f"c-{cat}" for cat in
                ["melee", "archery", "dodge", "athletics",
                 "lore", "survival", "medicine", "craft", "awareness"]]
    c.spells = ["s-terr"]
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "charm-caste-favored-min" not in codes


def test_spell_does_not_count_for_minimum_when_occult_not_favored():
    rs, c = _ruleset(), _legal_solar()
    # Four Caste/Favoured Charms + an Occult spell (Occult not Caste/Favoured here)
    # -> only 4 Caste/Favoured picks, so the minimum is unmet.
    c.charms = [f"c-{cat}" for cat in
                ["melee", "archery", "dodge", "athletics",
                 "lore", "survival", "medicine", "craft", "occult"]]
    c.spells = ["s-terr"]
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "charm-caste-favored-min" in codes


# --------------------------------------------------------------------------- #
# Combos (core p.213): starting with a Combo costs BP = its number of Charms
# --------------------------------------------------------------------------- #

def test_combo_costs_one_bonus_point_per_charm():
    rs, c = _ruleset(), _legal_solar()
    c.combos = [Combo(name="Flurry", charm_ids=["c-melee", "c-archery", "c-awareness"])]
    issues = validate.validate_chargen(rs, c)
    assert "3 of 15" in _bp(issues)         # 3 Charms -> 3 BP


def test_combos_from_snapshot_when_locked():
    rs, c = _ruleset(), _legal_solar()
    snap = ChargenSnapshot(
        attributes=dict(c.attributes), abilities=dict(c.abilities),
        virtues=dict(c.virtues), specialties=[], backgrounds=list(c.backgrounds),
        charms=list(c.charms), spells=[],
        combos=[Combo(name="Frozen", charm_ids=["c-melee", "c-archery"])],
        essence_rating=2, willpower_purchased=0, wp_virtue_component=6,
    )
    c.chargen_snapshot = snap
    c.combos = []                            # current is empty; the snapshot is the source
    assert "2 of 15" in _bp(validate.validate_chargen(rs, c))


# --------------------------------------------------------------------------- #
# Bonus-point accounting
# --------------------------------------------------------------------------- #

def test_attribute_overspend_costs_four_bp_each():
    rs, c = _ruleset(), _legal_solar()
    c.attributes[AT.STAMINA] = 3          # Physical spend 8 -> 9, one dot over the 8 pool
    issues = validate.validate_chargen(rs, c)
    assert _errors(issues) == []
    assert "4 of 15" in _bp(issues)       # 1 over-pool attribute dot * 4


def test_bonus_points_exceeded_is_flagged():
    rs, c = _ruleset(), _legal_solar()
    c.essence_rating = 5                  # (5-2)*7 = 21 bonus points
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "bonus-points-exceeded" in codes


# --------------------------------------------------------------------------- #
# Specialties (p.105: 1 BP/dot; Caste/Favoured get 2 dots per BP)
# --------------------------------------------------------------------------- #

def test_non_caste_favored_specialty_is_full_price():
    rs, c = _ruleset(), _legal_solar()
    c.specialties = [Specialty(ability=A.LORE, name="Histories", rating=2)]  # not c/f
    assert "2 of 15" in _bp(validate.validate_chargen(rs, c))    # 2 dots * 1 BP


def test_caste_favored_specialty_is_half_price():
    rs, c = _ruleset(), _legal_solar()
    c.specialties = [Specialty(ability=A.MELEE, name="Swords", rating=2)]    # caste, 2 dots
    assert "1 of 15" in _bp(validate.validate_chargen(rs, c))    # 2 dots / 2 per point


def test_caste_favored_specialty_rounds_up():
    rs, c = _ruleset(), _legal_solar()
    c.specialties = [Specialty(ability=A.AWARENESS, name="Ambush", rating=3)]  # favoured, 3 dots
    assert "2 of 15" in _bp(validate.validate_chargen(rs, c))    # ceil(3/2)


def test_caste_favored_specialty_dots_pool_before_rounding():
    rs, c = _ruleset(), _legal_solar()
    # Two 1-dot Caste/Favoured specialties -> 2 dots pooled -> 1 BP together.
    c.specialties = [
        Specialty(ability=A.MELEE, name="Swords", rating=1),
        Specialty(ability=A.AWARENESS, name="Ambush", rating=1),
    ]
    assert "1 of 15" in _bp(validate.validate_chargen(rs, c))


# --------------------------------------------------------------------------- #
# Willpower start cap
# --------------------------------------------------------------------------- #

def test_purchased_willpower_above_eight_needs_two_high_virtues():
    rs, c = _ruleset(), _legal_solar()
    # Two highest Virtues = 6; buy 3 Willpower -> 9, but no Virtue is >= 4.
    c.willpower_purchased = 3
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "willpower-start-cap" in codes


def test_willpower_above_eight_allowed_with_two_high_virtues():
    rs, c = _ruleset(), _legal_solar()
    # Raise two Virtues to 4 (costs BP) so the cap exception applies.
    c.virtues.update({V.COMPASSION: 4, V.CONVICTION: 4, V.TEMPERANCE: 1, V.VALOR: 1})
    c.willpower_purchased = 1             # two highest = 8, +1 = 9, exception met
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "willpower-start-cap" not in codes


# --------------------------------------------------------------------------- #
# Snapshot source-of-truth
# --------------------------------------------------------------------------- #

def test_locked_snapshot_is_validated_not_current_traits():
    rs, c = _ruleset(), _legal_solar()
    # Current traits are legal, but the frozen snapshot has illegal Essence.
    c.chargen_snapshot = ChargenSnapshot(
        attributes=dict(c.attributes), abilities=dict(c.abilities),
        virtues=dict(c.virtues), specialties=[], backgrounds=list(c.backgrounds),
        charms=list(c.charms), spells=[], essence_rating=5,
        willpower_purchased=0, wp_virtue_component=6,
    )
    codes = {i.code for i in _errors(validate.validate_chargen(rs, c))}
    assert "essence-below-start" not in codes
    assert "bonus-points-exceeded" in codes      # essence 5 -> 21 BP, from the snapshot
