# The dumb dice roller — decision 0019's build record

**Status: BUILT 2026-09-08. NOT browser-verified in its final shape.** The human
clicked the roller and the initiative rating mid-session and reported them fine; the
**transcript fold, the batch roll and the two layout fixes landed after that**, and
have been seen only as offscreen renders. Suite green at **3,356 passed, 1 skipped**.

Decision record: `docs/decisions/0019-a-dumb-dice-roller.md`. Read it before touching
any of this — its **no-wire rule** is what allows the feature to exist at all, and no
test in the suite can notice its loss by accident (the ones that can are named below).

## What shipped

Three pieces, all on surfaces that already existed.

| Piece | Where | What it does |
|---|---|---|
| `engine/dice.py` | pure | `roll(count, target_number, die_faces, *, doubles_tens, can_botch, rng)` → `RollResult(faces, successes, botch, …)`; `count_successes` for an already-rolled handful |
| `view.new_roller_state` / `roll_dice` / `RollEntry` | presenter | the single roller's controls and its capped session transcript |
| `view.roll_log_split` / `previous_rolls_label` | presenter | newest line above the fold, the rest behind it |
| `engine/initiative.py` | pure | `initiative(ruleset, character, *, weapon)` → `InitiativeRating(lines, total, excludes, turn_note, tie_break)` |
| `view.build_initiative` / `InitiativeView` | presenter | the rating for the weapon the pool sidebar already names |
| `view.new_batch_state` / `batch_roster` / `batch_rows` / `roll_batch` / `BatchRoll` | presenter | the Storyteller's multi-row batch and its fold state |
| `ui/play.dice_roller_panel` · `initiative_panel` | UI (webapp) | Play tab; layout only |
| `qt/play.PlayPage._build_roller` · `_initiative_panel` | UI (native) | the same two, same tab |
| `ui/gm.batch_roller_panel` · `qt/party.PartyPage._build_batch` | UI (both) | the batch, below both rosters on the party surface |

**The roller** takes a dice count, a target number, a free-text label and two
switches, and prints the faces, the success count and a botch flag. Results are a
transcript: capped at `view.ROLL_LOG_LENGTH` (12), never written to a `Character`,
gone with the session. The newest roll shows; the rest fold behind
**"Previous rolls (N)"**, collapsed by default (human's ask — a table session's log
otherwise pushes the controls off the panel).

**The initiative rating** is Dexterity + Wits + the wielded weapon's Speed, itemised,
in its own card captioned **"A RATING, NOT A POOL"**, carrying the `+1d10 each turn`
line and the tie-break. It reads the same weapon the pool sidebar's "Attack with"
control names.

**The batch roll** is the Storyteller's: a name for the batch, then one row per
roster entry — name, dice count, optional per-row label — and one press. The log
folds under the batch's name; opening it shows a line per row. A row left at **0
dice sits the batch out**. Adversaries are included, because a dice count does not
care whether it came from a `Character` or an `Adversary`.

## The rules, and where each came from

The two dice rules were grepped out of `images/_extracted/Exalted Core.md` on
2026-09-08 and are quoted in full in 0019. The initiative modifiers are the **human's
ruling of 2026-09-08**, given with their own citations.

- **The Rule of Ten** (p.90) — a 10 counts as **two** successes. ⚠ The default
  success count is therefore **not** `len([d for d in dice if d >= tn])`; plain
  counting would have shipped silently wrong, and nobody raised it unprompted.
- **The Rule of One** (p.89) — a botch is no die at target-or-higher **and** at least
  one 1. ⚠ **1s never subtract successes.** That is another edition's convention and
  is the thing to refuse if it is ever proposed.
- Both switches default **ON** because both rules are general; the printed exceptions
  (damage rolls, the Rune) are per-effect and switch both off together, so they are
  controls the player flips on the Storyteller's say-so, not logic.
- **Initiative** (p.227) — Dexterity + Wits + weapon Speed, then +1d10 each turn;
  ties break on the higher Dex + Wits, then a roll-off. Speed is a **flat modifier,
  not dice** (p.326), and the sign is stored in the data (Daiklave +3, Grand Daiklave
  −3, Sledge −6), so no caller flips it.
- **Speed is adjusted twice**, both through code that already owned the rule:
  `derive.effective_weapon` for the magical material (p.341 — orichalcum +1 for
  Solars, jade +3 for the Dragon-Blooded, nothing from moonsilver/starmetal/
  soulsteel, and the Exalt-type gate plus `no_magical_material_bonus` come with it),
  and `pools.weapon_minimum_shortfall` for −1 per dot short of the weapon's minima.
- **Excluded from the rating, and said so on the surface**: Charms (Speardancer
  Concentration is named as the example the player adds themselves), armour mobility
  and encumbrance, accumulated fatigue, and wound penalties. ⚠ The mobility exclusion
  is the human's **reading of p.332's scope**, not an explicit exclusion in the text.
  Fatigue is left to the Storyteller because the core initiative rules make no such
  adjustment. Wound penalties reach initiative only under **Power Combat**, which
  this build does not implement — ⚠ and adopting Power Combat redefines Speed as a
  function of reach and adds a Rate stat, so **every weapon value in `data/` changes
  with it**. That is not "add a wound line".
- The rating is **not clamped**: a Sledge in weak hands is a negative rating and
  nothing printed floors it, the same reasoning `PoolBreakdown.below_one` carries.

## The no-wire rule, and the tests that guard it

0019's load-bearing clause is that the roller never learns *which* roll it is
rolling. It is presentational and therefore easy to polish away. These assert it —
they are the reason the feature is safe, and deleting one is deleting the mechanism:

| Test | What it pins |
|---|---|
| `test_dice.py::test_the_roller_takes_a_count_and_never_a_roll` | `dice.roll`'s parameter set, exactly |
| `test_dice.py::test_the_module_imports_nothing_from_the_character_or_rules_models` | the engine module holds no `exalted_builder` object at all — negative-controlled by wiring a `Character` in and watching it fail |
| `test_dice.py::test_a_result_carries_no_name_for_the_roll` | no name/label/definition field on a `RollResult` |
| `test_dice.py::test_no_probability_or_odds_helper_is_exposed` | 0009 barred a success-odds display by name; 0019 keeps that bar |
| `test_dice.py::test_the_presenter_takes_no_roll_definition_either` | the seam where a `PoolRow` and the roller are both visible |
| `test_roller_ui.py` / `test_qt_play.py::test_no_pool_row_grows_a_roll_button` | exactly ONE Roll button on a page rendering the full pool catalogue |
| `test_batch_roll.py::test_the_batch_takes_rows_and_counts_and_never_a_roll` | the batch signature |
| `test_batch_roll_ui.py` / `test_qt_party.py::test_no_row_offers_a_named_roll_to_fill_its_count` | no select/combo beside a batch row offering a named roll — **the most likely future regression**, because with six rows on screen it is the obvious convenience |
| `test_initiative.py::test_initiative_is_not_a_row_in_the_roll_catalogue` | 0019 forbids an initiative row in `data/dice_pools.json`; asserted by id **and** by name |

The pool list's standing caveat was reworded in both shells to say the rule on the
surface: *"Nothing is resolved here, and no row rolls itself — the roller takes a
number you type."*

## What the work turned up on the way

- ⚠ **The Qt health track drew at two different pitches, and it was pre-existing.**
  A wrapped track (more than `_BOXES_PER_ROW` levels — an Ox-Body character) drew its
  full rows justified across the panel and its short final row packed left, because
  only the **last** row got a trailing stretch and a `QHBoxLayout` of fixed-size cells
  with no stretch spreads its slack *between* them. Reported by the human against the
  Play tab as "something weird"; confirmed pre-existing by rendering the same tab from
  a clean HEAD worktree. **The party card had the identical defect**, one widget class
  over. Both fixed, both covered by geometry tests measuring box pitch per row, both
  negative-controlled (the old code measures 53 vs 34 and the tests fail).
- ⚠ **`qtbot.waitExposed` returns before a nested `QScrollArea` has laid out its
  contents.** Every box then reports the same `y`, so a geometry assertion reads one
  row where there are two and passes vacuously. Needs a `qtbot.wait(50)` before
  measuring. Adding that wait too broadly broke an unrelated scroll test's timing —
  it is now applied only where geometry is measured.
- ⚠ **`_StatLine` cannot be given a fixed width.** Its `Ignored` horizontal size
  policy beats `setFixedWidth` and collapses the label to nothing. A long roster name
  ("Gearheart-of-the-Ninefold-Cog") pushed its batch row's dice box out of line with
  every other row's; the fix elides explicitly against a known width. **The collapse
  was invisible to the tests and only showed in a render.**
- The example characters are faithful to the catalogue where it looked wrong: Ashes
  of Dawn's **Reaver Daiklave really is Speed +0** in `weapons.json`. Yarak's
  orichalcum Daiklave reading **+4** (3 printed, +1 material) is the real-data proof
  that the material path reaches initiative.

## Planned — roll initiative for everyone, once the GM page holds real characters

✅ **BUILT for the campaign table, 2026-09-24** (P3 step 9; `docs/plans/p3-tables.md` §14 "Step 9"). The desktop Party page and Qt do not have it. The text below is the reasoning it was built on.

**Originally: not now, and it has a hard precondition.** Today the party surface owns its own
roster entries, not links to the players' characters, so it has no Dexterity, Wits or
wielded weapon to read. **Once the GM page is linked to the players' actual characters
rather than being its own separate thing** — the hosted/VTT shape in
`docs/plans/hosting-state-model.md` — add a way to roll initiative for the whole table
in one press: `engine.initiative` per linked character for the rating, plus one d10
each, sorted descending, with the printed tie-break (higher Dex + Wits, then a
roll-off).

⚠ **This does NOT breach 0019's no-wire rule, and the reason is specific to
initiative**: the +1d10 is a *fixed, printed* die count (p.227) that no Charm, stunt or
ST modifier feeds into, so the roller is still being handed a number rather than a
named roll. **Nothing else on the sheet gets this treatment** — the moment a
"roll everyone's Join Battle/attack/Melee" appears next to it, the wire 0009 barred is
back. Keep it a one-off, and keep it out of `data/dice_pools.json` (see the initiative
test above, which forbids that row by id and by name).

## Open — for the human

Two TODOs the human raised at the end of the session are in
`docs/status/handoff.md`, both quoted verbatim and neither started: the Qt Party
window still being **structured like a copy of the webapp**, and the batch roll being
**all-or-nothing** when they want to choose how many rolls and for whom. ⚠ The second
is ambiguous between "select the participants" and "several rolls for one character"
— the handoff says to ask before building either.

No open **rules** questions. Everything above is either page-cited or the human's
explicit ruling of 2026-09-08.

## What a human should click

Nothing below has been seen outside an offscreen render.

1. **Play tab, both shells** — roll 15–20 dice a few times: every 10 must count twice.
   Roll 1–2 dice until a 1 comes up with no success: **Botch**, not Failure. Untick
   "Can botch" and confirm the same dice read Failure.
2. **The transcript fold** — after three rolls, "Previous rolls (2)" with the newest
   line outside it. Open it; roll again; it should stay open.
3. ⚠ **Roll with the label box EMPTY.** The line must carry the outcome and the dice
   and **no roll name anywhere**. This is 0019's whole safety mechanism and no test
   failure will ever tell you it broke.
4. **Initiative** — Yarak unarmed reads 7; with the Daiklave chosen, 11 (`+5 dex
   +2 wits +4 spd`, the +4 being orichalcum on a Solar).
5. **The party surface, both shells** — name a batch, give two rows dice and leave one
   at 0, press Roll all. The fold shows the batch name; opening it shows a line per
   row labelled with whose dice they were.
6. **A wrapped health track** (any Ox-Body character, or Yarak's 19 levels) on the
   Play tab **and** on a party card — the boxes must hold one pitch across both rows.
