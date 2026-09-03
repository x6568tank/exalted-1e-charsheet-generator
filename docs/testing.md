# The test suite — the count, and why it moves

**3,181 passing, 1 skipped** (2026-09-03, main PC, `main`, after the 265-spell
re-transcription — includes the Qt-port tests in `tests/test_qt_*.py`,
`tests/test_charm_actions.py`, `tests/test_gear_actions.py` and
`tests/test_variant_purchases.py`).

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

## The two tests that are not what they look like

- ⚠ **The SKIP is conditional and healthy, not a disabled test:**
  `test_buy_merit_prices_the_tier_against_the_characters_own_menu` skips when no Merit
  tier exists that is generic-but-not-Solar.
- ⚠ **One test is machine-dependent in OUTCOME, and that is the point:**
  `test_every_description_matches_the_source_text` **defers** entries whose source
  chapter is absent, and fails them where the chapter is present. **Neither outcome is a
  regression**, and do not "fix" it by editing a path. `docs/status/godblooded.md`.

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
