# Session handoff — 2026-09-11 (§5 piece 1 shipped; hosting is no longer dormant)

# 👉 YOU ARE HERE

Last FULL suite: **3540 passed · 1 skipped · 0 failed** (11m02s, on the tree described
below). **Observed, not computed.** ⚠ The count moves by machine and by optional
dependency — see `docs/testing.md`, and do not reconcile this against another machine.

**The arithmetic lands.** The previous handoff observed **3527 passed · 1 skipped**. This
tree is **3540 + 1 skipped**. The **+13** is `tests/test_server_main.py`, which is the
only file added. Nothing else moved, in either direction.

**Working tree: check it yourself.** ⚠ Six handoffs in a row have now made a tree claim.
Run `git status` and `git log` before acting on this line.

## ✅ SHIPPED this session — `server/main.py`, the switch

Piece 1 of §5 of `hosting-state-model.md`. **§5.1a of that file is the record; do not
restate it here.** What a reader needs before touching anything:

* `server/main.py:build_server(session_root=None)` calls
  `register_pages(..., session_root=root)`. With no argument it reads
  `config.session_root()`.
* `main()` reads both environment variables, makes the root, and runs
  `ui.run(reload=False)`. The `build_server` / `main` split exists **so a test can assert
  on the wiring**; `ui.run` is not testable and the one argument this file adds is.
* `config.required_storage_secret()` is new.

### ✅ The previous handoff's headline scope line is now FALSE, on purpose

It said *"NOTHING SHIPPED REACHES THIS YET… no shipped entry point turns it on."* **An
entry point now turns it on.** Everything §3 built — per-session destinations, the
auto-save timer, the registry — is reachable through `python -m exalted_builder.server.main`.

### 🐞 The previous handoff was wrong that both variables raise

It said *"`EXALTED_STORAGE_SECRET` and `EXALTED_SESSION_ROOT`. Both raise when absent, on
purpose."* **`config.storage_secret()` does not raise.** It returns a **random
per-process key**, which is right for the desktop and silently wrong for a server: the key
changes at each restart, so every session cookie becomes invalid, so every browser gets a
new session id, a **new session directory**, and no view of the character the auto-save
timer wrote for it. The server starts and looks healthy.

⚠ **This is why the claim was dangerous rather than merely untidy** — the failure it
describes is invisible, and the doc said the code prevented it.

`config.required_storage_secret()` raises. `config.storage_secret()` is unchanged, and
the desktop still takes the random fallback. ⚠ **Do not call `storage_secret()` from
anything hosted.**

### ⚠ There is no auth, and a mechanism stands in for it

`DEFAULT_HOST` is `127.0.0.1`, **departing from §5.1's `0.0.0.0` sketch** — that sketch
assumes the auth gate, which is piece 3 and is not built.
`check_bind_is_allowed(host, acknowledged=)` raises on a non-loopback bind without
`--public`. **Delete that function when auth lands, not before.** It is a mechanism rather
than a warning per `feedback_turn_a_repeated_warning_into_a_mechanism`; a comment saying
"do not expose this" would not have stopped a `--host 0.0.0.0`.

### ⚠ The prototype path is OUTSIDE the session root, and that is load-bearing

`prototype_context` points the prototype at `<root>/../prototype.character.json`. It is a
**marker**: a prototype path appearing inside a session directory shows the factory
returned the prototype's own path, which is §3.7's defect. ⚠ **A prototype inside the root
would make every `is_relative_to(root)` assertion pass with no isolation at all** — the
`fixture_missing_the_keyed_axis` shape, one layer over.

### Negative controls, all four run, restored from a copy

Per `feedback_restore_a_probe_from_a_copy_not_git`.

* Drop `session_root=` from `build_server` → **4 cases redden**, the other 9 stay green.
* Move the prototype path inside the root → **only** the negative-control case reddens.
* Neuter `check_bind_is_allowed` → only the public-bind case reddens.
* Make `required_storage_secret` fall through to `storage_secret` → **2 cases redden**.

### ✅ A real server was run, and here is exactly what that proved

`EXALTED_STORAGE_SECRET=… EXALTED_SESSION_ROOT=… python -m exalted_builder.server.main
--port 8099`. Two bare `curl`s got **two distinct session ids** in the signed cookie
(`aae506df-…` and `f38112b6-…`), so the per-browser key is real and not a harness artifact.
Both guards were also confirmed live: a `--host 0.0.0.0` and an unset secret each refused
to start with their own message.

⚠ **What it did NOT prove, and this is the honest half.** **No session directory appeared**
— correctly, because `AutoSave` writes on a digest *change* and nothing edited a character.
The edit → two-files step is covered by `tests/test_session_destinations.py` through the
production wiring, **not by this run**. Per `a compensation is a hypothesis`: the live run
is not a substitute for two real browsers, and that click-through item is still owed.

## 👉 NEXT — in rough order of what would bite

- **§5 piece 2 — `builder.save()`'s third branch. The smallest and the most misleading
  thing left.** Native gets a dialog, everything else downloads to the browser, so a
  hosted Save shows a green *"Downloading …"* toast over an empty volume. It was built
  once and **reverted in full** (`hosting-per-instance.md` has the shape). ⚠ **Piece 1
  made this worse in one specific way**: edits now persist by timer, so the hosted story
  is *"your work is safe, but the Save button lies about where it went."*
- **§5 piece 3 — auth.** `/login`, the gate, `bcrypt` (not `passlib`), a `[server]` extra.
  ⚠ **The first piece of this project with no adjacent pattern to copy** — §3 always had
  `register_pages` or `custom_content` to follow. It is also the one place where an
  unreviewed default is a security bug rather than a wrong number.
  **`check_bind_is_allowed` is deleted by this piece.**
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
- ⚠ **The duplicated Merit/Flaw strings — and it is TEN, not one.** Re-derived by
  intersecting the string literals of `qt/advantages.py` and `ui/advantages.py` with `ast`:
  **10 shared literals of 40+ characters**, byte-identical, with nothing stopping them
  drifting. ⚠ **Previous handoffs called this "the duplicated sentence", singular** — a
  one-sentence framing invites a one-line fix that leaves nine behind. `ui/view.py` owns
  every other shared string and should own these.

## ⚠ Traps still live

**`builder.save()`'s two-way branch.** Now the next item rather than a background trap —
see above.

**The stale server wears a healthy port.** `reload=False`; a `kill` on the PID from
`pgrep … | tail -1` kills the WRAPPER, not the listener, and `curl` still answers **200**
off the old build. **Get the PID from `ss -ltnp | grep <port>`.** Cost two sessions.
✅ This session used `ss -ltnp` and the port released cleanly — the recipe works.

**Any `ui.run` that registers these routes must pass a `storage_secret`.** `session_key()`
raises without one, on purpose. `server/main.py` passes the **required** accessor.

**The width budget** — `_BOXES_PER_ROW`, the tracker box sizes and `_RAIL_WIDTH` are ONE
budget, and no test can see it. Measure `page._scroll.widget().minimumSizeHint().width()`
against `page._scroll.viewport().width()`.

**The app still reports no version anywhere.** ⚠ Now worse: there is a runnable server, so
*"is everyone on the same build?"* is a live support question. Pair it with the launcher
trap: `branding.install_desktop_entry()` writes `Exec=` from `sys.executable`. ⚠ Check the
DATES before blaming the build; the stale-binary theory has been wrong twice.

## 🖱 Not browser-verified — what a human should click

**The desktop is untouched.** `server/main.py` is a new module and no desktop entry point
imports it. `config.storage_secret()` is byte-identical.

1. ⚠ **Two real browsers against `python -m exalted_builder.server.main`**, with both
   variables set. Edit a name in each, wait ~5 s, and confirm **two directories** under
   the root, each holding that browser's character. **This is the step the live run above
   could not reach**, and it is the whole point of the session.
2. **A second tab of the SAME browser must show the SAME character** — the key is per
   browser by ruling (`vtt.md` §8 Q1), not per tab. ⚠ **The suite cannot express this at all.**
3. **`/gm` → Builder in one of two browsers** — the other must keep its own character.
4. **The Save button on the hosted server.** ⚠ Expect it to be **wrong** — it downloads to
   the browser. Confirm that is what it does, so piece 2 is fixing an observed behaviour.

## ❓ Open for the human

- **Nothing is waiting on the human** to proceed. All seven of `vtt.md`'s questions are
  ruled, and §5.3's per-user ruleset question belongs to piece 4.
- **No open RULES questions.** This session touched no game values.
- **Two design choices made without asking, both reversible, both worth a look:**
  - **Loopback default + `--public`.** It departs from §5.1's written `0.0.0.0`. Say so if
    you want the sketch honoured instead.
  - **A separate strict secret accessor** rather than making `storage_secret()` itself
    raise. The desktop's random fallback is deliberate and keeping both was the smaller
    change; merging them would break `ui/builder.py:main` and `ui/gm.py:main`.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The other splats'
Charms were explicitly left as they are (human, 2026-09-01). The caste/aspect-book
Background sweep is closed for planning on the human's hedge of 2026-09-11 — ⚠ a hedge,
not authority to author one.
