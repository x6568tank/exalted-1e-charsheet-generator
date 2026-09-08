"""Turn a raw `images/_extracted/` extraction into prose a GM-helper LLM can read.

Input:  a page-marked extraction from `extract_born_digital.py` or `ocr_scan_book.py`
Output: a markdown reference with headings, joined words and recovered tables

    python tools/build_gm_reference.py                        # Abyssals, the default
    python tools/build_gm_reference.py --book dragon-blooded
    python tools/build_gm_reference.py --book X --src A --out B

⚠ Everything book-specific lives in `BOOKS`, keyed by `--book`. `recovered` is keyed
by PRINTED PAGE NUMBER, so running one book's entry over another book's extraction
splices the wrong tables in silently — pass `--book`, not just `--src`.

⚠ This is a READABILITY derivation, not an authoring source. Values written into
`data/` come from the raw extraction or the page, never from the output here. Every
transform is letter-case, spacing or whitespace only -- no numeral is ever altered,
which `--verify` re-checks page by page against the source.

The extractor DELETES a line whose glyph spacing it cannot trust, leaving only a
`<!--SHATTERED HEADING-->` comment. Small-caps headings trip that test, so on this
book 36 entries had no name at all in the body text until they were restored here.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

# The dictionary disambiguates a merge ("V EIL" -> VEIL) from an article that must
# stay apart ("A UNIFIED"). It is not installed everywhere, and the project's two
# machines differ, so its absence degrades the merge rather than killing the run.
DICT_PATH = pathlib.Path("/usr/share/dict/words")
if DICT_PATH.exists():
    WORDS = {w.strip().upper() for w in DICT_PATH.open() if len(w.strip()) > 1}
else:
    WORDS = set()
    print(
        f"⚠ {DICT_PATH} not found — small-caps headings will be merged without the\n"
        "  word check, so an article may be glued on ('AUNIFIED FRONT'). Prose and\n"
        "  every numeral are unaffected. Install `words` for a clean run.",
        file=sys.stderr,
    )

STAT_KEYS = ("Cost:", "Duration:", "Type:", "Minimum ", "Prerequisite Charms:")


def unshatter(text: str) -> str:
    """Rejoin letterspaced small-caps runs ("V EIL" -> "VEIL").

    White Wolf sets headings in small caps, so each capital extracts as its own text
    object. A single capital followed by an uppercase run is merged UNLESS the merged
    form is not a dictionary word while the run alone is one -- that is the "A UNIFIED
    FRONT" case, where the lone capital is the article and must stay separate.
    """

    def merge(m: re.Match) -> str:
        head, run = m.group(1), m.group(2)
        joined = head + run
        if joined not in WORDS and run in WORDS:
            return m.group(0)
        return joined

    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\b([A-Z]) ([A-Z]{2,})", merge, text)
    text = re.sub(r"([A-Z]) -([A-Z])", r"\1-\2", text)
    text = re.sub(r"\s+’\s*(?=[A-Za-z])", "’", text)
    return text


SMALL = {"a", "an", "and", "the", "of", "or", "to", "in", "on", "at", "for",
         "from", "by", "with", "as", "is", "not", "into", "upon", "per"}


def smart_title(s: str) -> str:
    """Title-case a heading, leaving short function words lowercase.

    `str.title()` yields "With The Anchor Of Flesh" and breaks "Varan’S"; this keeps
    the first and last word capitalised, lowercases SMALL words between them, and
    never splits on an apostrophe.
    """
    parts = s.split()
    out = []
    for i, w in enumerate(parts):
        core = w.lower()
        if 0 < i < len(parts) - 1 and core in SMALL:
            out.append(core)
        else:
            out.append(core[:1].upper() + core[1:])
    return " ".join(out)


def tidy(text: str) -> str:
    """Spacing repairs that do not touch any numeral."""
    text = re.sub(r"\bMinimum([A-Z])", r"Minimum \1", text)
    text = re.sub(r"\bPrerequisite([A-Z])", r"Prerequisite \1", text)
    text = re.sub(r"(\w)\s+\.", r"\1.", text)
    return text


def dehyphenate(lines: list[str]) -> list[str]:
    """Join a word broken across a line break ("nec-" + "romancers")."""
    out: list[str] = []
    for ln in lines:
        if out and out[-1].endswith("-") and re.match(r"^[a-z]", ln):
            out[-1] = out[-1][:-1] + ln
        else:
            out.append(ln)
    return out


# The seven pages the extractor refused, transcribed by reading the rendered PNG at
# 300 dpi. Each is a boxed table (or, for p.161, a Charm-tree diagram) whose columns
# interleaved in the text layer.
RECOVERED = {
    "33": """#### Table: Burnt Offerings (p.33)

| Resources Cost of Sacrifice* | Benefits Imparted |
|---|---|
| X | 1 Essence |
| • | 3 Essence |
| •• | 5 Essence |
| ••• | 10 Essence / 1 Willpower** |
| •••• | 20 Essence / 2 Willpower** |
| ••••• | 30 Essence / 3 Willpower** |

\\* Replica goods typically cost less, or can be made by family members for little
cost, but are less effective. Subtract • from the Resources worth of the real object,
but the cost of the replicas is generally •• less.
\\*\\* Each Willpower drains 10 Essence from the token.""",
    "161": """#### Diagram: Brawl 2 Charm tree (p.161)

Image-only content — reconstructed from the page render, arrows read prerequisite → dependent:

- Ravaging Strike → Scouring Erosion Method
- Ravaging Strike → Lashing Tempest Attack
- Lashing Tempest Attack → Bone-Shattering Blow
- Lashing Tempest Attack → Five Knife Strike
- Five Knife Strike → Blood-Drinking Palm
- Blood-Drinking Palm → Writhing Blood Chain Technique""",
    "242": """#### Table: Taste the Demon Wind (p.242)

| Number of Successes | Range |
|---|---|
| 1 | 100 yards |
| 2 | 250 yards |
| 3 | 500 meters |
| 4 | 1 mile |
| 5 | 5 miles |

⚠ "500 meters" at 3 is as printed — the column is otherwise in yards.

#### Table: Call the Ravening Hound (p.242)

| Number of Successes | Range | Maximum Number of Hungry Ghosts Called |
|---|---|---|
| 1 | 100 yards | 1 |
| 2 | 250 yards | 2 |
| 3 | 500 yards | 4 |
| 4 | 1 mile | 8 |
| 5 | 5 miles | 20 |""",
    "243": """#### Table: Tame the Wicked Appetite (p.243)

| Number of Successes | Number of Hungry Ghosts Tamed |
|---|---|
| 1 | 1 |
| 2 | 3 |
| 3 | 5 |
| 4 | 10 |
| 5 | 20 |""",
    "244": """#### Table: Command the Hungry Devil (p.244)

| Number of Successes | Number of Hungry Ghosts Commanded |
|---|---|
| 1 | 1 |
| 2 | 3 |
| 3 | 5 |
| 4 | 10 |
| 5 | 20 |""",
    "255": """#### Table: Essence-Containing Gem capacity (p.255)

| Gem Rating | Capacity |
|---|---|
| • | 3 motes |
| •• | 7 motes |
| ••• | 15 motes |
| •••• | 35 motes |
| ••••• | 75 motes |""",
    "283": """#### Table: Ghostly Experience Costs (p.283)

| Trait Increase | Cost |
|---|---|
| Attribute | current rating x 8 |
| Favored Ability | (current rating x 4) - 1 |
| Ability | current rating x 4 |
| Essence | current rating x 12 |
| Virtue | current rating x 6 |
| Willpower | current rating x 5 |
| Fetter | current rating x 3 |

| New Trait | Cost |
|---|---|
| Ability | 12 |
| Arcanos | 14 |
| Invent New Arcanos | 20 |
| New Fetter | 20 |
| New Fetter (Relentless Hunter) | 15 |

| Special | Cost |
|---|---|
| Shift Passion | 20 |
| Shift Fetter | 10 |

#### Table: Training Times (p.283)

⚠ Reference only — training times are out of scope for the builder (standing bar).

| Trait | Time Required |
|---|---|
| Increase Attribute | current rating x 3 months |
| New Ability | 12 weeks |
| Increase Ability | current rating x 2 weeks |
| Arcanos | 8 weeks |
| Invent New Arcanos | 32 weeks |
| Essence | current rating x 2 months* |
| Virtue | current rating x 10 weeks |
| Willpower | current rating x 6 weeks |
| New Fetter | 1 year** |
| New Fetter (Relentless Hunter) | 6 months** |
| Increase Fetter | 6 months** |
| Shift Passion (special) | 6 months/dot |
| Shift Fetter (special) | 1 year/dot** |

\\* Training required to advance to Essence 3 or higher. Cannot exceed Essence 5.
\\*\\* Total dots of Fetters cannot exceed Willpower + Essence.""",
}

NO_TEXT = {1, 8, 14, 74, 118, 128, 154, 230, 262, 289}

HEADER = """# Exalted 1e — The Abyssals: GM reference

Derived from `images/_extracted/Abyssals.md` (born-digital extraction of
*Exalted: The Abyssals*, WW8813) by `tools/`-adjacent script; see the provenance note
at the foot. Printed page numbers are preserved as `<!--PAGE n-->` markers and in the
`p.N` suffix on each recovered table, so anything here can be cited back to the book.

⚠ **This file is a READING aid, not an authoring source.** Values written into
`data/` must come from the raw extraction or the page itself, not from here.

---
"""

FOOTER = """
---

## Provenance

- **Source:** `sources/Exalt Books/Exalted - WW - The Abyssals (OCR) [WW8813].pdf`,
  291 pdf pages. Despite the `(OCR)` in the filename the book has a clean, genuine
  text layer (0.97 English rate, zero unresolved `(cid:N)` glyphs outside the front
  matter), so no glyph cipher was needed.
- **Raw extraction:** `images/_extracted/Abyssals.md`, produced by
  `tools/extract_born_digital.py`, offset `+1` (book page + 1 = pdf page). That file
  is authoritative and unmodified.
- **Offset verified** against the book's own printed folio: the page carrying Stolen
  Wax Discipline prints 237.
- **Transforms applied here** (readability only, no numeral altered): letterspaced
  small-caps headings rejoined; line-break hyphens closed; jammed stat keys
  (`MinimumEssence` → `Minimum Essence`) spaced; stray apostrophe spacing closed.
- **Seven blocked pages recovered** by rendering the page at 300 dpi and reading it:
  pp. 33, 161, 242, 243, 244, 255, 283. Renders are in
  `images/Abyssal/blocked-tables/`.
- **Ten pages have no text layer** (full-page art or chapter plates): 1, 8, 14, 74,
  118, 128, 154, 230, 262, 289.

⚠ **Charm-tree diagrams are image-only.** p.161 is one (recovered above); the book
contains others that this extraction cannot see as structure. Treat any Charm
prerequisite graph here as incomplete.
"""

DB_HEADER = """# Exalted 1e — The Dragon-Blooded: GM reference

Derived from `images/_extracted/DragonBlooded.md` (a tesseract OCR of the scan-only
*Exalted: The Dragon-Blooded*) by `tools/build_gm_reference.py`; see the provenance
note at the foot. Printed page numbers are preserved as `<!--PAGE n-->` markers, so
anything here can be cited back to the book.

⚠ **This file is a READING aid, not an authoring source.** Values written into
`data/` must come from the page itself, not from here — and on this book that bar is
higher than usual, because the source is OCR of a scan rather than a text layer.

⚠ **Every dot rating here is UNRELIABLE.** OCR cannot render the `•` glyph; it comes
out as `®`, `e`, `#`, `¢` and more. Read any rating off the page image at 400 dpi.

---
"""

DB_FOOTER = """
---

## Provenance

- **Source:** `sources/Exalt Books/Exalted - The Dragon-Blooded.pdf`, 297 pdf pages.
  A pure scan — `Acrobat 4.05 Scan Plug-in`, no text layer at all, so `pdftotext`
  returns nothing on every page.
- **Raw extraction:** `images/_extracted/DragonBlooded.md`, produced by
  `tools/ocr_scan_book.py` at 300 dpi, offset `-1` (printed = pdf - 1). That file is
  authoritative and unmodified.
- **Offset verified** against a known citation: Air Dragon Style prints 243
  (`martial_arts_styles.json`) and OCRs on pdf page 244.
- **Transforms applied here** (readability only, no numeral altered): letterspaced
  small-caps headings rejoined; line-break hyphens closed; jammed stat keys
  (`MinimumEssence` → `Minimum Essence`) spaced; stray apostrophe spacing closed.
- **No tables have been hand-recovered on this book.** A boxed table that OCR
  scrambled is still scrambled here; render the page and read it.

⚠ **Charm-tree diagrams are image-only** and this extraction cannot see them as
structure. Treat any Charm prerequisite graph here as incomplete.
"""

# Per-book settings. ⚠ `recovered` is keyed by PRINTED PAGE NUMBER, so pointing the
# Abyssals entry at another book's extraction would splice Abyssals' tables onto
# whatever happens to be page 242 there. Every book gets its own entry.
BOOKS = {
    "abyssals": {
        "src": pathlib.Path("images/_extracted/Abyssals.md"),
        "out": pathlib.Path("docs/reference/abyssals-gm-reference.md"),
        "header": HEADER,
        "footer": FOOTER,
        "recovered": RECOVERED,
    },
    "dragon-blooded": {
        "src": pathlib.Path("images/_extracted/DragonBlooded.md"),
        "out": pathlib.Path("docs/reference/dragonblooded-gm-reference.md"),
        "header": DB_HEADER,
        "footer": DB_FOOTER,
        "recovered": {},
    },
}


def verify(raw: str, built: str) -> int:
    """Re-derive the no-numeral-changed guarantee, page by page. Returns a exit code.

    Compares the digit sequence of every source page against the same page in the
    output, after stripping the tool comments the build removes and skipping pages
    where a recovered table deliberately adds numbers. Any drift means a transform
    touched a cost, rating or minimum, which is the one thing it must never do.
    """
    def by_page(t):
        return dict(re.findall(r"<!--PAGE (\d+)-->\n(.*?)(?=<!--PAGE |\Z)", t, re.S))

    src, out = by_page(raw), by_page(built)
    last = max(src, key=lambda n: int(n))
    drift = []
    for num, body in src.items():
        # The footer lands in the final page's slice, so its numbers are expected.
        if num in RECOVERED or num == last:
            continue
        body = re.sub(r"<!--SHATTERED HEADING, name unreadable: '(.*)'-->", r"\1", body)
        body = re.sub(r"<!--GARBLED.*?-->", "", body)
        if re.findall(r"\d+", body) != re.findall(r"\d+", out.get(num, "")):
            drift.append(num)

    checked = len(src) - len(set(RECOVERED) & set(src)) - 1
    if drift:
        print(f"✗ numeral drift on {len(drift)} page(s): {sorted(drift, key=int)}")
        return 1
    print(f"✓ no numeral drift across {checked} pages")

    rw = collections.Counter(re.findall(r"[a-z]{4,}", raw.lower()))
    nw = collections.Counter(re.findall(r"[a-z]{4,}", built.lower()))
    lost = sum(c - nw[w] for w, c in rw.items() if nw[w] < c)
    print(f"  word retention: {1 - lost / sum(rw.values()):.2%} "
          "(losses are hyphen-joins, de-jamming and removed tool comments)")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book", choices=sorted(BOOKS), default="abyssals",
                    help="selects the header, footer and recovered tables")
    ap.add_argument("--src", type=pathlib.Path, default=None)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--verify", action="store_true",
                    help="after writing, re-check that no numeral changed")
    args = ap.parse_args()

    book = BOOKS[args.book]
    global SRC, OUT, RECOVERED, HEADER, FOOTER
    SRC = args.src or book["src"]
    OUT = args.out or book["out"]
    RECOVERED, HEADER, FOOTER = book["recovered"], book["header"], book["footer"]
    raw = SRC.read_text()
    pages = re.findall(r"<!--PAGE (\d+)-->\n(.*?)(?=<!--PAGE |\Z)", raw, re.S)

    chunks = [HEADER]
    for num, body in pages:
        lines = body.split("\n")
        kept: list[str] = []
        for ln in lines:
            if ln.startswith("<!--GARBLED"):
                continue
            m = re.match(r"<!--SHATTERED HEADING, name unreadable: '(.*)'-->", ln)
            if m:
                name = tidy(unshatter(m.group(1))).strip()
                if re.fullmatch(r"[^A-Za-z]*", name):
                    continue  # dot-rows, index furniture, the URL
                if not any(len(tok) >= 3 for tok in re.findall(r"[A-Za-z]+", name)):
                    continue  # decorative art lettering, e.g. p.161's "B r a"/"w l 2"
                if num in RECOVERED:
                    continue  # superseded by the transcribed table appended below
                kept.append(f"\n### {smart_title(name)}\n")
                continue
            kept.append(ln)

        kept = dehyphenate(kept)
        text = tidy(unshatter("\n".join(kept)))

        # Promote all-caps standalone lines to headings so the doc is navigable.
        # A heading that wrapped onto a second line is TWO all-caps lines in a row;
        # promoting each separately splits names ("The Lover Clad in the" /
        # "Raiment of Tears"), so consecutive qualifying lines are joined first.
        def is_heading(s: str) -> bool:
            return bool(
                s
                and len(s) < 60
                and re.fullmatch(r"[A-Z0-9’'\-—:,\.\(\)\? ]+", s)
                and re.search(r"[A-Z]{3}", s)
                and not s.startswith(STAT_KEYS)
                and not re.fullmatch(r"[^A-Za-z]+", s)
            )

        src_lines = text.split("\n")
        out_lines: list[str] = []
        i = 0
        while i < len(src_lines):
            s = src_lines[i].strip()
            if is_heading(s):
                run = [s]
                j = i + 1
                while j < len(src_lines) and is_heading(src_lines[j].strip()):
                    run.append(src_lines[j].strip())
                    j += 1
                out_lines.append(f"\n### {smart_title(' '.join(run))}\n")
                i = j
            else:
                out_lines.append(src_lines[i])
                i += 1
        text = "\n".join(out_lines)

        chunks.append(f"<!--PAGE {num}-->\n")
        chunks.append(text.rstrip() + "\n")
        if num in RECOVERED:
            chunks.append("\n" + RECOVERED[num] + "\n")
        chunks.append("\n")

    built = "".join(chunks) + FOOTER
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(built)
    print(f"wrote {OUT}: {len(pages)} pages")

    if args.verify:
        raise SystemExit(verify(raw, built))


if __name__ == "__main__":
    main()
