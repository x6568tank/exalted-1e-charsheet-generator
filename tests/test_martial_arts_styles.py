"""
tests/test_martial_arts_styles.py — the martial-arts STYLE entity.

Plan: docs/plans/martial-arts-styles.md. Two tests here matter more than the rest:

* `test_every_charm_in_a_style_agrees_on_who_may_learn_it` is the one that started
  this job. Style-level access is authored per-CHARM (open_to_all, open_to_tiers,
  restricted_to, immaculate), so one Charm can silently disagree with its own style
  — and one does. It ships with exactly one documented exception, and the exception
  SET is asserted, so a second divergence fails instead of joining an allowlist.

* `test_no_engine_module_reads_the_style_catalogue` pins the Phase-1 boundary. The
  style's printed `Type:` and the Charms' `open_to_tiers` describe one fact; while
  both exist, only the Charm fields may be live.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from exalted_builder import rules_db
from exalted_builder.models.rules import Charm, MartialArtsStyle, Source

_ROOT = Path(__file__).resolve().parents[1]
_DATA_DIR = _ROOT / "exalted_builder" / "data"
_STYLES_JSON = _DATA_DIR / "martial_arts_styles.json"

#: The human ruled this CORRECT AS PRINTED, 2026-08-14. "Blessing of Righteous Solar
#: Spark Meditation" (PG p.255) sits in a Type: Celestial style but its own text
#: names the Solar Exalted, so it is genuinely narrower than the style around it.
#: Recorded as data because a bare inconsistency reads as an authoring slip forever
#: — the next person to run a consistency check would "fix" it.
_DOCUMENTED_ACCESS_EXCEPTIONS = {
    "solar.martial-arts.righteous-devil.blessing-of-righteous-solar-spark-meditation",
}


@pytest.fixture(scope="module")
def ruleset():
    return rules_db.load_ruleset(_DATA_DIR)


def _ma_charms(ruleset):
    out: dict[str, list[Charm]] = {}
    for charm in ruleset.charms.values():
        if charm.category.startswith("martial_arts:"):
            out.setdefault(charm.category, []).append(charm)
    return out


# --------------------------------------------------------------------------- #
# The consistency test — the reason this entity exists
# --------------------------------------------------------------------------- #

def test_every_charm_in_a_style_agrees_on_who_may_learn_it(ruleset):
    """A style's access rules are a property of the STYLE, but they are authored on
    every one of its Charms. One Charm missing a flag means a learner can take 11
    Charms of a style and not the 12th, which no page says.

    This found Righteous Devil. Anything else it finds is a new bug.
    """
    divergent = {}
    for category, charms in sorted(_ma_charms(ruleset).items()):
        keyed = {}
        for charm in charms:
            if charm.id in _DOCUMENTED_ACCESS_EXCEPTIONS:
                continue
            keyed[charm.id] = (charm.open_to_all,
                               tuple(sorted(charm.open_to_tiers)),
                               tuple(sorted(charm.restricted_to)),
                               charm.immaculate)
        if len(set(keyed.values())) > 1:
            divergent[category] = keyed
    assert not divergent, (
        "these styles disagree with themselves about who may learn them:\n"
        + "\n".join(f"  {c}: {sorted(set(v.values()))}" for c, v in divergent.items()))


def test_the_documented_exception_set_is_exactly_what_the_human_ruled(ruleset):
    """Pin the exception list itself. Without this, the consistency test above
    degrades into an allowlist that quietly absorbs every new divergence."""
    assert len(_DOCUMENTED_ACCESS_EXCEPTIONS) == 1
    charm_id, = _DOCUMENTED_ACCESS_EXCEPTIONS
    charm = ruleset.charms[charm_id]
    assert charm.category == "martial_arts:righteous-devil"
    # The ruling was that it is NARROWER than its style: the style is Celestial and
    # the other Charms open to Celestials, this one does not.
    assert charm.open_to_tiers == []
    peers = [c for c in _ma_charms(ruleset)["martial_arts:righteous-devil"]
             if c.id != charm_id]
    assert peers and all(c.open_to_tiers == ["Celestial"] for c in peers)


# --------------------------------------------------------------------------- #
# The Phase-1 boundary
# --------------------------------------------------------------------------- #

def test_no_engine_module_reads_the_style_catalogue():
    """`MartialArtsStyle.tier` is DISPLAY ONLY. It and the Charms' `open_to_tiers`
    describe one fact, and two live descriptions of one rule disagree — the shape
    decision 0011 exists to prevent.

    If the styles should later own access, that is a migration with the per-Charm
    fields REMOVED, and this test is changed on purpose as part of it.
    """
    offenders = []
    for path in (_ROOT / "exalted_builder" / "engine").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "martial_arts_styles":
                offenders.append(f"{path.name}:{node.lineno}")
            elif isinstance(node, ast.Name) and node.id == "MartialArtsStyle":
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        "engine/ reads the style catalogue at " + ", ".join(offenders)
        + " — access is still decided by the Charm fields; see the plan")


# --------------------------------------------------------------------------- #
# Catalogue integrity
# --------------------------------------------------------------------------- #

def test_every_style_resolves_to_charms(ruleset):
    """A style whose category no Charm uses is a slug typo: it would load clean and
    never appear anywhere."""
    used = set(_ma_charms(ruleset))
    for style in ruleset.martial_arts_styles.values():
        assert style.category in used, f"{style.id} -> {style.category} matches no Charm"


def test_styles_are_keyed_by_id_and_have_one_category_each(ruleset):
    styles = list(ruleset.martial_arts_styles.values())
    assert len(styles) == len({s.category for s in styles}), "two styles share a category"
    for style in styles:
        assert style.id.startswith("style."), style.id
        assert style.category.startswith("martial_arts:"), style.category


def test_authored_styles_carry_something_printed_and_an_attribution(ruleset):
    """An entry with nothing in it is an empty row that makes the catalogue look
    complete, so every style must carry at least one of the three printed things.

    ⚠ This test used to demand `tier` AND a 200-character `preamble`, which the
    Phase-1 four happened to satisfy because all four come from the Player's Guide
    — the one book that prints a `Type:` line and prose for every style. Phase 2
    found that most books print NEITHER: eleven styles have only a "Weapons and
    Armor" sidebar above the Charm list (Tiger, Ebon Shadow, the five Dragon Paths,
    Violet Bier). Tightening this back would force a tier to be invented from
    memory, which decision 0001 forbids.
    """
    for style in ruleset.martial_arts_styles.values():
        assert style.tier or style.preamble or style.mechanics, \
            f"{style.id} is an empty entry"
        assert style.source.book and style.source.page, f"{style.id} is unattributed"


def test_the_worklist_is_down_to_one_documented_absence(ruleset):
    """Phase 2 authored 17 of the 18. The one left is NOT pending work:

    * `enlightenment` — not a style at all but the Dragon Path initiation tree
      (`ui/picker.py` says so), whose two Charms sit under the chapter's Spirit
      Walking prose. Its one style-level rule, the Dragon Paths and Elements
      sidebar, is carried by the five Dragon Path styles it gates.

    ⚠ `snake` and `hungry-ghost` were briefly recorded here as documented absences
    too, on the strength of their OWN pages printing nothing. That was wrong, and
    the way it was wrong is the lesson: **a style's rules need not be printed with
    its Charms.** The Player's Guide p.200 `MARTIAL ARTS WEAPONS` table exists
    specifically to supply form weapons for "some martial arts from early in the
    game's publication history [that] are not explicitly associated with weapon
    types" — Snake, Hungry Ghost and Five-Dragon among them. Checking the style's
    own chapter is necessary and NOT sufficient.

    Still pinned so the list can only shrink.
    """
    missing = rules_db.unauthored_martial_arts_styles(ruleset)
    assert missing == ["martial_arts:enlightenment"]


def test_a_slug_typo_in_a_style_is_a_load_error(tmp_path):
    """The style->Charm direction IS fatal, unlike the worklist direction: a style
    pointing at a category nothing uses is a mistake, not pending work."""
    problems: list[str] = []
    charm = Charm(id="c1", name="C", category="martial_arts:tiger", cost={},
                  type="Simple", duration="Instant")
    rules_db._check_martial_arts_styles(
        {"s": MartialArtsStyle(id="style.typo", name="T",
                               category="martial_arts:tigre")},
        {"c1": charm}, problems)
    assert problems and "tigre" in problems[0]


def test_a_homebrew_only_style_is_not_reported_as_unauthored():
    """custom_content mints `martial_arts:<slug>` at runtime and there is no page to
    write a preamble from. Decision 0012: homebrew must never break the load."""
    class _RS:
        charms = {"h": Charm(id="h", name="H", category="martial_arts:my-style",
                             cost={}, type="Simple", duration="Instant", custom=True)}
        martial_arts_styles: dict = {}
    assert rules_db.unauthored_martial_arts_styles(_RS()) == []

    # Negative control: the SAME category, printed rather than homebrew, IS work.
    class _RS2(_RS):
        charms = {"p": Charm(id="p", name="P", category="martial_arts:my-style",
                             cost={}, type="Simple", duration="Instant")}
    assert rules_db.unauthored_martial_arts_styles(_RS2()) == ["martial_arts:my-style"]


# --------------------------------------------------------------------------- #
# Source fidelity
# --------------------------------------------------------------------------- #

def test_authored_preambles_match_the_printed_page():
    """Every authored style's prose must actually come off its page. Guards the one
    thing delegation and haste both break: a plausible paraphrase.

    ⚠ It can only check styles whose book has an extract in `images/_extracted/`,
    and `images/` is gitignored, so which rows are checked is MACHINE-DEPENDENT —
    the same deferral the M&F source-text test makes (CLAUDE.md, Status). Phase 2's
    other eleven books are pure scans or text-layer PDFs under `sources/`, which is
    gitignored too; they were read page by page instead, and the page is recorded in
    each row's `source`.
    """
    import re
    extracts = {"Player's Guide": "Player's Guide.md", "Core": "Exalted Core.md"}
    cache: dict[str, str] = {}
    checked = 0
    for row in json.loads(_STYLES_JSON.read_text()):
        if not row["preamble"]:
            continue                       # a page that prints only a rules sidebar
        filename = extracts.get(row["source"]["book"])
        if filename is None:
            continue                       # book not extracted — read on the page
        if filename not in cache:
            path = _ROOT / "images" / "_extracted" / filename
            if not path.exists():
                cache[filename] = ""
            else:
                flat = re.sub(r"\s+", " ", path.read_text(errors="replace"))
                cache[filename] = re.sub(r"[^a-z]", "", flat.lower())
        squashed = cache[filename]
        if not squashed:
            continue                       # extract not on this machine
        # A distinctive clause from the middle of the preamble, squashed so the
        # extractor's spaced small-caps and line breaks cannot cause a false miss.
        probe = re.sub(r"[^a-z]", "", row["preamble"].lower())[120:260]
        assert probe in squashed, f"{row['id']}: preamble is not the printed text"
        checked += 1
    if not checked:
        pytest.skip("no extracted book for any authored style on this machine")


# --------------------------------------------------------------------------- #
# The picker panel
# --------------------------------------------------------------------------- #

@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_an_authored_style_shows_its_preamble_and_rules(user) -> None:
    """The whole point of the entity, on screen: the style's Type, its prose and
    its Weapons-and-Armor rule, above the Charm tree."""
    await user.open("/style-authored")
    await user.should_see("Righteous Devil Style — Celestial")
    await user.should_see("Player's Guide p.254")
    # The header alone would pass on an empty expansion. Assert the PROSE and the
    # style-level RULE — the two things that had nowhere to live before this entity.
    await user.should_see("precepts of those who would walk in the footsteps")
    await user.should_see("as helpless as a disarmed swordsman")


@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_an_unauthored_style_shows_no_empty_panel(user) -> None:
    """The negative control, and the reason it is a separate route: three styles
    has no entry at all, and an empty box above its tree would be worse than
    nothing. `martial_arts:enlightenment` is that one — the Dragon Path initiation
    tree, not a style — so the panel must not render at all.

    ⚠ This route has now gone stale TWICE in one session. It pointed at Tiger,
    which Phase 2 authored; re-pointed at Snake, which the Player's Guide sweep
    then authored. Both times it kept PASSING, because each newly-authored style
    happened not to contain the literal string being asserted absent. A negative
    control aimed at something that later becomes positive does not fail — it
    silently stops testing anything. Re-point it, never relax the assertion."""
    await user.open("/style-unauthored")
    await user.should_not_see("Righteous Devil Style")
    await user.should_not_see("Weapons and Armor")


def test_the_generated_style_label_agrees_with_the_printed_name(ruleset):
    """`view._style_label` builds a display name from the SLUG, and the Charm detail
    card has always used it. Now that the printed name is authored, the two must
    agree — or the same style is called two different things on two surfaces.

    Phase 1 predicted this would fail for the first style whose printed name is not
    its slug title-cased, and Phase 2 produced it: `martial_arts:praying-mantis` is
    printed **Mantis Style** (Caste Book: Eclipse p.73). As predicted, the fix was
    for the label to prefer the authored name — so this now asserts that it does.
    """
    from exalted_builder.ui import view as viewmod
    for style in ruleset.martial_arts_styles.values():
        got = viewmod._style_label(style.category, ruleset)
        assert got == style.name, (
            f"{style.category}: generated {got!r} but the page prints {style.name!r}")
    # The slug fallback must survive for homebrew, which has no catalogue entry.
    assert viewmod._style_label("martial_arts:my-own", ruleset) == "My Own Style"
    # And a style whose printed name IS the slug title-cased must agree both ways,
    # so the fallback cannot drift away from the authored names unnoticed.
    assert viewmod._style_label("martial_arts:ebon-shadow") == "Ebon Shadow Style"


def test_the_panel_heading_omits_an_absent_tier():
    """A style with no printed `Type:` must not render "Air Dragon Style — " with a
    dangling separator.

    ⚠ **This is a SYNTHETIC fixture on purpose, and it is the fourth time this
    session that a control lost its subject.** It began as a render route pointed at
    Air Dragon, which gained a tier from the Player's Guide initiation sweep; it was
    re-pointed at Ebon Shadow, which gained one from the human's ruling that all four
    remaining styles are Celestial. **Every style in the catalogue now has a tier**,
    so there is no real subject left — and a control aimed at nothing keeps passing
    while testing nothing.

    The tier-less path is still reachable: `MartialArtsStyle.tier` defaults to "",
    homebrew styles have no catalogue entry at all, and the next book read may print
    a style with no `Type:` line. So the branch is kept and tested against a
    constructed StyleView, which cannot be authored out from under it.
    """
    from exalted_builder.ui.view import StyleView
    tierless = StyleView(name="Some Style", tier="", preamble="",
                         mechanics=["a rule"], source_label="Book p.1")
    assert tierless.heading == "Some Style"
    assert "—" not in tierless.heading
    assert StyleView(name="Some Style", tier="Celestial", preamble="",
                     mechanics=[], source_label="").heading == "Some Style — Celestial"


@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_style_with_rules_but_no_prose_renders_no_empty_label(user) -> None:
    """The other half of the same shape, which DOES still have real subjects: TEN
    styles print a rules sidebar and no prose — Snake, Tiger, Ebon Shadow, Violet
    Bier, Hungry Ghost and the five Dragon Paths. The panel must show the rule and
    not an empty paragraph above it."""
    await user.open("/style-rules-only")
    await user.should_see("Ebon Shadow Style")
    await user.should_see("fighting chains and sai freely")
    # Premise guard: this only tests anything while its subject has no preamble.
    ruleset = rules_db.load_ruleset(_DATA_DIR)
    style, = [s for s in ruleset.martial_arts_styles.values()
              if s.category == "martial_arts:ebon-shadow"]
    assert style.preamble == "", (
        "the /style-rules-only route's subject gained a preamble — re-point it at a "
        "style that still has none, or rebuild it synthetically as the heading test was")


# --------------------------------------------------------------------------- #
# Access: the PG p.235 rules, added 2026-08-14
# --------------------------------------------------------------------------- #

def _char(splat, caste="", charms=()):
    from exalted_builder.models.character import Character
    return Character(id="x", name="x", exalt_type=splat, caste=caste,
                     essence=3, abilities={"martial_arts": 5}, charms=list(charms))


_IMMACULATE_PAIR = ["dragonblooded.martial-arts.spirit-sight",
                    "dragonblooded.martial-arts.spirit-walking"]


def test_ma_tier_is_projected_from_the_style_and_never_authored(ruleset):
    """`Charm.ma_tier` has ONE authored home — `MartialArtsStyle.tier` — and the
    loader projects it. Authoring it in a charms JSON is the two-live-descriptions
    shape decision 0011 exists to prevent, so assert the projection agrees with the
    catalogue for every Charm, and that no charms file sets it."""
    tiers = {s.category: s.tier for s in ruleset.martial_arts_styles.values()}
    for charm in ruleset.charms.values():
        assert charm.ma_tier == tiers.get(charm.category, ""), charm.id
    for path in (_DATA_DIR / "charms").glob("*.json"):
        for row in json.loads(path.read_text()):
            assert "ma_tier" not in row, f"{path.name}:{row.get('id')} authors ma_tier"


def test_an_initiated_dragon_blood_reaches_celestial_martial_arts(ruleset):
    """PG pp.235-236: "It is possible for the Terrestrial Exalted to practice
    Celestial martial arts." The initiation machinery (three Charm pairs,
    `db_enlightenment_met`) already existed and GATED the styles; nothing GRANTED
    them, because a Dragon-Blood reached her own Dragon Paths by splat ownership.

    Celestial Monkey is the witness: it has carried `open_to_tiers: ["Celestial"]`
    all along and an initiated Dragon-Blood was still refused it.
    """
    from exalted_builder.engine import validate as V
    monkey = next(c for c in ruleset.charms.values()
                  if c.category == "martial_arts:celestial-monkey")
    assert V.charm_matches_splat(
        _char("Dragon-Blooded", "earth", _IMMACULATE_PAIR), monkey, ruleset)
    assert not V.charm_matches_splat(_char("Dragon-Blooded", "earth"), monkey, ruleset)


def test_the_celestial_grant_is_scoped_to_dragon_blooded_not_to_the_tier(ruleset):
    """⚠ The trap this branch nearly shipped with. FOUR splats are Terrestrial-tier
    — Dragon-Blooded, Dragon-Kings, God-Blooded, Mountain-Folk — and
    `db_enlightenment_met` returns True for every NON-Dragon-Blood, since they need
    no initiation. A tier-scoped grant therefore hands the other three every
    Celestial style for free, having met no initiation at all.

    PG p.235 also bars one outright: "Dragon Kings ... can never master anything
    other than Terrestrial styles designed specifically for Dragon Kings."
    """
    from exalted_builder.engine import validate as V
    terrestrial = [k for k, e in ruleset.exalts.items() if e.tier == "Terrestrial"]
    assert set(terrestrial) >= {"Dragon-Blooded", "Dragon-Kings", "Mountain-Folk"}, \
        "the trap this test guards depends on there being several Terrestrial splats"
    monkey = next(c for c in ruleset.charms.values()
                  if c.category == "martial_arts:celestial-monkey")
    for splat in terrestrial:
        if splat == "Dragon-Blooded":
            continue
        assert not V.charm_matches_splat(_char(splat), monkey, ruleset), splat


def test_a_lunar_may_never_learn_sidereal_martial_arts(ruleset):
    """PG p.235, inside the LUNAR MARTIAL ARTISTS section: "They may not learn
    Sidereal martial arts under any circumstances."

    ⚠ "They" is the LUNAR Exalted, not the Celestial tier — the sentence sits in
    that section. So Solars and Abyssals keep their tier-granted access and only
    Lunars are barred. Both halves are asserted; a bar written against the tier
    would pass the first and fail the second.
    """
    from exalted_builder.engine import validate as V
    sidereal_ma = [c for c in ruleset.charms.values() if c.ma_tier == "Sidereal"]
    assert sidereal_ma
    for charm in sidereal_ma:
        assert not V.charm_matches_splat(_char("Lunar", "full-moon"), charm, ruleset)
    open_charm = next(c for c in sidereal_ma if c.open_to_tiers)
    assert V.charm_matches_splat(_char("Solar", "dawn"), open_charm, ruleset)
    assert V.charm_matches_splat(_char("Abyssal", "dusk"), open_charm, ruleset)


def test_snake_and_tiger_are_celestial_styles(ruleset):
    """The human's ruling, 2026-08-14: Snake and Tiger are Celestial styles, open to
    the Celestial Exalted and to Dragon-Blooded who hold an initiation pair.

    Printed support beyond the PG p.236 `Examples:` line that names both: Sidereals
    p.195 describes a Sidereal invoking "Tiger Form and Ebon Shadow Form or Snake
    Form and Charcoal March of Spiders Form", and DB p.241's sidebar says "if
    taught, the Dragon-Blooded could master Snake Style, Tiger Style or any of the
    other styles more commonly practiced by the Anathema."
    """
    from exalted_builder.engine import validate as V
    for category in ("martial_arts:snake", "martial_arts:tiger"):
        charms = [c for c in ruleset.charms.values() if c.category == category]
        assert charms and all(c.open_to_tiers == ["Celestial"] for c in charms), category
        assert all(c.ma_tier == "Celestial" for c in charms), category
        entry = charms[0]
        assert V.charm_matches_splat(_char("Lunar", "full-moon"), entry, ruleset)
        assert V.charm_matches_splat(
            _char("Dragon-Blooded", "earth", _IMMACULATE_PAIR), entry, ruleset)
        assert not V.charm_matches_splat(_char("Dragon-Blooded", "earth"), entry, ruleset)


def test_no_second_style_label_generator_disagrees_with_the_authored_name(ruleset):
    """⚠ FOUND IN THE CLICK-THROUGH, 2026-08-14. `view._style_label` was taught to
    prefer the authored style name — and the picker's category DROPDOWN kept its own
    independent generator, `picker._pretty`, which title-cased the slug. So the
    preamble panel said "Mantis Style" while the dropdown above it said
    "Praying-Mantis", on the same screen, for the same style.

    Two implementations of one fact is the shape decision 0011 exists to prevent, and
    a passing suite did not notice because each was tested on its own.

    ⚠ `.title()` also never repaired the hyphen, so every multi-word slug was wrong:
    "Charcoal-March-Of-Spiders", "Violet-Bier-Of-Sorrows".
    """
    from exalted_builder.ui import picker as pickermod
    import inspect
    src = inspect.getsource(pickermod.build_picker)
    assert "_style_label" in src, (
        "picker no longer defers to view._style_label — a second label generator has "
        "come back; the dropdown and the preamble panel will disagree")

    # And assert the labels themselves, so the deferral cannot regress into a
    # lookalike that reintroduces the slug.
    from exalted_builder.ui import view as viewmod
    for category, expected in (
            ("martial_arts:praying-mantis", "Mantis Style"),
            ("martial_arts:charcoal-march-of-spiders", "Charcoal March of Spiders Style"),
            ("martial_arts:violet-bier-of-sorrows", "Violet Bier of Sorrows Style")):
        label = viewmod._style_label(category, ruleset)
        assert label == expected, category
        assert "-" not in label, f"{category}: slug hyphen leaked into {label!r}"
