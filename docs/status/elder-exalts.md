# Elder Exalts — DONE (engine + UI), browser-verified

**Shipped 2026-07-31.** Source: `images/Elder Exalts/Player's Guide.md` (PG pp.258-259),
the whole of the printed rules — two pages, and the shortest source any feature in this
build has had.

An elder Exalt is **not a splat and not an origin**. It is an axis on a character
already built, like Thaumaturgy: it adds no traits, no Charms and no chargen step, and
it does exactly one thing — raise ceilings. So it is one module, `engine/elder.py`, with
one entry point, following the containment shape decision 0011 set for Merits & Flaws.

## What the two pages contain, and what shipped

| p.258-259 rule | Status |
|---|---|
| Age → maximum Essence (100/6, 250/7, 500/8, 1,000/9+) | **DONE** |
| Abilities and Attributes may not pass permanent Essence | **DONE** |
| Virtues never pass 5 | Already true; pinned by a test |
| Terrestrials never pass Essence 7 without "outside energies" | **DONE**, as an ST toggle |
| Training times for elder raises | **NOT SHIPPED** — see below |
| Annual downtime XP awards + the 4:3:2:1 split | **DONE 2026-08-01**, as a calculator — see below |

## The rules, in the order they resolve

1. **AGE alone** lets permanent Essence pass 5, per the p.259 chart. Age is years of
   *Exalted existence*, not years lived — `Character.age` counts from the Exaltation.
2. **ESSENCE in turn** is the ceiling on Abilities and Attributes.
3. Virtues are capped at 5 regardless, with no elder exception.

The chart's top row prints **"9+"**. It ships as a flat **9**: the build never invents a
number the page does not give, and the "+" names no value. A character who should exceed
it is the Storyteller's business.

## Three rulings behind the implementation

* **The Essence ceiling on traits binds only ABOVE 5** (human, rules authority,
  2026-07-31). Read literally, "Abilities and Attributes may not be raised above the
  level of the character's permanent Essence" would cap an Essence 2 Solar's Melee at 2,
  which is nonsense at any age. So the ceiling is `max(5, Essence)` — it never *lowers*
  the ordinary maximum, it only follows Essence upward past it. This matches what
  `engine/merits.py` already assumed for Legendary Attribute (p.20: "for mortals and
  Exalted with Essence 1 to 5, this allows a rating of 6. Exalted with Essence 6 may
  raise the Attribute to 7").
* **Age is NOT a chargen choice** (same). One explicit restriction on creation is that a
  character may not leave it with Essence above 5, so age can do nothing at chargen but
  mislead. `Character.age` is **post-lock editable and greyed until the lock** — the
  exact inverse of the eight frozen chargen choices of decision 0013. The chargen half
  is enforced independently as `essence-above-elder-chargen-cap` in `validate`.
* **Age is not play-state.** It only moves in play, which argues for `PlayState`, but
  decision 0006 keeps play-state out of every permanent derivation and this feeds trait
  ceilings. It lives on `Character` for the same reason `limit_permanent` does.

## What was built

| Piece | Where |
|---|---|
| `elder_caps(ruleset, character) -> ElderCaps` — the one entry point | `engine/elder.py` |
| `essence_cap_for_age(age)` — the p.259 chart | `engine/elder.py` |
| `Character.age` (post-lock only, `ge=0`, default 0) | `models/character.py` |
| `HouseRules.terrestrial_essence_transcendence` | `models/character.py` |
| Essence / Ability / Attribute / Craft ceilings on the buy path | `engine/advancement.py` |
| `essence-above-elder-chargen-cap` | `engine/validate.py` |
| The age input (inside the Downtime dialog) + dot tracks built from the ceilings | `ui/editor.py` |
| The ST Options row, with a "no effect" note off-tier and under 500 years | `ui/view.py` |

`ElderCaps` carries a third field, `terrestrial_limited`, purely so the error a player
sees names the rule that actually stopped them (the tier ceiling) rather than their age.

**Crafts are covered; Colleges are not.** p.258 names "Abilities and Attributes". A
per-focus Craft *is* an Ability (core p.136), so the ceiling reaches it. An Astrological
College is a rated Advantage with its own chargen pool and is neither — it stays at 5,
deliberately, and `raise_college` says so at the site.

## What is deliberately absent

* **Training times.** p.258 calculates them "using the same formulas as is usual for that
  Exalt type" and gates the elder ceilings behind them. This build does not model the
  passage of in-game time (CLAUDE.md: almost certainly never), so **the age chart is the
  whole gate**. A known, accepted incompleteness, in the same family as Weak Essence's
  withheld Charms and Brigid's Heir.
* **Enforcement of the p.259 4:3:2:1 split.** The awards themselves shipped
  2026-08-01 (below); what stayed out is *policing* how they are spent. Earmarking every
  ledger row by category would touch the whole advancement system to enforce a rule the
  page itself frames as an injunction to Storytellers. Human's call.

## Verification

1,584 tests pass. `tests/test_elder.py` covers the chart, both ceilings, the Terrestrial
clause and its toggle, the chargen bar, and the "low Essence never lowers 5" ruling —
all through `advancement.raise_to`, **the buy path**, not the per-dot `raise_*` alone.

Preflight ran. `ElderCaps` is registered in the preflight read-site audit
(`.claude/skills/preflight/effect_reads.py`) alongside `MeritEffects`, so a future dead
field in it is caught. Three render routes were added to `tests/_ui_main.py`
(`/editor-elder`, `/editor-elder-terrestrial`, `/sheet-elder`) — an elder is the first
character in the build whose ratings legally exceed the pip count every dot track was
written against, which is exactly the shape that has blanked panels before.

**Browser-verified 2026-07-31**, and again on 2026-08-01 for the downtime calculator.
What was clicked, in priority order:

1. A **locked Solar**, age set to 1000 — Essence clicks to 9, and Abilities and
   Attributes to whatever Essence then is. **The age box now lives in the Downtime
   dialog**, not in Identity (see below); it is post-lock, like the age itself.
2. The **dot tracks past 5**. The ceilings are correct in the engine; whether nine pips
   in a row still *fit* the panel is the open question, and only a browser answers it.
   Same for the Sheet's read-only rendering of a 9.
3. A **locked Dragon-Blooded**, age 1000 — held at Essence 7, with the ST Options toggle
   ("Terrestrial may pass Essence 7") lifting it to 9.
4. **Any young character**, to confirm nothing moved: the ceilings are 5/5 below 100
   years, which is every character in every existing save.


## The downtime calculator (2026-08-01)

**Shipped as a calculator that grants, never as an enforcement** — the human's call
between three scopes. `engine/elder.downtime_award` totals p.259's annual experience for
a stretch of skipped years and reports the 4:3:2:1 split; the UI is a **Downtime…**
dialog in the Edit tab's sticky XP column, beside Adjust XP, **post-lock only** like
`Character.age` itself.

### The two things the page does not settle, and the rulings taken

1. **A downtime that crosses an age band.** The annual rate falls as the character ages
   (5/4/3/2 at 100/250/500/1,000), and the page never says what to do when a stretch
   spans a boundary. **Ruling (human, 2026-08-01): walk it year by year**, applying the
   rate for the age *reached* in each year — the page describes the award as "a
   year-by-year stream of individual incidents", and a flat rate at either end of the
   stretch over- or under-pays. Age 90 + 40 years pays **155**, not the 200 a
   final-age flat rate would give nor the 0 a starting-age one would.
2. **A lump sum that is not a multiple of ten.** The page's shortcut ("divide by 10, then
   multiply by 4, 3, 2 and 1") only divides cleanly on multiples of ten. Ours floors each
   share and gives the remainder to the largest category, so **the four parts always sum
   back to the lump**. That last step is ours, not the page's, and is marked so at the
   site.

### Two behaviours worth knowing

* **The chart begins at 100 years and this build invents no row beneath it**, so a year
  lived under 100 years of Exaltation awards zero here. The dialog *says so* rather than
  printing a bare 0, which would read as a bug.
* **Granting advances the age by the same years.** They are the same downtime, and
  letting them drift would let a player collect a century of maturation experience
  without ever reaching the century that raises their Essence ceiling.

### What it deliberately is not

The grant is **not a ledger row** — this build logs *purchases*, not grants (Adjust XP
does not log either; a per-session XP-grant ledger is a standing deferred item in
CLAUDE.md). It moves `xp_earned` and reports what it did.

Training times remain absent, so an elder raise is still cheaper in table-time than
printed. Unchanged by this.

Ten tests in `tests/test_elder.py`: the chart, the band walk, band coalescing, the
sub-100 floor, the split ratio, a rounding sweep over 400 totals, and both UI halves
(`/editor-downtime-view` reads, `/editor-downtime` grants — separate routes, because a
route builds once per session and the granting test mutates).


## The age box moved out of Identity (2026-08-01)

Human's call, at the browser: once Downtime grants advance the age, an "Exalted years"
box in the Identity panel is **a second control reaching the same state** — and the two
disagree by construction. A player could age a century in Identity and then collect that
century's maturation experience from Downtime, or grant the downtime and wonder why
Identity's number had changed under them.

So Identity lost the box and the Downtime dialog gained it. **Setting the age and
granting the award stay separate gestures**, deliberately: a character who was *already*
ancient when play began did not earn that maturation experience at this table, so the
age field writes immediately and Grant is its own press.

The elder ceilings readout followed the control — it was a tooltip on the Identity box,
and it is now a line in the dialog ("Now: Essence up to 9, Abilities and Attributes up to
9"), along with the Terrestrial note and a "this downtime reaches Essence N" cue when the
years being considered would cross a band. The one number that governs every track on the
sheet must not be settable with nothing on screen saying what it does.

`test_the_editor_builds_for_an_elder` now asserts "Exalted years" is **absent** from the
editor page, so the box cannot quietly come back.
