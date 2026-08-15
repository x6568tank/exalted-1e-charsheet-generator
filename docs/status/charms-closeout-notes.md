# Charms close-out batch — authoring notes

**Batch:** delegation brief `docs/plans/delegation-brief-charms-closeout.md` (2026-08-11).
The last batch authorable from text already on disk. 16 entries across five record
shapes, five different files. All values traced to `images/_extracted/` page text.

⚠ **CORRECTED 2026-08-14.** This file used to record Investiture of Infernal Glory as
authored. It was not, and that was a DELIBERATE CHOICE, not an oversight — see
"Entries skipped" below. A gap scan found the discrepancy; the doc was wrong, the data
was right.

**Result:** 1,837 Charms (1,828 + 5 Outcaste + 3 Player's Guide + 1 Spirit; the
Beastman Gifts are variants, not records), 13 elemental powers. The brief's check
script passes (no duplicate ids, every prerequisite id resolves). Full suite: see the
test line below.

## Entries skipped

**Investiture of Infernal Glory (PG p.85) — DELIBERATELY NOT AUTHORED.**

The page prints **three** Virtue minimums — `Minimum Compassion: 3`,
`Minimum Conviction: 5`, `Minimum Valor: 4` — plus `Minimum Essence: 7`. The `Charm`
model holds **one** (`min_virtue` + `min_ability`). Encoding it means picking the
strictest single gate and **silently dropping the other two floors**, so a character
who fails Compassion 3 or Valor 4 would be offered a Charm the page forbids her. That
is a wrong answer wearing the costume of a right one, and it is worse than an absent
entry — the entry is visibly missing, the missing gate is not.

Authoring it needs a model change (multiple Virtue minimums) and is not a DATA-ONLY
batch's business. Until then it stays out. ⚠ **Its absence is a decision. Do not
"fix" it by encoding a single Virtue minimum.**

No other entry was skipped. No GARBLED / COLUMN SPLIT FAILED / SHATTERED HEADING
marker covered any authored content; the p.89 GARBLED marker in the Player's Guide
extract is past Investiture's block and was not needed.

`Five Directions Formation Protocol` (PG p.242) was **not** in this batch — still
unauthored per the brief's NOT-in-this-batch section (prints `Varies` for Cost,
Duration, Type, Minimum Martial Arts and Minimum Essence; encoding it invents five
numbers).

## Every `???`

None. Every cost, minimum and prerequisite was read with certainty from the extract.

## Prerequisites — all resolved

| Charm | Printed prerequisite(s) | Encoded id(s) |
|---|---|---|
| Vision Outside Time | Atsiluth's Bounty, Falsehood Unearthing Attitude | `dragonblooded.investigation.atsiluths-bounty` (new) AND `dragonblooded.investigation.falsehood-unearthing-attitude` (existing) |
| Tireless Footfalls Cadence | Memorable Performance Technique | `dragonblooded.performance.memorable-performance-technique` |
| Peerless Training Method Protocols | Flawless Training Execution | `dragonblooded.performance.flawless-training-execution` (new) |
| Power-Investing Prana | Will-Bolstering Method | `solar.lore.will-bolstering-method` |
| Dragon-Soul Enlightening Method | Tiger-Warrior Training Technique | `solar.performance.tiger-warrior-training-technique` |
| Wise Commander's Gift | Benevolent Master's Blessing | `dragonblooded.bureaucracy.benevolent-masters-blessing` |
| Soaring Pinions (Beastman Gift) | Prerequisite Gift: Fluttering Wings | variant-key group `[["fluttering-wings"]]` on the same Charm |

Atsiluth's Bounty and Flawless Training Execution print `Prerequisite Charms: None`.
Everything else has `[]`.

## Worklist-vs-printed name disagreements

None. All names match the worklist.

The one extraction wrinkle the brief warned about: the p.85 heading extracted as
`INVESTITUREOF INFERNAL GLORY`; the name is **Investiture of Infernal Glory**.

## Beastman Gift repeatability

**None of the three is repeatable.** Aspect of the Gillman, Soaring Pinions and
Fluttering Wings all print no "may be taken more than once" language (unlike Bestial
Reflexes and Enhanced Senses, which explicitly do), so all three were encoded
`max_purchases: 1`.

## ⚠ Anything noticed and not acted on

1. ⚠⚠ **ELEMENTAL POWERS: the brief's Section 3 contradicts the printed source and a
   prior ruling.** The Player's Guide p.68 states outright: "Of the elemental powers on
   page 56 of GoD, only Consume Element and Plague of Menaces can be learned." The
   existing test `test_the_elemental_power_catalogue_is_the_nine_learnable_powers`
   (`tests/test_godblooded.py:1325`) encodes exactly that — the catalogue is the
   **nine learnable** powers, and its docstring names Day to Night, Foul the Waters,
   Immolation and Elemental Unction as "elemental-spirit traits, absent from the
   catalogue." The brief directed authoring all four; this batch did, faithfully
   transcribing the GoD p.56 sidebar, which is why the catalogue is now 13 and that
   test fails. **The four records are not wrong transcriptions — the question is
   whether they belong in a *learnable* catalogue at all, and the printed text says
   no.** Left in per the brief's explicit direction; flagged for the human to rule.
   If the ruling is "restore the nine learnable powers," removing the four records
   (`elemental.day-to-night`, `elemental.foul-the-waters`, `elemental.immolation`,
   `elemental.elemental-unction`) is a self-contained deletion that also greens the
   test.

2. **Investiture of Infernal Glory prints THREE Virtue minimums, and the model holds
   ONE** — which is why it was **skipped rather than encoded**. See "Entries skipped".
   Its printed prerequisites (Endowment, Geas, Memory Transference, Scourge) all exist
   as `spirit.spirit-templates.*`, so only the Virtue-minimum model change stands
   between the page and a record.

3. **The `element` field was added to the five Dragon-Blooded Charms and Wise
   Commander's Gift** (`Water` for the two Investigation Charms, `Wood` for the three
   Performance Charms, `Water` for Bureaucracy), following the neighbour convention in
   each target file. The brief's example shape omits `element`, but every existing
   record in those files carries it (Investigation→Water, Performance→Wood,
   Bureaucracy→Water). Not authoring it would make the records inconsistent with their
   files. The book does not print an element on these Charms; this is the build's
   established DB assignment, not a page value.

4. **OCR cleanups** in descriptions (nothing structural): "they not function" →
   "they do not function" (Outcaste p.130), "for miles around to turn black" case fix
   (GoD sidebar), "one of it's own" → "one of its own" (GoD sidebar). Stray marginal
   glyphs (e.g. the `a-`/`ts` in the p.130 Vision Outside Time column) dropped.

5. **Elemental Powers `activation` vs `description` split.** The brief's Section 3
   shape puts the printed mote cost in `activation` and the effect in `description`. I
   followed that for the four new powers. The two already-authored GoD powers
   (Consume Element, Plague of Menaces) use a different convention — their
   `activation` is the God-Blooded modifier summary ("Costs the God-Blooded the normal
   number of motes…") — and were left untouched.

6. **Variable-cost records are `raw`-only**, matching the per-die/per-fang records in
   the same files (e.g. `dragonblooded.investigation.indisputable-physical-analysis-technique`
   `{"raw": "1 mote per two dice"}`). Affected: Tireless Footfalls Cadence ("2 motes
   per fang"), Flawless Training Execution ("5 motes, 1 Willpower, plus 1 mote and 1
   committed mote per fang trained"), Wise Commander's Gift (mote cost variable, so
   only `willpower: 1` is structured).

7. **Vision Outside Time is one Charm** (Investigation, p.130) per the brief's note —
   the index's Lore listing is a duplicate, not authored.

## Verification

- Brief check script: **1,837 charms | 13 elemental powers**, no duplicate ids, every
  prerequisite id resolves. ✅
- Full suite `.venv/bin/python -m pytest -q`: **8 failed, 2,092 passed** (154.31s).
  The brief predicted exactly one failure. The other seven fail because the brief's
  "No test counts these" premise was wrong — they are hardcoded counts/sets that this
  batch's legitimate additions bump. None of the seven is a data defect (the brief's
  "report it" instruction is met below; the deltas are the additions themselves):
  - `test_shipped_db_water_ability_charm_counts` — hardcodes `investigation: 10`; now
    12 (+Atsiluth's Bounty, +Vision Outside Time).
  - `test_shipped_db_wood_ability_charm_counts` — hardcodes `performance: 7`; now 10
    (+Tireless Footfalls Cadence, +Flawless Training Execution, +Peerless Training
    Method Protocols).
  - `test_gift_charm_shape` — hardcodes `len(variants) == 19`; now 22 (+3 Beastman
    Gifts).
  - `test_gift_prerequisite_chain` — hardcodes the root-gift set at 10 keys; now 12
    (+Aspect of the Gillman, +Fluttering Wings, both prereq-less).
  - `test_the_spirit_charm_catalogue_is_authored` — asserts
    `spirit == set(SPIRIT_IDS)`; `SPIRIT_IDS` is a hardcoded constant lacking the new
    Investiture of Infernal Glory.
  - `test_the_sorcery_initiation_is_reachable_in_the_picker` — knock-on of the same
    stale `SPIRIT_IDS`.
  - `test_the_elemental_power_catalogue_is_the_nine_learnable_powers` — **a real
    conflict, not staleness; see Flag 1.**
  - `test_every_description_matches_the_source_text` — the known machine-specific
    failure (46 Godblooded entries on a machine with the CH2 file present). Expected.
  None of the failing tests counts a value that is wrong; each counts a value that is
  now intentionally larger. Under the DATA-ONLY constraint no test was touched.

---

## Review addendum — 2026-08-11 (Claude)

**Two of the brief's five sections directed authoring content that had already been
ruled out. Both removals are done; the batch's transcriptions were not at fault.**

### Section 3 — the four GoD elemental powers: REMOVED
PG p.68: *"Of the elemental powers on page 56 of GoD, only Consume Element and Plague of
Menaces can be learned."* `test_the_elemental_power_catalogue_is_the_nine_learnable_powers`
already encoded that ruling, and its docstring named the other four "elemental-spirit
traits, absent from the catalogue". The batch transcribed them faithfully and flagged the
conflict rather than picking a side, which was exactly right. Catalogue back to **9**.

### Section 5 — Investiture of Infernal Glory: REMOVED
`docs/status/godblooded.md`: **"Intentionally unauthored"** (human, 2026-08-07) — akuma
are not PCs without heavy ST intervention, and the Charm fits neither the single-
`min_virtue` model nor God/Demon learnability. Its stat block is kept in the
transcription for if it is ever needed. Note the recorded transcription is p.87 with
Min Compassion 3 / Conviction 5 / Valor 4 / Essence 7, which also differs from what the
p.85 heading suggested. `spirit_templates` back to **80**.

### How the brief got it wrong, so it does not recur
The worklist was built from a mechanical "in the index, not in the build" diff. That
diff cannot distinguish *not yet authored* from *deliberately excluded*, and I did not
check. **The tell was in the brief's own text**: it said "two of that sidebar's six
powers are already authored — leave them alone" without asking why only those two. A
partial gap is a decision, not an oversight.

`docs/status/content-gap-entries.md` now carries that warning at the top, with both
rulings named, and the instruction to grep `docs/status/` and `tests/` for an entry name
before authoring it.

### The remaining eight entries are legitimate — four stale counts updated
5 Outcaste DB Charms + 3 Player's Guide gifts. Checked for prior rulings first; none.

- `test_shipped_db_water_ability_charm_counts` — investigation 10→12, bureaucracy 11→12.
  (Wise Commander's Gift is a Player's Guide Charm but Bureaucracy is a Water Ability,
  so it counts in the Water total; every other DB Bureaucracy Charm is `element: Water`
  too, and the batch matched its neighbours correctly.)
- `test_shipped_db_wood_ability_charm_counts` — performance 7→10.
- `test_gift_charm_shape` — variants 19→22.
- `test_gift_prerequisite_chain` — roots gain Aspect of the Gillman and Fluttering Wings;
  added an explicit assertion that Soaring Pinions requires Fluttering Wings, verified
  against p.207's "Prerequisite Gifts: Fluttering Wings".

**Final: 1,836 Charms, 9 elemental powers, suite 2,099 passing** + the known
machine-specific failure.
