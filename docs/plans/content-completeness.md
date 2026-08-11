# Plan — content completeness (the 1.0 catalogue sweep)

**Recorded 2026-08-10 (human's ask).** Not scheduled, not started. This is the
**catalogue-completeness half of 1.0**: every splat's mechanics are shipped and
browser-verified, but the three big content catalogues — **Charms/Arcanoi**, **spells**
and **artifacts** — hold only what the pages on disk supported at the time each splat
was built. This plan is the sweep that closes them.

Three tracks, each keyed to a **discovery index** the human supplies:

| # | Track | Discovery index | Index on disk? |
|---|---|---|---|
| 1 | Charms + Arcanoi | `charmtrees-20060324.pdf` | **YES** ⚠ in the `-ds` worktree |
| 2 | Spells | `Ledaal Pongwin's Grand List of Spells and Protocols.md` | **YES** ⚠ in the `-ds` worktree |
| 3 | Artifacts | `docs/status/artifact-backlog-entries.md` | **YES — already built** |

> ⚠ **All three indexes live in the `deepseek-experiment` worktree**, not this one:
> `/home/gil/Projects/Exalted 1E Charsheet Generator-ds/images/`. `images/` is
> gitignored, so it does not travel between worktrees any more than it travels between
> machines. **Look there before concluding an index is missing** — the `-ds` copy of
> `images/` is also fuller than `main`'s (e.g. its `Non-Exalts/` tree). The human put
> them there by accident 2026-08-10; whether they get copied to `main`'s `images/` or
> read in place is a housekeeping call, not a blocker either way.

## ⚠ The rule that governs all three tracks

**A discovery index is a discovery index, never a source of values.** This was settled
for artifacts (`docs/status/artifact-backlog.md`: *"Values still come from the real
pages — the guide is book+page discovery only"*) and it extends unchanged to the charm
trees and the spell masterlist. The index answers *what exists and on which page*.
Every cost, minimum, prerequisite, duration and line of description still comes from a
human-supplied page image or pasted `.md` (CLAUDE.md → *Workflow expectations*).

Two consequences worth stating before anyone starts:

- **Reading the `sources/` PDFs is still forbidden**, including the charm-trees PDF.
  The human syncs it into `images/` — as page images, or as pasted text where it is
  text-selectable. The charm trees are boxes-and-arrows diagrams, so they are
  **screenshot territory**, not paste territory.
- **A gap the index names but no page covers is BLOCKED, not authorable.** Record it in
  the track's queue and move on. That is exactly how the artifact backlog behaves today.

## Baseline — what the build holds right now (2026-08-10)

Measured, not remembered.

### Charms + Arcanoi — 1,709 entries in `exalted_builder/data/charms/`

| Splat | Entries | Notes |
|---|---|---|
| Solar | 313 | 25 abilities + 5 MA styles (incl. Tiger / Praying Mantis / Ebon Shadow / Falling Blossom) |
| Lunar | 217 | Attribute-keyed, not ability-keyed |
| Abyssal | 236 | |
| Dragon-Blooded | 316 | 25 abilities + 5 Dragon paths + Jade Mountain |
| Sidereal | 183 | 25 abilities + 4 Sidereal MA styles |
| Alchemical | 121 | |
| Mountain Folk | 94 | five Patterns |
| Ghost Arcanoi | 56 | six Arcanoi |
| Spirit templates | 80 | the Godblooded spirit catalogue |
| Godblooded / Dragon-Kings | 9 | heritage + path bolt-ons |

### Spells — 92 in `exalted_builder/data/spells.json`

| Tradition | Circles |
|---|---|
| Sorcery | Terrestrial 16, Celestial 9, Solar 6 |
| Necromancy | Shadowlands 9, Labyrinth 7, Void 7 |
| Alchemical | Man-Machine 23, God-Machine 15 |

The 1E spell books most likely to hold the gap: **Book of Three Circles**, **Savant &
Sorcerer**, the Player's Guide. None of their spell pages are on disk (the artifact
backlog verified this for their artifact pages; the same books, same absence).

### Artifacts — 40 in `exalted_builder/data/artifacts.json`

The discovery layer for this track is **already built and the on-disk slice is
EXHAUSTED**: 749 index entries → 417 with a 1E ref → 360 unique names, spread over 28
books, of which only the four Caste Books (Dawn/Night/Twilight/Zenith/Eclipse) had
pages. **~320 named artifacts are blocked purely on page sync.**

## Track 3 — artifacts (start here; it is the only track that can start)

The work is already queued per-book in `docs/status/artifact-backlog-entries.md`. The
whole track is **page-sync-bound**, so it proceeds book by book, largest first:

| Book | Unblocked entries | Pages needed |
|---|---|---|
| Bone & Ebony | 74 | 58-79, 104, 113-114 |
| Outcastes | 27 | 50-54, 58-59, 62-64, 92, 121-122 |
| ~~Fair Folk (non-MF ch.)~~ | ~~27~~ | **OUT OF SCOPE 2026-08-10** |
| core | 24 | 336-338, 340 (341/343-345 partial) |
| Ruins of Rathess | 18 | 80-84, 86-88, 91, 194 |
| Autochthonians | 17 | 182-190 |
| Abyssals | 16 | 254-261 |
| Book of Three Circles | 14 | 24-27, 92-96 |
| Player's Guide | 14 | 192-195, 211 |
| …18 further books | ~90 | see the entries doc |

**Syncing one book unblocks its whole share at once** — that is the unit of work, and it
is why this track is cheap per-entry once pages land. Two entries stay blocked
regardless (Direlance catalogue entry, Slayer Khatar) — their description pages are the
wrong crops.

⚠ **Fair Folk artifacts (pp.205-211, 27 entries) are OUT OF SCOPE — human's ruling,
2026-08-10, after reviewing the entries.** They are "similarly game-changing to the
normal Fair Folk rules", so they follow their splat out under decision 0010. **This is
closed, not deferred — do not re-ask, do not author them, and do not count them in this
track's totals.** Fair Folk pp.205-211 are no longer a page sync anyone needs.

This does **not** retract the Fair Folk book as a *source*: the ten Mountain Folk
artifacts from pp.279-283 stay, and Mountain Folk **Charms** printed in that book stay.
The distinction is Fair Folk *content*, not the book it is bound in.

## Track 1 — Charms + Arcanoi: **THE DIFF IS DONE (2026-08-10)**

### The index
**`charmtrees-20060324.pdf`** — *Exalted® First Edition Charm Trees*, 24 Mar 2006, **by
the same author (Wordman) as the artifact guide**, built the same way ("assembled by
Wordman using XML, Python and dot"). 190 pages, one `<Splat>: <Ability>` tree per page,
every Charm box carrying `Min, Ess book.page`. **Born-digital text**, so it was parsed
deterministically with pdfplumber — the artifact precedent exactly
(`docs/status/artifact-backlog.md` → *The parse*), for the same reason: re-OCRing clean
text adds hallucination risk for zero gain.

**Parse method:** words → visual rows → segments split on x-gaps; find stat segments by
regex, then walk upward gathering x-overlapping segments as that box's name. Validated
against a hand-read page (Abyssal: Archery → 11 boxes, matching both the page and the
build exactly). **189 trees, 2,184 Charm boxes.**

### The gap: **179 Charms/Arcanoi missing** (Fair Folk excluded)

Of 1,953 in-scope boxes: **1,694 exact name matches, 80 name variants, 179 genuine
gaps.** Getting to that number took three passes, and the corrections are the most
useful thing in this section.

**⚠ A name-only diff massively overstates the gap. The first pass said 278.** What
turned out not to be gaps:

- **19 were already in the build, in a file the splat mapping didn't expect** — 9 Spirit
  boxes live in `elemental_powers.json`, 7 Ghost boxes in
  `godblooded_death_in_life.json`, plus `Ox-Body Technique` and two
  `Shadowlands Circle Necromancy` cross-listings. **The house rule in diff form: absent
  from the file you expected is not absent from the build.** Diff the whole catalogue
  first, attribute second.
- **52 are typos in the tree PDF, where the build is right** — `Mulit-Limb Frame`,
  `Aura-Dampending Component`, `Relevatory Sight`, `Graceful Toroise`,
  `Yeilding Spirit Form`, `Earth Yeild Abundance`. ⚠ **Never "correct" the build toward
  the tree.** The tree is a fan index; the build was authored from pages.
- **28 are the build's PARAMETERISED entries**, and this is the class that fooled the
  first pass hardest. **The build deliberately stores one record where the trees print
  one box per variant** — `Keen (Sense) Technique`, `(Sense)-Riding Technique`,
  `Mantle of (Element) Invulnerability`, `(Element) Protection Form`,
  `Auspicious Prospects for (Caste)`, `Exalt Ways`. Five tree boxes, one build record.
  **Do not split these into duplicates**; that would silently double-charge the player.

**Matching rule that produced the final number** — a box is a gap only if it fails
*both*: (a) fuzzy ≥0.86 against the whole catalogue, and (b) fuzzy ≥0.75 against Charms
the build attributes to the *same book*. Every build Charm carries a source book+page,
which makes (b) possible. **Page-anchoring alone is not sufficient either** — the four
`-Bolstering Meditation` Charms are cited at p.254 by the tree and p.247 by the build,
so a ±3-page window still missed them. Book-level, not page-level, is the reliable anchor.

**The Mountain Folk case is the worked example.** The first pass flagged 7 MF Charms as
missing; the true number is **1**. Five were the parameterised `Fivefold … Jade`
entries, one was a tree typo, and only `Heart of Chaos` (fair.247) has no counterpart.
When a shipped, browser-verified splat appears to be missing content, **the diff is the
thing more likely to be wrong.**

### Missing by book — all 179 resolved to a source

| Book | Missing |
|---|---|
| **bone — Book of Bone and Ebony** | **70** |
| **play — Player's Guide** | **57** |
| luna — The Lunars | 17 |
| seas — Savage Seas | 10 |
| abys — The Abyssals | 7 |
| outc — The Outcaste | 6 |
| game — Games of Divinity | 4 |
| time — Time of Tumult | 3 |
| core, dbld, fair | 5 |

### Where the gap actually is

| Tree group | Missing | Source |
|---|---|---|
| **Ghost (Arcanoi)** | **71** | Bone & Ebony |
| **Celestial Martial Arts** | **35** | Player's Guide |
| Lunar | 20 | The Lunars |
| Solar | 17 | Savage Seas, Time of Tumult, core |
| **Terrestrial Martial Arts** | **14** | Player's Guide |
| Terrestrial (Dragon-Blooded) | 9 | Outcaste, DB |
| Abyssal | 7 | Abyssals 203-205 |
| Spirit | 5 | Games of Divinity 4, PG 1 |
| Mountain Folk | 1 | `Heart of Chaos` (fair.247) |
| **Sidereal** | **0** | — fully authored |

**Two books hold 127 of the 179.** Four findings worth acting on:

1. **The Ghost catalogue is less than half authored.** 56 Arcanoi in the build, 71
   missing, all from **Book of Bone and Ebony**. Ghosts shipped from the E:Ab pages
   alone; B&E is *the* Arcanoi book and was never available. This is the single largest
   content hole in the build.
2. **Martial Arts is the second hole — 49 Charms, every one from the Player's Guide.**
   Ten Celestial MA trees and four Terrestrial MA trees the build has never seen. The MA
   styles that *are* in the build came from the castebooks and the DB books.
3. **The shipped splats are in better shape than the raw diff suggested.** Sidereal is
   **complete** (0 missing), Mountain Folk is missing exactly **1**, Alchemical 0,
   Abyssal 7 — and the Abyssal seven are a single coherent block (`Enhanced (Attribute)
   Discipline` and the `Superior/Incomparable (Sense)` sets, abys.203-205), which given
   the parameterised-entry pattern above may itself be fewer records than it looks.
   **Check whether the build wants these as parameterised entries before authoring
   eight.**
4. **The 231 Fair Folk Charm boxes across 24 trees are excluded and stay excluded** —
   decision 0010, closed, and now reinforced by the human's 2026-08-10 ruling on Fair
   Folk artifacts. Mountain Folk Charms printed in that book remain in scope: the book
   is not the splat.

### Remaining work on this track
- [ ] sync **Book of Bone and Ebony** (Arcanoi) and the **Player's Guide** MA chapters
- [ ] author per book — standard loop (`docs/adding-a-splat.md`,
      `tools/CHARM_AUTHORING_SPEC.md`), then `tools/validate_charms.py`, then the
      `preflight` skill before any click-through
- [ ] MA styles need **style→category wiring** (`martial_arts:<slug>`), not just records
      — see `docs/adding-a-splat.md`; a records-only import will look complete and not be

### The trees are also an AUDIT, not only a discovery index
Every box carries `Min, Ess book.page`, and the tree's edges are the **prerequisite
graph** — so this PDF is a check on the 1,709 Charms already shipped, not just a list of
the 179 missing. **Treat any tree-vs-data disagreement on a prerequisite or a minimum as
a question for the human, never a fix to apply.** AND-of-OR prerequisites are an
architectural invariant (`docs/ARCHITECTURE.md`), the tree is fan-made, and it has
already demonstrated a ~2.4% error rate on names — assume comparable on edges. Extracting
the edges is additional work the name diff did not do.

## Track 2 — spells: **STEP 2 IS DONE, the diff is below**

The masterlist is *Ledaal Pongwin's Grand List of Spells and Protocols* — a fan index in
exactly the shape this plan wants: `name | book code | page`, grouped by circle, with a
book-code legend. **295 entries.** The diff against the build's 92 was run 2026-08-10.

### The gap: **213 spells missing** (295 listed − 79 matched − 3 naming variants)

| Circle (list → build) | In build | Listed | **Missing** |
|---|---|---|---|
| Terrestrial | 16 | 97 | **86** |
| Celestial | 9 | 46 | **40** |
| **Adamant → `Solar`** ⚠ | 6 | 31 | **27** |
| Shadowlands | 9 | 42 | **33** |
| Labyrinth | 7 | 24 | **17** |
| Void | 7 | 17 | **10** |
| Man-Machine | 23 | 23 | **0** |
| God-Machine | 15 | 15 | **0** |
| **Total** | **92** | **295** | **213** |

**The two Alchemical traditions are already 100% complete** — a strong signal that the
list and the build agree on shape and naming where both are populated. The gap is
entirely sorcery + necromancy.

### Missing by book — the whole track is three books

| Book | Missing | Pages on disk? |
|---|---|---|
| **S&S — Savant and Sorcerer** | 93 | **NO** |
| **B&E — Book of Bone and Ebony** | 60 | **NO** |
| **B3C — Book of Three Circles** | 49 | **NO** |
| SAS — Savage Seas | 4 | NO |
| E:SI, B&S, E:AU, E:1, E:AB, GOD, `E:S` | 7 | partial |

**202 of 213 come from three books, none of which have pages on disk.** Syncing S&S,
B&E and B3C converts this track from blocked to a large but purely mechanical authoring
job. That is the single highest-leverage page sync in the whole plan.

### Findings the diff turned up — do not silently reconcile any of these

1. **`Adamant` = `Solar` — RESOLVED, human 2026-08-10.** There are **two in-universe
   naming schemes for the sorcery circles**, and which one a character uses depends on
   whether they study **Realm** sorcery: `Terrestrial > Celestial > Solar` and
   `Emerald > Sapphire > Adamant` are the same three circles under different names.
   The list uses the second, the build the first; **they are not in conflict and no new
   circle is needed** — the 27 Adamant spells are `Solar`-circle spells. The same
   equivalence explains the *Emerald Circle Countermagic* / *Sapphire Countermagic* /
   *Adamant Countermagic* spell names sitting one per circle.
   ⚠ **Do not "fix" either vocabulary to match the other**, and note the build has no
   representation of the Realm-vs-not distinction — whether it ever needs one (a display
   preference, say) is unasked and out of scope here.
2. **`Plague of Bronze Snakes` is printed twice** — Terrestrial (S&S 112) *and*
   Man-Machine (E:AU 153). The build holds only the Man-Machine one, so the Terrestrial
   printing is a genuine gap with a colliding name. Ids must not collide.
3. **Three naming variants, not gaps** — the build is right and the list has typos in
   two of them: `Emerald Circle Countermagic` / build `Emerald Countermagic`;
   `Philogiston Web` / build **`Phlogiston Web`**; `Destiny-Optimizing Mediation` /
   build **`Destiny-Optimizing Meditation`**.
4. **⚠ The masterlist is NOT exhaustive — the diff runs both ways.** Eleven spells in
   the build appear nowhere on the list, most of them Savage Seas and Sidereals entries
   authored from real pages (*Calling the Gulls with Beaks of Steel*, *Invocation of the
   Living Ship*, *Keel Cleaves the Clouds*, *Lightning Whip Smites the Waters*, *Whisper
   of the Grasses*, *Curse of Betrayal*, *Hidden Judges of the Secret Flame*, *Shout of
   Turmoil*, *Atrocious Fire Transformation*, *Evocation from the Mirror*). **Nothing in
   the build gets deleted because the list omits it** — the list is a floor on what
   exists, never a ceiling.
5. **Two suspect page refs to check against the real page:** `Gift of Knowledge | E:S |
   123` uses a book code absent from the legend (`E:SI`?), and *Raise the Puissant
   Sanctum* (S&S 57) / *Craft the Puissant Sanctum* (S&S 57-58) sit far outside the
   S&S page range every other Celestial/Adamant entry uses (125-143).
6. **Two confusable book codes:** `S&S` = Savant and Sorcerer, `SAS` = Savage Seas,
   `B&S` = Blood and Salt. Three books, three near-identical codes.

### Remaining work on this track
- [ ] human ruling on **Adamant vs Solar** (blocks 27 spells)
- [ ] sync **S&S, B&E, B3C** spell pages (unblocks 202)
- [ ] author from pages, in book batches; re-check circle gates after each batch
- [ ] fold the 4 Savage Seas + 7 scattered entries in as their pages allow

The one thing to get right up front is **circle assignment**. `highest_magic_circle_id`
is the recorded trap of this codebase — it is the circle **BARRED at chargen**, not the
reachable cap ([[multi-splat-architecture]]). A batch of new spells changes what each
splat can reach; the per-splat circle gates must be re-checked after the batch lands,
not assumed to still hold.

Also: the build already carries **three distinct traditions** in one file (sorcery,
necromancy, Alchemical Man/God-Machine). A masterlist that only covers sorcery closes
one third of the track — confirm its coverage before treating the diff as complete.

## Sequencing

**All discovery work is DONE.** Both diffs have been run and the artifact backlog was
already built. **Every remaining blocker is a page sync** — no discovery is left.

### The whole gap, in one table

| Track | In build | Missing | Diff status |
|---|---|---|---|
| Charms + Arcanoi | 1,709 | **179** | done 2026-08-10 |
| Spells | 92 | **213** | done 2026-08-10 |
| Artifacts | 40 | **266** | backlog built 2026-08-08 (Fair Folk 17 removed) |
| **Total** | **1,841** | **658** | |

### Sequence by BOOK, not by track

This is the real finding of running both diffs: **the books pay across all three tracks
at once, so sync order should follow combined yield — and one book dwarfs the rest.**

| Book | Charms | Spells | Artifacts | **Total** |
|---|---|---|---|---|
| **Book of Bone and Ebony** | **70** | **60** | **74** | **204** |
| Savant and Sorcerer | — | 93 | 5 | **98** |
| **Player's Guide** | **57** | — | 14 | **71** |
| Book of Three Circles | — | 49 | 14 | **63** |
| The Outcaste | 6 | — | 27 | **33** |
| The Abyssals | 7 | 1 | 16 | **24** |
| Savage Seas | 10 | 4 | 4 | **18** |
| The Lunars | 17 | — | — | **17** |

**Book of Bone and Ebony is the single highest-value page sync in the project** — 204
entries, and it fills the two largest individual holes at once: the Ghost Arcanoi
catalogue (all 71 missing Arcanoi) and the necromancy circles (60 spells). Savant and
Sorcerer is second at 98; the Player's Guide is third at 71 and is the **only** source
of the 49 missing Martial Arts Charms.

Tracks are otherwise independent and can interleave freely.

## What the human owes

- [x] the **charm-trees PDF** — on disk (`-ds` worktree), **diff DONE: 179 missing**
- [x] the **spell masterlist** — on disk (`-ds` worktree), **diff DONE: 213 missing**
- [x] ~~ruling: `Adamant` vs `Solar`~~ — **RESOLVED 2026-08-10: same circle, two
      in-universe naming schemes (Realm vs not). Nothing blocked.**
- [ ] **page sync, highest leverage first — this is now the ONLY thing gating the plan:**
      1. **Book of Bone and Ebony** — 204 entries (70 Arcanoi + 60 spells + 74 artifacts)
      2. **Savant and Sorcerer** — 98 (93 spells + 5 artifacts)
      3. **Player's Guide** — 71 (57 Charms, incl. all 49 missing MA + 14 artifacts)
      4. **Book of Three Circles** — 63 (49 spells + 14 artifacts)
- [ ] **artifact source pages** for the remaining books — the backlog names exactly which
- [x] ~~a ruling on Fair Folk artifacts~~ — **CLOSED 2026-08-10: OUT OF SCOPE.** The
      human reviewed them; they are as game-changing as the Fair Folk rules themselves
      and follow their splat out under decision 0010. Do not re-ask.
- [x] ~~a ruling on Mountain Folk Charms in the Fair Folk book~~ — **moot.** The real
      count is **1** (`Heart of Chaos`), not 7, and Mountain Folk content in that book
      was always in scope; the book is not the splat.

## Pointers
- **Every missing entry, enumerated per book: `docs/status/content-gap-entries.md`**
  (regenerate with `tools/gen_content_gap.py`)
- Artifact discovery layer + the parse method: `docs/status/artifact-backlog.md`
- Per-book artifact authoring queues: `docs/status/artifact-backlog-entries.md`
- What a splat's Charm authoring actually costs: `docs/adding-a-splat.md`
- Charm record shape: `tools/CHARM_AUTHORING_SPEC.md`, `tools/validate_charms.py`
- Delegating a batch to a cheap model + the four-check audit: `docs/delegated-authoring.md`
- VLM transcription pipeline: `tools/VLM_TRANSCRIPTION_PROMPT.md`
