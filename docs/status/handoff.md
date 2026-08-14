# Session handoff — 2026-08-14

## The Book of Three Circles is browser-verified, and Group A is done

**Three things shipped.**

**1. BOTC click-through — clean.** All four items passed: the spell picker's Circle
dropdown, the artifact/weapon comboboxes, the merit gate in both directions (the
`_art_catalog` stale-closure trap did not fire), and the merit-gated names' absence from
the Artifact-dot surfaces. `book-of-three-circles.md` is marked verified.

**2. The one finding was presentational, and is fixed.** The Crimson Bow showed as two
peer inventory rows — the artifact and the stat line `grant_gear` stamped for it — which
the human read as *"odd, and a little obtuse."* It was the mechanism working; the
inventory just rendered one object as two unrelated lines. **They are now ONE row**, the
artifact owning it with the stat line in `detail` and `InventoryRow.linked_list_name` /
`.linked_index` as a second route back to the gear editor. Display-only: the typed lists
are untouched, so the dice-pool sidebar's positional indices into `character.weapons`
still hold. Record: `gear-and-inventory.md`. The binding test names `build_gear`, not
`inventory_rows` — the stat line has no row of its own now, so a panel that ignored
`linked_index` would make it silently uneditable.

**3. Group A — all 68 authored.** All ten books extracted with
`extract_born_digital.py`, which is all Group A ever needed. Artifacts **237 → 302**,
spells **294 → 296**, weapons **103 → 110**. Full record and the per-book table:
`content-gap-retriage.md`.

⚠ **Group A was 68, not 63.** Exact-name re-checking found five entries the retriage's
fuzzy matcher had scored as present — *Implosion Bow, Light* against **Medium Implosion
Bow**, *Masks that Command Animals* against the unrelated artifact named **Mask**. The
retriage's own trap, firing on the retriage. **A fuzzy gap count is a LOWER bound on the
work.**

⚠ **An unflagged extraction page is not a clean page.** Six of seven GARBLED markers were
running heads and blocked nothing — but **Cult p.70 was column-interleaved and NOT
flagged**, splicing two artifacts' sentences together mid-clause with nothing to say so.
Both that and Wood p.81 were resolved by rasterising with `pdftoppm -r 110`.

## The fourth `(ARTIFACT N/A)` entry — ruled and shipped

**The Iron Puzzle Box (Halta p.93)** prints `(ARTIFACT N/A)` and reads as a plot device
of exactly the Mantle of Brigid class. **Human, 2026-08-14: "Legendary Artifact, yes."**
Authored with `requires_merit`; `PLOT_DEVICES` in `test_rated_artifacts.py` is now four.

⚠ **It is the standing counter-example to "no `(ARTIFACT N/A)` entry remains unauthored
anywhere in the build."** That claim was only ever about the books read so far. Three
Group B books are still unsynced and any of them can hold a fifth.

## Group C — done the same day (3 authored, 2 false gaps, 3 pending your sign-off)

The eight were really five. **Authored:** Five Directions Formation Protocol (PG p.242 —
a Crimson Pentacle Blade **Charm**, not an artifact), Transference of the Sanctum (GoD
p.49) and Gift of Knowledge. **False gaps:** *Implosion Bow, Medium* and *Nutrient
Recycling Engine* were both already authored off the exact pages listed, under the
BOOK's names — *Medium Implosion Bow* and *Portable Nutriment Recycling Engine*.

**`E:S` is resolved: it is The Sidereals.** p.123 prints all three of that book's spells
in one paragraph, so the gap list had split one page across two book codes. Fold `E:S`
into Sidereals wherever it appears.

⚠ **Seven false gaps across Groups A and C now, and a matcher that would have caught
every one:** match on NAME, and when that fails, **match on BOOK + PAGE**. Both Group C
misses cite the exact page of an entry already in the catalogue. No name matcher, fuzzy
or exact, closes that; a page-keyed one closes all seven with no false positives.

**Ruins of Rathess p.86 ×3 — RESOLVED, and not by the reassembly.** The book landed in
`sources/`, so the page was rasterised and read directly: **Ring of Images ••, Crystal of
Protection •••, Ring of Disguise •••**, all authored. Both independent reassemblies turned
out to be exactly right — and it still should not have been authored on that basis. Two
batches were right to skip it, and the real fix took one `pdftoppm` call the moment the
book existed. **When a marked page is blocked, acquire the page; do not argue about the
reassembly.**

## Group B — DONE the same day. **The content gap is CLOSED.**

All four remaining books landed in `sources/` and all 39 entries are authored. Every one
is a **pure scan**, so each page was rasterised with `pdftoppm -r 110` and read directly.
Record: `content-gap-retriage.md`.

| | Session start | Now |
|---|---|---|
| Artifacts | 237 | **330** |
| Spells | 294 | **304** |
| Charms | 1,896 | **1,910** |
| Weapons | 103 | **112** |
| Armour | 27 | **28** |

**Every book held more than the triage said** — Savage Seas 17→18, Time of Tumult 13→14,
Storyteller's Companion 4→6, Sidereals 5→6. Across Groups A, B and C the fuzzy matcher
undercounted by **11 entries**. Proven three times now: **a fuzzy gap count is a LOWER
bound on the work**; when a name match fails, match on **book + page**.

**The fifth `(ARTIFACT N/A)` arrived exactly where the record said it might** — the **Eye
of Autochthon** (Storyteller's Companion p.80), the artifact the Legendary Artifact Merit
names as its own exemplar. Authored on your standing ruling; `PLOT_DEVICES` is five.

## Two printed defects — both closed 2026-08-14

1. **"Minimum Offult: 3"** (Time of Tumult p.96, World Within a Picture Style). Verified
   at 300 dpi that the "ff" is the book's typo, not the scan's. **Human ruled: it is
   Occult.** Encoded as `extra_min_abilities: [{occult, 3}]`; the printed spelling stays
   in the Charm's description so the book's text is not lost. Barring verified both ways.
2. **"Wind-Defying Course Method"** (Savage Seas p.115) vs **"…Technique"** two entries
   away. One Charm exists, and it is in the **COREBOOK at p.209-210**, not Savant and
   Sorcerer. Wired and resolving.

## The click-through — 2026-08-14, clean, no defects

Four items, all passing, against a Solar Twilight at Essence 5 / Occult 3 / Craft 5
holding Legendary Artifact: **the inventory merge with real content** (five rows not
eight, the armour half rendering `Mob-2` correctly), **the Occult gate**, **the
merit-gated five**, and **the new catalogue** counts and names.

Preflight earned its keep beforehand: the **armour side of the merge had no test**, and
the Armor of Aquatic Puissance had just made it a live shape. Test added before booking
browser time.

## Next

**Nothing is blocked, nothing is half-finished, and the catalogue is complete.** The two
remaining unauthored areas — the Mist numina and Cult Abyssals — are **deferred
indefinitely** and are not gaps.

1. **Commit and push.** ~25 files are uncommitted: the inventory merge, ~120 catalogue
   entries across nine books, the Occult fix, and the doc corrections.
2. **The Qt port** remains the standing post-1.0 goal, still not scheduled
   (`docs/plans/qt-port.md`). Do not treat it as a 1.0 blocker.

# Session handoff — 2026-08-13 (late)

## The Book of Three Circles is authored — all 62 entries, ⚠ NOT browser-verified

**Record: `docs/status/book-of-three-circles.md`.** Spells **246 → 294**, artifacts
**222 → 237**, plus the Crimson Bow's weapon row. Suite **2,355 passing / 2,356 total** —
the one failure is the known machine-only M&F description test.

It is a **pure scan** and was read with `pdftoppm -r 110`, no VLM leg — **PDF page = book
page + 1**. Four things worth carrying forward:

* **S&S wins every conflict** (human's ruling). Free to honour: the gap list is by
  construction the names the build lacks, and its copies of the shared spells came from
  S&S. Nothing existing was touched; a fuzzy sweep of all 48 new names found one near
  match that is a genuinely different spell printed on the same page.
* **The ch.4 circle is SOLAR.** The fan spell index calls that group "Adamant"; the book's
  chapter head says *THE SOLAR CIRCLE*. Adamant appears only as *Adamant Countermagic*.
* **ch.5 rates its artifacts by `LEVEL N` SECTION HEADING**, not per-entry dot strings —
  an entry's rating is whichever block it sits in. All nine agreed with the fan index.
* **The two `(ARTIFACT N/A)` entries became a THIRD acquisition channel** (your ruling:
  they are plot devices costing the **Legendary Artifact 10-pt Merit**, which the Merit's
  own text all but says, naming the Mantle as its example). This **amends decision 0017**.
  `ArtifactType.requires_merit` is data, the offer moves with the Merit, the bar
  (`artifact-missing-merit`) runs both sides of the lock, and nothing is charged to a
  budget. The **B&E Insidious Ebon Xoanon** was ruled the same way the same day and is
  authored, so **no `ARTIFACT N/A` entry is left unauthored anywhere in the build**.

**Next on this thread:** a click-through — the spell picker's Circle dropdown, the
artifact/weapon comboboxes, and the merit-gated pair (take Legendary Artifact on
Advantages, then look for the Mantle in the Gear tab's artifact dropdown; drop the Merit
and confirm the Issue appears). Preflight is clean and the two render routes are green.
Then **Group A — 63 entries in born-digital books that only
need an `extract_born_digital.py` run** (five Aspect Books, Abyssals pp.254-261, Blood and
Salt, Halta, Cult, Manacle and Coin).

## The content gap was re-triaged — nothing is page-blocked any more

**Record: `docs/status/content-gap-retriage.md`.** All 647 discovery rows were re-diffed
against the current catalogues: **467 have been authored since 2026-08-10; 180 remain**
(**120** after the Book of Three Circles, above),
and the old "213 entries, every one page-blocked" line is wrong in both halves.

| Group | Entries | Needs |
|---|---|---|
| A — born-digital books never extracted | **63** | one `extract_born_digital.py` run each |
| B — pure scans | **101** → **39** | `pdftoppm`, then read the pages |
| C — misses in already-extracted books | **8** | a look at Markdown already on disk |
| (closed rulings, not work) | 8 | — |

~~Biggest single read: **Book of Three Circles is 62**.~~ **Done, same session.** The next
biggest is **Savage Seas (17)**, which unlike BOTC spans Charms, spells and artifacts.

⚠ **The Lunar 17 was a FALSE GAP and is closed.** All 16 (plus 3 of the PG 5) are Deadly
Beastman Transformation **Gifts**, authored as `variants` on the parent Charm since the
Lunar splat shipped. The gap diff compares `name` fields and a variant has no `name` —
19 of the "213" were never missing. Any gap number is an upper bound until the matcher
has been pointed at every shape a Charm takes here.

⚠ **The Ollama VLM leg is for non-visual models** (human, 2026-08-13). A vision-capable
model reads the rasterised pages itself; don't route a scan through `vlm_read_ratings.py`
out of habit. The `vlm-cannot-count-dots` caution is about that small local VLM.

**Also this session:** `git pull` was a divergent-branch rebase — the local `docs` commit
went on top of six remote commits, with three conflicts resolved (test count → 2,347, the
Wonders row keeping its Hearthstone-allowance paragraph, the handoff taking the remote's).

# Session handoff — 2026-08-13

## Gear, inventory, goods and the shop — DONE, browser-verified 2026-08-13

**The record is `docs/status/gear-and-inventory.md`** — the Gear tab, the inventory view,
the Buy surface, mundane goods and the custom gear library, plus the traps that refactor
produced. Decision **0017** (artifacts have two acquisition channels — the Background is
pre-game, cash is in-play) is in `docs/decisions/`; the artifact BUDGET rules and the two
new extraction tools are in `rated-artifacts.md`; the gear library is in
`custom-content.md`.

## The rest of 2026-08-13, in brief

* **The corebook Artifact Background is enforced** and was never running for plain
  Solars, Lunars, Sidereals, Ghosts, Godblooded or the Abyssal renegade — a splat with no
  `BackgroundRule` read as "no budget" rather than "the default budget", and three tests
  asserted `== []` on that gap. Amended the same day to ONE ARTIFACT PER BACKGROUND ROW.
* **Dragon Kings had their own Artifact entry all along** (PG p.175-176), and were
  reading the Dragon-Blooded one. The RULE was right either way, which is why nothing
  caught it.
* **Two extraction tools, both proved before use**: `parse_resources_costs.py` (the
  corebook's dot columns — 42/42 against hand-authored values, and it found a typo) and
  `parse_mc_prices.py` (Manacle and Coin's two-column price pages — 43/43 against a page
  authored independently, which then unblocked p.125).
* **`sources/` is now on this machine.** Abyssals pp.254-261 extracts cleanly (16 blocked
  entries), Outcaste p.118 is readable (re-check the Mist-aspect blocker before planning
  it), The Lunars is present but a pure scan.

## Next up

Nothing is blocking and nothing is half-finished. Open threads, in rough order of value:

1. ~~**The 213 catalogue entries** — re-triage now that `sources/` has landed.~~ **DONE
   2026-08-13** — see the late entry at the top of this file.
2. **The Mist aspect** — the last unauthored piece of the Outcaste book, possibly
   unblocked; needs a page read and probably a ruling.
3. ~~**The Lunar 17** — needs the VLM leg on a pure scan; never exercised.~~ **CLOSED
   2026-08-13: a false gap. They are the DBT Gifts, already authored as `variants`.**

⚠ **One printed oddity is recorded and confirmed, not fixed:** M&C p.125 prints "Created
walkaway" where its three siblings are "… charm". The human confirmed 2026-08-13 that the
entry is just that; whether the book dropped a word is unknowable from the page.

# Session handoff — 2026-08-12

**Rewritten each session.** The durable operating guide is `CLAUDE.md`.

## Current state
- Suite **2,255 passing**, no failures. The documented machine-only
  `test_every_description_matches_the_source_text` is GREEN here (the Godblooded chapter
  md is absent on this machine, so its 46 entries defer) — not a regression either way,
  see `docs/status/godblooded.md`.
- **The Backgrounds work is DONE and browser-verified end to end** — the overhaul
  (per-splat catalogues, dot ladders, `charm_noun`) and the numeric rules (R1–R5).
  Record: `docs/status/backgrounds.md`; the brief that drove the second half is
  `docs/briefs-background-rules.md`.
- **The Cult of the Illuminated second pass is DONE and browser-verified** (2026-08-12):
  the Cult's own Artifact Background — which had never been authored, so Illuminated
  Solars were silently getting the corebook's — and the **Cult Dragon-Blooded origin**.
  Record: `docs/status/illuminated.md`. Cult Abyssals are deliberately deferred (56
  unmapped "closest Abyssal equivalent" Charms; needs a human-approved mapping).
- **Working tree clean, `main` pushed.** `2a95a85` carried the previous sessions' work
  (the mortal-catalogue fix, the Connections per-row revert, the preflight render
  routes, the Illuminated pass); `f2ef735` is the dice-pool feature below.

## What happened this session
0. **The dice-pool feature, end to end** — decision 0016, the data, the engine, the
   sidebar, the fatigue counter and the custom builder. Three rulings from the human
   mid-build. Preflight found one real bug (panel state inside the refreshable); the
   sign trap and the specialty under-count were found by checking output against the
   book rather than against the tests. See **Next up**.
1. **Click-through of the overhaul** — all six items passed. One fix off it: the
   catalogue dialog's ladder rendered as a wall of text, because a NiceGUI label
   collapses newlines. It needed blank lines AND `whitespace-pre-line`.
2. **Two rulings closed.** The ten Mountain Folk Backgrounds are prose-only and now
   borrow the core ladder via `BackgroundType.ladder_from` (resolved once by the loader —
   the read sites see a splat-FILTERED catalogue that does not contain the entry being
   borrowed from). The Tiger Warriors ladder is signed off. ⚠ Writing the first test for
   the borrow exposed a live bug: the Mountain Folk dropdown offered ten names TWICE.
   Fixed generally — a splat's own tagged copy displaces the untagged one.
3. **The numeric rules, delegated to DeepSeek** off a written brief, then reviewed —
   **three rounds**, defects each time, all the house bug. See below.
4. **`preflight` + click-through of the numeric rules**, passed after two more fixes.
5. **The Cult of the Illuminated, second pass** — the browser found Illuminated Solars
   getting the corebook Artifact; the entry had never been authored. Shipped with the
   Cult Dragon-Blooded origin, a third `GrantedCharmChoice` shape (a flat pool mixing
   style categories with a named Charm), and a crash preflight caught that the suite
   could not — see `docs/status/illuminated.md` and CLAUDE.md's traps list.
6. **Gear `resources_cost` answered and shipped** — core p.325 (the human found the
   sidebar; the extracted corebook is now in `images/_extracted/`). An affordability
   HINT on the gear dialogs, NOT a validation, because the printed rule contradicts an
   ownership invariant in its own middle clause. `docs/status/rated-artifacts.md`.

## The delegation, honestly — the part worth reading
The brief was good and most of the authored work was right: R4's bonus-point pricing was
exact, and the Merit caps survived a rewrite of the very control that carries them. But
every defect was one shape, and a green suite saw none of them:

- **Round 1.** `validate_chargen` never passed the character, so R1 never ran in
  production and the mortal toggle could not lift its own bar. All nine tests called
  `background_issues(...)` directly — **the read site was tested, the caller was not.**
- **Round 2.** The fix for the universal cap skipped it whenever a rule merely EXISTED,
  so the three rules stating no maximum (Alchemical Class, Alchemical Backing,
  Illuminated Illumination) lost the cap at chargen while keeping it post-lock.
- **Round 3, in the browser.** The mortal permission lifted the BAR but not the OFFER
  list — permission that reveals nothing. And Connections' total-cap leaked into the
  per-row control, offering a row ceiling of 27.

**What to change in the next brief:** "test the binding, not the field" was not enough.
Name **which function the test must call**. A test that reaches past the caller into the
helper cannot see the caller's mistake, and that is the mistake a cheap model makes over
and over.

## Shipped and closed this session

**The dice-pool feature — DONE, committed (`f2ef735`), browser-verified.** Decision
0016 was written and the feature built off it: `data/dice_pools.json` (14 page-cited
rolls), `RollDefinition` on the RuleSet, a pure `engine/pools.py`, a **left sidebar on
the Play tab listing every roll at once** (each with its own one-line arithmetic — a
list, not a picker, on the human's call), and a **custom Attribute + Ability panel in
the main column**. All three open rules questions were ruled and implemented the same
day: wound penalties apply to Virtue/Willpower checks, resist-infection is exempt
(p.233), and accumulated armour fatigue is a manual `PlayState.fatigue` counter.
Suite 2,172 → **2,255**. Clicked through in its final shape; no defects found.
Record: `docs/status/dice-pools.md`.

Three bugs were caught BEFORE the browser, and all three are worth remembering because
the suite was green through every one of them:

- ⚠ **The mobility sign.** `Armor.mobility_penalty` is stored NEGATIVE, and the first
  cut read it as a magnitude — i.e. it ADDED dice. Ten tests covered that line and
  passed, because every fixture had been written with the same wrong sign: engine and
  tests agreed with each other and neither agreed with the data. Found only when
  unrelated work put real catalogue values on screen.
- **The specialty under-count.** The loader splits a legacy `rating: 2` into two
  instance rows, so offering the raw rows gave two identical +1 entries where p.134
  says +2. Now summed by name.
- **Panel state inside the refreshable** (preflight's find) — marking damage reset the
  player's selection, on exactly the click that sends them to the pool.

## Next up
1. **Browser-verify the Resources hint** — the gear dialogs are the only thing shipped
   today that no one has clicked. Open Add weapon on a character with Resources ••: Self
   Bow should read "within your means", Long Bow "a serious expense", Composite Bow
   "beyond your Resources" and be faded (but still pickable).
2. **One feature the human asked to scope, 2026-08-12, still un-started:**
   - **Mundane purchasable gear.** Cheap: `resources_cost`, `gear_affordability` and the
     shared catalogue dialog all exist; it needs a `GearEntry` model, `Character.gear`, a
     `data/gear.json` and a third section on the equipment surface. No engine work — per
     the p.325 ruling, Resources is a hint, never a validation. **Page-blocked on the
     equipment lists**, same blocker as item 3.
3. **The other 63 `resources_cost` values** — page-blocked, needs a human read of the
   corebook equipment tables; the Cost column is dot glyphs the font cipher did not
   resolve. `docs/status/rated-artifacts.md` has the detail.

## Blocked on pages — do these at home, not at work
⚠ `images/` and `sources/` are gitignored and do not travel.
- **17 Lunar Charms** from the content gap. `sources/Exalted - The Lunars.pdf` is a PURE
  SCAN (0 of 258 pages carry text, so neither `extract_born_digital` nor
  `solve_cid_bands` applies) but rasterises cleanly with `pdftoppm -r 110`. **PDF page =
  book page + 3.** The job that would justify the Ollama VLM leg (`qwen3-vl:8b-instruct`
  is pulled); ⚠ its dot counts are biased low, so for any ladder take the rating from the
  rung's POSITION, never from counting.
- The rest of the 213 page-blocked catalogue entries — `docs/status/catalogue-sweep.md`
  ranks the syncs by yield.
