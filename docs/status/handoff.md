# Session handoff — 2026-08-14 (martial-arts Phase 2, access rules, gap scan)

# 👉 YOU ARE HERE

**Everything below is DONE and GREEN. Nothing is half-finished. Nothing is waiting on
a decision from you.** Sections after this one are the detail; you do not need to read
them to pick the work back up.

**State: 24 files uncommitted, suite green, browser-verified.**

```
git add -A          # ⚠ TWO screenshots are UNTRACKED — `commit -a` alone misses them
git commit
.venv/bin/python -m pytest -q     # expect: 2,386 passed, 1 skipped, 1 failed
```

⚠ **The 1 failure is expected on this machine** — `test_every_description_matches_the_
source_text` fails here because the Godblooded chapter markdown is present, and defers
where it is not. CLAUDE.md says neither outcome is a regression. **Not something to fix.**

## Versioning — one small thing to decide, nothing depends on it

**v0.9.9 is already tagged, and the tree has moved past it** (the gap scan's 30 entries,
the access fixes, the README/screenshot work). `pyproject.toml` currently reads
**0.9.9**. If you tag again, bump it to **0.9.10** in the same commit — your own
"worse comes to worst we go to 0.9.10". That is the whole decision.

**1.0 is NOT this.** 1.0 was scoped as: README truthfulness (**done**), screenshots
(**done**), pyproject sync (**done modulo the number above**), and **packaged builds on
the Releases page (NOT done — the only one left)**.

## If you do one thing next

**Commit.** Then, in whatever order suits:

1. **Packaged builds** — the last 1.0 item. A re-run, not new work; the PDF sheet was
   already packaged-build-verified.
2. **Split `engine/validate.py`** — the last of the three post-catalogue TODOs.
   `docs/plans/validate-refactor.md`. Write the roll-up membership test FIRST.
3. **The unswept catalogue** — see the gap-scan section below. Bigger than it sounds;
   scope it on its own, do not assume today's scan covered it.

## Nothing is pending your ruling

Every question I raised today you answered, and all of them are implemented:
Snake/Tiger Celestial · the other four tier-less styles Celestial · option A for the
`ma_tier` discriminator · poisons one row each · creature-embedded Charms ignored ·
Han-Tha path is a worked example (so **not authored anywhere** — it would go in
`custom/` if you ever want it).

---

## What happened this session

1. **Phase 1 was browser-verified.** You clicked the preamble panel and confirmed it.
2. **Phase 2 is DONE** — 17 styles authored, the catalogue closed at **21 of 22**.
   `docs/status/martial-arts-styles.md` is the full record.

⚠ **It closed at 19 first, and your question is what found the other two.** I had
recorded Snake and Hungry Ghost as documented absences because their own pages print
no style-level material — which is true, and was the wrong conclusion. **Player's
Guide p.200's `MARTIAL ARTS WEAPONS` table exists specifically to supply form weapons
for styles printed before the association was formalised**, Snake and Hungry Ghost
among them, and it also gave Five-Dragon the mechanics it had shipped without. The
rule that generalises: **checking a style's own chapter is necessary and not
sufficient — a later book can carry the rule the original omitted.**

That closes the second of the three TODOs written when the content gap closed.
**`engine/validate.py` is the only one left.**

## The click-through — DONE 2026-08-14, all eight items

The human clicked all eight. **One real bug, two errors in my checklist, and one
incidental finding.**

### The bug: a SECOND style-label generator (fixed)

The preamble panel said "Mantis Style"; the dropdown above it said
"Praying-Mantis". `view._style_label` had been taught the authored name and
`ui/picker.py`'s own `_pretty` had not. ⚠ It was wrong for **every multi-word slug**
("Charcoal-March-Of-Spiders") — Mantis is just the one where it was noticeable.
Fixed by deferral, with a test, and **the fix is browser-verified** — the dropdown
now reads "Martial Arts: Mantis".

### Two checklist items where the APP was right and I was wrong

* **Ebon Shadow needed an initiation pair to appear.** Correct — Ebon Shadow became
  Celestial on the same day's ruling, so uninitiated Dragon-Bloods are properly
  barred. I wrote that item before the ruling and did not revise it.
* **An uninitiated Dragon-Blood was offered Falling Blossom and Crimson Pentacle
  Blade** as well as Five-Dragon and Jade Mountain. Correct — both are TERRESTRIAL
  styles, and `_is_dragon_path_style`'s docstring names them. My item under-specified.

**Both are the same mistake: a checklist written from what I expected rather than
from what the rules say.** A click-through item that asserts too little is as
misleading as one that asserts the wrong thing — the human has to decide whether an
unexpected extra is a bug, and only the code knows.

### Incidental: two shipped examples have an unresolvable caste

`ruleset.castes.get()` is case-sensitive and caste ids are lowercase slugs, but
`examples/yarak.character.json` carries `"Twilight"` and
`examples/ashes-of-dawn.character.json` carries `"Dawn"`. Both render a blank caste
panel. `gearheart` and `nine-bells-ringing` are fine. **Not fixed** — unrelated to
this work, and it is a two-word data change someone should make deliberately.

⚠ It also cost three rebuilds of the click-through fixtures, because I copied
`yarak` as the base and inherited its bad caste on top of my own two mistakes
(replacing the abilities dict wholesale, then the caste casing). **Validate a
hand-built fixture through the real model AND check its ids resolve before handing
it to a human.**

## Two decisions I made that are yours to reverse

* **The five Immaculate Dragon Paths duplicate their shared rules.** DB pp.242-243
  prints the Signature Weapons rule, the per-path weapon benefit and the elemental
  cost sidebar **once for all five paths**. Each of the five entries now carries its
  own weapon rule plus the two shared ones. I left **"Switching Paths"** and **"The
  Path of Elemental Mastery"** out as chapter-level system text about moving between
  Paths rather than about any one style. Say the word and they go in.
* **`tier` now has TWO printed sources, on your ruling.** The style's own `Type:`
  line where it has one, and otherwise the Player's Guide initiation `Examples:`
  lines (pp.234-239) — Five-Dragon Terrestrial; Snake, Tiger and the five Glorious
  Dragon Paths Celestial. They agree with each other where both exist, and with the
  Charms' `open_to_tiers`. **Four entries are still blank** (Ebon Shadow, Mantis,
  Violet Bier, Hungry Ghost): no `Type:` line, named by no `Examples:` list.

## One thing I found and did NOT fix

**The seven Jade Mountain Charms cite Aspect Book: Earth p.71. The style and its
Charms are on pp.74-77.** Read off the PDF's own text layer with the printed footer
visible. I recorded p.75 on the style and left the Charms alone — that is an
attribution sweep, not this job. Flagging it so it does not get lost.

## The traps worth carrying out of today

* **A test can encode a one-book sample as a rule.** Phase 1 asserted every style
  has a `tier` and a 200-character `preamble`; that held only because all four
  samples were Player's Guide styles, and **14 of the other 18 print neither**. The
  same fact explains why Phase 1's strict name matcher "found" only 4 of 22: it
  required a `Type:` line, so it was searching for a shape that mostly does not
  exist. Not a regex bug — the verification-shape trap.
* **A negative control can go positive underneath you.**
  `test_an_unauthored_style_shows_no_empty_panel` pointed at Tiger, which this
  session authored. It kept passing for the wrong reason (Tiger's rule is headed
  "Tiger's Claws", not "Weapons and Armor"), so it silently stopped testing
  anything. Re-pointed at Snake.
* **Measure the PDF page offset, never guess it.** The Sidereals is offset by 3 and
  every other book by 1. Two pages off in that book lands you in the Bureaucracy
  Charms on a page that looks entirely plausible.
* **A section heading need not contain the style's name.** The Sidereals book heads
  each style by its Maiden's domain — Violet Bier of Sorrows is printed under
  `THE SWORD: MARTIAL ARTS`.

## The access work — DONE 2026-08-14 (option A, your call)

Verifying your Snake/Tiger ruling turned up a **live pre-existing bug**; it and three
related items are fixed. Full detail in `docs/status/martial-arts-styles.md`.

* **`Charm.ma_tier`, PROJECTED by the loader** from `MartialArtsStyle.tier` — not
  authored in the charm files. The style stays the single authored copy, `engine/`
  gets a Charm-level field, and the Phase-1 boundary test still passes. Better than
  the scripted 232-file migration option A first implied; a test asserts no charms
  JSON sets it.
* **The p.101 Sidereal cap** counted 140 Charms across twelve styles as "Sidereal
  Martial Arts forms"; only 41 across three are. **A ronin could not take a single
  Celestial Monkey Charm.** Now `ma_tier == "Sidereal"`.
* **The PG p.235 grant** — an initiated Dragon-Blood reaches Celestial styles. Your
  initiation machinery was already complete and correct; it gated but never granted.
* **The Lunar bar** on Sidereal MA — Lunars only, Solars and Abyssals unaffected.
* **Snake and Tiger** set to Celestial per your ruling.

⚠ **The trap the grant nearly shipped with:** it was first scoped to the TIER, and
four splats are Terrestrial-tier while `db_enlightenment_met` returns True for every
non-Dragon-Blood — so Dragon-Kings, God-Blooded and Mountain-Folk would have got
every Celestial style free, PG p.235 barring Dragon Kings outright. Scoped to the
splat, with a test. **A helper that answers "True, not applicable" for everyone
outside its subject is a grant waiting to happen when used as a condition.**

## The four tier-less styles — RESOLVED, all Celestial (your ruling)

Ebon Shadow, Mantis, Violet Bier and Hungry Ghost are all Celestial. **Every style in
the catalogue now has a tier**, and 30 Charms gained `open_to_tiers: ["Celestial"]`,
so Celestial Exalts and initiated Dragon-Blooded reach all four.

Two tests asserted the old narrower access and were rewritten deliberately — the
castebook Solar-only guard (which did its job: it caught the Tiger widening) and the
Sidereal one that had Violet Bier closed. **The distinction that mattered survived:**
Violet Bier is still not a Sidereal MA *form* and still never counts against the
p.101 cap.

⚠ **The negative control went stale a fourth time — and this time it went RED**,
because the previous re-point had added a premise assertion. There is now no
tier-less style left to aim it at, so it was rebuilt around a synthetic fixture
instead of deleted: the heading logic moved to `StyleView.heading` (derived state in
the presenter, which the Qt port wants anyway) and is tested against a constructed
tier-less StyleView. The preamble-less half still has ten real subjects and keeps
its render route plus its own guard.

## The transcribed-book gap scan — 30 entries authored

Prompted by "can you scan the transcribed books for anything I've missed". Full detail
in `thaumaturgy.md`, `godblooded.md` and `charms-closeout-notes.md`.

| Found | Where |
|---|---|
| Subtle Comprehension Technique | The Outcaste p.150 |
| The Ravenous Fire, Oblivion's Avatar | S&S p.113, BoBE p.102 |
| 16 "Formulas From Other Works" | PG p.143 |
| 3 minor rituals | BoBE pp.118-119 — **the human found these, not the scan** |
| 10 machine-spirit Charms | Autochthonians pp.178-180 |

**Corrected, not authored:** Investiture of Infernal Glory. `charms-closeout-notes.md`
claimed it was authored; it was deliberately skipped because the page prints THREE
Virtue minimums and the model holds one. The doc now says so.

**Ruled out of scope by the human:** the ~9 creature-embedded Charms in bestiary stat
blocks, and the Han-Tha Dark Path (a "worked example" the book invites STs to extend →
belongs in `custom/`, not `data/`; not authored anywhere yet).

⚠ **The lesson, and it cost a wrong "nothing is a known gap" claim:** the scan keyed on
printed stat blocks, so it was **structurally blind to rituals**, which print none at
all — and to one ritual that has no heading either. **Ask what shapes a sweep cannot
see before trusting it.** Still unswept by any method: Merits, Backgrounds and
prose-described artifacts in the transcribed books, and everything in the scan-only
books (Sidereals, Dragon-Blooded, castebooks, Lunars, Abyssals).

## Where the work goes next

**Split `engine/validate.py`** — 5,791 lines, 182 functions, 47% of the engine.
`docs/plans/validate-refactor.md`. The seam is DOMAIN, not splat. **Write the
roll-up membership test FIRST** — a `check_*` dropped from `validate()` still
passes its own unit tests and never runs.

Still deferred indefinitely and **not** gaps: the Mist numina, Cult Abyssals, and
now the three martial-arts absences (`snake`, `hungry-ghost`, `enlightenment`).
Training times are still a no.
