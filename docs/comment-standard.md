# 📝 The comment standard (human, 2026-08-17) — applies to ALL new code

A docstring carries **input, output, and how it gets from one to the other. Nothing
else.** No decision-making logs, no chain of thought, no dated narration of how the code
reached its shape. *"Commit messages are fine to be wordy… we do want a log, but that
shouldn't bloat the code."* Put the reasoning, the alternatives and the
bugs-found-along-the-way in the commit message and `docs/status/`.

Three things STAY: **page citations** ("core p.104", or a short undated "human's ruling"
where no page exists); **⚠ records of behavioural traps** — *"those are important to
anyone working on this"*, and a trap buried in narration should come OUT as an explicit
⚠, not be deleted with it; and the contract itself.

## The pass, and what is left of it

`engine/validate/` had this pass on 2026-08-17. Three days later, `ea0df0e` and
`2833f682` (2026-08-20, "trimming down code comments" / "more comment cleanups") swept
**`ui/`**, **`models/`** and **`engine/` outside validate** too — this was not recorded
here at the time, which left this file claiming those three as untouched for two weeks.
**Re-measured 2026-09-03** (docstring-lines / total-lines, all `*.py` under each dir):
`ui/` 11%, `models/` 22%, `engine/` outside validate 26% — all down sharply from the
24%/61%/38% this file used to cite, and a spot-check of the longest remaining
docstrings (`models/adversary.py` at 49 lines, `engine/pools.py` at 35) found citations,
⚠ traps and contract, not narration — length there tracks genuinely complex data
shapes, not unpruned prose. Treat `ui/`, `models/` and `engine/` outside validate as
**done**, not a backlog.

**`qt/` had the pass on 2026-09-10** — all 18 files, ~3,400 prose lines. It was the last
gap; there is no comment-pass backlog now.

What the pass actually removed was **not bulk**: docstring density went 13% → 13% and total
prose 22% → 23% (the package grew 43 lines). It removed the three things the standard names
and left everything else alone:

* **Dated narration.** 52 `(human, 2026-08-21)`-style stamps became undated `(human's
  ruling)`, which is the form this file asks for. Bug archaeology went with them — `layout.py`
  carried "the *ghosty duplicate* the human reported against the Advantages spike (2026-08-21),
  and before that `_clear_lay` in milestone 1"; the trap it wrapped ("`item.widget()` is None
  for a `QLayout`") stayed.
* **Meta-commentary about the rules themselves** — "that instruction was already in
  `docs/plans/qt-port.md` and was not enough, which is why the shape is now a function",
  "an exception that is written down is not drift".
* **Non-STE prose** — em-dash chains, 40-word sentences, passive voice, "we"/"us".

⚠ **The ⚠ count went 363 → 561.** That is the pass working as intended, not inflation: the
standard says *a trap buried in narration should come OUT as an explicit ⚠*, and a third of
the traps in `qt/` were buried in exactly that way. Page citations were held at 62 distinct,
zero lost.

⚠ **`theme.py` cannot be checked by `prose_guard.py`.** Its trap comments live inside the
QSS f-string, so they are code to the AST and the guard reports CODE CHANGED. Verify that
file by stripping `/* … */` from both revisions and comparing the rendered rule text
instead. It is the only file in the package with comments inside a string literal.

Use `prose_guard.py`'s method: strip all docstrings, compare the AST (byte-identical ⇒ no
code changed), then assert no page citation and no ⚠ marker was lost.

⚠ The guard proves *nothing was broken*. It cannot tell you the prose got better — it
passes just as happily on a no-op. Read the diff.

⚠ **Judge such a pass by what the prose IS, never by line count** — validate's only went
35% → 34% and that was the correct outcome. A long docstring is not evidence of bloat by
itself; check content before trimming.
