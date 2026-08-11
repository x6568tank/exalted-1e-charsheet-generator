import json, re, collections

CANON = {
    "bone": "Book of Bone and Ebony", "B&E": "Book of Bone and Ebony",
    "play": "Player's Guide", "PG": "Player's Guide",
    "botc": "Book of Three Circles", "B3C": "Book of Three Circles",
    "svnt": "Savant and Sorcerer", "S&S": "Savant and Sorcerer",
    "seas": "Savage Seas", "SAS": "Savage Seas",
    "luna": "The Lunars", "E:LU": "The Lunars",
    "abys": "The Abyssals", "E:AB": "The Abyssals",
    "outc": "The Outcaste", "side": "Sidereals", "E:SI": "Sidereals",
    "game": "Games of Divinity", "GOD": "Games of Divinity",
    "time": "Time of Tumult", "core": "Exalted Core", "E:1": "Exalted Core",
    "dbld": "Dragon-Blooded", "E:DB": "Dragon-Blooded",
    "fair": "Fair Folk (Mountain Folk ch.)",
    "salt": "Blood and Salt", "B&S": "Blood and Salt",
    "auto": "Autochthonians", "E:AU": "Autochthonians",
    "comp": "Storyteller's Companion", "ruin": "Ruins of Rathess",
    "cult": "Cult of the Illuminated", "halt": "Kingdom of Halta",
    "coin": "Manacle and Coin",
    "ab_a": "Aspect Book: Air", "ab_e": "Aspect Book: Earth",
    "ab_f": "Aspect Book: Fire", "ab_v": "Aspect Book: Water",
    "ab_w": "Aspect Book: Wood",
    "cb_d": "Caste Book: Dawn", "cb_n": "Caste Book: Night",
    "cb_t": "Caste Book: Twilight", "cb_z": "Caste Book: Zenith",
    "cb_e": "Caste Book: Eclipse",
    "E:S": "⚠ UNKNOWN CODE (`E:S` — legend omits it; likely Sidereals)",
    "?": "⚠ unresolved",
}
ONDISK = {"Caste Book: Dawn", "Caste Book: Night", "Caste Book: Twilight",
          "Caste Book: Zenith", "Caste Book: Eclipse", "Fair Folk (Mountain Folk ch.)"}

charms = json.load(open("missing_charms_full.json"))
spells = json.load(open("missing_spells_full.json"))

# --- artifacts out of the existing backlog doc
art = collections.defaultdict(list)
cur = None
for line in open("/home/gil/Projects/Exalted 1E Charsheet Generator/docs/status/artifact-backlog-entries.md"):
    m = re.match(r"^### `([a-z_0-9]+)`", line)
    if m:
        cur = m.group(1); continue
    if cur and line.startswith("|"):
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 4 and c[0] not in ("Name",) and not set(c[0]) <= set(":- "):
            if c[3] == "—":
                # Fair Folk pp.205-211 are OUT OF SCOPE (human, 2026-08-10) — they
                # follow their splat out under decision 0010. Only the Mountain Folk
                # chapter (pp.279-283, already authored) survives from this book.
                if cur == "fair":
                    continue
                art[cur].append({"name": c[0], "rating": c[1], "page": c[2]})

books = collections.defaultdict(lambda: {"charms": [], "spells": [], "artifacts": []})
for r in charms:
    books[CANON.get(r["book"], r["book"])]["charms"].append(r)
for r in spells:
    books[CANON.get(r["book"], r["book"])]["spells"].append(r)
for k, v in art.items():
    books[CANON.get(k, k)]["artifacts"] += v

order = sorted(books, key=lambda b: -(len(books[b]["charms"]) + len(books[b]["spells"]) + len(books[b]["artifacts"])))

out = []
W = out.append
W("# The content gap — every missing entry, by book\n")
W("**Generated 2026-08-10** from the three discovery indexes. This is the per-entry")
W("companion to `docs/plans/content-completeness.md`, which holds the method, the")
W("corrections and the sequencing rationale. **Read that first.**\n")
W("⚠ **This is DISCOVERY ONLY — name, book and page.** Every value (cost, minimum,")
W("prerequisite, duration, description) still comes from the human-supplied page.")
W("The indexes are fan-made and demonstrably carry errors; see the plan's correction log.\n")
W("⚠ **A name here is not proof the entry is absent from the build.** These lists")
W("already survived three filters (exact match, global fuzzy ≥0.86, same-book fuzzy")
W("≥0.75), but the build's **parameterised entries** — `Keen (Sense) Technique`,")
W("`Mantle of (Element) Invulnerability` — mean one record can legitimately cover")
W("several rows below. **Check the build before authoring.**\n")

tc = sum(len(v["charms"]) for v in books.values())
ts = sum(len(v["spells"]) for v in books.values())
ta = sum(len(v["artifacts"]) for v in books.values())
uc = len({r["name"] for r in charms})
W(f"**Totals: {tc} Charm/Arcanoi rows ({uc} unique) · {ts} spells · {ta} artifacts "
  f"= {tc+ts+ta} rows.**\n")
W(f"The Charm rows exceed unique names by {tc-uc}: the trees **cross-list** a Charm that")
W("belongs to more than one tree (`Pole the Black Depths` sits in two Arcanoi;")
W("`Vision Outside Time` in two DB abilities). Author once, wire to both.\n")

W("## Priority — combined yield per book\n")
W("| Book | Charms | Spells | Artifacts | **Total** | Pages on disk? |")
W("|---|---|---|---|---|---|")
for b in order:
    v = books[b]
    n = len(v["charms"]) + len(v["spells"]) + len(v["artifacts"])
    disk = "YES (partial)" if b in ONDISK else "**NO**"
    W(f"| {b} | {len(v['charms']) or '—'} | {len(v['spells']) or '—'} | {len(v['artifacts']) or '—'} | **{n}** | {disk} |")
W("")

for b in order:
    v = books[b]
    n = len(v["charms"]) + len(v["spells"]) + len(v["artifacts"])
    W(f"\n## {b} — {n} entries\n")
    if v["charms"]:
        W(f"### Charms / Arcanoi ({len(v['charms'])})\n")
        W("| Name | Tree | Page | Combo-OK |")
        W("|---|---|---|---|")
        for r in sorted(v["charms"], key=lambda r: (r["tree"], int(r["page"]) if r["page"].isdigit() else 0)):
            W(f"| {r['name']} | {r['tree']} | {r['page']} | {'✔' if r['combo'] else ''} |")
        W("")
    if v["spells"]:
        W(f"### Spells ({len(v['spells'])})\n")
        W("| Name | Circle | Page |")
        W("|---|---|---|")
        for r in sorted(v["spells"], key=lambda r: (r["build_circle"], r["name"])):
            cc = r["build_circle"] + (f" *(list: {r['circle']})*" if r["circle"] != r["build_circle"] else "")
            W(f"| {r['name']} | {cc} | {r['page']} |")
        W("")
    if v["artifacts"]:
        W(f"### Artifacts ({len(v['artifacts'])})\n")
        W("| Name | Rating | Page |")
        W("|---|---|---|")
        for r in sorted(v["artifacts"], key=lambda r: (r["page"], r["name"])):
            W(f"| {r['name']} | {r['rating']} | {r['page']} |")
        W("")

open("/home/gil/Projects/Exalted 1E Charsheet Generator/docs/status/content-gap-entries.md", "w").write("\n".join(out) + "\n")
print(f"{tc} charms + {ts} spells + {ta} artifacts = {tc+ts+ta}")
print(f"{len(order)} books")
