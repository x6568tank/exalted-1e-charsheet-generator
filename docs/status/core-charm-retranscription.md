# The Core Charm re-transcription — 2026-09-01

**Suite: 3,115 passed, 1 skipped** (main PC) — the count both before and after this work,
so nothing here was invisible to a test that then broke. That cuts both ways: **the suite
never had an opinion about any of it.** One test referenced a Charm description at all
(see *What this turned up*), and no test asserts a printed minimum against a page.

⚠ **NOT browser-verified, and it does not need a click-through to be trusted — but two
things want eyes.** No UI changed; this is data only. What a human should look at, once:

1. **A Charm detail panel on the Charms tab**, any Solar corebook Charm. The descriptions
   are now 3-8x longer than the ones the panel was laid out against — check nothing
   overflows, elides badly or pushes the buy control off-screen.
2. **The printed/PDF sheet** for a Solar carrying several corebook Charms, same reason.
   `printable-sheet.md` owns that surface.

**All 220 Core Charms across the 25 Solar ability files were re-transcribed from the
page.** Mean description length went from **113 characters to 581** (median 85 → 561),
which puts Core in line with every other book in the catalogue — it had been an order of
magnitude thinner than the next-thinnest, and was the oldest data in the tree.

⚠ **220, not the 234 that `source.book == "Core"` returned when this started.** The
difference is 12 spirit templates that needed nothing (below) and **2 Charms that were
never Core at all** (the necromancy provenance error, below — fixed 2026-09-01). Counting
the query rather than the work is how a sweep overstates itself; the query moved under it.

This is the Charm half of the job the 19 Core spells got in `bb5adae`, and it was found the
same way: the cap in the delegation brief ("one-or-two-sentence") did not merely shorten
the text, it **dropped mechanics and invented replacements**.

## ⚠ It was a CORRECTNESS sweep, not a prose sweep

Four Core Archery descriptions were not thin but WRONG, each in the 2e-shaped direction
the edition rule exists to stop:

| Charm | what the data said | what p.154-157 says |
|---|---|---|
| Wise Arrow | bonus dice "up to **double** the Dexterity + Archery pool" | "cannot exceed her **normal** Dexterity + Archery dice pool" |
| Rain of Feathered Death | "strike **multiple targets**, or one target many times" | "**all** the arrows must attack **the same target**" |
| Dazzling Flare Attack | "bursts into a **blinding flare**, **dazzling foes**" | no such effect: +1 die, +2 damage/mote capped at permanent Essence, min 1 mote, a beacon visible for miles |
| Trance of Unhesitating Speed | extra attacks "**up to the character's Dexterity**" | no cap printed; cost is 2x attacks so far |

⚠ **Wise Arrow's wrong cap is Excellent Strike's real one.** Melee p.162 does say "can no
more than double her character's regular Dexterity + Melee dice pool" — the summariser
carried a neighbouring Charm's clause across. A wrong number that is printed *somewhere*
is the hardest kind to catch by reading.

## ⚠ The offset trap — nearly authored 234 Charms against shifted citations

`detect_offset` returns None on this book: the folios are drawn in a **subsetted display
face**, so they read as `(cid:N)` and the detector runs on raw text *before* decoding. An
offset inferred from content instead was **wrong by one**, which would have pointed every
Charm at its neighbour's page.

**Decoding the printed folio through the glyph map settles it, and nothing else does.**
`pdf 155` decodes its footer to `154`, so the offset is **+1** — and the authored citations
were right all along. The command that reproduces this extraction:

```
python tools/extract_born_digital.py "sources/Exalt Books/Exalted.pdf" \
    153-224,290-293 --offset 1 --glyph-map tools/glyph_maps/exalted-core.json \
    --out "images/_extracted/Exalted Core-charms.md"
```

## The 2026-09-01 glyph fix was load-bearing for NUMBERS

The pre-fix extraction of Trance of Unhesitating Speed's worked example read *"The cost is
**07** motes... **3** for the first, **5** for the second, **7** for the third"*. The
correct text is *"**18** motes... **4**, **6**, **8**"*. The digits were off by one along
with the letters, so the old text was **plausible and wrong** — exactly the failure mode
the glyph map file warns about. The example's own arithmetic (4+6+8 = 18) is what confirms
the fix.

## Not touched

* **`spirit_templates.json`** (12 Charms, pp.291-292) was already at full length
  (350-800 chars) and every Virtue minimum matches the page. It needed nothing.
* Seven Core Charms remain under 250 characters because **the printed entry really is that
  short** — Iron Kettle Body is one sentence on p.178 ("As Unfailing Tortoise Technique,
  but the character's Resistance is added to her lethal soak as well").

---

# The value corrections — data brought to the printed stat block

**ALL 32 WERE APPLIED on 2026-09-01**, on the human's ruling once they had read the table
("correct all confirmed discrepancies; other splats can stand as is"). 33 field changes
across 32 Charms in 17 files. The table below is therefore a **record of what changed** —
the "data" column is what the value used to be, and `data/` now holds the printed column.

⚠ **The earlier ruling was the opposite** — "collect them, change nothing" — and this file
said so until the table had been reviewed. That sequence is the point: the values moved only
after the rules authority read every row. **Do not treat this file as licence to correct a
printed value against `data/` without asking.**

⚠ **Other splats were explicitly left alone** in the same ruling, including the
`min_essence == min_ability` duplication grep. Their Charms were authored by the same pass
and are NOT known to be clean — an untested splat here is untested, not verified.

The corrections were applied by a script that carried the **expected old value** for every
field and aborted if any failed to match, so it could only touch what the audit recorded.
Re-running the mechanical audit afterwards reports **one** mismatch: Ox-Body Technique, the
known false positive described below. Suite green at **3,115 passed, 1 skipped**.

**32 discrepancies across the 232 Core-attributed Charms** — 27 minimums, 3 costs, 2 types. They were not randomly
distributed: they are overwhelmingly `min_ability` / `min_essence`, which is what a
page-image pass misreads, and the direction is not consistent (data both above and below
the page), so this is not one systematic off-by-one.

⚠ **Three of the `min_essence` rows are a DUPLICATION, not a misreading** — Peony Blossom
Attack, Summoning the Loyal Steel and Understanding the Court each have `min_essence` set
to a copy of their own (correct) `min_ability`, where the page prints a lower Essence.
Human's read, 2026-09-01, on being shown the first two.

## How this table was verified

The table was first built by reading the pages by eye — the same method that produced the
errors being audited — so it was then **re-derived mechanically**: a parser pulls every
`Minimum <X>:` / `Minimum Essence:` pair out of the extraction, keys it to the nearest
preceding heading and diffs it against `data/`. The script is not kept (it is 60 lines and
one-shot); what matters is the result and its two limits:

* ⚠ **It found one thing that is NOT a defect: Ox-Body Technique.** The page prints
  `Minimum Endurance: **Varies**`, and a non-numeric minimum makes the parser pair that
  block's Essence with the NEXT block's ability number. `min_ability: 1` in the data is a
  deliberate modelling choice for "Varies" (the Charm is bought once per Endurance dot),
  not an error. **Any future re-run of this audit will report Ox-Body again.**
* ⚠ **It could not locate 22 of the 222 blocks at all**, because a Charm-tree diagram or a
  page break splits them. Three table rows fall in that set and rest on a direct read of the
  page instead: Irresistible Questioning Technique (3/2), All-Encompassing Sorcerer's Sight
  (5/2) and Irresistible Salesman Spirit (5/3). **Silence from the audit is not agreement.**

Every non-minimum row (the 3 costs and 2 types) was confirmed by reading its printed
`Cost:` / `Type:` line directly.

| Charm | file | field | was | now (printed) |
|---|---|---|---|---|
| Trance of Unhesitating Speed | solar_archery | min_ability | 4 | **3** (p.155) |
| Fiery Arrow Attack | solar_archery | min_ability | 3 | **2** (p.156) |
| Peony Blossom Attack | solar_melee | min_essence | 3 | **1** (p.163) |
| Summoning the Loyal Steel | solar_melee | min_essence | 3 | **1** (p.164) |
| Glorious Solar Saber | solar_melee | min_ability | 4 | **3** (p.164) |
| Edge of Morning Sunlight | solar_melee | min_ability | 4 | **5** (p.166) |
| Fivefold Bulwark Stance | solar_melee | cost | `5 motes` | **5 motes, 1 Willpower** (p.167) |
| Precision of the Striking Raptor | solar_thrown | min_ability | 1 | **2** (p.168) |
| Harmonious Presence Meditation | solar_presence | min_ability | 1 | **3** (p.175) |
| Listener-Swaying Argument | solar_presence | cost | `2 motes per success, 1 Willpower` | **2 motes per die, 1 Willpower** (p.175) |
| Iron Skin Concentration | solar_resistance | min_ability | 1 | **2** (p.176) |
| Poison-Resisting Meditation | solar_resistance | type | `Simple` | **Reflexive** (p.179) |
| Irresistible Questioning Technique | solar_investigation | min_ability | 2 | **3** (p.186) |
| Unknown Wisdom Epiphany | solar_investigation | min_ability | 3 | **5** (p.186) |
| Ailment-Rectifying Method | solar_medicine | min_ability | 1 | **2** (p.188) |
| Celestial Circle Sorcery | solar_occult | cost | `1 Willpower (per spell…)` | **2 Willpower** (p.191) |
| All-Encompassing Sorcerer's Sight | solar_occult | min_ability | 2 | **5** (p.193) |
| Monkey Leap Technique | solar_athletics | min_ability | 2 | **1** (p.193) |
| Lightning Speed | solar_athletics | min_ability | 1 | **2** (p.193) |
| Unsurpassed (Sense) Discipline | solar_awareness | min_ability | 4 | **5** (p.196) |
| Reed in the Wind | solar_dodge | min_ability | 1 | **2** (p.197) |
| Seasoned Criminal Method | solar_larceny | min_essence | 2 | **1** (p.199) |
| Lock-Opening Touch | solar_larceny | min_essence | 2 | **1** (p.201) |
| Easily Overlooked Presence Method | solar_stealth | min_essence | 2 | **1** (p.201) |
| Insightful Buyer Technique | solar_bureaucracy | min_ability | 2 | **3** (p.203) |
| Consumer-Evaluating Glance | solar_bureaucracy | min_ability | 2 | **3** (p.203) |
| Irresistible Salesman Spirit | solar_bureaucracy | min_ability / min_essence | 3 / 2 | **5 / 3** (p.203) |
| Foul Air of Argument Technique | solar_bureaucracy | min_ability | 4 | **5** (p.205) |
| Twisted Words Technique | solar_linguistics | min_ability | 5 | **4** (p.207) |
| Depth-Plumbing Intuition | solar_sail | min_ability | 3 | **4** (p.210) |
| Mastery of Small Manners | solar_socialize | type | `Simple` | **Reflexive** (p.211) |
| Understanding the Court | solar_socialize | min_essence | 5 | **2** (p.212) |

## What this turned up on the way

* ⚠ **One test asserted a Charm description by literal substring, and it broke.**
  `test_sheet_shows_charm_and_spell_descriptions` matched `"Adds an extra die of damage"` —
  the old stub's wording — to prove the sheet renders descriptions at all. `bb5adae` had
  already fixed the *spell* half of the same test for the same reason a day earlier, and
  the Charm half was left pointing at text that was about to be rewritten. It now matches
  `"an additional die of damage"`, and was negative-controlled (break the data string, the
  test fails). **A render test keyed to content is a test that fails whenever the content
  improves** — the coupling is the finding, not the breakage.
* ⚠ **`git checkout <file>` destroyed 22 finished descriptions and nearly shipped the
  stubs back.** The negative control above works by mutating a data file; undoing that with
  `git checkout` restores to **HEAD**, not to the pre-probe state, and the file had an hour
  of uncommitted work in it. It was recovered only because the patch payload still existed
  in a scratchpad. **When a probe mutates a tracked file that holds uncommitted work, copy
  it aside first and restore from the copy** — never from git.
* **The description cap is still written into both artifact briefs** —
  `delegation-brief-artifacts.md` (line 86) and `-artifacts-2.md` (line 94), each
  "1-4 sentences", under which 330 artifacts were authored. **Raised and ruled on: the
  artifacts are fine and the cap stays** (human, 2026-09-01). Left as-is deliberately.

## Questions that were asked, and the rulings — CLOSED, do not reopen

All three were put to the human on 2026-09-01 and answered the same day. Recorded so the
answers are findable, **not** to be re-raised:

1. **The necromancy provenance** — ANSWERED, and it was a normalisation defect, not a
   missing citation. See the section below.
2. **Do the 330 artifacts need the audit the Core Charms just had?** — **NO.** *"No, looks
   fine."* The "1-4 sentences" cap stays in both artifact briefs. ⚠ Do not propose an
   artifact description audit again, and do not treat the cap's presence in those briefs as
   an open defect.
3. **The other splats' Charms and the `min_essence == min_ability` grep** — **NO**, they
   stand as they are. They are *not known clean*; that is accepted, not overlooked.

## The provenance error — FIXED, and it is the normalisation pass's fingerprint

**Shadowlands Circle Necromancy** and **Labyrinth Circle Necromancy** (`solar_occult.json`)
were attributed to `Core` pp.197 and 198. Those Core pages carry **Awareness and Dodge**;
there is no necromancy anywhere in the Core Charm chapter.

**The pages were right and the book was wrong.** The human's call (2026-09-01) — *"Check
Abyssals, same page. Books might've gotten fucked in the normalization passes"* — was
correct on both counts, and confirmed twice over:

* `abyssal_occult.json` already carries **Shadowlands Circle Necromancy p.197** and
  **Labyrinth Circle Necromancy p.198** against **The Abyssals**. Same Charms, same pages.
* **The Abyssals p.197 and p.198 read directly** (`--offset 1`, the book's own text layer)
  print exactly those two entries, at `1 Willpower / Occult 3 / Essence 3` and
  `2 Willpower / Occult 4 / Essence 4` — which is what the Solar copies already held. Only
  `source.book` was wrong.

Both now say `The Abyssals`, pages unchanged.

⚠ **This is the second instance of the same fingerprint.** The 1.0 catalogue sweep caught
**233 Abyssal Charms mis-attributed to `Exalted 1e Core` while carrying Abyssals page
numbers** (`catalogue-sweep.md`), and the diagnosis then was the same: **`source.book` is a
zero-read-site field, so nothing exercises it and it rots silently.** Two survivors of that
class were still in the tree fifteen months later, in a *different* splat's file.

⚠ **The tell is cheap and nobody was running it: a citation whose page does not contain the
Charm.** Both instances would have been caught by cross-checking book+page against the
extraction — which now exists for Core. **A `source` that no code reads is not
self-correcting; it needs a test or a sweep, and it has neither.** Whether one gets written
is the human's call, not a gap to close unasked.

## Printed oddities — recorded, nothing to fix

* **Judge's Ear Technique** (p.185) prints its stat block as `Minimum Ability: 2` /
  `Minimum Investigation: 1` — the labels are swapped or mislabelled in the book itself.
  The data's 2 / 1 is the sensible reading and was left alone.
* **Foul Air of Argument Technique** (p.205) prints no `Type:` line at all. Data says
  Simple; left alone.
* **Sandstorm-Wind Attack** (p.165) has its stat block interleaved with the Charm-tree
  diagram, and the two `Minimum` values do not survive extraction — no parse and no read
  can recover them from `images/_extracted/`. **CLOSED: the human confirmed 4 / 2 from the
  page (2026-09-01), which is what the data already holds.** Not a discrepancy, and not an
  open question — do not re-raise it as unverifiable.
* Printed spellings that differ from the data and were left as the data has them:
  "IRRESISTABLE QUESTIONING TECHNIQUE" (p.186), "IRRESISTABLE SALESMAN SPIRIT" (p.203),
  "WHIRLWIND BRUSH METHOD" in the p.206 tree vs "WHIRLING BRUSH METHOD" on its entry.
