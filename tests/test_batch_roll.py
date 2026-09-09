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
    """Counts go in through `set_batch_count`, exactly as both shells write them
    — typing dice into a row is what ticks it into the batch, so a test that
    poked `state["counts"]` directly would build a state no surface can produce."""
    state = viewmod.new_batch_state()
    for key, count in counts.items():
        viewmod.set_batch_count(state, key, count)
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
    assert [(r.key, r.name, r.count, r.label) for r in rows] == [
        ("m.taban", "Taban", 4, "")]


def test_an_untouched_row_offers_zero_dice():
    rows = viewmod.batch_rows(viewmod.new_batch_state(), _ROWS)
    assert [(r.key, r.name, r.count, r.label) for r in rows] == [
        ("m.yarak", "Yarak", 0, ""), ("m.taban", "Taban", 0, "")]
    assert [(r.included, r.times, r.rolls) for r in rows] == [
        (False, 1, 0), (False, 1, 0)]


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
    assert set(state) == {"name", "counts", "labels", "included", "times",
                          "target_number", "doubles_tens", "can_botch", "log",
                          "open", "next_key"}


# --- choosing who rolls, and how many times (human's ask, 2026-09-09) -------
#
# ⚠ Both halves stay inside 0019: the tick chooses a CHARACTER, and the repeat
# count is a number the Storyteller types. Neither names a roll.

def test_typing_dice_ticks_the_row_into_the_batch():
    """⚠ Without the auto-tick a Storyteller types dice, presses Roll and gets
    nothing, with the number sitting right there on screen. The silent no-op is
    the reason `set_batch_count` exists instead of a dict write per shell."""
    state = viewmod.new_batch_state()
    viewmod.set_batch_count(state, "m.yarak", 5)
    assert viewmod.batch_rows(state, _ROWS)[0].included


def test_unticking_a_row_sits_it_out_without_clearing_its_dice():
    """Parking a row must not destroy what was typed — that is the whole
    difference between the tick and zeroing the count."""
    state = _state(**{"m.yarak": 3, "m.taban": 2})
    viewmod.set_batch_included(state, "m.yarak", False)
    batch = viewmod.roll_batch(state, _ROWS, rng=_Fixed([9, 9]))
    assert [r.label for r in batch.rolls] == ["Taban"]
    assert viewmod.batch_rows(state, _ROWS)[0].count == 3


def test_a_ticked_row_with_no_dice_still_sits_out():
    """The two ways out of a batch must agree: ticking someone in does not
    conjure dice for them."""
    state = viewmod.new_batch_state()
    viewmod.set_batch_included(state, "m.yarak", True)
    assert viewmod.batch_rows(state, _ROWS)[0].rolls == 0
    assert viewmod.roll_batch(state, _ROWS) is None


def test_one_row_can_roll_several_times():
    state = _state(**{"m.yarak": 1})
    viewmod.set_batch_times(state, "m.yarak", 3)
    batch = viewmod.roll_batch(state, _ROWS, rng=_Fixed([10, 5, 1]))
    assert [r.faces_text for r in batch.rolls] == ["10", "5", "1"]
    assert [r.label for r in batch.rolls] == [
        "Yarak (1 of 3)", "Yarak (2 of 3)", "Yarak (3 of 3)"]


def test_a_single_roll_carries_no_ordinal_suffix():
    """"(1 of 1)" on every line of an ordinary batch would be noise."""
    batch = viewmod.roll_batch(_state(**{"m.yarak": 1}), _ROWS, rng=_Fixed([7]))
    assert batch.rolls[0].label == "Yarak"


def test_repeats_use_the_storytellers_label_when_given():
    state = _state(**{"m.yarak": 1})
    state["labels"]["m.yarak"] = "search the room"
    viewmod.set_batch_times(state, "m.yarak", 2)
    batch = viewmod.roll_batch(state, _ROWS, rng=_Fixed([7, 7]))
    assert [r.label for r in batch.rolls] == [
        "search the room (1 of 2)", "search the room (2 of 2)"]


def test_times_floors_at_one_and_is_capped():
    """⚠ 0 must not become a second way to say "sit out" — the tick owns that,
    and two controls meaning the same thing is how one silently overrides the
    other."""
    state = viewmod.new_batch_state()
    viewmod.set_batch_times(state, "m.yarak", 0)
    assert state["times"]["m.yarak"] == 1
    viewmod.set_batch_times(state, "m.yarak", 999)
    assert state["times"]["m.yarak"] == viewmod.MAX_BATCH_REPEATS


def test_repeat_labels_are_ordinals_and_never_a_roll_name():
    """⚠ 0019's no-wire rule at the new seam: "(2 of 3)" says which of the
    Storyteller's own repeats a line is. A batch may never emit a line naming
    what was rolled."""
    state = _state(**{"m.yarak": 2})
    viewmod.set_batch_times(state, "m.yarak", 2)
    batch = viewmod.roll_batch(state, _ROWS, rng=_Fixed([7, 7, 7, 7]))
    for entry in batch.rolls:
        assert not set(vars(entry)) & {"roll", "roll_id", "definition", "pool"}
        assert entry.label.startswith("Yarak (")


def test_the_batch_detail_counts_the_repeats_not_the_rows():
    state = _state(**{"m.yarak": 1})
    viewmod.set_batch_times(state, "m.yarak", 3)
    batch = viewmod.roll_batch(state, _ROWS, rng=_Fixed([7, 7, 7]))
    assert batch.detail.startswith("3 rolls · ")


# --- the duplicate-id collision (found at the browser, 2026-09-09) ----------

def test_two_characters_sharing_an_id_still_get_their_own_dice():
    """⚠ THE regression test for the bug the human hit: every app path that made
    a blank character handed it the literal "char.new", so two of them in one
    party keyed to ONE row. The second row's count overwrote the first's and both
    characters rolled the same number of dice.

    `new_character_id` stops NEW parties from reaching this shape; parties already
    saved with the duplicate cannot be migrated, so `batch_roster` must keep the
    keys unique on its own.
    """
    from exalted_builder.models.character import Character
    from exalted_builder.models.party import Party, PartyMember
    party = Party(id="p", members=[
        PartyMember(character=Character(id="char.new", name="Yarak", caste="dawn")),
        PartyMember(character=Character(id="char.new", name="Taban", caste="dawn")),
    ])
    rows = viewmod.batch_roster(party)
    assert len({key for key, _ in rows}) == 2
    state = viewmod.new_batch_state()
    viewmod.set_batch_count(state, rows[0][0], 5)
    viewmod.set_batch_count(state, rows[1][0], 3)
    assert [(r.name, r.count) for r in viewmod.batch_rows(state, rows)] == [
        ("Yarak", 5), ("Taban", 3)]
    batch = viewmod.roll_batch(state, rows, rng=_Fixed([7] * 8))
    assert [len(r.faces) for r in batch.rolls] == [5, 3]


def test_a_blank_character_gets_a_unique_id():
    """The root fix. Two blanks made the same way must not be the same record."""
    from exalted_builder.models.character import new_character_id
    assert new_character_id() != new_character_id()


def test_no_app_path_hands_out_a_constant_character_id():
    """⚠ A grep, because the defect was one literal repeated across SEVEN sites in
    both shells — fixing the one the bug surfaced in would have left six."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent / "exalted_builder"
    guilty = [str(p.relative_to(root)) for p in root.rglob("*.py")
              if 'id="char.new"' in p.read_text()]
    assert guilty == [], f"constant character id still created in: {guilty}"
