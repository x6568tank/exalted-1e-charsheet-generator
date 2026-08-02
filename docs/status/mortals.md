# Mortals & Heroic Mortals

**Status: chargen DONE (2026-07-30), engine + UI, tests green. BROWSER-VERIFIED
2026-08-01**, no findings. Note the gap between those dates: magic access was
deliberately absent when this shipped (see *Deferred*) and arrived later via Merits &
Flaws, so the click-through covered more than this document describes — Essence
Awareness, Essence Mastery, Terrestrial Martial Arts and Terrestrial Sorcery are all
part of a mortal now. `docs/status/merits-flaws.md` is the record for that half.

The first **non-Exalt** splat, and the first that is **casteless** and **barred from
Charms**. One splat, two origins — not two splats.

## Sources

| Pages | What they gave |
|---|---|
| `images/Mortals/Mortals & Heroic Mortals/Exalted p103.png` | "Down and Dirty, or Playing Humans" — the entire five-step chargen procedure, both columns of numbers, and the mortal→Exalt conversion recipe |
| `Player's Guide.md` p.11-12 | Heroic-mortal clarifications: no extra health levels, mortal infection/poison, no attunement to the Five Magical Materials / Manses / Hearthstones, Essence 1 with no pool access |
| `Player's Guide.md` p.115 | The mortal XP table (also the source the thaumaturgy costs already came from) |
| `Player's Guide.md` p.121 | The Essence Mastery Merit — the future unlock, authored nowhere yet |

Everything else on p.11-12 (stunt bonuses, damage rolling, poison difficulties) sits on
the far side of decisions `0008`/`0009` and was deliberately not modelled.

## Heroic vs ordinary is the `origin` axis

p.103 draws ONE procedure through both and varies exactly two things. So `Mortal` +
`Mortal:ordinary` are budget rows, not two `exalts.json` entries.

| | Heroic (default row) | Ordinary (`Mortal:ordinary`) |
|---|---|---|
| Attribute pools | **6/4/3** | **4/3/3** |
| Ability dots | **22** | **16** |
| Backgrounds | 5 | 5 |
| Charms | 0 | 0 |
| Essence | 1 (start and cap) | 1 |
| Bonus points | **21** | **21** |

**The 21 is flat.** An early reading of mine paired "21" with "16" as a heroic/ordinary
bonus-point split; that is wrong. The 16 is the *ordinary mortal's Ability dots*, and
the page says plainly "mortal characters get 21 bonus points". `test_mortals.py` pins
this because it is the easiest number in the splat to get backwards.

`heroic` has no `Mortal:heroic` row — it falls back to the plain `Mortal` row, the same
trick `dynastic` and `loyal` use. A test asserts the fallback resolves to 6/4/3, because
trap #2 says a missing keyed row fails silently at the wrong prices.

## Rulings and why the data looks like it does

JSON carries no comments, so the three non-obvious `exalts.json` values are recorded here.

* **`essence: {all coefficients 0, peripheral_virtue_mode: "none"}`** — derives both
  pools to 0/0. That is "Mortal characters have an Essence of 1, but no way to gain
  access to their Essence pool" (PG p.11) expressed as data rather than a code branch.
  A mortal has an Essence *rating* and no Essence *pool*, and the existing
  `EssencePoolSpec` turned out to express that exactly.
* **`tier: "Mortal"`** — deliberately NOT `"Terrestrial"`. `tier` is what opens a
  cross-splat Martial Arts style via `Charm.open_to_tiers`; calling a mortal
  Terrestrial would hand them Terrestrial MA immediately, which is precisely what is
  gated on Merits they cannot yet have.
* **`magic_track: "sorcery"`, `highest_magic_circle_id: ""`** — inert. Sorcery needs an
  initiation Charm and mortals may hold no Charms, so sorcery is unreachable by
  construction rather than by a rule. When Merits open Terrestrial Sorcery this is
  already pointing the right way.

Three new model fields, all data-driven so the next casteless/Charmless splat needs no code:

* **`ExaltDefinition.charms_available`** (False for Mortal). `charm_count: 0` was NOT
  enough: it grants none at creation but leaves them *purchasable with bonus points*,
  and eight `open_to_all` Charms have `min_essence: 1`, which an Essence-1 mortal meets.
  Enforced at chargen (`charms-not-available`) and in `advancement.learn_charm`, both
  with mortal-specific messages — "wrong splat" would misdescribe a Charm that belongs
  to no splat.
* **`ExaltDefinition.essence_cap`** (1 for Mortal). A LIFETIME ceiling, as opposed to
  `ChargenBudgets.essence_start_cap`, which only binds until lock. p.103 bars only bonus
  points; PG p.11's "no way to gain access to their Essence pool" is what bars XP.
* **`XpCosts.essence_by_rating`** (`{2: 20, 3: 40}` for Mortal). The mortal table prices
  Essence flat **by destination**, which `LinearCost` cannot express.

One new `HouseRules` field, `mortal_favored_ability` — see below.

## The casteless machinery

"Mortals select Nature as normal but do not select a caste." All 14 caste lookup sites
already guarded `None`, so most of this was free. What was not:

* `validate.splat_has_castes()` — new. Suppresses `unknown-caste` for a splat with no
  castes at all, so a mortal sheet does not carry a permanent spurious error. Careful
  distinction: a **Lunar HAS castes** that merely carry no Caste Abilities, so the check
  stays live for them.
* The favoured-ability block in `validate_chargen` used to live entirely inside the
  "caste known" branch. A casteless splat now carries its Favoured set through the other
  branch, or the optional rule below could never be validated.
* Editor: the caste `ui.select` and the caste-info box are hidden for a casteless splat,
  replaced by a short "Not one of the Chosen" note.
* **Bug found in passing:** `set_exalt_type` kept a stale caste when the new splat had
  none, so a Dawn Solar switched to Mortal silently kept Dawn's discounted Abilities. It
  now clears. Also pulls Essence into the new splat's legal range, which the function
  had never done (visible before only as the Illuminated Solar's start-at-3).

## The optional Favored Ability (`HouseRules.mortal_favored_ability`)

p.103's optional rule, on the **ST Options tab**, PER-CHARACTER. It is not a free
discount — the same paragraph attaches a ceiling: *"the character can never have any
other Ability rated higher than his Favored Ability."* That constraint is validated
(`mortal-favored-not-highest`); equal is explicitly allowed.

**HEROIC MORTALS ONLY.** The page offers it to "heroic mortals", so it varies by
origin and lives on the budget row as `ChargenBudgets.optional_favored_ability` (true
on `Mortal`, absent on `Mortal:ordinary`). **Both** halves must hold — the origin
allows it AND the ST switches it on — via `validate.optional_favored_ability_open`.
An earlier cut gated only on "the splat has no castes", which let an ordinary mortal
take one; caught in browser testing, 2026-07-30. The ST Options note names which half
is missing.

## Browser-testing findings (2026-07-30)

Three bugs the tests did not catch, all reported from a real click-through:

1. **The Charm picker crashed for a mortal, blanking Abilities *and* Thaumaturgy.**
   `_all_categories` is empty for a splat with no Charms, so the Category `ui.select`
   was built with `{}` options and a non-empty value — which raises at BUILD time and
   takes the whole `build_picker` call down, siblings included. This is
   `adding-a-splat.md` trap #3 in a form the guard did not anticipate: the existing
   comment worried about a value outside its options, not about there being no options
   at all. Fixed twice over: the Abilities/Martial Arts pages are no longer offered to
   a Charmless splat (a mortal's picker opens on Thaumaturgy, its only page), and the
   Category select `setdefault`s its own value so it can never raise again.
2. **The Favored Ability toggle applied to ordinary mortals** — see above.
3. **A character with nothing in it validated as legal** — see below. Not a Mortal
   bug at all.

## The unspent-dots check (engine-wide, not Mortal-specific)

Found via Mortals but **pre-existing for every splat**: the budget arithmetic was
entirely one-sided. Every domain computed `max(0, spend - budget)`, charged the
overflow to bonus points and errored only if that exceeded the allowance. Nothing ever
noticed a character who spent too *little*, so a blank sheet reported "✓ Legal". A
blank Solar produced only caste-related errors; a mortal, having no caste rules left to
fail, made the gap visible.

`validate.unspent_budget_issues` now reports each unallocated pool. Rulings from the
human, 2026-07-30:

* **Warnings, not errors** — an unfinished sheet is incomplete, not illegal. The UI
  already filters its legality banner on `severity == "error"` and paints warnings
  amber, so nothing else had to change.
* **Backgrounds are covered; bonus points are not** — "BP are bonus for a reason".
* Attribute pools are counted **per group**, not in aggregate: 18 dots poured entirely
  into Physical still leaves the 6 and 4 pools unspent, and says so.
* Only dots at or below the pre-BP cap count toward a pool, mirroring
  `bonus_point_breakdown` exactly so the two can never disagree.

Tests live in `tests/test_chargen.py` (engine-wide), not here. Note this makes
`examples/nine-bells-ringing.character.json` report 8 of 15 Background dots unspent —
correct; that fixture was never fully allocated. Its pre-existing
`charm-caste-favored-min` error is unrelated and predates this work.

## Deferred — magic access, pending Merits & Flaws

**A mortal currently has no route to any magic at all.** That is a deliberate
consequence of the human's call (2026-07-30) to ship chargen first rather than pull M&F
forward, and it is *correct but incomplete*: mortal magic is gated on Merits, and M&F is
not implemented (its source file, `images/Merits & Flaws/CH 1 - Merits and Flaws.md`, is
a 4-line header stub with no content).

What that work must carry, all recorded in CLAUDE.md's Merits & Flaws TODO:

* **Essence Mastery** (5-pt Supernatural, prereq Essence Awareness, PG p.121) unlocks
  the Essence pool. After it, a mortal may buy Essence to **3** with XP — 20 XP for
  Essence 2, then 40 for Essence 3. The cap of 3 is not a house ruling: **the printed
  table stops there**, listing no Essence 4 or 5. So `essence_cap` goes 1 → 3; the field
  is not deleted.
* The same Merit's printed text is also the basis for the Martial Arts ruling — holders
  have "sufficient Essence to activate the Root of the Perfected Lotus and practice
  Terrestrial Martial Arts".
* Terrestrial Martial Arts opens **except `dragonblooded.martial-arts.spirit-walking`**,
  which grants Celestial MA. Note `charm_matches_splat` will NOT catch this for free:
  Spirit Walking is `open_to_all`. Its prerequisite, Spirit Sight, is *not* barred — a
  mortal may hold it and dead-end there (human confirmed, "it is just the one Charm").
* Sorcery opens at the **Terrestrial circle only**.
* The mortal XP table also prices "New Merit (mystical only) | cost in bonus points ×2".

## Also not done

* **The mortal→Exalt conversion** p.103 describes (+3 Attributes, +3 Abilities, mark
  Caste Abilities, pick Favored, 10 Charms, Essence 2, a Virtue Flaw, adjust health).
  A genuinely nice feature — "play the prelude as a mortal, then Exalt" — and entirely
  unimplemented. No one has asked for it.
* **The p.115 table is worded permissively** — it "can be used to supplant" the core
  p.270 costs "not only for thaumaturges, but for any mortal characters". It is authored
  here as *the* mortal table. If the human wants it to be an ST toggle instead, that is
  a small change to one `costs_xp.json` row plus a `HouseRules` flag.
* Training times (the table's other half) are not modelled;
  `XpEntry.training_complete` remains the dormant hook it already was.
