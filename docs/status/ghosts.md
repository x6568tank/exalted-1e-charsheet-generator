# Ghosts — DONE (data, engine, UI), browser-verified 2026-08-01

**Shipped 2026-08-01.** The **seventh splat** and the **second non-Exalt** one, after
Mortals. Source, all human-pasted into `images/Non-Exalts/Ghosts/`:

| Source | Pages | What it gave |
|---|---|---|
| `CH 3 - Character Creation.md` | E:Ab 123, 125-127 | budgets, the two axes, the BP table |
| `CH 4 - Traits.md` | 148, 150-153 | Backgrounds (three new, three barred), powers of the dead |
| `CH 6 - The Arts of the Dead.md` | 232-253 | the 56 Arcanoi and the four Craft schools |
| `Abyssals p283.png` | 283 | the experience table, and the Passion ruling |

## What makes ghosts different from every splat before them

Four things, in order of how much code they cost:

1. **Their Charms are VIRTUE-keyed.** Every one of the 56 Arcanoi prints exactly one
   "Minimum Compassion/Conviction/Temperance/Valor" and no Ability minimum at all.
   This is the **third and last keying axis** — `Charm.min_virtue`, alongside Lunar's
   `min_attribute`. `validate.charm_ability_shortfalls` had promised "a third gating
   axis has exactly one function to change", and that held.
2. **Fetters and Passions**, two rated traits nothing else has. See below — the
   Passion rule is the interesting one.
3. **Two independent chargen axes at once** — ghosts are the first splat to use both
   `origin` and `upbringing` for unrelated things.
4. **Three bars**: no Combos ever, thaumaturgy held but never used, and no other
   splat's Charms — **except the Terrestrial supernatural martial arts**, which every
   ghost may learn (PG p.234). See below.

## Passions are a live derivation, not a budget

**The most important thing in this file.** p.126 sets the pool at creation — "a number
of dots of Passions for each Virtue equal to the number of dots the character has in
that Virtue" — and p.283 closes it: *"Ghosts increase their Passions when they increase
their Virtues. **There is no other way for these Traits to increase.**"*

The human confirmed the post-lock half explicitly (rules authority, 2026-08-01): **lock
the character, buy a dot of a Virtue with experience, and one dot of that Virtue's
Passions becomes available to distribute.**

Three consequences, each of which is a place this could have gone wrong:

* `derive.passion_pool` reads the **current** Virtues and takes no snapshot. Passions
  are deliberately **absent from `ChargenSnapshot`** — freezing them would be decision
  0005's Willpower treatment applied to a rule that says the opposite.
* **The pools are PER VIRTUE and do not pool.** Compassion 3 buys three dots of
  Compassion Passions and nothing else. `check_fetters_and_passions` reports per Virtue
  for that reason: a ghost over on Compassion and under on Valor nets to zero, and one
  aggregate number would hide both errors at once.
* **There is no `passion` row in any cost table**, BP or XP, and there must not be. The
  only experience operation is **Shift Passion** (20 XP), which moves a dot between
  Passions and leaves the total where the Virtues put it.

`test_raising_a_virtue_WITH_XP_opens_a_passion_dot` is the test this whole area exists
for, and it drives `advancement.raise_virtue` rather than poking the Virtue directly.

## Fetters

Bought normally — 5 dots at chargen, none above 3 without bonus points, 3 BP/dot,
`current × 3` XP, 20 for a new one. Two things worth knowing:

* **The cap is Willpower + Essence and it MOVES** (p.127, restated in the p.283
  footnote). So it is derived, not budgeted, and `check_fetters_and_passions` runs on
  **both** sides of the lock — a ghost who buys Willpower may hold more, and one cursed
  down is over the cap and told so. `advancement` asks the cap before every purchase
  that adds a dot.
* **The new-Fetter discount is the only conditional price in the build**: 15 instead of
  20 for a ghost who knows Mark of the Relentless Hunter. The Arcanos is named in
  **data** (`ExperienceCosts.new_fetter_discount_charm_id`), never in code, and asked of
  `validate.charm_picks` rather than `character.charms`.

## The two axes

| Axis | Values | Decides |
|---|---|---|
| `origin` | `heroic` / `mundane` | 6/4/3 · 22 abilities · 6 Arcanoi · 21 BP, vs 4/3/3 · 16 · 2 · 15 |
| `upbringing` | *(blank)* = ancestor-worship / `immaculate` | 8 vs 5 Background dots, and the Ancestor Cult / Grave Goods ceiling |

⚠ **A ghost's origin is never blank.** `_keyed_row` only consults the `E:o:u` key when
the origin is non-empty, so `heroic` is a real value rather than a fallback — unlike
every origin default before it. The plain `Ghost` row IS the heroic row, so an
origin-less legacy save still lands somewhere sane.

## Backgrounds (p.150-153)

* **New:** Ancestor Cult, Grave Goods, Underworld Cult — all `exalt_type: Ghost`.
* **Barred:** Familiar, Liege, Manse. Ghosts serving Deathlords use Backing.
* **Whispers costs double** — "The first 3 dots cost 2 Background or bonus points each,
  while each dot above 3 costs 4 bonus points each." This needed a new model field:
  `BackgroundRule.dot_cost`. The existing `expensive_above`/`expensive_dot_cost` pair
  **cannot** express "every dot is dearer", because its threshold doubles as its
  disabled sentinel.
* **Immaculate-region ghosts cap Ancestor Cult and Grave Goods at 1** — a HARD ceiling
  bonus points cannot buy past, hence the other new field, `BackgroundRule.max_rating`.

## UI

* **Fetters and Passions live on the Advantages tab** (human's call), beside Backgrounds
  and M&F — they are lists edited under two budget regimes, which is what that tab is
  for. The Passion dot track is a **free setter on both sides of the lock**: it
  distributes a derived pool, it does not buy anything.
* **Arcanoi are their own Charms page** in the picker (human's call), like
  Thaumaturgy's. The page is selected by `min_virtue`, not by a hardcoded list of the
  six categories, so a seventh path needs no edit.
* Sheet panels for both, dropped entirely when empty.
* Palette: **pale grey-green** (`zinc`) — grave-mould, pushed off both the Abyssal's ash
  and the Mortal's earth, the two it could be confused with.

## Two findings the tests did not catch

1. **`charm_learnable_by_splat` routed around the foreign-Charm bar.** The bar lived in
   `charm_matches_splat`, but the other function falls THROUGH that to the p.127
   generalist privilege — so a ghost handed the Eclipse privilege by a house rule would
   have walked straight past p.126. **Found by preflight, not by 1,668 passing tests.**
   The build's most-repeated bug shape, again.
2. **`CharmCost.health_type` is no longer homebrew-only.** CLAUDE.md documented it as
   having no printed use; Stolen Wax Discipline (p.238) is the first — "5 motes, one
   lethal health level". A test asserting "unset on every printed Charm" was narrowed to
   the invariant that still holds.

## How the catalogue was extracted

`tools/extract_ghost_arcanoi.py`, kept in the repo because `images/` is gitignored — on
a clone it is the record of how the data was derived. It reports and exits non-zero
rather than guessing. Three things in the paste needed real handling:

* a **Cost line wrapping mid-parenthesis** (p.237) — folded while brackets are unclosed;
* **three prerequisite lines wrapping mid-NAME** — folded only while the trailing name
  fails to resolve against the known Charms. The first attempt used a loose heuristic
  and swallowed entire descriptions into the prerequisite field;
* **`Type: Supplementary`** on one Charm where nine others print `Supplemental`.

Verified against the source's own counts: 56 Charms; paths 10/11/9/9/8/9; Virtues 18
Compassion / 18 Temperance / 11 Conviction / 9 Valor; every Cost line round-trips
verbatim; every row carries its page.

**50 Charms carry prerequisites** (56 edges, 6 roots), and how that number was reached
is worth recording as a caution.

CH6 prints 49 well-formed non-`None` "Prerequisite Charms:" lines — **plus one the paste
mangled into `PrerequisiteCharms:`** with the space dropped, on p.244's Feeding the
Lamprey's Appetite. The same line also names `Essence-DevouringGhost Touch`, losing a
space inside the Charm name. The field regex required literal spaces, so the whole line
fell through into the description and the Charm silently lost its gate.

**A field name that fails to match does not fail loudly.** The extractor reports and
exits non-zero on an unresolvable prerequisite, but a line it never recognises as a field
at all is just prose. That is the failure mode to watch for in any future extraction.

The human hand-corrected the JSON; a later re-extract overwrote the fix; and the
resulting drop from 50 prerequisites to 49 was misread as the data being stale rather
than the extractor being wrong. **49 was the wrong answer, arrived at confidently, and
briefly written into a test as if it were source-verified.** The parser now tolerates
dropped spaces in both field names and Charm names, so the correction is derived from
source and survives a re-extract.

`test_no_arcanos_description_swallowed_a_field_line` guards the whole class, not just
the one instance.

**Names.** The source prints headings in ALL CAPS, so they are title-cased on the way in
— but `str.title()` treats an apostrophe as a word boundary and produced "Lamprey'S
Appetite" on five Arcanoi (reported at the browser). `title_name` fixes it for both the
ASCII apostrophe and the curly U+2019 the paste actually uses, while leaving hyphenated
names with both halves capitalised ("Ghost-Devil Form" — which is why `string.capwords`
is not the answer). Two tests cover it, asserted over the whole catalogue rather than the
five known names.

Re-running `tools/extract_ghost_arcanoi.py --write` reproduces the shipped files
byte-for-byte, which is the check to run if the data is ever in doubt.

## Deliberately absent

* **Training times** (p.283 prints a full table). CLAUDE.md: almost certainly never.
* **"Invent New Arcanos" (20 XP)** — inventing one is authoring homebrew, which the
  `custom/` library covers and does not price. Recorded rather than modelled, so that
  no dead field exists for it.
* The four **Craft schools** (Moliation, Pandemonium, Soulforging, Jadecrafting) needed
  no data: Craft is already a per-focus free-text Ability. Their Standard/Challenging
  difficulty tables are roll mechanics — decision 0009.
* **Powers of the Dead** (p.148-150: Acute Sense, Naturally Immaterial, Vulnerable to
  Wards) are dice modifiers and narrative, i.e. decisions 0008/0009.

## Ghost martial arts (Player's Guide p.234)

**This page arrived after the splat shipped and OVERTURNED a reading recorded here as an
open question.** E:Ab p.126's "Ghosts may not learn Exalted Charms" had been read as
barring the Terrestrial styles as well. It does not:

> "Ghosts may learn supernatural martial-arts techniques as well. Like thaumaturges and
> God-Blooded, they can learn only Terrestrial styles. They do so at the same cost per
> Charm that they would pay for inventing a new Arcanos (20 experience points)."

That is worth recording as a process note, not just a fix: **the reading was flagged
BECAUSE it was a reading, and the flag is what got it corrected within the day.** The bar
would otherwise have looked like transcription.

### How it is modelled

* **Access is the SPLAT's and is unconditional** —
  `ExaltDefinition.terrestrial_martial_arts`, one printed exception to
  `foreign_charms_barred`. Every ghost has it, with or without the Merit. Modelling the
  access as the Merit's would have barred it from every ghost without one.
* **The default price is a penalty**: `new_martial_arts_charm` 20, against the 14 an
  ordinary Arcanos costs. p.234 sets it equal to inventing a new Arcanos.
* **`validate.is_terrestrial_martial_arts` is the one definition** of the class, shared
  with the mortal Essence Mastery route so the two cannot drift.

### Fighter in Life (variable-point Merit, GHOSTS ONLY)

> "For every point spent on this Merit, the character can choose to have known one
> Terrestrial-level Martial Arts Charm during her life. … It merely allows the ghost to
> purchase it at character creation for 6 bonus points or during play for the cost of
> developing a regular Arcanos (14 experience points)."

A **count, not a permission** — `MeritEffects.terrestrial_ma_picks`, per decision 0011,
and no module outside `engine/merits.py` names the id (a test pins that for this Merit
specifically). The first N such Charms price at the Arcanos rate; the (N+1)th pays 20
again. Which N is the player's, and the page does not say, so it covers the first bought
— the cheapest reading.

**The chargen half needed no code.** The ghost bonus-point rate for a Charm is already 6,
which is exactly what the Merit prints, so `charm_pick_bp_costs` falls through to the
right number on its own.

### One ordering bug this caused

The Immaculate rate branch in `costs.charm_cost` fired BEFORE the martial-arts branch, so
a ghost learning an Immaculate Dragon Path was charged **Dragon-Blooded's** Immaculate
rate (p.292) — a row the Ghost cost table does not even author. The ghost branch now
comes first.

### The tagging correction this exposed (2026-08-01)

Asking "should ghosts reach the Immaculate Dragon Paths?" turned up a **pre-existing data
bug that had nothing to do with ghosts**. Human, rules authority:

> **Five-Dragon Style is Terrestrial; the Immaculate Dragon Paths are Celestial.**

The data had both **exactly backwards**:

| Style | Was tagged | Actually | Cost of the error |
|---|---|---|---|
| Five-Dragon | `open_to_tiers: ["Celestial"]` | **Terrestrial** (`open_to_all`) | Terrestrial-only splats were DENIED a style they may learn |
| Air/Earth/Fire/Water/Wood Dragon (×59 Charms) | `open_to_all: true` | **Celestial** (`open_to_tiers`) | Terrestrial-only splats were OFFERED five styles they may not |

Wrong in both directions, so it cost twice, and it was invisible because the only splats
with Terrestrial-only martial arts are recent: mortals (via Essence Mastery, 2026-07-30)
and ghosts (via PG p.234, today). Celestials reach the Dragon Paths either way — by tier
now instead of by `open_to_all` — so no shipped splat's access changed except at the
Terrestrial end.

**Follow-up for the human, not actioned:** the mortal `bar_immaculate_charms` ruling
(2026-07-30) exists to keep Essence Mastery from handing a mortal the Dragon Paths. With
the Paths correctly Celestial, **mortals cannot reach them anyway** and that flag is now
redundant. It has been LEFT IN PLACE — it is a recorded ruling and it is still correct,
just no longer load-bearing. Removing it is your call, not mine.

### Spirit Walking is barred (human, rules authority, 2026-08-01)

**Ghosts may not take Spirit Walking** — the same Charm the Essence Mastery Merit
withholds from mortals, and for the same reason: it is what opens the Immaculate Dragon
Paths. Spirit Sight is not barred; the ruling named one Charm, matching the mortal
precedent exactly.

Modelled as **`ExaltDefinition.barred_charm_ids`** — DATA, so barring a Charm from a
splat is a JSON edit and no module names a Charm id to do it. The mortal bar stays where
it is (a `MeritEffects` field), because there it is the *Merit's* doing rather than the
splat's.

**It had to be restated at BOTH entry points.** `charm_learnable_by_splat` does not
merely delegate to `charm_matches_splat` — it falls THROUGH a False answer into the
Terrestrial-martial-arts grant and the p.127 generalist privilege, so a bar checked only
in the callee is one that route walks straight past. The first attempt did exactly that
and the bar silently did nothing. This is the third instance of that shape in two days
(the foreign-Charm bar, the Immaculate cost ordering, this) — **in this codebase, a
permission checked in one function is not checked.**

## Verification

1,678 tests pass; `tools/validate_charms.py --splat ghost` is clean (0 errors, 0
warnings). Preflight ran and found the `charm_learnable_by_splat` bug above.
`tests/test_ghost.py` is 76 tests.

**Browser-verified 2026-08-01** — clicked through, no findings. The list below is kept as the regression walk-through, in priority order:

1. **The Advantages tab, pre-lock** (`/ghost-advantages`) — the Fetter pool against the
   live Willpower+Essence cap, and the per-Virtue Passion distribution.
2. **The same tab, locked** — then **raise a Virtue with XP on the Edit tab and come
   back**: a Passion dot must have opened. That is the rule most likely to be subtly
   wrong in a way tests do not see.
3. **The picker's Arcanoi page** — six paths and the tree canvas. The **Martial Arts**
   page should also be offered (p.234); an **Abilities** page must NOT be.
4. **The sheet** — both new panels, and "Single pool" rather than "Personal 0".
5. **An Immaculate-region ghost** — 5 Background dots, and Ancestor Cult refusing to go
   past 1.
