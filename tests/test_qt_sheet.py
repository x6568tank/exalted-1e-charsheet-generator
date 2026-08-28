"""The Qt Sheet tab (exalted_builder/qt/sheet.py) — QTextDocument sheet + print.

The HTML builders are the qt_sheet spike's tested core; these tests keep that
coverage in the port: every section renders for a fresh character, the document is
non-empty, the print path writes a real PDF, and the page widget reloads from the
shared context.
"""

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from exalted_builder.models.character import Character
from exalted_builder.qt.sheet import (SheetPage, build_document, print_colors,
                                      print_pdf, screen_colors, sheet_html)
from exalted_builder.ui.view import build_sheet_view


def test_sheet_html_has_all_sections(ruleset):
    html = sheet_html(build_sheet_view(ruleset, Character(id="char.new")))
    for section in ("Attributes", "Abilities", "Traits"):
        assert section in html
    assert "Strength" in html          # an attribute row rendered


def test_sheet_html_uses_splat_accent(ruleset):
    solar = sheet_html(build_sheet_view(ruleset, Character(id="c", exalt_type="Solar")))
    db = sheet_html(build_sheet_view(ruleset, Character(id="c", exalt_type="Dragon-Blooded")))
    assert solar != db


def test_build_document_is_nonempty(ruleset):
    doc = build_document(sheet_html(build_sheet_view(ruleset, Character(id="char.new"))))
    assert len(doc.toPlainText()) > 100


def test_print_pdf_writes_a_real_file(qapp, ruleset, tmp_path):
    """⚠ Takes `qapp` although it builds no widget: laying a document out for the
    printer hits QFontDatabase, which ABORTS the interpreter — not fails — when no
    QApplication exists. It passed for months only because some earlier module's qtbot
    had already made one; running this file on its own took the whole run down."""
    doc = build_document(sheet_html(build_sheet_view(ruleset, Character(id="char.new"))))
    out = tmp_path / "sheet.pdf"
    print_pdf(doc, str(out))
    assert out.stat().st_size > 500


def test_the_printed_sheet_stays_ink_on_paper(ruleset):
    """⚠ The screen set is for the SCREEN. `sheet_html` defaults to the paper colours so
    a caller that just wants a printable document — `print_pdf`, and any future export —
    cannot pick up the dark page by omission."""
    view = build_sheet_view(ruleset, Character(id="c", exalt_type="Solar"))
    assert sheet_html(view) == sheet_html(view, print_colors("Solar"))
    assert sheet_html(view) != sheet_html(view, screen_colors("Solar"))
    assert screen_colors("Solar").muted in sheet_html(view, screen_colors("Solar"))


def test_the_screen_sheet_lightens_the_splat_accent(ruleset):
    """The printed accents are dark tones that vanish on the dark base, so the screen
    set lightens them exactly as every other widget's does."""
    solar = build_sheet_view(ruleset, Character(id="c", exalt_type="Solar"))
    assert print_colors("Solar").accent not in sheet_html(solar, screen_colors("Solar"))
    assert screen_colors("Solar").accent != screen_colors("Lunar").accent


def test_sheet_page_reloads_from_context(qtbot, ruleset):
    char = Character(id="char.new", name="First")
    page = SheetPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    first = page.view.toPlainText()
    assert "First" in first
    char.name = "Second"
    page.reload()
    assert "Second" in page.view.toPlainText()
