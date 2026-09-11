# Session handoff — 2026-09-11 (the VTT is planned and ruled; P0/P1 done, P2 started)

# 👉 YOU ARE HERE

Last FULL suite: **3462 passed · 1 skipped · 2 xfailed · 0 failed** (**work laptop**,
`main`, 11m47s). **Observed, not computed.** ⚠ The count moves by machine and by optional
dependency — see `docs/testing.md`, and do not reconcile this against another machine.

⚠ **An earlier run in the same session read 3455 and MUST NOT be quoted.** Three files
were edited while it was in flight, so it describes a tree that no longer exists. The
mistake that caused it is worth knowing: `pgrep -c pytest` matches the process NAME, which
is `python`, so it reported zero while the run was alive, and piping through `tail` kept
the output file at zero bytes. **Use `pgrep -af pytest`, and write the log to a file
rather than through a pipe.**

⚠ **THE SUITE NOW HAS TWO `xfailed` TESTS, AND THAT IS NEW.** Both are
`tests/test_session_isolation.py`, both are `xfail(strict=True)`, and both describe the
**target** state of the hosting session refactor — they fail on today's code by design.
**A red run is still a real one.** ⚠ **When the session refactor lands they will XPASS,
which pytest reports as a FAILURE** until whoever fixed it deletes the marker. That is
deliberate; do not "fix" it by weakening an assertion. `docs/testing.md` has the reasoning.

✅ **The arithmetic that was owed is now settled.** The handoff before this one carried
**3391 passed / 3392 collected** as *"arithmetic, not an observation"*. The 3443 run
confirmed it: 3391 + 52 = **3443**. This session then added **19**: 12 registry tests and
7 secret tests. 3443 + 19 = **3462**, on a different machine, which lands exactly.

**Working tree: clean as of the last commit of this session.** ⚠ Two handoffs in a row
made a tree claim that was already false; **run `git status` and `git log` yourself before
acting on this line.**

## ✅ SHIPPED this session, part 2 — P2 has begun, additively

Work done on the **work laptop**, in a short window, which chose the pieces: the two
**purely additive** rows of `hosting-state-model.md` §3.9, and neither invasive one.

**The storage table is re-verified against NiceGUI 3.14.0** — P2's gating task. Two cells
were wrong, the two-tier design survives, and Redis is answered. §3.4 has it all; the
summary is in the P2 entry below. Do not re-open it.

**`exalted_builder/server/` is new, and nothing imports it yet.** That is deliberate.

* `session.py` — `SessionRegistry`: `ctx_for(key)`, a bounded LRU with an idle `sweep()`,
  rehydration through a `factory(key)`, and an `on_evict` hook for §3.7's auto-save.
  ⚠ It departs from §3.4's sketch in two ways ON PURPOSE — a class rather than a
  module-level `_SESSIONS` dict (a module global is itself process-global state, which is
  the shape of the bug being removed, and it leaks between tests), and `factory(key)`
  rather than `ctx_for(key, user_id)` (the registry knows nothing of auth or the DB).
* `config.py` — `storage_secret()`. Reads `EXALTED_STORAGE_SECRET`; with none, mints a
  random per-process key. ⚠ **There is no default secret and there must never be one.**
  A known constant lets anybody forge a session cookie, and every functional test still
  passes while it happens.
* Three `ui.run` call sites now pass it: `ui/builder.py:main()` (both branches),
  `pack/run_app.py`, and `tests/_isolation_main.py` — the last closes §3.4's Constraint 3
  and is what lets P0 reach tier 1 at all. The nine per-screen dev entry points are
  untouched; they use no storage.

### 🐞 A test that passed against the defect it guarded

⚠ **The best thing this session produced.** `test_the_cap_never_evicts_the_session_it_just
_made` passed with the protection deleted. Above `max_sessions=0` the new session is always
the most recently used, so the least-recently-used rule can never select it and the guard
cannot be observed to fail. **A cap of 0 is the one reachable failing case**, and the test
uses it now. This is `CLAUDE.md` §7 exactly — a rule in a place where it does not operate —
and it was found by mutation, not by reading.

**Five mutations were run against the registry and two against the secret.** All seven fail
the intended test now. ⚠ That method is the reason to trust these 19 tests; a green run on
new code proves nothing on its own.

## ✅ SHIPPED this session — the VTT is a plan with rulings, not an idea

The human asked to plan the VTT. The blocking question was *"how hard is a basic
whiteboard/spatial surface?"*, with the scope choice riding on the answer.

**`docs/plans/vtt.md` is the plan and the authority on phasing.** Do not restate it here.
The findings that shaped it:

* **The board is cheap; the substrate under it is expensive, and the table-only option
  needs that same substrate.** So the two options were never a fork — the board is ~15% of
  the total, additive, and severable. **The scope choice was deferred at no cost.**
* Three things make it cheap, all verified in-tree rather than recalled: the custom-canvas
  bridge already ships (`ui/assets.py` → `ui/picker.py:1813` → `emitEvent` →
  `ui/builder.py:150`), `Client.instances` + per-client `run_javascript` is the broadcast
  primitive, and the engine learns nothing.
* **`Table` should be a first-class entity.** The human's rulings on homebrew scope and on
  the GM page arrived separately and both describe it. `HouseRules` already marks each
  field TABLE-WIDE or PER-CHARACTER — **the grain was right before there was a table.**
* **Homebrew "modding" is one new scope, not two new mechanisms.** Decision 0012 shipped
  character-carried copies in 2026-07-29, and its precedence rules already compose. ⚠ The
  hazard: `load_party()` already absorbs every member's homebrew into one library
  (`persistence.py:236-239`) — at table scope that is *simultaneously* the feature asked
  for and an unprompted injection path. **The difference is consent, and nothing in the
  code expresses it.** Ruled: on a table, `absorb_custom=False` and the ST approves.

**All seven open questions are RULED** (§8 of the plan). Q5 — does the board ship —
was answered 2026-09-11: *"Board ships later; assume yes for now, we'll see how it
ships."* ⚠ **Assume yes for PLANNING; the shape is a hedge, not a spec.** It is not
authority to start P4, which still comes after P3 and is still severable.

**Decision 0020 is RATIFIED** — `docs/decisions/0020-the-board-is-dumb.md`, indexed in
`CLAUDE.md` §9 and `docs/decisions/README.md`. *"The board may hold a picture of the table.
It may not hold a model of the table."* Same cut as 0019, and it exists because the moment
a token knows which character it is, the next ask is "how far can I move" — which is 0008,
and no test would fail on the way.

### P0 — the isolation test, confirmed RED

`tests/test_session_isolation.py` + `_isolation_main.py` + `_isolation_names.py`.
Demonstrates `hosting-state-model.md` §3.1 instead of reasoning about it: two sessions
share one `Character`, on `/` and across `/gm` → `/`.

⚠ **The first `/gm` version PASSED and was wrong**, and this is the session's best lesson —
see `docs/lessons.md`. It asserted `should_see(MEMBER_NAME)`, which the GM card **prints**,
so it matched whether or not the navigation happened. Also `find("Builder")` matched
**two** buttons. Now in `lessons.md` as: **when a test navigates, assert on a value the
origin page cannot produce.**

### P1 — re-scoped, because it was already done

⚠ **The third carried plan item this project has found already complete, and the same
cause each time: written from a census nothing re-ran.** `pyproject.toml` already declares
`pydantic` as the only hard dependency. A clean-venv install proves the engine is already
consumable with no toolkit. The carve-out would have touched **491 absolute import sites**
(456 in `tests/`) to buy something already true. **Physical split DEFERRED until
`exalted-table` exists.** §1.1's structure and the private-dependency rule still stand.

What P1 became: **`tests/test_engine_seam.py`** — the boundary is now enforced rather than
merely true. Full detail in `status/engine-and-ui.md`.

### 🐞 And it found a real defect — the thaumaturgy data did not ship

`package-data` named `data/*.json` and `data/charms/*.json`; `data/thaumaturgy/` was added
later and never added there. A wheel carried **189 of 193** data files and **zero**
thaumaturgy. ⚠ **The four release assets were NOT affected** — `pack/*.spec` copies the
tree recursively. **Only `pip install` was**, which is the deployment hosting uses.

⚠ **Nothing reported it, because `rules_db.py:790` treats every thaumaturgy file as
optional — correctly.** A ruled absence and a lost file are the same bytes. Fixed, proven
by rebuild, and `tests/test_packaging.py` now catches the *next* uncovered directory.
Written up in `status/engine-and-ui.md`.

## 👉 NEXT — in rough order of what would bite

- **P2, continued — `register_pages` → per-request `ctx`. THE NEXT PIECE, and the first
  invasive one.** The registry exists and nothing calls it; this is the row that connects
  them. ⚠ **Do not start it in a short window.** It rewires the live entry point, and the
  row after it — `save_path` → `save_fn` — touches **9** signatures plus call sites
  (8 in `ui/`, plus `qt/main_window.py:593`, which §3.5 warns the count of 8 omits).
  ⚠ **The estimate has been quoted two ways: ~5 days is §3 alone; the phase is 10–12 days
  part-time** (`vtt.md:502`, §3 + §5 + auth + DB). Use the larger one.
  **The gate for this row: the two `xfail(strict=True)` tests XPASS, which pytest reports
  as a FAILURE — then delete the markers.** That is the signal the wiring worked.
  Carried findings that bite here:
  - ⚠ **Do not take the tab-storage shortcut §3.4 describes.** `app.storage.tab` does hold
    a live object and does survive navigation, but it is keyed per *tab* and the ruling is
    per *browser*. It reintroduces the isolation bug one scope down, and nothing fails.
  - ⚠ **Run one worker.** The registry holds live `Character` objects, so it can never be
    JSON, so it can never cross processes. Redis is not an alternative — it makes *every*
    NiceGUI store serialized, including `tab`.
  - ⚠ **Any page that reads `app.storage.tab` must be `async` and
    `await context.client.connected()` first.** A page body runs before the client
    connects. This cost is not in §3.9's estimate.
  - ⚠ **Tier-1 misuse fails in a background task, not at the assignment.** Putting a
    `Character` into `app.storage.user` succeeds at the line that does it; the `TypeError`
    arrives later as a logged ERROR. A test only catches it by asserting on `caplog`.
  - ⚠ **`builder.save()`'s two-way branch is the third-deployment trap below, and this row
    is where it bites.**
- **Backgrounds `source` — 51 of 63 DONE 2026-09-11. 12 left, and they need a human with a
  page.** ⚠ **This entry used to say "a provenance job, not a reading job; it needs no pages
  fed." That was wrong**: `source` is `{book, page}` and the page is the whole record. The
  51 were extracted mechanically by `tools/find_background_sources.py`, which scores each
  row's own `description` against the pasted sources; the page convention was calibrated
  against 81 known-good Merit citations (74 exact). **The residue is not more of the same
  job** — `status/backgrounds.md` lists all 12 with their scores. Two are Lunar and have no
  page-marked text on this machine at all. ⚠ **Do not lower the matcher threshold to clear
  them**; that threshold is what stopped ten Mountain Folk rows being written into the
  wrong book. A row with no `source` is honest; a confident wrong one is not.
- **Roll initiative for the whole table — BLOCKED** on the party holding real characters.
  That is now phase **P3** of `docs/plans/vtt.md`, so it is scheduled rather than stuck.
  Stays a one-off: initiative's +1d10 is a printed fixed count. Do not generalise it.
- **A content-fidelity SCRIPT** (`tools/`) — diff authored descriptions against pasted
  source and REPORT differences, across Charms and spells too. ⚠ **An option, not a debt.**
  Nothing is blocked on it and it must never go back into the suite.
- ⚠ **The duplicated Custom Merit/Flaw sentence.** Byte-identical in `qt/advantages.py`
  and `ui/advantages.py`, with nothing stopping them drifting. `ui/view.py` owns every
  other shared string and should own this one. A real refactor, not a one-liner.

## ⚠ Traps still live — all carried, none fixed this session

**The stale server wears a healthy port.** `ui/builder.py` runs `reload=False`; a `kill` on
the PID from `pgrep … | tail -1` kills the WRAPPER, not the listener, and `curl` still
answers **200** off the old build. Get the PID from `ss -ltnp | grep 8080`. **Cost two
sessions.** ⚠ A long-running hosted process makes this worse.

**The width budget** — `_BOXES_PER_ROW`, the tracker box sizes and `_RAIL_WIDTH` are ONE
budget, and no test can see it. Measure `page._scroll.widget().minimumSizeHint().width()`
against `page._scroll.viewport().width()`.

**The app still reports no version anywhere.** `pyproject.toml` says 1.0.0, no titlebar
string, no About item. ⚠ On a server with players connecting, *"is everyone on the same
build?"* becomes a support question with no answer. Pair it with the launcher trap:
`branding.install_desktop_entry()` writes `Exec=` from `sys.executable`, so the desktop
entry PINS to the first frozen binary that ever ran. ⚠ Check the DATES before blaming the
build; the stale-binary theory has been wrong twice.

**`builder.save()`'s two-way branch is silently wrong for a third deployment.** Native gets
a dialog, everything else downloads to the browser — so a hosted Save shows a green
*"Downloading …"* toast over an empty volume. The fix was built and **reverted in full**
(`hosting-per-instance.md`). Whoever adds the third deployment must add the third branch,
and nothing in the code will warn them. ⚠ **P2 hits this.**

## 🖱 Not browser-verified — what a human should click

Almost nothing this session has a UI surface. Two things do:

0. **The app still launches.** `storage_secret` was added to `ui/builder.py:main()` and to
   `pack/run_app.py`, and **no test calls either** — the suite never runs `main()`. Checked
   headlessly on the laptop: the server starts, `/` returns 200 at 507 KB, `/gm` returns
   200, and the log holds no error. ⚠ **That proves it does not crash, and nothing more**
   (`feedback_serve_and_grep_is_not_verification`). The **native** branch
   (`--native`, PySide-backed window) and the **frozen** build were NOT run; both take the
   same argument by the same edit, but neither was executed. ⚠ Also unrun: the `v*` tag's
   four release assets.


1. **GM page → a member card → the "Builder" button.** It gained
   `.mark(f"open-in-builder-{index}")`, following the `mark("batch-roll")` convention
   already on that page. `.mark()` sets a CSS marker class. Confirm the button still looks
   and behaves as before **with two or more party members** — the marker is per-index, and
   a wrong index would be a wrong-member handoff. 265 party/GM/adversary tests pass and not
   one of them looks at a real display.

2. **Nothing for the Backgrounds work.** `source` on a Background has **no read site** —
   checked, not assumed: the four `row.get("source")` sites in `ui/view.py` (4105, 4245,
   4309, 4552) are the homebrew authoring forms for Charms, spells, rituals and gear, and
   they read a custom library row, never `data/backgrounds.json`. ⚠ That is also why a
   wrong citation is invisible: no test and no screen can report one.

## ❓ Open for the human

- **Nothing is waiting on the human.** All seven of the plan's open questions are ruled.
- **No open RULES questions.** Everything this session is either the human's explicit
  ruling of 2026-09-11 or page-cited.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The other splats' Charms
were explicitly left as they are (human, 2026-09-01). The caste/aspect-book Background
sweep is closed for planning on the human's hedge of 2026-09-11 — ⚠ a hedge, not authority
to author one.
