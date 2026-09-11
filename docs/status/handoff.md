# Session handoff — 2026-09-11 (P2 row 4 committed; §3.7 re-specified before coding)

# 👉 YOU ARE HERE

Last FULL suite: **3482 passed · 1 skipped · 0 failed** (11m23s, on the tree described
below). **Observed, not computed.** ⚠ The count moves by machine and by optional
dependency — see `docs/testing.md`, and do not reconcile this against another machine.

**The arithmetic lands.** 3473 (previous) **+ 9** the new `tests/test_tab_save_fn.py`
= **3482**. Nothing else moved.

**Working tree: clean as of 2026-09-11.** The `save_fn` row is committed as `68bca45`.
⚠ Four handoffs in a row have now made a tree claim; **run `git status` and `git log`
yourself before acting on this line.**

## ✅ SHIPPED this session — `save_path` → `save_fn` across the seven tabs

Row 4 of `hosting-state-model.md` §3.9. **§3.5a of that file and the last section of
`status/engine-and-ui.md` are the record; do not restate them here.** What a reader needs
before touching anything:

`exalted_builder/ui/saving.py` is new — the `SaveFn` type and `save_to_path(path)`, which
writes the file and notifies. **Seven `build_*` tabs take `save_fn` as their third
positional argument** (editor, gear, advantages, picker, combos, play, storyteller). A tab
cannot see a path, thus a tab cannot assume a file system.

**`build_app` alone still takes a `save_path`** — it owns the file dialogs and builds the
fallback context. It derives `tab_save` from the **live** `ctx["path"]` and hands that
down, so a Load, a New or a Save-As is picked up without depending on a refresh.

### 🐞 The parameter being replaced was already dead in the app

Each tab used `save_path` in exactly one place: a `save()` wired to a Save button that
renders **only under `with_header=True`**, and the builder passes `with_header=False` to
all seven. So §3.5's "persistence seam" was reachable only from the seven per-screen dev
entry points.

⚠ **Scope, precisely: this removed a false affordance. It did not add a hosted write
path.** `builder.save()`'s two-way branch is still the live save and still has no third
deployment — a hosted Save still shows a green *"Downloading …"* toast over an empty
volume. **Do not read this row as having fixed hosted saving.**

### 🐞 No test in the suite had ever clicked Save

Seven tabs, seven wirings, zero coverage — a tab could have dropped its third argument
entirely and stayed green. `tests/test_tab_save_fn.py` is the guard: one case per tab,
each asserting the callback ran **once** with **that tab's character by identity**.
⚠ The identity assertion is the load-bearing one; a count alone passes when a tab saves
the wrong character, which a party of several members makes reachable.

**Negative-controlled per tab, and that is why the seven cases are worth trusting.** A
no-op substitution in one tab reddens exactly that tab's case and leaves six green. Seven
for seven. One shared assertion would have hidden six of them.

### 🐞 The two contracts are asymmetric, and it sprang the same day

"Every `build_*` takes a callback now" is false for exactly one function, and the
mechanical sweep converted four `build_app` call sites with the rest. **The failure named
nothing useful**: NiceGUI raised *"argument should be a str or an os.PathLike object …
not 'function'"* from a page handler, six test files deep, naming neither `build_app` nor
the argument. ⚠ **The ⚠ in that docstring was written an hour before it failed to prevent
the mistake it described.** `build_app` now raises a named TypeError, held by
`test_build_app_rejects_a_save_callback`.

### Two corrections to the plan, both in §3.5a

* ⚠ **The "9th save site" warning was wrong.** `qt/` imports only `ui.theme` and
  `ui.view` and calls no `build_*`; `qt/main_window.py:593` is a save SITE, not a
  `save_path` PARAMETER. Nothing in `qt/` was touched.
* **The count that mattered was neither 8 nor 9 but 160** — the `build_*` call sites in
  `tests/_ui_main.py`, which no estimate mentioned and which are most of the diff.

### ⚠ The runpy trap, which will re-bite the next harness

A `nicegui_main_file` is executed **by path**, so it becomes a module object that is *not*
the one the test imports. The first version of the guard recorded into a module-level list
in `_save_fn_main.py` and read an always-empty one — **all seven cases failed for a reason
that was not the defect**, which is the worst kind of red. Shared state must live in a
third module both sides import by name (`tests/_save_fn_state.py`;
`tests/_isolation_names.py` exists for the same reason).

## 👉 NEXT — in rough order of what would bite

- **P2 §3.7 — per-session store + write-through auto-save. THE NEXT PIECE, and the last
  of §3.** 1–1½ days. **§3.7 was rewritten on 2026-09-11 and is the spec — read it, do
  not work from this summary.** What changed and why it matters before you start:
  - 🐞 **Every session shares one save path.**
    `session_context_factory` copies `prototype["path"]` and `["dir"]` verbatim
    (`ui/builder.py:160`). 3.4a isolated the Character, **not the destination**.
    ⚠ Auto-save on today's `tab_save` = **N browsers writing one file on a timer**, no
    error. Invisible only because `with_header=False` leaves no tab save reachable — and
    **auto-save is the live caller that makes it reachable.** Fix the path first.
  - ⚠ **The plan's "one helper on `changed()`" was FALSE — three of seven tabs define
    `changed()`.** The rest funnel through `combos.refresh()` and direct
    `body.refresh()` / `detail.refresh()` calls (~10, ~1, ~12 sites). Hooking `changed()`
    = live in three tabs, silent in four, all green. **The house bug, in the plan that
    warns about it.** Use a dirty-hash `ui.timer` in `build_app` instead — measured
    0.015 ms per poll, and it cannot be wired to the wrong phase because it is not wired
    to a phase. ⚠ Load and New must reset the baseline hash.
  - **Shape: RAM stays a cache, the store becomes the truth.** Write-through, then
    eviction costs a re-read and §3.7's motivation is discharged. ⚠ **Do not port the
    mainstream stateless read-per-request mechanism** — it assumes a fat browser client,
    and NiceGUI is the inverse. It would force tabs to take an id (**§3.6 forbids this**)
    and destroy `open_member`'s by-reference identity (**§3.6 names this, no test
    catches it**).
  - **Where: `<root>/<session_key>/…` now, a SQLite row when auth lands in §5.** `<root>`
    belongs in `server/config.py`. ⚠ The destination is swappable for free — the seven
    tabs see only `save_fn`, which is what the 3.5a refactor bought.
  - **Test first: two sessions get two destinations.** Assert on the factory, not on the
    file; a write-then-read-back test passes when both sessions share one file.
  - ⚠ **Unverified, check before building:** that the play-tab state (`willpower_spent`,
    fatigue, health boxes) lives on the `Character` and not beside it. The dirty hash
    sees only what serializes.

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
    to the caller's dict after registration lands where no session sees it.
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
in full** (`hosting-per-instance.md`). ⚠ **This session's row did NOT address it** — it
is still the live save and P2 still hits it.

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

**Nothing in the builder changed behaviour, and that is the cheap claim to check.** The
seven Save buttons that did change are the per-screen dev entry points, which a player
never opens.

1. `python -m exalted_builder.ui.editor <file>` → **Save**. It must still write the file
   and show *"Saved to &lt;path&gt;"*. Same for `advantages`, `picker`, `combos`, `play`,
   `storyteller`. ⚠ **`play` and `storyteller` previously said *"Saved &lt;name&gt;"***
   and now say *"Saved to &lt;path&gt;"* — one wording, on purpose.
2. **Nothing on the builder's own Save, Load, New or Print.** They were not touched.

**Carried from the previous session, still owed and still the most valuable:**

0b. ⚠ **OPEN THE APP IN TWO BROWSERS.** Every claim in the last session's headline rests
   on a test harness that fakes two clients. Two real browsers on one server, each editing
   a name, then **`/gm` → Builder in one of them** — the second must keep its own
   character. And a **second tab of the SAME browser** must show the *same* character,
   because the key is per browser by ruling (`vtt.md` §8 Q1), not per tab. **That last
   case the suite cannot express at all.**

1. **GM page → a member card → the "Builder" button**, with two or more party members.
   It carries `.mark(f"open-in-builder-{index}")`; the marker is per-index and a wrong
   index would be a wrong-member handoff.

## ❓ Open for the human

- **Nothing is waiting on the human.** All seven of `vtt.md`'s open questions are ruled.
- **No open RULES questions.** This session touched no game values.
- ⚠ **The `close-out` skill is stale about CLAUDE.md.** Its step 3 names four edits to a
  `## Status` heading and a Done/Next TODO. **CLAUDE.md has none of them** — it was
  converted to a pure index, and its own §1 forbids status, counts and dates. Three of
  the four steps describe sections that no longer exist. Worth a fix to the skill.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The other splats'
Charms were explicitly left as they are (human, 2026-09-01). The caste/aspect-book
Background sweep is closed for planning on the human's hedge of 2026-09-11 — ⚠ a hedge,
not authority to author one.
