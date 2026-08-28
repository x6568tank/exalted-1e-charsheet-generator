# Session handoff — 2026-08-28 (the native binary, and the last light surfaces went dark)

# 👉 YOU ARE HERE

Last FULL green suite: **3,034 passed, 1 skipped** (main PC, `qt-port`, 7m38s), run after
the last code change. The tree is clean and nothing is half-finished.

Two things since the Party window: the app is **packaged as a native binary**
(`dist/ExaltedBuilderQt`, commit 728365c — the spec, the traps and the silent-windowed-
crash defect it surfaced are all in that commit message and `pack/BUILD.md`), and the
**two document surfaces went dark**, which was the last piece of theme drift in the port.

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

Add one glance now that the theme changed: **the Sheet tab and the Reference tab** are
dark for the first time. They were rendered offscreen and looked at, not used.

⚠ **The binary is built from a working tree, and `dist/` is gitignored** — the one on
disk is from 2026-08-27 and does NOT have the dark sheet in it. Rebuild before showing
the app to anyone from the binary.

## What shipped this session

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

Nothing this session touched a rules interpretation.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
