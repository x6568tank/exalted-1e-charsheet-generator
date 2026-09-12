# Session handoff — 2026-09-11 (§5 piece 2b: "Download a copy"; hosted click-through; empty ⓘ dialogs)

# 👉 YOU ARE HERE

Last FULL suite: **3548 passed + 1 skipped** — observed at the START of this session,
**before** piece 2b. It is the run the previous handoff left pending, and it agrees with
that handoff's arithmetic.
⚠ The count moves by machine and by optional dependency — see `docs/testing.md`, and do
not reconcile this against another machine.

⚠ **The full suite was NOT re-run after 2b** (human's call: targeted is enough for this
row). Observed instead: **190 passed** across the 13 hosting / builder / GM / session files,
including `test_engine_seam.py`. 2b adds six cases, so the next full run should read
**3554 + 1 skipped** — computed, not observed.

The trait-dialog fix below was verified with `tests/test_trait_descriptions.py` and
`tests/test_catalogue_dialogs.py` (**28 passed**), not with the full suite.

**Working tree:** clean when this line was written — 2b is `87b488c`, and the trait-dialog
fix and the click-through record are the commit that carries this file. Check
`git status` before acting on this line.

## ✅ BROWSER-VERIFIED — the hosted server, by the human, 2026-09-11

Run locally: `python -m exalted_builder.server.main` on `127.0.0.1:8080`, Firefox plus a
private window as the second player. **All seven checks passed:**

* **2b:** "Download a copy" on `/` downloads the character at once; the next auto-save
  still writes the one session file, not a file named after the download. "Download a
  copy" on `/gm` downloads the party, and Save party still writes to the session folder.
* **Carried from last session, now done:** two browsers → two session directories; hosted
  Save in each writes its own file with no download; a second tab of one browser shows the
  same character; `/gm` → Builder in one browser leaves the other's character alone.

⚠ **Still not done:** the desktop Save (it must still prompt and download). It needs the
desktop build, not this server.

## 🐞 FIXED — the ⓘ trait dialogs were empty in the NiceGUI shell

Found in the click-through above. The dialog showed the trait name and its family and
nothing else. **Not a hosting bug** — the NiceGUI shell has shown empty ⓘ dialogs since the
feature shipped on 2026-09-02 (that commit says it was not checked). The Qt shell has its
own dialog and was never affected.

**Cause:** the text sat in a `ui.scroll_area` inside a card with only `max-h`. A QScrollArea
has no height of its own, so it rendered at zero height. The catalogue picker uses the same
pattern and works because its card has a fixed `h-[85vh]`. **Fix:** a plain column with
`overflow-y-auto`, which takes the height of its text and scrolls at the card's maximum.
Browser-verified by the human.

⚠ **The old tests passed against it** — `should_see` finds the text in the element tree,
and the harness has no layout. The new guard,
`test_trait_descriptions.py::test_the_dialog_text_is_not_in_a_zero_height_scroll_area`,
checks structure: a scroll area in the open dialog must be in a card with a fixed `h-`
class. It was red on the old code.

## ✅ SHIPPED — §5 piece 2b, "Download a copy" on a hosted run

**§5.1c of `docs/plans/hosting-state-model.md` is the record** ("What shipped", at the end
of that section). What a reader needs before touching anything:

* A hosted run shows **"Download a copy"** beside Save on `/` (mark `top-bar-download`) and
  beside Save party on `/gm` (mark `gm-download-party`). Both are gated on the **same
  `hosted` bit** as the save branch and the auto-save timer. Not-hosted builds do not show
  them.
* ⚠ **The trap is closed by a split, not by care.** `builder._download_copy` and
  `gm._party_download_copy` send the file and touch nothing in `ctx`. The desktop helpers
  `_browser_download` / `_party_download` call them and **then** repoint `ctx` themselves,
  each with a ⚠ desktop-only comment. **Do not move the repoint back into the shared
  helper** — the hosted button would then move the auto-save target.
* The tests assert `ctx` is **unchanged** after a download, and the gate in both
  directions. `_hosted_save_main.py` gained a `/desktop-gm` control route.
* Negative controls: four, all run, restored from a copy. Listed in §5.1c.

### 🐞 A fixture that could not see its own trap

The first draft of the character trap case would have passed against the trap: with an
unedited character, the desktop helper repoints `ctx["path"]` to the **same filename it
already holds**. The case now renames the character first and asserts the fixture can
see a repoint before it clicks. The party case does not need this — `party_path` starts
as None.

### ⚠ One design choice made without asking

**No filename prompt** on the hosted button — it downloads at once under the suggested
name. A prompt is a second place a typed name could reach `ctx`, and the browser can
rename the file anyway. Reversible; say so if you want the prompt.

## 👉 NEXT — in rough order of what would bite

- **§5 piece 3 — auth.** `/login`, the gate, `bcrypt` (not `passlib`), a `[server]` extra.
  ⚠ **The first piece of this project with no adjacent pattern to copy** — §3 always had
  `register_pages` or `custom_content` to follow. It is also the one place where an
  unreviewed default is a security bug rather than a wrong number.
  **`server/main.check_bind_is_allowed` is deleted by this piece, not before.** It is the
  mechanism standing in for auth: a non-loopback bind refuses to start without `--public`.
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

The hosted click-through is **done** (see ✅ BROWSER-VERIFIED above). One item is left:

1. **Save on the DESKTOP still opens the filename prompt and downloads.** Run
   `python -m exalted_builder.ui.builder`, not the server. That branch is untouched and
   the harness covers it, but the three save branches now sit in one function, and 2b
   added hosted-only buttons beside it — confirm they are **absent** there too.

⚠ **The Qt ⓘ dialogs were never broken**, and nothing in this session changed them.

## ❓ Open for the human

- **No open RULES questions.** This session touched no game values.
- **Three design choices made without asking, all reversible:**
  - **No filename prompt on "Download a copy"** (new this session, above).
  - **Loopback default + `--public`.** Departs from §5.1's written `0.0.0.0`, because that
    sketch assumes the auth gate.
  - **A separate strict secret accessor** rather than making `storage_secret()` itself
    raise. Merging them would break `ui/builder.py:main` and `ui/gm.py:main`.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The other splats'
Charms were explicitly left as they are (human, 2026-09-01). The caste/aspect-book
Background sweep is closed for planning on the human's hedge of 2026-09-11 — ⚠ a hedge,
not authority to author one.
