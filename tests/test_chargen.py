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
    MeritFlaw,
    Specialty,
)
from exalted_builder.models.rules import (
    AbilityName,
    AttributeName,
    Caste,
    CasteDefinition,
    Charm,
    CharmType,
    RuleSet,
    VirtueName,
)

A = AbilityName
AT = AttributeName
V = VirtueName


def _ruleset() -> RuleSet:
    castes = {
        Caste.DAWN: CasteDefinition(
            caste=Caste.DAWN,
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
    return RuleSet(castes=castes, charms=charms)


def _legal_solar() -> Character:
    c = Character(id="char.legal", caste=Caste.DAWN)
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
# Merits & Flaws (Player's Guide): Merits cost BP, Flaws grant BP up to 10
# --------------------------------------------------------------------------- #

def test_merit_costs_bonus_points():
    rs, c = _ruleset(), _legal_solar()
    c.merits_flaws = [MeritFlaw(name="Quick", points=3, is_flaw=False)]
    assert "3 of 15" in _bp(validate.validate_chargen(rs, c))


def test_flaw_grants_bonus_points():
    rs, c = _ruleset(), _legal_solar()
    c.merits_flaws = [MeritFlaw(name="Nightmares", points=4, is_flaw=True)]
    assert "0 of 19" in _bp(validate.validate_chargen(rs, c))   # 15 + 4 from the flaw


def test_flaw_credit_is_capped_at_ten():
    rs, c = _ruleset(), _legal_solar()
    c.merits_flaws = [MeritFlaw(name="Cursed", points=15, is_flaw=True)]
    issues = validate.validate_chargen(rs, c)
    assert any(i.code == "flaw-credit-capped" for i in issues)
    assert "0 of 25" in _bp(issues)                             # 15 + capped 10


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
