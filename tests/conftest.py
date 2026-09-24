"""Shared test setup for the Qt-port tests (and harmless for every other test).

`QT_QPA_PLATFORM=offscreen` is pinned before any Qt import so the ported-widget tests
run headless; `setdefault` lets a real display override it for a manual look. The
`ruleset` fixture is the app ruleset, loaded once per module (the ported widgets all
consume a RuleSet + Character, the same shape the NiceGUI tests get from _ui_main).
"""

import os

import pytest

import exalted_builder
from exalted_builder import rules_db
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def ruleset():
    return rules_db.load_app_ruleset(Path(exalted_builder.__file__).parent / "data")


# --------------------------------------------------------------------------- #
# The NiceGUI user simulation: route navigate and notify to the correct user
# --------------------------------------------------------------------------- #
#
# ⚠ The simulation keeps ONE `ui.navigate` and ONE `ui.notify` for the process.
# `User.__getattribute__` sets them to the user whose attribute was read last. The
# outbox of each simulated client reads its user at each `run_javascript` message.
# Thus a page of a second user that sends JavaScript (a scroll, for example) while
# a handler awaits takes the navigation of that handler: the WRONG browser goes to
# the page. This made `test_a_character_that_joins_after_the_form_is_drawn_is_not_granted`
# flaky (docs/testing.md).
#
# The patch sends each call to the user whose client runs the handler
# (`context.client`). Outside a client, the call goes where the simulation sends it.

import weakref

from nicegui import context
from nicegui.testing.user import User
from nicegui.testing.user_navigate import UserNavigate
from nicegui.testing.user_notify import UserNotify

_USERS: "weakref.WeakSet[User]" = weakref.WeakSet()


def _field(user: User, name: str):
    """Read `name` of `user` without `User.__getattribute__`, which moves the globals."""
    return object.__getattribute__(user, name)


def _owner() -> User | None:
    """Return the simulated user whose client runs the current code, or None."""
    try:
        client = context.client
    except RuntimeError:
        return None
    for user in list(_USERS):
        if _field(user, "client") is client:
            return user
    return None


_user_init = User.__init__


def _init(self, *args, **kwargs) -> None:
    _user_init(self, *args, **kwargs)
    _USERS.add(self)


User.__init__ = _init


def _routed(method_name: str):
    original = getattr(UserNavigate, method_name)

    def method(self, *args, **kwargs):
        owner = _owner()
        if owner is not None and owner is not self.user:
            return getattr(_field(owner, "navigate"), method_name)(*args, **kwargs)
        return original(self, *args, **kwargs)
    return method


for _name in ("to", "back", "forward", "reload"):
    setattr(UserNavigate, _name, _routed(_name))

_notify_call = UserNotify.__call__


def _notify(self, message, **kwargs) -> None:
    owner = _owner()
    if owner is not None and _field(owner, "notify") is not self:
        return _field(owner, "notify")(message, **kwargs)
    return _notify_call(self, message, **kwargs)


UserNotify.__call__ = _notify
