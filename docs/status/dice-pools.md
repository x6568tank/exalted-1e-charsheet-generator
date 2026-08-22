# Dice pools — the base-pool calculator

**Status: DONE 2026-08-12, browser-verified** — engine + data + UI, suite green
(2,255), committed as `f2ef735`. Clicked through by the human in its final shape (the
sidebar list plus the main-column custom builder); no defects reported.

The three open rules questions were RULED the same day (human, rules authority) and
all three are implemented — see **Rulings** below.
Decision record: `docs/decisions/0016-base-dice-pools-are-in-scope.md`.

## What it is

One number the sheet could already answer and didn't: *how many dice do I pick up?*
A **left sidebar on the Play tab** listing every roll at once, each on one line with
its own arithmetic — Dexterity + Melee + the daiklave's accuracy, a Virtue check, a
Willpower check — from traits already on the character.

**A list, not a picker** (human's call 2026-08-12). One shared weapon dropdown and
three penalty toggles sit above the list; the standing exclusions sit below. Nobody
drives a dropdown mid-turn to find out how many dice they hold — they scan for the
row. Two rolls expand into several rows because a list has nothing to pick from: a
Virtue check becomes one row per Virtue, and a roll whose Ability carries specialties
gets one extra row per specialty NAME (folding it in would claim dice the character
does not always have — p.134 scopes a specialty to its own facet).

In the **main column**, under the tracker, is a **custom Attribute + Ability panel**:
two dropdowns, all 9 × 25 pairs, computed live with the same penalty terms. It sits
there rather than in the sidebar because the roll list is long and the tracker beside
it is short — the panel fills that space instead of lengthening the taller side. The catalogue covers the rolls the
corebook spells out by name; the rest of 1e is "roll Attribute + Ability" for whatever
the table is doing, and there is no printed roster of those to author — so it is a
builder (`pools.custom_roll`), not data, and its `source` is deliberately left empty
so it never implies a page it does not have.

**No dice are rolled and nothing is resolved.** 0016 narrowed 0008's boundary to let
this exist; 0009 is untouched and was not reopened.

## The shape

| Piece | Where | What it does |
|---|---|---|
| `RollDefinition`, `PoolKind`, `WeaponStat` | `models/rules.py` | the shape of one named roll |
| `data/dice_pools.json` | 14 rolls | which traits compose each, off the printed page |
| `RuleSet.roll_catalog` | loader | keyed by id; optional file, empty = no presets |
| `engine/pools.py` | pure | `base_pool`, `wound_penalty`, `fatigue_penalty`, `mobility_penalty`, `specialties_for`, `weapon_minimum_shortfall` |
| `view.build_pool_sidebar` | presenter | every row computed at once; the play-state reads |
| `view.build_custom_pool` / `pools.custom_roll` | both | the player's own Attribute + Ability |
| `play.custom_pool_panel` | UI | the same, in the main column |
| `view.build_pool_view` / `build_pool_choices` | presenter | one roll at a time (kept; nothing on screen uses it now) |
| `ui/play.dice_pool_sidebar` | UI (webapp) | layout only |
| `qt/play.PlayPage._fill_pools` / `_custom_pool_panel` | UI (native) | the same two surfaces on the Qt Play tab (milestone 6, 2026-08-22) — layout only, off the same two presenter calls |

`PoolBreakdown` is `(roll, lines, total, excludes, notes)`; every contribution is a
signed `PoolLine`, and `total` is the sum of `lines` and nothing else, so a rendered
number can always be checked against the arithmetic that produced it.

## The rules, and where each came from

Every value is page-cited in `data/dice_pools.json` and in the code comments. The
load-bearing ones:

* **Attack** — "the attacker's player rolls Dexterity + the Ability that governs the
  kind of attack" (core p.228). Unarmed may use Brawl *or* Martial Arts, so those
  ship as separate rows rather than a choice inside one.
* **Weapon accuracy / defense** — "added to or subtracted from the character's
  Dexterity + Ability total when rolling for attacks", and defense "added … when she
  parries with the weapon" (p.327). Archery and Thrown restate it (pp.330-331).
* **Weapon minimums** — "for each dot the character is missing from any minimum, she
  subtracts 1 from the speed, attack and defense of the weapon" (p.327). Character-
  derived, so it is in the pool; it renders as its own negative line.
* **Specialties** — one extra die per instance, three per Ability (p.134). A specialty
  is an INSTANCE, not a rated trait (ruling 2026-07-31), so `Specialty.rating` is the
  count and the line's value *is* that count.
* **Armour mobility** — ⚠ **a PER-ROLL fact, not a blanket subtraction.** p.332: it
  "doesn't normally apply to attack and parry rolls, but does apply to dodge rolls and
  Athletics rolls for feats that require whole-body agility". Hence
  `RollDefinition.mobility_applies`, true for exactly two shipped rows, and a test
  that asserts exactly those two.
* **Wound penalties** — they apply to essentially every roll, Virtue and Willpower
  checks included (p.229's "Order of Modifiers"; ruled 2026-08-12). The one printed
  exemption is resisting infection, p.233. That is `RollDefinition.wound_applies`,
  and the gate is in the ENGINE, not the caller.
* **Accumulated armour fatigue** — "a -1 penalty to all actions", accumulating on
  each failed Stamina + Endurance roll and dissipating one point per eight hours of
  rest out of the armour (p.332). `PlayState.fatigue`, a manual counter.
* **Willpower checks** — the PERMANENT score, "not the current rating (the squares)"
  (p.88). So it is `derive.willpower`, not the play-state track.
* **Virtue checks** — the Virtue's rating alone (p.130).
* **The custom block's mobility** — OFF by default and a checkbox, not a guess.
  p.332 names dodge and whole-body Athletics feats, then adds that the Storyteller
  "can also apply this penalty to anything else she deems becomes more difficult in
  20 or more pounds of protective gear". That clause is a per-action judgement, so it
  is the player's to answer.
* **Which rolls a weapon belongs to** — read off the catalogue `tags` (five of them
  name an Ability: archery/brawl/martial_arts/melee/thrown; "blade", "impact",
  "spear", "artifact" and "ranged" do not). The character's `Weapon` is an inline copy
  carrying no tags (decision 0007), so the name is matched back to the catalogue. ⚠ An
  unmatched (homebrew, renamed) weapon returns None meaning **UNKNOWN, not "none"**,
  and applies everywhere — otherwise the first weapon a player names themselves
  silently stops adding its accuracy.
* **Magical materials** — the pool goes through `derive.effective_weapon` /
  `effective_armor`, so an orichalcum daiklave helps a Solar and not a Lunar (p.341),
  and moonsilver armour costs a Lunar no mobility (p.345).

## What is deliberately absent

Listed on-screen, under every pool, and this text is **load-bearing, not decoration**:
0008 rejected a static combat line because it "looks authoritative and is wrong the
moment a Charm fires", and the itemised breakdown plus this list is the mitigation
0016 accepted in its place.

* **Charm dice** — they need to know which Charms are ACTIVE, which is play-state
  (decision 0006). No Charm effect is modelled, and a test asserts a Charm-holding
  character gets the same pool as one holding none.
* Stunts, difficulty, range, cover, multiple-action splitting — Storyteller-supplied.
* Rolling, damage, soak-versus-attack, opposed rolls, initiative (0008, 0009).

**Do not collapse a row to a single number.** Each row renders `PoolBreakdown.compact`
("+4 dex +3 melee +2 acc -1 wnd -2 ftg") beside its total — a column of bare totals is
precisely the "looks authoritative" surface 0008 rejected, and a list of them would be
worse than the single number ever was. `tests/test_pools_ui.py` asserts the arithmetic
strings, not just the totals, for exactly this reason — and both the preset list and
the custom block render through one `play._pool_row`, so they cannot drift apart on
it.

## ⚠ The sidebar and the custom panel share one state dict across two columns

`new_pool_state` is created once in `build_play` and passed to BOTH, so the penalty
switches in the sidebar govern the custom rows in the other column. That only works
because neither block owns a private `@ui.refreshable` — each takes the caller's
`body.refresh`, which redraws the whole tab. A refreshable local to the sidebar
cannot reach across, and the failure is the silent kind this build keeps producing:
**the switch goes on working where you can see it and stops working where you
cannot.** `test_a_sidebar_toggle_reaches_the_custom_panel_in_the_other_column` is the
binding for it and has a verified negative control.

⚠ **The Qt tab has the same shape and the same trap.** `PlayPage._pool_state` is built
once in `__init__` and never inside a rebuild, and `_refresh()` redraws BOTH columns
rather than the one that was clicked — for the same reason, plus a second: a health mark
is a term in every pool row on the other side. A per-panel redraw would leave the roll
list showing an undamaged character's dice.

## Play-state isolation, concretely

`engine.pools.base_pool` **never reads `Character.play`**. The wound and fatigue
penalties arrive as caller-supplied signed integers; `pools.wound_penalty()` and
`pools.fatigue_penalty()` are separate functions the presenter calls and hands back
in — and neither creates `Character.play`, so a never-played character's save stays
clean. That keeps the one play-state read visible at
the call site and keeps the pool a pure function of (RuleSet, Character, choices). A
test greps `validate/advancement/lifecycle/costs` for an import of `pools`.

## Rulings — human, 2026-08-12

1. **Wound penalties DO apply to Virtue and Willpower checks.** Shipped as
   `RollDefinition.wound_applies`, defaulting True. A Valor-1 character at -1 reads
   0 dice, and that is correct.
2. **The resist-infection row is exempt**, because p.233 says so in as many words.
   `wound_applies: false` on that row only — and the panel STATES the exemption
   rather than offering a switch, because it is a printed rule, not a preference.
   ⚠ The exemption names wound penalties and nothing else, so armour fatigue still
   subtracts from that roll.
3. **Accumulated fatigue is tracked.** `PlayState.fatigue`, an unbounded positive
   counter with its own panel on the Play tab, shown when armour is worn or points
   are already on the clock (they outlive taking the armour off). It subtracts from
   every pool with no per-roll gate — "all actions" is unqualified. Nothing adds or
   sheds a point: one needs a failed roll (0009) and the other needs eight hours of
   in-game rest, which this build does not track. Both are the ST's, exactly as
   Limit is.

## ⚠ The sign trap, found while wiring fatigue

`Armor.mobility_penalty` is stored **already signed and NEGATIVE** in
`data/armor.json` (a buff jacket is -1). The first cut of `pools.mobility_penalty`
read it as a positive magnitude and negated it — which turns a -1 into **+1 bonus
die**. It survived the first round of tests only because every fixture in the test
file had been written with the wrong sign too, so engine and test agreed with each
other and neither agreed with the data.

The engine now takes `abs()`, as `engine/adversaries.py` already did, so a
hand-typed positive is still a penalty. Two tests pin it: one asserts both signs
subtract, one asserts the shipped catalogue is all ≤ 0. **The general lesson: when a
new consumer reads an existing field, check the sign convention against the DATA, not
against a fixture you wrote yourself.**

## Not done

* No dice-pool surface on the GM party page or the adversary roster.
* The catalogue is core-only. Splat books that print their own rolls (Sidereal
  astrology, Alchemical Charm-slot actions) are not swept.

## What preflight could and could not check

Whether the numbers are RIGHT for a real character at a real table — which the
click-through then answered, and cleanly. Pass 1 found nothing (this feature adds no
effects-dataclass fields); pass 2 found one real bug of its own — the panel's selection state lived inside the tracker's refreshable body, so
marking damage reset the player's chosen roll on exactly the click that sends them to
the pool. Fixed by hoisting it to `build_play`, with a test that has a verified
negative control.
