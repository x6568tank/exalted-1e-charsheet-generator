# The Advantages tab — DONE, browser-verified 2026-07-31

Backgrounds and Merits & Flaws moved off the Edit⇄XP split onto one top-level
**Advantages** tab. 1,485 tests. **Browser-verified 2026-07-31** (clicked through, no
findings). Shipped in v0.7.6.

**The value of this refactor is DELETION.** Two implementations of each panel became
one: `editor.py` lost 237 lines, `xp.py` lost 308, and `ui/advantages.py` (698) holds
both regimes. It was never a UI-polish exercise.

## Why — the bar encodes two shapes, and these were filed under the wrong one

`visible_tabs` distinguishes exactly two kinds of tab:

* **Edit ⇄ XP** — one slot, two sides, mutually exclusive. Chargen builds the baseline,
  XP spends against it.
* **Charms / Combos / Advantages** — on the bar throughout, *switching mode* at the
  lock: picking against the chargen budget before, buying with experience after.

Backgrounds and M&F behave like the second and were filed under the first. They are not
baseline-then-spend; they are **one list edited under two budget regimes**, and filing
them wrongly is what forced each to be written twice.

**The duplication shipped three bugs before it was removed**, all the same root cause —
one module knowing something the other did not:

* the XP tab filtered its Merit dropdown by splat and the editor did not, so a Solar
  could pick Chimera at chargen and only be told afterwards;
* `drop_merit` branched on the catalogue's `kind`, so buying off an either-entry held as
  a Flaw PAID the character;
* `costs.merit_cost` could not see `cost_by_kind`, so Eternal Vow cost 0 XP in play.

## Shape

`ui/advantages.py` exports `build_advantages(ruleset, character, save_path, *,
with_header=False)` — the signature `build_editor` / `build_xp` / `build_picker` already
take, so `builder.py`'s mount dispatch needed no new shape.

Mode comes from the character, never the caller (`_in_play()`, reading
`chargen_locked`), exactly as the picker does:

| | pre-lock | post-lock |
|---|---|---|
| Backgrounds | against `b.background_dots`, pre-bonus cap, dot-track control, Flaw caps honoured | free and story-driven, plain number, no log row |
| M&F | bonus points, a Merit charging and a Flaw granting | `buy_merit` / `gain_flaw` / `drop_merit`, XP-priced, debt-aware |
| readout | bonus points + the per-domain breakdown | XP available + debt, read-only |

`_background_rows(bg_cap)` is the shared list; the two regimes differ only in the rating
control they pass, which is exactly what the two old panels differed by.

**Two controls became module-level so the move did not recreate the duplication it
removes:** `editor.dot_track(pal, on_change)` and `editor.panel_card(pal, title)`.

## The bonus-point readout — ruling 1, and it holds

These traits draw on the SHARED chargen bonus-point pool alongside everything left on
Edit, so the tab carries its own readout (the Charms picker's precedent) plus the
per-domain `validate.bonus_point_breakdown`. **Acceptance met:** spending on Advantages
moves the total shown there, and Edit agrees — pinned by
`test_the_two_tabs_agree_about_the_bonus_points`, which compares the rendered line on
both pages rather than trusting that both call the same function.

## What preflight found: a build-time crash, latent since before the move

**`ui.select` raises at build time when its value is not among its options, and the
raise takes every sibling with it.** A stored structured detail can legitimately be
off-list — validate compares `detail.strip().title()`, so `"strength"` passes validation
and never matches the title-cased `"Strength"` option. Confirmed by reverting the guard:
`ValueError: Invalid value: strength`, and the whole tab blank.

Inherited from the editor, not introduced here. Unmatched values now render as their own
`(not a choice)` option. `/advantages-odd-detail` is the regression route.

The merged M&F row also went **flex-wrap**. It can carry six controls where each old
panel carried four — entry, side, tier, arena, stipulations, detail — and a no-wrap row
crushes its later children to slivers rather than wrapping them, which is how a sheet
panel went invisible earlier the same day.

## What stayed put

**Edit keeps** attributes, abilities, virtues, specialties, crafts, colleges, equipment.
**XP keeps** everything XP-priced, the ledger, undo, the Reduce-a-Trait card, permanent
Resonance, and **equipment editing** (the human's ruling: it is free and story-driven
like Backgrounds, but has no chargen-budget half to unify).

Undo of an M&F purchase still happens on the XP tab, wherever it was bought — the
Advantages readout says so rather than growing a second ledger.

**Unaffected:** the sheet, GM/party mode, and every engine module. `engine/merits.py`
and decision 0011 are untouched, and no Merit id became visible to a new caller.

## Tests

`test_backgrounds_and_merits_have_exactly_one_implementation` greps `editor.py` and
`xp.py` for `merits_flaws` / `backgrounds_for` and fails if either grows a panel back.
**That is the test that matters** — the rest verify behaviour that already worked.

`test_advantages_is_a_both_sides_tab_not_half_of_the_edit_xp_pair` pins the plumbing
crux: getting it into the Edit/XP branch would rebuild the split being removed.

Render-matrix routes added for the shapes this change can produce: a casteless splat
(`/advantages-mortal` — every caste-keyed lookup gets `caste == ""`), an off-catalogue
Merit id and Background name in both regimes (`/advantages-unknown`,
`/advantages-unknown-xp`), and the off-list detail above.

## The M&F filter/search — DONE 2026-08-01

The usability problem this tab inherited: **99 entries in a flat dropdown.** The chargen
row select had no type-ahead at all, and the play "gain" select had type-ahead over a
label that leads with the name, so a search for a *category* or for what an entry *does*
found nothing on either side.

**One filter serves both regimes** (`_mf_matches` in `ui/advantages.py`) — the same
discipline as the rest of the module, since a second copy is exactly what put the splat
filter on one panel and not the other.

* **Free text** matches name, category **and rules text**, so "combat" or "essence"
  finds entries whose *name* says neither.
* **Side** — All / Merits / Flaws. A `kind: "either"` entry answers to **both**, because
  it is genuinely either; hiding it from both is how a player loses Eternal Vow.
* **Category** — the five authored ones (Physical, Mental, Social, Supernatural,
  Property), read off the data rather than listed here.
* A **"N of M shown"** counter, so a filter that hides everything reads as a filter and
  not as an empty catalogue.

**The controls do not refresh the panel.** A `ui.input` fires per keystroke and a rebuilt
input has lost focus, so a refreshing search box eats every character after the first.
The filter reaches into the live selects with `set_options` instead — which is why every
select it touches must re-add its own current value:

> `ui.select` **raises at build time** when its value is not among its options, and the
> raise takes the whole tab with it. A held entry that the filter excludes is the easiest
> way to trigger that, so `_row_opts` and `_gain_opts` both `setdefault` their own value.
> `test_a_held_entry_survives_a_filter_that_excludes_it` pins it.

Six tests in `tests/test_merits_flaws.py`, driving **both** routes (`/mf-side`,
`/mf-side-xp`) — a filter that works at chargen and not in play is precisely the drift
this module exists to prevent.

**Not done, deliberately:** the availability filter still prunes only ~11 of 99, so
side + category + search is what does the work. That is by design — an entry this
character cannot take is hidden, not greyed.

## Background descriptions under the row — DONE, browser-verified 2026-08-05

The Backgrounds panel was "a little barebones" (human, 2026-08-05): the catalogue
descriptions already existed and the dropdown already showed them as hover tooltips
(`DescribedSelect`), but a picked Background row showed nothing — unlike the M&F rows,
which print their rules text under the row. Each Background now prints its catalogue
description beneath its row, in **both regimes** (it lives in the shared
`_background_rows`, so play gets it for free). 1,934 tests. **Browser-verified
2026-08-05** (clicked through on the default example — Artifact 3 / Manse 2 /
Resources 2, all three blurbs printing; a pick swapped a blurb live; a free-text name
hid its blurb with no crash).

**Two implementation notes, both learnings from doing it the wrong way first:**

* **The row's own select updates only its own label, synchronously.** The first version
  used a per-row `@ui.refreshable`; its `refresh()` is fire-and-forget async, and the
  refresh body read the LOOP variable `bg` (every row's handler would have re-rendered
  the last row's description). The shipped version is a plain `ui.label` set by a
  `_sync()` helper, with `bg` and the label **default-captured** so each row's handler
  binds to ITS row. Picking a Background swaps the blurb immediately, and a free-text
  name no catalogue entry covers just hides the label — no crash, since Backgrounds are
  free text.
* **No full-panel rebuild on pick.** A rebuilt input eats every keystroke after the
  first (the filter bar's lesson, again). The label is updated in place instead.

**The tests are deliberately discriminating — the review caught this.** The first
version asserted `user.should_see(description)`; that passes against code with NO
persistent label, because the catalogue text also rides inside the dropdown options as
hover-tooltip data (`DescribedSelect`). Every assertion now reads the label found by its
`data-testid="bg-desc"` prop (the one prop that distinguishes it from the M&F rules-text
labels sharing its classes), and asserts visibility too — the hidden-label path is read
via `user.client.elements`, since the harness's `find` filters to visible elements. The
negative control is real: all four tests fail when `advantages.py` is reverted to the
pre-feature version. `user.find` does not return elements in model order either, so the
live-swap test identifies its row by the select's value, never by position.

Four tests in `tests/test_backgrounds_splat.py`, driving `/merits-backgrounds`, the
locked `/backgrounds-description-xp` and `/advantages-unknown`: the descriptions render
at chargen, a pick swaps them live, they print in play too, and a free-text name hides
its blurb instead of crashing.

## The native (Qt) Advantages tab — 2026-08-21

`exalted_builder/qt/advantages.py`, milestone 3 of the port (`docs/plans/qt-port.md`).
Same rules, same engine calls, a different idiom: retained-mode panels rebuilt by
`reload()`, with anything a keystroke touches writing straight to the model and
re-syncing only its own labels.

**Two things moved OUT of the web widget first**, so no rules decision exists twice —
`view.default_merit_tier` (with `merit_tier_label` / `merit_option_label`) and
`advancement.gain_merit_or_flaw` (the merit-vs-flaw side resolution plus both of its
refusals). `ui/advantages.py` delegates to them now; that is the whole reason the two
shells cannot drift on the Prodigy default or on which side of the transaction a
purchase is.

⚠ The audit asked whether Advantages needed an `advantages_actions.py` the way Charms
needed `charm_actions.py`. **It does not** — no lock-toggle, a post-lock half already in
`engine/advancement.py`, a chargen half that is `list.append`. The reasoning is in the
plan doc; do not re-derive it.

Where the native tab deliberately differs from the web one:

* **No bonus-point line of its own** — the shell's readout bar carries it, and printing
  it here too showed the same sentence twice. The tab's line is its own issues
  (Background / Merit / Flaw / Artifact codes), and XP available + debt post-lock.
* **Printed prose is clamped, full text on the tooltip.** Qt has no CSS line-clamp, and
  a Manse's paragraph pushed every other row off the panel.
* **A merit row is two lines** (entry + delete, then the entry-specific controls). Qt has
  no flex-wrap, and a no-wrap row crushes its later children to slivers.

31 tests in `tests/test_qt_advantages.py`; they skip without the optional `qt` extra.
