# The Advantages tab — PLAN ONLY, not built

**Status: agreed in principle 2026-07-31 (human), NOT implemented. No code has moved.**
This file is the plan, written in a session that could not touch the code — see
**Sequencing** at the bottom for why it must not be started yet.

Backgrounds and Merits & Flaws move off the Edit⇄XP split onto one top-level tab named
**Advantages**.

## Why — the bar already encodes two shapes, and these are filed under the wrong one

`visible_tabs` (`ui/builder.py:53`) distinguishes exactly two kinds of tab:

* **Edit ⇄ XP** — one slot, two sides, mutually exclusive. "Chargen builds the baseline,
  XP spends against it."
* **Charms / Combos** — on the bar throughout, *switching mode* at the lock: picking
  against the chargen budget before, buying with experience after.

Backgrounds and M&F sit in the first but behave like the second. They are not
baseline-then-spend; they are **one list edited under two budget regimes**. Filing them
under Edit⇄XP is what forced each to be written twice:

| | chargen | in play |
|---|---|---|
| Backgrounds | `editor.py:574` — budgeted (`b.background_dots`, `background_cap_pre_bp`), `dots()` widget | `xp.py:479` — free/story-driven, `ui.number`, "free — no XP" |
| Merits & Flaws | `editor.py:591` — BP panel with the ±sign labels | `xp.py` gain/lose card — XP-priced, debt-aware |

The two Background panels are near-identical below the header: same
`ruleset.backgrounds_for`, same `bg_names`/`bg_descriptions`, same `DescribedSelect` with
`new_value_mode="add-unique"`, same note field. They differ in the header, the rating
widget, and the handler names (`add_bg`/`remove_bg` vs `_add_bg`/`_del_bg`).

**This duplication is not a hypothetical drift risk — it already shipped a bug.** The XP
tab filtered its Merit dropdown by splat and the editor did not, so a Solar could pick
Chimera at chargen and be told off afterwards. Fixed 2026-07-31 by giving both the same
`validate.merit_available_to` predicate; the root cause is that there were two of them.

**The refactor deletes two surfaces rather than adding one.** That is its whole value —
it is not a UI-polish exercise.

## The four rulings (human, 2026-07-31)

1. **The shared bonus-point readout must work.** This is the load-bearing risk, not the
   tab plumbing — see below.
2. Tab-identifier spread across `builder.py` is accepted: "we might have to start
   consolidating before 1.0."
3. **Equipment editing does NOT move.** It sits in the same "free, story-driven" bucket
   in `xp.py` and stays there.
4. The name is **Advantages**.

## Shape

A new `ui/advantages.py` exporting `build_advantages(ruleset, character, save_path, *,
with_header=False)` — the same signature `editor.build_editor`, `xp.build_xp` and
`picker.build_picker` already take, so `builder.py`'s mount dispatch needs no new shape.

Mode comes from the character, not the caller: an `in_play()` helper reading
`character.chargen_locked`, exactly as `picker.py:327` does. One component, two regimes:

* **pre-lock** — Backgrounds against `b.background_dots` with the pre-bonus cap; M&F
  against bonus points, with the Flaw grant reported separately (a Flaw *grants*, it
  does not cost a negative).
* **post-lock** — Backgrounds free and story-driven with no log row; M&F through
  `advancement.buy_merit` / `gain_flaw` / `drop_merit`, debt-aware.

The engine already supports both sides; nothing here needs new rules work.

## The bonus-point readout — ruling 1, and the thing most likely to go wrong

Backgrounds and M&F draw on the **shared** chargen bonus-point pool alongside everything
left on the Edit tab. Move them to their own tab naively and a player spends 6 BP on
Merits while the budget that changed is displayed on a tab they cannot see.

The precedent is the Charms picker: it carries its own `readout()` (`picker.py:496`)
reading `view.build_sheet_view`, and pulls the `bonus-points` issue out of
`view.issues` — the same thing `editor.py:203` does. The Advantages tab must do
likewise. `validate.bonus_point_breakdown` is the per-domain source if a finer
breakdown is wanted than the one-line message.

**Acceptance for this ruling:** spend a bonus point on the Advantages tab and the total
shown *on that tab* moves immediately; switch to Edit and it agrees. If the two ever
disagree, the refactor is not done.

## Touch points in `builder.py`

Mechanical, ~6 spots, all keyed off the tab NAME as an identifier:

* `_TABS` (line 50) — insert `"Advantages"`; position on the bar is a display choice,
  but it reads best next to Edit.
* `visible_tabs` (53) — Advantages is a **both-sides** tab like Charms/Combos, so it is
  *not* part of the Edit/XP hidden pair. This is the crux: getting it into the wrong
  branch here rebuilds the very split being removed.
* `resolve_tab` (62) — no change needed, but re-read it: it maps a hidden tab to its
  counterpart, and Advantages never hides.
* `_ICONS` (378) — needs an entry or `ui.tab` raises on the lookup.
* `_LABELS` (383) — only if the bar name differs from the identifier. "Advantages"
  reads fine as-is, so probably not.
* The mount dispatch (~164) — one more branch alongside `editor` / `picker` / `xp_mod`.

## What moves, what stays

**Moves:** the Backgrounds panel from `editor.py` and from `xp.py`; the M&F panel from
`editor.py`; the M&F gain/lose card from `xp.py`.

**Stays on Edit:** attributes, abilities, virtues, specialties, crafts, colleges,
equipment. Edit gets thinner but is nowhere near empty.

**Stays on XP:** everything XP-priced, plus **equipment editing** (ruling 3) and the
Reduce-a-Trait card.

**Unaffected:** the sheet (display only), GM/party mode, and every engine module. This
is a UI-layer move; `engine/merits.py` and decision 0011 are untouched, and no Merit id
becomes visible to a new caller.

## Tests

`tests/_ui_main.py` grows pages for the new tab in both regimes — an unlocked character
and a locked one — mirroring `/merits` + `/mf-xp` and `/thaum-picker` +
`/thaum-picker-inplay`. The existing M&F UI tests move with the panels. Add one that
pins the readout: a Merit purchase changes the number rendered *on the Advantages tab*.

`test_theme.py` and anything enumerating `_TABS` will need the new name.

## Sequencing — do NOT start this yet

**Cluster A6 (Background budget and rating restrictions) is committed but unpushed on
the human's desktop, which has no remote route** (established 2026-07-31). A6 lives in
precisely the code this refactor relocates. Starting now guarantees a rebase of A6 onto
files whose target code has moved to a new module — and the quiet failure is that A6's
engine half applies cleanly while its UI half conflicts.

Order:

1. Browser click-through of M&F clusters A1–A5 (still the highest-value item; nothing in
   A1–A5 has had one).
2. Land the desktop A6.
3. This refactor.
4. The M&F filter/search (kind, category, free-text) on the new tab — 99 entries in a
   flat dropdown is the actual usability problem, and after this refactor there is one
   place to solve it instead of two. Note the availability filter prunes ~11 of 99 at
   best, so kind + category + search is what does the work.
