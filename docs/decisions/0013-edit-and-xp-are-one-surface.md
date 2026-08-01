# 0013 — Edit and XP are one surface; the dot track is the buy control

**Status:** Accepted and implemented 2026-07-31; browser-verified the same day.
Build record: `docs/status/edit-xp-merge.md`.

## Problem

Edit and XP are the last surviving pair of tabs that implement **the same traits twice**
under two budget regimes. Chargen gets `editor.py`'s dot grid — caste grouping, budget
headers, live validation, Merit-moved ceilings. Post-lock gets `xp.py`'s *dropdown per
trait kind*: one Attribute row, one Ability row, one Virtue row, each a select plus a
"Raise" button.

That asymmetry is not cosmetic, it manufactures bugs. Reported by a player 2026-07-31:
**`xp.py` hardcodes `cap: int = 5`** and passes it for both Attributes and Virtues, so
Legendary Attribute (6) and True Paragon (6) are unreachable post-lock — while
`advancement.raise_attribute` and `raise_virtue` honour both caps correctly and
`editor.py` reads them correctly at chargen. Game logic in the UI, contradicting the
engine, on one of the two surfaces only. Fixing the constant fixes the instance and
leaves the class.

This is the same duplication the Advantages tab removed in v0.7.6, and the same one
Charms and Combos never had: those tabs are ONE implementation that switches from picking
(free, within the chargen budget) to buying (with XP). Traits are the last hold-out.

## Alternatives

* **Keep two tabs; fix the caps.** Rejected. Two surfaces over one model drift by
  default, and every future trait rule has to be wired twice or it is wired once and
  silently wrong on the other side — which is exactly what happened.
* **Merge, but make the dot tracks up-only post-lock** (removal stays a separate named
  action). Rejected *despite* being the cheapest and the closest match to how Charms and
  Combos already behave. It preserves the "Reduce a Trait" card — a dropdown-per-trait-kind,
  the very UI this decision exists to delete — so the unification stops one step short of
  its own point.
* **Merge; allow a downward click only when that trait's raises are the tail of the XP
  log**, reading as undo. Rejected as the worst of the three. Legality would be invisible
  and time-varying: the same dot is live before you buy a Charm and dead after, with
  nothing on screen explaining why. It also never reaches the reduction case, so the
  Reduce card survives anyway, and it is the only option users would learn a behaviour
  from that a later change would break.

## Decision

**One trait surface, on both sides of the lock.** The Edit tab stays visible post-lock and
its dot tracks change mode rather than being replaced:

* **Pre-lock:** unchanged. Free setters against the chargen budget.
* **Post-lock, upward:** a stepper. Clicking dot *N* from *M* calls the existing
  `advancement.raise_*` once per dot, so each step is priced from the live rating and
  logged as its own row. No new pricing code — the escalating `current × N` cost falls out
  of the loop. The whole click is costed before any of it commits, so a click you cannot
  afford is refused whole rather than half-applied.
* **Post-lock, downward:** a **dialog that asks which of the two downward events this is**,
  because the application cannot infer it:
  * **Undo** — refunds XP, pops log rows, LIFO, can never go below the chargen snapshot.
  * **Reduce** — free, refunds nothing, appends a reduction row, **requires a reason**
    (curse, permanent Charm cost), may go below the snapshot.

  The dialog names the dot count explicitly on both branches. A branch that is not legal
  is greyed; if neither is, the click is refused without opening anything.

The XP tab dissolves. The ledger becomes **read-only history on the sheet**; Undo lives
next to the buying, which is buy-where-you-browse extended to undo-where-you-bought.

## Consequences

* **A new engine predicate is required**: how many tail rows of the XP log are consecutive
  raises of a given trait. It decides what the dialog offers and caps the undo count. This
  is the one piece of the rejected tail-based option that survives — but it governs a
  dialog's contents, never whether a click does anything, so it is never the user's
  problem.
* **Willpower keeps an explicit reduce control.** It is not a dot track and cannot become
  one: decision 0005 pins its Virtue component at lock, so only `willpower_purchased` is
  editable and a dot gesture would misrepresent the total. Four of the five reducible
  targets move to the dot gesture; Willpower is the fifth.
* **The sheet stays pure.** `app.render_sheet` takes only a `SheetView` — no ruleset, no
  character, no callbacks — and the GM party screen and the render tests depend on that.
  The ledger on the sheet is therefore history, not controls.
* **Decision 0004 is untouched.** Chargen remains a snapshot, advancement remains an
  append-only log. This unifies the *surface*, not the model; every post-lock change still
  goes through `advancement.*` and is still logged.
* **The deferred current-vs-snapshot reconciliation stays deferred.** Because post-lock
  dots only ever move through `raise_*` / `undo_last` / `lower_*`, nothing hand-edits
  current state, which is the property the read-only lock was providing. Losing that
  property was the main risk of merging the tabs, and the stepper is what avoids it.
* A downward click on a chargen dot with nothing bought above it does nothing. That is
  correct — there is no XP to refund and no curse to record — but it is the one gesture
  that will read as a dead control.

* **Discovered while implementing:** making Edit a both-sides tab exposes every free
  setter on it to a locked character, and eight of them are chargen *choices* rather
  than traits to buy — Favoured Abilities/Attributes, caste, Exalt type, origin,
  upbringing, training camp, its choices, Calling, and the flawed Virtue. They set the
  rates every later purchase is priced at, so they are disabled once locked (readable,
  not hidden). Nature is deliberately left editable: no XP effect, and it changes through
  story. This consequence was not foreseen when the decision was taken.
