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

`engine/validate/` has had this pass (2026-08-17). Not yet done, in size order as
measured THEN: **`ui/`** (3,676 prose lines, 24%), **`models/`** (2,672, 61% — densest in
the build), **`engine/` outside validate** (2,496, 38%) — plus **`qt/`**, which did not
exist at that measurement and has never had the pass.

⚠ Re-measure before acting on those numbers; `ui/` in particular has shrunk as the port
moved logic into `engine/` and `view.py`.

Use `prose_guard.py`'s method: strip all docstrings, compare the AST (byte-identical ⇒ no
code changed), then assert no page citation and no ⚠ marker was lost.

⚠ **Judge such a pass by what the prose IS, never by line count** — validate's only went
35% → 34% and that was the correct outcome.
