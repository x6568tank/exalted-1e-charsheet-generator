# Essence & trait ceilings, and the downtime calculator

**Shipped 2026-07-31, simplified 2026-08-06.** Source: `images/Elder Exalts/Player's
Guide.md` (PG pp.258-259), the whole of the printed rules — two pages, and the shortest
source any feature in this build has had.

**Human ruling 2026-08-06** simplifies the shipped elder-age axis: the age chart is
**gone**, Essence is **XP-purchasable** to the splat's ceiling, and the p.259 downtime
awards survive as a calculator whose age is a pure input (there is no `Character.age`).
This was the human's call after the Dragon-Kings attribute work surfaced how awkward the
age gate was — Essence-raising hidden behind a downtime grant, and no printed age rules
for the non-Exalt splats.

## What survives of pp.258-259

| p.258-259 rule | Status |
|---|---|
| Abilities and Attributes may not pass permanent Essence | **DONE** — `max(5, Essence)`, binds only above 5 |
| Permanent Essence is capped (the chart's "9+" as a flat 9) | **DONE** — the six Exalts set `essence_cap: 9` |
| Terrestrials never pass Essence 7 without "outside energies" | **DONE**, as an ST toggle |
| Virtues never pass 5 | Already true; pinned by a test |
| Age chart (100/6, 250/7, 500/8, 1,000/9) | **REMOVED 2026-08-06** — Essence is purchasable, not age-gated |
| Training times for elder raises | **NOT SHIPPED** — see below |
| Annual downtime XP awards + the 4:3:2:1 split | **DONE 2026-08-01**, as a calculator — see below |

## The rules, in the order they resolve

1. **Essence is XP-purchasable** up to the splat's `ExaltDefinition.essence_cap` — 0 in
   the data resolving to the flat **9** (the p.258 chart's printed "9+", taken as a
   number once the chart is gone), and a Terrestrial further held at **7** by the same
   clause as ever. Chargen is separately held at 5 (`essence-above-elder-chargen-cap`):
   no character leaves creation with more.
2. **Essence in turn** is the ceiling on Abilities and Attributes.
3. Virtues are capped at 5 regardless, with no exception.

## Rulings

* **The Essence ceiling on traits binds only ABOVE 5** (human, 2026-07-31, unchanged).
  The ceiling is `max(5, Essence)` — it never *lowers* the ordinary maximum, it only
  follows Essence upward past it. Matches what `engine/merits.py` already assumed for
  Legendary Attribute (p.20).
* **No character may leave creation with Essence above 5** (2026-07-31, unchanged), now
  enforced purely by `essence-above-elder-chargen-cap` — the age reasoning is gone.
* **Age is not a character trait at all** (2026-08-06). The downtime chart's rate depends
  on years of Exalted existence, so the calculator keeps an **age input** — a pure
  calculator field that gates nothing and is not saved.

## What was built

| Piece | Where |
|---|---|
| `elder.trait_ceiling(character)` — `max(5, Essence)`, the one trait-ceiling read | `engine/elder.py` |
| `elder.essence_cap(ruleset, character)` — splat cap (0→9) + Terrestrial-7 | `engine/elder.py` |
| `elder.downtime_award` / `annual_xp_for_age` / `split_downtime_experience` | `engine/elder.py` |
| Essence / Ability / Attribute / Craft ceilings on the buy path | `engine/advancement.py` |
| `essence-above-elder-chargen-cap` (Essence ≤ 5 at creation) | `engine/validate.py` |
| The Essence dot track (pre-lock 5, post-lock the splat cap) + the Downtime dialog | `ui/editor.py` |
| The ST Options row, with a "no effect" note off-tier | `ui/view.py` |
| The six Exalts' `essence_cap: 9` | `data/exalts.json` |

**Crafts are covered; Colleges are not.** p.258 names "Abilities and Attributes". A
per-focus Craft *is* an Ability (core p.136), so the ceiling reaches it. An Astrological
College is a rated Advantage with its own chargen pool and is neither — it stays at 5,
deliberately, and `raise_college` says so at the site.

## What is deliberately absent

* **Training times.** p.258 calculates them "using the same formulas as is usual for that
  Exalt type" and gates the elder ceilings behind them. This build does not model the
  passage of in-game time (CLAUDE.md: almost certainly never). Unchanged by the 2026-08-06
  simplification.
* **Enforcement of the p.259 4:3:2:1 split.** The awards shipped 2026-08-01; what stayed
  out is *policing* how they are spent — a rule the page itself frames as an injunction
  to Storytellers. Human's call.

## Verification

1,969 tests pass. `tests/test_elder.py` covers both ceilings, the Terrestrial clause and
its toggle, the chargen bar, the "low Essence never lowers 5" ruling, and the downtime
calculator — all through `advancement.raise_to`, **the buy path**, not the per-dot
`raise_*` alone.

Preflight ran. `ElderCaps` was registered in the preflight read-site audit and is
**removed** with the object. Render routes in `tests/_ui_main.py` (`/editor-elder`,
`/editor-elder-terrestrial`, `/sheet-elder`) still exercise an elder — the first
characters in the build whose ratings legally exceed the pip count every dot track was
written against.

**Browser-verified 2026-07-31, 2026-08-01 (downtime), 2026-08-06 (simplified).** What was
clicked in the last pass:

1. A **locked Solar, Essence 8, Melee 7** — the Essence track runs to 9, and Abilities
   and Attributes to whatever Essence then is; no age box anywhere on the page.
2. A **locked Dragon-Blooded at Essence 7** — held there, with the ST Options toggle
   ("Terrestrial may pass Essence 7") lifting it to 9.
3. The **Downtime dialog** — its "Exalted years so far" field drives the award; granting
   moves `xp_earned` and advances the calculator's own age input.

## The downtime calculator (2026-08-01, age input reworked 2026-08-06)

**A calculator that grants, never an enforcement.** `engine/elder.downtime_award` totals
p.259's annual experience for a stretch of skipped years and reports the 4:3:2:1 split;
the UI is a **Downtime…** dialog in the Edit tab's sticky XP column, beside Adjust XP,
post-lock only (it grants XP).

The chart's rate depends on years of Exalted existence, so the dialog takes an **"Exalted
years so far" input** — the calculator's age, **not a character trait** (2026-08-06:
`Character.age` is gone and age gates nothing). Granting advances that local age so a
later grant is priced from where the last one ended.

### The two things the page does not settle, and the rulings taken

1. **A downtime that crosses an age band.** The annual rate falls as the age input rises
   (5/4/3/2 at 100/250/500/1,000), and the page never says what to do when a stretch
   spans a boundary. **Ruling (human, 2026-08-01): walk it year by year**, applying the
   rate for the age *reached* in each year. Age 90 + 40 years pays **155**, not the 200 a
   final-age flat rate would give nor the 0 a starting-age one would.
2. **A lump sum that is not a multiple of ten.** Ours floors each share and gives the
   remainder to the largest category, so **the four parts always sum back to the lump**.
   That last step is ours, not the page's, and is marked so at the site.

### What it deliberately is not

The grant is **not a ledger row** — this build logs *purchases*, not grants (Adjust XP
does not log either). It moves `xp_earned` and reports what it did.

## The Essence dot-row override bug (found 2026-08-06, another session)

A regression from the 2026-08-06 simplification itself: the editor's Essence dot row was
built from `elder.essence_cap` alone, so a **mortal with Essence Mastery** and a
**God-Blooded with Awakened Essence** got a one-pip row and could not spend XP on
Essence at all — `raise_essence` honoured the `essence_cap_override`, the dot row did
not. The engine was never wrong; the UI gate was. Fixed by applying the override to the
row's ceiling in the same order `raise_essence` does, with three render tests through
the NiceGUI harness (mortal 3 pips, God-Blooded 3 pips, plain mortal still 1 pip). The
lesson is the buy-path one: a green `raise_essence` test cannot see a UI gate that
caps below what the engine permits.
