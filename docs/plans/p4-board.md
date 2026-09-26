# P4 — The board: design

**Status: design ruled 2026-09-25 (§5). Steps 1–4 BUILT 2026-09-25 (§8); step 5, the human's click-through, is owed.** The human opened P4 on 2026-09-25
(*"Phase four is up!"*).

**Read first:** decision `0020` (the board is dumb — it is the authority on scope),
`vtt.md` §0 and §3 (why the board is cheap, and the "broadcast commitments, not motion"
rule), and `p3-tables.md` §15 (the board lives in the centre column of layout A).

This file does not restate 0020. Everything below is inside it.

---

## 1. What already exists

* **The frame.** `server/table_view.py` `_board()` draws the centre column: a `BOARD`
  header and a decorative 40 px grid with "The board comes next." P4 replaces the inside.
* **The canvas bridge.** `ui/assets.py` inlines a vendored library from `ui/vendor/`
  (Cytoscape today); `ui/picker.py` drives it with `ui.run_javascript` and hears back
  through `emitEvent` → `ui.on`. The board is the same round trip.
* **The table folder.** `<root>/table-<id>/` holds `log.json`, the notes and the roster.
  `board.json` is one more file there. ⚠ The folder has the **10 MB** account quota
  (`server/quota.py`), and every write goes through `atomic_write`, so the quota already
  guards the board.
* **The poll.** The table page repaints on a **2 s** `ui.timer` digest check.
* **`access()`** re-checks membership in every handler. Board handlers use it too.

## 2. The model

`board.json`: a list of objects, each with an `id`, a `kind`, a `z`, geometry, a style,
and `author_id`.

| Kind | Fields |
|---|---|
| `stroke` | points, colour, width |
| `shape` | rect / ellipse / line / arrow, box or endpoints, colour, fill |
| `text` | position, the typed text, size, colour |
| `token` | position, radius, colour or image, **the typed label** |
| `image` | the background: a file in the table folder, position, scale, locked |

* **Last write wins per object id.** A move sends the object's new geometry, not a diff.
* **The server is the authority.** The browser sends an intent (add / move / delete);
  the handler checks `access()` and the permission (§5 Q1), writes `board.json`, bumps a
  version, and fans out. A late joiner gets the whole list.
* ⚠ **No `character_id`, no `copy_id`, no roster id on any object** — 0020. A token's
  label is a text box the person fills. Nothing pre-fills it from the party, the roster
  or the viewer's character.

## 3. Sync

**Push, not the poll.** A token dropped on one screen should land on the others at once;
a 2 s poll makes the board feel broken. Each open table page registers with a per-table
subscriber set; a committed change calls `run_javascript` on each subscriber's client.
`on_disconnect` removes it. The rails keep the 2 s poll — only the board is pushed.

**Commitments, not motion** (`vtt.md` §0): a stroke goes out when the pen lifts; a token
when it is dropped. No live cursors, no mid-drag streaming.

## 4. Library

**Konva** (MIT), vendored into `ui/vendor/` the way Cytoscape is — no CDN. It gives
draggable shapes, freehand lines, images, layers, hit-testing and touch, and nothing that
knows about a game. The alternative, Fabric.js, is heavier and does the same job.

## 5. The rulings, 2026-09-25

All four were asked on 2026-09-25 and the human took the recommendation on each.

| # | Question | Ruling |
|---|---|---|
| Q1 | Who can change the board? | **Players and the ST**: each draws, places tokens, and moves or deletes **any** object, as at a real table. **Only the ST** clears the board and sets the background. **Spectators watch.** "Spectator" is how the campaign is opened (`p3-tables.md` §1), so the check is the page's mode, re-checked in the handler. |
| Q2 | Background images | **The ST uploads.** The server opens the file as an image, re-encodes it, and refuses a result over **~2 MB**. It is stored in the table folder, under the table's quota — **raised to 50 MB on 2026-09-25** (human: *"Increase table size to 50 MB"*); an account folder keeps 10 MB (`quota.TABLE_QUOTA_BYTES`). |
| Q3 | Scenes | **One board per campaign.** A scene change is Clear or a new background. Scenes can be added later without a reshape. |
| Q4 | A Storyteller-only layer | **Not in v1.** Everyone sees every object. The hidden-object trap in §7 is dormant until this is reopened. |

## 6. Build order

Each step is its own commit, tests first.

1. **The guard tests, red first.** A grep test that no board module imports `engine/`
   and that no board object field names a character, copy or roster id (0020's
   structural discriminator). `board.json` store: add / move / delete / clear, version,
   quota, bounds.
2. **The canvas, local only.** Konva vendored; pen, shapes, text, tokens, select, move,
   delete; the handlers write through the store.
3. **The fan-out.** The subscriber set, push on commit, snapshot on join, reconnect.
4. **Backgrounds** (Q2): the ST's upload, re-encode, the size cap, Clear.
5. **Click-through.**

## 7. Traps — the house-bug list for this phase

| Trap | Guard |
|---|---|
| A token bound to a character "for convenience" | the grep test in step 1; the click-through list |
| A token label pre-filled from the party or the roster | same — the label box starts empty |
| A permission enforced in the browser only (the Konva `draggable` flag) | the handler re-checks; a test sends a move for an object the viewer may not move |
| A hidden ST object sent to a player's browser and "hidden" by the canvas | a player's snapshot is built from a filtered list; a test walks the player's payload |
| A board write that bypasses the quota | through `atomic_write`; a test fills the folder |
| An image upload trusted by its extension | the server opens it as an image and re-encodes it |
| Push wired to one handler and not the others (type 1) | one commit path that every intent goes through; a test per intent that a second client sees it |

## 8. Build log

### Steps 1–4 — built 2026-09-25

**Step 1 (`d3726ca`): the store.** `server/table_board.py`. `board.json` holds
`{version, objects, background}`. Each kind is a pydantic model with `extra="forbid"`,
so an added field (`character_id`) is **refused, not dropped**. A test pins the exact
field list of each kind, which makes any new field a conscious edit. Bounds: 1,000
objects, 2,000 points a stroke, a 40-character label, 500 characters of text,
coordinates within ±20,000, stroke points rounded to one decimal. A move keeps its
layer; to front / to back; a restack that moves nothing writes nothing. The
background: Pillow opens it (PNG, JPEG, WebP or GIF only), refuses over 40 MP before
decoding, EXIF-rotates, scales to 4096 px on the long side, and writes PNG (if it has
alpha) or JPEG q85. The upload's own bytes are never written. It is refused over 2 MB
**after** encoding. `persistence.atomic_write_bytes` is new, so the image goes through
the same quota guard; `atomic_write` now calls it.

**Steps 2–3: the canvas and the fan-out.** `server/table_board_view.py` and
`server/board.js`, with Konva 10.7.0 (MIT) vendored in `ui/vendor/konva.min.js` and
inlined into the page. The tarball's sha512 was checked against the npm registry.
* `BoardSession` has no NiceGUI call: it handles the canvas intents (put, delete,
  front, back, sync, ask) and is tested with fake pages. Each change goes through
  `_commit` (one op) or `_publish` (a whole snapshot) → `BoardHub.broadcast` → every
  open page of that table. **A push, not the page's 2 s poll.** A version gap on a
  canvas asks for a snapshot; a reconnect remounts; one failing page does not stop
  the rest.
* `BoardPanel` binds delivery to **its own client**. A broadcast runs in the
  sender's context, so `ui.run_javascript` there would reach the wrong page.
* Tools: select/move/resize, pen, line, arrow, rectangle, ellipse, text, token, eraser;
  eight colours, three widths, Fill; Delete (also the Delete key), front, back, Fit.
  Pan by dragging the empty board, zoom with the wheel. A token or text asks for its
  words in a dialog; double-click edits them. The label box starts empty (0020).
* The ST's ⋮ menu: Set the background… / Remove the background / Clear the board…
  (Clear keeps the background).
* Spectating is `not is_st and chosen is None`: a member with no copy, or who picked
  Spectate. The session asks it at **each intent**; the toolbar mode is display only.
  The poll and Open as both re-send the mode.

**Step 4: the background route.** `GET /table/<id>/board-background` serves the file
to a member and 404s anyone else. The login gate covers it by default, and
`test_auth_gate` enumerates it. The URL carries the background's `stamp`, so it only
changes when the image does.

**Tests:** `tests/test_table_board.py` (store, bounds, permissions, image handling,
quota, the 0020 grep over all three board files with a mutation check in each
language), `tests/test_table_board_view.py` (fan-out, refusals, spectators, mode sync,
the toolbar by role through production wiring, the image route).

**Driven in a real browser by me** (headless Firefox + Selenium, two accounts at once,
scratch server): mount and render of every kind over a background; alice's pen stroke
and token drag appeared on the ST's screen; token by dialog; eraser; Delete key; ST
Clear reached alice; alice switching to Spectate dropped her toolbar to "You are
watching"; a 3000×2000 upload re-encoded to 215 KB and showed. **This is not the
human's click-through.** Not driven: resize handles, text editing by double-click,
pinch zoom on a phone (there is none: see below), a reconnect.

**What the work turned up**
* 🐞 **Enter in the label dialog could beat the box's last value update**, and the
  token was saved with an empty label. Seen only when Selenium typed and pressed Enter
  at once; a pause made it pass. The key event now carries `e.target.value` itself.
  The Log's text box had the same pattern and now sends the text with Enter too
  (human: *"Proooobably?"*, 2026-09-25); a test triggers Enter with the box empty on
  the server and checks the post, and it fails with the old code.
* 🐞 **Found by the human in the first seconds of the click-through:** hovering the
  first three colour swatches lit up the Eraser. `ink_eraser` is not in NiceGUI 3.13's
  bundled Material Icons font, so the `<i>` printed the name as invisible text that
  overflowed 80 px to the right and took the pointer. Now `cleaning_services`. A
  browser sweep of every `i.material-icons` on the table page for
  `scrollWidth > clientWidth` finds none now. ⚠ No test guards this: checking the font
  needs fontTools + brotli. **Any icon name newer than the bundled font fails the same
  silent way.**
* 🐞 A restack that moved nothing bumped the version and broadcast. Fixed in the store.
* `atomic_write` now writes bytes. On Windows a desktop save now has `\n` line
  endings, not `\r\n`. JSON does not care.
* Token images are **not** built yet: 0020 allows them, but each needs an upload. The
  human raised the campaign quota to 50 MB with them in mind (2026-09-25); **read as a
  yes, to be confirmed after the first look** at the board.
* No touch pinch-zoom; one-finger drag pans. At phone width the board sits below the
  rails (the existing P3 layout).

### Step 5 — the click-through (owed)

Seed: `tools/seed_table_clickthrough.py --seed`, then run it; two browsers (alice, the
storyteller). Check: draw with each tool; drag and resize a token and see it move on
the other screen; double-click a token to rename it; eraser; Delete key; front/back;
ST sets a map, clears, removes the map; a spectator sees changes live but has no
tools; ⚠ **0020 on the list:** no token offers a character's name, and nothing on the
board reads from the party.
