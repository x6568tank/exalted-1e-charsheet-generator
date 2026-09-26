# P4 — The board: design

**Status: DESIGN RULED 2026-09-25 (§5). No code yet.** The human opened P4 on 2026-09-25
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
| Q2 | Background images | **The ST uploads.** The server opens the file as an image, re-encodes it, and refuses a result over **~2 MB**. It is stored in the table folder, under the table's **10 MB** quota. |
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
