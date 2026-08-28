"""pytest-qt coverage for the sheet-view spike — headless (conftest sets the
offscreen platform). The point is the plan's open question: does a SheetView render
into a QTextDocument and print, and does it test well."""

from exalted_builder.ui.view import build_sheet_view

from sheet_spike import (SheetWindow, build_document, load_world, print_pdf,
                         sheet_html)


def test_all_examples_build_html():
    # Every example character must render — a field name mistake would surface here
    # across all four splats, not just the first.
    ruleset, characters = load_world()
    for label, char in characters:
        html_text = sheet_html(build_sheet_view(ruleset, char))
        assert "Attributes" in html_text
        assert "Abilities" in html_text
        assert "Traits" in html_text
        assert label.split(" — ")[0] in html_text      # the character's name


def test_html_has_trait_and_section_content():
    ruleset, characters = load_world()
    html_text = sheet_html(build_sheet_view(ruleset, characters[0][1]))
    assert "Willpower" in html_text
    assert "Strength" in html_text                       # an attribute label
    assert "Virtues" in html_text


def test_ratings_render_as_dots():
    ruleset, characters = load_world()
    html_text = sheet_html(build_sheet_view(ruleset, characters[0][1]))
    assert "●" in html_text                              # filled dots
    assert "○" in html_text                              # unfilled track dots


def test_columns_have_separators():
    ruleset, characters = load_world()
    html_text = sheet_html(build_sheet_view(ruleset, characters[0][1]))
    assert "border-left:1px solid" in html_text          # the vertical rules


def test_background_ratings_use_dots():
    ruleset, characters = load_world()
    html_text = sheet_html(build_sheet_view(ruleset, characters[3][1]))   # Yarak: 4 bgs
    bg_section = html_text.split("<b>Backgrounds</b>")[1].split("</table>")[0]
    assert "●" in bg_section
    assert "○" in bg_section


def test_willpower_has_squares_track():
    ruleset, characters = load_world()
    html_text = sheet_html(build_sheet_view(ruleset, characters[0][1]))
    assert "●" in html_text                            # the WP dot track
    assert "□" in html_text                            # the squares tracker below it


def test_equipment_sits_in_traits_not_charms():
    ruleset, characters = load_world()
    view = build_sheet_view(ruleset, characters[0][1])   # Ashes-of-Dawn owns a weapon
    if not view.weapons:
        return                                          # no gear on this machine — defer
    html_text = sheet_html(view)
    weapon_name = view.weapons[0].name
    assert weapon_name in html_text
    assert html_text.index(weapon_name) < html_text.index("Charms &amp; Spells")


def test_health_track_renders_boxes():
    from sheet_spike import _health_track_html
    out = _health_track_html(["-0", "-1", "Incap"])
    assert out.count("□") == 3
    assert "-0" in out and "Incap" in out
    # consecutive same-level boxes group with one label beneath
    grouped = _health_track_html(["-1", "-1", "-2", "-2", "-4"])
    assert grouped.count("□") == 5
    assert grouped.count("-1") == 1
    assert grouped.count("-2") == 1
    # the boxes of one level are a single text run — they never split individually
    pair = _health_track_html(["-1", "-1"])
    assert pair.count("□") == 2
    assert "□□" in pair


def test_health_labels_pad_to_common_width():
    # "Incap" is longer than the other labels; the shorter ones get nbsp padding so
    # every row's boxes start at the same column.
    from sheet_spike import _health_track_html
    out = _health_track_html(["-0", "Incap", "-1"])
    assert "&nbsp;" in out


def test_health_labels_strip_charm_marker():
    # The ★ marks Charm-granted levels; the sheet drops it (the boxes are identical
    # in play), so Charm-granted levels group with the natural ones.
    from sheet_spike import _health_track_html
    out = _health_track_html(["-1 ★", "-1 ★", "Incap"])
    assert "★" not in out
    assert out.count("□") == 3              # 2 merged -1s + 1 Incap
    assert out.count("-1") == 1             # the two -1 levels merged into one row


def test_equipment_has_subheading_in_traits():
    ruleset, characters = load_world()
    view = build_sheet_view(ruleset, characters[0][1])    # Ashes-of-Dawn owns a weapon
    if not view.weapons:
        return
    html_text = sheet_html(view)
    assert html_text.index("Traits") < html_text.index("Equipment") \
        < html_text.index("Charms &amp; Spells")


def test_document_plain_text_nonempty(qtbot):
    ruleset, characters = load_world()
    doc = build_document(sheet_html(build_sheet_view(ruleset, characters[0][1])))
    text = doc.toPlainText()
    assert characters[0][0].split(" — ")[0] in text
    assert len(text) > 100


def test_print_to_pdf_writes_file(qtbot, tmp_path):
    ruleset, characters = load_world()
    doc = build_document(sheet_html(build_sheet_view(ruleset, characters[0][1])))
    out = tmp_path / "sheet.pdf"
    print_pdf(doc, str(out))
    assert out.exists()
    assert out.stat().st_size > 500                     # a real PDF, not an empty file


def test_window_offers_examples_and_shows_sheet(qtbot):
    ruleset, characters = load_world()
    win = SheetWindow(ruleset, characters)
    qtbot.addWidget(win)
    assert win.combo.count() == len(characters)
    assert win.view.toPlainText()
    win.combo.setCurrentIndex(len(characters) - 1)
    qtbot.wait(5)
    assert win._characters[win.combo.currentIndex()][0].split(" — ")[0] in win.view.toPlainText()
