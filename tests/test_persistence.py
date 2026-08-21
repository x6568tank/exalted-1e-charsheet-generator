"""Tests for persistence.load/save — JSON round-trip fidelity, enum-keyed dict
serialisation, atomic writes, and error propagation. Saves go to pytest's
tmp_path; no committed fixtures.
"""

import json
from pathlib import Path

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
    VirtueName,
)


def _rich_character() -> Character:
    """A character touching the non-default corners: nested sub-records, enum-keyed
    dicts with non-default values, lists, and an Optional that is set."""
    c = Character(id="char.persist", name="Harmonious Jade", caste="twilight")
    c.attributes[AttributeName.STRENGTH] = 4
    c.abilities[AbilityName.OCCULT] = 5
    c.virtues[VirtueName.CONVICTION] = 3
    c.favored_abilities = [AbilityName.OCCULT, AbilityName.LORE]
    # Two rows rather than one at rating 2: a specialty is an instance, not a rated
    # trait (human, 2026-07-31), and taking the same one twice is how it stacks. A
    # legacy rating-2 save no longer round-trips unchanged BY DESIGN — the loader
    # splits it — which `test_a_legacy_rated_specialty_is_split_into_instances_on_load`
    # covers in test_advancement.
    c.specialties = [Specialty(ability=AbilityName.OCCULT, name="Demons", rating=1),
                     Specialty(ability=AbilityName.OCCULT, name="Demons", rating=1)]
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


def test_biography_fields_round_trip_and_old_saves_default(tmp_path):
    # The Qt Identity tab's bio block rides on real Character fields. They must
    # round-trip, and a save written before they existed must load with "" (a missing
    # key is pydantic's default — the backwards-compat contract).
    c = Character(id="bio", name="A", sex="M", age="32", eye_color="grey",
                  hair_color="black", skin_color="pale", height="6'0\"",
                  weight="180", description="d", backstory="b", notes="n")
    path = persistence.save_character(c, tmp_path / "bio.character.json")
    assert persistence.load_character(path) == c
    old = persistence.character_from_json('{"id": "old", "name": "Old"}')
    assert old.sex == "" and old.eye_color == "" and old.backstory == "" \
        and old.notes == ""


def test_legacy_capitalised_caste_migrates_to_id():
    """A pre-Phase-2 save stored the caste as its display name ("Dawn"); it now
    loads as the lowercase id ("dawn") so old saves keep working."""
    c = persistence.character_from_json('{"id": "legacy", "caste": "Twilight"}')
    assert c.caste == "twilight"


def test_current_caste_id_passes_through_unchanged():
    c = persistence.character_from_json('{"id": "new", "caste": "eclipse"}')
    assert c.caste == "eclipse"


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


# --------------------------------------------------------------------------- #
# Save-target naming (filename derived from the character's name)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name,expected", [
    ("Ashes-of-Dawn", "ashes-of-dawn"),
    ("Harmonious Jade", "harmonious-jade"),
    ("  Spaced  Out  ", "spaced-out"),
    ("Né'phâr the 3rd!", "n-ph-r-the-3rd"),
    ("", "new-character"),
    ("***", "new-character"),
])
def test_slugify_name(name, expected):
    assert persistence.slugify_name(name) == expected


def test_suggested_filename_uses_the_name():
    c = Character(id="char.x", name="Ashes-of-Dawn")
    assert persistence.suggested_filename(c) == "ashes-of-dawn.character.json"


def test_suggested_filename_falls_back_for_blank_name():
    assert persistence.suggested_filename(Character(id="char.x")) == "new-character.character.json"


@pytest.mark.parametrize("text, expected", [
    ("", "ashes-of-dawn.character.json"),          # blank -> character-derived
    ("   ", "ashes-of-dawn.character.json"),
    ("My Hero", "my-hero.character.json"),          # bare stem -> slug + suffix
    ("backup.json", "backup.json"),                 # explicit .json kept
    ("hero.character.json", "hero.character.json"),  # full name kept verbatim
])
def test_normalize_save_filename(text, expected):
    c = Character(id="char.x", name="Ashes-of-Dawn")
    assert persistence.normalize_save_filename(text, c) == expected


def test_default_save_dir_is_cwd_when_not_frozen():
    # Not running as a PyInstaller bundle under pytest, so it should be the CWD.
    assert persistence.default_save_dir() == Path.cwd()


def test_save_uses_suggested_filename_in_a_directory(tmp_path):
    c = _rich_character()
    target = tmp_path / persistence.suggested_filename(c)
    persistence.save_character(c, target)
    assert target.name == "harmonious-jade.character.json"
    assert persistence.load_character(target).name == "Harmonious Jade"


def test_ammunition_quantity_survives_a_save_and_load(tmp_path):
    """`Weapon.quantity` is written by the editor and read by nothing in the engine —
    the shape that has silently lost data in this build before (a stat the adversary
    editor wrote and the save dropped). Pin the round trip, since no derivation would
    ever notice the field going missing."""
    from exalted_builder.models.character import Weapon
    c = Character(id="char.ammo", name="Fletcher", caste="dawn")
    c.weapons = [Weapon(name="Long Bow", accuracy=1, rate=3, range=200),
                 Weapon(name="Broadhead Arrow", damage=2, quantity=24)]
    path = tmp_path / "ammo.json"
    persistence.save_character(c, path)
    back = persistence.load_character(path)
    assert [w.quantity for w in back.weapons] == [1, 24]
