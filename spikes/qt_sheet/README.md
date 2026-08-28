# Qt sheet-view spike

Answers `docs/plans/qt-port.md`'s remaining open question — **does the sheet view
become a `QTextDocument`?** — before the full port is committed. It renders a real
`ui.view.build_sheet_view` into a `QTextDocument`, shows it on screen, and prints it
via `QDoc.print_(QPdfWriter)`, reusing the same framework-free data layer
`ui/pdf.py` feeds to reportlab. Nothing in `exalted_builder/` imports Qt.

## Run the window (real display)

```sh
.venv/bin/python spikes/qt_sheet/sheet_spike.py
```

A dropdown picks among the four example characters in `examples/` (Solar, Solar,
Sidereal, Alchemical — each carries its own splat accent colour, as a port would).
The sheet renders as a scrollable `QTextDocument` in pdf.py's section order: header,
Attributes, Abilities, Advantages, Traits (Willpower/Virtues/Essence/Soak/Health/
Equipment), then Charms & Spells. Trait and advantage ratings are 5-dot tracks in the
splat accent; the health track is boxed, grouped by level with the label left; the
trait band is 3-up and Advantages 2-up — sized for the A4 page, not the 900px window.
**Print PDF…** writes the same document, paginated, via `QPdfWriter` — the on-screen
view and the PDF are one source, with no page numbers (the page size is reset before
printing, since the on-screen `QTextBrowser` rewrites the document's page size).

## Run the tests (headless)

```sh
.venv/bin/python -m pytest spikes/qt_sheet -q
```

`conftest.py` pins `QT_QPA_PLATFORM=offscreen`. **14 tests**: every example character
renders HTML with the key sections (a field-name mistake surfaces across all four
splats, not just the first), the plain-text document carries the sheet content, the
print path writes a real non-empty PDF, the window offers the examples and switches
between them, trait dots and advantage columns render, the health track groups by
level (and strips the ★ Charm marker), the Willpower squares track renders, and
Equipment sits in the trait band rather than under Charms.

## What it reuses vs. what it adds

| Reused (framework-free, as a port would) | Spike-only |
|---|---|
| `rules_db.load_ruleset` / `persistence.load_character` | `sheet_html` (pdf.py's section order, splat accent) |
| `ui.view.build_sheet_view` / `weapon_stat_line` / `armor_stat_line` | `build_document` (QTextDocument, paginated) |
| `ui.theme.palette` (per-splat colours) | `print_pdf` (QPdfWriter) + `SheetWindow` |

## Footprint

- `PySide6` / `pytest-qt` already live in `.venv` from the tree spike — not added to
  `pyproject.toml`; they join their proper extras when the port is committed.
- `spikes/` sits outside `testpaths = ["tests"]`, so the main suite never sees it.
