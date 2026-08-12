# Session handoff — 2026-08-12

**Rewritten each session.** The durable operating guide is `CLAUDE.md`.

## Current state
- Suite **2,127 passing**, no failures. The documented machine-only
  `test_every_description_matches_the_source_text` is GREEN on this machine now (the
  Godblooded chapter md is absent here, so its 46 entries defer) — still not a
  regression either way, see `docs/status/godblooded.md`.
- **The Backgrounds overhaul is DONE and browser-verified** (2026-08-12). Written up in
  `docs/status/backgrounds.md`; the click-through record is at the bottom of that file.
- `main` is at the close-out. `deepseek-experiment` is behind it.

## What happened this session
1. **`preflight`** — Pass 1 turned up nothing new (the 27 single-site effect fields are
   all pre-triaged; the four new Background fields all have healthy read sites). Pass 2
   confirmed the narrowed catalogue cannot crash a select (`_opts_with` folds the held
   value into the options). Pass 3 found the real gap: the per-row **rung label had no
   UI coverage at all**, only `view.background_rung` unit tests. Three harness tests
   added, negative-controlled.
2. **The click-through** — all six items passed, ladder rungs read correctly.
3. **One fix off it:** the dialog's ladder rendered as a wall of text. A plain NiceGUI
   label collapses newlines, so this took BOTH blank lines between rungs and
   `whitespace-pre-line` on the label. Covered by test; not re-clicked.

## Next up — in the order I'd take them
1. **Engine enforcement of the Background numeric rules** — the last open piece of the
   original ask and it needs **no pages**. The five thresholds are listed in
   `docs/status/backgrounds.md`; `engine/artifacts.py` is the precedent. Connections is
   the only one needing a new field ("cap from a trait total").
2. **Gear `resources_cost` vs the Resources Background** — ⚠ still blocked on the human
   saying what the rule IS (per-item or total, chargen-only or both sides). Do not infer
   it from the Artifact table.

## Waiting on the human (rules questions, do not choose)
- **The ten Mountain Folk Background copies carry no ladder.** They arrived with their
  own printed descriptions but no rungs, so a Mountain Folk row shows a description and
  no rung where a Solar shows both. Does CH6 print dot ladders for these, or prose only?
- **Tiger Warriors ladder** — a page break and a tangent table displaced every dot marker
  one line early. The reassembly is mechanical but it is the human's call
  (`garbled-transcription-defer`).

## Blocked on pages — do these at home, not at work
⚠ `images/` and `sources/` are gitignored and do not travel.
- **17 Lunar Charms** from the content gap. `sources/Exalted - The Lunars.pdf` is a PURE
  SCAN (0 of 258 pages carry text, so neither `extract_born_digital` nor
  `solve_cid_bands` applies) but rasterises cleanly with `pdftoppm -r 110`. **PDF page =
  book page + 3.** This is the job that would justify the Ollama VLM leg
  (`qwen3-vl:8b-instruct` is pulled); ⚠ its dot counts are biased low, so for any ladder
  take the rating from the rung's POSITION, never from counting.
- The rest of the 213 page-blocked catalogue entries — `docs/status/catalogue-sweep.md`
  ranks the syncs by yield.
