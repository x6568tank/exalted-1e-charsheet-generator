"""Cult of the Illuminated — the Solar alternate origin (p.89-106).

Phase 1 covers the data foundation only: the `Solar:illuminated` budget row, the
two training camps, the six Callings, and the loader's link-checks over them. The
engine does not yet ACT on `camp`/`calling` — camp Ability floors, granted Charms,
the Calling BP/XP discounts and the Essence ceiling are Phase 2/3 and get their own
tests there. Nothing here should pass by accident once those land.
"""
import pytest

from exalted_builder.models.character import BackgroundEntry, Character
from exalted_builder.models.rules import AbilityName
from exalted_builder.rules_db import load_ruleset

DATA = "exalted_builder/data"


@pytest.fixture(scope="module")
def rs():
    return load_ruleset(DATA)


# --------------------------------------------------------------- budget row

def test_illuminated_budget_row_differs_from_standard_solar(rs):
    """p.89-90: the deltas from a standard Solar, and only these deltas."""
    std = rs.budgets_for("Solar")
    ill = rs.budgets_for("Solar", "illuminated")

    assert (std.ability_dots, ill.ability_dots) == (25, 30)
    assert (std.background_dots, ill.background_dots) == (7, 9)
    assert (std.charm_count, ill.charm_count) == (10, 8)
    assert (std.charm_min_caste_favored, ill.charm_min_caste_favored) == (5, 4)
    assert (std.essence_start, ill.essence_start) == (2, 3)

    # Unchanged: Attributes, the Caste/Favored dot floor, Virtues, bonus points.
    assert ill.attribute_pools == std.attribute_pools == (8, 6, 4)
    assert ill.ability_min_caste_favored == std.ability_min_caste_favored == 10
    assert ill.virtue_dots == std.virtue_dots == 5
    assert ill.bonus_points == std.bonus_points == 15
    assert ill.favored_count == std.favored_count == 5


def test_essence_ceiling_is_five(rs):
    """p.90: Essence starts at 3 and may be raised with bonus points, but "under no
    circumstances may an Illuminated Solar begin with an Essence of six (6) or
    higher" — so the chargen ceiling is 5. No other splat sets one."""
    assert rs.budgets_for("Solar", "illuminated").essence_start_cap == 5
    for key in ("Solar", "Lunar", "Sidereal", "Alchemical", "Dragon-Blooded", "Abyssal"):
        assert rs.budgets_for(key).essence_start_cap == 0, key


def test_camp_and_calling_are_required_only_for_this_origin(rs):
    ill = rs.budgets_for("Solar", "illuminated")
    assert ill.requires_camp and ill.requires_calling
    for key in ("Solar", "Lunar", "Sidereal", "Alchemical", "Dragon-Blooded", "Abyssal"):
        b = rs.budgets_for(key)
        assert not b.requires_camp and not b.requires_calling, key


def test_backing_is_barred_via_the_allowed_backgrounds_list(rs):
    """p.96: "a Solar cannot belong to another organization ... and, thus, cannot take
    the Backing Background." Expressed as the p.93 permitted list, reusing the ronin
    mechanism — the only hard Background validation in the project."""
    allowed = rs.budgets_for("Solar", "illuminated").allowed_backgrounds
    assert allowed, "an empty list means unrestricted, which would let Backing through"
    assert "Backing" not in allowed
    assert {"Illumination", "Sorcery", "Tiger Warriors"} <= set(allowed)
    # Every other origin stays unrestricted apart from the ronin.
    assert rs.budgets_for("Solar").allowed_backgrounds == []


def test_illumination_dot_is_free_on_top_of_the_pool(rs):
    """p.90: nine Background dots, and "in addition, all Illuminated Solars begin with
    Illumination • for free". free_rating grants the dot outside the pool; min_rating
    makes it mandatory. Contrast the Alchemical Class •••, which is mandatory but IS
    paid for out of the pool (min_rating with no free_rating)."""
    rule = rs.budgets_for("Solar", "illuminated").background_rules["illumination"]
    assert rule.free_rating == 1
    assert rule.min_rating == 1

    alch = rs.budgets_for("Alchemical").background_rules["class"]
    assert alch.free_rating == 0, "the Alchemical Class dots are paid for, not granted"


def test_the_cult_prints_its_own_artifact_background(rs):
    """p.96: the Cult's Artifact is not the core one. It is a combined-rating BUDGET
    (the Abyssal p.131 shape), and an Illuminated Solar must be offered that copy
    rather than the corebook's cost-curve version — which is what the browser found.

    Both catalogue entries are keyed BY ID rather than by the name "artifact",
    because the name alone matches both copies and the displacement rule would then
    hand a standard Solar the Cult's version."""
    ill = {b.id for b in rs.backgrounds_for("Solar", "illuminated")}
    std = {b.id for b in rs.backgrounds_for("Solar")}
    assert "background.artifact-illuminated" in ill
    assert "background.artifact" not in ill
    assert std & {"background.artifact", "background.artifact-illuminated"} \
        == {"background.artifact"}

    tiers = rs.budgets_for("Solar", "illuminated").background_rules["artifact"].budget_tiers
    assert [(t.rating, t.combined_max) for t in tiers] == \
        [(1, 2), (2, 3), (3, 4), (4, 6), (5, 8)]
    # The page prints no per-item ceiling on any row, unlike the loyal Abyssal's.
    assert all(t.individual_max == 0 for t in tiers)
    assert rs.budgets_for("Solar").background_rules.get("artifact") is None


# ------------------------------------------------------------------- camps

def test_two_camps_scoped_to_the_illuminated_origin(rs):
    camps = rs.camps_for("Solar", "illuminated")
    assert [c.id for c in camps] == ["sequestered-tabernacle", "kether-rock"]
    # A standard Solar is offered no camp at all, which is how the UI stays quiet.
    assert rs.camps_for("Solar", "") == []
    assert rs.camps_for("Lunar", "") == []


def test_sequestered_tabernacle_ability_floor(rs):
    """p.89: Endurance •, Linguistics •, Lore •, Martial Arts ••, Occult •,
    Presence •••, Socialize •."""
    got = {m.abilities[0].value: m.rating
           for m in rs.camps["sequestered-tabernacle"].required_min_abilities}
    assert got == {"endurance": 1, "linguistics": 1, "lore": 1, "martial_arts": 2,
                   "occult": 1, "presence": 3, "socialize": 1}


def test_kether_rock_ability_floor_uses_or_semantics_for_archery_or_brawl(rs):
    """p.89: "Either Archery • or Brawl •" — AbilityMinimum already means "at least
    `rating` in AT LEAST ONE of `abilities`", so this needed no new machinery."""
    mins = rs.camps["kether-rock"].required_min_abilities
    either = [m for m in mins if len(m.abilities) > 1]
    assert len(either) == 1
    assert {a.value for a in either[0].abilities} == {"archery", "brawl"}
    assert either[0].rating == 1

    fixed = {m.abilities[0].value: m.rating for m in mins if len(m.abilities) == 1}
    assert fixed == {"endurance": 1, "medicine": 1, "melee": 2,
                     "presence": 1, "resistance": 1, "survival": 3}


def test_tabernacle_grants_two_fixed_charms_plus_a_style_choice(rs):
    """p.90: Ox-Body Technique, Harmonious Presence Meditation, and two Charms from
    ONE of four martial arts styles."""
    camp = rs.camps["sequestered-tabernacle"]
    assert camp.granted_charms == ["solar.endurance.ox-body-technique",
                                   "solar.presence.harmonious-presence-meditation"]
    (choice,) = camp.granted_charm_choices
    assert choice.pick == 2
    assert choice.fixed_sets == []
    assert choice.from_categories == ["martial_arts:ebon-shadow", "martial_arts:praying-mantis",
                                      "martial_arts:snake", "martial_arts:tiger"]


def test_kether_rock_grants_two_fixed_charms_plus_one_whole_pair(rs):
    """p.90: Ox-Body Technique, Hardship-Surviving Mendicant Spirit, and one of four
    printed pairs. The Iron Skin Concentration / Spirit Strengthens the Skin swap is
    authored as two separate pairs, because which one applies is the group's Power
    Combat house rule, not something the engine should decide."""
    camp = rs.camps["kether-rock"]
    assert camp.granted_charms == ["solar.endurance.ox-body-technique",
                                   "solar.survival.hardship-surviving-mendicant-spirit"]
    (choice,) = camp.granted_charm_choices
    assert choice.from_categories == []
    assert all(len(s) == 2 for s in choice.fixed_sets)
    assert len(choice.fixed_sets) == 5          # 4 printed pairs + the Power Combat variant
    flat = {cid for s in choice.fixed_sets for cid in s}
    assert "solar.resistance.iron-skin-concentration" in flat
    assert "solar.resistance.spirit-strengthens-the-skin" in flat


def test_every_granted_charm_id_resolves(rs):
    """The loader link-check enforces this; assert it directly so a future edit that
    weakens the check still fails here. A dangling granted Charm is silent — it just
    never shows up on the sheet."""
    for camp in rs.camps.values():
        for cid in camp.granted_charms:
            assert cid in rs.charms, (camp.id, cid)
        for choice in camp.granted_charm_choices:
            for group in choice.fixed_sets:
                for cid in group:
                    assert cid in rs.charms, (camp.id, cid)


# ---------------------------------------------------------------- callings

def test_three_callings_per_camp(rs):
    assert [c.id for c in rs.callings_for("sequestered-tabernacle")] == \
        ["exemplar", "inquisitor", "itinerant"]
    assert [c.id for c in rs.callings_for("kether-rock")] == \
        ["architect", "deacon", "paladin"]


def test_each_calling_names_five_abilities(rs):
    """p.90-92: every Calling lists exactly five Calling Abilities."""
    for calling in rs.callings.values():
        assert len(calling.abilities) == 5, calling.id
        assert len(set(calling.abilities)) == 5, calling.id


def test_paladin_craft_records_its_printed_focus(rs):
    """p.93 prints "Craft (War)". Craft is per-focus in this project (p.136), so the
    focus has to survive into the data or the discount cannot find the right Craft."""
    assert rs.callings["paladin"].ability_focus == {"craft": "War"}
    assert AbilityName.CRAFT in rs.callings["paladin"].abilities
    # No other Calling has a parenthetical focus.
    assert all(not c.ability_focus for c in rs.callings.values() if c.id != "paladin")


def test_every_calling_charm_id_resolves(rs):
    for calling in rs.callings.values():
        for cid in calling.charms:
            assert cid in rs.charms, (calling.id, cid)


def test_calling_charm_lists_are_complete_except_one_known_gap(rs):
    """Five of the six Charms this origin's Callings referenced but `data/` lacked were
    authored from the book's own Charms chapter (p.100-106), so the lists are now as
    printed. Two counts are NOT ten, for two different reasons:

    * Itinerant — the page itself prints only NINE Calling Charms for it, on both p.91
      and the p.93 summary. Not a gap.
    * Deacon — still missing **Unshakable Bloodhound Technique**, which p.100 implies
      was reprinted from a Caste Book but which does not appear in the chapter. It
      needs a Caste Book page before it can be authored (see _ILLUMINATED_PENDING.md).
    """
    counts = {c.id: len(c.charms) for c in rs.callings.values()}
    assert counts == {"exemplar": 10, "inquisitor": 10, "itinerant": 9,
                      "architect": 10, "deacon": 9, "paladin": 10}


def test_a_calling_ability_is_not_thereby_a_favored_ability(rs):
    """The Calling is a DISCOUNT axis, not a second Favored list — the page has it
    stacking with the Caste/Favored discount, which only makes sense if they are
    separate. Nothing in the data may imply otherwise."""
    calling = rs.callings["exemplar"]
    assert not hasattr(calling, "favored")
    # Overlap with Caste Abilities is expected and harmless (Exemplar shares
    # Endurance/Performance with Zenith); it must not be deduplicated away.
    zenith = set(rs.castes["zenith"].caste_abilities)
    assert set(calling.abilities) & zenith


# --------------------------------------------------------------- character

def test_character_carries_camp_calling_and_granted_charms():
    """The three new fields default empty, so every existing save still loads."""
    c = Character(id="t1", name="Test", exalt_type="Solar", caste="zenith")
    assert (c.camp, c.calling, c.granted_charms) == ("", "", [])

    ill = Character(id="t2", name="Test", exalt_type="Solar", caste="zenith",
                    origin="illuminated", camp="kether-rock", calling="paladin",
                    granted_charms=["solar.endurance.ox-body-technique"])
    assert ill.camp == "kether-rock"
    assert ill.granted_charms == ["solar.endurance.ox-body-technique"]


def test_granted_charms_are_not_stored_in_charms():
    """Granted Charms live on their own list for the same reason ox_body and
    beastman_gifts do: anything counting picks against the Charm pool or the
    Caste/Favored minimum must not see them."""
    c = Character(id="t3", name="Test", exalt_type="Solar", caste="dawn",
                  origin="illuminated", camp="kether-rock", calling="deacon",
                  granted_charms=["solar.endurance.ox-body-technique"])
    assert c.charms == []
    assert "solar.endurance.ox-body-technique" not in c.charms


# ============================================================================ #
# Phase 2 — chargen validation
# ============================================================================ #

from exalted_builder.engine import costs, validate           # noqa: E402
from exalted_builder.models.rules import AbilityName as AB    # noqa: E402


def _illuminated(rs, **kw):
    """A LEGAL Illuminated Solar: Kether Rock / Deacon, meeting every camp floor.

    Kether Rock demands (Archery|Brawl) 1, Endurance 1, Medicine 1, Melee 2,
    Presence 1, Resistance 1, Survival 3 (p.89) — 10 dots of the 30 spent on floors.
    """
    abilities = {AB.BRAWL: 1, AB.ENDURANCE: 1, AB.MEDICINE: 1, AB.MELEE: 2,
                 AB.PRESENCE: 1, AB.RESISTANCE: 1, AB.SURVIVAL: 3}
    abilities.update(kw.pop("abilities", {}))
    camp = rs.camps[kw.pop("camp", "kether-rock")]
    granted = kw.pop("granted_charms", camp.granted_charms + [
        "solar.resistance.durability-of-oak-meditation",
        "solar.resistance.iron-skin-concentration"])
    data = dict(
        id="ill", name="Illuminated", exalt_type="Solar", caste="dawn",
        origin="illuminated", camp=camp.id, calling="deacon",
        essence_rating=3, abilities=abilities, granted_charms=granted,
    )
    data.update(kw)
    return Character(**data)


def _codes(issues):
    return {i.code for i in issues}


# ------------------------------------------------------- camp / calling legality

def test_camp_and_calling_are_required_for_this_origin(rs):
    c = _illuminated(rs, camp="kether-rock")
    assert _codes(validate.check_camp_and_calling(rs, c)) == set()

    missing = c.model_copy(update={"camp": "", "calling": ""})
    assert _codes(validate.check_camp_and_calling(rs, missing)) == \
        {"camp-required", "calling-required"}


def test_unknown_camp_and_calling_are_reported(rs):
    c = _illuminated(rs).model_copy(update={"camp": "nowhere", "calling": "nobody"})
    assert _codes(validate.check_camp_and_calling(rs, c)) == \
        {"camp-required", "calling-required"}


def test_a_calling_must_belong_to_the_chosen_camp(rs):
    """p.90-92: the Tabernacle's three Callings are not on offer at Kether Rock."""
    c = _illuminated(rs, camp="kether-rock").model_copy(update={"calling": "exemplar"})
    assert "calling-wrong-camp" in _codes(validate.check_camp_and_calling(rs, c))


def test_a_standard_solar_may_not_have_a_camp_or_calling(rs):
    c = Character(id="s", name="Std", exalt_type="Solar", caste="dawn",
                  camp="kether-rock", calling="deacon")
    assert _codes(validate.check_camp_and_calling(rs, c)) == \
        {"camp-not-supported", "calling-not-supported"}


# --------------------------------------------------------- camp ability floors

def test_camp_ability_floor_is_enforced_through_validate_chargen(rs):
    """The camp's floors join the same union the caste's do, so they surface as the
    existing `required-min-ability` code rather than a new one."""
    short = _illuminated(rs, abilities={AB.SURVIVAL: 1})       # Kether wants Survival 3
    codes = _codes(validate.validate_chargen(rs, short))
    assert "required-min-ability" in codes
    assert "required-min-ability" not in _codes(validate.validate_chargen(rs, _illuminated(rs)))


def test_kether_rock_accepts_archery_or_brawl(rs):
    """"Either Archery • or Brawl •" — satisfying either is enough, neither is not."""
    with_archery = _illuminated(rs, abilities={AB.BRAWL: 0, AB.ARCHERY: 1})
    assert "required-min-ability" not in _codes(validate.validate_chargen(rs, with_archery))

    with_neither = _illuminated(rs, abilities={AB.BRAWL: 0, AB.ARCHERY: 0})
    assert "required-min-ability" in _codes(validate.validate_chargen(rs, with_neither))


def test_tabernacle_floors_differ_from_kether_rock(rs):
    """A character built for Kether Rock fails the Tabernacle's regimen and vice
    versa — proof the floor follows the camp, not the origin."""
    tab_granted = rs.camps["sequestered-tabernacle"].granted_charms + [
        "solar.martial-arts.snake-form", "solar.martial-arts.striking-cobra-technique"]
    swapped = _illuminated(rs, camp="sequestered-tabernacle", calling="exemplar",
                           granted_charms=tab_granted)
    assert "required-min-ability" in _codes(validate.validate_chargen(rs, swapped))


# ------------------------------------------------------------- granted Charms

def test_granted_package_must_include_every_fixed_grant(rs):
    c = _illuminated(rs, granted_charms=["solar.resistance.durability-of-oak-meditation",
                                         "solar.resistance.iron-skin-concentration"])
    assert "granted-charm-missing" in _codes(validate.granted_charm_issues(rs, c))


def test_kether_rock_pair_must_be_taken_whole(rs):
    """One of the printed pairs, all-or-nothing — half a pair resolves nothing."""
    camp = rs.camps["kether-rock"]
    half = _illuminated(rs, granted_charms=camp.granted_charms + ["solar.dodge.reed-in-the-wind"])
    codes = _codes(validate.granted_charm_issues(rs, half))
    assert "granted-charm-choice-unresolved" in codes


def test_power_combat_variant_pair_is_also_legal(rs):
    """Durability of Oak + Spirit Strengthens the Skin is the Power Combat form of the
    Durability of Oak + Iron Skin pair (p.90); both are authored, both must pass."""
    camp = rs.camps["kether-rock"]
    for second in ("solar.resistance.iron-skin-concentration",
                   "solar.resistance.spirit-strengthens-the-skin"):
        c = _illuminated(rs, granted_charms=camp.granted_charms + [
            "solar.resistance.durability-of-oak-meditation", second],
            abilities={AB.RESISTANCE: 3})
        assert _codes(validate.granted_charm_issues(rs, c)) == set(), second


def test_extra_charms_in_the_package_are_rejected(rs):
    camp = rs.camps["kether-rock"]
    c = _illuminated(rs, granted_charms=camp.granted_charms + [
        "solar.dodge.reed-in-the-wind", "solar.dodge.shadow-over-water",
        "solar.melee.golden-essence-block"])
    assert "granted-charm-extra" in _codes(validate.granted_charm_issues(rs, c))


def test_tabernacle_style_charms_must_come_from_one_style(rs):
    """"two Charms from ONE of the following four martial arts" (p.90). Only Snake
    Style exists in the Solar data today, so a legal pick is two Snake Charms."""
    camp = rs.camps["sequestered-tabernacle"]
    snake = [c.id for c in rs.charms.values() if c.category == "martial_arts:snake"][:2]
    ok = _illuminated(rs, camp="sequestered-tabernacle", calling="exemplar",
                      granted_charms=camp.granted_charms + snake,
                      abilities={AB.MARTIAL_ARTS: 5, AB.PRESENCE: 3},
                      essence_rating=3)
    assert "granted-charm-choice-unresolved" not in _codes(validate.granted_charm_issues(rs, ok))

    one_only = _illuminated(rs, camp="sequestered-tabernacle", calling="exemplar",
                            granted_charms=camp.granted_charms + snake[:1],
                            abilities={AB.MARTIAL_ARTS: 5, AB.PRESENCE: 3})
    assert "granted-charm-choice-unresolved" in _codes(validate.granted_charm_issues(rs, one_only))


def test_a_granted_charm_still_needs_its_own_minima(rs):
    """p.90: "As usual, the Solar must meet the minimum requirements to gain these
    Charms." The package exempts a Charm from the POOL, not from its requirements."""
    camp = rs.camps["kether-rock"]
    # Shadow Over Water requires Dodge 3; the Reed in the Wind pair is otherwise legal.
    c = _illuminated(rs, granted_charms=camp.granted_charms + [
        "solar.dodge.reed-in-the-wind", "solar.dodge.shadow-over-water"],
        abilities={AB.DODGE: 0})
    assert "granted-charm-minimum" in _codes(validate.granted_charm_issues(rs, c))
    # With Dodge 3 the very same package is clean.
    ok = _illuminated(rs, granted_charms=camp.granted_charms + [
        "solar.dodge.reed-in-the-wind", "solar.dodge.shadow-over-water"],
        abilities={AB.DODGE: 3})
    assert _codes(validate.granted_charm_issues(rs, ok)) == set()


def test_granted_charms_do_not_count_against_the_charm_pool(rs):
    """8 picks (p.90) plus 4 granted. The granted ones must cost no bonus points."""
    c = _illuminated(rs)
    assert len(c.granted_charms) == 4
    assert c.charms == []
    bp = validate.bonus_point_breakdown(rs, c)
    charm_line = next(l for l in bp.lines if l.domain == "Charms & Spells")
    assert charm_line.points == 0


def test_granted_charms_are_rejected_without_a_camp(rs):
    c = Character(id="s", name="Std", exalt_type="Solar", caste="dawn",
                  granted_charms=["solar.endurance.ox-body-technique"])
    assert "granted-charm-not-supported" in _codes(validate.granted_charm_issues(rs, c))


# ---------------------------------------------------------- Essence ceiling

def test_essence_may_not_exceed_five_at_creation(rs):
    """p.90: starts at 3, may be raised with bonus points, never begins at 6+."""
    assert "essence-above-chargen-cap" not in _codes(
        validate.validate_chargen(rs, _illuminated(rs, essence_rating=5)))
    assert "essence-above-chargen-cap" in _codes(
        validate.validate_chargen(rs, _illuminated(rs, essence_rating=6)))


def test_essence_below_three_is_still_below_start(rs):
    assert "essence-below-start" in _codes(
        validate.validate_chargen(rs, _illuminated(rs, essence_rating=2)))


# ------------------------------------------------- free Illumination dot

def test_illumination_first_dot_costs_no_pool_dots(rs):
    """p.90: nine dots, and Illumination • free "in addition"."""
    rule = rs.budgets_for("Solar", "illuminated").background_rules["illumination"]
    assert validate.background_pool_dots(rule, 1) == 0     # granted
    assert validate.background_pool_dots(rule, 3) == 2     # dots 2-3 paid
    # A Background with no rule pays for every dot, unchanged.
    assert validate.background_pool_dots(None, 3) == 3


def test_alchemical_class_dots_are_still_paid_for(rs):
    """Regression guard: free_rating defaults to 0, so the Alchemical Class ••• grant
    (mandatory but paid out of the pool) keeps costing three dots."""
    rule = rs.budgets_for("Alchemical").background_rules["class"]
    assert validate.background_pool_dots(rule, 3) == 3


# ============================================================================ #
# Phase 2/3 — Calling discounts (BP and XP)
# ============================================================================ #

def test_calling_abilities_are_not_favored_abilities(rs):
    """The Calling is a separate axis: it discounts, it does not make an Ability
    Favored, so it must not feed the Caste/Favoured dot minimum."""
    c = _illuminated(rs)                                    # Deacon
    calling = validate.calling_abilities(rs, c)
    assert AB.STEALTH in calling                            # a Deacon Calling Ability
    assert AB.STEALTH not in validate.caste_favored_abilities(rs, c)


def test_calling_ability_bp_rate_is_one_per_dot(rs):
    """p.93 table: Ability 2, "1 if Favored or Caste or Calling Ability". Deacon's
    Calling Abilities are Investigation/Larceny/Melee/Stealth/Survival; Stealth is
    neither Caste (Dawn) nor Favored here, so it is the Calling-only tier."""
    over = {AB.STEALTH: 3}                                  # pushes past the 30-dot pool
    base = _illuminated(rs, abilities={**{AB.SURVIVAL: 3}, **over},
                        favored_abilities=[])
    line = next(l for l in validate.bonus_point_breakdown(rs, base).lines
                if l.domain == "Abilities")
    # 13 dots spent, pool is 30 — nothing overflows, so no BP either way. The rate is
    # asserted directly below instead; this pins that a Calling Ability is free within
    # the pool exactly like any other.
    assert line.points == 0


def test_calling_and_caste_ability_dots_cost_one_bp_per_two_rounding_up(rs):
    """p.93: "1 for 2 if both a Calling Ability and a Favored or Caste Ability".
    Rounds UP (rules-authority call, 2026-07-24). Melee is both a Dawn Caste Ability
    and a Deacon Calling Ability, so its dots are the fractional tier."""
    bp = rs.bonus_costs_for("Solar")
    assert bp.calling_ability == 1
    assert bp.calling_ability_favored_caste_dots_per_point == 2
    assert bp.calling_charm == 4
    assert bp.calling_charm_favored_caste == 3

    # Above the pre-BP cap of 3, dots always cost BP — the cleanest way to observe the
    # tier. Melee 5 = 2 dots above the cap in the 'both' tier => ceil(2/2) = 1 BP.
    c = _illuminated(rs, abilities={AB.MELEE: 5})
    line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                if l.domain == "Abilities")
    assert line.points == 1

    # Melee 4 = 1 dot above the cap => ceil(1/2) = 1 BP, i.e. rounds UP not down.
    c4 = _illuminated(rs, abilities={AB.MELEE: 4})
    line4 = next(l for l in validate.bonus_point_breakdown(rs, c4).lines
                 if l.domain == "Abilities")
    assert line4.points == 1


def test_a_non_calling_non_caste_ability_still_costs_the_full_rate(rs):
    """Regression: Sail is neither Dawn Caste nor a Deacon Calling Ability, so its
    above-cap dots cost the undiscounted 2 BP each."""
    c = _illuminated(rs, abilities={AB.SAIL: 5}, favored_abilities=[])
    line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                if l.domain == "Abilities")
    assert line.points == 2 * 2


def test_calling_charm_bp_is_four_or_three(rs):
    """p.90: "purchasing a Calling Charm costs 4 freebies, 3 if Favored or Caste"."""
    # Ten Magistrate Eyes is a Deacon Calling Charm gated on Investigation.
    charm_id = "solar.investigation.ten-magistrate-eyes"
    assert charm_id in rs.callings["deacon"].charms

    # 9 picks against a pool of 8 => exactly one pick is paid for, and because
    # pick_costs sorts dearest-first into the free pool, the CHEAPEST pick is the one
    # charged. Compare two builds whose 9th Charm differs only in Calling membership:
    # a Calling Charm costs 4, an ordinary one 5, so the delta must be exactly 1.
    dawn_cats = {a.value for a in rs.castes["dawn"].caste_abilities}
    deacon = set(rs.callings["deacon"].charms)

    def bp_for(ninth):
        # Every filler must cost the SAME full 5 BP, so the cheapest pick — the one the
        # free pool leaves unpaid — is deterministically the 9th Charm. That means
        # excluding both Dawn Caste categories and Deacon Calling Charms from fillers.
        fillers = [x.id for x in rs.charms.values()
                   if x.exalt_type == "Solar" and x.min_ability <= 1
                   and x.min_essence <= 3 and x.id != ninth
                   and x.category not in dawn_cats
                   and x.id not in deacon
                   and not x.category.startswith("martial_arts")][:8]
        assert len(fillers) == 8
        c = _illuminated(rs, charms=fillers + [ninth],
                         abilities={AB.INVESTIGATION: 5, AB.SURVIVAL: 3})
        return next(l.points for l in validate.bonus_point_breakdown(rs, c).lines
                    if l.domain == "Charms & Spells")

    # Any ordinary (non-Calling) Solar Charm in a non-Dawn-Caste category, so both
    # sides of the comparison are in the same Caste/Favoured bucket.
    ordinary = next(x.id for x in rs.charms.values()
                    if x.exalt_type == "Solar" and x.min_ability <= 1
                    and x.min_essence <= 3
                    and x.category not in dawn_cats
                    and not x.category.startswith("martial_arts")
                    and x.id not in deacon)
    assert bp_for(charm_id) == bp_for(ordinary) - 1


def test_calling_ability_xp_discount_stacks_with_caste_favored(rs):
    """p.102 worked example: the fourth dot of a Calling Ability, normally 6 XP, costs
    5 — or 4 if the Ability is also Favored or Caste."""
    c = _illuminated(rs)                                    # Dawn / Deacon
    # Stealth: Calling only (Dawn Caste is Archery/Brawl/MA/Melee/Thrown).
    assert costs.ability_step(rs, c, AB.STEALTH, 3) == 5
    # Melee: Calling AND Dawn Caste => both discounts.
    assert costs.ability_step(rs, c, AB.MELEE, 3) == 4
    # Sail: neither => the undiscounted 6.
    assert costs.ability_step(rs, c, AB.SAIL, 3) == 6


def test_calling_charm_xp_discount_stacks_with_caste_favored(rs):
    """p.102: "a Calling Charm costs 8 experience points, or 6 if Favored or Caste"."""
    c = _illuminated(rs)
    calling_charm = rs.charms["solar.investigation.ten-magistrate-eyes"]
    assert costs.charm_cost(rs, c, calling_charm) == 8      # Investigation: not Dawn

    # No Deacon Calling Charm happens to sit in a Dawn Caste category, so the
    # stacking case uses Zenith + Paladin: Performance is both a Zenith Caste Ability
    # and the category of several Paladin Calling Charms.
    zenith = _illuminated(rs, caste="zenith", calling="paladin",
                          abilities={AB.PERFORMANCE: 3})
    perf = next(rs.charms[cid] for cid in rs.callings["paladin"].charms
                if rs.charms[cid].category == "performance")
    assert costs.charm_cost(rs, zenith, perf) == 6


def test_a_standard_solar_gets_no_calling_discounts(rs):
    """Regression: the discount fires only for a character WITH a Calling, so every
    existing Solar is priced exactly as before."""
    std = Character(id="s", name="Std", exalt_type="Solar", caste="dawn")
    assert validate.calling_abilities(rs, std) == set()
    # Melee is a Dawn Caste Ability, so the Caste discount alone gives 5; Sail gets
    # neither discount and stays at the full 6. Neither moves without a Calling.
    assert costs.ability_step(rs, std, AB.MELEE, 3) == 5
    assert costs.ability_step(rs, std, AB.SAIL, 3) == 6
    charm = rs.charms["solar.investigation.ten-magistrate-eyes"]
    assert costs.charm_cost(rs, std, charm) == 10


# ============================================================================ #
# Charms (p.100-106) — 20 Charms across 6 Abilities plus Falling Blossom Style
# ============================================================================ #

_ILL_BOOK = "Exalted 1e Cult of the Illuminated"


def _ill_charms(rs):
    return [c for c in rs.charms.values() if c.source.book == _ILL_BOOK]


def test_twenty_charms_authored_from_this_book(rs):
    """The chapter has 21 headings, but FALLING BLOSSOM STYLE is the style's preamble
    (no Cost/Duration block), not a Charm — so 20."""
    got = _ill_charms(rs)
    assert len(got) == 20
    by_cat = {}
    for c in got:
        by_cat[c.category] = by_cat.get(c.category, 0) + 1
    assert by_cat == {"brawl": 5, "endurance": 1, "linguistics": 1,
                      "martial_arts:falling-blossom": 7, "presence": 4,
                      "survival": 1, "socialize": 1}


def test_every_new_charm_carries_its_page(rs):
    for c in _ill_charms(rs):
        assert c.source.page is not None, c.id
        assert 100 <= c.source.page <= 106, (c.id, c.source.page)


def test_brawl_cascade_resolves_to_an_existing_corebook_root(rs):
    """The Brawl tree hangs off corebook Charms: Inevitable Victory Meditation needs
    Fists of Iron Technique, and Irrepressible Bravery Tactic needs Thunderclap Rush
    Attack. (The page prints "Fist of Iron Technique" — a typo for the corebook
    "Fists of Iron Technique", which is what the id points at.)"""
    ivm = rs.charms["solar.brawl.inevitable-victory-meditation"]
    assert ivm.prerequisites == [["solar.brawl.fists-of-iron-technique"]]
    ibt = rs.charms["solar.brawl.irrepressible-bravery-tactic"]
    assert ibt.prerequisites == [["solar.brawl.thunderclap-rush-attack"]]

    # Supremacy of War Method needs BOTH of the above branches (AND, two groups).
    sow = rs.charms["solar.brawl.supremacy-of-war-method"]
    assert sow.prerequisites == [["solar.brawl.inevitable-victory-meditation"],
                                 ["solar.brawl.dancing-with-strife-technique"]]


def test_ascendant_battle_visage_crosses_into_endurance(rs):
    """Its prerequisites span two trees — Supremacy of War Method (Brawl) and
    Bloodthirsty Sword-Dancer Spirit (Endurance) — as two AND groups."""
    c = rs.charms["solar.brawl.ascendant-battle-visage"]
    assert c.prerequisites == [["solar.brawl.supremacy-of-war-method"],
                              ["solar.endurance.bloodthirsty-sword-dancer-spirit"]]
    assert c.min_essence == 4


def test_ascendant_battle_visage_has_a_second_ability_minimum(rs):
    """p.102 gives this Charm TWO Ability minimums: "Minimum Brawl: 5 / Minimum
    Endurance: 5". Brawl is the primary gate (it is the Charm's category); Endurance
    lives in `extra_min_abilities`. The description carries no note about it — the
    field is the record now."""
    c = rs.charms["solar.brawl.ascendant-battle-visage"]
    assert c.min_ability == 5
    assert [(list(r.abilities), r.rating) for r in c.extra_min_abilities] == \
        [([AB.ENDURANCE], 5)]
    assert "Minimum Endurance" not in c.description


def test_extra_min_abilities_is_empty_for_every_other_charm(rs):
    """Multi-gate Charms are rare enough that each new one has to be deliberate."""
    multi = sorted(c.id for c in rs.charms.values() if c.extra_min_abilities)
    assert multi == [
        # Aspect Book: Air p.68 — "Minimum Craft: 4 / Minimum Linguistics: 1". Craft is
        # the primary gate (it is the Charm's category and what pricing keys off).
        "dragonblooded.craft.diligent-engineer-discipline",
        # Aspect Book: Fire — "Minimum Dodge: 4 / Minimum Melee: 4", two gates at the
        # same rating; Melee is primary because that is the section it is printed in.
        "dragonblooded.melee.style-countering-meditation",
        # Aspect Book: Air — "Minimum Stealth: 4 / Minimum Larceny: 2".
        "dragonblooded.stealth.empty-hand-posture",
        # God-Blooded (PG p.48) — "Essence 3 and Occult 5 to undergo the Terrestrial
        # initiation": the necromancy initiation groups with the Arcanoi on the
        # General Arcanoi page, so Occult is its ONLY ability gate and lives here.
        "godblooded.general-arcanoi.shadowlands-circle-necromancy",
        "solar.brawl.ascendant-battle-visage",
        # Caste Book: Eclipse p.73 — "Minimum Linguistics: 5 / Minimum Lore: 3".
        "solar.linguistics.masterful-training-manual",
        # Caste Book: Zenith p.78 — "Minimum Performance: 5 / Minimum Presence: 3".
        "solar.performance.impenetrable-identity",
        # Caste Book: Zenith p.73-74 — the two drink-fuelled Resistance Charms each
        # print a second "Minimum Performance" line.
        "solar.resistance.drunken-warrior-technique",
        "solar.resistance.inebriated-fool-defense",
        # God-Blooded (PG p.48) — the sorcery half of the same sentence that gates the
        # necromancy initiation above: "Characters must also have Essence 3 and Occult 5
        # to undergo the Terrestrial initiation." It sits in the Virtue-keyed spirit
        # catalogue but is the one member with no Virtue, so Occult is its only ability
        # gate and rides here for the same reason the necromancy one does.
        "spirit.spirit-templates.terrestrial-circle-sorcery",
    ]


def test_falling_blossom_is_a_terrestrial_style_open_to_every_splat(rs):
    """p.102: "Falling Blossom Style is a Terrestrial Style, and thus, Dragon-Blooded
    may learn it at no penalty, and mortals with the Essence Mastery Merit ... may also
    learn it." That is exactly what `open_to_all` means in this project."""
    style = [c for c in rs.charms.values() if c.category == "martial_arts:falling-blossom"]
    assert len(style) == 7
    assert all(c.open_to_all for c in style), [c.id for c in style if not c.open_to_all]
    # It is NOT one of the four styles the Tabernacle's free package draws from (p.90).
    (choice,) = rs.camps["sequestered-tabernacle"].granted_charm_choices
    assert "martial_arts:falling-blossom" not in choice.from_categories


def test_falling_blossom_cascade_is_self_contained(rs):
    """Every prerequisite in the style points inside the style — it has one root
    (Living Shield Technique) and needs no corebook Charm."""
    style = {c.id: c for c in rs.charms.values()
             if c.category == "martial_arts:falling-blossom"}
    for c in style.values():
        for group in c.prerequisites:
            for pid in group:
                assert pid in style, (c.id, pid)
    roots = [c.id for c in style.values() if not c.prerequisites]
    assert roots == ["solar.martial-arts.living-shield-technique"]


def test_falling_blossom_form_is_the_style_form_charm(rs):
    form = rs.charms["solar.martial-arts.falling-blossom-form"]
    assert form.type.value == "Simple"
    assert form.min_ability == 4
    assert form.prerequisites == [["solar.martial-arts.undefended-assault-method"],
                                 ["solar.martial-arts.dual-scarlet-blossom-technique"]]
    # Both capstones branch off the Form.
    for cap in ("purity-of-purpose-attack", "strength-of-faith-meditation"):
        assert rs.charms[f"solar.martial-arts.{cap}"].prerequisites == \
            [["solar.martial-arts.falling-blossom-form"]]


def test_variable_costs_keep_the_flat_component_at_zero(rs):
    """`cost.raw` is authoritative for a variable cost, and the numeric fields hold only
    the FLAT part — so a "per die"/"per success" Charm has 0 motes, not 1."""
    per_success = rs.charms["solar.brawl.irrepressible-bravery-tactic"]
    assert per_success.cost.raw == "3 motes per success"
    assert per_success.cost.motes == 0

    per_die = rs.charms["solar.martial-arts.strength-of-faith-meditation"]
    assert per_die.cost.raw == "1 mote per die, 1 Willpower"
    assert (per_die.cost.motes, per_die.cost.willpower) == (0, 1)

    # Dual Scarlet Blossom spends health levels per die too — also variable, so 0.
    dual = rs.charms["solar.martial-arts.dual-scarlet-blossom-technique"]
    assert dual.cost.raw == "1 mote and 1 health level per die, 1 Willpower"
    assert (dual.cost.motes, dual.cost.health) == (0, 0)


def test_committed_essence_charms_are_flagged(rs):
    """Two of these commit Essence for their duration rather than spending it:
    Supremacy of War Method holds motes until spent as dice, and Excellent Emissary's
    Tongue holds them for as long as the language is known."""
    assert rs.charms["solar.brawl.supremacy-of-war-method"].cost.committed
    assert rs.charms["solar.linguistics.excellent-emissarys-tongue"].cost.committed
    # And a Charm that merely spends motes is not flagged.
    assert not rs.charms["solar.presence.prey-freezing-gaze"].cost.committed


def test_presence_cascade_chains_off_corebook_charms(rs):
    p = "solar.presence."
    assert rs.charms[p + "prey-freezing-gaze"].prerequisites == \
        [[p + "harmonious-presence-meditation"]]
    assert rs.charms[p + "soul-shaping-words-technique"].prerequisites == \
        [[p + "listener-swaying-argument"]]
    assert rs.charms[p + "true-harmony-revelation"].prerequisites == \
        [[p + "soul-shaping-words-technique"]]
    assert rs.charms[p + "horizon-to-horizon-presence-method"].prerequisites == \
        [[p + "hypnotic-tongue-technique"], [p + "terrifying-apparition-of-glory"]]


def test_the_five_previously_missing_calling_charms_now_resolve(rs):
    """These five were referenced by callings.json but absent from `data/`; authoring
    the chapter closed the gap. Asserted by id so a rename cannot silently reopen it."""
    for cid in ("solar.presence.prey-freezing-gaze",
                "solar.linguistics.excellent-emissarys-tongue",
                "solar.endurance.tireless-travelers-stamina",
                "solar.socialize.graceful-courtier-attitude",
                "solar.survival.game-snaring-huntsmans-method"):
        assert cid in rs.charms, cid
        assert any(cid in c.charms for c in rs.callings.values()), cid


def test_a_calling_charm_from_this_book_is_priced_at_the_calling_rate(rs):
    """End-to-end: Prey-Freezing Gaze is an Inquisitor Calling Charm, and Presence is
    not a Dawn Caste Ability, so it costs the undiscounted-Caste Calling rate of 8."""
    inquisitor = _illuminated(rs, camp="sequestered-tabernacle", calling="inquisitor",
                              granted_charms=rs.camps["sequestered-tabernacle"].granted_charms
                              + [c.id for c in rs.charms.values()
                                 if c.category == "martial_arts:snake"][:2],
                              abilities={AB.MARTIAL_ARTS: 5, AB.PRESENCE: 3})
    charm = rs.charms["solar.presence.prey-freezing-gaze"]
    assert costs.charm_cost(rs, inquisitor, charm) == 8


# ============================================================================ #
# Multi-gate Charms — the shared trait-minimum helper
# ============================================================================ #

def _brawler(rs, brawl, endurance):
    """A Solar holding Ascendant Battle Visage's whole prerequisite chain, so the only
    thing under test is the pair of Ability minimums."""
    return Character(
        id="mg", name="Multi", exalt_type="Solar", caste="dawn", essence_rating=4,
        abilities={AB.BRAWL: brawl, AB.ENDURANCE: endurance},
        charms=["solar.brawl.fists-of-iron-technique",
                "solar.brawl.thunderclap-rush-attack",
                "solar.brawl.inevitable-victory-meditation",
                "solar.brawl.irrepressible-bravery-tactic",
                "solar.brawl.dancing-with-strife-technique",
                "solar.brawl.supremacy-of-war-method",
                "solar.endurance.bloodthirsty-sword-dancer-spirit",
                "solar.brawl.ascendant-battle-visage"],
    )


def test_shortfalls_reports_the_primary_gate(rs):
    c = _brawler(rs, brawl=3, endurance=5)
    charm = rs.charms["solar.brawl.ascendant-battle-visage"]
    assert validate.charm_ability_shortfalls(c, charm) == [("brawl", 5, 3)]


def test_shortfalls_reports_the_extra_gate(rs):
    """The whole point: Brawl 5 alone is no longer enough."""
    c = _brawler(rs, brawl=5, endurance=2)
    charm = rs.charms["solar.brawl.ascendant-battle-visage"]
    assert validate.charm_ability_shortfalls(c, charm) == [("endurance", 5, 2)]


def test_shortfalls_reports_both_when_both_fail(rs):
    c = _brawler(rs, brawl=1, endurance=1)
    charm = rs.charms["solar.brawl.ascendant-battle-visage"]
    assert validate.charm_ability_shortfalls(c, charm) == [("brawl", 5, 1), ("endurance", 5, 1)]


def test_shortfalls_is_empty_when_both_are_met(rs):
    c = _brawler(rs, brawl=5, endurance=5)
    charm = rs.charms["solar.brawl.ascendant-battle-visage"]
    assert validate.charm_ability_shortfalls(c, charm) == []


def test_all_three_engine_gates_honour_the_extra_minimum(rs):
    """The three places that check trait minimums now share one helper, so all three
    must agree. Before the field existed each compared `min_ability` by hand, which is
    exactly how a fourth call site would have diverged."""
    charm = rs.charms["solar.brawl.ascendant-battle-visage"]
    short = _brawler(rs, brawl=5, endurance=2)
    ok = _brawler(rs, brawl=5, endurance=5)

    # 1. the picker's forward-looking eligibility check
    assert not validate.meets_charm_requirements(rs, short, charm)
    assert validate.meets_charm_requirements(rs, ok, charm)

    # 2. the owned-Charm audit
    codes = [i.code for i in validate.check_charm_prerequisites(rs, short)]
    assert "charm-min-ability" in codes
    assert "charm-min-ability" not in [
        i.code for i in validate.check_charm_prerequisites(rs, ok)]

    # 3. the granted-Charm package check (reached via a camp that grants it)
    camp = rs.camps["kether-rock"]
    granted = _illuminated(rs, granted_charms=camp.granted_charms + [
        "solar.dodge.reed-in-the-wind", "solar.dodge.shadow-over-water",
        "solar.brawl.ascendant-battle-visage"],
        abilities={AB.DODGE: 3, AB.BRAWL: 5, AB.ENDURANCE: 2}, essence_rating=4)
    msgs = [i.message for i in validate.granted_charm_issues(rs, granted)
            if i.code == "granted-charm-minimum"]
    assert any("endurance 5" in m for m in msgs), msgs


def test_or_semantics_work_inside_an_extra_minimum(rs):
    """`extra_min_abilities` reuses AbilityMinimum, so an entry can be an OR — each
    entry is an independent AND whose members are alternatives. No Charm needs this
    yet; the shape is asserted so the infrastructure is known to support it."""
    from exalted_builder.models.rules import AbilityMinimum
    charm = rs.charms["solar.brawl.ascendant-battle-visage"].model_copy(
        update={"extra_min_abilities": [
            AbilityMinimum(abilities=[AB.MELEE, AB.THROWN], rating=3)]})

    neither = _brawler(rs, brawl=5, endurance=5)
    assert validate.charm_ability_shortfalls(neither, charm) == [("melee or thrown", 3, 0)]

    with_melee = neither.model_copy(update={
        "abilities": {**neither.abilities, AB.MELEE: 3}})
    assert validate.charm_ability_shortfalls(with_melee, charm) == []

    with_thrown = neither.model_copy(update={
        "abilities": {**neither.abilities, AB.THROWN: 4}})
    assert validate.charm_ability_shortfalls(with_thrown, charm) == []


def test_extra_minimum_does_not_affect_pricing_or_favored_ness(rs):
    """The extra gate is a REQUIREMENT only. A Zenith Solar has Endurance as a Caste
    Ability, but Ascendant Battle Visage is a Brawl Charm and must stay full price —
    the second gate must never leak into the discount logic."""
    zenith = Character(id="z", name="Z", exalt_type="Solar", caste="zenith",
                       essence_rating=4)
    dawn = Character(id="d", name="D", exalt_type="Solar", caste="dawn",
                     essence_rating=4)
    charm = rs.charms["solar.brawl.ascendant-battle-visage"]
    assert costs.charm_cost(rs, zenith, charm) == 10       # Brawl is not a Zenith Ability
    assert costs.charm_cost(rs, dawn, charm) == 8          # Brawl IS a Dawn Ability


def test_requirements_list_is_ordered_primary_then_extras(rs):
    charm = rs.charms["solar.brawl.ascendant-battle-visage"]
    assert validate.charm_ability_requirements(charm) == [("brawl", 5), ("endurance", 5)]
    # A single-gate Charm is unchanged.
    assert validate.charm_ability_requirements(
        rs.charms["solar.brawl.dancing-with-strife-technique"]) == [("brawl", 3)]
    # An Attribute-keyed Charm still reports its Attribute.
    lunar = next(c for c in rs.charms.values() if c.min_attribute)
    assert validate.charm_ability_requirements(lunar)[0][0] == lunar.min_attribute


def test_the_detail_card_shows_every_requirement(rs):
    """view.build_charm_detail must list both gates, or a player sees only half of
    what the Charm needs."""
    from exalted_builder.ui import view
    c = _brawler(rs, brawl=5, endurance=5)
    detail = view.build_charm_detail(rs, c, "solar.brawl.ascendant-battle-visage")
    assert "Brawl 5" in detail.requirement
    assert "Endurance 5" in detail.requirement
    assert "Essence 4" in detail.requirement


# ============================================================================ #
# Phase 4 — presenters (toolkit-free; the render tests live in test_illuminated_ui)
# ============================================================================ #

def test_camp_view_is_none_without_a_camp_origin(rs):
    """The panel is gated on the origin's budget, so no other splat grows one."""
    from exalted_builder.ui import view
    for c in (Character(id="a", name="a", exalt_type="Solar", caste="dawn"),
              Character(id="b", name="b", exalt_type="Lunar", caste="full-moon"),
              Character(id="c", name="c", exalt_type="Sidereal", caste="battles")):
        assert view.build_camp_view(rs, c) is None, c.exalt_type
    assert not view.requires_camp(rs, Character(id="d", name="d", exalt_type="Solar",
                                                caste="dawn"))


def test_camp_view_offers_both_camps_and_the_chosen_camps_callings(rs):
    from exalted_builder.ui import view
    v = view.build_camp_view(rs, _illuminated(rs))
    assert [cid for cid, _ in v.camp_options] == ["sequestered-tabernacle", "kether-rock"]
    # Callings are scoped to the CHOSEN camp, not to the origin.
    assert [cid for cid, _ in v.calling_options] == ["architect", "deacon", "paladin"]
    assert v.calling_label == "Deacon"
    assert v.calling_abilities == ["Investigation", "Larceny", "Melee", "Stealth", "Survival"]


def test_camp_view_renders_the_or_minimum_as_one_line(rs):
    from exalted_builder.ui import view
    v = view.build_camp_view(rs, _illuminated(rs))
    assert "Archery or Brawl 1" in v.minimums
    assert "Survival 3" in v.minimums


def test_camp_view_marks_the_taken_pair_as_chosen(rs):
    """The default fixture takes Durability of Oak + Iron Skin, so that option — and
    only that option — is the resolved one."""
    from exalted_builder.ui import view
    (choice,) = view.build_camp_view(rs, _illuminated(rs)).choices
    assert not choice.is_category_choice
    labels = {o.key: o.label for o in choice.options}
    assert choice.chosen_key in labels
    assert labels[choice.chosen_key] == "Durability of Oak Meditation + Iron Skin Concentration"
    assert len(choice.options) == 5


def test_camp_view_lists_all_four_styles_with_readable_labels(rs):
    """A closed ui.select never puts its options in the DOM, so the option LABELS are
    asserted here rather than in a render test. All four styles are authored: Snake
    (core), Tiger (Caste Book: Dawn p.73-74), Praying Mantis (Caste Book: Eclipse
    p.73-75) and Ebon Shadow (Caste Book: Night p.67-70)."""
    from exalted_builder.ui import view
    tab = _illuminated(rs, camp="sequestered-tabernacle", calling="exemplar",
                       granted_charms=rs.camps["sequestered-tabernacle"].granted_charms)
    (choice,) = view.build_camp_view(rs, tab).choices
    assert choice.is_category_choice
    assert choice.pick == 2
    assert [o.label for o in choice.options] == [
        "Ebon Shadow Style", "Praying Mantis Style", "Snake Style", "Tiger Style"]
    pools = {o.label: len(o.charm_ids) for o in choice.options}
    assert pools == {"Ebon Shadow Style": 11, "Praying Mantis Style": 10,
                     "Snake Style": 10, "Tiger Style": 9}
    assert choice.chosen_key == ""            # nothing taken, so unresolved


def test_calling_marks_and_charm_tag_presenters(rs):
    from exalted_builder.ui import view
    c = _illuminated(rs)
    marks = view.calling_ability_marks(rs, c)
    assert AB.STEALTH in marks and AB.MELEE in marks
    assert AB.SAIL not in marks
    assert view.is_calling_charm(rs, c, "solar.investigation.ten-magistrate-eyes")
    assert not view.is_calling_charm(rs, c, "solar.brawl.ferocious-jab")


def test_granted_charm_rows_are_built_for_the_sheet(rs):
    from exalted_builder.ui import view
    rows = view.granted_charm_rows(rs, _illuminated(rs))
    assert [r.name for r in rows] == [
        "Ox-Body Technique", "Hardship-Surviving Mendicant Spirit",
        "Durability of Oak Meditation", "Iron Skin Concentration"]


def test_sheet_view_labels_granted_charms_and_keeps_picks_separate(rs):
    """`granted_charms` is a FOURTH list outside `character.charms` (after ox_body and
    beastman_gifts), so the sheet has to enumerate it explicitly — the same miss
    Beastman Gifts had. Labelled so a granted Charm is not read as a spent pick."""
    from exalted_builder.ui import view
    c = _illuminated(rs, charms=["solar.brawl.ferocious-jab"],
                     abilities={AB.BRAWL: 3, AB.SURVIVAL: 3})
    names = [r.name for r in view.build_sheet_view(rs, c).charms]
    assert "Ferocious Jab" in names                       # a pick, unlabelled
    assert "Ox-Body Technique (granted)" in names
    assert sum("(granted)" in n for n in names) == 4


def test_the_editor_offers_the_illuminated_origin_for_solars():
    """The engine can be complete and the feature still unreachable. `_SPLAT_ORIGINS` is
    the editor's only route to an origin, so it is asserted here rather than left to a
    render test — and "standard" must fall back to the plain Solar budget row."""
    from exalted_builder.ui.editor import _SPLAT_ORIGINS
    origins = _SPLAT_ORIGINS["Solar"]
    assert list(origins) == ["standard", "illuminated"]
    assert origins["illuminated"] == "Cult of the Illuminated"


def test_every_origin_offered_by_the_editor_resolves_to_a_budget(rs):
    """A typo in _SPLAT_ORIGINS silently falls back to the splat's default budget, which
    looks like the feature simply not working. Assert each origin either has its own row
    or is the deliberate first/default key."""
    from exalted_builder.ui.editor import _SPLAT_ORIGINS
    for splat, origins in _SPLAT_ORIGINS.items():
        for i, key in enumerate(origins):
            # The God-Blooded "origins" are the Half-Caste's parent Exalt types; every
            # parent shares the single God-Blooded budget (the parent decides Charm
            # access, not the dot budget), so none of them needs its own row.
            if splat == "God-Blooded":
                continue
            keyed = rs.budgets.get(f"{splat}:{key}")
            assert keyed is not None or i == 0, (
                f"{splat}:{key} has no budget row and is not the default origin")


def test_switching_splat_clears_a_stale_camp(rs):
    """Regression: switching away from an Illuminated Solar used to leave `camp` set,
    which then reported camp-not-supported. Asserted through the engine because the
    editor setter is a closure."""
    c = _illuminated(rs)
    assert _codes(validate.check_camp_and_calling(rs, c)) == set()
    moved = c.model_copy(update={"exalt_type": "Lunar", "caste": "full-moon", "origin": ""})
    assert "camp-not-supported" in _codes(validate.check_camp_and_calling(rs, moved))
    cleared = moved.model_copy(update={"camp": "", "calling": "", "granted_charms": []})
    assert _codes(validate.check_camp_and_calling(rs, cleared)) == set()


def test_picking_the_illuminated_origin_seeds_a_legal_character(rs):
    """The bug the user hit was reachability: the engine was complete and the origin
    unselectable. The other half is that selecting it must leave the character LEGAL,
    not merely leave three more dropdowns to fill in — so the defaulting rule lives in
    the engine and is asserted here.

    (This replaced a UI click-through test that passed alone and failed in-suite; the
    behaviour it claimed to prove is verified deterministically instead.)"""
    fresh = Character(id="f", name="Fresh", exalt_type="Solar", caste="dawn",
                      origin="illuminated", essence_rating=3)
    camp, calling, granted = validate.default_camp_and_calling(rs, fresh)
    assert camp == "sequestered-tabernacle"          # the first camp offered
    assert calling == "exemplar"                     # its first Calling
    assert granted == list(rs.camps[camp].granted_charms)

    seeded = fresh.model_copy(update={"camp": camp, "calling": calling,
                                      "granted_charms": granted})
    assert _codes(validate.check_camp_and_calling(rs, seeded)) == set()


def test_seeding_is_idempotent_and_keeps_the_players_choices(rs):
    """Re-running the seed must not discard a resolved grant choice, or a body.refresh()
    would silently wipe the player's martial-arts pick."""
    c = _illuminated(rs)                              # Kether Rock, pair resolved
    before = list(c.granted_charms)
    camp, calling, granted = validate.default_camp_and_calling(rs, c)
    assert (camp, calling) == ("kether-rock", "deacon")
    assert granted == before


def test_seeding_clears_everything_for_an_origin_without_camps(rs):
    c = _illuminated(rs).model_copy(update={"origin": ""})
    assert validate.default_camp_and_calling(rs, c) == ("", "", [])


# ---------------------------------------------------- unpickable grant options

def test_all_four_tabernacle_styles_are_pickable(rs):
    """The Tabernacle offers four martial arts (p.90). Every one of them is authored
    now — Snake from the corebook, the other three from their castebooks — so all four
    must be LISTED and available. The unavailable/reason path is still exercised by
    test_a_partially_authored_style_reports_how_short_it_is below; it must keep working
    for whatever style is added next."""
    from exalted_builder.ui import view
    tab = _illuminated(rs, camp="sequestered-tabernacle", calling="exemplar",
                       granted_charms=rs.camps["sequestered-tabernacle"].granted_charms)
    (choice,) = view.build_camp_view(rs, tab).choices

    by_label = {o.label: o for o in choice.options}
    assert len(by_label) == 4
    for label in ("Ebon Shadow Style", "Praying Mantis Style", "Snake Style",
                  "Tiger Style"):
        assert by_label[label].available, label
        assert by_label[label].reason == "", label


def test_a_partially_authored_style_reports_how_short_it_is(rs):
    """A style with SOME but not enough Charms is a different failure from an empty one,
    and the reason must say which — otherwise the fix is a guess."""
    from exalted_builder.ui import view
    from exalted_builder.models.rules import GrantedCharmChoice

    one_snake = [c.id for c in rs.charms.values() if c.category == "martial_arts:snake"][:1]
    # A choice needing 2 from a category that only holds 1 authored Charm.
    fake_rs = rs.model_copy(deep=True)
    fake_rs.camps["sequestered-tabernacle"] = rs.camps["sequestered-tabernacle"].model_copy(
        update={"granted_charm_choices": [GrantedCharmChoice(
            label="Two Charms from one martial arts style", pick=2,
            from_categories=["martial_arts:solo"])]})
    fake_rs.charms[one_snake[0]] = rs.charms[one_snake[0]].model_copy(
        update={"category": "martial_arts:solo"})

    tab = _illuminated(rs, camp="sequestered-tabernacle", calling="exemplar",
                       granted_charms=rs.camps["sequestered-tabernacle"].granted_charms)
    (choice,) = view.build_camp_view(fake_rs, tab).choices
    (opt,) = choice.options
    assert not opt.available
    assert opt.reason == "only 1 Charm(s) authored, needs 2"


def test_fixed_set_options_are_all_available(rs):
    """Kether Rock's pairs are link-checked by the loader, so every option is takeable —
    availability is not a category-choice-only concept, it is just always True here."""
    from exalted_builder.ui import view
    (choice,) = view.build_camp_view(rs, _illuminated(rs)).choices
    assert all(o.available and o.reason == "" for o in choice.options)


def test_selecting_snake_style_resolves_the_choice(rs):
    """The positive case the user could reach: taking two Snake Charms marks the choice
    resolved, and the package validates clean."""
    from exalted_builder.ui import view
    camp = rs.camps["sequestered-tabernacle"]
    snake = sorted((c for c in rs.charms.values() if c.category == "martial_arts:snake"),
                   key=lambda c: (c.min_ability, c.min_essence, c.name))[:2]
    tab = _illuminated(rs, camp="sequestered-tabernacle", calling="exemplar",
                       granted_charms=list(camp.granted_charms) + [c.id for c in snake],
                       abilities={AB.MARTIAL_ARTS: 5, AB.PRESENCE: 3})
    (choice,) = view.build_camp_view(rs, tab).choices
    assert choice.chosen_key == "martial_arts:snake"
    assert _codes(validate.granted_charm_issues(rs, tab)) == set()


# ------------------------------------------ choosing WHICH Charms a style grants

def _tabernacle(rs, granted=None):
    """A Tabernacle character whose Martial Arts is high enough to reach most of a
    style, so the minimum-flagging is exercised rather than blanket-failing."""
    camp = rs.camps["sequestered-tabernacle"]
    return _illuminated(rs, camp="sequestered-tabernacle", calling="exemplar",
                        abilities={AB.MARTIAL_ARTS: 4},
                        granted_charms=granted if granted is not None
                        else list(camp.granted_charms))


def test_choosing_a_style_opens_a_second_control_for_which_charms(rs):
    """The Tabernacle package is "two Charms from ONE of four martial arts" (p.90).
    Choosing the STYLE is only half the choice — the player must also choose WHICH two,
    and before this the UI silently auto-picked them with no way to change it.

    `charm_options` is empty until a style is chosen, then lists that style's whole
    roster."""
    from exalted_builder.ui import view

    (before,) = view.build_camp_view(rs, _tabernacle(rs)).choices
    assert before.chosen_key == ""
    assert before.charm_options == []          # no style chosen yet -> no sub-choice

    camp = rs.camps["sequestered-tabernacle"]
    tab = _tabernacle(rs, granted=list(camp.granted_charms) + [
        "solar.martial-arts.crimson-leaping-cat-technique",
        "solar.martial-arts.striking-fury-claws-attack"])
    (after,) = view.build_camp_view(rs, tab).choices
    assert after.chosen_key == "martial_arts:tiger"
    assert after.pick == 2
    assert len(after.charm_options) == 9       # the whole Tiger roster is offered
    assert after.chosen_charm_ids == [
        "solar.martial-arts.crimson-leaping-cat-technique",
        "solar.martial-arts.striking-fury-claws-attack"]


def test_a_style_stays_chosen_while_only_one_of_its_charms_is_held(rs):
    """Regression: `chosen_key` used to require `pick` Charms already held, so emptying
    the sub-select to one Charm made the style look unchosen — which removed the
    sub-select and stranded the player with no way to add the second."""
    from exalted_builder.ui import view
    camp = rs.camps["sequestered-tabernacle"]
    tab = _tabernacle(rs, granted=list(camp.granted_charms) + [
        "solar.martial-arts.tiger-form"])
    (choice,) = view.build_camp_view(rs, tab).choices
    assert choice.chosen_key == "martial_arts:tiger"
    assert choice.chosen_charm_ids == ["solar.martial-arts.tiger-form"]
    assert choice.charm_options, "the sub-select must stay open to add the second Charm"


def test_charms_whose_minimums_are_unmet_are_offered_but_flagged(rs):
    """p.90 requires the character to "meet the minimum requirements", and the engine
    reports a violation as `granted-charm-minimum`. The option is still selectable —
    raising the trait later clears it — but it must say why it is flagged, with a
    readable trait name rather than the raw enum value."""
    from exalted_builder.ui import view
    camp = rs.camps["sequestered-tabernacle"]
    tab = _tabernacle(rs, granted=list(camp.granted_charms) + [
        "solar.martial-arts.crimson-leaping-cat-technique"])
    (choice,) = view.build_camp_view(rs, tab).choices
    by_label = {o.label: o for o in choice.charm_options}
    # Martial Arts 4: a Minimum Martial Arts 5 Charm is out of reach for now.
    assert by_label["Celestial Tiger Hide"].meets_minimums is False
    assert by_label["Celestial Tiger Hide"].reason == "needs Martial Arts 5"
    assert by_label["Crimson Leaping Cat Technique"].meets_minimums is True
    assert by_label["Crimson Leaping Cat Technique"].reason == ""


def test_fixed_set_choices_have_no_sub_choice(rs):
    """Kether Rock's package is "one of the following pairs" — the printed pair IS the
    grant, so there is nothing further to pick and `charm_options` stays empty."""
    from exalted_builder.ui import view
    kether = _illuminated(rs)
    for choice in view.build_camp_view(rs, kether).choices:
        if not choice.is_category_choice:
            assert choice.charm_options == []
            assert choice.chosen_charm_ids == []


# ---------------------------------------------- Cult Dragon-Blooded (p.96)

def _cult_db(rs, camp="kether-rock-db", **kw):
    """A Cult Dragon-Blooded. p.96 generates them "as standard outcastes ... with the
    following exceptions", so everything not named below comes off the outcaste row."""
    abilities = {AB.BRAWL: 1, AB.ENDURANCE: 1, AB.MEDICINE: 1, AB.MELEE: 2,
                 AB.PRESENCE: 1, AB.RESISTANCE: 1, AB.SURVIVAL: 3, AB.MARTIAL_ARTS: 4}
    abilities.update(kw.pop("abilities", {}))
    granted = kw.pop("granted_charms", list(rs.camps[camp].granted_charms))
    data = dict(id="cdb", name="Cult DB", exalt_type="Dragon-Blooded", caste="fire",
                origin="illuminated", camp=camp, calling="", essence_rating=2,
                abilities=abilities, granted_charms=granted)
    data.update(kw)
    return Character(**data)


def test_cult_dragonblooded_budget_is_the_outcaste_row_with_four_exceptions(rs):
    """p.96: "generated as standard outcastes (Exalted: The Outcaste, pp. 159-160)
    with the following exceptions: They gain 30 dots of Abilities and have the normal
    requirements for their training camp. They receive seven (7) Background dots and
    may select Cult Backgrounds." Everything else must still be the outcaste's —
    budget rows REPLACE wholesale, so the unchanged values are restated, and this test
    is what keeps a future edit from letting one drift."""
    out = rs.budgets_for("Dragon-Blooded", "outcaste")
    cult = rs.budgets_for("Dragon-Blooded", "illuminated")

    assert (out.ability_dots, cult.ability_dots) == (25, 30)
    assert (out.background_dots, cult.background_dots) == (12, 7)
    for field in ("attribute_pools", "ability_min_caste_favored", "favored_count",
                  "charm_count", "charm_min_caste_favored", "virtue_dots",
                  "essence_start", "bonus_points"):
        assert getattr(cult, field) == getattr(out, field), field


def test_a_cult_dragonblooded_has_a_camp_but_no_calling(rs):
    """p.96 gives them "the normal requirements for their training camp" and never
    mentions a Calling — the Solar apparatus does not come wholesale (human, rules
    authority). The camp panel must therefore render with no Calling control."""
    from exalted_builder.ui import view
    cult = rs.budgets_for("Dragon-Blooded", "illuminated")
    assert cult.requires_camp is True
    assert cult.requires_calling is False

    cv = view.build_camp_view(rs, _cult_db(rs))
    assert [cid for cid, _ in cv.camp_options] == \
        ["sequestered-tabernacle-db", "kether-rock-db"]
    assert cv.calling_options == []
    assert not validate.check_camp_and_calling(rs, _cult_db(rs))


def test_the_db_camps_borrow_the_solar_camps_ability_floors(rs):
    """"the normal requirements for their training camp" (p.96) — the floors are the
    camp's, not a second set printed for Dragon-Blooded."""
    for db, solar in (("sequestered-tabernacle-db", "sequestered-tabernacle"),
                      ("kether-rock-db", "kether-rock")):
        assert rs.camps[db].required_min_abilities == \
            rs.camps[solar].required_min_abilities


def test_kether_rock_grants_a_dragonblood_nothing(rs):
    """p.96: Kether Rock's Dragon-Blooded "select seven (7) standard Dragon-Blooded
    Charms" — which is the outcaste's normal allowance, so the camp hands out no free
    package at all. Contrast the Solar Kether Rock, which grants two Charms and a
    pair."""
    camp = rs.camps["kether-rock-db"]
    assert list(camp.granted_charms) == []
    assert list(camp.granted_charm_choices) == []
    assert not validate.granted_charm_issues(rs, _cult_db(rs))
    assert rs.budgets_for("Dragon-Blooded", "illuminated").charm_count == 7


def test_the_tabernacle_grants_a_dragonblood_two_charms_plus_three_from_a_pool(rs):
    """p.96: Venerable Silk "trains Dragon-Blooded in Celestial martial arts", so they
    "gain Walker-Among-Irises Perception and Iris-Bulb Discourse ... and three (3)
    Charms from Ebon Shadow Style, Falling Blossom Style, Praying Mantis Style, Snake
    Style, Tiger Style or Ox-Body Technique".

    The three come from ONE FLAT POOL, mixed freely — unlike the Solar camps' "two
    Charms from ONE of the following four martial arts" (human, rules authority) —
    and the pool mixes five styles with a named Ability Charm, which is why
    `pool_categories`/`pool_charms` exists at all."""
    camp = rs.camps["sequestered-tabernacle-db"]
    assert list(camp.granted_charms) == [
        "dragonblooded.martial-arts.walker-among-irises-perception",
        "dragonblooded.martial-arts.iris-bulb-discourse"]
    (choice,) = camp.granted_charm_choices
    assert choice.pick == 3
    assert not choice.from_categories and not choice.fixed_sets
    assert set(choice.pool_categories) == {
        "martial_arts:ebon-shadow", "martial_arts:falling-blossom",
        "martial_arts:praying-mantis", "martial_arts:snake", "martial_arts:tiger"}
    assert list(choice.pool_charms) == ["dragonblooded.endurance.ox-body-technique"]

    pool = choice.pool_charm_ids(rs.charms)
    assert "dragonblooded.endurance.ox-body-technique" in pool
    assert any(rs.charms[c].category == "martial_arts:falling-blossom" for c in pool)


def test_the_pool_choice_needs_exactly_three_charms_from_anywhere_in_it(rs):
    """Under-picking is unresolved, three is legal in ANY combination (the point of
    the shape — two styles at once must NOT raise granted-charm-choice-mixed), and a
    fourth is an extra."""
    camp = rs.camps["sequestered-tabernacle-db"]
    fixed = list(camp.granted_charms)
    (choice,) = camp.granted_charm_choices
    pool = choice.pool_charm_ids(rs.charms)
    ebon = [c for c in pool if rs.charms[c].category == "martial_arts:ebon-shadow"]
    snake = [c for c in pool if rs.charms[c].category == "martial_arts:snake"]

    def codes(granted):
        return _codes(validate.granted_charm_issues(
            rs, _cult_db(rs, camp="sequestered-tabernacle-db", granted_charms=granted)))

    assert "granted-charm-choice-unresolved" in codes(fixed + ebon[:2])
    mixed = fixed + [ebon[0], snake[0], "dragonblooded.endurance.ox-body-technique"]
    assert not (codes(mixed) & {"granted-charm-choice-unresolved",
                                "granted-charm-choice-mixed", "granted-charm-extra"})
    assert "granted-charm-extra" in codes(mixed + [snake[1]])


def test_the_pool_choice_renders_as_one_control_not_two(rs):
    """A category choice is a style select plus a Charm select; a pool choice has no
    style step, so `options` must be empty and `charm_options` full from the start.
    An empty style select would be a dropdown the player can neither use nor
    dismiss — the editor keys off exactly this."""
    from exalted_builder.ui import view
    cult = _cult_db(rs, camp="sequestered-tabernacle-db")
    (choice,) = view.build_camp_view(rs, cult).choices
    assert choice.options == []
    assert choice.is_category_choice is False
    assert len(choice.charm_options) > 40
    assert choice.pick == 3


def test_cult_dragonblooded_take_the_cults_artifact_and_a_capped_illumination(rs):
    """p.96: "For other Cult Exalted, orichalcum is reserved exclusively for Solars.
    They may take jade with this Background" — the Cult's Artifact is theirs, so it
    displaces the Realm's doubled one. Illumination is theirs too, but capped: "
    Dragon-Blooded may not exceed Illumination •••" (p.97)."""
    offered = {b.id for b in rs.backgrounds_for("Dragon-Blooded", "illuminated")}
    assert "background.artifact-illuminated" in offered
    assert "background.artifact-dragonblooded" not in offered
    assert {"background.illumination", "background.sorcery-illuminated"} <= offered
    # Still Dragon-Blooded: the Realm Backgrounds do not go away.
    assert {"background.breeding", "background.family"} <= offered

    rules = rs.budgets_for("Dragon-Blooded", "illuminated").background_rules
    assert rules["illumination"].max_rating == 3
    assert rules["illumination"].free_rating == 0, \
        "the free dot is printed for Solars only (p.97)"
    assert [(t.rating, t.combined_max) for t in rules["artifact"].budget_tiers] == \
        [(1, 2), (2, 3), (3, 4), (4, 6), (5, 8)]


def test_a_cult_dragonblooded_sorcery_stops_below_the_celestial_rungs(rs):
    """The Sorcery Background is offered to Dragon-Blooded on the strength of "any
    Illuminated Exalt training in the camps can learn sorcery" (p.98), but its •••• and
    ••••• rungs grant "four/five spells from either the Terrestrial or the Celestial
    Circles" — which a Terrestrial cannot cast. Capped at ••• , the highest rung that
    grants Terrestrial spells only (human, rules authority, 2026-08-12).

    Solars keep the full ladder: the cap is on the ORIGIN row, not the Background."""
    db = rs.budgets_for("Dragon-Blooded", "illuminated")
    assert db.background_rules["sorcery"].max_rating == 3

    solar = rs.budgets_for("Solar", "illuminated")
    assert "sorcery" not in solar.background_rules

    c = Character(id="s", name="s", exalt_type="Dragon-Blooded", caste="fire",
                  origin="illuminated",
                  backgrounds=[BackgroundEntry(name="Sorcery", rating=4)])
    assert validate.background_rating_cap(db, c, "Sorcery") == 3
    assert "background-above-origin-cap" in _codes(
        validate.background_issues(db, c.backgrounds, c))
