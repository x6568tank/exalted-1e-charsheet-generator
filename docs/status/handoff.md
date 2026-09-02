# Session handoff — 2026-09-01 (the Core Charm re-transcription)

# 👉 YOU ARE HERE

Last FULL green suite: **3,115 passed, 1 skipped** (main PC, `main`, 7m02s), run after the
last executable change. The tree is clean of half-finished work.

⚠ The count moved 3,083 → 3,115 for a reason that is not this session's data work: the
2026-09-01 commit `bb5adae` added `tests/test_extract_columns.py`, the column-splitting
guards for the born-digital extractor.

**One thing shipped: every Core Charm description was re-transcribed from the page, and
32 wrong printed values were corrected.** The whole record — including the traps, which are
worth more than the diff — is `docs/status/core-charm-retranscription.md`. Do not
re-derive it here.

In one paragraph: Core's 220 ability-file Charms carried descriptions averaging **113 characters**
against 500-1,000 for every other book, because they were authored from page images under a
delegation brief that capped descriptions at "one or two sentences". They are now **581**.
Four were not thin but **wrong** — Wise Arrow's dice cap, Rain of Feathered Death's target
rule, an invented "dazzling foes" effect, an invented Dexterity cap — all in the 2e-shaped
direction. A mechanical audit of the printed stat blocks then found **32 value
discrepancies** (27 minimums, 3 costs, 2 types), which the human read and ruled on, and
which are now applied.

## 👉 NEXT

Nothing is blocked. In rough order of what would bite:

- **No open questions.** Both were answered 2026-09-01 and are recorded in
  `core-charm-retranscription.md`: the **necromancy provenance** was a `source.book`
  corruption (pages right, book wrong — now `The Abyssals`, and the SECOND instance of that
  exact fingerprint), and the **330 artifacts do NOT need the description audit** — the
  "1-4 sentences" cap stays in both artifact briefs. ⚠ Do not re-propose either.
- **The 265 delegated spells still under the old cap** — Savant and Sorcerer (94), Bone &
  Ebony (62), Three Circles (48), Autochthonians (38), Abyssals (23). Same job as the 19
  Core spells in `bb5adae` and the 220 Charms here, same sources, and the method is now
  proven twice. This is the obvious next piece of the same thread.
- **Dispatch the release workflow by hand before tagging** — the four-asset matrix has
  still never been run, and a tag is the wrong place to find that out. Unchanged from the
  2026-08-28 handoff; `pack/BUILD.md`.
- **The three Qt interplay checks and four never-used surfaces**, carried forward below.
- **The comment pass** on `ui/`, `models/` and `engine/` outside validate — still the
  largest tidy-up owed. ⚠ Re-measure the line counts first.

## What a human should click, and why it is short

**Nothing in the UI changed** — this was data. Two things want eyes exactly once, because
the descriptions are now 3-8x longer than the panels were laid out against:

1. a **Charm detail panel** for any Solar corebook Charm (overflow, elision, buy control);
2. the **printed/PDF sheet** for a Solar carrying several of them.

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

⚠ **The binary on disk is from 2026-08-27 and `dist/` is gitignored** — it has none of this
session's work, or the last three sessions'. Rebuild before showing the app to anyone.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The **Backgrounds in the
scan-only splat books** remain the one known content gap — a reading job, not a blocked one.

⚠ **The other splats' Charms were explicitly left as they are** (human, 2026-09-01), including
the `min_essence == min_ability` duplication grep that found three bad rows in Core. They
were authored by the same pass and are **not known to be clean** — untested, not verified.
