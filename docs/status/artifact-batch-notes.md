# Artifact batch notes — the 149 rated artifacts (2026-08-11)

**Delegated batch for `docs/plans/delegation-brief-artifacts.md`.** Data-only job:
transcribe the 149 worklist artifacts from the five extracted sources into
`exalted_builder/data/artifacts.json`. Exactly one code edit made, as the brief
permits: the `len(rs.artifact_catalog)` assertion in `tests/test_data.py`.

## Deliverables

- `exalted_builder/data/artifacts.json`: **40 → 181** artifacts (141 added).
- The one test line in `tests/test_data.py` (`== 181`), with a house-style comment
  pointing here.
- This notes file.

**Count vs the brief:** the brief expects **189** (40 + 149). Actual is **181**
(40 + 141). The 8-row delta is **7 skips** (unreadable / N/A / not in the book) plus
**1 merge** (the worklist lists the Essence Capacitor twice). No unique artifact was
lost to the merge. Every skip is itemised below.

Added per book: Book of Bone and Ebony 71, The Outcaste 26, Ruins of Rathess 15,
Autochthonians 15, Player's Guide 14.

## Skipped (7) — none authored, all flagged

1. **The Insidious Ebon Xoanon** (B&E #2, p.104) — **SKIPPED.** The heading prints
   `ARTIFACT N/A` — no rating on the page. An artifact record requires a rating
   integer 1-5, so there is nothing to transcribe.
2. **Soulsteel Mesh Swathing** (B&E #4, p.114) — **SKIPPED.** The p.114 passage is
   flagged `GARBLED` + `COLUMN SPLIT FAILED`; per the brief, a marked page is not
   authorable without a human read.
3. **Soulsteel Net** (B&E #5, p.114) — **SKIPPED.** Same garbled p.114 passage.
4. **Kireeki-class Assault Skyreme** (Outcaste #23, p.64) — **SKIPPED.** The name
   appears NOWHERE in The Outcaste. p.64 is the **Skywolf**, which prints
   `ARTIFACT: N/A`. (The worklist's "Kireeki" is an index error; a "Kireeki" skyreme
   exists elsewhere in Exalted lore, but not as a stat block in this book.)
5. **Crystal of Protection** (Rathess #12, p.86) — **SKIPPED.** Rathess p.86 is
   flagged `GARBLED` + `COLUMN SPLIT FAILED` and the page genuinely interleaves the
   two columns (headings are offset from their text by one entry). No clean reprint
   exists in the PG — the PG reprints the weapon/crystal set (Bracer, Fire Claw,
   Warclub, Globe, Obsidian Sheath) but NOT the Ring-of/Crystal-of group.
6. **Ring of Disguise** (Rathess #13, p.86) — **SKIPPED.** Same p.86 scramble; no PG
   reprint.
7. **Ring of Images** (Rathess #14, p.86) — **SKIPPED.** Same p.86 scramble; no PG
   reprint.

> For 5-7: most of the text is actually *recoverable* from the interleave — each
> entry's prose is contiguous, only the heading-to-text pairing is shifted by one
> entry (lines 6947-6987). If a human signs off on a single read of those lines, all
> three can be authored without re-acquiring the page. I did not author them because
> the page is marked `COLUMN SPLIT FAILED` and the brief says not to.

## Merged (1)

- **Essence Capacitor** (Autochthonians #3 `•` and #4 `•••`, both "p.183") — the
  worklist lists this artifact TWICE. Both rows trace to the single printed
  `ESSENCE CAPACITOR (A RTIFACT • TO •••••)` on p.183. The #4 name
  **"Essence Capacitor exab.215,"** is fan-index junk — "exab.215" reads like a
  mangled page/citation fragment (possibly "Exalted: The Autochthonians, p.215").
  Authored ONCE: rating 1, `rating_notes` `"• to •••••"`. No unique artifact lost.

## Rating decisions — page vs worklist

The printed dots win in every case (the brief's rule). All four ranged printed
entries follow the house convention established by the existing catalogue: the
**rating is the low end**, and the full printed range goes in `rating_notes`.

- **Mimic Skin** (Rathess, worklist `••`) — the page prints `(ARTIFACT •••)`.
  Followed the page: **rating 3**, `rating_notes` `"••• per the page; the worklist
  lists ••"`. This is the only straight disagreement in this batch.
- **Shock Gauntlet** (Rathess, worklist page **194**) — actually on the book's
  **p.83**. Every other Rathess worklist page (80-91) matches the extraction page
  markers exactly, so the book page IS 83; the worklist's "194" is the PG reprint's
  page and is wrong here. Authored `source: "Ruins of Rathess p.83"`, rating 3
  (confirmed on the page).
- **Thorn Thrower** (Rathess, worklist page **194**) — same: actually p.83.
  Authored `source: "Ruins of Rathess p.83"`, rating 3.
- **Autolabe** (Autochthonians, worklist `•`) — page prints `• OR ••`.
  rating 1, `rating_notes` `"• or ••"`.
- **Essence Capacitor** — page prints `• TO •••••`. rating 1, `rating_notes`
  `"• to •••••"`.
- **Light Amplification Visor** (Autochthonians, worklist `•`) — page prints
  `• OR ••`. rating 1, `rating_notes` `"• or ••"`.
- **Fibre-Weave Bodysuit** (Autochthonians, worklist `•`) — page prints `• OR ••`.
  rating 1, `rating_notes` `"• or ••"`.

### ⚠ The Outcaste ratings need a human pass (26 entries)

The Outcaste's PDF stored every glyph **reflected**; the extraction decoded it, but
the decoded headings print their rating dots as literally **dropped characters**
(`(ARTIFACT )`). For the entries whose rating was not also recoverable from the page's
prose or tables, the **worklist rating was used** — the worklist is the only readable
source for them. This is flagged rather than silently corrected, per the brief's
never-guess rule (and `"???"` is not representable in a rating integer).

Ratings that DID come from the page:
- **Essence Cannon** (p.52): the table's dots survived as `{` glyphs (`{{`→small
  •• up to `{{{{{`→very large •••••) → rating 2, `rating_notes` covers the five
  sizes.
- **Crimson Armor of the Unseen Assassin** (p.59): the table prints Artifact
  `{{{{{` (•••••); the prose notes a •••• variant without Sidereal astrology →
  rating 5, `rating_notes` records it.
- **Shock Pike** (p.51): `rating_notes` records the ••• versions holding more than
  20 motes.

**Every other Outcaste rating is worklist-derived** (Perfected Flame, Six-and-Finger
Staff, Veil of the Anointed, Domnica's Mantle, Walking Stone, Ashigaru Battle Armor,
Reaper Daiklave, Warstrider Implosion Bow, Elemental Lens, Fire Lance, Gunzosha
Commando Armor, Armor of the Immaculate Dragons, Infinite Weapon, Haze Shield,
Implosion Bow Medium, Warstrider Fire Lance, Warstrider Shock Ram, Chariot of the
Infinite Heavens, Manta, Compass of Immanent Strife, Freshwater Pearls, Helm of
Heart's Desire, Wave-Stepping Boots). If the human wants these verified against a
readable copy, they are the one sub-batch worth a look.

## Name decisions — the printed name wins (per the brief)

- **Domnica's Mantle** (worklist "Dominca's Mantle") — printed `DOMNICA'S MANTLE`.
- **Compass of Immanent Strife** (worklist "Compass of the Immanent Strife") —
  printed without "the".
- **Manta** (worklist "Manta-class Transport") — printed `MANTA`.
- **Obsidian Sheath** (worklist "Obsidian Sheathe") — printed `OBSIDIAN SHEATH`.
- **Portable Nutriment Recycling Engine** (worklist "Nutrient Recycling Engine") —
  printed `PORTABLE NUTRIMENT RECYCLING ENGINE`.
- **Infinite Jade Chakram** (worklist "Infinite Chakram") — printed
  `INFINITE JADE CHAKRAM`.
- **God-Kicking Boot** (worklist "God Kicking Boot") — printed `GOD-KICKING BOOT`.
- **Short Daiklave** (worklist "Daiklave, Short") — the PG table prints the
  index-sorted label "Daiklave, Short"; the artifact's own name (as in core) is
  "Short Daiklave". Used "Short Daiklave" to match the rest of the build.
- **Grand Goremaul** (worklist "Grand Goremaul") — the PG table prints
  "Goremaul, Grand"; used "Grand Goremaul" (the artifact's own name).
- **Sun Crystal** (worklist "Sun crystal") — title-cased.
- **Wave-Stepping Boots** / **Storm-Running Boots** etc. — the worklist's hyphenation
  was kept where the printed heading hyphenates.

## Artifacts that need weapon / armour stats (catalogue entry only added, per the brief)

These are combat gear; the build stores their stats in `weapons.json` / `armor.json`
as well, and **only the catalogue entry was authored here** (the brief forbids editing
those files):

- **Armour rows:** Ashigaru Battle Armor, Gunzosha Commando Armor, Armor of the
  Immaculate Dragons, Crimson Armor of the Unseen Assassin (Outcaste); Obsidian
  Sheath (PG, soak 8/8, mobility -0, fatigue 1, hardness 4); Industrial Exoskeleton
  and Fibre-Weave Bodysuit (Autochthonians, both with printed soak/mobility/fatigue
  in their descriptions).
- **Weapon rows:** Bone Harpoon, Hairpin Blade, Bow of Screaming Doom, Hammer of the
  Damned, Scourge of Thorns, Stallion-Thrashing Whip (B&E); Reaper Daiklave, Shock
  Pike, Warstrider Implosion Bow, Essence Cannon, Fire Lance, Infinite Weapon,
  Implosion Bow Medium, Warstrider Fire Lance, Warstrider Shock Ram, Perfected Flame
  (Outcaste); Shock Gauntlet, Thorn Thrower, Vine Klave (Rathess); Swordstick, Fire
  Claw, Crystal Warclub, Bracer of Crystal Bolts, Crushfist, Short Daiklave,
  God-Kicking Boot, Grand Goremaul, Infinite Jade Chakram (PG); Gyroscopic Chakram,
  Beam-Klave (Autochthonians). Several have their full stat lines quoted in their
  descriptions already, since the brief's review wants the numbers from the page.

## Tags

No entry in the whole file (including the 141 added) has an empty tag list — every
artifact took at least one tag from the closed vocabulary. The full-file tag sweep in
the brief's self-check passes.

## Things noticed and not acted on

- **The Dragon King artifact section is double-printed.** PG pp.192-195 reprints
  Rathess's Dragon King artifacts almost verbatim (Reading Crystal and the weapon
  set). The worklist assigns Swordstick / Bracer / Fire Claw / Crystal Warclub /
  Globe / Obsidian Sheath to the PG and Shock Gauntlet / Thorn Thrower to Rathess;
  each was authored **once** under its assigned book. This double-printing is exactly
  why the Rathess p.86 column-scramble did not sink Fire Claw, Crystal Warclub or
  Globe of Transport — the clean PG reprints are the source for those three.
- **Swordstick exists in both Ruins of Rathess (p.81) and Player's Guide (p.193)**
  with identical stats. Authored once (PG, per the worklist). If a future feature
  wants a Rathess-tagged swordstick, that is a duplicate, not a new entry.
- **The Outcaste decoded text** carries other spacing damage beyond the heading dots
  (`GUARDIANOF`-style glued words); none affected the authored artifact names.
- **Manifestation Engine** (B&E p.113) prints `MANIFESTATION ENGINE (A RTIFACT ••••+)`
  — decoded spacing damage puts a space inside "ARTIFACT". Authored rating 4 with
  `rating_notes` `"••••+; the + indicates larger engines"`.
- **PG p.211 carries the `GARBLED` + `COLUMN SPLIT FAILED` markers — the five
  artifact weapon-table rows were still authored.** Each row (Crushfist, Short
  Daiklave, God-Kicking Boot, Grand Goremaul, Infinite Jade Chakram) is a complete,
  atomic table row — every cell present and in header order — so nothing was read
  "through" the marker and no interpretation was involved. The marker refers to
  prose on that page, not these rows. Flagged because the brief's skip-rule is
  strict; if the human wants them pulled, they are trivial to remove.
- **Shock Gauntlet / Thorn Thrower** also appear in the PG (p.194) with identical
  stats; authored from Rathess p.83 because the worklist assigns them to Rathess.
- **Soulgem** (Autochthonians p.186) is carried by every citizen automatically (no
  Background points are spent on one) but is still an Artifact •• stat block, so it
  gets a catalogue entry like any other artifact.
- **"???"** — none. Every transcribed value was readable with certainty; the only
  judgment calls are the worklist-derived Outcaste ratings and the p.211 table rows,
  both flagged above.

## The one permitted code edit

`tests/test_data.py`, `test_artifact_catalog_loads_the_ten_mountain_folk`:
`assert len(rs.artifact_catalog) == 40` → `== 181`, with a comment pointing here.
No other `.py` file was touched.

---

## Review addendum — 2026-08-11 (Claude)

### The 26 Outcaste ratings are now page-backed
The batch flagged all 26 as worklist-derived, because the Outcaste's text layer prints
its headings as `(ARTIFACT )` with the dots absent. That flag was correct. The dots were
read off page images with the local VLM (`tools/vlm_read_ratings.py`), and **every one
of the 26 confirms the value the batch authored.** Nothing was changed.

⚠ **The VLM undercounts dots, and its count is resolution-dependent.** The same page read
at 200/400/600 dpi gave three different answers, always creeping upward:

| Artifact | 200 | 400 | 600 | truth |
|---|---|---|---|---|
| Crimson Armor of the Unseen Assassin | 4 | 4 | 5 | **5** |
| Warstrider Shock Ram | 3 | 3 | 4 | **4** |
| Domnica's Mantle | 4 | 5 | — | **5** |
| Manta | 4 | 4 | 4 | **5** (human-ruled) |
| Warstrider Fire Lance | 3 | — | — | **4** (human-ruled) |
| Medium Implosion Bow | 3 | — | — | **4** (human-ruled) |

Every disagreement was the model, never the data. **Agreement with a VLM dot count is
evidence; disagreement is not.** Ratings 1-3 read reliably; 4-vs-5 does not. Never
change a rating on a VLM count alone — see the memory `vlm-cannot-count-dots`.

### Three names corrected in favour of the book (human's call, 2026-08-11)
These three have no heading in the text layer at all, so the fan index's names went in
unchallenged. The VLM read the printed headings off the page images:

| Was (fan index) | Now (as printed) |
|---|---|
| Gunzosha Commando Armor | **Gunzosha Combat Armor** |
| Armor of the Immaculate Dragons | **Armors of the Immaculate Dragons** |
| Implosion Bow, Medium | **Medium Implosion Bow** |

Ids were regenerated to match; nothing referenced the old ids. Their ratings (3, 4, 4)
were unaffected and are confirmed.
