"""Thaumaturgic rituals as LIBRARY content (2026-08-28).

The chapter prints five rituals and says outright that more should be written
(p.148), so the catalogue is a seed — the same argument the gear library was built on
a day earlier, and the same three contracts:

  * **the book always wins an id collision**;
  * **a bad row is reported and dropped, never fatal**;
  * **a delete does not rewrite characters** — an unresolvable id is a case the rest
    of the build already handles.

⚠ **A ritual has TWO custom shapes and they are not interchangeable.** A library row
is a `ThaumaturgicRitual` in the RuleSet, bought by id by anyone. A ritual invented
for one character is an inline `RitualEntry` with an empty `ritual_id`, on that sheet
alone. Both entry points stay (the human's ruling, 2026-08-28); these tests cover the
first and `test_qt_charms.py` covers the second.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import custom_content as customs, rules_db
from exalted_builder.models.character import AbilityName, Character
from exalted_builder.ui import view as viewmod

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


def _load(custom_dir):
    return rules_db.load_ruleset(DATA_DIR, custom_dir)


def _row(**over):
    row = {"id": "custom.whisper-of-the-salt-road",
           "name": "Whisper of the Salt Road", "level": 2,
           "cost": "1 mote", "description": "A test ritual."}
    row.update(over)
    return row


def test_a_library_ritual_joins_the_catalogue_flagged_as_yours(tmp_path):
    customs.save_ritual(_row(), custom_dir=tmp_path)
    entry = _load(tmp_path).thaum_rituals["custom.whisper-of-the-salt-road"]
    assert entry.name == "Whisper of the Salt Road"
    assert entry.level == 2
    assert entry.custom


def test_the_book_wins_an_id_collision(tmp_path):
    printed = next(iter(_load(tmp_path).thaum_rituals))
    # Written by hand, because `save_ritual` refuses a non-`custom.` id outright —
    # this is the file-edited-by-hand case the loader still has to survive.
    path = tmp_path / customs.RITUALS_FILE
    path.write_text(f'[{{"id": "{printed}", "name": "Impostor", "level": 1}}]')
    rs = _load(tmp_path)
    assert rs.thaum_rituals[printed].name != "Impostor"
    assert any("shadows a ritual" in p for p in rs.custom_problems)


def test_a_broken_row_is_reported_and_never_fatal(tmp_path):
    (tmp_path / customs.RITUALS_FILE).write_text(
        '[{"id": "custom.nonsense", "name": "Nonsense", "level": 99}]')
    rs = _load(tmp_path)                       # does not raise
    assert "custom.nonsense" not in rs.thaum_rituals
    assert any("custom.nonsense" in p for p in rs.custom_problems)


def test_a_library_id_must_carry_the_custom_prefix(tmp_path):
    with pytest.raises(customs.CustomContentError):
        customs.save_ritual(_row(id="ritual.pretending"), custom_dir=tmp_path)


def test_saving_the_same_name_twice_replaces_rather_than_duplicates(tmp_path):
    customs.save_ritual(_row(), custom_dir=tmp_path)
    customs.save_ritual(_row(level=4), custom_dir=tmp_path)
    rows = customs.library_rituals(tmp_path)
    assert len(rows) == 1 and rows[0]["level"] == 4


def test_a_reload_picks_up_a_write_and_a_delete(tmp_path):
    """⚠ The half `reload_custom_layer` forgot for GEAR until a day earlier: the load
    path merged it and the reload path did not, so a row appeared only after a
    restart and a deleted one never went away. Written first for rituals, and it
    caught the same omission — the purge loop had to be added here too."""
    rs = _load(tmp_path)
    customs.save_ritual(_row(), custom_dir=tmp_path)
    rules_db.reload_custom_layer(rs, tmp_path)
    assert "custom.whisper-of-the-salt-road" in rs.thaum_rituals
    customs.delete_ritual("custom.whisper-of-the-salt-road", custom_dir=tmp_path)
    rules_db.reload_custom_layer(rs, tmp_path)
    assert "custom.whisper-of-the-salt-road" not in rs.thaum_rituals
    assert len(rs.thaum_rituals) == len(_load(tmp_path).thaum_rituals)   # book intact


def test_a_library_ritual_is_offered_to_a_character_like_a_printed_one(tmp_path):
    """The point of the library shape: it is bought BY ID from the ordinary picker,
    priced by its level, not retyped onto each sheet."""
    customs.save_ritual(_row(level=1), custom_dir=tmp_path)
    rs = _load(tmp_path)
    char = Character(id="c")
    char.abilities[AbilityName.OCCULT] = 3
    row = next(r for r in viewmod.build_thaum_picker(rs, char).rituals
               if r.key == "custom.whisper-of-the-salt-road")
    assert row.custom and row.available and row.price > 0


def test_deleting_a_library_ritual_leaves_a_character_who_knows_it_alone(tmp_path):
    """A save keeps the id. ⚠ Deliberately NOT a rewrite of the character: an
    unresolvable id is a graceful case everywhere else, and re-authoring the ritual
    under the same id brings it back."""
    customs.save_ritual(_row(level=1), custom_dir=tmp_path)
    rs = _load(tmp_path)
    char = Character(id="c")
    char.abilities[AbilityName.OCCULT] = 3
    from exalted_builder.engine import thaum_actions
    from exalted_builder.models.rules import Orientation
    thaum_actions.buy_thaum_entry(rs, char, "ritual",
                                  "custom.whisper-of-the-salt-road", Orientation.REALM)
    assert customs.delete_ritual("custom.whisper-of-the-salt-road", custom_dir=tmp_path)
    rules_db.reload_custom_layer(rs, tmp_path)
    assert char.thaumaturgy.rituals[0].ritual_id == "custom.whisper-of-the-salt-road"


# --------------------------------------------------------------------------- #
# travelling with a character
# --------------------------------------------------------------------------- #

def test_a_library_ritual_travels_inside_the_save(tmp_path):
    """⚠ A library ritual is referenced BY ID, so it travels like a Charm or a spell
    and unlike gear (which a save copies inline, decision 0007). Without this, handing
    a character to another player hands them a ritual their library cannot resolve."""
    customs.save_ritual(_row(level=1), custom_dir=tmp_path)
    rs = _load(tmp_path)
    char = Character(id="c")
    char.abilities[AbilityName.OCCULT] = 3
    from exalted_builder.engine import thaum_actions
    from exalted_builder.models.rules import Orientation
    thaum_actions.buy_thaum_entry(rs, char, "ritual",
                                  "custom.whisper-of-the-salt-road", Orientation.REALM)
    assert customs.embed_definitions(char, custom_dir=tmp_path) == 1
    assert [r["id"] for r in char.custom_definitions["rituals"]] == [
        "custom.whisper-of-the-salt-road"]

    # …and lands in the recipient's empty library when they open it.
    other = tmp_path / "someone-else"
    other.mkdir()
    assert customs.absorb_definitions(char, custom_dir=other) == [
        "custom.whisper-of-the-salt-road"]
    assert _load(other).thaum_rituals["custom.whisper-of-the-salt-road"].custom


def test_an_inline_ritual_has_nothing_to_embed(tmp_path):
    """The negative control. A ritual written for one character IS the save — it has
    no `ritual_id`, so there is no library row to carry and none to absorb."""
    rs = _load(tmp_path)
    char = Character(id="c")
    char.abilities[AbilityName.OCCULT] = 3
    from exalted_builder.engine import thaum_actions
    from exalted_builder.models.rules import Orientation
    thaum_actions.buy_custom_ritual(rs, char, "Mine Alone", 1, Orientation.REALM)
    assert customs.referenced_ritual_ids(char) == set()
    assert customs.embed_definitions(char, custom_dir=tmp_path) == 0
