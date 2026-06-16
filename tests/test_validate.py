"""Tests for engine.validate — reference integrity, Charm prerequisites, and
spell-circle access. RuleSets are built inline from the models (no data files).
"""

from exalted_builder.engine import validate
from exalted_builder.models.character import Character, Combo
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


def test_exalt_type_known_vs_unknown():
    rs = _ruleset()                                  # default exalts = {"Solar"}
    assert validate.check_exalt_type(rs, _char(exalt_type="Solar")) == []
    issues = validate.check_exalt_type(rs, _char(exalt_type="Abyssal"))
    assert [i.code for i in issues] == ["exalt-type-unknown"]


def test_ox_body_charm_resolves_per_splat():
    """The Ox-Body resolver returns the charm named by the character's splat's
    ExaltDefinition; an unknown splat falls back to Solar's (absent here -> None)."""
    rs = _ruleset()                                  # no ox-body charm in this set
    assert validate.ox_body_charm_id(rs, _char(exalt_type="Solar")) == \
        "solar.endurance.ox-body-technique"
    assert validate.ox_body_charm(rs, _char(exalt_type="Solar")) is None


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


def test_martial_arts_style_category_resolves_to_martial_arts():
    # Convention: a Martial Arts style charm's category is 'martial_arts:<style>',
    # which gates on the Martial Arts ability.
    rs = _ruleset()
    rs.charms["ma"] = Charm(
        id="ma", name="Tiger Claw", category="martial_arts:tiger", type=CharmType.SIMPLE,
        min_ability=3, min_essence=1,
    )
    c = _char(charms=["ma"], essence_rating=2)
    c.abilities[AbilityName.MARTIAL_ARTS] = 2        # below the min -> flagged
    assert [i.code for i in validate.check_charm_prerequisites(rs, c)] == ["charm-min-ability"]
    c.abilities[AbilityName.MARTIAL_ARTS] = 3        # meets it
    assert validate.check_charm_prerequisites(rs, c) == []
    assert validate.meets_charm_requirements(rs, c, rs.charms["ma"]) is True


def test_unrecognised_category_is_left_unchecked():
    rs = _ruleset()
    rs.charms["x"] = Charm(
        id="x", name="Odd", category="sorcery", type=CharmType.SIMPLE,
        min_ability=5, min_essence=1,
    )
    c = _char(charms=["x"], essence_rating=2)        # 'sorcery' has no gating ability
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


def test_meets_spell_requirements_needs_granting_charm():
    rs = _ruleset()
    spell = rs.spells["death-of-obsidian"]
    assert validate.meets_spell_requirements(rs, _char(), spell) is False
    c = _char(charms=["terrestrial-circle"])
    assert validate.meets_spell_requirements(rs, c, spell) is True


def test_meets_spell_requirements_bars_solar_circle_at_chargen():
    rs = _ruleset()
    rs.spells["rain-of-doom"] = Spell(
        id="rain-of-doom", name="Rain of Doom", circle=SpellCircle.SOLAR)
    rs.charms["solar-circle"] = Charm(
        id="solar-circle", name="Solar Circle Sorcery", category="occult",
        type=CharmType.PERMANENT, min_ability=5, min_essence=5,
        grants_sorcery_circle=SpellCircle.SOLAR)
    c = _char(charms=["solar-circle"])
    spell = rs.spells["rain-of-doom"]
    assert validate.meets_spell_requirements(rs, c, spell) is False           # chargen
    assert validate.meets_spell_requirements(rs, c, spell, chargen=False) is True


# --------------------------------------------------------------------------- #
# Combos (core pp.213-214)
# --------------------------------------------------------------------------- #

def _combo_ruleset() -> RuleSet:
    """A set of instant-duration Charms of assorted types, plus one non-instant
    Charm, for exercising Combo legality."""
    def mk(cid, ctype, duration="Instant"):
        return Charm(id=cid, name=cid.replace("-", " ").title(), category="melee",
                     type=ctype, min_ability=1, min_essence=1, duration=duration)
    charms = {
        "simple-a": mk("simple-a", CharmType.SIMPLE),
        "simple-b": mk("simple-b", CharmType.SIMPLE),
        "supp-a": mk("supp-a", CharmType.SUPPLEMENTAL),
        "reflex-a": mk("reflex-a", CharmType.REFLEXIVE),
        "extra-a": mk("extra-a", CharmType.EXTRA_ACTION),
        "extra-b": mk("extra-b", CharmType.EXTRA_ACTION),
        "scene-buff": mk("scene-buff", CharmType.REFLEXIVE, duration="One scene"),
    }
    castes = {Caste.DAWN: CasteDefinition(caste=Caste.DAWN, caste_abilities=[AbilityName.MELEE])}
    return RuleSet(castes=castes, charms=charms)


def _combo_char(combo_ids, known=None) -> Character:
    c = Character(id="char.combo")
    c.charms = list(known if known is not None else combo_ids)
    c.combos = [Combo(name="Test Combo", charm_ids=list(combo_ids))]
    return c


def test_legal_combo_is_clean():
    rs = _combo_ruleset()
    c = _combo_char(["simple-a", "supp-a", "reflex-a"])
    assert validate.validate_combos(rs, c) == []


def test_combo_needs_at_least_two_charms():
    rs = _combo_ruleset()
    c = _combo_char(["simple-a"])
    codes = [i.code for i in validate.validate_combos(rs, c)]
    assert codes == ["combo-too-small"]


def test_combo_rejects_duplicate_charm():
    rs = _combo_ruleset()
    c = _combo_char(["simple-a", "simple-a"])
    codes = {i.code for i in validate.validate_combos(rs, c)}
    assert "combo-duplicate-charm" in codes


def test_combo_charm_must_be_known():
    rs = _combo_ruleset()
    # Both Charms exist in the rule set, but the character only knows one.
    c = _combo_char(["simple-a", "supp-a"], known=["simple-a"])
    codes = {i.code for i in validate.validate_combos(rs, c)}
    assert "combo-unknown-charm" in codes


def test_combo_rejects_non_instant_charm():
    rs = _combo_ruleset()
    c = _combo_char(["simple-a", "scene-buff"])
    codes = {i.code for i in validate.validate_combos(rs, c)}
    assert "combo-non-instant" in codes


def test_combo_allows_only_one_simple_charm():
    rs = _combo_ruleset()
    c = _combo_char(["simple-a", "simple-b"])
    codes = {i.code for i in validate.validate_combos(rs, c)}
    assert "combo-multiple-simple" in codes


def test_combo_allows_only_one_extra_action_charm():
    rs = _combo_ruleset()
    c = _combo_char(["extra-a", "extra-b"])
    codes = {i.code for i in validate.validate_combos(rs, c)}
    assert "combo-multiple-extra-action" in codes


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
