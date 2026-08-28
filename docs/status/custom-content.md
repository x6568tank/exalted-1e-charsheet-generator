# Custom content — user-authored Charms, Martial Arts styles and spells

**DONE 2026-07-29**, all five phases. Browser-verified by the human. The plan and
the reasoning behind each decision are in `docs/plans/custom-content.md`; this file
is the map of what exists.

⚠ **One ruling in this file was REVERSED on 2026-08-27** — "no authoring form was
needed" for gear (the 2026-08-13 section). The reversal, and why, is at the bottom
under **"Gear joined the Custom tab"**. Read that before citing the older line.

A Storyteller can author their own Charms, styles and spells in the built app, keep
them across characters, and hand a character to another player without the recipient
losing them.

## The shape of it

**A user-level library is the store; a character carries copies of what it uses.**

| Piece | Where |
|---|---|
| Library paths, read/write, id rules, embed/absorb | `exalted_builder/custom_content.py` |
| Merging the library over the book data | `rules_db._load_custom_layer`, `load_app_ruleset`, `reload_custom_layer` |
| The authoring page | `exalted_builder/ui/custom.py` (route `/custom`, and the builder's **Custom** tab) |
| The NATIVE authoring page | `exalted_builder/qt/custom.py` (the Qt shell's **Custom** tab) |
| Form ⇄ payload shuffling, the library list | `ui/view.py` — the `custom_*` presenters and `CustomRow` |
| What a character carries | `Character.custom_definitions` |
| Tests | `tests/test_custom_content.py` (pure), `tests/test_custom_ui.py` (render), `tests/test_qt_custom.py` (native) |

Library location (`custom_content.custom_data_dir`): `$EXALTED_CUSTOM_DIR`, else
`custom/` beside the saves — next to the executable in a packaged build. Gitignored.
File shapes are identical to `data/`: `charms/*.json` and `spells.json`, so anything
that can produce book data can produce homebrew.

## The rules that hold it together

1. **Book data errors stay fatal; custom data errors never are.** `load_ruleset`
   raises `RuleDataError` for `data/`; every problem in the user's library is dropped
   and reported on `RuleSet.custom_problems`. A typo in homebrew must not stop the app
   from starting.
2. **The book always wins an id collision**, and page-authored ids are forced to the
   `custom.` prefix, so shadowing printed content is impossible by construction.
3. **A custom row is dropped before the RuleSet is built** if its prerequisites cannot
   resolve, iterated to a fixpoint (dropping one row orphans its dependants). Nothing
   downstream ever sees a Charm pointing at an id that is not there. An OR group
   survives if any one member exists.
4. **A custom spell in a circle no Charm grants is dropped** — it could never be
   learned. A custom Charm may grant a circle, which is how a homebrew spell tree works.
5. **Editing keeps the id; only deleting can orphan a reference.** A deleted Charm a
   character owns shows as a ⚠ row plus an `unknown-charm` error, and comes back if
   re-created under the same name.
6. **The library wins an absorb conflict.** Opening someone's character never reverts
   your own edit of the same id.
7. **Custom content is marked wherever it is read** (human's requirement): `✎` on the
   sheet, a line on the picker's detail card, a violet double border on the Charm-tree
   node. `⚠` for an id that resolves to nothing.

## Things that came free

* **A Martial Arts style needs no schema.** The `_group_of` helper inside
  `picker.build_picker` derives the style groups from the `martial_arts:<slug>`
  category, so the style exists the moment a Charm uses it. There is deliberately no
  Styles tab.
* **Pricing needed nothing.** BP/XP cost keys off `category` + `min_ability`.
* **Combo eligibility needed nothing** — it is derived from `duration == "Instant"`
  (core p.213).
* **The engine was already resilient to unresolvable ids.** A probe over ~26 engine and
  presenter paths crashed in none of them; `validate.charm_picks` already yielded a
  dead pick with the raw id as its name. See the plan's phase 2 for what was actually
  missing.

## Two fields added for homebrew, with no printed use

Both are additive, default to nothing, and are documented in `models/rules.py`:

* **`CharmCost.health_type`** (`Damage`, optional) — which kind of health level a
  Charm spends. **Every one of the 52 printed Charms with a health cost just says
  "1 health level"**, so unset is the default and renders exactly as before. `Damage`
  moved from `character.py` to `rules.py` for this; `character.py` re-exports it.
* **`Charm.extra_min_attributes`** (`AttributeMinimum`) — several Attribute minimums,
  ANDed, each an OR over its own traits. **No 1e page gates a Charm on more than one
  Attribute**; a test pins that, and it is the thing to revisit if a splat ever does.
  Its Ability counterpart, `extra_min_abilities`, was already there (Ascendant Battle
  Visage, p.102).

Both are enforced and displayed through the same two functions as before —
`validate.charm_ability_shortfalls` and `charm_ability_requirements` — which is what
`charm_ability_shortfalls`' docstring meant by "a third gating axis has exactly one
function to change".

**Neither affects price.** The primary `min_ability` (from the category) is what
pricing and the Caste/Favoured discount read; extra requirements are pure gates, so
adding one can never make a Charm cheaper.

## Not editable in the form (deliberate)

Repeatable Charms (`repeatable_cap_ability` + `variants` — the Ox-Body shape) are
authored through the JSON pane. The form says so. Everything else on `Charm` has a
control, the splat-specific fields inside a collapsed "Advanced" section.


## Gear joined the library — 2026-08-13

**The human's call**, off the observation that the custom affordance "felt like there's
a better way". There were two problems and only one was about buttons:

1. **Catalogue browsing existed in five places** — the Buy surface plus four per-panel
   dialogs, one per catalogue. Their only remaining job was the Custom row, so they
   collapsed to a one-click blank add and Buy became the single browse.
2. **"Custom" gear meant free text on ONE character.** You invented a homebrew daiklave
   and it existed on that sheet alone, retyped for the next character, with no way to
   fix a mistake everywhere. Charms and spells had had the answer since decision 0012;
   equipment simply never got it.

`custom/weapons.json`, `armor.json`, `gear.json` and `artifacts.json` now load through
the SAME layer, with the same three contracts: **the book always wins an id collision**,
**a bad row is reported and dropped rather than fatal**, and **saves carry copies**.
`rules_db._merge_custom_gear` is the merge; `custom_content.save_gear_row` is the write.

* **"Save to my library"** sits on every gear row (`save-to-library`). No authoring form
  was needed: you tweak an item on a character and click once.
* ⚠ **A character's `Weapon` is NOT a `WeaponType`.** It carries `quantity` and
  `from_artifact` — facts about OWNING a thing, not about its design — so the payload is
  four small explicit mappings, not a model dump. The binding test loads the library
  after clicking the real button, because every direct-API test would pass against a
  button that wrote a malformed row.
* ⚠ **Library rows are tagged, not flagged.** `WeaponType` and friends are frozen and
  shared with the book data; a `custom` field on them would put a homebrew concept in
  the printed models. The Buy dialog reads the tag to mark a row "★ yours".
* ⚠ **`ArmorType.weight` is required and a character's armour row has none**, so a saved
  armour defaults to Light and the notify SAYS SO. Nothing in the engine reads armour
  weight today; the player edits the file if it matters.


## The Qt Custom tab — 2026-08-27

`qt/custom.py`, the last rail placeholder in the port. Human-clicked the day it shipped.
The settled collection layout: toolbar (New · Delete… · JSON… · Import…) · a sub-tab per
kind · a sortable table · a splitter with the authoring form in the detail pane.

⚠ **The webapp's third column became a toolbar DIALOG, not a nested tab.**
`ui/custom.py` puts library / form / JSON side by side; the collection layout has one
detail pane, and JSON in-and-out is an *action* on the row rather than a property of it.

⚠ **This is the ONE collection whose detail pane is not a projection of a selected row.**
It also holds an UNSAVED new row, because the form is where authoring happens. So
`_fill_tables` must never fall back to selecting row 0 — every other collection does
exactly that, and here it would throw away a half-written Charm on every rebuild.
`_editing == ""` is the new-row state. There is a test, negative-controlled.

⚠ **`reload()` is deliberately NOT called in the constructor.** This is the one tab whose
refresh reads the FILESYSTEM, and the shell builds all nine pages up front — calling it
there re-scans the user's homebrew library on every window and in all 300-odd Qt tests.
The shell calls `reload()` when the tab is shown. Also negative-controlled.

## Gear joined the Custom tab — 2026-08-27

**Two changes, and the second REVERSES a ruling.**

### 1. The list (a gap): gear was WRITE-ONLY

`library_gear` had **exactly one caller** — the loader — and there was **no
`delete_gear` at all**. So a row saved through "Save to my library" could be neither
seen nor removed except by hand-editing `custom/weapons.json`. Charms and spells had
list + edit + delete; gear had none of it. A third **Gear** sub-tab now lists all four
catalogues with a **Kind** column (they are one concept on screen — things you own — so
they share a list rather than splitting into four more sub-tabs).

⚠ **The gear delete warning is a DIFFERENT sentence from the Charm one, and a test pins
that they differ.** Deleting a library Charm orphans an id on every sheet that owns it;
deleting library gear orphans nothing, because saves carry inline COPIES of gear
(decision 0007). Reusing the Charm warning would frighten the user about something that
cannot happen.

### 2. The form (a REVERSAL): gear is authorable here now

⚠ **This reverses "No authoring form was needed: you tweak an item on a character and
click once" (2026-08-13, above).** The human reopened it on 2026-08-27. The reason:
the old flow made you **give a character an item in order to invent one** — Buy →
"Custom weapon" → a blank row on somebody's sheet → edit → save → delete the row you
never wanted.

**BOTH entry points stay** (the human's call). The Gear-tab button is retroactive ("I
tweaked this and want to keep it"); the Custom form is deliberate ("I want to design
one"). They cannot drift: both write through `custom_content.save_gear_row`.

The form is GENERATED from the models — `view.CUSTOM_GEAR_FIELDS` is a spec per kind and
`view.custom_gear_form` reads defaults straight off `WeaponType` / `ArmorType` /
`GearType` / `ArtifactType`. ⚠ Those models are **frozen** and shared with the book data,
so there is no instance to `setattr` down the way `qt/gear.py`'s owned-row editors do:
it is a flat dict validated on save, the Charm form's pattern.

**Three fields are deliberately absent from every form:**

* `id` — follows the name on first save, frozen after (characters reference it).
* `tags` — the loader stamps `custom` itself, and `["shield"]` on an `ArmorType` is the
  only other meaningful one. Rare enough for the JSON pane.
* ⚠ `requires_merit` (ArtifactType) — **decision 0011: no module outside
  `engine/merits.py` may name a Merit id**, and a Merit dropdown would put one in UI
  code. A test greps for exactly that.

⚠ **`source` is not uniform and was NOT made uniform.** `GearType` carries a `Source`
model, `ArtifactType` a bare string, and `WeaponType`/`ArmorType` have no source field at
all. Inventing one for the two that lack it writes a key the model rejects.

**What the form fixed on the way:**

* ⚠ **`ArmorType.weight` is REQUIRED** and the Gear-tab path cannot know it — a
  character's armour row carries no weight, so that path defaults to Light and
  apologises in its notify. The form asks.
* ⚠ **`GearType.kind` decides whether a thing is ownable at all.** `view.shop_rows`
  filters out anything that is not `"goods"`, so a row saved as a service silently never
  appears in Buy. The dropdown now says so in words.
* ⚠ **Required-with-no-default fields.** `soak_lethal` / `soak_bashing` have no default,
  so dropping them as "empty" makes the row unloadable; `ArtifactType.rating` is `ge=1`,
  so zero is not a legal blank either. `view._GEAR_REQUIRED` holds both the field list
  and what a blank form starts them at. There is a test that saves a blank form of all
  four kinds.
* `mobility_penalty` gets a signed box (floor −20): it is stored NEGATIVE, and a
  0-floored field makes a penalty impossible to enter.

Import stays disabled on the Gear sub-tab: `parse_rows` yields bare rows and a gear row
does not name WHICH of the four catalogues it belongs to. `New`'s Kind picker is what
supplies that, and it freezes once the row is saved.

## The bug underneath both — `reload_custom_layer` skipped gear

⚠ **`rules_db.reload_custom_layer` re-merged Charms and spells and silently skipped the
four gear catalogues, while `load_ruleset` merged them from the start.** So a library
weapon reached Buy only after an app **RESTART** — which is exactly what the save notify
said out loud: *"It will appear in Buy the next time the app loads its rules."* That
sentence was accurate, and had been for two weeks.

It was invisible because `library_gear` had one caller. **Building the list is what
exposed it**: the new Detail column fell back to the bare name instead of a stat line,
because the row was not in the catalogue. Fixed in `reload_custom_layer` (drop
`"custom"`-tagged rows, then re-merge), both gear pages now re-merge on save, and **the
two stale notify strings went with the fix** — that prose *was* the blocker's
description.

Two tests in `test_custom_content.py` pin both halves: a saved row appears, and a
deleted one goes. ⚠ A reload that only ADDS leaves a deleted row in the catalogue
forever, which is the shape that makes a delete look like it failed.

## Rituals joined the library — 2026-08-28

**A third id-referenced kind, and the first to arrive with its predecessors' lessons
already written down.** The chapter prints five thaumaturgic rituals and says outright
that more should be written (p.148), so the catalogue is a seed — the same argument gear
was given a day earlier. `custom/rituals.json`, `custom_content.{library,save,delete}_ritual`,
merged into `RuleSet.thaum_rituals` by `_load_custom_layer`, flagged with a new
`ThaumaturgicRitual.custom` field (a *field*, not a tag — unlike gear, this model is
ours and not shared with a frozen catalogue shape).

⚠ **A ritual now has TWO custom shapes and they are not interchangeable.**

| | Library row | Inline entry |
|---|---|---|
| What | `ThaumaturgicRitual` in the RuleSet | `RitualEntry` with `ritual_id == ""` |
| Where authored | Custom tab → Rituals | the Thaumaturgy picker's "Add ritual" row |
| Who can learn it | every character, by id, priced by level | the one character it was written on |
| Travels | inside `custom_definitions["rituals"]` | it *is* the save |

**Both entry points stay** (the human's ruling, 2026-08-28 — the same answer gear got the
day before, for the same reason: one is deliberate design, the other is "I need a ritual
mid-session").

### Three things the predecessors taught, applied without being re-learned

* **The reload path, not just the load path.** `reload_custom_layer` purges
  `custom`-flagged rituals before re-merging. The test for it was written first and
  caught the omission immediately — this is gear's bug, and it did try to happen again.
* **A write path needs a read path.** The library list, the form, and Delete all shipped
  in the same change as the saver; gear was write-only for two weeks because they did not.
* **It travels.** A library ritual is referenced BY ID, so `collect/embed/absorb_definitions`
  carry it exactly as they carry a Charm — `referenced_ritual_ids` is the walker. ⚠ Gear
  is exempt from that layer and rituals are NOT, and the difference is decision 0007: a
  save carries an inline copy of a weapon, and only an *id* for a ritual.

### `view.CUSTOM_KINDS` — one table, both shells

The two Custom pages each carried a `charm if kind == "charm" else spell` ternary at a
dozen sites. That shape treats "not a Charm" as a spell, so a third kind was a dozen
chances to be silently wrong. `view.CUSTOM_KINDS` is now the single table (form, payload,
saver, deleter, library reader, RuleSet attribute) and both shells index it; a missing key
raises where the ternary guessed. ⚠ **Gear is deliberately not in it** — its four
catalogues need a second key, and every `if kind == "gear"` branch in a shell is that
difference.

### A webapp bug the first tab-switching test found

⚠ **`ui/custom.py::_switch_kind` repainted the FORM and not the LIBRARY.** The list
filters on the active kind at render time, so switching to Spells kept the Charm rows —
under a heading that said "YOUR SPELLS". Every test until now had authored and read
within one kind. `library.refresh()` is the fix, and the ritual render test is its guard.

### Qt: address a sub-tab by NAME

`CustomPage.show_kind(kind)` exists because the tests reached for `tabs.setCurrentIndex(2)`
and Rituals went in at index 2. Three tests pointed at the wrong kind and stayed green
until an assertion happened to disagree. **The one-line lesson the project already had,
in its own file.**
