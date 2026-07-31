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

## Next, if wanted

**The M&F filter/search** (kind, category, free-text). 99 entries in a flat dropdown is
the real usability problem, and there is now one place to solve it instead of two. Note
the availability filter prunes ~11 of 99 at best, so kind + category + search is what
does the work.
