# The corebook Wonders chapter — DONE 2026-08-12

**Browser-verified 2026-08-12.** Suite **2,285**. The Hearthstone ALLOWANCE — the S&S
pp.66-67 rules that came after the first click-through — is written up at the bottom of
this file and is browser-verified too.

The corebook's own artifacts were the ones a player was most likely to reach for and
the ones the catalogue did not have. `data/artifacts.json` held **8** core entries, all
of them authored from page images; the other ~16, plus the ten Hearthstones, were
blocked. The block was not missing pages.

## What actually blocked it: one undecoded font

`images/_extracted/Exalted Core.md` was extracted with `tools/glyph_maps/exalted-core.json`,
which recorded **twelve of the corebook's thirteen subsetted fonts as solved and the
thirteenth — `ZTR41D0.tmp,Bold`, 2.5% of the book — as UNSOLVED**, every glyph left as
U+FFFD. That face draws the **entry names and the table column heads**. The prose under
each entry read perfectly; the name above it was a row of boxes. So the pages were on
disk and readable and the catalogue still could not be authored from them, and the eight
entries that DID exist were the ones someone had read off a page image.

**The lesson generalises past this book:** a source can be 97% decoded and still 100%
blocked for authoring, if the missing 3% is the identifying half. Measure a decode by
whether the thing you need to author is legible, not by the character-level percentage.

### How it was solved (2026-08-12)

`tools/solve_cid_bands.py` anchors each font on English — the commonest 3-letter word
being "the". This face sets NAMES and column heads, so that anchor never existed and the
solver correctly reported UNSOLVED rather than guessing. It was solved by **crib**
instead: the five magical-material run-in heads on p.338 (`Orichalcum:` `Moonsilver:`
`Jade:` `Starmetal:` `Soulsteel:`) pin all 26 lowercase letters, nine capitals and the
colon between them in one go.

Two structural findings, both now in the glyph map's `why_split_bands`:

* **The subset has no `Q`.** A dropped glyph shifts every id after it, so `A-P` solve at
  one constant and `R-Z` at another. Decoding with a single constant does not fail
  loudly — it yields fluent nonsense (`Qoleaxe` on p.328, or `Sesources` in the weapon
  table header). This is the same failure that made the per-font fix necessary in the
  first place, one level down.
* Punctuation splits the same way: `, - . / 0-9 :` at one constant, `( ) *` at another.

`ArmorType`-style band lists are now supported: **`upper` and `punct` in a glyph map may
be a LIST of `[k, lo_ord, hi_ord]` sub-bands** instead of a single int
(`extract_born_digital.make_font_decoder`). Every previously authored font keeps the int
form and behaves identically.

Re-extracting the whole book: **1,383,330 chars, 3.00% → 0.63% undecoded.** Three glyphs
of this face remain unmapped (cids 4, 5, 6 — a quote pair with one occurrence each, and
a separator ornament); none carries a game value and they stay U+FFFD rather than get a
plausible guess.

## What was authored

`data/artifacts.json`: **196 → 222**.

**Ten Hearthstones** (pp.338-340, two per element), tagged `hearthstone`:
Windhands Gemstone ••• / Gem of Sapphire and Emerald ••••• (Air), Salt-Gem of the
Spirit's Eye •• / Gem of Adamant Skin •••• (Earth), Gem of the Calm Heart • / Jewel of
Hungry Fire •• (Fire), The Freedom Stone ••• / Seacalm Gemstone •••• (Water), Stone of
Healing • / Gem of Incomparable Wellness ••••• (Wood).

**Sixteen Greater Wonders** (pp.340-346) as standalone catalogue entries: Daiklave,
Grand Daiklave, Reaver Daiklave, Dire Lance, Goremaul, Grimcleaver, Serpent-Sting Staff,
Smashfist, Short Powerbow, Long Powerbow, Lightning Torment Hatchets, and the five
artifact armours (Breastplate, Reinforced Buff Jacket, Reinforced Breastplate,
Articulated Plate, Superheavy Plate). All of these already existed as **gear rows** with
an `artifact_rating`; they were simply absent from the artifact catalogue, so a player
could add a daiklave as a weapon but could not find one when browsing artifacts.
`test_the_corebook_wonders_are_in_the_catalogue` asserts the catalogue rating equals the
gear row's `artifact_rating` for all fifteen, so the two copies of each printed number
cannot drift.

## ⚠ A Hearthstone is not bought with Artifact

**The trap this area printed.** A Hearthstone is a rated object and belongs in the rated
catalogue, but **its dots are the rating of the MANSE that grew it** — the stone comes
with the Manse Background, not with Artifact dots. Dropping the ten stones into
`data/artifacts.json` unqualified would have made them indistinguishable from artifacts
at the one surface that spends the budget: picking one appends an `ArtifactEntry` and
charges the E:Ab p.131 combined-rating budget for something Artifact never bought. The
mis-charge is silent and looks exactly like a legal purchase.

The fix is a field, not an allowlist: **`ArtifactType.background`** (`"artifact"` |
`"manse"`, defaulting to `"artifact"` so every entry authored before it keeps its old
behaviour). `engine.artifacts.purchasable_with_artifact` / `.hearthstones` are the ONE
split, and both artifact-spending surfaces — the row's name combobox and its catalogue
dialog — read it. `test_hearthstones_are_never_offered_as_artifact_purchases` pins it at
the surface that would commit the charge, not only in the engine.

The stones' home is the **Manse Background row**, which grows a diamond-icon picker. It
deliberately creates no `ArtifactEntry`.

⚠ **Both halves of that sentence were superseded the same day** — see *Hearthstone
allowances* at the bottom of this file. The picker was gated by `_is_manse` (a substring
test on the row's free-text name) and a pick appended the stone's NAME to the row's note.
The gate is now `artifacts.grows_hearthstones`, reading the data, and the pick lands in
`BackgroundEntry.hearthstones` with its rating.

## The re-sweep, and what it found

With names decoded book-wide, every display-face run in the PDF (579 distinct) was
diffed against the loaded ruleset. Almost all of the 450 unmatched were chapter headers,
glossary terms and table column heads; the pp.314-318 beasts were all already in
`data/adversaries.json`. Three real gaps came out of it, all shipped the same day:

| Gap | Pages | Shape |
|---|---|---|
| **Arrows** — Broadhead, Fowling, Frog Crotch, Target | 330 | `weapons.json` rows tagged `ammunition` |
| **Helms** — Pot Helm, Masked Helm, Slotted Helmet | 334-335 | `armor.json` rows tagged `helm` |
| **The ten sample Virtue Flaws** | 131-133 | new `data/virtue_flaws.json` + `VirtueFlawType` |

### Arrows: in 1e the arrow IS the bow's damage

Every bow row in `weapons.json` carries **no damage value at all**, and that was correct
and incomplete at the same time: p.330 puts the damage on the arrow ("broadhead arrows
do the firing character's Strength + 2 as their base damage"). Same arithmetic `damage`
already means everywhere else, and `damage_type` already carries the L/B that Fowling
needs. Frog Crotch's doubled lethal soak and Target's halved lethal soak are `notes`, as
printed text — decision 0008 keeps damage out of this build and 0016 did not move that.

**Arrows are FREE** (human, rules authority, 2026-08-12): no arrow has a printed
Resources cost in the corebook or Manacle and Coin — the only priced ammunition is
Southern Fire Arrows at Resources •• — and 2e prints none either. `resources_cost` is
left unset; a specific type that states one gets one.

**Ammunition is stackable**: `Weapon.quantity` (default 1, ge=1), a count and nothing
more — no engine reads it, because nothing derives an attack. `set_weapon` carries it
across a catalogue pick, which replaces the row wholesale.

### Helms carry no stats, on purpose

p.334 states outright that helmets "are largely a cosmetic matter — they're a substitute
for a striking hair style" and that **"all helms are considered mechanically
identical."** All three ship with zero soak, zero mobility penalty and zero fatigue, and
`test_weapon_and_armor_catalogs_load` asserts that, so a later pass cannot "fix" them by
inventing a soak. The optional gritty-game rule (a called shot at a bare head, -1
success) is recorded in the Pot Helm's notes. `RuleSet.helms()` splits them out and
`body_armor()` now excludes helms as well as shields.

### Virtue Flaws: a dropdown, not a constraint

`Character.virtue_flaw` was `virtue` + free-text `description`, so the player typed what
the book prints as a named list. `data/virtue_flaws.json` holds the ten samples with
their **Limit Break Conditions** as their own field (the half consulted at the table).
The editor's dropdown is **filtered to the flawed Virtue** — p.131 requires a Flaw to
belong to a Virtue rated 3 or more, and the Virtue is already chosen in the select above
it, so offering a Compassion Flaw beside a flawed Valor would be offering an illegal
pick. Picking one **copies** the printed text into the free-text field (decision 0007:
ids for invariant content, inline copies for variable) — the book says in as many words
that these are not the only Flaws an Exalt might develop, and a stored id would make an
edited Flaw claim to be the printed one.

⚠ **A printed oddity, transcribed not corrected:** Deliberate Cruelty is a CONVICTION
Flaw whose duration keys off **Temperance** ("for a number of days after her Limit
Breaks equal to the character's Temperance"), where every other Flaw keys to its own
Virtue. It is in the data exactly as printed with a `notes` field saying so. **The rules
authority has not ruled on whether it is an erratum** — do not silently align it.

## The other two UI pieces

* **Catalogue icons.** `ui/catalogue.icon_for(tags, default)` derives a Material icon
  from the tags the data already carries — nothing new authored per entry — and
  `catalogue_dialog` takes `icons=` / `default_icon=`. Wired into weapons, armour,
  artifacts and Hearthstones. Order matters in `_ICON_BY_TAG`: the first match wins, so
  `ammunition` precedes `archery` (an arrow must not read as a bow) and the Hearthstone
  ELEMENTS precede `hearthstone` (every stone carries both tags and the element is the
  more useful half). An icon is presentation only and derived at render time — it can
  never be edited into a lie, which is this dialog's own scar (see
  `catalogue-dialogs.md`).
* **The nocked arrow on the Play tab.** `build_pool_sidebar` takes `arrow_index` and
  returns `arrows` + `arrow_note`. It is REFERENCE: an arrow contributes no dice (p.330
  gives arrows a base damage and a soak clause and **no accuracy**), so the control sits
  with the other controls rather than inside a pool row, and prints "Damage only — an
  arrow adds no dice to the attack pool." `test_a_nocked_arrow_shows_its_damage_and_adds_no_dice`
  asserts every Archery row is byte-identical before and after nocking one.
  ⚠ `PoolSidebarView.weapons` changed from `list[str]` to `list[tuple[int, str]]`: the
  list is now filtered (ammunition is not something you attack with) and its position
  was being used as the index into `character.weapons`, so a filtered list numbered by
  position would have attacked with the wrong weapon.

## Files

* `tools/glyph_maps/exalted-core.json` — the solved face, the crib, the split-band note
* `tools/extract_born_digital.py` — `make_font_decoder` accepts band lists
* `images/_extracted/Exalted Core.md` — re-extracted (gitignored)
* `data/artifacts.json` (222), `data/weapons.json` (102), `data/armor.json` (27),
  `data/virtue_flaws.json` (10, new)
* `models/rules.py` — `ArtifactType.background`, `VirtueFlawType`,
  `RuleSet.virtue_flaw_catalog`, `RuleSet.helms()`
* `models/character.py` — `Weapon.quantity`
* `engine/artifacts.py` — `MANSE_BACKGROUND`, `purchasable_with_artifact`, `hearthstones`
* `ui/catalogue.py` (icons), `ui/advantages.py` (filtered artifact surfaces, Manse
  picker), `ui/editor.py` (quantity, Virtue Flaw dropdown), `ui/view.py` + `ui/play.py`
  (nocked arrow)

---

# Hearthstone allowances — DONE 2026-08-12, browser-verified

Suite **2,285**. The follow-up to the section above: the Wonders pass gave Hearthstones
a home on the Manse Background row, and the human's click-through found that nothing
checked them — *"Hearthstones don't check their Manse rating against your background
(or use the multiple-Hearthstone math from Savant and Sorceror p66)."*

The governing sentence is **S&S p.67**: "The sum of the levels of all the Hearthstones
produced can never exceed the level of the Manse." p.66's *Multiple Hearthstones by
Design* is the other half — a Manse can be built to yield several stones instead of one,
so the rule caps the **total**, never the count.

## Why it could not be checked at all

The first cut appended the picked stone's NAME to the Background row's `note` and kept
no rating. There was no number to check. And `note` is bound to a text input that
rewrites it on every keystroke, so parsing the names back out would have been the
**catalogue-dialog discriminator bug** exactly — a rule switched on by state the player
can edit to switch off (see `catalogue-dialogs.md`).

So stones are stored structurally: `BackgroundEntry.hearthstones`, a list of
`HearthstoneEntry(name, rating)`. The rating is an inline COPY of the catalogue entry's
(decision 0007) — S&S p.67 says every Manse is unique and the printed ten are examples,
so a stone renamed at the table must not keep claiming the printed one's level.

## The allowance is data, and it is not uniform

⚠ **The assumption that nearly shipped: "a Manse row's rating IS the Manse's level."**
True for the corebook and false for three of the six variants. The printed ladders
already carried the real numbers:

| Variant | Shape | Source |
|---|---|---|
| core `Manse`; Sidereal + Dragon-King `Celestial Manse` | linear, 1 level/dot | "Level N Manse" / "Produces a level N Hearthstone" |
| Dragon-Blooded `Manse`; Abyssal `Underworld Manse` | tiers **2/3/6/8/10**, largest single stone **2/2/3/4/5** | their ladders, rung by rung |
| Mountain Folk `Manse` | 2 levels/dot | CH6 prose; the splat prints no ladder |

The DB and Abyssal rung 3 is the one that proves the shape is needed: six levels total
but no stone above 3, so 4+2 is illegal where 3+2+1 is legal. No single cap expresses
that, and `BackgroundBudgetTier` (the Abyssal Artifact budget's row model) already did.

**These live on `BackgroundType`, not on `BackgroundRule`.** That is a deliberate
departure from the convention stated in the `ladder` field's own comment ("the numeric
rules a ladder happens to state belong in the per-splat `BackgroundRule`"), for one
reason: `background_rules` is keyed per BUDGET ROW and Dragon-Blooded has **14** of
them, so the DB tiers would have been authored up to fourteen times. The Manse variants
are already six distinct per-splat catalogue entries with their own ids, and
`background_catalogue_for` already resolves the right one per character. One authoring
site each, beside the ladder text they were transcribed from.

⚠ `BackgroundBudgetTier.max_items` is new and is set on exactly one rung: the DB and
Abyssal single-dot row prints *"She may have **one** Hearthstone of level 1 or 2"*, a
COUNT the two maxima cannot express (combined 2 + individual 2 permits two level-1
stones). Read out of prose rather than a table; **the human signed it off 2026-08-12.**

## Demesnes are deliberately not modelled

Every Manse ladder doubles as the Demesne ladder one rung up, and S&S p.66 gives Demesne
stones their own rule (one level BELOW the Demesne, decaying once removed). **Human's
ruling 2026-08-12:** "Demesne hearthstones are barely a thing and are directly said to
barely exist." So `BackgroundEntry.is_demesne` marks the row and it grows no stones —
that toggle is the whole of the support they get.

The toggle stays visible on a row already flipped, or there would be no way back; and a
stone stranded by flipping (or by renaming the row) still renders with its delete
control, because **an Issue the player has no widget to act on is worse than no Issue.**

## Enforcement

`validate.check_hearthstones`, called unconditionally from `validate` — **hard on both
sides of the lock, the human's ruling.** The allowance is keyed to a Background the story
raises and lowers, so a chargen-only check would fall silent exactly when the cap started
moving. **Per ROW, not per character**: two Manse rows are two Manses with two
allowances. Four codes: `hearthstone-over-combined`, `-over-individual`, `-over-count`,
`-without-manse`.

The `"manse" in name.lower()` substring test is GONE, replaced by
`artifacts.grows_hearthstones` reading the data. The substring both over-matched (a row
typed "Manse (destroyed)") and could say nothing about how many levels a row carries.

## What the work turned up

* **Two UI bugs in one line, both invisible to a green suite.** The running total
  captured its allowance when the row was BUILT, so raising the Manse moved the printed
  rung and left "4 / 3" insisting the row was still over budget; and the rating control's
  sync hook drove only the rung label, never the stone total. Found in the browser.
  **Why the suite could not see it: every test until the regression read the total on a
  freshly built panel, which is the one phase a stale captured value agrees with.** The
  fix recomputes the allowance inside the repaint and chains the total's sync onto
  `row_sync["fn"]`.
* **Preflight caught the sibling before the browser did.** The stone's rating
  `ui.number` called `refresh_all()`, which rebuilds the panel — and a rebuilt input eats
  every keystroke after the first. That lesson was already written twenty lines away on
  the Background description label and still got re-broken. Repaint in place; only
  removal rebuilds, because a click carries no in-progress typing.
* **A test that passed alone and failed in the suite**, for the reason already recorded
  in `nicegui-harness-one-route-per-test`: it imported `_ui_main`'s character to assert
  on it, and the harness loads that file as its own module object, so the import bound a
  different instance. Asserting through the UI is both correct and stronger here — the
  printed total can only read "4" if the pick recorded the stone's RATING.

## Files

* `models/rules.py` — `BackgroundType.hearthstone_tiers` / `hearthstone_per_dot`;
  `BackgroundBudgetTier.max_items`; the tier class MOVED above `BackgroundType` so the
  annotation resolves
* `models/character.py` — `HearthstoneEntry`, `BackgroundEntry.hearthstones` /
  `is_demesne`
* `engine/artifacts.py` — `HearthstoneAllowance`, `grows_hearthstones`,
  `hearthstone_allowance`, `hearthstone_total`
* `engine/validate.py` — `check_hearthstones`, called from `validate`
* `ui/advantages.py` — structured picker, Demesne toggle, per-stone rows, the running
  total, `bg-rating` marker
* `data/backgrounds.json` — the six Manse variants
