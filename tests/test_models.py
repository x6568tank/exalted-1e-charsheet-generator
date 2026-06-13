"""Tests for the pydantic models: structural invariants and cost arithmetic.

These guard the contract layer — shape, serialization, and the bounds the engine
relies on. Game-legality tests live alongside engine/validate.py once it exists.
"""

import json

import pytest
from pydantic import ValidationError

from exalted_builder.models.character import (
    AttributeName,
    Character,
    Specialty,
)
from exalted_builder.models.rules import (
    AbilityName,
    ArmorType,
    Charm,
    CharmType,
    ExperienceCosts,
    SpellCircle,
)


def test_character_defaults():
    c = Character(id="char.001")
    assert c.attributes[AttributeName.STRENGTH] == 1      # attributes start at 1
    assert len(c.abilities) == 25 and all(v == 0 for v in c.abilities.values())
    assert len(c.virtues) == 4
    assert c.chargen_locked is False
    assert c.wp_virtue_component is None                  # frozen only at lock


def test_enum_keyed_dict_roundtrips_through_json():
    c = Character(id="char.001")
    dumped = json.loads(c.model_dump_json())
    assert dumped["attributes"]["strength"] == 1          # serializes with string keys
    restored = Character.model_validate(json.loads(c.model_dump_json()))
    assert restored.attributes[AttributeName.WITS] == 1


def test_charm_is_immutable():
    ch = Charm(id="x", name="X", category="melee", type=CharmType.SIMPLE,
               min_ability=1, min_essence=1)
    with pytest.raises(ValidationError):
        ch.name = "Y"


def test_charm_prerequisites_are_and_of_or_groups():
    ch = Charm(id="x", name="X", category="melee", type=CharmType.SUPPLEMENTAL,
               min_ability=3, min_essence=2, prerequisites=[["a", "b"], ["c"]])
    assert ch.prerequisites == [["a", "b"], ["c"]]


def test_grants_sorcery_circle_field():
    ch = Charm(id="t", name="Terrestrial Circle Sorcery", category="occult",
               type=CharmType.PERMANENT, min_ability=3, min_essence=1,
               grants_sorcery_circle=SpellCircle.TERRESTRIAL)
    assert ch.grants_sorcery_circle is SpellCircle.TERRESTRIAL


@pytest.mark.parametrize("rating, ok", [(1, True), (3, True), (0, False), (4, False)])
def test_specialty_rating_bounds(rating, ok):
    if ok:
        Specialty(ability=AbilityName.OCCULT, name="Demonology", rating=rating)
    else:
        with pytest.raises(ValidationError):
            Specialty(ability=AbilityName.OCCULT, name="Demonology", rating=rating)


def test_xp_increase_costs_are_current_rating_scaled():
    xp = ExperienceCosts()
    assert xp.attribute.at(3) == 12             # current * 4
    assert xp.ability.at(3) == 6                # current * 2
    assert xp.ability_favored_caste.at(3) == 5  # current * 2 - 1 (flat discount)
    assert xp.essence.at(2) == 16               # current * 8
    assert xp.virtue.at(2) == 6                 # current * 3


def test_armor_type_parses_with_soak_l_b():
    a = ArmorType(id="armor.lamellar", name="Lamellar", weight="Medium",
                  soak_lethal=6, soak_bashing=8, mobility_penalty=-2,
                  fatigue=1, resources_cost=3)
    assert a.weight.value == "Medium"
    assert (a.soak_lethal, a.soak_bashing) == (6, 8)
