# Session handoff — 2026-09-03 (artifact attunement, and two rules with no implementation)

# 👉 YOU ARE HERE

Last FULL green suite: **3,238 passed, 1 skipped** (main PC, `main`, 17m22s).
**4 commits ahead of `origin/main`, not pushed** — `ceac278` (attunement blockers + the
comment-pass correction), `46a4f30` (attunement phase 1), `bbdc661` (phase 2 + two Merit
fixes), plus the two carried from the previous session — and ⚠ **the working tree is
DIRTY**: the ST toggle, the species-3 fix and this whole close-out are uncommitted.

⚠ The count moved 3,181 → 3,238; all 57 are tests added this session. Nothing was fixed
by accident and nothing went missing.

## What shipped

**1. Artifact attunement, phases 1 and 2** (`status/rated-artifacts.md`, and
`plans/artifact-attunement.md` for the full design). An owned artifact with a printed
cost can commit its motes, and the Play tab's maxima come down by the total, on all four
mote surfaces. The flag is the player's — nothing auto-attunes. The derivation walks
`artifacts.artifact_items()`, the one enumeration, so a daiklave entered as both an
artifact row and its weapon stat line commits once; the **gear row wins** (human's
ruling). **Not browser-verified.**

**2. `MeritEffects.no_magical_material_bonus`** (`status/merits-flaws.md`). Both Magical
Attunement Merits refuse the material bonus in as many words and nothing implemented it —
the right answer arrived by coincidence, because a Mortal/God-Blooded exalt_type matches
no material. The same pages settled the attunement doubling: a character no material
resonates with pays the **printed** cost.

**3. `MeritEffects.essence_pool_split_thirds`** (`status/godblooded.md`). Aura of Power
was read from the save, stored, and had **zero read sites**. `essence_pool_is_merged`
asked the splat first, and a God-Blooded's `single_essence_pool` is True, so the Flaw
never got a vote. Reported from the human's own save; Taban now reads Personal 10 ·
Peripheral 21 instead of Single pool 31.

## 👉 NEXT

Nothing is blocked. In rough order of what would bite:

- **The `ArtifactType.attunement` backfill.** All 330 rows are 0, so the
  standalone-Wonder path is unexercised by real data. It is a **parse job, not a
  re-read**: 74 rows state a commitment in their transcribed description. ⚠ Exclude
  gear-statblocked duplicates first (`gear_stat_line`) — the Skirmish Pike is in the 74
  and must stay 0 because `weapons.json` holds its 5.
- **Attunement phase 3's remainder** — whether the printed sheet marks an attuned item.
  Low priority, untouched.
- **`qt/` is the one real comment-pass gap** (carried; `docs/comment-standard.md`).
- **The Backgrounds in the scan-only splat books** — still the one known content gap, a
  reading job.

## Rules questions — both ANSWERED 2026-09-03, none outstanding

- **`free_max` and committed motes** became an ST toggle rather than a ruling:
  `HouseRules.committed_motes_reduce_free_essence`, PER-CHARACTER, default OFF. The app
  cannot decide it, because both Willpower rolls involved are the table's.
- **Aura of Power's anima clause needs no implementation** — anima is a user-entered
  field. Not a gap; do not re-raise it.

⚠ **The toggle's own test found a SPECIES 3 house bug in the phase-2 work, and the
DEFAULT VALUE was the off switch.** A mortal's pool is entirely Personal and
`attuned_pool` defaults to `"peripheral"`, so a mortal's commitment landed on a
0-maximum pool and cost nothing — checkbox ticked, number right, tracker untouched.
Fixed by generalising the merged-pool case: **a commitment allocated to a pool the
character does not have is re-routed to the one they do.** Found by accident, because an
unrelated test's fixture happened to be a mortal. `status/rated-artifacts.md`.

## What a human should click

**Nothing this session was browser- or app-clicked.** In priority order:

1. A **daiklave** on the Gear tab in both shells — real catalogue attunement (5 motes).
   Checkbox appears; pool dropdown only once checked.
2. The **Play tab** after attuning it — the pool shrinks and the note says why.
3. A **ghost** (merged pool) — no pool choice offered at all.
4. A **mortal** with Essence Awareness and an attuned artifact — the motes must come out
   of Personal (their only pool), and the new ST toggle should appear on ST Options and
   move the free-mote line when flipped. This is the path that was silently free until
   2026-09-03.
5. **Taban's sheet and printed PDF** — the split reads Personal 10 · Peripheral 21.

## ⚠ Two test traps this session paid for, both re-bitable elsewhere

1. **Qt: `isVisible()` is False for everything on a page that is never shown.** A
   headless visibility assertion passes against a control that is *always* shown, and its
   positive half cannot pass at all. Use **`isHidden()`**.
2. **A fixture that omits the axis a rule keys on produces a confident, WRONG gap
   report.** A synthetic God-Blooded built with no `caste` showed an Essence pool of 0,
   and that was written up as "Awakened Essence grants no pool" — a fabricated second
   bug. The pool formula is heritage-keyed and had worked all along. It was the human's
   real save that corrected it. Same shape bit the merged-pool test the same day: a
   synthetic ruleset with no Ghost exalt made it assert the exact bug it guarded.
   **Splat-shape and merged-pool tests need the REAL `ruleset` fixture.**

## Carried forward, still true

The Qt port is feature-complete and the Party window is clicked. Four surfaces are still
**rendered offscreen but never used**: the **Sheet tab**, the Party window's **Reference
tab**, the **Thaumaturgy → Rituals tab** and the **Custom tab's Rituals sub-tab**.

⚠ **`dist/` is gitignored and its binaries are from 2026-08-14 / 2026-08-30** — neither
has this session's work. Rebuild before showing the app to anyone, and remember the
launcher trap: `branding.install_desktop_entry()` pins `Exec=` to the first frozen binary
that ever ran, and nothing in the UI reports a version. ⚠ **This session, the stale-binary
theory was WRONG** — the suspected fix predated the binary by a month. Check the dates
before blaming the build.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no.

⚠ **The other splats' Charms were explicitly left as they are** (human, 2026-09-01),
including the `min_essence == min_ability` duplication grep that found three bad rows in
Core. Untested, not verified.
