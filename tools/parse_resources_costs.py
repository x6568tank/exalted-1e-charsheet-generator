#!/usr/bin/env python3
"""Read the corebook's Resources-cost columns straight out of the PDF text layer.

Core prices gear in DOTS, and the dot is a glyph in a subsetted display font that the
corebook's thirteen-cipher glyph map does not decode — so `images/_extracted/Exalted
Core.md` renders every cost as U+FFFD and the Cost column has been unreadable since the
catalogue sweep (63 values recorded as "unattributed" in docs/status/rated-artifacts.md).

The dot does not need decoding, only IDENTIFYING: it is `(cid:10)` in
`ZTR41CA.tmp,Bold`, and the count of that glyph in a row IS the rating. Established on
core p.330, where "Chakram +0 +1L 3 20 •" and the Minimums column "S ••" gave six
occurrences in exactly the right places, and confirmed against the 54 costs already
authored by hand (see `--verify`).

⚠ This counts glyph OCCURRENCES in a text layer — it is not the VLM leg, and the
"never count dots, take the rating from the rung's position" rule in CLAUDE.md is about
rasterised pages, where a model's dot counts are biased low. Here the count is exact or
the parse fails loudly.

Usage:
    parse_resources_costs.py <pdf> --verify        # diff against data/*.json
    parse_resources_costs.py <pdf> --pages 323-324 # dump what a page range yields
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).parent))
from extract_born_digital import make_font_decoder            # noqa: E402

# The dot glyph. Identified on core p.330 — see the module docstring. A LIST because a
# second face may draw the same mark elsewhere in the book; add rather than replace, and
# say where the evidence came from.
DOT_GLYPHS = {
    ("BFHAOF+ZTR41CA.tmp,Bold", "(cid:10)"),   # p.330 weapon tables, Resources + Minimums
}

GLYPH_MAP = Path(__file__).parent / "glyph_maps" / "exalted-core.json"
OFFSET = 2                                     # book page + 2 = pdf index + 1


def _words(chars, decode):
    """Chars grouped into words with their x spans, left to right."""
    out, cur = [], []
    for ch in sorted(chars, key=lambda c: c["x0"]):
        if cur and ch["x0"] - cur[-1]["x1"] > 1.2:
            out.append(cur)
            cur = []
        cur.append(ch)
    if cur:
        out.append(cur)
    return [("".join(decode(c["text"], c["fontname"]) for c in w), w[0]["x0"], w[-1]["x1"])
            for w in out]


def rows_on_page(pdf, book_page: int):
    """Every visual line on `book_page` as (text, cost_dots), counting ONLY the dots in
    the Resources column.

    ⚠ A whole-row dot count is WRONG and looks right. The weapon tables carry a
    `Minimums` column that is also drawn in dots ("Hatchet … -1 S ••"), so summing the
    row charges a hatchet its Strength minimum as Resources — the first cut of this
    parser did exactly that and read Axe • as •••. It was caught only by diffing against
    the hand-authored values, which is the whole reason `--verify` exists and why it runs
    before any new value is trusted.

    So each table's Resources column is located from its own header row (the x span of
    the word "Resources", running to the next header word or the column edge) and dots
    are counted inside that band. A page with no such header yields no costs rather than
    a guess.

    Lines are grouped on rounded `top`, the same way the extractor does it.
    """
    decode = make_font_decoder(str(GLYPH_MAP))
    page = pdf.pages[book_page + OFFSET - 1]
    lines = collections.defaultdict(list)
    for ch in page.chars:
        lines[round(ch["top"] / 2)].append(ch)

    out, band, name_left = [], None, 0.0
    for top in sorted(lines):
        chars = sorted(lines[top], key=lambda c: c["x0"])
        words = _words(chars, decode)
        text = " ".join(w for w, _, _ in words).strip()

        # A header line re-aims the band — tables restart down the page and in the
        # second column, and a band held over from the previous table would count the
        # wrong x range for every row under it.
        #
        # ⚠ A header with NO Resources column must CLEAR it, not leave the old one
        # standing. p.330 sets the thrown-weapons table (which has Resources) directly
        # above the hand-to-hand table (which has Minimums, also drawn in dots) — so a
        # held-over band read "Hatchet … S ••" as Resources ••. It went unnoticed
        # because the first, correct Hatchet row won the dict and `--verify` passed:
        # a masked bug behind a green check.
        if re.match(r"^(Name|Item)\b", text) and not re.search(r"Resources|Cost", text):
            band = None
        for i, (word, x0, x1) in enumerate(words):
            # ⚠ "Resources Cost" is ONE word here and TWO words on the weapon tables:
            # words are split on a 1.2pt gap and the goods tables on pp.323-324 set the
            # header tighter than that. An exact-match test on "Resources" silently
            # matched nothing on those two pages — the entire mundane-equipment table
            # parsed as zero costed rows and looked like a page range that held no
            # table, rather than like a bug.
            if re.fullmatch(r"Resources(\s+Cost)?|Cost", word.strip().rstrip(":")):
                right = words[i + 1][1] if i + 1 < len(words) else x1 + 80
                band = (x0 - 4, max(right, x1) + 4)
                # Where this table's NAME column starts — the header word to the left
                # of the cost ("Item", "Name"). pp.323-324 are two-column pages whose
                # tables sit in the right column, so a line's text is left-column PROSE
                # followed by the table row: without this the parsed name came out as
                # "small town are unlikely to find articulated plate armor. Fancy
                # clothing". Only text between the name column and the cost band counts.
                # The FIRST word of the header line, not the one next to the cost:
                # "Name Speed Accuracy Damage Defense Resources Minimums" would
                # otherwise start the name column at "Defense" and every weapon name
                # would be cut away — 42 agreements went to 0 on that mistake.
                name_left = words[0][1]
                break

        dots = 0
        row_name = text
        if band:
            dots = sum(1 for c in chars
                       if (c["fontname"], c["text"]) in DOT_GLYPHS
                       and band[0] <= c["x0"] <= band[1])
            row_name = " ".join(w for w, wx0, _ in words
                                if name_left - 4 <= wx0 < band[0]).strip()
        out.append((row_name or text, dots))
    return out


def costed_rows(pdf, first: int, last: int) -> dict[str, int]:
    """`{name: dots}` for every line on the range that carries dots and a name.

    The name runs up to the first SPACE-PRECEDED number, sign or dot — "Chakram +0 +1L
    3 20 •", "Fine camel/horse •••". ⚠ Splitting on the first digit-or-sign anywhere is
    the obvious version and it is wrong: it cuts hyphenated names in half, turning
    "Seven-Section Staff" into "Seven" and "Wind-Fire Wheel" into "Wind", which then
    match nothing in the catalogue and disappear into the not-found list looking like
    rows the parser never reached.

    A line with dots and no leading text is a continuation (the tables wrap parenthetical
    qualifiers onto their own line) and is skipped rather than guessed at.
    """
    found: dict[str, int] = {}
    for page in range(first, last + 1):
        for text, dots in rows_on_page(pdf, page):
            if not dots:
                continue
            # The footnote asterisk is part of the printed name ("Great Sword*",
            # "Poleaxe*" — the mark that says "can be thrown"), not of the weapon, and
            # leaving it on silently fails every match against the catalogue.
            name = re.split(r"\s(?=[+\-\d\u2022\ufffd])", text, maxsplit=1)[0]
            name = name.strip(" .*\u2020\u2022\ufffd")
            if not name or len(name) < 3:
                continue
            found.setdefault(name, dots)
    return found


def authored() -> dict[str, int]:
    data = Path(__file__).parent.parent / "exalted_builder" / "data"
    out: dict[str, int] = {}
    for f in ("weapons", "armor"):
        rows = json.loads((data / f"{f}.json").read_text())
        rows = rows if isinstance(rows, list) else list(rows.values())
        for r in rows:
            if r.get("resources_cost"):
                out[r["name"]] = r["resources_cost"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--pages", default="323-335")
    ap.add_argument("--verify", action="store_true",
                    help="diff the parse against the hand-authored costs and exit "
                         "non-zero on any disagreement")
    a = ap.parse_args()
    first, _, last = a.pages.partition("-")
    with pdfplumber.open(a.pdf) as pdf:
        parsed = costed_rows(pdf, int(first), int(last or first))

    if not a.verify:
        for name, dots in sorted(parsed.items()):
            print(f"{dots}  {name}")
        print(f"\n{len(parsed)} costed rows", file=sys.stderr)
        return 0

    hand = authored()
    agree, differ, absent = 0, [], []
    for name, dots in hand.items():
        got = parsed.get(name)
        if got is None:
            absent.append(name)
        elif got == dots:
            agree += 1
        else:
            differ.append(f"{name}: authored {dots}, parsed {got}")
    print(f"agree      {agree}")
    print(f"DISAGREE   {len(differ)}")
    for d in differ:
        print(f"   {d}")
    print(f"not found  {len(absent)}  (a row the parser did not reach, not a conflict)")
    for n in absent:
        print(f"   {n}")
    return 1 if differ else 0


if __name__ == "__main__":
    raise SystemExit(main())
