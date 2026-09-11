# Session handoff — 2026-09-11 (the VTT is planned, ruled, and phases P0/P1 are done)

# 👉 YOU ARE HERE

Last FULL suite: **3443 passed · 1 skipped · 2 xfailed · 0 failed** (main PC, `main`,
10m56s), **3446 collected**. **Observed, not computed**, and run after every executable
change of the session. Only docs changed afterwards.

⚠ **THE SUITE NOW HAS TWO `xfailed` TESTS, AND THAT IS NEW.** Both are
`tests/test_session_isolation.py`, both are `xfail(strict=True)`, and both describe the
**target** state of the hosting session refactor — they fail on today's code by design.
**A red run is still a real one.** ⚠ **When the session refactor lands they will XPASS,
which pytest reports as a FAILURE** until whoever fixed it deletes the marker. That is
deliberate; do not "fix" it by weakening an assertion. `docs/testing.md` has the reasoning.

✅ **The arithmetic that was owed is now settled.** The previous handoff carried
**3391 passed / 3392 collected** as *"arithmetic, not an observation"*. This run confirms
it: 3391 + 52 = **3443**, and 3392 + 54 = **3446**. Both columns land exactly.

**Working tree: DIRTY, nothing committed.** ⚠ Last session's handoff made a tree claim that
was already false; **run `git status` and `git log` yourself before acting on this line.**

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

- **P2, the hosting substrate** — `hosting-state-model.md` §3 and §5. **~5 days
  part-time and the riskiest work in the plan.** Nothing blocks it. ⚠ **Re-verify §3.4's
  storage table first**: it was written against NiceGUI **3.13** and the installed version
  is **3.14.0**. All five stores still exist, but `app.storage` now also exposes
  `redis_url` and `redis_key_prefix`, which may bear on the single-process assumption the
  whole design rests on. **Not investigated.**
- **Backfill `source` on the 63 Backgrounds** — still **63/63** missing. A provenance job,
  not a reading job; it needs no pages fed. ⚠ The "~1,800 pages" framing was wrong and was
  corrected 2026-09-11 — do not re-raise it.
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

Almost nothing this session has a UI surface. One thing does:

1. **GM page → a member card → the "Builder" button.** It gained
   `.mark(f"open-in-builder-{index}")`, following the `mark("batch-roll")` convention
   already on that page. `.mark()` sets a CSS marker class. Confirm the button still looks
   and behaves as before **with two or more party members** — the marker is per-index, and
   a wrong index would be a wrong-member handoff. 265 party/GM/adversary tests pass and not
   one of them looks at a real display.

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
