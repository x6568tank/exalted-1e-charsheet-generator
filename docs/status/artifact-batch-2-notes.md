# Artifact batch 2 notes — the last 15 authorable artifacts (2026-08-11)

**Delegated batch for `docs/plans/delegation-brief-artifacts-2.md`.** Data-only job:
transcribe the 23 worklist artifacts from six extracted sources into
`exalted_builder/data/artifacts.json`. Exactly one code edit made, as the brief permits:
the `len(rs.artifact_catalog)` assertion in `tests/test_data.py`.

## Deliverables

- `exalted_builder/data/artifacts.json`: **181 → 196** artifacts (**15 added**).
- The one test line in `tests/test_data.py` (`== 196`), with a house-style comment
  pointing here.
- This notes file.

**Count vs the brief:** the brief expects **204** (181 + 23). Actual is **196**
(181 + 15). The 8-row delta is **all skips** — 3 already in the catalogue (batch 1),
1 not in the source book at all, 1 duplicate, 1 `ARTIFACT N/A`, and 3 on a page whose
extraction is still flagged `COLUMN SPLIT FAILED`. No unique artifact was lost to a
merge. Every skip is itemised below.

Added per book: Exalted Core 8, Savant and Sorcerer 5, Book of Bone and Ebony 2.

## Skipped (8) — none authored, all flagged

1. **The Insidious Ebon Xoanon** (B&E, worklist `n/A`, p.104) — **SKIPPED.** The heading
   prints `ARTIFACT N/A` — no rating on the page. An artifact record requires a rating
   integer 1-5, so there is nothing to transcribe. Same reason batch 1 skipped it.
2. **Kireeki-class Assault Skyreme** (Outcaste, worklist `n/A`, p.64) — **SKIPPED.**
   The name appears NOWHERE in `The Outcaste.md`. Worklist page 64 is the **Skywolf**
   (prints `ARTIFACT: N/A`), and no "Kireeki" string exists anywhere in the file. Same
   index error batch 1 recorded.
3. **Crystal of Protection** (Rathess #1, p.86) — **SKIPPED.** ⚠ see the p.86 note below.
4. **Ring of Disguise** (Rathess #2, p.86) — **SKIPPED.** Same.
5. **Ring of Images** (Rathess #3, p.86) — **SKIPPED.** Same.
6. **Daiklave, Short** (Player's Guide, p.211) — **SKIPPED — ALREADY IN THE CATALOGUE.**
   Exists as `artifact.players-guide.short-daiklave`, rating 2, source "Player's Guide
   p.211" (batch 1 authored it under the artifact's own name "Short Daiklave", per the
   batch-1 name decision). Not a duplicate — the worklist row is simply already done.
7. **Implosion Bow, Medium** (Outcaste, worklist `••••`, p.59) — **SKIPPED — ALREADY
   IN THE CATALOGUE.** Exists as `artifact.outcaste.medium-implosion-bow`, rating 4,
   source "The Outcaste p.59" (batch 1 renamed the fan index's "Implosion Bow, Medium"
   to the printed "Medium Implosion Bow"; rating 4 was VLM-read off the page and
   human-ruled).
8. **Manta-class Transport** (Outcaste, worklist `•••••`, p.63) — **SKIPPED — ALREADY
   IN THE CATALOGUE.** Exists as `artifact.outcaste.manta`, rating 5, source "The
   Outcaste p.63" (batch 1 used the printed name "Manta"; rating 5 human-ruled after a
   VLM undercount).

> Items 6-8 mean a third of the worklist was stale: batch 1 already shipped those
> pages. The current brief was written against the same fan index, not the catalogue.

## Ratings — all 15 authorable entries are page-backed, no `???`, no disagreements

Every authored rating was read off the printed dots / `�`-count in the source:

| Entry | Rating | Source of the value |
|---|---|---|
| Charm against Disease | • | TALISMANS section header `*RESOURCES VARY OR ARTIFACT �+` (one `�`); worklist agrees |
| Dragon Tear Tiara | •• | heading `DRAGON TEAR TIARA *ARTIFACT ��+` (two `�`); worklist agrees |
| Good Luck Charm | • | TALISMANS section header; worklist agrees |
| Hearthstone Amulet | • | heading `HEARTHSTONE AMULET *ARTIFACT �+`; worklist agrees |
| Walkaway | • | TALISMANS section header; worklist agrees |
| Warding Charms | • | TALISMANS section header; worklist agrees |
| Hearthstone Bracers | •• | heading `HEARTHSTONE BRACERS *ARTIFACT ��+`; worklist agrees |
| Slayer Khatar | •• | heading `SLAYER KHATAR *ARTIFACT ��+`; worklist agrees |
| Collar of Dawn's Cleansing Light | • | `(ARTIFACT •)` printed; worklist agrees |
| Mask | •• | `(ARTIFACT ••)` printed; worklist agrees |
| Ring of Being | •••• | `(ARTIFACT ••••)` printed; worklist agrees |
| Wings of the Raptor | •••• | `(ARTIFACT ••••)` printed; worklist agrees |
| Soul Mirror | ••••• | `(ARTIFACT •••••)` printed; worklist agrees |
| Soulsteel Net | •••• | printed in prose: "these nets count as Artifact •••• items"; worklist agrees |
| Soulsteel Mesh Swathing | ••••• | printed in prose: "requires Resources (or Artifact) •••••"; worklist agrees |

**No `�`-count vs worklist disagreements** were found. Every core `�`-count matched its
worklist rating, so no `rating_notes` were needed and none were written.

## Name decisions — printed wins over the worklist

- **Collar of Dawn's Cleansing Light** (worklist "Collar of Cleansing Light") —
  the printed heading is `COLLAR OF DAWN'S CLEANSING LIGHT`.
- **Medium Implosion Bow** / **Manta** / **Short Daiklave** — already handled by batch 1
  (see skips 6-8); no new names authored.
- The four core talismans (**Charm against Disease, Good Luck Charm, Walkaway,
  Warding Charms**) have **no printed artifact heading** — they are subsections of the
  TALISMANS section. The names come from the worklist, and the page text introduces
  them as classes, not single named items ("a charm against disease", "good luck
  charms", "walkaways", "warding charms"). Per the brief, I authored what the page
  describes and note here that these are generic classes, not specific artifacts.
  Similarly **Mask** (S&S) is a class of ivory face masks rather than a single named
  item.

## ⚠ Ruins of Rathess p.86 — the brief's "re-extracted" claim does not hold

The brief's trap 4 says p.86 "has since been re-extracted in correct reading order."
**The file still carries both markers and is still interleaved:**

```
<!--GARBLED p.86: ... NOT authorable without a human read-->
<!--COLUMN SPLIT FAILED: ... NOT authorable without a human read.-->
```

and the text visibly interleaves the two columns (e.g. line 6932 runs a Fire Claw
fragment into a Crystal of Protection fragment). Per the brief's skip-rule for marked
pages, the three entries are not authored. **This is the second batch to skip them for
exactly this reason.**

The good news: batch 1's assessment still holds — **the text is recoverable.** Each
entry's prose is contiguous and complete; the interleave only mixes the columns
line-by-line. For a single human read, my reassembly:

- **Crystal of Protection (ARTIFACT •••)** — fist-sized crystal statue of a tyrant
  lizard or other dangerous reptile; placed on a solid surface and fed 7 motes it
  produces a hemispheric dome of softly glowing sunfire, 4 yards in diameter and 2
  high, light equal to late twilight; keeps wind, rain and cold off anyone inside;
  anyone outside attempting to enter takes 5L Essence burns (armor does not protect,
  only natural soak); protects against ranged attacks equal to 75 percent cover
  (subtract three from the successes of any ranged attack); no protection against
  hand-to-hand; lasts until anyone inside leaves or a full day passes, then collapses
  until exposed to sunlight for at least half a day; often attached to saddles or worn
  as large pendants.
- **Ring of Disguise (ARTIFACT •••)** — orichalcum ring set with a transparent violet
  stone; resizes to fit any mortal or Dragon King hand on committing 4 motes; projects
  intangible illusions around the wearer, each costing 8 motes and lasting a scene
  (another 8 motes to continue); can create an illusion of any person, Dragon King or
  other human-shaped creature the wearer is familiar with, but it is only visual — the
  wearer smells and sounds the same, and touching reveals the difference (such as a
  Dragon King disguised as a human).
- **Ring of Images (ARTIFACT ••)** — jade ring set with a small amber stone; projects
  small illusions of anything the wearer can imagine up to (permanent Essence) yards
  away, no larger than a large house cat, solely visual and auditory (no scent,
  intangible); one illusion at a time, 1 mote per 15 minutes to sustain; creating
  requires a normal action, moving and directing are reflexive.

All three ratings printed on the page (**•••, •••, ••**) match the worklist. If the
human signs off on the reconstruction, all three can be authored without re-acquiring
the page.

## Book of Bone and Ebony p.114 — authored despite the GARBLED marker

p.114 carries `<!--GARBLED p.114: 1 line(s) with broken glyph spacing ... NOT authorable
without a human read-->`. Batch 1 skipped the two soulsteel entries on that basis. I
authored them because: (a) this brief **re-lists both as authorable-now**, and
(b) the single broken line is at the top of the page (a maelstrom-barge sidebar); the
**SOULSTEEL MESH** sidebar I transcribed reads cleanly — every sentence is coherent and
both ratings are printed inside its prose, so nothing was read "through" the marker. If
the human wants them pulled, they are trivial to remove.

## The Direlance (core p.341) — closed: no standalone entry

p.341 is weapon-class prose — daiklaves, grand daiklaves, reaver daiklaves and the
"dire lances (spears)" similar-weapons class, flowing straight into the p.342 weapon
stat table (`Dire Lance*` row). **There is no standalone Direlance artifact entry on the
page.** Nothing authored, which closes the long-open question. The `Dire Lance*` gear
row already lives in the weapon catalogue (`weapon.melee.direlance`, batch 1). The
existing test assertion `"artifact.core.direlance" not in rs.artifact_catalog` remains
true.

## The Outcaste headings drop their rating dots (nothing new, already resolved)

Every `(ARTIFACT )` heading in The Outcaste's decoded text prints blank — the dot glyphs
were dropped in extraction. All three Outcaste worklist rows were either already in the
catalogue with page-backed ratings (batch 1's VLM pass + human rulings: Medium Implosion
Bow ••••, Manta •••••) or not in the book (Kireeki). Nothing new to author here.

## The one permitted code edit

`tests/test_data.py`, `test_artifact_catalog_loads_the_ten_mountain_folk`:
`assert len(rs.artifact_catalog) == 181` → `== 196`, with a comment pointing here.
No other `.py` file was touched.

## ⚠ One reported failing test I did NOT edit (per the brief)

The suite has **two** failures, not the brief's expected one:

1. `test_merits_flaws.py::test_every_description_matches_the_source_text` — the known,
   machine-specific failure (46 Godblooded entries, red only where the CH2 file is
   present). Not mine.
2. `tests/test_data.py::test_the_gear_artifact_rows_from_the_backlog_batch`, line ~426:
   `assert "artifact.core.slayer-khatar" not in rs.artifact_catalog` — **this assertion
   is now false because this brief mandates authoring the Slayer Khatar.** Batch 1 wrote
   it while the Khatar was blocked ("no description on disk"); the core text layer has
   since been decoded and the Khatar's description is on p.344. Per the brief's rule
   ("any *other* failing test is a real defect: report it, do not edit it"), I am
   reporting it rather than editing it. The fix is to drop the `slayer-khatar` half of
   that assertion (and update the surrounding "two blocked core items" comment); the
   `direlance` half stays true.

## Things noticed and not acted on

- **Charm against Disease's heading sits on p.336 but its effect text flows onto
  p.337.** I sourced it `Exalted Core p.336` (where the heading/talisman begins), per
  the worklist. The other three core talismans are fully on p.337.
- **Hearthstone Bracers** (p.338) is the last entry before the Hearthstones chapter —
  correctly on p.338 per the worklist.
- The core `�`-count mechanic worked exactly as the brief promised: one `�` per dot,
  and every count agreed with the worklist, so no entry needed a human read.
- No tag list is empty; every new entry took at least one tag from the closed
  vocabulary. The full-file self-check passes.
- The Savant and Sorcerer `¥`-level and `(A RTIFACT •)`-style spacing damage did not
  affect any name or rating.

---

## Review addendum — 2026-08-11 (Claude)

**Verified:** scope clean (only `artifacts.json` + the one permitted test line); 196
entries, ids unique, ratings integers 1-5, tag vocabulary closed; loads cleanly.
**All 15 ratings trace to the page — zero errors.** The four core minor items sit under
a shared `RESOURCES VARY OR ARTIFACT •` heading; `SOUL MIRROR (ARTIFACT •••••)`,
`WINGS OF THE RAPTOR (ARTIFACT ••••)` and the Mask's `(ARTIFACT ••` confirm the rest.
The `�`-per-dot rule held on every core entry.

### The batch was right about my brief — Rathess p.86 was NOT re-extracted
The brief claimed that page had been re-extracted in correct reading order. **It had
not.** It still carries both a `GARBLED` and a `COLUMN SPLIT FAILED` marker and its two
columns are still welded line by line. Skipping its three entries was correct, and the
reassembly left in these notes is the right handoff. **The markers did their job**; the
brief's prose was the unreliable part.

### ⚠ The reviewer nearly deleted two valid records
`Soulsteel Net` and `Soulsteel Mesh Swathing` appear nowhere in Bone & Ebony as
`(ARTIFACT …)` headings, and a heading-shaped search says they do not exist. They do:
p.114 rates them **in prose** — *"these nets count as **Artifact ••••** items"* and
*"requires **Resources (or Artifact) •••••** to purchase"*. The batch reported exactly
this ("in-prose ratings") in its handback and the reviewer did not connect it before
running a search that could not have found them.

**The lesson, which is now four-for-four this session:** a search shaped like the thing
you expect proves nothing about a thing shaped differently. Absence of a *heading* is
not absence of an *entry*. Same error as searching for a Charm name and landing on its
first passing mention.

### Stale assertion fixed
`test_the_gear_artifact_rows_from_the_backlog_batch` asserted both blocked core items
were absent. The Slayer Khatar is now authored (p.344 decoded), so that half was stale;
it now asserts presence. **The Direlance half stays — and is now a finding rather than a
gap:** p.341 carries only weapon-class prose and the p.342 stat table, so no standalone
entry exists to author. That long-open question is closed.

### Where this leaves the artifact track
196 authored. Every artifact readable from text on disk is now in the build; everything
that remains needs a page sync. Still outstanding and NOT authorable: the three Rathess
p.86 entries (marker), `Insidious Ebon Xoanon` (prints `ARTIFACT N/A`),
`Kireeki-class Assault Skyreme` (name absent from The Outcaste — p.64 is the Skywolf).
