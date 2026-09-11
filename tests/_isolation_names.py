"""The names the session-isolation test and its main file both use.

⚠ This module must stay free of side effects. It exists because
`tests/_isolation_main.py` registers routes when it is imported, and the test
module must not do that outside the simulation. See the note at the top of
`tests/test_session_isolation.py`.
"""

# The name of the character that '/' starts with.
START_NAME = "Unedited"

# The name of the party member, which '/gm' can open in the builder.
MEMBER_NAME = "PartyGuest"

# The name that session A types. No other session can show it.
EDIT_NAME = "AliceEditedThis"
