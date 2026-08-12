# Session handoff — 2026-08-11 (evening)

**Rewritten each session.** The durable operating guide is `CLAUDE.md`.

## Current state
- Suite **2,122 passing**; the one failure is the documented machine-only
  `test_every_description_matches_the_source_text` (46 Godblooded entries — red on
  this machine, green on the laptop, not a regression).
- `main` and `deepseek-experiment` both at the Backgrounds work, pushed to `origin`.
- **The Backgrounds overhaul is DONE in data and engine, and is NOT browser-verified.**

## 👉 START HERE — the click-through is owed
Everything below shipped tests-green and untouched by a browser. The UI surfaces that
changed are exactly the kind 2,000 passing tests have never caught here:

- the per-row **dot rung** under each Background row (`ui/advantages.py`), which is
  keyed to the rating and must follow a dot-track click in BOTH regimes;
- the **catalogue dialog**, whose "Full description" now carries the whole ladder;
- the new **house-rules toggle row** ("Open every Background to every splat") with its
  live count;
- the chargen readout's **unspent-Arcanoi line** and the picker's `Arcanoi:` label.

**Run the `preflight` skill first, then `run-server`.** The dot rung is the one to
watch: it is refreshed by a callback the rating control has to invoke, and the play
regime's number input does not rebuild the panel.

## What changed this session (bug list from a friend's play-test)
1. **Ghosts had no unspent-Arcanoi warning.** Every other chargen pool warned about
   leftovers and the Charm pool warned about none. `ExaltDefinition.charm_noun` is new
   (data, like `caste_noun`), so a ghost reads "Arcanoi", not "Charms".
2. **Backgrounds leaked across splats.** Arsenal (Lookshy's armoury) was offered to all
   eleven splats; so were Retainers, Sorcery, Command, Henchmen, Reputation and Family.
   Every splat/origin row now carries `catalogue_backgrounds` — its own book's printed
   list — with `HouseRules.all_backgrounds_available` as the Storyteller's override.
3. **Sidereals were missing six Backgrounds** (Acquaintances, Celestial Manse,
   Connections, Salary, Savant, Sifu) and wrongly offered four their book bars.
4. **Every Background now carries its printed dot ladder** (49 of 51; the two without
   are deliberate — see Deliberate gaps).
5. **Artifact and Manse are reworked per splat** instead of one entry with a pile of
   per-splat parentheses and a Solar-only ladder.
6. **God-Blooded saw 13 of their 25** printed Backgrounds. Twelve are published in
   other splats' books and cross-referenced by PG p.50; their copies are tagged for the
   splat that PRINTED them, and `exalt_type` cannot say "Abyssal and God-Blooded".

## Next, and all of it works WITHOUT `images/`
⚠ `images/` and `sources/` are gitignored and do not travel. On a machine without them,
**anything needing a page is impossible** — pick from this list instead.

1. **The click-through above.** Highest value; blocks calling any of this done.
2. **Engine enforcement of Background numeric rules** — the last open item from the
   original ask. The thresholds are now visible in committed data (descriptions and
   ladders), so this needs no pages: Sidereal Connections capped at total Attributes
   (27 at chargen), Celestial Manse ≤3 without ST permission, Sidereal Resources
   ronin-only, mortals barred from Artifact/Manse without permission, Mountain Folk
   Backing ≤2 for the Unenlightened. Most map onto existing `BackgroundRule` fields;
   Connections needs a new "cap from a trait total" field. Read
   `engine/artifacts.py` first — it is the precedent, and the rule of the area is
   thresholds as DATA, nothing splat-specific in code.
3. **`close-out`** — no status doc exists for this work yet, and CLAUDE.md still says
   2,102 tests and lists the Background descriptions as "Next up / not started".
4. **Gear `resources_cost` vs the Resources Background** — still ⚠ **ask the human what
   the rule IS** before building (per-item or total, chargen-only or both sides).

## Blocked on pages — do these at home, not at work
- **Tiger Warriors ladder** wants a one-read sign-off: its rungs are interrupted by a
  page break and a tangent table, which displaced every dot marker one line early. The
  fragments rejoin cleanly so the reassembly is mechanical, but it is the human's call
  (the `garbled-transcription-defer` rule). Same standing as the Rathess p.86 items.
- **17 Lunar Charms** from the content gap. Newly reachable: `sources/Exalted - The
  Lunars.pdf` is a PURE SCAN (0 of 258 pages carry text, so neither
  `extract_born_digital` nor `solve_cid_bands` applies) but rasterises cleanly with
  `pdftoppm -r 110`. **PDF page = book page + 3.** This is the job that would justify
  the Ollama VLM leg (`qwen3-vl:8b-instruct` is pulled); ⚠ its dot counts are biased
  low, so for any ladder take the rating from the rung's POSITION, never from counting.

## Deliberate gaps — not TODOs
- **Family** has no ladder: E:DB p.159 prints a random table instead.
- **Alchemical Artifact** has no ladder: the book prints none.
- **Cult** is `universal: true` (human's ruling) — offered to every splat, and still
  bannable; the Great Geas keeps it off both Mountain Folk origins.

## Traps this session added, worth not re-learning
- **`catalogue_backgrounds` is NOT `allowed_backgrounds`.** The first decides what the
  dropdown OFFERS; the second is HARD validation that makes an unlisted Background an
  ERROR. Writing a list into the wrong one makes every free-text Background illegal for
  that splat — the suite caught exactly that when they were first written as one field.
  Where a row has both, offered must be a SUBSET of allowed (tested).
- **A list entry may be a NAME or an exact id, and an id bypasses the splat tag.** Use
  an id whenever a name is ambiguous — five names are printed twice (Connections,
  Celestial Manse, Salary, Savant, Sorcery) — or when a book grants another splat's
  Background. A bare name in a splat that has BOTH an untagged and its own tagged copy
  offers the row twice.
- **"Missing pages" is a claim to check, not assume.** Twice this session I called
  something page-blocked that was not: the Abyssal/Alchemical/Dragon-King Artifact
  reworks were all on disk, and the Lunars book was in `sources/` the whole time.
