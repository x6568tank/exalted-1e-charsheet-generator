# Plan — user-authored custom Charms / Martial Arts / Spells

Status: **PLANNED, not started** (2026-07-29). Scheduled BEFORE the six non-Exalt
splats, at the human's request.

Goal: a Storyteller using the built app can author their own Charms, Martial Arts
styles and spells, keep them across characters, and hand a character file to
someone else without the recipient losing them.

## Storage model (decided 2026-07-29)

**A user-level custom library is the store; the definitions a character actually
uses are ALSO embedded in its save file and re-absorbed on load.**

* Library — `custom/charms/*.json`, `custom/spells.json`, in the same shapes as
  `data/`. Same files `tools/md_to_charms.py` already emits, so its output can be
  dropped straight in.
* Location — `custom_data_dir()`: `<exe dir>/custom/` in a PyInstaller build,
  `Path.cwd()/custom/` in dev, overridable by `$EXALTED_CUSTOM_DIR` (tests pass an
  explicit path). Mirrors `persistence.default_save_dir()`, which already puts
  saves beside the executable — no new dependency.
* Portability — on save, the edge walks the character's referenced ids
  (`charms`, `spells`, `combos`, `retainer_charms`, `granted_charms`, plus the
  prerequisite closure of those Charms), pulls each custom definition out of the
  library, and writes them into the save. On load, any embedded definition whose
  id is NOT in the library is absorbed into it and the user is told. Same id,
  different content: the library wins, and the user is told.

Rejected: library-only (a save handed to another machine carries dangling ids)
and character-embedded-only (no reusable library, and every engine call site
would need a per-character merged RuleSet).

## Why this is cheap

1. All ten UI pages already call `rules_db.load_ruleset(_DATA_DIR)`. The overlay
   goes *inside* `load_ruleset`, so no call site changes.
2. Custom Martial Arts styles need no schema at all. `picker.py:334` derives the
   style groups from the `martial_arts:<style>` category string; a new style is a
   new category string and the picker groups it automatically.
3. BP/XP pricing keys off `category` + `min_ability`, which a custom Charm has
   like any other. No pricing work.
4. Inline user-authored content has a precedent from thaumaturgy —
   `RitualEntry`/`FormulaEntry` (`character.py:111`, `:140`) already use
   `id == "" ⇒ described inline`, as custom weapons/armor do.

## Architecture constraints this must respect

* **`models/character.py` must not import the rules models.** So the embedded
  payload is `Character.custom_definitions: dict[str, list[dict]]` — an opaque
  JSON blob the character carries. It is validated into `Charm`/`Spell` at the
  edge (`rules_db` / the new `custom_content.py`), never by the character model.
* **Book data errors must stay fatal; custom data errors must not.**
  `load_ruleset` accumulates into one `RuleDataError` and raises
  (`rules_db.py:322`). One typo in a user-authored file must never brick the app:
  the offending row is dropped and reported, and the app still loads.
* Custom rows are still *rules* data — frozen, id-referenced, read-only to the
  engine. Nothing about the pure-engine boundary changes.

## Phases

### 1. Loader overlay (~½ day)

* `custom: bool = False` on `Charm` and `Spell` (both frozen; a default keeps
  every existing file valid). The loader stamps `True` on custom rows; the UI
  uses it for a badge and to decide what is editable.
* `load_ruleset(data_dir, custom_dir=None)`; defaults to `custom_data_dir()` when
  that exists.
* Custom problems go to a separate list, never into `RuleDataError`. Surfaced as
  `RuleSet.custom_problems: list[str]` for a UI warning banner.
* Book first, then custom. A custom id colliding with a book id is rejected with
  a message (book wins) rather than tripping `_index`'s duplicate error.
* Referential checks run over the merged set, but a failure caused by a custom row
  drops that row instead of raising. Dropping a Charm can orphan another custom
  Charm's prerequisite, so iterate to a fixpoint.
* `_check_sorcery_reachable` stays enforced for custom spells — a spell in a
  circle no Charm grants is unlearnable, so drop it and say so.

### 2. Missing-id resilience — DONE

**The premise was wrong and no placeholder was needed.** A probe that held
unresolvable Charm/spell ids through ~26 engine and presenter paths (validate,
derive, the BP breakdown, the XP audit, every `build_*` presenter, the Alchemical
slot/Array/refit paths) crashed in NONE of them. The twelve `ruleset.charms[...]`
sites read as unguarded are all fed by ids that were resolved upstream, and
`validate.charm_picks` already yields an unresolvable pick with `name` set to the
raw id — the canonical-enumeration work had already covered this. `check_references`
already emitted `unknown-charm`/`unknown-spell` errors too.

What was actually missing, and shipped instead:

* `check_references` only walked `character.charms`. It now also walks
  `retainer_charms` (the Alchemical Panoply) and `granted_charms`, each with a
  message saying which list the dead id sits on.
* `missing` and `custom` flags on `CharmRow`/`SpellRow`, `custom` on
  `CharmDetail`/`SpellDetail`/`SpellPickRow`/`CharmNode` — the presenters knew the
  difference but had no way to say so.
* The badge itself (answer to open question 1: yes): `✎` violet for homebrew and
  `⚠` red for a dead id on the sheet (`app.py:_content_mark`), a full-width line on
  the picker's detail card, and a violet double border on the Charm-tree node.
* `picker._node_classes` — the Cytoscape class list had two copies, one for the
  initial build and one for the repaint, and the repaint had already dropped
  `external` once. Both now call one helper.
* A blanket regression test that walks every presenter with a dead id, so the
  resilience that already existed cannot quietly regress.

NOT yet browser-verified: the badge renders through the presenters under test, but
nobody has looked at it. Click it through at the end of phase 3, when there is real
homebrew to look at.

### 3. Author UI v1 (~1–1.5 days)

New `exalted_builder/ui/custom.py`, page `/custom`, linked from the builder chrome
and the picker. Tabs: Charms / Spells / Styles. Zero game logic — it writes JSON
and reloads the RuleSet.

* Charm form v1: name, id (auto-slugged, forced `custom.` prefix so a collision
  with a book id is impossible), category (abilities + known MA styles +
  "new style…"), `exalt_type`, `type`, cost, `min_ability`, `min_essence`,
  prerequisites (multi-select over the merged Charm set), description, source.
* Picking "new style…" and typing a name writes `martial_arts:<slug>` as the
  category — that is the whole custom-style feature.
* Spell form: name, circle (one of the eight existing circles), cost, description.
* Editing keeps the id, so characters that own the Charm never break. Delete
  refuses while the open character references it, and warns otherwise.

### 4. Embed-on-save / absorb-on-load — DONE

`Character.custom_definitions: dict[str, list[dict]]` (opaque dicts — the character
models must not import the rules catalogue), plus in `custom_content`:
`referenced_ids`, `collect_definitions`, `embed_definitions`, `absorb_definitions`.

Both ends hang off **`persistence`**, not the UI: there are 22 save/load call sites
across `ui/`, and the one that got missed would silently drop homebrew.
`persistence` imports `custom_content` lazily, because `custom_content` imports it
back for `atomic_write`/`default_save_dir` (the `builder`→`ui.gm` precedent).

Decisions made while building:

* **The walk covers every list that can hold a Charm** — `charms`,
  `retainer_charms` (Panoply), `granted_charms`, Combo and Array membership,
  `spells`, and the **chargen snapshot**, whose ids the XP audit re-prices against.
* **Prerequisite closure**, because a homebrew Charm's prerequisite may itself be
  homebrew; embedding the leaf alone would land as a row the loader drops.
* **Re-derived from the library on every save**, so an edit travels and a dropped
  Charm's definition goes with it — but a definition the LOCAL library does not have
  is kept, which is the "someone else's character, opened and re-saved here" case.
* **The library always wins an absorb conflict**: opening a character never reverts
  the recipient's own edit of the same id. Rows are absorbed WITHOUT validation — a
  malformed one is the loader's to report, and refusing it here would throw away the
  only copy of a Charm the character references.
* Party files get the same treatment per member, or the GM's format would be the one
  save shape that loses homebrew.
* `builder._apply_loaded` (the single funnel for both the file and upload paths)
  passes `absorb_custom=False` and absorbs itself, so it can report
  "Imported N homebrew definition(s) from this save" and refresh the live rule set.

### 5. Advanced fields + docs (~1 day)

`element`, `open_to_all`, `open_to_tiers`, `grants_circle`, `min_attribute`,
`extra_min_abilities`, `installation_cost` (Alchemical), Combo eligibility.
Then CLAUDE.md + `docs/status/custom-content.md`.

## Tests (`tests/test_custom_content.py`)

Overlay merge; book-wins collision; malformed custom JSON is non-fatal; dangling
prerequisite dropped and the fixpoint reached; unreachable custom spell circle
dropped; embed → wipe library → load → absorbed round-trip; placeholder renders
instead of KeyError. UI smoke through the NiceGUI `User` harness, one route per
test.

## Open questions for the human (rules authority)

1. Should a custom Charm be badged as non-canon on the character sheet and in the
   GM party view? (Assumption: yes, a small badge.)
2. May a custom Charm count toward the chargen caste/favored Charm minimum and be
   used in Combos? (Assumption: yes — it is an ordinary Charm of its category.)
3. Custom spells: is inventing a NEW circle ever wanted, or is picking one of the
   eight printed circles enough? (Assumption: the eight are enough.)
