---
name: close-out
description: Finish a work item — run the suite, write the docs/status record, sync CLAUDE.md's test count and TODO, decide whether a memory is warranted. Use when a chunk of work is done, when asked to "write this up", update the status docs, or before committing a completed item.
---

# Closing out a work item

Every work item in this project ends the same way, and the ending is where the
documentation drifts. Do these in order. The point is that CLAUDE.md stays short and
true while the real record goes in `docs/status/`.

## 1. The suite

```
.venv/bin/python -m pytest -q
```

Record the **exact** number. Not "tests pass" — the count, because it is the anchor
the status docs use to say when a bug was invisible to how many tests. If anything
fails, stop and say so with the output; do not write up work as done.

## 2. The status file — one, not two

Write the record in the **single** `docs/status/*.md` that owns the area (the table
in CLAUDE.md maps area → file). Follow the shape those files already use:

- What shipped, in mechanics not prose.
- The test count at that moment, and **"Not browser-verified"** if it is not — say
  it plainly, every time. That phrase is load-bearing; it is how the next session
  knows what still needs the human's eyes.
- **What the work turned up on the way** — the neighbouring bug, the rule that was
  mis-placed, the thing that was priced but not enforced. These are the most
  re-read lines in the whole `docs/status/` tree. Write them even when they are
  embarrassing, especially then.
- Open rules questions, marked as questions for the human. Never a chosen
  interpretation.

**Do not restate architecture, conventions or decisions.** `docs/ARCHITECTURE.md`,
`docs/content.md` and `docs/decisions/` are each the single copy. Two copies drift
and the next session believes the wrong one.

If the work closed a decision, add a numbered record in `docs/decisions/` and index
it in that README — the alternatives rejected and what the choice costs, not just
the choice.

## 3. CLAUDE.md — the four edits, and no more

CLAUDE.md is a pointer file. It gets exactly these:

1. **The test count in the `## Status` heading.** It drifts constantly; check it
   against step 1 every time even if this work did not change it.
2. **The TODO.** Move the finished item out of **Next** and into **Done**, in one
   place. An item that appears in both is the current failure mode — check for it.
3. **Any new status file** added to the area table.
4. **A status-line change** if a splat or subsystem changed state (the
   one-paragraph state of the world, the splat tables).

Then prune. Specifically look for:

- **Time-relative headings** — `Next (2026-07-30, after lunch)` and the like. They
  were true for one afternoon. Fold the content into the plain TODO or delete it.
- **Items in both Done and Next.**
- **Anything that grew into a full explanation** — if a TODO entry has become three
  paragraphs of mechanics, that is a `docs/status/` file trying to happen. Move it
  and leave a pointer.
- **Superseded claims** — a "NOT STARTED" or "blocked on X" that is no longer true.

## 4. Memory — only if it survives the repo

Write a memory only for what the repo does not already record. Not code structure,
not what a status doc now says, not the fix you just made. Worth saving:

- A **workflow correction** from the human, with the why.
- A **ruling or constraint** that is not derivable from the data files.
- A **trap** that will re-bite in a different area than the one it bit in.

Check the existing memory files for one that already covers it and update that
rather than adding a near-duplicate; if a memory is now wrong, delete it. Then add
or fix the one-line pointer in `MEMORY.md`.

## 5. Report

Tell the human: the test count, what is written up where, **whether it is
browser-verified** (almost always: no, and it should say what to click), and any
open rules question waiting on them.

Commit only if asked.
