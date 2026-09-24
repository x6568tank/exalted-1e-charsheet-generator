"""The routing of `ui.navigate` and `ui.notify` in the NiceGUI user simulation.

`tests/conftest.py` sends each call to the simulated user whose client runs the
handler. Without it, the simulation sends the call to the user whose attribute was
read last, and a second open page takes the navigation of a handler.

PRODUCTION wiring: `tests/_auth_main.py`.
"""

from __future__ import annotations

import asyncio

import pytest
from nicegui import ui

pytest.importorskip("bcrypt")

from exalted_builder.server import chrome  # noqa: E402

from .test_table_view import MAIN, _campaign, state  # noqa: E402


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_second_page_does_not_take_the_navigation_of_a_sign_up(create_user) -> None:
    """The Storyteller's page is open. Its outbox reads its user at each JavaScript
    message. A read between the sign-up click and the navigation of the handler
    moved the navigation to the Storyteller."""
    st, _, table, _ = await _campaign(create_user)
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="st-grant-form")
    newcomer = create_user()
    await newcomer.open("/signup")
    newcomer.find(marker="signup-username").type("Newcomer")
    newcomer.find(marker="signup-password").type(state.PASSWORD)
    newcomer.find(marker="signup-confirm").type(state.PASSWORD)

    newcomer.find(marker="signup-submit").click()
    st.javascript_rules  # noqa: B018 - what the outbox of the Storyteller does
    await asyncio.sleep(0.5)

    assert newcomer.back_history[-1] == "/home"
    assert st.back_history[-1] == chrome.table_url(table.id)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_notification_goes_to_the_user_whose_client_sends_it(create_user) -> None:
    st, _, table, _ = await _campaign(create_user)
    other = create_user()
    await other.open("/login")
    await st.open(chrome.table_url(table.id))

    # ⚠ Read the client without `User.__getattribute__`, which moves the globals.
    client = object.__getattribute__(st, "client")
    other.javascript_rules  # noqa: B018 - the globals now point at `other`
    with client:
        ui.notify("for the Storyteller")

    assert st.notify.contains("for the Storyteller")
    assert not other.notify.contains("for the Storyteller")
