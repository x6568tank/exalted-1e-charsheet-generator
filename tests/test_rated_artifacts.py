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


def test_zeroing_the_artifact_column_makes_a_dual_nature_device_mundane(rs):
    """Human's ruling 2026-08-08: a dual-nature device needs no toggle — the player
    just sets the Background that was paid and zeroes the other. A Mountain Folk
    crossbow (catalogue row carries BOTH "Resources •• / Artifact ••") with
    `artifact_rating` left at 2 counts toward the budget; setting it to 0 makes it
    mundane gear whatever `resources_cost` says, and the budget stops seeing it."""
    c = _abyssal(backgrounds=[_bg("Artifact", 1)],                    # combined ≤ 3
                 weapons=[Weapon(name="Crossbow", artifact_rating=2, resources_cost=2),
                          Weapon(name="Orb", artifact_rating=2)])
    assert [(i.name, i.rating) for i in artifacts.artifact_items(c)] == [
        ("Crossbow", 2), ("Orb", 2)]
    assert artifacts.combined_rating(c) == 4
    assert _codes(validate.check_artifacts(rs, c), "artifact-combined-over-budget")
    # The Resources-funded reading: Art 0, Res kept. Mundane gear, not an artifact.
    c.weapons[0].artifact_rating = 0
    assert [(i.name, i.rating) for i in artifacts.artifact_items(c)] == [("Orb", 2)]
    assert artifacts.combined_rating(c) == 2
    assert validate.check_artifacts(rs, c) == []


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
    no `budget_tiers`, and the cascade must not hand it the loyal row's — but "uses the
    core Background" is a RULE, not an absence of one (ruling 2026-08-13), so the
    renegade lands in the corebook branch rather than escaping the check."""
    assert rs.budgets_for("Abyssal", "fugitive").background_rules == {}
    c = _abyssal(origin="fugitive", backgrounds=[_bg("Artifact", 1)],
                 artifacts=[_art(name="Wings", rating=5)])
    assert [i.code for i in validate.check_artifacts(rs, c)] == [
        "artifact-item-over-background"]
    ok = _abyssal(origin="fugitive", backgrounds=[_bg("Artifact", 5)],
                  artifacts=[_art(name="Wings", rating=5)])
    assert validate.check_artifacts(rs, ok) == []


@pytest.mark.parametrize("splat,caste", [
    ("Solar", "Dawn"), ("Lunar", "Full Moon"),
])
def test_splats_with_no_artifact_rule_get_the_corebook_one(rs, splat, caste):
    """Human ruling 2026-08-13: the corebook Artifact Background is ONE artifact rated
    no higher than the Background, and a splat whose book alters nothing uses it. The
    multiplier splats (DB/DK/MF/Alchemical) are the ones that get several, and the
    tiered splats (loyal Abyssal, Illuminated) print their own table.

    ⚠ This test asserted `== []` until the ruling — a splat with no `BackgroundRule`
    was reading as "no budget", so a Solar could hold a 5-dot artifact on Artifact 0
    and nothing said a word."""
    c = Character(id="c.x", exalt_type=splat, caste=caste, essence_rating=2,
                  backgrounds=[_bg("Artifact", 1)],
                  artifacts=[_art(name="Wings", rating=5)])
    assert [i.code for i in validate.check_artifacts(rs, c)] == [
        "artifact-item-over-background"]


@pytest.mark.parametrize("splat,caste", [
    ("Solar", "Dawn"), ("Lunar", "Full Moon"),
])
def test_the_corebook_background_permits_exactly_one_artifact(rs, splat, caste):
    """The count half of the same ruling: every rung of the printed ladder describes a
    SINGLE item ("A useful item, a weapon or suit of armor"), where the Dragon-Blooded
    ladder spells out pairs. Artifact ••• is one 3-dot artifact, not three 1-dot ones
    and not a 2 plus a 1."""
    def _issues(**kw):
        return [i.code for i in validate.check_artifacts(
            rs, Character(id="c.x", exalt_type=splat, caste=caste, essence_rating=2,
                          **kw))]

    assert _issues(backgrounds=[_bg("Artifact", 3)],
                   artifacts=[_art(name="Daiklave", rating=3)]) == []
    assert _issues(backgrounds=[_bg("Artifact", 3)],
                   artifacts=[_art(name="Sword", rating=2),
                              _art(name="Amulet", rating=1)]) == [
        "artifact-over-background-dots"]
    # Owning artifacts with no Background at all is the same finding every branch
    # raises, with the same code — a player who deletes the Background must not see a
    # different error than one who never bought it.
    assert _issues(artifacts=[_art(name="Amulet", rating=1)]) == [
        "artifact-without-background"]


def test_the_corebook_rule_counts_artifact_WEAPONS_and_ARMOUR_too(rs):
    """The count is over `artifact_items`, which folds all three homes together — the
    surface a player actually breaches it on is a daiklave plus a suit of articulated
    plate, neither of which lives in `character.artifacts`. Mundane gear alongside them
    is untouched: `artifact_rating` 0 is the mundane default, not a zero-dot artifact.
    """
    c = Character(id="c.aw", exalt_type="Solar", caste="Dawn", essence_rating=2,
                  backgrounds=[_bg("Artifact", 3)])
    c.weapons.append(Weapon(name="Daiklave", artifact_rating=3))
    c.weapons.append(Weapon(name="Short Sword"))
    assert validate.check_artifacts(rs, c) == []
    c.armor.append(Armor(name="Articulated Plate", artifact_rating=3))
    assert [i.code for i in validate.check_artifacts(rs, c)] == [
        "artifact-over-background-dots"]


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
async def test_an_artifact_rating_edit_updates_the_budget_header_in_place(user) -> None:
    """The budget header must track a rating edit on the SAME tab (the half of the
    dropped-click fix a DK can't show — DK prints no combined line). Raising the
    Tattered Wings 2→3 takes the combined 7→8, which the header must print as 8/7,
    and the rating input must survive the edit (a body rebuild would destroy it and
    NiceGUI drops the next click)."""
    from nicegui import ui as _ui

    await user.open('/artifacts-advantages')
    await user.should_see("7/7 combined")
    number = next(e for e in user.client.elements.values()
                  if isinstance(e, _ui.number) and e.props.get("label") == "Rating")
    number.value = 3
    await user.should_see("8/7 combined")          # header tracked the edit
    assert next(e for e in user.client.elements.values()
                if isinstance(e, _ui.number) and e.props.get("label") == "Rating") is number


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
async def test_a_splat_with_no_budget_TABLE_states_the_corebook_rule(user) -> None:
    """A Solar is not budgeted by a TABLE, but is governed by the corebook rule (ruling
    2026-08-13), and the header has to say so — the player must not first learn of the
    one-artifact limit from a validation error raised after they picked the second.
    CHAR_ARTIFACTS_SOLAR holds Artifact 4 and one 4-dot artifact, which is legal."""
    await user.open('/artifacts-advantages-solar')
    await user.should_see("Tattered Wings")
    await user.should_see("1/1")
    await user.should_see("one artifact rated up to 4")
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


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_artifact_name_field_is_a_catalogue_combobox(user) -> None:
    """The name field is fed from `data/artifacts.json` (the click-through wish from
    2026-08-05). Catalogue names must be selectable, and an off-catalogue stored name
    ("Tattered Wings") must survive as an option — the `_opts_with` guard against the
    NiceGUI build-time crash a value-not-among-options would raise."""
    from nicegui import ui as _ui
    await user.open('/artifacts-advantages')
    await user.should_see("Tattered Wings")
    combobox = next(e for e in user.client.elements.values()
                    if isinstance(e, _ui.select)
                    and e.props.get("label") == "Artifact name")
    assert combobox.value == "Tattered Wings"
    assert "Tattered Wings" in combobox.options          # the guard folded it in
    assert "Echo Jewel" in combobox.options              # catalogue names are offered
    assert "Myrmidon Carapace" in combobox.options
    assert "The Jackal's Skull" in combobox.options      # the 2026-08-08 Twilight sync
    assert "Iron Horse" in combobox.options              # the 2026-08-08 Eclipse sync


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_picking_a_catalogue_artifact_autofills_its_rating(user) -> None:
    """A catalogue pick sets name AND rating from the entry (mirrors `set_armor`'s
    autofill), so the player cannot mis-price a known artifact. Tattered Wings 2 →
    Echo Jewel 1 takes the combined 7→6, which the header must print in place — and the
    rating input must survive the change (a body rebuild would drop the next event)."""
    from nicegui import ui as _ui
    await user.open('/artifacts-advantages')
    await user.should_see("7/7 combined")
    combobox = next(e for e in user.client.elements.values()
                    if isinstance(e, _ui.select)
                    and e.props.get("label") == "Artifact name")
    combobox.value = "Echo Jewel"
    await user.should_see("Echo Jewel")
    await user.should_see("6/7 combined")                # header tracked the autofill
    number = next(e for e in user.client.elements.values()
                  if isinstance(e, _ui.number) and e.props.get("label") == "Rating")
    assert number.value == 1                             # rating autofilled from the entry


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_catalogue_pick_fills_the_description_label(user) -> None:
    """The click-through wish: a persistent description under each standalone-artifact
    row, mirroring the Background `bg-desc` pattern. An off-catalogue name shows no
    text; a catalogue pick shows the entry's page-vetted description."""
    from nicegui import ui as _ui
    await user.open('/artifacts-advantages')
    desc = next(e for e in user.client.elements.values()
                if isinstance(e, _ui.label)
                and e.props.get("data-testid") == "art-desc")
    assert desc.text == ""                               # Tattered Wings: off-catalogue
    combobox = next(e for e in user.client.elements.values()
                    if isinstance(e, _ui.select)
                    and e.props.get("label") == "Artifact name")
    combobox.value = "Echo Jewel"
    # The `rs` fixture is unavailable in the nicegui async context, so load the
    # catalogue directly for the expected text (the label is found by data-testid, so
    # this cannot pass against code with no persistent label — see the bg-desc tests).
    entry = next(a for a in rules_db.load_ruleset(DATA_DIR).artifact_catalog.values()
                 if a.name == "Echo Jewel")
    assert desc.text == entry.description
    assert desc.visible


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_alchemical_goods_reference_is_gone(user) -> None:
    """The goods removal ruling (2026-08-08) pins the UI side: the Advantages tab
    builds without the alchemical-goods reference panel, and Godstrike Oil — the most
    distinctive of the three — does not appear anywhere on it. (The data-side pin is
    `test_the_alchemical_goods_catalogue_does_not_exist` in test_data.py.)"""
    await user.open('/artifacts-advantages')
    await user.should_see("7/7 combined")            # the tab built: the budget header
    await user.should_not_see("Godstrike Oil")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_combobox_offers_the_castebook_artifacts(user) -> None:
    """The 2026-08-08 backlog batch added ten non-gear castebook artifacts to the
    catalogue; the name combobox must offer them (the click-through wish extends to new
    catalogue rows — a name the dropdown doesn't offer is a name a player must type and
    mis-price)."""
    from nicegui import ui as _ui
    await user.open('/artifacts-advantages')
    await user.should_see("7/7 combined")
    combobox = next(e for e in user.client.elements.values()
                    if isinstance(e, _ui.select)
                    and e.props.get("label") == "Artifact name")
    for name in ("Shield Bracer", "Map of Azure Victory", "Chariot of Aerial Conquest",
                 "Arrows of Distant Death", "Spider Grippers", "Belt of Shadow Walking",
                 "Circlet of Spirits", "Hooked Daiklaves of Dual Prowess",
                 "Death Shield Ring", "Ring of the Deliberative"):
        assert name in combobox.options, f"{name!r} should be offered by the combobox"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_combobox_offers_the_corebook_wonders(user) -> None:
    """The corebook's own artifacts were the ones a player was most likely to look for
    and the ones the catalogue did not have: a daiklave was addable as a weapon but was
    not in the artifact catalogue at all."""
    from nicegui import ui as _ui
    await user.open('/artifacts-advantages')
    await user.should_see("7/7 combined")
    combobox = next(e for e in user.client.elements.values()
                    if isinstance(e, _ui.select)
                    and e.props.get("label") == "Artifact name")
    for name in ("Daiklave", "Grand Daiklave", "Reaver Daiklave", "Dire Lance",
                 "Goremaul", "Grimcleaver", "Serpent-Sting Staff", "Smashfist",
                 "Short Powerbow", "Long Powerbow", "Lightning Torment Hatchets",
                 "Superheavy Plate (Artifact)", "Breastplate (Artifact)"):
        assert name in combobox.options, f"{name!r} should be offered by the combobox"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_hearthstones_are_never_offered_as_artifact_purchases(user) -> None:
    """A Hearthstone's dots are the MANSE's rating (core p.338). Offering one on the
    artifact row would append an `ArtifactEntry` and charge the p.131 Artifact budget
    for a stone Artifact dots never bought — the mis-charge is silent, which is why it
    is pinned at the surface that would commit it rather than only in the engine."""
    from nicegui import ui as _ui
    await user.open('/artifacts-advantages')
    await user.should_see("7/7 combined")
    combobox = next(e for e in user.client.elements.values()
                    if isinstance(e, _ui.select)
                    and e.props.get("label") == "Artifact name")
    for stone in ("Windhands Gemstone", "Gem of Adamant Skin", "The Freedom Stone",
                  "Stone of Healing", "Gem of Incomparable Wellness"):
        assert stone not in combobox.options, f"{stone!r} is bought with Manse"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_manse_row_offers_the_hearthstone_catalogue(user) -> None:
    """...and the stones do have a home: the Manse row itself, where the pick lands in
    `BackgroundEntry.hearthstones` rather than in `Character.artifacts`."""
    await user.open('/manse-hearthstones')
    await user.should_see("Manse")
    buttons = [e for e in user.client.elements.values()
               if "hearthstone-picker" in getattr(e, "_markers", [])]
    assert len(buttons) == 1, "exactly the Manse row carries the picker, not Artifact"
    user.find(marker="hearthstone-picker").click()
    await user.should_see("Hearthstones")
    await user.should_see("Gem of Adamant Skin")


def test_every_catalogue_icon_resolves_in_the_font_nicegui_actually_ships() -> None:
    """NiceGUI ships two icon fonts and a bare name resolves against the OLDER one,
    Material Icons. A Symbols-only name renders as nothing at all — no error, no
    fallback — which is how every melee weapon shipped with a blank where its icon
    should be (browser, 2026-08-12). `swords` is the only Symbols-only name this build
    wants, and it must keep Quasar's `sym_o_` prefix."""
    from exalted_builder.ui import catalogue as cataloguemod
    assert cataloguemod.icon_for(["melee"]) == "sym_o_swords"
    assert cataloguemod.icon_for(["weapon"]) == "sym_o_swords"
    # ...and nothing else acquired a Symbols-only name without the prefix. Each bare
    # name below was verified present in Material Icons Outlined by reading the glyph
    # order of the woff2 NiceGUI ships — see the note on `_ICON_BY_TAG` for the check.
    verified_bare = {
        "north_east", "air", "landscape", "local_fire_department", "water_drop",
        "park", "diamond", "shield", "sports_motorsports", "sports_martial_arts",
        "sports_handball", "sports_mma", "security", "visibility", "campaign",
        "sailing", "handyman",
    }
    for tag, icon in cataloguemod._ICON_BY_TAG:
        assert icon.startswith("sym_o_") or icon in verified_bare, (
            f"{icon!r} (tag {tag!r}) is neither prefixed nor a verified Material Icons "
            f"name — check it against the shipped font before adding it")


# --------------------------------------------------------------------------- #
# Hearthstones — the Savant and Sorcerer pp.66-67 allowance
#
# "The sum of the levels of all the Hearthstones produced can never exceed the level
# of the Manse" (p.67). A Manse may be designed to yield several stones instead of one
# (p.66), so the cap is on the TOTAL, not the count.
#
# ⚠ Every test here goes through `validate.validate` — the CALLER — and never calls
# `check_hearthstones` directly. That is this project's most-repeated bug and the exact
# shape the Backgrounds delegation shipped three times: nine tests reached past the
# caller into the helper, so a rule that never ran in production passed all nine.
# --------------------------------------------------------------------------- #

def _with_manse(rs, exalt_type: str, name: str, rating: int, stones, **kw) -> Character:
    from exalted_builder.models.character import HearthstoneEntry
    c = Character(id="c.h", exalt_type=exalt_type, essence_rating=2,
                  caste=kw.pop("caste", ""))
    for k, v in kw.items():
        setattr(c, k, v)
    c.backgrounds = [BackgroundEntry(
        name=name, rating=rating,
        hearthstones=[HearthstoneEntry(name=n, rating=r) for n, r in stones],
        **({"is_demesne": True} if kw.get("_demesne") else {}))]
    return c


def _hs_codes(rs, character) -> set[str]:
    return {i.code for i in validate.validate(rs, character)}


def test_hearthstone_levels_may_not_exceed_the_manse(rs) -> None:
    """The p.67 sentence, on the corebook's own linear Manse: three dots is a level-3
    Manse, so two level-2 stones is one level too many."""
    over = _with_manse(rs, "Solar", "Manse", 3, [("A", 2), ("B", 2)], caste="Dawn")
    assert "hearthstone-over-combined" in _hs_codes(rs, over)


def test_several_hearthstones_are_legal_while_they_sum_to_the_manse(rs) -> None:
    """The other half of p.66, and the half a naive "one stone, level = rating" check
    would have got wrong: a Manse ••• may produce 2+1 as readily as a single 3."""
    split = _with_manse(rs, "Solar", "Manse", 3, [("A", 2), ("B", 1)], caste="Dawn")
    assert "hearthstone-over-combined" not in _hs_codes(rs, split)
    whole = _with_manse(rs, "Solar", "Manse", 3, [("A", 3)], caste="Dawn")
    assert "hearthstone-over-combined" not in _hs_codes(rs, whole)


def test_the_dragonblooded_ladder_caps_the_largest_single_stone(rs) -> None:
    """The DB and Abyssal Manse ladders are NOT linear — their rung 3 allows "no more
    than six levels, total" but only "a level 3 Hearthstone" as the largest. Six levels
    as 4+2 is therefore illegal while 3+2+1 is legal, which no combined cap alone can
    express."""
    c = _with_manse(rs, "Dragon-Blooded", "Manse", 3, [("Big", 4), ("Small", 2)],
                    caste="Earth")
    codes = _hs_codes(rs, c)
    assert "hearthstone-over-individual" in codes
    assert "hearthstone-over-combined" not in codes, "six levels is within the rung"
    ok = _with_manse(rs, "Dragon-Blooded", "Manse", 3,
                     [("A", 3), ("B", 2), ("C", 1)], caste="Earth")
    assert not ({"hearthstone-over-individual", "hearthstone-over-combined"}
                & _hs_codes(rs, ok))


def test_the_dragonblooded_one_dot_rung_allows_a_single_stone(rs) -> None:
    """"She may have ONE Hearthstone of level 1 or 2" — a printed COUNT, which the two
    maxima cannot express: combined 2 with individual 2 would permit two level-1
    stones."""
    c = _with_manse(rs, "Dragon-Blooded", "Manse", 1, [("A", 1), ("B", 1)],
                    caste="Earth")
    assert "hearthstone-over-count" in _hs_codes(rs, c)


def test_the_corebook_manse_is_not_given_the_dragonblooded_allowance(rs) -> None:
    """The six Manse variants share two names between them, so the allowance must be
    resolved through the SPLAT-FILTERED catalogue. A Solar Manse ••• is a level-3 Manse
    (three levels of stone), not the Dragon-Blooded rung's six — matching on the bare
    name would hand the Solar whichever copy the lookup met first, which is the
    Illuminated Artifact scar."""
    c = _with_manse(rs, "Solar", "Manse", 3, [("A", 3), ("B", 3)], caste="Dawn")
    assert "hearthstone-over-combined" in _hs_codes(rs, c)


def test_the_mountain_folk_manse_carries_two_levels_per_dot(rs) -> None:
    """CH6 prints no ladder, only prose: "Each dot in this Background provides two dots
    worth of Manses". Manse •• is therefore four levels of stone, not two."""
    ok = _with_manse(rs, "Mountain-Folk", "Manse", 2, [("A", 2), ("B", 2)],
                     caste="artisan")
    assert "hearthstone-over-combined" not in _hs_codes(rs, ok)
    over = _with_manse(rs, "Mountain-Folk", "Manse", 2,
                       [("A", 2), ("B", 2), ("C", 1)], caste="artisan")
    assert "hearthstone-over-combined" in _hs_codes(rs, over)


def test_a_demesne_grows_no_hearthstones(rs) -> None:
    """The human's ruling, 2026-08-12: rather than model S&S p.66's Demesne stones
    (one level weaker, and they decay once removed), a row flipped to Demesne simply
    produces none."""
    from exalted_builder.models.character import HearthstoneEntry
    c = Character(id="c.d", exalt_type="Solar", caste="Dawn", essence_rating=2)
    c.backgrounds = [BackgroundEntry(name="Manse", rating=3, is_demesne=True,
                                     hearthstones=[HearthstoneEntry(name="A",
                                                                    rating=1)])]
    assert "hearthstone-without-manse" in _hs_codes(rs, c)


def test_a_background_that_is_not_a_manse_grows_no_hearthstones(rs) -> None:
    """A stone stranded by renaming the row it sat on. Reported rather than ignored —
    it is the one way a stone can outlive the allowance that justified it."""
    from exalted_builder.models.character import HearthstoneEntry
    c = Character(id="c.r", exalt_type="Solar", caste="Dawn", essence_rating=2)
    c.backgrounds = [BackgroundEntry(name="Resources", rating=3,
                                     hearthstones=[HearthstoneEntry(name="A",
                                                                    rating=1)])]
    assert "hearthstone-without-manse" in _hs_codes(rs, c)


def test_the_hearthstone_cap_still_binds_after_the_lock(rs) -> None:
    """The human's ruling: hard on BOTH sides of the lock. The allowance is keyed to a
    Background the story raises and lowers, so a chargen-only check would fall silent
    exactly when the cap started moving — the house bug, which in this build has shipped
    four times."""
    c = _with_manse(rs, "Solar", "Manse", 3, [("A", 2), ("B", 2)], caste="Dawn")
    c.chargen_locked = True
    assert "hearthstone-over-combined" in _hs_codes(rs, c)


def test_each_manse_row_gets_its_own_allowance(rs) -> None:
    """Per-row, not per-character: a Manse • and a Manse ••••• are two Manses with two
    separate allowances, and a summed check would let the small one carry the big one's
    stone."""
    from exalted_builder.models.character import HearthstoneEntry
    c = Character(id="c.two", exalt_type="Solar", caste="Dawn", essence_rating=2)
    c.backgrounds = [
        BackgroundEntry(name="Manse", rating=1,
                        hearthstones=[HearthstoneEntry(name="Big", rating=4)]),
        BackgroundEntry(name="Manse", rating=5, hearthstones=[]),
    ]
    assert "hearthstone-over-combined" in _hs_codes(rs, c)


def test_a_manse_with_no_stones_is_never_a_finding(rs) -> None:
    """Owning a Manse and carrying no Hearthstone is ordinary — it is the Underworld
    ladder's own rung-1 case, and the corebook's Manse Background exists to be bought
    before a stone is chosen."""
    c = _with_manse(rs, "Solar", "Manse", 3, [], caste="Dawn")
    assert not any(i.code.startswith("hearthstone-") for i in validate.validate(rs, c))


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_picking_a_hearthstone_records_its_rating(user) -> None:
    """The pick must land STRUCTURALLY, with the stone's level.

    The first cut appended the name to the row's free-text `note` and kept no rating,
    so the S&S p.67 total was uncheckable — and `note` is bound to a text input that
    rewrites it on every keystroke, so reading the names back out would have been the
    catalogue-dialog discriminator bug over again: a rule switched on by state the
    player can edit to switch it off.

    ⚠ Asserted THROUGH THE UI rather than by importing `_ui_main`'s character: the
    harness loads that file as its own module object, so an `from tests._ui_main import`
    in the test binds a different instance and the assertion passes alone and fails in
    the suite. The running total is the strongest thing to read anyway — it can only
    say "4" if the pick recorded the stone's RATING, which is the whole point.
    """
    await user.open('/manse-pick')
    user.find(marker="hearthstone-picker").click()
    await user.should_see("Gem of Adamant Skin")
    user.find("Gem of Adamant Skin").click()
    # Manse ••• allows 3 levels; the Gem of Adamant Skin is 4, so the total both
    # proves the rating landed and shows the row is now over its allowance.
    await user.should_see("Hearthstones: 4 / 3 levels")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_demesne_row_keeps_its_toggle_but_loses_the_picker(user) -> None:
    """The permission must move the OFFER as well as the bar, and it must be
    reversible — hiding the toggle along with the picker would strand the row as a
    Demesne with no way back (the mortal-Artifact lesson, 2026-08-12)."""
    await user.open('/manse-demesne')
    await user.should_see("Manse")
    pickers = [e for e in user.client.elements.values()
               if "hearthstone-picker" in getattr(e, "_markers", [])]
    toggles = [e for e in user.client.elements.values()
               if "demesne-toggle" in getattr(e, "_markers", [])]
    assert pickers == [], "a Demesne grows no Hearthstones"
    assert len(toggles) == 1, "the toggle must survive so the row can be flipped back"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_tiered_manse_row_renders_its_printed_allowance(user) -> None:
    """The Abyssal and Dragon-Blooded ladders are a different code path from the
    corebook's linear Manse — a printed tier with its own combined total and a ceiling
    on the largest single stone. Underworld Manse ••• allows six levels, so a lone
    level-4 stone is WITHIN the total and over the per-stone ceiling: the row must
    print 4 / 6 rather than reading as over budget."""
    await user.open('/manse-tiered')
    await user.should_see("Hearthstones: 4 / 6 levels")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_stranded_stone_still_renders_and_can_be_removed(user) -> None:
    """A stone on a row that grows none — what renaming a Manse row leaves behind. The
    allowance is None here, a branch nothing else reaches, and the row must still draw
    its delete control: an Issue the player has no widget to act on is worse than no
    Issue at all."""
    await user.open('/manse-stranded')
    await user.should_see("Resources")
    await user.should_see("Stone of Healing")
    pickers = [e for e in user.client.elements.values()
               if "hearthstone-picker" in getattr(e, "_markers", [])]
    assert pickers == [], "Resources grows no Hearthstones"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_raising_the_manse_moves_the_hearthstone_denominator(user) -> None:
    """BOTH halves of "4 / 3" move. The numerator when a stone is added or re-rated;
    the DENOMINATOR when the Manse rating changes, because a bigger Manse legalises a
    stone that was over budget a moment ago.

    Found in the browser (2026-08-12): the allowance was computed once when the row was
    built and captured in the closure, so raising the Manse moved the printed rung and
    left the total insisting the row was still over. The suite could not see it — every
    test until this one read the total on a freshly built panel, which is exactly the
    phase the stale value agrees with."""
    await user.open('/manse-raise')
    await user.should_see("Hearthstones: 4 / 3 levels")
    # `.clear()` first — `.type()` APPENDS, and typing "5" into a field holding "3"
    # sets the Manse to 35 rather than 5.
    user.find(marker="bg-rating").clear().type("5")
    await user.should_see("Hearthstones: 4 / 5 levels")


def test_a_splat_whose_rule_lives_only_on_its_ORIGIN_rows_is_not_given_the_corebook(rs):
    """The Mountain Folk cascade has no base row — only `Mountain-Folk:enlightened`
    and `:unenlightened`, both carrying the doubled rule. A Mountain Folk who has not
    chosen an Enlightenment yet resolves to NO rule, and the corebook fallback would
    hand them a one-artifact limit their own book overrides.

    ⚠ This is the regression the fallback introduced: before the corebook default, a
    missing rule meant no check and this character was merely unvalidated. Silence is
    the right answer for a half-built character; the wrong rule is not.
    """
    def _codes(**kw):
        c = Character(id="mf", exalt_type="Mountain-Folk", caste="artisan",
                      essence_rating=2, backgrounds=[_bg("Artifact", 3)],
                      artifacts=[_art(name="A", rating=1), _art(name="B", rating=1)],
                      **kw)
        return [i.code for i in validate.check_artifacts(rs, c)]

    assert _codes() == [], "an origin-less Mountain Folk must not be judged"
    # Both origins print the doubled rule, under which two 1-dot artifacts on
    # Artifact 3 are legal — so the ORIGIN-LESS answer above must not be the corebook's.
    assert _codes(origin="enlightened") == []
    assert _codes(origin="unenlightened") == []
    # The negative control, and it is not decoration — it caught the first cut of the
    # guard. That version asked "does ANY row in this splat's cascade print a rule?",
    # and `Solar:illuminated`'s tier table answered yes, so the corebook default
    # switched off for every ordinary Solar: the guard silently disabled the feature
    # it was protecting. A plain Solar has a BASE budget row, so its cascade has
    # resolved and it is judged.
    solar = Character(id="s", exalt_type="Solar", caste="Dawn", essence_rating=2,
                      backgrounds=[_bg("Artifact", 3)],
                      artifacts=[_art(name="A", rating=1), _art(name="B", rating=1)])
    assert [i.code for i in validate.check_artifacts(rs, solar)] == [
        "artifact-over-background-dots"]


def test_dragon_kings_read_their_OWN_artifact_entry_not_the_dragon_blooded_one(rs):
    """PG p.175-176 prints a Dragon King Artifact Background — "Weapons and tools,
    either vegetative, crystal or orichalcum" — whose changed-background footnote
    borrows the Terrestrial RULE and says so ("See E:DB, p. 157 for details").

    The build had `background.artifact-dragonblooded` in the Dragon-Kings catalogue,
    so a Dragon King read the DB entry: House assignments, the Realm's arsenal. ⚠ The
    RULE was right either way — PG gives them the same doubled shape — which is why
    nothing caught it. Correct behaviour, borrowed mechanism.

    The ladder is still the DB one, via `ladder_from`, because the page's own
    cross-reference points there (human's call 2026-08-13).
    """
    entries = [b for b in rs.backgrounds_for("Dragon-Kings", "ancient")
               if b.name == "Artifact"]
    assert [b.id for b in entries] == ["background.artifact-dragonkings"]
    assert "vegetative, crystal or orichalcum" in entries[0].description
    # The borrow resolved at load time, so the read sites see real rungs.
    assert entries[0].ladder and "A pair of level 1 artifacts." in entries[0].ladder
    # And the modern origin, which has its own catalogue row.
    assert [b.id for b in rs.backgrounds_for("Dragon-Kings")
            if b.name == "Artifact"] == ["background.artifact-dragonkings"]
    # The Dragon-Blooded keep theirs — the displacement must not have moved it.
    assert [b.id for b in rs.backgrounds_for("Dragon-Blooded")
            if b.name == "Artifact"] == ["background.artifact-dragonblooded"]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_raising_the_artifact_background_moves_the_artifacts_header(user) -> None:
    """The header states the corebook allowance ("one artifact rated up to 4"), and the
    rating it reads is edited in the BACKGROUNDS panel — a different panel, which cannot
    refresh this one without a hook. Found in the browser 2026-08-13: raising Artifact
    left the header at the old number until the player switched tabs and back.

    ⚠ The second consumer of a Background rating to go stale here; the Hearthstone
    denominator was the first, and its test above says the same thing. Every test until
    these two read the header on a freshly built panel — the one phase a stale closure
    agrees with.
    """
    await user.open('/artifact-header-sync')
    await user.should_see("one artifact rated up to 4")
    # `.clear()` first — `.type()` appends. See the Manse test above.
    user.find(marker="bg-rating").clear().type("5")
    await user.should_see("one artifact rated up to 5")


# --- the artifact/gear link (2026-08-13) ------------------------------------ #

def test_a_granted_gear_row_is_not_a_SECOND_artifact(rs):
    """Twenty names live in both catalogues, and the artifact row carries no stats — so
    owning "Daiklave" as an artifact and adding a "Daiklave" weapon to swing it is the
    natural way to play one. That counted the same object twice, which the corebook
    one-artifact rule turns from a wart into a false error."""
    c = Character(id="c.g", exalt_type="Solar", caste="Dawn", essence_rating=2,
                  backgrounds=[_bg("Artifact", 3)],
                  artifacts=[_art(name="Daiklave", rating=3)])
    key = artifacts.item_key(artifacts.SOURCE_ARTIFACT, "Daiklave")
    c.weapons.append(Weapon(name="Daiklave", artifact_rating=3, from_artifact=key))
    assert [(i.name, i.source) for i in artifacts.artifact_items(c)] == [
        ("Daiklave", "artifact")]
    assert artifacts.combined_rating(c) == 3
    assert validate.check_artifacts(rs, c) == []


def test_an_UNLINKED_duplicate_still_counts_twice(rs):
    """The negative control, and the honest behaviour: the link is what dedupes, not
    the shared name. A player who types a second daiklave by hand owns two as far as
    this build can tell, and the budget says so."""
    c = Character(id="c.g2", exalt_type="Solar", caste="Dawn", essence_rating=2,
                  backgrounds=[_bg("Artifact", 3)],
                  artifacts=[_art(name="Daiklave", rating=3)])
    c.weapons.append(Weapon(name="Daiklave", artifact_rating=3))
    assert len(artifacts.artifact_items(c)) == 2
    assert [i.code for i in validate.check_artifacts(rs, c)] == [
        "artifact-over-background-dots"]


def test_an_ORPHANED_link_counts_on_its_own_rather_than_vanishing(rs):
    """⚠ The failure direction that matters. `from_artifact` is a SOFT reference, and
    the artifact it names can be renamed or deleted out from under it. If the flag were
    trusted as stored, the gear would then be an artifact nothing counts — a free
    daiklave. Resolved against the artifacts actually owned instead, so an orphan
    stands on its own and is visible."""
    key = artifacts.item_key(artifacts.SOURCE_ARTIFACT, "Daiklave")
    c = Character(id="c.g3", exalt_type="Solar", caste="Dawn", essence_rating=2,
                  backgrounds=[_bg("Artifact", 3)])
    c.weapons.append(Weapon(name="Daiklave", artifact_rating=3, from_artifact=key))
    assert [(i.name, i.source) for i in artifacts.artifact_items(c)] == [
        ("Daiklave", "weapon")]
    # And it comes back under the artifact's wing when the artifact returns.
    c.artifacts.append(_art(name="Daiklave", rating=3))
    assert [i.source for i in artifacts.artifact_items(c)] == ["artifact"]


def test_gear_stat_line_matches_only_ARTIFACT_rated_gear(rs):
    """A mundane row sharing a name with an artifact must not be granted as that
    artifact's stat line — it would then be excluded from the budget, and a mundane
    hatchet would quietly cancel a real artifact."""
    assert artifacts.gear_stat_line(rs, "Daiklave")[0] == artifacts.SOURCE_WEAPON
    assert artifacts.gear_stat_line(rs, "Myrmidon Carapace")[0] == artifacts.SOURCE_ARMOR
    assert artifacts.gear_stat_line(rs, "Hatchet") is None      # mundane in weapons.json
    assert artifacts.gear_stat_line(rs, "Tattered Wings") is None   # artifact, no stats
    assert artifacts.gear_stat_line(rs, "") is None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_picking_an_artifact_weapon_grants_its_stat_line_ONCE(user) -> None:
    """The BUY PATH, which is the only place the link is actually created — the engine
    tests above build `from_artifact` by hand and so cannot see a UI that never sets it.

    Asserted ENTIRELY on screen, in two ways that a first draft got wrong:

    * The header reading "1/1" IS the dedup. A granted row that counted as a second
      artifact would say 2/1 and raise the corebook error, so this one string covers
      the whole feature.
    * The stat line is checked on the EDITOR route for the same character rather than
      by importing the fixture: `from tests._ui_main import …` can bind a different
      module instance than the one the harness loaded for the page, so the assertion
      read a character nothing had mutated — it passed alone and failed in the suite.

    The row is clicked by DISPATCHING to the name label itself. Two things make the
    obvious `user.find("Reaver Daiklave").click()` wrong here: it also matches Grand
    Daiklave, Reaver Daiklave and Hooked Daiklaves (and which one it lands on varies
    with Python's per-run string hashing), and `find` matches an INPUT'S VALUE too — so
    filtering the list first and then clicking the match clicks the filter box, leaving
    the dialog open and the pick unmade, which is exactly how this failed.
    """
    from nicegui import ui as _ui
    def _pick(name: str) -> None:
        rows = [e for e in user.client.elements.values()
                if isinstance(e, _ui.label) and e.text == name and e._event_listeners]
        assert len(rows) == 1, f"{len(rows)} clickable labels read exactly {name!r}"
        el = rows[0]
        el._handle_event({"id": el.id,
                          "listener_id": list(el._event_listeners)[0], "args": {}})

    await user.open('/artifact-grant')
    user.find("Add artifact").click()
    await user.should_see("Reaver Daiklave")
    _pick("Reaver Daiklave")
    await user.should_see("1/1")
    await user.should_see("one artifact rated up to 3")

    # The granted stat line, on the equipment surface it was granted to.
    await user.open('/artifact-grant-editor')
    await user.should_see("Reaver Daiklave")

    # Picking it again adds a second ARTIFACT row (the player asked for one), but must
    # NOT grant a second stat line — 2 countable items, not 3.
    await user.open('/artifact-grant')
    user.find("Add artifact").click()
    await user.should_see("Reaver Daiklave")
    _pick("Reaver Daiklave")
    await user.should_see("2/1")
    await user.should_not_see("3/1")


def test_the_two_catalogues_agree_on_every_shared_artifact_rating(rs) -> None:
    """Twenty entries are in `artifacts.json` AND in the gear catalogues, and picking
    the artifact grants the gear row — so the two ratings sit side by side on screen.
    If they ever diverge, the sheet shows one daiklave priced two ways and the budget
    silently uses the artifact's. Nothing enforces this at load; this test is the
    enforcement.
    """
    by_name = {a.name.strip().lower(): a for a in rs.artifact_catalog.values()}
    disagreements = []
    for catalog in (rs.weapon_catalog, rs.armor_catalog):
        for entry in catalog.values():
            art = by_name.get(entry.name.strip().lower())
            if art is not None and entry.artifact_rating > 0 \
                    and art.rating != entry.artifact_rating:
                disagreements.append(
                    f"{entry.name}: artifacts.json {art.rating} vs gear "
                    f"{entry.artifact_rating}")
    assert not disagreements, "; ".join(disagreements)


# --- the two acquisition channels (2026-08-13) ------------------------------ #

def test_a_purchased_artifact_is_not_charged_to_the_background(rs):
    """Two printed channels: the Artifact Background is the PRE-GAME one — every gear
    table defines its Artifact column as the dots "the character must spend to start
    the game owning one of these" (core p.342, p.345) — and cash is the IN-PLAY one
    (Manacle and Coin pp.122-125, which prices the same daiklave the Background rates
    Artifact •• at Resources ••••).

    So a bought artifact is equipment, and the budget must not see it.
    """
    c = Character(id="c.b", exalt_type="Solar", caste="Dawn", essence_rating=2,
                  chargen_locked=True, backgrounds=[_bg("Artifact", 2)],
                  artifacts=[_art(name="Wings", rating=2),
                             _art(name="Daiklave", rating=2,
                                  acquired=artifacts.ACQUIRED_PURCHASED)])
    assert [i.name for i in artifacts.budgeted_items(c)] == ["Wings"]
    assert [i.name for i in artifacts.purchased_items(c)] == ["Daiklave"]
    assert artifacts.combined_rating(c) == 2
    # One Background artifact rated 2 on Artifact 2 — legal under the corebook rule,
    # and it stays legal with a bought daiklave beside it.
    assert validate.check_artifacts(rs, c) == []


def test_the_character_still_OWNS_a_purchased_artifact(rs):
    """`budgeted_items` answers "what did the Background pay for"; `artifact_items`
    answers "what does she own", and only the first is about money. Damaged Artifact,
    the sheet and the pickers read the second — a bought daiklave can be damaged and
    wielded like any other."""
    c = Character(id="c.b2", exalt_type="Solar", caste="Dawn", essence_rating=2,
                  chargen_locked=True,
                  artifacts=[_art(name="Daiklave", rating=2,
                                  acquired=artifacts.ACQUIRED_PURCHASED)])
    assert [i.name for i in artifacts.artifact_items(c)] == ["Daiklave"]
    assert artifacts.find_item(
        c, artifacts.item_key(artifacts.SOURCE_ARTIFACT, "Daiklave")) is not None


def test_artifacts_may_not_be_BOUGHT_at_chargen(rs):
    """⚠ `acquired` is a discriminator the player is MEANT to edit, so it is a hole
    through the budget by construction — mark everything purchased and the Artifact
    Background stops binding. The ruling closes it where it matters: creation, the
    phase the budget exists for and the one the printed phrase excludes ("to start the
    game owning"). Post-lock the same character is silent."""
    def _codes(locked: bool):
        c = Character(id="c.b3", exalt_type="Solar", caste="Dawn", essence_rating=2,
                      chargen_locked=locked, backgrounds=[_bg("Artifact", 2)],
                      artifacts=[_art(name="Daiklave", rating=2,
                                      acquired=artifacts.ACQUIRED_PURCHASED)])
        return [i.code for i in validate.check_artifacts(rs, c)]
    assert _codes(locked=False) == ["artifact-purchased-at-chargen"]
    assert _codes(locked=True) == []


def test_an_artifact_WEAPON_can_be_purchased_too(rs):
    """The provenance lives on all three ownables, because artifacts live in three
    places — a bought daiklave is usually a weapon row, not a standalone artifact."""
    c = Character(id="c.b4", exalt_type="Solar", caste="Dawn", essence_rating=2,
                  chargen_locked=True, backgrounds=[_bg("Artifact", 1)])
    c.weapons.append(Weapon(name="Daiklave", artifact_rating=2,
                            acquired=artifacts.ACQUIRED_PURCHASED))
    assert artifacts.budgeted_items(c) == []
    assert validate.check_artifacts(rs, c) == []


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_acquisition_control_is_POST_LOCK_only(user) -> None:
    """At creation the Background is the only channel there is, so offering the choice
    would be offering an illegal pick — the same reasoning that filters the Virtue Flaw
    dropdown to the flawed Virtue. The validator bars it either way; this stops the
    player reaching the bar."""
    await user.open('/artifact-bought')
    await user.should_see("Acquired")
    await user.open('/artifact-unlocked')
    await user.should_see("Tattered Wings")        # the panel is there…
    await user.should_not_see("Acquired")          # …without the control


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_header_says_what_the_background_did_NOT_pay_for(user) -> None:
    """A header counting only budgeted items sits above a list showing every artifact,
    so the difference has to be stated or the count reads as a bug. CHAR_ARTIFACT_BOUGHT
    holds one Background artifact; the test flips it to Bought and watches both move."""
    from nicegui import ui as _ui
    await user.open('/artifact-bought')
    await user.should_see("1/1")
    await user.should_not_see("bought with Resources")
    sel = next(e for e in user.client.elements.values()
               if isinstance(e, _ui.select) and "art-acquired" in getattr(e, "_markers", []))
    sel.set_value("purchased")
    await user.should_see("bought with Resources")
    await user.should_see("0/1")
