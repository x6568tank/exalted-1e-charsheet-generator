"""Tests for engine.dice — the dumb roller (decision 0019).

The boundary this file defends is 0019's no-wire rule: the roller takes a COUNT
and never a roll. Several tests below assert absences — no character, no
`RollDefinition`, no name on a result — because that gap is the whole safety
mechanism and nothing else in the suite can notice it going away.

The arithmetic under test is two printed rules: the Rule of Ten (core p.90, a 10
is two successes) and the Rule of One (p.89, no success plus at least one 1 is a
botch, and 1s never subtract).
"""

import inspect
import random

import pytest

from exalted_builder.engine import dice
from exalted_builder.ui import view as viewmod


class _Fixed(random.Random):
    """An RNG that deals a scripted sequence of faces, so a test can state the
    dice it means instead of hunting for a seed that produces them."""

    def __init__(self, faces):
        super().__init__(0)
        self._faces = list(faces)

    def randint(self, a, b):
        return self._faces.pop(0)


def _roll(faces, **kw):
    return dice.roll(len(faces), rng=_Fixed(faces), **kw)


# --- the Rule of Ten (core p.90) -----------------------------------------

def test_a_ten_counts_as_two_successes():
    assert _roll([10, 7, 2]).successes == 3


def test_plain_counting_is_not_what_ships():
    """⚠ The regression this file exists for: `len([d for d in f if d >= tn])`
    agrees with the rule on every roll that contains no 10."""
    result = _roll([10, 10, 6])
    assert len([d for d in result.faces if d >= 7]) == 2
    assert result.successes == 4


def test_doubles_tens_off_makes_a_ten_one_success():
    assert _roll([10, 7, 2], doubles_tens=False).successes == 2


def test_doubling_is_on_by_default():
    assert dice.roll(1, rng=_Fixed([10])).doubles_tens is True


def test_only_a_literal_ten_doubles_on_a_smaller_die():
    """The page names the face, not the die's maximum: a d6 has no 10 to double."""
    assert _roll([6, 6], die_faces=6, target_number=5).successes == 2


# --- the Rule of One (core p.89) -----------------------------------------

def test_no_success_and_a_one_is_a_botch():
    assert _roll([1, 4, 5]).botch is True


def test_a_failure_with_no_one_is_not_a_botch():
    assert _roll([2, 4, 5]).botch is False


def test_one_success_ignores_every_one():
    result = _roll([1, 1, 9])
    assert result.successes == 1
    assert result.botch is False


def test_ones_never_subtract_successes():
    """⚠ Another edition's convention. If this test ever fails because someone
    'fixed' the count, the page (p.89) is the arbiter: 1s are IGNORED."""
    assert _roll([1, 1, 1, 9, 9]).successes == 2


def test_can_botch_off_suppresses_the_botch():
    result = _roll([1, 4, 5], can_botch=False)
    assert result.botch is False
    assert result.successes == 0


def test_botching_is_on_by_default():
    assert dice.roll(1, rng=_Fixed([1])).can_botch is True


# --- the rest of the arithmetic ------------------------------------------

def test_target_number_defaults_to_seven():
    assert _roll([6]).successes == 0
    assert _roll([7]).successes == 1


def test_target_number_is_settable():
    assert _roll([6], target_number=6).successes == 1


def test_zero_dice_is_a_legal_empty_roll():
    """A pool can fall below one die (`PoolBreakdown.below_one`), so the player
    can legitimately have none to pick up. That is not an error."""
    result = dice.roll(0, rng=_Fixed([]))
    assert result.faces == ()
    assert result.successes == 0
    assert result.botch is False


def test_a_negative_count_is_rejected():
    with pytest.raises(ValueError):
        dice.roll(-1)


def test_an_absurd_count_is_rejected():
    with pytest.raises(ValueError):
        dice.roll(dice.MAX_DICE + 1)


def test_faces_are_reported_in_the_order_rolled():
    assert _roll([3, 10, 1]).faces == (3, 10, 1)


def test_ones_and_tens_are_available_for_display():
    result = _roll([1, 1, 10, 4])
    assert (result.ones, result.tens) == (2, 1)


def test_summary_states_the_count_without_naming_a_roll():
    assert _roll([10, 7, 2]).summary == "3 successes"
    assert _roll([2, 3]).summary == "Failure"
    assert _roll([1, 3]).summary == "Botch"
    assert _roll([9]).summary == "1 success"


def test_the_rng_is_injectable_and_seeding_repeats_a_roll():
    """A roller that cannot be seeded cannot be tested (0019)."""
    a = dice.roll(20, rng=random.Random(12345))
    b = dice.roll(20, rng=random.Random(12345))
    assert a.faces == b.faces


def test_the_default_rng_produces_faces_in_range():
    faces = dice.roll(dice.MAX_DICE).faces
    assert len(faces) == dice.MAX_DICE
    assert all(1 <= f <= 10 for f in faces)


# --- decision 0019's no-wire rule ----------------------------------------

def test_the_roller_takes_a_count_and_never_a_roll():
    """⚠ 0019's load-bearing clause. A `RollDefinition`, a `Character` or a
    `PoolBreakdown` in this signature is the wire the record exists to prevent —
    once the roller knows WHICH roll it is, 'add the Charm dice' is a small
    change, and that is 0008's open-ended job."""
    params = set(inspect.signature(dice.roll).parameters)
    assert params == {
        "count", "target_number", "die_faces", "doubles_tens", "can_botch", "rng"}


def test_a_result_carries_no_name_for_the_roll():
    """The label is the player's free text and lives on the surface, not here.
    A name on the result is the app claiming the pool was right."""
    fields = set(vars(dice.roll(1, rng=_Fixed([5]))))
    assert not fields & {"name", "label", "roll", "roll_id", "definition"}


def test_the_module_imports_nothing_from_the_character_or_rules_models():
    """The roller is pure and knows no game objects, so a future wire has to be
    written as an import first — which this fails on."""
    imported = {n for n, v in vars(dice).items() if inspect.ismodule(v)}
    assert imported == {"random"}
    referenced = {getattr(v, "__module__", "") for v in vars(dice).values()}
    assert not [m for m in referenced
                if m.startswith("exalted_builder") and m != dice.__name__]


def test_no_probability_or_odds_helper_is_exposed():
    """0009 barred a success-odds display by name and 0019 keeps that bar — it
    needs no dice to appear, so the absence has to be asserted."""
    exported = [n for n in dir(dice) if not n.startswith("_")]
    assert not [n for n in exported
                if any(w in n.lower() for w in ("odds", "probab", "chance", "expect"))]


# --- the presenter (ui/view.py) ------------------------------------------

def test_state_defaults_both_switches_on():
    state = viewmod.new_roller_state()
    assert (state["doubles_tens"], state["can_botch"]) == (True, True)
    assert state["label"] == ""
    assert state["log"] == []


def test_rolling_prepends_to_the_transcript():
    state = viewmod.new_roller_state()
    state["count"] = 3
    viewmod.roll_dice(state, rng=_Fixed([10, 7, 2]))
    viewmod.roll_dice(state, rng=_Fixed([1, 2, 3]))
    assert [e.outcome for e in state["log"]] == ["Botch", "3 successes"]


def test_the_transcript_is_capped():
    state = viewmod.new_roller_state()
    for _ in range(viewmod.ROLL_LOG_LENGTH + 5):
        viewmod.roll_dice(state, rng=_Fixed([5]))
    assert len(state["log"]) == viewmod.ROLL_LOG_LENGTH


def test_the_label_is_the_players_text_and_is_carried_verbatim():
    state = viewmod.new_roller_state()
    state["label"] = "  Attack on the bandit  "
    entry = viewmod.roll_dice(state, rng=_Fixed([9]))
    assert entry.label == "Attack on the bandit"


def test_an_unlabelled_roll_is_legal():
    """The label is optional — most 1e rolls are in no catalogue at all."""
    assert viewmod.roll_dice(viewmod.new_roller_state(), rng=_Fixed([9])).label == ""


def test_faces_are_classified_for_display():
    state = viewmod.new_roller_state()
    state["count"] = 4
    entry = viewmod.roll_dice(state, rng=_Fixed([10, 8, 1, 4]))
    assert [f.kind for f in entry.faces] == ["double", "hit", "one", "miss"]
    assert entry.faces_text == "10 8 1 4"


def test_a_ten_is_not_a_double_when_the_switch_is_off():
    state = viewmod.new_roller_state()
    state["doubles_tens"] = False
    assert viewmod.roll_dice(state, rng=_Fixed([10])).faces[0].kind == "hit"


def test_detail_records_the_switches_the_roll_was_made_under():
    assert viewmod.roll_detail(5, 7, True, True) == (
        "5 dice · TN 7 · 10s double · can botch")
    assert viewmod.roll_detail(1, 6, False, False) == (
        "1 die · TN 6 · 10s count once · cannot botch")


def test_a_zero_count_rolls_nothing_rather_than_raising():
    """The count field is editable and a pool can fall below one die."""
    state = viewmod.new_roller_state()
    state["count"] = 0
    entry = viewmod.roll_dice(state, rng=_Fixed([]))
    assert entry.faces == () and entry.outcome == "Failure"


def test_the_presenter_takes_no_roll_definition_either():
    """⚠ 0019's no-wire rule at the seam where it is most tempting to break: the
    presenter can see both a `PoolRow` and the roller, so it is the one place a
    later session could join them without touching the engine."""
    params = set(inspect.signature(viewmod.roll_dice).parameters)
    assert params == {"state", "rng"}
    assert not set(vars(viewmod.RollEntry("", (), 0, False, "", ""))) & {
        "roll", "roll_id", "definition", "pool", "character"}


# --- the transcript fold -------------------------------------------------

def test_the_fold_starts_closed():
    """A long session's log is what the fold exists to get out of the way."""
    assert viewmod.new_roller_state()["log_open"] is False


def test_the_split_keeps_the_newest_roll_above_the_fold():
    state = viewmod.new_roller_state()
    for face in (2, 3, 9):
        viewmod.roll_dice(state, rng=_Fixed([face]))
    newest, older = viewmod.roll_log_split(state)
    assert newest.faces[0].value == 9
    assert [e.faces[0].value for e in older] == [3, 2]


def test_the_split_of_an_empty_log_has_no_newest():
    assert viewmod.roll_log_split(viewmod.new_roller_state()) == (None, [])


def test_a_single_roll_leaves_nothing_behind_the_fold():
    state = viewmod.new_roller_state()
    viewmod.roll_dice(state, rng=_Fixed([9]))
    assert viewmod.roll_log_split(state)[1] == []


def test_the_fold_caption_states_how_many_are_hidden():
    assert viewmod.previous_rolls_label(3) == "Previous rolls (3)"
