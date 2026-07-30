# Adding a splat

Six splats are implemented. **Not one of them was data alone**, and anyone who tells you
this engine is generic enough that a new splat is "just JSON" is selling you something.
What is true is narrower and still useful:

> A splat's **content** (Charms, spells, castes, costs, budgets) is data. A splat's
> **novel subsystem** is code. The ratio has been roughly 90/10 by volume and 10/90 by
> effort.

This walkthrough is the honest version: the data you will certainly write, the questions
that tell you whether you also need engine work, what each of the six actually cost, and
the traps that have already bitten.

## Step 0 — get the pages, or stop

If you're vibecoding a custom splat, have your data ready in `images/{Splat}/` or not at all.
Otherwise, I'd still like *some* record of your new Splat's baseline -- the budgets, the 
XP-tables, Charm trees, Spells, etc etc. Before writing anything, you need 
* Character Creation, something like the summary in the splatbooks
* Traits pages -- custom backgrounds, virtues, and anything the Splat does different from base Solars
* Charms, or if it has access to other Splat's charm trees.
* XP-Advancement costs or it'll default to Solars

## Step 1 — the four data rows

Almost every splat starts with the same four edits, and a surprising amount works
immediately afterwards because the UI iterates `ruleset.exalts` rather than hardcoding
splats.

1. **`exalts.json`** — one `ExaltDefinition`. Its fields are the splat's mechanical
   identity: the Essence formula, `magic_track` (sorcery / necromancy / weaving),
   `highest_magic_circle_id`, `ox_body_charm_id`, `caste_noun` ("Caste" / "Aspect"),
   `tier` (Terrestrial / Celestial), `limit_label`, and the thaumaturgy fields.
2. **`castes.json`** — one row per caste, with its anima power and *either*
   `caste_abilities` *or* `caste_attributes` (see the Lunar note below), plus
   `required_min_abilities` if the splat prints per-caste floors.
3. **`chargen_budgets.json`** — a row keyed by exalt type. ~38 fields exist; author only
   the ones your splat changes and let the rest fall back.
4. **`costs_bonus.json` + `costs_xp.json`** — the BP and XP rows, if the splat has its
   own. Anything unstated falls back to the Solar baseline, which is usually right and
   occasionally is not: don't assume.

Then `theme.py` gets a palette (`fam` must be a real Tailwind colour family), and the
Charms go in `data/charms/*.json`.

See `content.md` for the conventions those files follow.

## Step 2 — the questions that decide whether you write code

Ask these against the Traits and Character Creation pages **before** estimating:

| Question | If yes |
|---|---|
| Are Charms keyed to something other than an Ability? | New gating axis. Lunar needed `Charm.min_attribute` and `CasteDefinition.caste_attributes` as parallels to the Ability versions |
| Does the splat lack ability-castes entirely? | Anything that lays the Ability roster out *by caste* renders blank. `view.ability_group_defs` is the one place that decides grouping -- currently falls back to Player's Guide grouping if no caste grouping |
| Does chargen spend a pool this engine has never had? | New budget field **and** new validation. Sidereal's 7 College dots; Alchemical's Charm Slots |
| Is there an intra-splat variant (Dynastic vs Outcaste, ronin)? | The `origin` axis, and possibly `upbringing` under it — both are keyed-table suffixes |
| Does it have its own magic track or circles? | New `SpellCircle` values and a `magic_track`; the circles must each be granted by a Charm |
| Is there a Limit analogue? | `limit_label`, or a whole subsystem (Sidereal Paradox, Alchemical Clarity) |
| Are there repeatable Charms beyond Ox-Body? | Its own `Character` list, cap/variant checks, lock snapshot, undo and picker panel. Display, counting and pricing come free via `validate.charm_picks` |
| Is there a chargen *package* (take these 5 Charms instead)? | A branch in `validate_chargen`, like the Immaculate path |

## Step 3 — what the six actually cost

| Splat | Data | Engine work it needed anyway |
|---|---|---|
| **Solar** | the baseline | — (it *is* the baseline) |
| **Abyssal** | 233 Charms, 23 necromancy spells, 5 renamed castes | Necromancy as a second magic track: three new circles, and a Background split by loyal/fugitive origin |
| **Dragon-Blooded** | 325 Charms, 5 Aspect books, 4 Outcaste origins | The `origin` axis, then `upbringing` beneath it; the Immaculate Order chargen package; Aspect-ability shape; per-splat Background availability |
| **Lunar** | 217 Charms, the Gift menu | **The biggest structural break**: Attribute-keyed Charms, no ability-castes at all (default War/Life/Wisdom grouping), Deadly Beastman Transformation as a second repeatable-Charm shape, a Combo mixing rule |
| **Sidereal** | 193 Charms, 5 Maiden castes | Astrological Colleges as a whole new rated subsystem with its own pool; per-caste ability floors (`required_min_abilities`); Sidereal Martial Arts caps; Paradox instead of Limit; the ronin variant |
| **Alchemical** | 121 Charms, 38 weaving protocols | Charm Slots (a fundamentally different Charm economy), Arrays, Submodules, Clarity, the vat refit module, a new Attribute budget mode (`attribute_mode: "caste_favored"`), the retainer Panoply |

The pattern: **the foundation is genuinely reusable, and every splat has had exactly one
or two things the foundation had never seen.** Budget the data as a known quantity and the
subsystem as the real project.

## Step 4 — traps that have already caught someone

1. **`highest_magic_circle_id` is the circle *barred at chargen*, not the highest
   reachable one.** Reading it the intuitive way silently lets a starting character take
   the top circle. `""` means nothing is withheld (Dragon-Blooded, whose only circle is
   Terrestrial).
2. **A keyed-table row that does not exist falls back silently.** Passing an origin on the
   `upbringing` argument, or misspelling a key, returns the general row and everything
   still "works" at the wrong prices. Always assert one distinctive number in a test.
3. **`ui.select` 500s at render if its initial value is not among its options.** Every
   splat adds options somewhere (castes, Backgrounds, Attribute panels). This is why UI
   tests go through NiceGUI's `User` harness — a unit test will never catch it.
4. **Do not walk `character.charms` yourself.** Charms live on four lists; call
   `validate.charm_picks`. Four call sites once each walked their own subset and all four
   missed Gifts the day Gifts landed.
5. **Ability-caste assumptions are load-bearing in the UI.** Lunar's empty
   `caste_abilities` rendered blank panels in two places before `ability_group_defs`
   became the single decision point.
6. **Every spell circle must be granted by some Charm** or the loader refuses the data
   set. Author the initiation Charm and the spells together.
7. **Solar fallbacks are a feature and a hazard.** Anything a splat does not state
   inherits Solar's number. That is usually correct and is occasionally a silent rules
   bug -- the XP tables needed fixing for exactly this reason.

## Step 5 — definition of done

A splat is not done when the tests pass.

1. Data authored from source, with page numbers recorded if any exist.
2. `.venv/bin/python -m pytest` green, including a splat-specific test module asserting
   the distinctive numbers (`tests/test_lunar.py` and friends are the pattern).
3. **Driven in a browser by a human** — every tab, with a real character of that splat.
   Every one of the six turned up at least one thing only clicking found.
4. `docs/status/<splat>.md` written: what was authored, which pages, and every ruling made
   along the way.
5. `CLAUDE.md` updated — the status table, the splat colour table, and the TODO.

## The parts that are genuinely free

Worth knowing so you do not budget for them:

* the editor, sheet, XP tab and party view pick up a new splat with no code change,
  because they iterate `ruleset.exalts` and read the keyed tables
* BP and XP pricing, once the rows exist
* Charm-tree rendering, including cross-category prerequisites
* Combos, Ox-Body, thaumaturgy, and the custom-content layer
* a Martial Arts style — that one really is data: a `martial_arts:<slug>` category and
  nothing else
