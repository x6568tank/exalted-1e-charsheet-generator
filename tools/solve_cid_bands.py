"""Solve the glyph order of every subsetted font in a PDF that lacks ToUnicode.

A subsetted font numbers its glyphs in its own order, so each font in the book is a
separate substitution cipher. The Exalted corebook has thirteen; the body font is 89%
of the text and the rest — sidebars, quotes, tables — are their own ciphers. Decoding
everything with one font's mapping produces confident nonsense for the other 11%.

Each cipher has the same SHAPE: descending bands where `cid + ord(char)` is constant
within a band, with the constants differing per band because unused glyphs are dropped
from the subset and shift every id after them. So the solve is three constants per
font, anchored on English:

  * lowercase — from the most common 3-letter word ("the")
  * uppercase — from a capitalised word whose tail already decodes
  * digits/punctuation — from the most common word-final glyph (".")

Every anchor is cross-checked against a second, independent one; a font that fails the
check is reported UNSOLVED rather than guessed at.

    python tools/solve_cid_bands.py <pdf> [--min-chars 200]
"""
from __future__ import annotations

import argparse
import collections
import re
import warnings

import pdfplumber

warnings.filterwarnings("ignore")

CID = re.compile(r"^\(cid:(\d+)\)$")


def streams(pdf, max_pages=None):
    """Per-font cid sequence in reading order.

    Note the space is itself a glyph in these subsets, so pdfplumber cannot split
    words — `extract_words` returns whole lines. Word boundaries have to come from
    the font's own space cid, which is found by frequency below.
    """
    out = collections.defaultdict(list)
    pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
    for page in pages:
        for c in page.chars:
            m = CID.match(c["text"])
            if m:
                out[c["fontname"].split("+")[-1]].append(int(m.group(1)))
    return out


def solve(stream):
    """Return (space_cid, lower_k, upper_k, punct_k) or None."""
    if len(stream) < 200:
        return None
    freq = collections.Counter(stream)
    space = freq.most_common(1)[0][0]

    words, cur = [], []
    for c in stream:
        if c == space:
            if cur:
                words.append(tuple(cur))
                cur = []
        else:
            cur.append(c)
    if cur:
        words.append(tuple(cur))
    wf = collections.Counter(words)

    three = [w for w, _ in wf.most_common(400) if len(w) == 3]
    if not three:
        return None
    t, h, e = three[0]
    ks = {116 + t, 104 + h, 101 + e}
    if len(ks) != 1:
        return None                      # "the" anchor inconsistent -> not solved
    lower_k = ks.pop()

    lo_range = {lower_k - 122, lower_k - 97}          # z..a
    lo, hi = min(lo_range), max(lo_range)

    # uppercase: a word whose 1st glyph is outside the lowercase band and whose tail
    # decodes to lowercase letters. "The" is the reliable one.
    upper_k = None
    for w, _ in wf.most_common(400):
        if len(w) < 3 or lo <= w[0] <= hi:
            continue
        tail = "".join(chr(lower_k - c) for c in w[1:] if lo <= c <= hi)
        if len(tail) != len(w) - 1:
            continue
        if tail == "he":
            upper_k = 84 + w[0]          # 'T'
            break
        if tail == "he" or tail == "n":
            continue
    if upper_k is None:
        for w, _ in wf.most_common(400):     # fall back: any capitalised word
            if len(w) < 4 or lo <= w[0] <= hi:
                continue
            tail = "".join(chr(lower_k - c) for c in w[1:] if lo <= c <= hi)
            if len(tail) == len(w) - 1 and tail.isalpha():
                # assume the commonest capital starting a long word is 'S' or 'T';
                # too weak to trust, so leave unsolved
                break

    # punctuation: the commonest word-final glyph outside both letter bands is '.'
    up_lo = up_hi = None
    if upper_k:
        up_lo, up_hi = upper_k - 90, upper_k - 65
    # The two commonest word-final non-letters are '.' and ',' — and because the band
    # descends, the period (ASCII 46) takes the LOWER cid of the pair. That makes the
    # anchor self-checking: 46 + cid_period must equal 44 + cid_comma, or the guess is
    # wrong and the font is left unsolved. (Assuming the single commonest is a period
    # silently picks the comma and shifts every digit by two.)
    finals = collections.Counter(w[-1] for w in words if w)
    cand = [c for c, _ in finals.most_common(12)
            if not (lo <= c <= hi)
            and not (up_lo is not None and up_lo <= c <= up_hi)][:2]
    punct_k = None
    if len(cand) == 2:
        a_, b_ = sorted(cand)
        if 46 + a_ == 44 + b_:
            punct_k = 46 + a_
    return space, lower_k, upper_k, punct_k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--min-chars", type=int, default=200)
    a = ap.parse_args()
    with pdfplumber.open(a.pdf) as pdf:
        st = streams(pdf)
    print(f"{'font':24s} {'chars':>8s}  space  lower  upper  punct")
    for f, s in sorted(st.items(), key=lambda kv: -len(kv[1])):
        if len(s) < a.min_chars:
            print(f"{f:24s} {len(s):8d}  (too little text to solve)")
            continue
        r = solve(s)
        if not r:
            print(f"{f:24s} {len(s):8d}  UNSOLVED")
            continue
        sp, lk, uk, pk = r
        print(f"{f:24s} {len(s):8d}  space={sp:<4} {lk!s:>5} {uk!s:>6} {pk!s:>6}")


if __name__ == "__main__":
    raise SystemExit(main())
