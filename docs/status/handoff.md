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
