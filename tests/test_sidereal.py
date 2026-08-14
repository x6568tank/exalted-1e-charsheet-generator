"""Sidereal chargen — exercises the shipped Sidereal data (exalts.json Sidereal row,
chargen_budgets/costs_bonus/costs_xp Sidereal rows, the 5 Maiden castes, the
Astrological Colleges, and the full v0.7 Charm catalogue: 193 Charms across 24
ability trees + Violet Bier of Sorrows + 3 Celestial-open Sidereal Martial Arts
styles) against the ability-caste machinery. The 12-Charm pool the earlier
foundation phase could not assert is now covered by
test_sidereal_chargen_clean_with_full_charm_pool.

Sources: The Sidereals p96-101 (Character Creation), Charms chapter (p.140-193);
see [[sidereal-chargen-findings]].
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
    # 12 Charms, >=5 from Auspicious/Favored (all 12 are: 7 auspicious, 5 favored),
    # each within the fixture's ability ratings, none needing a prerequisite.
    c.charms = [
        "sidereal.melee.harmony-of-blows",
        "sidereal.melee.orchestration-of-conflict",
        "sidereal.melee.impeding-the-flow",
        "sidereal.presence.heroic-essence-replenishment",
        "sidereal.presence.presence-in-absence-technique",
        "sidereal.resistance.red-haze",
        "sidereal.resistance.someone-elses-destiny",
        "sidereal.lore.systematic-understanding-of-everything",
        "sidereal.occult.mark-of-exaltation",
        "sidereal.occult.incite-decorum",
        "sidereal.awareness.wise-choice",
        "sidereal.stealth.soft-presence-practice",
    ]
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


# --- Charm catalogue (v0.7): 193 Charms across 24 ability trees + Violet Bier of
# --- Sorrows + 3 Celestial-open Sidereal Martial Arts styles. ------------------

def _sid_charms(rs):
    return [c for c in rs.charms.values() if getattr(c, "exalt_type", None) == "Sidereal"]


def test_sidereal_catalogue_loads(rs):
    """The whole Sidereal catalogue is present and link-checks clean on load."""
    sid = _sid_charms(rs)
    assert len(sid) == 193
    # every prerequisite id resolves to a real Charm
    dangling = [(c.id, p) for c in sid for grp in c.prerequisites for p in grp
                if p not in rs.charms]
    assert dangling == []
    # no Charm is missing a description
    assert [c.id for c in sid if len(c.description.strip()) < 20] == []


def test_sidereal_category_coverage(rs):
    """All 24 auspicious abilities are represented, plus the four MA style trees."""
    cats = {c.category for c in _sid_charms(rs)}
    abilities = {a for a in (
        "endurance ride sail survival thrown craft dodge linguistics performance "
        "socialize archery brawl melee presence resistance investigation larceny "
        "lore occult stealth athletics awareness bureaucracy medicine").split()}
    assert abilities <= cats
    assert "martial_arts:violet-bier-of-sorrows" in cats
    for style in ("charcoal-march-of-spiders", "prismatic-arrangement-of-creation",
                  "citrine-poxes-of-contagion"):
        assert f"martial_arts:{style}" in cats


def test_sidereal_book_martial_arts_styles_are_celestial_open(rs):
    """All four martial-arts styles in The Sidereals are learnable by Celestial
    Exalts — the three secret styles (source preamble: 'treat Sidereal Martial Arts
    as Solar Charms') and Violet Bier of Sorrows.

    ⚠ **Violet Bier was widened on 2026-08-14** (human's ruling: the four styles that
    printed no `Type:` line are all Celestial). This test used to assert it carried
    NO `open_to_tiers` — a conservative default from when the splat was authored, not
    a printed exclusivity. Sidereals p.184 positions it as the lesser style Sidereals
    learn *before* the secret arts, which makes it Celestial rather than Sidereal.

    **The distinction that actually matters did not move**, and is asserted below:
    Violet Bier is not a Sidereal Martial Arts FORM, so it never counts against the
    p.101 chargen cap. That is now `ma_tier`, not `open_to_tiers` — the two were
    conflated, which is the bug `test_a_celestial_style_is_not_a_sidereal_martial_
    arts_form` exists for.
    """
    for c in _sid_charms(rs):
        if c.category.startswith("martial_arts:"):
            assert c.open_to_tiers == ["Celestial"], c.id
    vb = [c for c in _sid_charms(rs) if c.category == "martial_arts:violet-bier-of-sorrows"]
    assert vb and all(c.ma_tier == "Celestial" for c in vb)


def test_sidereal_sorcery_initiations_grant_circles(rs):
    grants = {c.name: str(c.grants_circle) for c in _sid_charms(rs) if getattr(c, "grants_circle", None)}
    assert grants == {"Terrestrial Circle Sorcery": "SpellCircle.TERRESTRIAL",
                      "Celestial Circle Sorcery": "SpellCircle.CELESTIAL"}
    # Celestial requires Terrestrial (the "one prayer strip Charm" clause is narrative)
    cel = rs.charms["sidereal.occult.celestial-circle-sorcery"]
    assert cel.prerequisites == [["sidereal.occult.terrestrial-circle-sorcery"]]


def test_sidereal_deep_prereq_cascade_resolves(rs):
    """A maxed Prismatic capstone resolves its full prerequisite chain."""
    cid = "sidereal.prismatic-arrangement-of-creation.prismatic-arrangement-of-creation-form"
    reqs = validate.meets_charm_requirements
    # walk the whole style: owning every non-capstone Charm must satisfy the capstone
    style = [c for c in _sid_charms(rs)
             if c.category == "martial_arts:prismatic-arrangement-of-creation"]
    owned = {c.id for c in style}
    c = _sidereal()
    c.essence_rating = 5
    for ab in (A.MARTIAL_ARTS,):
        c.abilities[ab] = 5
    c.charms = list(owned - {cid})
    # the capstone's own prerequisites are all in `owned`
    cap = rs.charms[cid]
    assert all(any(p in owned for p in grp) for grp in cap.prerequisites)


def test_sidereal_ox_body_wired(rs):
    e = next(x for x in rs.exalts.values() if x.id == "Sidereal")
    assert e.ox_body_charm_id == "sidereal.endurance.ox-body-technique"
    ob = rs.charms[e.ox_body_charm_id]
    assert ob.repeatable_cap_ability == "endurance" and ob.type.value == "Special"


def test_sidereal_chargen_clean_with_full_charm_pool(rs):
    """Un-defers the 12-Charm assertion the foundation tests could not make: a legal
    Chosen of Battles with a full 12-Charm spend validates with no chargen issues."""
    c = _sidereal()
    assert len(c.charms) == 12
    issues = validate.validate_chargen(rs, c)
    charm_issues = [i for i in issues if "charm" in i.code]
    assert charm_issues == [], charm_issues


# --- Sidereal Martial Arts cost/cap wiring (p.101, p.265) ---------------------
# The SMA rate applies to ALL Martial Arts (Violet Bier AND the 3 supernatural
# styles) — there is no Solar-only Martial Arts a Sidereal cannot learn.

_VB_FLIGHT = "sidereal.violet-bier-of-sorrows.flight-of-mercury"
_SMA_FORM = "sidereal.charcoal-march-of-spiders.dance-of-the-hungry-spider"
_CHARCOAL = [
    "sidereal.charcoal-march-of-spiders.dance-of-the-hungry-spider",
    "sidereal.charcoal-march-of-spiders.maw-of-dripping-venom",
    "sidereal.charcoal-march-of-spiders.rain-of-unseen-threads",
    "sidereal.charcoal-march-of-spiders.nest-of-living-strands",
]


def _form_ids(rs):
    return [cid for cid, ch in rs.charms.items()
            if ch.category.startswith("martial_arts") and ch.open_to_tiers]


def test_sidereal_martial_arts_bp_and_xp_rates(rs):
    bc = rs.bonus_costs_for("Sidereal")
    xp = rs.xp_costs_for("Sidereal")
    assert (bc.martial_arts_charm, bc.martial_arts_charm_favored_caste) == (8, 6)   # vs Charm 7/5
    assert (xp.new_martial_arts_charm, xp.new_martial_arts_charm_favored_caste) == (12, 10)  # vs 11/9
    # other splats leave the fields None → their MA Charms keep the ordinary rate
    assert rs.bonus_costs_for("Solar").martial_arts_charm is None
    assert rs.xp_costs_for("Lunar").new_martial_arts_charm is None


def test_sidereal_all_martial_arts_use_the_ma_xp_rate(rs):
    """Violet Bier AND the supernatural styles both cost 12 XP (10 if MA is Caste)."""
    battles = _sidereal("battles"); battles.abilities[A.MARTIAL_ARTS] = 5; battles.essence_rating = 5
    endings = _sidereal("endings"); endings.abilities[A.MARTIAL_ARTS] = 5; endings.essence_rating = 5
    for cid in (_VB_FLIGHT, _SMA_FORM):
        charm = rs.charms[cid]
        assert costs.charm_cost(rs, battles, charm) == 12   # Battles: MA not Auspicious
        assert costs.charm_cost(rs, endings, charm) == 10   # Endings: MA is Auspicious → discount
    # an ordinary ability Charm is unaffected (Battles Melee is Caste → 9)
    assert costs.charm_cost(rs, battles, rs.charms["sidereal.melee.harmony-of-blows"]) == 9


def test_sidereal_martial_arts_bp_rate_in_breakdown(rs):
    """A Martial Arts pick paid from bonus points is charged 8 (6 if MA is Caste)."""
    forms = _form_ids(rs)[:13]                          # 13 picks, free pool is 12
    battles = _sidereal("battles"); battles.charms = forms
    endings = _sidereal("endings"); endings.charms = forms
    def charm_bp(c):
        bd = validate.bonus_point_breakdown(rs, c)
        return next(l.points for l in bd.lines if l.domain == "Charms & Spells")
    assert charm_bp(battles) == 8      # MA not Caste for Battles
    assert charm_bp(endings) == 6      # MA is Caste for Endings


def test_sidereal_martial_arts_form_chargen_cap(rs):
    """p.101: no more than 3 chargen Charms from a Sidereal Martial Arts *form*.
    Violet Bier is not a form and does not count against the cap."""
    c = _sidereal("endings")
    c.charms = _CHARCOAL                                 # 4 form Charms → over the cap
    assert _codes(validate.validate_chargen(rs, c), "charm-too-many-martial-arts-forms") != []
    c.charms = _CHARCOAL[:3]                             # exactly 3 → allowed
    assert _codes(validate.validate_chargen(rs, c), "charm-too-many-martial-arts-forms") == []
    c.charms = _CHARCOAL[:3] + [_VB_FLIGHT]              # Violet Bier does not count
    assert _codes(validate.validate_chargen(rs, c), "charm-too-many-martial-arts-forms") == []


def test_sidereal_ronin_may_take_no_martial_arts_forms(rs):
    """p.101: a ronin may take NONE from a Sidereal Martial Arts form; Violet Bier
    of Sorrows stays open to them."""
    c = _sidereal("endings"); c.origin = "ronin"
    c.charms = [_SMA_FORM]                               # even one form is barred
    assert _codes(validate.validate_chargen(rs, c), "charm-too-many-martial-arts-forms") != []
    c.charms = [_VB_FLIGHT]                              # Violet Bier remains legal
    assert _codes(validate.validate_chargen(rs, c), "charm-too-many-martial-arts-forms") == []


def test_a_celestial_style_is_not_a_sidereal_martial_arts_form(rs):
    """⚠ REGRESSION, 2026-08-14. The p.101 cap identified a "Sidereal Martial Arts
    form" as any martial-arts Charm with a non-empty `open_to_tiers`. That is a
    proxy for "Celestial-open", not for "Sidereal", and it matched 140 Charms across
    TWELVE styles when only 41 across three are Sidereal MA — the five Immaculate
    Dragon Paths, Celestial Monkey, Dreaming Pearl, Righteous Devil and Hungry Ghost
    all counted against the cap.

    The sharpest symptom: a RONIN, whose cap is 0, could not take a single Celestial
    Monkey Charm — a style with no Sidereal connection whatsoever.

    The discriminator is now `Charm.ma_tier`, projected from the style catalogue at
    load. This test pins the distinction from the OTHER side of the cap, so a future
    proxy that happens to satisfy the tests above cannot reintroduce it.
    """
    celestial = [c.id for c in rs.charms.values()
                 if c.category == "martial_arts:celestial-monkey"][:4]
    assert len(celestial) == 4

    c = _sidereal("endings")
    c.charms = celestial
    assert _codes(validate.validate_chargen(rs, c),
                  "charm-too-many-martial-arts-forms") == []

    # And for the ronin, whose cap of 0 made the bug unmissable.
    c = _sidereal("endings"); c.origin = "ronin"
    c.charms = celestial[:1]
    assert _codes(validate.validate_chargen(rs, c),
                  "charm-too-many-martial-arts-forms") == []


def test_only_the_three_sidereal_styles_count_as_forms(rs):
    """Pin the SET, not just a sample. Sidereals pp.184-201 print exactly three
    secret styles; everything else with a martial-arts category is a lesser style.
    A new style authored with the wrong tier fails here rather than silently
    changing what a Sidereal may buy at chargen."""
    forms = {c.category for c in rs.charms.values() if c.ma_tier == "Sidereal"}
    assert forms == {
        "martial_arts:charcoal-march-of-spiders",
        "martial_arts:citrine-poxes-of-contagion",
        "martial_arts:prismatic-arrangement-of-creation",
    }
