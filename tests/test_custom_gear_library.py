"""Custom gear as LIBRARY content — the same treatment Charms and spells got in
decision 0012, extended to equipment on 2026-08-13.

Before this, "custom" gear meant free text on ONE character: you invented a homebrew
daiklave and it existed on that sheet alone, retyped for the next character, with no way
to fix a mistake everywhere. The machinery already existed; equipment simply never got
it.

Three contracts, all inherited from the Charm layer and all load-bearing:

  * **the book always wins an id collision** — a printed weapon must never be silently
    replaced by homebrew reusing its id;
  * **a bad row is reported and dropped, never fatal** — a Storyteller must not be able
    to brick the builder with a typo in their homebrew;
  * **saves carry copies**, so a character does not break when the library moves.
"""

import json
from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import custom_content as customs, rules_db

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


def _load(custom_dir):
    return rules_db.load_ruleset(DATA_DIR, custom_dir)


def test_a_library_weapon_joins_the_catalogue_tagged_as_yours(tmp_path):
    customs.save_gear_row("weapons", {
        "id": "custom.homebrew-daiklave", "name": "Homebrew Daiklave",
        "accuracy": 3, "damage": 6, "damage_type": "L", "artifact_rating": 3,
    }, custom_dir=tmp_path)
    rs = _load(tmp_path)
    w = rs.weapon_catalog["custom.homebrew-daiklave"]
    assert w.name == "Homebrew Daiklave"
    # Tagged rather than flagged: WeaponType is frozen and shared with the book data,
    # and a `custom` field on it would put a homebrew concept in the printed model.
    assert "custom" in w.tags
    assert not rs.custom_problems


def test_every_gear_kind_has_a_library(tmp_path):
    customs.save_gear_row("armor", {"id": "custom.plate", "name": "Scrap Plate",
                                    "weight": "Heavy", "soak_lethal": 5,
                                    "soak_bashing": 6}, custom_dir=tmp_path)
    customs.save_gear_row("gear", {"id": "custom.silk", "name": "Bolt of silk",
                                   "kind": "goods", "resources_cost": 2},
                          custom_dir=tmp_path)
    customs.save_gear_row("artifacts", {"id": "custom.orb", "name": "Whispering Orb",
                                        "rating": 3}, custom_dir=tmp_path)
    rs = _load(tmp_path)
    assert rs.armor_catalog["custom.plate"].name == "Scrap Plate"
    assert rs.gear_catalog["custom.silk"].resources_cost == 2
    assert rs.artifact_catalog["custom.orb"].rating == 3


def test_the_book_wins_an_id_collision(tmp_path):
    """A printed weapon must never be replaced by homebrew that reuses its id. The row
    is dropped and REPORTED — silence would let a library quietly rewrite the rules."""
    printed = next(iter(_load(None).weapon_catalog.values()))
    (tmp_path / "weapons.json").write_text(json.dumps(
        [{"id": printed.id, "name": "Impostor", "accuracy": 99}]))
    rs = _load(tmp_path)
    assert rs.weapon_catalog[printed.id].name == printed.name
    assert any("shadows an entry from the rulebook" in p for p in rs.custom_problems)


def test_a_broken_row_is_reported_and_never_fatal(tmp_path):
    """The whole reason the custom layer is separate from the book's: a typo here must
    not stop the app loading. The GOOD row in the same file still arrives."""
    (tmp_path / "weapons.json").write_text(json.dumps([
        {"id": "custom.fine", "name": "Fine Sword", "accuracy": 2},
        {"id": "custom.broken", "name": "Broken", "accuracy": "not a number"},
    ]))
    rs = _load(tmp_path)                       # does not raise
    assert "custom.fine" in rs.weapon_catalog
    assert "custom.broken" not in rs.weapon_catalog
    assert any("custom.broken" in p for p in rs.custom_problems)


def test_a_library_id_must_carry_the_custom_prefix(tmp_path):
    """⚠ Checked at SAVE time, not only on load. Book ids are namespaced, so reserving
    the prefix makes a collision impossible by construction rather than by catching it
    later — and the user hears about it while they can still rename the thing."""
    with pytest.raises(customs.CustomContentError):
        customs.save_gear_row("weapons", {"id": "solar.daiklave", "name": "Sneaky"},
                              custom_dir=tmp_path)
    with pytest.raises(customs.CustomContentError):
        customs.save_gear_row("weapons", {"id": "custom.x", "name": "  "},
                              custom_dir=tmp_path)


def test_saving_the_same_name_twice_REPLACES_rather_than_duplicates(tmp_path):
    """The id is derived from the name, so a second save of an edited item updates the
    library row instead of breeding a near-duplicate — the behaviour `save_charm`
    already has, and the reason it keeps the id."""
    for dmg in (4, 7):
        customs.save_gear_row("weapons", {
            "id": customs.make_id("Homebrew Lance"), "name": "Homebrew Lance",
            "damage": dmg}, custom_dir=tmp_path)
    rows = json.loads((tmp_path / "weapons.json").read_text())
    assert len(rows) == 1 and rows[0]["damage"] == 7


# --- the buy path: the button has to write a row the loader will accept ------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_save_to_library_writes_a_row_the_loader_can_read(user, tmp_path,
                                                                monkeypatch) -> None:
    """⚠ The BINDING test. Every test above calls `save_gear_row` directly, so all of
    them would pass against a button that built a malformed payload — and a character's
    `Weapon` is NOT a `WeaponType`: it carries `quantity` and `from_artifact`, which are
    facts about owning a thing rather than about its design.

    So this clicks the real control and then LOADS the library, which is the only way to
    find out whether what was written is a catalogue row.
    """
    monkeypatch.setenv(customs.CUSTOM_DIR_ENV, str(tmp_path))
    await user.open('/custom-gear')          # CHAR_CUSTOM holds "My Custom Blade"
    await user.should_see("Weapons")
    buttons = [e for e in user.client.elements.values()
               if "save-to-library" in getattr(e, "_markers", [])]
    assert buttons, "no save-to-library control on the gear rows"
    # Every row's button, not `buttons[0]` — the panels render armour first, so
    # indexing picked the armour row and the weapon assertion below failed against
    # working code. Saving both is the better test regardless: the four kinds have
    # four different payload shapes and only a load can tell whether each is valid.
    for b in buttons:
        b._handle_event({"id": b.id,
                         "listener_id": list(b._event_listeners)[0], "args": {}})
    await user.should_see("to your library")

    rs = _load(tmp_path)
    assert not [p for p in rs.custom_problems if "custom." in p], rs.custom_problems
    weapons = [w for w in rs.weapon_catalog.values() if "custom" in w.tags]
    assert [w.name for w in weapons] == ["My Custom Blade"]
    assert weapons[0].accuracy == 2 and weapons[0].damage == 5
    armour = [a for a in rs.armor_catalog.values() if "custom" in a.tags]
    assert [a.name for a in armour] == ["My Plate"]
    assert armour[0].soak_lethal == 4
