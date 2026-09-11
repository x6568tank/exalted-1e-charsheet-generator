# The test suite — the count, and why it moves

**3,443 passing, 1 skipped, 2 xfailed** (2026-09-11, main PC, `main`, 10m56s, after the
VTT phase-P0/P1 work — 3,446 collected).

⚠ **`xfailed` is a state this suite has never had before. Both are deliberate.**
`tests/test_session_isolation.py` describes the target state of the hosting session
refactor, and it FAILS on today's code by design — see `docs/plans/vtt.md` P0. They carry
`xfail(strict=True)`, so:

- the suite stays green and the *"a red run is a real one"* invariant survives;
- **when the refactor lands, pytest reports XPASS and FAILS the run**, forcing whoever
  fixed it to delete the marker. A non-strict xfail would go quietly green and nothing
  would ever report that the work was done.

**Do not "fix" an xfail here by weakening its assertions.** They assert the target, not
the current behaviour.

⚠ **Of the +262 over 2026-09-03's 3,181, this session added only 52** — the other ~210 is
the 2026-09-04..09-10 work, which this file never recorded. **And 48 of those 52 are ONE
parametrised file:** `tests/test_engine_seam.py` runs once per engine-side source file
(47) plus a control. `tests/test_packaging.py` adds 3, `tests/test_session_isolation.py` 1
passing.

**A parametrised file moves this number by its cardinality, not by its coverage** — the
mirror of the note below about a data sweep moving it by zero. Three new test files read
as +52 here and are three ideas.

⚠ **The 3,391 the handoff carried was arithmetic, never observed.** This run confirms it:
3,391 + 52 = 3,443 passed, and 3,392 + 54 = 3,446 collected. Both columns land exactly, so
that inference is no longer outstanding.

**Historic:** 3,181 passing, 1 skipped (2026-09-03, after the 265-spell re-transcription —
includes the Qt-port tests in `tests/test_qt_*.py`, `tests/test_charm_actions.py`,
`tests/test_gear_actions.py` and `tests/test_variant_purchases.py`).

⚠ **The +32 over 2026-08-28's 3,083 is not the Charm work** — that changed data, not
tests. It is `tests/test_extract_columns.py`, the column-splitting guards added with the
born-digital extractor fixes in `bb5adae`. A data sweep that adds no tests moves this
number by zero, which is worth remembering before reading a jump as coverage.

Run with `.venv/bin/python -m pytest`. The suite takes 6–7 minutes; **if nothing
executable has changed since the last green run, reuse that number and say so.**

## Reading the number

- ⚠ **The Qt tests need the OPTIONAL `qt` extra, and SKIP without it** (522 of them,
  fourteen whole modules). `pytest.importorskip("PySide6")` guards each; before that guard
  a bare import was a COLLECTION ERROR, which takes the entire run down rather than
  those tests. **A count 522 lower on a webapp-only machine is that working**, not
  tests going missing — install with `.venv/bin/pip install -e '.[qt]'`.
- ⚠ **Quote the RUN's numbers, not `--collect-only`'s** — the two have disagreed by one
  here and the cause was not chased. The run is what tells you the suite is green.
- ⚠ **Read the "passed" count off a run that was GREEN.** `2674 passed` on a line that
  also says `1 failed` is not the suite's number, and it went into three docs on
  2026-08-21 before the fix put the real figure one higher. Check the failure count
  before you copy the pass count.
- ⚠ **The COUNT is machine-dependent, by dozens of tests** — the `images/`-presence
  deferral pattern showing up in COLLECTION rather than outcomes. **Do not treat a lower
  count as tests having been deleted**, and do not "reconcile" two machines' numbers.
  Record the number you measured, where and when.

## The one test that is not what it looks like

- ⚠ **The SKIP is conditional and healthy, not a disabled test:**
  `test_buy_merit_prices_the_tier_against_the_characters_own_menu` skips when no Merit
  tier exists that is generic-but-not-Solar.

### ✅ No test is machine-dependent in OUTCOME any more (2026-09-09)

`test_every_description_matches_the_source_text` used to be — it compared each M&F
description against its pasted chapter by normalised LENGTH, failing below 92%, and
**deferred** entries whose chapter was absent. So it passed on one machine and failed on
another off the same commit, and the older prose in this repo describing "the known
machine-dependent failure" means this test.

**Deleted 2026-09-09** (human: *"you can just get rid of it entirely at this point"*).
Two reasons, and the second is the sharper one:

1. It read `images/`, which is gitignored, so the suite's OUTCOME depended on which
   machine ran it — the thing this file spends most of its length teaching people to
   read around.
2. ⚠ **It went green by checking LESS.** On its final run it deferred **71** entries
   where it had deferred 46 and failed — the missing chapters route to nothing, so those
   entries were skipped rather than verified, and the only trace was a warnings summary.
   A test whose pass can mean "I stopped looking" is worse than no test.

**If that check is wanted again, it is a script, not a suite invariant** — one that diffs
authored content against the source and REPORTS the differences, which is both more useful
(it names what changed) and more broadly applicable (Charms and spells have the same
transcription risk, and neither ever had such a test). It is not written; nothing is
waiting on it.

⚠ **The suite no longer has a known failure.** A red run is now a real one.

## The trap that looks like a machine crash

⚠ **A Qt test that touches fonts without a QApplication ABORTS the interpreter**, and it
looks like a native crash on the machine, not a test failure. Laying a QTextDocument out
for the printer is enough. Such a test passes in a full run — some earlier module's
`qtbot` made the app — and takes the whole run down when its file is run alone.
`test_print_pdf_writes_a_real_file` did that for months; the fix is to take the `qapp`
fixture even when the test builds no widget.

⚠ **A QSS rule is invisible to the whole suite, so guard it by RENDERING.** See
`docs/plans/qt-port.md` for the full account: `tests/test_qt_theme.py`'s first version
compared whole-widget images with `!=` and passed against the very defect it was named
for. **Negative-control a rendering test by deleting the rule it guards.**
