# Phase 2 — the two scan-only books (2026-08-15)

The second half of the "one last scan" before 1.0. **Scope: the two books with no PDF
text layer at all**, which is why they were left to last. Phase 1 is
`docs/status/phase-1-scan.md`.

## Result in one line

**274 pages read. Everything catalogue-able in Scavenger Sons is authored — 15 gear
rows, 5 weapon rows and 6 adversary templates. Creatures of the Wyld yielded NOTHING.**

`gear.json` 78 → **93** · `weapons.json` 112 → **117** · `adversaries.json` 52 → **58**

With this, **every book in `sources/` has been opened.**

## Method — OCR to LOCATE, page images to READ

Both books are pure scans: `pdftotext` returns **one byte per page** (a form feed).

1. `pdftoppm` → PNG (Scavenger Sons 200 dpi, Creatures of the Wyld 120 dpi).
2. `tesseract` over every page → a page-marked text file, used **only to find where the
   crunch is**.
3. Every value authored was read by eye off the page image, never off the OCR.

⚠ **The OCR is lossy and its counts are a LOWER BOUND.** A keyword census found five
`Cost:` lines in Scavenger Sons; there are at least nine. Soma's cost line was mangled
past matching, and the Deep-Forest Drugs section runs across a page break the census
could not see. **A count from OCR tells you where to look, never how much there is** —
the same lesson the fuzzy name matcher taught during the content-gap re-triage.

⚠ **OCR cannot render the `•` glyph.** It comes out as `®`, `e`, `#`, `¢` and more, so
every Resources value here was read off the page, and two were re-cropped at **400 dpi**
to be certain. This is the `vlm-cannot-count-dots` rule applying to OCR as well.

⚠ **Scavenger Sons has a page offset of ZERO** (PDF 29 = printed 29, confirmed on the
footer). Do not assume the +1 that most books here use.

## Creatures of the Wyld — nothing, and that is the finding

130 pages, "A Bestiary of the Second Age for Exalted". It is exactly what its cover
says: **~80 creature stat blocks** (81 `Attributes:`, 94 `Health Levels`, 118 `Soak`).

* **Every one of its 30 `Cost:` lines is a creature-embedded power** — pp.60, 71, 103,
  107, 118, 122-123, 125, 128 — and those were ruled out of scope on 2026-08-14.
* **No named artifacts.** The 20 `Artifact` hits are prose, NPC `Backgrounds:` lines, or
  a p.64/p.66 sidebar *discussing* what the rating tiers mean.
* **No gear, no Merits, no Backgrounds, no spells.**

⚠ **The Five-Metal Shrike (pp.59-61) looks like an artifact and is not.** It is a First
Age warship written up as a CREATURE — Attributes, Virtues, Abilities and Charms — and
its Resources figures are the cost of *repairing* it, not of buying it. A sweep keyed on
"Resources ••••" would file it as purchasable gear.

## Scavenger Sons — the payload

144 pages, a gazetteer: five regional chapters plus two appendices. **Appendix Two is
the Fair Folk and is out of scope** (decision 0010).

### Authored — 9 gear rows (the six horses below make 15, `gear.json` 78 → 93)

**Deep-Forest Drugs (pp.32-33)** — death sap, soma, bright morning, life flower (blue),
life flower (purple).
**Southern Magical Gemstones (p.47)** — dreamstone (small), dreamstone (large), yasal
crystal.
**Water shoes (p.55)** — under the existing `Clothing and Jewelry` category.

The dual-cost encoding follows the ruling already recorded in `phase-1-scan.md`, and
phase 2 exercised all three branches plus a **new wrinkle worth keeping**:

⚠ **Bright morning prints `••• (•••• in the Realm)`, and that is NOT a remoteness
premium.** The drug is *illegal in the Realm* — the higher figure is a legality
premium. It therefore stays ONE row at the general price rather than being priced "away
from origin" like soma and the water shoes. **Two prices with the same shape can have
different causes; read the prose, not the parentheses.**

### Authored — 5 weapon rows, `weapons.json` 112 → 117

Firewand and bayonet (p.37), war boomerang and spear thrower (p.29), firedust (p.37).

Three rulings from the rules authority, 2026-08-15:

* ⚠ **The war boomerang is BASHING.** The printed table has **no damage-type column** —
  it reads `+3` with no L or B. Bashing is the human's call and the row's `notes` say
  so, so a later reader does not mistake it for a printed value.
* ⚠ **Firedust is stored at `••`,** the LOW figure of its outside-the-South range
  ("• per shot in the South… anywhere from •• to ••• outside"). A range has no field to
  live in; the full printed text is in `notes`. It is a `weapons.json` row tagged
  `ammunition`, following the four corebook arrows rather than inventing a gear category.
* **The spear thrower carries no attack line** and is tagged `accessory`: it is not a
  weapon but a modifier to javelins (+2 damage, double range, no accuracy loss).

### Authored — the Horses of Marukan, BOTH ways (p.88)

Six gear rows under `Slaves and Animals` (rider/dray/swift/scout ••• , battler ••••,
finest ••••) **and** six `Beast` templates on the adversary roster
(`adv.beast_marukani_*`), on the human's ruling that they are both a purchase and a
creature.

⚠ **The health column uses an `xN` repeat notation with an IMPLICIT ×1** —
`-0x/-1x2/-2x2/-4/I`. Where the count is absent it is one, which is confirmed by the
rider's track then totalling exactly the standard seven levels. Read at 400 dpi; at 200
the digits are ambiguous.

⚠ **This broke a test, and the test was wrong.**
`test_beasts_carry_the_p317_default_attributes` asserted Intelligence 1 / Perception 2 /
Wits 3 on EVERY beast — but p.317's own wording is *"unless otherwise stated"*, and
Scavenger Sons p.88 states otherwise ("The scout, finest, and rider all have Wits 4 and
Perception 3. The finest has an Intelligence of 2"). The assertion held only because
every beast in the build until now came from a book that printed no mental Attributes:
**a one-book sample encoded as a rule.** Rewritten with an explicit `STATED_OTHERWISE`
allowlist so an ACCIDENTAL drift off the default still fails, plus a second test that
the allowlist's ids still exist.

### NOT authored — Haltan pets (p.28)

A Haltan Exalt may keep one Familiar plus as many tame animals as she has dots in
Charisma; little pets cost **1 bonus point**, dangerous or large useful ones **2**, and
they may be bought with experience in Haltan lands at **double** the bonus-point cost.
This is a chargen purchase rule, not a catalogue row, and there is no Haltan origin axis
to hang it on. Recorded here only. **Not a gap.**

## The authored items in detail

**Firewand (p.37)** — Accuracy +1, Damage 12L, Range 10, Rate Special, Resources •••,
Weight 4 lbs. One-shot firedust flamethrower, attacks with Dexterity + Archery, reload
one full turn doing nothing else. **Bayonet** — Speed +0, Accuracy +1, Damage 3L,
Defense +0, Resources •••, Minimum Strength •. Firedust itself costs • per shot in the
South, "anywhere from •• to •••" outside it — **a RANGE, which no field can hold.**

⚠ **The firewand nearly got written off as already authored.** `weapons.json` holds a
**Flamecaster** with *identical* stats (Acc +1, Dmg 12L, Range 10) — but that is the
**Mountain Folk** pyromantic-gel artifact weapon (p.278), a different item that happens
to share a stat line. The corebook prints no firewand at all (grep of the extracted
corebook finds only "Firewander", a Nexus district). **A stat-line match is not an
identity match, in either direction.**

**War boomerang (p.29)** — Accuracy +0, Damage +3, Rate 2, Range 20, Cost •, 0.5 lbs.;
a character with Thrown 2+ may make a second reflexive Dexterity + Thrown roll on a miss
to bring it back. **Spear thrower (p.29)** — Cost •, 0.5 lbs.; adds +2 to the damage of
javelins and doubles their range with no accuracy loss. It is an accessory that modifies
another weapon, not a weapon with its own line.

## On a creature creator — an observation, not a proposal

The human raised this and explicitly did not ask for it. Recording only the fact that
bears on it: **the creature stat shape is consistent across books.** The Marukan horses
(Scavenger Sons p.88), the ice weasel (Bastions p.39) and the Creatures of the Wyld
blocks all use the same small set of fields — Physical Attributes, Willpower, a health
track, one or two named attacks, dodge/soak, a short Ability list — which is also what
`Adversary` already models. The variable part is the Charms, and those are the part
ruled out of scope. **Nothing here is a recommendation to build it.**
