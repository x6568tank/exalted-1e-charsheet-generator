# Session handoff — 2026-08-28 (the dark document surfaces, then a shell-parity sweep)

# 👉 YOU ARE HERE

Last FULL green suite: **3,065 passed, 1 skipped** (main PC, `qt-port`, 7m26s), run after
the last code change. The tree is clean and nothing is half-finished.

Three things since the Party window: the app is **packaged as a native binary**
(`dist/ExaltedBuilderQt`, commit 728365c — the spec, the traps and the silent-windowed-
crash defect it surfaced are all in that commit message and `pack/BUILD.md`); the **two
document surfaces went dark**, the last piece of theme drift in the port; and a
**shell-parity sweep** closed four holes and grew a new custom-library kind.

## 👉 NEXT: still the Party window click-through

**It remains the only owed work**, unchanged from the last handoff except that its first
finding is fixed. Scope it to what only a real display can answer:

1. **Open the Party window from the builder toolbar, add the open character, click a
   health box, then go back and spend XP in the builder.** The card must redraw.
2. **"Builder" on a card, edit something, come back.** One builder, retargeted, same
   object. Does that read right in use, with two windows open?
3. **The Adversaries tab as a COLLECTION rather than cards** — add a template, duplicate
   it twice, damage one. Does the Damage column carry what the card stack used to?
4. **Close the builder.** The party window must go with it.

Add two glances now, both rendered offscreen and looked at but not used: **the Sheet tab
and the Reference tab**, dark for the first time; and **the Thaumaturgy → Rituals tab**,
which grew an authoring row, an Add-version button and a "Known in:" line — plus the
**Custom tab's Rituals sub-tab** beside it.

⚠ **The binary is built from a working tree, and `dist/` is gitignored** — the one on
disk is from 2026-08-27 and does NOT have the dark sheet in it. Rebuild before showing
the app to anyone from the binary.

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
