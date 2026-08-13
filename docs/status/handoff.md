# Session handoff — 2026-08-13

**The human clicked through the corebook Wonders work overnight and it passed.** Two
things shipped the morning after, both off a preflight run:

1. **The Play tab's unarmed notice was re-parented** (`ui/play.py`). Its `else` belonged
   to `if sv.weapons:`, and `4f875d3` inserted the nocked-arrow controls between the
   `if` and the `else` — so an armed character with nothing nocked was told "No weapon
   owned" beneath a dropdown listing their weapon. The unarmed case still read correctly
   *by accident*, which is why the suite stayed green. Fixed, with a two-route
   regression test and its negative control.
2. **The corebook Artifact Background is now enforced** — human ruling 2026-08-13, full
   record in `docs/status/rated-artifacts.md`. One artifact, rated no higher than the
   Background, for every splat whose book alters nothing. `check_artifacts` used to
   `return issues` when a splat had no `BackgroundRule`, so the check did not run for
   plain Solar, Lunar, Sidereal, Ghost, Godblooded or the Abyssal renegade. **Three
   tests asserted `== []` on that gap** — they encoded the bug as the spec.

**Then an audit of every splat's Artifact rule**, prompted by the human asking what the
new default does to the others. It turned up two more:

3. **Mountain Folk with no Enlightenment chosen were being handed the corebook rule** —
   theirs is the ONE splat with no base budget row, so an origin-less character resolves
   to no rule at all. A regression the fallback itself introduced: before it, a missing
   rule meant no check. Now guarded by `artifacts.rule_is_pending_an_origin` — silence
   beats the wrong rule. ⚠ The first cut of that guard asked "does any row in this
   splat's cascade print a rule?", and `Solar:illuminated` answered yes, **switching the
   corebook default off for every ordinary Solar** — the guard disabled the feature it
   was protecting. Caught by the negative control in the same test.
4. **Dragon Kings were reading the Dragon-Blooded Artifact entry** — CLOSED. The page
   (PG p.175-176, in `images/_extracted/Player's Guide.md`) prints them their own:
   "Weapons and tools, either vegetative, crystal or orichalcum", whose footnote borrows
   the Terrestrial RULE explicitly ("See E:DB, p. 157 for details"). Authored as
   `background.artifact-dragonkings` with `ladder_from` the DB entry — the human's call,
   since the page's own cross-reference points there. The rule was right the whole time,
   which is why nothing caught it. `docs/status/rated-artifacts.md`.

Suite **2,292 passing**. ⚠ The artifact work is NOT browser-verified: click the
Advantages tab on a plain Solar and confirm the header reads `Artifacts (n/1 — Artifact
N, one artifact rated up to N)`, that a second artifact raises an error, and that an
artifact weapon + artifact armour counts as two.

**Items 1 and 2 of the gear/catalogue overhaul are done** (the human's plan, 2026-08-13;
item 3 — `GearEntry` / `data/gear.json` / the services-vs-possessions ruling — is
deliberately not started):

* **The artifact/gear double-entry is fixed.** `from_artifact` links a granted stat line
  to its artifact, and the budget counts the pair once. Details and the four traps in
  `docs/status/rated-artifacts.md`.
* **`tools/parse_resources_costs.py` reads the dot columns**, proven by `--verify`
  against the hand-authored data: **42 agree, 0 disagree**. Found one typo (Reinforced
  Buff Jacket ••• → ••).
* **Shields and helms are priced after all** — Manacle and Coin p.124, supplied by the
  human; all six authored. The corebook simply does not price them, and this file had
  recorded that as "no printed cost", which was a stronger claim than the evidence.
* ⚠ **`images/_extracted/Exalted Core.md` was the PRE-crack copy on this machine** and
  has been re-extracted now that `sources/` is here. **The offset auto-detect fails on
  this PDF — pass `--offset 2`.**

**The purchasing catalogue is NO LONGER PAGE-BLOCKED.** The human's call, 2026-08-13:
base it on **Manacle and Coin pp.122-125**, not the corebook. Clean text layer, real `•`
characters (the dot-counting parser is not needed for it), the same tables fuller, and
two the corebook lacks — the Resources↔cash conversion (p.122) and Everyday / Greater &
Lesser Wonders (p.125). The two books agree on all 39 shared rows.

**That ruling is now CLOSED as decision 0017** — the two numbers measure different
things and the corebook says so: its gear tables define the Artifact column as the dots
spent "to start the game owning" the item (p.342). So the Background is the pre-game
channel and cash is the in-play one. **The model and the rule are BUILT** (`acquired` on
the three ownables, `artifacts.budgeted_items`, the post-lock-only control, the
`artifact-purchased-at-chargen` bar); **the M&C prices are NOT yet authored** — that is
the next slice, along with `data/gear.json`.

⚠ NOT browser-verified: the Acquired control appears only post-lock, and flipping it to
Bought must drop the header count and print "+ 1 bought with Resources".

Also still open: the Resources hint on the gear dialogs is unclicked.

---

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
