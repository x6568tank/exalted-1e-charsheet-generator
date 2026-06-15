"""Tests for ui.builder helpers that don't need a running server."""

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
