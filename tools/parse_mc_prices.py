#!/usr/bin/env python3
"""Parse the Manacle and Coin price tables (pp.123-125) column-aware.

The book's text layer is clean — real `•` characters, no cipher — so the ONLY problem is
geometry: these are two-column pages whose tables sit in both columns, and the generic
extractor interleaves them. On p.125 that produced names like "Burning incense Healing"
and "Created walkaway 7 obols 90 dinars 2 minae 400 dinars Item Resources Jade Silver",
which is the column-scramble the workflow says to flag rather than guess at.

The layout, measured rather than assumed (`--geometry` prints it):

    LEFT  column: name @104   dots @184   jade @238   silver @283
    RIGHT column: name @339   dots @420   jade @474   silver @519

so a column split at x≈330 separates them, and within a column each field has its own
band.

⚠ **Distinguishing a wrapped NAME from a section HEADING is the whole difficulty**, and
the font does not do it: "Healing" and "Talismans" are italic but "Offerings and Prayers"
is not. The VERTICAL RHYTHM does — a wrapped second line sits ~6pt below its row, a
heading ~9pt below the row above it — and a no-dots line can only continue a row if the
previous line in that column actually was one. Both conditions are required; either
alone misreads the page.

Verified by re-parsing p.123 and diffing against `data/gear.json`, which was authored
from that page's clean single-column extraction: `--verify` must report 43/43.

Usage:
    parse_mc_prices.py <pdf> --verify        # re-parse p.123, diff against gear.json
    parse_mc_prices.py <pdf> --pages 125     # dump a page's rows as JSON
    parse_mc_prices.py <pdf> --geometry 125  # print the measured column bands
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import pdfplumber

OFFSET = 1                                 # book page + 1 = pdf page
COLUMN_SPLIT = 330.0                       # measured; see --geometry
# Measured on both pages, and identical on each: a wrapped second line sits +12.0 below
# its row, while a new row — or a section heading — sits +18.0. The threshold goes
# between them.
#
# ⚠ 7.0 here was wrong and looked plausible: it came from an exploratory dump that had
# grouped lines by `round(top/2)`, so every gap in it was HALVED. The parser then joined
# no continuations at all and 27 of 43 rows silently lost their second line.
CONTINUATION_GAP = 14.0


def _lines(page, x_lo: float, x_hi: float):
    """Lines of this column, as (top, [chars]) sorted down the page."""
    rows = collections.defaultdict(list)
    for c in page.chars:
        if x_lo <= c["x0"] < x_hi:
            rows[round(c["top"], 1)].append(c)
    return [(top, sorted(rows[top], key=lambda c: c["x0"])) for top in sorted(rows)]


def _text(chars) -> str:
    return "".join(c["text"] for c in chars).strip()


def parse_column(page, x_lo: float, x_hi: float) -> list[dict]:
    """Every priced row in one column of one page.

    The state machine is three lines long and each branch was a bug first:

    * **A line in a continuation slot continues the open row, WHATEVER is on it.** The
      test is position, not content — "(rating • to •••)" is the second line of "Erect a
      Manse" and it carries dots, so a parser that checks for dots first invents a row
      called "(rating" and loses the real one.
    * **Continuations CHAIN.** "Crew and provender / for a ship for a / month" is three
      lines; closing the row after the first continuation dropped the third line of
      every long name.
    * **A heading closes the open row**, so the row printed under it does not get
      swallowed as a continuation — headings and following rows are both +12 apart.
    """
    out: list[dict] = []
    open_row: dict | None = None
    last_top: float | None = None
    for top, chars in _lines(page, x_lo, x_hi):
        text = _text(chars)
        # The running head ("EXALTED • MANACLE AND COIN") carries a bullet and would
        # otherwise parse as a one-dot row.
        if not text or top < 100:
            continue
        if (open_row is not None and last_top is not None
                and top - last_top <= CONTINUATION_GAP):
            open_row["name"] += " " + text
            last_top = top
            continue

        dots = [c for c in chars if c["text"] == "•"]
        last_top = top
        if not dots:
            open_row = None                # a heading, or the Item/Resources header
            continue
        first = min(c["x0"] for c in dots)
        last = max(c["x1"] for c in dots)
        name = _text([c for c in chars if c["x1"] <= first])
        # Jade and silver are their own bands; joined blind they read "1 obol8
        # dinars". Split on the widest gap right of the dots.
        tail = [c for c in chars if c["x0"] >= last]
        cash = ""
        if tail:
            gaps = [(tail[i + 1]["x0"] - tail[i]["x1"], i)
                    for i in range(len(tail) - 1)]
            widest, at = max(gaps, default=(0.0, -1))
            cash = (f"{_text(tail[:at + 1])} / {_text(tail[at + 1:])}"
                    if widest > 4 else _text(tail))
        open_row = {"name": name, "dots": len(dots), "cash": cash}
        out.append(open_row)
    return out


HEADER = re.compile(r"^(Item|Resources|Jade|Silver)\b")


def parse_page(pdf, book_page: int) -> list[dict]:
    page = pdf.pages[book_page + OFFSET - 1]
    rows = (parse_column(page, 0, COLUMN_SPLIT)
            + parse_column(page, COLUMN_SPLIT, page.width))
    return [r for r in rows if r["name"] and not HEADER.match(r["name"])]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--pages", default="125")
    ap.add_argument("--geometry", type=int)
    ap.add_argument("--verify", action="store_true",
                    help="re-parse p.123 and diff against data/gear.json")
    a = ap.parse_args()

    with pdfplumber.open(a.pdf) as pdf:
        if a.geometry:
            page = pdf.pages[a.geometry + OFFSET - 1]
            xs = collections.Counter(round(c["x0"] / 5) * 5 for c in page.chars)
            for x in sorted(xs):
                print(f"  x~{x:4}  {xs[x]:4}")
            return 0

        if a.verify:
            parsed = {r["name"]: r["dots"] for r in parse_page(pdf, 123)}
            data = Path(__file__).parent.parent / "exalted_builder" / "data" / "gear.json"
            authored = {e["name"]: e["resources_cost"]
                        for e in json.loads(data.read_text())}
            agree = [n for n, v in authored.items() if parsed.get(n) == v]
            differ = [(n, v, parsed.get(n)) for n, v in authored.items()
                      if parsed.get(n) != v]
            print(f"agree     {len(agree)} / {len(authored)}")
            for n, was, now in differ:
                print(f"  DIFFER  {n}: gear.json {was}, parsed {now}")
            extra = [n for n in parsed if n not in authored]
            for n in extra:
                print(f"  EXTRA   {n} = {parsed[n]}")
            return 1 if differ or extra else 0

        for pg in [int(x) for x in a.pages.split(",")]:
            for r in parse_page(pdf, pg):
                print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
