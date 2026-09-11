"""The hosted-server side of the application.

This package holds the state that a hosted deployment needs and that the desktop
and Qt shells do not: one context for each browser session, instead of the one
process-wide context `ui/builder.py:main()` builds.

⚠ `session.py` imports no web toolkit. Keep it that way. The wiring that reads a
cookie and calls the registry belongs in `ui/`, not here.

See `docs/plans/hosting-state-model.md` section 3.
"""
