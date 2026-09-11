# Lessons — the house bug, and what generalises past its own area

Extracted from `CLAUDE.md` (2026-09-01) to keep that file an index. **Nothing here is
history for its own sake** — every entry is a rule that has already been violated at
least once, usually more. `CLAUDE.md` keeps the one-line headlines; this file keeps the
evidence behind them.

## The house bug — stated once
A rule that IS implemented, sitting where it does not run when it matters. It has
appeared in three species; all three keep recurring.

1. **Wired to the wrong phase.** Three M&F instances, then mortal magic access wired to
   chargen only, then the XP tab's hardcoded trait ceiling. `preflight`'s read-site audit
   reports single-site fields as healthy — **a single read site is as suspect as none
   when the read sits in the phase that wrote it. Test the buy path, not the effect.**
2. **Zero read sites, and still looks healthy**, because something else does its job by
   accident (`heritage_traits.magic_track`; the Ghost catalogue holds no sorcery, so
   Charm access happened to produce the right answer while both Half-Castes were broken).
   **Correct behaviour in the case you tested is not evidence the mechanism exists.**
3. **The switch is player-editable to a value that switches it off.** A custom M&F row
   keyed on `custom_name` being truthy — and the name input writes that field on every
   keystroke. **A discriminator must be a field nothing on the screen can edit.** When
   you add a "kind" flag, ask which widget can write it.

The mechanical sweep for all three is `docs/delegated-authoring.md` — **read it before
delegating a splat to a cheap model, and run its four checks before booking browser
time.** (Godblooded was authored end to end by DeepSeek V4 Flash; the review found four
defects, every one of them the house bug.)

## Lessons that generalise past their own area
Each is written up in full where it happened; these are the reusable one-liners.

### Sweeps, gap lists and authoring
- **"Missing from the build" is not "should be authored."** A gap diff cannot see a human
  ruling — grep `docs/status/` and `tests/` for an entry name first.
- **A search shaped like what you expect proves nothing about a thing shaped
  differently.** Before trusting a sweep, ask which shapes it **cannot see** (rituals
  print no stat block; one has no heading at all).
- **A fuzzy gap count is a LOWER bound on the work.** When a name match fails, match on
  **book + page** — but keep the name check too; entries printed in two books slip a
  page-keyed check.
- **A gap-list entry can name the wrong MODULE, not just the wrong size.** Downtime sat
  under "Edit's deferred panels" for two sessions and is a shell control. Check where
  the webapp puts a thing before porting it to where the list says it is.
- **A "free" ruling that contradicts the book's price language needs the human's intent
  confirmed** — a mistaken "free" ships as a silent under-charge.
- **When a tool closes a blocker, the prose describing the blocker is part of the change.**
  A stale "page-blocked" line reads exactly like a live one.
- **A census has a shelf life, and nothing re-runs it.** The "~1,800 pages of Backgrounds"
  item rode the NEXT list for four weeks: `phase-2-scan.md` (2026-08-15) carried forward a
  census taken before the Background overhaul (2026-08-12) had already read three of its
  five splat groups. **The work that closes a gap does not go back and edit the documents
  that estimated it** — so a later doc citing an earlier number is not corroboration, it is
  the same number twice. ⚠ Worse, the overhaul's coverage was never written down AS
  coverage, and a raw count of non-empty rows understated it by half because sub-origin
  rows INHERIT. **Re-measure against the data before you plan from a gap estimate**, and
  when you close part of a gap, say which part in the estimate's own file.
  ⚠ **Third instance, 2026-09-11, and this one was a day old.** The VTT plan's "carve the
  engine into its own package" phase was written from `hosting-per-instance.md`'s
  comparison table — and `pyproject.toml` already declared `pydantic` as the only hard
  dependency, so the engine was already installable with no toolkit. A clean-venv install
  proved it in two minutes; executing the phase would have touched **491 import sites** to
  buy something already true. **A plan you wrote yourself last session is a census too.**
  ⚠ And the measurement was not wasted: building the wheel to check is what found the
  thaumaturgy packaging defect. **Re-measuring a stale item is how you find the live one.**

### Code and engine
- **A permission toggle must move the OFFER as well as the bar.** A granted-but-unfindable
  Background is worse than no toggle.
- **A predicate that answers "True, not applicable" outside its subject is a grant waiting
  to happen.**
- **When you teach one formatter a new fact, grep for its siblings.** Per-module display
  helpers touch no engine code, so containment tests never see them.
- **When a structural invariant is relaxed, name where it moved TO in the same change.**
- **An exemption keyed on a basename is an exemption anything can claim** — key on path.
- **Check sign conventions against `data/`** before consuming a field (`Armor.mobility_penalty`
  is stored NEGATIVE; a consumer reading it as a magnitude adds dice).
- **When code copies one model into another field by field, derive the field set from the
  models.** A hand-written copy list documents the fields someone thought of: `ui/gear.py`
  carried `from_artifact` across a catalogue re-pick because a comment warned about it,
  and silently dropped `acquired` — re-charging the Artifact budget for a cash-bought
  item. `gear_actions._owned_fields` is the complement of `_catalogue_stats`, so neither
  half can be forgotten.
- **A guard in a DISPATCHER can shadow a more careful guard one layer down, turning
  implemented support into dead code.** `charm_actions.learn_charm` refused any owned
  Charm post-lock with a bare `in character.charms`; `advancement.learn_charm` beneath
  it had supported the repeatable case all along, cap check and page citation included.
  Both shells go through the dispatcher, so nothing could reach it. **When you write a
  broad refusal, check what the layer below already handles more precisely.**

### Tests
- **Negative controls go stale silently and keep passing.** After authoring content that
  used to be missing, grep the tests for the names you just added; when no real subject
  remains, rebuild the control on a synthetic fixture — never delete it. **Moving a
  feature stales them too** — once Combos left the rail, "a ghost's rail has no Combos"
  passed for every splat and proved nothing.
- **A test's SUBJECT can quietly become the wrong subject.** The Qt "Add another" tests
  used a Charm that later turned out to be a variant menu, not a generic repeatable.
  They were green throughout and proved nothing about the case they named. When a
  thing's classification changes, grep the tests that named it.
- **Address a widget by name, never by position in a `findChildren` list.** A test that
  grabbed `findChildren(QSpinBox)[0]` got the row's quantity box instead of the stat it
  meant, and passed a wrong assertion into existence.
- **Tests, then a render, then a LAUNCH — each catches what the last could not.** The
  adversary roster card passed 3,083 tests, then two rounds of offscreen renders, and
  still shipped clipped mid-word text the moment it was opened with the real catalogue.
  **A render shows you geometry; only real data shows you what the geometry has to
  hold** — and ⚠ **self-authored fixtures agree with the bug**, because every test
  adversary is called "Bandit" and no line in the suite is long enough to reach a card
  edge. When a surface's job is to display real content, render it with real content.

- **When a test NAVIGATES, assert on a value the origin page cannot produce.** The first
  version of the `/gm` → `/` session-isolation test clicked "Builder" and asserted
  `should_see(MEMBER_NAME)` — but the GM card *prints the member's name*, so the assertion
  matched whether or not the navigation ever happened. A test of the leakiest phase in the
  hosting plan was green while proving nothing. It had two independent causes and both
  recur: `find("Builder")` matched **two** buttons (and `find(...).elements` is an
  unordered set), and the assertion was satisfiable by the page it started from. The fix
  is a marker for the click, an assertion on something only the *destination* renders, and
  a **mid-test** check that the navigation actually happened so the final assertion cannot
  pass vacuously.
- **A deliberate optional and a lost file are the same bytes.** `data/thaumaturgy/` was
  never added to `package-data`, so an installed wheel had none of it — and nothing
  reported that, because `rules_db` treats every thaumaturgy file as *optional* so that a
  data set without thaumaturgy still loads. The correct decision one layer over is what
  made the omission invisible. **This is attunement-by-absence in the build**, and the
  discriminator is the same: do not assert the value, assert it against something that
  proves the absence was chosen. Here that is expanding the declared globs and comparing
  them to what is on disk, so the test fails for the *next* directory too.
- **`xfail(strict=True)`, never plain `xfail`, for a test that describes a target.** A
  non-strict xfail goes quietly green the day the defect is fixed and nothing ever reports
  that the work was done. Strict turns that day into a failing run that forces someone to
  delete the marker. ⚠ And a failing test that is *expected* to fail must never be left
  bare in a suite whose invariant is "a red run is a real one".

### The two shells, and porting between them
- **A page added to a shell inherits a HOOK CONTRACT from its sibling pages** — diff the
  constructor calls, not the page. `CharmsPage` was built without the `on_change` every
  other Qt page passes, so spending on it never moved the shell's readout bar; the tab's
  own local readout updated fine, which is what hid it.
- **A cross-shell parity audit needs THREE axes, and each one's conclusion is a lower
  bound on the next.** Names by shell, handler functions per tab pair, and printed page
  citations per tab pair — the third exists to catch what the first two declare they
  cannot see (a panel that renders FEWER LINES), and it found the only gap outside the
  panel the other two had agreed was the whole story.
- **A cross-shell parity audit needs TWO axes, and the answer's SHAPE is the finding.**
  Scoring every `view.py`/`engine/` name by which shell uses it found three holes;
  comparing handler functions per tab pair found three more, and all six were in ONE
  panel — the one where the port collapsed a four-column page into a tree plus a shared
  detail pane. **When a port compresses a surface's shape, that surface is where its
  missing controls are.** Both axes are blind to a control that exists in both shells
  but is disabled in one, to a panel with fewer lines, and to a different default —
  three more defects turned up in the same code, found only by fixing the others and
  looking at the render.
- **A compensation you reasoned your way to is a HYPOTHESIS until someone uses it.** The
  Qt roster replaced the webapp's card grid with a table and argued in three documents
  that the Damage column bought back what cards did better. It did not — six damage cells
  are not six health tracks you click, and *"gming combat is a challenge"* was the
  verdict. **Write the compensation down as a claim to be tested, not as a closed
  trade**, and note that no test can fail on it: all 3,065 were green, because they all
  addressed the surface that DID exist.

### Qt widgets
See also the standing port rules in `docs/plans/qt-port.md`.

- **A GUI toolkit can silently degrade a value you hand it and hand back.** Qt stores
  combo item data as a QVariant, and a `str`-valued Enum returns from `currentData()` as
  a plain `str`; with no `validate_assignment` on the model, writing it succeeds and
  fails later somewhere else. **Never read a key back out of a widget — index the dict
  you built the widget from.**
- **A click that rebuilds its own button throws the focus and drags the scroll with it.**
  Qt hands focus to whatever inherits it, and an enclosing `QScrollArea` scrolls to
  follow. **A live tracker REPAINTS** (`qt/trackers.py::restyle`); only a change that
  re-lengthens a track may rebuild. ⚠ **Do not verify this with `QPushButton.click()`** —
  a programmatic click takes no focus, so the bug does not reproduce and the test passes
  against it. `show()`, `waitExposed`, `setFocus(MouseFocusReason)`, *then* click.
- **A word-wrapped `QLabel` answers `heightForWidth` and `QGridLayout` does not honour
  it**, so a card in a grid is laid out too short, and the only children that cannot
  shrink gracefully — fixed-size boxes — get painted through whatever is under them. No
  word-wrap on a card a grid lays out, and a hard `setMinimumHeight` on the fixed part;
  a `QSizePolicy.Fixed` alone does not save you. Invisible to every test.
- **A RULED absence and an unread page are byte-identical in the data**, because both are
  an omitted field falling back to a model default. Nothing on the row records that a human
  looked and found nothing — which is precisely how a later session "fills the gap" from
  its own 2e knowledge. ⚠ **A bare `== 0` does not fix this: it restates the current value
  and discriminates nothing.** Pin the absence against a DISCRIMINATOR that would differ if
  the source had simply not been read — a same-spread neighbour that does print the value
  (`test_the_ruled_zero_attunement_rows`). Where no discriminator exists, say so in the
  docstring rather than implying one. Applies to any defaulted field, `source.book`
  included.
- **A handoff describes a moment, and the session keeps moving after it is written.** The
  2026-09-09 handoff's most alarming line — "Working tree is DIRTY and nothing is
  committed" — was the one false thing in it; the commit landed afterwards. **Check
  `git status` and `git log` against the handoff's claims before acting on them**, and
  never re-report a handoff's tree state as current fact.
- **A test can go green by checking LESS.** The M&F description test passed on 2026-09-09
  by deferring 71 entries where it had deferred 46 and failed — the missing chapters route
  to nothing, so the entries were skipped, not verified. The deferral count lived only in
  the warnings summary. **When a known failure turns green, find out whether it was fixed
  or merely stopped looking.** ⚠ That test was **deleted the same day** (human) and the
  lesson is why: a check whose source is gitignored makes the suite's OUTCOME
  machine-dependent, and its pass could mean "I stopped looking." **Content fidelity
  against an out-of-tree source is a SCRIPT that reports differences, not a suite
  invariant.** Its structural siblings survive — they assert shape, need no source, and
  caught what it could not.
