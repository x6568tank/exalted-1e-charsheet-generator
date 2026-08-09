# Session handoff — 2026-08-09

**Rewritten each session.** This is the ephemeral handoff block; the durable operating
guide is `CLAUDE.md`. When a session ends, replace *Current state* and *Open threads*
with what the next session needs; everything else can point at the per-topic status
docs.

## Current state
- Suite green: **2,068 passing** (the one machine-only M&F description failure is not a
  regression — see CLAUDE.md → Status).
- Branch `deepseek-experiment`, worktree `…-ds`.
- Newest shipped (2026-08-08): the **castebook artifact batch** — the 12 genuinely-new
  remainder of the "40 authorable-now" backlog entries, addressed unsupervised (the
  human was out; the source pages were on disk). Ten became catalogue entries in
  `data/artifacts.json` (`artifact.castebook-*`, Caste Books Dawn/Night/Zenith
  pp.78-81 — Shield Bracer, Map of Azure Victory, Chariot of Aerial Conquest, Arrows of
  Distant Death, Spider Grippers, Belt of Shadow Walking, Circlet of Spirits, Hooked
  Daiklaves of Dual Prowess, Death Shield Ring, Ring of the Deliberative); the **Hooked
  Daiklaves** and the **Direlance** also got rated `weapons.json` rows (table stats,
  attune 4-per-blade / not printed). Also 2026-08-08: the rated-artifact **catalogue +
  combobox** (name field autofills name + rating, per-row description label), the **six
  dual-nature devices** (crossbows + Flamecaster + Pyromantic Grenade carry both
  `artifact_rating` and `resources_cost`; the player picks the funding with the Art/Res
  edit fields), and the **Elemental Powers** catalogue (9-power learnable set for
  Elemental-origin God-Blooded, PG p.68, 7 BP / 14 XP).
- **No open threads.** The Hooked Daiklaves rating ruling is CLOSED (the **heading ••••
  is canonical** — human checked `images/Solars/Castebooks/Night/81.png` 2026-08-08; the
  page's own table misprints •••••, so the catalogue and the weapon row both carry 4).
  The Advantages-tab combobox click-through is CLOSED (the name→rating autofill +
  description label + off-catalogue rename is **item-independent**, exercised with other
  catalogue items). ⚠ Two page-vs-guide rating disputes, **page as authority:** Ring of
  the Deliberative •••• (the guide's ••••• is 2e) and Hooked Daiklaves ••••.

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
- Castebook batch + catalogue/dropdown contract + dual-nature devices + alchemical-goods
  ruling: `docs/status/rated-artifacts.md`
- Elemental Powers + p.48 sorcery + the 80-Charm spirit catalogue: `docs/status/godblooded.md`
- Mountain Folk (Enlightenment axis, five-Pattern economy): `docs/status/mountain-folk.md`
- Session-state notes from prior handoffs live in git history, not here.
