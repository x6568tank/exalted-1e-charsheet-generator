"""The Attribute / Ability / Virtue reference text (data/trait_descriptions.json).

Covers the data's coverage of the three closed vocabularies, the loader's coverage
check (which is the only thing standing between a short file and a silently empty
panel), and the `ui/view.py` presenter both shells render.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.models.rules import AbilityName, AttributeName, VirtueName
from exalted_builder.ui import view as viewmod


DATA = Path(exalted_builder.__file__).parent / "data"


# --------------------------------------------------------------------------- #
# the data
# --------------------------------------------------------------------------- #

def test_every_attribute_ability_and_virtue_has_reference_text(ruleset):
    td = ruleset.trait_descriptions
    assert td is not None
    assert {a.id for a in td.attributes} == set(AttributeName)
    assert {a.id for a in td.abilities} == set(AbilityName)
    assert {v.id for v in td.virtues} == set(VirtueName)


def test_attributes_and_virtues_carry_a_full_one_to_five_ladder(ruleset):
    td = ruleset.trait_descriptions
    for row in list(td.attributes) + list(td.virtues):
        assert sorted(row.ladder) == [1, 2, 3, 4, 5], row.id
        assert all(row.ladder.values()), row.id


def test_the_ability_ladder_is_generic_and_starts_at_unskilled(ruleset):
    # ⚠ 1e prints NO per-Ability rungs — the ladder is shared, and it has a rung 0
    # ("Unskilled", -2 dice) that the Attribute and Virtue ladders have no counterpart
    # for. A per-Ability ladder appearing here would be a 2e import.
    td = ruleset.trait_descriptions
    assert sorted(td.ability_ladder) == [0, 1, 2, 3, 4, 5]
    assert "-2" in td.ability_ladder[0]


def test_every_row_carries_prose(ruleset):
    td = ruleset.trait_descriptions
    for row in list(td.attributes) + list(td.abilities) + list(td.virtues):
        # The Core-Charm re-transcription's lesson: a row that EXISTS is not a row that
        # says anything. A one-line stub would pass a coverage check and read as blank.
        assert len(row.description) > 120, row.id


def test_abilities_print_specialties_and_the_three_feat_tiers(ruleset):
    td = ruleset.trait_descriptions
    for row in td.abilities:
        if row.id is AbilityName.LINGUISTICS:
            # The one Ability whose page prints a specialty PARAGRAPH and no feats.
            assert row.specialties == [] and row.specialties_note
            assert not (row.standard or row.challenging or row.legendary)
            continue
        assert row.specialties, row.id
        assert row.standard and row.challenging and row.legendary, row.id


def test_virtues_carry_both_printed_lists(ruleset):
    for row in ruleset.trait_descriptions.virtues:
        assert row.aids_in and row.must_fail_check_to, row.id


# --------------------------------------------------------------------------- #
# the loader's coverage check
# --------------------------------------------------------------------------- #

def test_a_missing_row_is_a_load_error(ruleset):
    td = ruleset.trait_descriptions
    problems: list[str] = []
    rules_db._check_trait_descriptions(
        td.model_copy(update={"attributes": td.attributes[:-1]}), problems)
    assert problems == ["trait_descriptions.json: no attribute row for 'wits'"]


def test_a_duplicated_row_is_a_load_error(ruleset):
    td = ruleset.trait_descriptions
    problems: list[str] = []
    rules_db._check_trait_descriptions(
        td.model_copy(update={"virtues": list(td.virtues) + [td.virtues[0]]}), problems)
    assert problems == ["trait_descriptions.json: duplicate virtue row 'compassion'"]


def test_an_absent_file_is_not_an_error(ruleset):
    # The file is optional by design: no text simply means no ⓘ buttons.
    problems: list[str] = []
    rules_db._check_trait_descriptions(None, problems)
    assert problems == []


# --------------------------------------------------------------------------- #
# the presenter
# --------------------------------------------------------------------------- #

def test_attribute_info_marks_the_characters_own_rung(ruleset):
    info = viewmod.attribute_info(ruleset, AttributeName.STRENGTH, 3)
    assert info.title == "Strength"
    assert info.subtitle == "Physical Attribute"
    assert [r for _, _, r in info.ladder] == [False, False, True, False, False]
    assert info.sections == []


def test_attribute_info_without_a_rating_marks_nothing(ruleset):
    info = viewmod.attribute_info(ruleset, AttributeName.WITS)
    assert not any(current for _, _, current in info.ladder)


def test_ability_info_spells_the_success_counts_into_the_feat_headings(ruleset):
    # The page prints "1 / 3 / 5 successes" once, on p.132, and never again beside a
    # feat — a heading that just said "Challenging" would send the reader hunting.
    info = viewmod.ability_info(ruleset, AbilityName.MELEE, 2)
    headings = [h for h, _ in info.sections]
    assert headings == ["Sample specialties", "Standard (1 success)",
                        "Challenging (3 successes)", "Legendary (5 successes)"]
    assert [n for n, _, _ in info.ladder] == [0, 1, 2, 3, 4, 5]
    assert [r for _, _, r in info.ladder] == [False, False, True, False, False, False]


def test_ability_info_renders_the_linguistics_specialty_paragraph(ruleset):
    info = viewmod.ability_info(ruleset, AbilityName.LINGUISTICS, 1)
    assert [h for h, _ in info.sections] == ["Specialties"]


def test_virtue_info_names_the_virtue_in_both_section_headings(ruleset):
    info = viewmod.virtue_info(ruleset, VirtueName.VALOR, 5)
    assert [h for h, _ in info.sections] == ["Valor aids in",
                                             "Must fail a Valor check to"]
    assert info.subtitle == "Virtue"


@pytest.mark.parametrize("call", [
    lambda rs: viewmod.attribute_info(rs, AttributeName.WITS),
    lambda rs: viewmod.ability_info(rs, AbilityName.MELEE),
    lambda rs: viewmod.virtue_info(rs, VirtueName.VALOR),
])
def test_a_ruleset_without_trait_text_presents_nothing(ruleset, call):
    # The shells hide the ⓘ on a None, so this is the switch that keeps the feature
    # optional rather than a crash on a partial data set.
    assert call(ruleset.model_copy(update={"trait_descriptions": None})) is None


# --------------------------------------------------------------------------- #
# the NiceGUI shell
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_opens_a_traits_reference_dialog(user) -> None:
    await user.open('/blank')
    user.find(marker="trait-info-strength").click()
    await user.should_see("Physical Attribute")
    await user.should_see("Doughty laborer (dead lift 200 lbs.).")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_ability_dialog_carries_specialties_and_feats(user) -> None:
    await user.open('/blank')
    user.find(marker="trait-info-melee").click()
    await user.should_see("Sample specialties")
    await user.should_see("Legendary (5 successes)")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_every_rated_trait_carries_an_info_marker(user) -> None:
    # 9 Attributes + 25 Abilities + 4 Virtues — the count the Qt shell asserts too, so
    # a trait family that loses its ⓘ in one shell cannot pass by matching the other.
    await user.open('/blank')
    markers = {m for e in user.client.elements.values() for m in (e._markers or [])
               if m.startswith("trait-info-")}
    assert len(markers) == 38
