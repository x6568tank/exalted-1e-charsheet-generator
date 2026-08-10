# Session handoff — 2026-08-10

**Rewritten each session.** This is the ephemeral handoff block; the durable operating
guide is `CLAUDE.md`. When a session ends, replace *Current state* and *Open threads*
with what the next session needs; everything else can point at the per-topic status
docs.

## Current state
- Suite green: **2,092 passing** (the one machine-only M&F description failure is not a
  regression — see CLAUDE.md → Status). Tree clean, branch `deepseek-experiment`,
  worktree `…-ds`.
- **The `undo_last` merits bug is FIXED** (this session): `undo_last` grew a `merits`
  branch — buys/gains remove the last matching `MeritFlawPurchase`, drops re-add the
  purchase carried on a new `XpEntry.removed_purchase`, legacy drop rows are refused —
  and XP-log rows now label merits by name instead of the bare "merits". 8 new tests.
  Record: `docs/status/merits-flaws.md` → *Undo of Merit changes*. **Not
  browser-verified** (see START HERE).
- **Catalogue picker dialogs are DONE and committed** (`a5fc3f6`, `b162a05`,
  `fbe97a0`), browser-verified 2026-08-10, through **two code-review passes** — the
  second found and fixed a serious bug (the play Custom prompt died because a nested
  `ui.dialog()`'s canary lived inside the catalogue dialog's tree; it now builds in
  `context.client.layout`) and corrected an overclaim (a custom M&F drop returns `None`
  and logs nothing — it has no XP value, so there is nothing to undo; the real gap,
  `undo_last` having no merits branch for REAL drops, is now closed). Full record:
  `docs/status/catalogue-dialogs.md`.

## 👉 START HERE — browser-verify the merit-undo fix
The fix is engine + presenter and is pinned by 8 tests, but **not browser-verified**.
Click-through: in play, buy a Merit for XP (e.g. Lucky), confirm the sheet lists it and
the XP card shows it, hit **Undo last: …** in the Experience card — the Merit row should
leave the sheet and the XP come back. Then drop a Merit (Advantages tab) and Undo — it
should return, full state (tier/arena/detail) intact, XP restored. The "Undo last"
button should name the Merit, not "merits".

(Also still open: the Twilight/Eclipse artifact names — see Open threads.)

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

## Open threads (not the focus this session)
- **The 20 Twilight/Eclipse artifact names are still NOT browser-verified.** Pin +
  combobox tests green, but no click-through of the new names in the Advantages tab.
  Light check — pick a Twilight and an Eclipse name, confirm name→rating autofill +
  description label.

## Blocked / not started
- **Direlance catalogue entry** + **Slayer Khatar** — their description pages aren't on
  disk (p.341's crop is Artifact Materials, p.344's is the Lightning Torment Hatchet).
  Per-book authoring queue: `docs/status/artifact-backlog-entries.md`.
- **Dragon-Blooded numina / the Mist aspect** — blocked on pages; see CLAUDE.md →
  TODO → Blocked.

## Pointers
- Catalogue dialogs + the code-review fixes (incl. the canary trap and the drop-returns-
  None ruling): `docs/status/catalogue-dialogs.md`
- Twilight/Eclipse batch + catalogue/dropdown contract + dual-nature devices +
  alchemical-goods ruling: `docs/status/rated-artifacts.md`
- The 1E artifact discovery layer + per-book queues: `docs/status/artifact-backlog.md`,
  `docs/status/artifact-backlog-entries.md`
- Elemental Powers + p.48 sorcery + the 80-Charm spirit catalogue: `docs/status/godblooded.md`
- Mountain Folk (Enlightenment axis, five-Pattern economy): `docs/status/mountain-folk.md`
- Session-state notes from prior handoffs live in git history, not here.
