# 0021 — Retire the packaged webapp; the browser product is the hosted site

**Status:** Accepted, 2026-09-26. The human's call: *"let's retire the local webapp build
and point people at the website."* Narrows [0018](0018-qt-port-committed.md), which kept
the NiceGUI webapp as a co-shipping product.

## Problem

A release shipped two desktop products: the packaged webapp (`ExaltedBuilder`, a local
NiceGUI server that opens the user's browser) and the native Qt app (`ExaltedBuilderQt`).
Since 0018 was written, the hosted site went live (P1–P4: accounts, per-account
characters and homebrew, campaigns, the table, the board). That left three ways to get
the NiceGUI builder in a browser and two ways to use the app offline, with the packaged
webapp the weaker offline option — 0018 exists because a packaged browser was not the
native app the human wanted.

## Decision

- **The release ships the Qt app only.** The matrix is 2 OSes x 1 product.
  `pack/exalted-builder.spec`, `pack/run_app.py`, `linux.sh` and `windows.bat` are deleted.
  The `[desktop]` extra no longer installs nicegui.
- **Someone who prefers the browser UI uses the hosted site**, or runs their own server
  (the README's Self-hosting section).
- **`ui/` stays.** It is not the webapp's private code: the hosted server is built from
  it (`server/home.py`, `chrome.py`, `table_custom.py`, `table_roster.py` import
  `ui.builder`, `ui.custom`, `ui.app`, `ui.view`, `ui.wiki_view`).
- **`python -m exalted_builder.ui.builder` stays, as a development entry point.** It is
  the cheap click-through surface: no login, and no `Secure`/`__Host-` cookie that a
  plain-HTTP localhost cannot keep. The `run-server` skill, `start_server.sh` and the
  User-harness tests use it. It is not a shipped product and is not in the release.

## Alternatives rejected

- **Keep shipping both.** Two assets per OS for one audience, and a packaged browser that
  0018 already judged the weaker offline product.
- **Delete `ui/builder.py`'s local entry point too.** Every click-through would then need
  an account and the cookie workaround, for no gain to a user.

## Cost

- **Offline users get Qt only**, so a Qt gap is now a gap with no offline fallback. The
  Qt parity audits found their gap lists to be a lower bound every time
  (`docs/plans/qt-port.md`).
- **Browser users depend on a server being up** and on an account. The hosted site is
  one process on one machine, with no uptime monitor at the time of writing.
- The NiceGUI builder keeps being maintained for the hosted site regardless, so this
  saves packaging and release surface, not UI work.
