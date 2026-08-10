# Catalogue picker dialogs — DONE, browser-verified 2026-08-10

The five "add" surfaces open a **browse-before-you-choose dialog** now. 2,081 tests.
**Browser-verified 2026-08-10** (clicked through every surface, one nitpick on dialog
size — widened 34rem→46rem and the list 55vh→75vh at the human's request).

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

## What the click-through found

Nothing broken — every surface worked on the first pass. The human's only comment was
the dialog size (widened). The one design question left open: the play surface keeps
both the side/category filter bar AND the dialog's text search — the human found it
fine but it's the knob to turn if it ever feels redundant.

Still parked, untouched by this work: prose descriptions for weapons/armour (the
vision-model pipeline — this dialog was built to show them the moment they land), and
the wider cross-splat artifact catalogue.
