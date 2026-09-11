# Session handoff — 2026-09-11 (§5 pieces 1 and 2; hosting runs and Save tells the truth)

# 👉 YOU ARE HERE

Last FULL suite: **PENDING — the final run is in flight; record what it prints.**
⚠ **Observed, not computed.** The count moves by machine and by optional dependency — see
`docs/testing.md`, and do not reconcile this against another machine.

**The expected arithmetic, and it was checked by counting rather than by guessing.** The
previous handoff observed **3527 + 1 skipped**. Piece 1 added
`tests/test_server_main.py` (**+13** → 3540). Piece 2 adds `tests/test_hosted_save.py`
(**+7**) and one guard case in `test_engine_seam.py` (**+1**) → **3548 + 1 skipped**.

⚠ **An intermediate run printed 3651, and that number is wrong to carry.** The guard was
first written parametrized over every `tests/test_*.py`, which is **104 files**, so one
invariant bought 104 cases: 3540 + 7 + 104 = 3651, exactly. It is now ONE case over all
the files, and the message names each offending file and line. **Do not reconcile a
handoff against 3651.**

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

## ✅ ALSO SHIPPED — §5 piece 2, the third save branch

**§5.1b of `hosting-state-model.md` is the record.** `builder.save()` branches hosted /
native / browser. A hosted Save writes `ctx["path"]` with no dialog.

⚠ **The shipped fix is NOT the design `hosting-per-instance.md` sketched**, and the reason
is that document's own warning. There is no `--save-dir`, no `EXALTED_SAVE_DIR`, no
`_SERVER_SAVE_DIR`. That global was safe *"only because this deployment is one player per
process"* — **§3's registry ended that**, so resurrecting it would have re-created the
shared-state bug one layer over. The destination is `ctx["path"]`, which the session owns.

### ⚠ `build_app`'s `auto_save` parameter is RENAMED to `hosted`

It selects **three** behaviours now: the auto-save timer, server-side Save, and — via
`register_pages(hosted=session_root is not None)` — the isolated destination. **Do not
split it into two parameters.** They could then disagree, which is a Save writing
server-side to a destination every session shares: §3.7's hazard on a button.
`tests/test_hosted_save.py` asserts no `auto_save` parameter exists.

### 🐞 There were TWO save sites, and every document said one

`gm.save_party()` carried the **identical** two-way branch, and **`/gm` is a hosted
route**. A hosted Storyteller clicking *"Save party"* got a download and the server kept
no roster. Fixing only `builder.save()` would have marked the trap closed in four
documents and left the same failure one page over — **the house bug, type 1.**

⚠ **It was found by grepping `_native_window` across `ui/`, not by reading the plan**,
which named `builder.save()` and nothing else. `build_gm` now takes the same `hosted` bit
and `register_pages` passes it to both routes. ⚠ **The negative control that matters is
registering `/gm` WITHOUT the bit** — that is the defect exactly, and it reddens.

⚠ **The other four `_native_window` sites in `gm.py` are correct as they are**: the party
PDF export, the party load, the character browse, and the add-to-party dialog shape. Those
are downloads and uploads, which is what a hosted run wants. **Do not convert them.**

### ⚠ The PDF export deliberately keeps TWO branches

A character file is state the server owns; a sheet is an artefact the player keeps, so a
hosted export still downloads. The stale *"same split as save()"* comment at that call
site is corrected in place. **Do not "restore parity".**

### 🐞 My own absence assertion passed against the defect

`should_not_see` **returns on the first attempt at which the text is absent**, so it
raced the async click handler: the download dialog had not opened yet, the check found
nothing, and the case went green **with the two-way branch still in place**. Only the
negative control found it — two of three hosted cases reddened and that one did not.
The fix is a `should_see` that settles the handler first; ⚠ the two lines must stay in
that order. See `feedback_should_not_see_races_async_handlers`.

### Negative controls, all four run, restored from a copy

* Restore the two-way branch in `builder.save` → **all 3 hosted character cases** redden
  (2 of 3 before the `should_not_see` fix above).
* Make the hosted branch unconditional → the **desktop control** reddens, which is what
  shows that branch is genuinely protected.
* Split `hosted` back into two parameters → the one-switch case reddens.
* Drop the `top-bar-save` mark → 4 redden.
* Restore the two-way branch in `gm.save_party` → both party cases redden.
* **Register `/gm` without the hosted bit** → both party cases redden. This is the
  house-bug control: the branch is correct and the route does not pass the switch.

### 🐞 A PRE-EXISTING suite bug that a new FILENAME exposed

The first full run reddened on `test_qt_shell.py::test_shell_new_resets_the_character`,
in a file this session never touched.

**Cause:** after any `nicegui_main_file` test, `sys.modules["exalted_builder"]` is **a
different object** — a hollow namespace stub with `__file__` None and `__path__` `[]`.
Already-imported classes keep working, so almost nothing notices. What breaks is a
**dotted-string monkeypatch target**, which makes pytest re-walk the path from the package
root at call time: `AttributeError: module 'exalted_builder' has no attribute 'qt'`, while
`sys.modules["exalted_builder.qt"]` sits there, present and correct.

⚠ **It is ordering-dependent, thus invisible, thus it had been green for months.**
`test_session_isolation.py` and `test_session_destinations.py` both sort AFTER
`test_qt_shell.py`. `test_hosted_save.py` sorts at 'h' and does not. **Nothing about the
new file is wrong — a test file's NAME was load-bearing.**

**Proved pre-existing, not caused:** forcing either existing main-file test to run ahead of
`test_qt_shell.py` reproduces it exactly. ⚠ **Do not diagnose this by renaming the new
file** — that dodges it and leaves the landmine armed.

**Fixed** at the one violation (import the module, patch the object), and
negative-controlled twice: the rewritten patch still intercepts (flip Yes→No and the case
fails), and the old form still reproduces the ordering bug.

⚠ **The guard is `test_engine_seam.py::test_no_test_patches_by_dotted_string`** — AST, per
test file, message names the offending line. A warning would not have survived; see
`feedback_turn_a_repeated_warning_into_a_mechanism`. **Never patch by dotted string in this
repo.**

### ✅ RULED, and it is the next row: "Download a copy"

Piece 2 left a hosted player with no way to get their character JSON out. **Human,
2026-09-11: *"They should have a way to download a copy."*** **Scoped in §5.1c and NOT
built** — see NEXT below.

## 👉 NEXT — in rough order of what would bite

- **§5 piece 2b — "Download a copy" on a hosted run. RULED, SCOPED, NOT BUILT, and the
  human said he would take it next session.** Full spec in `hosting-state-model.md`
  §5.1c. It is wiring, not a new mechanism — the hosted PDF export already downloads, so
  `ui.download.content` is proven on that path. Three things the spec insists on:
  - ⚠ **The helpers exist but are UNREACHABLE on a hosted run**, which reads exactly like
    present-and-working. `builder._open_browser_save_dialog` / `_browser_download` and
    `gm._open_browser_party_save` / `_party_download` are all dead on that path now —
    `save()` returns before them.
  - ⚠ **THE TRAP: a download must not repoint the save destination.** Both existing
    helpers set `ctx["path"]` / `ctx["party_path"]` from the typed filename. That is right
    on the desktop, where the download *is* the save. Hosted, it **moves where the
    auto-save timer writes**, to a name typed into a download box, silently, on a 5-second
    timer. **Reuse them unchanged and you ship that.**
  - ⚠ **TWO sites again** — the character and the party. Piece 2's whole finding was that
    the singular description hid a second site. Do not repeat it.
  - **Shape is RULED: hosted only** (human, 2026-09-11 — *"hosted only, yes"*). A
    "Download a copy" button beside Save, gated on the **same `hosted` bit**, not a fourth
    switch. ⚠ **The desktop is untouched** — in a plain browser its Save already *is* the
    download dialog, so an always-present button would duplicate it. Not a parity port.
  - The tests must assert `ctx` is **unchanged** after a download, not merely that a
    download happened. The latter passes with the trap fully present. Plus the gate in
    **both** directions — present hosted, absent not-hosted.
  - ⚠ It is the **smallest row left**, smaller than piece 2: ~15 lines over two files in
    front of helpers that already exist. The `ctx` trap is the only thing that can make it
    expensive.
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

✅ **`builder.save()`'s two-way branch is STRUCK — it is fixed, not carried.** Four
documents described it; all four are corrected. ⚠ Do not re-assert it from an older copy.

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
4. **The Save button on the hosted server.** It must write into that browser's session
   directory and toast *"Saved …"* — **no download, no filename prompt.** ⚠ Then click
   Save in the OTHER browser and confirm the two files stay separate.
5. **The Save button on the DESKTOP still opens the filename prompt and downloads.** That
   branch is untouched and the harness covers it, but the two branches now sit in one
   function and a human sees the difference in one click each.
6. **`/gm` → "Save party" on the hosted server.** It must write a `.party.json` into that
   session's directory and toast *"Saved party to …"* — no download.

## ❓ Open for the human

- **Nothing is waiting on the human** to proceed. All seven of `vtt.md`'s questions are
  ruled; the hosted-download question raised this session is **ruled too** (yes — §5.1c),
  and §5.3's per-user ruleset question belongs to piece 4.
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
