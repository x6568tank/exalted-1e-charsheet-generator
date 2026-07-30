"""Merits & Flaws — the Thaumaturgy slice (Player's Guide pp.120-122).

Decision 0011: M&F return as ONE centralized calculation, never the per-file hooks
that got them ripped out in June 2026. The load-bearing test in this module is
`test_no_module_outside_engine_merits_names_a_merit_id` — it is what stops the old
situation recreating itself.

These 11 Merits were authored first because they are the mortal magic-access set:
Essence Awareness unlocks part of a mortal's Essence pool, Essence Mastery unlocks all
of it and opens Terrestrial Martial Arts and Terrestrial sorcery. See
docs/status/merits-flaws.md.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import advancement, costs, derive, merits, validate
from exalted_builder.models.character import Character, MeritFlawPurchase as MP
from exalted_builder.models.rules import SpellCircle
from exalted_builder.ui import view
from exalted_builder.models.rules import VirtueName as V

DATA_DIR = Path(exalted_builder.__file__).parent / "data"

AWARENESS = "thaum.essence-awareness"
MASTERY = "thaum.essence-mastery"
OATH = "thaum.oathbound-magic"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _mortal(*purchases, **kw) -> Character:
    c = Character(id="c.m", exalt_type="Mortal", caste="", origin="heroic",
                  essence_rating=1, merits_flaws=list(purchases))
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _unlocked(*extra, **kw) -> Character:
    return _mortal(MP(merit_id=AWARENESS), MP(merit_id=MASTERY), *extra, **kw)


def _codes(issues, code):
    return [i for i in issues if i.code == code]


# --- decision 0011: the containment rule ------------------------------------ #

def test_no_module_outside_engine_merits_names_a_merit_id():
    """THE test for decision 0011. Merits were removed because their effects were
    scattered; the whole design is that `engine/merits.py` is the only module that
    knows a Merit id exists. Everything else reads MeritEffects fields.

    If this fails, do NOT add the offending file to an allowlist — move the branch
    into merits_and_flaws_calc and give MeritEffects a field for it.
    """
    pkg = Path(exalted_builder.__file__).parent
    offenders = []
    for path in sorted(pkg.rglob("*.py")):
        if path.name == "merits.py":
            continue
        text = path.read_text()
        if "thaum.essence-" in text or "thaum.oathbound" in text:
            offenders.append(str(path.relative_to(pkg)))
    assert offenders == []


def test_merit_definitions_carry_no_mechanical_effect(rs):
    """rules.MeritFlaw is inert by design: printed text, cost, prerequisites. A field
    describing what a Merit DOES belongs in engine.merits, not the data."""
    fields = set(type(next(iter(rs.merits_flaws.values()))).model_fields)
    assert fields == {"id", "name", "kind", "category", "cost", "cost_options",
                      "cost_options_by_exalt_type", "cost_options_by_caste", "cost_by_kind",
                      "variable_cost", "exalt_types", "cost_note",
                      "prerequisites", "prerequisite_note", "repeatable_by",
                      "thaumaturges_only", "description", "source"}


# --- the catalogue ---------------------------------------------------------- #

def test_the_eleven_thaumaturgy_merits_load(rs):
    """The pp.120-122 slice, which is keyed `thaum.*`. The general chapter is keyed
    `mf.*` and is counted separately, so this stays exact as that lands."""
    thaum = {m.id: m for m in rs.merits_flaws.values() if m.id.startswith("thaum.")}
    assert len(thaum) == 11
    assert len([m for m in thaum.values() if m.kind == "merit"]) == 8
    assert len([m for m in thaum.values() if m.kind == "flaw"]) == 3
    # printed point values, spot-checked against the page
    assert rs.merits_flaws[AWARENESS].cost == 3
    assert rs.merits_flaws[MASTERY].cost == 5
    assert rs.merits_flaws["thaum.holy-mien"].cost == 7
    assert rs.merits_flaws["thaum.essence-recovery"].cost == 2


def test_a_printed_prerequisite_we_cannot_check_is_text_not_a_broken_link(rs):
    """Celestial Travel Permit needs "Celestial Patron of at least 2" — a Background,
    not a Merit. It must be SHOWN, and must not masquerade as a checkable link."""
    permit = rs.merits_flaws["thaum.celestial-travel-permit"]
    assert permit.prerequisites == []
    assert "Celestial Patron" in permit.prerequisite_note


# --- Essence unlock --------------------------------------------------------- #

def test_a_mortal_without_merits_has_no_essence_pool(rs):
    eff = merits.merits_and_flaws_calc(rs, _mortal())
    assert eff.essence_pool_unlocked is False
    assert derive.essence_pools(rs, _mortal()) == (0, 0)


def test_essence_awareness_unlocks_the_pool_but_not_without_restriction(rs):
    eff = merits.merits_and_flaws_calc(rs, _mortal(MP(merit_id=AWARENESS)))
    assert eff.essence_pool_unlocked is True
    assert eff.essence_pool_unrestricted is False    # 2/3 needs a Willpower roll


def test_the_unlocked_mortal_pool_formula(rs):
    """PG p.114: "an Essence pool equal to (Essence + Willpower + Conviction +
    [highest Virtue x 2])" — one pool, so peripheral stays 0."""
    c = _mortal(MP(merit_id=AWARENESS))
    c.virtues = {V.COMPASSION: 2, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 4}
    # Willpower = two highest Virtues = 4 + 3 = 7
    # 1 (Essence) + 7 (WP) + 3 (Conviction) + 4x2 (highest) = 19
    assert derive.essence_pools(rs, c) == (19, 0)


def test_an_exalt_pool_is_untouched_by_the_merit_machinery(rs):
    """The unlock is keyed on the splat having no native pool, not on being Mortal —
    and an Exalt must compute identically whether or not they hold Merits."""
    s = Character(id="s", exalt_type="Solar", caste="dawn")
    before = derive.essence_pools(rs, s)
    s.merits_flaws = [MP(merit_id=AWARENESS), MP(merit_id=MASTERY)]
    assert derive.essence_pools(rs, s) == before
    assert merits.merits_and_flaws_calc(rs, s).essence_cap_override is None


def test_essence_mastery_raises_the_cap_to_three_and_no_further(rs):
    """"the limit of human potential — mortals that exceed Essence 3 become gods"
    (PG p.114). The 20/40 XP prices come from the p.115 table."""
    c = _unlocked()
    c.chargen_locked = True
    advancement.add_xp(c, 200)
    assert advancement.raise_essence(rs, c).cost == 20      # -> Essence 2
    assert advancement.raise_essence(rs, c).cost == 40      # -> Essence 3
    with pytest.raises(advancement.AdvancementError, match="above 3"):
        advancement.raise_essence(rs, c)


def test_without_mastery_essence_stays_pinned_at_one(rs):
    c = _mortal(MP(merit_id=AWARENESS))
    c.chargen_locked = True
    advancement.add_xp(c, 200)
    with pytest.raises(advancement.AdvancementError, match="above 1"):
        advancement.raise_essence(rs, c)


# --- magic access ----------------------------------------------------------- #

def test_essence_mastery_opens_terrestrial_martial_arts(rs):
    """"Characters with Essence Mastery have sufficient Essence to activate the Root
    of the Perfected Lotus and practice Terrestrial Martial Arts" (PG p.121)."""
    plain, unlocked = _mortal(), _unlocked()
    style = rs.charms["dragonblooded.martial-arts.spirit-sight"]
    assert validate.charm_matches_splat(plain, style, rs) is False
    assert validate.charm_matches_splat(unlocked, style, rs) is True


def test_spirit_walking_stays_barred_even_with_mastery(rs):
    """It is what grants CELESTIAL Martial Arts, which a mortal can never reach
    (human, rules authority, 2026-07-30 — "it is just the one Charm").

    Note the existing tier machinery does NOT catch this on its own: Spirit Walking
    is `open_to_all`, so without the explicit bar it would come free with the style.
    """
    walking = rs.charms[merits.SPIRIT_WALKING]
    assert walking.open_to_all is True          # the reason a bar is needed at all
    assert validate.charm_matches_splat(_unlocked(), walking, rs) is False
    # ...while its PREREQUISITE remains legal and simply dead-ends
    sight = rs.charms["dragonblooded.martial-arts.spirit-sight"]
    assert validate.charm_matches_splat(_unlocked(), sight, rs) is True


def test_mastery_does_not_open_ordinary_charms(rs):
    """A Merit opens Martial Arts, not Charms at large: a Solar Melee Charm stays
    out of reach."""
    melee = rs.charms["solar.melee.excellent-strike"]
    assert validate.charm_matches_splat(_unlocked(), melee, rs) is False
    assert _codes(validate.validate(rs, _unlocked(charms=["solar.melee.excellent-strike"])),
                  "charms-not-available")


def test_mastery_grants_terrestrial_sorcery_only(rs):
    """A mortal holds no Charms, so a Merit-granted circle is their only route to
    sorcery — and it stops at Terrestrial (human, 2026-07-30)."""
    assert validate.accessible_circles(rs, _mortal()) == set()
    assert validate.accessible_circles(rs, _unlocked()) == {SpellCircle.TERRESTRIAL}


# --- points ----------------------------------------------------------------- #

def test_merits_cost_bonus_points_and_flaws_do_not(rs):
    c = _mortal(MP(merit_id=AWARENESS), MP(merit_id=MASTERY),
                MP(merit_id="thaum.dark-magics"))
    assert validate.merit_bonus_point_cost(rs, c) == 8      # 3 + 5; the Flaw is free


def test_oathbound_stacking_matches_the_printed_example(rs):
    """PG p.122: "a pair of oaths to never initiate violence and to use no bladed
    weapon would be worth five bonus points, rather than six (3 + 3, -1 for an
    additional oath in the same arena)."

    NOTE the page's prose ("reduced in value by the total number of oaths") and its
    worked example disagree — prose would give 4. The example is implemented.
    """
    two_same = _mortal(MP(merit_id=OATH, tier="moderate", arena="combat"),
                       MP(merit_id=OATH, tier="moderate", arena="combat"))
    assert merits.oathbound_bonus_points(two_same, rs) == 5

    two_different = _mortal(MP(merit_id=OATH, tier="moderate", arena="combat"),
                            MP(merit_id=OATH, tier="moderate", arena="food"))
    assert merits.oathbound_bonus_points(two_different, rs) == 6   # arenas don't interact

    alone = _mortal(MP(merit_id=OATH, tier="legendary", arena="x"))
    assert merits.oathbound_bonus_points(alone, rs) == 8


def test_an_oath_raises_the_bonus_point_allowance_not_the_spend(rs):
    """A Flaw's value is a GRANT. Modelled on `available` rather than as a negative
    spend line, so it can never silently pay for an overspend elsewhere."""
    base = validate.bonus_point_breakdown(rs, _mortal())
    with_oath = validate.bonus_point_breakdown(
        rs, _mortal(MP(merit_id=OATH, tier="major", arena="combat")))
    assert base.available == 21
    assert with_oath.available == 26                 # 21 + 5
    assert with_oath.total == base.total             # the Flaw costs nothing


def test_merit_xp_is_double_the_bonus_point_value(rs):
    """PG p.115: "New Merit (mystical only) | cost in bonus points x2"."""
    c = _mortal()
    assert costs.merit_cost(rs, c, rs.merits_flaws[AWARENESS]) == 6     # 3 x2
    assert costs.merit_cost(rs, c, rs.merits_flaws[MASTERY]) == 10      # 5 x2
    assert costs.merit_cost(rs, c, rs.merits_flaws[OATH], "major") == 10


# --- validation ------------------------------------------------------------- #

@pytest.mark.parametrize("purchases,code", [
    ([MP(merit_id=MASTERY)], "merit-prerequisite"),
    ([MP(merit_id="thaum.nope")], "merit-unknown"),
    ([MP(merit_id=OATH, tier="enormous")], "merit-bad-tier"),
    ([MP(merit_id=AWARENESS), MP(merit_id=AWARENESS)], "merit-repeated"),
])
def test_structural_merit_problems_are_reported(rs, purchases, code):
    assert _codes(validate.merit_issues(rs, _mortal(*purchases)), code)


def test_a_repeatable_merit_may_be_taken_more_than_once(rs):
    """The Flow of Essence: "May be taken more than once, selecting a different
    Attribute group each time."""
    c = _mortal(MP(merit_id=AWARENESS),
                MP(merit_id="thaum.flow-of-essence", detail="Physical"),
                MP(merit_id="thaum.flow-of-essence", detail="Mental"))
    assert _codes(validate.merit_issues(rs, c), "merit-repeated") == []


def test_thaumaturges_only_is_enforced(rs):
    """Oathbound Magic is "THAUMATURGES ONLY" — a character holding no Arts,
    Sciences, rituals or formulas may not take it."""
    c = _mortal(MP(merit_id=OATH, tier="minor", arena="x"))
    assert _codes(validate.merit_issues(rs, c), "merit-thaumaturges-only")


# --- advancement ------------------------------------------------------------ #

def test_buying_a_merit_with_xp_respects_prerequisites(rs):
    c = _mortal()
    c.chargen_locked = True
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError, match="requires Essence Awareness"):
        advancement.buy_merit(rs, c, MASTERY)
    assert advancement.buy_merit(rs, c, AWARENESS).cost == 6
    assert advancement.buy_merit(rs, c, MASTERY).cost == 10
    assert [p.merit_id for p in c.merits_flaws] == [AWARENESS, MASTERY]


def test_flaws_cannot_be_bought_with_experience(rs):
    """A Flaw is taken at creation in exchange for bonus points. Buying a
    disadvantage for XP is not a transaction the rules contemplate."""
    c = _mortal()
    c.chargen_locked = True
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError, match="is a Flaw"):
        advancement.buy_merit(rs, c, "thaum.dark-magics")


def test_merits_freeze_into_the_chargen_snapshot(rs):
    """Merits bought at creation must snapshot with everything else, or the XP audit
    would re-price them against a moving baseline."""
    from exalted_builder.engine import lifecycle
    c = _mortal(MP(merit_id=AWARENESS))
    c.virtues = {V.COMPASSION: 1, V.CONVICTION: 1, V.TEMPERANCE: 1, V.VALOR: 1}
    lifecycle.lock_chargen(c)
    assert [p.merit_id for p in c.chargen_snapshot.merits_flaws] == [AWARENESS]


def test_immaculate_martial_arts_stays_barred_from_mortals(rs):
    """Human, rules authority, 2026-07-30. The five elemental Dragon styles are the
    Immaculate Dragon Paths — exactly what Spirit Walking exists to unlock — so they
    are closed to mortals even though Essence Mastery opens Terrestrial MA generally.

    A CLASS of Charms, not a list of ids, hence its own MeritEffects flag. Note the
    ordinary Dragon-Path gate does NOT cover this: `db_enlightenment_met` is
    Dragon-Blooded-specific and returns True for everyone else.
    """
    unlocked = _unlocked()
    assert merits.merits_and_flaws_calc(rs, unlocked).bar_immaculate_charms is True
    dragon = rs.charms["dragonblooded.air-dragon.air-dragons-sight"]
    assert validate.is_immaculate_charm(dragon) is True
    assert validate.charm_matches_splat(unlocked, dragon, rs) is False
    # ...while non-Immaculate Terrestrial styles remain open
    assert validate.charm_matches_splat(
        unlocked, rs.charms["solar.martial-arts.living-shield-technique"], rs) is True


def test_a_dragon_blooded_is_unaffected_by_the_mortal_immaculate_bar(rs):
    """The bar rides on a Merit effect, so it must not leak onto the splat whose
    Charms these actually are."""
    db = Character(id="db", exalt_type="Dragon-Blooded", caste="air",
                   charms=["dragonblooded.martial-arts.spirit-sight",
                           merits.SPIRIT_WALKING])
    dragon = rs.charms["dragonblooded.air-dragon.air-dragons-sight"]
    assert validate.charm_matches_splat(db, dragon, rs) is True


# --- UI render (NiceGUI User harness) --------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_editor_merits_panel_renders(user) -> None:
    """Including the variable-cost row, whose tier/arena controls exist only for
    Oathbound Magic, and an unresolvable id — a select whose value is absent from its
    options raises at build time and would take the whole editor down."""
    await user.open('/merits')
    await user.should_see("Merits & Flaws")
    await user.should_see("Essence Mastery")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_sheet_shows_merits_with_the_flaw_signed_positive(user) -> None:
    await user.open('/merits-sheet')
    await user.should_see("Merits & Flaws")
    await user.should_see("Essence Awareness")
    await user.should_see("+5")          # the major oath GRANTS points
    await user.should_see("−5")          # Essence Mastery COSTS them


# --- post-creation change (PG p.17, "Gaining and Losing Merits and Flaws") --- #
# The book gives three methods and lets the ST choose. Only "experience" moves XP;
# "backgrounds" and "swap" are mechanically identical here and differ only in what
# they oblige the Storyteller to do at the table.

from exalted_builder.models.character import HouseRules


def _locked(*purchases, method="experience", xp=0) -> Character:
    c = _mortal(*purchases, house_rules=HouseRules(mf_change_method=method))
    c.chargen_locked = True
    advancement.add_xp(c, xp)
    return c


def test_experience_is_the_default_method():
    assert HouseRules().mf_change_method == "experience"


@pytest.mark.parametrize("method", ["backgrounds", "swap"])
def test_the_other_two_methods_move_no_experience(rs, method):
    """"do not cost or reward players after character creation" (PG p.17)."""
    c = _locked(method=method, xp=50)
    assert advancement.buy_merit(rs, c, AWARENESS).cost == 0
    assert advancement.xp_available(c) == 50
    assert advancement.gain_flaw(rs, c, "thaum.dark-magics").cost == 0
    assert advancement.xp_available(c) == 50


def test_gaining_a_merit_costs_twice_its_value(rs):
    c = _locked(xp=50)
    assert advancement.buy_merit(rs, c, AWARENESS).cost == 6      # 3 BP x2
    assert advancement.xp_available(c) == 44


def test_gaining_a_flaw_pays_twice_its_value(rs):
    """"If a character loses a Merit or gains a Flaw, she receives a number of
    experience points equal to twice its bonus point value.\""""
    c = _locked(xp=0)
    entry = advancement.gain_flaw(rs, c, "thaum.dark-magics")
    assert entry.cost == -6                                        # 3 BP x2, paid TO her
    assert advancement.xp_available(c) == 6


def test_losing_a_merit_pays_and_losing_a_flaw_charges(rs):
    c = _locked(MP(merit_id=AWARENESS), MP(merit_id="thaum.dark-magics"), xp=50)
    before = advancement.xp_available(c)
    # drop the Flaw (index 1) — buying it off CHARGES her
    assert advancement.drop_merit(rs, c, 1).cost == 6
    assert advancement.xp_available(c) == before - 6
    # drop the Merit — losing it PAYS her
    assert advancement.drop_merit(rs, c, 0).cost == -6
    assert advancement.xp_available(c) == before


def test_a_merit_that_is_a_prerequisite_cannot_be_dropped(rs):
    c = _locked(MP(merit_id=AWARENESS), MP(merit_id=MASTERY), xp=50)
    with pytest.raises(advancement.AdvancementError, match="prerequisite of Essence Mastery"):
        advancement.drop_merit(rs, c, 0)


# --- the debt mechanic ------------------------------------------------------- #

def test_an_unaffordable_change_goes_into_debt_rather_than_being_refused(rs):
    """"If the character cannot pay this full cost, she pays whatever she has
    available and must allocate all further experience to the remaining balance until
    it is paid in full" (PG p.17). A Merit change is not always the player's choice,
    so it takes on a balance instead of being refused the way a Charm would be."""
    c = _locked(xp=10)
    advancement.buy_merit(rs, c, AWARENESS)          # 6, affordable
    advancement.buy_merit(rs, c, MASTERY)            # 10, only 4 left
    assert advancement.xp_debt(c) == 6
    assert advancement.xp_available(c) == -6


def test_debt_clears_itself_as_experience_is_earned(rs):
    c = _locked(xp=10)
    advancement.buy_merit(rs, c, AWARENESS)
    advancement.buy_merit(rs, c, MASTERY)
    advancement.add_xp(c, 4)
    assert advancement.xp_debt(c) == 2
    advancement.add_xp(c, 10)
    assert advancement.xp_debt(c) == 0


def test_debt_never_destroys_experience(rs):
    """THE regression test for this mechanic. An earlier cut STORED the balance and
    paid it down inside add_xp, while logging only the affordable part of the cost —
    so the remainder was never counted as spent and 6 XP silently vanished. Debt is
    derived from (earned - spent) precisely so that cannot happen."""
    c = _locked(xp=10)
    advancement.buy_merit(rs, c, AWARENESS)          # 6
    advancement.buy_merit(rs, c, MASTERY)            # 10  -> 16 total
    advancement.add_xp(c, 14)                        # 24 earned
    assert advancement.xp_spent(c) == 16             # the FULL cost is logged
    assert advancement.xp_available(c) == 24 - 16
    assert advancement.xp_debt(c) == 0


def test_debt_is_derived_not_stored():
    """If this fails someone reintroduced the field; read xp_debt's docstring first."""
    assert "xp_debt" not in Character.model_fields


# --- the 10-point Flaw cap (PG p.16 and p.17) -------------------------------- #

def test_every_flaw_grants_its_value_not_just_oathbound(rs):
    """"Flaws work in reverse, imposing disadvantages in exchange for additional
    bonus points" (PG p.16) — general, not special to Oathbound Magic."""
    c = _mortal(MP(merit_id="thaum.dark-magics"),
                MP(merit_id="thaum.sheltered-upbringing"))
    assert merits.merits_and_flaws_calc(rs, c).bonus_point_grant == 6      # 3 + 3


def test_flaw_grant_is_capped_at_ten_and_reports_the_raw_total(rs):
    """"Characters may only receive up to 10 extra bonus points from Flaws,
    regardless of the number taken" (p.16). The uncapped figure is still reported so
    the UI can say "10 of 14" rather than silently swallowing four points."""
    c = _mortal(MP(merit_id="thaum.dark-magics"),
                MP(merit_id="thaum.sheltered-upbringing"),
                MP(merit_id=OATH, tier="legendary", arena="x"))
    eff = merits.merits_and_flaws_calc(rs, c)
    assert eff.flaw_points_raw == 14                # 3 + 3 + 8
    assert eff.bonus_point_grant == merits.FLAW_POINT_CAP == 10


def test_the_cap_reaches_the_bonus_point_allowance(rs):
    c = _mortal(MP(merit_id="thaum.dark-magics"),
                MP(merit_id="thaum.sheltered-upbringing"),
                MP(merit_id=OATH, tier="legendary", arena="x"))
    assert validate.bonus_point_breakdown(rs, c).available == 21 + 10      # not 21 + 14


def test_no_experience_for_flaws_past_the_cap(rs):
    """p.17: "Characters with more than 10 points of Flaws receive no experience for
    the excess." Measured against the Flaws already held."""
    at_cap = _locked(MP(merit_id=OATH, tier="legendary", arena="x"),
                     MP(merit_id="thaum.sheltered-upbringing"), xp=0)     # 11 points
    assert advancement.gain_flaw(rs, at_cap, "thaum.dark-magics").cost == 0

    # a Flaw that straddles the cap pays for its legal part only: 8 held, room 2,
    # a 3-point Flaw -> two thirds of its 6 XP
    straddling = _locked(MP(merit_id=OATH, tier="legendary", arena="x"), xp=0)
    assert advancement.gain_flaw(rs, straddling, "thaum.dark-magics").cost == -4


# --- the general chapter (PG pp.16-41), authored in batches ------------------ #

def test_general_chapter_rows_are_well_formed(rs):
    """Every `mf.*` row must price by exactly one shape. The chapter's cost lines are
    too irregular to parse mechanically (see docs/status/merits-flaws.md), so these
    numbers were read by hand — this asserts the SHAPE, and the spot-checks below
    assert individual values against their printed line."""
    general = [m for m in rs.merits_flaws.values() if m.id.startswith("mf.")]
    assert general, "no general-chapter Merits authored yet"
    for m in general:
        shapes = [bool(m.cost), bool(m.cost_options), m.variable_cost,
                  bool(m.cost_by_kind)]
        assert sum(shapes) == 1, f"{m.id} must use exactly one cost shape"
        assert m.category in ("Physical", "Mental", "Social", "Property", "Supernatural")
        assert m.description and m.source.page


def test_per_splat_costs_price_by_the_characters_splat(rs):
    """"(1- OR 2-PT. MERIT, 1-PT. FOR LUNARS)" is a real mechanical difference, not
    flavour — a Lunar pays 1 where everyone else pays 2."""
    def bp(splat, caste, **kw):
        c = Character(id="c", exalt_type=splat, caste=caste, merits_flaws=[MP(**kw)])
        return validate.merit_bonus_point_cost(rs, c)
    assert bp("Solar", "dawn", merit_id="mf.ambidextrous", tier="2") == 2
    assert bp("Lunar", "full-moon", merit_id="mf.ambidextrous", tier="2") == 1
    # "(5-PT. MERIT, 3-PT. FOR EXALTED)" — enumerated per splat rather than special-cased
    assert bp("Mortal", "", merit_id="mf.legendary-attribute") == 5
    assert bp("Solar", "dawn", merit_id="mf.legendary-attribute") == 3


def test_a_variable_cost_merit_prices_from_the_purchase(rs):
    """"(VARIABLE COST MERIT)" — the page fixes no price, so the table's agreed value
    rides on the purchase."""
    assert rs.merits_flaws["mf.special-resistance"].variable_cost is True
    c = Character(id="c", exalt_type="Solar", caste="dawn",
                  merits_flaws=[MP(merit_id="mf.special-resistance", points=4)])
    assert validate.merit_bonus_point_cost(rs, c) == 4


def test_the_whole_general_chapter_is_authored(rs):
    """87 entries across pp.16-41 — 43 Merits and 44 Flaws, in five categories."""
    general = [m for m in rs.merits_flaws.values() if m.id.startswith("mf.")]
    assert len(general) == 87
    # Three entries are printed as BOTH ("MERIT OR FLAW"), so they carry kind
    # "either" and sit in neither count — 43/44 is how the chapter PRINTS them.
    either = [m for m in general if m.kind == "either"]
    assert {m.id for m in either} == {"mf.mutation", "mf.favor", "mf.eternal-vow"}
    assert len([m for m in general if m.kind == "merit"]) + len(either) == 43
    assert len([m for m in general if m.kind == "flaw"]) == 44
    assert {m.category for m in general} == {
        "Physical", "Mental", "Social", "Property", "Supernatural"}


def test_every_entry_keeps_its_printed_cost_line(rs):
    """`cost_note` is verbatim, because a few qualifiers cannot be modelled at all
    (a per-caste price, a relative one) and dropping them would lose printed rules."""
    for m in rs.merits_flaws.values():
        if m.id.startswith("mf."):
            assert m.cost_note.startswith("(") and m.cost_note.endswith(")"), m.id
            assert "MERIT" in m.cost_note.upper() or "FLAW" in m.cost_note.upper()


@pytest.mark.parametrize("mid,expected", [
    # the four the first parser got WRONG, pinned against their printed lines
    ("mf.pain-tolerance", {"3": 3, "5": 5, "7": 7}),      # (3-, 5- OR 7-PT. MERIT)
    ("mf.mute", {"1": 1, "3": 3, "4": 4}),                # (1-, 3- OR 4-PT. FLAW, ...)
    ("mf.sun-seared", {"2": 2, "3": 3, "6": 6}),          # (2-, 3- OR 6-PT. FLAW)
    ("mf.amnesia", {"1": 1, "2": 2, "5": 5}),             # (1-, 2- OR 5-PT. FLAW)
])
def test_comma_separated_price_lists_survive(rs, mid, expected):
    assert rs.merits_flaws[mid].cost_options == expected


def test_a_range_expands_inclusively(rs):
    """"2- TO 6-PT." is every rung, not just the endpoints."""
    assert rs.merits_flaws["mf.virtue-specialty"].cost_options == {
        str(n): n for n in range(2, 7)}


def test_ocr_split_names_are_repaired_but_apostrophes_survive(rs):
    """A word broken after a capital is rejoined; "TAINT'S WARNING" is two words."""
    names = {m.name for m in rs.merits_flaws.values()}
    assert "Double-Jointed" in names and "Hidden Manse" in names
    assert "Taint'S Warning" in names or "Taint's Warning" in names
    assert not any("Sheir" in n or "Swarning" in n for n in names)


def test_restricted_entries_record_their_splats(rs):
    assert rs.merits_flaws["mf.chimera"].exalt_types == ["Lunar"]
    assert rs.merits_flaws["mf.legendary-breeding"].exalt_types == ["Dragon-Blooded"]
    assert set(rs.merits_flaws["mf.greater-curse"].exalt_types) == {
        "Solar", "Lunar", "Sidereal", "Abyssal"}


# --- the four qualifier rulings (human, 2026-07-30) ------------------------- #

def test_brigids_heir_prices_by_caste(rs):
    """"(5-PT. MERIT, 4-PT. FOR TWILIGHT CASTE)" — the only price in 87 entries that
    keys on caste rather than splat, so caste outranks the splat override."""
    def bp(caste):
        c = Character(id="c", exalt_type="Solar", caste=caste,
                      merits_flaws=[MP(merit_id="mf.brigid-s-heir")])
        return validate.merit_bonus_point_cost(rs, c)
    assert bp("twilight") == 4
    assert bp("dawn") == 5


def test_mute_costs_an_exalt_one_less_with_no_zero_rung(rs):
    """"1-PT. LESS FOR EXALTED" applied to 1/3/4. The rung that would become 0 is
    dropped (human's ruling): a Flaw granting nothing is not a purchase."""
    mute = rs.merits_flaws["mf.mute"]
    assert mute.cost_options == {"1": 1, "3": 3, "4": 4}
    assert mute.cost_options_by_exalt_type["Solar"] == {"2": 2, "3": 3}
    assert 0 not in mute.cost_options_by_exalt_type["Solar"].values()


@pytest.mark.parametrize("mid", ["mf.mutation", "mf.favor", "mf.eternal-vow"])
def test_two_sided_entries_let_the_purchase_choose(rs, mid):
    """"MERIT OR FLAW" — which side applies is the player's choice, not the
    catalogue's."""
    assert rs.merits_flaws[mid].kind == "either"
    as_merit = MP(merit_id=mid, taken_as="merit", points=2)
    as_flaw = MP(merit_id=mid, taken_as="flaw", points=2)
    assert validate.effective_merit_kind(rs.merits_flaws[mid], as_merit) == "merit"
    assert validate.effective_merit_kind(rs.merits_flaws[mid], as_flaw) == "flaw"


def test_eternal_vow_prices_each_side_differently(rs):
    """"(3-PT. MERIT OR 1-PT. FLAW)" — the Flaw side was lost entirely before."""
    ev = rs.merits_flaws["mf.eternal-vow"]
    assert ev.cost_by_kind == {"merit": 3, "flaw": 1}
    c = Character(id="c", exalt_type="Solar", caste="dawn",
                  merits_flaws=[MP(merit_id="mf.eternal-vow", taken_as="merit")])
    assert validate.merit_bonus_point_cost(rs, c) == 3
    # taken as a Flaw it costs nothing and GRANTS 1
    c.merits_flaws = [MP(merit_id="mf.eternal-vow", taken_as="flaw")]
    assert validate.merit_bonus_point_cost(rs, c) == 0
    assert merits.flaw_points(rs, c) == 1


def test_a_two_sided_entry_taken_as_a_flaw_grants_points(rs):
    c = Character(id="c", exalt_type="Solar", caste="dawn",
                  merits_flaws=[MP(merit_id="mf.mutation", taken_as="flaw", points=4)])
    assert merits.merits_and_flaws_calc(rs, c).bonus_point_grant == 4
    assert validate.merit_bonus_point_cost(rs, c) == 0


def test_an_unchosen_side_is_reported_not_silently_defaulted(rs):
    """Pricing defaults an either-entry to "merit" so nothing crashes, but the
    player must actually make the choice — so validate says so."""
    c = _mortal(MP(merit_id="mf.mutation", points=2))
    assert _codes(validate.merit_issues(rs, c), "merit-side-unchosen")
    c.merits_flaws = [MP(merit_id="mf.mutation", taken_as="flaw", points=2)]
    assert _codes(validate.merit_issues(rs, c), "merit-side-unchosen") == []


def test_splat_restrictions_are_now_enforced(rs):
    """`exalt_types` was authored but inert until this check."""
    lunar_only = MP(merit_id="mf.chimera")
    assert _codes(validate.merit_issues(rs, _mortal(lunar_only)), "merit-wrong-splat")
    lunar = Character(id="l", exalt_type="Lunar", caste="full-moon",
                      merits_flaws=[lunar_only])
    assert _codes(validate.merit_issues(rs, lunar), "merit-wrong-splat") == []


# --- Holy Mien's cross-Merit grant (PG p.121 + p.24) ------------------------ #

def test_holy_mien_grants_priest_free_and_discounts_its_high_rung(rs):
    """"grants the character possessing it the Priest Merit at the one-point level at
    no extra cost and reduces the cost of the seven-point level to six bonus points."

    Priest lives in the general chapter, so this could not be wired until that landed.
    Expressed as MeritEffects fields — no caller names either Merit."""
    def bp(*p):
        c = Character(id="c", exalt_type="Solar", caste="dawn", merits_flaws=list(p))
        return validate.merit_bonus_point_cost(rs, c)
    hm, p1 = MP(merit_id="thaum.holy-mien"), MP(merit_id="mf.priest", tier="1")
    p7 = MP(merit_id="mf.priest", tier="7")
    assert bp(p1) == 1 and bp(p7) == 7               # unaffected on their own
    assert bp(hm, p1) == 7                           # Holy Mien 7 + Priest(1) free
    assert bp(hm, p7) == 7 + 6                       # ...and the 7-pt rung drops to 6


def test_the_granted_merit_is_reported_for_display(rs):
    c = Character(id="c", exalt_type="Solar", caste="dawn",
                  merits_flaws=[MP(merit_id="thaum.holy-mien")])
    assert merits.merits_and_flaws_calc(rs, c).granted_merits == frozenset({"mf.priest"})
    # ...and nothing is granted without it
    c.merits_flaws = []
    assert merits.merits_and_flaws_calc(rs, c).granted_merits == frozenset()


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_xp_tab_offers_merit_gain_and_loss(user) -> None:
    """The post-lock M&F controls. This page also guards a shadowing bug that took the
    WHOLE XP tab down: the card's select was first named `sel`, which Python then
    treated as local throughout `panel()`, leaving the raise-a-trait selectors
    unassigned."""
    await user.open('/mf-xp')
    await user.should_see("Merits & Flaws")
    await user.should_see("Gain")
    await user.should_see("Raise a Trait")      # the card the shadowing bug killed
    # the preview renders before anything is selected, rather than being absent
    await user.should_see("Select an entry to see its rules text.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_sheet_lists_merits_alongside_backgrounds(user) -> None:
    """The panel shares a row with Backgrounds, Specialties, Colleges and
    Thaumaturgy. That row WRAPS: on a no-wrap row five panels squeeze the later ones
    to slivers, which is why this block looked missing when it was merely crushed."""
    await user.open('/merits-sheet')
    await user.should_see("Merits & Flaws")
    await user.should_see("Backgrounds")
    await user.should_see("Essence Mastery")


def test_sheet_rows_carry_the_rules_text_for_the_tooltip(rs):
    """The sheet panel shares a row with four others, so the text cannot be printed
    inline — it rides on a hover tooltip instead. Reported 2026-07-30: the block was
    there but showed only a name and a number, which is not usable at the table."""
    c = _mortal(MP(merit_id=MASTERY), MP(merit_id="mf.brigid-s-heir"))
    rows = {r[0]: r for r in view.merit_rows(rs, c)}
    name, points, _detail, _kind, tip = rows["Essence Mastery"]
    assert points == "−5"
    assert "Root of the Perfected Lotus" in tip          # the rules text
    assert rows["Brigid'S Heir"][4].startswith("(5-PT.")  # ...and the printed cost line


def test_an_unresolvable_row_explains_itself_in_the_tooltip(rs):
    c = _mortal(MP(merit_id="mf.not-a-merit"))
    row = view.merit_rows(rs, c)[0]
    assert row[0].startswith("⚠")
    assert "missing" in row[4]
