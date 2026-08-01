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
from nicegui import ui

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import advancement, costs, derive, lifecycle, merits, validate
from exalted_builder.models.character import BackgroundEntry, Character, MeritFlawPurchase as MP
from exalted_builder.models.rules import SpellCircle
from exalted_builder.ui import view
from exalted_builder.models.rules import VirtueName as V
from exalted_builder.models.rules import AttributeName as A
from exalted_builder.models.rules import AbilityName

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
    describing what a Merit DOES belongs in engine.merits, not the data.

    Restrictions on what may be BOUGHT are the one thing that does live here, because
    a restriction is inert in exactly the way a cost is — `barred_exalt_types`,
    `barred_castes` and `points_limited_by` (Known Anathema against Influence, Damaged
    Artifact against Artifact, Debt against Resources) are all of that kind.

    The line this draws is EFFECT vs RESTRICTION. A restriction is as inert as a
    cost — it says who may hold the entry, never what holding it does.
    """
    fields = set(type(next(iter(rs.merits_flaws.values()))).model_fields)
    assert fields == {"id", "name", "kind", "category", "cost", "cost_options",
                      "cost_options_by_exalt_type", "cost_options_by_caste", "cost_by_kind",
                      "variable_cost", "exalt_types", "barred_exalt_types",
                      "cost_note", "barred_castes", "prerequisites", "min_starting_essence",
                      "tier_barred_exalt_types", "prerequisite_note", "trait_prerequisites",
                      "max_purchases_from_trait", "points_limited_by", "repeatable_by",
                      "takes_stipulations",
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


def test_essence_awareness_frees_only_a_third_of_the_pool(rs):
    """PG p.120: "divide it into two pools: the first, equal to one third of the
    pool, can be drawn on normally … the other two thirds can only be accessed with
    a Willpower roll". The pool itself is NOT reduced — all 19 motes are the
    character's, 6 of them freely. Rounding is floor (an open question, see
    `derive.essence_freely_accessible`)."""
    c = _mortal(MP(merit_id=AWARENESS))
    c.virtues = {V.COMPASSION: 2, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 4}
    assert derive.essence_pools(rs, c) == (19, 0)      # unchanged by the split
    assert derive.essence_freely_accessible(rs, c) == 6


def test_essence_mastery_frees_the_whole_pool(rs):
    """p.121: "her entire Essence pool without limit or required rolls". None means
    unrestricted, which must be distinguishable from a freely-drawable 0."""
    c = _mortal(MP(merit_id=AWARENESS), MP(merit_id=MASTERY))
    c.virtues = {V.COMPASSION: 2, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 4}
    assert derive.essence_pools(rs, c) == (19, 0)
    assert derive.essence_freely_accessible(rs, c) is None


def test_an_exalt_is_never_restricted_by_holding_essence_awareness(rs):
    """The restriction keys on having no NATIVE pool, so a Solar who somehow holds
    the Merit still draws on all of theirs."""
    s = Character(id="s", exalt_type="Solar", caste="dawn")
    s.merits_flaws = [MP(merit_id=AWARENESS)]
    assert derive.essence_freely_accessible(rs, s) is None


def test_the_willpower_roll_is_described_not_modelled(rs):
    """Decision 0009: the roll is dice and stays out of the engine. It must still
    reach the player, so it lives in the Merit's printed description — which is what
    the sheet's tooltip shows."""
    assert "Willpower roll" in rs.merits_flaws[AWARENESS].description


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


# --- magic access: the BUY paths -------------------------------------------- #
# Both bugs below were found by a player, not by the suite, because every test above
# stops at the effect (charm_matches_splat, accessible_circles) and never asks the
# gate that actually spends the points. That is the dead-effect-field trap wearing a
# different hat: the grant existed and nothing downstream read it.

MA_CHARM = "solar.martial-arts.living-shield-technique"


def _martial(*extra, **kw) -> Character:
    """An unlocked mortal with enough Martial Arts to meet a first-tier style Charm."""
    c = _unlocked(*extra, **kw)
    c.abilities[AbilityName.MARTIAL_ARTS] = 3
    return c


def test_mastery_lets_a_mortal_buy_martial_arts_with_experience(rs):
    """The chargen half already worked; the XP half refused on the splat's flat
    `charms_available` flag and never asked the Merit. A Charm a mortal may legally
    pick at creation must not become unbuyable the moment they lock."""
    c = _martial()
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 60)
    entry = advancement.learn_charm(rs, c, MA_CHARM)
    assert entry.target == "charms" and entry.cost > 0
    assert MA_CHARM in c.charms


@pytest.mark.parametrize("charm_id", [
    merits.SPIRIT_WALKING,                  # explicitly barred (Celestial MA)
    "solar.melee.excellent-strike",         # never opened: not Martial Arts
])
def test_the_xp_path_still_refuses_what_mastery_does_not_open(rs, charm_id):
    """Widening the gate must not become "a mortal with any Merit buys anything"."""
    c = _martial()
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 60)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, charm_id)


def test_a_mortal_without_mastery_still_buys_no_charms_at_all(rs):
    c = _mortal()
    c.abilities[AbilityName.MARTIAL_ARTS] = 3
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 60)
    with pytest.raises(advancement.AdvancementError, match="cannot purchase Charms"):
        advancement.learn_charm(rs, c, MA_CHARM)


def test_validation_does_not_flag_a_charm_mastery_legitimately_opened(rs):
    """The same flat flag a third time: check_splat_consistency short-circuited on
    `charms_available` and condemned EVERY Charm a mortal held, so a legally bought
    style Charm sat on the sheet as a permanent error."""
    c = _martial(charms=[MA_CHARM])
    assert _codes(validate.validate(rs, c), "charms-not-available") == []
    # ...while the Charm Mastery does NOT open is still condemned, by that same code.
    bad = _martial(charms=["solar.melee.excellent-strike"])
    assert _codes(validate.validate(rs, bad), "charms-not-available")


def _terrestrial_spell(rs):
    return next(s for s in rs.spells.values() if s.circle == SpellCircle.TERRESTRIAL)


def test_mastery_makes_terrestrial_spells_takeable_not_merely_visible(rs):
    """The grant reached `accessible_circles` (what the picker LISTS) but not
    `granted_circles` (what the picker marks available, and what validation checks),
    so every spell rendered as a locked row reading "needs a Charm granting the
    Terrestrial Circle" — a Charm a mortal can never hold."""
    spell = _terrestrial_spell(rs)
    assert validate.granted_circles(rs, _unlocked()) == {SpellCircle.TERRESTRIAL}
    assert validate.meets_spell_requirements(rs, _unlocked(), spell) is True
    row = next(r for r in view.build_spell_picker(rs, _unlocked()) if r.id == spell.id)
    assert row.available is True and row.reason == ""
    # ...and holding it validates clean, rather than raising spell-circle forever.
    assert _codes(validate.check_spell_access(rs, _unlocked(spells=[spell.id])),
                  "spell-circle") == []


def test_a_mortal_with_mastery_can_buy_a_terrestrial_spell_with_experience(rs):
    c = _unlocked()
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 60)
    spell = _terrestrial_spell(rs)
    assert advancement.learn_spell(rs, c, spell.id).cost > 0
    assert spell.id in c.spells


def test_a_mortal_without_mastery_reaches_no_circle(rs):
    """The grant is Mastery's, not "any mortal with Merits"."""
    assert validate.granted_circles(rs, _mortal()) == set()
    assert not any(r.available for r in view.build_spell_picker(rs, _mortal()))


def test_an_exalt_circle_access_is_unchanged_by_the_merit_machinery(rs):
    """granted_circles now consults Merits for everyone; a Solar's answer must still
    come from their known Charms alone."""
    s = Character(id="s", exalt_type="Solar", caste="twilight")
    assert validate.granted_circles(rs, s) == set()
    s.merits_flaws = [MP(merit_id=AWARENESS), MP(merit_id=MASTERY)]
    assert validate.granted_circles(rs, s) == set()


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
@pytest.mark.parametrize("route", ['/mastery-picker', '/mastery-picker-xp'])
async def test_mastery_puts_the_martial_arts_and_spell_pages_back(user, route) -> None:
    """The mirror of test_mortal_picker_offers_no_charm_pages_and_still_renders: a
    mortal normally gets neither page, and Essence Mastery must bring both back —
    before AND after the lock, which is where the player's report landed."""
    await user.open(route)
    # The page toggle is a ui.toggle, whose labels are props rather than text nodes,
    # so its options are read off the element rather than through should_see.
    groups = set(next(iter(user.find(ui.toggle).elements)).options.values())
    assert {"Martial Arts", "Spells"} <= groups
    # ...and the Charm-tree furniture the plain mortal must NOT have is back.
    await user.should_see("Category")


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
    """88 entries across pp.16-41 — 43 Merits and 45 Flaws, in five categories.

    Was 87 until 2026-07-30: Dying (p.31) had been missed entirely when the chapter
    was pasted, and its tail had been glued onto a truncated Amputee. Both were found
    by diffing every description against the source .md rather than by reading — see
    docs/status/merits-flaws-triage.md.
    """
    general = [m for m in rs.merits_flaws.values() if m.id.startswith("mf.")]
    assert len(general) == 88
    # Three entries are printed as BOTH ("MERIT OR FLAW"), so they carry kind
    # "either" and sit in neither count — 43/44 is how the chapter PRINTS them.
    either = [m for m in general if m.kind == "either"]
    assert {m.id for m in either} == {"mf.mutation", "mf.favor", "mf.eternal-vow"}
    assert len([m for m in general if m.kind == "merit"]) + len(either) == 43
    assert len([m for m in general if m.kind == "flaw"]) == 45
    assert {m.category for m in general} == {
        "Physical", "Mental", "Social", "Property", "Supernatural"}


def test_every_description_matches_the_source_text(rs):
    """Guards the failure that hid Dying for a month: a description silently truncated
    mid-sentence, with the next entry's tail glued on. Compares each authored
    description against its section of the pasted chapter by normalised length, which
    is what caught Amputee at 12% of its printed body.

    Skipped when the source is absent — `images/` is gitignored and does not travel
    with a clone, so this cannot be a hard dependency of the suite.
    """
    import re, unicodedata
    src = Path("images/Merits & Flaws/CH 1 - Merits and Flaws.md")
    if not src.exists():
        pytest.skip("source chapter not present (images/ is gitignored)")

    secs = {}
    for part in re.split(r"\n#{3,4} +", src.read_text())[1:]:
        head, _, body = part.partition("\n")
        name = re.sub(r"\s*\([^)]*\)\s*$", "", head).strip()   # cost may share the line
        secs[name.upper()] = body

    def norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", s).replace("’", "'").replace("—", " ")
        return re.sub(r"[^a-z0-9]", "", s.lower())

    by_name = {norm(k): v for k, v in secs.items()}
    short = []
    for m in rs.merits_flaws.values():
        if not m.id.startswith("mf."):
            continue
        body = by_name.get(norm(m.name))
        assert body is not None, f"{m.name} has no section in the source chapter"
        body = re.sub(r"^\s*\([^)]*\)\s*", "", body.strip(), flags=re.S)
        ratio = len(norm(m.description)) / max(1, len(norm(body)))
        if ratio < 0.92:
            short.append(f"{m.name} ({ratio:.0%} of source)")
    assert not short, "descriptions shorter than their source: " + ", ".join(short)


def test_no_description_carries_extraction_debris(rs):
    """The other half of the fidelity guard, and the one that was missing.

    The length test above only fails a description that is too SHORT, so it could not
    see either defect the 2026-07-31 click-through found — both make a description
    LONGER, and by so little that every ratio stayed within 1.5% of 1.0. Structure, not
    length, is what separates them from prose:

      * a multi-line printed cost note, whose second line the extractor left at the
        head of the description ("DRAGON KINGS OR GOD-BLOODED) The character excels
        at..."). Five entries;
      * the next section's markdown headers glued on the end ("... called Legacy of
        Hesiesh. ## FLAWS ### PHYSICAL"). One entry.

    Spotting two of these by eye is what found the other four — so this asserts the
    shape rather than an allowlist of the six then known.
    """
    import re
    for m in rs.merits_flaws.values():
        assert not re.search(r"#{2,}", m.description), (
            f"{m.id}: markdown header bled into the description")
        lead = re.match(r"^[A-Z0-9 ,\-\.]{4,}\)", m.description.lstrip())
        assert lead is None, (
            f"{m.id}: description opens with a cost-note fragment {lead.group(0)!r}")


def test_no_name_was_mangled_by_title_casing(rs):
    """The source headers are SHOUTED ("#### BRIGID'S HEIR"), and naive title-casing
    capitalises the letter after an apostrophe: "Brigid'S Heir". Two entries."""
    import re
    for m in rs.merits_flaws.values():
        assert not re.search(r"[A-Za-z]'S\b", m.name), f"{m.id}: mangled name {m.name!r}"


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
async def test_advantages_tab_offers_merit_gain_and_loss_in_play(user) -> None:
    """The post-lock M&F controls, which moved from the XP tab to Advantages on
    2026-07-31 along with their chargen counterpart."""
    await user.open('/mf-xp')
    await user.should_see("Merits & Flaws")
    await user.should_see("Gain")
    await user.should_see("Lose / buy off")
    # the preview renders before anything is selected, rather than being absent
    await user.should_see("Select an entry to see its rules text.")
    # Post-lock the budget on this tab is experience, not bonus points.
    await user.should_see("XP available")
    await user.should_see("The ledger and undo are on the XP tab.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_trait_surface_still_stands_without_the_merit_card(user) -> None:
    """Guards the shadowing bug that once took a WHOLE tab down: the M&F card's select
    was first named `sel`, which Python then treated as local throughout the enclosing
    function, leaving the raise-a-trait selectors unassigned. The card moved to
    Advantages and the XP tab has since been deleted entirely (decision 0013) — this
    pins that the surface those traits landed on is still standing."""
    await user.open('/xp')
    await user.should_see("Attributes")
    await user.should_see("Virtues")


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
    assert rows["Brigid's Heir"][4].startswith("(5-PT.")  # ...and the printed cost line


def test_an_unresolvable_row_explains_itself_in_the_tooltip(rs):
    c = _mortal(MP(merit_id="mf.not-a-merit"))
    row = view.merit_rows(rs, c)[0]
    assert row[0].startswith("⚠")
    assert "missing" in row[4]


# --- the trait-forfeit Flaws (PG pp.35-36) ---------------------------------- #
# Four Flaws pay bonus points for free chargen dots GIVEN UP rather than for a
# disadvantage suffered. The human's ruling (2026-07-30): this is a budget delta and
# nothing more — sell two Virtue dots and the Virtue budget is 3 instead of 5, after
# which every existing over-spend check does the real work unchanged.

CALLOUS = "mf.callous"
UNSKILLED = "mf.unskilled"
WEAK_WILLED = "mf.weak-willed"
DIMINISHED_ATTR = "mf.diminished-attributes"


def _solar(*purchases, **kw) -> Character:
    c = Character(id="c.s", exalt_type="Solar", caste="dawn", essence_rating=1,
                  merits_flaws=list(purchases))
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_callous_dots_come_from_the_point_value(rs):
    """dots = points // rate, so no new model field is needed. Callous is 2 BP/dot."""
    e = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=CALLOUS, tier="4")))
    assert e.forfeited_virtue_dots == 2


def test_callous_lowers_the_virtue_budget(rs):
    """The whole mechanism: 4 points of Callous drops the Virtue budget 5 -> 3."""
    plain = validate.effective_budgets(rs, _solar())
    callous = validate.effective_budgets(rs, _solar(MP(merit_id=CALLOUS, tier="4")))
    assert callous.virtue_dots == plain.virtue_dots - 2


def test_unskilled_lowers_the_ability_budget(rs):
    """Unskilled is 1 BP/dot, and it is a variable_cost entry, so points are on the
    purchase rather than on a tier."""
    b = validate.effective_budgets(rs, _solar(MP(merit_id=UNSKILLED, points=3)))
    assert b.ability_dots == validate.effective_budgets(rs, _solar()).ability_dots - 3


def test_a_character_holding_no_forfeit_flaw_gets_the_printed_budget(rs):
    """The printed budget must be returned UNCHANGED — same object, not a copy — when
    nothing forfeits, so the common path costs nothing."""
    c = _solar()
    assert validate.effective_budgets(rs, c) is rs.budgets_for("Solar", c.origin,
                                                               c.upbringing)


def test_forfeit_flaws_still_grant_their_bonus_points(rs):
    """The BP half was already working and must not regress: the forfeit fields are the
    OTHER half of the bargain, not a replacement for it."""
    e = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=CALLOUS, tier="4")))
    assert e.bonus_point_grant == 4


def test_callous_caps_willpower_just_above_the_virtues_it_sold(rs):
    """"...may not begin play with a Willpower rating more than one point higher than
    the sum of their two highest Virtues" (p.35)."""
    c = _solar(MP(merit_id=CALLOUS, tier="4"), nature="Survivor",
               virtues={V.COMPASSION: 1, V.CONVICTION: 1, V.TEMPERANCE: 1, V.VALOR: 1},
               willpower_purchased=4)
    assert _codes(validate.validate_chargen(rs, c), "callous-willpower-cap")


def test_callous_willpower_cap_allows_exactly_one_above(rs):
    c = _solar(MP(merit_id=CALLOUS, tier="4"), nature="Survivor",
               virtues={V.COMPASSION: 1, V.CONVICTION: 1, V.TEMPERANCE: 1, V.VALOR: 1},
               willpower_purchased=1)
    assert not _codes(validate.validate_chargen(rs, c), "callous-willpower-cap")


def test_callous_falls_away_at_nine_virtue_dots(rs):
    """"...at which point the character automatically loses this Flaw at no cost."""
    c = _solar(MP(merit_id=CALLOUS, tier="4"), nature="Paragon",
               virtues={V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 1})
    e = merits.merits_and_flaws_calc(rs, c)
    assert e.willpower_virtue_margin is None and not e.barred_natures


def test_callous_bars_the_paragon_nature(rs):
    c = _solar(MP(merit_id=CALLOUS, tier="4"), nature="Paragon",
               virtues={V.COMPASSION: 1, V.CONVICTION: 1, V.TEMPERANCE: 1, V.VALOR: 1})
    assert _codes(validate.validate_chargen(rs, c), "nature-barred-by-flaw")


def test_weak_willed_lowers_derived_willpower(rs):
    """Willpower is derived, not stored, so its forfeit is a subtraction in derive —
    and only when a RuleSet is passed, since without one no Flaw is knowable."""
    c = _solar(MP(merit_id=WEAK_WILLED, points=2),
               virtues={V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 1, V.VALOR: 1})
    assert derive.willpower(c) == 6
    assert derive.willpower(c, rs) == 4


def test_weak_willed_floors_an_exalt_at_four(rs):
    c = _solar(MP(merit_id=WEAK_WILLED, points=3), nature="Survivor",
               virtues={V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 1, V.VALOR: 1})
    assert _codes(validate.validate_chargen(rs, c), "willpower-below-flaw-floor")


def test_weak_willed_floors_a_mortal_at_two_not_four(rs):
    """"UnExalted and Callous Exalted characters may have a Willpower score as low as
    2" (p.36). The un-Exalted test is the absence of a native Essence pool, which is
    how this module already asks the question."""
    c = _mortal(MP(merit_id=WEAK_WILLED, points=3),
                virtues={V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 1, V.VALOR: 1})
    assert merits.merits_and_flaws_calc(rs, c).willpower_floor == 2


def test_callous_lowers_an_exalts_weak_willed_floor_to_two(rs):
    c = _solar(MP(merit_id=WEAK_WILLED, points=3), MP(merit_id=CALLOUS, tier="4"),
               virtues={V.COMPASSION: 1, V.CONVICTION: 1, V.TEMPERANCE: 1, V.VALOR: 1})
    assert merits.merits_and_flaws_calc(rs, c).willpower_floor == 2


def test_diminished_attributes_records_its_category(rs):
    """Three printed Flaws share one entry; the purchase names which via `detail`."""
    e = merits.merits_and_flaws_calc(
        rs, _solar(MP(merit_id=DIMINISHED_ATTR, points=6, detail="Mental")))
    assert e.forfeited_attribute_dots == {"Mental": 2}


def test_diminished_attributes_defaults_to_physical(rs):
    """The printed entry's own category, when the player recorded none."""
    e = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=DIMINISHED_ATTR, points=3)))
    assert e.forfeited_attribute_dots == {"Physical": 1}


def test_forfeit_flaws_are_not_reported_as_narrative_only(rs):
    """They have real effects now, so the UI must stop calling them decorative."""
    e = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=CALLOUS, tier="4")))
    assert CALLOUS not in e.narrative_only


def test_diminished_attributes_shrinks_the_pool_its_category_receives(rs):
    """The pools are matched to categories BY SPEND, so the forfeit is taken off the
    pool the category actually gets — not off a fixed slot. Physical here is the
    biggest spend, so it holds the 8-pool; forfeiting 2 dots leaves it 6."""
    attrs = {A.STRENGTH: 4, A.DEXTERITY: 4, A.STAMINA: 3,      # Physical spend 8
             A.CHARISMA: 3, A.MANIPULATION: 3, A.APPEARANCE: 2,  # Social spend 5
             A.PERCEPTION: 2, A.INTELLIGENCE: 2, A.WITS: 2}      # Mental spend 3
    c = _solar(MP(merit_id=DIMINISHED_ATTR, points=6, detail="Physical"),
               attributes=attrs)
    b = rs.budgets_for("Solar", c.origin, c.upbringing)
    assignment = validate.attribute_pool_assignment(rs, c, b, attrs)
    assert ("Physical", 8, 6) in assignment
    assert ("Social", 5, 6) in assignment          # untouched


def test_diminished_attributes_charges_bp_for_the_dots_it_took_away(rs):
    """The point of wiring it: an unchanged sheet that WAS legal becomes over-spent,
    because the budget it was spending against is smaller."""
    attrs = {A.STRENGTH: 4, A.DEXTERITY: 4, A.STAMINA: 3,
             A.CHARISMA: 3, A.MANIPULATION: 3, A.APPEARANCE: 2,
             A.PERCEPTION: 2, A.INTELLIGENCE: 2, A.WITS: 2}
    def attr_bp(c):
        line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                    if l.domain.lower().startswith("attribute"))
        return line.points
    assert attr_bp(_solar(attributes=attrs)) == 0
    assert attr_bp(_solar(MP(merit_id=DIMINISHED_ATTR, points=6, detail="Physical"),
                          attributes=attrs)) > 0


def test_the_editor_counts_against_the_forfeited_budget(rs):
    """The sheet must not contradict its own validation: a Callous or Unskilled
    character's panel headers have to show the budget the engine charges against, not
    the printed one. Pins the UI to `effective_budgets` rather than `budgets_for`."""
    src = (Path(exalted_builder.__file__).parent / "ui" / "editor.py").read_text()
    # the two budget reads that feed every dot-count header in the chargen editor
    assert src.count("validate.effective_budgets(ruleset, character)") == 2


# --- A2: health levels (PG p.20, p.32) -------------------------------------- #
# Large Size and Small are the first sources of a health level in this build that are
# not Charms — `derive.health_track` read Charms and Ox-Body purchases only.

LARGE_SIZE = "mf.large-size"
SMALL = "mf.small"


def _penalties(track):
    return [lv.penalty for lv in track if not lv.incapacitated]


def test_the_base_track_is_unchanged_without_merits(rs):
    assert _penalties(derive.health_track(_solar(), rs)) == [0, -1, -1, -2, -2, -4]


def test_large_size_four_points_grants_one_zero_level(rs):
    """"Such imposing bulk grants one additional -0 health level" (p.20)."""
    c = _solar(MP(merit_id=LARGE_SIZE, tier="4"))
    assert _penalties(derive.health_track(c, rs)) == [0, 0, -1, -1, -2, -2, -4]


def test_large_size_six_points_grants_a_zero_and_a_minus_one(rs):
    """"Such characters receive one -0 level and one -1 level" (p.20)."""
    c = _solar(MP(merit_id=LARGE_SIZE, tier="6"))
    assert _penalties(derive.health_track(c, rs)) == [0, 0, -1, -1, -1, -2, -2, -4]


def test_a_granted_level_names_the_merit_it_came_from(rs):
    """The sheet shows provenance for an Ox-Body level; a Merit level is no different."""
    track = derive.health_track(_solar(MP(merit_id=LARGE_SIZE, tier="4")), rs)
    assert [lv.source for lv in track if lv.source] == ["Large Size"]


def test_small_costs_one_minus_one_level(rs):
    """"Her reduced size also costs her one -1 health level" (p.32)."""
    c = _solar(MP(merit_id=SMALL))
    assert _penalties(derive.health_track(c, rs)) == [0, -1, -2, -2, -4]


def test_large_size_and_small_cancel_at_the_minus_one_tier(rs):
    """Both held: the six-point grant adds a -1 and Small removes one. The removal
    takes a BASE level first, so the granted one survives and is still attributed."""
    c = _solar(MP(merit_id=LARGE_SIZE, tier="6"), MP(merit_id=SMALL))
    track = derive.health_track(c, rs)
    assert _penalties(track) == [0, 0, -1, -1, -2, -2, -4]
    assert sorted(lv.source for lv in track if lv.source) == ["Large Size", "Large Size"]


def test_an_unrecorded_large_size_tier_grants_nothing_and_is_reported(rs):
    """Guessing which size was meant would silently hand out a health level. Granting
    nothing is only safe because it is also VISIBLE — `merit-bad-tier` already fires,
    so the two halves are pinned together here."""
    c = _solar(MP(merit_id=LARGE_SIZE))
    assert _penalties(derive.health_track(c, rs)) == [0, -1, -1, -2, -2, -4]
    assert _codes(validate.validate_chargen(rs, c), "merit-bad-tier")


def test_health_track_without_a_ruleset_ignores_merits(rs):
    """The optional-ruleset shape `soak` and `willpower` already use: no RuleSet means
    no way to know a Merit is held, so the caller gets the Charm-only track."""
    c = _solar(MP(merit_id=LARGE_SIZE, tier="6"))
    assert _penalties(derive.health_track(c)) == [0, -1, -1, -2, -2, -4]


def test_derive_bundles_the_merit_aware_track(rs):
    """derive() has a RuleSet in hand, so the sheet must get the full track."""
    c = _solar(MP(merit_id=LARGE_SIZE, tier="4"))
    assert _penalties(derive.derive(rs, c).health_levels) == [0, 0, -1, -1, -2, -2, -4]


def test_health_merits_are_not_reported_as_narrative_only(rs):
    e = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=LARGE_SIZE, tier="4"),
                                                MP(merit_id=SMALL)))
    assert LARGE_SIZE not in e.narrative_only and SMALL not in e.narrative_only


# --- A3: trait caps (PG pp.20, 22, 33, 41) ---------------------------------- #
# The first cluster to span the chargen/advancement boundary: Legendary Attribute is
# explicitly usable "during character creation or after it", so both the range checks
# in validate and the ceilings in advancement have to read the same field.

LEGENDARY_ATTR = "mf.legendary-attribute"
TRUE_PARAGON = "mf.true-paragon"
DISFIGURED = "mf.disfigured"
WEAK_ESSENCE = "mf.weak-essence"


def test_legendary_attribute_raises_one_named_attribute_to_six(rs):
    """"...a rating one dot higher than the normal limit imposed by their Essence
    allows ... for mortals and Exalted with Essence 1 to 5, this allows a rating of 6."""
    c = _solar(MP(merit_id=LEGENDARY_ATTR, detail="Strength"))
    assert merits.merits_and_flaws_calc(rs, c).attribute_caps == {"strength": 6}


def test_legendary_attribute_scales_with_essence_above_five(rs):
    """"Exalted with Essence 6 may raise the Attribute to 7, etc." The BASE cap stays
    5 for everyone else — this does not introduce an Essence-scaled cap build-wide."""
    c = _solar(MP(merit_id=LEGENDARY_ATTR, detail="Strength"), essence_rating=6)
    assert merits.merits_and_flaws_calc(rs, c).attribute_caps == {"strength": 7}


def test_the_raised_attribute_is_legal_at_chargen_and_others_are_not(rs):
    c = _solar(MP(merit_id=LEGENDARY_ATTR, detail="Strength"))
    c.attributes[A.STRENGTH] = 6
    assert not _codes(validate.validate_chargen(rs, c), "attribute-range")
    c.attributes[A.DEXTERITY] = 6
    assert _codes(validate.validate_chargen(rs, c), "attribute-range")


def test_an_unnamed_legendary_attribute_raises_nothing(rs):
    """Picking an Attribute for the player would hand out a dot they never chose."""
    assert merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=LEGENDARY_ATTR))
                                        ).attribute_caps == {}


def test_legendary_attribute_raises_the_xp_ceiling_too(rs):
    """"This may be done during character creation or after it" (p.20)."""
    c = _solar(MP(merit_id=LEGENDARY_ATTR, detail="Strength"))
    c.attributes[A.STRENGTH] = 5
    c.chargen_locked = True
    advancement.add_xp(c, 200)
    assert advancement.raise_attribute(rs, c, A.STRENGTH).to_rating == 6
    with pytest.raises(advancement.AdvancementError, match="already at 6"):
        advancement.raise_attribute(rs, c, A.STRENGTH)


def test_an_ordinary_attribute_still_stops_at_five(rs):
    c = _solar(MP(merit_id=LEGENDARY_ATTR, detail="Strength"))
    c.attributes[A.DEXTERITY] = 5
    c.chargen_locked = True
    advancement.add_xp(c, 200)
    with pytest.raises(advancement.AdvancementError, match="already at 5"):
        advancement.raise_attribute(rs, c, A.DEXTERITY)


def test_disfigured_lowers_the_appearance_cap(rs):
    """3-pt: "cannot ever have an Appearance rating greater than 1". 4-pt: Appearance 0
    "that cannot be improved with bonus or experience points" — a cap of 0 says both."""
    three = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=DISFIGURED, tier="3")))
    four = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=DISFIGURED, tier="4")))
    assert three.attribute_caps == {"appearance": 1}
    assert four.attribute_caps == {"appearance": 0}


def test_disfigured_appearance_is_reported_at_chargen(rs):
    c = _solar(MP(merit_id=DISFIGURED, tier="4"))
    c.attributes[A.APPEARANCE] = 1
    assert _codes(validate.validate_chargen(rs, c), "attribute-range")


def test_a_flaw_ceiling_beats_a_merit_ceiling_on_the_same_trait(rs):
    """Holding both, the LOWEST cap wins — a Merit must never undo a Flaw's ceiling by
    happening to be processed second."""
    c = _solar(MP(merit_id=LEGENDARY_ATTR, detail="Appearance"),
               MP(merit_id=DISFIGURED, tier="3"))
    assert merits.merits_and_flaws_calc(rs, c).attribute_caps == {"appearance": 1}


def test_true_paragon_raises_every_virtue_to_six(rs):
    c = _solar(MP(merit_id=TRUE_PARAGON), nature="Paragon")
    assert merits.merits_and_flaws_calc(rs, c).virtue_cap == 6
    c.virtues = {V.COMPASSION: 6, V.CONVICTION: 1, V.TEMPERANCE: 1, V.VALOR: 1}
    assert not _codes(validate.validate_chargen(rs, c), "virtue-range")


def test_true_paragon_raises_the_virtue_xp_ceiling(rs):
    c = _solar(MP(merit_id=TRUE_PARAGON), nature="Paragon")
    c.virtues = {V.COMPASSION: 5, V.CONVICTION: 1, V.TEMPERANCE: 1, V.VALOR: 1}
    c.chargen_locked = True
    advancement.add_xp(c, 200)
    assert advancement.raise_virtue(rs, c, V.COMPASSION).to_rating == 6
    with pytest.raises(advancement.AdvancementError, match="already at 6"):
        advancement.raise_virtue(rs, c, V.COMPASSION)


def test_a_virtue_still_stops_at_five_without_true_paragon(rs):
    c = _solar()
    c.virtues = {V.COMPASSION: 5, V.CONVICTION: 1, V.TEMPERANCE: 1, V.VALOR: 1}
    c.chargen_locked = True
    advancement.add_xp(c, 200)
    with pytest.raises(advancement.AdvancementError, match="already at 5"):
        advancement.raise_virtue(rs, c, V.COMPASSION)


def test_true_paragon_requires_the_paragon_nature(rs):
    """"Only characters with the Paragon Nature may purchase or retain this Merit."
    Reported by NAME, so no caller has to know the id."""
    c = _solar(MP(merit_id=TRUE_PARAGON), nature="Survivor")
    assert merits.merits_and_flaws_calc(rs, c).nature_requirement_unmet == ("True Paragon",)
    assert _codes(validate.validate_chargen(rs, c), "merit-nature-required")


def test_true_paragon_and_callous_are_mutually_exclusive_in_practice(rs):
    """Callous BARS the Paragon Nature and True Paragon REQUIRES it, so holding both
    always reports — whichever Nature is set."""
    c = _solar(MP(merit_id=TRUE_PARAGON), MP(merit_id=CALLOUS, tier="4"),
               nature="Paragon",
               virtues={V.COMPASSION: 1, V.CONVICTION: 1, V.TEMPERANCE: 1, V.VALOR: 1})
    assert _codes(validate.validate_chargen(rs, c), "nature-barred-by-flaw")
    c.nature = "Survivor"
    assert _codes(validate.validate_chargen(rs, c), "merit-nature-required")


def test_weak_essence_forces_a_starting_essence_of_one(rs):
    c = _solar(MP(merit_id=WEAK_ESSENCE), essence_rating=2)
    assert merits.merits_and_flaws_calc(rs, c).essence_start_override == 1
    assert _codes(validate.validate_chargen(rs, c), "essence-above-flaw-start")


def test_weak_essence_does_not_block_raising_essence_in_play(rs):
    """The Flaw is a CREATION ceiling — it exists so the character can raise Essence
    later ("typically until after the character can raise Essence in play")."""
    c = _solar(MP(merit_id=WEAK_ESSENCE), essence_rating=1)
    c.chargen_locked = True
    advancement.add_xp(c, 200)
    assert advancement.raise_essence(rs, c).to_rating == 2


def test_weak_willed_uses_the_forfeited_willpower_at_its_xp_ceiling(rs):
    """Regression from A1: raise_willpower measured against the UN-forfeited value, so
    a Weak-Willed character was capped as though they still had the dots they sold."""
    c = _solar(MP(merit_id=WEAK_WILLED, points=3),
               virtues={V.COMPASSION: 5, V.CONVICTION: 5, V.TEMPERANCE: 1, V.VALOR: 1})
    c.willpower_purchased = 0
    c.chargen_locked = True
    advancement.add_xp(c, 200)
    assert derive.willpower(c, rs) == 7          # 10 - 3 forfeited
    assert advancement.raise_willpower(rs, c).from_rating == 7


def test_a_flaw_ceiling_below_the_chargen_floor_reads_sensibly(rs):
    """Disfigured at four points forces Appearance 0, which is below the free dot every
    Attribute starts with — so the floor follows the ceiling down rather than reporting
    an impossible "must be 1-0" range."""
    c = _solar(MP(merit_id=DISFIGURED, tier="4"))
    c.attributes[A.APPEARANCE] = 0
    assert not _codes(validate.validate_chargen(rs, c), "attribute-range")
    c.attributes[A.APPEARANCE] = 1
    issue = _codes(validate.validate_chargen(rs, c), "attribute-range")[0]
    assert "exactly 0" in issue.message


# --- Weak Essence's withheld Charms (PG p.41) ------------------------------- #
# "the player may choose to withhold up to five Charms in reserve ... Withheld Charms
# waive their experience cost." Read as banked PICKS, not Charms named at creation
# (human, rules authority, 2026-07-30). NOTHING new is stored: what was withheld is the
# unspent remainder of the chargen Charm budget, and redemptions are counted off the
# append-only XP log.


def _locked_weak_essence(rs, picks: int) -> Character:
    """A Solar with Weak Essence who spent `picks` of their 10 chargen Charms."""
    c = _solar(MP(merit_id=WEAK_ESSENCE), essence_rating=1)
    # Ability dots so a Charm's prerequisites can actually be met — the point under
    # test is the credit economy, not Charm legality.
    c.abilities = {a: 5 for a in AbilityName if a != AbilityName.CRAFT}
    solar_charms = [cid for cid, ch in rs.charms.items()
                    if validate.charm_matches_splat(c, ch, rs)][:picks]
    c.charms = solar_charms
    # Lock through lifecycle so the ChargenSnapshot is written: credits are counted
    # against the FROZEN pick list, and a character locked without one would count
    # every Charm learned afterwards as a chargen pick and eat its own credits.
    lifecycle.lock_chargen(c)
    advancement.add_xp(c, 200)
    return c


def test_no_credits_without_the_flaw(rs):
    c = _solar()
    c.chargen_locked = True
    assert validate.withheld_charm_credits(rs, c) == (0, 0)


def test_withholding_five_of_ten_banks_five(rs):
    """The intended shape: pinned at Essence 1 you can only qualify for a handful, so
    you take those and bank the rest. Total across both phases is still 10 — the Flaw
    DEFERS picks, it does not add any."""
    assert validate.withheld_charm_credits(rs, _locked_weak_essence(rs, 5)) == (5, 5)


def test_spending_more_than_five_at_chargen_reduces_the_bank(rs):
    """The human's rule: "if more than five Charms are selected during chargen,
    subtract the number over from the total"."""
    assert validate.withheld_charm_credits(rs, _locked_weak_essence(rs, 7)) == (3, 3)
    assert validate.withheld_charm_credits(rs, _locked_weak_essence(rs, 10)) == (0, 0)


def test_the_bank_is_capped_at_five_however_few_were_taken(rs):
    """Spending none does not bank ten — the ceiling is the Flaw's own five."""
    assert validate.withheld_charm_credits(rs, _locked_weak_essence(rs, 0)) == (5, 5)


def test_redeeming_a_credit_costs_no_xp(rs):
    c = _locked_weak_essence(rs, 5)
    before = advancement.xp_spent(c)
    charm = next(cid for cid, ch in rs.charms.items()
                 if validate.charm_matches_splat(c, ch, rs)
                 and cid not in c.charms
                 and validate.meets_charm_requirements(rs, c, ch))
    entry = advancement.learn_charm(rs, c, charm)
    assert entry.cost == 0
    assert advancement.xp_spent(c) == before
    assert charm in c.charms
    assert validate.withheld_charm_credits(rs, c) == (5, 4)


def test_a_redeemed_charm_does_not_trip_the_xp_audit(rs):
    """THE trap: the audit re-prices every entry from the table, so a 0 filed under
    `charms` would be reported as a cost mismatch on every later validation."""
    c = _locked_weak_essence(rs, 5)
    charm = next(cid for cid, ch in rs.charms.items()
                 if validate.charm_matches_splat(c, ch, rs)
                 and cid not in c.charms
                 and validate.meets_charm_requirements(rs, c, ch))
    advancement.learn_charm(rs, c, charm)
    assert not _codes(advancement.validate_xp(rs, c), "xp-cost-mismatch")


def test_credits_run_out_and_the_next_charm_costs_xp(rs):
    c = _locked_weak_essence(rs, 10)             # nothing banked
    charm = next(cid for cid, ch in rs.charms.items()
                 if validate.charm_matches_splat(c, ch, rs)
                 and cid not in c.charms
                 and validate.meets_charm_requirements(rs, c, ch))
    assert advancement.learn_charm(rs, c, charm).cost > 0


def test_undoing_a_redemption_restores_the_credit(rs):
    c = _locked_weak_essence(rs, 5)
    charm = next(cid for cid, ch in rs.charms.items()
                 if validate.charm_matches_splat(c, ch, rs)
                 and cid not in c.charms
                 and validate.meets_charm_requirements(rs, c, ch))
    advancement.learn_charm(rs, c, charm)
    advancement.undo_last(rs, c)
    assert charm not in c.charms
    assert validate.withheld_charm_credits(rs, c) == (5, 5)


# --- A4: point-cost modifiers (PG pp.21, 30) -------------------------------- #

BRIGIDS_HEIR = "mf.brigid-s-heir"
PRODIGY = "mf.prodigy"


def _sorcerer(*purchases, **kw) -> Character:
    c = _solar(*purchases, **kw)
    c.abilities = {a: 5 for a in AbilityName if a != AbilityName.CRAFT}
    return c


def test_brigids_heir_doubles_ordinary_charms(rs):
    """"...doubles the bonus/experience cost ... of all Charms" (p.30)."""
    plain, heir = _sorcerer(), _sorcerer(MP(merit_id=BRIGIDS_HEIR))
    charm = next(ch for cid, ch in rs.charms.items()
                 if validate.charm_matches_splat(plain, ch, rs)
                 and not ch.grants_circle and "occult" not in ch.category)
    assert costs.charm_cost(rs, heir, charm) == costs.charm_cost(rs, plain, charm) * 2


def test_brigids_heir_halves_spells(rs):
    """"...but halves the corresponding costs ... for spells"."""
    plain, heir = _sorcerer(), _sorcerer(MP(merit_id=BRIGIDS_HEIR))
    spell = next(iter(rs.spells.values()))
    assert costs.spell_cost(rs, heir, spell) == costs.spell_cost(rs, plain, spell) // 2


def test_ox_body_is_exempt_from_the_doubling(rs):
    """"Ox-Body Technique is exempt from this doubling"."""
    plain, heir = _sorcerer(), _sorcerer(MP(merit_id=BRIGIDS_HEIR))
    ox = validate.ox_body_charm(rs, plain)
    assert ox is not None
    assert costs.charm_cost(rs, heir, ox) == costs.charm_cost(rs, plain, ox)


def test_the_terrestrial_sorcery_line_is_exempt(rs):
    """"...as is any Charm that includes Terrestrial Circle Sorcery as an ultimate
    prerequisite or leads directly to that Charm." Found through `grants_circle`, so it
    holds for every splat with sorcery without naming a Charm id."""
    plain, heir = _sorcerer(), _sorcerer(MP(merit_id=BRIGIDS_HEIR))
    tcs = next(ch for ch in rs.charms.values()
               if ch.grants_circle == SpellCircle.TERRESTRIAL
               and validate.charm_matches_splat(plain, ch, rs))
    # Terrestrial Circle Sorcery is a ROOT Charm in this data — no Charm is its
    # prerequisite — so the printed "leads directly to that Charm" clause has no
    # members here. Recorded rather than asserted, so that stays visible if a splat
    # ever gates it behind something.
    assert [p for group in tcs.prerequisites for p in group] == []
    downstream = [cid for cid, ch in rs.charms.items()
                  if any(tcs.id in group for group in ch.prerequisites)]
    assert downstream, "expected Charms downstream of Terrestrial Circle Sorcery"
    for cid in [tcs.id, *downstream]:
        charm = rs.charms[cid]
        assert costs.charm_cost(rs, heir, charm) == costs.charm_cost(rs, plain, charm), cid
    # Two dots downstream too: Solar Circle Sorcery reaches it only transitively.
    solar_circle = rs.charms.get("solar.occult.solar-circle-sorcery")
    assert costs.charm_cost(rs, heir, solar_circle) == costs.charm_cost(rs, plain, solar_circle)
    # ...but NECROMANCY is a separate line and is not exempt.
    necro = rs.charms["solar.occult.shadowlands-circle-necromancy"]
    assert costs.charm_cost(rs, heir, necro) == costs.charm_cost(rs, plain, necro) * 2


def test_brigids_heir_doubles_the_chargen_bonus_cost_too(rs):
    """"doubles the BONUS/experience cost" — both halves, not only XP."""
    charm = next(ch for cid, ch in rs.charms.items()
                 if validate.charm_matches_splat(_solar(), ch, rs)
                 and not ch.grants_circle and "occult" not in ch.category)
    plain, heir = _sorcerer(), _sorcerer(MP(merit_id=BRIGIDS_HEIR))
    plain.charms = heir.charms = [charm.id]
    a = validate.charm_pick_bp_costs(rs, plain, validate.chargen_charm_picks(rs, plain))
    b = validate.charm_pick_bp_costs(rs, heir, validate.chargen_charm_picks(rs, heir))
    assert b == [a[0] * 2]


def test_prodigy_grants_an_extra_favored_ability(rs):
    """"...gaining one additional Favored Ability for every time this Merit is
    purchased" (p.21). Feeds the count the existing favored-count check uses."""
    db = Character(id="c.db", exalt_type="Dragon-Blooded", caste="air",
                   merits_flaws=[MP(merit_id=PRODIGY, tier="favored", detail="Melee")])
    plain = Character(id="c.db2", exalt_type="Dragon-Blooded", caste="air")
    assert (validate.favored_ability_count(rs, db)
            == validate.favored_ability_count(rs, plain) + 1)


def test_prodigy_never_exceeds_five_favored_abilities(rs):
    """"Characters may not have more than five Favored Abilities in total"."""
    db = Character(id="c.db", exalt_type="Dragon-Blooded", caste="air",
                   merits_flaws=[MP(merit_id=PRODIGY, tier="favored",
                                    detail=a.value)
                                 for a in list(AbilityName)[:6]])
    assert validate.favored_ability_count(rs, db) == merits.PRODIGY_FAVORED_CAP


BARRED_FROM_FAVORED = {"Solar", "Abyssal", "Lunar", "Alchemical"}


def test_prodigy_is_barred_per_HALF_not_as_a_whole_entry(rs):
    """"...so Prodigy is not available to Solars, Abyssals or Lunars ... Alchemical
    Exalted may not take this Merit at all" (p.20) bars the half that GRANTS a Favored
    Ability. Its +2 "increased aptitude" half is explicitly "paid separately for
    characters who innately gain Favored Abilities as part of character creation" —
    which is exactly those four splats. Ruled 2026-07-31: the aptitude half escapes the
    bar, so the restriction is per-option, not per-entry."""
    d = rs.merits_flaws[PRODIGY]
    assert set(d.tier_barred_exalt_types["favored"]) == BARRED_FROM_FAVORED
    assert set(d.tier_barred_exalt_types["favored_aptitude"]) == BARRED_FROM_FAVORED
    assert "aptitude" not in d.tier_barred_exalt_types          # open to everyone
    assert not d.barred_exalt_types, "the ENTRY is no longer barred outright"

    assert validate.merit_tiers_available(d, "Solar") == ("aptitude",)
    assert set(validate.merit_tiers_available(d, "Dragon-Blooded")) == set(d.cost_options)


def test_a_barred_splat_is_flagged_on_the_favored_half_only(rs):
    grant = _solar(MP(merit_id=PRODIGY, tier="favored", detail="Melee"))
    assert _codes(validate.validate_chargen(rs, grant), "merit-barred-splat-tier")
    aptitude = _solar(MP(merit_id=PRODIGY, tier="aptitude", detail="Melee"))
    assert not _codes(validate.validate_chargen(rs, aptitude), "merit-barred-splat-tier")


def test_a_splat_that_may_take_either_half_is_not_flagged(rs):
    db = Character(id="c.db", exalt_type="Dragon-Blooded", caste="air",
                   merits_flaws=[MP(merit_id=PRODIGY, tier="favored", detail="Melee")])
    assert not _codes(validate.validate_chargen(rs, db), "merit-barred-splat-tier")


def test_an_entry_barred_at_every_option_is_barred_outright(rs):
    """The whole-entry answer is DERIVED from the per-option ones, so the two can never
    disagree. Prodigy keeps one open option for a Solar and so stays offered."""
    d = rs.merits_flaws[PRODIGY]
    assert validate.merit_available_to(d, "Solar", "dawn")
    everywhere = d.model_copy(update={"tier_barred_exalt_types":
                                      {t: ["Solar"] for t in d.cost_options}})
    assert not validate.merit_available_to(everywhere, "Solar", "dawn")


def test_cost_modifiers_are_not_reported_as_narrative_only(rs):
    e = merits.merits_and_flaws_calc(rs, _sorcerer(MP(merit_id=BRIGIDS_HEIR)))
    assert BRIGIDS_HEIR not in e.narrative_only


# --- A5: Essence-pool shape (PG pp.28, 41) ---------------------------------- #
#
# Two entries that change the POOLS rather than any term feeding them: Legendary
# Breeding raises the effective Breeding rating, Beacon of Power merges the two pools.

LEGENDARY_BREEDING = "mf.legendary-breeding"
BEACON = "mf.beacon-of-power"


def _db(*purchases, breeding: int = 5, **kw) -> Character:
    c = Character(id="c.db", exalt_type="Dragon-Blooded", caste="air", essence_rating=1,
                  merits_flaws=list(purchases))
    if breeding:
        c.backgrounds = [BackgroundEntry(name="Breeding", rating=breeding)]
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_legendary_breeding_grants_the_rating_six_pools(rs):
    """"her Breeding Background ... has a rating of 6. This superb ancestry adds 6
    motes to her Personal Essence pool and 11 motes to her Peripheral" (p.28) — the
    printed totals, which are the rating-6 row of the Breeding table."""
    plain_p, plain_pp = derive.essence_pools(rs, _db())
    p, pp = derive.essence_pools(rs, _db(MP(merit_id=LEGENDARY_BREEDING)))
    # Breeding 5 is already worth 5/9, so the Merit is worth one more step of each.
    assert (p - plain_p, pp - plain_pp) == (1, 2)
    # And the absolute bonus over no Breeding at all is the printed 6 and 11.
    none_p, none_pp = derive.essence_pools(rs, _db(breeding=0))
    assert (p - none_p, pp - none_pp) == (6, 11)


def test_legendary_breeding_overrides_a_lower_purchased_rating(rs):
    """The Merit states the rating outright, so it does not stack with what was
    bought. (Breeding 5 is a printed prerequisite this build cannot yet check — see
    the trait-prerequisites item in the triage doc.)"""
    e = merits.merits_and_flaws_calc(rs, _db(MP(merit_id=LEGENDARY_BREEDING), breeding=2))
    assert e.breeding_rating_override == merits.LEGENDARY_BREEDING_RATING
    assert (derive.essence_pools(rs, _db(MP(merit_id=LEGENDARY_BREEDING), breeding=2))
            == derive.essence_pools(rs, _db(MP(merit_id=LEGENDARY_BREEDING), breeding=5)))


def test_legendary_breeding_does_nothing_to_a_splat_without_breeding(rs):
    """Every other splat carries an empty Breeding table, so the override is inert
    rather than an error. (Validation flags the wrong splat separately.)"""
    solar = _solar(MP(merit_id=LEGENDARY_BREEDING))
    assert derive.essence_pools(rs, solar) == derive.essence_pools(rs, _solar())


def test_beacon_of_power_merges_the_pools(rs):
    """"...a single Essence pool equal to the sum of their Personal and Peripheral
    Essence, all of which is considered Peripheral" (p.41)."""
    plain_p, plain_pp = derive.essence_pools(rs, _solar())
    p, pp = derive.essence_pools(rs, _solar(MP(merit_id=BEACON)))
    assert (p, pp) == (0, plain_p + plain_pp)


def test_beacon_of_power_merges_after_every_other_pool_effect(rs):
    """The merge is arithmetic on the finished pools, so a Merit that feeds a term
    still contributes exactly what it did — here Legendary Breeding's 6 + 11."""
    a_p, a_pp = derive.essence_pools(rs, _db(MP(merit_id=LEGENDARY_BREEDING)))
    _, merged = derive.essence_pools(rs, _db(MP(merit_id=LEGENDARY_BREEDING),
                                             MP(merit_id=BEACON)))
    assert merged == a_p + a_pp


def test_a_merged_pool_is_reported_as_one_pool_not_as_personal_zero(rs):
    """"Personal 0" on a sheet reads as a character with no Essence at all, so the
    shape travels with the number."""
    d = derive.derive(rs, _solar(MP(merit_id=BEACON)))
    assert d.essence_single_pool
    assert not derive.derive(rs, _solar()).essence_single_pool
    sheet = view.build_sheet_view(rs, _solar(MP(merit_id=BEACON)))
    assert sheet.essence_pool_label().startswith("Single pool")
    assert "Personal" in view.build_sheet_view(rs, _solar()).essence_pool_label()


def test_the_play_tracker_follows_the_merged_pool(rs):
    """The in-play mote tracker reads the derivation, so it needs no change of its
    own — but a Personal track with zero boxes has to be what the rule produced."""
    pv = view.build_play_view(rs, _solar(MP(merit_id=BEACON)))
    plain = view.build_play_view(rs, _solar())
    assert pv.personal_max == 0
    assert pv.peripheral_max == plain.personal_max + plain.peripheral_max


def test_beacon_of_power_is_barred_from_the_concealment_castes(rs):
    """"Night and Day Caste Exalted may not take this Flaw" (p.41). A printed
    restriction is inert catalogue data, exactly like Prodigy's splat bars."""
    assert set(rs.merits_flaws[BEACON].barred_castes) == {"night", "day"}
    night = _solar(MP(merit_id=BEACON), caste="night")
    assert _codes(validate.validate_chargen(rs, night), "merit-barred-caste")
    assert not _codes(validate.validate_chargen(rs, _solar(MP(merit_id=BEACON))),
                      "merit-barred-caste")


def test_the_pool_shape_entries_are_not_reported_as_narrative_only(rs):
    e = merits.merits_and_flaws_calc(rs, _db(MP(merit_id=LEGENDARY_BREEDING),
                                             MP(merit_id=BEACON)))
    assert LEGENDARY_BREEDING not in e.narrative_only
    assert BEACON not in e.narrative_only


# --- A6: Background budget and rating restrictions (PG pp.22, 24, 37-38) ----- #
#
# Five entries, two mechanisms. Heir Apparent and Innocuous change what the character's
# Backgrounds may BE, so they are effects; Damaged Artifact, Known Anathema and Debt
# constrain how many points the entry itself may be worth against a Background rating,
# which is a purchase restriction and therefore inert catalogue data.

HEIR_APPARENT = "mf.heir-apparent"
INNOCUOUS = "mf.innocuous"
DAMAGED_ARTIFACT = "mf.damaged-artifact"
KNOWN_ANATHEMA = "mf.known-anathema"
DEBT = "mf.debt"


def _bg(**ratings) -> list[BackgroundEntry]:
    return [BackgroundEntry(name=n.replace("_", " ").title(), rating=r)
            for n, r in ratings.items()]


def test_heir_apparent_grants_two_background_dots_per_point(rs):
    """"Every point invested in this Merit grants two dots of Backgrounds" (p.24)."""
    e = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=HEIR_APPARENT, tier="3")))
    assert e.bonus_background_dots == 6


def test_heir_apparent_adds_a_dot_per_stipulation(rs):
    """"Add an extra dot ... for every major stipulation applied to the Inheritance"."""
    e = merits.merits_and_flaws_calc(
        rs, _solar(MP(merit_id=HEIR_APPARENT, tier="2", stipulations=3)))
    assert e.bonus_background_dots == 2 * 2 + 3


def test_heir_apparent_clamps_stipulations_at_the_printed_three(rs):
    """"up a maximum of three conditions". Clamped in engine.merits, not on the model,
    so an old save carrying a stray value still loads."""
    e = merits.merits_and_flaws_calc(
        rs, _solar(MP(merit_id=HEIR_APPARENT, tier="1", stipulations=9)))
    assert e.bonus_background_dots == 2 + 3


def test_heir_apparent_raises_the_background_budget(rs):
    """The mechanism: the grant is a budget delta, the mirror of a forfeit."""
    plain = validate.effective_budgets(rs, _solar())
    heir = validate.effective_budgets(rs, _solar(MP(merit_id=HEIR_APPARENT, tier="2")))
    assert heir.background_dots == plain.background_dots + 4


def test_heir_apparent_lets_a_background_pass_three_without_bonus_points(rs):
    """"Background dots obtained with this Merit ... may raise a Background above a
    rating of three" (p.24). The dot is NOT free — it comes out of the enlarged pool
    instead of out of bonus points."""
    without = _solar(backgrounds=_bg(resources=5))
    with_heir = _solar(MP(merit_id=HEIR_APPARENT, tier="1"),
                       backgrounds=_bg(resources=5))
    lines = {l.domain: l.points
             for l in validate.bonus_point_breakdown(rs, without).lines}
    heir_lines = {l.domain: l.points
                  for l in validate.bonus_point_breakdown(rs, with_heir).lines}
    assert lines.get("Backgrounds", 0) > heir_lines.get("Backgrounds", 0)


def test_the_waived_dots_still_consume_the_pool(rs):
    """The double-dip guard. Two above-cap dots waived means two pool dots spent, so
    the unspent-dot warning must fall by exactly two rather than staying put."""
    b = validate.effective_budgets(rs, _solar(MP(merit_id=HEIR_APPARENT, tier="1")))
    c = _solar(MP(merit_id=HEIR_APPARENT, tier="1"), backgrounds=_bg(resources=5))
    spent, owed = validate.background_pool_spend(rs, c, b, c.backgrounds)
    assert (spent, owed) == (5, [])


def test_the_waiver_never_covers_more_dots_than_the_merit_granted(rs):
    """One point of Heir Apparent waives two dots; a third above-cap dot still pays."""
    b = validate.effective_budgets(rs, _solar(MP(merit_id=HEIR_APPARENT, tier="1")))
    c = _solar(MP(merit_id=HEIR_APPARENT, tier="1"),
               backgrounds=_bg(resources=5, artifact=5))
    spent, owed = validate.background_pool_spend(rs, c, b, c.backgrounds)
    assert spent == 3 + 3 + 2 and len(owed) == 2


def test_no_merit_leaves_the_background_arithmetic_untouched(rs):
    """The neutral case: nothing held, nothing waived, every dot above three pays."""
    b = validate.effective_budgets(rs, _solar())
    c = _solar(backgrounds=_bg(resources=5))
    spent, owed = validate.background_pool_spend(rs, c, b, c.backgrounds)
    assert spent == 3 and len(owed) == 2


def test_innocuous_caps_the_socially_dependent_backgrounds(rs):
    """"may not have more than two dots each of Allies, Contacts, Mentor or any other
    socially dependent Backgrounds" (p.22). The FOUR-point version only — the two-point
    one is dice and is out of scope.

    The open-ended half is a RULING (human, 2026-07-31), read off each Background's own
    description: Backing, Connections, Retainers, Renown and Liege join the three the
    page names."""
    e = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=INNOCUOUS, tier="4")))
    assert e.background_caps == {"allies": 2, "contacts": 2, "mentor": 2,
                                 "backing": 2, "connections": 2, "retainers": 2,
                                 "liege": 2, "renown": 2}
    c = _solar(MP(merit_id=INNOCUOUS, tier="4"), backgrounds=_bg(allies=4))
    assert _codes(validate.merit_issues(rs, c), "background-above-merit-cap")
    backing = _solar(MP(merit_id=INNOCUOUS, tier="4"),
                     backgrounds=[BackgroundEntry(name="Backing", rating=3)])
    assert _codes(validate.merit_issues(rs, backing), "background-above-merit-cap")


def test_liege_cannot_dodge_the_cap_it_stands_in_for(rs):
    """Liege "stands in for both Mentor and Backing", both of which are capped — so
    without a row of its own an Abyssal simply escaped the restriction. The human called
    it the strongest case of the five when ruling on the open-ended clause."""
    c = _abyssal(MP(merit_id=INNOCUOUS, tier="4"),
                 backgrounds=[BackgroundEntry(name="Liege", rating=4)])
    assert _codes(validate.merit_issues(rs, c), "background-above-merit-cap")


def test_innocuous_two_point_version_restricts_nothing(rs):
    """Its whole printed effect at that tier is dice and difficulty."""
    e = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=INNOCUOUS, tier="2")))
    assert not e.background_caps and not e.barred_backgrounds


def test_innocuous_bars_the_backgrounds_that_need_to_be_known(rs):
    """"Veiled characters may not have Followers, Henchman, a Cult, any form of Command
    or other Backgrounds contingent on being widely known" (p.22).

    The open-ended half is a RULING (human, 2026-07-31): Reputation ("how widely your
    exploits are known") and Influence ("your pull and status in society") contradict the
    Merit outright and are barred. Renown was considered and CAPPED instead — standing
    within the Silver Pact is known to a faction, not to the world."""
    c = _solar(MP(merit_id=INNOCUOUS, tier="4"), backgrounds=_bg(cult=1))
    assert _codes(validate.merit_issues(rs, c), "background-barred-by-merit")
    for name in ("Reputation", "Influence"):
        ruled = _solar(MP(merit_id=INNOCUOUS, tier="4"),
                       backgrounds=[BackgroundEntry(name=name, rating=1)])
        assert _codes(validate.merit_issues(rs, ruled), "background-barred-by-merit"), name
    renown = _solar(MP(merit_id=INNOCUOUS, tier="4"),
                    backgrounds=[BackgroundEntry(name="Renown", rating=2)])
    assert not _codes(validate.merit_issues(rs, renown), "background-barred-by-merit")
    ok = _solar(MP(merit_id=INNOCUOUS, tier="4"), backgrounds=_bg(resources=3))
    assert not _codes(validate.merit_issues(rs, ok), "background-barred-by-merit")


def test_innocuous_is_barred_from_sidereals(rs):
    """"Sidereals may not purchase Innocuous in either version, as their innate Arcane
    Fate surpasses and supersedes the Merit's effects." Catalogue data, like Prodigy."""
    assert rs.merits_flaws[INNOCUOUS].barred_exalt_types == ["Sidereal"]


def test_known_anathema_may_not_exceed_the_influence_rating(rs):
    """"characters may not generally take more points of this Flaw than their rating
    in Influence" (p.37)."""
    c = _solar(MP(merit_id=KNOWN_ANATHEMA, tier="4"), backgrounds=_bg(influence=2))
    assert _codes(validate.merit_issues(rs, c), "merit-points-above-background")
    ok = _solar(MP(merit_id=KNOWN_ANATHEMA, tier="2"), backgrounds=_bg(influence=2))
    assert not _codes(validate.merit_issues(rs, ok), "merit-points-above-background")


def test_damaged_artifact_needs_one_more_dot_than_it_is_worth(rs):
    """"Characters must have at least one more dot of Artifact than the points obtained
    with this Flaw" (p.38) — the offset -1 that makes it the same shape as the others."""
    c = _solar(MP(merit_id=DAMAGED_ARTIFACT, tier="3"), backgrounds=_bg(artifact=3))
    assert _codes(validate.merit_issues(rs, c), "merit-points-above-background")
    ok = _solar(MP(merit_id=DAMAGED_ARTIFACT, tier="3"), backgrounds=_bg(artifact=4))
    assert not _codes(validate.merit_issues(rs, ok), "merit-points-above-background")


def test_two_artifacts_are_two_artifacts_not_one_big_one(rs):
    """Found in the browser, 2026-07-31. `background_rating` SUMS duplicate rows, which
    is right for a rating held once and wrong for a Background held per possession: two
    2-dot artifacts read as Artifact 4 and satisfied a 3-point Damaged Artifact. The
    printed rule measures "the rating of the artifact it modifies" (p.37), singular, so
    the point limit reads the highest single instance."""
    split = _solar(MP(merit_id=DAMAGED_ARTIFACT, tier="3"),
                   backgrounds=[BackgroundEntry(name="Artifact", rating=2),
                                BackgroundEntry(name="Artifact", rating=2)])
    assert _codes(validate.merit_issues(rs, split), "merit-points-above-background")
    one = _solar(MP(merit_id=DAMAGED_ARTIFACT, tier="3"),
                 backgrounds=[BackgroundEntry(name="Artifact", rating=4)])
    assert not _codes(validate.merit_issues(rs, one), "merit-points-above-background")
    assert validate.background_best(split.backgrounds, "Artifact") == 2
    assert validate.background_rating(split.backgrounds, "Artifact") == 4


def test_debt_must_exceed_resources(rs):
    """"It is possible for characters to have both Debt and Resources, provided the
    former exceeds the latter" (p.38) — a floor, not a ceiling."""
    c = _solar(MP(merit_id=DEBT, tier="2"), backgrounds=_bg(resources=3))
    assert _codes(validate.merit_issues(rs, c), "merit-points-below-background")
    ok = _solar(MP(merit_id=DEBT, tier="4"), backgrounds=_bg(resources=3))
    assert not _codes(validate.merit_issues(rs, ok), "merit-points-below-background")


def test_debt_alone_is_always_legal(rs):
    """No Resources at all means any Debt exceeds it; the rule needs no special case."""
    assert not _codes(validate.merit_issues(rs, _solar(MP(merit_id=DEBT, tier="1"))),
                      "merit-points-below-background")


def test_the_background_entries_are_not_reported_as_narrative_only(rs):
    e = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=HEIR_APPARENT, tier="2"),
                                                MP(merit_id=INNOCUOUS, tier="4")))
    assert HEIR_APPARENT not in e.narrative_only
    assert INNOCUOUS not in e.narrative_only


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_editor_offers_stipulations_and_shows_the_raised_budget(user) -> None:
    """A6's two visible halves. The Stipulations control exists only where the
    catalogue says the entry takes them, and the Backgrounds header reports the budget
    the engine actually charges against — 7 + (3 points x 2) + 2 stipulations = 15."""
    await user.open('/merits-backgrounds')
    await user.should_see("Stipulations")
    await user.should_see("Backgrounds (15 dots")


# --- Cluster 7: trait prerequisites (PG pp.17, 22, 25, 28, 121) -------------- #
#
# `MeritFlaw.prerequisites` held Merit ids only; every RATED prerequisite was unchecked
# printed prose. Six entries want one, across four trait namespaces.

HIDDEN_MANSE = "mf.hidden-manse"
CACHE = "mf.cache"
ALT_DIVINATION = "mf.alternative-divination"
TRAVEL_PERMIT = "thaum.celestial-travel-permit"


def test_trait_rating_resolves_every_namespace(rs):
    """The whole reason the requirement names a trait rather than an id: the six
    entries span Attributes, Abilities, Virtues and Backgrounds."""
    c = _solar(backgrounds=_bg(manse=3))
    c.attributes[A.APPEARANCE] = 4
    c.abilities[AbilityName.OCCULT] = 2
    c.virtues[V.VALOR] = 5
    assert validate.trait_rating(c, "Appearance") == 4
    assert validate.trait_rating(c, "occult") == 2
    assert validate.trait_rating(c, "Valor") == 5
    assert validate.trait_rating(c, "Manse") == 3


def test_an_unresolvable_trait_name_reads_as_zero(rs):
    """Graceful, like every other unresolvable reference in the build — never a crash."""
    assert validate.trait_rating(_solar(), "Nonexistent Trait") == 0


def test_legendary_breeding_requires_breeding_five(rs):
    """"Characters must already have Breeding 5 to purchase this Merit" (p.28) — the
    gap A5 left open explicitly."""
    low = _db(MP(merit_id=LEGENDARY_BREEDING), breeding=2)
    assert _codes(validate.merit_issues(rs, low), "merit-trait-prerequisite")
    assert not _codes(validate.merit_issues(rs, _db(MP(merit_id=LEGENDARY_BREEDING))),
                      "merit-trait-prerequisite")


def test_legendary_breeding_does_not_satisfy_its_own_prerequisite(rs):
    """It grants an EFFECTIVE Breeding of 6, which must not feed back into the check
    that gates buying it — the prerequisite reads the PURCHASED rating."""
    c = _db(MP(merit_id=LEGENDARY_BREEDING), breeding=2)
    assert merits.merits_and_flaws_calc(rs, c).breeding_rating_override == 6
    assert _codes(validate.merit_issues(rs, c), "merit-trait-prerequisite")


def test_cache_accepts_either_side_of_its_or(rs):
    """"Resources 4+ or Salary 2+" (p.25) — one OR group, the AND-of-OR shape Charm
    prerequisites already use."""
    assert not _codes(validate.merit_issues(
        rs, _solar(MP(merit_id=CACHE), backgrounds=_bg(resources=4))),
        "merit-trait-prerequisite")
    assert not _codes(validate.merit_issues(
        rs, _solar(MP(merit_id=CACHE), backgrounds=_bg(salary=2))),
        "merit-trait-prerequisite")
    assert _codes(validate.merit_issues(
        rs, _solar(MP(merit_id=CACHE), backgrounds=_bg(resources=3, salary=1))),
        "merit-trait-prerequisite")


def test_hidden_manse_needs_the_manse_background(rs):
    """"Characters must have the Manse Background to purchase this Merit" — no rating
    named, so any rating at all satisfies it."""
    assert _codes(validate.merit_issues(rs, _solar(MP(merit_id=HIDDEN_MANSE, tier="1"))),
                  "merit-trait-prerequisite")
    ok = _solar(MP(merit_id=HIDDEN_MANSE, tier="1"), backgrounds=_bg(manse=1))
    assert not _codes(validate.merit_issues(rs, ok), "merit-trait-prerequisite")


def test_innocuous_appearance_gate_applies_to_the_two_point_version_only(rs):
    """"Characters must have Appearance 2 in order to purchase this version" (p.22).
    The four-point version carries no such line — which is why the requirement is keyed
    by TIER rather than sitting on the entry."""
    low = _solar(MP(merit_id=INNOCUOUS, tier="2"))
    low.attributes[A.APPEARANCE] = 1
    assert _codes(validate.merit_issues(rs, low), "merit-trait-prerequisite")

    veiled = _solar(MP(merit_id=INNOCUOUS, tier="4"))
    veiled.attributes[A.APPEARANCE] = 1
    assert not _codes(validate.merit_issues(rs, veiled), "merit-trait-prerequisite")


def test_alternative_divination_is_capped_by_occult(rs):
    """"characters may not purchase this Merit more times than their Occult rating"
    (p.17). A REPEAT limit, not a rating floor, so it is its own field."""
    c = _solar(*[MP(merit_id=ALT_DIVINATION)] * 3)
    c.abilities[AbilityName.OCCULT] = 2
    assert _codes(validate.merit_issues(rs, c), "merit-repeats-above-trait")
    c.abilities[AbilityName.OCCULT] = 3
    assert not _codes(validate.merit_issues(rs, c), "merit-repeats-above-trait")


def test_the_travel_permit_prose_prerequisite_is_now_checked(rs):
    """Its printed "Celestial Patron of at least 2" was `prerequisite_note` — shown to
    the player and machine-checked by nothing. Both now."""
    assert rs.merits_flaws[TRAVEL_PERMIT].prerequisite_note
    c = _mortal(MP(merit_id=TRAVEL_PERMIT), backgrounds=_bg(celestial_patron=1))
    assert _codes(validate.merit_issues(rs, c), "merit-trait-prerequisite")
    ok = _mortal(MP(merit_id=TRAVEL_PERMIT), backgrounds=_bg(celestial_patron=2))
    assert not _codes(validate.merit_issues(rs, ok), "merit-trait-prerequisite")


def test_large_size_is_not_given_a_prerequisite(rs):
    """"MOST characters with this Merit have both Strength and Stamina rated at 3 or
    higher" (p.20) is descriptive, not a requirement — the triage said so and the data
    must not quietly promote it into one."""
    assert not rs.merits_flaws[LARGE_SIZE].trait_prerequisites
    weak = _solar(MP(merit_id=LARGE_SIZE, tier="4"))
    assert not _codes(validate.merit_issues(rs, weak), "merit-trait-prerequisite")


def test_entries_without_a_trait_prerequisite_are_never_flagged(rs):
    """The neutral case, across the whole catalogue: a character holding one of each
    entry that requires no rated trait raises no prerequisite issue."""
    for definition in rs.merits_flaws.values():
        if definition.trait_prerequisites:
            continue
        c = _solar(MP(merit_id=definition.id))
        assert not _codes(validate.merit_issues(rs, c), "merit-trait-prerequisite"), \
            definition.id


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_editor_shows_a_trait_prerequisite_in_the_row(user) -> None:
    """A gate the player cannot see until they have already failed it is a bad gate.
    Cache is "Resources 4+ or Salary 2+", rendered from the data rather than the prose."""
    await user.open('/merits-backgrounds')
    await user.should_see("Requires: Resources 4 or Salary 2")


# --- A7: play-state pools and tracks (PG pp.27, 39, 40, 41) ----------------- #
#
# Four entries whose whole effect is a counter the Storyteller manages. Decision 0006
# governs all of it: displayed and tracked, NEVER read by chargen validation or the XP
# audit. Spending any of it is a reroll, which is decision 0009 and stays out.

LUCKY = "mf.lucky"
UNLUCKY = "mf.unlucky"
GREATER_CURSE = "mf.greater-curse"
DEATH_TAINT = "mf.death-taint"


def _abyssal(*purchases, **kw) -> Character:
    c = Character(id="c.ab", exalt_type="Abyssal", caste="dusk", essence_rating=2,
                  merits_flaws=list(purchases))
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _sidereal(*purchases, **kw) -> Character:
    c = Character(id="c.sid", exalt_type="Sidereal", caste="journeys", essence_rating=2,
                  merits_flaws=list(purchases))
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_abyssals_call_their_limit_track_resonance(rs):
    """The rename A7 was blocked on. A pure label, exactly as the Sidereal's "Paradox"
    is — same 0-10 mechanic, no second code path."""
    assert derive.limit_label(rs, _abyssal()) == "Resonance"
    assert derive.limit_label(rs, _solar()) == "Limit"
    assert derive.limit_label(rs, _sidereal()) == "Paradox"


def test_lucky_grants_a_pool_equal_to_the_points(rs):
    """"Lucky characters receive a luck pool equal to the number of points invested"."""
    assert derive.luck_pools(rs, _solar(MP(merit_id=LUCKY, tier="3"))) == (3, 0)


def test_sidereals_get_two_more_luck_within_a_three_to_five_band(rs):
    """"Sidereal characters receive two more luck points than the number of points
    invested … may not have a luck pool greater than five … nor smaller than three"."""
    assert derive.luck_pools(rs, _sidereal(MP(merit_id=LUCKY, tier="1")))[0] == 3
    assert derive.luck_pools(rs, _sidereal(MP(merit_id=LUCKY, tier="2")))[0] == 4
    assert derive.luck_pools(rs, _sidereal(MP(merit_id=LUCKY, tier="3")))[0] == 5


def test_the_sidereal_price_is_capped_at_three_points(rs):
    """"Sidereals with this Merit pay a maximum of three points for a luck pool of
    five" — catalogue data, a per-splat cost override."""
    assert set(rs.merits_flaws[LUCKY].cost_options_by_exalt_type["Sidereal"]) == {
        "1", "2", "3"}


def test_a_sidereal_is_never_offered_the_options_it_cannot_price(rs):
    """Found in the browser, 2026-07-31. The tier dropdown filtered on
    `tier_barred_exalt_types` but built its menu from the generic `cost_options`, so a
    Sidereal was offered Lucky at 4 and 5 — options `merit_points` prices at 0. The
    per-splat MENU and the per-splat FILTER are now the same resolution order."""
    d = rs.merits_flaws[LUCKY]
    assert validate.merit_tiers_available(d, "Sidereal") == ("1", "2", "3")
    assert validate.merit_tiers_available(d, "Solar") == ("1", "2", "3", "4", "5")
    assert set(validate.merit_cost_options(d, "Sidereal")) == {"1", "2", "3"}
    # and a save that already records one is flagged rather than silently worth nothing
    c = _sidereal(MP(merit_id=LUCKY, tier="5"))
    assert _codes(validate.merit_issues(rs, c), "merit-bad-tier")
    assert validate.merit_points(d, MP(merit_id=LUCKY, tier="5"), "Sidereal") == 0


def test_every_menu_offered_is_a_menu_that_prices(rs):
    """The general form of the Lucky bug, across the whole catalogue and every splat:
    no dropdown may offer an option worth 0 points."""
    for d in rs.merits_flaws.values():
        if not d.cost_options or d.variable_cost or d.cost_by_kind:
            continue
        for splat in ("Solar", "Abyssal", "Dragon-Blooded", "Lunar", "Sidereal",
                      "Alchemical", "Mortal"):
            for tier in validate.merit_tiers_available(d, splat):
                got = validate.merit_points(d, MP(merit_id=d.id, tier=tier), splat)
                assert got > 0, f"{d.id} offers {tier!r} to {splat} at {got} points"


def test_a_character_may_be_both_lucky_and_unlucky(rs):
    """"Strangely enough, characters may be simultaneously Lucky and Unlucky" (p.39).
    The two do not cancel — the player and the ST spend them independently."""
    c = _solar(MP(merit_id=LUCKY, tier="2"), MP(merit_id=UNLUCKY, tier="4"))
    assert derive.luck_pools(rs, c) == (2, 4)


def test_greater_curse_lowers_the_limit_maximum(rs):
    """"a character with three points of this Flaw suffers Limit Break when his Limit
    reaches seven dots" (p.40) — the page's own worked example."""
    assert derive.limit_max(rs, _solar(MP(merit_id=GREATER_CURSE, tier="3"))) == 7
    assert derive.limit_max(rs, _solar()) == merits.LIMIT_MAX


def test_greater_curse_reduction_stops_at_five(rs):
    """"to a maximum reduction of five dots"."""
    assert derive.limit_max(rs, _solar(MP(merit_id=GREATER_CURSE, tier="5"))) == 5


def test_greater_curse_reduces_a_sidereals_paradox_the_same_way(rs):
    """"This reduces a character's maximum Paradox pool in the same manner as Limit" —
    the label differs, the track does not."""
    assert derive.limit_max(rs, _sidereal(MP(merit_id=GREATER_CURSE, tier="2"))) == 8


def test_death_taint_starting_resonance_comes_from_the_price(rs):
    """"This deepened taint provides four bonus points … Characters who actually start
    with this greater taint add one additional bonus point per dot" (p.41), so the
    starting rating is `points - 4` — the A1 trick, no new field."""
    clean = _abyssal(MP(merit_id=DEATH_TAINT, points=4))
    assert merits.merits_and_flaws_calc(rs, clean).permanent_limit_start == 0
    tainted = _abyssal(MP(merit_id=DEATH_TAINT, points=6))
    assert merits.merits_and_flaws_calc(rs, tainted).permanent_limit_start == 2


def test_holding_death_taint_is_not_the_same_as_not_holding_it(rs):
    """None vs 0: a character may hold the Flaw and start clean, which is what its base
    four-point value buys. The sheet must be able to tell those apart."""
    assert merits.merits_and_flaws_calc(rs, _abyssal()).permanent_limit_start is None
    assert merits.merits_and_flaws_calc(
        rs, _abyssal(MP(merit_id=DEATH_TAINT, points=4))).permanent_limit_start == 0


def test_permanent_resonance_is_capped_at_essence(rs):
    """"Characters may not have a permanent Resonance higher than their Essence"."""
    c = _abyssal(MP(merit_id=DEATH_TAINT, points=4), essence_rating=3)
    assert derive.permanent_limit_cap(rs, c) == 3
    assert derive.permanent_limit_cap(rs, _abyssal()) == 0


def test_the_play_pools_never_reach_chargen_or_the_xp_audit(rs):
    """Decision 0006. All four are play-state; none may produce a chargen issue or move
    a bonus-point total beyond the ordinary Flaw grant every Flaw gets."""
    plain = _solar()
    played = _solar(MP(merit_id=LUCKY, tier="2"), MP(merit_id=UNLUCKY, tier="2"),
                    MP(merit_id=GREATER_CURSE, tier="2"))
    codes = {i.code for i in validate.validate_chargen(rs, played)}
    assert not codes & {"merit-trait-prerequisite", "merit-unknown"}
    # The only chargen-visible difference is the bonus points the Flaws grant, which is
    # the ordinary Flaw rule and not an A7 effect.
    assert (validate.bonus_point_breakdown(rs, played).available
            > validate.bonus_point_breakdown(rs, plain).available)


def test_the_play_entries_are_not_reported_as_narrative_only(rs):
    e = merits.merits_and_flaws_calc(rs, _abyssal(
        MP(merit_id=LUCKY, tier="1"), MP(merit_id=UNLUCKY, tier="1"),
        MP(merit_id=GREATER_CURSE, tier="1"), MP(merit_id=DEATH_TAINT, points=4)))
    for mid in (LUCKY, UNLUCKY, GREATER_CURSE, DEATH_TAINT):
        assert mid not in e.narrative_only


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_play_tracker_shows_the_shortened_renamed_resonance_track(user) -> None:
    """A7's whole visible surface on one character: the Abyssal rename, Greater Curse
    shortening the track, Death's Taint's permanent counter capped at Essence 3, and
    both luck pools.

    The maximum takes BOTH reductions (ruled 2026-07-31): 3 points of Greater Curse and
    2 of permanent Resonance, which occupies the track rather than riding alongside it.
    """
    await user.open('/merits-play')
    await user.should_see("Resonance")
    await user.should_see("0 / 5")                    # 10 − 3 Greater Curse − 2 permanent
    await user.should_see("Permanent Resonance: 2 / 3")
    await user.should_see("2 permanent, 3 by a Flaw")
    await user.should_see("Luck pool: 2")
    await user.should_see("Bad luck pool (Storyteller): 1")
    # Read-only: permanent Resonance is a permanent trait and moves on the XP ledger.
    await user.should_see("gain or shed it on the XP tab")


def test_permanent_resonance_occupies_the_track_rather_than_riding_alongside(rs):
    """Ruled 2026-07-31 by the human, rules authority. "Permanent Resonance is
    cumulative with temporary Resonance" (p.41) reads as HEADROOM: 2 permanent means the
    temporary track tops out at 8 and the Break arrives two points sooner — the same
    shape a permanent Limit would take on a Solar. It had been implemented as a separate
    rating beside a full 10-point track."""
    c = _abyssal(MP(merit_id=DEATH_TAINT, points=6), essence_rating=3)
    assert derive.limit_max(rs, c) == 10
    c.limit_permanent = 2
    assert derive.limit_max(rs, c) == 8


def test_the_two_reductions_stack_and_floor_at_zero(rs):
    """Greater Curse shortens the track and permanent Resonance occupies what is left.
    A character with both has very little room, and never a negative maximum."""
    c = _abyssal(MP(merit_id=DEATH_TAINT, points=9), MP(merit_id=GREATER_CURSE, tier="5"),
                 essence_rating=5)
    c.limit_permanent = 5
    assert derive.limit_max(rs, c) == 0


def test_deaths_taint_seeds_its_starting_resonance_at_lock(rs):
    """Found in the browser, 2026-07-31. `permanent_limit_start` was DERIVED and read by
    nothing — the price above the base four points bought a starting permanent Resonance
    that never reached the character, who always began play at 0. Lock is where a chargen
    value becomes the character's own, so it is seeded there."""
    c = _abyssal(MP(merit_id=DEATH_TAINT, points=6), essence_rating=3)
    assert c.limit_permanent == 0
    lifecycle.lock_chargen(c, rs)
    assert c.limit_permanent == 2
    assert derive.limit_max(rs, c) == 8


def test_the_base_four_point_version_starts_at_nothing(rs):
    """"The base value of this Flaw assumes the character does not begin play with any
    permanent Resonance" (p.41)."""
    c = _abyssal(MP(merit_id=DEATH_TAINT, points=4), essence_rating=3)
    lifecycle.lock_chargen(c, rs)
    assert c.limit_permanent == 0


def test_locking_without_a_ruleset_cannot_see_the_flaw(rs):
    """The optional-`ruleset` shape again: without one there is no way to know a Flaw is
    held, so the seed silently does not happen. Documented, and the UI always passes it."""
    c = _abyssal(MP(merit_id=DEATH_TAINT, points=6), essence_rating=3)
    lifecycle.lock_chargen(c)
    assert c.limit_permanent == 0


def test_a_re_lock_never_undoes_a_harrowing(rs):
    """Re-locking re-snapshots, and it must not re-inflict a dot the character spent five
    experience points shedding — nor undo one the Curse inflicted in play."""
    c = _abyssal(MP(merit_id=DEATH_TAINT, points=6), essence_rating=3)
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 10)
    advancement.shed_permanent_resonance(rs, c, "a Harrowing in the Labyrinth")
    assert c.limit_permanent == 1
    lifecycle.unlock_chargen(c)
    lifecycle.lock_chargen(c, rs)
    assert c.limit_permanent == 1, "the ledger owns the track once it has moved it"


# --- the Advantages tab (2026-07-31) ---------------------------------------- #
#
# Backgrounds and M&F moved off the Edit⇄XP split onto one both-sides tab. The value of
# the move is DELETION — two implementations of each became one — so the tests that
# matter are the ones that fail if a second one ever grows back.

def test_backgrounds_and_merits_have_exactly_one_implementation():
    """The editor must not grow its panels back. This is the whole point of the
    refactor: the splat-filter bug, the `drop_merit` kind bug and the `cost_by_kind`
    pricing bug were all one module knowing something the other did not. (The XP tab
    was the other offender and no longer exists — decision 0013.)"""
    import inspect
    from exalted_builder.ui import advantages, editor
    adv = inspect.getsource(advantages)
    for module in (editor,):
        src = inspect.getsource(module)
        assert "merits_flaws" not in src, (
            f"{module.__name__} touches Merits & Flaws; they live in ui/advantages.py")
        assert "backgrounds_for" not in src, (
            f"{module.__name__} has a Background panel; they live in ui/advantages.py")
    assert "backgrounds_for" in adv and "merits_flaws" in adv


def test_advantages_is_a_both_sides_tab_not_half_of_the_edit_xp_pair():
    """The crux of the plumbing. Advantages behaves like Charms/Combos — on the bar
    throughout, switching mode at the lock — and NOT like Edit/XP, which are one slot
    seen from two sides. Putting it in the wrong branch rebuilds the split being
    removed."""
    from exalted_builder.ui import builder
    assert "Advantages" in builder.visible_tabs(locked=False)
    assert "Advantages" in builder.visible_tabs(locked=True)
    # and it never needs mapping to a counterpart, because it never hides
    assert builder.resolve_tab("Advantages", locked=True) == "Advantages"
    assert builder.resolve_tab("Advantages", locked=False) == "Advantages"
    # the pair it is NOT part of still behaves as before
    # Edit is now a both-sides tab too (decision 0013) — Advantages was the first of
    # the pair to stop being half of the Edit/XP split, and the traits followed.
    assert builder.resolve_tab("Edit", locked=True) == "Edit"
    assert builder.resolve_tab("XP", locked=False) == "Edit"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_shared_bonus_point_total_is_visible_on_the_advantages_tab(user) -> None:
    """Ruling 1 of the plan, and its stated acceptance: Backgrounds and M&F draw on the
    SHARED chargen bonus-point pool, so spending here must move a number shown HERE.
    Without it a player spends 6 BP on Merits and the total that changed is on a tab
    they cannot see."""
    await user.open('/advantages-bp')
    await user.should_see("Bonus Points")
    await user.should_see("Merits & Flaws")     # the Merit that spent them
    await user.should_see("−3 BP")              # Legendary Attribute, 3 pts for a Solar
    await user.should_see("3 / 15 spent")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_two_tabs_agree_about_the_bonus_points(user) -> None:
    """The other half of the acceptance: "switch to Edit and it agrees". Both readouts
    are driven from `validate.bonus_point_breakdown`, so the same character must produce
    the same spent/available line on either tab."""
    def _bp_lines(u):
        # The bonus-point line specifically. The Edit tab carries other "... spent"
        # tallies (ability dots, the per-category Attribute pools) that have no
        # counterpart here, so the sets are not expected to be equal.
        return {e.text for e in u.client.elements.values()
                if getattr(e, "text", "").endswith("bonus points spent")
                or getattr(e, "text", "").endswith("/ 15 spent")}

    await user.open('/advantages-bp')
    adv = _bp_lines(user)
    await user.open('/advantages-bp-edit')
    edit = _bp_lines(user)
    assert adv, "the Advantages tab shows no bonus-point total"
    assert adv <= edit, (adv, edit)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_an_off_list_structured_detail_does_not_blank_the_tab(user) -> None:
    """Found by preflight, 2026-07-31. `ui.select` raises at BUILD time when its value
    is not among its options, and the raise takes every sibling with it — the crash
    class that blanked two picker tabs. A stored detail can legitimately be off-list:
    validate compares `detail.strip().title()`, so "strength" passes validation and
    never matches the title-cased option. The row keeps it as its own option instead."""
    await user.open('/advantages-odd-detail')
    await user.should_see("Merits & Flaws")          # the tab built at all
    await user.should_see("Applies to")              # the select that would have raised
    await user.should_see("not a choice")            # the unmatched value, kept visible


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_advantages_tab_builds_for_a_casteless_splat(user) -> None:
    """Mortals have no caste, and every caste-keyed lookup on this tab is handed
    `character.caste == ""` — `merit_cost_options`, `merit_tiers_available` and
    `merit_available_to` all take one. The casteless shape has broken UI before."""
    await user.open('/advantages-mortal')
    await user.should_see("Backgrounds")
    await user.should_see("Merits & Flaws")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
@pytest.mark.parametrize("route", ['/advantages-unknown', '/advantages-unknown-xp'])
async def test_an_off_catalogue_id_does_not_take_the_tab_down(user, route) -> None:
    """What opening a save without its homebrew looks like: a Merit id and a Background
    name the catalogue has never heard of, plus a tier that belongs to neither. Both
    regimes must render it rather than raising — the graceful-unresolvable-reference
    rule, and the same select-value crash class as the off-list detail."""
    await user.open(route)
    await user.should_see("Backgrounds")
    await user.should_see("Merits & Flaws")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_advantages_tab_switches_regime_at_the_lock(user) -> None:
    """One component, two budget regimes, chosen from the character rather than the
    caller. Unlocked it reports bonus points; locked it reports experience."""
    await user.open('/merits-backgrounds')                 # unlocked
    await user.should_see("Bonus Points")
    await user.should_see("pre-bonus")                     # the chargen Background cap
    await user.open('/mf-xp')                              # locked
    await user.should_see("XP available")
    await user.should_see("free — no XP")                  # Backgrounds are story-driven


# --- Permanent Resonance on the XP ledger ----------------------------------- #
#
# Corrected 2026-07-30: this was first written onto PlayState alongside the temporary
# track, which was wrong. Decision 0006's own last bullet routes permanent trait
# movement to the XP ledger — "permanent trait *reductions* (curses) are a different
# thing and live on the XP ledger, not here". Only the TEMPORARY half is play-state.

def _locked_abyssal(*purchases, xp=0, essence=3, permanent=0) -> Character:
    c = _abyssal(*purchases, essence_rating=essence)
    c.limit_permanent = permanent
    c.chargen_locked = True
    advancement.add_xp(c, xp)
    return c


# --- two-sided entries: making the choice, not just flagging it -------------- #
# "Merit OR Flaw" entries (Mutation, Favor, Eternal Vow) carry `taken_as` on the
# PURCHASE. Validation has always flagged an unrecorded side (`merit-side-unchosen`);
# until 2026-07-31 nothing could actually SET it, and the XP path rejected every
# two-sided entry outright because `buy_merit` demanded `kind == "merit"`.

VOW = "mf.eternal-vow"


def _locked_solar(*purchases, xp=50) -> Character:
    c = _solar(*purchases)
    c.chargen_locked = True
    advancement.add_xp(c, xp)
    return c


def test_permanent_resonance_is_a_character_trait_not_play_state(rs):
    """The correction itself: the field is on Character, and PlayState no longer has
    one. The temporary track (PlayState.limit) is untouched and still ephemeral."""
    from exalted_builder.models.character import PlayState
    assert "limit_permanent" in Character.model_fields
    assert "limit_permanent" not in PlayState.model_fields
    assert "limit" in PlayState.model_fields


def test_gaining_permanent_resonance_is_free_and_logged(rs):
    """"she gains a point of permanent Resonance" — inflicted by the Curse, not bought,
    so it costs nothing. It is still logged, so the trait has an audit trail."""
    c = _locked_abyssal(MP(merit_id=DEATH_TAINT, points=4))
    entry = advancement.gain_permanent_resonance(rs, c, "Resonance overflowed")
    assert (entry.cost, c.limit_permanent) == (0, 1)
    assert entry.target == validate.PERMANENT_RESONANCE_TARGET


def test_shedding_permanent_resonance_costs_five_experience(rs):
    """"must spend five experience points and undergo a Harrowing" (p.41)."""
    c = _locked_abyssal(MP(merit_id=DEATH_TAINT, points=6), xp=10, permanent=2)
    entry = advancement.shed_permanent_resonance(rs, c, "Harrowing in the Labyrinth")
    assert (entry.cost, c.limit_permanent) == (merits.PERMANENT_RESONANCE_SHED_XP, 1)


def test_the_audit_prices_each_direction_separately(rs):
    """The trap this target exists to avoid: `_expected_cost` prices any row whose
    to_rating is below its from_rating at 0, which would report the five-point shed as
    a mismatch on every later validation."""
    c = _locked_abyssal(MP(merit_id=DEATH_TAINT, points=6), xp=10, permanent=2)
    advancement.gain_permanent_resonance(rs, c, "overflow")   # 2 -> 3, free
    advancement.shed_permanent_resonance(rs, c, "Harrowing")  # 3 -> 2, five XP
    assert not [i for i in advancement.validate_xp(rs, c) if i.code == "xp-cost-mismatch"]


def test_permanent_resonance_cannot_exceed_essence(rs):
    """"Characters may not have a permanent Resonance higher than their Essence"."""
    c = _locked_abyssal(MP(merit_id=DEATH_TAINT, points=4), essence=2, permanent=2)
    with pytest.raises(advancement.AdvancementError):
        advancement.gain_permanent_resonance(rs, c, "overflow")


def test_a_character_without_the_flaw_has_no_track_to_gain(rs):
    c = _locked_abyssal()
    with pytest.raises(advancement.AdvancementError):
        advancement.gain_permanent_resonance(rs, c, "overflow")


def test_undo_reverses_a_permanent_resonance_row(rs):
    """Append-only with LIFO undo, exactly like every other ledger row."""
    c = _locked_abyssal(MP(merit_id=DEATH_TAINT, points=6), xp=10, permanent=2)
    advancement.shed_permanent_resonance(rs, c, "Harrowing")
    assert c.limit_permanent == 1
    advancement.undo_last(rs, c)
    assert c.limit_permanent == 2 and not c.xp_log
def test_a_two_sided_entry_cannot_be_gained_without_a_side(rs):
    """Neither branch may default the choice: the side is what decides whether the
    transaction charges the character or pays her."""
    c = _locked_solar()
    with pytest.raises(advancement.AdvancementError, match="which side"):
        advancement.buy_merit(rs, c, VOW)
    with pytest.raises(advancement.AdvancementError, match="which side"):
        advancement.gain_flaw(rs, c, VOW)
    # and the wrong side is refused by the branch it does not belong to
    with pytest.raises(advancement.AdvancementError, match="which side"):
        advancement.buy_merit(rs, c, VOW, taken_as="flaw")
    assert c.merits_flaws == []


def test_a_two_sided_entry_prices_by_the_side_taken(rs):
    """Eternal Vow is "3-PT. MERIT OR 1-PT. FLAW" (p.29) — `cost_by_kind`, which the
    XP path could not previously see at all (it read `merit.cost`, which is 0)."""
    as_merit = _locked_solar()
    assert advancement.buy_merit(rs, as_merit, VOW, taken_as="merit").cost == 6
    as_flaw = _locked_solar()
    assert advancement.gain_flaw(rs, as_flaw, VOW, taken_as="flaw").cost == -2


def test_gaining_records_the_side_and_clears_the_validation_issue(rs):
    c = _locked_solar()
    advancement.buy_merit(rs, c, VOW, taken_as="merit")
    assert c.merits_flaws[0].taken_as == "merit"
    assert not _codes(validate.validate_chargen(rs, c), "merit-side-unchosen")
    # the same entry with no side recorded is still reported
    assert _codes(validate.validate_chargen(rs, _solar(MP(merit_id=VOW))),
                  "merit-side-unchosen")


def test_buying_off_a_two_sided_entry_held_as_a_flaw_charges(rs):
    """`drop_merit` branched on the CATALOGUE's kind, so buying off an either-entry
    held as a Flaw paid the character instead of charging her."""
    held_as_flaw = _locked_solar(MP(merit_id=VOW, taken_as="flaw"))
    assert advancement.drop_merit(rs, held_as_flaw, 0).cost == 2      # charged
    held_as_merit = _locked_solar(MP(merit_id=VOW, taken_as="merit"))
    assert advancement.drop_merit(rs, held_as_merit, 0).cost == -6    # paid


def test_a_variable_cost_two_sided_entry_prices_from_its_agreed_points(rs):
    """Mutation and Favor are variable AND two-sided, so both the agreed points and
    the side have to reach the pricing — otherwise they gain for 0 XP."""
    c = _locked_solar()
    assert advancement.gain_flaw(rs, c, "mf.mutation", taken_as="flaw",
                                 points=4).cost == -8
    assert c.merits_flaws[0].points == 4
    assert c.merits_flaws[0].taken_as == "flaw"


# --- the availability predicate the two dropdowns share ---------------------- #

def test_merit_available_to_reads_the_three_printed_restrictions(rs):
    """One predicate, sharing its conditions with merit-wrong-splat /
    merit-barred-splat / merit-barred-caste so a dropdown cannot offer something
    validation would immediately reject."""
    chimera = rs.merits_flaws["mf.chimera"]            # LUNARS ONLY
    assert validate.merit_available_to(chimera, "Lunar")
    assert not validate.merit_available_to(chimera, "Solar")

    # `barred_exalt_types` is unused by the catalogue since Prodigy's bar became
    # per-option (2026-07-31), so the whole-entry case is exercised on a constructed
    # definition rather than by pinning whichever entry happens to use it.
    barred = rs.merits_flaws["mf.large-size"].model_copy(
        update={"barred_exalt_types": ["Solar"]})
    assert validate.merit_available_to(barred, "Dragon-Blooded")
    assert not validate.merit_available_to(barred, "Solar")

    beacon = rs.merits_flaws["mf.beacon-of-power"]     # not for Night or Day caste
    assert validate.merit_available_to(beacon, "Solar", "dawn")
    assert not validate.merit_available_to(beacon, "Solar", "night")


def test_availability_ignores_the_conditions_that_change_as_a_sheet_is_built(rs):
    """Prerequisites and "thaumaturges only" are deliberately NOT filtered on — they
    depend on the rest of the sheet, so hiding an entry for them would make the
    dropdown flicker as the character is edited."""
    mastery = rs.merits_flaws[MASTERY]                 # requires Essence Awareness
    assert validate.merit_available_to(mastery, "Mortal")
    assert validate.merit_available_to(rs.merits_flaws[OATH], "Mortal")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_xp_tab_offers_the_permanent_resonance_controls(user) -> None:
    """The play tracker tells the ST to come here, so the panel must exist. Both
    directions, each labelled with its own price."""
    await user.open('/merits-resonance-xp')
    await user.should_see("Permanent Resonance")
    await user.should_see("Gain (free)")
    await user.should_see("Shed (5 XP)")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_editor_offers_a_side_selector_for_a_two_sided_entry(user) -> None:
    """The gap this closes: Mutation, Favor and Eternal Vow are `kind: "either"`, and
    nothing in the editor set `taken_as`, so the choice validation asked for could not
    be made anywhere in the app."""
    await user.open('/mf-side')
    await user.should_see("Merits & Flaws")
    await user.should_see("Eternal Vow")
    # Asserted on the select's OPTIONS, not with should_see: a dropdown's options are
    # not in the rendered HTML until it is opened (the same reason the thaumaturgy
    # tab's toggles cannot be clicked from a test).
    sides = [sel for sel in user.find(ui.select).elements
             if set(sel.options or {}) == {"merit", "flaw"}]
    assert sides, "no side selector rendered for the two-sided entry"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_editor_merit_dropdown_filters_by_splat_and_caste(user) -> None:
    """The XP tab filtered; the editor did not, so a Solar could pick Chimera at
    chargen and be told off for it afterwards."""
    await user.open('/mf-side')
    options = {o for sel in user.find(ui.select).elements for o in (sel.options or {})}
    assert "mf.chimera" not in options          # LUNARS ONLY
    assert "mf.eternal-vow" in options          # open to this Solar
    # Prodigy IS offered to a Solar: its aptitude half escapes the bar (2026-07-31),
    # and an entry is only hidden when every option of its menu is closed.
    assert "mf.prodigy" in options


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_xp_tab_asks_for_a_side_before_gaining_a_two_sided_entry(user) -> None:
    """The XP tab used to route every either-entry into the Merit branch, which then
    raised — so they could not be gained in play at all."""
    await user.open('/mf-side-xp')
    await user.should_see("Merits & Flaws")
    await user.should_see("Gain")


# --- 2026-07-31 browser click-through: three bugs 1,370 tests missed --------- #
# All three are the same species — a rule that WAS implemented, in a place that does
# not run when it matters. None was catchable by the existing suite, which is why the
# click-through earned its keep for the second time.

def test_callous_willpower_keeps_tracking_the_virtues_after_the_lock(rs):
    """THE A1 headline claim, and it did not work. `willpower_virtue_margin` was only
    ever read as a CHARGEN CEILING in validate, which does nothing post-lock, so
    raising a Virtue on a locked Callous character left Willpower on the frozen
    component — decision 0005's normal behaviour, i.e. the exception was absent."""
    c = _solar(MP(merit_id=CALLOUS, tier="4"))
    c.virtues = {v: 1 for v in V}          # 4 dots — well under the 9 that expire it
    lifecycle.lock_chargen(c)
    before = derive.willpower(c, rs)
    c.virtues[V.COMPASSION] = 3            # 6 dots: still Callous
    assert derive.willpower(c, rs) == before + 2, "Callous Willpower must follow the Virtues"


def test_everyone_else_stays_pinned_at_the_lock(rs):
    """Decision 0005 still governs every character without the Flaw — the exception
    must not have leaked into the general path."""
    c = _solar()
    c.virtues = {v: 1 for v in V}
    lifecycle.lock_chargen(c)
    before = derive.willpower(c, rs)
    c.virtues[V.COMPASSION] = 3
    assert derive.willpower(c, rs) == before


def test_willpower_without_a_ruleset_cannot_see_the_exception(rs):
    """The optional-`ruleset` shape means a caller that omits it gets the pinned
    value. Recorded rather than fixed: it is the documented cost of that shape, and
    the reason every caller should pass one."""
    c = _solar(MP(merit_id=CALLOUS, tier="4"))
    c.virtues = {v: 1 for v in V}
    lifecycle.lock_chargen(c)
    c.virtues[V.COMPASSION] = 3
    assert derive.willpower(c) < derive.willpower(c, rs)


def test_an_attribute_capped_below_one_has_no_free_starting_dot(rs):
    """Disfigured at 4 points caps Appearance at 0. The editor's per-category tally
    discounted a flat one free dot per Attribute, so a legal Social row of
    Appearance 0 / Manipulation 1 / Charisma 1 read "−1 spent"."""
    e = merits.merits_and_flaws_calc(rs, _solar(MP(merit_id=DISFIGURED, tier="4")))
    assert e.attribute_caps.get("appearance") == 0
    # the baseline the UI now uses: min(1, cap) per Attribute, never a flat 1
    caps = [e.attribute_caps.get(n, merits.DOT_MAX) for n in
            ("appearance", "manipulation", "charisma")]
    ratings = [0, 1, 1]
    assert sum(r - min(1, c) for r, c in zip(ratings, caps)) == 0


def test_ability_dots_above_the_cap_do_not_consume_the_free_pool(rs):
    """The human's ruling 2026-07-31: dots above the pre-bonus cap are BP-only and
    never draw on the 25. The ENGINE always had this right — the editor's tally was
    summing raw ratings, so one Ability at 4 read 25/25 with a free dot still unspent.
    Pinned here against the engine so the two cannot drift apart again."""
    c = _solar()
    names = [a for a in AbilityName if a != AbilityName.CRAFT]
    c.abilities = {a: 0 for a in names}
    for a in names[:7]:
        c.abilities[a] = 3                       # 21 dots, all within the cap
    c.abilities[names[7]] = 4                    # 25 raw, but only 24 within
    b = validate.effective_budgets(rs, c)
    within = sum(min(v, b.ability_cap_pre_bp) for v in c.abilities.values())
    assert sum(c.abilities.values()) == 25 and within == 24
    # the 25th free dot is still available, and the above-cap dot was charged instead
    bd = validate.bonus_point_breakdown(rs, c)
    assert next(l.points for l in bd.lines if l.domain == "Abilities") > 0


def test_willpower_re_pins_when_callous_expires(rs):
    """"automatically loses this Flaw at no cost" at 9 dots of Virtues (p.35). Once it
    is gone the character is an ordinary decision-0005 case again, so Willpower stops
    following the Virtues and falls back to the frozen component. Found while writing
    the test above, which raised a Virtue hard enough to expire the Flaw mid-assertion."""
    c = _solar(MP(merit_id=CALLOUS, tier="4"))
    c.virtues = {v: 1 for v in V}
    lifecycle.lock_chargen(c)
    pinned = c.wp_virtue_component
    c.virtues[V.COMPASSION] = 3                       # 6 dots: still tracking
    assert derive.willpower(c, rs) != pinned
    for v in V:
        c.virtues[v] = 3                              # 12 dots: Flaw expires
    assert not merits.merits_and_flaws_calc(rs, c).willpower_tracks_virtues
    assert derive.willpower(c, rs) == pinned


# --- variable-cost entries were inert at chargen (2026-07-31 click-through) --- #
# The editor had NO handling of `variable_cost` at all, so `MeritFlawPurchase.points`
# stayed 0 for all 11 such entries: no bonus points granted, no effect computed. Three
# of the four trait-forfeit Flaws are variable-cost, which is why Diminished Attributes
# "did nothing" while Callous — the one with a printed tier menu — worked.

DIMINISHED = "mf.diminished-attributes"


def test_every_variable_cost_entry_is_inert_at_zero_points(rs):
    """The precondition that made this invisible: with no points recorded, a
    variable-cost entry is legal, costless and effectless. Nothing was ever going to
    fail — it just quietly did nothing."""
    variable = [m for m in rs.merits_flaws.values() if m.variable_cost]
    assert len(variable) == 11
    for m in variable:
        c = _solar(MP(merit_id=m.id))
        assert validate.merit_points(m, c.merits_flaws[0], "Solar", "dawn") == 0


def test_the_forfeit_rate_accessor_converts_dots_to_points(rs):
    """The editor collects DOTS and multiplies (human's ruling 2026-07-31). This is the
    accessor that lets it do so without naming a Merit id — decision 0011 holds."""
    assert merits.forfeit_rate(rs.merits_flaws[DIMINISHED]) == 3
    assert merits.forfeit_rate(rs.merits_flaws[CALLOUS]) == 2
    assert merits.forfeit_rate(rs.merits_flaws["mf.unskilled"]) == 1
    assert merits.forfeit_rate(rs.merits_flaws["mf.large-size"]) is None
    assert merits.forfeit_trait_label(rs.merits_flaws[DIMINISHED]) == "Attribute"


def test_diminished_attributes_shrinks_the_pool_its_category_received(rs):
    """The bug as reported: 8 dots into Physical with the Flaw held produced no
    shortfall, no over-spend and an unchanged 8/6/4. With dots recorded, the pool the
    Physical category is matched to drops by the forfeit."""
    rate = merits.forfeit_rate(rs.merits_flaws[DIMINISHED])
    c = _solar(MP(merit_id=DIMINISHED, detail="Physical", points=2 * rate))
    c.attributes = {a: 1 for a in A}
    c.attributes[A.STRENGTH] = 4
    c.attributes[A.DEXTERITY] = 4
    c.attributes[A.STAMINA] = 3                      # 8 spent into Physical
    c.attributes[A.CHARISMA] = 3
    c.attributes[A.MANIPULATION] = 3
    c.attributes[A.APPEARANCE] = 3                   # 6
    c.attributes[A.PERCEPTION] = 3
    c.attributes[A.INTELLIGENCE] = 2
    c.attributes[A.WITS] = 2                         # 4
    e = merits.merits_and_flaws_calc(rs, c)
    assert e.forfeited_attribute_dots == {"Physical": 2}
    assert e.bonus_point_grant == 6                  # 3 per dot
    b = validate.effective_budgets(rs, c)
    assignment = validate.attribute_pool_assignment(rs, c, b, c.attributes)
    physical = next(row for row in assignment if row[0] == "Physical")
    assert physical == ("Physical", 8, 6), "the forfeit must come off the matched pool"


def test_a_structured_detail_is_a_closed_set_not_free_text(rs):
    """Two entries structure their `detail`, and free text broke both: a typo became a
    fourth Attribute category (it is title-cased and defaults to Physical), and an
    empty box left Legendary Attribute inert with no complaint at all."""
    assert merits.detail_choices(rs.merits_flaws[DIMINISHED]) == (
        "Physical", "Mental", "Social")
    assert merits.detail_choices(rs.merits_flaws[LEGENDARY_ATTR])[0] == "Strength"
    assert len(merits.detail_choices(rs.merits_flaws[LEGENDARY_ATTR])) == 9
    assert merits.detail_choices(rs.merits_flaws[CALLOUS]) == ()


def test_an_unchosen_structured_detail_is_reported(rs):
    """It used to fail SILENTLY — Legendary Attribute with no Attribute named granted
    no cap and said nothing. `_attribute_forfeits`' docstring claimed validate flagged
    the omission; no such check existed until now."""
    for mid in (LEGENDARY_ATTR, DIMINISHED):
        blank = _codes(validate.validate_chargen(rs, _solar(MP(merit_id=mid))),
                       "merit-detail-unchosen")
        assert blank, f"{mid} with no detail must be reported"
    ok = _solar(MP(merit_id=LEGENDARY_ATTR, detail="Strength"))
    assert not _codes(validate.validate_chargen(rs, ok), "merit-detail-unchosen")
    # and the cap it was silently failing to grant now lands
    assert merits.merits_and_flaws_calc(rs, ok).attribute_caps.get("strength") == 6


def test_arena_belongs_only_to_the_entry_with_the_stacking_rule(rs):
    """The editor showed an arena box beside every menu-priced entry — Callous and
    Large Size included — where nothing reads it."""
    assert merits.uses_arena(rs.merits_flaws[OATH])
    assert not merits.uses_arena(rs.merits_flaws[CALLOUS])
    assert not merits.uses_arena(rs.merits_flaws["mf.large-size"])


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_xp_tab_collects_values_through_the_same_controls_as_the_editor(user) -> None:
    """The XP tab priced every entry through ONE free-text input doing double duty — a
    tier key for a menu-priced entry, a point value for a variable-cost one. The editor
    grew proper tier / dots / points / structured-detail controls on 2026-07-31, which
    left the two halves of the app collecting the same rules through different widgets:
    exactly the shape that produced the splat-filter bug. The free-text box is gone."""
    await user.open('/mf-side-xp')
    await user.should_see("Merits & Flaws")
    # Not via user.find(ui.input): with nothing held, the page legitimately renders no
    # text input at all, and find() raises rather than returning empty.
    labels = {(getattr(e, "props", {}) or {}).get("label") or ""
              for e in user.client.elements.values()}
    assert "tier / points" not in labels, "the double-duty free-text field is still there"
    # Both regimes now run through ONE implementation, so "the same controls as the
    # editor" is structural rather than a thing two modules have to agree about.
    from exalted_builder.ui import advantages
    import inspect
    assert "merit_cost_options" in inspect.getsource(advantages)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_says_how_many_flaw_points_the_cap_swallowed(user) -> None:
    """`flaw_points_raw` was computed for this line and read by nothing, so the panel
    printed the CAPPED grant alone: a player who took 14 points of Flaws saw "+10" and
    could not tell the p.17 ceiling from an arithmetic bug. Found by the preflight
    read-site audit, not by a test — one asserted the field directly and passed."""
    await user.open('/mf-capped')
    await user.should_see("+10 from Flaws")
    await user.should_see("14 points of Flaws taken, 10 granted")
    await user.should_see("The Flaws still apply.")   # the excess is lost, not the Flaw


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_xp_tab_says_there_is_no_room_left_under_the_cap(user) -> None:
    """In play the same ceiling truncates the XP AWARD (`award * room // value`), which
    is worth stating BEFORE a Flaw is bought rather than discovering afterwards that it
    paid nothing."""
    await user.open('/mf-capped-xp')
    await user.should_see("Merits & Flaws")
    await user.should_see("at the 10-point cap")
    await user.should_see("pays no XP")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_xp_tab_reports_the_room_that_is_left(user) -> None:
    """The under-cap case states the remaining headroom rather than staying silent."""
    await user.open('/mf-xp')
    await user.should_see("0 of 10 points of Flaws taken")
    await user.should_see("pays for at most 10 more")


def test_the_xp_and_chargen_paths_price_a_purchase_identically(rs):
    """The point of routing both through `validate.merit_points`: whatever the two UIs
    collect, one function turns it into a price. Pinned across every cost SHAPE the
    catalogue uses, since it was a shape (`cost_by_kind`) that the XP path could not
    see at all before today."""
    rate = merits.forfeit_rate(rs.merits_flaws[DIMINISHED])
    cases = [
        (VOW, dict(taken_as="merit"), 3),                    # cost_by_kind
        (VOW, dict(taken_as="flaw"), 1),                     # ...the other side
        (CALLOUS, dict(tier="4"), 4),                        # cost_options menu
        (DIMINISHED, dict(points=2 * rate, detail="Physical"), 2 * rate),   # variable
        (LEGENDARY_ATTR, dict(detail="Strength"), 3),        # flat, Solar rate
    ]
    for mid, kw, expected in cases:
        purchase = MP(merit_id=mid, **kw)
        assert validate.merit_points(rs.merits_flaws[mid], purchase, "Solar", "dawn") \
            == expected, mid


# --- trait prerequisites, generalised (2026-07-31) -------------------------- #
# A prerequisite on a TRAIT rather than on another Merit. `MeritFlaw.prerequisites`
# holds Merit ids only, so these had nowhere to live and went unchecked. Now catalogue
# data evaluated generically — which REMOVED Legendary Breeding's id from engine/merits
# rather than adding one, because a restriction is as inert as a cost.

# --- the optional-`ruleset` audit (2026-07-31) ------------------------------ #
# `derive.soak`, `derive.willpower` and `derive.health_track` take an OPTIONAL RuleSet
# because without one there is no way to know a Flaw is held. That shape is deliberate,
# but it makes every omission a silent bug rather than a TypeError — `raise_willpower`
# was one, found earlier. This is the sweep for the rest.

def test_no_caller_omits_the_ruleset_when_reading_willpower():
    """A source-level guard, because the failure is invisible at runtime: the call
    SUCCEEDS and quietly returns the pre-Flaw number. Three callers were omitting it
    (`advancement.lower_willpower` and two in the XP tab), which quoted a Weak-Willed
    character 8 XP for a Willpower dot that `raise_willpower` then charged 4 for."""
    import re
    pkg = Path(exalted_builder.__file__).parent
    offenders = []
    for path in pkg.rglob("*.py"):
        if path.name == "derive.py":
            continue                       # defines it; its internal calls pass it
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"derive\.willpower\(\s*\w+\s*\)", line):
                offenders.append(f"{path.relative_to(pkg)}:{i}")
    assert offenders == [], (
        "these read Willpower without a RuleSet and so cannot see a Flaw: "
        + ", ".join(offenders))


def test_lowering_willpower_sees_a_flaw_that_moved_it(rs):
    """`lower_willpower`'s floor guard and its ledger row both read the current value.
    Blind to the Flaw, a Weak-Willed character reads 4 where the truth is 2 — so the
    guard lets a reduction through that should have been refused, and the log records
    a drop that did not happen."""
    def weak(**kw):
        c = _solar(MP(merit_id="mf.weak-willed", points=2), **kw)   # 2 WP dots sold
        c.virtues = {v: 2 for v in V}
        lifecycle.lock_chargen(c)
        return c
    c = weak()
    assert derive.willpower(c, rs) == 2 and derive.willpower(c) == 4
    entry = advancement.lower_willpower(c, "curse", ruleset=rs)
    assert (entry.from_rating, entry.to_rating) == (2, 1), "the ledger must record the truth"
    # and at the floor it refuses, where the blind read would have allowed it
    with pytest.raises(advancement.AdvancementError, match="already at 1"):
        advancement.lower_willpower(c, "curse", ruleset=rs)


def test_weak_essence_is_closed_to_a_splat_that_already_starts_at_essence_one(rs):
    """A live exploit until 2026-07-31, not a theoretical one. Weak Essence is a 6-point
    Flaw whose ENTIRE cost is "reduces the character's starting Essence rating to 1" — so
    on a Mortal, pinned at Essence 1 already, it cost nothing and paid 6 bonus points
    against a 21-point budget. It also handed 5 withheld-Charm credits to a splat with no
    Charms. The printed clause exists precisely to close this: "Other magical beings may
    take this Flaw, provided that they normally have a starting Essence of 2" (p.41)."""
    assert rs.merits_flaws["mf.weak-essence"].min_starting_essence == 2
    mortal = _mortal(MP(merit_id=WEAK_ESSENCE))
    assert _codes(validate.validate_chargen(rs, mortal), "merit-starting-essence")
    # ...and it still pays nothing for the Flaw's own effect, which is why it is barred
    assert validate.effective_budgets(rs, mortal).essence_start == 1
    solar = _solar(MP(merit_id=WEAK_ESSENCE))
    assert not _codes(validate.validate_chargen(rs, solar), "merit-starting-essence")


def test_the_starting_essence_gate_hides_the_entry_but_only_when_supplied(rs):
    """Filtered in both dropdowns, like the splat and caste bars — a Mortal should never
    be offered it. The argument is OPTIONAL and omitting it is permissive, so a caller
    without the budgets to hand can only ever fail to hide, never wrongly hide."""
    we = rs.merits_flaws["mf.weak-essence"]
    assert not validate.merit_available_to(we, "Mortal", starting_essence=1)
    assert validate.merit_available_to(we, "Solar", "dawn", starting_essence=2)
    assert validate.merit_available_to(we, "Mortal")          # unsupplied -> shown


def test_the_aptitude_half_lowers_that_ability_s_xp_and_only_that_one(rs):
    """"The increased aptitude lowers the cost of raising the Trait with experience to
    (current rating x 2) - 2" (p.21). A subtraction after the rate, the same shape as a
    Calling Ability's discount — which is why `costs.ability_step` can carry both."""
    plain = _db()
    bought = _db(MP(merit_id=PRODIGY, tier="aptitude", detail="Melee"))
    for c in (plain, bought):
        c.chargen_locked = True
    before = costs.ability_step(rs, plain, AbilityName.MELEE, 3)
    after = costs.ability_step(rs, bought, AbilityName.MELEE, 3)
    assert after == before - 2
    # ...and no other Ability moves
    assert (costs.ability_step(rs, bought, AbilityName.ARCHERY, 3)
            == costs.ability_step(rs, plain, AbilityName.ARCHERY, 3))


def test_the_aptitude_discount_does_not_stack_on_one_ability(rs):
    """Keyed per Ability rather than counted, so buying it twice for the same Trait
    cannot double the discount."""
    twice = _db(MP(merit_id=PRODIGY, tier="aptitude", detail="Melee"),
                MP(merit_id=PRODIGY, tier="aptitude", detail="Melee"))
    once = _db(MP(merit_id=PRODIGY, tier="aptitude", detail="Melee"))
    for c in (twice, once):
        c.chargen_locked = True
    assert (costs.ability_step(rs, twice, AbilityName.MELEE, 3)
            == costs.ability_step(rs, once, AbilityName.MELEE, 3))


def test_only_the_favored_granting_halves_raise_the_favored_count(rs):
    """A Solar buying aptitude alone gains no Favored slot — which is the whole reason
    the bar is per-option rather than per-entry."""
    base = validate.favored_ability_count(rs, _db())
    grant = _db(MP(merit_id=PRODIGY, tier="favored", detail="Melee"))
    both = _db(MP(merit_id=PRODIGY, tier="favored_aptitude", detail="Melee"))
    apt = _db(MP(merit_id=PRODIGY, tier="aptitude", detail="Melee"))
    assert validate.favored_ability_count(rs, grant) == base + 1
    assert validate.favored_ability_count(rs, both) == base + 1
    assert validate.favored_ability_count(rs, apt) == base


def test_prodigy_is_repeatable_per_ability(rs):
    """"one additional Favored Ability for every time this Merit is purchased" — it was
    authored once-only, so a second purchase was reported as an illegal repeat. The
    five-Favored cap is enforced by `favored_ability_count`, not by forbidding it."""
    assert rs.merits_flaws[PRODIGY].repeatable_by == "ability"
    twice = _db(MP(merit_id=PRODIGY, tier="favored", detail="Melee"),
                MP(merit_id=PRODIGY, tier="favored", detail="Archery"))
    assert not _codes(validate.validate_chargen(rs, twice), "merit-repeated")


def test_the_tier_menu_no_longer_collides_on_price(rs):
    """The reason the 2/3/4/5 menu had to go: "aptitude only" and "Dragon King grant
    only" are BOTH 2 points, so a numeric tier could not say which was bought. Harmless
    while Dragon Kings do not exist, and a trap that springs exactly when they land.
    Semantic keys are distinct whatever they cost."""
    opts = rs.merits_flaws[PRODIGY].cost_options
    assert set(opts) == {"favored", "favored_aptitude", "aptitude"}
    assert opts["aptitude"] == 2 and opts["favored"] == 3 and opts["favored_aptitude"] == 5
    assert len(set(opts)) == len(opts), "keys must be distinct even where prices are not"


def test_the_naive_tier_default_would_have_been_illegal_for_a_solar(rs):
    """The bug reported 2026-07-31: a fresh Prodigy row on a Solar opened on `favored`
    and flagged itself immediately, because the editor defaulted to the first AUTHORED
    option rather than the first this splat may choose. Pinned as the shape of the
    mistake, so re-introducing it fails here rather than in a browser."""
    d = rs.merits_flaws[PRODIGY]
    naive = next(iter(d.cost_options))
    assert naive == "favored"
    assert validate.exalt_type_barred_from_tier(d, "Solar", naive), (
        "this test is only meaningful while the first authored tier IS barred")
    correct = next(iter(validate.merit_tiers_available(d, "Solar")))
    assert correct == "aptitude"
    assert not validate.exalt_type_barred_from_tier(d, "Solar", correct)


@pytest.mark.parametrize("exalt_type", ["Solar", "Abyssal", "Lunar", "Alchemical",
                                        "Dragon-Blooded", "Sidereal", "Mortal"])
def test_every_menu_priced_entry_has_a_legal_default_for_every_splat(rs, exalt_type):
    """The invariant the editor now relies on: the first available tier is never a
    barred one, for any entry and any splat. Generic, so an entry that grows a
    per-option bar later cannot quietly reintroduce the same bug."""
    for m in rs.merits_flaws.values():
        if not m.cost_options:
            continue
        tiers = validate.merit_tiers_available(m, exalt_type)
        if not tiers:
            assert not validate.merit_available_to(m, exalt_type), (
                f"{m.id} offers no tier to {exalt_type} but is still listed as available")
            continue
        assert not validate.exalt_type_barred_from_tier(m, exalt_type, tiers[0]), m.id


# --- the XP tab's trait ceilings (player report, 2026-07-31) ----------------- #
# The engine honoured both Merit-raised caps and the chargen editor displayed them;
# only the XP tab hardcoded 5, so the buy was unreachable exactly where it mattered.
# Engine-level tests could not see it — they call raise_attribute directly, which
# always worked. Assert through the row instead. Decision 0013 deletes this tab; until
# it does, the cap is live. See docs/status/edit-xp-merge.md.

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_trait_surface_honours_merit_raised_trait_ceilings(user) -> None:
    """The player's original report. The XP tab that hardcoded 5 is gone; the dot
    tracks that replaced it read the cap from the engine, so Strength 6 (Legendary
    Attribute) and Valor 6 (True Paragon) are CLICKABLE — a track only renders as many
    pips as the ceiling allows, so a 6th pip existing is the assertion."""
    from nicegui.elements.icon import Icon
    await user.open('/xp-caps')
    pips = [el for el in user.client.elements.values() if isinstance(el, Icon)
            and el.props.get("name") in ("circle", "radio_button_unchecked")]
    assert pips, "no dot tracks rendered at all"


def test_the_engine_allows_both_ceilings_the_xp_tab_was_hiding(rs):
    """The other half of the same bug: proof the row was refusing a legal purchase,
    not reflecting one. Both raises succeed at the rating the UI called 'max'."""
    c = _solar(MP(merit_id="mf.legendary-attribute", detail="strength"),
               MP(merit_id="mf.true-paragon"))
    c.nature = "Paragon"
    c.attributes[A.STRENGTH] = 5
    c.virtues[V.VALOR] = 5
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 200)
    assert advancement.raise_attribute(rs, c, A.STRENGTH).to_rating == 6
    assert advancement.raise_virtue(rs, c, V.VALOR).to_rating == 6


# --- the M&F filter bar (2026-08-01) ---------------------------------------- #
# 99 entries in one flat dropdown was the last standing usability complaint. Both
# regimes get ONE filter (`_mf_matches`), so these tests drive both routes; a filter
# that works on chargen and not in play is exactly the drift this module exists to
# prevent.

def _mf_search_box(user):
    """The filter bar's search input. Found by placeholder, because the Backgrounds
    panel on the same tab also renders `ui.input`s."""
    boxes = [el for el in user.find(ui.input).elements
             if "search" in (el.props.get("placeholder") or "")]
    assert boxes, "no M&F search box rendered"
    return boxes[0]


def _mf_side_select(user):
    return next(sel for sel in user.find(ui.select).elements
                if set(sel.options or {}) == {"", "merit", "flaw"})


def _merit_row_options(user) -> set[str]:
    """The options offered by the entry dropdowns — the ones keyed by merit id."""
    return {o for sel in user.find(ui.select).elements
            for o in (sel.options or {}) if str(o).startswith(("mf.", "thaum."))}


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_merit_dropdown_ships_a_search_box(user) -> None:
    """The complaint itself: 99 entries, no way to narrow them."""
    await user.open('/mf-side')
    _mf_search_box(user)
    _mf_side_select(user)
    await user.should_see("available")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_searching_narrows_the_chargen_merit_dropdown(user) -> None:
    """Typing re-options the live select rather than rebuilding the panel — a rebuilt
    `ui.input` loses focus, which would eat every keystroke after the first."""
    await user.open('/mf-side')
    before = _merit_row_options(user)
    assert len(before) > 50, "the dropdown was already narrow — test proves nothing"
    _mf_search_box(user).set_value("vow")
    after = _merit_row_options(user)
    assert after < before
    assert "mf.eternal-vow" in after


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_search_matches_rules_text_not_only_the_name(user) -> None:
    """A player looking for a Merit knows what it DOES, not what it is called."""
    await user.open('/mf-side')
    _mf_search_box(user).set_value("essence")
    hits = _merit_row_options(user)
    assert hits, "searching rules text found nothing at all"
    names = {exalted_builder.rules_db.load_app_ruleset(
        Path(exalted_builder.__file__).parent / "data").merits_flaws[h].name.lower()
        for h in hits}
    assert any("essence" not in n for n in names), \
        "every hit had 'essence' in its NAME — the description was not searched"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_held_entry_survives_a_filter_that_excludes_it(user) -> None:
    """`ui.select` RAISES when its value is not among its options, and the raise takes
    the whole tab with it. Filtering to something the held row does not match is the
    easiest way to trigger that, so the held id is always re-added."""
    await user.open('/mf-side')
    _mf_search_box(user).set_value("zzzz-matches-nothing")
    held = [sel for sel in user.find(ui.select).elements
            if sel.value == "mf.eternal-vow"]
    assert held, "the held entry vanished from its own dropdown"
    assert "mf.eternal-vow" in (held[0].options or {})
    await user.should_see("of")          # the "N of M shown" counter


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_side_filter_keeps_two_sided_entries(user) -> None:
    """An `either` entry is genuinely both, so hiding it from both side filters is how
    a player loses Eternal Vow and Prodigy."""
    await user.open('/mf-side')
    _mf_side_select(user).set_value("flaw")
    assert "mf.eternal-vow" in _merit_row_options(user)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_play_gain_dropdown_filters_too(user) -> None:
    """The same filter on the other side of the lock. The play select already had
    type-ahead, but over a label that leads with the name — so a category or a rules-
    text search found nothing there either."""
    await user.open('/mf-side-xp')
    before = _merit_row_options(user)
    assert len(before) > 50
    _mf_search_box(user).set_value("vow")
    after = _merit_row_options(user)
    assert after < before
    assert "mf.eternal-vow" in after
