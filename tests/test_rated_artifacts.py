"""Rated artifacts — the E:Ab p.131 Artifact budget and per-item Damaged Artifact.

Two printed rules needed individual artifacts to point at, and neither could be
expressed while the build had only a summed Artifact Background:

  * the loyal Abyssal's Artifact Background is a BUDGET (combined rating plus a
    per-item ceiling), not a cost curve;
  * Damaged Artifact's limit is "the rating of the artifact it modifies", per-item.

See docs/status/rated-artifacts.md. The tier-1 soak reading (−1 lethal AND −1 bashing,
rather than one point shared) is the human's ruling of 2026-08-02.

⚠ These tests exercise the BUY PATH, not just the effect — the recurring bug in this
build is a rule that is implemented but sits where it does not run. So the Damaged
Artifact tests go through `validate` and `derive.soak` rather than asserting on
`MeritEffects` fields, and the panel tests assert the controls exist at all.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import artifacts, derive, merits, validate
from exalted_builder.models.character import (Armor, ArtifactEntry, BackgroundEntry,
                                              Character, MeritFlawPurchase as MP,
                                              Weapon)

DATA_DIR = Path(exalted_builder.__file__).parent / "data"

DAMAGED = "mf.damaged-artifact"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _abyssal(origin: str = "", **kw) -> Character:
    """A loyal Abyssal by default; `origin="fugitive"` is the renegade, who uses the
    core rulebook's Artifact Background and therefore no budget at all."""
    c = Character(id="c.a", exalt_type="Abyssal", caste="Dusk", origin=origin,
                  essence_rating=2)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _art(**kw) -> ArtifactEntry:
    return ArtifactEntry(**kw)


def _bg(name: str, rating: int) -> BackgroundEntry:
    return BackgroundEntry(name=name, rating=rating)


def _codes(issues, code):
    return [i for i in issues if i.code == code]


# --- the enumeration -------------------------------------------------------- #

def test_artifact_items_folds_all_three_sources():
    """The ONE enumeration: standalone artifacts, artifact weapons, artifact armour.
    Re-entering a daiklave in `artifacts` would double-count it against the budget,
    which is exactly what folding prevents."""
    c = _abyssal(
        artifacts=[_art(name="Tattered Wings", rating=4)],
        weapons=[Weapon(name="Daiklave", artifact_rating=3),
                 Weapon(name="Hatchet")],                       # mundane: skipped
        armor=[Armor(name="Soulsteel Plate", artifact_rating=2)],
    )
    items = artifacts.artifact_items(c)
    assert [(i.name, i.rating, i.source) for i in items] == [
        ("Tattered Wings", 4, "artifact"),
        ("Daiklave", 3, "weapon"),
        ("Soulsteel Plate", 2, "armor"),
    ]
    assert artifacts.combined_rating(c) == 9


def test_unnamed_and_mundane_rows_are_not_artifacts():
    """The editor adds a blank row for the player to fill in; a blank row is not yet
    an artifact, and `artifact_rating` 0 is the mundane default rather than a
    zero-dot artifact."""
    c = _abyssal(artifacts=[_art(name="  ", rating=3)],
                 weapons=[Weapon(name="Sword", artifact_rating=0)])
    assert artifacts.artifact_items(c) == []


# --- the p.131 budget ------------------------------------------------------- #

@pytest.mark.parametrize("rating,combined,individual", [
    (1, 3, 0), (2, 5, 3), (3, 7, 4), (4, 10, 0), (5, 13, 0),
])
def test_budget_table_matches_the_page(rs, rating, combined, individual):
    """E:Ab p.131, transcribed in docs/status/rated-artifacts.md. 0 = no per-item
    ceiling, which the two top rows print ("no limit on individual level")."""
    b = rs.budgets_for("Abyssal")
    tier = artifacts.budget_tier(b, rating)
    assert (tier.combined_max, tier.individual_max) == (combined, individual)


def test_combined_rating_over_budget_is_an_error(rs):
    c = _abyssal(backgrounds=[_bg("Artifact", 2)],           # combined ≤ 5
                 artifacts=[_art(name="Wings", rating=3),
                            _art(name="Orb", rating=3)])     # 6 > 5
    assert _codes(validate.check_artifacts(rs, c), "artifact-combined-over-budget")


def test_combined_rating_within_budget_is_clean(rs):
    c = _abyssal(backgrounds=[_bg("Artifact", 2)],
                 artifacts=[_art(name="Wings", rating=3),
                            _art(name="Ring", rating=2)])     # 5 ≤ 5
    assert validate.check_artifacts(rs, c) == []


def test_individual_cap_is_a_warning_not_an_error(rs):
    """The page makes the per-item ceilings Storyteller-overridable — "none
    individually above Artifact 3 without Storyteller permission" — so they are
    reported rather than blocked, which is how every soft printed limit behaves here.
    The combined budget carries no such clause and stays an error."""
    c = _abyssal(backgrounds=[_bg("Artifact", 2)],            # individual ≤ 3
                 artifacts=[_art(name="Wings", rating=4)])
    found = _codes(validate.check_artifacts(rs, c), "artifact-item-over-cap")
    assert len(found) == 1 and found[0].severity == "warning"


def test_gear_counts_against_the_budget_too(rs):
    """An artifact daiklave is an artifact. The budget reads the folded enumeration,
    so equipment cannot be a way around it."""
    c = _abyssal(backgrounds=[_bg("Artifact", 1)],            # combined ≤ 3
                 weapons=[Weapon(name="Daiklave", artifact_rating=4)])
    assert _codes(validate.check_artifacts(rs, c), "artifact-combined-over-budget")


def test_artifacts_without_the_background_are_flagged(rs):
    c = _abyssal(artifacts=[_art(name="Wings", rating=2)])
    assert _codes(validate.check_artifacts(rs, c), "artifact-without-background")


def test_renegade_abyssals_use_the_core_background(rs):
    """p.131: "Renegade Abyssals use the Artifact Background found in Chapter Four:
    Traits of the main Exalted rulebook." The `Abyssal:fugitive` budget row must carry
    no `budget_tiers`, and the cascade must not hand it the loyal row's."""
    assert rs.budgets_for("Abyssal", "fugitive").background_rules == {}
    c = _abyssal(origin="fugitive", backgrounds=[_bg("Artifact", 1)],
                 artifacts=[_art(name="Wings", rating=5)])
    assert validate.check_artifacts(rs, c) == []


@pytest.mark.parametrize("splat,caste", [
    ("Solar", "Dawn"), ("Lunar", "Full Moon"),
])
def test_other_splats_have_no_artifact_budget(rs, splat, caste):
    """Opt-in per splat, like every other Background mechanic. Solar and Lunar have
    no Artifact rule at all; the multiplier splats (DB/DK/Alchemical) DO have a budget
    — the double/triple-dots rule — and are covered by the test below."""
    c = Character(id="c.x", exalt_type=splat, caste=caste, essence_rating=2,
                  backgrounds=[_bg("Artifact", 1)],
                  artifacts=[_art(name="Wings", rating=5)])
    assert validate.check_artifacts(rs, c) == []


def test_the_dragon_blooded_double_dots_rule_is_enforced(rs):
    """The DB/DK 'twice the dots' worth' Artifact rule was data-only — never enforced
    — until the multiplier branch of check_artifacts; a DB with Artifact • and a
    5-dot artifact was silently legal. Now it is flagged, same as the Dragon-Kings
    (test_dragonkings.py) and Alchemical (three dots per dot). The rule is a
    STRUCTURE (E:DB p.157): one flagship equal to the Background + smaller artifacts
    totaling no more than it — so a single 4-dot artifact needs Artifact 4, and the
    valid Artifact-2 build is a 2-dot flagship plus two 1-dot extras."""
    c = Character(id="c.x", exalt_type="Dragon-Blooded", caste="Fire", essence_rating=2,
                  backgrounds=[_bg("Artifact", 1)],
                  artifacts=[_art(name="Wings", rating=5)])
    codes = {i.code for i in validate.check_artifacts(rs, c)}
    assert "artifact-over-background-dots" in codes
    ok = Character(id="c.ok", exalt_type="Dragon-Blooded", caste="Fire", essence_rating=2,
                   backgrounds=[_bg("Artifact", 2)],
                   artifacts=[_art(name="Wings", rating=2), _art(name="Orb", rating=1),
                              _art(name="Charm", rating=1)])
    assert validate.check_artifacts(rs, ok) == []


def test_budget_is_checked_on_both_sides_of_the_lock(rs):
    """The Fetter-cap precedent: the ceiling is keyed to a Background that experience
    can RAISE, so a chargen-only check would go quiet exactly when the cap started
    moving. `validate` runs it regardless of `chargen_locked`."""
    c = _abyssal(backgrounds=[_bg("Artifact", 1)],
                 artifacts=[_art(name="Wings", rating=5)], chargen_locked=True)
    assert _codes(validate.validate(rs, c), "artifact-combined-over-budget")


def test_raising_the_background_lifts_the_budget(rs):
    """The moving half of the same rule, from the other direction."""
    c = _abyssal(backgrounds=[_bg("Artifact", 1)],
                 artifacts=[_art(name="Wings", rating=3), _art(name="Orb", rating=2)])
    assert _codes(validate.check_artifacts(rs, c), "artifact-combined-over-budget")
    c.backgrounds[0].rating = 3                                # combined ≤ 7
    assert validate.check_artifacts(rs, c) == []


# --- Damaged Artifact: the per-item limit ----------------------------------- #

def test_damaged_artifact_limit_reads_the_named_item_not_the_sum(rs):
    """THE bug this work closes (docs/status/rated-artifacts.md). A character with a
    4-dot and a 2-dot artifact could take the full three-point Flaw against the 2-dot
    one, because the check summed to 6."""
    c = _abyssal(backgrounds=[_bg("Artifact", 4)],
                 artifacts=[_art(name="Daiklave", rating=4), _art(name="Wings", rating=2)],
                 merits_flaws=[MP(merit_id=DAMAGED, tier="3",
                                  artifact_key="artifact:wings")])
    assert _codes(validate.validate_chargen(rs, c), "merit-points-above-background")


def test_damaged_artifact_is_legal_against_a_big_enough_item(rs):
    c = _abyssal(backgrounds=[_bg("Artifact", 4)],
                 artifacts=[_art(name="Daiklave", rating=4), _art(name="Wings", rating=2)],
                 merits_flaws=[MP(merit_id=DAMAGED, tier="3",
                                  artifact_key="artifact:daiklave")])
    assert not _codes(validate.validate_chargen(rs, c), "merit-points-above-background")


def test_the_summed_one_more_dot_rule_still_applies(rs):
    """The Flaw prints TWO constraints and both survive: "must have at least one more
    dot of Artifact than the points obtained" is against the summed Background, and is
    why the limits became plural rather than being replaced."""
    c = _abyssal(backgrounds=[_bg("Artifact", 3)],
                 artifacts=[_art(name="Daiklave", rating=3)],
                 merits_flaws=[MP(merit_id=DAMAGED, tier="3",
                                  artifact_key="artifact:daiklave")])
    # Item rating 3 permits 3 points; the summed Background 3 − 1 = 2 does not.
    assert _codes(validate.validate_chargen(rs, c), "merit-points-above-background")


def test_damaged_artifact_must_name_an_artifact(rs):
    """Unresolved is REPORTED, never defaulted — picking the character's best artifact
    for them would make an illegal purchase legal with nobody deciding to."""
    c = _abyssal(backgrounds=[_bg("Artifact", 4)],
                 artifacts=[_art(name="Daiklave", rating=4)],
                 merits_flaws=[MP(merit_id=DAMAGED, tier="1")])
    assert _codes(validate.validate_chargen(rs, c), "merit-artifact-unchosen")


def test_a_dangling_artifact_key_is_reported_not_ignored(rs):
    """Renaming an artifact changes its key. The purchase must complain rather than
    quietly stop constraining anything."""
    c = _abyssal(backgrounds=[_bg("Artifact", 4)],
                 artifacts=[_art(name="Daiklave", rating=4)],
                 merits_flaws=[MP(merit_id=DAMAGED, tier="1",
                                  artifact_key="artifact:wings")])
    assert _codes(validate.validate_chargen(rs, c), "merit-artifact-unchosen")


def test_damaged_artifact_can_name_a_weapon_or_armour(rs):
    """Artifacts live in three places, so the key must reach all three. One point,
    because a 3-dot artifact costs a loyal Abyssal one Background dot (Trinkets allows
    a combined 3) and the acquisition-cost cap binds at 1."""
    c = _abyssal(backgrounds=[_bg("Artifact", 4)],
                 armor=[Armor(name="Soulsteel Plate", artifact_rating=3)],
                 merits_flaws=[MP(merit_id=DAMAGED, tier="1",
                                  artifact_key="armor:soulsteel plate")])
    assert not _codes(validate.validate_chargen(rs, c), "merit-artifact-unchosen")
    assert not _codes(validate.validate_chargen(rs, c), "merit-points-above-background")


# --- the acquisition-cost cap (PG p.38, third clause) ----------------------- #

@pytest.mark.parametrize("splat,caste,rating,cost", [
    # Core: one dot buys one dot of artifact.
    ("Solar", "Dawn", 4, 4),
    ("Solar", "Dawn", 1, 1),
    # "Dragon-Blooded receive twice the dots' worth of artifacts" — ceiling division,
    # so a 3-dot artifact still costs 2.
    ("Dragon-Blooded", "Fire", 4, 2),
    ("Dragon-Blooded", "Fire", 3, 2),
    ("Dragon-Blooded", "Fire", 1, 1),
    # "Alchemicals receive THREE dots of artifacts per dot bought".
    ("Alchemical", "Orichalcum", 3, 1),
    ("Alchemical", "Orichalcum", 4, 2),
])
def test_acquisition_cost_by_splat(rs, splat, caste, rating, cost):
    b = rs.budgets_for(splat)
    assert artifacts.acquisition_cost(b, rating) == cost


@pytest.mark.parametrize("rating,cost", [
    (1, 1),       # Trinkets: combined ≤ 3, no individual cap
    (3, 1),       # still Trinkets — a lone 3-dot artifact fits a combined 3
    (4, 3),       # Well-Equipped: Sound Gear's combined 5 would fit, its individual 3 does not
    (5, 4),       # Supremely Appointed: the first row with no individual ceiling
])
def test_acquisition_cost_respects_the_individual_cap(rs, rating, cost):
    """⚠ This is where the build DISAGREES WITH THE BOOK, deliberately.

    p.38 prices the 4-dot tattered wings at two Abyssal Background points, reading only
    Sound Gear's "combined no higher than 5" and ignoring its "none individually above
    Artifact 3" — its own table. The human ruled 2026-08-02 that the table wins, so the
    answer here is three, not the printed two.
    """
    assert artifacts.acquisition_cost(rs.budgets_for("Abyssal"), rating) == cost


def test_the_acquisition_cost_cap_binds_before_the_rating_cap(rs):
    """"whichever is less" — the point of the clause. A Dragon-Blood's 4-dot artifact
    cost only 2 dots, so 3 points of the Flaw is illegal even though the rating allows
    it and the summed Background is high enough."""
    c = Character(id="c.db", exalt_type="Dragon-Blooded", caste="Fire", origin="dynastic",
                  essence_rating=2, backgrounds=[_bg("Artifact", 5)],
                  artifacts=[_art(name="Daiklave", rating=4)],
                  merits_flaws=[MP(merit_id=DAMAGED, tier="3",
                                   artifact_key="artifact:daiklave")])
    assert _codes(validate.validate_chargen(rs, c), "merit-points-above-background")
    c.merits_flaws[0].tier = "2"
    assert not _codes(validate.validate_chargen(rs, c), "merit-points-above-background")


def test_the_multiplier_survives_every_dragonblooded_origin(rs):
    """The keyed-table cascade REPLACES rather than merges, so a multiplier authored
    only on the base row would be silently lost by every origin beneath it. This is the
    `highest_magic_circle_id` trap in another costume."""
    for origin, upbringing in [("", ""), ("dynastic", ""), ("outcaste", ""),
                               ("lookshy", ""), ("lookshy", "foreign"),
                               ("forest-witch", ""), ("forest-witch", "oreithyia"),
                               ("lost-egg", ""), ("lost-egg", "patrician"),
                               ("pirate", ""), ("pirate", "outcaste")]:
        b = rs.budgets_for("Dragon-Blooded", origin, upbringing)
        assert artifacts.acquisition_cost(b, 4) == 2, (origin, upbringing)


# --- Damaged Artifact: the armour soak effect ------------------------------- #

def _armored(points: int, **kw) -> Character:
    return _abyssal(
        backgrounds=[_bg("Artifact", 5)],
        armor=[Armor(name="Plate", soak_lethal=8, soak_bashing=10, artifact_rating=3)],
        merits_flaws=[MP(merit_id=DAMAGED, tier=str(points),
                         artifact_key="armor:plate")] if points else [],
        **kw)


def test_undamaged_armour_soaks_normally(rs):
    c = _armored(0)
    s = derive.soak(c, rs)
    assert (s.armor_lethal, s.armor_bashing) == (8, 10)


@pytest.mark.parametrize("points,lethal,bashing", [
    (1, 7, 9),        # −1 from EACH track (human's ruling, 2026-08-02)
    (2, 5, 7),        # the printed "six points", ruled to split 3 and 3
    (3, 0, 0),        # "the artifact is presently useless"
])
def test_damaged_armour_loses_soak(rs, points, lethal, bashing):
    s = derive.soak(_armored(points), rs)
    assert (s.armor_lethal, s.armor_bashing) == (lethal, bashing)


def test_soak_floors_at_zero(rs):
    """A damaged artifact never soaks negatively."""
    c = _abyssal(backgrounds=[_bg("Artifact", 5)],
                 armor=[Armor(name="Rag", soak_lethal=1, soak_bashing=2,
                              artifact_rating=2)],
                 merits_flaws=[MP(merit_id=DAMAGED, tier="2",
                                  artifact_key="armor:rag")])
    s = derive.soak(c, rs)
    assert (s.armor_lethal, s.armor_bashing) == (0, 0)


def test_damage_applies_to_the_named_piece_only(rs):
    """Two suits, one damaged. The reduction must not spill onto the other."""
    c = _abyssal(backgrounds=[_bg("Artifact", 5)],
                 armor=[Armor(name="Plate", soak_lethal=8, soak_bashing=10,
                              artifact_rating=3),
                        Armor(name="Buff Jacket", soak_lethal=2, soak_bashing=4)],
                 merits_flaws=[MP(merit_id=DAMAGED, tier="1",
                                  artifact_key="armor:plate")])
    s = derive.soak(c, rs)
    assert (s.armor_lethal, s.armor_bashing) == (7 + 2, 9 + 4)


def test_damage_applies_after_the_magical_material_bonus(rs):
    """Order matters: applying the reduction FIRST would let a magical material repair
    the damage. The Flaw describes what the item lost from what it actually provides."""
    c = _abyssal(backgrounds=[_bg("Artifact", 5)],
                 armor=[Armor(name="Plate", soak_lethal=8, soak_bashing=10,
                              artifact_rating=3, material="soulsteel")],
                 merits_flaws=[MP(merit_id=DAMAGED, tier="1",
                                  artifact_key="armor:plate")])
    plain = derive.effective_armor(rs, c, c.armor[0])
    s = derive.soak(c, rs)
    assert (s.armor_lethal, s.armor_bashing) == (plain.soak_lethal - 1,
                                                 plain.soak_bashing - 1)


def test_a_damaged_weapon_changes_no_derivation(rs):
    """Decision 0008: a weapon losing "a point of damage or accuracy" is combat
    derivation, which this build does not do. It is still recorded and displayed."""
    c = _abyssal(backgrounds=[_bg("Artifact", 5)],
                 weapons=[Weapon(name="Daiklave", damage=4, accuracy=2,
                                 artifact_rating=3)],
                 merits_flaws=[MP(merit_id=DAMAGED, tier="2",
                                  artifact_key="weapon:daiklave")])
    w = derive.effective_weapon(rs, c, c.weapons[0])
    assert (w.damage, w.accuracy) == (4, 2)
    effects = merits.merits_and_flaws_calc(rs, c)
    assert effects.damaged_artifacts == {"weapon:daiklave": 2}


def test_two_purchases_against_one_item_take_the_worse(rs):
    """"Presently useless" cannot be exceeded, and the tiers describe one artifact's
    condition rather than stacking damage."""
    c = _abyssal(backgrounds=[_bg("Artifact", 5)],
                 armor=[Armor(name="Plate", soak_lethal=8, soak_bashing=10,
                              artifact_rating=4)],
                 merits_flaws=[MP(merit_id=DAMAGED, tier="1",
                                  artifact_key="armor:plate"),
                               MP(merit_id=DAMAGED, tier="2",
                                  artifact_key="armor:plate")])
    assert merits.merits_and_flaws_calc(rs, c).damaged_artifacts == {"armor:plate": 2}


def test_soak_without_a_ruleset_does_not_apply_damage(rs):
    """Documented, not desirable: the optional `ruleset` makes an omission a silent
    wrong answer. Pinned so the docstring warning cannot quietly stop being true."""
    c = _armored(3)
    assert derive.soak(c).armor_lethal == 8
    assert derive.soak(c, rs).armor_lethal == 0


# --- the UI: every field must be both editable and displayed ---------------- #
#
# The dead-field bug's specific shape here: `Character.artifacts` and
# `MeritFlawPurchase.artifact_key` are written by hand-authored data and by the
# validator, and if neither appears in an editor the next save wipes them. These
# tests are the read sites, in the same spirit as the adversary roster's.

import pytest  # noqa: E402  (the engine tests above run without NiceGUI)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_artifacts_panel_edits_and_shows_the_budget(user) -> None:
    """Artifact 3 is Well-Equipped: combined ≤ 7. The character owns 2 + 3 + 2 = 7,
    so the header must print 7/7 — and the weapon and armour must be named as counted,
    or the total looks wrong beside a panel listing one 2-dot item."""
    await user.open('/artifacts-advantages')
    await user.should_see("Artifacts")
    await user.should_see("7/7 combined")
    await user.should_see("Well-Equipped")
    await user.should_see("Tattered Wings")
    await user.should_see("Also counted, from equipment")
    await user.should_see("Soulsteel Daiklave (3)")
    await user.should_see("Grave Plate (2)")
    await user.should_see("Add artifact")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_damaged_artifact_offers_an_artifact_picker(user) -> None:
    """Without this control the Flaw's limit could never be satisfied and its soak
    effect never fired. The options must span all three sources — a picker that only
    offered standalone artifacts would leave a damaged daiklave unnameable."""
    from nicegui import ui as _ui
    await user.open('/artifacts-advantages')
    await user.should_see("Damaged Artifact")
    picker = next(e for e in user.client.elements.values()
                  if isinstance(e, _ui.select) and e.props.get("label") == "Artifact")
    assert set(picker.options) == {
        "artifact:tattered wings", "weapon:soulsteel daiklave", "armor:grave plate"}
    assert picker.value == "armor:grave plate"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_artifacts_panel_is_on_the_bar_post_lock(user) -> None:
    """Artifacts are equipment: they change in play through the story, so the panel
    stays editable past the lock rather than turning into a frozen chargen choice."""
    await user.open('/artifacts-advantages-xp')
    await user.should_see("Artifacts")
    await user.should_see("Tattered Wings")
    await user.should_see("Add artifact")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_splat_with_no_budget_still_edits_artifacts(user) -> None:
    """The budget is opt-in; the list is not. A Solar owns artifacts too — the page's
    own worked example is a Solar's — they are just not budgeted by a table."""
    await user.open('/artifacts-advantages-solar')
    await user.should_see("Artifacts")
    await user.should_see("Tattered Wings")
    await user.should_not_see("combined")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_sheet_shows_artifacts_and_marks_the_damaged_one(user) -> None:
    """A damaged artifact says so: its soak is already reduced in the numbers above,
    and an unexplained low figure reads as a bug rather than as the Flaw working."""
    await user.open('/artifacts-sheet')
    await user.should_see("Artifacts")
    await user.should_see("Tattered Wings")
    await user.should_see("Soulsteel Daiklave")
    await user.should_see("Grave Plate")
    await user.should_see("−1")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_picker_survives_owning_no_artifacts(user) -> None:
    """Preflight pass 2, the NiceGUI build-time crash class: a `ui.select` raises when
    its value is not among its options, and the raise takes the whole tab down with its
    siblings. Empty options with no value chosen must build, and must SAY why the
    picker is empty rather than showing a dead dropdown."""
    await user.open('/artifacts-advantages-none')
    await user.should_see("Damaged Artifact")
    await user.should_see("no artifacts owned")
    # The siblings are the real assertion: a crash here blanks the whole tab.
    await user.should_see("Backgrounds")
    await user.should_see("Artifacts")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_renamed_artifact_leaves_a_labelled_stale_option(user) -> None:
    """The same crash class from the other direction: a stored key that resolves to
    nothing must stay selectable and be labelled, not vanish or raise."""
    from nicegui import ui as _ui
    await user.open('/artifacts-advantages-stale')
    picker = next(e for e in user.client.elements.values()
                  if isinstance(e, _ui.select) and e.props.get("label") == "Artifact")
    assert picker.value == "artifact:old name"
    assert "(missing)" in picker.options["artifact:old name"]
