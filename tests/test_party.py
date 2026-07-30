"""Tests for the GM party bundle: the Party model, its JSON round-trip, the
filename helpers, and the PartyCardView presenter.

The invariant worth guarding here is that a Party is a *container* — it adds no
rules and no derived values of its own, and a card can never disagree with the
Play tab about the same character."""

from pathlib import Path

import pytest

from exalted_builder import persistence, rules_db
from exalted_builder.models.character import Character, Damage, PlayState
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.models.rules import AbilityName
from exalted_builder.ui import view as viewmod

_DATA_DIR = Path("exalted_builder/data")


@pytest.fixture(scope="module")
def ruleset():
    return rules_db.load_ruleset(_DATA_DIR)


# --------------------------------------------------------------------------- #
# The model
# --------------------------------------------------------------------------- #

def test_party_defaults_to_empty():
    p = Party(id="p")
    assert p.members == []
    assert p.name == "" and p.session_notes == ""


def test_member_notes_default_to_empty():
    m = PartyMember(character=Character(id="c"))
    assert m.notes == ""


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #

def _two_member_party() -> Party:
    a = Character(id="a", name="Ashes of Dawn", caste="dawn")
    a.play = PlayState(health=[Damage.BASHING, None, Damage.LETHAL],
                       motes_personal_spent=4, willpower_spent=2, limit=3)
    a.xp_earned = 25
    b = Character(id="b", name="Jade Wind", exalt_type="Dragon-Blooded", caste="fire")
    return Party(id="party.tuesday", name="Tuesday Game", session_notes="met the Guild factor",
                 members=[PartyMember(character=a, notes="owes the Guild"),
                          PartyMember(character=b)])


def test_party_roundtrips_through_json():
    back = persistence.party_from_json(persistence.party_to_json(_two_member_party()))
    assert back.name == "Tuesday Game"
    assert back.session_notes == "met the Guild factor"
    assert [m.character.name for m in back.members] == ["Ashes of Dawn", "Jade Wind"]
    assert back.members[0].notes == "owes the Guild"
    assert back.members[1].notes == ""


def test_party_roundtrip_preserves_play_state_and_xp():
    """The play-state is the whole point of the bundle — it must survive a save."""
    back = persistence.party_from_json(persistence.party_to_json(_two_member_party()))
    play = back.members[0].character.play
    assert play.health == [Damage.BASHING, None, Damage.LETHAL]
    assert play.motes_personal_spent == 4
    assert play.willpower_spent == 2
    assert play.limit == 3
    assert back.members[0].character.xp_earned == 25


def test_party_roundtrip_preserves_a_never_played_member():
    """A character added straight from chargen has no play-state; it must stay None
    rather than being materialised on save (see models.character.PlayState)."""
    back = persistence.party_from_json(persistence.party_to_json(_two_member_party()))
    assert back.members[1].character.play is None


def test_party_with_a_legacy_character_loads():
    """A member whose embedded character predates the in-play layer (no `play` key)
    parses, exactly as load_character does for a bare save."""
    p = persistence.party_from_json(
        '{"id": "p", "members": [{"character": {"id": "legacy", "name": "Old"}}]}')
    assert p.members[0].character.play is None
    assert p.members[0].character.name == "Old"


def test_save_and_load_party_roundtrip(tmp_path):
    target = tmp_path / "nested" / "tuesday.party.json"
    written = persistence.save_party(_two_member_party(), target)
    assert written == target
    assert persistence.load_party(target).members[0].notes == "owes the Guild"


def test_save_party_creates_parents_and_leaves_no_temp_file(tmp_path):
    """save_party goes through the same atomic write as save_character."""
    target = tmp_path / "deep" / "dir" / "p.party.json"
    persistence.save_party(_two_member_party(), target)
    assert target.exists()
    assert list(target.parent.glob("*.tmp")) == []


def test_save_party_replaces_an_existing_file_atomically(tmp_path):
    target = tmp_path / "p.party.json"
    persistence.save_party(Party(id="p", name="First"), target)
    persistence.save_party(Party(id="p", name="Second"), target)
    assert persistence.load_party(target).name == "Second"
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_character_still_atomic_after_the_refactor(tmp_path):
    """The character path shares atomic_write now — guard it kept its behaviour."""
    target = tmp_path / "a" / "b" / "hero.character.json"
    persistence.save_character(Character(id="c", name="Hero"), target)
    assert persistence.load_character(target).name == "Hero"
    assert list(target.parent.glob("*.tmp")) == []


# --------------------------------------------------------------------------- #
# Filenames
# --------------------------------------------------------------------------- #

def test_suggested_party_filename_slugifies_the_name():
    assert persistence.suggested_party_filename(
        Party(id="p", name="Tuesday Game")) == "tuesday-game.party.json"


def test_suggested_party_filename_falls_back_to_party():
    """An unnamed party must not borrow the character fallback ('new-character')."""
    assert persistence.suggested_party_filename(Party(id="p")) == "party.party.json"
    assert persistence.suggested_party_filename(Party(id="p", name="   ")) == "party.party.json"


def test_normalize_party_filename_handles_blank_stem_and_explicit_json():
    p = Party(id="p", name="Tuesday Game")
    assert persistence.normalize_party_filename("", p) == "tuesday-game.party.json"
    assert persistence.normalize_party_filename("Big Table", p) == "big-table.party.json"
    assert persistence.normalize_party_filename("keep.json", p) == "keep.json"
    assert persistence.normalize_party_filename("x.party.json", p) == "x.party.json"


# --------------------------------------------------------------------------- #
# The presenter
# --------------------------------------------------------------------------- #

def test_party_card_view_reports_identity_and_permanent_numbers(ruleset):
    c = Character(id="c", name="Ashes", caste="dawn")
    c.abilities[AbilityName.DODGE] = 4
    cv = viewmod.build_party_card_view(ruleset, c)
    assert cv.name == "Ashes"
    assert cv.caste_label == "Dawn"
    assert cv.exalt_type == "Solar"
    assert cv.dodge == 4
    assert cv.chargen_locked is False


def test_party_card_view_names_an_unnamed_character():
    """A blank name would render an empty card heading."""
    rs = rules_db.load_ruleset(_DATA_DIR)
    assert viewmod.build_party_card_view(rs, Character(id="c")).name == "(unnamed)"


def test_party_card_view_matches_the_play_tab_for_the_same_character(ruleset):
    """A card and the Play tab read the same capacities — the card composes
    build_play_view rather than re-deriving them."""
    c = Character(id="c", name="Ashes", caste="dawn")
    card = viewmod.build_party_card_view(ruleset, c)
    play = viewmod.build_play_view(ruleset, c)
    assert len(card.play.health_boxes) == len(play.health_boxes)
    assert card.play.personal_max == play.personal_max
    assert card.play.peripheral_max == play.peripheral_max
    assert card.play.willpower_max == play.willpower_max


def test_party_card_view_reports_soak_from_the_engine(ruleset):
    from exalted_builder.engine import derive
    c = Character(id="c", name="Ashes", caste="dawn")
    cv = viewmod.build_party_card_view(ruleset, c)
    assert cv.soak == derive.derive(ruleset, c).soak


def test_party_card_view_uses_the_db_aspect_vocabulary(ruleset):
    """A mixed party must show each member's own splat vocabulary — DB call the
    caste slot an Aspect."""
    c = Character(id="c", name="Cathak", exalt_type="Dragon-Blooded", caste="fire")
    cv = viewmod.build_party_card_view(ruleset, c)
    assert cv.exalt_type == "Dragon-Blooded"
    assert cv.caste_noun == "Aspect"
    assert cv.identity_line == "Fire Aspect · Dragon-Blooded"


def test_party_card_identity_line_for_a_solar(ruleset):
    c = Character(id="c", name="Ashes", caste="dawn")
    assert viewmod.build_party_card_view(ruleset, c).identity_line == "Dawn Caste · Solar"
