"""Tests for persistence.load/save — JSON round-trip fidelity, enum-keyed dict
serialisation, atomic writes, and error propagation. Saves go to pytest's
tmp_path; no committed fixtures.
"""

import json

import pytest
from pydantic import ValidationError

from exalted_builder import persistence
from exalted_builder.models.character import (
    Armor,
    BackgroundEntry,
    Character,
    HealthLevel,
    Specialty,
    Weapon,
)
from exalted_builder.models.rules import (
    AbilityName,
    AttributeName,
    Caste,
    VirtueName,
)


def _rich_character() -> Character:
    """A character touching the non-default corners: nested sub-records, enum-keyed
    dicts with non-default values, lists, and an Optional that is set."""
    c = Character(id="char.persist", name="Harmonious Jade", caste=Caste.TWILIGHT)
    c.attributes[AttributeName.STRENGTH] = 4
    c.abilities[AbilityName.OCCULT] = 5
    c.virtues[VirtueName.CONVICTION] = 3
    c.favored_abilities = [AbilityName.OCCULT, AbilityName.LORE]
    c.specialties = [Specialty(ability=AbilityName.OCCULT, name="Demons", rating=2)]
    c.backgrounds = [BackgroundEntry(name="Manse", rating=3, note="Mountain retreat")]
    c.charms = ["solar.occult.terrestrial-circle"]
    c.spells = ["solar.spell.death-of-obsidian-butterflies"]
    c.health_bonus_levels = [HealthLevel(penalty=-1, source_charm="ox-body")]
    c.willpower_purchased = 2
    c.wp_virtue_component = 6
    # Inline equipment exercising the artifact/ranged fields on the inline models.
    c.weapons = [Weapon(name="Daiklave", speed=3, accuracy=2, damage=5,
                        damage_type="L", defense=2, min_strength=2, artifact_rating=2)]
    c.armor = [Armor(name="Articulated Plate (Artifact)", soak_lethal=12, soak_bashing=14,
                     mobility_penalty=-2, fatigue=1, attunement=6, artifact_rating=4)]
    return c


def test_round_trip_preserves_everything(tmp_path):
    c = _rich_character()
    path = persistence.save_character(c, tmp_path / "jade.character.json")
    loaded = persistence.load_character(path)
    assert loaded == c                      # pydantic structural equality


def test_string_round_trip():
    c = _rich_character()
    assert persistence.character_from_json(persistence.character_to_json(c)) == c


def test_enum_keyed_dicts_serialise_as_value_strings(tmp_path):
    c = _rich_character()
    path = persistence.save_character(c, tmp_path / "jade.character.json")
    raw = json.loads(path.read_text())
    # Keys are the enum *values*, not "AttributeName.STRENGTH".
    assert raw["attributes"]["strength"] == 4
    assert raw["abilities"]["occult"] == 5
    assert raw["virtues"]["conviction"] == 3


def test_save_creates_parent_directories(tmp_path):
    c = _rich_character()
    nested = tmp_path / "saves" / "solars" / "jade.character.json"
    persistence.save_character(c, nested)
    assert nested.exists()


def test_save_is_atomic_and_leaves_no_temp_files(tmp_path):
    c = _rich_character()
    persistence.save_character(c, tmp_path / "jade.character.json")
    # The temp file used during the atomic replace must be gone.
    assert [p.name for p in tmp_path.iterdir()] == ["jade.character.json"]


def test_overwrite_replaces_prior_save(tmp_path):
    path = tmp_path / "jade.character.json"
    persistence.save_character(_rich_character(), path)
    updated = _rich_character()
    updated.name = "Renamed"
    persistence.save_character(updated, path)
    assert persistence.load_character(path).name == "Renamed"


def test_missing_file_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError):
        persistence.load_character(tmp_path / "nope.character.json")


def test_malformed_data_raises_validation_error(tmp_path):
    path = tmp_path / "bad.character.json"
    path.write_text('{"id": "x", "essence_rating": "not-a-number"}')
    with pytest.raises(ValidationError):
        persistence.load_character(path)
