"""Column detection in `tools/extract_born_digital.py`.

The PDFs live in gitignored `sources/`, so these build the page GEOMETRY by hand
instead: `columns()` only ever asks a page for `width` and `extract_words()`, so a
stub carrying the x/y boxes of a layout is a complete input.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from extract_born_digital import columns  # noqa: E402


class StubPage:
    """A page that reports the word boxes it was built with."""

    def __init__(self, words, width=612.0):
        self.width = width
        self._words = words

    def extract_words(self, **kw):
        return self._words


def _word(x0, x1, top):
    return {"x0": x0, "x1": x1, "top": top, "bottom": top + 10,
            "text": "x", "fontname": "F"}


def _two_column_body(n_lines=40, start_top=400.0):
    """A normal two-column body: left 76-300, right 330-527, gutter at ~315."""
    words = []
    for i in range(n_lines):
        top = start_top + i * 12
        words.append(_word(76, 300, top))
        words.append(_word(330, 527, top))
    return words


def test_plain_two_column_page_splits():
    page = StubPage(_two_column_body())
    assert len(columns(page)) == 2


def test_single_column_page_does_not_split():
    words = [_word(76, 527, 100 + i * 12) for i in range(40)]
    assert len(columns(StubPage(words))) == 1


def test_text_in_one_half_is_not_a_gutter():
    # A margin is not a gutter: all text sits right of centre (core p.158 and the
    # other Charm-tree pages, where the tree takes one half of the page).
    words = [_word(330, 527, 100 + i * 12) for i in range(40)]
    assert len(columns(StubPage(words))) == 1


def test_diagram_straddling_the_gutter_does_not_defeat_the_split():
    """⚠ The regression this file exists for.

    Core pp.154-292 put a Charm-tree diagram at the top of ~37 pages. Its node labels
    sit at arbitrary x and straddle the gutter a dozen times, which lifts the
    whole-page projection profile's floor past its threshold — so no gutter is found,
    one column is returned, and the two-column BODY BELOW the diagram interleaves.
    It is silent: `looks_two_column` reads the same scattered label edges and also
    says no, so no COLUMN SPLIT FAILED marker fires either.
    """
    diagram = [
        _word(271, 339, 132), _word(281, 329, 140), _word(285, 324, 172),
        _word(291, 319, 184), _word(294, 316, 216), _word(295, 315, 228),
        _word(281, 330, 260), _word(290, 320, 268), _word(270, 340, 304),
        _word(283, 327, 312), _word(291, 319, 344), _word(280, 330, 356),
    ]
    page = StubPage(diagram + _two_column_body())
    assert len(columns(page)) == 2, "the body below a gutter-straddling diagram interleaved"


def test_a_full_width_heading_does_not_defeat_the_split():
    # Same failure shape, commonest cause: one full-width line over a two-column body.
    page = StubPage([_word(76, 527, 380)] + _two_column_body())
    assert len(columns(page)) == 2


@pytest.mark.parametrize("n_intrusions", [1, 5, 12, 19])
def test_split_survives_intrusions_up_to_half_the_lines(n_intrusions):
    # 40 body lines; the gutter must still be found while the clear run stays >= half.
    intrusions = [_word(200, 400, 100 + i * 12) for i in range(n_intrusions)]
    page = StubPage(intrusions + _two_column_body())
    assert len(columns(page)) == 2
