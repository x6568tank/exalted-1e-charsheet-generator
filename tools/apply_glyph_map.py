"""Apply a glyph map to an extracted book, and print a diff for human review.

Two PDFs in `sources/` carry text that is present but not decodable:

* **Savant and Sorcerer** — the font map resolves no punctuation, so extraction
  emits `(cid:213)` markers (1,754 of them).
* **The Outcaste** — every glyph is reflected (`code = 288 - ord(char)`), so plain
  extraction yields a fat text layer of gibberish.

Both are mechanical, reversible transforms. Neither is a licence to guess: the map
lives in `tools/glyph_maps/*.json` as **data with its evidence attached**, so the
substitutions can be argued with, and this tool prints every distinct substitution in
context so a human can check them before anything is authored.

    python tools/apply_glyph_map.py tools/glyph_maps/savant-and-sorcerer.json \
        --in "images/_extracted/Savant and Sorcerer.md" --out FILE --review

`--review` prints the diff and writes nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

CID = re.compile(r"\(cid:(\d+)\)")


def decode_reflect288(text: str, charmap: dict[str, str]) -> str:
    """Undo `code = 288 - ord(char)`.

    ASCII codes pass through the cipher untouched, which is why the punctuation
    overrides in `charmap` are keyed on raw ASCII and must be applied HERE rather
    than afterwards — after decoding, a passthrough "K" (an apostrophe) is
    indistinguishable from a real letter K that arrived as 0xD5.
    """
    out = []
    for ch in text:
        o = ord(ch)
        key = hex(o)
        if key in charmap:
            out.append(charmap[key])
        elif 128 <= o <= 255:
            out.append(chr(288 - o))
        else:
            out.append(ch)
    return "".join(out)


def split_layout_columns(page: str, min_gutter=3, agree=0.90):
    """Split a poppler `-layout` page into columns, in reading order.

    `-layout` is used because it is the only mode that preserves every character:
    pdfminer drops U+00AD (this cipher's lowercase 's') and plain pdftotext eats the
    line-end ones as hyphenation, so "hamlets are" silently becomes "hamletare". The
    price is that -layout keeps the visual grid, putting both columns on every line —
    so the gutter is found here as a run of character positions blank on virtually
    every line, and the left column is emitted entire, then the right.

    Returns the page unchanged when no corridor is found, so single-column pages and
    full-width tables are left alone.
    """
    rows = [ln for ln in page.split("\n") if ln.strip()]
    if len(rows) < 6:
        return page
    width = max(len(r) for r in rows)
    if width < 60:
        return page
    blank = []
    for x in range(int(width * 0.25), int(width * 0.75)):
        hits = sum(1 for r in rows if x >= len(r) or r[x] == " ")
        if hits >= agree * len(rows):
            blank.append(x)
    if not blank:
        return page
    runs, cur = [], [blank[0]]
    for a, b in zip(blank, blank[1:]):
        if b == a + 1:
            cur.append(b)
        else:
            runs.append(cur)
            cur = [b]
    runs.append(cur)
    best = max(runs, key=len)
    if len(best) < min_gutter:
        return page
    cut = best[0]
    left = [r[:cut].rstrip() for r in rows]
    right = [r[cut:].rstrip() for r in rows]
    if min(sum(bool(x) for x in left), sum(bool(x) for x in right)) < 0.25 * len(rows):
        return page
    return "\n".join([x for x in left if x] + [x for x in right if x])


def decode_bands(text: str, spec: dict) -> str:
    """Undo a subsetted-font glyph order made of descending bands.

    Within a band, `cid + ord(char)` is constant; the bands differ because unused
    glyphs are dropped from the subset and shift every id after them. Anything outside
    the bands belongs to one of the book's display subsets, which have their own orders
    and are left as U+FFFD rather than guessed at.
    """
    bands = [(b["lo"], b["hi"], b["const"]) for b in spec.get("bands", [])]
    singles = {int(k): v["to"] for k, v in spec.get("singles", {}).items()}
    out = []
    for ch in text:
        n = ord(ch)
        if ch in "\n\f":
            out.append(ch)
            continue
        if n in singles:
            out.append(singles[n])
            continue
        for lo, hi, const in bands:
            if lo <= n <= hi:
                out.append(chr(const - n))
                break
        else:
            out.append("\ufffd" if n < 32 else ch)
    return "".join(out)


def load_map(path):
    spec = json.load(open(path))
    cid = {k: v["to"] for k, v in spec.get("cid", {}).items()}
    chars = {k: v["to"] for k, v in spec.get("chars", {}).items()}
    return spec, cid, chars


PAGE_MARK = re.compile(r"<!--PAGE (\d+)-->")


def context(text, needle, n=3, pad=34, pages=None):
    """Windows around each hit, prefixed with the printed page when known.

    A reviewer ruling on an ambiguous glyph needs to open the book at the right page,
    so the page is part of the evidence, not a nicety.
    """
    marks = pages if pages is not None else [
        (m.start(), int(m.group(1))) for m in PAGE_MARK.finditer(text)
    ]

    def page_of(i):
        p = None
        for off, num in marks:
            if off <= i:
                p = num
            else:
                break
        return p

    out, start = [], 0
    for _ in range(n):
        i = text.find(needle, start)
        if i < 0:
            break
        win = text[max(0, i - pad):i + len(needle) + pad].replace("\n", " ")
        out.append(f"p.{page_of(i)}  {win}" if page_of(i) else win)
        start = i + len(needle)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("map")
    ap.add_argument("--in", dest="src", help="extracted .md (cid maps)")
    ap.add_argument("--pdf", help="source pdf (cipher maps; read via poppler)")
    ap.add_argument("--out")
    ap.add_argument("--offset", type=int, default=0,
                    help="cipher maps: pdf page number minus printed book page number")
    ap.add_argument("--review", action="store_true",
                    help="print the substitution report and write nothing")
    a = ap.parse_args()

    spec, cid, chars = load_map(a.map)

    if spec.get("cipher") in ("reflect288", "bands"):
        if not a.pdf:
            print("this map needs --pdf: pdfminer drops U+00AD, so the text must come "
                  "from poppler", file=sys.stderr)
            return 2
        raw = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", a.pdf, "-"],
            capture_output=True).stdout.decode("utf-8", "replace")
        # poppler separates pages with a form feed; turn those into the same
        # <!--PAGE n--> markers the rest of the pipeline uses.
        pages = raw.split("\f")
        out = []
        for i, pg in enumerate(pages):
            if not pg.strip():
                continue
            out.append(f"<!--PAGE {i + 1 - a.offset}-->")
            body = split_layout_columns(pg)
            out.append(decode_reflect288(body, chars)
                       if spec["cipher"] == "reflect288" else decode_bands(body, spec))
        after = "\n".join(out)
        before = raw
    else:
        before = open(a.src).read()
        after = CID.sub(lambda m: cid.get(m.group(1), m.group(0)), before)

    flat = re.sub(r"\s*\n\s*", " ", before)
    print(f"# {spec['book']} — glyph map review\n")
    print(spec["problem"] + "\n")

    table = (list(spec.get("cid", {}).items()) + list(spec.get("chars", {}).items())
             + list(spec.get("singles", {}).items()))
    for code, info in table:
        needle = f"(cid:{code})" if code.isdigit() else None
        print(f"## {code} -> {info['to']!r}   ({info['why']})")
        if "WARNING" in info:
            print(f"   ⚠ {info['WARNING']}")
        for ex in info.get("seen_in", [])[:3]:
            print(f"   evidence: {ex}")
        if needle:
            hits = context(before, needle)
            for h in hits:
                fixed = CID.sub(lambda m: cid.get(m.group(1), m.group(0)), h)
                print(f"     before: …{h}…")
                print(f"      after: …{fixed}…")
        print()

    for code, info in spec.get("unresolved", {}).items():
        n = info.get("count")
        print(f"## {code} — UNRESOLVED, left verbatim"
              + (f"  ({n} occurrences)" if n else ""))
        if info.get("candidates"):
            print(f"   candidates: {' or '.join(repr(c) for c in info['candidates'])}")
        print(f"   {info['note']}")
        # Show the evidence for the UNRESOLVED ones too — they are the entries a human
        # actually has to rule on, so withholding their context defeats the review.
        for ex in info.get("seen_in", []):
            print(f"     …{ex}…")
        for h in context(flat, f"(cid:{code})", n=4):
            print(f"     in text: …{h}…")
        print()

    leftover = sorted(set(CID.findall(after)))
    if leftover:
        print(f"⚠ still unmapped after the pass: {['(cid:%s)' % c for c in leftover]}")

    if a.review:
        print("\n(--review: nothing written)")
        return 0
    if not a.out:
        print("pass --out FILE to write, or --review to inspect", file=sys.stderr)
        return 2
    open(a.out, "w").write(after)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
