"""Tests for engine.validate — reference integrity, Charm prerequisites, and
spell-circle access. RuleSets are built inline from the models (no data files).
"""

from exalted_builder.engine import validate
from exalted_builder.models.character import Character
from exalted_builder.models.rules import (
    AbilityName,
    Caste,
    CasteDefinition,
    Charm,
    CharmType,
    RuleSet,
    Spell,
    SpellCircle,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _ruleset() -> RuleSet:
    """A small linked set: a Melee base Charm and a follow-up that requires it,
    plus the Terrestrial sorcery initiation and a Terrestrial spell."""
    charms = {
        "fire-and-stones": Charm(
            id="fire-and-stones", name="Fire and Stones Strike", category="melee",
            type=CharmType.SUPPLEMENTAL, min_ability=3, min_essence=2,
        ),
        "follow-up": Charm(
            id="follow-up", name="Follow-Up", category="melee",
            type=CharmType.SUPPLEMENTAL, min_ability=4, min_essence=2,
            prerequisites=[["fire-and-stones"]],
        ),
        "terrestrial-circle": Charm(
            id="terrestrial-circle", name="Terrestrial Circle Sorcery",
            category="occult", type=CharmType.PERMANENT, min_ability=3, min_essence=1,
            grants_sorcery_circle=SpellCircle.TERRESTRIAL,
        ),
    }
    spells = {
        "death-of-obsidian": Spell(
            id="death-of-obsidian", name="Death of Obsidian Butterflies",
            circle=SpellCircle.TERRESTRIAL,
        ),
    }
    castes = {
        Caste.DAWN: CasteDefinition(
            caste=Caste.DAWN,
            caste_abilities=[AbilityName.ARCHERY, AbilityName.BRAWL,
                             AbilityName.MARTIAL_ARTS, AbilityName.MELEE,
                             AbilityName.THROWN],
        ),
    }
    return RuleSet(castes=castes, charms=charms, spells=spells)


def _char(**kw) -> Character:
    c = Character(id="char.validate")
    for k, v in kw.items():
        setattr(c, k, v)
    return c


# --------------------------------------------------------------------------- #
# Reference integrity
# --------------------------------------------------------------------------- #

def test_unknown_charm_and_spell_ids_flagged():
    rs = _ruleset()
    c = _char(charms=["does-not-exist"], spells=["also-missing"])
    issues = validate.check_references(rs, c)
    codes = {i.code for i in issues}
    assert codes == {"unknown-charm", "unknown-spell"}


def test_clean_references_no_issues():
    rs = _ruleset()
    c = _char(charms=["fire-and-stones"], spells=[])
    assert validate.check_references(rs, c) == []


# --------------------------------------------------------------------------- #
# Charm prerequisites
# --------------------------------------------------------------------------- #

def _melee_char(rating: int, essence: int, charms: list[str]) -> Character:
    c = _char(charms=charms, essence_rating=essence)
    c.abilities[AbilityName.MELEE] = rating
    return c


def test_min_ability_violation():
    rs = _ruleset()
    c = _melee_char(rating=2, essence=2, charms=["fire-and-stones"])  # needs Melee 3
    issues = validate.check_charm_prerequisites(rs, c)
    assert [i.code for i in issues] == ["charm-min-ability"]


def test_min_essence_violation():
    rs = _ruleset()
    c = _melee_char(rating=3, essence=1, charms=["fire-and-stones"])  # needs Essence 2
    issues = validate.check_charm_prerequisites(rs, c)
    assert [i.code for i in issues] == ["charm-min-essence"]


def test_missing_charm_prerequisite():
    rs = _ruleset()
    # Holds the follow-up but not its prerequisite Charm.
    c = _melee_char(rating=4, essence=2, charms=["follow-up"])
    issues = validate.check_charm_prerequisites(rs, c)
    assert [i.code for i in issues] == ["charm-prerequisite"]


def test_satisfied_prerequisite_chain_is_clean():
    rs = _ruleset()
    c = _melee_char(rating=4, essence=2, charms=["fire-and-stones", "follow-up"])
    assert validate.check_charm_prerequisites(rs, c) == []


def test_and_of_or_group_satisfied_by_any_member():
    rs = _ruleset()
    rs.charms["or-charm"] = Charm(
        id="or-charm", name="Either-Or", category="melee", type=CharmType.SIMPLE,
        min_ability=1, min_essence=1, prerequisites=[["fire-and-stones", "follow-up"]],
    )
    # Only one of the OR group is needed.
    c = _melee_char(rating=4, essence=2, charms=["fire-and-stones", "or-charm"])
    assert validate.check_charm_prerequisites(rs, c) == []


def test_martial_arts_style_category_skips_ability_check():
    rs = _ruleset()
    rs.charms["ma"] = Charm(
        id="ma", name="Style Charm", category="Tiger Style", type=CharmType.SIMPLE,
        min_ability=5, min_essence=1,
    )
    c = _char(charms=["ma"], essence_rating=2)   # no martial_arts dots, but unchecked
    assert validate.check_charm_prerequisites(rs, c) == []


# --------------------------------------------------------------------------- #
# Spell-circle access
# --------------------------------------------------------------------------- #

def test_spell_without_initiation_is_flagged():
    rs = _ruleset()
    c = _char(spells=["death-of-obsidian"])      # no sorcery Charm known
    issues = validate.check_spell_access(rs, c)
    assert [i.code for i in issues] == ["spell-circle"]


def test_spell_with_matching_initiation_is_clean():
    rs = _ruleset()
    c = _char(charms=["terrestrial-circle"], spells=["death-of-obsidian"])
    assert validate.check_spell_access(rs, c) == []


# --------------------------------------------------------------------------- #
# Aggregate + chargen placeholder
# --------------------------------------------------------------------------- #

def test_validate_aggregates_all_checks():
    rs = _ruleset()
    c = _char(charms=["follow-up"], spells=["death-of-obsidian"], essence_rating=1)
    c.abilities[AbilityName.MELEE] = 1
    codes = sorted(i.code for i in validate.validate(rs, c))
    # follow-up: min-ability + min-essence + missing prereq; spell: no circle
    assert codes == ["charm-min-ability", "charm-min-essence",
                     "charm-prerequisite", "spell-circle"]


def test_chargen_validation_runs_and_reports_bonus_points():
    # Detailed chargen rules are exercised in test_chargen.py; here just confirm
    # the entry point runs and always emits the bonus-point tally.
    rs = _ruleset()
    issues = validate.validate_chargen(rs, _char(favored_abilities=[
        AbilityName.AWARENESS, AbilityName.DODGE, AbilityName.ATHLETICS,
        AbilityName.RESISTANCE, AbilityName.ENDURANCE,
    ]))
    assert any(i.code == "bonus-points" for i in issues)
