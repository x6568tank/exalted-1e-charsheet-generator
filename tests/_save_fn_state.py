"""The characters and the call log that the tab save-callback test shares.

⚠ This module exists because of the runpy trap. The harness executes
`_save_fn_main.py` by PATH, thus that file becomes a module object that is not
the one the test imports. State that lives in it is written by the pages and
read by nobody. Both sides import THIS module by name, thus both get one object.

`tests/_isolation_names.py` exists for the same reason.
"""

from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character

# One character for each tab. A shared character cannot show which tab called
# back, because the test asserts that the callback received THIS tab's character.
CHARS = {name: Character(id=f"save.{name}", name=f"Save {name}", caste="dawn")
         for name in ("editor", "gear", "advantages", "picker", "combos",
                      "storyteller", "play")}

# The Play tab shows only after the lock.
lifecycle.lock_chargen(CHARS["play"])

# Every call that a tab makes to its save callback, in order. The test clears it.
CALLS: list[Character] = []


def recorder(character: Character):
    """Return a save callback that appends its argument to `CALLS`."""
    def save_fn(saved: Character) -> None:
        CALLS.append(saved)

    return save_fn
