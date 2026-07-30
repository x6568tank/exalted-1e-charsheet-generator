# Custom content — user-authored Charms, Martial Arts styles and spells

**DONE 2026-07-29**, all five phases. Browser-verified by the human. The plan and
the reasoning behind each decision are in `docs/plans/custom-content.md`; this file
is the map of what exists.

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
| Form ⇄ payload shuffling, the library list | `ui/view.py` — the `custom_*` presenters and `CustomRow` |
| What a character carries | `Character.custom_definitions` |
| Tests | `tests/test_custom_content.py` (pure), `tests/test_custom_ui.py` (render) |

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
