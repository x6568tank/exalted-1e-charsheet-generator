# Edit ⇄ XP merge — one trait surface on both sides of the lock

**Decision:** `docs/decisions/0013-edit-and-xp-are-one-surface.md` (accepted 2026-07-31).
Read it first — it records why option **C** (a downward click asks *undo or reduce?*) beat
the two cheaper alternatives, and what that costs.

**Status: PLANNED, in progress.** Phases below are checked off as they land.

## Why this is bigger than it looked

The trait rows are not the only duplication. Walking both files, **five more panels exist
on both tabs**:

| Panel | `editor.py` | `xp.py` |
|---|---|---|
| Crafts | `panel(...)` @581 | card @237 |
| Astrological Colleges | @625 | card @268 |
| Specialties | @641 | inside "Add" @213 |
| Armor | @691 | inside "Equipment" @347 |
| Weapons | @712 | (same card) |

That is the Advantages-tab situation exactly: one list, two budget regimes, two
implementations, and the drift between them is where bugs live. The `cap=5` bug is the
symptom that got reported; these five are the same disease undiagnosed.

**XP-tab-only, and therefore genuinely homeless when it dissolves:**

* Raise a Trait → becomes the dot tracks themselves
* Reduce a Trait → becomes the downward-click dialog, plus a Willpower-only control
* Permanent Resonance gain/shed (Abyssal, Death's Taint)
* Add XP
* The ledger + Undo
* The withheld-Charm-credits note (Weak Essence)

## Phases

### P0 — engine groundwork *(no UI)*

* [x] **Fix `cap=5` first, standalone.** `xp.py:98,128,140` — the live bug from the player
      report. Fixed before the refactor rather than as part of it, so it ships even if the
      merge takes several sessions. Read `attribute_caps` / `virtue_cap` the way
      `editor.py:331,333` already does.
* [x] **`advancement.refundable_depth(character, target, detail="") -> int`** — how many
      rows at the TAIL of `xp_log` are consecutive raises of exactly this target. 0 when
      the tail belongs to anything else. Greys the dialog's undo branch and caps its count.
      **A reduction row at the tail stops the count** — direction (`to > from`) is what
      separates a purchase from a curse, *not* cost, since a withheld-Charm pick (Weak
      Essence) is a real purchase that also costs 0.
* [x] **`advancement.raise_to(ruleset, character, target, to_rating)`** — the stepper.
      Validates the whole click against a **deep-copied probe** before committing any of
      it, so an unaffordable *or illegal* click leaves the character untouched instead of
      landing halfway up the track. Delegates to the existing `raise_*`; adds no pricing
      and no rule. Downward returns `[]` — choosing undo-vs-reduce is the dialog's job.
* [x] `_DOT_TRACK_RAISES` names the four dot-tracked targets (attributes, abilities,
      virtues, essence) using the same `XpEntry.target` convention `undo_last` partitions
      on, so the UI names a trait identically everywhere.

### P1 — the dot track learns a post-lock mode

* [ ] `editor.dot_track` (shared by the Advantages tab — check both callers) gains a mode.
      Pre-lock: unchanged free setter. Post-lock: upward click → `raise_to`; downward click
      → the dialog.
* [ ] The dialog: two branches, explicit dot counts, reason input live on the reduce branch
      only, illegal branch greyed, neither-legal → no dialog at all.
* [ ] Cost preview on hover/label so a click's price is visible before it is made.

### P2 — the Edit tab stays visible post-lock

* [ ] `builder.visible_tabs` stops hiding Edit when locked.
* [ ] The five duplicated panels get their post-lock behaviour (Crafts, Colleges,
      Specialties, Armor, Weapons) — buy-where-you-browse, matching Charms/Combos.
* [ ] Budget headers switch to XP readouts post-lock rather than showing chargen pools.

### P3 — the XP tab dissolves

* [ ] Delete the five duplicated cards outright.
* [ ] Rehome: permanent Resonance, Add XP, withheld-Charm credits, the Willpower reduce
      control. Add XP is arguably an ST action, not a sheet one — decide when we get there.
* [ ] `builder._TABS` / `visible_tabs` / `resolve_tab` lose "XP"; saved UI state naming it
      must not strand the user on a tab that no longer exists.

### P4 — the ledger moves to the sheet

* [ ] Read-only history block, near the validation box. **`app.render_sheet` takes only a
      `SheetView`** — no ruleset, no character, no callbacks — and the GM party screen and
      the render tests depend on that purity. So the ledger there is history; Undo lives
      where the buying happens.
* [ ] `build_sheet_view` already runs the XP audit post-lock (`view.py:1545`), so this is a
      display move, not plumbing.

### P5 — verification

* [ ] Run the **`preflight`** skill. This work is exactly its target: a rule wired into one
      lifecycle phase is the bug class being deleted, and it is the bug class most likely to
      be re-introduced by a half-finished mode switch.
* [ ] Render matrix: locked × unlocked × a splat with no Colleges × a splat with no Crafts ×
      a mortal (no Charms, no castes) × mid-ledger with undo available.
* [ ] Human click-through.

## Traps banked in advance

* **`dot_track` has two callers** (editor and Advantages). A mode added for one must not
  change the other's behaviour silently.
* **Willpower is not a dot track** and cannot become one (decision 0005 pins the Virtue
  component; only `willpower_purchased` is editable). It keeps an explicit control.
* **Undo is LIFO across the WHOLE log**, not per trait. `refundable_depth` exists to make
  that legible; it must never be read as "this trait can be refunded" in isolation.
* **A downward click on an untouched chargen dot does nothing** — no XP to refund, no curse
  to record. Accepted in 0013, but it is the one gesture that will read as a dead control,
  so it wants a hint rather than silence.
* The **dead-effect-field trap's sibling** applies to every phase here: a rule wired into
  the pre-lock branch only will pass every test and be wrong in play. Test the buy path.
