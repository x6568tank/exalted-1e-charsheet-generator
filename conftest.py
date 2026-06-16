import os
import sys

# Make the package importable when running `pytest` from the project root.
sys.path.insert(0, os.path.dirname(__file__))

# The NiceGUI User-simulation fixture (used by the UI render regression tests).
# `pytest_plugins` is only honoured in the top-level conftest, so it lives here.
pytest_plugins = ["nicegui.testing.user_plugin"]
