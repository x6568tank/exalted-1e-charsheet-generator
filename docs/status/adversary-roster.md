# The adversary roster — DONE, browser-verified 2026-08-01

A Storyteller's list of extras, beasts and NPCs on `/gm`, beside the party they are
fighting. 1,794 tests. **Browser-verified 2026-08-01** — clicked through, no findings.
The *What to click* list at the bottom is kept as the regression walk-through.

Requested by the human 2026-08-01: *"a way for a GM in GM mode to add and track
extras/beasts/whatever. Just a list of them with relevant stats pre-filled and
primitive trackers, nothing else."* The scope line is the design: **this is not a
second character builder.** Nothing validates, prices or locks.

## What shipped

| Piece | Where |
|---|---|
| `Adversary`, `AdversaryAttack`, `AdversaryTrait` | `models/adversary.py` |
| `Party.adversaries` | `models/party.py` |
| Template instantiation, health notation, damage track, armour+shield soak/dodge | `engine/adversaries.py` |
| Roster ids, duplicate naming, and the trait/attack **codec** — `parse_traits`/`trait_line`, `parse_attacks`/`attack_line` (**moved here from `ui/` 2026-08-10**) | `engine/adversaries.py` |
| The card's stat-line wording: `summary_line`, `trait_map_line` (**moved here from `ui/` 2026-08-10**) | `ui/view.py` |
| The roster section, cards, editor dialog — widgets only now | `ui/adversaries.py` |
| 49 catalogue templates | `data/adversaries.json` |
| The three p.335 shields, as tagged rows | `data/armor.json` |
| Catalogue loader | `rules_db.load_adversary_catalog` |

Cards carry a health track, a Willpower spent-track and one mote counter; the buttons
are Reset, Duplicate, Edit and Delete. Entries persist in the existing `.party.json`,
and bundles saved before this loads with the list empty.

**⚠ `parse_traits`/`trait_line` and `parse_attacks`/`attack_line` are CODEC PAIRS, not
a parser plus a display helper.** The GM edits both fields as free text: the `*_line`
function fills the input, the `parse_*` function reads it back, and the round trip is
asserted (`trait_line(parse_traits(s)) == s`). Change one side and you must change the
other. That pairing is why they stayed together in `engine/adversaries.py` when the
2026-08-10 sweep sent the other model→text functions to `view.py` — splitting a codec
across two modules is worse than either home. `expand_health`/`format_health` beside
them is the same shape and the reason `engine/` is the home.

## An Adversary is NOT a Character, and that is the load-bearing decision

The human's framing was explicit: *"these enemies need nothing more than the bare
minimum."* Reusing `Character` was the fast path and would have dragged chargen, the
lock and the XP ledger onto a bandit — after which "not a second character builder"
erodes by increments. A test asserts the separation (`test_adversary_is_not_a_character`)
so re-merging them has to be argued for rather than drifted into.

The cost is a second small model with its own tracker widgets, which duplicate
`ui/play.py`'s cycle and colours by design — a GM should not have to learn two damage
trackers, so they were kept deliberately in step rather than shared through a Character-
shaped signature.

## One model, five printed templates

The corebook prints adversaries at five levels of detail and they nest, so every field
but `name` is optional and "bare minimum" is what an extra actually stores:

* **Extra** (p.241) — base initiative, one combat pool, Valor, Willpower, 3 health levels
* **Beast** (p.316-317) — + Str/Dex/Sta, attacks, Abilities, dodge/soak
* **NPC** (p.276-279) — + all 9 Attributes, 4 Virtues, Essence, notes
* **Spirit** (p.292-295) — + Nature, Backgrounds, Charms, Powers, Cost To Materialize
* **Exalt / Deathlord** (p.302-315) — + Caste/Aspect, Spells, Personal/Peripheral Essence

Three shapes the pages forced, each with a test:

1. **`charms`, `spells` and `powers` are PROSE, never ids.** The book prints "All Solar
   Charms the Storyteller cares to give him" (p.303) and, for Sesus Nagezzer, a
   paragraph naming no Charm at all. There is nothing to resolve and the loader's
   link-checking would reject the attempt.
2. **`dodge` is nullable, not zero-defaulted.** The Bear prints no dodge figure (p.316)
   and Nagezzer prints the literal "Does not dodge" (p.307). Absent ≠ a pool of 0.
3. **Two mote-pool shapes.** Spirits print one `Essence Pool: 112`; Exalts print
   `Personal 11 / Peripheral 27`. Elementals invert the materialize cost entirely —
   their natural state is physical, so they pay to *De*materialize (p.295/298).

`health_levels` is a flat penalty list, the shape `OxBodyPurchase.health_levels` already
uses. The book's repeat notation (`-0/-1 x 7/-2 x 12/-4/Incap` = 22 boxes) is expanded on
author and on GM input, never at render time.

## Instancing is the feature

Five bandits off one catalogue row, each with its own health track. Without it a GM is
back to hand-copying, which is the problem the roster exists to solve. `instantiate()`
deep-copies and clears tracked state, so duplicating a bloodied bandit gives a fresh one;
the Duplicate button numbers the copy ("Bandit" → "Bandit 2") and inserts it beside its
original so a squad reads as a squad.

Template instantiation is the same mechanism — the human's stated purpose was *"so GMs
can set up enemy NPCs without going through the full chargen"*, which makes a template a
**starting point that becomes an editable copy**, not a read-only row. The catalogue is
never written back to.

## The catalogue: generic templates only

49 entries — 3 extra tiers, 5 mortal archetypes, 3 soldier grades, the Merchant Prince,
4 Wyld, 5 undead, 1 elemental, 23 beasts and **4 Exalts**.

**Named individuals are excluded** by the human's ruling: Fakharu, Erymanthus, the Mask
of Winters and Juggernaut are in `images/` as worked examples of the statblock shape,
which is the job they have done. A test enumerates them and fails if one is ever added.
**The Fair Folk are excluded under decision 0010** — pp.285-287 are entirely theirs and
were skipped on sight.

**The four Exalts are the deliberate exception** (human, 2026-08-01, taking option 2 of
three offered). The corebook stats Exalted ONLY as named individuals, which under the
strict reading left the roster with no Dragon-Blooded, Sidereal or Abyssal at all — its
one real hole. But four of those blocks sit under ROLE headings and are plainly meant as
archetypes, and the book says so of one outright: *"Avaku could be any ambitious young
Dragon-Blooded warrior. Such foes typically travel in groups of two to six, usually
leading detachments of elite troops. Terrestrial Exalted are never extras."* (p.308)

| Template | Splat | From |
|---|---|---|
| Dynasty Noble | Dragon-Blooded, Wood | Sesus Nagezzer, p.306-307 |
| Ambitious Young Officer | Dragon-Blooded, Fire | Denovah Avaku, p.307-308 |
| Bronze Faction Functionary | Sidereal, Favored of Saturn | Ahn-Aru, p.311-312 |
| Deathknight | Abyssal, Day | Typhon, p.314-315 |

Names stripped, everything else as printed. Two carry a wrinkle worth knowing:

* the **Dynasty Noble** has no combat line at all — "Attack: Charms only" and "Dodge
  Total: Does not dodge", so his `attacks` list is empty and `dodge` is None. He is the
  clearest proof the nullable-dodge decision was right.
* the **Deathknight**'s armour is recorded as NATURAL soak rather than an `armor_id`,
  because he permanently runs the Abyssal equivalent of Front-Line Warrior's Stamina and
  so takes no mobility penalty from it. Attaching the armour would have derived 8-2=6
  against a printed Dodge Pool of 8.

**The fifth role-headed Exalt block is deliberately absent.** The Lunar Trickster
(Magnificent Jaguar, p.309-310) prints every combat number as a base//combat-form PAIR,
and alternate forms are unmodelled by decision — half his statblock has nowhere to go and
the other half cannot be invented. A test asserts the absence so it reads as a choice.

Soak is stored as *natural soak + an armour id* and the engine adds them back into the
printed total; a parametrised test asserts eight templates come back to the figure on the
page. Where the book names bespoke armour with no catalogue equivalent (the Wyld Shaman's
scars and tattoos, the Wolfman's battered chain hauberk) the whole printed figure is
stored as natural soak and the source is named in the entry's notes.

## What this turned up on the way

**The dead-field bug happened again, and preflight caught three of them at once.**
`powers`, `combat_pool` and `cost_to_dematerialize` were authored into the catalogue,
printed on no card, and — worse — absent from the editor dialog, so opening and saving
any spirit or extra would have **silently wiped them**. 1,777 tests were green over that.
The render-matrix pass found the first (a spirit route asserting on its Powers line); the
other two came from auditing the rest of the model the same way.

Two tests now make the class impossible to reintroduce: every stat field must be both
written by `edit_dialog` and read on the card. A new field fails them until it is wired to
both ends. **The card's read set includes `engine/adversaries.py`** — `dodge`, the soak
pair and `armor_id` reach the card only through the engine, which is the correct path, not
a miss.

Also caught, before it could bite: a `pool` local in `edit_dialog` was about to shadow the
Essence-pool input with the new combat-pool one.

## Shields — CLOSED, and it closed the one open discrepancy

Shields were briefly a known gap: Infantry and Elite Troops print `Dodge Pool: 3/0` and
`5/2`, and with only an armour slot the derived pool came out exactly **one higher** than
the page. The human's call was to make a shield ordinary equipment — a second equippable
slot beside armour — and the stats turned out to exist, hidden in the **p.335 armour
prose** rather than in any table (`images/Non-Exalts/Extras/Exalted 335.png`).

**Shields are ARMOUR ROWS, not a model of their own** (`tags: ["shield"]` in
`armor.json`). A first pass added a parallel `ShieldType` + `shields.json` + a
`shield_catalog`; the human pointed out that characters already hold a LIST of armour, so
a shield is simply another row. That deleted the model, the file and the catalogue, and
**gets `Character` shields for free** — no new field, no new UI, and because a shield has
no soak the derived total is unchanged while its mobility penalty shows on the sheet
beside the armour's. `RuleSet.body_armor()` and `RuleSet.shields()` are the two views;
they are asserted disjoint.

| | Mobility | Difficulty melee | Difficulty ranged |
|---|---|---|---|
| Buckler | 0 | +1 | 0 — "does nothing to protect the character from missile fire" |
| Target Shield | -1 | +1 | +1 |
| Tower Shield | -2 | +1 | +2 |

`difficulty_melee` / `difficulty_ranged` are the only shield-specific fields on
`ArmorType` and are 0 on every real armour. They are **display only** — decision 0008
keeps attack resolution out of this build, so the card prints them the way the book's own
statblocks do ("+1 difficulty to attack") and the Storyteller applies them.

Shields grant no soak, which is what makes the shared row honest: summing one into a soak
total changes nothing, so nothing had to learn that a row might not be armour.

**The Adversary keeps a `shield_id` slot** only because it holds ONE armour rather than a
list, and a shield stacks with armour rather than replacing it. `armor_options()` filters
shields out of the armour picker and `shield_options()` offers only shields, so the two
dropdowns cannot disagree.

With the shield attached to Infantry, Elite Troops and the Wyld Barbarian, **every printed
dodge pair in the catalogue now round-trips exactly** — 4/3, 3/0, 5/2 and 4/2.

The tower shield's strapped configuration (protects as a target shield, hands free, +1
fatigue) is recorded in its `notes` and not modelled as a separate row.

**The dead-field guard paid for itself here.** Adding `shield_id` needed no new test:
`test_every_stat_field_survives_an_edit` and `…_reaches_the_card` walk `model_fields`, so
they covered the new field the moment it existed and would have failed had the editor or
the card missed it.

## Transcription caveats

* **The Yeddim's Trample** (p.317) — **RESOLVED, a misprint** (human, 2026-08-01). The
  Attack column reads `-2x3/-4/I`, which is health-level notation rather than
  Speed/Accuracy/Damage; the ruling is that it is the health track's own continuation
  typeset into the wrong column, which is consistent with where that track ends. The
  attack is named and left unrated, and `test_the_yeddim_trample_has_no_invented_numbers`
  pins it — a plausible number is the easy thing to add here and must not be.
* A few beast health tracks come from a dense two-page table (`-0x2/-1x3/-2x3/-4/I` and
  the like) and are the most likely place for a misread. Worth spot-checking Bear,
  Siaka, Tyrant Lizard and Yeddim against the page.
* **Spreads 290-291, 296-297, 308-309 were not read.** 296-297 are absent from
  `images/`; the others are section intros whose sample characters are named individuals
  and therefore out of scope. If a generic elemental sits on 296-297, it is not in the
  catalogue.

## What to click

1. `/gm` → **Adversaries**. Add from the catalogue: an extra, a beast, a soldier, the
   Zephyr. Check the stat line reads the way the page does.
2. **Duplicate** a damaged entry — the copy must come up clean and numbered.
3. **Edit** a spirit (the Zephyr), save without changing anything, and confirm Powers,
   Charms and the dematerialize cost all survive. This is the bug that was just fixed.
4. Type an ad-hoc entry from scratch: attacks as `Bite: Speed 6 Accuracy 7 Damage 1L`,
   abilities as `Melee 3 (Swords +2), Dodge 2`, health as `-0/-1 x 2/-4/Incap`.
5. **Elite Troops** should read `Dodge 2` and `+1/+1 difficulty to hit` — the shield
   working. Swap its shield to a **tower shield** in the editor and the dodge should
   drop to 1 with `+1/+2` difficulty.
6. Save and reload the party, and confirm the roster and its marks come back.

## The second shell — the native Party window (2026-08-27)

`qt/adversaries.py`, a tab of `qt/party.py`. Same model, same engine, **a different
shape**: the webapp's card stack becomes the settled Qt collection layout — toolbar
(Add / Duplicate / Reset / Delete), a roster table, and the selected entry's trackers and
editor in a detail pane. The modal editor dialog is that pane; nothing about the data
changed.

⚠ **Cards did one thing better and it is kept.** Six bandits' damage visible at once is
now the table's **Damage column** (`1/ 0x 0*  (-1)`); it is the compensation that makes a
collection acceptable here, not decoration.

⚠ **The table is sortable but NOT SORTED** (`sortByColumn(-1, …)`). Roster order is the
feature — a duplicate is inserted *beside* its original so a squad reads as a squad — and
an alphabetical default would scatter it on the click that made it.

### The mutations moved into the engine

`add_blank`, `add_from_template`, `duplicate`, `remove`, `reset_tracking`, `mote_cap`,
`set_motes_spent` and `set_count` were closures in `ui/adversaries.py`, so the native
shell could not reach them. They live in `engine/adversaries.py` now and **the webapp
calls them too** — one path, both shells, exactly as the Combo mutations went.

⚠ `test_reset_clears_exactly_what_instantiate_clears` pins `reset_tracking` against
`instantiate`: both give an entry a fresh start, and a new tracked field added to one and
not the other is how a "fresh" duplicate ends up carrying spent motes.

### The dead-field guard, rebuilt as a drive

The webapp's guard greps `edit_dialog`'s source for `a.<field> =`. The Qt one
parametrises over `Adversary.model_fields` and **drives the named widget**, asserting the
model changed — so a field wired to a widget that writes the *wrong* attribute fails too,
which a grep can never see. `tests/test_qt_adversaries.py`.

### Three printed rules the widgets had to encode

1. **0 means ABSENT in the trait grids**, shown as "—" (p.316: a beast prints three of
   the nine, and no block prints a zero).
2. **The nullable combat numbers run from −1**, shown as "—", because absent is not zero
   (the Bear prints no dodge, p.316; Nagezzer "does not dodge", p.307).
3. **Charms / Spells / Powers stay free text** (p.303).
