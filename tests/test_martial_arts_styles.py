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


def test_authored_styles_carry_a_printed_type_and_prose(ruleset):
    """`tier` and `preamble` are the whole point of the entity; an entry with
    neither is an empty row that makes the catalogue look complete."""
    for style in ruleset.martial_arts_styles.values():
        assert style.tier, f"{style.id} has no printed Type:"
        assert len(style.preamble) > 200, f"{style.id} has no preamble"
        assert style.source.book and style.source.page, f"{style.id} is unattributed"


def test_the_unauthored_worklist_is_the_expected_eighteen(ruleset):
    """Phase 1 ships 4 of 22 by design (docs/plans/martial-arts-styles.md), so the
    remaining 18 are a WORKLIST, not a load error — the loader must not raise on
    them or the app would not start.

    Pinned so the list can only shrink: authoring a style without removing it here
    fails, and so does silently losing one.
    """
    missing = rules_db.unauthored_martial_arts_styles(ruleset)
    assert missing == sorted([
        "martial_arts:air-dragon",
        "martial_arts:charcoal-march-of-spiders",
        "martial_arts:citrine-poxes-of-contagion",
        "martial_arts:earth-dragon",
        "martial_arts:ebon-shadow",
        "martial_arts:enlightenment",
        "martial_arts:falling-blossom",
        "martial_arts:fire-dragon",
        "martial_arts:five-dragon",
        "martial_arts:hungry-ghost",
        "martial_arts:jade-mountain",
        "martial_arts:praying-mantis",
        "martial_arts:prismatic-arrangement-of-creation",
        "martial_arts:snake",
        "martial_arts:tiger",
        "martial_arts:violet-bier-of-sorrows",
        "martial_arts:water-dragon",
        "martial_arts:wood-dragon",
    ])


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

    Skipped where the extracted book is not on this machine — `images/` is
    gitignored and does not travel (CLAUDE.md).
    """
    book = _ROOT / "images" / "_extracted" / "Player's Guide.md"
    if not book.exists():
        pytest.skip("Player's Guide extract not on this machine")
    import re
    flat = re.sub(r"\s+", " ", book.read_text(errors="replace"))
    squashed = re.sub(r"[^a-z]", "", flat.lower())

    for row in json.loads(_STYLES_JSON.read_text()):
        assert row["source"]["book"] == "Player's Guide", row["id"]
        # A distinctive clause from the middle of the preamble, squashed so the
        # extractor's spaced small-caps and line breaks cannot cause a false miss.
        probe = re.sub(r"[^a-z]", "", row["preamble"].lower())[120:260]
        assert probe in squashed, f"{row['id']}: preamble is not the printed text"


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
    """The negative control, and the reason it is a separate route: 18 styles have
    no preamble yet, and an empty box above each of their trees would be worse than
    nothing. Tiger is unauthored — the panel must not render at all."""
    await user.open("/style-unauthored")
    await user.should_not_see("Righteous Devil Style")
    await user.should_not_see("Weapons and Armor")


def test_the_generated_style_label_agrees_with_the_printed_name(ruleset):
    """`view._style_label` builds a display name from the SLUG, and the Charm detail
    card has always used it. Now that the printed name is authored, the two must
    agree — or the same style is called two different things on two surfaces.

    This will fail for the first style whose printed name is not simply its slug
    title-cased (a "Style of ..." or a possessive), which is the moment the detail
    card should start preferring the authored name.
    """
    from exalted_builder.ui import view as viewmod
    for style in ruleset.martial_arts_styles.values():
        assert viewmod._style_label(style.category) == style.name, (
            f"{style.category}: generated {viewmod._style_label(style.category)!r} "
            f"but the page prints {style.name!r}")
