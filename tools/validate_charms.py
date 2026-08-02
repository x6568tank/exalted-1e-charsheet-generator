#!/usr/bin/env python3
"""Lint newly-authored Charm JSON before it goes anywhere near the RuleSet.

Written for the delegated-authoring workflow: an agent (or a human) transcribes a
Charm tree from a page into `data/charms/<splat>_<category>.json`, then this runs
over it. It catches the mechanical mistakes that transcription reliably makes and
that `rules_db.load_ruleset` either does not check or reports too late to be
useful, plus a few "2e crept in" smells.

    .venv/bin/python tools/validate_charms.py                     # every charm file
    .venv/bin/python tools/validate_charms.py --splat sidereal    # one splat
    .venv/bin/python tools/validate_charms.py data/charms/foo.json ...

Exit status is 1 if any ERROR was reported, 0 otherwise. WARNs never fail the run
— they are things a human should eyeball, not things that are definitely wrong.

This is a lint pass, NOT a substitute for `load_ruleset` (which owns cross-file
reference integrity) or for reading the page. It cannot tell you a transcribed
number is the wrong number.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "exalted_builder" / "data"
CHARM_DIR = DATA / "charms"

sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------- expectations

VALID_TYPES = {"Reflexive", "Supplemental", "Simple", "Extra Action", "Permanent", "Special"}
# The four Virtues, for `min_virtue` (the ghosts' Virtue-keyed Arcanoi). Spelled out
# rather than imported so this tool stays runnable without the package importable.
_VIRTUES = {"compassion", "conviction", "temperance", "valor"}

# Terms that are 2e/2.5e-only or are a 2e rename of a 1e trait. Their presence in a
# 1e description usually means the author reached for training data, not the page.
# (CLAUDE.md: 1e ONLY. 2e is far better represented in training data, so this is the
# single most likely failure mode.)
EDITION_SMELLS = [
    (r"\bMote Accumulation\b", "2e term"),
    (r"\bDodge\s+MDV\b|\bMDV\b", "2e Mental Defense Value"),
    (r"\bDV\b(?!\w)", "2e Defense Value (1e uses dice pools / difficulty)"),
    (r"\bOnslaught penalt", "2e"),
    (r"\bstunt dice\b.*\btier\b", "2e stunt tiers"),
    (r"\bWar\b(?=\s+(?:Ability|score|roll|\d))", "no War Ability in 1e core"),
    (r"\bIntimacies\b|\bIntimacy\b", "2e Intimacies"),
    (r"\bLimit Break\b.*\bTorment\b", "2e phrasing"),
    (r"\bEssence\s+pool\s+of\s+\d+\s*/\s*\d+", "2e pool notation"),
    (r"\bspeed\s+\d+,\s*accuracy", "2e weapon line"),
]

# OCR damage that survives into descriptions. Mirrors what the Sidereal repair pass
# actually found, so a re-run of that class of bug is caught mechanically.
OCR_SMELLS = [
    (r"\bI(?:ow|ows|ight|esh|ick|ame|oat|ower|ammable)\b", "fl/fi ligature lost (I for fl)"),
    (r"aGict|aGlict|ELect|ELict", "ffl/ffe ligature mangled"),
    (r"\bSuecess\b|\bExale\b|\bcurns\b|\btutn\b|\bsctipture\b|\bcemborary\b", "OCR letter swap"),
    # Word-glue. Anchored on a word boundary so "Stamina" does not match "…ina".
    (r"\b(?:asa|toan|hera|forany|thatshe|fora|ina|sensesa|isa|ora)\b(?=[a-z])", "missing space"),
    (r"\b[a-z]{2,}(?:[A-Z][a-z]{3,})", "missing space (camelCase run)"),
    (r"\s[a-z]+-\s[a-z]+", "hyphenation artifact"),
    # A trailing ALL-CAPS run is a next-charm title bleeding in. Two+ caps words, and
    # not a legitimate sutra line, which the styles print in caps mid-sentence.
    (r"[.!?”]\s+[A-Z]{4,}(?:\s+[A-Z']{2,})+\s*$", "trailing ALL-CAPS run (next charm's title?)"),
]

# NOT checked, deliberately — each fired dozens of times on correct data:
#   * "description starts lower-case": the Sidereal Martial Arts styles print their
#     sutra as a continuing lower-case fragment ("she ate them.", "what is whole").
#   * "prerequisite has a HIGHER min_ability than its dependent": common and legal
#     across every splat's real trees, so it carries no signal.


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ---------------------------------------------------------------------- report

class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"ERROR {where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warns.append(f"WARN  {where}: {msg}")

    def dump(self) -> int:
        for line in self.errors:
            print(line)
        for line in self.warns:
            print(line)
        print(f"\n{len(self.errors)} error(s), {len(self.warns)} warning(s)")
        return 1 if self.errors else 0


# ------------------------------------------------------------------- checks

def check_file_shape(path: Path, raw: str, rep: Report) -> list[dict] | None:
    """The file parses, is a list, and round-trips byte-identically through the
    canonical dump. A non-round-tripping file means a later programmatic edit would
    reformat the whole file and bury the real diff."""
    where = path.name
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        rep.error(where, f"not valid JSON: {exc}")
        return None
    if not isinstance(data, list):
        rep.error(where, "top level must be a JSON array of Charm objects")
        return None
    canonical = json.dumps(data, indent=2, ensure_ascii=False) + ("\n" if raw.endswith("\n") else "")
    if canonical != raw:
        rep.warn(where, "not canonical formatting (json.dumps indent=2, ensure_ascii=False)")
    return data


def check_charm(c: dict, path: Path, rep: Report) -> None:
    cid = c.get("id") or "<no id>"
    where = f"{path.name}:{cid}"

    for field in ("id", "name", "category", "type"):
        if not c.get(field):
            rep.error(where, f"missing required field {field!r}")

    if c.get("type") and c["type"] not in VALID_TYPES:
        rep.error(where, f"type {c['type']!r} is not one of {sorted(VALID_TYPES)}")

    # --- id / category conventions -------------------------------------------
    # Project convention: ids use hyphens in every segment, `category` uses
    # underscores for multi-word categories. Mismatched separators are the single
    # most common transcription slip (see the Lunar files in CLAUDE.md).
    cid_s = c.get("id", "")
    if "_" in cid_s:
        rep.error(where, "id contains '_' — id segments use hyphens, only `category` uses underscores")
    if cid_s and cid_s != cid_s.lower():
        rep.error(where, "id must be lowercase")
    if cid_s.count(".") < 2:
        rep.error(where, "id should be '<splat>.<category>.<charm-name>'")
    else:
        splat_seg, cat_seg, name_seg = cid_s.split(".", 2)
        cat = c.get("category", "")
        # Two conventions coexist for `martial_arts:<style>` and both are in use:
        # Solar/Abyssal/DB put the literal "martial-arts" in the id segment, Sidereal
        # puts the style name (sidereal.violet-bier-of-sorrows.*). Accept either;
        # only flag a segment that matches neither.
        if cat.startswith("martial_arts:"):
            allowed = {_norm("martial_arts"), _norm(cat.split(":", 1)[1])}
            if _norm(cat_seg) not in allowed:
                rep.error(where, f"id category segment {cat_seg!r} matches neither 'martial-arts' nor the style in {cat!r}")
        elif cat and _norm(cat_seg) != _norm(cat):
            rep.error(where, f"id category segment {cat_seg!r} does not match category {cat!r}")
        if c.get("name") and _norm(name_seg) != _norm(c["name"]):
            rep.warn(where, f"id name segment {name_seg!r} does not match name {c['name']!r}")
        want_splat = _norm(c.get("exalt_type", "Solar"))
        if want_splat and _norm(splat_seg) != want_splat:
            rep.warn(where, f"id splat segment {splat_seg!r} vs exalt_type {c.get('exalt_type')!r}")

    # --- the gating axis ------------------------------------------------------
    # CLAUDE.md: `min_attribute` NAMES the gating trait and `min_ability` RATES it.
    # The Alchemical catalogue shipped 120 Charms with min_ability 0 because the
    # first pass captured only the name — every one of them gated on nothing, and
    # every Array priced at 0 XP. This check exists specifically for that bug.
    # A repeatable Charm (Ox-Body and friends) legitimately has no minimum — its
    # `repeatable_cap_ability` names the capping trait and min_attribute may echo it.
    repeatable = bool(c.get("repeatable_cap_ability"))
    _keys = [k for k in ("min_attribute", "min_virtue") if c.get(k)]
    if len(_keys) > 1:
        # A Charm keyed two ways silently loses one gate: `_min_trait_rating` returns
        # the FIRST match and never looks at the second.
        rep.error(where, f"keyed on more than one axis ({', '.join(_keys)}) — set at most one")
    if _keys and not c.get("min_ability") and not repeatable:
        rep.error(where, f"{_keys[0]} is set but min_ability is 0 — min_ability RATES it")
    if c.get("min_virtue") and c["min_virtue"] not in _VIRTUES:
        rep.error(where, f"min_virtue {c['min_virtue']!r} is not one of {sorted(_VIRTUES)}")
    if (not _keys and not c.get("min_ability") and not c.get("extra_min_abilities")
            and not repeatable):
        if c.get("type") not in {"Permanent", "Special"}:
            rep.warn(where, "no min_ability and no keying trait — is this Charm really ungated?")
    if c.get("min_essence", 1) < 1:
        rep.error(where, "min_essence must be >= 1")

    # --- extra Ability minimums (a Charm gated on more than one Ability) ------
    # Shape is list[{"abilities": [<AbilityName>, ...], "rating": N}] — each entry an
    # independent AND whose inner list is an OR. Getting the nesting wrong here fails
    # OPEN (the gate silently disappears), so it is an error, not a warning.
    extras = c.get("extra_min_abilities", [])
    if not isinstance(extras, list):
        rep.error(where, "extra_min_abilities must be a list of {abilities, rating} objects")
    else:
        primary = None
        if not _keys:
            cat = c.get("category", "")
            primary = cat if not cat.startswith("martial_arts") else None
        for req in extras:
            if not isinstance(req, dict):
                rep.error(where, f"extra_min_abilities entry {req!r} must be an object")
                continue
            abils = req.get("abilities")
            if not isinstance(abils, list) or not abils:
                rep.error(where, "an extra_min_abilities entry needs a non-empty `abilities` list")
                continue
            if any(not isinstance(a, str) for a in abils):
                rep.error(where, f"extra_min_abilities `abilities` must be name strings: {abils!r}")
            if not isinstance(req.get("rating"), int) or req["rating"] < 1:
                rep.error(where, f"extra_min_abilities entry needs `rating` >= 1: {req!r}")
            if primary and primary in abils:
                rep.warn(where, f"extra_min_abilities repeats the primary gate {primary!r} "
                                f"— that is what min_ability is for")

    # --- prerequisites: AND-of-OR, i.e. list[list[str]] ----------------------
    prereqs = c.get("prerequisites", [])
    if not isinstance(prereqs, list):
        rep.error(where, "prerequisites must be a list of lists (AND-of-OR)")
    else:
        for grp in prereqs:
            if not isinstance(grp, list):
                rep.error(where, f"prerequisite group {grp!r} must be a LIST of ids (AND-of-OR), not a bare string")
            elif not grp:
                rep.error(where, "empty prerequisite group")
            elif cid_s in grp:
                rep.error(where, "Charm lists itself as its own prerequisite")

    # --- cost ----------------------------------------------------------------
    cost = c.get("cost")
    if not isinstance(cost, dict):
        rep.error(where, "missing cost object")
    else:
        raw = cost.get("raw", "")
        if not raw:
            rep.warn(where, "cost.raw is empty — it is the authoritative display string")
        # A whole description dumped into cost.raw was a real Sidereal bug. Real
        # variable-cost strings do run long ("4 motes per tentacle if all attacks
        # target a single foe; 5 motes per tentacle if targeted at multiple foes"),
        # so only prose-with-sentences is an error.
        if re.search(r"[a-z]\.\s+[A-Z]", raw) or len(raw) > 130:
            rep.error(where, f"cost.raw holds prose — description spilled into it? {raw[:60]!r}…")
        elif len(raw) > 80:
            rep.warn(where, f"cost.raw is unusually long ({len(raw)} chars)")
        if re.search(r"\bI\s+(?:mote|Willpower|health)", raw):
            rep.error(where, f"cost.raw {raw!r} has 'I' where '1' belongs (OCR)")
        for key, unit in (("motes", "mote"), ("willpower", "Willpower"), ("health", "health level")):
            n = cost.get(key, 0)
            # A printed cost may spell the number ("one lethal health level",
            # E:Ab p.238) — that is the raw mentioning it, not omitting it.
            spelled = {1: "one", 2: "two", 3: "three"}.get(n, "")
            written = re.search(rf"\b{n}\b", raw) or (
                spelled and re.search(rf"\b{spelled}\b", raw, re.I))
            if n and not written and "per" not in raw.lower():
                rep.warn(where, f"cost.{key}={n} but cost.raw={raw!r} does not mention it")

    # A long duration is legitimate ("Until the character applies Mercury's bridle").
    # A duration holding SENTENCES is a description that spilled into the field.
    dur = c.get("duration", "")
    if not dur:
        rep.warn(where, "empty duration")
    elif re.search(r"[a-z]\.\s+[A-Z]", dur) or len(dur) > 90:
        rep.error(where, f"duration holds prose — description spilled into it? {dur[:60]!r}…")
    elif len(dur) > 50:
        rep.warn(where, f"duration is unusually long ({len(dur)} chars): {dur!r}")

    # --- description ---------------------------------------------------------
    desc = c.get("description", "")
    if not desc:
        rep.error(where, "empty description")
    else:
        if len(desc) < 120:
            rep.warn(where, f"description is only {len(desc)} chars — truncated?")
        for pat, why in OCR_SMELLS:
            m = re.search(pat, desc, re.MULTILINE)
            if m:
                rep.warn(where, f"{why}: {m.group(0)!r}")
        for pat, why in EDITION_SMELLS:
            m = re.search(pat, desc)
            if m:
                rep.error(where, f"EDITION: {m.group(0)!r} — {why}. 1e only; verify against the page")

    # --- provenance ----------------------------------------------------------
    src = c.get("source") or {}
    if not src.get("book"):
        rep.warn(where, "source.book is empty")
    if src.get("page") in (None, 0, ""):
        rep.warn(where, "source.page is not set — every value must be traceable to a page")


def check_corpus(charms: list[tuple[dict, Path]], rep: Report, targets: set[Path]) -> None:
    """Whole-corpus checks: duplicate ids/names, prerequisite resolution, orphan
    trees. Reads ALL charm files even when linting one — a new file's prerequisites
    point at existing Charms — but only REPORTS on the targeted files, so linting a
    new tree does not bury you in findings about old ones."""
    def mine(path: Path) -> bool:
        return path.resolve() in targets

    by_id: dict[str, Path] = {}
    for c, path in charms:
        cid = c.get("id")
        if not cid:
            continue
        if cid in by_id and (mine(path) or mine(by_id[cid])):
            rep.error(f"{path.name}:{cid}", f"duplicate id (also in {by_id[cid].name})")
        by_id[cid] = path

    names = Counter(
        (c.get("exalt_type", "Solar"), c.get("name", ""))
        for c, p in charms if mine(p)
    )
    for (splat, name), n in names.items():
        if n > 1 and name:
            rep.warn(f"{splat}", f"{n} Charms share the name {name!r}")

    for c, path in charms:
        if not mine(path):
            continue
        cid = c.get("id", "")
        for grp in c.get("prerequisites", []) or []:
            if not isinstance(grp, list):
                continue
            for pid in grp:
                if pid not in by_id:
                    rep.error(f"{path.name}:{cid}", f"prerequisite {pid!r} does not exist")
                    continue
                pre = next(x for x, _ in charms if x.get("id") == pid)
                # Only flag a prerequisite that is *wildly* above its dependent. A
                # one-step inversion is common and legal in the real trees; a 3+ step
                # gap is a transposed pair.
                gap = pre.get("min_ability", 0) - c.get("min_ability", 0)
                if c.get("min_ability") and gap >= 3:
                    rep.warn(
                        f"{path.name}:{cid}",
                        f"prerequisite {pid} needs min_ability {pre['min_ability']} "
                        f"vs this Charm's {c['min_ability']} — transposed?",
                    )

    # Per (splat, category): a tree with no root cannot be reached, and a tree that
    # is ALL roots usually means the prerequisites were never transcribed.
    groups: dict[tuple[str, str], list[dict]] = {}
    touched: set[tuple[str, str]] = set()
    for c, p in charms:
        key = (c.get("exalt_type", "Solar"), c.get("category", ""))
        groups.setdefault(key, []).append(c)
        if mine(p):
            touched.add(key)
    for (splat, cat), members in groups.items():
        if (splat, cat) not in touched:
            continue
        ids = {c.get("id") for c in members}
        roots = [c for c in members if not any(
            pid in ids for grp in (c.get("prerequisites") or []) if isinstance(grp, list) for pid in grp
        )]
        if not roots:
            rep.error(f"{splat}/{cat}", "no root Charm — every Charm depends on another in this tree (cycle?)")
        elif len(members) > 3 and len(roots) == len(members):
            rep.warn(f"{splat}/{cat}", f"all {len(members)} Charms are roots — prerequisites missing?")


def check_against_loader(rep: Report) -> None:
    """Finally, hand the whole thing to the real loader. It owns cross-file
    reference integrity and spell-circle access; this lint deliberately does not
    duplicate that logic."""
    try:
        from exalted_builder.rules_db import load_ruleset
    except Exception as exc:  # pragma: no cover - import guard
        rep.warn("loader", f"could not import rules_db ({exc})")
        return
    try:
        rs = load_ruleset(DATA)
    except Exception as exc:
        rep.error("loader", f"load_ruleset() rejected the data set:\n{exc}")
        return
    print(f"loader OK: {len(rs.charms)} charms, {len(rs.spells)} spells")


# ------------------------------------------------------------------------ main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=Path, help="charm JSON files (default: all)")
    ap.add_argument("--splat", help="only lint files matching this splat prefix, e.g. 'sidereal'")
    ap.add_argument("--no-loader", action="store_true", help="skip the load_ruleset() pass")
    args = ap.parse_args(argv)

    all_files = sorted(CHARM_DIR.glob("*.json"))
    all_files = [p for p in all_files if not p.name.endswith(".example.json")]

    if args.files:
        targets = [p if p.is_absolute() else (ROOT / p) for p in args.files]
    elif args.splat:
        targets = [p for p in all_files if p.name.startswith(args.splat.lower())]
        if not targets:
            print(f"no charm files match splat {args.splat!r}", file=sys.stderr)
            return 2
    else:
        targets = all_files

    rep = Report()

    # Corpus context: parse every file so prerequisites can resolve across splats,
    # but only run per-charm checks on the targeted files.
    corpus: list[tuple[dict, Path]] = []
    for path in all_files:
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        if isinstance(data, list):
            corpus.extend((c, path) for c in data if isinstance(c, dict))

    target_set = {p.resolve() for p in targets}
    for path in targets:
        raw = path.read_text()
        data = check_file_shape(path, raw, rep)
        if data is None:
            continue
        for c in data:
            if isinstance(c, dict):
                check_charm(c, path, rep)
            else:
                rep.error(path.name, f"array element is not an object: {c!r}")

    check_corpus(corpus, rep, target_set)

    if not args.no_loader:
        check_against_loader(rep)

    print(f"\nlinted {len(targets)} file(s), {sum(1 for c, p in corpus if p.resolve() in target_set)} charm(s)")
    return rep.dump()


if __name__ == "__main__":
    raise SystemExit(main())
