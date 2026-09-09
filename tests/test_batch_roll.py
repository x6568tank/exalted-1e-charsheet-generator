"""Tests for the GM's batch roll (view.roll_batch) — decision 0019's no-wire
rule applied to several rows at once.

The batch is the shape where the rule is easiest to lose: with six characters on
screen, filling each count from a named roll is the obvious convenience, and it
is exactly what 0019 rejects — the app would be asserting what six sheets are
rolling, and "add their Charm dice" is the next ask. Several tests here assert
that absence, because nothing else can.
"""

import random

import pytest

from exalted_builder.ui import view as viewmod


class _Fixed(random.Random):
    """An RNG dealing a scripted sequence, so a test states the dice it means."""

    def __init__(self, faces):
        super().__init__(0)
        self._faces = list(faces)

    def randint(self, a, b):
        return self._faces.pop(0)


_ROWS = [("m.yarak", "Yarak"), ("m.taban", "Taban")]


def _state(**counts) -> dict:
    state = viewmod.new_batch_state()
    state["counts"].update(counts)
    return state


# --- the batch ------------------------------------------------------------

def test_every_row_with_dice_gets_its_own_roll():
    state = _state(**{"m.yarak": 2, "m.taban": 1})
    batch = viewmod.roll_batch(state, _ROWS, rng=_Fixed([10, 7, 3]))
    assert [r.faces_text for r in batch.rolls] == ["10 7", "3"]
    assert [r.successes for r in batch.rolls] == [3, 0]


def test_a_row_left_at_zero_is_skipped_not_rolled_empty():
    """In a party of six the usual case is three of them rolling."""
    batch = viewmod.roll_batch(_state(**{"m.yarak": 3}), _ROWS, rng=_Fixed([9, 9, 9]))
    assert len(batch.rolls) == 1
    assert batch.rolls[0].label == "Yarak"


def test_no_row_with_dice_rolls_nothing_at_all():
    assert viewmod.roll_batch(viewmod.new_batch_state(), _ROWS) is None


def test_the_batch_carries_the_storytellers_name():
    state = _state(**{"m.yarak": 1})
    state["name"] = "  Join Battle  "
    batch = viewmod.roll_batch(state, _ROWS, rng=_Fixed([5]))
    assert batch.name == "Join Battle"
    assert batch.caption == "Join Battle"


def test_an_unnamed_batch_still_captions_itself():
    """The fold has to say something when collapsed, or it reads as empty."""
    batch = viewmod.roll_batch(_state(**{"m.yarak": 1, "m.taban": 1}), _ROWS,
                               rng=_Fixed([5, 5]))
    assert batch.caption == "2 rolls"


def test_the_row_label_is_the_storytellers_when_they_typed_one():
    state = _state(**{"m.yarak": 1})
    state["labels"]["m.yarak"] = "resisting the poison"
    batch = viewmod.roll_batch(state, _ROWS, rng=_Fixed([8]))
    assert batch.rolls[0].label == "resisting the poison"


def test_the_row_label_falls_back_to_the_characters_name():
    """⚠ A CHARACTER's name, which asserts nothing about a pool — not a ROLL's
    name, which would. The distinction is the whole of 0019's no-wire rule."""
    batch = viewmod.roll_batch(_state(**{"m.taban": 1}), _ROWS, rng=_Fixed([8]))
    assert batch.rolls[0].label == "Taban"


def test_the_switches_apply_to_every_row_in_the_batch():
    state = _state(**{"m.yarak": 1, "m.taban": 1})
    state["doubles_tens"] = False
    batch = viewmod.roll_batch(state, _ROWS, rng=_Fixed([10, 10]))
    assert [r.successes for r in batch.rolls] == [1, 1]
    assert "10s count once" in batch.detail


def test_the_detail_states_the_row_count_and_the_switches():
    batch = viewmod.roll_batch(_state(**{"m.yarak": 1, "m.taban": 2}), _ROWS,
                               rng=_Fixed([5, 5, 5]))
    assert batch.detail == "2 rolls · TN 7 · 10s double · can botch"


def test_one_row_reads_roll_singular():
    batch = viewmod.roll_batch(_state(**{"m.yarak": 1}), _ROWS, rng=_Fixed([5]))
    assert batch.detail.startswith("1 roll ·")


# --- the log and its folds ------------------------------------------------

def test_batches_stack_newest_first_and_are_capped():
    state = _state(**{"m.yarak": 1})
    for _ in range(viewmod.ROLL_LOG_LENGTH + 3):
        viewmod.roll_batch(state, _ROWS, rng=_Fixed([5]))
    assert len(state["log"]) == viewmod.ROLL_LOG_LENGTH
    assert state["log"][0].key > state["log"][1].key


def test_the_newest_batch_opens_and_the_others_keep_their_state():
    state = _state(**{"m.yarak": 1})
    first = viewmod.roll_batch(state, _ROWS, rng=_Fixed([5]))
    state["open"].discard(first.key)                    # the GM collapsed it
    second = viewmod.roll_batch(state, _ROWS, rng=_Fixed([5]))
    assert second.key in state["open"]
    assert first.key not in state["open"]


def test_a_key_is_never_reused_within_a_session():
    """The surface remembers which folds are open BY KEY. A reused key would
    open a batch the Storyteller never touched."""
    state = _state(**{"m.yarak": 1})
    keys = [viewmod.roll_batch(state, _ROWS, rng=_Fixed([5])).key for _ in range(5)]
    assert len(set(keys)) == 5


# --- the roster is keyed, not positional ----------------------------------

def test_counts_follow_the_row_key_when_the_roster_renumbers():
    """⚠ A positional key moves one character's dice onto another's row the
    moment a member is removed — the same defect `clamp_pool_selection` exists
    for. The count belongs to Taban whichever position Taban is in."""
    state = _state(**{"m.taban": 4})
    shrunk = [("m.taban", "Taban")]
    rows = viewmod.batch_rows(state, shrunk)
    assert rows == [("m.taban", "Taban", 4, "")]


def test_an_untouched_row_offers_zero_dice():
    assert viewmod.batch_rows(viewmod.new_batch_state(), _ROWS) == [
        ("m.yarak", "Yarak", 0, ""), ("m.taban", "Taban", 0, "")]


# --- 0019's no-wire rule, at the seam where it is most tempting -----------

def test_the_batch_takes_rows_and_counts_and_never_a_roll():
    """⚠ A `RollDefinition`, a `PoolBreakdown` or a `Character` in this signature
    is the wire. With six rows on screen, pre-filling from a named roll is the
    obvious convenience and the exact thing 0019 rejected."""
    import inspect
    params = set(inspect.signature(viewmod.roll_batch).parameters)
    assert params == {"state", "rows", "rng"}


def test_a_batch_result_carries_no_roll_definition():
    batch = viewmod.roll_batch(_state(**{"m.yarak": 1}), _ROWS, rng=_Fixed([5]))
    assert not set(vars(batch)) & {"roll", "roll_id", "definition", "pool"}
    assert not set(vars(batch.rolls[0])) & {"roll", "roll_id", "definition", "pool"}


def test_the_state_holds_no_pool_or_character_reference():
    """The GM roller's state is counts, labels and switches. A character or a
    ruleset in it would mean something in the batch can look a pool up."""
    state = viewmod.new_batch_state()
    assert set(state) == {"name", "counts", "labels", "target_number",
                          "doubles_tens", "can_botch", "log", "open", "next_key"}
