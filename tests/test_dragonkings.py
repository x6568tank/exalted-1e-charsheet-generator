"""Tests for the Dragon-Kings splat — Player's Guide CH4, pp.154-195.

The ninth splat, the fourth non-Exalt, and the first with a RATED subsystem (the ten
Paths of Prehuman Mastery) that is not Charms: a first-class rating 1-6 per Path with
its own chargen pool, BP/XP tables and an Essence gate. The distinctive numbers are
asserted one per keyed-table row, because a keyed row that does not exist falls back
silently at another splat's prices — `adding-a-splat.md` trap #2.

Human rulings baked in (2026-08-05): each breed auto-favours its two element Paths
plus one player-chosen Path from the other eight; DK Combos work (the virtual-Charm
bridge); the Intelligence cap by Essence IS modelled; Essence 6 raises Abilities (via
elder.trait_ceiling) and Virtues (DK-only table) to 6. **2026-08-06:** breed attribute
modifiers are free ON TOP of a stored 5 (the effective total may pass 5 at 0 BP); the
stored-5 ceiling and the BP/XP gate above it are the whole attribute rule.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db

_DATA = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_app_ruleset(_DATA)


from exalted_builder.engine import (advancement, costs, derive, lifecycle,  # noqa: E402
                                    paths as engine_paths, validate)
from exalted_builder.models.character import (Character, Combo,  # noqa: E402
                                              MeritFlawPurchase, PathRating)
from exalted_builder.models.rules import (AbilityName, AttributeName,  # noqa: E402
                                          InnateWeapon, VirtueName)


# --------------------------------------------------------------------------- #
# The four data rows + the Paths catalogue
# --------------------------------------------------------------------------- #

def test_the_dragon_kings_exalt_row_is_not_a_fallback(rs) -> None:
    dk = rs.exalt_for("Dragon-Kings")
    assert dk.id == "Dragon-Kings"
    assert dk.label == "Dragon Kings"
    assert dk.caste_noun == "Breed"
    assert dk.tier == "Terrestrial"


def test_the_dragon_kings_single_essence_pool_is_the_printed_formula(rs) -> None:
    """p.177: "(Essence x 4) + (Willpower x 2) + Conviction + Valor", fully
    harmonized (one pool), no anima banner."""
    dk = rs.exalt_for("Dragon-Kings")
    assert dk.single_essence_pool is True
    assert dk.essence.personal_essence_coeff == 4
    assert dk.essence.personal_willpower_coeff == 2
    assert dk.essence.personal_named_virtues == ["conviction", "valor"]
    # No circle is barred at chargen — Terrestrial is the only reachable circle, and
    # barring it would break p.192's chargen spell purchase (review finding 1). Access
    # is enforced by granted_circles, not by this field.
    assert dk.highest_magic_circle_id == ""


def test_the_dragon_kings_life_caps(rs) -> None:
    dk = rs.exalt_for("Dragon-Kings")
    assert dk.essence_cap == 6          # p.177 "Dragon Kings cannot exceed Essence 6"
    assert dk.foreign_charms_barred is True
    assert dk.combos_available is True   # p.177 "may purchase and use Combos normally"
    assert dk.stamina_adds_to_lethal_soak is False   # p.165 physiology sidebar


def test_the_breed_innate_weapons_are_the_printed_tables(rs) -> None:
    """PG pp.167-174 transcribe the four breeds' natural weapons verbatim. Display-only
    (decision 0008 keeps attack derivation out), but a wrong value would show on the
    sheet — the tables were the dead field's only content before this test."""
    expected = {
        "pterok": [
            InnateWeapon(name="Bite", speed=1, accuracy=0, damage=3, damage_type="L", defense=-2),
            InnateWeapon(name="Wing Buffet", speed=1, accuracy=1, damage=4, damage_type="B", defense=0),
        ],
        "raptok": [
            InnateWeapon(name="Bite", speed=0, accuracy=0, damage=3, damage_type="L", defense=-2),
            InnateWeapon(name="Claw", speed=1, accuracy=1, damage=3, damage_type="L", defense=0),
        ],
        "anklok": [
            InnateWeapon(name="Bite", speed=0, accuracy=0, damage=3, damage_type="L", defense=-2),
            InnateWeapon(name="Claw", speed=1, accuracy=1, damage=3, damage_type="L", defense=0),
            InnateWeapon(name="Tail", speed=1, accuracy=-1, damage=4, damage_type="L", defense=-2),
        ],
        "mosok": [
            InnateWeapon(name="Bite", speed=0, accuracy=0, damage=4, damage_type="L", defense=-2),
            InnateWeapon(name="Claw", speed=1, accuracy=1, damage=2, damage_type="L", defense=0),
            InnateWeapon(name="Tail", speed=0, accuracy=-1, damage=5, damage_type="B", defense=-2),
        ],
    }
    for breed_id, weapons in expected.items():
        bt = rs.castes[breed_id].breed_traits
        assert bt.innate_weapons == weapons


def test_the_modern_dragon_king_budget_is_the_printed_one(rs) -> None:
    b = rs.budgets_for("Dragon-Kings", "", "")
    assert b.attribute_pools == (7, 5, 4)
    assert b.ability_dots == 25
    assert b.ability_min_caste_favored == 10
    assert b.favored_count == 3
    assert b.background_dots == 7
    assert b.virtue_dots == 5
    assert b.required_virtue_dots == {VirtueName.VALOR: 1}
    assert b.essence_start == 2
    assert b.essence_start_cap == 3
    assert b.bonus_points == 15
    assert b.charm_count == 0
    assert b.path_dots == 6
    assert b.path_min_breed_favored == 3
    assert b.path_cap_pre_bp == 3
    assert b.path_max_by_essence == {1: 1, 2: 3, 3: 5, 4: 5, 5: 5, 6: 6}


def test_the_ancient_dragon_king_budget_is_the_printed_one(rs) -> None:
    b = rs.budgets_for("Dragon-Kings", "ancient", "")
    assert b.attribute_pools == (8, 6, 5)
    assert b.ability_dots == 35
    assert b.background_dots == 12
    assert b.essence_start == 3
    assert b.essence_start_cap == 5
    assert b.bonus_points == 25
    assert b.path_dots == 10
    assert b.path_min_breed_favored == 5
    # p.160: "All ancient Dragon Kings must know Linguistics • (Old Realm), Lore ••
    # and Occult ••".
    floors = {frozenset(m.abilities): m.rating for m in b.required_min_abilities}
    assert (frozenset([AbilityName.LORE]), 2) in floors.items()
    assert (frozenset([AbilityName.OCCULT]), 2) in floors.items()
    assert (frozenset([AbilityName.LINGUISTICS]), 1) in floors.items()


def test_the_dragon_king_bonus_point_table_is_the_printed_one(rs) -> None:
    c = rs.bonus_costs_for("Dragon-Kings", "", "")
    assert c.attribute == 4 and c.ability == 2 and c.ability_favored_caste == 1
    assert c.background == 1 and c.background_above_3 == 2
    assert c.specialty == 1 and c.specialty_favored_caste_dots_per_point == 2
    assert c.virtue == 3 and c.willpower == 2 and c.essence == 8
    assert c.charm == 7 and c.charm_favored_caste == 7   # prices chargen spells
    assert c.magic_charm == 7                              # the sorcery initiation
    # p.176: "Path | 5 (10 if the Path is being raised above 3); Breed Path | 4 (8 if
    # the Path is being raised above 3)".
    assert c.path == 5 and c.path_breed == 4
    assert c.path_above_3 == 10 and c.path_breed_above_3 == 8


def test_the_dragon_king_xp_table_is_the_printed_one(rs) -> None:
    x = rs.xp_costs_for("Dragon-Kings")
    assert x.essence.coeff == 8
    assert x.new_path == 7 and x.new_path_breed == 6
    assert x.path.coeff == 5 and x.path_breed.coeff == 4
    assert x.new_magic_charm == 12 and x.new_spell == 12


def test_the_ten_paths_catalogue_with_sixty_powers(rs) -> None:
    assert len(rs.paths) == 10
    for path in rs.paths.values():
        assert len(path.powers) == 6
    # The dot-level powers are projected into the charm catalogue as virtual rows so
    # Combos and the sheet can name them — but they are NOT learnable.
    virtual = [c for c in rs.charms.values() if c.virtual]
    assert len(virtual) == 60
    for c in virtual:
        assert validate.charm_matches_splat(
            Character(id="dk", exalt_type="Dragon-Kings"), c, rs) is False


def test_savant_is_ancient_only(rs) -> None:
    """p.176 footnote: "Only ancient Dragon Kings may possess this Background at
    character creation." The excluded origin is the MODERN key, never the ancient
    one — a backwards value would bar the wrong half (review finding, final pass)."""
    modern = {bg.name for bg in rs.backgrounds_for("Dragon-Kings", "")}
    ancient = {bg.name for bg in rs.backgrounds_for("Dragon-Kings", "ancient")}
    assert "Savant" not in modern
    assert "Savant" in ancient


def test_celestial_manse_and_salary_are_dragon_king_backgrounds(rs) -> None:
    names = {bg.name for bg in rs.backgrounds_for("Dragon-Kings", "")}
    assert "Celestial Manse" in names and "Salary" in names
    assert rs.budgets_for("Dragon-Kings", "", "").background_rules[
        "celestial manse"].max_rating == 2
    assert rs.budgets_for("Dragon-Kings", "ancient", "").background_rules[
        "salary"].max_rating == 2


# --------------------------------------------------------------------------- #
# Helper
# --------------------------------------------------------------------------- #

def _dk(caste: str = "pterok", origin: str = "", essence: int = 2, **kw) -> Character:
    """A minimal Dragon King: a Pterok with three non-breed Favoured Abilities, the
    standard virtues, and a solid-Earth favoured Path."""
    c = Character(id="dk.test", exalt_type="Dragon-Kings", caste=caste,
                  origin=origin, essence_rating=essence)
    c.virtues.update({"conviction": 3, "valor": 2, "compassion": 2, "temperance": 2})
    c.favored_abilities = [AbilityName.MELEE, AbilityName.DODGE, AbilityName.SURVIVAL]
    c.favored_path = "dk.solid-earth"
    for k, v in kw.items():
        setattr(c, k, v)
    return c


# --------------------------------------------------------------------------- #
# Derivation: Essence pool, soak, health
# --------------------------------------------------------------------------- #

def test_the_dragon_king_essence_pool_is_single_and_on_formula(rs) -> None:
    c = _dk(essence=3)
    assert derive.willpower(c, rs) == 5        # 3 + 2 (two highest virtues)
    per, peri = derive.essence_pools(rs, c)
    assert derive.essence_pool_is_merged(rs, c) is True
    assert per == 0
    assert peri == 4 * 3 + 2 * 5 + 3 + 2       # Ess×4 + WP×2 + Conviction + Valor = 27


def test_the_dragon_king_soak_is_stamina_plus_innate_only(rs) -> None:
    """p.165: bashing = Stamina + innate armor; lethal = innate armor (Stamina
    contributes nothing). Anklok +6B/6L, Sta 4 → 10B/6L."""
    ank = _dk(caste="anklok")
    ank.attributes[AttributeName.STAMINA] = 4
    sk = derive.soak(ank, rs)
    assert sk.bashing == 10 and sk.lethal == 6
    # A Solar control still gets the half-Stamina lethal term, so the DK special case
    # cannot silently regress toward the Exalt default.
    sol = Character(id="sol.ctl", exalt_type="Solar", caste="dawn", essence_rating=2)
    sol.attributes[AttributeName.STAMINA] = 4
    assert derive.soak(sol, rs).lethal == 2


def test_anklok_and_mosok_get_an_extra_health_level(rs) -> None:
    for caste in ("anklok", "mosok"):
        assert len(derive.health_track(_dk(caste=caste), rs)) == 8
    for caste in ("pterok", "raptok"):
        assert len(derive.health_track(_dk(caste=caste), rs)) == 7


# --------------------------------------------------------------------------- #
# Paths: chargen accounting, favour, Essence gate
# --------------------------------------------------------------------------- #

def test_breed_path_dots_are_free_and_satisfy_the_minimum(rs) -> None:
    """A modern Pterok's three dots in a breed (air) Path cost 0 BP and meet the
    'at least 3 from Breed or Favoured Paths' floor."""
    c = _dk()
    c.paths.append(PathRating(path_id="dk.celestial-air", rating=3))   # breed (air)
    assert engine_paths.path_is_favored(rs, c, "dk.celestial-air") is True
    bb = validate.bonus_point_breakdown(rs, c)
    paths_line = next(l for l in bb.lines if l.domain == "Paths")
    assert paths_line.points == 0
    assert not any(i.code == "path-min-breed-favored"
                   for i in validate.validate_chargen(rs, c))


def test_a_breed_path_dot_above_three_costs_the_breed_above_3_rate(rs) -> None:
    c = _dk()
    c.paths.append(PathRating(path_id="dk.celestial-air", rating=4))
    bb = validate.bonus_point_breakdown(rs, c)
    paths_line = next(l for l in bb.lines if l.domain == "Paths")
    assert paths_line.points == 8              # one dot above 3 × path_breed_above_3


def test_overflow_of_the_path_pool_is_priced_at_the_favoured_rate(rs) -> None:
    """3 favoured (breed) dots + enough dear dots to overflow the 6-dot pool: the
    overflow is paid cheapest-first, at the favoured rate (path_breed, 4)."""
    c = _dk()
    c.paths.append(PathRating(path_id="dk.celestial-air", rating=3))   # cheap (breed)
    c.paths.append(PathRating(path_id="dk.growing-wood", rating=3))    # dear
    c.paths.append(PathRating(path_id="dk.shaping-wood", rating=1))    # dear → 7 within
    bb = validate.bonus_point_breakdown(rs, c)
    paths_line = next(l for l in bb.lines if l.domain == "Paths")
    assert paths_line.points == 4          # 1 overflow dot × path_breed (4)


def test_the_path_bp_recompute_reads_the_snapshot_favored_path(rs) -> None:
    """Decision 0003: the post-lock BP recompute prices creation from the frozen
    snapshot, so a drift in `character.favored_path` after lock must NOT move the
    total. The overflow dot is favoured because the player's chosen path is
    solid-earth; the snapshot must remember that even once the live character's
    `favored_path` is gone (`ChargenSnapshot.favored_path` was written but never
    read — the recompute read the live character instead)."""
    c = _dk()
    c.paths.append(PathRating(path_id="dk.solid-earth", rating=3))   # favoured (choice)
    c.paths.append(PathRating(path_id="dk.growing-wood", rating=3))  # dear
    c.paths.append(PathRating(path_id="dk.shaping-wood", rating=1))  # dear → 7 within
    lifecycle.lock_chargen(c, rs)
    paths_line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                      if l.domain == "Paths")
    assert paths_line.points == 4          # 1 overflow dot × path_breed (4)
    c.favored_path = ""                    # the live choice is gone after lock
    again = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                 if l.domain == "Paths")
    assert again.points == 4               # the snapshot still prices solid-earth favoured


def test_the_essence_gate_caps_paths(rs) -> None:
    """p.177: a Path may not exceed rating 3 at Essence 2. A chargen rating above the
    gate is flagged; an XP raise past it refuses."""
    c = _dk(essence=2)
    c.paths.append(PathRating(path_id="dk.celestial-air", rating=4))
    codes = {i.code for i in validate.validate_chargen(rs, c)}
    assert "path-essence-cap" in codes
    # The buy path: at Essence 2 a Path at 3 cannot be raised to 4.
    c2 = _dk(essence=2)
    c2.paths.append(PathRating(path_id="dk.celestial-air", rating=3))
    lifecycle.lock_chargen(c2, rs)
    advancement.add_xp(c2, 100)
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_path(rs, c2, "dk.celestial-air")


def test_the_intelligence_cap_resolves_against_current_essence(rs) -> None:
    """p.177: Intelligence caps at 1/3/5/6 by Essence — and resolves against the
    CURRENT rating, so a modern DK who BP-buys Essence 3 legitimately lifts the cap
    to 5 (round-2 finding 2)."""
    modern = _dk(essence=2)
    modern.attributes[AttributeName.INTELLIGENCE] = 4
    assert any(i.code == "intelligence-essence-cap"
               for i in validate.validate_chargen(rs, modern))
    bp_boosted = _dk(essence=3)
    bp_boosted.attributes[AttributeName.INTELLIGENCE] = 4
    assert not any(i.code == "intelligence-essence-cap"
                   for i in validate.validate_chargen(rs, bp_boosted))


def test_the_intelligence_cap_binds_post_lock(rs) -> None:
    """The Essence-gated Intelligence ceiling is a CEILING, not a chargen floor — XP
    must not be able to raise Intelligence past it (the Callous shape)."""
    c = _dk(essence=2)
    c.attributes[AttributeName.INTELLIGENCE] = 3
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_attribute(rs, c, AttributeName.INTELLIGENCE)


def test_the_essence_six_virtue_unlock_is_reachable(rs) -> None:
    """p.177 row 6: at Essence 6 a Dragon King may raise Virtues to 6. Without the
    advancement gate this would be unreachable — `raise_virtue`'s default ceiling is
    5, and the unlock is post-lock by construction (Essence 6 needs age >100)."""
    elder = _dk(essence=6)
    elder.virtues[VirtueName.VALOR] = 5
    lifecycle.lock_chargen(elder, rs)
    advancement.add_xp(elder, 100)
    advancement.raise_virtue(rs, elder, VirtueName.VALOR)   # 5 → 6: allowed
    assert elder.virtues[VirtueName.VALOR] == 6
    # …and below Essence 6 the same raise refuses.
    modern = _dk(essence=2)
    modern.virtues[VirtueName.VALOR] = 5
    lifecycle.lock_chargen(modern, rs)
    advancement.add_xp(modern, 100)
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_virtue(rs, modern, VirtueName.VALOR)


def test_the_valor_floor_is_enforced(rs) -> None:
    c = _dk()
    c.virtues[VirtueName.VALOR] = 0
    assert any(i.code == "required-virtue-dots"
               for i in validate.validate_chargen(rs, c))


def test_the_favoured_path_must_not_be_a_breed_path(rs) -> None:
    c = _dk()
    c.favored_path = "dk.celestial-air"     # a Pterok's own breed Path
    assert any(i.code == "favored-path-is-breed-path"
               for i in validate.validate_chargen(rs, c))


def test_a_breed_bonus_stacks_on_top_for_free(rs) -> None:
    """p.175: the breed modifier is a free bonus ON TOP of the stored value, so the
    effective total may pass 5 at 0 BP — a Pterok's stored Dexterity 5 reads as an
    effective 7. Only the STORED value past 5 is the BP/XP gate."""
    c = _dk()                                # Pterok: +2 Dexterity
    c.attributes[AttributeName.DEXTERITY] = 5
    codes = {i.code for i in validate.validate_chargen(rs, c)}
    assert "attribute-breed-bonus-cap" not in codes
    assert "attribute-range" not in codes
    assert not any(i.code == "bonus-points-exceeded"
                   for i in validate.validate_chargen(rs, c))
    attr_line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                     if l.domain == "Attributes")
    assert attr_line.points == 0


def test_a_breed_bonus_attribute_at_four_is_free(rs) -> None:
    """Anklok +2 Str → stored 4 is an effective 6, free: the free cap is stored 5
    for every Attribute, not reduced by the breed bonus."""
    c = _dk(caste="anklok")
    c.attributes[AttributeName.STRENGTH] = 4
    codes = {i.code for i in validate.validate_chargen(rs, c)}
    assert "attribute-breed-bonus-cap" not in codes
    assert not any(i.code == "bonus-points-exceeded"
                   for i in validate.validate_chargen(rs, c))
    attr_line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                     if l.domain == "Attributes")
    assert attr_line.points == 0


def test_a_stored_six_stays_illegal_at_chargen(rs) -> None:
    """The trait cap is Essence (max(5, Essence)); a chargen Dragon King sits at
    Essence 2/3, so stored 6 — even on an unaugmented Attribute — is out of range.
    Past 5 is the post-lock XP path, and it needs Essence 6."""
    c = _dk()                                # Pterok: no Charisma bonus
    c.attributes[AttributeName.CHARISMA] = 6
    assert any(i.code == "attribute-range"
               for i in validate.validate_chargen(rs, c))


def test_an_essence_six_dragon_king_can_xp_raise_an_attribute_to_six(rs) -> None:
    """Essence is the trait cap, so at Essence 6 stored reaches 6 — and the breed
    modifier stacks on top for an effective 8 (Anklok +2 Str)."""
    elder = _dk(caste="anklok", essence=6)
    elder.attributes[AttributeName.STRENGTH] = 5
    lifecycle.lock_chargen(elder, rs)
    advancement.add_xp(elder, 100)
    advancement.raise_attribute(rs, elder, AttributeName.STRENGTH)
    assert elder.attributes[AttributeName.STRENGTH] == 6


def test_a_young_dragon_king_cannot_xp_raise_an_attribute_past_five(rs) -> None:
    """Same cap from the other side: at Essence 2 the trait ceiling is max(5, 2) = 5,
    so XP cannot push a modern Dragon King's Strength past 5."""
    modern = _dk(essence=2)
    modern.attributes[AttributeName.STRENGTH] = 5
    lifecycle.lock_chargen(modern, rs)
    advancement.add_xp(modern, 100)
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_attribute(rs, modern, AttributeName.STRENGTH)


def test_a_dragon_king_cannot_hold_weak_essence(rs) -> None:
    """PG p.41: 'Dragon Kings are an exception to this rule [the starting-Essence-2
    gate], since those with Essence 1 are feral predators unsuitable for players' — a
    BAR, not a waiver: a Dragon King reduced to Essence 1 would be unplayable. The
    `min_starting_essence: 2` floor alone would admit both DK origins (2/3); the
    `barred_exalt_types` row is the exception clause."""
    c = _dk()
    c.merits_flaws = [MeritFlawPurchase(merit_id="mf.weak-essence", points=6)]
    assert any(i.code == "merit-barred-splat"
               for i in validate.validate_chargen(rs, c))
    # A Solar still qualifies via the floor — the bar is Dragon-Kings only.
    sol = Character(id="sol.we", exalt_type="Solar", caste="dawn")
    sol.merits_flaws = [MeritFlawPurchase(merit_id="mf.weak-essence", points=6)]
    assert not any(i.code == "merit-barred-splat"
                   for i in validate.validate_chargen(rs, sol))


# --------------------------------------------------------------------------- #
# Combos: the virtual-Charm bridge (p.177 "may purchase and use Combos normally")
# --------------------------------------------------------------------------- #

def test_a_dragon_king_combo_of_path_powers_is_legal(rs) -> None:
    c = _dk()
    # Bolt of Fire (Blazing Fire dot 3, Simple, Instant) + Perception of Subtle Flaws
    # (Clear Air dot 4, Supplemental, Instant).
    c.paths.append(PathRating(path_id="dk.blazing-fire", rating=3))
    c.paths.append(PathRating(path_id="dk.clear-air", rating=4))
    combo = Combo(name="Sunfire Judgment", charm_ids=[
        "dk.path.dk.blazing-fire.dot3", "dk.path.dk.clear-air.dot4"])
    codes = {i.code for i in validate.combo_issues(rs, c, combo)}
    assert not codes
    eligible = validate.eligible_combo_charms(rs, c)
    assert "dk.path.dk.blazing-fire.dot3" in eligible


def test_virtual_path_powers_are_not_buyable(rs) -> None:
    c = _dk()
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, "dk.path.dk.blazing-fire.dot3")


# --------------------------------------------------------------------------- #
# Sorcery
# --------------------------------------------------------------------------- #

def test_the_dragon_king_sorcery_initiation_has_the_printed_gate_and_cost(rs) -> None:
    """p.192: minimum Essence ••• and Occult •••, 7 BP / 12 XP."""
    charm = rs.charms["dragonkings.occult.terrestrial-circle-sorcery"]
    assert charm.min_essence == 3 and charm.min_ability == 3
    assert charm.grants_circle is not None
    c = _dk(essence=3)
    assert costs.charm_cost(rs, c, charm) == 12


def test_the_dragon_king_artifact_background_buys_double_dots(rs) -> None:
    """p.176: "the Artifact Background of the Dragon Kings provides twice as many dots
    worth of artifacts as normal." Human ruling 2026-08-05 (via a 1e-experienced
    source): "you get (Rating x 2) artifact dots to spread around, with no one
    artifact having a rating higher than (Background rating)". So Artifact • buys a
    2-dot budget with no single artifact above •; a 3-dot artifact with Artifact • is
    over on both axes — a rule that was data-only, never enforced, before this check
    (same gap as the DB double-dots)."""
    from exalted_builder.models.character import ArtifactEntry, BackgroundEntry
    over = _dk()
    over.backgrounds.append(BackgroundEntry(name="Artifact", rating=1))
    over.artifacts.append(ArtifactEntry(name="Winged charm", rating=3))
    # `validate` (the aggregate), not validate_chargen — artifacts are checked on
    # both sides of the lock.
    codes = {i.code for i in validate.validate(rs, over)}
    assert "artifact-over-background-dots" in codes      # 3 > 2
    assert "artifact-item-over-background" in codes      # 3 > 1
    fine = _dk()
    fine.backgrounds.append(BackgroundEntry(name="Artifact", rating=2))
    fine.artifacts.append(ArtifactEntry(name="Winged charm", rating=2))
    fine.artifacts.append(ArtifactEntry(name="Reading crystal", rating=1))
    codes = {i.code for i in validate.validate(rs, fine)}
    assert "artifact-over-background-dots" not in codes  # 3 <= 4
    assert "artifact-item-over-background" not in codes  # each <= 2
    # Two artifacts rated AT the Background rating is two flagships — invalid (human
    # correction 2026-08-05). One flagship plus smaller artifacts is the intended shape.
    two_full = _dk()
    two_full.backgrounds.append(BackgroundEntry(name="Artifact", rating=5))
    two_full.artifacts.append(ArtifactEntry(name="First", rating=5))
    two_full.artifacts.append(ArtifactEntry(name="Second", rating=5))
    codes = {i.code for i in validate.validate(rs, two_full)}
    assert "artifact-two-flagships" in codes
    flagship = _dk()
    flagship.backgrounds.append(BackgroundEntry(name="Artifact", rating=5))
    flagship.artifacts.append(ArtifactEntry(name="First", rating=5))
    flagship.artifacts.append(ArtifactEntry(name="Second", rating=4))
    flagship.artifacts.append(ArtifactEntry(name="Third", rating=1))
    codes = {i.code for i in validate.validate(rs, flagship)}
    assert "artifact-two-flagships" not in codes
    assert "artifact-item-over-background" not in codes
    over_main = _dk()
    over_main.backgrounds.append(BackgroundEntry(name="Artifact", rating=2))
    over_main.artifacts.append(ArtifactEntry(name="Too big", rating=5))
    codes = {i.code for i in validate.validate(rs, over_main)}
    assert "artifact-item-over-background" in codes


def test_highest_magic_circle_is_unchanged_by_the_initiation(rs) -> None:
    """A DK may hold Terrestrial only; the Celestial bar is structural (no DK charm
    grants it) and `highest_magic_circle_id` stays "" (finding 1)."""
    c = _dk(essence=3)
    assert validate.chargen_barred_circle(rs, c) is None
    assert validate.granted_circles(rs, c) == set()


# --------------------------------------------------------------------------- #
# Render smoke (preflight Pass 3): the sheet and picker must BUILD for a DK
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_dragon_king_sheet_renders_paths(user) -> None:
    """The sheet's Paths panel and sectioned charm panels render (they were entirely
    absent before this splat). The Pterok's breed innate weapons also render —
    `BreedTraits.innate_weapons` was authored but dead (no read site) until now."""
    await user.open('/dksheet')
    await user.should_see("PATHS OF PREHUMAN MASTERY")   # _heading upper-cases
    await user.should_see("Celestial Air")
    await user.should_see("INNATE WEAPONS")             # its own section
    await user.should_see("Wing Buffet")
    await user.should_see("Dmg+4B")                     # the printed stat, display-only
    await user.should_see("Charms (0)")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_dragon_king_picker_builds_with_a_paths_tab(user) -> None:
    """The picker builds for a DK (no trap-3 blank) and offers the Paths page."""
    await user.open('/dkpicker')
    await user.should_see("Paths")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_dragon_king_sheet_shows_a_breed_attribute_above_five(user) -> None:
    """p.175: the breed bonus stacks ON TOP of a free stored 5 — the sheet draws the
    Pterok's stored Dexterity 5 as an effective 7, not a 5 clamped to the old cap."""
    await user.open('/dksheet-big')
    await user.should_see("Dexterity (+2 breed)")
    await user.should_see("●●●●● +2")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_artifact_rating_round_trip_keeps_the_two_flagships_warning(user) -> None:
    """Browser re-verify repro (2026-08-05): editing an artifact rating 5→4→5 must
    leave the `artifact-two-flagships` warning live. The engine rebuilt fresh on
    every tab-switch, so a warning that vanished after the round trip meant the
    rating input's on_change was rebuilding the whole body, destroying the widget
    mid-interaction — NiceGUI drops events targeting a deleted element
    (Client.handle_event), so the 4→5 click was silently lost and the stored rating
    desynced from the number on screen.

    The fix has three observable consequences, asserted here:
    1. the rating widget SURVIVES an edit (no body rebuild, so no dropped clicks);
    2. the warning appears LIVE on the Advantages tab itself (the readout now
       carries artifact issues), not only on the Sheet after a tab switch.
    (The combined-budget header line tracks rating edits too, but only splats with
    a budget-tier table print one — DK uses the multiplier rule, so that half is
    pinned in test_rated_artifacts against the Abyssal panel.)

    Assertions are UI-driven: `validate` reads the model, so the warning coming and
    going IS the stored rating persisting. (Asserting on the harness module's
    character object directly is unreliable — the fixture re-runs the harness file
    fresh per test, so `M.CHAR_*` is not the object the routes mutate.)"""
    from nicegui import ui as _ui

    # Advantages tab, two 5-dot artifacts: the warning is live in the readout.
    await user.open('/dk-artifacts-2flag-advantages')
    await user.should_see("permits only one artifact rated at 5")

    def ratings() -> list:
        return [e for e in user.client.elements.values()
                if isinstance(e, _ui.number) and e.props.get("label") == "Rating"]

    r = ratings()
    assert len(r) == 2
    first = r[0]
    first.value = 4                       # 5 -> 4: one flagship remains
    await user.should_not_see("permits only one artifact rated at 5")
    # (1) the widget survived — the same object is still mounted, not a rebuilt one.
    assert ratings()[0] is first

    first.value = 5                       # 4 -> 5: two flagships again, same widget
    # (2) the warning is back, on the same tab, without navigating to the Sheet.
    await user.should_see("permits only one artifact rated at 5")

    # And it is correct on the sheet too.
    await user.open('/dk-artifacts-2flag-sheet')
    await user.should_see("permits only one artifact rated at 5")
