#!/usr/bin/env python3
"""Report which modules read each field of an effects dataclass.

The Callous bug in one command. `willpower_virtue_margin` was read in exactly one
place -- `validate`, as a chargen ceiling -- so the rule was implemented and never
ran post-lock. A field's read sites tell you which lifecycle phases it binds in;
a single site is a question worth asking, and zero sites is a rule that does
nothing at all.

    .venv/bin/python .claude/skills/preflight/effect_reads.py
    .venv/bin/python .claude/skills/preflight/effect_reads.py --class MeritEffects

This is a heuristic grep, not a call-graph. It matches bare identifiers, so a field
whose name collides with an unrelated local will over-report. Read the sites it
names; do not trust the count alone.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
PKG = ROOT / "exalted_builder"

# Effects dataclasses this project computes centrally, and the module that owns
# each. A field read ONLY inside its owning module is fine when a helper there is
# the public read (merits.adjust_charm_cost); it is dead when nothing reads it.
OWNERS = {"MeritEffects": PKG / "engine" / "merits.py"}


def fields_of(src: str, cls: str) -> list[str]:
    m = re.search(rf"class {cls}\b.*?(?=\nclass |\ndef |\Z)", src, re.S)
    if not m:
        sys.exit(f"no class {cls} found")
    return re.findall(r"^    ([a-z_][a-z_0-9]*)\s*:", m.group(0), re.M)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="cls", default="MeritEffects")
    args = ap.parse_args()

    owner = OWNERS.get(args.cls)
    if owner is None:
        sys.exit(f"unknown effects class {args.cls}; add it to OWNERS")
    src = owner.read_text()
    names = fields_of(src, args.cls)

    others = [p for p in PKG.rglob("*.py") if p != owner]
    texts = {p: p.read_text() for p in others}

    single, zero, ui_only = [], [], []
    width = max(len(n) for n in names)
    print(f"{args.cls} -- {len(names)} fields, read sites outside {owner.name}\n")

    for name in names:
        pat = re.compile(rf"\b{name}\b")
        hits = collections.Counter()
        for p, text in texts.items():
            n = len(pat.findall(text))
            if n:
                hits[str(p.relative_to(PKG))] = n

        mods = sorted(hits)
        note = ""
        if not mods:
            # Consumed inside the owning module by a helper? Reads there are any
            # occurrence past the field's own declaration line.
            body = src.split(f"    {name}:", 1)[-1]
            internal = len(pat.findall(body)) - 1
            if internal > 0:
                note = f"  <- consumed in {owner.name} only ({internal} refs)"
            else:
                note = "  <- ZERO READS"
                zero.append(name)
        elif len(mods) == 1:
            note = "  <- SINGLE SITE"
            single.append((name, mods[0]))
            if mods[0].startswith("ui/"):
                ui_only.append((name, mods[0]))
        print(f"  {name:{width}}  {', '.join(mods) or '(none)'}{note}")

    print()
    if zero:
        print(f"ZERO READS ({len(zero)}) -- computed and consumed by nothing. Either")
        print("a real gap or display-only; a test asserting the field proves nothing")
        print("about behaviour either way.")
        for n in zero:
            print(f"  - {n}")
        print()
    if ui_only:
        print(f"UI-ONLY ({len(ui_only)}) -- the engine does not know this rule.")
        print("Game logic in the UI breaks the ui -> engine -> models rule.")
        for n, m in ui_only:
            print(f"  - {n:{width}}  {m}")
        print()
    if single:
        print(f"SINGLE SITE ({len(single)}) -- open each and check WHICH PHASE it")
        print("runs in. validate-only is chargen-only; derive-only never gates the")
        print("build. Do not trust the comment at the site: Callous's claimed to be")
        print("the decision-0005 exception and was not.")
        for n, m in single:
            print(f"  - {n:{width}}  {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
