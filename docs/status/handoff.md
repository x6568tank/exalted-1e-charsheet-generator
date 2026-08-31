# Session handoff — 2026-08-28 (the dark surfaces, a parity sweep, then the roster cards)

# 👉 YOU ARE HERE

Last FULL green suite: **3,083 passed, 1 skipped** (main PC, `qt-port`, 6m55s), run after
the last code change. The tree is clean and nothing is half-finished.

Four things since the Party window: the **adversary roster came back as cards on the
Party tab** and a tracker click stopped scrolling the pane away (both from the human's
first look at the pushed UI — see below); the app is **packaged as a native binary**
(`dist/ExaltedBuilderQt`, commit 728365c — the spec, the traps and the silent-windowed-
crash defect it surfaced are all in that commit message and `pack/BUILD.md`); the **two
document surfaces went dark**, the last piece of theme drift in the port; and a
**shell-parity sweep** closed four holes and grew a new custom-library kind.

## The Party window is CLICKED — the roster half of it (2026-08-28)

**Human-clicked on the real display, commit 617c5d9, verdict "looks good; no issues
here."** What was driven, and is therefore verified:

- the **Party tab's adversary card grid** — four entries off the real catalogue, two
  pre-damaged;
- **tracker clicks on both card kinds** — the pane does not scroll away and the box keeps
  the focus. That was the reported bug and the two unreported siblings;
- **Edit / Duplicate / Reset** on a roster card, including "Edit" landing on the right
  entry on the Adversaries tab;
- the **Adversaries detail pane** scrolled down, then clicked;
- **resize and reflow** — columns, matched card widths, stat lines re-eliding.

⚠ **The window was driven with a pre-loaded demo party, so three checks from the old
list were NOT exercised** and are the remainder of this click-through. Do not read
"the Party window is clicked" as covering them:

1. **Click a health box on a member card, then spend XP on that character in the
   builder.** The card must redraw.
2. **"Builder" on a card, edit something, come back.** One builder, retargeted, same
   object — does that read right with two windows open?
3. **Close the builder.** The party window must go with it.

## 👉 NEXT

Nothing is blocked and nothing is half-finished. In rough order of what would bite:

- **Dispatch the release workflow by hand before tagging** (see below) — the four-asset
  matrix has never been run, and a tag is the wrong place to find that out.
- **The three interplay checks above**, next time the app is open.
- **Four surfaces still only rendered offscreen, never used:** the **Sheet tab** and the
  Party window's **Reference tab**, dark for the first time; the **Thaumaturgy → Rituals
  tab**, which grew an authoring row, an Add-version button and a "Known in:" line; and
  the **Custom tab's Rituals sub-tab** beside it.
- **The comment pass** on `ui/`, `models/` and `engine/` outside validate — still
  deferred, still the largest tidy-up owed. ⚠ Re-measure the line counts first; `ui/` has
  shrunk since they were taken.

⚠ **The binary is built from a working tree, and `dist/` is gitignored** — the one on
disk is from 2026-08-27 and does NOT have any of this session's work in it. Rebuild
before showing the app to anyone from the binary.

## The release workflow now ships the native app — 2026-08-28

⚠ **It did not, and a tag would have looked fine.** `.github/workflows/release.yml`
built one product per OS (`pack/exalted-builder.spec`), so `v1.1` would have published
two green assets, no failures, and **no native app on the page at all** — the Qt spec
had shipped in the packaging commit and nothing in CI referenced it. The matrix is now
2 OSes x 2 products, extras per row (`[desktop]` vs `[desktop,qt]` — PySide6 is ~650 MB
and the webapp build excludes it), one tag shipping all four (the human's call).
**A build that is not in the matrix does not exist to a tag.** `pack/BUILD.md`.

⚠ **NOT yet exercised.** No tag has been cut and no `workflow_dispatch` run has been
made since the change — the YAML parses and every spec, extra and binary path in it was
checked against the tree, which is not the same as a green runner. **Dispatch it by hand
before tagging**: that path uploads the artifacts and skips the release step, so a
broken row cannot leave a half-populated public release behind.

## What shipped this session — part two: the shell-parity sweep

Asked whether either shell was missing anything the other had, and answered
mechanically: every public `ui/view.py` name and every public `engine/` function, scored
by which shell references it. **Four real holes, three of them ours.** Method, findings
and the method's blind spot: `docs/plans/qt-port.md`'s last section.

⚠ **It took THREE passes on three different axes, and every axis found more.**
Names-by-shell found three; handler-functions-per-tab-pair found three more; and printed
page citations per tab pair — a probe aimed squarely at what the first two declared they
could not see — found the seventh. **The first six are in ONE panel** (the Thaumaturgy
picker, where the port compressed a four-column page into a tree, three lists and one
detail pane), which is a real finding about where a port loses controls; **the seventh is
the correction to it**, and sat on the Traits tab.

⚠ **A mortal at the human Essence ceiling was told nothing** — PG p.114's "mortals that
exceed Essence 3 become gods", printed beside the webapp's track since Mortals shipped
and absent from Qt's, where the dots just stopped at 3. Display only; the cap was always
enforced. ⚠ Its negative control named a SOLAR first and passed against the defect — a
Solar has no `essence_cap_override` at all, so deleting the splat check changed nothing.
The real subject is **God-Blooded** (printed cap 1, so Essence Mastery raises it to 3
exactly as for a mortal). `docs/status/mortals.md`.

⚠ **Open, and NOT ours to invent: a God-Blooded stopped at that same raised cap gets no
explanation in either shell.** No printed clause covers it and writing one would be
authoring from memory. The human's call, not a gap to close.

**Six Qt Thaumaturgy holes, all fixed** (`docs/status/thaumaturgy.md`): owned regional
orientations were never shown; a SECOND regional version was unbuyable, because the combo
vanished once a row was owned and `add_thaum_orientation` had no Qt caller; and no custom
ritual could be written at all; an aspect could not be bought NARROWED (p.127, Summoning
alone, half price and recorded on the sheet); a specialty of your own could not be written
(p.126 invites them in as many words); and a Science could not be stepped back DOWN, so a
chargen mis-click was unfixable without editing the save. Fixing them turned up three more
that no list had —
`_refresh_thaum_selection` left the detail panel stale (always wrong, invisible until a
line in it moved on a purchase); the Qt combo defaulted to **North** where the webapp has
always defaulted to **Realm**; and — in the WEBAPP — ticking "narrow" halved what was
charged while the button went on printing the full price. `ThaumSpecialtyRow.narrowed_price`
is the second number, computed in `view.py` from `engine.costs` and read by both shells.

**Rituals became a custom-library kind, on both shells** — the human's call when the
webapp-only hole came up: `custom/rituals.json`, authored on the Custom tab's new Rituals
sub-tab, merged into `ruleset.thaum_rituals`, bought by id like a printed ritual.
⚠ **Both entry points stay**, so a ritual now has two custom shapes that are not
interchangeable — a library row, and an inline `RitualEntry` for one character. The table
that tells them apart is in `docs/status/custom-content.md`; read it before touching
either.

Three things that fell out, each a lesson the project already had:

* ⚠ **`ui/custom.py::_switch_kind` repainted the form and not the LIBRARY** — the Spells
  tab listed Charms, under a heading that said "YOUR SPELLS". Every test until now
  authored and read within one kind.
* ⚠ **`reload_custom_layer` needed the ritual purge**, exactly as it had needed the gear
  one. The test was written first and caught it the same hour.
* ⚠ **A library ritual TRAVELS** (`custom_definitions["rituals"]`), because it is
  referenced by id. Gear does not, because a save carries an inline copy — decision 0007
  is the whole difference.

**The webapp's Custom page gained the gear half** it never had, which was the one thing
Qt had and it did not.

## What shipped this session — part one

**The document surfaces are dark on screen and paper in print.** The Sheet tab and the
Party window's Reference tab were the only light surfaces left, and tabbing into a white
page from the dark shell is a flashbang; the Reference tab had the treatment only because
it copied the Sheet tab's one-line stylesheet. `qt/sheet.py::SheetColors` is now a frozen
colour set with two constructors — `print_colors` (unchanged greys) and `screen_colors`
(the dark base, accent lightened as every widget's is) — and every HTML helper takes the
set rather than a bare accent. **One document, two palettes**, which is what keeps the
print path honest: `sheet_html(view)` still defaults to paper.

Three traps, all written up in `docs/plans/qt-port.md`'s last section:

* ⚠ **`ink` and `paper` are the two colours the HTML does not carry** — a QTextBrowser
  takes its page shade from the WIDGET stylesheet, and the shell QSS hands every
  QTextBrowser the card shade. The ancestor-stylesheet trap in its fourth disguise.
* ⚠ **A document's colours are baked into its HTML**, so `qtheme.apply` does not reach
  them; `ReferencePage.apply_colors` re-renders and `PartyWindow.apply_chrome` calls it.
* ⚠ **`test_print_pdf_writes_a_real_file` had been ABORTING the interpreter** whenever
  its file was run alone — laying a document out for the printer hits QFontDatabase with
  no QApplication, which is a C-level abort, not a failure. It looked exactly like a Qt
  font regression on the machine. It takes `qapp` now.

The guard is a RENDER, next to the other invisible-QSS tests:
`test_no_document_surface_is_a_white_page_on_the_dark_app` measures each page's mean
brightness and fails above 120/255. **Negative-controlled on both halves** — restoring
either surface's `#fffdf7` fails it.

## The roster is drawn TWICE now, and a tracker click repaints — 2026-08-28

Two reports off the pushed Qt UI, and the second turned out to be three defects.

**1. "Let me see the added adversaries in the GM screen, like the webapp has —
otherwise gming combat is a challenge."** The Party tab now carries a **grid of
adversary tracker cards under the member cards**, which is where the webapp put them
(`ui/gm.py` renders the roster on the party page). ⚠ **The port had compressed a card
grid into a table plus ONE detail pane**, so a Storyteller could see exactly one
bandit's health at a time — the "a port that compresses a surface's shape is where its
missing controls are" rule, and every adversary test was green throughout because they
all addressed the tab that DID exist. The Adversaries tab keeps its collection layout
and stays the only place an entry is EDITED; a roster card's "Edit" raises that tab with
the entry selected rather than growing a second editor. `AdversaryTrackers` in
`qt/adversaries.py` is the one tracker both surfaces draw.

**2. "Clicking health or wp boxes scrolls the adversary's information to the bottom."**
The detail pane rebuilt itself on every mark, which **deletes the button under the
cursor**; Qt hands the focus to whatever inherits it and the enclosing `QScrollArea`
scrolls to follow. Trackers now **repaint in place** (`trackers.restyle`).

⚠ **Two more instances of the same bug, neither reported.** The probe that reproduced it
found the **member cards on the Party tab** doing it too — a health click there threw the
scroll 354 → 463 and left the focus in the toolbar's party-name field — and then the
roster card's own new "Reset" button did it a third time. All three repaint now.
`qt/play.py` was measured and holds its scroll; it loses focus only, and is left alone.
**A defect one widget over is still your defect.**

⚠ **Two LAYOUT defects that no test could see, found only by rendering offscreen and
looking.** A word-wrapped `QLabel` answers `heightForWidth` and **`QGridLayout` does not
honour it**, so the card was handed a height computed from one-line labels, overflowed,
and painted the health boxes THROUGH the Willpower heading below them. The fix is two
parts: no word-wrap in a card a grid lays out (long prose is elided with the full text on
hover), and a hard `setMinimumHeight` on the trackers — a size policy alone was not
enough. Separately, a grid only creates the columns it has items in, so a lone member
card drew full width over half-width adversary cards; `_even_columns` fixes that.

**Both scroll fixes are negative-controlled** — put `_sync_detail()`/`reload()` back into
the handler and the tests fail. ⚠ **Do not "verify" this with `QPushButton.click()`**: a
programmatic click takes no focus, so the bug does not reproduce and the test passes
against it. The tests call `setFocus(MouseFocusReason)` on a `show()`n, activated widget
first.

⚠ **A THIRD defect surfaced when the app was launched with real catalogue data**, after
the tests were green and the offscreen renders looked right: the long ability and prose
lines were **clipped mid-word with no ellipsis**. The first fix elided by character
count, and no single count is right for both a one-column and a three-column layout.
`_StatLine` now elides with `QFontMetrics` against its own width and takes
`QSizePolicy.Ignored` horizontally, so an "All Solar Charms the Storyteller cares to give
him" line cannot set the card's minimum width. **Synthetic fixtures agreed with the bug**
— a two-word adversary name never reached the card edge.

**Clicked and closed** — see the top of this file for what was verified and the three
interplay checks that were not.

## Not clicked, not blocking

Group 4's five per-splat **Charm surfaces** and the POST-lock half of the variant chooser;
each was rendered offscreen and each has test coverage. ⚠ `ui/picker.py::variant_menu_detail`
— the WEBAPP's variant panel — has still never been rendered at all.

## A webapp bug found and deliberately NOT fixed

⚠ **`ui/gm.py`'s card ignores `PlayView.single_pool`**, so a merged-pool character's card
draws a Personal box at a permanent 0/0 (p.41). The Qt card honours it. Still its own
one-line change in a surface nobody asked to touch.

## No open rules questions

Nothing here introduced a rules interpretation. The three printed rules the new
controls encode — Occult ≥ the ritual's level (p.148), a flat point per extra regional
version (p.124), and "the chapter prints five and expects more" (p.148) — were all
already in the engine and are carried, not invented.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.

## Rebased in from the other machine — the 2026-08-15 scans

The laptop's `4519309` was rebased onto this branch after 76 commits of divergence. It
carries three things that are NOT part of the Qt work and were never on this branch:

- **The `source.book` normalisation** — 146 charm files rewritten in place onto the bare
  book form (`Caste Book: Zenith`, not `Exalted 1e Caste Book: Zenith`). Guards live in
  `tests/test_data.py`; `docs/source-attribution.md` is the record. **A new book must be
  added to `CANONICAL_BOOKS` and to that doc's table together.**
- **The phase-1 and phase-2 scans** (`docs/status/phase-1-scan.md`, `phase-2-scan.md`) —
  the last seven unopened books in `sources/`. **Every book has now been opened.** 37 gear
  rows, 5 weapons, and the six Marukani horse breeds.
- **Six Marukani beast templates** in `adversaries.json`. ⚠ They were authored against
  the OLD singular `category` field and were migrated to `categories: ["Beast"]` during
  the rebase — the roster's multi-category change (a79303e) landed on this branch while
  they were being written.

⚠ **One known content gap came with them: Backgrounds in the scan-only splat books.**
See CLAUDE.md's *State of the world*. It is a reading job, not a blocked one.
