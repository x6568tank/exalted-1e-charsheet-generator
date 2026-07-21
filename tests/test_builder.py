"""Tests for ui.builder helpers that don't need a running server."""

from pathlib import Path

from exalted_builder.models.character import Character
from exalted_builder.models.party import PartyMember
from exalted_builder.ui import builder


class _FakeClient:
    def __init__(self, connected: bool) -> None:
        self.has_socket_connection = connected


def test_any_socket_connected_true_when_at_least_one_connected():
    assert builder._any_socket_connected([_FakeClient(False), _FakeClient(True)]) is True


def test_any_socket_connected_false_when_none_connected():
    assert builder._any_socket_connected([_FakeClient(False), _FakeClient(False)]) is False


def test_any_socket_connected_false_when_no_clients():
    assert builder._any_socket_connected([]) is False


# --------------------------------------------------------------------------- #
# The shared context: the builder and the GM party page work on one roster.
# --------------------------------------------------------------------------- #

def _ctx_with_party(*names: str) -> dict:
    ctx = builder.make_context(Character(id="solo", name="Solo"), Path("solo.json"))
    ctx["party"].members = [PartyMember(character=Character(id=n, name=n)) for n in names]
    return ctx


def test_make_context_starts_with_an_empty_party():
    ctx = builder.make_context(Character(id="c"), Path("c.json"))
    assert ctx["party"].members == []
    assert ctx["member"] is None


def test_open_member_shares_the_character_object():
    """The whole design rests on this: the builder edits the SAME object the card
    renders, so changes need no syncing back into the party."""
    ctx = _ctx_with_party("Ashes", "Jade")
    builder.open_member(ctx, 1)
    assert ctx["char"] is ctx["party"].members[1].character
    assert ctx["member"] == 1


def test_open_member_points_saves_at_that_character():
    ctx = _ctx_with_party("Ashes of Dawn")
    builder.open_member(ctx, 0)
    assert ctx["path"].name == "ashes-of-dawn.character.json"


def test_close_member_clears_the_pointer_but_keeps_the_character():
    ctx = _ctx_with_party("Ashes")
    builder.open_member(ctx, 0)
    builder.close_member(ctx)
    assert ctx["member"] is None
    assert len(ctx["party"].members) == 1        # the character is still in the party
