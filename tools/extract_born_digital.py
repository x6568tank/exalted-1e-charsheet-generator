"""Extract a page range from a born-digital 1E PDF into page-marked Markdown.

This is the CHEAP leg of the transcription pipeline: where a book has a real text
layer, re-OCRing it through the VLM adds hallucination risk for zero gain (the same
reasoning that governed the artifact guide and the charm trees). Output matches the
form the human's hand-pasted `.md` files already use — `<!--PAGE n-->` markers,
prose and tables verbatim, nothing interpreted.

⚠ Rule 0 is unchanged: transcribe, never interpret. Where two-column reflow or a
broken glyph run makes a passage unreadable without guessing, the extractor emits a
`<!--GARBLED ...-->` marker and leaves the raw text beneath it. **A marked passage is
BLOCKED for authoring** — treat it exactly like a page that is not on disk, and take
it to the human (rule recorded 2026-08-10).

Usage:
    # a section, a set of sections, or the whole book; offset auto-detected
    python tools/extract_born_digital.py <pdf> 36-92 --out FILE
    python tools/extract_born_digital.py <pdf> 58-79,104,113-114 --out FILE
    python tools/extract_born_digital.py <pdf> --out FILE          # whole book

Output goes to `images/_extracted/` — kept apart from the human's hand-pasted `.md`
files because the vetting checkpoint differs: a hand paste was read by a human on the
way in, an extraction has not been.
"""
from __future__ import annotations

import argparse
import collections
import re
import statistics
import warnings

import json

import pdfplumber

warnings.filterwarnings("ignore")

# Running heads render as letter-spaced capitals ("E • T B B E"); footers are bare
# page numbers. Both are furniture, not content.
RUNNING_HEAD = re.compile(r"^[A-Z][A-Z\s••]{4,}$")
BARE_NUMBER = re.compile(r"^\s*\d{1,3}\s*$")
# A run of single characters separated by spaces means the glyph spacing defeated
# word grouping — the text is present but unreadable without guessing.
SPACED_OUT = re.compile(r"(?:\b\w\s){6,}")
# `(cid:213)` is a glyph the PDF's font map does not resolve. Context usually makes it
# obvious (most are apostrophes), but "usually obvious" is exactly the inference this
# pipeline forbids — so they are marked and left in place for the human to rule on.
UNMAPPED_GLYPH = re.compile(r"\(cid:\d+\)")


def make_font_decoder(map_path):
    """Build a per-font (cid:N) decoder from a `bands_per_font` glyph map.

    Each subsetted font in the book is its OWN substitution cipher, so a glyph index
    means nothing without knowing which font drew it. That is why this reads
    pdfplumber words with `fontname` attached rather than plain text: the same
    `(cid:21)` is 't' in the body face and something else in a sidebar face, and one
    global mapping silently garbles every minority font while looking perfect on the
    majority one.
    """
    spec = json.load(open(map_path))
    if spec.get("cipher") != "bands_per_font":
        return None
    table = {}
    for font, b in spec["fonts"].items():
        table[font] = (b["space"], b["lower"], b["upper"], b["punct"])
    singles = {f: {} for f in table}
    for cid, info in spec.get("singles", {}).items():
        for f in info.get("fonts", list(table)):
            singles.setdefault(f, {})[int(cid)] = info["to"]

    def decode(text: str, font: str) -> str:
        # pdfplumber reports the full name with the PDF's random subset prefix
        # ("BFHAOF+ZTR41CA.tmp,Bold"); the map is keyed on the face itself.
        font = font.split("+")[-1]
        band = table.get(font)
        if band is None:
            # An unsolved face. Mark every glyph rather than borrow another font's
            # cipher, which is exactly how 11% of this book came out as fluent noise.
            return re.sub(r"\(cid:\d+\)", "\ufffd", text)
        space, lower, upper, punct = band
        sing = singles.get(font, {})

        def sub(m):
            n = int(m.group(1))
            if n == space:
                return " "
            if n in sing:
                return sing[n]
            if lower - 122 <= n <= lower - 97:
                return chr(lower - n)
            if upper - 90 <= n <= upper - 65:
                return chr(upper - n)
            if punct - 57 <= n <= punct - 40:
                return chr(punct - n)
            return "\ufffd"
        return re.sub(r"\(cid:(\d+)\)", sub, text)

    return decode


def make_decoder(map_path):
    """Build a (cid:N) -> character decoder from a glyph map.

    Used for books whose font subset carries no ToUnicode table, so every glyph
    extracts as a bare index. pdfplumber is the right reader for these: it reports
    `(cid:32)` explicitly, whereas poppler emits raw byte 0x20 for that glyph AND for
    layout padding, so the two become indistinguishable and the text silently fills
    with stray letters.
    """
    if not map_path:
        return None
    spec = json.load(open(map_path))
    bands = [(b["lo"], b["hi"], b["const"]) for b in spec.get("bands", [])]
    singles = {int(k): v["to"] for k, v in spec.get("singles", {}).items()}

    def decode(text: str) -> str:
        def sub(m):
            n = int(m.group(1))
            if n in singles:
                return singles[n]
            for lo, hi, const in bands:
                if lo <= n <= hi:
                    return chr(const - n)
            # A glyph from one of the book's display subsets, which have their own
            # orders. Marked, never guessed.
            return "\ufffd"
        return re.sub(r"\(cid:(\d+)\)", sub, text)

    return decode


def columns(page, min_gutter=8.0):
    """Split a page into columns using a vertical projection profile.

    A two-column layout leaves a band of x where no word overlaps. Scanning for the
    widest such band in the middle third is far more reliable than looking at gaps
    between word centres, which stay dense when the columns are wide.
    """
    words = page.extract_words(use_text_flow=False, extra_attrs=["fontname"])
    if not words:
        return []
    width = page.width
    lo, hi = 0.3 * width, 0.7 * width
    step = 2.0
    profile = []
    x = lo
    while x < hi:
        profile.append((x, sum(1 for w in words if w["x0"] < x < w["x1"])))
        x += step
    if not profile:
        return [words]
    counts = [n for _, n in profile]
    typical = statistics.median(counts)
    if typical < 5:
        return [words]
    # A gutter is where crossings COLLAPSE RELATIVE TO THIS PAGE. An absolute ceiling
    # looks right and is not: on a sparse page the gutter still carries a handful of
    # crossings (a pull-quote, a full-width head), so a fixed cut-off finds nothing,
    # falls back to one column, and interleaves the two columns line by line — which
    # reads as fluent prose and is nonsense. That is how Ruins of Rathess came out
    # welding "…a vast and" to "looting areas. This supplement".
    floor = min(counts)
    if floor > 0.35 * typical:
        return [words]
    ceiling = max(floor + 0.05 * typical, 1.0)
    band = [x for x, n in profile if n <= ceiling]
    if not band:
        return [words]
    runs, cur = [], [band[0]]
    for a, b in zip(band, band[1:]):
        if b - a <= step * 1.5:
            cur.append(b)
        else:
            runs.append(cur)
            cur = [b]
    runs.append(cur)
    best = max(runs, key=len)
    if (best[-1] - best[0]) < min_gutter:
        return [words]
    split = (best[0] + best[-1]) / 2
    # A split that leaves one side nearly empty is not a gutter, it is a margin.
    lo = sum(1 for w in words if (w["x0"] + w["x1"]) / 2 < split)
    if not (0.15 < lo / len(words) < 0.85):
        return [words]
    left = [w for w in words if (w["x0"] + w["x1"]) / 2 < split]
    right = [w for w in words if (w["x0"] + w["x1"]) / 2 >= split]
    return [c for c in (left, right) if c]


def _wtext(w, decode):
    return decode(w["text"], w.get("fontname", "")) if decode else w["text"]


def lines(words, ytol=2.5, decode=None):
    """Group words into visual lines, clustering on the BASELINE.

    Small-caps headings set the initial letter in a larger size, so "COMMON ARCANOI"
    is a big C and a small-caps "OMMON" whose `top` values differ by several points —
    clustering on `top` splits the heading and scrambles it into the next line.
    They share a baseline, so `bottom` reunites them.
    """
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["bottom"], 1), w["x0"])):
        for r in rows:
            if abs(r[0]["bottom"] - w["bottom"]) <= ytol:
                r.append(w)
                break
        else:
            rows.append([w])
    out = []
    for r in sorted(rows, key=lambda r: r[0]["bottom"]):
        r.sort(key=lambda w: w["x0"])
        parts = [_wtext(r[0], decode)]
        for prev, w in zip(r, r[1:]):
            # A small-caps heading renders its large initial as its own object:
            # "D" + "ARK" + "STEED". Rejoin those, and ONLY those. A plain
            # tight-adjacency test is not enough — it also welds real word pairs
            # ("CALLING" + "THE" -> "CALLINGTHE"), which then reads as a wrong Charm
            # name. Requiring the left fragment to be a lone capital and the right to
            # be all-caps keeps the rule to the case it was written for.
            drop_cap = (
                len(prev["text"]) == 1
                and prev["text"].isupper()
                and w["text"].isupper()
                and w["x0"] - prev["x1"] < 1.5
            )
            parts.append(("" if drop_cap else " ") + _wtext(w, decode))
        out.append(("".join(parts).strip(), r[0]["bottom"]))
    return out


def shattered(ln: str) -> bool:
    """True when a line is mostly loose single characters.

    Small-caps headings render each capital as its own text object, so a Charm name
    like MOON'S COLD GLOW extracts as "M ' C G" — the letters that survive are the
    capitals only. Reconstructing the name means guessing, so these are marked, never
    repaired here.
    """
    toks = ln.split()
    if len(toks) < 2:
        return False
    singles = sum(1 for t in toks if len(t) == 1)
    return singles >= 2 and singles / len(toks) >= 0.6


def flow_lines(page, ytol=2.5, decode=None):
    """Lines in the PDF's OWN reading order — what selecting and copying gives you.

    A born-digital PDF stores its text in content-stream order, which for these books
    is the real reading order: down column one, then down column two. Reconstructing
    that from geometry is guesswork that fails on any page whose gutter is untidy.
    Reading the stored order instead is not a heuristic at all.

    Returns None when the stored order is untrustworthy — see `column_switches`.
    """
    words = page.extract_words(use_text_flow=True, extra_attrs=["fontname"])
    if not words:
        return []
    rows, cur = [], [words[0]]
    for w in words[1:]:
        if abs(w["bottom"] - cur[-1]["bottom"]) <= ytol:
            cur.append(w)
        else:
            rows.append(cur)
            cur = [w]
    rows.append(cur)
    out = []
    for r in rows:
        parts = [_wtext(r[0], decode)]
        for prev, w in zip(r, r[1:]):
            drop_cap = (
                len(prev["text"]) == 1
                and prev["text"].isupper()
                and w["text"].isupper()
                and 0 <= w["x0"] - prev["x1"] < 1.5
            )
            parts.append(("" if drop_cap else " ") + _wtext(w, decode))
        out.append(("".join(parts).strip(), r[0]["bottom"]))
    return out


def column_switches(page, split):
    """How often the stored reading order hops between the two columns.

    Correct order stays in one column for a long run, then moves to the other: a
    handful of switches per page. Interleaved order alternates constantly. This is the
    check that tells the two apart without needing a dictionary — and it is why the
    stored order can be trusted rather than assumed.
    """
    words = page.extract_words(use_text_flow=True)
    if not words:
        return 0, 0
    side = [((w["x0"] + w["x1"]) / 2) >= split for w in words]
    return sum(1 for a, b in zip(side, side[1:]) if a != b), len(words)


def looks_two_column(page) -> bool:
    """Independent check for a two-column page, used to catch a failed split.

    Column detection failing is the most dangerous outcome this tool has: the two
    columns interleave into confident, readable nonsense. So the geometry is asked a
    second way — a two-column page has a strong cluster of word left-edges at the
    body margin AND another near the middle, where the second column starts.
    """
    words = page.extract_words(use_text_flow=False, extra_attrs=["fontname"])
    if len(words) < 120:
        return False
    W = page.width
    modes = collections.Counter(round(w["x0"] / 5) * 5 for w in words)
    strong = [x for x, n in modes.items() if n >= 0.04 * len(words)]
    left = [x for x in strong if x < 0.35 * W]
    mid = [x for x in strong if 0.40 * W < x < 0.62 * W]
    return bool(left and mid)


def split_x(page):
    """The gutter x used only to judge reading order, not to reorder anything."""
    cols = columns(page)
    if len(cols) < 2:
        return None
    return max(w["x1"] for w in cols[0])


def page_md(page, decode=None):
    body, flags, glyphs = [], [], 0

    # Prefer the PDF's stored reading order; fall back to geometry only if the stored
    # order proves to be interleaved.
    src, used_flow = None, False
    sx = split_x(page)
    if sx is not None:
        switches, n = column_switches(page, sx)
        if n and switches <= max(6, 0.03 * n):
            src, used_flow = flow_lines(page, decode=decode), True
    if src is None:
        cols = columns(page)
        src = [ln for col in cols for ln in lines(col, decode=decode)]

    cols = columns(page)
    if not used_flow and len(cols) < 2 and looks_two_column(page):
        body.append(
            "<!--COLUMN SPLIT FAILED: this page reads as two columns but could not be "
            "separated, so the lines below may interleave the two. NOT authorable "
            "without a human read.-->"
        )
        flags.append("column split failed")
    top_margin = 0.08 * page.height
    bot_margin = 0.92 * page.height
    for ln, y in src:
        furniture = y < top_margin or y > bot_margin
        if not ln or BARE_NUMBER.match(ln):
            continue
        # Running heads are all-caps too, so pattern alone would also delete every
        # Charm-name heading. Only strip all-caps text sitting in the page margins.
        if furniture and RUNNING_HEAD.match(ln):
            continue
        if shattered(ln) or SPACED_OUT.search(ln):
            flags.append(ln[:60])
            body.append(f"<!--SHATTERED HEADING, name unreadable: {ln!r}-->")
            continue
        glyphs += len(UNMAPPED_GLYPH.findall(ln))
        body.append(ln)
    return body, flags, glyphs


COMMON = (" the ", " and ", " of ", " to ", " a ", " is ", " that ", " with ")


def readable(pdf, probe=12) -> float:
    """Fraction of sampled pages whose text reads as English.

    A PDF can carry a fat text layer that is still unusable: The Outcaste extracts
    ~4,700 chars a page as byte-shifted gibberish ("Ý Ñ Ô Í Ô"). Character count is
    NOT readability, and a run that does not check will happily write a megabyte of
    garbage that looks like a successful transcription.
    """
    mid = len(pdf.pages) // 2
    ok = seen = 0
    for i in range(mid, min(mid + probe, len(pdf.pages))):
        txt = (pdf.pages[i].extract_text() or "").lower()
        if len(txt) < 200:
            continue
        seen += 1
        if sum(txt.count(w) for w in COMMON) >= 5:
            ok += 1
    return (ok / seen) if seen else 0.0


def folio_candidates(raw: str):
    """Page numbers a folio string might mean.

    Several of these books draw the folio two or three times (a layered drop
    shadow), so page 5 extracts as "555" and page 2 as "22". Reading that
    literally throws the offset out by ~20 and silently renumbers the whole
    extraction — which is how Ruins of Rathess came out starting at page 21.
    Emit every plausible reading and let cross-page consensus decide.
    """
    out = {int(raw)}
    for k in (2, 3, 4):
        if len(raw) % k == 0:
            part = raw[: len(raw) // k]
            if part * k == raw:
                out.add(int(part))
    return out


def detect_offset(pdf, probe=40):
    """Find (pdf index - printed page number) by reading printed folios.

    Saves having to work the offset out by hand per book, which is the fiddly part of
    pointing this at a new PDF. Returns the most common delta, or None if the folios
    cannot be read.
    """
    deltas = []
    for i in range(min(probe, len(pdf.pages))):
        txt = pdf.pages[i].extract_text() or ""
        for m in re.finditer(r"^\s*(\d{1,4})\s*$", txt, re.M):
            raw = m.group(1)
            for n in folio_candidates(raw):
                if 1 <= n <= len(pdf.pages) + 60:
                    deltas.append((i + 1) - n)
    if not deltas:
        return None
    # Pick the delta that the most pages agree on. Candidate generation is
    # deliberately generous, so consensus — not any single page — is the signal.
    top, votes = collections.Counter(deltas).most_common(1)[0]
    return top if votes >= 3 else None


def parse_ranges(spec: str):
    """'36-92' or '36-92,104,113-114' -> [(36,92),(104,104),(113,114)]"""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.append((int(a), int(b)))
        else:
            out.append((int(part), int(part)))
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Extract born-digital 1E PDF pages to page-marked Markdown.")
    ap.add_argument("pdf")
    ap.add_argument("pages", nargs="?", default=None,
                    help="book pages: '36-92' or '36-92,104,113-114'. "
                         "Omit (or pass 'all') to take the whole book.")
    ap.add_argument("--offset", type=int, default=None,
                    help="pdf page number minus printed book page number "
                         "(default: detect automatically)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--glyph-map", help="glyph map JSON for a subsetted-font book")
    ap.add_argument("--force", action="store_true",
                    help="extract even if the text layer fails the readability check")
    a = ap.parse_args()

    chunks, marked, done, unmapped = [], [], 0, {}
    with pdfplumber.open(a.pdf) as pdf:
        font_decoder = make_font_decoder(a.glyph_map) if a.glyph_map else None
        decoder = None if font_decoder else make_decoder(a.glyph_map)
        score = 1.0 if (decoder or font_decoder) else readable(pdf)
        if score < 0.5 and not a.force:
            print(f"REFUSING: only {score:.0%} of sampled pages read as English.")
            print("  This PDF's text layer is present but not decodable (a broken font")
            print("  map byte-shifts every character). Extraction would emit convincing")
            print("  garbage. Use the VLM leg on rasterised pages instead, or --force if")
            print("  you have checked the output yourself.")
            return 3
        offset = a.offset
        if offset is None:
            offset = detect_offset(pdf)
            if offset is None:
                print("could not detect the page offset — pass --offset explicitly")
                return 2
            print(f"detected offset {offset:+d} (book page + {offset} = pdf page)")

        if a.pages in (None, "all"):
            ranges = [(1 - offset + 1, len(pdf.pages) - offset)]
        else:
            ranges = parse_ranges(a.pages)

        for first, last in ranges:
            for bookpg in range(first, last + 1):
                idx = bookpg + offset - 1
                if not 0 <= idx < len(pdf.pages):
                    continue
                body, flags, glyphs = page_md(pdf.pages[idx], decode=font_decoder)
                if font_decoder:
                    glyphs = sum(x.count("\ufffd") for x in body)
                if decoder:
                    # Decode BEFORE counting unmapped glyphs: on a subsetted-font book
                    # every character is a (cid:N), so counting first reports the whole
                    # book as damaged.
                    body = [decoder(x) for x in body]
                    glyphs = sum(x.count("\ufffd") for x in body)
                if not body:
                    continue
                if glyphs:
                    unmapped[bookpg] = glyphs
                chunks.append(f"<!--PAGE {bookpg}-->")
                if flags:
                    marked.append(bookpg)
                    chunks.append(
                        f"<!--GARBLED p.{bookpg}: {len(flags)} line(s) with broken glyph "
                        f"spacing; raw text kept below, NOT authorable without a human "
                        f"read-->"
                    )
                chunks += body + [""]
                done += 1

    with open(a.out, "w") as fh:
        fh.write("\n".join(chunks) + "\n")

    span = ", ".join(f"{a_}-{b}" for a_, b in ranges)
    print(f"wrote {a.out}: {done} pages ({span})")
    if marked:
        print(f"⚠ GARBLED markers on {len(set(marked))} page(s): {sorted(set(marked))}")
        print("  These are BLOCKED for authoring — take them to the human.")
    else:
        print("no garbled markers")
    if unmapped:
        total = sum(unmapped.values())
        label = ("glyphs from an UNDECODED display subset" if a.glyph_map
                 else "UNMAPPED GLYPHS ((cid:N))")
        print(f"⚠ {total} {label} across {len(unmapped)} page(s).")
        print("  Left verbatim on purpose. Most are punctuation and the intent is "
              "usually obvious,")
        print("  but substituting them is interpretation — get the human's ruling "
              "before authoring")
        print("  any value from a line containing one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
