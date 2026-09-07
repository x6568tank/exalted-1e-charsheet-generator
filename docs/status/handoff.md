# Session handoff — 2026-09-07 (the artifact-attunement backfill)

# 👉 YOU ARE HERE

Last full suite on this machine (**the MAIN PC**): **3,251 passed · 1 failed · 1 skipped**,
8m22s. ⚠ **I called it the laptop twice before the human corrected me** — inferred from the
count and from the M&F test failing here, which `docs/testing.md` records as the outcome on
*some* machines. The arithmetic actually agrees with the main PC once `pypdf` is accounted
for: 3,194 collected + the 45 skipped PDF tests = 3,239, against the 3,238 + 1 skip recorded
here on 2026-09-03. **A test count does not identify a machine** — an absent optional
dependency moves it by more than the gap between two machines. ⚠ **The failure is the known machine-dependent one** —
`test_merits_flaws.py::test_every_description_matches_the_source_text`, 46 entries — and it
**fails identically on the stashed tree**, so it is not this session's work.

⚠ **But "machine-dependent" is not "noise", and the mechanism deserves stating**: that test
reads the source `.md` chapters off disk and **DEFERS any Merit whose chapter is not
there**. So it goes green by having less source available, and a machine where it FAILS is
the machine where the check actually ran. Here it ran and found 46 descriptions under 92%
of their printed text — the same order-of-magnitude-too-thin shape as the Core Charms
before their re-transcription, not a machine quirk. `docs/testing.md` has it as an oddity;
what it is measuring is real.

⚠ **The count rose 3,194 → 3,253 and only 14 of that is new tests.** The other 45 were
already written and were being SKIPPED: `tests/test_pdf.py` module-skips when `pypdf` is
missing, and it was missing from this venv even though `pyproject.toml` declares it in the
test extra. It is installed now — which is why the skip count also fell from 2 to 1. ⚠ **A
sheet change on this machine was therefore unverifiable until then**, and the skip said so
in one grey line at the bottom of a run. Check `-rs` before trusting a green PDF run. `docs/testing.md` for how to read a
run's numbers honestly; **do not reconcile this against the main PC's 3,238.**

The tree at session start was **clean and level with `origin/main`** — everything the
2026-09-03 handoff listed as uncommitted went out in `754ea95`. This session's work is
**uncommitted**.

## What shipped

**1. The `ArtifactType.attunement` backfill** — the top NEXT item from the last handoff,
now done. 89 of the 330 catalogue rows carry a printed commitment (1 to 15 motes); the other
241 print no figure. **No page was opened**: every value was parsed out of the row's own
human-vetted `description`. The standalone-Wonder path is no longer unexercised by real
data. Method, guards and both deferral lists: `status/rated-artifacts.md`.

Three tests came out of the pass's two guards — the number must appear in the description
it was read from, and **no gear-statblocked duplicate may carry a number** (the daiklaves,
the powerbows, the five artifact armours and the Skirmish Pike stay 0 because
`weapons.json`/`armor.json` own their cost).

**2. Attunement phase 3 — the sheet marks it.** "Printed sheet should" (human), so the
artifact row now prints **`attuned · 5m`** on all three sheet surfaces (screen, Qt, PDF)
through ONE helper, `view.attunement_mark`. The number is the effective cost, doubled where
the wielder is not a user of the item's material. It appears in the **Artifacts** panel
only, and that is complete rather than partial: `_artifact_rows` folds artifact weapons and
armour into that panel, so every attunable thing is marked exactly once. ⚠ The pools beside
it are still the FULL ones — only the Play tab subtracts — which is why the mark carries
the cost and not just the word. `SheetView.artifacts` is a 5-tuple now.

**That closes artifact attunement** apart from a human click-through.

**NOT browser-verified.** Nothing was clicked.

## 👉 NEXT

Nothing is blocked.

- **A human click-through of attunement** — now the ONLY thing left in it, and it has real
  catalogue data behind it. The five-item list is unchanged and lives at the bottom of
  `status/rated-artifacts.md`'s 2026-09-03 section; pick a **daiklave**, then a
  **standalone Wonder** (the Ring of Being at 15 motes is the loudest), then the mortal
  case that was silently free until 2026-09-03 — and now also **the sheet and the PDF**,
  which should say `attuned · Nm` beside the item while the pools stay full.
- **Six gear rows need a page, and they are all Aspect Book rows** — the Most Terrifying
  Armor of the Air Dragon (Air p.81), Forge-Hand Gauntlets + Eye of the Fire Dragon (Fire
  p.81), Black Widow Razors + Death at the Root (Wood p.83), Gauntlets of Distant Touch
  (Water p.80). ⚠ **No Aspect Book material is under `images/` on the main PC** as of
  2026-09-07, though `derive.py` cites an `images/Dragonblooded/Aspects/…` path and the six
  stat lines were authored from those books. That citation was deliberately NOT "fixed" —
  an absent path is not a missing source. The pages need putting in front of me.
- **Two more want a ruling, not a page** — Cold Wind Knives and the Powerbow of Perfect
  Accuracy. Both pages ARE on disk and were read 2026-09-07; neither prints a commitment,
  and the Powerbow's whole spread has every neighbour's cost already authored, so its 0 is
  right-by-absence. `status/rated-artifacts.md`.
- **`qt/` is the one real comment-pass gap** (carried; `docs/comment-standard.md`).
- **The Backgrounds in the scan-only splat books** — still the one known content gap.

## Rules questions — one answered, two open

**ANSWERED 2026-09-07: the four transient commitments are ordinary attunement.** The Horn
of the Ways (5), the Traveler's Staff (5), the Blood Seed (10) and the Lizard Tail
Regrowth Sphere (10) commit motes for the duration of a USE and say the Essence comes
back; the human's ruling is that **the toggle already on the artifact/gear row is the
control** — opt-in per item, ticked for the scene and unticked after. No transient-vs-
standing distinction in the model. ⚠ Do not re-raise it as a modelling gap.

**ANSWERED 2026-09-07: the Wavecleaver Daiklaive and the Direlance commit 5** — the
daiklave family's cost, neither printed on any page on disk. ⚠ Both `notes` strings record
that the number is a ruling rather than a reading, and a test pins each; the ruling also
turned `test_data.py`'s `lance.attunement == 0` from a true statement about an absence into
a failure, the negative-control-goes-positive shape again.

Still open: whether the printed sheet marks an attuned item (carried from 2026-09-03).

## What the pass turned up

⚠ **Six rows state in as many words that they cost NOTHING to attune** (Iron Horse, Slayer
Khatar, Essence Storing Crystal, Face of Discretion, Skin-Mount Amulet, Winterbreath Jar).
They are correct at 0 — but their 0 is now indistinguishable from the 245 rows that simply
have no printed figure. The same authored-clean-vs-never-backfilled ambiguity this pass
closed for the other 85, one level down. Not worth a field unless it bites.

## Carried forward, still true

The Qt port is feature-complete and the Party window is clicked. Four surfaces are still
**rendered offscreen but never used**: the **Sheet tab**, the Party window's **Reference
tab**, the **Thaumaturgy → Rituals tab** and the **Custom tab's Rituals sub-tab**.

⚠ **`dist/` is gitignored and its binaries are from 2026-08-14 / 2026-08-30** — neither has
this work. Rebuild before showing the app to anyone, and remember the launcher trap:
`branding.install_desktop_entry()` pins `Exec=` to the first frozen binary that ever ran,
and nothing in the UI reports a version. ⚠ **Check the DATES before blaming the build** —
on 2026-09-03 the stale-binary theory was wrong twice over.

⚠ **The two test traps from 2026-09-03 are still live elsewhere**: Qt's `isVisible()` is
False for everything on a page that is never shown (use `isHidden()`), and a fixture that
omits the axis a rule keys on produces a confident, WRONG gap report (splat-shape and
merged-pool tests need the REAL `ruleset` fixture).

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The artifacts were ruled
FINE on description quality (human, 2026-09-01) — that ruling is about prose, and did not
bar this pass, which read those descriptions rather than judging them.
