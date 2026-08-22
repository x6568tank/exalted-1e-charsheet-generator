# The Gear tab, the inventory and the shop — DONE, browser-verified 2026-08-13

**2,347 tests.** Browser-verified end to end on 2026-08-13 (fifteen-item checklist, one
bug found — see **What the click-through caught**).

Everything a character OWNS moved to one top-level tab, and the three surfaces that used
to edit it became one. This file owns the Gear tab, the inventory view, the Buy surface,
mundane goods and the custom gear library. The Artifact BUDGET rules stay in
`rated-artifacts.md`; decision 0017 (the two acquisition channels) stays in
`docs/decisions/`.

## Why it happened

Equipment was scattered by accident of history: weapons and armour on the **Edit** tab,
artifacts on **Advantages**, nothing anywhere for mundane goods. That split is not
cosmetic — it is what let one daiklave be entered twice and charged twice against the
p.131 budget, because its STATS lived on one tab and its BUDGET on another.

The human's first proposal was a Goods sub-tab under Advantages. Half of that was right
(equipment does not belong on Edit) and half was not: **"Advantages" is a 1e game term
meaning Backgrounds plus Merits & Flaws**, and goods are not one. Filing them there would
read as wrong to anyone who knows the book, and nesting would cost a click on a surface
used during play. It became a top-level **Gear** tab instead (human's call, 2026-08-13).

## What shipped

### The tab — `ui/gear.py`
Moved out of `ui/editor.py` (Edit is traits only now) and `ui/advantages.py` (Backgrounds
+ M&F, otherwise unchanged). Holds: the inventory, the Buy surface, the Artifacts budget
line with its Background-funded picker, and the services price list.

**The Artifact link is stated on BOTH surfaces rather than nested:** the budget header
sits with the artifacts (it is about what you own), and the **Artifact Background row on
Advantages** prints `buys N dot(s) of artifacts · M owned`.

⚠ **The cross-panel refresh hook is gone and must not come back.** `artifact_header_sync`
existed to let the Background row refresh the artifacts header while they shared a tab.
Two tabs render separately, so it had nothing to refresh; the Background note is driven
by `_sync`, where a rating change already arrives.

⚠ **Damaged Artifact stayed on Advantages.** It is a Merit, and its per-item picker
belongs with M&F even though the artifacts it points at moved. One character, two routes:
`/artifacts-advantages` (Gear) and `/artifacts-merits` (Advantages).

### The inventory — `view.inventory_rows` / `filter_inventory` / `inventory_counts`
One filterable list over all four owned-lists, per the human's model: *"your inventory,
which is Everything, but you can filter it down to certain types of goods, some of which
would overlap."*

* **A VIEW, never a storage shape.** The four lists stay typed because they carry
  different fields, and because `character.weapons` is indexed BY POSITION elsewhere (the
  dice-pool sidebar reads those indices). Unifying storage would be a save migration that
  buys nothing.
* **The filters are NOT a partition.** An artifact daiklave answers to `weapon` AND
  `artifact`, an arrow to `weapon` and `ammunition`, so the chip counts sum to more than
  the row count. A later change that "fixes" that has broken the feature.
* The artifact kind comes from `artifacts.artifact_items` — the same enumeration the
  budget reads — so a granted stat line is not tagged as a second artifact. The inventory
  and the validator cannot disagree about what is owned.
* **Each row expands to the editor for ITS kind**, reached through `InventoryRow.list_name`
  / `.index`. The three per-kind panels are gone: an inventory listing everything, beside
  panels editing the same objects, was four surfaces for one job — and only the list can
  show a daiklave as both weapon and artifact.
* **An artifact and the stat line `grant_gear` stamped for it are ONE ROW** (2026-08-14,
  the human on the BOTC click-through: two peer rows for one Crimson Bow *"feels odd, and
  a little obtuse"*). **Browser-verified 2026-08-14** against real catalogue content — the
  Wavecleaver Daiklaive and Lightning Ballista on the weapon side, and the **Armor of
  Aquatic Puissance** on the armour side, whose `mobility_penalty` renders as the printed
  **-2** (the sign that has bitten twice). ⚠ The armour half had **no test** until
  preflight caught it on the day the Armor of Aquatic Puissance made it a live shape —
  the merge loops over both lists, but every test written for it had used a weapon.
  The artifact owns the row — it is the object; the gear row is what
  it DOES — and the stat line rides in `detail` with `InventoryRow.linked_list_name` /
  `.linked_index` as a SECOND route back. Three things this had to preserve, each with a
  test:
  - **the merged row keeps BOTH filter kinds**, so a daiklave is still under Weapons.
    Merging two rows must not cost the object a filter it used to appear under;
  - **the expansion renders BOTH editors** (the artifact's, then the gear half under a
    "Stat line" heading). The stat line has no row of its own any more, so a panel that
    ignored `linked_index` would make it silently uneditable — the view would be right
    and the surface wrong, which is why the binding test names `build_gear` and not
    `inventory_rows`;
  - **an ORPHANED link does not merge** (`from_artifact` pointing at a renamed or deleted
    artifact). The gear row stands alone AND counts as an artifact on its own, matching
    `artifact_items` — a merge that hid it would make it free.
  ⚠ The merge keys on `from_artifact`, **never on the name**: a hand-entered same-named
  weapon is a second object that the budget charges for, and hiding it behind the first
  would contradict the validator.
  ⚠ Display-only. The typed lists are untouched, so `character.weapons` keeps the
  positional indices the dice-pool sidebar reads.

### Buy — one shop over every priced catalogue
Replaces four per-panel dialogs ("Add weapon" / "Add armor" / "Add goods" / artifacts),
which were four shops. The kind rides in the row KEY so one dialog appends to four lists.

* **Type filter chips**, from `group_of` (new optional arg on the shared
  `catalogue_dialog`). A dialog spanning four catalogues is a wall of names otherwise,
  and the text box only helps someone who already knows what to type.
* **"Custom weapon / armour / goods" rows live IN the dialog** (`custom_kinds`), which is
  what let the last per-panel button go: a shop CAN know which list a blank row belongs
  in once you say which kind you are making.
* **Services are never offered** — the ruling holds at the offer, not just in the data.
* **Artifacts are sold ONLY post-lock** (decision 0017), so the shop enforces what the
  validator does instead of letting a player walk into its bar.

### Mundane goods — `data/gear.json`, `GearType`, `GearEntry`
**56 rows**: 43 off Manacle and Coin p.123 and 13 Everyday Wonders off p.125, split
`goods` (ownable, 29) and `service` (reference, 27).

**Human's ruling 2026-08-13: services are a REFERENCE PRICE LIST, not inventory.** Upkeep,
events, commissions and rentals are priced and never owned — a character does not carry a
month of stabling in her pack, and modelling one as an inventory row would be the tracker
pretending to be a chronicle simulator (the same reasoning that keeps training times out).

**Human's ruling: there is no SELL action.** Core p.145 says possessions can be sold
"though doing so may take some time" and prints no rate, and the buy-side dot-drop is
already not applied automatically. Deleting a row is selling.

⚠ **"Erect a Manse" is a service with a note.** It is printed on the page, but the thing
it buys is a BACKGROUND; authoring it as goods would put a Manse in someone's backpack.

⚠ **`GearType.cash` is reference text, never arithmetic.** M&C p.122 says outright that
the Resources ladder is not linear and converting it is a Storyteller judgement, so the
printed jade/silver equivalents are stored verbatim and nothing computes from them.

### The custom gear library
Gear joined the `custom/` library that Charms and spells have had since decision 0012 —
`custom/weapons.json`, `armor.json`, `gear.json`, `artifacts.json`, merged by
`rules_db._merge_custom_gear`, written by `custom_content.save_gear_row`. Full record in
`docs/status/custom-content.md`. **"Save to my library"** sits on every gear row; no
authoring form was needed.

## What the work turned up on the way

* **`GearType.cash` had ZERO read sites when the price list first shipped.** It printed a
  name and a dot column, so a PRICE list showed no prices, and the human called it
  useless — correctly. The house bug, in same-day code, by the same author who had
  written the preflight note about it that morning.
* **A bare dot column is unreadable.** `•••` beside a good was asked about in the browser:
  every other dot column on the sheet is a rated TRAIT and this one is a PRICE. Now
  `Res •••` with a tooltip.
* **Mountain Folk Resources were capped without their compensation.** `max_rating: 3` was
  authored; CH6's "effective rating equal to dots + 2" was not, so nothing above
  Resources ••• could be bought by the richest Jadeborn in Creation. A cap with its
  compensation missing is worse than neither. Now `BackgroundRule.effective_bonus` /
  `effective_floor` (the page also floors an unbought Background at •• Enlightened / •
  Unenlightened), read through `validate.effective_background_rating`.
  ⚠ `gear_affordability` now takes the RULESET as a REQUIRED first argument, deliberately
  not the optional-ruleset shape used elsewhere: that shape trades a TypeError for a
  silently wrong answer, and this function's wrong answer is an invisible "you cannot buy
  that".

## What the click-through caught (2026-08-13)

**The price list rendered EMPTY while every test passed.** Its `ui.scroll_area` carried
`flex-1 min-h-0` AND an inline height: `flex: 1 1 0%` collapsed it to a zero basis and
`min-h-0` removed the content floor that would have saved it. The rows were in the DOM
the whole time, which is why `should_see` was happy and why no render test could have
caught it.

⚠ **`flex-1 min-h-0` is correct only when the PARENT is a fixed-height flex column** —
true of the catalogue dialog's `h-[85vh]` card, where the recipe was copied from, false of
a panel card with no height. `test_the_price_lists_scroll_area_keeps_a_definite_height` is
a source-level guard, since CSS is invisible to the harness.

## Traps for the next session

* ⚠ **A helper defined inside `body()` but CALLED from a row editor at `build_gear` scope
  is a NameError at call time — and NiceGUI logs it and renders an EMPTY PANEL rather
  than crashing.** It presents as "the tab lost its content", not as an error. Hit three
  times during the fold; `armor_names`, `stat_num`, `_armor_summary`, `art_catalog` and
  `_artifacts_header` all had to be hoisted. **If a panel goes blank after a move, look
  for a closure over a name that stayed behind.**
* ⚠ **A negative control must name something only the deleted thing said.** Asserting
  `"Goods" not in labels` failed against working code, because "Goods" survives as a row
  tag and a filter chip. The armour panel's full title `"Armor (sets soak)"` is the
  probe that works.
* ⚠ **Scope a dialog assertion to the dialog.** The Gear tab lists the same item names in
  the inventory behind an open dialog, so `should_not_see` after a filter click asserts
  against the wrong widget and passes regardless. Use the dialog's `descendants()`, or
  the `inv-row` marker for inventory rows.
* ⚠ **Probe an artifact rule with an artifact that is not ALSO gear.** Twenty catalogue
  artifacts are weapons or armour too (Daiklave, Grand Daiklave, Myrmidon Carapace) and
  are offered at chargen as GEAR whatever the artifact rule says — correctly, since such
  a row carries `artifact_rating` and the budget counts it either way. A test probing
  with "Grand Daiklave" asserted nothing; use the Dragon Tear Tiara.

## The rules left this file's widget on 2026-08-21 (the Qt port, milestone 4)

`engine/gear_actions.py` now owns every mutation the tab makes, and `ui/view.py` every
line of text it prints. `ui/gear.py` is 947 → 650 lines of layout. The reason is the
port — two shells drive these edits now — but the split is the one decision 0002 asks
for regardless. What moved:

| To | What |
|---|---|
| `engine/gear_actions.py` | `add_row`/`remove_row`/`remove_artifact`, `set_weapon`/`set_armor`, `grant_gear`, `add_artifact`/`set_artifact`, `acquisition_for`, `buy` (the shop key dispatch), `library_payload`/`reserved_ids` |
| `ui/view.py` | `artifacts_header` + `artifacts_bought_note` + `artifacts_also_counted`, `inventory_heading`/`inventory_filter_label`/`inventory_row_tags`, `shop_rows` + `ShopRow` + `shop_custom_kinds`, `service_rows`, and `catalog_weapon_summary`/`catalog_armor_summary`/`gear_cost_note` lifted out of `ui/catalogue.py` (which re-exports them) |

⚠ The `ui/catalogue.py` → `view.py` lift is not tidying. `qt/` must never import
`ui/catalogue.py` because it imports nicegui, and "nothing outside `ui/` imports nicegui"
is the invariant the whole port rests on.

### ⚠ The bug the extraction found — `from_artifact`'s sibling

`set_weapon`/`set_armor` REPLACE the row with a catalogue copy, so anything not in the
copy is lost. The hand-written carry-across list held `from_artifact` — because the
comment three lines above it warned about exactly that — and **never knew `acquired`
existed**. `artifacts.budgeted_items` reads `acquired`, so re-picking a cash-bought
artifact weapon's own name from its own dropdown turned it back into a Background-funded
one and charged the p.131 budget for something Resources had paid for:

```
budgeted before re-pick: []
budgeted after  re-pick: ['Daiklave']
```

The fix is **not** "add `acquired` to the list". `_owned_fields` is the complement of
`_catalogue_stats`, both derived from the two pydantic models, so the fields a copy
leaves out cannot be the fields nobody thought of. **When code copies one model into
another field by field, derive the field set from the models.**

Both halves are tested in `tests/test_gear_actions.py`, armour included — ⚠ the armour
half of this merge went untested once before, because every test written for it had used
a weapon.

## Open questions for the human

None outstanding. The three rulings this work needed — services as reference, no sell
action, and artifacts purchasable only in play — were all given and are recorded above
and in decision 0017.
