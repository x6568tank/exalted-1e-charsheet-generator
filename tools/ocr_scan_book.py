"""OCR a scan-only 1E PDF into page-marked Markdown.

The EXPENSIVE leg of the transcription pipeline, for books whose PDF has no text
layer at all (`pdftotext` returns one form feed per page). Renders each page with
pdftoppm and reads it with tesseract, emitting the same shape the born-digital
extractor and the human's hand-pasted `.md` files use: `<!--PAGE n-->` markers in
PRINTED page numbers, prose verbatim, nothing interpreted.

Usage:
    python tools/ocr_scan_book.py <pdf> --offset -3 --out FILE
    python tools/ocr_scan_book.py <pdf> --offset -3 --pages 36-92 --out FILE

⚠ Rule 0 is unchanged: transcribe, never interpret. Lines the OCR could not resolve
are left in place under a `<!--GARBLED ...-->` marker; a marked passage is BLOCKED
for authoring, exactly like a page that is not on disk.

⚠ **OCR cannot render the `•` glyph** — it comes out as `®`, `e`, `#`, `¢` and more.
Every dot rating in this output is UNRELIABLE and must be read off the page image
(re-crop at 400 dpi if uncertain). Same rule as the phase-2 scan.

⚠ The offset is per-book and must be confirmed against a printed folio before the
run; it is not guessable. Sidereals is -3, Scavenger Sons was 0, most books here
are +1.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Running heads render as letter-spaced small caps ("EXALTED • THE SIDEREALS",
# "CHAPTER ONE • YU-SHAN") over the page's border art; footers are a bare folio.
# Both are furniture, not content.
RUNNING_HEAD = re.compile(r"^[A-Z][A-Za-z\s.•*®¢|]{3,60}$")
BARE_NUMBER = re.compile(r"^\s*[|\[\(]?\s*\d{1,3}\s*[|\]\)]?\s*$")
# Border art OCRs as a soup of punctuation and stray letters. A line that is mostly
# non-word characters carries no text.
def _is_noise(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 3:
        return True
    word = sum(c.isalnum() for c in stripped)
    return word / len(stripped) < 0.55

# A run of isolated single characters means the scan defeated word grouping — the
# text is present but unreadable without guessing.
SPACED_OUT = re.compile(r"(?:\b\w\s){6,}")


def parse_pages(spec: str, last: int) -> list[int]:
    """Turn "36-92,104,113-114" into a sorted page list; None means the whole book."""
    if not spec:
        return list(range(1, last + 1))
    out: set[int] = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def page_count(pdf: Path) -> int:
    """Read the page count off pdfinfo."""
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    for line in info.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    raise SystemExit(f"pdfinfo gave no page count for {pdf}")


def ocr_page(pdf: Path, page: int, dpi: int, workdir: Path) -> str:
    """Render one PDF page to PNG and return tesseract's raw text for it."""
    stem = workdir / f"p{page}"
    subprocess.run(
        ["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page), "-png",
         str(pdf), str(stem)],
        check=True, capture_output=True,
    )
    pngs = sorted(workdir.glob(f"p{page}-*.png"))
    if not pngs:
        return ""
    try:
        result = subprocess.run(
            ["tesseract", str(pngs[0]), "-", "--psm", "3"],
            capture_output=True, text=True,
        )
        return result.stdout
    finally:
        for png in pngs:
            png.unlink()


def clean(raw: str) -> tuple[list[str], list[str]]:
    """Strip furniture and noise from one page's OCR; return (lines, garbled notes).

    Drops border-art soup, the running head and the bare folio. Lines whose word
    grouping collapsed are KEPT and reported, never silently dropped.
    """
    lines = raw.splitlines()
    kept: list[str] = []
    garbled: list[str] = []
    for line in lines:
        if not line.strip():
            kept.append("")
            continue
        if _is_noise(line):
            continue
        if BARE_NUMBER.match(line):
            continue
        if SPACED_OUT.search(line):
            garbled.append(line.strip())
        kept.append(line.rstrip())
    # The running head survives the noise filter on a clean scan; it is always in the
    # first few kept lines and always matches the small-caps shape.
    for i, line in enumerate(kept[:4]):
        if line and RUNNING_HEAD.match(line) and ("•" in line or "*" in line or "®" in line):
            kept.pop(i)
            break
    # Collapse the blank runs left behind by the drops.
    out: list[str] = []
    for line in kept:
        if not line and (not out or not out[-1]):
            continue
        out.append(line)
    while out and not out[-1]:
        out.pop()
    return out, garbled


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--offset", type=int, required=True,
                    help="printed = pdf + offset; CONFIRM against a folio first")
    ap.add_argument("--pages", default="", help='e.g. "36-92,104"; default whole book')
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    last = page_count(args.pdf)
    pages = parse_pages(args.pages, last)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp, args.out.open("w") as fh:
        workdir = Path(tmp)
        fh.write(f"<!-- OCR of {args.pdf.name} at {args.dpi} dpi. "
                 f"Page markers are PRINTED pages (pdf {args.offset:+d}). "
                 f"Dot ratings are unreliable - read them off the page image. -->\n\n")
        total_garbled = 0
        for n, page in enumerate(pages, 1):
            raw = ocr_page(args.pdf, page, args.dpi, workdir)
            lines, garbled = clean(raw)
            fh.write(f"<!--PAGE {page + args.offset}-->\n")
            if garbled:
                total_garbled += len(garbled)
                fh.write(f"<!--GARBLED {len(garbled)} line(s) on this page; "
                         f"word grouping collapsed - read off the page image-->\n")
            fh.write("\n".join(lines))
            fh.write("\n\n")
            fh.flush()
            print(f"[{n}/{len(pages)}] pdf {page} -> printed {page + args.offset} "
                  f"({len(lines)} lines)", file=sys.stderr, flush=True)
    print(f"done: {args.out} ({total_garbled} garbled lines)", file=sys.stderr)


if __name__ == "__main__":
    main()
