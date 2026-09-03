# Artifact attunement — commit the motes

**Status: PHASE 1 DONE (2026-09-03), phases 2-3 open.** Planned 2026-09-02; the four
blocking questions were resolved 2026-09-03 against the corebook, a Dragon-Blooded
Aspect book and the Player's Guide — see **Resolved questions** below.

⚠ **The fields are stored, carried and toggled, and NOTHING READS THEM YET.** That is
species 2 of the house bug by construction — `attuned` looks exactly as healthy today
as `attunement` did before this plan, and every screen is correct because no screen has
changed. Phase 2 (`derive.committed_attunement` + `build_play_view`) is what makes the
feature exist. **Do not close this plan on phase 1's tests being green.**

## The ask

An owned artifact with a printed attunement cost should be able to *commit* those
motes, shrinking the Essence the Play tab has left to spend.

**Explicit toggle, not automatic** (human, 2026-09-02): *"you can own artifacts without
being attuned to them."* Ownership and attunement are different facts, and the daiklave
in the manse is not committing anything. So the flag is the player's, defaulting off,
and "has an attunement cost" only decides whether the toggle is *offered*.

## What exists today

`attunement` is a **zero-read-site field** — a display-only number, the same
fingerprint as `source.book`.

| Where | What |
|---|---|
| `models/character.py:416` (`Weapon`), `:453` (`Armor`) | `attunement: int = 0` |
| `models/rules.py:1178`, `:1218` | the catalogue counterpart, copied on a pick |
| `ui/gear.py:380,425` · `qt/gear.py:67,72` | an editable spin box, both shells |
| `ui/view.py:3950,3970` | a field in the custom-gear authoring form |
| `engine/gear_actions.py:325,337` | dumped into a saved library row |

Nothing reads it. `engine/derive.py`, `engine/play.py` and `engine/pools.py` do not
mention it, and `PlayState` has no committed-motes concept — only
`motes_personal_spent` / `motes_peripheral_spent`, two dumb counters.

⚠ **`ArtifactEntry` has no `attunement` field at all** (`models/character.py:99-143`) —
only `name`, `rating`, `note`, `acquired`, and neither does its catalogue counterpart
`ArtifactType`. Resolved question 4: `ArtifactType` gains the field in phase 1; see
below.

## The constraint this runs into

`engine/play.py`'s module docstring is a standing bar:

> ⚠ **This is a DUMB tracker and must stay one.** No auto mote-accounting, no
> damage-wrapping rules, no auto-healing — the Storyteller stays in control.

An explicit toggle is what keeps this inside the bar: the player says "I am attuned",
and the pool arithmetic follows from a stated fact rather than the tracker deciding one.
**Nothing here may auto-attune on purchase, on equipping, or on load.** The bar still
forbids the obvious next step (auto-committing when a Charm fires); do not take it.

⚠ **Decision 0006 — play-state is validation-isolated.** `attuned` lands on the *gear
row*, which `engine/validate/` already reads for the Artifact budget. Nothing in
`validate/` may read the new field: whether you are attuned must never change what you
may legally buy. `tests/test_play_state.py` guards the import direction but **not** this,
so it needs its own negative test (below).

## Design decisions taken

**1. The flag lives on the gear row (`Weapon.attuned` / `Armor.attuned`), not in
`PlayState`.**
Decision 0006 argues for `PlayState`, but gear rows are inline copies addressed by list
index — there is no stable key to point at. `artifacts.item_key` keys on *name*, and two
identical daiklaves collapse onto one key (see [[feedback_duplicate_background_names_need_ids]]:
a shared printed name matches every copy, and the bug is on the row you are not editing).
A bool on the row cannot drift from the row.

The cost of this choice: a *play* fact now sits in the *permanent* model, so it rides
along into `library_payload` territory and into the artifact-budget neighbourhood. Both
are handled below.

**2. The tracker's pool maximum shrinks** (human, 2026-09-02). Whichever pool a
commitment is allocated to comes down by that item's committed total in
`build_play_view`, and the Play tab's boxes literally get shorter. Rejected: the
Alchemical installation-motes model (`ui/view.py:2385,2415`), which displays a *fit*
against `derive.charm_installation_pool` without subtracting — correct there because
installation is a chargen-legality check, wrong here because attunement is a live
capacity.

**3. The allocation is a per-row field, not a derived split** (follows from resolved
question 1). Since the player freely chooses Personal vs Peripheral per commitment —
same as any Charm cost — `attuned` alone isn't enough data to know which pool to shrink.
`Weapon`/`Armor` gain `attuned_pool: Literal["personal", "peripheral"] = "peripheral"`,
editable alongside the checkbox, meaningful only when `attuned` is set. Defaults to
Peripheral as the common case (an artifact's anima flare is usually already accepted;
Personal is the scarcer, more deliberately-spent pool) — the default is a UX choice, not
a rules one, and the field stays fully player-editable either way. On a merged-pool
splat the dropdown is moot (there is only one pool to land in) but the field still
exists; the derivation reads whichever pool actually has a nonzero max.

## Resolved questions (2026-09-03)

1. **Which pool?** — **The player allocates, same as any Charm cost.** Core p.147-148:
   *"Characters can freely mix Personal and Peripheral Essence when using a Charm — only
   the motes of Peripheral Essence count toward the anima banner."* The daiklave rule
   (core p.344) explicitly ties artifact commitment to this same mechanic: *"she must
   commit 5 motes of Essence... just as if she was sustaining the magic of a Charm that
   cost 5 motes to activate."* **Not fixed to Peripheral** — the plan's original
   assumption was wrong. This means the commitment needs a stored *allocation*, not a
   single subtraction: see the new design decision 3 below.
2. **Merged pools?** — **Resolves itself once Q1 is implemented.** A merged-pool
   character (`essence_pool_is_merged`) has only one pool to allocate the commitment
   into; no special-casing needed beyond what the allocation mechanism already requires.
3. **Does the number vary with the wielder?** — **Yes, confirmed and generalized**
   (human's ruling, 2026-09-03): *any* magical item costs **double** its printed
   commitment for a wielder who is not a "user" of that item's material — jade for a
   non-Terrestrial, soulsteel for a non-Abyssal, moonsilver for a non-Lunar, starmetal
   for a non-Sidereal, orichalcum for a non-Solar. Sourced from one concrete example:
   `images/Dragonblooded/Aspects/Earth/CH 6 - Miracles of Pasaip.md`, a jade Hearthstone
   Compass note that it does *not* impose "the usual double mote commitment for
   non-Terrestrials" — "the usual" confirms this is the GENERAL rule, this item the
   exception. Mechanically the same shape `derive.effective_armor` already handles for
   per-wielder material soak bonuses — `committed_attunement` must read the *effective*
   item (material + wielder), not the stored row.
4. **Should `ArtifactEntry` gain an attunement number?** — **Yes**, on `ArtifactType`
   (`data/artifacts.json`'s 330-row catalogue), zero-defaulted. ⚠ **Only author a
   nonzero value for genuinely standalone Wonders.** `ArtifactType`'s own docstring
   already documents that some rows are gear-statblocked duplicates that also live in
   `weapons.json`/`armor.json` (its own worked example: the Skirmish Pike) — for those,
   `Weapon`/`Armor`'s `attunement` is already the authoritative number, and giving
   `ArtifactType` a second one invites the two drifting apart. Leave those rows at 0 and
   steer players to enter the item as a `Weapon`/`Armor` row instead if they want its
   attunement tracked — the same steer the catalogue already gives for stats generally.
   No new source of truth; the backfill itself (which rows get a real number) is a
   separate authoring pass, not phase 1.

   **Lead for that pass, measured 2026-09-03: the numbers are already in `data/`.** Of
   the 330 rows, **195 mention motes in their transcribed description and 74 state a
   commitment in a directly parseable shape** ("Commit 5 motes to attune", "Commits 3
   motes"). Those descriptions came off the page under the human's own vetting, and
   `data/` is an allowed source by the never-author-from-memory rule, so this is a
   parse job rather than a re-read — the same mechanical-extraction shape that beat
   hand-typing before. ⚠ **The parse must EXCLUDE gear-statblocked duplicates**: the
   Skirmish Pike is in the 74 and must stay 0 here, because `weapons.json` already
   carries its 5. Filter against `gear_stat_line` before writing anything, and verify
   every parse rather than trusting the regex.

### Mortal / God-Blooded gating (Player's Guide, not one of the four blockers but load-bearing)

* **God-Blooded**: `mf.magical-attunement` (4-pt Supernatural Merit, prereq
  `mf.awakened-essence`) — automatic once bought, "like other magical beings," just
  capped off the Magical Material bonus (PG p.66). Already wired per the 2026-09-02
  session (handoff). No new mechanic needed here.
* **Mortals**: a *different*, cheaper Merit (2-pt Supernatural, prereq Essence
  Awareness, PG p.120) — but attuning is **not automatic**: *"Any attempt to attune to a
  device requires a Willpower roll, difficulty = half the device's commitment cost.
  Failure drains double the commitment cost. A botch drains all Essence."* That roll is
  out of scope by decision 0009 (no dice rolling, ever) and `engine/play.py`'s dumb-
  tracker bar. **Ruling: model it as the same toggle as everyone else, gated on the
  Merit.** The roll is resolved off-screen by the table; the checkbox just represents
  the stated outcome ("I succeeded, I'm attuned"), and a failed/botched attempt's mote
  drain is reflected manually in the existing dumb `motes_*_spent` counters like any
  other off-screen event. No roll logic anywhere in the engine — consistent with how
  the build already treats every other roll in the game.

## The work

### Phase 1 — the flag, the pool choice, and the toggle — **DONE 2026-09-03**

Built as planned, with three things the plan did not say:

* **`ArtifactEntry` carries the pair too, and the READ side is the one enumeration**
  (human's ruling 2026-09-03; the alternative considered and rejected was merging the
  three owned-item models into one). All three storage models carry
  `attunement`/`attuned`/`attuned_pool`; **`artifacts.ArtifactItem` grows the same three
  fields, and `derive.committed_attunement` walks `artifact_items()` — never the three
  lists.** The storage stays split because the three models differ by their printed
  STAT BLOCK (Acc/Dmg/Def vs soak vs neither), not by ownership semantics; merging them
  would give one row type with a union of mostly-zero fields — `ArtifactType`'s Skirmish
  Pike problem — and would not retire `from_artifact`, since a daiklave legitimately
  needs both a rating row and a stat line.
  The artifact editor gained the number and the toggle in both shells.
* **`library_payload` carries `attunement` for artifacts too**, alongside the weapon and
  armour rows that already did. `attuned`/`attuned_pool` are excluded from all of them,
  and the docstring now says why.
* **The pool dropdown is HIDDEN, not disabled, until the box is checked** — and hidden
  outright on a merged-pool character. Both shells.

⚠ **THE DOUBLE-COUNT GUARD NOW COVERS MOTES, and the GEAR ROW WINS** (human's ruling
2026-09-03). A daiklave entered as an `ArtifactEntry` *and* its `Weapon` stat line is
ONE object — `artifact_items` already drops the weapon so the p.131 budget charges it
once, and the commitment had to follow or the sword would commit its motes twice. The
fold reads the commitment off `artifacts.stat_line_row(character, key)` when one exists,
falling back to the artifact row otherwise; an ORPHANED link (artifact renamed or
deleted) leaves the gear row standing on its own, exactly as it already does for rating.
The editors enforce the same thing: an artifact with a stat line is offered a pointer at
it, not a second control. `ArtifactType.attunement` staying 0 on every gear-statblocked
duplicate (resolved question 4) is what makes the fallback safe.

⚠ **Known limitation, both shells: typing an attunement cost onto a row does not make
the toggle appear** until the editor is rebuilt (select another row and come back). The
control is decided at build time and the `Attune` spin box only re-syncs the summary. A
catalogue pick is unaffected — it rebuilds the pane — so this bites only hand-authored
gear. Left as-is rather than always-building-and-hiding, because the "offers no toggle"
tests would then be asserting on a hidden widget instead of an absent one. **Worth a
human's opinion; it is on the click-through list, not fixed.**

⚠ **Two test traps this cost, both now written into the tests themselves.** In Qt,
`isVisible()` is False for every widget on a page that is never shown, so a
visibility assertion passes against a control that is always shown and the positive
half cannot pass at all — **use `isHidden()`**. In NiceGUI, `from tests._ui_main import
CHAR_ATTUNE` reads a *different object* than the harness's copy (and breaks the next
test in the file), so the model write is asserted through its observable effect in the
client — the dropdown appearing — not by reading the character.

Both were negative-controlled: the Ghost branch was flipped to Solar and the merged-pool
test failed correctly; the `attunement > 0` guard was deleted and the one-checkbox test
saw two. Restored from a copy, never `git checkout`.

Original plan for the phase, kept for the record:

* `models/character.py` — `attuned: bool = False` and
  `attuned_pool: Literal["personal", "peripheral"] = "peripheral"` on `Weapon` and
  `Armor`, with a comment saying both are the PLAYER's statement and that no
  `validate/` module may read either.
* `models/rules.py` — `attunement: int = 0` on `ArtifactType`, comment steering authors
  away from double-entering a weapon/armor-duplicate row's number (see resolved
  question 4). No backfill required to ship phase 1; the field just needs to exist.
* **`engine/gear_actions.py` needs nothing for `attuned`/`attuned_pool`.**
  `_owned_fields` (line 40) derives the player's fields as the *complement* of the
  catalogue's, precisely so a new one is carried across a catalogue re-pick without
  anyone remembering to list it. Neither field is on `WeaponType`/`ArmorType`, so both
  survive a re-pick for free — but **assert that in a test**, because the whole reason
  that function is computed is that the hand-written version silently dropped
  `acquired` for weeks. `ArtifactType.attunement` DOES need copying onto a fresh
  `ArtifactEntry` pick, the same as `rating` already is.
* `library_payload` (line 303) must **not** gain `attuned`/`attuned_pool` — that
  function's docstring already says ownership state does not belong in a catalogue, and
  both fields are ownership/play state twice over.
* `ui/gear.py` — a checkbox in `_weapon_editor` / `_armor_editor`, beside the `Attune`
  spin box, **rendered only when `attunement > 0`**; a pool dropdown beside it, visible
  only when the checkbox is set (hidden entirely on a merged-pool splat — see phase 2).
* `qt/gear.py` — the same, but `_WEAPON_STATS` / `_ARMOR_STATS` are `(field, label,
  signed)` triples driving spin boxes and neither new field fits that table. Add the
  checkbox and dropdown outside the table rather than widening the triple for two more
  fields.

### Phase 2 — the derivation (once the material-doubling and allocation logic is written)

* `engine/derive.py` — `committed_attunement(ruleset, character) -> dict[str, int]`,
  keyed by pool (`"personal"`/`"peripheral"`), summing each attuned item's *effective*
  commitment into whichever pool its `attuned_pool` names. ⚠ **Iterate
  `artifacts.artifact_items(character)`, NOT the three owned lists** — that fold is
  where the one-object rule lives, and walking the lists directly re-opens the
  double-count for a linked pair. It already carries `attunement`, `attuned` and
  `attuned_pool`, resolved to the winning row. "Effective" means: double the
  stored `attunement` when the wielder is not a "user" of the item's Magical Material
  (resolved question 3) — read however `derive.effective_armor` already identifies
  material + wielder match, don't re-derive that lookup. ⚠ Weapons carry `quantity`; it
  is a count with no engine reader (decision 0008) and **must not multiply the
  commitment** — twenty attuned arrows are not twenty attunements.
* `ui/view.py:3116` `build_play_view` — subtract the personal/peripheral split from
  `personal_max`/`peripheral_max` respectively, each floored at 0. On a merged-pool
  splat (`essence_pool_is_merged`) route the whole total into whichever single pool is
  actually nonzero, ignoring `attuned_pool` (resolved question 2). `PlayView` gains a
  `committed: dict[str, int]` (or two ints) so the label can say *why* the pool is
  short; "Peripheral 4/10" with no explanation reads as a bug, the same reasoning that
  put `essence_single_pool` on the view.
* **The re-clamp.** `engine/play.py:set_motes` clamps to a cap *passed in by the caller*.
  Attuning something while motes are already spent leaves a stored
  `motes_peripheral_spent` (or `_personal_spent`) above the new maximum. Clamp on read in
  `build_play_view`, not by mutating the save from a derivation.

### Phase 3 — the surfaces

* `ui/play.py:380` and `qt/play.py:292` already render from `PlayView`, so both get the
  smaller pool for free — **but the party window does too** (`qt/party.py:584`,
  `ui/gm.py:428`), and that is three shells to look at, not one.
* The PDF sheet (`ui/pdf.py`) and sheet view print `attunement`; decide whether an
  attuned item is marked. Low priority.

## Traps, named

* **This is a house bug waiting to happen — species 2.** `attunement` has zero read
  sites today and looks perfectly healthy. The failure mode of this change is a flag
  that stores and displays fine while `build_play_view` never subtracts it, and every
  screen still looks right. **Test the pool, not the checkbox.**
* **`validate/` must stay blind to it.** Add a grep-style negative test in the mould of
  the no-module-names-a-Merit-id test: no module under `engine/validate/` may reference
  `attuned`.
* **The discriminator question.** `Weapon.from_artifact` is a discriminator nothing on
  screen may edit; `attuned` is the opposite by design — player-editable is the entire
  point. Say so in the comment, or the next reader "fixes" it.
* **A single-pool splat** puts everything in Peripheral and Personal at 0. A naive
  subtraction from Personal silently does nothing for ghosts and Beacon of Power holders
  — `attuned_pool` must be ignored, not trusted, on a merged-pool character.
* **The doubling is about the WIELDER, not the owner.** Two characters can have the same
  Weapon row (party-shared gear, a loan) — read the doubling off whoever is *equipping*
  it in the derivation's context, not a cached fact on the row itself, or a jade
  daiklave handed to a non-Terrestrial silently keeps costing half.
* **`ArtifactType.attunement` is zero-defaulted and will look identical to "authored
  clean" and "never backfilled."** The same fingerprint as `attunement` itself before
  this plan. Don't read a 0 on a Wonder as "this item costs nothing to attune" without
  checking whether anyone has actually transcribed the number from its page yet.

## Tests owed

1. ✅ `attuned` and `attuned_pool` survive a catalogue re-pick (`gear_actions.set_weapon`
   on the row's own name) — weapon and armour both, `tests/test_gear_actions.py`.
2. Committed total ignores unattuned items, and ignores `quantity`.
3. `build_play_view` reduces the named pool; **negative control** — clear the flag, pool
   returns.
4. A non-user wielder (e.g. a non-Terrestrial with a jade item) pays double; a user
   wielder (a Terrestrial with the same item) pays the printed number.
5. Merged-pool splat: the commitment lands on the one real pool regardless of
   `attuned_pool`, not on the always-0 Personal pool. (Phase 1 covers only the *UI* half
   — the dropdown is hidden for a ghost; the derivation half is still owed.)
6. Already-spent motes above the new cap clamp on read and do not corrupt the save.
7. ✅ No `engine/validate/` module references `attuned` or `attuned_pool` —
   `tests/test_play.py`, beside the two existing decision-0006 guards. Catches the
   `getattr("attuned")` spelling as well as the attribute.
8. ✅ An item with `attunement == 0` offers no toggle in either shell —
   `tests/test_qt_gear.py` and `tests/test_gear_catalogue.py`, both negative-controlled.
9. ✅ A fresh `ArtifactEntry` pick copies `ArtifactType.attunement` the same way it
   copies `rating`; the rename path (`set_artifact`) does too.
10. ✅ (added) The fold carries the commitment off a weapon row, off a standalone
    artifact, and — for a LINKED pair — off the gear row rather than the artifact row,
    counting one item not two. An orphaned link leaves both standing.
11. ✅ (added) The artifact editor offers the number and toggle for a standalone Wonder,
    and a pointer instead when a stat line exists. ⚠ The merged inventory row renders
    BOTH halves in one pane, so the correct assertion is *exactly one* checkbox (the
    weapon's), not zero.

⚠ **Test 9 has no real data behind it and cannot get any yet.** All 330
`ArtifactType` rows are `attunement: 0` — the backfill is a separate authoring pass —
so the test injects a nonzero row into the shared ruleset and restores it. A
`next(a for a in catalog if a.attunement > 0)` would raise StopIteration today and
start passing silently the day someone transcribes one; the helper says so.

## Estimate

**Phases 1–3, roughly a half-session of engine + model work, plus a click-through of the
Play tab in both shells and the party window.** The rules questions that were blocking
phase 2 are resolved (see above); what's left is ordinary implementation risk, not an
open rules gap.
