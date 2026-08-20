# 0018 — The Qt port is committed: a PySide6 native app alongside the NiceGUI webapp

**Status:** Accepted, 2026-08-20. The human committed to the port after the two spikes
(`spikes/qt_tree/`, `spikes/qt_sheet/`) answered its open questions. This is the
decision the plan's sequencing promised; `docs/plans/qt-port.md` becomes the build
record.

## Problem

The webapp is shipped (1.0.0, 2026-08-17) and packages to a standalone executable via
`pack/`, but that executable is a **packaged browser** — native window chrome around the
same DOM. The human wants a genuinely native, non-Electron desktop app offered
*alongside* the webapp (2026-08-20): "a reasonably sized native app." That is a product
decision, not an aesthetics preference — and it settles the plan's old counterweight
("a real app is therefore not a reason on its own") by being the reason.

The port was a standing goal since 2026-08-10, gated on two open questions: does
`QGraphicsView` fit the charm-tree picker, does the sheet become a `QTextDocument`, and
does retained-mode Qt even test well. Both spikes answered yes, human-approved, with 42
tests between them (see the plan's two "DONE" spike sections). The gate is passed; the
port is committed.

## Decision

Branch and rebuild the UI on **PySide6/Qt** as the bedrock of a 2.0, against the
**untouched** `engine/`, `models/`, loader and `ui/view.py` — every one of which the
spikes proved ports as-is (toolkit-free, tested). The **NiceGUI webapp remains a
co-shipping product**, frozen during the port as the reference implementation to diff
behaviour against. `docs/plans/qt-port.md` becomes the build record.

The two spikes are the evidence the commitment is cheap to make now:

- **`spikes/qt_tree/`** (28 tests): `QGraphicsView` renders the charm picker's trees —
  tidy-tree layout, grouping, node/edge-aware routing, arrows, fit-to-view — fed by the
  real `build_charm_graph`, with no change to any existing file.
- **`spikes/qt_sheet/`** (14 tests): `build_sheet_view` → `QTextDocument` → `QPdfWriter`
  gives the sheet and print from one source.
- **pytest-qt** tests retained-mode widgets headless (offscreen).

## Alternatives rejected

* **Stay NiceGUI-only; the `pack/` webview is "native enough".** Rejected: native
  *widgets* are the point (human, 2026-08-20); a packaged browser keeps the entire
  NiceGUI bug class.
* **NiceGUI `native=True` via pywebview** — a native window around the same DOM. Gets
  none of the three benefits (tree fit, sheet-as-document, the bug-class elimination)
  at non-trivial packaging cost.
* **A Qt port before 1.0.** Rejected: 1.0 shipped on NiceGUI first, as sequenced.
* **No native app at all.** Rejected: the native offering is the product ask.
* **A transliteration of the NiceGUI idiom** — the plan and both spikes are explicit
  that Qt is retained-mode and "rebuild the world per click" must not be copied; a
  mechanical translation "produces something that works and feels wrong."

## Cost

- **~10,490 lines of widget rewrite** (the 13 NiceGUI widget modules). The spikes
  de-risked the tree and sheet, not the form-heavy editing UI, which is mechanical
  lift-and-shift against `view.py` that no spike covers.
- **Two shells to maintain** after the port: a feature lands in shared code plus a thin
  widget touch-up in each shell. The shared `view.py` is what keeps that from being two
  products.
- **The NiceGUI build is frozen during the port** — it becomes the diff reference, not a
  parallel target in feature motion.
- **Per-splat theming is deferred to the port** (the Qt Style Sheets mapping of
  `ui/theme.py`'s palettes is unexamined) — the one thing both spikes agreed is
  port-time work.
- This decision commits the **direction**, not a start date; the plan's sequencing
  stands.
