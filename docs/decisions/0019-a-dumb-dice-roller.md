# 0019 — A dumb dice roller, unwired from the pools

**Status:** Accepted, 2026-09-08. **Reverses [0009](0009-no-dice-rolling.md)** in a
narrow, named shape, and amends one clause of
[0016](0016-base-dice-pools-are-in-scope.md). Also amends 0016's initiative exclusion.

⚠ **0009 says "Do not propose it."** That bar was not violated: the human reopened it
themselves (2026-09-08), unprompted, in the course of costing a hosted/VTT-ish table.
A future session must still not propose *extending* this — the bar survives for
everything 0009 barred that this record does not name.

## Problem

0009 barred rolling of any kind, and its reasoning was that a roller is the thin end:
once the app knows a pool, rolling it is a small change, and the next ask is Charm dice —
which is modelling Charm effects across 1,921 Charms, the open-ended job that
[0008](0008-no-combat-derivation.md) rejected and that made the old Merits & Flaws
implementation unmaintainable ([0011](0011-merits-and-flaws-return-centralized.md)).

That reasoning is about **the wire between the pool and the roll**, not about dice. A
roller that never learns which roll it is rolling cannot be asked for Charm dice, because
it does not know a Charm could apply. The human's framing (2026-09-08): *"a dumb roller
where you tell it how many dice to roll… no actual dice pools. In-app dice pools could be
used as a starting point, and explicitly say to ask the ST for modifiers."*

## Decision

**The app may roll a NUMBER of dice. It may not roll a ROLL.**

In scope:

* A roller taking a **dice count** the player types in, plus an optional target number,
  die type, and two switches — **`10s count double`** and **`can botch`**, both defaulting
  ON. That is its entire input. The switches exist because the printed exceptions to those
  two rules are per-effect and the roller cannot know which roll it is rolling; the player
  turns them off because the ST said so, not because the app worked it out.
* Reporting the **faces rolled and the success count**, and nothing else. Success
  counting carries the two core rules below — both are properties of a handful of dice
  and know nothing about the character, so neither breaches the no-wire rule.
* An **initiative rating** on the sheet — but not as a pool row; see below.
* Pre-filling the dice-count field from a `PoolBreakdown` row — see the no-wire rule
  below for the three conditions that makes legal.
* An **initiative** row in `data/dice_pools.json`, lifting 0016's exclusion of it —
  see the caveat below, which is a blocker on authoring it.

Out of scope, and this is what keeps 0008 and the rest of 0009 intact:

* **Charm dice.** Unchanged from 0016. Nothing is modelled.
* **Storyteller modifiers** — stunts, difficulty, environment. The surface says to ask
  the ST; it does not offer a field that implies the app could know.
* **Resolution.** No opposed rolls, no damage, no soak comparison, no "you hit". Two
  rolls on one screen are two numbers, never a contest.
* **A success-odds or probability display.** 0009 barred this by name and it stays
  barred — it is the CRPG tell, and it needs no dice to appear.
* Rolling anything **automatically**, on any trigger. The player presses the button.

### ⚠ The no-wire rule — the load-bearing part of this record

The gap between a pool row and the roll box is the whole safety mechanism. It is the same
shape as 0016's "an itemised breakdown, never one big number": presentational, and
therefore easy for a later session to polish away without noticing what it was for.

Pre-filling the box is permitted **only** if all three hold:

1. The value lands in an **editable field** the player must press Roll on. It is a
   suggestion, not a submission.
2. The result's label is **free text the player types or edits** — "Attack on the bandit",
   "Resist the poison" — and **never the roll definition's name or id**, auto-filled or
   otherwise. Ruled 2026-09-08; the human's own wording is *"it has a label, and you input
   how many dice."* A label the app chose is the app claiming the pool was right, which is
   exactly 0008's *"looks authoritative and is wrong the moment a Charm fires."* A label
   the player wrote is the player's claim, and it also covers the great majority of 1e
   rolls that are in no catalogue at all.
   ⚠ **This is why a shared roll log stays legible without the app asserting outcomes.**
   Deleting the free-text field and substituting the roll name is the exact regression
   this record exists to prevent.
3. The pool surface keeps saying **what it excludes** and to ask the ST. 0016 already
   requires this; the roller makes it load-bearing rather than merely honest.

**A future change that binds a roll definition to a roll result re-creates the thing 0009
was written to prevent, and no test will fail.** Put it on the click-through list.

### The three values this record needs, all off the page

Sourced 2026-09-08 from `images/_extracted/Exalted Core.md`. ⚠ **Those passages are
glyph-ciphered** — "Iowever" for However, and the dice in the worked examples render `1`
as `0` and `10` as `/`. The **prose rules are clean and are what is quoted**; nothing here
is derived from an example's digits. Re-check against the page image before trusting any
number that came out of an example.

⚠ **The page numbers come from the book's own INDEX** (`Rule of One 89`, `Rule of Ten 90`),
not from the transcription's `<!--PAGE-->` markers, which sit one page early here. That is
the offset trap `status/core-charm-retranscription.md` already records.

* **The Rule of Ten** (Core p.90): *"Whenever a character rolls a '10,' that die counts as
  **two** successes."* ⚠ The roller's default success count is therefore **not**
  `len([d for d in dice if d >= tn])`. Neither the human nor the model raised this
  unprompted; plain counting would have shipped silently wrong.
  **It is general, and two printed EXCEPTIONS prove it** — both switching off the same
  pair of rules together: **damage rolls** (*"you cannot botch a damage roll… Conversely,
  rolling a 10 on the damage roll does not count as two successes"*) and **the Rune**
  (*"The player cannot botch these rolls, and 10s do not count as two successes on
  them"*). Damage rolls are out of scope under [0008](0008-no-combat-derivation.md)
  regardless.
* **The Rule of One** (Core p.89): *"if any die on such a failed roll comes up '1,'
  you've botched… as long as you roll at least one success, you ignore any [1]s."* So a
  botch is **no die at target-or-higher AND at least one 1**. ⚠ **1s never subtract
  successes** — that is a different edition's convention and it is the thing to refuse if
  it is ever proposed. The human's initial call was "1e has no botch logic by default"
  (2026-09-08); the page overrides it, and the half they were right about is the absence
  of a subtract mechanic.
* **Initiative** (Core p.226; weapon Speed p.326): base initiative is **Dexterity +
  Wits**, adjusted by the wielded weapon's Speed — *"added to or subtracted from the
  character's initiative total"*, a **flat modifier, not dice** — giving the *initiative
  rating*. Then *"every turn, each player rolls a 10-sided die and adds the number
  rolled."*

⚠ **Initiative is therefore NOT a dice pool and must not be authored as a row in
`data/dice_pools.json`.** It is a static rating (trait arithmetic, in scope under
[0016](0016-base-dice-pools-are-in-scope.md) like any other) plus a single d10 the roller
already handles. The human's working figure was "Dexterity + Wits + weapon speed dice,
+10", which is wrong in both halves — speed contributes a modifier rather than dice, and
the +10 is **+1d10**, not a flat ten. `Weapon.speed`'s existing comment
(`models/rules.py:1206`, *"modifier to initiative"*) was right all along.

## Alternatives rejected

* **Keep 0009 whole.** Costs the one thing a hosted table actually wants, to protect a
  line whose reasoning is about the wire, not the dice.
* **A roller wired to the named rolls** — press Roll on the "Attack — Melee" row. This is
  0009's own rejected "narrow roller… the opening only ever widens", and it is the version
  that generates the Charm-dice ask. Rejected explicitly and by name.
* **A roller that silently omits Charms but is labelled as a full roll.** 0008's other
  rejected alternative, verbatim: *"worse than nothing."*
* **No pre-fill at all** — force the player to retype the number. Considered and not
  taken: it buys nothing the three conditions above do not, and a number the app already
  computed being untypeable is user-hostile.

## Consequences

* **0009 is no longer "Accepted" in its own terms** and its index row must say so. Its
  reasoning survives and is quoted above; its conclusion does not.
* **0008 is untouched.** It stays intact *because of* the no-wire rule, not despite the
  roller — which is why that rule is in this record and not in a UI comment.
* The roller is **pure and toolkit-free** like the rest ([0002](0002-data-driven-rules-pure-engine.md)):
  an `engine/` function taking `(count, target_number, die_faces)` and returning the faces
  and the success count, so both shells and any future hosted client share it. The RNG is
  injectable, because a roller that cannot be seeded cannot be tested.
* **Roll results are not persisted to the character.** They are not play-state and not
  permanent state; they are a transcript. A *shared* roll log is party state and only
  exists if hosting does.
* It ships in **both shells** — `ui/` and `qt/`. A feature that lands in one is how the
  two products drift.
* This record does **not** decide hosting, a shared roll log, or a whiteboard. Those are
  costed in `docs/plans/hosting-state-model.md` and the handoff, and none is ruled.
