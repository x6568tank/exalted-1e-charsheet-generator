# Session handoff — 2026-09-11 (§5 piece 3: auth — the login gate)

# 👉 YOU ARE HERE

Last FULL suite: **3636 passed + 1 skipped** — observed after the second round of the auth
work. The third round (the cookie) added one case to `test_server_main.py`, run on its own
(14 passed): **3637 is COMPUTED, not observed.**
⚠ The count moves by machine and by optional dependency — see `docs/testing.md`, and do
not reconcile this against another machine. ⚠ **`bcrypt` is new and optional**: without
it, `test_user_db.py`, `test_auth_gate.py` and `test_users_cli.py` skip (58 cases).

**The arithmetic agrees.** 3555 (previous handoff) → 3595 after round one (observed) →
3636 after round two (observed): +7 `test_user_db`, +5 `test_auth_gate`, +11
`test_login_throttle`, +12 `test_folder_quota`, +6 `test_users_cli`.

**Working tree: DIRTY, UNCOMMITTED.** `git status` at the time of writing: 10 modified
(including `persistence.py`), 12 new — `server/{auth,db,quota,throttle,users}.py`,
`tests/_auth_main.py`, `tests/_auth_state.py`, and five `tests/test_*.py`. Last commit
`78848e1`. Check `git status` before acting on this line.

## ✅ SHIPPED (not browser-verified) — §5 piece 3, auth

**§5.1d of `docs/plans/hosting-state-model.md` is the record** — the rulings, the
mechanics, the five negative controls and the known limits. What a reader needs first:

* **Rulings, asked before building (human, 2026-09-11):** self-signup page; SQLite
  `users` table now; context and save folder keyed to the **account**
  (`<root>/user-<id>/`), so a player's devices see one character.
* The gate is **`auth.AuthGate`, a middleware** — not a per-page `require_auth()` as the
  §5.1 sketch had. It covers every route by default, `/docs` and `/openapi.json`
  included. `OPEN_PATHS` is the exception list.
* ⚠ **`main()` installs the gate, `build_server` does not.** Starlette refuses
  `add_middleware` after the app starts, and unit tests call `build_server` in a process
  where a User-harness test already started it. `test_server_main.py` asserts `main`
  calls `install_gate` before `ui.run`. **Do not move the call into `build_server`.**
* `check_bind_is_allowed` and `--public` are **deleted**, as §5.1a required. The server
  now needs a third env var: **`EXALTED_DB_PATH`**, no default.
* `[server]` extra in `pyproject.toml`: `nicegui`, `reportlab`, `bcrypt` (not `passlib`).

### ✅ Second round, same session — the human ruled on the known limits

**§5.1d is the record** (a second rulings table, what shipped, controls 6–10, and
"Found on the way, second round"). In short:

* **Usernames are now case-sensitive** (ruling; reverses the first build).
* **Rate limit per username** — `server/throttle.py`. ⚠ Counts an attempt at its
  START, not after bcrypt; do not "fix" that, it is what closes the parallel race.
* **10 MB per account** — `server/quota.py`, through a new
  **`persistence.set_write_guard`** hook in `atomic_write`, installed by `main()`.
  ⚠ Every hosted write goes through `atomic_write`; a new write path that bypasses it
  bypasses the quota.
* **Manual password reset** — `python -m exalted_builder.server.users reset <name>`
  (and `list`). `EXALTED_ADMIN_CONTACT` puts *"Forgot your password? Email …"* on
  `/login`. The human is making `admin@x6568tank.com` for it.

### ✅ Third round — the cookie

**`Secure` ON** (ruling). The cookie is now **`__Host-exalted-session`**
(`server/main.SESSION_COOKIE`): the prefix makes browsers refuse it from any other
subdomain, which closes session fixation via the human's other `x6568tank.com` apps
(Jellyfin, Calibre, Seafile, Filebrowser). ⚠ **Never give it a `domain`** — the browser
then drops it. Checked on a live server's `Set-Cookie`. `.nicegui/` → a deploy concern,
understood.

### ⚠ Known limits still open — §5.1d has each with its cost

A reset does not end existing logins; signup is not rate-limited; no account delete;
homebrew is outside the quota; the session id still does not rotate at login (only the
physical-access case remains); **a LAN player on plain `http://192.168…` cannot log in**
— the Secure cookie needs HTTPS or `localhost`.

## 🎲 Answered this session — the Table replaces `/gm`

The human asked whether a shared Table an ST sets up replaces the GM screen. **Yes —
already ruled** (`vtt.md` §8 Q4 and §1.3): the GM page dissolves into a first-class
`Table` at **P3**. Auth only supplies the user id that Table membership will point at.
**There is deliberately no global admin/ST role on accounts** — Storyteller is a property
of a table.

## 👉 NEXT — in rough order of what would bite

- **Click through auth** (below) and commit.
- **§5 piece 4 — the DB, and §5.3's per-user rulesets.** ⚠ **Measure one merged `RuleSet`
  in memory BEFORE fixing the DB layout.** §5.3 reverses the original plan (per-user is
  *easier* than shared, because shared needs the `load_character` write hazard solved and
  per-user dissolves it) and that reversal has to be decided before the layout, not after.
- **Backgrounds `source` — 51 of 63 DONE. 12 left, and they need a human with a page.**
  `status/backgrounds.md` lists all 12 with their scores. Two are Lunar and have no
  page-marked text on this machine at all. ⚠ **Do not lower the matcher threshold to
  clear them.**
- **Roll initiative for the whole table — BLOCKED** on the party holding real characters.
  That is phase **P3** of `docs/plans/vtt.md`, so it is scheduled rather than stuck.
  Stays a one-off: initiative's +1d10 is a printed fixed count. Do not generalise it.
- **A content-fidelity SCRIPT** (`tools/`) — diff authored descriptions against pasted
  source and REPORT differences. ⚠ **An option, not a debt.** It must never go into the suite.
- ⚠ **The duplicated Merit/Flaw strings — and it is TEN, not one.** Intersecting the
  string literals of `qt/advantages.py` and `ui/advantages.py` with `ast` gives **10 shared
  literals of 40+ characters**, byte-identical, with nothing stopping them drifting.
  ⚠ Older handoffs called this "the duplicated sentence", singular — a one-sentence framing
  invites a one-line fix that leaves nine behind. `ui/view.py` owns every other shared
  string and should own these.

## ⚠ Traps still live

**`config.storage_secret()` does not raise; `config.required_storage_secret()` does.** The
first returns a random per-process key — right for the desktop, silently wrong for a
server (every restart invalidates every session cookie, so every browser gets a new
session directory and loses sight of its auto-saved character). ⚠ **Do not call
`storage_secret()` from anything hosted.** §5.1a.

**Never patch by dotted string in this repo.** After any `nicegui_main_file` test,
`sys.modules["exalted_builder"]` is a hollow stub, and a dotted monkeypatch target fails
by test-file ORDER. `test_engine_seam.py::test_no_test_patches_by_dotted_string` enforces
it. Import the module and patch the object.

**`should_not_see` races async click handlers.** It returns on the first attempt at which
the text is absent. After a click, settle with a `should_see` on something the branch
produces first. See `feedback_should_not_see_races_async_handlers`.

**The prototype path is OUTSIDE the session root, on purpose.** A prototype inside the
root makes every `is_relative_to(root)` assertion pass with no isolation at all. §5.1a.

**The stale server wears a healthy port.** `reload=False`; a `kill` on the PID from
`pgrep … | tail -1` kills the WRAPPER, not the listener, and `curl` still answers **200**
off the old build. **Get the PID from `ss -ltnp | grep <port>`.**

**Any `ui.run` that registers these routes must pass a `storage_secret`.** `session_key()`
raises without one, on purpose. `server/main.py` passes the **required** accessor.

**The width budget** — `_BOXES_PER_ROW`, the tracker box sizes and `_RAIL_WIDTH` are ONE
budget, and no test can see it. Measure `page._scroll.widget().minimumSizeHint().width()`
against `page._scroll.viewport().width()`.

**The app still reports no version anywhere.** There is a runnable server, so *"is
everyone on the same build?"* is a live support question. Pair it with the launcher trap:
`branding.install_desktop_entry()` writes `Exec=` from `sys.executable`. ⚠ Check the DATES
before blaming the build; the stale-binary theory has been wrong twice.

## 🖱 Not browser-verified — what a human should click

1. **Auth, on the hosted server.** Run with all three variables:
   `EXALTED_STORAGE_SECRET=… EXALTED_SESSION_ROOT=… EXALTED_DB_PATH=… python -m exalted_builder.server.main`.
   ⚠ **Browse to `http://localhost:8080`, not `127.0.0.1`.** The cookie is Secure;
   browsers exempt `localhost`. If a correct login lands straight back on the login
   page, the browser refused the cookie — report which browser and address.
   * Open `/` with no login → the login page. Make an account → the builder opens.
   * A wrong password → "Wrong username or password.", and still gated.
   * Open `/gm` logged out → log in → you land on `/gm`, not `/`.
   * **A private window, same account** → the same character (the ruling). A second
     account → a different, empty one.
   * **Log out** on `/` and on `/gm` → the login page; `/` is gated again.
   * Restart the server → still logged in (secret and `.nicegui/` unchanged).
   * Log in as `Harmonious` when the account is `harmonious` → refused (case ruling).
   * Five wrong passwords → the sixth, even correct, says *"Too many failed attempts"*.
   * With `EXALTED_ADMIN_CONTACT` set, the login page shows the address.
   * `python -m exalted_builder.server.users reset <name>` in a terminal → the new
     password works, the old one does not.
2. **Save on the DESKTOP still opens the filename prompt and downloads** (carried).
   Run `python -m exalted_builder.ui.builder`. Confirm the hosted-only buttons —
   **now three: Download a copy, Log out, and the party's Download a copy** — are
   absent there.

⚠ The Qt shell is untouched by this session.

## ❓ Open for the human

- **No open RULES questions.** This session touched no game values.
- **Design choices made without asking, all reversible:**
  - **Rate-limit numbers:** 5 free, 30 s doubling to 15 min, forget after 1 h.
  - **`DEFAULT_HOST` stays loopback** now that `--public` is gone.
  - **No filename prompt on "Download a copy"** (carried).
  - **A separate strict secret accessor** (carried).

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The other splats'
Charms were explicitly left as they are (human, 2026-09-01). The caste/aspect-book
Background sweep is closed for planning on the human's hedge of 2026-09-11 — ⚠ a hedge,
not authority to author one.
