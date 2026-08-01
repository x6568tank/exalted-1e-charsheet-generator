"""Extract the 56 Arcanoi from the human's pasted CH6 markdown into data/charms/.

Kept in the repo rather than thrown away because `images/` is gitignored: on a clone
without the source this is the record of HOW the Ghost catalogue was derived, and with
the source it re-derives it byte-for-byte.

Fixing the parser beats hand-typing. Every field is verified against the source's own
counts afterwards (tests/test_ghost.py pins them), and anything that cannot be resolved
is REPORTED and exits non-zero rather than guessed — the same contract
tools/md_to_charms.py follows.

Three things in the paste needed real handling, each with a precise rather than
heuristic test, because a loose one silently swallowed the description on the first run:

  * a Cost line that wraps mid-parenthesis (p.237) — folded while brackets are unclosed;
  * three Prerequisite lines that wrap mid-NAME — folded only while the trailing name
    fails to resolve against the known Charms, so a fragment that resolves stops it;
  * "Type: Supplementary" on one Charm where nine others print "Supplemental".

Usage:
    .venv/bin/python tools/extract_ghost_arcanoi.py [--write]
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

SRC = Path("images/Non-Exalts/Ghosts/CH 6 - The Arts of the Dead.md")
OUT = Path("exalted_builder/data/charms")

# The six Arcanoi paths, in printed order. The four Craft (…) headings on the same
# level are ABILITIES, not paths, and carry no Charms — they are skipped.
PATHS = {
    "SHIFTING GHOST-CLAY PATH": "shifting_ghost_clay",
    "TERROR-SPREADING ART": "terror_spreading",
    "SAVAGE GHOST TAMER ARTS": "savage_ghost_tamer",
    "ESSENCE-MEASURING THIEF ARTS": "essence_measuring_thief",
    "THE STRINGLESS PUPPETEER ART": "stringless_puppeteer",
    "TANGLED WEB ARTS": "tangled_web",
}

VIRTUES = ("Compassion", "Conviction", "Temperance", "Valor")
# `\s*` between the words, not a literal space: the paste drops spaces here and there
# (p.244 prints "PrerequisiteCharms:"), and a field name that fails to match does not
# fail loudly — the whole line silently becomes description text and the Charm loses
# its prerequisite. Found because the human hand-corrected exactly that Charm and a
# later re-extract overwrote the fix.
FIELD_RE = re.compile(
    r"^(Cost|Duration|Type|Prerequisite\s*Charms|Minimum\s*(?:%s|Essence))\s*:\s*(.*)$"
    % "|".join(VIRTUES))


# Every field name, keyed by its spaces-removed form, so a matched name normalises to
# one spelling however the paste rendered it.
_CANON_FIELDS = {re.sub(r"\s+", "", f): f for f in
                 ["Cost", "Duration", "Type", "Prerequisite Charms",
                  *(f"Minimum {v}" for v in (*VIRTUES, "Essence"))]}


def canon_field(name: str) -> str:
    return _CANON_FIELDS[re.sub(r"\s+", "", name)]


def title_name(raw: str) -> str:
    """Title-case a heading the source prints in ALL CAPS.

    `str.title()` treats an apostrophe as a word boundary, so "LAMPREY'S" comes out
    "Lamprey'S". Five Arcanoi are affected. Handles both the ASCII apostrophe and the
    curly one the paste actually uses (U+2019), and leaves hyphenated names alone —
    "Ghost-Devil Form" wants both halves capitalised, which is why `string.capwords`
    is not the answer here.
    """
    return re.sub(r"(?<=\w)['’](\w)",
                  lambda m: m.group(0)[0] + m.group(1).lower(), raw.title())


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s


def clean(text: str) -> str:
    """Drop the human's page markers and the tangent/table blocks, join the hard
    line wraps the PDF paste carries, and repair words split across a line break."""
    text = re.sub(r"<!--PAGE[^>]*-->", "", text)
    text = re.sub(r"<!--(TANGENT TABLE|DIFFICULTY TABLE|BP TABLE).*?<!--END [^>]*-->",
                  "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    # "appear-\nances" -> "appearances"; any other newline becomes a space.
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def parse_cost(raw: str) -> dict:
    """Motes / Willpower / health out of the printed cost line. `raw` is kept
    verbatim and is authoritative wherever the line says more than the numbers do
    (per-activation rates, 'or', experience riders)."""
    cost: dict = {"raw": raw}
    m = re.search(r"(\d+)\s*motes?", raw, re.I)
    if m:
        cost["motes"] = int(m.group(1))
    m = re.search(r"(\d+)\s*Willpower", raw, re.I)
    if m:
        cost["willpower"] = int(m.group(1))
    elif re.search(r"\bWillpower\b", raw, re.I):
        cost["willpower"] = 1          # "1 Willpower" written without the digit
    m = re.search(r"(?:one|(\d+))\s+(lethal|bashing|aggravated)\s+health level", raw, re.I)
    if m:
        cost["health"] = int(m.group(1) or 1)
        # models.rules.Damage is the 1e shorthand ('/' bashing, 'x' lethal,
        # '*' aggravated), not the English word.
        cost["health_type"] = {"bashing": "/", "lethal": "x",
                               "aggravated": "*"}[m.group(2).lower()]
    return cost


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines()

    charms: list[dict] = []
    path = None
    page = 0
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m_page = re.match(r"<!--PAGE\s+(\d+)\s*-->", line)
        if m_page:
            page = int(m_page.group(1))
            i += 1
            continue
        if line.startswith("### "):
            head = line[4:].strip().upper()
            path = PATHS.get(head)          # None for the four Craft headings
            i += 1
            continue
        if line.startswith("#### ") and path:
            name = line[5:].strip()
            page_at_heading = page
            fields: dict[str, str] = {}
            body: list[str] = []
            i += 1
            # Field block: contiguous "Key: value" lines, with continuation lines
            # folded into the previous field (one Cost wraps mid-parenthesis).
            last_key = None
            while i < len(lines):
                cur = lines[i]
                stripped = cur.strip()
                if stripped.startswith("####") or stripped.startswith("### "):
                    break
                m = FIELD_RE.match(stripped)
                if m:
                    last_key = canon_field(m.group(1))
                    fields[last_key] = m.group(2).strip()
                    i += 1
                    continue
                # A field value wrapped across a line break. Exactly one Charm does
                # this (p.237: "Cost: 20 motes, 2 Willpower (no Willpower in the /
                # shadowlands)"), so the test is precise rather than heuristic: fold
                # ONLY while the previous value has an unclosed parenthesis. Anything
                # looser swallows the description, which is what the first run did.
                if last_key and stripped and fields[last_key].count("(") > fields[last_key].count(")"):
                    fields[last_key] = (fields[last_key] + " " + stripped).strip()
                    i += 1
                    continue
                body.append(cur)
                i += 1
            charms.append({"name": name, "path": path, "fields": fields,
                           "page": page_at_heading, "body": "\n".join(body)})
            continue
        i += 1

    # --- resolve into the shipped shape ------------------------------------
    ids: dict[str, str] = {}
    # A second lookup with every non-alphanumeric removed. The same dropped-space
    # problem hits the VALUES too — p.244 names "Essence-DevouringGhost Touch" — and an
    # unresolved prerequisite is reported rather than guessed, so without this the
    # extractor stops on a name that is only cosmetically wrong.
    squashed_ids: dict[str, str] = {}
    for c in charms:
        # The id's category segment is HYPHENATED; only the `category` FIELD keeps
        # underscores (tools/validate_charms.py enforces both halves).
        cid = f"ghost.{c['path'].replace('_', '-')}.{slug(c['name'])}"
        ids[c["name"].upper()] = cid
        squashed_ids[re.sub(r"[^a-z0-9]", "", c["name"].lower())] = cid

    def resolve(name: str) -> str | None:
        """A Charm name to its id, tolerating the paste's dropped spaces. Exact match
        first; only then the squashed form, so a genuinely unknown name still fails."""
        name = name.strip().rstrip(".")
        if not name:
            return None
        hit = ids.get(name.upper())
        if hit is not None:
            return hit
        return squashed_ids.get(re.sub(r"[^a-z0-9]", "", name.lower()))

    problems: list[str] = []
    out: dict[str, list[dict]] = {}
    for c in charms:
        f = c["fields"]
        cid = ids[c["name"].upper()]
        missing = [k for k in ("Cost", "Duration", "Type", "Minimum Essence") if k not in f]
        if missing:
            problems.append(f"{cid}: missing {missing}")
            continue
        virtue = next((v for v in VIRTUES if f"Minimum {v}" in f), None)
        if virtue is None:
            problems.append(f"{cid}: no Minimum <Virtue> line")
            continue

        prereqs: list[list[str]] = []
        praw = f.get("Prerequisite Charms", "None").strip()
        body_lines = c["body"].splitlines()
        # The prerequisite line ALSO wraps ("…, Steeling" / "the Spirit"), and unlike
        # the Cost line it carries no bracket to detect the wrap with. Resolve it
        # against the known Charm names instead of guessing where it ends: pull in
        # following lines only while the trailing name fails to resolve, which is
        # data-driven and cannot run away into the description — a fragment that
        # resolves stops it immediately.
        if praw.lower() not in ("none", ""):
            for _ in range(2):
                tail = re.split(r",| and ", praw)[-1].strip().rstrip(".")
                if resolve(tail) or not body_lines:
                    break
                praw = (praw + " " + body_lines.pop(0).strip()).strip()
            c["body"] = "\n".join(body_lines)
            for part in re.split(r",| and ", praw):
                part = part.strip().rstrip(".")
                if not part:
                    continue
                target = resolve(part)
                if target is None:
                    problems.append(f"{cid}: UNRESOLVED prerequisite {part!r}")
                else:
                    prereqs.append([target])

        ctype = f["Type"].strip()
        if ctype == "Supplementary":        # one printing variant, p.253
            ctype = "Supplemental"

        row = {
            "id": cid,
            "name": title_name(c["name"]),
            "category": c["path"],
            "exalt_type": "Ghost",
            "type": ctype,
            "min_virtue": virtue.lower(),
            "min_ability": int(re.search(r"\d+", f[f"Minimum {virtue}"]).group()),
            "min_essence": int(re.search(r"\d+", f["Minimum Essence"]).group()),
            "prerequisites": prereqs,
            "cost": parse_cost(f["Cost"]),
            "duration": f["Duration"].strip(),
            "description": clean(c["body"]),
            "source": {"book": "Exalted: The Abyssals", "page": c["page"]},
        }
        out.setdefault(c["path"], []).append(row)

    print(f"parsed {len(charms)} charms across {len(out)} paths")
    for path, rows in out.items():
        print(f"  {path:26} {len(rows):>3}")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  " + p)
        return 1

    if "--write" in sys.argv:
        for path, rows in out.items():
            dest = OUT / f"ghost_{path}.json"
            dest.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
            print("wrote", dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
