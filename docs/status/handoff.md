# Session handoff — 2026-08-10 (end of day)

**Rewritten each session.** This is the ephemeral handoff block; the durable operating
guide is `CLAUDE.md`. When a session ends, replace *Current state* and *Open threads*
with what the next session needs; everything else can point at the per-topic status
docs.

## Current state
- Suite green: **2,092 passing** (the one machine-only M&F description failure is not a
  regression — see CLAUDE.md → Status). Branch `main`.
- **⚠ Uncommitted at end of session: the tier-2 move** (6 files — `engine/adversaries.py`,
  `ui/adversaries.py`, `ui/view.py`, `docs/ARCHITECTURE.md`,
  `docs/status/adversary-roster.md`, `docs/plans/qt-port.md`), plus this close-out's doc
  edits. Suite green with them in place. **Branch before committing** — the convention is
  no direct commits to `main`.
- **Catalogue picker dialogs — DONE, browser-verified, through TWO code-review passes**
  (`a5fc3f6`, `b162a05`, `fbe97a0`). The second pass found a serious bug the first fix
  introduced and corrected an overclaim. Record: `docs/status/catalogue-dialogs.md`.
- **The `undo_last` merits bug is FIXED and browser-verified.** `undo_last` grew a
  `merits` branch — buys/gains remove the last matching `MeritFlawPurchase`, drops re-add
  the purchase carried on a new `XpEntry.removed_purchase`, legacy drop rows are refused
  — and XP-log rows label merits by name instead of the bare "merits".
  Record: `docs/status/merits-flaws.md` → *Undo of Merit changes*.
- **A Qt/PySide6 port is now a recorded post-1.0 goal**, not scheduled and not started.
  Plan, measured baseline and open questions: `docs/plans/qt-port.md`; the standing
  guard is in CLAUDE.md → *After 1.0 — the Qt port*.
- **Three misplacement cleanups landed** on the strength of that audit — see below.

## 👉 START HERE — nothing is blocking
No click-through is owed on this session's work. Pick from *Open threads*; the cheapest
is the Twilight/Eclipse artifact names.

## What moved this session (the layering cleanups)
All three were behaviour-preserving, verified by diffing each moved function against its
pre-move source, and left every call site and test untouched via re-exports.

1. **`engine/thaum_actions.py`** — 206 lines of lock-dispatching thaumaturgy purchases
   out of `ui/picker.py` (2,313 → 2,124 lines). They were game logic and never imported
   `nicegui`. `picker.py` re-exports every name.
2. **Tier 1 — one printed rule encoded twice, in two places.** `editor._BASE_HEALTH` is
   now `Counter(derive.BASE_WOUND_PENALTIES)` instead of a hand-written
   `{0: 1, -1: 2, -2: 2, -4: 1}`; the weapon/armour stat lines are one copy in
   `view.weapon_stat_line` / `armor_stat_line` instead of two. **The armour pair had
   already drifted** — two spaces before `Mob` in the row readout, one in the catalogue
   dialog, while the dialog's docstring claimed they matched. Unified on the row
   readout's spacing (the older, browser-verified surface).
3. **Tier 2 — `ui/adversaries.py` 640 → 490 lines**, now widgets only. Ids, duplicate
   naming and the trait/attack codec went to `engine/adversaries.py`; `summary_line` and
   `trait_map_line` went to `view.py`.

## ⚠ Flagged, not invented
- The **Flamecaster / Pyromantic Grenade** print a Resources cost only; their Artifact
  rating **mirrors 3** so the Art field can fund them either way — the ST sets the real
  value.
- The **Myrmidon Carapace**'s weight class is not printed — assigned **Medium**, human
  confirmed fine 2026-08-08.
- The **alchemical goods** (Godstrike Oil, Pyromantic Gel, Synthetic Leather, MF
  pp.275-277) were authored as a `GoodType` catalogue, shown in the browser, then
  **removed on the human's ruling** — the build only catalogues what feeds a mechanical
  read site (materials → derive, artifacts → budget/dropdown, weapons/armour → the
  sheet); a goods card would be the first data with no mechanism behind it. Full
  transcription kept in `docs/status/rated-artifacts.md` → *The alchemical goods*.
- **Undo of a merit drop on a pre-fix save is permanently refused**, and `undo_last` is
  LIFO, so such a save's undo stack is blocked from that row down. Deliberate — the
  human's call is that no save in existence holds a pre-fix merit-drop row. Written up
  beside the design rationale it appears to contradict, in
  `docs/status/merits-flaws.md`.

## Open threads (none urgent)
- **The 20 Twilight/Eclipse artifact names are still NOT browser-verified.** Pin +
  combobox tests green, but no click-through of the new names in the Advantages tab.
  Light check — pick a Twilight and an Eclipse name, confirm name→rating autofill +
  description label.
- **Tier 3 of the `ui/` audit** — five small sites (`play.py`'s PlayState mutators,
  `editor.py`'s origin/upbringing options, `builder.py`'s `visible_tabs`,
  `storyteller.py`'s `set_rule`, three duplicate dot formatters). **Deliberately not
  scheduled**: sweep each up while porting the module it lives in. Table with
  destinations in `docs/plans/qt-port.md` → *The audit*.
- **Naming follow-up:** `thaum_actions.raise_thaum_science` / `add_thaum_orientation`
  shadow the `advancement` functions they call after the lock. Works, reads badly;
  renaming the dispatchers is a clean standalone commit.

## Blocked / not started
- **Direlance catalogue entry** + **Slayer Khatar** — their description pages aren't on
  disk (p.341's crop is Artifact Materials, p.344's is the Lightning Torment Hatchet).
  Per-book authoring queue: `docs/status/artifact-backlog-entries.md`.
- **Dragon-Blooded numina / the Mist aspect** — blocked on pages; see CLAUDE.md →
  TODO → Blocked.

## Pointers
- The post-1.0 Qt port plan + the `ui/` misplacement audit (tiers 1-3):
  `docs/plans/qt-port.md`
- Catalogue dialogs + both code-review passes (the canary trap, the drop-returns-None
  ruling): `docs/status/catalogue-dialogs.md`
- Merit undo, `XpEntry.removed_purchase`, the legacy-row guard: `docs/status/merits-flaws.md`
- Thaumaturgy purchases now in `engine/thaum_actions.py`: `docs/status/thaumaturgy.md`
- The adversary trait/attack **codec pair** invariant: `docs/status/adversary-roster.md`
- Twilight/Eclipse batch + catalogue/dropdown contract + dual-nature devices +
  alchemical-goods ruling: `docs/status/rated-artifacts.md`
- The 1E artifact discovery layer + per-book queues: `docs/status/artifact-backlog.md`,
  `docs/status/artifact-backlog-entries.md`
- Elemental Powers + p.48 sorcery + the 80-Charm spirit catalogue: `docs/status/godblooded.md`
- Mountain Folk (Enlightenment axis, five-Pattern economy): `docs/status/mountain-folk.md`
- Session-state notes from prior handoffs live in git history, not here.
