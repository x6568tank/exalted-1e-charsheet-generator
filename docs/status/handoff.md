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

- **The 46 M&F descriptions measurably short of source is machine-conditional, not a
  standing worklist.** `test_every_description_matches_the_source_text` only checks
  entries whose covering chapter is pasted into (gitignored) `images/`; it defers the
  rest rather than failing them. **On this checkout (2026-09-03), the Godblooded
  (PG pp.65-80) and ghost (p.234) chapters are absent — 71 entries deferred, 0 failing**,
  and this was verified genuine, not a broken check: the 88 entries covered by the
  pasted CH1 chapter (PG pp.16-41) all pass at .97-.99 ratio, and a negative control
  (truncating Amputee's description to 20 chars) made the test fail correctly, then was
  reverted clean. The "46 short" figure is real only on a machine that has those two
  chapters pasted — re-run the test there to get the current worklist; do not treat a
  clean run elsewhere as the gap having closed. `docs/testing.md` already documented
  this outcome as machine-dependent and healthy; nothing here contradicts that.
- **The release workflow and the Qt interplay checks below are DONE, not open** — human
  confirmation 2026-09-03: multiple tagged builds have since run the four-asset matrix
  clean, and all three Party-window interplay checks (health-box redraw, single
  retargeted builder, close-cascade) were clicked and correct. Struck from NEXT; do not
  re-carry them.
- **The comment pass is also stale in its own doc, corrected 2026-09-03.**
  `ui/`/`models/`/`engine/` outside validate already had it — two 2026-08-20 commits
  (`ea0df0e`, `2833f682`) did the trimming three days after the standard was written,
  just never recorded here. Re-measured density is down sharply (61%→22% models,
  24%→11% ui, 38%→26% engine) and a spot-check of the longest remaining docstrings found
  citations/⚠/contract, not narration. **`qt/` is the one real gap** — it postdates the
  original 2026-08-17 measurement and has never had the pass. `docs/comment-standard.md`.

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

The Qt port is **feature-complete and the Party window is clicked**. ⚠ The three
interplay checks once carried here (health-box redraw, builder retarget, close-cascade)
are **DONE as of 2026-09-03** (human confirmation, all three clicked and correct) — do
not re-carry them as open.

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
