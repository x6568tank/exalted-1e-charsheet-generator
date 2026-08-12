# Session handoff — 2026-08-12

**Rewritten each session.** The durable operating guide is `CLAUDE.md`.

## Current state
- Suite **2,147 passing**, no failures. The documented machine-only
  `test_every_description_matches_the_source_text` is GREEN on this machine now (the
  Godblooded chapter md is absent here, so its 46 entries defer) — still not a
  regression either way, see `docs/status/godblooded.md`.
- **The Backgrounds overhaul is DONE and browser-verified** (2026-08-12), and the
  **numeric rules are now implemented** (same day, 9 new tests) — but the numeric
  rules are **NOT yet browser-verified**. Written up in `docs/status/backgrounds.md`.
- `main` is at the close-out. `deepseek-experiment` is behind it.

## What happened this session
1. **The Background numeric rules implemented** (`docs/briefs-background-rules.md`, 12
   tests in `tests/test_background_rules.py`, suite 2,134 → **2,147**). R1 Connections
   ≤ the Attribute sum (a new `max_rating_is_attribute_sum` field); R2 Celestial Manse
   ≤3 on BOTH sides with a PER-CHARACTER toggle; R3 mortals barred from Artifact/Manse
   with a toggle; R4 Mountain Folk Artifact ≤10 at 1 BP/dot above 5; R5 the plumbing —
   `background_issues` takes an optional character + `post_lock`, called post-lock from
   `validate.validate` for `bind_post_lock` rules only, and both rating controls read
   `validate.background_rating_cap`. The model's `BackgroundEntry.rating` was a THIRD
   hardcoded 5 and is relaxed to `le=10` (the human's R4 number). ⚠ **NOT browser-verified.**
2. **The earlier session's click-through and ladder-fix record stands** (see below).

## Next up — in the order I'd take them
1. **Browser-verify the numeric rules** — the click-through list is at the bottom of
   `docs/status/backgrounds.md`. Run `preflight` before booking the browser time.
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
