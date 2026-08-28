# Edit ⇄ XP merge — one trait surface on both sides of the lock

**Decision:** `docs/decisions/0013-edit-and-xp-are-one-surface.md` (accepted 2026-07-31).
Read it first — it records why option **C** (a downward click asks *undo or reduce?*) beat
the two cheaper alternatives, and what that costs.

**Status: DONE and browser-verified 2026-07-31, 1,555 tests passing.**
Three follow-up rulings landed after the click-through — see the bottom of this file. Phases below are checked off as they land.

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

### P1 — the dot track learns a post-lock mode ✅

* [x] **`editor.dot_track(pal, on_change, *, buy=None)`** and `dots(get, setv, lo, hi,
      target=None)`. The mode is opt-in **per call, not per control**: a track only
      changes behaviour when the caller names an `XpEntry` target, so the Advantages
      tab's Background rows and the editor's Craft/College/Specialty tracks keep the free
      setter untouched. The shared control decides nothing — it hands the click to `buy`
      and does what it is told.
* [x] Wired on the four dot-tracked traits: Attributes, Abilities, Virtues, Essence.
* [x] **The dialog.** Two branches with explicit dot counts, the refund's real XP value,
      reason input on the reduce branch, illegal branch greyed *with the reason named*
      rather than silently dead, neither-legal → a notify instead of an empty dialog.
* [x] `advancement.refund_to` / `lower_to` — the two downward operations, so the UI never
      hand-rolls a loop with rollback. `refund_to` treats `refundable_depth` as a hard
      error, never a truncation: unwinding more rows than this trait owns at the tail
      would silently reverse somebody else's purchase.
* [x] **`build_editor` now returns its dialog opener.** A render test cannot reach a
      dialog that only exists in response to a pip click, and an unbuilt NiceGUI branch is
      this project's most-repeated UI bug — so the dialog gets built in both of its
      interesting states (`/editor-lower-both`, `/editor-lower-curse-only`) exactly the
      way `build_picker` exposes its detail card.
* [x] `/editor-locked` renders the editor post-lock at all, which nothing did before.
* [ ] Cost preview on the pips, so a click's price is visible *before* it is made.
      Deferred to P2 — it wants the budget-header rework beside it.

### P2 — the Edit tab stays visible post-lock ✅

* [x] `builder.visible_tabs` no longer hides Edit when locked, and `resolve_tab` lands on
      Edit in BOTH directions — lock while looking at your Attributes and you are still
      looking at them, now priced in XP. Four existing tests encoded the old swap and were
      rewritten to encode the new rule.
* [x] Budget headers and tallies switch off post-lock: the Attribute/Ability/Virtue panel
      headers drop their chargen pools, the per-category "N spent" tallies stop, and the
      **Bonus Points card becomes an Experience card**. Bonus points are frozen into the
      ChargenSnapshot at the lock, so showing them beside dots that now cost XP names the
      wrong currency. `readout()` needed only its wording changed — `build_sheet_view`
      already swaps the chargen check for the XP audit.
* [x] **Crafts and Colleges** got the dot-track treatment, which needed a `detail` axis
      through `raise_to`/`refund_to`/`lower_to`/`refundable_depth`: their log rows all
      share one target (`crafts`) and are told apart by the focus. Without it, buying
      Smithing then Tailoring would make Smithing look refundable.
* [x] Their 0→1 boundary is one gesture but two engine operations at two prices
      (`learn_craft` vs `raise_craft`); `_step_craft` / `_step_college` own that split so
      the UI never sees it.
* [x] Armor and Weapons need no mode — equipment editing is free on both sides. Their
      duplication is pure deletion, in P3.

**⚠ Specialties are NOT wired, deliberately.** `add_specialty` buys one at rating 1 and
the engine has no way to RAISE a specialty's rating with experience — no
`raise_specialty`, and the log row carries no ratings at all. Chargen rates them 1-3 with
bonus points, so the dot track exists, but post-lock it would need a rule nobody has a
page for. Left as a free-edit control and **flagged for the human**: is raising a
specialty in play a real 1e operation, and at what price? Do not invent one.

Crafts and Colleges have the same gap in the other direction — no `lower_*` exists for
either, so the downward dialog greys its curse branch for them. That one is fine as-is
(it greys by *asking* the engine, not by knowing), but it is the same missing-rule shape.

### P3 — the XP tab dissolves *(the column is done; the tab is not)*

* [x] **The in-play sticky column, to the human's own layout** (2026-07-31, at the
      browser): Adjust XP on top, then the log, then validation. The whole column is ONE
      refreshable (`side_column`) because *which cards exist* changes at the lock —
      `readout`/`bp_log` stopped being individually refreshable to make that possible.
* [x] **Validation is DEMOTED post-lock, not deleted.** Asked for as "hide it"; kept
      because `validate()` still finds real things in play — a curse that drops an Ability
      below a known Charm's requirement raises `charm-min-ability`, and the new downward
      dialog is what makes that easy to cause. The card renders only when it has a finding
      other than `xp-summary`, so a clean character shows the column the human drew and a
      broken one still gets warned. Both states are pinned by tests.
* [x] Post-lock the card shows **findings only** — the derived Willpower/Essence/Soak
      block stays on the chargen side, where a builder watches it move, rather than
      competing with a ledger for the eye.
* [x] **"Undo last: <row>"** in the Adjust XP card. A read-only log has no per-row undo
      button, and traits are the ONLY purchases with a downward gesture of their own — a
      Charm, Combo, spell, specialty or thaumaturgy buy would have been stranded. It names
      the row it will reverse, because "Undo" alone is a guess. Click-through tested: the
      label appears, the click reverses, the label goes.
      * ⚠ **Amended 2026-08-22: a CHARM buy now has a downward gesture of its own too.**
        The Charms tab's "Remove" is enabled when the selected Charm IS the most recent
        XP entry, and reverses it (`charm_actions.undo_charm` / `undo_charm_reason`);
        otherwise it is disabled and says why. This does NOT replace "Undo last" — the
        log is LIFO, so only one Charm is ever reachable that way, and Combos, spells
        and thaumaturgy still have no gesture of their own. The reason above stands;
        only "a Charm buy would have been stranded" is now out of date.
* [x] **Rehomed the four things that lived ONLY on the XP tab**, before deleting anything
      — the order matters, since deleting first would have silently removed Death's
      Taint's whole play-time mechanic:
  * **Willpower** raise/lower pair in the Essence & Willpower panel. Not a dot track and
    never will be (0005 pins its Virtue half). Its downward gesture is a ONE-branch
    dialog: with no upward click of its own there is no refund branch to offer, so undo
    reaches a Willpower purchase from the ledger instead.
  * **Specialties** are now bought named-and-priced post-lock rather than appended blank
    — an empty row would already have cost XP. Existing rows go read-only, as the Charms
    tab's do.
  * **Permanent Resonance** (Death's Taint) as its own locked-only panel, gated on
    `derive.permanent_limit_cap` so no Merit id is named in the UI.
  * **Withheld-Charm credits** (Weak Essence) into the Experience card, beside the XP
    accounting — it is experience the player does NOT have to spend.
* [x] **`exalted_builder/ui/xp.py` is DELETED** (493 lines), and `builder._TABS` /
      `visible_tabs` / `resolve_tab` lose "XP" with it. `resolve_tab` already landed on
      Edit in both directions, so a saved UI state naming "XP" strands nobody.
* [x] Seven tests that named the XP tab were **retargeted, not deleted** — each guarded
      something real (the shadowed-local crash, "the trait surface must not sell Charms",
      the Merit-raised ceilings, College buying, equipment surviving). Only the assertions
      that named the tab changed.

### P4 — the ledger's read-only copy on the sheet ✅

* [x] `SheetView` gained `xp_earned` / `xp_spent` / `xp_available` / `xp_log`, and
      `app.render_sheet` prints them above the Validation block. **The purity contract
      held**: it still takes only the dataclass — no ruleset, no character, no callbacks
      — which is what the GM party screen and every render test depend on. A test asserts
      the sheet copy carries no controls, and another asserts the fields exist on the
      dataclass rather than through a page.
* [x] Empty pre-lock, and suppressed explicitly rather than rendering an "Experience"
      heading with nothing under it.

### P5 — verification *(partial)*

* [x] `preflight` pass 1 (effect read-sites): nothing new. The three UI-ONLY fields it
      reports are pre-existing in `ui/advantages.py`, unrelated to this work.
* [x] `preflight` pass 2 (build-time crashes): the one new `ui.select` (the specialty buy
      form) draws from the full Ability enum with an enum default, so its value can never
      be outside its options. `_frozen` only adds a prop and changes no value. One
      `locked` binding in `body()`, no shadowing.
* [x] `preflight` pass 3 (render matrix): the merged editor now builds post-lock for
      **Mortal** (no castes, no Charms, Essence pinned at 1), **Alchemical** (Favored
      *Attributes*), **Lunar** (castes with no caste-Abilities), **Abyssal** (Resonance +
      withheld credits), **Sidereal** (Colleges), and a save carrying **off-catalogue
      gear and a custom Nature** — the select-value trap, which now matters more because
      a frozen select still has to build with whatever the save holds.
* [x] **Human click-through 2026-07-31 — no notes.** Undo was exercised across trait purchases AND Ox-Body, which was the label most in doubt.

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


## What the work turned up on the way

Written down because these are the lines worth re-reading, not because they flatter.

* **The reported bug was the smallest of five instances.** `xp.py`'s hardcoded
  `cap: int = 5` was one symptom; walking both files found **five more panels
  implemented twice** (Crafts, Colleges, Specialties, Armor, Weapons) plus the whole
  trait surface. Nobody had noticed because each duplicate worked in isolation — only
  the *drift* between them was wrong, and no test compares two implementations.
* **`refundable_depth` nearly used the wrong discriminator.** The obvious way to tell a
  purchase from a curse in the XP log is cost — a reduction costs 0. That is wrong: a
  Weak Essence withheld-Charm pick is a genuine purchase that also costs 0. Direction
  (`to_rating > from_rating`) is the only reliable test.
* **Crafts sharing one log target nearly broke refunds silently.** Every Craft row is
  `target="crafts"` with the focus in `detail`. Matching the tail on target alone would
  have made *Smithing* refundable after buying *Tailoring*. The `detail` axis exists for
  that, and a test pins it.
* **Deleting before rehoming would have removed Death's Taint's play-time mechanic.**
  The permanent-Resonance gain/shed card existed on the XP tab and nowhere else. So did
  Weak Essence's withheld-Charm note and the only Willpower controls. Rehome first.
* **Making Edit a both-sides tab exposed eight chargen controls to a locked character** —
  found by the human at the browser, not by the suite. Re-picking Favoured Abilities in
  play would silently re-rate every future purchase; changing caste/Exalt type/origin
  would swap the budget row the snapshot was written from. They are now `_frozen()`:
  greyed but READABLE, with the panel saying why. A test asserts none of them are frozen
  during chargen, so the freeze cannot leak backwards.
* **Seven tests named the XP tab but guarded something real** — the shadowed-local crash
  that once took a whole tab down, "the trait surface must not sell Charms", the
  Merit-raised ceilings, College buying, equipment surviving the lock. All retargeted;
  only the assertions naming the tab changed. Deleting them would have been the easy
  wrong move.

## Rules questions — ANSWERED by the human, 2026-07-31

All three were resolved the same day they were raised. Recorded with the ruling's own
words, because two of them contradict what the code assumed.

1. **Specialties are instances, not rated traits.** *"You don't raise specialties, you
   just take the same one multiple times, and you can only have 3 specialties per
   ability — you can have melee 4 with two specialties in swords and one in parrying,
   but you can't buy two dots of sword specialties."*
   * Every specialty is worth 1; **duplicates are the stacking mechanism**.
   * The cap is **3 rows per Ability**, counted per Ability and not per name — two
     Swords and one Parrying fills Melee.
   * `Specialty.rating`'s docstring already claimed "cap of three per ability enforced
     in engine". **Nothing enforced it.** It does now, in `advancement.add_specialty`
     AND in `validate.check_specialties` — chargen writes the list straight from the
     editor, so an advancement-only guard would have left the whole pre-lock path
     unchecked, which is this project's recurring mis-placed-rule shape.
   * A legacy rated specialty is **split into instances on load**
     (`persistence._split_rated_specialties`) — mechanically identical, and it means
     the cap, the bonus-point sum and the buy path all see one shape. The bundled
     example character had a `Daiklaves 2`.
   * The specialty **dot track is gone from the editor**. It was the one control left
     as a free setter in play "pending a rate"; there is no rate because there is no
     raising.
2. **Crafts and Colleges can be reduced.** *"Just because a misclick can always
   happen."* A usability rule, not a printed one, and recorded as such:
   `advancement.lower_craft` / `lower_college`, free, refunding nothing, removing the
   row at 0. Undo is LIFO and cannot always reach a mistake; this is the escape hatch.
   **A reduction is still not a refund** — `refund_to` remains the only path that
   returns experience.
3. **Nature freezes at the lock**, with the other chargen choices. No XP effect, but it
   is True Paragon's prerequisite, so a Nature changed in play would invalidate a held
   Merit after the fact.

---

## The Qt Edit surface — specialties move under their Abilities (2026-08-22)

**Not browser-verified.** Suite at the time: **2,776 passed, 1 skipped** (main PC,
`qt-port`). The webapp's Specialties panel is UNCHANGED; this is the native shell only.

`qt/editor.py` no longer has a Specialties panel. A specialty is a child row under its
own Ability's dot row, and every Ability row carries a `+`.

* Pre-lock: `+` appends an instance to THAT Ability; the name is editable in place, `✕`
  drops one instance.
* Post-lock: `+` opens a named-and-priced buy for that Ability
  (`advancement.add_specialty`); existing rows go read-only, as the Charms rows do.
* `view.specialty_groups(character, ability)` is the derived shape — `[(name, count)]`
  in first-seen order. It lives in the presenter so the webapp can adopt the same
  display without a second grouping implementation.

**⚠ The GROUP is the specialty.** Two rows named "Swords" are one specialty taken
twice, so a rename renames every instance in the group and `✕` drops exactly one. This
is the ruling above rendered honestly: the count IS the stacking.

**⚠ The cap is still not enforced on the add, and the REASON CHANGED.** It used to be
"the row is appended on Melee and retargeted, so blocking the add blocks the wrong
Ability". There is no retarget any more — the `+` knows its Ability. The reason now is
simply that chargen writes the list straight and `validate.check_specialties` reports
the over-cap, which is also what covers a save arriving over it; enforcing in a widget
would invent a rule the engine does not ask for. **The old reason is no longer true and
was rewritten in place** — a stale rationale reads exactly like a live one.

### What this removed

The blank-row-on-Melee-then-retarget dance, and with it the stale-validation trap it
created. That flow put a transient `specialty-cap` error on screen mid-edit, which then
needed a re-validation hook on the retarget or three Melee plus three Dodge read back as
"Melee has 4". Position now carries the Ability, so neither the transient error nor the
hook exists.

### What it turned up on the way

* **The new `+` and `✕` shipped INVISIBLE.** The Qt stylesheet gives every
  `QPushButton` `background:CARD`, and these sit on a `_Panel` — which is CARD. Every
  test passed; only the offscreen grab showed it. Same "an ancestor stylesheet beats a
  set palette" rule already recorded for `QTextEdit` inside a `_Panel`, third instance.
  Fixed with an inline `_TINY_BUTTON` style.
* **Two tests were nearly lost with the panel.** `_combo`'s enum-degradation control was
  written against the Specialties Ability dropdown. Deleting it alongside that dropdown
  would have retired a LIVE trap — the Virtue Flaw and camp selects still pass enum
  keys. Rebuilt on a synthetic subject so the next surface to move cannot take it down,
  and it immediately caught a wrong assertion: `currentData()` is still the degraded
  copy, which is the entire reason `_combo` resolves the key by index.

### No open rules questions

Nothing here needed a rules call. The instance-not-rating ruling above is the one it
rests on, and it was already recorded.
