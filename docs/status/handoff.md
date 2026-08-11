# Session handoff — 2026-08-11 (end of day)

**Rewritten each session.** This is the ephemeral handoff block; the durable operating
guide is `CLAUDE.md`. When a session ends, replace *Current state* and *Open threads*
with what the next session needs; everything else can point at the per-topic status docs.

## Current state
- Suite green: **2,102 passing** (the one machine-only M&F description failure is not a
  regression — CLAUDE.md → Status). Branch `main`; `deepseek-experiment` merged and
  0 ahead.
- **The 1.0 catalogue sweep is DONE for everything on disk** —
  `docs/status/catalogue-sweep.md`. Charms 1,709 → **1,836**, spells 92 → **246**,
  artifacts 40 → **196**, across six delegated batches, **browser-verified 2026-08-11**.
- **`sources/` extraction is authorised** (human, 2026-08-10) and eight books are
  decoded into `images/_extracted/`. Three were ciphered; the corebook has thirteen
  fonts each with its own cipher. Tools + the ciphers-as-data: `tools/glyph_maps/`,
  `tools/solve_cid_bands.py`, `tools/extract_born_digital.py`,
  `tools/apply_glyph_map.py`.
- **Decision 0015 — Exalt tiers are RANKED** (Terrestrial < Celestial < Solar). Solar
  had been mislabelled `Celestial` because exact-match could not express "or below";
  Alchemical matched nothing and needed a hardcoded Perfected Lotus Matrix grant. Both
  fixed.
- ⚠ **`images/` does not travel between worktrees or machines.** The extractions live
  only on this machine. Every glyph map and tool IS committed, so they can be
  regenerated — one command per book.

## 👉 START HERE — nothing is blocking
No click-through is owed. Everything authorable from text on disk is authored.

## The one thing that unblocks more work: page syncs
**213 entries remain and every one is page-blocked.** By combined yield:

| Book | Artifacts | Spells | Charms | Total |
|---|---|---|---|---|
| Book of Three Circles | 14 | 49 | — | **63** |
| Savage Seas | 4 | 4 | 10 | **18** |
| The Lunars | — | — | 17 | **17** |
| Abyssals pp.254-261 | 16 | — | — | **16** |
| Time of Tumult | 11 | — | 3 | **14** |
| Blood and Salt | 11 | 2 | — | **13** |
| Aspect Book: Air | 13 | — | — | **13** |

⚠ **Before authoring any of it, read `catalogue-sweep.md`'s trap list** — in particular
that *"missing from the build" is not "should be authored"*, which sent two batches
deliberately-excluded content this session.

## Open questions for the human (none blocking)
- **Rathess p.86** — three artifacts under a `COLUMN SPLIT FAILED` marker; a
  reassembly is in `artifact-batch-2-notes.md` awaiting a one-read sign-off.
- **`Insidious Ebon Xoanon`** prints `ARTIFACT N/A`; `rating` is required 1-5.
- **`Kireeki-class Assault Skyreme`** — the fan index places it at Outcaste p.64, which
  is the Skywolf; the name is nowhere in the book.
- **Savant and Sorcerer `(cid:144)`** + seven rarer codes (25 occurrences) unmapped.

## Older threads, still open
- **Tier 3 of the `ui/` audit** — five small sites; deliberately not scheduled, sweep
  each up while porting its module (`docs/plans/qt-port.md` → *The audit*).
- **Naming follow-up:** `thaum_actions.raise_thaum_science` / `add_thaum_orientation`
  shadow the `advancement` functions they call. Works, reads badly.
- **Dragon-Blooded numina / the Mist aspect** — blocked on pages; CLAUDE.md → Blocked.

## Pointers
- The sweep, its five traps, and the new gate mechanics: `docs/status/catalogue-sweep.md`
- Per-batch records: `spell-batch-notes.md`, `artifact-batch-notes.md`,
  `artifact-batch-2-notes.md`, `ghost-arcanoi-batch-notes.md`,
  `martial-arts-batch-notes.md`, `charms-closeout-notes.md`
- Every missing entry, per book: `docs/status/content-gap-entries.md`
- How `source.book` is written and why it rots: `docs/source-attribution.md`
- Ranked tiers, alternatives rejected, what it costs: `docs/decisions/0015-*.md`
- The post-1.0 Qt port (now decision **0016** when committed): `docs/plans/qt-port.md`
