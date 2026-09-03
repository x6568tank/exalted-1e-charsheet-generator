# Session handoff — 2026-09-03 (the 265 delegated spells re-transcribed)

# 👉 YOU ARE HERE

Last FULL green suite: **3,181 passed, 1 skipped** (main PC, `main`, 14m46s). Tree is
clean, 2 commits ahead of `origin/main` (not pushed): `f50973e` (planning artifact
attunement), `dba43ae` (the spell re-transcription below).

⚠ The count moved 3,135/2 skipped/1 failed → 3,181/1 skipped/0 failed since the last
handoff, but **not from this session's work** — this job touched only
`exalted_builder/data/spells.json` descriptions, no test file. The closed skip and
failure predate this pass; `test_every_description_matches_the_source_text` is the
machine-dependent-outcome test named in `docs/testing.md` (pass-with-deferrals here,
fails where the source chapter is present) — do not read this as newly fixed.

## What shipped

**The 265 delegated spells re-transcribed against source** — same method as the Core
Charm fix (`status/spell-retranscription.md`). Savant and Sorcerer (94), Book of Bone
and Ebony (62), The Autochthonians (38), The Abyssals (23), plus 48 Three Circles
entries checked clean. 116 of 265 descriptions changed; 149 were already complete.
Restored named variant spells that a 2026-08-11 batch had explicitly logged as
unauthored (Willful Flesh Commands, Consorting with Devils, Blackstorm Wagon, and
others — now prose inside their parent spell, not new catalogue entries), a truncated
entry (The Ravenous Fire), a spell missing its entire mechanical payload (Ritual of
Elemental Empowerment's element table), and two resistance-roll direction bugs (Curse
of Slavish Humility, Iron Countermagic). Spell count held at 306 throughout — this was
a correctness pass, not an addition. **Not browser-verified** — data only, no UI
touched; see the status file for the one panel worth a look.

## Previously: what shipped 2026-09-02

**1. Catalogue picking on the adversary roster** (`status/adversary-roster.md`). Five
fields on the ST view's adversary editor gained an "Add from catalogue" button — Charms
(1,861), Spells (306), Powers (99), Abilities (25), Backgrounds (42, deduped) — in BOTH
shells. It validates nothing by design: no splat filter, no prerequisite, no minimum, and
the dialog says so in its own subtitle. Picks append the printed NAME, so `charms`,
`spells` and `powers` stay prose. `keep_open` and `render_cap` were added to the shared
catalogue dialogs, both opt-in.

**2. Merit & Flaw prerequisites reach a screen** (`status/merits-flaws.md`).
`MeritFlawDefinition.prerequisites` had ONE read site — the validator — and appeared in
neither UI; **32 entries stated no gate at all**. The "Requires:" line now lives in
`view.merit_requirement_line` and both shells call it.

**3. Awakened Essence supersedes the mortal Essence tree** (human ruling). New
`MeritEffects.prerequisites_satisfied`; four superseded entries barred from God-Blooded via
`barred_exalt_types`; the 4-pt God-Blooded Magical Attunement now requires Awakened Essence.
⚠ That last one is on the human's authority, NOT a page — the transcribed p.66 text does
not carry it.

**4. Transcription markup stripped** from Destiny and Eternal Vow (`<!--TANGENT TABLE-->`),
with a catalogue-wide guard.

## 👉 NEXT

Nothing is blocked. In rough order of what would bite:

- **46 M&F descriptions measurably short of source** — Undetectable Lie 10%, Subtle Glamour
  12%, Chillikin Companion 15%, Aura of Power 29%. This is what
  `test_every_description_matches_the_source_text` has been reporting all along; it is the
  same authoring cap as the Core Charms. The failing test IS the worklist.
- **Dispatch the release workflow by hand before tagging** — the four-asset matrix has
  still never been run. ⚠ The matrix itself was verified intact this session (2 OSes x
  webapp/Qt, macOS deliberately commented out), so the CLAUDE.md trap is not present; what
  is unverified is whether it RUNS.
- **The three Qt interplay checks and four never-used surfaces**, carried forward below.
- **The comment pass** on `ui/`, `models/` and `engine/` outside validate. ⚠ Re-measure
  the line counts first.

## What a human should click

The adversary picker is tests-green and rendered-offscreen but **not browser- or
app-clicked**. `/gm` → edit an adversary → hammer the Charms picker (1,861 rows, chips,
stay-open, the render cap's "…and N more" footer), then the same on the Qt Party window.

## ⚠ Read this before debugging anything the human reports from the app

This session spent **six rounds** on a bug that was already fixed, and the write-up in
`status/merits-flaws.md` is worth reading in full. The short version:

1. **Read the display-path code before measuring anything.** The answer was a
   `description[:320]` slice; six rounds went into `QScrollArea` geometry instead.
2. **`processEvents()` is not an event loop.** It produced `scroll max 0`, a confident
   wrong root cause, and a fix for a bug that did not exist — which was then reverted.
3. **Reproduce in the APP** (`main_window.py`, rail driven), never the page widget alone.
4. **Three free discriminators**: a cut between two characters with no space is a slice,
   not a wrap; a height-clipped `QLabel` cuts mid-glyph and adds no ellipsis; a stop at a
   round number means `git log -S`.
5. **To identify which BUILD is running, read its bytecode** —
   `PyInstaller.archive.readers` → `PYZ.pyz` → walk `co_names`/`co_consts`. That is how
   `dist/ExaltedBuilderQt` was shown to contain `_clamp` and the `~/Applications` download
   shown not to.

⚠ **The stale-binary warning was already in the last handoff and it still bit.** The
mechanism is now known and recorded in CLAUDE.md's deferred list: the app self-installs a
`.desktop` whose `Exec=` is pinned to the first frozen binary that ever ran, and nothing in
the UI reports a version. **Do not trust "I'm running the latest build" — verify it.**

## Carried forward from 2026-08-28, still true

The Qt port is **feature-complete and the Party window is clicked**. Three interplay checks
were never exercised, because that window was driven with a pre-loaded demo party:

1. Click a health box on a member card, then spend XP on that character in the builder —
   the card must redraw.
2. "Builder" on a card, edit something, come back — one builder, retargeted, same object.
3. Close the builder — the party window must go with it.

Four surfaces are still **rendered offscreen but never used**: the **Sheet tab**, the Party
window's **Reference tab**, the **Thaumaturgy → Rituals tab** and the **Custom tab's
Rituals sub-tab**.

⚠ **`dist/` is gitignored and its binary is from 2026-08-30** — it has none of this
session's work. Rebuild before showing the app to anyone, and see the launcher trap above.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The **Backgrounds in the
scan-only splat books** remain the one known content gap — a reading job, not a blocked one.

⚠ **The other splats' Charms were explicitly left as they are** (human, 2026-09-01), including
the `min_essence == min_ability` duplication grep that found three bad rows in Core. They
were authored by the same pass and are **not known to be clean** — untested, not verified.
