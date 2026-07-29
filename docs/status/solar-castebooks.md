# Status detail — Solar castebooks

Referenced from `CLAUDE.md` → Status. DONE 2026-07-25.

Read from `images/Solars/Castebooks/<Dawn|Eclipse|Night|Twilight|Zenith>/*.png`
(29 page scans). **139 Charms, 7 spells, 30 weapons, 2 armours.** Open items,
source defects and the rules calls are in
`images/Solars/Castebooks/_CASTEBOOK_PENDING.md` — read that before touching this.
Tests: `tests/test_solar_castebooks.py`.
- **The three missing Martial Arts styles are now authored** — the ones
  `data/camps.json`'s Sequestered Tabernacle package has named since the Illuminated
  work: **Tiger** (`martial_arts:tiger`, 9, Dawn p.73-74), **Praying Mantis**
  (`martial_arts:praying-mantis`, 10, Eclipse p.73-75) and **Ebon Shadow**
  (`martial_arts:ebon-shadow`, 11, Night p.67-70), each in its own file per the
  one-file-per-style convention. All three are **Solar-only** (no `open_to_all`/
  `open_to_tiers` — their pages say nothing about other splats, unlike Falling
  Blossom). Eclipse's own heading is "Mantis-Style", but the category key is
  `praying-mantis` because `camps.json` already said so; the key is pinned from BOTH
  sides in the tests, since renaming it would silently empty that grant.
- **Five castebook Charms were already in `data/`** from Cult of the Illuminated,
  which reprints them — Tireless Traveler's Stamina, Excellent Emissary's Tongue,
  Graceful Courtier Attitude, Prey-Freezing Gaze, Game-Snaring Huntsman's Method.
  They were NOT re-authored. **Rules-authority call, 2026-07-25: where the two books
  disagree the ILLUMINATED version wins, in every case** — including Excellent
  Emissary's Tongue, which Illuminated lists as merely "reprinted for ease of
  reference" yet prices differently (4 motes + 1 WP vs the castebook's 3 motes).
  `data/` already held the Illuminated numbers, so nothing changed. Do not
  "correct" them back; the discrepancies are tabulated in `_CASTEBOOK_PENDING.md`.
- **Four new multi-gate Charms** join Ascendant Battle Visage in using
  `extra_min_abilities` (Masterful Training Manual, Impenetrable Identity, Drunken
  Warrior Technique, Inebriated Fool Defense). Same rule as before: the extra is a
  requirement check ONLY and never touches pricing — pinned by a test.
- **Environmental Hazard-Resisting Meditation (Zenith p.72-73) is a SECOND
  repeatable Solar Charm** — 4 resistance variants, cap = Resistance dots, "similar
  to Ox-Body Technique". The DATA is complete (`repeatable_cap_ability`+`variants`);
  the ENGINE is deliberately NOT wired, because a repeatable Charm needs its own
  `Character` list and this would be the fifth list outside `character.charms`.
  Today it is an ordinary one-off pick (legal, priced, gated). The enumeration blocker
  is gone entirely as of 2026-07-29 — `validate.charm_picks` /
  `chargen_charm_picks` / `charm_pick_bp_costs` (see `engine-and-ui.md`) are the one
  place a new repeatable list has to be taught about, and display, counting AND BP
  pricing all follow from it. What remains is the STORAGE half: a `Character` list, an
  `ExaltDefinition` field naming the Charm, cap/variant checks, XP, the lock snapshot,
  undo and a picker panel.
- All seven Twilight spells are authored (p.74-77); p.77 then turns to hearthstones,
  which `note.md` puts out of scope, so the castebooks are complete within it.
- Gear: `notes` carries everything the models have no field for — Strength-relative
  damage, the Siege Crossbow's 1/10 rate, the Flame Spear's `+6/8*` split. Two items
  (Ultimately Useful Tube, Gauntlets of Distant Claws) are two catalog rows each.
  Per the human's `note.md`, hearthstones/Manses/non-gear artifacts were skipped.
