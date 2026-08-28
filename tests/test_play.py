"""Tests for the in-play tracker: the PlayState model, its persistence round-trip
and back-compat, the build_play_view capacities, and the invariant that play-state
never leaks into chargen / validation (it is a separate layer)."""

from exalted_builder import persistence
from exalted_builder.engine import validate
from exalted_builder.models.character import Character, Damage, PlayState
from exalted_builder.models.rules import (
    AbilityName, CasteDefinition, Charm, CharmType, RuleSet)
from exalted_builder.ui import view as viewmod


def _ruleset() -> RuleSet:
    castes = {"dawn": CasteDefinition(
        id="dawn", label="Dawn",
        caste_abilities=[AbilityName.ARCHERY, AbilityName.BRAWL,
                         AbilityName.MARTIAL_ARTS, AbilityName.MELEE, AbilityName.THROWN])}
    charms = {"melee": Charm(id="melee", name="M", category="melee",
                             type=CharmType.SIMPLE, min_ability=1, min_essence=1)}
    return RuleSet(castes=castes, charms=charms)


def test_play_defaults_to_none():
    assert Character(id="c").play is None


def test_old_save_without_play_loads():
    """A save predating the in-play layer (no `play` key) loads with play=None."""
    c = persistence.character_from_json('{"id": "legacy", "name": "Old"}')
    assert c.play is None


def test_playstate_roundtrips_through_json():
    c = Character(id="c")
    c.play = PlayState(health=[Damage.BASHING, Damage.LETHAL, None],
                       motes_personal_spent=4, motes_peripheral_spent=7,
                       willpower_spent=2, limit=3)
    back = persistence.character_from_json(persistence.character_to_json(c))
    assert back.play.health == [Damage.BASHING, Damage.LETHAL, None]
    assert back.play.motes_personal_spent == 4
    assert back.play.willpower_spent == 2
    assert back.play.limit == 3


def test_damage_marks_serialize_as_shorthand():
    """Damage marks persist as the 1e shorthand strings / x *."""
    c = Character(id="c")
    c.play = PlayState(health=[Damage.AGGRAVATED])
    assert '"*"' in persistence.character_to_json(c)


def test_limit_is_capped_at_ten():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        PlayState(limit=11)


def test_play_state_does_not_affect_validation():
    """Play-state is a separate layer — setting damage/motes/limit must not change
    any validation issue (chargen or the always-on checks)."""
    rs, c = _ruleset(), Character(id="c", caste="dawn")
    before = [i.code for i in validate.validate(rs, c)]
    before_chargen = [i.code for i in validate.validate_chargen(rs, c)]
    c.play = PlayState(health=[Damage.LETHAL] * 7, motes_personal_spent=99,
                       willpower_spent=5, limit=10)
    assert [i.code for i in validate.validate(rs, c)] == before
    assert [i.code for i in validate.validate_chargen(rs, c)] == before_chargen


def test_build_play_view_capacities_match_engine():
    rs = _ruleset()
    c = Character(id="c", caste="dawn", essence_rating=3)
    pv = viewmod.build_play_view(rs, c)
    # base health track is 7 levels (-0/-1/-1/-2/-2/-4/Incap) with no bonuses
    assert len(pv.health_boxes) == 7
    assert pv.health_boxes[-1].incapacitated and pv.health_boxes[-1].label == "Incap"
    # Solar: personal = Ess*3 + WP, peripheral = Ess*7 + WP + ΣVirtues; WP=2, ΣV=4
    assert pv.personal_max == 3 * 3 + 2
    assert pv.peripheral_max == 3 * 7 + 2 + 4
    assert pv.willpower_max == 2


# --------------------------------------------------------------------------- #
# decision 0006, enforced structurally rather than by inspection
# --------------------------------------------------------------------------- #

def test_validate_never_imports_the_play_module():
    """⚠ decision 0006 — play-state is validation-isolated.

    `engine/play.py` now sits importably beside `engine/validate/`, so the cheap
    mistake is a convenience import that quietly lets a marked health box change what
    a character may legally buy. The behavioural tests above cover the cases someone
    thought to write; this covers the ones they did not, by forbidding the edge itself.
    """
    import ast
    from pathlib import Path

    import exalted_builder

    validate_dir = Path(exalted_builder.__file__).parent / "engine" / "validate"
    modules = sorted(validate_dir.glob("*.py"))
    assert modules, "no validate modules found — has the package moved?"
    offenders = []
    for path in modules:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = {a.name for a in node.names}
                if (node.module or "").endswith("play") or "play" in names:
                    offenders.append(f"{path.name}: from {node.module} import "
                                     f"{', '.join(sorted(names))}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.endswith(".play") or alias.name == "play":
                        offenders.append(f"{path.name}: import {alias.name}")
    assert offenders == [], offenders


def test_validate_never_reads_the_play_field():
    """The other half: no `.play` attribute access anywhere in validation. An import
    guard alone is dodgeable — `character.play` needs no import."""
    import ast
    from pathlib import Path

    import exalted_builder

    validate_dir = Path(exalted_builder.__file__).parent / "engine" / "validate"
    offenders = []
    for path in sorted(validate_dir.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Attribute) and node.attr == "play":
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], offenders
