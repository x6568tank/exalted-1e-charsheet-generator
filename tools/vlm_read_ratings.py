"""Read artifact rating dots off page images with the local VLM.

Why this exists: The Outcaste's PDF prints its artifact headings as
`(ARTIFACT •••)`, and the dots are NOT in the text layer — poppler renders the
heading as `(ARTIFACT )` with nothing between the parens. Every other value in that
book decodes fine; the ratings alone need eyes. A rating is spent against the
Artifact Background budget, so guessing one is not an option.

Scope is deliberately tiny: name + dots, one page at a time, nothing else. The model
is told to transcribe and to write `???` rather than infer — the same Rule 0 that
governs `tools/VLM_TRANSCRIPTION_PROMPT.md`.

    python tools/vlm_read_ratings.py --pdf <pdf> --pages 38,51,52 --offset 2 \
        --out ratings.json
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

MODEL = "qwen3-vl:8b-instruct"
OLLAMA = "http://localhost:11434/api/generate"

PROMPT = """You are reading one scanned page from a tabletop RPG rulebook.

Find every ARTIFACT ENTRY HEADING on this page. They look like:

    FRESHWATER PEARLS (ARTIFACT ***)
    BONE HARPOON (ARTIFACT **)
    STORM-WARDING PARASOL (ARTIFACT *, ** FOR THE LARGE VERSION)

where the * characters are printed as filled dots.

For EACH heading, report:
  NAME | DOTS | any extra text inside the parentheses

Rules, in order of importance:
1. TRANSCRIBE ONLY. Never infer, never complete, never correct. This is Exalted
   First Edition; if a value looks wrong to you, it is not wrong.
2. COUNT THE DOTS EXACTLY. Report the count as a digit (1-5). If you cannot count
   them with certainty, write ??? instead of a number. A ??? costs five seconds; a
   wrong number survives for months.
3. If a heading has parentheses but you cannot read what is inside, write ???.
4. Copy the NAME exactly as printed, including any that are hyphenated or unusual.
5. If there are no artifact headings on this page, output exactly: NONE

Output one heading per line, nothing else. No preamble, no commentary, no summary.
Format: NAME | DOTS | EXTRA
"""


def render(pdf: str, pdf_page: int, dpi: int, outdir: Path) -> Path:
    stem = outdir / f"p{pdf_page}"
    subprocess.run(
        ["pdftoppm", "-r", str(dpi), "-f", str(pdf_page), "-l", str(pdf_page),
         "-png", "-singlefile", pdf, str(stem)],
        check=True, capture_output=True)
    return stem.with_suffix(".png")


def ask(png: Path, num_ctx: int) -> str:
    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "images": [base64.b64encode(png.read_bytes()).decode()],
        "stream": False,
        # Deterministic: this is transcription, and sampling is how a plausible wrong
        # dot count gets invented.
        "options": {"temperature": 0, "num_ctx": num_ctx},
    }
    req = urllib.request.Request(
        OLLAMA, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["response"].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--pages", required=True, help="BOOK pages, comma separated")
    ap.add_argument("--offset", type=int, default=0,
                    help="pdf page number minus book page number")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--num-ctx", type=int, default=16384)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    pages = [int(x) for x in a.pages.split(",") if x.strip()]
    results = {}
    with tempfile.TemporaryDirectory() as td:
        outdir = Path(td)
        for bp in pages:
            png = render(a.pdf, bp + a.offset, a.dpi, outdir)
            print(f"p.{bp} … ", end="", flush=True)
            try:
                raw = ask(png, a.num_ctx)
            except Exception as exc:  # noqa: BLE001
                print(f"FAILED: {exc}", file=sys.stderr)
                results[bp] = {"error": str(exc)}
                continue
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            rows = []
            for ln in lines:
                if ln.upper() == "NONE":
                    continue
                parts = [p.strip() for p in ln.split("|")]
                if len(parts) >= 2:
                    rows.append({"name": parts[0], "dots": parts[1],
                                 "extra": parts[2] if len(parts) > 2 else ""})
            results[bp] = {"raw": raw, "rows": rows}
            unsure = sum(1 for r in rows if "?" in r["dots"])
            print(f"{len(rows)} heading(s)" + (f", {unsure} unsure" if unsure else ""))
    json.dump(results, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    raise SystemExit(main())
