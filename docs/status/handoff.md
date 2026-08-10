# Session handoff — 2026-08-10

**Rewritten each session.** This is the ephemeral handoff block; the durable operating
guide is `CLAUDE.md`. When a session ends, replace *Current state* and *Open threads*
with what the next session needs; everything else can point at the per-topic status
docs.

## Current state
- Suite green: **2,081 passing** (the one machine-only M&F description failure is not a
  regression — see CLAUDE.md → Status).
- Branch `deepseek-experiment`, worktree `…-ds`.
- Newest shipped (2026-08-10): **the catalogue picker dialogs, browser-verified same
  day** — a shared `ui/catalogue.py` dialog on every add surface (weapons/armour/
  artifacts/backgrounds/M&F): filterable list of name + summary, full description
  collapsible, a **Custom** row. Custom M&F is display-only via
  `MeritFlawPurchase.custom_name` (no mechanical effect, renders by name on the sheet,
  drops freely). The old silent cheapest-append `add_merit` is deleted. The only
  click-through finding was dialog size (widened 34rem→46rem, list 55vh→75vh).
  Full record: `docs/status/catalogue-dialogs.md`.
- Earlier 2026-08-08 (committed, **written up this session**): the **Twilight/Eclipse
  catalogue batch** — Caste Book Twilight (12) + Eclipse (8) pp.79-81, VLM-transcribed,
  into `data/artifacts.json` (now **40 entries**; no on-disk artifact remains
  unauthored; Audient Brush is a phantom). Full record: `docs/status/rated-artifacts.md`
  → *The 2026-08-08 evening batch*; `artifact-backlog.md` on-disk rows corrected.
- **Open thread: the 20 Twilight/Eclipse names are still NOT browser-verified.** The
  pin + combobox tests are green, but no click-through of the new names. Light check —
  pick a Twilight and an Eclipse name in the Advantages tab, confirm name→rating
  autofill + description label.

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

## Blocked / not started
- **Direlance catalogue entry** + **Slayer Khatar** — their description pages aren't on
  disk (p.341's crop is Artifact Materials, p.344's is the Lightning Torment Hatchet).
  Per-book authoring queue: `docs/status/artifact-backlog-entries.md`.
- **Dragon-Blooded numina / the Mist aspect** — blocked on pages; see CLAUDE.md →
  TODO → Blocked.

## Pointers
- Twilight/Eclipse batch + catalogue/dropdown contract + dual-nature devices +
  alchemical-goods ruling: `docs/status/rated-artifacts.md`
- The 1E artifact discovery layer + per-book queues: `docs/status/artifact-backlog.md`,
  `docs/status/artifact-backlog-entries.md`
- Elemental Powers + p.48 sorcery + the 80-Charm spirit catalogue: `docs/status/godblooded.md`
- Mountain Folk (Enlightenment axis, five-Pattern economy): `docs/status/mountain-folk.md`
- Session-state notes from prior handoffs live in git history, not here.
