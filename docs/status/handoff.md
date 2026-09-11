# Session handoff — 2026-09-11 (§3.7 shipped; §3 of the hosting model is COMPLETE)

# 👉 YOU ARE HERE

Last FULL suite: **3527 passed · 1 skipped · 0 failed** (10m23s, on the tree described
below). **Observed, not computed.** ⚠ The count moves by machine and by optional
dependency — see `docs/testing.md`, and do not reconcile this against another machine.

**The arithmetic lands, and it was checked by ID rather than by adding up.** HEAD
collected **3483** (= the previous handoff's 3482 + 1 skipped). This tree collects
**3528** = 3527 + 1 skipped. The **+45** is `test_session_context_factory.py` +15,
`test_session_root.py` +7, `test_session_destinations.py` +8, `test_auto_save.py` +15.
A `comm` of the two collected-id lists shows **nothing else added and nothing removed**.
⚠ Two earlier full runs this session were discarded because the tree was still being
edited under them. Do not reuse a suite number taken over a moving tree.

**Working tree: clean as of 2026-09-11.** The §3.7 row is committed on `main`, on top of
`1a9288b`. ⚠ Five handoffs in a row have now made a tree claim; **run `git status` and
`git log` yourself before acting on this line.**

## ✅ SHIPPED this session — per-session destinations + write-through auto-save

Row 5 of `hosting-state-model.md` §3.9, and **the last row of §3. §3 is now complete.**
**§3.7b of that file and the last section of `status/engine-and-ui.md` are the record; do
not restate them here.** What a reader needs before touching anything:

* `server/config.session_root()` reads `EXALTED_SESSION_ROOT` and **raises** when it is
  unset. No default, for the same reason `storage_secret()` has none.
* `session_context_factory(prototype, session_root=None)` → `<root>/<key>/<filename>`.
  With **no** root it keeps the prototype path — that is the desktop, and it is
  deliberate.
* `saving.AutoSave` polls a digest of `model_dump_json()`; `build_app(..., auto_save=)`
  runs it on a `ui.timer` every `saving.AUTOSAVE_SECONDS` (5 s).

### ⚠ A hosted run needs TWO environment variables now, and each raises

`EXALTED_STORAGE_SECRET` and `EXALTED_SESSION_ROOT`. Both raise when absent, on purpose.

### ⚠ NOTHING SHIPPED REACHES THIS YET — and that is the honest scope

All three production callers of `register_pages` (`ui/gm.py:738`, `pack/run_app.py:99`,
`ui/builder.py:714`) are desktop and pass **no** root. So the capability exists, is
tested, and **no shipped entry point turns it on.** Wiring it is §5's job.
**Do not read this row as having deployed hosted saving.** What it removed is the
blocker that made §3.7's auto-save unsafe to build at all.

### 🐞 Two handlers undid the factory, and only the wiring test saw it

**The spec's fix was not sufficient, and this is the finding worth carrying.**
`new_character` and the upload branch of `_apply_loaded` each recomputed the destination
from `persistence.default_save_dir()`, which is process-wide. The factory gave the
session its own directory and **the first click of New took it straight back out**, into
a folder every session shares.

⚠ **The factory's own unit tests pass with this defect present** — the factory *is*
correct, and a later handler overrules it. That is the house bug, type 1, and it is why
"assert on the factory" (which §3.7 rightly demands) is **necessary but not sufficient**.
`tests/test_session_destinations.py` runs the production wiring and clicks New; nothing
else could see it.

The fix is `ctx["home_dir"]`, the one folder a session owns.
⚠ **Do not call `persistence.default_save_dir()` in a handler.**

### 🐞 Sanitising the session key was not enough to keep two sessions apart

`session_dirname` replaces an unsafe character with an underscore, which maps `"a/b"` and
`"a_b"` to **one** directory — this whole section's defect, one level down. A digest of
the original key is now appended whenever a character changed. A plain UUID session id is
unchanged and stays readable.

### ⚠ Auto-save and isolation are ONE switch, on purpose

`register_pages` passes `auto_save=session_root is not None`. The hazard §3.7 names — a
timer over a shared path — **cannot be configured.** Do not give them separate switches.
This spent a mechanism instead of another warning, per
`feedback_turn_a_repeated_warning_into_a_mechanism`; the last row proved a ⚠ in a
docstring does not prevent the mistake it describes.

### ✅ The spec's one unverified precondition is CONFIRMED

Play-tab state serializes: `Character.play` is a real pydantic field (`PlayState`), so
`willpower_spent`, `fatigue`, `health`, `limit`, `clarity_temporary` and `renown` all
reach the digest. ⚠ A tracker added **beside** the Character in future would be invisible
to auto-save, with nothing failing.

### Negative controls, all three run

* Reintroduce the shared path in the factory → the 10 destination cases redden, the 10
  older ones **and the desktop control** stay green. The desktop control is therefore not
  passing vacuously.
* Unwire the `ui.timer` → the two auto-save cases redden, the six destination cases stay
  green.
* Both restored **from a copy taken aside**, not `git checkout`, per
  `feedback_restore_a_probe_from_a_copy_not_git`.

## 👉 NEXT — in rough order of what would bite

- **P2 §5 — the entry point, auth, and the DB. THE NEXT PIECE, and all that remains of
  P2.** Read §5 of `hosting-state-model.md`; it has its own corrections (§5.2 on
  `app.storage.user`, §5.3 on the shared ruleset and the custom layer). What this
  session changes about it:
  - **§5's `server/main.py` is now the thing that turns hosting on.** It must pass
    `session_root=config.session_root()` to `register_pages`. Until it does, every code
    path built this session is dormant.
  - **Re-keying anonymous work at signup**: a DB row is an owner-column update; a
    directory is a move. §3.7 notes this is a mild argument for the DB and **not** a
    reason to build it before the directory.
  - ⚠ **`builder.save()`'s two-way branch is still wrong for a hosted run** — see the
    traps below. Auto-save writes server-side and does **not** go through it, so the
    hosted story is now *"your edits persist, but the Save button still lies."* That is
    a better failure than before and still a failure.

  Carried findings still live for the rest of P2:
  - ⚠ **Run one worker.** The registry holds live `Character` objects, so it can never be
    JSON, so it can never cross processes. Redis is not an alternative — it makes *every*
    NiceGUI store serialized, including `tab`.
  - ⚠ **Do not take the tab-storage shortcut §3.4 describes.** `app.storage.tab` does
    hold a live object and does survive navigation, but it is keyed per *tab* and the
    ruling is per *browser*. It reintroduces the isolation bug one scope down, and
    nothing fails.
  - ⚠ **Tier-1 misuse fails in a background task, not at the assignment.** Putting a
    `Character` into `app.storage.user` succeeds at the line that does it; the
    `TypeError` arrives later as a logged ERROR. Only a `caplog` assertion catches it.
    Tier 1 is still **unused**.
  - ⚠ **`ctx` is a PROTOTYPE**, copied per session by `session_context_factory`. An edit
    to the caller's dict after registration lands where no session sees it. The
    destination is **no longer** part of that copy when a root is supplied.
- **Backgrounds `source` — 51 of 63 DONE. 12 left, and they need a human with a page.**
  `status/backgrounds.md` lists all 12 with their scores. Two are Lunar and have no
  page-marked text on this machine at all. ⚠ **Do not lower the matcher threshold to
  clear them**; that threshold is what stopped ten Mountain Folk rows being written into
  the wrong book. A row with no `source` is honest; a confident wrong one is not.
- **Roll initiative for the whole table — BLOCKED** on the party holding real characters.
  That is phase **P3** of `docs/plans/vtt.md`, so it is scheduled rather than stuck.
  Stays a one-off: initiative's +1d10 is a printed fixed count. Do not generalise it.
- **A content-fidelity SCRIPT** (`tools/`) — diff authored descriptions against pasted
  source and REPORT differences. ⚠ **An option, not a debt.** Nothing is blocked on it
  and it must never go back into the suite.
- ⚠ **The duplicated Custom Merit/Flaw sentence.** Byte-identical in `qt/advantages.py`
  and `ui/advantages.py`, with nothing stopping them drifting. `ui/view.py` owns every
  other shared string and should own this one. A real refactor, not a one-liner.

## ⚠ Traps still live — all carried, none fixed this session

**`builder.save()`'s two-way branch is silently wrong for a third deployment.** Native
gets a dialog, everything else downloads to the browser. The fix was built and **reverted
in full** (`hosting-per-instance.md`). ⚠ **This session's row did NOT address it.**

**The stale server wears a healthy port.** `ui/builder.py` runs `reload=False`; a `kill`
on the PID from `pgrep … | tail -1` kills the WRAPPER, not the listener, and `curl` still
answers **200** off the old build. Get the PID from `ss -ltnp | grep 8080`. **Cost two
sessions.** ⚠ A long-running hosted process makes this worse.

**Any future `ui.run` that registers these routes must pass a `storage_secret`, and
nothing enforces it.** `session_key()` raises without one, on purpose — there is no
fallback key. This already bit `ui/gm.py:main()`.

**The width budget** — `_BOXES_PER_ROW`, the tracker box sizes and `_RAIL_WIDTH` are ONE
budget, and no test can see it. Measure `page._scroll.widget().minimumSizeHint().width()`
against `page._scroll.viewport().width()`.

**The app still reports no version anywhere.** `pyproject.toml` says 1.0.0, no titlebar
string, no About item. ⚠ On a server with players connecting, *"is everyone on the same
build?"* becomes a support question with no answer. Pair it with the launcher trap:
`branding.install_desktop_entry()` writes `Exec=` from `sys.executable`, so the desktop
entry PINS to the first frozen binary that ever ran. ⚠ Check the DATES before blaming the
build; the stale-binary theory has been wrong twice.

## 🖱 Not browser-verified — what a human should click

**The desktop behaviour is unchanged, and that is the cheap claim to check.**
`EXALTED_SESSION_ROOT` is unset on the desktop, so the destination rule and the auto-save
timer are both off. Nothing this session can reach a desktop user.

1. **The desktop builder: Save, Load, New, upload, Print.** They must write where they
   did before. ⚠ **New and the upload path are the two that changed lines** — they read
   `ctx["home_dir"]` instead of calling `default_save_dir()`, and on the desktop those
   are the same folder. Confirm a New character still offers to save beside the
   executable / in the launch folder.
2. **No auto-save toast should ever appear on the desktop.** Auto-save is quiet by
   design, so the thing to confirm is the absence of surprise writes.

**The hosted path needs a real server, and the suite cannot express it:**

3. ⚠ **Run with both variables set and open TWO browsers.**
   `EXALTED_STORAGE_SECRET=… EXALTED_SESSION_ROOT=/tmp/exalted-sessions` — but note
   **no entry point passes the root yet**, so this needs §5 or a throwaway script that
   calls `register_pages(rs, ctx, session_root=…)`. Then: edit a name in each, wait ~5 s,
   and confirm **two directories** under the root, each holding that browser's character.
4. **Carried and still owed from the previous session:** two real browsers, each editing
   a name, then **`/gm` → Builder in one of them** — the second must keep its own
   character. And a **second tab of the SAME browser** must show the *same* character,
   because the key is per browser by ruling (`vtt.md` §8 Q1), not per tab. **That last
   case the suite cannot express at all.**
5. **GM page → a member card → the "Builder" button**, with two or more party members.
   It carries `.mark(f"open-in-builder-{index}")`; the marker is per-index and a wrong
   index would be a wrong-member handoff.

## ❓ Open for the human

- **Nothing is waiting on the human.** All seven of `vtt.md`'s open questions are ruled.
  ⚠ Q3's *ruling* stands but its *mechanism* was wrong; `vtt.md` is corrected in place.
- **No open RULES questions.** This session touched no game values.
- **A design choice made without asking, worth knowing about:** the no-root case keeps
  the prototype path rather than isolating. The polarity is deliberate — forgetting the
  root on the desktop is loud (the file does not update), and a hosted run that forgets
  it gets a raise. Say so if you want the opposite.
- ⚠ **The `close-out` skill is stale about CLAUDE.md.** Its step 3 names four edits to a
  `## Status` heading and a Done/Next TODO. **CLAUDE.md has none of them** — it was
  converted to a pure index, and its own §1 forbids status, counts and dates. Three of
  the four steps describe sections that no longer exist. Worth a fix to the skill.
  **Carried unfixed for two sessions now.**

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The other splats'
Charms were explicitly left as they are (human, 2026-09-01). The caste/aspect-book
Background sweep is closed for planning on the human's hedge of 2026-09-11 — ⚠ a hedge,
not authority to author one.
