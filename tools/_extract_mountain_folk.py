"""One-off extraction of the Mountain Folk Charm blocks (CH6 pp.244-275) from the
pasted chapter text into the five `mountain_folk_<pattern>.json` files.

The pasted text is machine-readable: every Charm is a `#### NAME` block with the
five fields Cost / Duration / Type / Minimum Essence / Prerequisite Charms in a
fixed order, then the body. Five blocks are VARIABLE Charms that print one template
with per-variant sections and expand into 4-5 separate Charms each; the other 72
are single entries. Variable blocks are PRINTED for manual expansion (their
per-variant prerequisites and description splits are bespoke); the standard blocks
are parsed, their name-only prerequisites resolved, and written out.

Run `validate_charms.py --splat mountain-folk` after this to verify every parse.
"""
import json
import re

SRC = "images/Mortals/Mountain Folk/CH 6 - The Mountain Folk.md"
OUT = "exalted_builder/data/charms"
BOOK = "Exalted: The Mountain Folk (CH6)"


def slug(s: str) -> str:
    s = s.lower().replace("(", "").replace(")", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


_SMALL = {"of", "and", "the", "for", "to", "in", "on", "with"}


def title_case(s: str) -> str:
    """The page prints Charm titles in ALL CAPS; prereqs use title case. Normalise
    both to title case with lowercase articles, so names and prereq references match."""
    words = s.lower().split()
    return " ".join(w.capitalize() if (i == 0 or w not in _SMALL) else w
                    for i, w in enumerate(words))


def fix_name(name: str) -> str:
    """Repair the two OCR word-splits in the pasted titles: "SHAPING MIND C
    ONCENTRATION" and "E SSENCE-TRANSFER TECHNIQUE". After title_case these read
    "Shaping Mind C Oncentration" and "E Ssence-transfer Technique" (the hyphen
    lowercases the segment after it)."""
    return (name.replace("C Oncentration", "Concentration")
                .replace("E Ssence-transfer", "Essence-Transfer"))


def parse_cost(raw: str) -> dict:
    raw = raw.strip()
    low = raw.lower()
    if low in ("none", "varies"):
        return {"raw": raw}
    out = {"motes": 0, "willpower": 0, "health": 0, "raw": raw}
    m = re.search(r"(\d+)\s*motes?", raw, re.I)
    if m:
        out["motes"] = int(m.group(1))
    m = re.search(r"(\d+)\s*willpower", raw, re.I)
    if m:
        out["willpower"] = int(m.group(1))
    m = re.search(r"(\d+)\s*health", raw, re.I)
    if m:
        out["health"] = int(m.group(1))
    return out


FIELDS = ("Cost:", "Duration:", "Type:", "Minimum Essence:", "Prerequisite Charms:")


def clean_body(body: str) -> str:
    """Join the pasted text's ~60-char hard wraps back into flowing prose. A line
    ending in a hyphen is a typesetter's mid-word wrap (e.g. "glim-"/"mer") — strip
    the hyphen and join directly; any other wrapped line joins with a space.
    Paragraphs (blank-line separated) stay separated by \n\n."""
    paragraphs = []
    for para in body.split("\n\n"):
        out = ""
        for line in (l.strip() for l in para.split("\n") if l.strip()):
            if out.endswith("-"):
                out = out[:-1] + line
            elif out:
                out += " " + line
            else:
                out = line
        if out:
            paragraphs.append(out)
    return "\n\n".join(paragraphs)


def page_for(start, lines):
    """The page of the nearest <!--PAGE n--> marker at or before `start` — every
    pasted page in the Charm section carries one. Scans back to the section head."""
    for j in range(start, -1, -1):
        m = re.match(r"<!--PAGE (\d+)-->", lines[j])
        if m:
            return int(m.group(1))
    return 0


def main() -> None:
    lines = open(SRC, encoding="utf-8").read().splitlines()
    charm_start = next(i for i, l in enumerate(lines) if l == "## CHARMS")
    tech_start = next(i for i, l in enumerate(lines) if l == "## MOUNTAIN FOLK TECHNOLOGY")

    # Assign each #### block to a Pattern.
    order = []
    cur = None
    for i, l in enumerate(lines):
        if i < charm_start or i >= tech_start:
            continue
        if l.startswith("### "):
            m = re.match(r"### THE (\w+) PATTERN", l)
            if m:
                cur = m.group(1).lower()
            continue
        if l.startswith("#### ") and cur:
            order.append((i, cur))

    # Parse every block: name, fields, body.
    blocks = []
    for idx, (start, pattern) in enumerate(order):
        end = order[idx + 1][0] if idx + 1 < len(order) else tech_start
        bl = lines[start:end]
        name = fix_name(title_case(bl[0].split("#### ", 1)[1].strip()))
        fields = {}
        body_start = None
        prev_field = None
        for j in range(1, len(bl)):
            f = next((f for f in FIELDS if bl[j].startswith(f)), None)
            if f:
                fields[f] = bl[j].split(":", 1)[1].strip()
                prev_field = f
            elif prev_field and bl[j].strip() and not bl[j].startswith("<!--") \
                    and (re.match(r"^[\d)&]", bl[j]) or bl[j][:1].islower()
                         or fields[prev_field].rstrip().endswith(("-", ","))
                         or re.search(r"\(\d+$", fields[prev_field].rstrip())
                         or fields[prev_field].rstrip() in (
                             "Incomparable Efficiency", "Compassion-Bolstering",
                             "Conviction-Bolstering", "Temperance-Bolstering")):
                # A wrapped field continuation (only the Prerequisite line wraps in
                # this chapter: "… (x\n1), …", "…, Ei-\ndetic …", "…, Industry\nand
                # Forge Wisdom"). Merged without a space when the previous line ended
                # in a hyphen (a hyphenated word-break), with a space otherwise. Body
                # paragraphs start with a capital sentence and never match.
                if fields[prev_field].rstrip().endswith("-"):
                    fields[prev_field] = fields[prev_field].rstrip()[:-1] + bl[j].strip()
                else:
                    fields[prev_field] += " " + bl[j].strip()
            elif bl[j].strip() and not bl[j].startswith("<!--"):
                body_start = j
                break
        body = "\n".join(bl[body_start:]).strip()
        # Drop any trailing sidebar/box marker (TANGENT/XP/BP tables are not Charm
        # text); strip MID-BODY page markers without losing the prose either side.
        body = re.sub(
            r"\n*<!--(?:PAGE \d+|TANGENT TABLE|END TANGENT|XP TABLE|END XP|"
            r"BP TABLE|END BP)-->.*$", "", body, flags=re.S)
        body = re.sub(r"\n*<!--PAGE \d+-->\n*", "\n", body).strip()
        body = clean_body(body)
        blocks.append({"name": name, "pattern": pattern, "fields": fields,
                       "body": body, "page": page_for(start, lines)})

    # Expand variable templates into concrete names. Compared lowercased because
    # title_case leaves "(Virtue)" as "(virtue)" — Python's capitalize() does not
    # uppercase a letter after a parenthesis — so the templates must not demand a
    # capital V.
    def expand_variants(name: str) -> list[str]:
        virtues = ["Compassion", "Conviction", "Temperance", "Valor"]
        colors = ["Green", "Red", "Black", "Blue", "White"]
        n = name.lower()
        if n == "pillar of (virtue)":
            return [f"Pillar of {v}" for v in virtues]
        if n == "(virtue)-bolstering meditation":
            return [f"{v}-Bolstering Meditation" for v in virtues]
        if n == "mien of (virtue)":
            return [f"Mien of {v}" for v in virtues]
        if n == "(color) jade transformation":
            return [f"{c} Jade Transformation" for c in colors]
        if n == "fivefold embodiment of (color) jade":
            return [f"Fivefold Embodiment of {c} Jade" for c in colors]
        return [name]

    # Name -> id, keyed by slug so the ALL-CAPS page titles and the title-case
    # prereq references collide correctly. Variable templates' ids resolve too, so a
    # variable Charm can be a prerequisite of another Charm.
    def pattern_of(name: str) -> str:
        for b in blocks:
            for cand in expand_variants(b["name"]):
                if cand == name:
                    return b["pattern"]
        raise KeyError(name)

    def id_of(name: str) -> str:
        return f"mountainfolk.{pattern_of(name)}.{slug(name)}"

    all_names = set()
    pattern_ids: dict[str, set[str]] = {p: set() for p in
                                        ("foundation", "worker", "warrior", "artisan", "enlightened")}
    for b in blocks:
        for cand in expand_variants(b["name"]):
            all_names.add(cand)
            pattern_ids[b["pattern"]].add(id_of(cand))
    name_id = {slug(n): id_of(n) for n in all_names}

    _PILLAR_SLUGS = ("pillar-of-compassion", "pillar-of-conviction",
                     "pillar-of-temperance", "pillar-of-valor")

    # Resolve a `Prerequisite Charms:` line to AND-of-OR groups. The special forms —
    # "One Pillar of (Virtue)" (OR of four), "All Pillar of (Virtue) Charms" (AND of
    # four), "Entire <Pattern> Pattern (N Charms)" (AND of every Charm in that
    # Pattern, the Pattern Mastery apexes) — can each be followed by further
    # comma-separated names, so they contribute their groups and parsing continues.
    def prereqs(line: str, pattern: str, self_id: str) -> list[list[str]]:
        line = line.strip()
        if not line or line.lower() == "none":
            return []
        low = line.lower()
        groups: list[list[str]] = []
        m = re.match(r"^one pillar of \(virtue\) charm", low)
        if m:
            groups.append([name_id[s] for s in _PILLAR_SLUGS])
            line = line[m.end():].lstrip(", ").strip()
        m = re.match(r"^all pillar of \(virtue\) charms?", low)
        if m:
            groups += [[name_id[s]] for s in _PILLAR_SLUGS]
            line = line[m.end():].lstrip(", ").strip()
        m = re.match(r"^entire (\w+) pattern(?: \(\d+ charms? total\))?", low)
        if m:
            # The Pattern Mastery is itself a member of its Pattern, so it must not
            # list itself as a prerequisite.
            groups += [[cid] for cid in sorted(pattern_ids[m.group(1).lower()])
                       if cid != self_id]
            line = line[m.end():].lstrip(", ").strip()
        if not line:
            return groups
        # A comma-separated list is AND — one group per Charm. "(x N)" is a
        # repeat-count note on the page, not a separate prerequisite.
        for part in re.split(r",\s*(?=[A-Z])", line):
            part = re.sub(r"\s*\(x\s*\d+\)\s*$", "", part).strip()
            if part:
                groups.append([name_id[slug(part)]])
        return groups

    # Build the standard entries.
    standard = []
    variable = []
    for b in blocks:
        expanded = expand_variants(b["name"])
        if len(expanded) == 1 and expanded[0] == b["name"]:
            standard.append({
                "id": id_of(b["name"]),
                "name": b["name"],
                "category": f"mountain_folk:{b['pattern']}",
                "exalt_type": "Mountain-Folk",
                "type": b["fields"].get("Type:", ""),
                "min_essence": int(b["fields"].get("Minimum Essence:", "1")),
                "prerequisites": prereqs(b["fields"].get("Prerequisite Charms:", "None"),
                                         b["pattern"], id_of(b["name"])),
                "cost": parse_cost(b["fields"].get("Cost:", "None")),
                "duration": b["fields"].get("Duration:", ""),
                "description": b["body"],
                "source": {"book": BOOK, "page": b["page"]},
            })
        else:
            variable.append(b)

    # Print the variable blocks for manual expansion.
    print(f"\nStandard charms: {len(standard)}; variable blocks: {len(variable)}\n")
    for b in variable:
        print("=" * 70)
        print(f"VARIABLE: {b['name']} ({b['pattern']}) p.{b['page']}")
        print(f"Type: {b['fields'].get('Type:')}  Min Ess: {b['fields'].get('Minimum Essence:')}  "
              f"Cost: {b['fields'].get('Cost:')}  Dur: {b['fields'].get('Duration:')}")
        print(f"Prereq line: {b['fields'].get('Prerequisite Charms:')}")
        print(f"ID prefix: {b['pattern']}.{slug(b['name'])}")
        print(b["body"][:4000])
        print()

    # Write the standard entries per pattern.
    for pat in ("foundation", "worker", "warrior", "artisan", "enlightened"):
        pat_entries = [e for e in standard if e["category"].endswith(f":{pat}")]
        path = f"{OUT}/mountain_folk_{pat}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pat_entries, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"{pat}: {len(pat_entries)} standard charms -> {path}")


if __name__ == "__main__":
    main()
