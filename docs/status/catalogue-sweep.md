# The 1.0 catalogue sweep — DONE for everything on disk (2026-08-10/11)

The three content catalogues went from "what the pages on disk happened to support" to
"everything the available books contain". Six delegated batches, each reviewed against
the page. **Suite: 2,102 passing** (plus the known machine-specific M&F description
failure — see `godblooded.md`). **Browser-verified 2026-08-11** — see *The
click-through* below.

| Catalogue | Before | After |
|---|---|---|
| Charms / Arcanoi | 1,709 | **1,836** |
| Spells | 92 | **246** |
| Rated artifacts | 40 | **196** |

The plan, the per-book gap tables and the sequencing rationale live in
`docs/plans/content-completeness.md` and `docs/status/content-gap-entries.md`. Each
batch has its own record: `spell-batch-notes.md`, `artifact-batch-notes.md`,
`artifact-batch-2-notes.md`, `ghost-arcanoi-batch-notes.md`,
`martial-arts-batch-notes.md`, `charms-closeout-notes.md`.

## What made it possible: `sources/` extraction

The human authorised reading `sources/` directly (2026-08-10), moving the vetting
checkpoint from their manual copy to their reading of the output. Eight books are now
page-marked Markdown in `images/_extracted/`:

Bone & Ebony · Player's Guide · Savant and Sorcerer · Autochthonians · Games of
Divinity · Ruins of Rathess · The Outcaste · **Exalted Core**

Tools: `extract_born_digital.py` (page ranges or whole book, offset auto-detected),
`solve_cid_bands.py` (solves a subsetted font's glyph order), `apply_glyph_map.py`
(applies a cipher and prints a reviewable diff), and `tools/glyph_maps/*.json` — the
ciphers as data, each carrying its evidence.

### Three books were ciphered, each differently

* **The Outcaste** — every glyph reflected, `ord(plain) = 288 - ord(cipher)`. Proved by
  the running head decoding to `EXALTED THE OUTCASTE`.
* **Savant and Sorcerer** — no punctuation in the font map; 1,754 `(cid:N)` markers,
  all nine mapped and human-confirmed.
* **Exalted Core** — thirteen subsetted fonts, **each its own cipher**, in three
  descending bands (`cid + ord` constant per band). Four faces solved = 97% of the
  text; the rest is marked `U+FFFD`, never guessed.

## ⚠ Five traps this work produced, in rough order of how much they cost

1. **A search shaped like what you expect proves nothing about a thing shaped
   differently.** This misfired four times in one session: a name search landing on a
   Charm's first passing mention rather than its entry; a heading-shaped search
   concluding two artifacts did not exist when p.114 rated them **in prose**; a
   character-count audit passing while columns were interleaved; page-sampling passing
   while a failure varied by **font**. Every apparent DS error traced back to one of
   these. **Anchor on the entry (`Cost:` line), not the name; check order, not volume;
   sample along the axis the failure varies on.**
2. **"Missing from the build" ≠ "should be authored".** The gap diff is mechanical and
   cannot see a human ruling. Two batches were sent content that had been deliberately
   excluded — the four GoD elemental powers (PG p.68: only Consume Element and Plague
   of Menaces are learnable) and Investiture of Infernal Glory (akuma-only, ruled out
   2026-08-07). **A partial gap is a decision, not an oversight**: when a source's
   entries are split between authored and not, that asymmetry has a written reason.
   `content-gap-entries.md` now opens with this warning.
3. **A docstring asserting an invariant is a claim with an expiry date.**
   `view.virtue_split` said "Ghost Arcanoi paths carry a single Virtue per category" —
   true when written, false the moment Bone & Ebony landed six multi-Virtue paths, and
   the code depending on it broke where no test looked.
4. **The VLM cannot count dots.** Same page at 200/400/600 dpi gave three different
   Artifact ratings, biased low. Agreement with it is evidence; disagreement is
   probably the model. Recorded as the memory `vlm-cannot-count-dots`.
5. **Character count is not readability.** The Outcaste extracts ~4,700 chars/page of
   byte-shifted gibberish. `extract_born_digital.py` now refuses below a 50% English
   check, because the failure mode is a megabyte of convincing garbage.

## What the batches turned up in the build itself

* **A live picker bug** (found by the delegated model, fixed on review): the first
  multi-Virtue Arcanoi paths made `view.virtue_split` emit `category:virtue` sub-keys
  that `picker._group_of` did not recognise, so a ghost was offered a Charms page it
  should never have and lost paths from its Arcanoi dropdown.
* **233 Abyssal Charms mis-attributed** to `Exalted 1e Core` while carrying Abyssals
  page numbers. `source.book` is a zero-read-site field, which is why it rotted
  silently — see `docs/source-attribution.md`, written for this.
* **The Dragon-Path gate was over-broad**, exempting two styles by name and hiding
  every *Terrestrial* style from an uninitiated Dragon-Blooded. Falling Blossom had
  been invisible to them since it was authored; adding Crimson Pentacle Blade only made
  it visible. It now keys on tier — see decision 0015.
* **The Direlance question is closed**: core p.341 decoded and carries only
  weapon-class prose plus the p.342 stat table, so no standalone catalogue entry exists
  to author. The Slayer Khatar, blocked for the same reason, **is** now authored.

## New mechanics shipped alongside

* **`Charm.restricted_to`** — `"<Splat>"` / `"<Splat>:<caste>"` entries, one of which
  the character must match. Narrows an access already granted. Dreaming Pearl Courtesan
  (PG p.249: "mastered only by the Solar Exalted and Moonshadow Caste Abyssals").
* **`Charm.max_virtue`** — the only requirement in the build a character fails by
  having **more** of a trait, so it cannot ride on the `min_*` shortfall machinery.
  Celestial Monkey (PG p.246). Read in **two** places on purpose: the picker check and
  the validator, so raising a Virtue *after* buying in still reports `charm-max-virtue`.
* **The Dragon-Path enlightenment gate accepts any one of three pairs** — Immaculate,
  Iris-Bulb, Tiger-and-Bear (PG p.236: "just one set of such Charms. There are others").
* **`Charm.open_to_tiers` is now RANKED**, not exact-match — decision 0015.

⚠ **Trap for anyone testing these:** the per-Charm checks run in `validate.validate()`,
**not** `validate.validate_chargen()`. Asserting against the latter yields an empty set
and a rule that looks enforced when it is not. That mistake was made and caught while
writing these tests.

## The click-through (2026-08-11, browser-verified)

All passed: both new gate fields including the post-purchase `charm-max-virtue` report;
all three enlightenment pairs opening the Dragon Paths, and a mixed half-pair correctly
not; 14 Arcanoi paths rendering with no ghost offered a Charms page; the four new
Martial Arts styles; artifact/spell dropdowns. Two defects were found **by the human at
the browser** and fixed: the over-broad Dragon-Path gate, and the Alchemical martial-arts
bar sitting below `open_to_all` so it missed Terrestrial styles.

## Open questions for the human

* **Rathess p.86** — three artifacts (Crystal of Protection, Ring of Disguise, Ring of
  Images) sit under a `COLUMN SPLIT FAILED` marker. The batch left a reassembly in
  `artifact-batch-2-notes.md` for a one-read sign-off.
* **`Insidious Ebon Xoanon`** prints `ARTIFACT N/A`; `rating` is required and must be
  1-5. Unauthorable as the model stands.
* **`Kireeki-class Assault Skyreme`** — the fan index places it at Outcaste p.64, which
  is the Skywolf. The name appears nowhere in the book.
* **Savant and Sorcerer `(cid:144)`** and seven rarer codes (25 occurrences) remain
  unmapped and are left verbatim.

## What is left, and it is all page-blocked

**213 entries**: 112 artifacts, 61 spells, ~31 Charms. Nothing further can be authored
without new page syncs. Highest combined yield: **Book of Three Circles** (63), Savage
Seas (18), The Lunars (17), Time of Tumult (14), Abyssals pp.254-261 (16).
