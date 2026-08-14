"""
tests/test_pdf.py — the generated PDF character sheet (ui/pdf.py).

The FIRST test in this file is the important one, and it is written the way it is
because of this project's recurring bug: a field that nothing reads. The Sheet tab
and the PDF render from the same `SheetView`, so the moment a new splat adds a
field, the screen sheet shows it and the PDF silently omits it forever — no test
fails, because a renderer that ignores a field is indistinguishable from one that
has no opinion about it. `test_every_sheetview_field_is_printed_or_declared_omitted`
turns that silence into a failure.

The rest is ordinary: content round-trips (does what the SheetView holds reach the
page), negative controls for the two blocks the human ruled OFF the sheet, purity,
and pagination.
"""

from __future__ import annotations

import ast
import dataclasses
import io
from pathlib import Path

import pytest

from reportlab.lib.units import mm

from exalted_builder import persistence, rules_db
from exalted_builder.models.character import Character, MeritFlawPurchase
from exalted_builder.ui import pdf
from exalted_builder.ui import view as viewmod

pypdf = pytest.importorskip("pypdf")

_ROOT = Path(__file__).resolve().parents[1]
_DATA_DIR = _ROOT / "exalted_builder" / "data"
_EXAMPLES = sorted((_ROOT / "examples").glob("*.character.json"))


@pytest.fixture(scope="module")
def ruleset():
    return rules_db.load_app_ruleset(_DATA_DIR)


def _sheet(ruleset, path: Path) -> viewmod.SheetView:
    return viewmod.build_sheet_view(ruleset, persistence.load_character(path))


def _text(data: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _winansi_safe(ch: str) -> bool:
    """True if reportlab's default base-14 encoding can actually draw `ch`."""
    if ch in "\n\r\t":
        return True
    try:
        ch.encode("cp1252")
    except UnicodeEncodeError:
        return False
    return True


def _pages(data: bytes) -> int:
    return len(pypdf.PdfReader(io.BytesIO(data)).pages)


# --------------------------------------------------------------------------- #
# 1. The field-coverage test — written before the layout, and the reason this
#    file exists at all.
# --------------------------------------------------------------------------- #

def test_every_sheetview_field_is_printed_or_declared_omitted():
    """Every field on SheetView is either read by ui/pdf.py or named in its
    `DELIBERATELY_OMITTED` set. A new field fails this until somebody DECIDES.

    This is the mechanical form of CLAUDE.md's sharpest rule — a zero-site field
    can still look healthy, because something else may be doing its job by
    accident. Here nothing does: an unread field is simply absent from the paper
    sheet, and absence is exactly what nobody notices.
    """
    source = Path(pdf.__file__).read_text()
    fields = {f.name for f in dataclasses.fields(viewmod.SheetView)}

    unread = set()
    for name in fields:
        if name in pdf.DELIBERATELY_OMITTED or name in pdf.READ_VIA_METHOD:
            continue
        # Deliberately strict: `view.<field>`, not a bare `.<field>`. Loosening it
        # to any attribute access would let common names (`.name`, `.cost`) pass on
        # an unrelated row object, which is precisely the silence being tested for.
        if f"view.{name}" not in source:
            unread.add(name)
    assert not unread, (
        f"ui/pdf.py never reads {sorted(unread)}. Either print the field or add it "
        "to DELIBERATELY_OMITTED with a reason — silence is how a panel goes "
        "missing for a whole splat."
    )

    # The omission lists must describe REAL fields: a renamed field that is still
    # listed as "deliberately omitted" would silence this test forever.
    stale = (set(pdf.DELIBERATELY_OMITTED) | set(pdf.READ_VIA_METHOD)) - fields
    assert not stale, f"{sorted(stale)} are not SheetView fields any more"

    # A field routed through a method must actually have that method called.
    for name, method in pdf.READ_VIA_METHOD.items():
        assert f"{method}()" in source, (
            f"{name} is declared as read through {method}(), which ui/pdf.py "
            f"never calls")


def test_deliberate_omissions_are_the_humans_ruling():
    """The human ruled the two build-time blocks OFF the printed sheet
    (docs/plans/print-pdf.md, decision 4). Pin it: a later session that quietly
    prints the validation panel should have to change this list on purpose."""
    assert pdf.DELIBERATELY_OMITTED == {
        "issues", "xp_log", "xp_earned", "xp_spent", "xp_available", "charms",
    }


# --------------------------------------------------------------------------- #
# 2. Content round-trip
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("path", _EXAMPLES, ids=lambda p: p.stem)
def test_example_characters_render_and_carry_their_content(ruleset, path):
    view = _sheet(ruleset, path)
    text = _text(pdf.build_pdf(view))

    assert view.name in text
    assert view.exalt_type in text

    for _category, rows in view.attributes:
        for row in rows:
            assert row.label in text, f"attribute {row.label} missing"
    for _group, rows in view.ability_groups:
        for row in rows:
            assert row.label in text, f"ability {row.label} missing"
    for row in view.virtues:
        assert row.label in text
    for name, _rating, _note in view.backgrounds:
        assert name in text, f"background {name} missing"
    for ability, spec_name, _rating in view.specialties:
        assert spec_name in text, f"specialty {spec_name} missing"
    for _section, rows in view.charm_sections:
        for charm in rows:
            assert charm.name in text, f"charm {charm.name} missing"
    for spell in view.spells:
        assert spell.name in text
    for weapon in view.weapons:
        assert weapon.name in text
    for armor in view.armor:
        assert armor.name in text


def test_ratings_and_derived_numbers_reach_the_page(ruleset):
    """Dots are DRAWN, not typed, so a rating's presence is asserted through the
    numeric readouts the sheet also prints — Willpower, soak, essence."""
    view = _sheet(ruleset, _EXAMPLES[0])
    text = _text(pdf.build_pdf(view))

    assert str(view.willpower) in text
    assert str(view.soak.lethal) in text
    assert str(view.essence_rating) in text
    assert view.essence_pool_label().split("·")[0].strip() in text.replace("\n", " ")


def test_notes_print_but_rules_text_does_not(ruleset):
    """The human's ruling: notes yes, rules text no. A Background's note and an
    artifact's source are structured fields and print; a Charm description is
    rules text and must not appear anywhere."""
    character = persistence.load_character(_EXAMPLES[0])
    view = viewmod.build_sheet_view(ruleset, character)
    text = _text(pdf.build_pdf(view))

    noted = [n for _name, _r, n in view.backgrounds if n]
    assert noted, "fixture no longer exercises background notes"
    for note in noted:
        assert note in text, f"background note {note!r} was dropped"

    described = [c for _s, rows in view.charm_sections for c in rows if c.description]
    assert described, "fixture no longer exercises charm descriptions"
    for charm in described:
        # The first clause is enough: reportlab may wrap, so match a short prefix
        # that could only come from the description body.
        probe = charm.description.strip()[:40]
        assert probe not in text, (
            f"charm rules text leaked onto the sheet: {probe!r}")


def test_merit_flaw_names_and_costs_print_without_their_rules_text(ruleset):
    """A Merit prints as name + printed cost + the player's `detail` note. The
    tooltip's OTHER half — the rules text — is the human's one exclusion, and the
    Merit panel is where it would most easily creep back in.

    No example character carries Merits, so they are attached here rather than
    skipping: a skipped test is how this panel would ship unprinted.
    """
    character = persistence.load_character(_EXAMPLES[0])
    character.merits_flaws = [
        MeritFlawPurchase(merit_id="mf.acute-sense", detail="hearing"),
        MeritFlawPurchase(merit_id="mf.addiction"),
    ]
    view = viewmod.build_sheet_view(ruleset, character)
    assert len(view.merits_flaws) == 2, "fixture ids no longer resolve"

    text = _text(pdf.build_pdf(view))
    for name, points, detail, _kind, tip in view.merits_flaws:
        assert name in text, f"merit {name} missing"
        assert points in text, f"merit {name} lost its cost"
        if detail:
            assert detail in text, f"merit note {detail!r} was dropped"
        # The tooltip is the printed cost line PLUS the rules text. Its tail is
        # rules text by construction, and must not be on the page.
        tail = tip.strip()[-40:]
        if len(tip) > 60:
            assert tail not in text, f"merit rules text leaked: {tail!r}"


# --------------------------------------------------------------------------- #
# 3. Negative controls — the two blocks the human ruled off the sheet
# --------------------------------------------------------------------------- #

def test_validation_issues_and_xp_ledger_are_absent(ruleset):
    """Decision 4 enforced, not assumed. Uses a character that HAS both, so the
    absence means the renderer dropped them rather than there being nothing to
    drop — the negative control this project keeps needing."""
    character = persistence.load_character(_EXAMPLES[0])
    view = viewmod.build_sheet_view(ruleset, character)

    assert view.issues, "fixture no longer produces validation issues"
    view.xp_log = [viewmod.XpLogRow(index=0, label="Melee 2 -> 3", detail="Melee", cost=4)]
    view.xp_earned, view.xp_spent, view.xp_available = 20, 4, 16
    view.chargen_locked = True

    text = _text(pdf.build_pdf(view))

    for issue in view.issues:
        assert issue.message not in text, "the validation panel reached paper"
    assert "Melee 2 -> 3" not in text, "the XP ledger reached paper"
    assert "Validation" not in text
    # The experience TOTAL is a different thing and DOES print.
    assert "Experience" in text


def test_every_shipped_splat_renders(ruleset):
    """The render matrix, as a PDF rather than a page. The four example characters
    are Solar/Solar/Sidereal/Alchemical, which leaves seven splats — and the ones
    with the unusual SHAPES — never rendered to paper at all.

    The shapes that have broken UI before, and every one of them reaches a panel
    here: a splat with no Charms (Mortal), no castes (Mortal, Ghost), no
    ability-castes (Lunar), a rated Path subsystem (Dragon-Kings), Fetters and
    Passions (Ghost), a merged Essence pool.
    """
    failures = []
    for exalt_type in ruleset.exalts:
        character = Character(id=f"c.{exalt_type.lower()}", name=f"{exalt_type} Test",
                              exalt_type=exalt_type)
        try:
            view = viewmod.build_sheet_view(ruleset, character)
            data = pdf.build_pdf(view)
        except Exception as ex:                     # noqa: BLE001 - collect them all
            failures.append(f"{exalt_type}: {type(ex).__name__}: {ex}")
            continue
        if exalt_type not in _text(data):
            failures.append(f"{exalt_type}: rendered but its splat name is absent")
    assert not failures, "splats that will not print:\n  " + "\n  ".join(failures)


@pytest.mark.parametrize("exalt_type", ["Mortal", "Ghost", "Lunar", "Dragon-Kings"])
def test_awkward_splat_shapes_keep_their_traits(ruleset, exalt_type):
    """Rendering without raising is the low bar. These four are the shapes whose
    panels are conditional, so assert the traits actually reached the page rather
    than that nothing blew up."""
    character = Character(id="c.x", name="Shape Test", exalt_type=exalt_type)
    view = viewmod.build_sheet_view(ruleset, character)
    text = _text(pdf.build_pdf(view))
    for _category, rows in view.attributes:
        for row in rows:
            assert row.label in text, f"{exalt_type}: attribute {row.label} missing"
    for row in view.virtues:
        assert row.label in text, f"{exalt_type}: virtue {row.label} missing"
    assert "Willpower" in text and "Health" in text


# --------------------------------------------------------------------------- #
# 4. Glyphs — the trap the plan named in advance
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("path", _EXAMPLES, ids=lambda p: p.stem)
def test_no_unprintable_glyph_reaches_the_page(ruleset, path):
    """reportlab's base-14 fonts encode as WinAnsi (cp1252). Any glyph outside it
    prints as a blank or a black box, and ui/view.py bakes several into DISPLAY
    STRINGS that look like ordinary text — '★' for a Charm-granted health level,
    '★'/'✚' on a Dragon-King Path, '●'/'✦' in labels. Those arrive through data,
    not through this module's own source, so reading ui/pdf.py cannot catch them.

    Assert on the rendered page instead. cp1252, NOT latin-1: the em dash, the
    bullet and the curly quotes are all in WinAnsi and print correctly, so a
    latin-1 check would fail on text that is perfectly fine.
    """
    view = _sheet(ruleset, path)
    text = _text(pdf.build_pdf(view))
    offenders = sorted({c for c in text if not _winansi_safe(c)})
    assert not offenders, (
        f"unprintable glyph(s) {offenders} reached the page — translate them to "
        "ASCII (and say what the mark MEANS, since paper has no tooltip)")


def test_charm_granted_health_levels_are_marked_and_explained(ruleset):
    """The '★' on a Charm-granted level becomes '*', and the sheet says so. A
    mark with no legend is noise; dropping it silently loses which levels the
    character actually bought."""
    view = _sheet(ruleset, _ROOT / "examples" / "yarak.character.json")
    assert any("★" in l for l in view.health), "fixture lost its Ox-Body levels"
    text = _text(pdf.build_pdf(view))
    assert "Charm-granted level" in text


def test_dragon_king_path_favour_marks_become_words(ruleset):
    """`PathRow.favored` is a RAW GLYPH in the view model — '★' for a breed Path,
    '✚' for the player's choice. A blank Dragon-King owns no Paths, so the splat
    matrix above never reaches this; it is set explicitly for that reason."""
    view = _sheet(ruleset, _EXAMPLES[0])
    view.paths = [
        viewmod.PathRow(name="Path of the Sun", element_label="Fire", favored="★",
                        rating=2, powers=[viewmod.PathPowerRow(
                            dot=1, name="Sunfire Gaze", cost="3m", type="Simple",
                            duration="Instant", text="RULES TEXT MUST NOT PRINT")]),
        viewmod.PathRow(name="Path of the Moon", element_label="Water", favored="✚",
                        rating=1, powers=[]),
    ]
    text = _text(pdf.build_pdf(view))
    assert "(breed)" in text and "(chosen)" in text
    assert "★" not in text and "✚" not in text
    assert "Sunfire Gaze" in text
    # A Path power is a Charm by another name; the names-and-costs-only ruling
    # covers it too.
    assert "RULES TEXT MUST NOT PRINT" not in text


def test_a_long_health_track_stays_inside_its_panel():
    """An Ox-Body Solar has nineteen health levels. A single-row track ran out of
    its panel and printed over the Virtues beside it, so the track wraps; this
    pins the wrapping rather than the overflow."""
    narrow = pdf._HealthTrack(["-0"] * 19 + ["Incap"], 60 * mm)
    assert narrow.width <= 60 * mm
    assert len(narrow.rows) > 1
    for row in narrow.rows:
        used = sum(col for _label, col in row) + narrow._GUTTER * (len(row) - 1)
        assert used <= 60 * mm


# --------------------------------------------------------------------------- #
# 5. Purity — ui/pdf.py must survive the Qt port untouched
# --------------------------------------------------------------------------- #

def test_pdf_module_does_not_import_nicegui():
    """`build_pdf` takes a SheetView and nothing else, and imports no web toolkit.
    That is what lets the GM screen, the tests and a future PySide6 build all use
    one renderer (docs/plans/qt-port.md)."""
    tree = ast.parse(Path(pdf.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert imported, "parsed no imports at all — the check would pass vacuously"
    assert "nicegui" not in imported


def test_build_pdf_needs_only_a_sheetview():
    """No ruleset, no Character, no callbacks — the same purity render_sheet has."""
    view = viewmod.build_sheet_view(
        rules_db.load_app_ruleset(_DATA_DIR), Character(id="char.blank"))
    assert pdf.build_pdf(view).startswith(b"%PDF")


# --------------------------------------------------------------------------- #
# 6. Pagination and paper
# --------------------------------------------------------------------------- #

def test_a_large_charm_holding_paginates(ruleset):
    view = _sheet(ruleset, _EXAMPLES[0])
    view.charm_sections = [(
        "Charms",
        [viewmod.CharmRow(name=f"Test Charm Number {i}", category="Melee",
                          cost="5m", duration="Instant")
         for i in range(200)],
    )]
    data = pdf.build_pdf(view)
    assert _pages(data) > 1
    assert "Test Charm Number 199" in _text(data)


@pytest.mark.parametrize("paper", ["A4", "Letter"])
def test_both_paper_sizes_are_offered_and_differ(ruleset, paper):
    view = _sheet(ruleset, _EXAMPLES[0])
    assert paper in pdf.PAPER_SIZES
    data = pdf.build_pdf(view, paper=paper)
    box = pypdf.PdfReader(io.BytesIO(data)).pages[0].mediabox
    expected = pdf.PAPER_SIZES[paper]
    assert round(float(box.width)) == round(expected[0])
    assert round(float(box.height)) == round(expected[1])


def test_an_empty_specialties_panel_is_dropped_not_printed_blank(ruleset):
    """An empty box holding "—" takes a third of a row to say nothing. On screen
    that panel is a landmark you return to; on paper it is just a blank rectangle.
    Human's call, 2026-08-14.

    Negative-controlled against a character who HAS specialties, so this cannot
    pass by the panel having vanished for everyone.
    """
    empty = _sheet(ruleset, _ROOT / "examples" / "gearheart.character.json")
    assert not empty.specialties, "fixture gained specialties"
    assert "Specialties" not in _text(pdf.build_pdf(empty))

    populated = _sheet(ruleset, _ROOT / "examples" / "yarak.character.json")
    assert populated.specialties, "fixture lost its specialties"
    text = _text(pdf.build_pdf(populated))
    assert "Specialties" in text
    assert populated.specialties[0][1] in text


def test_no_panel_prints_an_empty_box(ruleset):
    """The general rule the Specialties fix generalises to: a panel holding nothing
    is dropped, never printed as a box containing "—". Asserted on a BLANK
    character, where every optional panel is empty at once — including the
    Advantages heading, which must not outlive the band it heads."""
    view = viewmod.build_sheet_view(ruleset, Character(id="c.blank", name="Blank"))
    text = _text(pdf.build_pdf(view))
    for panel in ("Backgrounds", "Specialties", "Equipment", "Advantages",
                  "Artifacts", "Merits & Flaws"):
        assert panel not in text, f"empty {panel} panel printed as a blank box"
    # The sheet is still a sheet: the traits it always has are still there.
    assert "Willpower" in text and "Virtues" in text and "Strength" in text


def test_the_bottom_band_reflows_when_the_equipment_panel_is_dropped(ruleset):
    """Dropping a panel must re-spread the band, not leave a hole. The column count
    is decided before anything is built — a panel's inner tables are laid out
    against its construction width, so widening it afterwards detaches the dots
    from their labels."""
    bare = viewmod.build_sheet_view(ruleset, Character(id="c.bare", name="Bare"))
    assert not pdf._has_equipment_panel(bare)
    assert "Compassion" in _text(pdf.build_pdf(bare))

    kitted = _sheet(ruleset, _ROOT / "examples" / "yarak.character.json")
    assert pdf._has_equipment_panel(kitted)
    assert "Equipment" in _text(pdf.build_pdf(kitted))


def test_an_anima_alone_keeps_the_left_panel_without_a_gear_placeholder(ruleset):
    """The panel is NOT empty merely because there is no gear — an Alchemical with
    no weapons still has an Anima, and the panel used to print "—" above it for the
    gear that was not there."""
    view = _sheet(ruleset, _ROOT / "examples" / "gearheart.character.json")
    assert view.anima and not view.weapons and not view.armor
    text = _text(pdf.build_pdf(view))
    assert view.anima in text
    assert "Equipment" not in text, "gear heading printed with no gear under it"


def test_a_character_with_no_charms_gets_no_charms_heading(ruleset):
    """A Sidereal fresh out of chargen owns no Charms. An empty CHARMS rule ruled
    across the page reads as a renderer that lost the list, not as a character who
    has none — the same reason every panel here is dropped when empty."""
    view = _sheet(ruleset, _EXAMPLES[0])
    view.charm_sections = [("Charms", [])]
    view.spells, view.paths, view.combos, view.elemental_powers = [], [], [], []
    assert "CHARMS" not in _text(pdf.build_pdf(view)).upper()


def test_a_party_export_carries_every_member_one_per_page(ruleset):
    """The party export is the same renderer over a list, not a second layout.
    Each member starts on a fresh page — sheets get handed out at a table, so two
    half-sheets sharing a page would be unusable."""
    views = [_sheet(ruleset, p) for p in _EXAMPLES]
    singles = [_pages(pdf.build_pdf(v)) for v in views]

    data = pdf.build_party_pdf(views, party_name="Test Circle")
    text = _text(data)
    for view in views:
        assert view.name in text, f"{view.name} missing from the party export"
    assert _pages(data) == sum(singles), (
        "a member's sheet shares a page with the next one")


def test_an_empty_party_export_is_refused(ruleset):
    with pytest.raises(ValueError):
        pdf.build_party_pdf([])


def test_unknown_paper_size_is_rejected(ruleset):
    view = _sheet(ruleset, _EXAMPLES[0])
    with pytest.raises(ValueError):
        pdf.build_pdf(view, paper="Foolscap")


# --------------------------------------------------------------------------- #
# 7. The buttons — the renderer being right is no use if nothing reaches it
# --------------------------------------------------------------------------- #

@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_builder_offers_a_print_button_and_its_dialog(user) -> None:
    """The Print button lives on the header bar, NOT on the Sheet tab:
    `render_sheet` takes a SheetView and no callbacks, and a button inside it
    would need one — which is what the GM party screen and the render tests
    depend on it not having."""
    await user.open("/builder")
    await user.should_see("Print")
    # Negative control first: `should_see` will happily match text that was
    # already on the page, so a dialog assertion proves nothing unless the text
    # is absent beforehand.
    await user.should_not_see("Export character sheet")
    user.find("Print").click()
    await user.should_see("Export character sheet")
    # Paper size is asked here rather than stored — the human's ruling.
    await user.should_see("A4")
    await user.should_see("Letter")


@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_party_screen_offers_a_whole_party_export(user) -> None:
    await user.open("/gm")
    await user.should_see("Print all")
    await user.should_not_see("Export 2 character sheets")
    user.find("Print all").click()
    # The two-member fixture party: the dialog says how many sheets it will make,
    # so a mis-wired party() showing one member is visible before exporting.
    await user.should_see("Export 2 character sheets")


def test_suggested_filename_is_derived_from_the_character(ruleset):
    view = _sheet(ruleset, _EXAMPLES[0])
    assert pdf.suggested_filename(view).endswith(".pdf")
    assert "/" not in pdf.suggested_filename(view)


@pytest.mark.parametrize("typed,expected", [
    ("yarak", "yarak.pdf"),
    ("yarak.pdf", "yarak.pdf"),
    ("  spaced name  ", "spaced name.pdf"),
    ("../../etc/passwd", "etc-passwd.pdf"),
    ("..", None),        # nothing but traversal is nothing at all
    ("", None),          # falls back to the character's own name
    ("   ", None),
])
def test_export_filenames_are_made_safe(ruleset, typed, expected):
    """The dialog's name field is free text and its result goes straight to a
    browser download or an OS save dialog, so a path separator must never
    survive it."""
    view = _sheet(ruleset, _EXAMPLES[0])
    got = pdf.normalize_pdf_filename(typed, view)
    assert got == (expected if expected is not None else pdf.suggested_filename(view))
    assert "/" not in got and "\\" not in got
    assert got.endswith(".pdf")
