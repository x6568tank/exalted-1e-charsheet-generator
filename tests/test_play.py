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
