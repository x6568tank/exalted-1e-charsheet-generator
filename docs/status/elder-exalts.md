# Elder Exalts — DONE (engine + UI), not browser-verified

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
| Annual downtime XP awards + the 4:3:2:1 split | **NOT SHIPPED** — see below |

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
| "Exalted years" input + dot tracks built from the ceilings | `ui/editor.py` |
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
* **The p.259 downtime experience awards and their 4:3:2:1 split.** Annual XP for skipped
  decades, which "cannot be hoarded", spent across four mandated categories. This is a
  Storyteller's downtime bookkeeping across years of unplayed time, not a sheet
  calculation — the same reason `PlayState` is a dumb manual tracker. **Not refused, not
  scheduled**: if it comes back, the in-scope version is a *calculator* in the Adjust XP
  control (enter years → print "200 XP → 80/60/40/20") that the ST grants manually.
  Enforcing the split would mean earmarking every ledger row by category.

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

**NOT browser-verified.** What to click, in priority order:

1. A **locked Solar**, age set to 1000 — Essence should click to 9, and Abilities and
   Attributes to whatever Essence then is. The "Exalted years" box is beside Concept and
   is disabled until the lock.
2. The **dot tracks past 5**. The ceilings are correct in the engine; whether nine pips
   in a row still *fit* the panel is the open question, and only a browser answers it.
   Same for the Sheet's read-only rendering of a 9.
3. A **locked Dragon-Blooded**, age 1000 — held at Essence 7, with the ST Options toggle
   ("Terrestrial may pass Essence 7") lifting it to 9.
4. **Any young character**, to confirm nothing moved: the ceilings are 5/5 below 100
   years, which is every character in every existing save.
