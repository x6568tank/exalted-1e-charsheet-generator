"""Main file that proves the session cookie secret reaches NiceGUI.

It uses the PRODUCTION helper, `server.config.storage_secret`, and one page that
reads `app.storage.user`. That read raises `RuntimeError` if the secret is absent.

See `docs/plans/hosting-state-model.md` section 3.4, Constraint 3.
"""

from nicegui import app, ui

from exalted_builder.server.config import storage_secret


@ui.page("/")
def index() -> None:
    try:
        app.storage.user["probe"] = "written"
        ui.label(f"TIER ONE OK: {app.storage.user['probe']}")
    except RuntimeError as error:
        ui.label(f"TIER ONE UNAVAILABLE: {error}")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(storage_secret=storage_secret())
