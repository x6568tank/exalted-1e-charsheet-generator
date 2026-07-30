"""UI-layer tests for thaumaturgy: the Storyteller-options tab and the picker's
thaumaturgy page.

The engine is covered by tests/test_thaumaturgy_engine.py; what is tested here is
the presenter (ui/view.py) and the render, which is where a NiceGUI `ui.select`
with an out-of-range value blows up at render time rather than in a unit test.
"""

from pathlib import Path

import pytest
from nicegui.testing import User

from exalted_builder import rules_db
from exalted_builder.engine import advancement, lifecycle
from exalted_builder.models.character import (ArtSpecialty, Character, FormulaEntry,
                                              HouseRules, RitualEntry, ScienceRating,
                                              ThaumaturgyState)
from exalted_builder.models.rules import AbilityName, Orientation
from exalted_builder.ui import builder as buildermod
from exalted_builder.ui import picker as pickermod
from exalted_builder.ui import view as viewmod

_DATA = Path(__file__).resolve().parents[1] / "exalted_builder" / "data"


@pytest.fixture(scope="module")
def ruleset():
    return rules_db.load_ruleset(_DATA)


def _character(**kwargs) -> Character:
    return Character(id="char.test", name="Test", exalt_type="Solar",
                     caste="Twilight", **kwargs)


# --------------------------------------------------------------------------- #
# The scope table must not drift from the model
#
# HouseRules marks TABLE-WIDE vs PER-CHARACTER in comments only — a deliberate
# choice (human, 2026-07-29) to keep the model one flat document. The machine
# readable copy the ST tab renders from therefore lives in the presenter, which
# means the two CAN drift: add a field, update the comment, forget the table, and
# the toggle silently renders under the wrong heading or not at all.
#
# This test is what makes that choice safe. It is the reason no scope annotation
# was pushed back onto the model.
# --------------------------------------------------------------------------- #

def test_every_house_rule_field_appears_in_the_scope_table() -> None:
    listed = [entry[0] for entry in viewmod._HOUSE_RULES]
    assert sorted(listed) == sorted(HouseRules.model_fields)


def test_no_house_rule_is_listed_twice() -> None:
    listed = [entry[0] for entry in viewmod._HOUSE_RULES]
    assert len(listed) == len(set(listed))


def test_every_house_rule_declares_a_known_scope() -> None:
    for field, _label, scope, _citation, _description in viewmod._HOUSE_RULES:
        assert scope in ("table", "character"), field


def test_build_house_rules_returns_one_row_per_field(ruleset) -> None:
    rows = viewmod.build_house_rules(ruleset, _character())
    assert {r.field for r in rows} == set(HouseRules.model_fields)


def test_house_rule_rows_reflect_stored_values(ruleset) -> None:
    char = _character(house_rules=HouseRules(magic_for_everyone=True))
    rows = {r.field: r for r in viewmod.build_house_rules(ruleset, char)}
    assert rows["magic_for_everyone"].value is True
    assert rows["restrict_chargen_ritual_level"].value is False


def test_absent_house_rules_read_as_the_model_defaults(ruleset) -> None:
    # An old save has house_rules None; the tab must still render every row, each at
    # its model default. Every TOGGLE defaults off; a multiple-choice rule (the M&F
    # change method) defaults to the option the model declares, not to False.
    char = _character()
    assert char.house_rules is None
    defaults = HouseRules()
    for row in viewmod.build_house_rules(ruleset, char):
        assert row.value == getattr(defaults, row.field), row.field
        if not row.options:
            assert row.value is False, row.field


def test_a_multiple_choice_rule_offers_its_stored_value(ruleset) -> None:
    """A ui.select whose value is absent from its options raises at build time, so
    every choice the model accepts must appear in the row's options."""
    char = _character()
    rows = {r.field: r for r in viewmod.build_house_rules(ruleset, char)}
    row = rows["mf_change_method"]
    assert row.options and row.value in row.options
    for choice in ("experience", "backgrounds", "swap"):
        char.house_rules = HouseRules(mf_change_method=choice)
        r = {x.field: x for x in viewmod.build_house_rules(ruleset, char)}["mf_change_method"]
        assert r.value == choice and choice in r.options


def test_foreign_charm_toggle_is_annotated_inert_for_a_plain_caste(ruleset) -> None:
    # A Twilight cannot learn foreign Charms at all, so the toggle is shown with a
    # note rather than hidden — an ST hunting for it should be told why it is inert.
    rows = {r.field: r for r in viewmod.build_house_rules(ruleset, _character())}
    assert "No effect" in rows["st_foreign_charms"].note


def test_foreign_charm_toggle_has_no_note_for_an_eclipse(ruleset) -> None:
    char = Character(id="c", name="E", exalt_type="Solar", caste="eclipse")
    rows = {r.field: r for r in viewmod.build_house_rules(ruleset, char)}
    assert rows["st_foreign_charms"].note == ""


# --------------------------------------------------------------------------- #
# The thaumaturgy picker page — presenter
# --------------------------------------------------------------------------- #

def _thaum_char(occult: int, **kwargs) -> Character:
    char = _character(**kwargs)
    char.abilities[AbilityName.OCCULT] = occult
    return char


def test_arts_are_gated_on_occult(ruleset) -> None:
    v = viewmod.build_thaum_picker(ruleset, _thaum_char(3))
    arts = {a.name: a for a in v.arts}
    assert arts["Summoning"].available          # Occult 1
    assert arts["Exorcism"].available           # Occult 3
    assert not arts["Astrology"].available      # Occult 4
    assert "Occult 4" in arts["Astrology"].reason


def test_only_summoning_offers_aspect_narrowing(ruleset) -> None:
    # p.127 prints the half-cost narrowing option for Summoning alone.
    v = viewmod.build_thaum_picker(ruleset, _thaum_char(5))
    narrowing = {a.name for a in v.arts if a.allows_narrowing}
    assert narrowing == {"Summoning"}


def test_summoning_aspects_carry_their_own_occult_minima(ruleset) -> None:
    # Beasts/Mortals 1, Demons/Elementals 2, Ghosts/Spirits 3 (p.126-129).
    v = viewmod.build_thaum_picker(ruleset, _thaum_char(2))
    summoning = next(a for a in v.arts if a.name == "Summoning")
    by_name = {s.name.casefold(): s for s in summoning.specialties}
    assert by_name["beasts"].available
    assert by_name["demons"].available
    assert not by_name["ghosts"].available


def test_a_held_custom_specialty_is_listed_and_ungated(ruleset) -> None:
    char = _thaum_char(1)
    char.thaumaturgy = ThaumaturgyState(
        art_specialties=[ArtSpecialty(art_id="art.warding", name="Local Fair Folk")])
    v = viewmod.build_thaum_picker(ruleset, char)
    warding = next(a for a in v.arts if a.name == "Warding")
    custom = next(s for s in warding.specialties if s.name == "Local Fair Folk")
    assert custom.owned and custom.available and not custom.printed


def test_the_alchemy_ladder_has_no_gap(ruleset) -> None:
    """The picker used to render an EMPTY fifth rung, because the book prints
    • •• ••• •••• then ••••••. The printed 6 is a typo for 5 (human, 2026-07-30), so
    every rung now carries text and the ladder matches the other three Sciences."""
    v = viewmod.build_thaum_picker(ruleset, _thaum_char(3))
    alchemy = next(s for s in v.sciences if s.name == "Alchemy")
    assert alchemy.max_rating == 5
    assert [r.rating for r in alchemy.levels] == [1, 2, 3, 4, 5]
    assert all(r.description for r in alchemy.levels)


def test_rituals_are_gated_on_occult_equal_to_their_level(ruleset) -> None:
    v = viewmod.build_thaum_picker(ruleset, _thaum_char(2))
    by_level = {}
    for r in v.rituals:
        by_level.setdefault(r.level, []).append(r)
    assert all(r.available for r in by_level[1])
    assert all(r.available for r in by_level[2])
    assert all(not r.available for r in by_level[3])


def test_formulas_carry_no_purchase_gate(ruleset) -> None:
    # The source states an Occult requirement for Arts, aspects and rituals only.
    # Inventing a Science-rating gate for formulas would be a rule we do not have.
    v = viewmod.build_thaum_picker(ruleset, _thaum_char(1))
    assert v.formulas
    assert all(f.available and f.reason == "" for f in v.formulas)


def test_prices_switch_from_bonus_points_to_experience_at_the_lock(ruleset) -> None:
    char = _thaum_char(3)
    assert viewmod.build_thaum_picker(ruleset, char).currency == "BP"
    lifecycle.lock_chargen(char)
    assert viewmod.build_thaum_picker(ruleset, char).currency == "XP"


def test_ritual_price_is_two_plus_one_per_level(ruleset) -> None:
    # BP table p.116: Ritual = 2 + 1/level.
    v = viewmod.build_thaum_picker(ruleset, _thaum_char(5))
    for row in v.rituals:
        assert row.price == 2 + row.level


def test_owned_rows_come_from_the_engine_enumeration(ruleset) -> None:
    char = _thaum_char(3)
    char.thaumaturgy = ThaumaturgyState(
        arts=["art.warding"],
        sciences=[ScienceRating(science_id="science.alchemy", rating=2)])
    v = viewmod.build_thaum_picker(ruleset, char)
    kinds = {r.kind for r in v.owned}
    assert kinds == {"art", "science"}
    # Art 5 BP + Alchemy's 5+7 ladder = 17.
    assert v.total == 17


def test_magic_for_everyone_note_appears_before_anything_is_bought(ruleset) -> None:
    char = _thaum_char(4, house_rules=HouseRules(magic_for_everyone=True))
    v = viewmod.build_thaum_picker(ruleset, char)
    assert v.free_picks == 2
    assert "2 free purchase" in v.free_note


def test_the_free_grant_zeroes_the_dearest_eligible_purchase(ruleset) -> None:
    # An Art is never free; a level-3 ritual is, and is the dearest eligible thing
    # here, so the grant must land on it rather than on the 1-point formula.
    char = _thaum_char(4, house_rules=HouseRules(magic_for_everyone=True))
    char.thaumaturgy = ThaumaturgyState(
        arts=["art.warding"],
        rituals=[RitualEntry(ritual_id="ritual.warding-of-undue-influence",
                             level=3, orientations=[Orientation.REALM])],
        formulas=[FormulaEntry(formula_id="formula.wound-cleansing-unguent",
                               level=1, orientations=[Orientation.REALM])])
    v = viewmod.build_thaum_picker(ruleset, char)
    by_kind = {r.kind: r for r in v.owned}
    assert by_kind["art"].cost == 5 and not by_kind["art"].free
    assert by_kind["ritual"].cost == 0 and by_kind["ritual"].free


def test_the_chargen_science_cap_only_binds_at_chargen(ruleset) -> None:
    char = _thaum_char(5, house_rules=HouseRules(restrict_chargen_science_rating=True))
    char.thaumaturgy = ThaumaturgyState(
        sciences=[ScienceRating(science_id="science.geomancy", rating=3)])
    geomancy = next(s for s in viewmod.build_thaum_picker(ruleset, char).sciences
                    if s.name == "Geomancy")
    assert not geomancy.can_raise
    assert "p.113" in geomancy.reason
    # Locked, the restriction is spent: it caps what may be BOUGHT at creation.
    lifecycle.lock_chargen(char)
    geomancy = next(s for s in viewmod.build_thaum_picker(ruleset, char).sciences
                    if s.name == "Geomancy")
    assert geomancy.can_raise


def test_a_ghost_style_splat_is_flagged_unusable_not_barred(ruleset) -> None:
    # thaumaturgy_usable False means "holds it, may never use it" (p.114) — the page
    # must still offer every purchase, with a note.
    unusable = [e for e in ruleset.exalts.values() if not e.thaumaturgy_usable]
    if not unusable:
        pytest.skip("no shipped splat is barred from using thaumaturgy")
    char = _thaum_char(3)
    char.exalt_type = unusable[0].id
    v = viewmod.build_thaum_picker(ruleset, char)
    assert not v.usable and v.usable_note
    assert any(a.available for a in v.arts)


# --------------------------------------------------------------------------- #
# Render tests (NiceGUI User simulation)
#
# These exist because a `ui.select` whose value is not among its options raises at
# RENDER time and no unit test above would catch it — the thaumaturgy page carries
# an orientation select and four sub-tabs seeded from state. One route per test,
# per tests/test_gm.py's note.
# --------------------------------------------------------------------------- #

MAIN = "tests/_ui_main.py"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_picker_offers_a_thaumaturgy_page(user: User) -> None:
    await user.open('/thaum-picker')
    await user.should_see("Thaumaturgy")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_thaumaturgy_page_renders_its_sub_tabs_and_arts(user: User) -> None:
    await user.open('/thaum-picker')
    await user.should_see("Arts")
    await user.should_see("Sciences")
    await user.should_see("Rituals")
    await user.should_see("Formulas")
    await user.should_see("Summoning")
    await user.should_see("Astrology")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_thaumaturgy_page_prices_in_bonus_points_before_the_lock(user: User) -> None:
    await user.open('/thaum-picker')
    await user.should_see("5 BP")            # an Art


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_thaumaturgy_page_prices_in_experience_once_locked(user: User) -> None:
    await user.open('/thaum-picker-inplay')
    await user.should_see("5 XP")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_sciences_tab_renders_the_alchemy_ladder(user: User) -> None:
    await user.open('/thaum-picker')
    user.find("Sciences").click()
    await user.should_see("Alchemy")
    await user.should_see("Weather Working")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_rituals_tab_renders_the_orientation_select(user: User) -> None:
    # The select is seeded from state["orientation"]; a value outside its options
    # would raise here rather than in any unit test.
    await user.open('/thaum-picker')
    user.find("Rituals").click()
    await user.should_see("Learn as")
    await user.should_see("Realm")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_owned_thaumaturgy_shows_the_bought_summary(user: User) -> None:
    await user.open('/thaum-picker-owned')
    await user.should_see("Bought")
    await user.should_see("Warding")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_magic_for_everyone_is_announced_on_the_page(user: User) -> None:
    await user.open('/thaum-picker-mfe')
    await user.should_see("Magic for Everyone")


# --- the Storyteller-options tab -------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_st_tab_renders_both_scope_groups(user: User) -> None:
    await user.open('/st-options')
    await user.should_see("TABLE-WIDE")
    await user.should_see("THIS CHARACTER")
    await user.should_see("Magic for Everyone")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_st_tab_shows_every_toggle(user: User) -> None:
    await user.open('/st-options')
    await user.should_see("Cap starting rituals at level 3")
    await user.should_see("Cap starting Sciences at 3 dots")
    await user.should_see("May start play knowing foreign Charms")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_st_tab_toggle_writes_through_to_the_character(user: User) -> None:
    # Asserted through the UI rather than by reaching back into _ui_main's character
    # (that module's routes are deliberately one-per-test). The live note only appears
    # once the flag is actually set, so seeing it proves the write reached the model
    # AND that the row re-read it — this character has Occult 0, so the grant is 0.
    await user.open('/st-options-eclipse')
    await user.should_not_see("Granting nothing yet")
    user.find("Magic for Everyone").click()
    await user.should_see("Granting nothing yet")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_st_tab_is_read_only_once_locked(user: User) -> None:
    await user.open('/st-options-locked')
    await user.should_see("Chargen is locked")
    await user.should_see("Unlock")


# --------------------------------------------------------------------------- #
# The purchase functions (ui/picker module level)
#
# These mutate the save, so they are tested directly rather than through a click:
# several buy buttons legitimately share a label ("5 BP" is every Art), which makes
# clicking one in particular impossible from the User simulation.
# --------------------------------------------------------------------------- #

def test_thaumaturgy_state_is_not_created_until_a_purchase(ruleset) -> None:
    char = _thaum_char(3)
    assert char.thaumaturgy is None
    pickermod.buy_thaum_art(ruleset, char, "art.summoning")
    assert char.thaumaturgy is not None


def test_buying_an_art_at_chargen_appends_it(ruleset) -> None:
    char = _thaum_char(3)
    pickermod.buy_thaum_art(ruleset, char, "art.warding")
    assert char.thaumaturgy.arts == ["art.warding"]
    assert not char.xp_log            # chargen spends bonus points, not experience


def test_buying_an_art_refuses_below_its_occult_minimum(ruleset) -> None:
    char = _thaum_char(2)
    with pytest.raises(advancement.AdvancementError, match="Occult 4"):
        pickermod.buy_thaum_art(ruleset, char, "art.astrology")
    assert char.thaumaturgy is None or not char.thaumaturgy.arts


def test_buying_an_art_twice_is_refused(ruleset) -> None:
    char = _thaum_char(3)
    pickermod.buy_thaum_art(ruleset, char, "art.warding")
    with pytest.raises(advancement.AdvancementError):
        pickermod.buy_thaum_art(ruleset, char, "art.warding")


def test_buying_an_art_in_play_logs_experience(ruleset) -> None:
    char = _thaum_char(3)
    lifecycle.lock_chargen(char)
    char.xp_earned = 20
    pickermod.buy_thaum_art(ruleset, char, "art.warding")
    assert [e.target for e in char.xp_log] == ["thaum_arts"]
    assert char.xp_log[0].cost == 5


def test_dropping_an_art_removes_it(ruleset) -> None:
    char = _thaum_char(3)
    pickermod.buy_thaum_art(ruleset, char, "art.warding")
    pickermod.drop_thaum_art(ruleset, char, "art.warding")
    assert char.thaumaturgy.arts == []


def test_a_specialty_does_not_require_owning_the_art(ruleset) -> None:
    # Stated three times in the source (p.126 twice, p.116 footnote). This must never
    # become a prerequisite.
    char = _thaum_char(1)
    pickermod.buy_thaum_specialty(ruleset, char, "art.warding", "Ghosts")
    assert char.thaumaturgy.arts == []
    assert char.thaumaturgy.art_specialties[0].name == "Ghosts"


def test_a_narrowed_aspect_stores_the_flag_and_halves_the_cost(ruleset) -> None:
    # p.127: narrowing "halves the cost of the aspect and should be noted on the
    # character sheet" — so it is stored, not inferred from the name.
    plain = _thaum_char(3)
    pickermod.buy_thaum_specialty(ruleset, plain, "art.summoning", "Beasts")
    narrow = _thaum_char(3)
    pickermod.buy_thaum_specialty(ruleset, narrow, "art.summoning", "Beasts",
                                  narrowed=True)
    assert narrow.thaumaturgy.art_specialties[0].narrowed is True
    plain_total = viewmod.build_thaum_picker(ruleset, plain).total
    narrow_total = viewmod.build_thaum_picker(ruleset, narrow).total
    assert plain_total == 2 and narrow_total == 1      # halved, rounded up


def test_a_duplicate_specialty_is_refused_case_insensitively(ruleset) -> None:
    char = _thaum_char(3)
    pickermod.buy_thaum_specialty(ruleset, char, "art.warding", "Ghosts")
    with pytest.raises(advancement.AdvancementError, match="already known"):
        pickermod.buy_thaum_specialty(ruleset, char, "art.warding", "ghosts")


def test_a_summoning_aspect_below_its_own_minimum_is_refused(ruleset) -> None:
    char = _thaum_char(2)          # Ghosts needs Occult 3
    with pytest.raises(advancement.AdvancementError, match="Occult 3"):
        pickermod.buy_thaum_specialty(ruleset, char, "art.summoning", "Ghosts")


def test_raising_a_science_walks_its_ladder(ruleset) -> None:
    char = _thaum_char(3)
    pickermod.raise_thaum_science(ruleset, char, "science.geomancy")
    pickermod.raise_thaum_science(ruleset, char, "science.geomancy")
    held = char.thaumaturgy.sciences[0]
    assert (held.science_id, held.rating) == ("science.geomancy", 2)
    # 5 for the first dot, 7 for the second (the Grabowski clarification).
    assert viewmod.build_thaum_picker(ruleset, char).total == 12


def test_every_science_now_stops_at_five(ruleset) -> None:
    """Alchemy used to be the exception, reaching six. `max_rating` stays per-Science —
    the machinery is still right, it simply has nothing exceptional to express now."""
    char = _thaum_char(5)
    for _ in range(5):
        pickermod.raise_thaum_science(ruleset, char, "science.alchemy")
    with pytest.raises(advancement.AdvancementError, match="maximum"):
        pickermod.raise_thaum_science(ruleset, char, "science.alchemy")
    for _ in range(5):
        pickermod.raise_thaum_science(ruleset, char, "science.enchantment")
    with pytest.raises(advancement.AdvancementError, match="maximum"):
        pickermod.raise_thaum_science(ruleset, char, "science.enchantment")


def test_the_chargen_science_cap_refuses_a_fourth_dot(ruleset) -> None:
    char = _thaum_char(5, house_rules=HouseRules(restrict_chargen_science_rating=True))
    for _ in range(3):
        pickermod.raise_thaum_science(ruleset, char, "science.geomancy")
    with pytest.raises(advancement.AdvancementError, match="p.113"):
        pickermod.raise_thaum_science(ruleset, char, "science.geomancy")


def test_lowering_a_science_to_zero_removes_it(ruleset) -> None:
    char = _thaum_char(3)
    pickermod.raise_thaum_science(ruleset, char, "science.geomancy")
    pickermod.lower_thaum_science(ruleset, char, "science.geomancy")
    assert char.thaumaturgy.sciences == []


def test_learning_a_ritual_records_its_orientation(ruleset) -> None:
    char = _thaum_char(3)
    pickermod.buy_thaum_entry(ruleset, char, "ritual",
                              "ritual.warding-of-undue-influence", Orientation.NORTH)
    entry = char.thaumaturgy.rituals[0]
    assert entry.orientations == [Orientation.NORTH]
    assert entry.level == 3


def test_learning_a_ritual_above_your_occult_is_refused(ruleset) -> None:
    char = _thaum_char(2)
    with pytest.raises(advancement.AdvancementError, match="Occult 3"):
        pickermod.buy_thaum_entry(ruleset, char, "ritual",
                                  "ritual.warding-of-undue-influence",
                                  Orientation.REALM)


def test_relearning_a_ritual_points_at_orientations_instead(ruleset) -> None:
    char = _thaum_char(3)
    pickermod.buy_thaum_entry(ruleset, char, "ritual",
                              "ritual.calling-the-flames-beneficence",
                              Orientation.REALM)
    with pytest.raises(advancement.AdvancementError, match="orientation"):
        pickermod.buy_thaum_entry(ruleset, char, "ritual",
                                  "ritual.calling-the-flames-beneficence",
                                  Orientation.NORTH)


def test_extra_orientations_accumulate_and_refuse_duplicates(ruleset) -> None:
    char = _thaum_char(3)
    key = "ritual.calling-the-flames-beneficence"
    pickermod.buy_thaum_entry(ruleset, char, "ritual", key, Orientation.REALM)
    pickermod.add_thaum_orientation(ruleset, char, "ritual", key, Orientation.NORTH)
    assert char.thaumaturgy.rituals[0].orientations == [Orientation.REALM,
                                                       Orientation.NORTH]
    with pytest.raises(advancement.AdvancementError, match="Already known in its North"):
        pickermod.add_thaum_orientation(ruleset, char, "ritual", key,
                                        Orientation.NORTH)


def test_an_extra_orientation_costs_a_flat_point(ruleset) -> None:
    # p.124: each further version is 1 point on top of the spell's own cost.
    char = _thaum_char(3)
    key = "ritual.calling-the-flames-beneficence"
    pickermod.buy_thaum_entry(ruleset, char, "ritual", key, Orientation.REALM)
    before = viewmod.build_thaum_picker(ruleset, char).total
    pickermod.add_thaum_orientation(ruleset, char, "ritual", key, Orientation.SOUTH)
    assert viewmod.build_thaum_picker(ruleset, char).total == before + 1


def test_an_extra_orientation_in_play_is_its_own_log_row(ruleset) -> None:
    # The reason orientation was built in from the start: "bought ritual X" would
    # otherwise be ambiguous between the ritual and a further version of it.
    char = _thaum_char(3)
    lifecycle.lock_chargen(char)
    char.xp_earned = 30
    key = "ritual.calling-the-flames-beneficence"
    pickermod.buy_thaum_entry(ruleset, char, "ritual", key, Orientation.REALM)
    pickermod.add_thaum_orientation(ruleset, char, "ritual", key, Orientation.WEST)
    assert [e.target for e in char.xp_log] == ["thaum_rituals",
                                              "thaum_orientations.ritual"]
    assert char.xp_log[-1].cost == 1


def test_a_custom_ritual_can_be_authored(ruleset) -> None:
    char = _thaum_char(3)
    pickermod.buy_custom_ritual(ruleset, char, "Blessing of the Hearth", 2,
                                Orientation.EAST)
    entry = char.thaumaturgy.rituals[0]
    assert entry.ritual_id == "" and entry.name == "Blessing of the Hearth"
    assert entry.level == 2
    assert viewmod.build_thaum_picker(ruleset, char).total == 4     # 2 + level


def test_a_custom_ritual_is_gated_on_occult_like_any_other(ruleset) -> None:
    char = _thaum_char(1)
    with pytest.raises(advancement.AdvancementError, match="Occult 4"):
        pickermod.buy_custom_ritual(ruleset, char, "Overreach", 4, Orientation.REALM)


def test_a_custom_ritual_shows_up_on_the_page_as_custom(ruleset) -> None:
    char = _thaum_char(3)
    pickermod.buy_custom_ritual(ruleset, char, "Blessing of the Hearth", 2,
                                Orientation.EAST)
    v = viewmod.build_thaum_picker(ruleset, char)
    row = next(r for r in v.rituals if r.name == "Blessing of the Hearth")
    assert row.custom and row.owned and row.orientations == ["East"]


def test_a_formula_records_its_science(ruleset) -> None:
    char = _thaum_char(1)
    pickermod.buy_thaum_entry(ruleset, char, "formula",
                              "formula.wound-cleansing-unguent", Orientation.REALM)
    entry = char.thaumaturgy.formulas[0]
    assert entry.science_id == "science.alchemy"
    assert viewmod.build_thaum_picker(ruleset, char).total == 1


def test_dropping_an_entry_removes_it(ruleset) -> None:
    char = _thaum_char(3)
    key = "ritual.calling-the-flames-beneficence"
    pickermod.buy_thaum_entry(ruleset, char, "ritual", key, Orientation.REALM)
    pickermod.drop_thaum_entry(char, "ritual", key)
    assert char.thaumaturgy.rituals == []


# --- the read-only sheet and the XP ledger ---------------------------------- #

def test_the_sheet_groups_thaumaturgy_by_branch(ruleset) -> None:
    char = _thaum_char(3)
    char.thaumaturgy = ThaumaturgyState(
        arts=["art.warding"],
        sciences=[ScienceRating(science_id="science.geomancy", rating=2)])
    rows = dict(viewmod.thaumaturgy_rows(ruleset, char))
    assert rows["Arts"] == ["Warding"]
    assert rows["Sciences"] == ["Geomancy 2"]
    assert "Rituals" not in rows          # empty sections are dropped, not shown as "—"


def test_a_non_thaumaturge_gets_no_sheet_panel(ruleset) -> None:
    assert viewmod.build_sheet_view(ruleset, _character()).thaumaturgy == []


def test_the_sheet_shows_owned_orientations(ruleset) -> None:
    char = _thaum_char(3)
    char.thaumaturgy = ThaumaturgyState(rituals=[RitualEntry(
        ritual_id="ritual.calling-the-flames-beneficence", level=1,
        orientations=[Orientation.REALM, Orientation.NORTH])])
    rows = dict(viewmod.thaumaturgy_rows(ruleset, char))
    assert "Realm, North" in rows["Rituals"][0]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_sheet_renders_the_thaumaturgy_panel(user: User) -> None:
    await user.open('/thaum-sheet')
    await user.should_see("Thaumaturgy")
    await user.should_see("Warding")
    await user.should_see("Geomancy 2")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_sheet_omits_the_panel_for_a_non_thaumaturge(user: User) -> None:
    await user.open('/sheet-desc')
    await user.should_not_see("Thaumaturgy")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_xp_tab_names_thaumaturgy_purchases(user: User) -> None:
    # Without the label branch these rows read "thaum_arts" / "thaum_orientations".
    await user.open('/thaum-xp')
    await user.should_see("Art: Warding")
    await user.should_see("Science: Alchemy 0 → 1")
    await user.should_see("Orientation: Warding of Undue Influence (North)")


# --- the tab bar ------------------------------------------------------------- #

def test_st_options_is_on_the_tab_bar_in_both_stages() -> None:
    # Unlike Edit/XP, which are one slot seen from two sides, the ST tab stays on the
    # bar throughout — it just goes read-only once chargen locks.
    assert "ST" in buildermod.visible_tabs(locked=False)
    assert "ST" in buildermod.visible_tabs(locked=True)


def test_locking_does_not_bump_you_off_the_st_tab() -> None:
    assert buildermod.resolve_tab("ST", locked=True) == "ST"
    assert buildermod.resolve_tab("ST", locked=False) == "ST"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_builder_reaches_the_st_options_tab(user: User) -> None:
    await user.open('/builder-st')
    user.find("ST Options").click()
    await user.should_see("TABLE-WIDE")
    await user.should_see("Magic for Everyone")
