# The 265 delegated spells re-transcribed — 2026-09-03

**Suite: 3,181 passed, 1 skipped** (main PC) — up from 3,135/2 skipped/1 failed at the
last handoff. The extra passes and the closed skip/fail are **not from this work**; they
landed in an earlier commit this session (`f50973e`/`7041b04`) and are untouched here.
This job changed **no test**, only `exalted_builder/data/spells.json` descriptions —
spell count stayed at **306** throughout.

**Not browser-verified**, same reasoning as the Core Charm pass: data-only change, no UI
touched. Worth a look once: a Spell detail panel on the Sorcery tab for a Solar/Abyssal
carrying a Savant & Sorcerer or Book of Bone and Ebony spell — descriptions are now
noticeably longer for the 116 changed entries.

## What this was

`spell-batch-notes.md` (2026-08-11) authored these 265 entries — **Savant and Sorcerer**
(94), **Book of Bone and Ebony** (62), **The Autochthonians** (38), **The Abyssals**
(23), plus 48 already-clean Three Circles entries folded into the same check — under the
same "one-or-two-sentence" delegation cap that thinned the Core Charms. Unlike Core, the
catalogue-completeness sweep never flagged these as short, because a cost/circle/name
triple reads as "present" regardless of description length; they sat unchecked for three
weeks after the Core fix proved the method.

**116 of 265 changed; 149 were already complete.** Read every entry against its
extracted source text (same pipeline as the Charm pass — `tools/extract_born_digital.py`
output, human-vetted).

## What the re-transcription turned up

- **Named variant spells the original batch explicitly logged as unauthored, now
  restored as prose inside their parent spell's description** (not new catalogue
  entries — no new ids, count held at 306): Willful Flesh Commands, Consorting with
  Devils, Funerary Misted Vessel, Puzzle Box of Love, Brick-by-Brick Solitude, Black
  Vial/Empty Night Future, Walking Gore Titan/Void Cocoon Warrior, Baneful Shadow,
  Blackstorm Wagon, and others. `spell-batch-notes.md`'s own "Passing mentions... NOT
  authored" list named most of these on 2026-08-11 — this pass is that debt coming due,
  not a new discovery.
- **A truncated entry**: The Ravenous Fire cut off mid-sentence at a page break.
- **A spell missing its entire mechanical payload**: Ritual of Elemental Empowerment's
  element table was absent from the description entirely.
- **Two resistance-roll direction bugs**, found only by comparing against source, not by
  length: Curse of Slavish Humility and Iron Countermagic both had the roll direction
  backwards.
- **Two `source.book` citations checked and confirmed correct** on review (Oblivion's
  Avatar, Peacock Shadow Eyes) — not touched, logged so a future sweep doesn't re-flag
  them as unchecked.

## What's still open

Nothing from this specific worklist. The wider **46 M&F descriptions measurably short of
source** (Undetectable Lie, Subtle Glamour, Chillikin Companion, Aura of Power, etc.) is
a separate, already-tracked item — `status/merits-flaws.md` and
`test_every_description_matches_the_source_text`'s deferred-entries warning name them.
