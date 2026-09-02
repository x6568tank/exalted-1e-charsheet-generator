# Artifact attunement — commit the motes

**Status: PLANNED, not started (2026-09-02).** Human asked for the plan only.

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
only `name`, `rating`, `note`, `acquired`. The standalone-artifact list is therefore
**out of scope for phase 1**; see the open questions.

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

**2. The tracker's pool maximum shrinks** (human, 2026-09-02). `peripheral_max` in
`build_play_view` comes down by the committed total, and the Play tab's boxes literally
get shorter. Rejected: the Alchemical installation-motes model (`ui/view.py:2385,2415`),
which displays a *fit* against `derive.charm_installation_pool` without subtracting —
correct there because installation is a chargen-legality check, wrong here because
attunement is a live capacity.

## Open questions — BLOCKING, need a page

Do not start phase 2 without answers. **I have no source for any of these and will not
supply one** — the 2e attunement rules are the exact shape of trap decision 0001 exists
for.

1. **Which pool does a committed attunement draw from — Personal, Peripheral, or the
   player's choice?** This decides whether `build_play_view` reduces one field or two,
   and whether the commitment needs its own stored allocation. The plan below assumes
   *Peripheral*, and **that assumption is unverified**.
2. **What happens on a merged pool?** `essence_pool_is_merged` (ghosts, Beacon of Power)
   leaves Personal 0 by rule; `derive.charm_installation_pool` already has the
   ask-here-not-at-the-call-site shape for exactly this, and the attunement code should
   borrow it rather than unpack `essence_pools`.
3. **Does the printed attunement number vary with the wielder** (magical material,
   Exalt type, anything else)? `derive.effective_armor` already re-derives armour stats
   per wielder for material bonuses. If attunement is one of those, the committed total
   must read the *effective* item, not the stored row — and phase 2's arithmetic changes.
4. **Should `ArtifactEntry` gain an attunement number?** That is not code work: it is
   authoring a value onto up to 330 catalogue rows from the pages, and the answer may
   simply be no.

## The work

### Phase 1 — the flag and the toggle (small)

* `models/character.py` — `attuned: bool = False` on `Weapon` and `Armor`, with a
  comment saying it is the PLAYER's statement and that no `validate/` module may read it.
* **`engine/gear_actions.py` needs nothing.** `_owned_fields` (line 40) derives the
  player's fields as the *complement* of the catalogue's, precisely so a new one is
  carried across a catalogue re-pick without anyone remembering to list it. `attuned`
  is absent from `WeaponType`/`ArmorType`, so it survives a re-pick for free — but
  **assert that in a test**, because the whole reason that function is computed is that
  the hand-written version silently dropped `acquired` for weeks.
* `library_payload` (line 303) must **not** gain it — that function's docstring already
  says ownership state does not belong in a catalogue, and `attuned` is ownership state
  twice over.
* `ui/gear.py` — a checkbox in `_weapon_editor` / `_armor_editor`, beside the `Attune`
  spin box, **rendered only when `attunement > 0`**.
* `qt/gear.py` — the same, but `_WEAPON_STATS` / `_ARMOR_STATS` are `(field, label,
  signed)` triples driving spin boxes and a bool does not fit that table. Add the
  checkbox outside the table rather than widening the triple for one field.

### Phase 2 — the derivation (small, once the questions are answered)

* `engine/derive.py` — `committed_attunement(ruleset, character) -> int`, summing
  `attunement` over weapons and armour with `attuned` set. ⚠ Weapons carry `quantity`;
  it is a count with no engine reader (decision 0008) and **must not multiply the
  commitment** — twenty attuned arrows are not twenty attunements. Answer question 3
  before choosing stored-vs-effective item.
* `ui/view.py:3116` `build_play_view` — subtract from `peripheral_max` (pending Q1),
  floored at 0. `PlayView` gains a `committed: int` so the label can say *why* the pool
  is short; "Peripheral 4/10" with no explanation reads as a bug, the same reasoning
  that put `essence_single_pool` on the view.
* **The re-clamp.** `engine/play.py:set_motes` clamps to a cap *passed in by the caller*.
  Attuning something while motes are already spent leaves a stored
  `motes_peripheral_spent` above the new maximum. Clamp on read in `build_play_view`, not
  by mutating the save from a derivation.

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
  subtraction from Personal silently does nothing for ghosts and Beacon of Power holders.

## Tests owed

1. `attuned` survives a catalogue re-pick (`gear_actions.set_weapon` on the row's own name).
2. Committed total ignores unattuned items, and ignores `quantity`.
3. `build_play_view` reduces the pool; **negative control** — clear the flag, pool returns.
4. Merged-pool splat: the commitment lands somewhere real, not on the 0 Personal pool.
5. Already-spent motes above the new cap clamp on read and do not corrupt the save.
6. No `engine/validate/` module references `attuned`.
7. An item with `attunement == 0` offers no toggle in either shell.

## Estimate

**Phases 1–3, roughly a half-session of engine + model work, plus a click-through of the
Play tab in both shells and the party window.** The blocking rules questions are the real
cost: without them phase 2 is guesswork, and guessing is how a 2e number gets into a 1e
build.
