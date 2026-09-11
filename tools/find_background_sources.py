"""Locate each Background's printed page in the pasted sources, by TEXT AGREEMENT.

⚠ **This is a tool, not a test, and it must never go into the suite.** It reads
`images/`, which is gitignored and absent from a clone, so a test form of it would
fail for everybody who did not author the pages. That is also why a wrong
`source.book` cannot be caught automatically — the field has no read sites
(`CLAUDE.md` section 13), and the only real check is a human against the page.

Run: `.venv/bin/python tools/find_background_sources.py`. It writes nothing to
`data/`; it prints a ranked report and dumps `bg_provenance.json` beside itself.

For every row in data/backgrounds.json:
  * find every ALL-CAPS heading in every images/**/*.md that matches the name,
  * score the source text that follows against the row's own `description`,
  * report the best match, its page (nearest preceding <!--PAGE n--> mark), and
    the runner-up, so a weak or ambiguous win is visible rather than silent.

Scoring, not name matching, is the point. Seven rows are called "Artifact" and
ten Mountain Folk rows share a name with a core row, so a name match alone hits
the wrong copy every time (see feedback_duplicate_background_names_need_ids).

The page convention was calibrated against 81 human-verified Merit citations in
the Player's Guide: 74 agreed exactly with "nearest preceding mark = the page the
text is on". Nothing here writes to data/.
"""

from __future__ import annotations

import json
import pathlib
import re
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parent.parent

# images/<dir> -> the canonical book name. A book is where the INK is, not the
# splat (docs/source-attribution.md), so this maps files, never exalt_type.
BOOK_OF_FILE = {
    "Exalted Core.md": "Core",
    "Exalted Core-charms.md": "Core",
    "Player's Guide.md": "Player's Guide",
    "Abyssals.md": "The Abyssals",
    "DragonBlooded.md": "The Dragon-Blooded",
    "Sidereals.md": "The Sidereals",
    "Autochthonians.md": "The Autochthonians",
    "Autochthonians(1).md": "The Autochthonians",
    "The Outcaste.md": "The Outcaste",
    "Cult of the Illuminated.md": "Cult of the Illuminated",
    "Games of Divinity.md": "Games of Divinity",
    "Savant and Sorcerer.md": "Savant and Sorcerer",
    "Ruins of Rathess.md": "Ruins of Rathess",
    "Book of Bone and Ebony.md": "Book of Bone and Ebony",
    "CH 6 - The Mountain Folk.md": "The Mountain Folk (CH6)",
    # Alchemicals are printed in The Autochthonians; this is its chapter 2.
    "CH 2 Character Creation and Traits.md": "The Autochthonians",
    "CH 3 Charms.md": "The Autochthonians",
    "CH 4 Miracles of the Machine God.md": "The Autochthonians",
    # Spirit material, identical text and page to the Games of Divinity extract.
    "CH 4 - Spirit Charms.md": "Games of Divinity",
    "Illuminated Backgrounds.md": "Cult of the Illuminated",
}

_WORD = re.compile(r"[a-z']+")
_STOP = set("the a an and or of to in is are for that this with it its as by on "
            "be can may not but if from at her his their your you character".split())


def words(text: str) -> Counter:
    return Counter(w for w in _WORD.findall(text.lower())
                   if w not in _STOP and len(w) > 2)


def overlap(a: Counter, b: Counter) -> float:
    """Fraction of the row's distinct words that the source text also has."""
    if not a:
        return 0.0
    return sum(1 for w in a if w in b) / len(a)


def load_sources() -> list[tuple[str, list[str], list[tuple[int, int]]]]:
    out = []
    for path in sorted((REPO / "images").rglob("*.md")):
        lines = path.read_text(errors="replace").split("\n")
        marks = [(i, int(m.group(1))) for i, line in enumerate(lines)
                 for m in [re.match(r"\s*<!--PAGE (\d+)-->", line)] if m]
        if marks:
            out.append((str(path.relative_to(REPO)), lines, marks))
    return out


def page_at(marks: list[tuple[int, int]], lineno: int) -> int | None:
    best = None
    for i, page in marks:
        if i <= lineno:
            best = page
        else:
            break
    return best


def heading_hits(lines: list[str], name: str) -> list[int]:
    """Lines that are exactly the name as a heading.

    Tolerates three things the sources really contain: the drop-cap split the OCR
    leaves ('A LLIES'), a trailing colon, and a markdown prefix ('#### ALLIES').
    ⚠ The Mountain Folk chapter uses the markdown form only. Without the '#'
    strip, all ten of its rows match a DIFFERENT book and score just low enough
    to look like weak evidence rather than a broken matcher.
    """
    target = name.upper().replace(" ", "")
    hits = []
    for i, line in enumerate(lines):
        bare = line.strip().lstrip("#").strip().rstrip(":").upper().replace(" ", "")
        if bare == target and len(line.strip()) < len(name) + 12:
            hits.append(i)
    return hits


def main() -> None:
    rows = json.loads((REPO / "exalted_builder/data/backgrounds.json").read_text())
    sources = load_sources()
    print(f"{len(rows)} rows, {len(sources)} page-marked source files\n")

    results = []
    for row in rows:
        want = words(row.get("description", ""))
        cands = []
        for path, lines, marks in sources:
            book = BOOK_OF_FILE.get(pathlib.Path(path).name)
            for i in heading_hits(lines, row["name"]):
                body = "\n".join(lines[i + 1:i + 22])
                cands.append({
                    "score": round(overlap(want, words(body)), 3),
                    "book": book, "file": path,
                    "page": page_at(marks, i), "line": i,
                    "peek": lines[i + 1].strip()[:52],
                })
        cands.sort(key=lambda c: -c["score"])
        # Two extracts of one book are not two opinions. Several books are in
        # images/ twice (Autochthonians(1).md, the Illuminated Backgrounds
        # excerpt), so keep the best candidate for each (book, page) only.
        # Without this a row agreeing with itself looks like an unresolved tie.
        seen, unique = set(), []
        for c in cands:
            key = (c["book"], c["page"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(c)
        results.append({"id": row["id"], "name": row["name"],
                        "exalt": row.get("exalt_type"), "cands": unique[:3]})

    for r in results:
        top = r["cands"][0] if r["cands"] else None
        runner = r["cands"][1] if len(r["cands"]) > 1 else None
        if not top:
            print(f"  --   {r['name']:18s} {str(r['exalt'] or '-'):15s} NO HEADING FOUND")
            continue
        gap = top["score"] - (runner["score"] if runner else 0.0)
        flag = "OK " if top["score"] >= 0.45 and gap >= 0.12 else "?? "
        book = top["book"] or f"UNMAPPED:{pathlib.Path(top['file']).name}"
        print(f"  {flag}  {r['name']:18s} {str(r['exalt'] or '-'):15s} "
              f"{top['score']:.2f} (+{gap:.2f})  {book} p.{top['page']}")

    (pathlib.Path(__file__).parent / "bg_provenance.json").write_text(
        json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
