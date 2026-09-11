---
name: close-out
description: Finish a work item — run the suite, write the docs/status record, rewrite the handoff, check CLAUDE.md's pointers, decide whether a memory is warranted. Use when a chunk of work is done, when asked to "write this up", update the status docs, or before committing a completed item.
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

Three things about the number:

- **It is observed, never computed.** Write it down from the run. If you also state
  the arithmetic (previous + new cases), say which one you observed.
- ⚠ **Do not reconcile it against another machine.** It moves by machine and by
  optional dependency, by dozens. See `docs/testing.md`.
- **The suite is ~10 minutes. Do not re-run it if nothing executable changed** since
  the last green run — doc edits do not change it. Reuse the number and say that you
  reused it.

⚠ Redirect the output to a **file**, not a pipe, and check liveness with
`pgrep -af pytest`. `pgrep -c pytest` matches the process *name*, which is `python`,
so it reports zero while the run is alive; piping through `tail` keeps the output at
zero bytes. That combination once put a wrong count into a handoff.

## 2. The status file — one, not two

Write the record in the **single** `docs/status/*.md` that owns the area (CLAUDE.md
§14 maps subject → file; §12 maps splat → file). Follow the shape those files already
use:

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

## 3. The handoff — rewritten, not appended to

`docs/status/handoff.md` is the first thing the next session reads. It describes the
**current** state, so it is **rewritten each session**, not added to. It is the one
file where last session's headline is expected to disappear.

It carries:

- The suite count from step 1, marked **observed**, and the arithmetic if you have it.
- ⚠ **The state of the working tree, checked with `git status` and `git log` at the
  time you write the line** — clean, or dirty and uncommitted. Say which. This line
  has been wrong in three consecutive handoffs; it is the single most load-bearing
  sentence in the file, because everything after it assumes a tree.
- What shipped, and a **pointer** to the `docs/status/` or `docs/plans/` file that
  holds the detail. Do not write the detail twice.
- 🐞 **What the work turned up** — the same rule as step 2. Carry a finding here only
  if the next session would act on it in the first ten minutes.
- **👉 NEXT**, in order of what would bite, with the carried ⚠ traps attached to the
  item they bite.
- **🖱 Not browser-verified** — what a human should click, and what was explicitly
  *not* touched, which is the cheap half of the check. Carry forward anything still
  owed from previous sessions; it does not expire because a session ended.
- **❓ Open for the human** — rules questions, and anything else blocked on them.

⚠ **Scope a claim to what you actually did.** "Removed a false affordance" and "fixed
hosted saving" read alike to a tired reader and one of them is a lie. If a row of a
plan is done but the thing the plan is *for* still does not work, say so in the same
paragraph.

## 4. CLAUDE.md — usually nothing

⚠ **CLAUDE.md has no status section, no test count, no date and no TODO list.** Its
own preamble — the four lines above §1 — forbids all four: *"Do not write status,
history, counts, dates, or session notes in this file. Write them in `docs/`. If a
statement in this file can become out of date, it is in the wrong file."* It is a
pure index of permanent rules and pointers.

So most close-outs change **nothing** here. Do not invent a section to update. It
gets an edit only when the work changed something permanent:

1. **A new `docs/` file** → add the row to the §14 documentation index, and to the
   §12 splat table if it is a splat's status file.
2. **A ratified decision** → add the row to the §9 table. The record itself goes in
   `docs/decisions/`, indexed in that README, with the rejected alternatives and the
   cost — not just the choice.
3. **A new permanent deferral or prohibition** → §10. A deferral with a date or a
   "for now" is not permanent; it belongs in `docs/status/`.
4. **A new trap that nothing enforces** → §13. ⚠ Only if nothing enforces it. A trap
   that now raises, or that a test catches, does not go here — a mechanism beats a
   warning, and §13 is for the ones that could not get a mechanism.
5. **A splat's colour or file** changing → §12.

Then check the file for drift in the other direction: any line carrying a count, a
date, a "currently", or a session note is in the wrong file — move it to
`docs/status/` and leave the pointer.

## 5. Memory — only if it survives the repo

Write a memory only for what the repo does not already record. Not code structure,
not what a status doc now says, not the fix you just made. Worth saving:

- A **workflow correction** from the human, with the why.
- A **ruling or constraint** that is not derivable from the data files.
- A **trap** that will re-bite in a different area than the one it bit in.

Check the existing memory files for one that already covers it and update that
rather than adding a near-duplicate; if a memory is now wrong, delete it. Then add
or fix the one-line pointer in `MEMORY.md` — the index in the memory directory, not
a file in this repository.

## 6. Report

Tell the human: the test count, what is written up where, **whether it is
browser-verified** (almost always: no, and it should say what to click), and any
open rules question waiting on them.

Say plainly what you did **not** do, and what a step turned out not to apply to.
A step that produced no edit is a result, not a silence.

Commit only if asked.

## Keeping this file true

⚠ **This file describes other files, so it rots when they change.** Step 3 and step 4
once described a `## Status` heading and a Done/Next TODO in CLAUDE.md. Both were
removed from CLAUDE.md when it became a pure index, and this skill went on naming
them — a stale instruction reads exactly like a live one, and the cost is a session
either editing CLAUDE.md against its own §1 or spending a pass discovering it cannot.

If a step here names a heading, a section or a file that you cannot find, **that is a
defect in this file, not a task to improvise around.** Say so, and fix it in the same
change that found it.
