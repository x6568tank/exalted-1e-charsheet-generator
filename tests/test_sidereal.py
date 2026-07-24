"""Sidereal chargen foundation — exercises the shipped Sidereal data (exalts.json
Sidereal row, chargen_budgets/costs_bonus/costs_xp Sidereal rows, the 5 Maiden
castes) against the existing ability-caste machinery. Charms and the Astrological
College subsystem land in later phases, so these tests assert on the specific
pieces the foundation provides rather than a fully-clean validate_chargen (which
needs the 12-Charm pool the catalogue will supply).

Sources: The Sidereals p96-101 (Character Creation); see [[sidereal-chargen-findings]].
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import advancement, costs, derive, lifecycle, validate
from exalted_builder.models.character import Character, CollegeRating
from exalted_builder.models.rules import AbilityName as A
from exalted_builder.models.rules import AttributeName as AT
from exalted_builder.models.rules import VirtueName as V
from exalted_builder.ui import view

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _codes(issues, code):
    return [i for i in issues if i.code == code]


def _sidereal(caste="battles") -> Character:
    """A Chosen of Battles meeting BOTH the Celestial Hierarchy minimums and the
    Battles per-house floor (Archery/Melee ●●●, Athletics ●●, Dodge ●●, Presence ●●,
    Resistance ●●, p.98), a legal 8/6/4 attribute spend and a full 35-dot ability
    spend (≥15 on Auspicious/Favored, ≤3 each). Battles Auspicious: archery, brawl,
    melee, presence, resistance."""
    c = Character(id="sid.test", exalt_type="Sidereal", caste=caste)
    c.favored_abilities = [A.AWARENESS, A.OCCULT, A.LORE, A.STEALTH]     # 4, none Battles-auspicious
    c.attributes.update({
        AT.STRENGTH: 5, AT.DEXTERITY: 4, AT.STAMINA: 2,        # Physical spend = 8
        AT.CHARISMA: 4, AT.MANIPULATION: 3, AT.APPEARANCE: 2,  # Social spend = 6
        AT.PERCEPTION: 3, AT.INTELLIGENCE: 2, AT.WITS: 2,      # Mental spend = 4
    })
    c.abilities.update({
        A.ARCHERY: 1, A.BRAWL: 1, A.MELEE: 3, A.PRESENCE: 2, A.RESISTANCE: 2,  # auspicious = 9
        A.AWARENESS: 2, A.OCCULT: 2, A.LORE: 3, A.STEALTH: 1,                   # favored = 8
        A.ATHLETICS: 2, A.DODGE: 2, A.BUREAUCRACY: 2, A.LINGUISTICS: 1,
        A.MARTIAL_ARTS: 2, A.SOCIALIZE: 1,                                     # other minimums = 10
        A.RIDE: 3, A.SAIL: 3, A.SURVIVAL: 2,                                   # filler = 8  (total 35)
    })
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 2, V.TEMPERANCE: 3, V.VALOR: 1})
    c.essence_rating = 2
    # 7 College dots, ≥4 in the Battles Maiden's House of War (p.98).
    c.colleges = [
        CollegeRating(college_id="sidereal.battles.banner", rating=3),
        CollegeRating(college_id="sidereal.battles.shield", rating=1),   # own-house = 4
        CollegeRating(college_id="sidereal.journeys.captain", rating=2),
        CollegeRating(college_id="sidereal.secrets.key", rating=1),      # other = 3 (total 7)
    ]
    return c


def test_sidereal_essence_pools(rs):
    c = _sidereal()
    # WP = 6 (3+3, two highest Virtues). Personal = 2×2 + 6; Peripheral = 2×6 + 6 + Σ(3+2+3+1).
    assert derive.willpower(c) == 6
    assert derive.essence_pools(rs, c) == (10, 27)


def test_sidereal_five_maiden_castes(rs):
    castes = {cid: c for cid, c in rs.castes.items() if c.exalt_type == "Sidereal"}
    assert set(castes) == {"journeys", "serenity", "battles", "secrets", "endings"}
    # Auspicious Abilities are the caste abilities (p.97).
    assert set(castes["battles"].caste_abilities) == {A.ARCHERY, A.BRAWL, A.MELEE, A.PRESENCE, A.RESISTANCE}
    assert set(castes["secrets"].caste_abilities) == {A.INVESTIGATION, A.LARCENY, A.LORE, A.OCCULT, A.STEALTH}


def test_sidereal_budgets(rs):
    b = rs.budgets_for("Sidereal")
    assert b.attribute_pools == (8, 6, 4)
    assert (b.ability_dots, b.ability_min_caste_favored, b.favored_count) == (35, 15, 4)
    assert (b.charm_count, b.charm_min_caste_favored) == (12, 5)
    assert (b.background_dots, b.virtue_dots, b.bonus_points) == (15, 5, 18)
    assert len(b.required_min_abilities) == 9


def test_sidereal_bonus_and_xp_costs(rs):
    bc = rs.bonus_costs_for("Sidereal")
    assert (bc.charm, bc.charm_favored_caste) == (7, 5)
    assert bc.essence == 10
    xp = rs.xp_costs_for("Sidereal")
    assert xp.essence.coeff == 9                       # user rule (p265 omits it; Lunar's is ×9)
    assert (xp.new_charm, xp.new_charm_favored_caste) == (11, 9)   # p265


def test_sidereal_required_minimums_satisfied(rs):
    c = _sidereal()
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") == []


def test_sidereal_missing_lore_minimum_flagged(rs):
    c = _sidereal()
    c.abilities[A.LORE] = 2                            # Celestial Hierarchy floor is Lore ●●●
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") != []


def test_sidereal_per_house_minimum_flagged(rs):
    # Battles' per-house floor requires Dodge ●● (p.98) — not part of the universal
    # Celestial Hierarchy minimums. Dropping it must flag, proving the caste's
    # required_min_abilities are unioned in.
    c = _sidereal(caste="battles")
    c.abilities[A.DODGE] = 1
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") != []
    # Secrets has no Dodge floor, so the same sheet as a Secrets caste wouldn't flag
    # Dodge — its floors are different (Awareness/Investigation/Larceny ●●●, etc.).
    secrets = rs.castes["secrets"]
    assert any(A.DODGE in req.abilities for req in rs.castes["battles"].required_min_abilities)
    assert not any(A.DODGE in req.abilities for req in secrets.required_min_abilities)


def test_sidereal_auspicious_ability_gets_the_discount(rs):
    c = _sidereal()
    # Melee is a Battles Auspicious (caste) ability → discounted; Sail is neither.
    assert costs.ability_step(rs, c, A.MELEE, 2) == 3      # 2×2 − 1
    assert costs.ability_step(rs, c, A.SAIL, 2) == 4       # 2×2, full


# --- Astrological Colleges (p.98, p.220-235) ------------------------------- #

def test_college_catalogue_is_25_across_5_houses(rs):
    assert len(rs.colleges) == 25
    from collections import Counter
    by_house = Counter(c.house for c in rs.colleges.values())
    assert by_house == {"journeys": 5, "serenity": 5, "battles": 5, "secrets": 5, "endings": 5}
    # a College's house is a caste id (so the own-Maiden rule matches Character.caste)
    assert rs.colleges["sidereal.serenity.ewer"].house == "serenity"
    assert rs.colleges["sidereal.serenity.ewer"].house_label == "House of Leisure"


def test_sidereal_college_budget(rs):
    b = rs.budgets_for("Sidereal")
    assert (b.college_dots, b.college_min_own_house, b.college_cap_pre_bp) == (7, 4, 3)
    bc = rs.bonus_costs_for("Sidereal")
    assert (bc.college, bc.college_own_house) == (8, 6)
    xp = rs.xp_costs_for("Sidereal")
    assert xp.new_college == 5 and xp.college.coeff == 3


def test_sidereal_college_own_house_minimum(rs):
    c = _sidereal()                                       # 4 own-house dots → ok
    assert _codes(validate.validate_chargen(rs, c), "college-own-house-min") == []
    c.colleges[1] = CollegeRating(college_id="sidereal.battles.shield", rating=0)   # own = 3
    assert _codes(validate.validate_chargen(rs, c), "college-own-house-min") != []


def test_sidereal_unknown_college_flagged(rs):
    c = _sidereal()
    c.colleges.append(CollegeRating(college_id="sidereal.nowhere.void", rating=1))
    assert _codes(validate.validate_chargen(rs, c), "unknown-college") != []


def test_sidereal_college_bonus_points(rs):
    c = _sidereal()
    line = next((l for l in validate.bonus_point_breakdown(rs, c).lines
                 if l.domain == "Colleges"), None)
    assert line is not None and line.points == 0          # 7 dots, none over cap → free
    # Nine dots (6 own @6, 3 other @8): free pool absorbs the 3 dear + 4 own, overflow
    # is 2 own-house dots paid cheapest-first → 2 × 6.
    c.colleges = [
        CollegeRating(college_id="sidereal.battles.banner", rating=3),
        CollegeRating(college_id="sidereal.battles.shield", rating=3),
        CollegeRating(college_id="sidereal.journeys.captain", rating=3),
    ]
    line = next(l for l in validate.bonus_point_breakdown(rs, c).lines if l.domain == "Colleges")
    assert line.points == 12


def test_non_sidereal_has_no_college_line(rs):
    solar = Character(id="sol", exalt_type="Solar", caste="dawn")
    assert all(l.domain != "Colleges" for l in validate.bonus_point_breakdown(rs, solar).lines)


def test_sidereal_college_xp_advancement(rs):
    c = _sidereal()
    lifecycle.lock_chargen(c)
    c.xp_earned = 100
    # New college costs the flat new_college (5); raising scales current × 3.
    e1 = advancement.learn_college(rs, c, "sidereal.endings.crow")
    assert e1.cost == 5 and any(cr.college_id == "sidereal.endings.crow" for cr in c.colleges)
    e2 = advancement.raise_college(rs, c, "sidereal.endings.crow")     # 1 → 2
    assert e2.cost == 3                                                # 1 × 3
    audit = {i.code for i in advancement.validate_xp(rs, c)}
    assert "xp-overspend" not in audit and "xp-mismatch" not in audit
    advancement.undo_last(rs, c)                                       # reverse the raise
    assert next(cr.rating for cr in c.colleges if cr.college_id == "sidereal.endings.crow") == 1
    advancement.undo_last(rs, c)                                       # reverse the learn
    assert not any(cr.college_id == "sidereal.endings.crow" for cr in c.colleges)


# --------------------------------------------------------------------------- #
# College presentation (pure presenter — see ui/view.py)
# --------------------------------------------------------------------------- #

def test_college_rows_mark_own_house_and_sort_it_first(rs):
    c = _sidereal()                                    # Chosen of Battles
    c.colleges = [
        CollegeRating(college_id="sidereal.journeys.gull", rating=1),      # other house
        CollegeRating(college_id="sidereal.battles.shield", rating=3),     # own Maiden
    ]
    rows = view.college_rows(rs, c)
    names = [r[0] for r in rows]
    assert rows[0][3] is True and rows[0][1] == 3      # own-house Battles college first
    assert rows[1][3] is False                         # Journeys after it
    assert len(names) == 2 and all(r[2] for r in rows)  # every row carries a house label


def test_college_rows_survive_an_unknown_id(rs):
    """A College id no longer in the RuleSet must still render (as its raw id) rather
    than silently vanishing from the sheet — the reader needs to see the breakage."""
    c = _sidereal()
    c.colleges = [CollegeRating(college_id="sidereal.nowhere.void", rating=2)]
    rows = view.college_rows(rs, c)
    assert rows == [("sidereal.nowhere.void", 2, "?", False)]


def test_sheet_view_carries_colleges_and_other_splats_get_none(rs):
    c = _sidereal()
    c.colleges = [CollegeRating(college_id="sidereal.battles.shield", rating=2)]
    assert view.build_sheet_view(rs, c).colleges
    solar = Character(id="sol", exalt_type="Solar", caste="dawn")
    assert view.build_sheet_view(rs, solar).colleges == []


def test_college_xp_log_label_names_the_college(rs):
    """Without a `colleges` branch the log falls through to the raw target string —
    the same class of miss the Beastman Gifts log had (see CLAUDE.md)."""
    c = _sidereal()
    lifecycle.lock_chargen(c)
    c.xp_earned = 20
    advancement.learn_college(rs, c, "sidereal.endings.crow")
    label = view.build_xp_log(rs, c)[-1].label
    assert "Crow" in label and "colleges" not in label


# --------------------------------------------------------------------------- #
# Ronin (p.100) — the Sidereal who evaded the Celestial Hierarchy
# --------------------------------------------------------------------------- #

def test_ronin_budget_row(rs):
    b = rs.budgets_for("Sidereal", "ronin")
    assert (b.ability_dots, b.ability_min_caste_favored) == (25, 10)   # "only 25 ... at least ten"
    assert b.background_dots == 7                                       # "only seven (7) dots"
    assert (b.charm_count, b.charm_min_caste_favored) == (8, 5)         # 8 Charms; >=5 C/F carries over
    assert (b.college_dots, b.college_min_own_house) == (0, 0)          # "no access to the colleges"
    assert b.attribute_pools == (8, 6, 4) and b.bonus_points == 18      # unchanged from the standard row
    # A ronin still HAS a Caste, so the per-house floor must be suppressed explicitly.
    assert b.ignore_caste_min_abilities is True
    assert b.required_min_abilities == []


def test_ronin_has_no_ability_minimums(rs):
    """p.100: "They have no minimum required Ability scores." — including the caste's
    own per-house floor, which a ronin would otherwise still inherit from its Caste."""
    c = _sidereal()
    c.origin = "ronin"
    c.abilities[A.LORE] = 0        # breaks the universal Celestial Hierarchy floor
    c.abilities[A.DODGE] = 0       # breaks the Battles per-house floor
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") == []
    # …while the same sheet as a Hierarchy Sidereal flags both.
    c.origin = "hierarchy"
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") != []


def test_ronin_background_allow_list(rs):
    from exalted_builder.models.character import BackgroundEntry
    c = _sidereal()
    c.origin = "ronin"
    c.backgrounds = [BackgroundEntry(name="Allies", rating=2),
                     BackgroundEntry(name="Manse", rating=1)]
    assert _codes(validate.validate_chargen(rs, c), "background-not-allowed") == []
    c.backgrounds.append(BackgroundEntry(name="Salary", rating=2))   # Hierarchy-only
    flagged = _codes(validate.validate_chargen(rs, c), "background-not-allowed")
    assert len(flagged) == 1 and flagged[0].where == "Salary"
    # A blank row is the editor's "fill me in" placeholder, not an illegal Background.
    c.backgrounds = [BackgroundEntry(name="", rating=0)]
    assert _codes(validate.validate_chargen(rs, c), "background-not-allowed") == []


def test_non_ronin_backgrounds_stay_unrestricted(rs):
    """The allow-list is opt-in per origin; every other splat keeps Backgrounds soft."""
    from exalted_builder.models.character import BackgroundEntry
    c = _sidereal()                                    # standard Hierarchy Sidereal
    c.backgrounds = [BackgroundEntry(name="Anything At All", rating=1)]
    assert _codes(validate.validate_chargen(rs, c), "background-not-allowed") == []
    assert rs.budgets_for("Solar").allowed_backgrounds == []


def test_sidereal_limit_track_is_called_paradox(rs):
    """p.253 — a rename of the same 0-10 Limit track, not a new mechanic."""
    c = _sidereal()
    assert derive.limit_label(rs, c) == "Paradox"
    assert derive.limit_label(rs, Character(id="s", exalt_type="Solar", caste="dawn")) == "Limit"
