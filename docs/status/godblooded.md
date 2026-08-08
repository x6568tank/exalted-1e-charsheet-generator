# Godblooded — DONE (Phase A: core + Ghost-Blooded; Phase B: Half-Caste), browser-verified

**Phase A + B shipped 2026-08-02; the review-fix Phase C, the ST-option follow-up, the
bar-list ruling and Phase D (Fae-Blooded) took the suite to 1921 green.** The eighth splat,
third non-Exalt. Source: `images/Non-Exalts/Godblooded/CH2 - Godblooded.md` (Player's
Guide CH2, pp.44-87, human-pasted). **Browser-verified 2026-08-02** — the human clicked
through both heritages. Phase A surfaced the missing necromancy initiation (and the
General Arcanoi grouping); Phase B surfaced the Arcanoi tab showing for a Half-Caste
(see below) and confirmed the Essence-pool numbers.

## Phase D — Fae-Blooded (2026-08-02, browser-verified — including the code-review fixes below)

The third heritage (of five), the day after the review brief. Source: PG pp.60, 73-80.
**16 new tests, suite 1907 → 1924; the code-review fixes below took it to 1928.**
The review called the glamour Merits the real project, and the delivered shape is:
**no Charms, no spells, `Ess×8` pool, Terrestrial MA only, 23 glamour Merits as
powers.**

**Click-through fixes (2026-08-02, the human drove it in a browser):**
* **Greater circles are now barred at the splat-access gate** — a Solar Half-Caste was
  OFFERED Celestial/Solar Circle Sorcery and an Abyssal one Labyrinth/Void necromancy.
  The Essence-3 cap was never enough: the access gate does not consult `min_essence`,
  so the picker showed the higher initiations even though the buy path refused. p.48:
  "Greater circles of sorcery and necromancy lie beyond the purview of the
  God-Blooded." `heritage_bars_initiation` now allows only the FIRST circle of the
  heritage's track (`TRACK_CIRCLES[track][:1]`).
* **The Virtue Attunement detail is a dropdown** — `merits.detail_choices` returns the
  four Virtues instead of free text (a typo would have silently dropped the discount).
* **The Commoner's second Virtue Attunement is a clean refusal** — the illegal second
  copy renders the `merit-repeats-above-origin` issue without crashing; a render route
  pins it.

* **The no-spells bar is the Phase C trap, now a rule.** `heritage_traits.magic_track`
  has a THIRD state: `""` means no restriction (the opposite of a Fae-Blooded), so the
  sentinel is `"none"`, read in `heritage_bars_initiation` → both charm gates (p.48:
  "All God-Blooded with the Awakened Essence Merit APART FROM Fae-Blooded may also
  learn to cast spells"). A Fae-Blooded's `accessible_circles` is empty even with
  Awakened Essence.
* **No Charms** — `charm_access: []` and, after the code review, a `charms_available:
  false` FLAG rather than an eight-Arcanoi deny-list (a deny-list would silently admit
  the ninth Arcanoi the day God/Demon-Blooded's spirit Charms are authored). The flag
  closes the whole native catalogue at the one native-match site in
  `charm_matches_splat`; Terrestrial Martial Arts still open via the p.234 splat grant,
  same as a ghost. `test_a_fae_blooded_cannot_hold_a_charm_authored_for_a_later_heritage`
  pins it with a Charm that exists on no list.
* **`Ess×8` pool** (p.66) — `unlocked_essence.personal_essence_coeff: 8`, nothing else.
* **The Noble/Commoner ORIGIN axis** (human 2026-08-02) — a new
  `GodbloodedHeritage.origin_options`, data-driven; the Origin dropdown offers Noble/
  Commoner to a Fae-Blooded (and the five parents to a Half-Caste, moved out of the
  editor into data). **`MeritFlaw.required_origins`** gates Prince of Chaos +
  Transcendent Dream Shape (Noble) and Goblin Body (Commoner), enforced in BOTH the
  validation and the picker. `heritage-requires-origin` catches a blank Fae-Blooded.
* **The 23 glamour M&F** (19 Merits + 4 Flaws, pp.74-80) with the printed prereq chains
  (Draught of Passion → Fervor's Kiss → Mien of Passion, etc.), Fae-Blooded-gated.
  The Essence-2/3 prereqs (Prince of Chaos, Wyldward, Subtle Glamour, Wyldwalk) go in
  `prerequisite_note` — `trait_rating` resolves Attributes/Abilities/Virtues/
  Backgrounds, not Essence. **Goblin Body and Transcendent Dream Shape are
  `variable_cost`** (ST agrees the points); the mutation form (E:L pp.212-222, not in
  the project) and the scene-long Attribute form are flagged in their descriptions.
* **The one real accounting effect — Virtue Attunement** (3pt) prices the attuned
  Virtue at **2 BP/dot** (vs 3) and **(current ×2) XP** (vs ×3). `MeritEffects
  .favored_virtues` (the WHICH, read off the purchase's `detail`) feeds the Virtue BP
  calc and `costs.virtue_step` (now takes the Virtue name). Two read sites, preflight-clean.
  **Once for a Commoner, twice for a Noble** (p.74, human 2026-08-02): a new
  `MeritFlaw.max_purchases_by_origin` (`{"Noble": 2, "Commoner": 1}`) caps the
  repeat, enforced in validate AND the post-lock buy path — a Commoner cannot pay XP
  for a second copy. `repeatable_by: "virtue"` records which Virtue in the detail.
* **Flags:** the Mountain Folk tangent (Craft-difficulty heritage, no proprietary
  Merits) is out of scope — that is the Mountain Folk splat, not a Fae-Blooded.
* **Terrestrial MA RULED (2026-08-02): yes, and gated on Awakened Essence.** The user
  pasted p.47-48: "God-Blooded characters with the Awakened Essence Merit may also
  study the Charms of the supernatural martial arts, though they can learn only
  Terrestrial styles." Fae-Blooded are NOT excluded from that clause (only the
  parents'-Charms clause excludes them). The splat-wide `terrestrial_martial_arts`
  grant plus the existing `pool_requires_unlocking` gate gives exactly that: with
  Awakened Essence a Fae-Blooded reaches Terrestrial MA, without it both the buy path
  and chargen validation refuse. The older "unconditional" Phase-A ruling (line 352)
  is superseded by this page-first reading for the Fae-Blooded.

**Code-review fixes (2026-08-02, the day after Phase D clicked through; suite 1924 →
1929). Browser-verified the same day — the human clicked all five: the heritage
switch stays alive, a stale-origin save builds and reports `heritage-foreign-origin`,
the 3/3/2/3 Virtue spread prices two attuned dots at 2 BP, Prince of Chaos lists
"Essence 2", and the Fae picker still offers only Terrestrial MA.**
* **set_caste re-seeds the origin** (ui/editor.py) — changing the Heritage dropdown
  stranded the OLD heritage's origin (a Fae-Blooded's "Solar" parent, a Half-Caste's
  "Noble"), and ui.select raises ValueError on a value not among the new options, so
  the editor died. `set_caste` now re-seeds the way `set_exalt_type` does; the Origin
  select also folds in a stale loaded value so a mis-saved file renders (and is
  reported) instead of crashing. Two render routes pin both shapes.
* **Attuned Virtues draw on the free pool LAST** (validate.bonus_point_breakdown) — the
  old code priced `attuned_within - pool` (attuned first), discounting the FEWEST dots;
  the comment already said the goal was the opposite. Now the pool absorbs the
  non-attuned dots first, so the discount lands on as many priced attuned dots as
  possible. `test_virtue_attunement_prices_the_attuned_virtue_at_two_bp` asserted -1
  and is now -2, with a second all-below-cap case that was charging nothing.
* **Prince of Chaos's Essence prereq was missing entirely** — p.76 prints
  "Prerequisites: Transcendent Dream Shape, Essence 2"; the entry carried only the
  Charm half. Added `prerequisite_note: "Essence 2"`, and moved the three "Requires
  Essence N." sentences (Wyldward / Wyldwalk / Subtle Glamour) out of the descriptions
  into the same field — all four Essence prereqs are now structured, and the doc's
  earlier "they go in `prerequisite_note`" claim (line 50) is true.
* **`heritage-foreign-origin`** (validate.heritage_origin_issues) — an origin that is
  not one of the heritage's options is now reported distinctly from a blank one, so the
  stale value from the set_caste bug is visible instead of merely fatal.
* **Latent, recorded not fixed:** Transcendent Dream Shape's printed in-play rate is
  **7 XP per bonus dot** (p.79), which diverges from the chapter's generic "double the
  bonus-point value" (2 pts → 4 XP); Goblin Body's 4 XP/mutation point happens to match
  the generic rate. No post-lock purchase path reaches either today, so neither rate is
  wired — record this before building the post-lock path.
* **Second review pass (2026-08-02), both latent traps fixed — suite 1928 → 1929:**
  - **set_caste now finishes set_origin's job.** When the heritage switch re-seeds a
    stale origin, it also clears the upbringing and re-seeds camp/Calling — the
    staleness set_origin (editor.py) explicitly clears. Unreachable today (no splat
    has both castes AND an intra-splat origin set_caste would re-seed), but a trap for
    the next splat that has both.
  - **The "another Exalt type" refusals read as nonsense for a God-Blooded holding a
    God-Blooded Arcanos.** Both the buy path (`advancement.learn_charm`) and
    `check_splat_consistency` now say "belongs to the character's own God-Blooded
    splat but is barred for this character" when the Charm is the character's OWN
    splat and a heritage bar refuses it (the mortal branch makes the same call), and
    the ST foreign-charm toggle no longer waives a bar on the character's own
    catalogue.

**What to click:** a Fae-Blooded (Noble and Commoner) — Origin dropdown shows Noble/
Commoner; picker offers no Abilities/Spells and only Terrestrial Martial Arts; the
Advantages tab lists the glamour Merits and the noble-gated ones grey out for a
Commoner; a Fae-Blooded with Awakened Essence has a 16-mote single pool at Essence 2;
attuning Compassion prices its 4th dot at 2 BP and (current ×2) XP; a Noble may hold
TWO attunements (two Virtues), a Commoner may not.

**⚠ This splat was authored end to end by a cheap model (DeepSeek V4 Flash) and
code-reviewed afterwards — see `docs/delegated-authoring.md`.** The review, 2026-08-02,
found and fixed four defects; the two mechanical ones are written up under **Phase C**
below. Both were bugs of the same class, and it is the class this whole build keeps
producing: a rule described in a docstring, authored into data, and never wired to a
read site. Suite 1887 → **1897**. Phase C is **NOT browser-verified**.

## Phase C — the review fixes (2026-08-02, NOT browser-verified)

Suite **1897 green** (1887 before). Ten new tests in `tests/test_godblooded.py`. Nothing
here is a new feature; all four are printed rules that Phases A/B named but did not run.

### 1. The magic track (p.48) — the one that hid best

> "Terrestrial Circle Sorcery is available to all the remaining heritages save
> Ghost-Blooded and Abyssal Half-Caste. Conversely, only these heritages may learn
> Shadowlands Circle Necromancy."

`heritage_traits.magic_track` was authored `"necromancy"` on the Ghost-Blooded and had
**zero read sites**. It nevertheless *looked* correct, because the Ghost catalogue holds
no sorcery — Charm access produced the right answer for the heritage that was tested,
by accident.

The rule is two-way, and Charm access only gets it right where the borrowed catalogue is
single-track. Both cases where it holds both were live violations:

* an **Abyssal Half-Caste** could learn `abyssal.occult.terrestrial-circle-sorcery`;
* a **Solar Half-Caste** could learn `solar.occult.shadowlands-circle-necromancy`.

Fixed with `validate.heritage_magic_track` + `heritage_bars_initiation`, read in **both**
charm gates beside the existing heritage bar. The bar touches only Charms with
`grants_circle` — it restricts which magic a heritage may *unlock*, never ordinary
Charms. Because a Half-Caste's track follows their PARENT and not their heritage, it
needed a new parent-keyed `GodbloodedHeritage.magic_track_by_parent` alongside the
scalar; the scalar serves the Ghost-Blooded. Circle membership comes from the existing
`models.rules.TRACK_CIRCLES`, so no new mapping was invented.

**Greater circles were checked and are fine** — Celestial/Labyrinth are `min_essence` 4
and Solar/Void are 5, against a God-Blooded cap of 3, exactly as Phase B claimed. Worth
recording because the first probe of this *looked* like a second violation: it used
`charm_learnable_by_splat`, which is a splat-ACCESS predicate and does not see
`min_essence`. Access ≠ purchasability; do not conclude a bug from the access check alone.

### 2. The summoning bar (p.48)

> "No God-Blood can learn spells to summon and bind elementals or demons."

Never modelled, and — the part worth noting — **not in Phase A's Flags list either.** The
Flags section is an honest record of what the author knew they skipped, which is a subset
of what they skipped. Do not read it as exhaustive.

Circle access cannot express this: the barred spells sit inside Circles a God-Blood
legitimately holds. New `ExaltDefinition.barred_spell_ids` (the spell-side parallel to
`barred_charm_ids`), authored on the God-Blooded row only, read in **both**
`meets_spell_requirements` (which covers the picker and `advancement.learn_spell`) and
`check_spell_access` (hand-edited saves, new `spell-barred` issue code).

Barred: Demon of the First/Second/Third Circle, Summon Elemental. **Summon Ghost is
deliberately NOT barred** — the rule names elementals and demons only, and it is a
Shadowlands spell the Ghost-Blooded necromancy path is entitled to. A test pins that.
The four Man-Machine summoning spells sit in a Circle no God-Blood can reach;
`binding-filament-system` was left alone rather than guess what it binds.

### 3. Load-time link-checking for id-bearing fields

New `rules_db._check_charm_references`, covering `ExaltDefinition.barred_charm_ids` /
`barred_spell_ids` and the heritage's `barred_charm_ids` / `ox_body_charm_ids` /
`gift_charm_ids`. Verified by poisoning a copy of `data/` — all four kinds report in one
pass.

The failure this prevents is quiet in a specific way: **a dangling id in a bar list makes
the bar silently pass.** The Charm stays learnable, nothing raises, and a test asserting
the field's *contents* is green. All 39 of the Half-Caste's barred ids did resolve; the
check is for the next edit, not this one.

`ExaltDefinition.ox_body_charm_id` / `gift_charm_id` are deliberately NOT checked: the
loader's own synthetic fixtures in `test_rules_db.py` and `test_custom_content.py` name
splat Charms outside their miniature catalogues, and adding them broke 31 tests.

### 4. Stale identifiers

Three comments in `models/rules.py` referred to `Character.parent_exalt`, a field that
never shipped — the parent rides `Character.origin`. The fingerprint of a design change
made mid-implementation with the prose left behind, which is how defect 1 happened.

### Still open after the review

* **Inheritance `free_rating: 5`** is a strictly dominant choice — 5 dots cost nothing
  from the 6-dot Background pool and pay +30 BP (net +20 over Inheritance 1, measured).
  The human called this intentional for the test run, 2026-08-02, and noted an **ST
  option would make more sense**. p.61 backs that reading: "Storytellers should assign a
  consistent Inheritance rating for all characters." Not changed — the human's call,
  and easier to change before saves exist.
* **`heritage_power` and `allowed_backgrounds` are still dead fields** (zero read sites),
  both deliberately: `heritage_power` is headed for the Caste-info panel and
  `allowed_backgrounds` for after Half-Caste. Recorded so the next dead-field sweep knows
  these two are planned rather than missed.
* A fresh God-Blooded **starts in an error state**: `Character.essence_rating` defaults to
  2, `essence_start` is 1, and `editor.py:1378-1381` only clamps down past
  `essence_start_cap` (3) — so the splat switch leaves Essence at 2 and
  `magic-requires-awakened-essence` fires immediately. Mortals escape this because their
  cap is 1. Source is unambiguous (p.48 "All God-Blooded begin with Essence 1", p.50 Step
  Five "Record Essence (1)"). Left alone at the human's call — other splats also open in
  an error state, though for the blank-sheet reason rather than this one.

### What to click for Phase C

Nothing visual changed. The two things worth confirming in a browser: an **Abyssal
Half-Caste**'s picker no longer offers Terrestrial Circle Sorcery (and a **Solar
Half-Caste**'s no longer offers Shadowlands Circle Necromancy), and a God-Blooded
sorcerer's Spells page no longer lists Demon of the First Circle or Summon Elemental.

## Inheritance as an ST option (2026-08-02, review brief #3; **redesigned at the click-through**)

The Inheritance Background already carries p.61's own sentence — *"the Storyteller
assigns a consistent rating to set the series' power level"* — but the engine read
only the character's assigned dots. Since Inheritance dots are **free** to assign
(`free_rating 5`), that let a player self-assign five for +30 BP with nothing stopping
them. It is now a **TABLE-WIDE ST option** — and the human's click-through ruling
(2026-08-02) fixed what the option DOES:

* **`HouseRules.godblooded_inheritance_rating: Optional[int]`** (1-5, `None` =
  per-character) — a select on the ST Options tab. **It sets how many dots of the
  Inheritance Background are FREE, never the rating itself.** The human: "the ST could
  choose how many free points of Inheritance a player character gets... but only gets
  the extra BP if they have the background set on their sheet." So the bonus points
  and Flaw capacity always follow the character's OWN sheet rating; the ST's pick only
  waives the cost (no Background-pool dots, no above-cap bonus points) for dots up to
  it. Unset → the budget's `free_rating` (5) governs.
* **Engine** — `merits.inheritance_free_rating` (the ST value or the data default)
  is read by `background_pool_spend` to waive the Inheritance background's pool AND
  above-cap cost; `merits.inheritance_rating` (the sheet rating) still feeds the bonus
  pool and Flaw cap. Two reads, so the free grant can never move the rating.
  **The first draft (ST rating replaces the sheet for the bonus pool) was wrong and
  is reverted** — it granted the bonus without the sheet background and charged the
  above-cap two points on a 4-dot Inheritance with the ST at 4.
* **Latent bug fixed on the way** — the ST tab's `set_rule` `bool()`-coerced *every*
  value, so the M&F-method select had been storing `True` instead of `"backgrounds"`.
  Non-boolean selects now store their value. (Nothing had noticed: the suite never
  exercised the tab's write path.)
* 9 new tests (5 engine, 4 UI), suite **1897 → 1906**; two more after the redesign.

**What to click:** ST Options on a God-Blooded — set **Divine**, give the character
Inheritance 4 on their sheet, and confirm nothing is charged for the background while
the bonus pool still shows the +24 for a rating-4 sheet; set the ST to 2 and confirm
the third and fourth dots now cost (1 pool dot + the two-point above-cap rate) with the
bonus pool unchanged. And set the M&F method to "Like Backgrounds", save, reload — the
dropdown must still read "Like Backgrounds", not blank or Experience.

## The Half-Caste bar list — human-ruled (2026-08-02, review brief #2)

The review brief called the curated bar list a placeholder ("the 39 current ids") and
p.47 makes the ST "the final arbiter" of the no-perfect/persistent restriction, so the
list was derived deliberately from the catalogue and the human ruled it. The 39 broke
into three rules, not one:

* **8 God-Blooded Arcanoi** — not part of the perfect/persistent bar at all; the
  browser-finding fix ("a Half-Caste learns their PARENT's catalogue"). Kept.
* **7 Maiden-approval Charms** (p.47 rule #3) — each carries the literal "Learning
  this Charm requires the [X] Maiden's approval" sentence. Kept. (One reading noted
  but not taken: p.47's Sidereal clause says a Sidereal Half-Caste may *learn* them
  "as a theoretical exercise" but cannot enact them — learn-but-inert rather than
  barred. The human ruled them barred; only a Sidereal Half-Caste could reach them.)
* **24 perfect/persistent candidates** (p.47 rule #2) — 16 clearly perfect or
  persistent-scene from the rules text (Heavenly Guardian Defense, Fivefold Bulwark
  Stance, …), 3 borderline KEPT on the human's call (Snake Head Defense — persistent
  anti-unanticipated-attack ward; Smoke Obscuring Effect — persistent dodge-aid;
  Blade of the Battle Maiden — scene-long parry enhancer), 5 CUT (Cunning Porcupine
  Defense, Trouble Reduction Strategy, Neighborhood Relocation Scheme, Joy in
  Adversity Stance — retaliation/conduit/terrain/mote-recovery, none a defense), and
  1 mis-inclusion REMOVED (Perfection of the Visionary Warrior — a sight Charm,
  "suffers no visibility penalties").

The list is now **34 ids**. A test pins the ruling (`test_the_half_caste_bar_list_is_human_ruled`),
so it cannot silently drift. Suite **1906 → 1907**. **NOT browser-verified** — the five
unbarred Charms now appear on a Half-Caste picker and should be eyeballed there.

## Phase B — Half-Caste (the cross-splat Charm-access piece)

Shipped with the parent-Exalt axis, the heritage Charm bars, and the Lunar gift cap.

### The parent-Exalt axis (in the **Origin** dropdown, human 2026-08-02)

`Character.origin` carries the Half-Caste's parent Exalt type ("Solar" / "Dragon-Blooded"
/ "Lunar" / "Sidereal" / "Abyssal") — the Origin dropdown for a God-Blooded, gated on
the heritage so a Ghost-Blooded never sees it. `heritage_traits.charm_access_parent`
makes `validate.heritage_charm_access` return the parent's catalogue instead of a static
list, so a Solar Half-Caste learns Solar Charms, a Lunar one Lunar, etc. Every parent
shares the single God-Blooded budget (the parent keys Charm access, not dots).

### The four printed rules (p.47)

1. **Parent catalogue only** — the parent-narrowed `heritage_charm_access` +
   `foreign_charms_barred`.
2. **No perfect/persistent scene-length defense** — the heritage's `barred_charm_ids`
   (34 ids), checked FIRST in both charm gates. **Human-ruled 2026-08-02** — see the
   bar-list section below; the review brief called the earlier list a placeholder and
   p.47 makes the ST the arbiter, so the human settled it.
3. **Sidereal Maiden-approval bar** — the 7 Maiden-approval Charms, same list (only a
   Sidereal Half-Caste can reach them, so one list covers both bars). Confirmed from
   data: each carries the literal "Learning this Charm requires the [X] Maiden's
   approval" sentence.
4. **Lunar 2-form cap** — heritage-keyed gift machinery (`gift_charm_ids`/`gift_caps`
   keyed by parent): a Lunar Half-Caste's Deadly Beastman Transformation resolves to
   the Lunar charm capped at 2, not the Essence cap.

Also: **6/5/4 attribute pools** (the prose-p.47 ruling, via
`validate.effective_attribute_pools`), the **Ess×5+ΣV** single pool (no Willpower term,
p.66; 14 at Essence 2 with all-1 default Virtues), the **Essence-3 cap bars greater
magic circles** (they need Essence 4+, no new machinery), and the **5 Half-Caste M&F**
(Breed True, Chillikin Companion, Anima Powers, Material Resonance, Inherited Curse).
The parent-specific M&F gating (Breed True = beastmen only, Chillikin = Solar parent
only) and the "Artifact Attunement"-vs-"Magical Attunement" prereq naming are flagged in
the descriptions, not enforced.

**Browser finding, 2026-08-02:** a Half-Caste saw the God-Blooded's own Arcanoi (they're
splat-wide, `exalt_type "God-Blooded"`), which put the Arcanoi tab on the picker. Fixed:
the Half-Caste heritage **bars all eight God-Blooded Arcanoi** (Death-in-Life, the
necromancy initiation, the spirit/Arcanos Ox-Body) — a Half-Caste learns their parent's
catalogue — and **`ox_body_charm_ids`** (parent-keyed) sends their Ox-Body to the
parent's version instead. The Arcanoi tab is now off a Half-Caste's picker; the
Ghost-Blooded keeps all of it.

## What shipped in Phase A

The **core God-Blooded splat** (chargen, Inheritance, Awakened Essence, XP/BP rows,
no-Combos bar) plus the **Ghost-Blooded heritage** — the one that needed the least new
Charm work because the Arcanoi already ship. Per `docs/adding-a-splat.md`, this was
90/10 data by volume and the **heritage Charm-access rule** was the real project.

### The four data rows + theme

* **`exalts.json`** — `God-Blooded`: `caste_noun "Heritage"`, `tier "Terrestrial"`,
  `essence_cap 1` (Awakened Essence → 3), `combos_available false`, `single_essence_pool`,
  `foreign_charms_barred true`, `terrestrial_martial_arts true`, `ox_body_charm_id` → the
  p.83 Ox-Body. No `unlocked_essence` at the splat level — it is per-heritage.
* **`castes.json`** — one heritage row, `ghost-blooded`, with a `heritage_traits` block:
  the Ghost-Blooded pool formula (p.66), `charm_access ["Ghost"]`, `magic_track
  "necromancy"`, the heritage power.
* **`chargen_budgets.json`** — 6/4/3, 22 Abilities (≥1 favoured, cap 3), 6 Backgrounds,
  21 BP, Essence 1→3, Virtues 1+5, plus **two new fields**: `inheritance_bonus_points`
  [0,6,12,18,24,30] and `inheritance_flaw_cap` [0,10,15,15,20,20]. `background_rules`
  makes Inheritance assigned-not-bought (`free_rating 5`, `min_rating 1`, `max_rating 5`).
* **`costs_bonus.json`** — the p.50 table: Essence 2 = 5 / 3 = 15 (flat, a new
  `essence_by_rating` BP shape), Charm 7, **`magic_charm` 10** (the sorcery/necromancy
  initiation, keyed off `Charm.grants_circle`).
* **`costs_xp.json`** — the p.49 table: new Charm/Spell 15 (no favoured discount),
  **`new_magic_charm` 25**, Essence ×12, MA 15.
* **`backgrounds.json`** — Inheritance and Patron, `exalt_type "God-Blooded"`.
* **`theme.py`** — `_GODBLOODED` (teal; the non-Exalt colour scheme is UNDECIDED and
  this is a placeholder).
* **`merits_flaws.json`** — 27 Godblooded entries: the Common set + the Ghost-Blooded
  set + Awakened Essence + Magical Attunement. Heritage-gated via `barred_castes`.

### Charms (8 new, pp.48, 83-85)

* The **God-Blooded Ox-Body Technique** (SPIRIT, ARCANOS) — two −2 levels per purchase,
  capped by **Conviction** (a new `Charm.repeatable_cap_virtue`, the `min_virtue` retarget
  applied to a repeatable cap).
* The six **Death-in-Life Path** Arcanoi (Transubstantiation of Flesh → Lower Soul
  Ascendant → Spiteful Essence Onslaught; and Transubstantiation → Wraith Form
  Transformation → Ghost Body Evasion / Restless Spirit Sojourn), Virtue-keyed like the
  shipped Arcanoi.
* **Shadowlands Circle Necromancy** — the Ghost-Blooded's own copy of the initiation
  (p.48), authoring the necromancy path the heritage is entitled to. **Grouped with the
  Ox-Body under a `general_arcanoi` category** (human, at the browser, 2026-08-02) so
  both live on the picker's Arcanoi page rather than the general Charms page; Occult 5
  is its gate via `extra_min_abilities` (the charm groups with the Arcanoi, so Occult
  cannot be its primary keying). ⚠ the Occult-5 reading applies PG p.48's generic
  "Terrestrial initiation" requirement to the necromancy path — confirm with the rules
  authority.

### Engine

* **`CasteDefinition.heritage_traits: Optional[GodbloodedHeritage]`** — ONE optional
  block (unlocked_essence, charm_access, magic_track, attribute_pools,
  allowed_backgrounds, heritage_power), per the scope-doc design: the shared class gains
  one field, not six. Named `heritage_traits`, not `godblooded`, so the crossover can
  reuse it.
* **The heritage Charm-access rule** (`validate.heritage_charm_access`) — a heritage
  borrows another splat's catalogue ("learn the Charms of their magical parents, exactly
  as their parents", p.47). Restated in BOTH `charm_matches_splat` and
  `charm_learnable_by_splat`, inside the `foreign_charms_barred` branch — the ghost
  preflight bug (a bar on only one of two routes) was the template for getting it right.
* **Inheritance → the BP pool and Flaw cap** (`validate.bonus_point_breakdown` +
  `merits.inheritance_rating`) — a Background that resizes both, indexed by rating.
* **The Awakened-Essence gate** (`validate.pool_requires_unlocking` +
  `validate.magic_gate_issues` + the `advancement` refusals) — a splat whose pool must
  be unlocked may not hold Charms/spells/Essence-above-start until it is (p.49). The
  pool formula itself lives on the heritage, so the "is it Merit-gated" check had to
  look there, not at the ExaltDefinition — the one bug the tests caught.
* **`derive.essence_pools`** — the per-heritage unlocked spec wins when the pool is
  unlocked (`single_essence_pool` then merges it, like the ghost).
* **Ox-Body / cost shapes** — `repeatable_cap_virtue`, `essence_by_rating` BP,
  `magic_charm`/`new_magic_charm` (both keyed off `grants_circle`).

### Rulings made / recorded

1. **Heritage is the CASTE axis** — `caste_noun "Heritage"`, `origin` stays empty
   (human, 2026-08-02).
2. **Half-Caste attributes are 6/5/4** — prose p.47 wins; the p.50 summary's 6/5/3 is a
   printing error (human, 2026-08-02). Not exercised in Phase A.
3. **Essence pool is a single merged pool** (human, 2026-08-02).
4. **Inheritance ≥1 dot required** (human, 2026-08-02).
5. **Terrestrial MA is unconditional** — p.234 names God-Blooded with thaumaturges and
   ghosts; p.47's "with the Awakened Essence Merit" gate is not enforced. Flagged; the
   human can veto at the click-through. **⚠ SUPERSEDED for the Fae-Blooded 2026-08-02**
   (see the Phase D section): the human pasted p.47-48, which gates the supernatural
   martial arts on the Awakened Essence Merit — and the existing `pool_requires_unlocking`
   gate delivers exactly that on the buy path and in chargen validation.

### Flags (printed rules deliberately not modelled in Phase A)

**⚠ This list is not exhaustive, and the review proved it.** p.48's summon-and-bind bar
was missed outright and appears nowhere below; it shipped in Phase C. A Flags list
records what its author knew they skipped — treat it as a floor on the gaps, never a
ceiling, and run the prohibition sweep in `docs/delegated-authoring.md` against the
source before trusting it.

* **"Inheritance bonus points may not be spent on Backgrounds"** (p.61) — this build has
  one unearmarked BP pool; the Oathbound-Magic earmark was already not modelled. The
  p.61 text is on the background's description.
* **The Merit-gated Backgrounds** (Artifact requires Magical Attunement, Cult/Familiar
  require Awakened Essence) — the backgrounds and Merits are authored, but the
  *prerequisite gate* is not enforced.
* **Aura of Power's pool split** (1/3 Personal, 2/3 Peripheral) contradicts the
  single-pool ruling for a character who takes it; not modelled.
* **The six "changed" spirit Charms** (Benefaction, Largess, Endowment, Imprecation,
  Malediction, Scourge) — modifications of originals we don't have; not authorable until
  the GoD pages land.
* **The other four heritages, Exalted-God-Blooded, Akuma, Ghost-Blooded Essence 4+** —
  deferred (see the scope note's build order in the git history / the plan file).

## What's next

**Fae-Blooded SHIPPED 2026-08-02** — the third heritage (see the Phase D section above);
its `"none"` magic-track sentinel closed the Phase C trap, and the Noble/Commoner origin
axis is in. **Two heritages remain: God/Demon-Blooded**, which wait on the Games-of-
Divinity spirit-Charm pages for more than the chapter's four self-contained Charms. The
**Exalted-God-Blooded crossover**, **Akuma**, **Ghost-Blooded Essence 4+** and the three
Phase-A flagged gaps (Inheritance BP earmark, Merit-gated Backgrounds, Aura of Power's
pool split) are deferred — see the Flags section.

**RULED 2026-08-02 — the Occult-5 necromancy initiation stands.** p.48 states the
Essence 3 + Occult 5 requirement for the *Terrestrial* initiation only and says nothing
about the necromancy path; the human's ruling is that **mirroring it is the most sensible
reading**, so `godblooded.general-arcanoi.shadowlands-circle-necromancy` keeps its
`min_essence 3` + `extra_min_abilities` Occult 5. Do not "fix" this toward the literal
page. The ⚠ in the Charms section above and in the Charm's own description are now
resolved and can be dropped on the next edit that touches them.

**Both open review items are now RESOLVED (2026-08-02):** the Half-Caste bar list was
ruled by the human — **34 ids**, the five non-defenses cut and the mis-inclusion
Visionary removed (see the bar-list section above) — and **Inheritance is an ST option**
(see its section above). Nothing on that pair is open anymore.

## God/Demon-Blooded — the last two heritages (2026-08-05 status)

**The spirit-Charm catalogue is scattered across SIX books.** The human surveyed the
charmtrees PDF and reported (2026-08-05): the spirit Charms a God-Blooded / Demon-Blooded
draw from live in the **Storyteller's Companion, the corebook, Exalted: The Lunars, the
Player's Guide, Ruin of Rathess, and Games of Divinity**. Only the GoD appendix
(pp.125-127, "Appendix: Spirit Charms") is pasted so far — **7 template Charms**,
Virtue-keyed (Conviction: Soul Rapt, Worldly Illusion; Temperance: Donning Spiritual
Armor, Essence Inveigle; Valor: Uncanny Prowess, Creation of Perfection, Spirit-Cutting;
**no Compassion set**). Even those reference prerequisites not in the set (Possession,
Harrow the Mind, Sustenance). The other five books hold mostly named gods' signature
Charms, not the generic set.

**The charm-access rule (PG p.48, human-pasted 2026-08-05):**
* **God-Blooded** "learn spirit Charms, exactly as their parents." **Cannot learn Wyld
  Shield**; **Portal** is only a lesser variant (permanent Willpower instead of
  temporary, ≥1 success per use).
* **Demon-Blooded** "follow the same rules regarding Charm selection as God-Blooded" (so
  the Wyld Shield ban carries); their Portal is Malfeas-only (can only enter Malfeas /
  return to the exact spot in Creation; escape difficulty = own Essence).
* **The parentage gate is an ST judgment, not a mechanic** — "limit or deny access to
  those Charms obviously inappropriate to a God-Blood's parentage." Not builder-
  enforceable, which is why authoring all six books is low-return for a builder.

**Scoped plan (human's call 2026-08-05: "check the rule, then scope"):** native
catalogue = the **GoD appendix generic set** (7 Charms now; any appendix pages past
p.127 if they exist), plus **Wyld Shield** and **Portal** as catalogue entries flagged by
the existing data-driven `barred_charm_ids` (the Ghosts/Spirit-Walking hook) so the two
rule exceptions are representable. **The other five books are deferred** — mostly
ST-gated god-specific Charms; pages get authored as the human pastes them.

**Still blocked on source (all on the human's home PC):**
1. The God-Blooded and Demon-Blooded **chargen sections** (PG CH2, ~pp.44-59 —
   attribute pools, abilities, backgrounds, essence pools, BP budget, Awakened Essence
   handling) to define the two heritage rows in `castes.json`.
2. Their **specific Merits & Flaws**.
3. **Wyld Shield** and **Portal** pages (for the two rule exceptions).
4. The rest of the **GoD appendix** past p.127, if it exists (Compassion set?).

**Engine readiness:** the Virtue-keyed Charm mechanism (`min_virtue`, Ghosts' Arcanoi),
`barred_charm_ids`, the heritage `charms_available` flag and the `magic_track` sentinels
are all in place — the day the pages land, God/Demon-Blooded is a data + one-flag flip,
not a modelling job.

## God/Demon-Blooded — heritage rows + M&F AUTHORED (2026-08-07, NOT browser-verified)

The two heritage rows and 16 M&F shipped 2026-08-07 from the PG CH2 pages already on
this machine (the human's "I'm on the home pc — feel free to do god/demons"); **everything
here is data + tests, no browser yet.**

### The spirit-Charm catalogue — AUTHORED (79 Charms, 2026-08-07)
**The catalogue is 79 Charms.** It landed in three batches over 2026-08-07 and the
subsections below are written in the order they happened, so read the count here and
not the ones inside them: 8 (GoD appendix + PG) → 20 (+ the 12 corebook Charms) → **79**
(+ the 46 Storyteller's Companion CH3, 4 more PG, 3 Ruins of Rathess, 3 Lunars). Sources
by book: STC 50, corebook 12, GoD 6, PG 5, RoR 3, Lunars 3.

The GoD appendix (`images/Non-Exalts/Spirit Charms/CH 4 - Spirit Charms.md`,
pp.125-127) landed first and the 8-strong `spirit.` catalogue shipped:
`data/charms/spirit_templates.json`, exalt_type **"Spirit"**, one category
`spirit_templates`. Seven GoD appendix templates — Soul Rapt (Conviction 5),
Worldly Illusion (Conviction 4), Donning Spiritual Armor (Temperance 2), Essence
Inveigle (Temperance 3), Uncanny Prowess (Valor 2), Creation of Perfection (Valor
2), Spirit-Cutting (Valor 3) — plus **Essence-Gifting Method** (Compassion 3, the
chapter's missing Compassion set filled from the Mortals PG chapter p.123, the
Investment Charms sidebar). All 8 are Virtue-keyed (`min_virtue` + the rating in
`min_ability`), the ghost-Arcanoi shape. (They were briefly grouped under **Arcanoi**,
since any `min_virtue` category was an Arcanos — that is no longer true, see item 4.)

**Then the 12 corebook spirit Charms landed the same day** via the VLM
transcription pipeline (see below): the corebook's four Virtue sets, transcribed
from `Exalted.pdf` pp.291-294 / book pp.290-293 into `images/Non-Exalts/Spirit
Charms/CH 8 - Corebook Spirit Charms.md`, human-vetted, authored into the same
`spirit_templates.json`. **Compassion:** Measure the Wind, Stoic Endurance, Touch
of Grace. **Conviction:** Harrow the Mind, Possession, Stoke the Flame.
**Temperance:** Cunning Thief, Host of Spirits. **Valor:** Essence Bite,
Materialize, Principle of Motion, Words of Power. (Note the corebook itself says
spirit Charms have NO prerequisites — the wired prereqs below are the GoD
appendix's own cross-references, which the appendix prints on its templates.)

**⚠ Things to know about the catalogue:**
1. **The category is `spirit_templates`, NOT `spirit`** — the Lunar Charms already own
   category `spirit` (the Spirit ability), and the picker's `_arcanoi_categories` is a
   GLOBAL set of every `min_virtue` category, so a virtue-keyed `spirit` category would
   have hijacked the Lunar page off Abilities onto Arcanoi. A test pins the set; the
   Lunar picker stayed green.
2. **All four off-catalogue prereqs are now WIRED** (the STC batch closed the last
   two). Soul Rapt → `possession`, Worldly Illusion → `harrow-the-mind` (corebook),
   Essence Inveigle → `sustenance`, Essence-Gifting Method → `benefaction` AND
   `dreamspeak` (STC). In every case the printed prereq moved out of the description
   into the `prerequisites` field; a test gates Soul Rapt on knowing Possession.
   **Nothing in the catalogue names a Charm that does not exist** — the loader's link
   check would fail the suite if it did.
3. **Wyld Shield + Portal are AUTHORED** (STC CH3, `spirit.spirit-templates.wyld-shield`
   / `.portal`), and the p.48 ban is live: Wyld Shield is in BOTH heritages'
   `barred_charm_ids`. Wyld Barrier requires Wyld Shield, so it is unreachable for
   God/Demon-Blooded by prerequisite cascade rather than by its own bar — correct, and
   deliberate. **The two Portal variants ride the heritage descriptions only** (the
   God-Blooded's costs permanent rather than temporary Willpower; the Demon-Blooded's is
   Malfeas-only with escape difficulty = own Essence): the catalogue holds the one
   printed stat block, and the variance is the Storyteller's to apply. (The ids use
   hyphens per the separator convention — the `spirit_templates` category name is the
   underscore exception.)
4. **Spirit Charms are NOT Arcanoi in the picker or on the sheet.** Both were
   identified by `min_virtue` alone; that now excludes `exalt_type == "Spirit"`
   (`picker._arcanoi_categories`, `view._section_label`). They are Charms — the human's
   ruling 2026-08-07, *"they're charms"* — so they sit on the Abilities page and the
   sheet files them under **Charms**. Because the one `spirit_templates` category spans
   all four Virtues, `view.virtue_split` presents it as four trees
   (`spirit_templates:<virtue>`), mirroring the ghost Arcanoi where each path is
   already its own tree. `build_charm_graph` understands that composite key; the
   `martial_arts:<style>` keys are NOT composites and stay on the direct-equality path.
   `spirit_templates` is the only multi-Virtue category in the ruleset, so no other
   splat's picker is touched.

**Access wiring (engine, verified by tests):** `charm_access: ["Spirit"]` resolves on
both routes (`charm_matches_splat` AND `charm_learnable_by_splat`) — the God-Blooded
"learn spirit Charms exactly as their parents" and the Demon-Blooded "follow the same
rules" (p.48). The other three heritages cannot touch the catalogue (Ghost-Blooded
borrow the Arcanoi, the Half-Caste the parent's, the Fae-Blooded nothing). The Death-in-
Life bar, the necromancy bar and the shared Ox-Body all still hold with the catalogue
present.

### The two heritage rows (`castes.json`, caste count 39 → 41)
* **God-Blooded** — `origin_options: ["Divine", "Elemental"]` (the sub-axis ruling,
  human 2026-08-07: the printed M&F are "Divine God-Blooded only" vs "Elemental
  God-Blooded only", so the sub-axis is an **origin dropdown**, the Fae-Blooded
  precedent, NOT a separate axis or a new field). `charm_access: ["Spirit"]`,
  `magic_track: "sorcery"`, `barred_charm_ids` = the 6 Death-in-Life Arcanoi (ghost
  heritage powers; the shared Ox-Body stays, p.47 "only two -2 health levels").
* **Demon-Blooded** — **no origin axis** (the book prints no Divine/Elemental split).
  Same `charm_access`, `magic_track`, and Death-in-Life bar.
* Both ride the p.66 pool: `Ess × 5 + Willpower × 2 + Σ Virtues`
  (`unlocked_essence`: personal_essence_coeff 5, personal_willpower_coeff 2,
  personal_virtue_mode "all", personal_virtue_coeff 1), the shared
  `mf.awakened-essence` pool, and the p.51/p.53 heritage powers (God: perceive sanctum
  entrances and immaterial spirits; Demon: perceive infernal energies, pierce
  shapechanging). `magic_track "sorcery"` bars Shadowlands necromancy via the existing
  `heritage_bars_initiation` (only touches `grants_circle` Charms).

### The 15 new M&F (`merits_flaws.json`, all gated by `barred_castes` on the four other
heritages and by `required_origins` where the book splits)
* **Divine God-Blooded** (8): Divine Apprentice (3 Social, prereq "Patron at least 3"),
  Sanctum's Key (1 Supernatural), Artisan of Prayers (3), Respiring Touch (7),
  Elemental Dominion (7, prereq Respiring Touch), Primal Restoration (7),
  Elemental Immunity (8, prereq Dominion, "Essence 2"), Elemental Archetype (2 Mental
  **flaw**).
* **Demon-Blooded** (7): Gatekeeper (1 Social), Immunity to Possession (3),
  Mark of Infernal Favor (3), Ordination of Lies (5), Ordination of Pain (5), Unholy
  (4 Supernatural **flaw**, prereq Affected by Wards), Walking Blasphemy (5
  Supernatural **flaw**, prereq Unholy, "Inheritance 3").
* Elemental Dominion and Unholy descriptions begin with their printed prereq line
  ("Prerequisites: Respiring Touch." / "Prerequisites: Affected by Wards.") so the
  `test_every_description_matches_the_source_text` fidelity check passes on the two new
  entries.

### The Ox-Body split (ruling 2026-08-07, human)
PG p.83 lists Ox-Body Technique as **(SPIRIT, ARCANOS)** — one Charm living in two
catalogues. The human's ruling: **copy it into the Spirit catalogue for the
God/Demon-Blooded and make the Arcanos version Ghost-Blooded-only.**

* **New spirit Charm** — `spirit.spirit-templates.ox-body-technique` (Conviction 1,
  repeatable cap by Conviction, two −2 levels, p.83 text). The `spirit_templates`
  catalogue is now **79 Charms**; `SPIRIT_IDS` in `test_godblooded.py` carries it under
  Conviction.
* **The arcanos version is barred for God/Demon-Blooded** — both heritage rows append
  `godblooded.general-arcanoi.ox-body-technique` to `barred_charm_ids` (now 8 entries),
  so only the Ghost-Blooded can learn it. This emptied the `general_arcanoi` category for
  them (its only other member was the already magic-track-barred necromancy initiation),
  so **the Arcanoi picker page no longer exists for God/Demon-Blooded** — the picker
  tests now assert `spirit_templates:<virtue>` trees instead. That is correct new
  behaviour, not a regression.
* **New per-heritage field** — `GodbloodedHeritage.ox_body_charm_id` (singular), checked
  after `ox_body_charm_ids` (the parent-keyed Half-Caste override) and before the splat
  fallback. God/Demon-Blooded → the spirit copy; Ghost-Blooded keeps the splat-level
  arcanos. `rules_db.py` link-checks the new field.

### Investiture of Infernal Glory — RULED OUT (human, 2026-08-07)
The stat block IS transcribed (p.87: Cost 60 motes, 6 Willpower; Min Compassion 3 /
Conviction 5 / Valor 4; Min Essence 7; prereqs Endowment, Geas, Memory Transference,
Scourge) but it fits neither the single-`min_virtue` model nor God/Demon learnability,
and the AKUMA prose (pp.382-391) makes it Demon-Prince-only. The human closed it:
*"Akuma aren't PCs without heavy ST intervention. So we can, until it's needed, ignore
it."* **Intentionally unauthored** — the stat block stays in the transcription for when
it is needed; do not author it.

### The sorcery gap — CLOSED 2026-08-08 (PG p.48, the Spells subheading)
The human supplied the page: *"All God-Blooded with the Awakened Essence Merit apart
from Fae-Blooded may also learn to cast spells. Terrestrial Circle Sorcery is available
to all the remaining heritages save Ghost-Blooded and Abyssal Half-Caste. Conversely,
only these heritages may learn Shadowlands Circle Necromancy. Greater circles of sorcery
and necromancy lie beyond the purview of the God-Blooded… the Charms necessary to unlock
spells (Terrestrial Circle Sorcery, for example) cost 10 bonus points. Once unlocked,
spells cost the same as Charms (7 bonus points each). Characters must also have Essence 3
and Occult 5 to undergo the Terrestrial initiation. No God-Blood can learn spells to
summon and bind elementals or demons…"*

**It cost one Charm.** Every other half of the rule was already built and only lacked
something to bite on:

* **`spirit.spirit-templates.terrestrial-circle-sorcery`** — the mirror of
  `godblooded.general-arcanoi.shadowlands-circle-necromancy`, same shape: `min_essence`
  3, Occult 5 via `extra_min_abilities`, `grants_circle: "Terrestrial"`, 1 Willpower.
  **⚠ The 1 Willpower cost is INHERITED, not printed** — p.48 gives no mote/Willpower
  line, so this follows the core initiation stat block exactly as the Ghost-Blooded
  necromancy entry already did. Flagged for the rules authority; the point costs
  (10 BP / 25 XP) ARE printed.
* **The heritage split needed no code** — `heritage_bars_initiation` already keyed off
  `magic_track`, so sorcery-for-God/Demon-Blooded, necromancy-for-Ghost-Blooded and
  neither-for-Fae-Blooded fell out of data that was already there. The **Abyssal
  Half-Caste** exception the page names likewise already worked, via
  `magic_track_by_parent` — that heritage answers differently by origin, which is the
  case the docstring says charm access alone cannot express.
* **The greater-circle bar** was already live (the first circle of the track only).
* **The summon/bind ban** was already authored splat-level in
  `ExaltDefinition.barred_spell_ids` — all four spells, so it holds for every heritage
  including the Half-Caste whatever the parent.
* **The prices** were already authored: God-Blooded `magic_charm` 10 BP against the
  ordinary Charm's 7, and `new_magic_charm` 25 XP.

**⚠ The trap it walked into, and the reason `virtue_split` changed.** This Charm has no
Virtue — p.48 gates it on an Ability. The picker splits `spirit_templates` into one tree
per Virtue, so a Charm with no Virtue fell through EVERY tree and would have been
present in the data and unbuyable in the UI: [[dead-effect-fields]] wearing a new hat.
`virtue_split` now emits a final **`:general`** sub-tree whenever a split category holds
un-keyed Charms, and `build_charm_graph` resolves it. A test asserts every Charm in the
catalogue is reachable from exactly one sub-tree, so the next un-keyed addition cannot
vanish silently. **Splitting a category is only safe if the split accounts for every
Charm in it.**

**Still open on the necromancy side (pre-existing, unchanged):** that entry's
description carries a ⚠ noting its Occult 5 is the *Terrestrial* requirement applied to
the necromancy path by analogy. p.48 names only the Terrestrial initiation, so the
sorcery Charm is now certain and the necromancy one is still a reading. Ask before
relying on it.

### ⚠ Pre-existing machine-only test failure (NOT caused by this work)
`test_every_description_matches_the_source_text` fails with 46 entries on this machine
and passes on the laptop: the test routes each M&F by `source.page` to pasted chapters
in `images/`, and the laptop lacks `CH2 - Godblooded.md` (entries defer) while this
machine has it (check resumes and the descriptions summarize the fuller printed text →
below 92%). The two new entries were brought to parity and are NOT in the failing list.
Leave the 46 alone until the human decides; they are not a regression.

## The Elemental Powers — SHIPPED 2026-08-08

**Human's ruling (2026-08-08), against PG p.68 (CH2 - Godblooded.md):** the elemental
powers are a **9-power learnable catalogue for Elemental-origin God-Blooded** — their own
page of the Charms picker, bought at **7 BP chargen / 14 XP in play** ("learned in play
for a number of experience points equal to double its bonus point value"). They are NOT
spirit Charms (no cost/type/duration lines) and NOT adversary traits. The old
`mf.elemental-power` Merit is **retired (deleted)** — the nine powers replace it.

**The learnable set** (p.68, "of the elemental powers on page 56 of GoD, only Consume
Element and Plague of Menaces can be learned"): the 7 Core p.296 powers (Aegis, Coarse
Skin, Dragon's Suspire, Element's Domain, Enshroud, Mobility, Rejuvenation) + Consume
Element + Plague of Menaces (GoD p.56). The other four GoD powers (Day to Night,
Elemental Unction, Foul the Waters, Immolation) are elemental-spirit traits, **not
authored.**

**Prereqs:** every power requires the `mf.elemental-dominion` Merit + Essence 2 (the
retired Merit's own prereqs); **Rejuvenation additionally requires `mf.primal-restoration`.**
`activation` and `description` are **descriptive text only** — decision 0008 keeps combat
effects as text (soak bonuses, damage dice, an attack roll all ride the prose).
**Training time is NOT built** (standing 2026-07-30 ruling — the p.68 "takes a number of
days equal to the bonus point cost" clause stays descriptive).

**Where it lives:** `data/elemental_powers.json` (9 entries, ids `elemental.<slug>`), a new
`RuleSet.elemental_powers` catalogue loaded and link-checked like merits;
`Character.elemental_powers` + snapshot + lock; `engine.costs.elemental_power_xp`
(7 BP × the `new_merit_bp_multiplier` doubling → 14, deliberately NOT the God-Blooded
new-Charm rate of 15); `engine.advancement.learn_elemental_power` (learn / audit / undo /
`drop_merit` dependents scan all extended); the picker's **Elemental Powers** page gated on
`validate.elemental_powers_available` (God-Blooded AND origin Elemental — every other
origin/splat's tab bar is unchanged); `engine.merits.merit_ids_held` for the
required-Merit check (containment rule decision 0011: Merit ids are named only there and
in data); and the **Sheet** now lists owned powers — the click-through found the picker
had them but the Charms & Sorcery band did not, so `SheetView.elemental_powers` carries
them as their own headed section (like Arcanoi/Gifts) in `charm_sections` and the editor's
picker panel, kept off the flat `view.charms` that tests pin.

⚠ **The 9 descriptions are lifted from the un-vetted VLM transcription** — a fabrication
incident is documented below on exactly this page ("Consume Element" originally carried
invented text). **The human must eyeball the 9 descriptions in `data/elemental_powers.json`
against the book before browser-verify** — the JSON is the durable copy (`images/` is
gitignored). The transcription lives at `images/Non-Exalts/Spirit Charms/Elemental Powers
- Core p296 + GoD p56.md` (home PC only); re-run the pipeline below on another machine if
needed.

**The pipeline recipe (it worked; reuse it):** `pdftoppm -r 300 -png`, page offset **+1
in both books** (Core p.296 = `Exalted.pdf` p.297; GoD p.56 = `Games of Divinity
(oef).pdf` p.57 — offset verified against the already-vetted GoD p.125 transcription,
not assumed), then `qwen3-vl:8b-instruct` via ollama with `num_ctx: 16384`,
`temperature: 0` and `tools/VLM_TRANSCRIPTION_PROMPT.md`. ~30s per image.

**⚠ The trap that made the human's vetting pass necessary:** GoD p.56's sidebar spans the
full page width. A 50/50 column split — correct for the corebook pages — cut every entry
in half, and **the VLM bridged the gaps with fluent invented text while reporting
`UNCERTAIN: none`.** "Consume Element" came out as *"The element burns motes of Essence
burned (e.g., 10 motes burned = +5 soak) against natural elements such as fire."* It was
caught only because it was incoherent; the full-page re-run then matched the discarded
right-column fragments word for word. **A confident `UNCERTAIN: none` is not evidence
the page was read correctly — check the layout before choosing the crop.** Numbers were
cross-checked against independent tesseract OCR (Core 5/5 exact; GoD's distinct values
1/3/5/10/15/16L all agree). Two stray transcription notes: (a) `Immolation` (GoD) still
reads oddly — *"This power is a dice action… Spends 1 mote of Essence and roll. the
bird's Valor + Charisma"* — possibly faithful to a badly-set page, needs eyes on the
book; (b) the last two bullets under Core's COMMON ELEMENTAL POWERS (regeneration,
breeding with mortals) are **body prose the VLM bulleted**, not named powers — 7 powers
plus 2 paragraphs (neither is in the catalogue).

**NOT browser-verified.** Run `preflight`, then the click-through, before this section
loses its warning.
