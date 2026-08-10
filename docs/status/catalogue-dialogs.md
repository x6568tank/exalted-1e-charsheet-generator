# Catalogue picker dialogs — DONE, browser-verified 2026-08-10

The five "add" surfaces open a **browse-before-you-choose dialog** now. 2,084 tests.
**Browser-verified 2026-08-10** (clicked through every surface; the human's only
request was a bigger dialog — see *The dialog sizing* below).

## What shipped

### `ui/catalogue.py` — one reusable dialog, five callers

`catalogue_dialog(pal, title, entries, on_pick, *, custom_label, subtitle)` is a modal
list: a filter input, name + one-line summary per entry (CSS `line-clamp-2`), a "Full
description" `ui.expansion` when the text is long enough that the clamp hides some of
it (~160 chars ≈ two lines in this dialog), and a **Custom** row at the top.

`entries` are `(key, name, summary, full_or_none)` — `key` is what `on_pick` receives
(the catalogue id where one exists, the name elsewhere), so M&F passes ids and gear
passes names without the dialog caring. `on_pick(None)` means Custom. Pure UI: no game
logic, no validation, no hardcoded cost tables — it reads whatever list the caller
hands it, already filtered for availability/splat.

Gear has no prose in the data, so its `summary` is a **stat line** computed from the
catalogue entry (`catalog_weapon_summary` / `catalog_armor_summary`) — the same shape
`_weapon_summary`/`_armor_summary` produce, minus the character-dependent material tag.
The human ruled (2026-08-10) that equipment's "collapsible full" is the existing
stat-edit expansion on the added row, so gear dialogs have no expansion — the prose for
weapons/armour is still the parked vision-model pipeline, and when it lands the dialog
shows it automatically (the summary is just a clamp of the same text).

### The five wirings — all reuse the existing append/autofill paths

| Surface | Dialog lists | Pick | Custom (on_pick None) |
|---|---|---|---|
| Add weapon (`editor.py`) | `weapon_catalog`, stat-line summaries | `add_item` + `set_weapon` | blank free-text row |
| Add armor | `armor_catalog`, stat-line summaries | `add_item` + `set_armor` | blank free-text row |
| Add artifact (`advantages.py`) | `artifact_catalog`, rating + description | append `ArtifactEntry(name, rating)` | blank row |
| Add background | `backgrounds_for(exalt_type, origin)` — splat-filtered | append `BackgroundEntry(name, 1)` | blank row |
| Add merit / flaw | `_available_merits()` filtered set | append `MeritFlawPurchase(merit_id, tier)` | custom row (below) |

The old `add_merit` that silently appended the **cheapest** available entry is gone —
the dialog is the browse.

### Custom M&F — `MeritFlawPurchase.custom_name`, display-only

The human's ruling 2026-08-10: custom Merits & Flaws are **in scope but display-only,
no mechanical effects**. New field `custom_name: str = ""` (default loads old saves
unchanged). A row with `custom_name` set and `merit_id=""`:

- renders in chargen as a **plain text input + delete** — no select, no tier/side/
  points controls (every one of those reads `definition`, which is None);
- **validates clean** — `validate.merit_issues` skips it entirely (no `merit-unknown`);
- has **no mechanical effect** — the engine's `_held` skips unresolvable ids, so the
  row contributes nothing to `merits_and_flaws_calc`;
- renders on the **sheet by name** — `view.merit_rows` emits
  `(custom_name, "", detail, "merit", "Custom — no printed effect.")` instead of the
  missing-data warning;
- **drops freely** — `advancement.drop_merit` treats it as a plain removal (no XP
  transaction), unlike a real Merit's lose/buy-off;
- appears in the play **Held** dropdown by name, tagged `(custom)`.

The play gain flow's dropdown became a **Browse catalogue** button; the side/category
filter bar now narrows what the dialog offers, and the dialog's own text search narrows
within that. Custom in play opens a small name-prompt dialog and appends directly (no
XP, no log).

## Traps recorded — the two things this work proved about the test harness

1. **The NiceGUI `user` harness dispatches clicks only to an element's OWN listeners —
   it never bubbles.** A `ui.row().on("click", …)` containing the clickable labels is
   unclickable in tests: `_dispatch_click` checks `listener.element_id == element.id`,
   so the row's handler never runs for a child click. Fix: attach the handler to the
   name label itself (the dialog's pick affordance IS the label), and use `.mark()` for
   the Custom row — `data-testid` is a DOM prop the harness ignores (`ElementFilter`
   reads `_markers`, set by `element.mark(...)`).
2. **`user.find(...).elements` is a set — iteration order is not stable.** A positional
   assert like `numbers[-1].value == 1` is a coin flip. Assert on the set of values,
   not the last element.
3. **`ui.scroll_area` does NOT size itself from `max-h` — and `flex-1` on its child
   list collapses to nothing inside a `max-h` (non-definite-height) flex card.** The
   height changes that looked like no-ops were exactly this: a QScrollArea needs a
   concrete height from its PARENT. The working shape is the card `h-[85vh]` (a
   definite height, not `max-h-[85vh]`) + `flex flex-col` on the card + the scroll
   area `flex-1 min-h-0` — the `min-h-0` is the classic flexbox scroll trap that lets
   the list shrink below its content and actually scroll.

## The dialog sizing — what the human actually wanted

The human's one click-through comment was size. The dialog started `w-[34rem]` with a
`max-h-[55vh]` scroll area; it shipped at `w-[46rem]` with the card `h-[85vh]`. The
width change was the visible half; the height took three passes to get right, and the
lesson is trap #3 above — the `max-h` values never bound, so the earlier "taller"
edits (55→65→75→95vh on the scroll area) did nothing until the card got a definite
height and the scroll area was told to fill it.

## What the click-through found

Nothing broken — every surface worked on the first pass. The one design question left
open: the play surface keeps both the side/category filter bar AND the dialog's text
search — the human found it fine but it's the knob to turn if it ever feels redundant.

Still parked, untouched by this work: prose descriptions for weapons/armour (the
vision-model pipeline — this dialog was built to show them the moment they land), and
the wider cross-splat artifact catalogue.

## The code-review fixes (2026-08-10) — 2,081 → 2,084 tests

A code-review pass over the merged branch found four things. The first is the house
bug's cousin and the most important.

1. **Blanking a Custom M&F name made an unfixable error row.** The custom-row
   discriminator was `custom_name`'s truthiness, and the name input writes `custom_name`
   on every keystroke — so select-all-and-retype passed through `custom_name=""`,
   flipping the row back to a NORMAL merit row with `merit_id=""`: `merit-unknown`
   validation, a ⚠ sheet row, and — post-lock — a `drop_merit` that raised, so the row
   could not be removed. The state that turns the mechanism on was player-editable to a
   value that turns it off. **Fix:** the discriminator everywhere is now the EMPTY
   `merit_id` (set at creation, never touched by the name input), at all five sites
   (chargen row, play held list, `view.merit_rows`, `validate.merit_issues`,
   `advancement.drop_merit`); a blanked name renders as "Custom". Pinned by
   `test_a_blanked_custom_name_stays_a_custom_row_not_an_error`.
2. **The play-gain pick path was untested.** The replaced test asserted the dialog
   lists and filters, never that clicking an entry reaches the pending selection —
   `_pick_gain → _mf_changed → Gain` could be broken with a green suite. Pinned by
   `test_picking_in_the_play_gain_catalogue_sets_the_pending_selection` (picks Eternal
   Vow, asserts the preview swaps its placeholder for the choose-a-side state).
3. **`drop_merit`'s custom branch returned a phantom XpEntry.** It deleted the row and
   returned an entry it never appended — unlike both real paths (which go through
   `_commit_award`/`_pay_or_owe`). **The re-review corrected my first fix:** my initial
   "append the cost-0 entry like every other drop" was wrong on two counts — `undo_last`
   has NO merits branch at all (pre-existing; it affects real `buy_merit`/`drop_merit`
   rows too, and is its own ticket), so the row wasn't undoable anyway; and the cost-0
   entry would sit on the LIFO stack, silently burning the player's NEXT Undo on a no-op
   instead of reversing their last real purchase. **Final fix:** a custom drop returns
   `None` and appends nothing — a plain removal with no XP value and no undoable side
   effect records nothing. Pinned by `test_dropping_a_custom_merit_is_a_plain_removal
   _not_a_transaction` (asserts `entry is None` and the ledger stays empty).
4. **The dialogs were rebuilt per open and never deleted.** A NiceGUI dialog is only
   HIDDEN when closed — each open built a fresh ~800-element M&F dialog that stayed in
   the client. **Fix:** `dialog.on_value_change(clear when closed)`, the single deletion
   point covering pick, custom, ESC and click-outside. Verified in the harness (325
   dialog labels → 34 after close). **The re-review found the fix's own bug:** the play
   Custom prompt is a NESTED `ui.dialog()` opened from the catalogue's `_custom`, and
   `Dialog.__init__` creates a hidden CANARY in the current slot (inside the catalogue
   dialog's tree) whose weakref finalizer deletes the nested dialog when the outer is
   cleared — so Custom became a silent no-op. `on_pick`-before-`close` alone wasn't
   enough. **Fix:** the play prompt is built inside `context.client.layout`, so its
   canary is a sibling of the catalogue dialog, not a descendant, and clearing the outer
   leaves it alive. Pinned end-to-end by `test_the_play_custom_merit_flow_appends_and
   _shows_in_held`.
