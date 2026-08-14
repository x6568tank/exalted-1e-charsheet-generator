# The martial-arts STYLE entity

**Status: Phase 1 DONE 2026-08-14, browser-verified 2026-08-14. Phase 2 DONE
2026-08-14 — the catalogue is COMPLETE at 21 of 22.** The one remaining category,
`martial_arts:enlightenment`, is not a style at all.
Plan and the decisions behind it: `docs/plans/martial-arts-styles.md`.
Closes the open TODO in `CLAUDE.md`.

## ⚠ The finding that reshaped Phase 2: most books print no preamble

Phase 1's four styles all came from the **Player's Guide**, which prints a `Type:`
line and two paragraphs of prose above every style. **It is the only book that
does.** Reading the other eleven books page by page found three different shapes:

| Shape | Styles | What the page prints above the Charm list |
|---|---|---|
| Type + prose + rules | the PG four, Jade Mountain, Falling Blossom, Mantis | everything |
| prose only, no `Type:` | Charcoal March, Prismatic Arrangement, Citrine Poxes | a per-style paragraph in a shared intro |
| **a rules sidebar and nothing else** | Tiger, Ebon Shadow, Violet Bier, the five Dragon Paths | one boxed "Weapons and Armor"-type rule |
| **nothing at all on its own page** | Snake, Hungry Ghost | the MARTIAL ARTS heading runs straight into the first Charm — **their rules are in the Player's Guide instead**, see above |

This broke a Phase-1 test that asserted every style has a `tier` AND a
200-character `preamble` — an assumption that held only because all four samples
came from one book. It is now "at least one of tier / preamble / mechanics, plus a
source". **Tightening it back would force a `tier` to be invented from memory,
which decision 0001 forbids**, so `tier` is left empty wherever no `Type:` word is
printed. Eight of the nineteen have an empty `tier` and that is correct.

## ⚠⚠ The mistake worth reading first: a style's rules need not be printed with its Charms

Phase 2 initially closed at **19 of 22**, recording `snake` and `hungry-ghost` as
**documented absences** on the evidence that their own pages print no style-level
material. That evidence was real — the core's and the Abyssals' MARTIAL ARTS
headings do run straight into the first Charm, verified against rendered pages — and
**the conclusion drawn from it was still wrong.**

The human asked "there's nothing anywhere for them?" and there was:

* **Player's Guide p.200, `MARTIAL ARTS WEAPONS`.** A table that exists for exactly
  this: *"Some martial arts from early in the game's publication history are not
  explicitly associated with weapon types. The table below lists explicit
  associations for previously unassociated forms."* It supplies form weapons for
  **Snake** (seven-section staff, hook swords), **Hungry Ghost** (tiger claws /
  shade talons) and **Five-Dragon** (sword, spear) — the last of which had shipped
  with an empty `mechanics` list — and corroborates the eight authored from their
  own books.
* **Player's Guide pp.234-239, the initiation sections.** `TERRESTRIAL /
  CELESTIAL / SIDEREAL INITIATION`, each ending in an `Examples:` line that names
  styles. This is a printed tier for styles whose own page prints no `Type:`.

**The general rule: checking the style's own chapter is necessary and not
sufficient.** A later book can supply the style-level rule the original omitted —
which is `feedback_source_precedence_rule` pointing the other way round from usual.

## ⚠ The one remaining absence — NOT a gap, do not author it

`test_the_worklist_is_down_to_one_documented_absence` pins it.

* **`enlightenment`** — not a style: the Dragon Path initiation tree
  (`ui/picker.py` said so first). Its two Charms sit under the chapter's Spirit
  Walking prose. Its one style-level rule, the **Dragon Paths and Elements**
  sidebar (DB p.241), is carried by the five Dragon Path styles it gates.

## ⚠ The five Immaculate Dragon Paths share their style-level rules — a judgement call

DB pp.242-243 prints the Dragon Path rules **once, for all five paths**: the
Signature Weapons rule, then a per-path weapon benefit, then the elemental-cost
sidebar. There is no per-style preamble anywhere.

**The call taken (mine, reversible):** each of the five carries its own
signature-weapon rule plus the two shared rules, duplicated across the five
entries, because each genuinely applies to that style. **Deliberately left out:**
"Switching Paths" and "The Path of Elemental Mastery" (DB p.243), which are about
moving between Paths rather than about any one style — chapter-level system text.
If the human wants them in, they are five identical `mechanics` entries away.

## ⚠⚠ The click-through found a SECOND label generator (2026-08-14)

`view._style_label` was taught to prefer the authored style name. **`ui/picker.py`
kept its own**, `_pretty`, which title-cased the slug — so the preamble panel read
**"Mantis Style"** while the category dropdown directly above it read
**"Praying-Mantis"**, on the same screen, for the same style. The suite was green
throughout: each generator was tested on its own, and nothing asserted they agreed.

⚠ **It was wrong for more than Mantis.** `.title()` never repaired the slug hyphen,
so every multi-word style was mangled in the dropdown — "Charcoal-March-Of-Spiders",
"Violet-Bier-Of-Sorrows". Only the one style whose printed name differs from its slug
made it *visible*.

`_pretty` now defers to `_style_label` and strips the " Style" suffix the dropdown's
format has never carried.
`test_no_second_style_label_generator_disagrees_with_the_authored_name` asserts both
the deferral and the resulting labels.

**The rule: when you teach one formatter a new fact, grep for its siblings before
calling it done.** A per-module display helper is the easiest place for a second
description of one fact to hide, because it never touches the engine and every test
of it passes.

## ⚠ `_style_label` now prefers the AUTHORED name

Phase 1 predicted this: *"will fail for the first style whose printed name is not
its slug title-cased."* Phase 2 produced it — `martial_arts:praying-mantis` is
printed **Mantis Style** (Caste Book: Eclipse p.73). `view._style_label` takes an
optional `ruleset` and returns the authored name when there is one; the slug
fallback survives for homebrew, which has no catalogue entry (decision 0012). All
three call sites pass the ruleset.

## ⚠⚠ Negative controls went stale THREE times in one session

Every one of these kept **passing**. Not one went red.

| Test | Pointed at | Why it stopped testing anything |
|---|---|---|
| `test_an_unauthored_style_shows_no_empty_panel` | **Tiger** | Phase 2 authored it. Survived only because it asserts the absence of "Weapons and Armor" and Tiger's rule is headed "Tiger's Claws" |
| the same test, re-pointed | **Snake** | the Player's Guide sweep authored it hours later. Survived because Snake's rule is headed "Form Weapons" |
| `test_a_rules_only_style_renders_without_a_dangling_tier` | **Air Dragon** | the initiation sweep gave it `tier: Celestial`, so it stopped being a no-tier style. This one DID go red, because it asserts something POSITIVE too |

**A negative control aimed at something that later becomes positive does not fail;
it silently stops testing anything.** The third row is the mitigation: it went red
because it also asserts content that must be present. The first two are now guarded
by an explicit premise assertion — `/style-rules-only`'s test asserts its subject
still has an empty `tier` and `preamble`, and fails loudly telling you to re-point
it rather than quietly passing.

**Whenever a work item AUTHORS content that used to be missing, grep the tests for
the names you just authored before calling the suite green.**

## ⚠⚠ A LIVE BUG the tier sweep exposed: `open_to_tiers` is overloaded

Setting `tier` put the style's tier beside the Charms' `open_to_tiers` for the first
time, and the two disagree in a way that turned out to be a real defect. **Nothing
here is fixed** — it is queued behind a design decision (tasks #8-#11).

**FIXED 2026-08-14 (option A, human's call).** The record below is kept because the
bug shape is worth carrying; what shipped is at the end of this section.

### The bug (pre-existing, live, not introduced by Phase 2)

`engine/validate.py`'s p.101 Sidereal chargen cap — *"no more than 3 chargen Charms
from a Sidereal Martial Arts form; a ronin none"* — identifies an SMA form as:

```python
c.category.startswith("martial_arts") and c.open_to_tiers
```

That matches **twelve** styles. Only **three** are Sidereal Martial Arts: Charcoal
March of Spiders, Prismatic Arrangement of Creation, Citrine Poxes of Contagion. The
other nine are ordinary Celestial styles — the five Immaculate Dragon Paths,
Celestial Monkey, Dreaming Pearl Courtesan, Righteous Devil, Hungry Ghost.

**Consequences today:** a Sidereal taking four Righteous Devil Charms at chargen is
wrongly told she is over the Sidereal MA cap, and **a ronin (cap 0) cannot take a
single Celestial Monkey Charm.**

`open_to_tiers` is answering two unrelated questions — "who may learn this" and "is
this a Sidereal MA form" — and the style `tier` field is what actually distinguishes
them. But `test_no_engine_module_reads_the_style_catalogue` bars the engine from
reading `tier`; that is the Phase-1 boundary, deliberately set. Hence the fork:

* **A** — add an explicit Charm field and point both the cap and access at it. Keeps
  the engine off the style catalogue, retires the overload, smallest blast radius.
* **B** — let the engine read `style.tier` and REMOVE the per-Charm tier fields.
  This is exactly the migration `docs/plans/martial-arts-styles.md` describes as how
  the boundary should eventually fall.

**A was chosen, and measurement is why.** B's whole case was collapsing the double
description, and the data says it cannot: `style.tier` covers only **186 of 232**
martial-arts Charms. Six (`martial_arts:enlightenment`) belong to no style entry at
all — and they are the initiation tree, load-bearing for these very access rules —
and forty sit in styles whose page prints no tier. B would still need a per-Charm
fallback for 46 Charms, so it moves most of one description rather than removing it.
**If B is ever revisited, the honest precondition is a tier for those 46.**

### What shipped (option A)

**`Charm.ma_tier`, PROJECTED by the loader — not authored in the charm files.**
`rules_db._project_style_tier_onto_charms` copies `MartialArtsStyle.tier` onto each
of the style's Charms at load. This is better than the scripted data migration option
A originally implied: the style remains the **single authored copy**, `engine/` gets
a Charm-level field so the Phase-1 boundary test still passes, and the two cannot
drift. `test_ma_tier_is_projected_from_the_style_and_never_authored` asserts both the
agreement and that no charms JSON sets the field.

Blank stays blank — 46 Charms have no tier, and **blank means "unknown", never
"Terrestrial"**. Every consumer must treat it that way.

Three engine changes followed:

1. **The p.101 cap** now counts `ma_tier == "Sidereal"` — 41 Charms, not 140.
2. **The PG p.235 grant**: an initiated Dragon-Blood reaches `ma_tier == "Celestial"`.
3. **The PG p.235 Lunar bar**: a Lunar never reaches `ma_tier == "Sidereal"`.

### ⚠ The trap the grant nearly shipped with

The grant was first written against the **tier** — "a Terrestrial who is initiated".
**Four splats are Terrestrial-tier** (Dragon-Blooded, Dragon-Kings, God-Blooded,
Mountain-Folk), and `db_enlightenment_met` returns **True for every non-Dragon-Blood**
because they need no initiation. A tier-scoped grant therefore hands the other three
every Celestial style for free, having met nothing — and PG p.235 bars one outright:
*"Dragon Kings ... can never master anything other than Terrestrial styles designed
specifically for Dragon Kings."* Scoped to the splat instead, with
`test_the_celestial_grant_is_scoped_to_dragon_blooded_not_to_the_tier` pinning it.

**The general shape: a helper that returns "True, not applicable" for everyone
outside its subject is a grant waiting to happen when you use it as a condition.**

### ⚠ A guard that worked — `test_castebook_styles_are_solar_only`

Widening Tiger failed a test written when the castebooks were authored, whose
docstring said *"Do not widen them without a page that says so."* Its escape clause
was met (PG p.236, Sidereals p.195, DB p.241, plus the human's ruling), so Tiger left
its scope deliberately and the test was renamed. **Mantis and Ebon Shadow stay pinned
there, unruled** — see the open question below.

### The gate that is not a grant (PG pp.235-236)

The Dragon-Blooded initiation machinery is **already complete and correct** — all
three Charm pairs are authored in `martial_arts:enlightenment`, and
`DB_MA_ENLIGHTENMENT_PAIRS` / `db_enlightenment_met` / `category_available` encode
"any one pair opens the gate". **Do not rebuild it.**

What is missing is the other half. `category_available` opens the style dropdown;
`charm_matches_splat` then refuses the Charms, because a Dragon-Blood reaches her
Dragon Paths by SPLAT OWNERSHIP, not by initiation. Measured: an initiated DB is
refused **Celestial Monkey**, which already carries `open_to_tiers: ["Celestial"]`.
PG p.235 says a Terrestrial may practise Celestial martial arts. One branch in
`charm_matches_splat` is the whole fix.

### RESOLVED: the four tier-less styles are all Celestial (human, 2026-08-14)

**Every style in the catalogue now carries a tier.** The ruling widened access:
Ebon Shadow, Mantis and Violet Bier gained `open_to_tiers: ["Celestial"]` on their
30 Charms (Hungry Ghost already had it), so Celestial Exalts and initiated
Dragon-Blooded reach all four. The books, and what each contributed:

| Style | Book | Evidence |
|---|---|---|
| **Ebon Shadow** | Caste Book: **Night** p.67 | a Solar castebook style, the same class as Tiger and Snake; and Sidereals p.195 has a Sidereal invoking *"Tiger Form and **Ebon Shadow Form**"* |
| **Mantis** | Caste Book: **Eclipse** p.73 | the same class again; the Sequestered Tabernacle offers all four together |
| **Violet Bier of Sorrows** | The Sidereals p.179 | Sidereals p.184 calls it the lesser style Sidereals learn **before** the secret arts — so Celestial, and explicitly NOT Sidereal-tier, which is why the cap must keep ignoring it |
| **Hungry Ghost** | The Abyssals p.162 | its Charms already carry `open_to_tiers: ["Celestial"]`, and `validate.py`'s own docstring calls it a Celestial style — the blank tier is purely an authoring gap |

**The book was the hint and it pointed one way.** The PG's `Examples:` line is
examples, not an enumeration, which is why it names Snake and Tiger and stops.

⚠ **Two tests asserted the narrower access and both were rewritten, deliberately:**
`test_castebook_styles_are_solar_only` (whose own docstring said *"Do not widen them
without a page that says so"* — the guard worked, Tiger failed it, and the widening
got reviewed instead of slipping through) and
`test_sidereal_martial_arts_styles_are_celestial_open`, which had asserted Violet
Bier carried NO `open_to_tiers`. That was a conservative default from when the splat
was authored, not printed exclusivity. **The distinction that mattered survived
intact:** Violet Bier is still not a Sidereal MA *form* and still never counts
against the p.101 cap — that is `ma_tier`, which is exactly the conflation this
work removed.

### ⚠ The negative control went stale a FOURTH time — and this time it went RED

`/style-rules-only` began pointed at Air Dragon (which gained a tier from the
initiation sweep), was re-pointed at Ebon Shadow (which gained one from this
ruling), and now **no style in the catalogue has a blank tier at all** — there is no
real subject left to aim it at.

It failed loudly rather than passing quietly, because the previous re-point added an
explicit premise assertion. That is the mitigation working as designed.

The fix follows the rule the earlier failures produced: **when nothing is absent any
more, rebuild the control around a synthetic fixture rather than deleting it.** The
heading logic moved out of `ui/picker.py` into `StyleView.heading` — which CLAUDE.md
wants anyway, derived state in the presenter for the Qt port — and is now tested
against a constructed tier-less `StyleView` that cannot be authored out from under
it. The tier-less branch stays reachable: `tier` defaults to "", homebrew styles have
no catalogue entry, and the next book read may print a style with no `Type:` line.
The *preamble*-less half still has TEN real subjects and keeps its render route,
with its own premise guard.

### ⚠ "They" in the Lunar bar means LUNARS

*"They may not learn Sidereal martial arts under any circumstances"* sits inside the
`LUNAR MARTIAL ARTISTS` section (PG p.235). It is a **Lunar** bar, not a
Celestial-tier one — Solars and Abyssals are unaffected, so `open_to_tiers:
["Celestial"]` on the three Sidereal styles is not wrong in general, only for
Lunars. An earlier draft of this doc flagged it as a blanket contradiction; that was
an over-read of the pronoun.

## ⚠ Flagged, not fixed: the seven Jade Mountain Charms cite the wrong page

`data/charms/*` gives all seven `Exalted 1e Aspect Book: Earth` **p.71**. The style
and its Charms are on **pp.74-77** (the style header and the first three Charms are
on p.75, read off the PDF's own text layer with the printed footer visible). The
style entry records p.75. The Charm pages were not touched — that is a separate
attribution sweep, and `docs/source-attribution.md` is where it belongs.

## How Phase 2's transcriptions were checked

Three of the seven books have a text layer, so their entries were verified
mechanically rather than by eye: squash the authored string to `[a-z0-9]` and assert
it appears in `pdftotext` output. **20 of 21 checkable strings matched exactly.**

⚠ The one that did not is instructive and is NOT a defect: Falling Blossom's weapons
rule **spans a page break**, and `pdftotext` interleaves the page number and the
running header into the middle of the sentence. The two halves each match. **A
squashed-substring fidelity check produces false misses at every page boundary** —
split on the break before concluding a transcription is a paraphrase.

The four scanned books (Dragon-Blooded, The Sidereals, the three castebooks) have no
text layer and were transcribed from rendered pages by eye; nothing mechanical can
check those.

## What shipped

- **`MartialArtsStyle`** (`models/rules.py`) — `id`, `name`, `category`, `tier`
  (the printed `Type:` word), `preamble`, `mechanics[]`, `source`.
- **`data/martial_arts_styles.json`** — **19 styles.** Phase 1's four off
  `images/_extracted/Player's Guide.md` pp.239-254: Crimson Pentacle Blade
  (**Terrestrial**), Celestial Monkey, Dreaming Pearl Courtesan, Righteous Devil
  (all Celestial). Phase 2's fifteen:

  | Style | Source | tier | preamble | mechanics |
  |---|---|---|---|---|
  | Jade Mountain | Aspect Book: Earth p.75 | Terrestrial | ✓ | 3 |
  | Falling Blossom | Cult of the Illuminated p.102 | Terrestrial | ✓ | 2 |
  | Mantis (`praying-mantis`) | Caste Book: Eclipse p.73 | — | ✓ | 1 |
  | Tiger | Caste Book: Dawn p.73 | — | — | 1 |
  | Ebon Shadow | Caste Book: Night p.67 | — | — | 1 |
  | Violet Bier of Sorrows | The Sidereals p.179 | — | — | 1 |
  | Charcoal March of Spiders | The Sidereals p.184 | Sidereal | ✓ | 3 |
  | Prismatic Arrangement of Creation | The Sidereals p.184 | Sidereal | ✓ | 3 |
  | Citrine Poxes of Contagion | The Sidereals p.184 | Sidereal | ✓ | 3 |
  | Five-Dragon | Dragon-Blooded p.199 | — | ✓ | 0 |
  | Air / Earth / Fire / Water / Wood Dragon | Dragon-Blooded pp.242-243 | — | — | 3 each |
- **`RuleSet.martial_arts_styles`** + a two-directional load-time link check.
- **`rules_db.unauthored_martial_arts_styles(ruleset)`** — the Phase 2 worklist.
- **`view.style_for_category`** → `StyleView`, and a **collapsible preamble panel**
  above the Charm tree on the picker's Martial Arts page.
- **`build_picker(..., initial_category=...)`** so a route can open one tree.
- `tests/test_martial_arts_styles.py` — 13 tests.

## ⚠ Righteous Devil Style — a documented exception, NOT a bug

Found by the consistency test written for this job: 11 of its 12 Charms carry
`open_to_tiers: ["Celestial"]`; **Blessing of Righteous Solar Spark Meditation**
(PG p.255) does not, so a Lunar or Sidereal may learn the style but not that Charm.

**The human ruled it CORRECT AS PRINTED (2026-08-14)** — the Charm's own text names
the Solar Exalted, so it is genuinely narrower than the Type: Celestial style around
it. It lives in `_DOCUMENTED_ACCESS_EXCEPTIONS` in the test, **and a second test
asserts that set contains exactly this one Charm**, so the exception cannot quietly
grow into an allowlist that absorbs the next real divergence.

**Do not "fix" this Charm.**

## ⚠ The Phase-1 boundary: `tier` is DISPLAY ONLY

The style's printed `Type:` and the Charms' `open_to_all` / `open_to_tiers` /
`restricted_to` / `immaculate` are **two descriptions of one fact**. The human's
scoping call was preamble-and-Type only: **access is still decided entirely by the
CHARM fields, exactly as before. This change altered no access rule.**

`test_no_engine_module_reads_the_style_catalogue` parses every `engine/*.py` and
fails on any read of `martial_arts_styles` or `MartialArtsStyle`. Two live
descriptions of one rule disagree — the shape decision 0011 exists to prevent, and
the reason the Edit⇄XP merge happened. If the styles should later own access, that
is a migration that **removes** the per-Charm fields, and the test changes as part
of it, on purpose.

## ⚠ An unauthored style is a WORKLIST ENTRY, not a load error

The link check runs both ways but they are **not symmetric**:

- **style → Charms is FATAL.** A style whose `category` no Charm uses is a slug
  typo; it would load clean and simply never appear.
- **Charms → style is NOT.** Raising on an unauthored style would stop the app
  from starting. They are reported by `unauthored_martial_arts_styles`, and a test
  pins the list so it can only shrink — authoring a style without removing it there
  fails, and so does losing one. The list is now the **three documented absences**
  above, so the mechanism outlives the worklist it was built for.

**Custom styles are exempt from both.** `custom_content.py` mints
`martial_arts:<slug>` at runtime and there is no page to write a preamble from;
decision 0012 says homebrew must never break the load. The exemption is tested with
its own negative control (the same category, printed rather than homebrew, IS work).

## Phase 2 — how the fifteen were read

Every source was in `sources/`. **Three of the seven books have a usable text
layer** (Aspect Book: Earth, Cult of the Illuminated, The Abyssals) — `pdftotext`
straight out, no rasterising. The other four are pure scans (Dragon-Blooded, The
Sidereals, and the three castebooks) and were rasterised with `pdftoppm -r 130` and
read page by page, per the 2026-08-13 authorisation.

⚠ **Every book's PDF page differs from its printed page, and by a different
amount.** Measured, not guessed — render one page and read its footer:

| Book | printed page = pdf page − |
|---|---|
| Aspect Book: Earth | 1 |
| The Abyssals | 1 |
| Dragon-Blooded | 1 |
| Castebooks (Night / Dawn / Eclipse) | 1 |
| **The Sidereals** | **3** |

Getting Sidereals wrong by two lands you in the Bureaucracy Charms with a page that
looks plausible. The pages recorded in `martial_arts_styles.json` are printed pages,
matching the Charms' own `source`.

## Traps

- **⚠ Matching style names against the books failed THREE times in one session**,
  in both directions. A loose substring matcher scored "snake"/"tiger" as found
  anywhere in any book; a strict `NAME STYLE` + `Type:` matcher then found only 4
  of 22 and reported the other 18 as absent when they are all present; and a
  `WEAPONS AND ARMOR` regex missed the sidebar spelled `WEAPONSAND ARMOR`.
  **What worked was book + page off the Charms' own `source`.** Exactly
  `feedback_gap_matchers_wrong_both_ways`, three more times.
  ⚠ **Phase 2 explains WHY the strict matcher failed, and it is worse than a regex
  bug:** it looked for a `NAME STYLE` header followed by a `Type:` line, and **14 of
  the 18 styles print no `Type:` line at all.** The matcher was not buggy — it was
  searching for a shape that mostly does not exist, which is
  `feedback_verification_shape_trap` rather than a matching problem. The 18 "absent"
  styles were all present the whole time.
- **⚠ A style section heading need not contain the style's name.** Violet Bier of
  Sorrows is printed under `THE SWORD: MARTIAL ARTS`, Charcoal March under
  `CONSUMPTION: THE CHARCOAL MARCH OF SPIDERS`, Prismatic under `ESSENCE: ...`,
  Citrine under `DECAY: ...` — the Sidereals book heads each by its Maiden's domain.
  Nothing that greps for "Violet Bier" finds that section.
- **Two "Celestial Monkey Style" hits in the Player's Guide are an ASTROLOGY
  correlations table**, not the style section. A name match can land in the wrong
  chapter of the right book.
- **The preamble panel renders NOTHING for an unauthored style**, not an empty box
  — the same rule the printed sheet's panels follow.
- `whitespace-pre-line` on the preamble label, or NiceGUI collapses the paragraph
  breaks (`docs/status/backgrounds.md` learned this first).
- **`initial_category` is validated against the offered options before use.** A
  caller-supplied category that is not on offer is the `ui.select` build-time crash
  that blanks sibling tabs (`adding-a-splat.md` trap #3), so it falls back rather
  than trusting the caller.
