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
