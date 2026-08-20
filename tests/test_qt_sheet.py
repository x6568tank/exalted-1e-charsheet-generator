"""The Qt Sheet tab (exalted_builder/qt/sheet.py) — QTextDocument sheet + print.

The HTML builders are the qt_sheet spike's tested core; these tests keep that
coverage in the port: every section renders for a fresh character, the document is
non-empty, the print path writes a real PDF, and the page widget reloads from the
shared context.
"""

from exalted_builder.models.character import Character
from exalted_builder.qt.sheet import (SheetPage, build_document, print_pdf,
                                      sheet_html)
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


def test_print_pdf_writes_a_real_file(ruleset, tmp_path):
    doc = build_document(sheet_html(build_sheet_view(ruleset, Character(id="char.new"))))
    out = tmp_path / "sheet.pdf"
    print_pdf(doc, str(out))
    assert out.stat().st_size > 500


def test_sheet_page_reloads_from_context(qtbot, ruleset):
    char = Character(id="char.new", name="First")
    page = SheetPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    first = page.view.toPlainText()
    assert "First" in first
    char.name = "Second"
    page.reload()
    assert "Second" in page.view.toPlainText()
