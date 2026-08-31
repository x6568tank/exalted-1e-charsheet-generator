"""Tests for the Ghost splat — Exalted: The Abyssals, CH3 p.123-127, CH4 p.148-153,
CH6 p.232-253, XP p.283.

Ghosts are the first NON-EXALT splat after Mortals, and the first splat in the build
whose Charms are keyed to a VIRTUE. The distinctive numbers are asserted one per
keyed-table row, because a keyed row that does not exist falls back silently at
another splat's prices — `adding-a-splat.md` trap #2, and the reason a typo in
`chargen_budgets.json` would otherwise pass every other test in the suite.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db

_DATA = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_app_ruleset(_DATA)


# --------------------------------------------------------------------------- #
# The four data rows
# --------------------------------------------------------------------------- #

def test_the_ghost_exalt_row_exists_and_is_not_a_fallback(rs) -> None:
    """`exalt_for` returns the SOLAR definition for an unknown splat, so asserting the
    id is what proves the row was found rather than defaulted."""
    g = rs.exalt_for("Ghost")
    assert g.id == "Ghost"
    assert g.label == "Ghost"


def test_ghosts_have_one_essence_pool_on_the_printed_formula(rs) -> None:
    """p.126: "[Essence x 10] + [Willpower x 3] + [(the sum of Virtues) x 2]", and
    "Ghosts do not have separate Personal and Peripheral Essence pools"."""
    g = rs.exalt_for("Ghost")
    assert g.single_essence_pool is True
    assert g.essence.personal_essence_coeff == 10
    assert g.essence.personal_willpower_coeff == 3
    assert g.essence.personal_virtue_mode == "all"
    assert g.essence.personal_virtue_coeff == 2


def test_ghosts_take_no_part_in_the_great_curse_and_never_learn_combos(rs) -> None:
    """p.148 for the Curse, p.234 for Combos. Both are flat bars, not budgets."""
    g = rs.exalt_for("Ghost")
    assert g.has_virtue_flaw is False
    assert g.combos_available is False
    # The dead keep the thaumaturgy they learned in life but may never use it
    # (PG p.114) — possession is not the same as use, so Charms stay available.
    assert g.thaumaturgy_usable is False
    assert g.charms_available is True


def test_ghost_essence_is_capped_at_five_for_life(rs) -> None:
    """p.283 footnote: "Cannot exceed Essence 5." A lifetime ceiling, not a chargen
    one — `essence_start_cap` would only bind until the lock."""
    assert rs.exalt_for("Ghost").essence_cap == 5


# --------------------------------------------------------------------------- #
# Chargen budgets — one distinctive number per row of the cascade
# --------------------------------------------------------------------------- #

def test_the_heroic_ghost_budget_is_the_printed_one(rs) -> None:
    """p.126-127: 6/4/3 Attributes, 22 Abilities, 6 Arcanoi, 8 Backgrounds, 5 Virtue
    dots, 5 Fetter dots, Essence 2, 21 bonus points."""
    b = rs.budgets_for("Ghost", "", "")
    assert b.attribute_pools == (6, 4, 3)
    assert b.ability_dots == 22
    assert b.charm_count == 6
    assert b.background_dots == 8
    assert b.virtue_dots == 5
    assert b.fetter_dots == 5
    assert b.essence_start == 2
    assert b.bonus_points == 21


def test_the_mundane_dead_get_their_own_row(rs) -> None:
    """The p.126 sidebar: "four dots to spend in one Attribute category, three dots in
    each of the other two categories, 16 dots in Abilities, two Arcanoi and 15 bonus
    points". Everything else is shared with the heroic row."""
    b = rs.budgets_for("Ghost", "mundane", "")
    assert b.attribute_pools == (4, 3, 3)
    assert b.ability_dots == 16
    assert b.charm_count == 2
    assert b.bonus_points == 15
    # Shared with the heroic dead, and the reason this is an origin and not a splat.
    assert b.virtue_dots == 5
    assert b.essence_start == 2
    assert b.fetter_dots == 5


@pytest.mark.parametrize("origin", ["heroic", "mundane"])
def test_an_immaculate_upbringing_halves_the_backgrounds(rs, origin) -> None:
    """p.126: "Ghosts from areas that uphold the Immaculate Philosophy have five (5)
    dots to spend on Backgrounds, while those from areas with active ancestor worship
    have eight (8)." The axis is independent of heroic/mundane, so BOTH origins carry
    the immaculate variant — a missing row here would silently pay 8.

    Ghosts are the first splat to use BOTH keyed axes at once, and that exposes a rule
    of the cascade: `_keyed_row` only tries `E:o:u` when the ORIGIN is non-empty. So a
    ghost's origin is always explicit ("heroic" is a value, not a blank), exactly as
    the Outcaste-book Dragon-Blooded origins are, and it is the UPBRINGING that may be
    empty. `test_a_ghost_with_no_origin_falls_back_to_the_heroic_row` pins the other
    end of that.
    """
    assert rs.budgets_for("Ghost", origin, "immaculate").background_dots == 5
    assert rs.budgets_for("Ghost", origin, "").background_dots == 8


def test_a_ghost_with_no_origin_falls_back_to_the_heroic_row(rs) -> None:
    """The plain "Ghost" row IS the heroic row, so an origin-less character (a legacy
    save, a half-built sheet) gets the heroic budget rather than nothing."""
    assert rs.budgets_for("Ghost", "", "") == rs.budgets_for("Ghost", "heroic", "")


def test_the_optional_favored_ability_is_heroic_only(rs) -> None:
    """p.126 offers it to "a heroic ghost character"; the mundane sidebar does not."""
    assert rs.budgets_for("Ghost", "heroic", "").optional_favored_ability is True
    assert rs.budgets_for("Ghost", "mundane", "").optional_favored_ability is False


# --------------------------------------------------------------------------- #
# Bonus points and experience
# --------------------------------------------------------------------------- #

def test_the_bonus_point_table_is_the_printed_one(rs) -> None:
    """p.127. Essence 12 and Arcanos 6 are the two that differ most from Solar's 7/5,
    so a silently-fallen-back row shows up here first."""
    c = rs.bonus_costs_for("Ghost")
    assert c.attribute == 4
    assert c.ability == 2
    assert c.ability_favored_caste == 1
    assert c.virtue == 5
    assert c.willpower == 3
    assert c.essence == 12
    assert c.charm == 6
    assert c.fetter == 3


def test_a_favored_specialty_is_two_dots_per_point(rs) -> None:
    """p.127 reads "Specialty | 1 (2 per 1 if in the Favored Ability)". Ruled as a
    DISCOUNT (human, rules authority, 2026-08-01) — two specialties per point, running
    the same direction as the Ability line above it, which also gets cheaper when
    Favored. The other reading (2 points each) would have made Favored dearer."""
    assert rs.bonus_costs_for("Ghost").specialty == 1
    assert rs.bonus_costs_for("Ghost").specialty_favored_caste_dots_per_point == 2


def test_the_experience_table_is_the_printed_one(rs) -> None:
    """p.283. Every rate differs from Solar's, which is exactly why the row has to
    exist: without it a ghost would raise Essence at ×8 instead of ×12."""
    x = rs.xp_costs_for("Ghost")
    assert x.attribute.coeff == 8
    assert x.ability.coeff == 4
    assert (x.ability_favored_caste.coeff, x.ability_favored_caste.offset) == (4, -1)
    assert x.essence.coeff == 12
    assert x.virtue.coeff == 6
    assert x.willpower.coeff == 5
    assert x.fetter.coeff == 3
    assert x.new_ability == 12
    assert x.new_charm == 14


def test_the_fetter_and_passion_operations_are_priced(rs) -> None:
    """p.283's "Special" block, plus the conditional new-Fetter discount. Nothing else
    in the build prices an operation on a trait's FOCUS rather than its rating."""
    x = rs.xp_costs_for("Ghost")
    assert x.new_fetter == 20
    assert x.new_fetter_discounted == 15
    assert x.new_fetter_discount_charm_id  # names the Arcanos, never hardcoded in code
    assert x.shift_passion == 20
    assert x.shift_fetter == 10


# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #

def test_the_ghost_palette_is_its_own_and_not_the_solar_fallback() -> None:
    from exalted_builder.ui import theme

    pal = theme.palette("Ghost")
    assert pal.splat_label == "Ghost"
    assert pal.accent != theme.palette("Solar").accent
    assert pal.accent != theme.palette("Abyssal").accent
    assert pal.accent != theme.palette("Mortal").accent


# --------------------------------------------------------------------------- #
# Virtue-keyed Arcanoi (E:Ab p.234-253)
# --------------------------------------------------------------------------- #
# The third and last keying axis. Every one of the 56 Arcanoi prints exactly one
# "Minimum <Virtue>" and no Ability minimum at all, so a ghost's Charms gate on a
# trait no Charm in the build had ever gated on.
#
# Asserted through the BUY PATH (`advancement.learn_charm`) as well as the gate
# function: this build's recurring bug is a rule that IS implemented sitting where it
# does not run, and a gate that reports a shortfall but does not refuse the purchase
# is precisely that shape.

from exalted_builder.engine import advancement, lifecycle, validate  # noqa: E402
from exalted_builder.models.character import Character  # noqa: E402
from exalted_builder.models.rules import AbilityName, Charm, CharmType, VirtueName  # noqa: E402


def _arcanos(cid: str = "ghost.test.wailing", virtue: str = "compassion",
             rating: int = 3, essence: int = 1) -> Charm:
    return Charm(id=cid, name="Test Arcanos", category="shifting_ghost_clay",
                 exalt_type="Ghost", min_virtue=virtue, min_ability=rating,
                 min_essence=essence, type=CharmType.SIMPLE)


def _ghost(**kw) -> Character:
    c = Character(id="g", name="Revenant", exalt_type="Ghost", caste="",
                  origin="heroic", essence_rating=2, **kw)
    return c


def test_a_virtue_keyed_charm_reports_the_virtue_as_its_requirement(rs) -> None:
    """Display half: the picker and sheet must name Compassion, not an Ability the
    Charm's category happens to resolve to."""
    charm = _arcanos(virtue="temperance", rating=2)
    assert validate.charm_ability_requirements(charm) == [("temperance", 2)]


def test_a_ghost_below_the_virtue_minimum_has_a_shortfall(rs) -> None:
    c = _ghost()
    c.virtues[VirtueName.COMPASSION] = 2
    short = validate.charm_ability_shortfalls(c, _arcanos(rating=3))
    assert short == [("compassion", 3, 2)]


def test_a_ghost_at_the_virtue_minimum_has_none(rs) -> None:
    c = _ghost()
    c.virtues[VirtueName.COMPASSION] = 3
    assert validate.charm_ability_shortfalls(c, _arcanos(rating=3)) == []


def test_the_gate_reads_the_NAMED_virtue_not_merely_the_highest(rs) -> None:
    """The bug this forecloses: a ghost with Valor 5 and Compassion 1 must still fail a
    Compassion 3 Arcanos. A 'best Virtue' reading would pass it."""
    c = _ghost()
    c.virtues[VirtueName.VALOR] = 5
    c.virtues[VirtueName.COMPASSION] = 1
    assert validate.charm_ability_shortfalls(c, _arcanos(rating=3)) == [("compassion", 3, 1)]


def test_the_buy_path_refuses_an_arcanos_whose_virtue_is_too_low(rs) -> None:
    """THE test that matters. `meets_charm_requirements` is what `learn_charm` asks,
    so a gate wired only into the display would let this purchase through."""
    charm = _arcanos("ghost.test.buy-refused", rating=4)
    rs2 = rs.model_copy(update={"charms": {**rs.charms, charm.id: charm}})
    c = _ghost()
    c.virtues[VirtueName.COMPASSION] = 2
    lifecycle.lock_chargen(c, rs2)
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs2, c, charm.id)


def test_the_buy_path_allows_it_once_the_virtue_is_high_enough(rs) -> None:
    """The other half — proof the refusal above is the gate doing its job and not the
    Charm being unbuyable for some unrelated reason (splat, Essence, price)."""
    charm = _arcanos("ghost.test.buy-allowed", rating=2)
    rs2 = rs.model_copy(update={"charms": {**rs.charms, charm.id: charm}})
    c = _ghost()
    c.virtues[VirtueName.COMPASSION] = 2
    lifecycle.lock_chargen(c, rs2)
    advancement.add_xp(c, 100)
    entry = advancement.learn_charm(rs2, c, charm.id)
    assert charm.id in c.charms
    # Priced from the Ghost row (p.283), not Solar's 10.
    assert entry.cost == 14


def test_a_virtue_keyed_charm_does_not_gate_on_its_category_as_an_ability(rs) -> None:
    """The collision `_min_trait_rating` exists to prevent, in its third form: a
    category that is ALSO a valid AbilityName must not be read as one when the Charm
    names a Virtue. 'melee' is such a category."""
    charm = Charm(id="ghost.test.melee-cat", name="Melee-category Arcanos",
                  category="melee", exalt_type="Ghost", min_virtue="valor",
                  min_ability=3, min_essence=1, type=CharmType.SIMPLE)
    c = _ghost()
    c.virtues[VirtueName.VALOR] = 3
    c.abilities[AbilityName.MELEE] = 0
    # Valor 3 is met and Melee 0 is irrelevant — the Virtue is the gate.
    assert validate.charm_ability_shortfalls(c, charm) == []


# --------------------------------------------------------------------------- #
# Fetters and Passions (E:Ab p.126-127, p.283)
# --------------------------------------------------------------------------- #

from exalted_builder.engine import derive  # noqa: E402
from exalted_builder.models.character import FetterEntry, PassionEntry  # noqa: E402

V = VirtueName


def _ghost_with_virtues(comp=3, conv=2, temp=1, val=1, **kw) -> Character:
    c = _ghost(**kw)
    c.virtues = {V.COMPASSION: comp, V.CONVICTION: conv,
                 V.TEMPERANCE: temp, V.VALOR: val}
    return c


# --- the Passion pool ------------------------------------------------------- #

def test_the_passion_pool_is_per_virtue_not_one_aggregate() -> None:
    """p.126: "a number of dots of Passions for each Virtue equal to the number of dots
    the character has in that Virtue". Compassion 3 buys three dots of COMPASSION
    Passions and nothing else — the pools do not pool."""
    c = _ghost_with_virtues(comp=3, val=1)
    assert derive.passion_pool(c)[V.COMPASSION] == 3
    assert derive.passion_pool(c)[V.VALOR] == 1


def test_passions_spent_against_the_wrong_virtue_do_not_count(rs) -> None:
    """The bug a single aggregate pool would hide: four dots of Compassion Passions
    against Compassion 3 and Valor 1 nets to zero overall, and is wrong twice."""
    c = _ghost_with_virtues(comp=3, val=1)
    c.passions = [PassionEntry(name="avenge me", virtue=V.COMPASSION, rating=4)]
    codes = {i.code for i in validate.check_fetters_and_passions(rs, c)}
    assert "passion-over-pool" in codes          # Compassion is over by one
    assert "passion-undistributed" in codes      # Valor still has its dot


def test_a_fully_distributed_ghost_is_clean(rs) -> None:
    c = _ghost_with_virtues(comp=2, conv=1, temp=1, val=1)
    c.passions = [
        PassionEntry(name="avenge me", virtue=V.COMPASSION, rating=2),
        PassionEntry(name="finish the work", virtue=V.CONVICTION, rating=1),
        PassionEntry(name="keep my temper", virtue=V.TEMPERANCE, rating=1),
        PassionEntry(name="fear nothing", virtue=V.VALOR, rating=1),
    ]
    assert validate.check_fetters_and_passions(rs, c) == []


def test_raising_a_virtue_WITH_XP_opens_a_passion_dot(rs) -> None:
    """⚠ THE test this whole area exists for, and the build's most-repeated bug shape.

    p.283: "Ghosts increase their Passions when they increase their Virtues. There is
    no other way for these Traits to increase" — and the human confirmed (2026-08-01)
    that this holds POST-LOCK. A pool wired into chargen only would pass every test
    above and silently stop tracking here, exactly as Callous's Willpower did.

    Driven through `advancement.raise_virtue`, the buy path, not by poking the Virtue.
    """
    c = _ghost_with_virtues(comp=2, conv=1, temp=1, val=1)
    c.passions = [
        PassionEntry(name="avenge me", virtue=V.COMPASSION, rating=2),
        PassionEntry(name="finish the work", virtue=V.CONVICTION, rating=1),
        PassionEntry(name="keep my temper", virtue=V.TEMPERANCE, rating=1),
        PassionEntry(name="fear nothing", virtue=V.VALOR, rating=1),
    ]
    lifecycle.lock_chargen(c, rs)
    assert validate.check_fetters_and_passions(rs, c) == []      # clean at the lock
    advancement.add_xp(c, 100)
    advancement.raise_virtue(rs, c, V.COMPASSION)

    assert derive.passion_pool(c)[V.COMPASSION] == 3
    assert derive.passion_dots_unspent(c)[V.COMPASSION] == 1
    codes = [i.code for i in validate.check_fetters_and_passions(rs, c)]
    assert codes == ["passion-undistributed"]


def test_passions_are_not_frozen_into_the_chargen_snapshot(rs) -> None:
    """The structural half of the same rule. Fetters ARE snapshotted; Passions must not
    be, or the audit would measure a live derivation against a frozen copy."""
    c = _ghost_with_virtues()
    c.fetters = [FetterEntry(name="my wife", rating=2)]
    lifecycle.lock_chargen(c, rs)
    snap = c.chargen_snapshot
    assert [f.name for f in snap.fetters] == ["my wife"]
    assert "passions" not in type(snap).model_fields


# --- Fetters ---------------------------------------------------------------- #

def test_the_fetter_cap_is_willpower_plus_essence(rs) -> None:
    """p.127, restated in the p.283 footnote. Essence 2 + Willpower 5 = 7 dots."""
    c = _ghost_with_virtues(comp=3, conv=2)     # two highest = 5 Willpower
    assert derive.willpower(c, rs) == 5
    assert derive.fetter_cap(c, rs) == 7


def test_too_many_fetter_dots_is_an_error(rs) -> None:
    c = _ghost_with_virtues(comp=1, conv=1, temp=1, val=1)   # Willpower 2, Essence 2
    c.fetters = [FetterEntry(name="a", rating=3), FetterEntry(name="b", rating=3)]
    codes = {i.code for i in validate.check_fetters_and_passions(rs, c)}
    assert "fetter-over-cap" in codes


def test_the_fetter_cap_binds_AFTER_the_lock_too(rs) -> None:
    """Not a chargen rule: the ceiling MOVES with Willpower and Essence, so a ghost at
    the cap cannot buy another dot, and the check must still run post-lock."""
    c = _ghost_with_virtues(comp=1, conv=1, temp=1, val=1)   # cap = 2 + 2 = 4
    c.fetters = [FetterEntry(name="a", rating=4)]
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_fetter(rs, c, "a")
    with pytest.raises(advancement.AdvancementError):
        advancement.add_fetter(rs, c, "b")


def test_raising_a_fetter_costs_current_times_three(rs) -> None:
    c = _ghost_with_virtues(comp=5, conv=5)     # Willpower 10 -> plenty of headroom
    c.fetters = [FetterEntry(name="a", rating=2)]
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    entry = advancement.raise_fetter(rs, c, "a")
    assert entry.cost == 6                      # 2 x 3
    assert c.fetters[0].rating == 3


def test_a_new_fetter_costs_twenty_and_fifteen_with_the_arcanos(rs) -> None:
    """p.283 prices a new Fetter at 20, or 15 for a ghost who knows Mark of the
    Relentless Hunter. The Arcanos is named in DATA — the only conditional price in the
    build — so this asserts the mechanism, using the id the cost table carries."""
    from exalted_builder.engine import costs as costsmod

    c = _ghost_with_virtues(comp=5, conv=5)
    lifecycle.lock_chargen(c, rs)
    cid = rs.xp_costs_for("Ghost").new_fetter_discount_charm_id
    # The id must RESOLVE, not merely be non-empty: nothing link-checks a cost-table
    # field, so a typo would silently make the discount unreachable forever.
    assert cid in rs.charms, cid
    assert rs.charms[cid].name == "Mark Of The Relentless Hunter"
    assert costsmod.new_fetter_cost(rs, c) == 20
    c.charms.append(cid)
    assert costsmod.new_fetter_cost(rs, c) == 15


def test_shifting_a_fetter_renames_it_without_moving_a_rating(rs) -> None:
    """p.283, "Shift Fetter | 10". A shift changes what the ghost is anchored TO, so it
    touches no pool and no cap."""
    c = _ghost_with_virtues(comp=5, conv=5)
    c.fetters = [FetterEntry(name="my wife", rating=3)]
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    entry = advancement.shift_fetter(rs, c, "my wife", "my daughter")
    assert entry.cost == 10
    assert [(f.name, f.rating) for f in c.fetters] == [("my daughter", 3)]


# --- shifting a Passion ----------------------------------------------------- #

def test_shifting_a_passion_moves_a_dot_and_leaves_the_total_alone(rs) -> None:
    """p.283: "This decreases a Passion by one dot. In turn, it increases an existing
    Passion by one dot or creates a new one-dot Passion." The total is set by the
    Virtues, so a shift must not change it."""
    c = _ghost_with_virtues(comp=3)
    c.passions = [PassionEntry(name="avenge me", virtue=V.COMPASSION, rating=3)]
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    before = sum(p.rating for p in c.passions)
    entry = advancement.shift_passion(rs, c, "avenge me", "protect my son")
    assert entry.cost == 20
    assert sum(p.rating for p in c.passions) == before
    assert sorted((p.name, p.rating) for p in c.passions) == [
        ("avenge me", 2), ("protect my son", 1)]


def test_a_passion_emptied_by_a_shift_is_removed(rs) -> None:
    """A 0-dot Passion is not a trait, it is a leftover row."""
    c = _ghost_with_virtues(comp=1, conv=1, temp=1, val=1)
    c.passions = [PassionEntry(name="one thing", virtue=V.COMPASSION, rating=1)]
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    advancement.shift_passion(rs, c, "one thing", "another thing")
    assert [(p.name, p.rating) for p in c.passions] == [("another thing", 1)]


def test_undoing_a_passion_shift_puts_the_dot_back(rs) -> None:
    """Undo is LIFO and must reverse a shift exactly, including removing a destination
    Passion the shift itself created."""
    c = _ghost_with_virtues(comp=2)
    c.passions = [PassionEntry(name="avenge me", virtue=V.COMPASSION, rating=2)]
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    advancement.shift_passion(rs, c, "avenge me", "protect my son")
    advancement.undo_last(rs, c)
    assert [(p.name, p.rating) for p in c.passions] == [("avenge me", 2)]


def test_undoing_a_new_fetter_and_a_fetter_raise(rs) -> None:
    c = _ghost_with_virtues(comp=5, conv=5)
    c.fetters = [FetterEntry(name="a", rating=1)]
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    advancement.raise_fetter(rs, c, "a")
    advancement.add_fetter(rs, c, "b")
    assert [(f.name, f.rating) for f in c.fetters] == [("a", 2), ("b", 1)]
    advancement.undo_last(rs, c)
    assert [f.name for f in c.fetters] == ["a"]
    advancement.undo_last(rs, c)
    assert c.fetters[0].rating == 1


# --- bonus points ----------------------------------------------------------- #

def test_fetters_get_their_own_bonus_point_line(rs) -> None:
    """5 dots free; dots above the pre-BP cap of 3 and any pool overflow cost 3 each
    (p.127). Fetters at 4 and 3: the within-pool count caps each Fetter at 3, so it is
    3 + 3 = 6 against the 5-dot pool (1 overflow), plus the 1 dot of the first Fetter
    that sits above the cap. 2 dots x 3 BP = 6.

    Deliberately the same `within`/`above` arithmetic Backgrounds use, so the two
    cannot disagree about what "spent from the pool" means."""
    c = _ghost_with_virtues(comp=5, conv=5)
    c.fetters = [FetterEntry(name="a", rating=4), FetterEntry(name="b", rating=3)]
    bd = validate.bonus_point_breakdown(rs, c)
    line = next(l for l in bd.lines if l.domain == "Fetters")
    assert line.points == 6


def test_no_other_splat_shows_a_fetter_line(rs) -> None:
    """The line is opt-in on `fetter_dots`, so a Solar's breakdown is unchanged."""
    solar = Character(id="s", exalt_type="Solar", caste="dawn")
    bd = validate.bonus_point_breakdown(rs, solar)
    assert not any(l.domain == "Fetters" for l in bd.lines)


# --------------------------------------------------------------------------- #
# Backgrounds, origins and the Combo bar (E:Ab p.150-153, p.234)
# --------------------------------------------------------------------------- #

from exalted_builder.models.character import BackgroundEntry, Combo  # noqa: E402


def test_the_three_ghost_backgrounds_are_offered_only_to_ghosts(rs) -> None:
    """p.151-153. All three are `exalt_type: Ghost`, so no other splat sees them."""
    ghost = {b.name for b in rs.backgrounds_for("Ghost")}
    solar = {b.name for b in rs.backgrounds_for("Solar")}
    for name in ("Ancestor Cult", "Grave Goods", "Underworld Cult"):
        assert name in ghost
        assert name not in solar


def test_ghosts_are_barred_from_familiar_liege_and_manse(rs) -> None:
    """p.150-151: "Ghost characters cannot possess the Backgrounds of Familiar, Liege
    or Manse." Ghosts serving Deathlords use Backing instead of Liege."""
    ghost = {b.name for b in rs.backgrounds_for("Ghost")}
    assert not ghost & {"Familiar", "Liege", "Manse"}
    assert "Backing" in ghost
    # …and no other splat lost them on the way.
    assert {"Familiar", "Liege", "Manse"} <= {b.name for b in rs.backgrounds_for("Abyssal")}


def test_an_immaculate_ghost_may_not_exceed_one_dot_of_ancestor_cult(rs) -> None:
    """p.126. A HARD ceiling — bonus points do not buy past it, unlike the ordinary
    pre-BP cap of 3 — because the Immaculate Order suppresses the cult that feeds it."""
    bgs = [BackgroundEntry(name="Ancestor Cult", rating=3)]
    imm = rs.budgets_for("Ghost", "heroic", "immaculate")
    assert [i.code for i in validate.background_issues(imm, bgs)] == [
        "background-above-origin-cap"]
    # The same three dots are legal for a ghost from an ancestor-worshipping region.
    anc = rs.budgets_for("Ghost", "heroic", "")
    assert validate.background_issues(anc, bgs) == []


def test_grave_goods_is_capped_the_same_way(rs) -> None:
    """The page names both Backgrounds in one clause, so both carry the rule."""
    imm = rs.budgets_for("Ghost", "mundane", "immaculate")
    bgs = [BackgroundEntry(name="Grave Goods", rating=2)]
    assert [i.code for i in validate.background_issues(imm, bgs)] == [
        "background-above-origin-cap"]


def test_whispers_costs_a_ghost_double(rs) -> None:
    """p.151: "at twice the cost. The first 3 dots cost 2 Background or bonus points
    each, while each dot above 3 costs 4 bonus points each." Modelled as both halves of
    one rule — the pool side doubles the dot cost, the bonus-point side adds a
    surcharge on top of the ordinary above-3 rate."""
    rule = rs.budgets_for("Ghost", "heroic", "").background_rules["whispers"]
    # `dot_cost`, not `expensive_dot_cost`: every dot is doubled, and that pair's
    # threshold doubles as its disabled sentinel, so it cannot say "from the first".
    assert rule.dot_cost == 2
    # background_above_3 is 2, so a dot above the cap costs 2 + 2 = 4, as printed.
    assert rs.bonus_costs_for("Ghost").background_above_3 + rule.bp_surcharge_per_dot == 4


def test_whispers_at_three_dots_eats_six_background_dots(rs) -> None:
    """End-to-end through the pool arithmetic, not just the rule fields: three dots at
    the doubled rate is six of the eight a ghost from an ancestor-worshipping region
    has."""
    c = _ghost(upbringing="")
    c.backgrounds = [BackgroundEntry(name="Whispers", rating=3)]
    b = rs.budgets_for("Ghost", "heroic", "")
    within, above = validate.background_pool_spend(rs, c, b, c.backgrounds)
    assert within == 6
    assert above == []


def test_a_ghost_may_never_learn_a_combo(rs) -> None:
    """p.234: "The dead may never learn Combos and so may never use more than one Charm
    per turn." A flat bar, so it is reported alone — the other findings are about how a
    Combo is built, which is noise for a character who may not have one."""
    c = _ghost()
    combo = Combo(name="Anything", charm_ids=["a", "b"])
    codes = [i.code for i in validate.combo_issues(rs, c, combo)]
    assert codes == ["combo-splat-barred"]


def test_the_combo_bar_reaches_the_buy_path(rs) -> None:
    """`add_combo` filters `combo_issues` for errors, so the bar has to BE an error —
    a warning would have let the purchase through."""
    c = _ghost()
    lifecycle.lock_chargen(c, rs)
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError):
        advancement.add_combo(rs, c, "Anything", ["a", "b"])


def test_other_splats_still_build_combos(rs) -> None:
    """The bar is opt-in on the splat row, so nothing else changed."""
    solar = Character(id="s", exalt_type="Solar", caste="dawn")
    codes = [i.code for i in validate.combo_issues(
        rs, solar, Combo(name="Two Charms", charm_ids=["a", "b"]))]
    assert "combo-splat-barred" not in codes


# --------------------------------------------------------------------------- #
# The Arcanoi catalogue (E:Ab p.232-253)
# --------------------------------------------------------------------------- #
# Extracted mechanically from the human's pasted CH6 markdown and verified against
# the source's own field counts. These pin the totals and the shape, so a re-extract
# that quietly drops or mangles rows fails here rather than in a browser.

_PATHS = ("shifting_ghost_clay", "terror_spreading", "savage_ghost_tamer",
          "essence_measuring_thief", "stringless_puppeteer", "tangled_web")


def _arcanoi(rs) -> list:
    return [c for c in rs.charms.values() if c.exalt_type == "Ghost"]


def _abyssals_arcanoi(rs) -> list:
    """Only the E:Ab CH6 set. The assertions below count THAT source's printed shape;
    Book of Bone and Ebony adds its own Arcanoi and must not move these numbers."""
    return [c for c in _arcanoi(rs)
            if c.source and c.source.book == "The Abyssals"]


def test_all_fifty_six_arcanoi_are_authored(rs) -> None:
    """56 `#### ` headings across the six paths in CH6, and no more: the four
    Craft (…) headings on the same level are ABILITIES and carry no Charms."""
    assert len(_abyssals_arcanoi(rs)) == 56


def test_the_six_paths_have_their_printed_counts(rs) -> None:
    from collections import Counter

    counts = Counter(c.category for c in _abyssals_arcanoi(rs))
    assert dict(counts) == {
        "shifting_ghost_clay": 10, "terror_spreading": 11, "savage_ghost_tamer": 9,
        "essence_measuring_thief": 9, "stringless_puppeteer": 8, "tangled_web": 9}


def test_every_arcanos_is_virtue_keyed(rs) -> None:
    """The defining property of the splat's magic. Every one prints exactly one
    Minimum <Virtue>; none prints an Ability minimum, so none may be Ability- or
    Attribute-keyed either."""
    for c in _arcanoi(rs):
        assert c.min_virtue, c.id
        assert not c.min_attribute, c.id
        assert c.min_ability >= 1, c.id            # min_ability RATES the Virtue


def test_the_virtue_split_matches_the_source(rs) -> None:
    """18 Compassion, 18 Temperance, 11 Conviction, 9 Valor — counted off the page.
    A mis-keyed Charm would move two of these numbers at once."""
    from collections import Counter

    assert dict(Counter(c.min_virtue for c in _abyssals_arcanoi(rs))) == {
        "compassion": 18, "temperance": 18, "conviction": 11, "valor": 9}


def test_every_arcanos_carries_its_page(rs) -> None:
    """Never-author-from-memory means every value is traceable. The pages run
    p.234-253, the span of CH6's Arcanoi."""
    for c in _abyssals_arcanoi(rs):
        assert c.source and c.source.book == "The Abyssals", c.id
        assert 232 <= c.source.page <= 253, (c.id, c.source.page)


def test_every_prerequisite_resolves_within_the_catalogue(rs) -> None:
    """The loader already refuses a dangling reference, so this is really an
    assertion about SHAPE.

    **50 Charms carry prerequisites**, and getting to that number the honest way is the
    whole story of this file. CH6 prints 49 well-formed "Prerequisite Charms:" lines
    that are not "None" — plus ONE that the paste mangled into "PrerequisiteCharms:"
    with the space dropped (p.244, Feeding the Lamprey's Appetite). A field name that
    fails to match does not fail loudly: the line silently becomes description text and
    the Charm loses its prerequisite. 49 was the WRONG answer, arrived at confidently.
    """
    with_prereqs = [c for c in _abyssals_arcanoi(rs) if c.prerequisites]
    assert len(with_prereqs) == 50, "49 printed lines + the one with the dropped space"
    edges = 0
    for c in _abyssals_arcanoi(rs):
        for group in c.prerequisites:
            for pid in group:
                assert pid in rs.charms, (c.id, pid)
                edges += 1
    assert edges == 56
    roots = [c for c in _abyssals_arcanoi(rs) if not c.prerequisites]
    assert len(roots) == 6


def test_the_one_health_level_cost_uses_the_damage_shorthand(rs) -> None:
    """p.238's Stolen Wax Discipline is the only Arcanos that spends a health level.
    `health_type` is the 1e mark ('x' lethal), not the English word — authoring the
    word made the row fail to load and silently dangled its two dependants."""
    from exalted_builder.models.rules import Damage

    c = rs.charms["ghost.shifting-ghost-clay.stolen-wax-discipline"]
    assert c.cost.health == 1
    assert c.cost.health_type == Damage.LETHAL
    assert c.cost.raw == "5 motes, one lethal health level"


def test_arcanoi_ids_hyphenate_the_category_segment(rs) -> None:
    """Convention (tools/validate_charms.py): id segments use hyphens and only the
    `category` FIELD keeps underscores. Both halves have to hold at once."""
    for c in _abyssals_arcanoi(rs):
        assert "_" not in c.id, c.id
        assert c.id.startswith("ghost."), c.id
        assert c.category in _PATHS, c.id


def test_a_wrapped_prerequisite_line_was_read_whole(rs) -> None:
    """Three prerequisite lines wrap mid-name in the paste ("…, Steeling" / "the
    Spirit"). Reading only the first line would have produced a dangling id — or
    worse, a silently EMPTY prerequisite list."""
    c = rs.charms["ghost.shifting-ghost-clay.ghost-devil-form"]
    names = {rs.charms[p].name for group in c.prerequisites for p in group}
    assert names == {"Nine Terrors Visage", "Steeling The Spirit"}


def test_a_wrapped_cost_line_was_read_whole(rs) -> None:
    """The one Cost that wraps mid-parenthesis (p.237)."""
    hits = [c for c in _arcanoi(rs) if "shadowlands" in c.cost.raw]
    assert len(hits) == 1
    assert hits[0].cost.raw == "20 motes, 2 Willpower (no Willpower in the shadowlands)"
    assert (hits[0].cost.motes, hits[0].cost.willpower) == (20, 2)


def test_the_supplementary_printing_variant_was_normalised(rs) -> None:
    """One Charm prints "Type: Supplementary" where the other nine of its kind print
    "Supplemental" (a printing inconsistency, not a distinct type). `CharmType` has no
    Supplementary, so leaving it would have failed the load."""
    from exalted_builder.models.rules import CharmType
    from collections import Counter

    counts = Counter(c.type for c in _abyssals_arcanoi(rs))
    assert counts[CharmType.SUPPLEMENTAL] == 10
    assert counts[CharmType.SIMPLE] == 41


# --------------------------------------------------------------------------- #
# Render matrix (preflight pass 3)
# --------------------------------------------------------------------------- #
# One route per SHAPE, not per known bug. Ghosts hit three shapes that have blanked
# panels before: a casteless splat, a splat whose picker categories are a brand-new
# group, and two rated traits with panels nothing else renders.


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_advantages_tab_builds_for_a_ghost(user) -> None:
    """Both new panels, pre-lock, with the live cap and the per-Virtue pools."""
    await user.open('/ghost-advantages')
    await user.should_see("Fetters")
    await user.should_see("my widowed wife")
    await user.should_see("Passions")
    await user.should_see("avenge my murder")
    # The cap is Willpower 5 + Essence 2 = 7, and it is stated, not implied.
    await user.should_see("cap = Willpower + Essence")
    # The rule a player would otherwise try to buy their way around.
    await user.should_see("never bought")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_advantages_tab_builds_for_a_locked_ghost(user) -> None:
    """The post-lock half: the Fetter buy controls and the Shift Passion control,
    neither of which exists pre-lock. This is the side that has to be driven through
    `advancement`, so a missing control means a rule that cannot be reached at all."""
    await user.open('/ghost-advantages-xp')
    await user.should_see("Fetters")
    await user.should_see("Raise")
    await user.should_see("Form (20 XP)")
    await user.should_see("Shift (20 XP)")          # the Passion shift
    await user.should_see("Shift (10 XP)")          # the Fetter shift


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_builds_for_a_casteless_ghost(user) -> None:
    """The Mortals shape: no castes at all, so every caste-grouped panel has to fall
    back rather than render blank."""
    await user.open('/ghost-editor')
    await user.should_see("Abilities")
    await user.should_see("Attributes")
    await user.should_see("Heroic Dead")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_builds_for_the_mundane_dead(user) -> None:
    await user.open('/ghost-editor-mundane')
    await user.should_see("Abilities")
    await user.should_see("Mundane Dead")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_picker_gives_arcanoi_their_own_page(user) -> None:
    """Human's call (2026-08-01): Arcanoi are their own Charms page, like Thaumaturgy,
    not entries in a dropdown of Ability names. And the page must be REACHABLE — a
    group with no categories renders an empty canvas.

    The Martial Arts page IS offered: PG p.234 lets ghosts learn Terrestrial styles.
    What must never appear is an ABILITIES page — ghosts hold no Ability-keyed Charms,
    and that page's Category dropdown raises outright when its options are empty,
    taking the whole picker down (adding-a-splat.md trap #3).
    """
    await user.open('/ghost-picker')
    await user.should_see("Arcanoi")
    await user.should_see("Martial Arts")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_sheet_builds_for_a_ghost(user) -> None:
    await user.open('/ghost-sheet')
    await user.should_see("Sighing Reed")
    await user.should_see("Fetters")
    await user.should_see("Passions")
    # A merged pool names itself rather than showing "Personal 0".
    await user.should_see("Single pool")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_advantages_tab_flags_an_immaculate_ghosts_ancestor_cult(user) -> None:
    """End-to-end for the origin cap: the readout on this tab is where a Background
    finding has to surface, since that is the tab that can fix it."""
    await user.open('/ghost-advantages-immaculate')
    await user.should_see("Ancestor Cult")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_panels_survive_a_ghost_with_no_fetters_or_passions(user) -> None:
    """`ui.select` raises at BUILD time when its value is not among its options, and
    the post-lock Fetter and Passion dropdowns are both built from the character's own
    lists — so an empty one is the easiest route to a blank tab (adding-a-splat.md
    trap #3, which has taken down whole tabs twice)."""
    await user.open('/ghost-advantages-empty')
    await user.should_see("Fetters")
    await user.should_see("Form (20 XP)")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_sheet_drops_both_panels_when_a_ghost_has_neither(user) -> None:
    """Empty panels on every sheet is what the Merits/Colleges/Thaumaturgy rule
    exists to avoid; Fetters and Passions follow it."""
    await user.open('/ghost-sheet-empty')
    await user.should_see("Forgotten")
    await user.should_not_see("Fetters")
    await user.should_not_see("Passions")


def test_the_foreign_charm_bar_survives_the_generalist_privilege(rs) -> None:
    """"Ghosts may not learn Exalted Charms" (E:Ab p.126) — no caste privilege and no
    house rule reopens it.

    Found by preflight, not by the suite: the bar lived in `charm_matches_splat`, but
    `charm_learnable_by_splat` falls THROUGH that to the p.127 generalist rule, so a
    second route reached the same permission with the bar enforced on only one of
    them. That is this build's most-repeated bug shape.

    The bar is NOT total — see the Terrestrial martial-arts exception below. This
    test is about the Charms it does cover, and about both routes agreeing.
    """
    from exalted_builder.models.character import HouseRules

    solar_charm = next(c for c in rs.charms.values()
                       if c.exalt_type == "Solar"
                       and not validate.is_terrestrial_martial_arts(c))
    c = _ghost()
    # Hand the ghost every permission the privilege asks for, then check it changes
    # nothing: an Eclipse caste id and the Storyteller's blessing.
    c.caste = "eclipse"
    c.house_rules = HouseRules(eclipse_foreign_charms=True)
    assert not validate.charm_matches_splat(c, solar_charm, rs)
    assert not validate.charm_learnable_by_splat(rs, c, solar_charm)
    # Their own Arcanoi are untouched by the bar.
    arcanos = next(x for x in rs.charms.values() if x.exalt_type == "Ghost")
    assert validate.charm_learnable_by_splat(rs, c, arcanos)


# --------------------------------------------------------------------------- #
# Ghost martial arts (Player's Guide p.234)
# --------------------------------------------------------------------------- #
# This page ARRIVED AFTER the splat shipped and overturned a reading recorded as an
# open question: "Ghosts may not learn Exalted Charms" (E:Ab p.126) had been read as
# barring the Terrestrial styles too. It does not. p.234: "Ghosts may learn
# supernatural martial-arts techniques as well. Like thaumaturges and God-Blooded,
# they can learn only Terrestrial styles."

FIGHTER_IN_LIFE = "mf.fighter-in-life"


def _terrestrial_ma(rs):
    """A plain Terrestrial style Charm — deliberately NOT an Immaculate Dragon Path
    one, whose own rate (p.292) is Dragon-Blooded's and would mask the ghost rate."""
    return next(c for c in rs.charms.values()
                if validate.is_terrestrial_martial_arts(c)
                and not validate.is_immaculate_charm(c) and c.min_essence == 1)


def test_every_ghost_may_learn_terrestrial_martial_arts(rs) -> None:
    """UNCONDITIONAL, and that is the load-bearing part: p.234's main text grants this
    to every ghost, and Fighter in Life only changes the price. Modelling the access as
    the Merit's would have barred it from every ghost without one."""
    c = _ghost()
    assert validate.charm_matches_splat(c, _terrestrial_ma(rs), rs)
    assert validate.charm_learnable_by_splat(rs, c, _terrestrial_ma(rs))
    assert not c.merits_flaws            # no Merit involved


def test_ghosts_still_cannot_reach_celestial_styles_or_other_splats_charms(rs) -> None:
    """"they can learn only Terrestrial styles" — the exception is exactly that wide."""
    c = _ghost()
    celestial = next((x for x in rs.charms.values()
                      if x.category.startswith("martial_arts")
                      and "Celestial" in x.open_to_tiers), None)
    if celestial is not None:
        assert not validate.charm_learnable_by_splat(rs, c, celestial)
    solar = next(x for x in rs.charms.values()
                 if x.exalt_type == "Solar"
                 and not validate.is_terrestrial_martial_arts(x))
    assert not validate.charm_learnable_by_splat(rs, c, solar)


def test_a_terrestrial_ma_charm_costs_a_ghost_twenty_without_the_merit(rs) -> None:
    """p.234: they learn one "at the same cost per Charm that they would pay for
    inventing a new Arcanos (20 experience points)" — a penalty against the 14 an
    ordinary Arcanos costs."""
    from exalted_builder.engine import costs as costsmod

    c = _ghost_with_virtues(comp=5, conv=5)
    lifecycle.lock_chargen(c, rs)
    assert costsmod.charm_cost(rs, c, _terrestrial_ma(rs)) == 20
    # …against an Arcanos, which is 14.
    arcanos = next(x for x in rs.charms.values() if x.exalt_type == "Ghost")
    assert costsmod.charm_cost(rs, c, arcanos) == 14


def test_fighter_in_life_buys_them_at_the_arcanos_rate(rs) -> None:
    """"It merely allows the ghost to purchase it … during play for the cost of
    developing a regular Arcanos (14 experience points)"."""
    from exalted_builder.engine import costs as costsmod
    from exalted_builder.models.character import MeritFlawPurchase

    c = _ghost_with_virtues(comp=5, conv=5)
    c.merits_flaws = [MeritFlawPurchase(merit_id=FIGHTER_IN_LIFE, points=2)]
    lifecycle.lock_chargen(c, rs)
    assert costsmod.charm_cost(rs, c, _terrestrial_ma(rs)) == 14


def test_the_allowance_runs_out_and_the_penalty_rate_returns(rs) -> None:
    """"For every point spent on this Merit, the character can choose to have known ONE
    Terrestrial-level Martial Arts Charm" — so the (N+1)th pays full price again."""
    from exalted_builder.engine import costs as costsmod
    from exalted_builder.models.character import MeritFlawPurchase

    # Essence minimums are irrelevant to PRICE, so the pool is not narrowed by them —
    # there are only two non-Immaculate Terrestrial styles at Essence 1.
    ma = [x for x in rs.charms.values()
          if validate.is_terrestrial_martial_arts(x)
          and not validate.is_immaculate_charm(x)][:3]
    assert len(ma) >= 3
    c = _ghost_with_virtues(comp=5, conv=5)
    c.merits_flaws = [MeritFlawPurchase(merit_id=FIGHTER_IN_LIFE, points=2)]
    lifecycle.lock_chargen(c, rs)

    assert costsmod.charm_cost(rs, c, ma[0]) == 14      # 1st, inside the allowance
    c.charms.append(ma[0].id)
    assert costsmod.charm_cost(rs, c, ma[1]) == 14      # 2nd, still inside
    c.charms.append(ma[1].id)
    assert costsmod.charm_cost(rs, c, ma[2]) == 20      # 3rd, allowance spent


def test_fighter_in_life_is_ghosts_only(rs) -> None:
    """"(VARIABLE POINT MERIT, GHOSTS ONLY)". It must not appear in any other splat's
    dropdown — the exact bug the Advantages tab was built to stop."""
    m = rs.merits_flaws[FIGHTER_IN_LIFE]
    assert m.exalt_types == ["Ghost"]
    assert m.variable_cost
    assert validate.merit_available_to(m, "Ghost", "")
    assert not validate.merit_available_to(m, "Solar", "dawn")
    assert not validate.merit_available_to(m, "Mortal", "")


def test_no_module_outside_merits_names_fighter_in_life() -> None:
    """Decision 0011's containment rule, checked for the newest Merit specifically:
    the allowance is a `MeritEffects` FIELD (`terrestrial_ma_picks`) and the id is
    named only where every other Merit id is."""
    import subprocess

    out = subprocess.run(
        ["grep", "-rl", "--include=*.py", "--include=*.json",
         "fighter-in-life", "exalted_builder/"],
        capture_output=True, text=True).stdout.split()
    assert set(out) <= {"exalted_builder/engine/merits.py",
                        "exalted_builder/data/merits_flaws.json"}, out


def test_ghosts_get_five_dragon_style_and_not_the_immaculate_paths(rs) -> None:
    """The tagging correction of 2026-08-01, from the ghost side — and the reason it
    cost twice. p.234 gives ghosts "only Terrestrial styles":

      * **Five-Dragon Style is Terrestrial**, so a ghost may learn it. It had been
        tagged Celestial-only, which denied it to them.
      * **The five Immaculate Dragon Paths are Celestial**, so a ghost may not. They
        had been tagged `open_to_all`, which handed all five over.

    Mortals with Essence Mastery were wrong in both directions for the same reason;
    their `bar_immaculate_charms` ruling was papering over half of it.
    """
    c = _ghost()
    five = [x for x in rs.charms.values() if x.category == "martial_arts:five-dragon"]
    paths = [x for x in rs.charms.values()
             if x.category.endswith("-dragon") and x.category != "martial_arts:five-dragon"
             and x.category.startswith("martial_arts:")]
    assert five and paths
    assert all(validate.charm_learnable_by_splat(rs, c, x) for x in five)
    assert not any(validate.charm_learnable_by_splat(rs, c, x) for x in paths)


_SPIRIT_WALKING = "dragonblooded.martial-arts.spirit-walking"
_SPIRIT_SIGHT = "dragonblooded.martial-arts.spirit-sight"


def test_ghosts_are_barred_from_spirit_walking(rs) -> None:
    """Human, rules authority, 2026-08-01. The same Charm the Essence Mastery Merit
    withholds from mortals, and for the same reason — it is what opens the Immaculate
    Dragon Paths.

    Modelled as `ExaltDefinition.barred_charm_ids`, i.e. DATA: barring a Charm from a
    splat is a JSON edit, and no module names a Charm id to do it.
    """
    c = _ghost()
    assert not validate.charm_matches_splat(c, rs.charms[_SPIRIT_WALKING], rs)
    assert not validate.charm_learnable_by_splat(rs, c, rs.charms[_SPIRIT_WALKING])
    # Spirit Sight is NOT barred — the ruling named one Charm, and the mortal
    # precedent bars exactly the same one.
    assert validate.charm_learnable_by_splat(rs, c, rs.charms[_SPIRIT_SIGHT])


def test_the_spirit_walking_bar_holds_on_both_entry_points(rs) -> None:
    """`charm_learnable_by_splat` does not merely delegate to `charm_matches_splat` —
    it falls THROUGH a False answer into the Terrestrial-martial-arts grant and the
    p.127 generalist privilege. A bar checked only in the callee is one this route
    walks straight past, which is exactly what happened on the first attempt.

    Driven with every permission a ghost could conceivably be handed.
    """
    from exalted_builder.models.character import HouseRules

    c = _ghost()
    c.caste = "eclipse"
    c.house_rules = HouseRules(eclipse_foreign_charms=True)
    c.chargen_locked = True                 # drops the chargen half of the privilege
    assert not validate.charm_learnable_by_splat(rs, c, rs.charms[_SPIRIT_WALKING])


def test_the_bar_is_splat_scoped_and_leaves_everyone_else_alone(rs) -> None:
    """Dragon-Blooded own the Charm and must keep it; the mortal bar is the Merit's
    and is untouched by this splat-level one."""
    db = Character(id="d", exalt_type="Dragon-Blooded", caste="fire", origin="dynastic")
    assert validate.charm_learnable_by_splat(rs, db, rs.charms[_SPIRIT_WALKING])
    solar = Character(id="s", exalt_type="Solar", caste="dawn")
    assert rs.exalt_for("Solar").barred_charm_ids == []
    assert validate.charm_matches_splat(solar, rs.charms[_SPIRIT_SIGHT], rs)


# --------------------------------------------------------------------------- #
# The 2026-08-01 browser click-through
# --------------------------------------------------------------------------- #
# Two findings, both invisible to 1,684 passing tests, and both the same species: a
# rule the ENGINE knows, in a UI decision that never asked it.

def test_the_arcanoi_page_is_a_charm_tree_page(rs) -> None:
    """FOUND IN THE BROWSER: the Arcanoi tab rendered nothing at all.

    `_is_graph_page()` hardcoded ("abilities", "styles"), so the new group was treated
    as a plain-panel page like Spells — no canvas, no category dropdown, blank tab. The
    group list was hardcoded in FOUR places and adding Arcanoi to three of them left
    the fourth silently wrong, which is why it is now named once.
    """
    import inspect

    from exalted_builder.ui import picker as pickermod

    src = inspect.getsource(pickermod.build_picker)
    assert '_GRAPH_GROUPS = ("abilities", "styles", "arcanoi")' in src
    # …and nothing still decides it by hand.
    assert src.count('("abilities", "styles")') == 0


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_arcanoi_page_renders_its_categories(user) -> None:
    """The behavioural half: the page must offer its paths, which only a graph
    page does — a plain-panel page has no category dropdown to put them in.

    Ghost paths render as ONE entry per art, never one per Virtue. The six E:Ab
    paths are single-Virtue; the six multi-Virtue BoBE arts are combined too,
    because their Virtue minimums are per-entry gates that cross Virtues freely
    rather than an organizing axis (see view.virtue_split). A `category:virtue`
    sub-key in the category dropdown would mean the split misfired again.
    """
    from nicegui import ui as nicegui_ui

    await user.open('/ghost-picker')
    cats = next(sel for sel in user.find(nicegui_ui.select).elements
                if "shifting_ghost_clay" in (sel.options or {}))
    for art in ("chains_of_the_ancient_monarchs", "common", "evoke_the_ancient_clay",
                "noble_craftsman_ways", "scholarly_ways", "tenacious_merchants_way",
                "shifting_ghost_clay", "tangled_web"):
        assert art in cats.options, art
    assert not any(":" in o for o in cats.options), \
        "a `category:virtue` sub-key means the ghost Virtue split misfired: " \
        + ", ".join(sorted(o for o in cats.options if ":" in o))


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_ghost_gets_no_combos_tab(user) -> None:
    """FOUND IN THE BROWSER: the Combos tab appeared for a splat the engine already
    refused every Combo for (E:Ab p.234).

    `visible_tabs` took only `locked` — it never asked whether the splat may have
    Combos at all. The tab bar is assembled in `build_app` and nowhere else, so no
    per-tab route could have caught this.

    Asserted on the tab element's VISIBILITY rather than with `should_not_see`:
    `set_visibility(False)` hides through CSS and leaves the element in the DOM, so a
    text search still finds it and would pass whether the fix worked or not.
    """
    from nicegui.elements.tabs import Tab

    await user.open('/ghost-app')
    await user.should_see("Advantages")
    tabs = {t._props.get("name"): t for t in user.client.elements.values()
            if isinstance(t, Tab)}
    assert "Combos" in tabs, "no Combos tab element at all — test is not proving much"
    assert tabs["Combos"].visible is False
    assert tabs["Charms"].visible is True


def test_the_combos_tab_survives_for_everyone_else() -> None:
    """The bar is opt-in, so Solars keep Combos and Alchemicals keep the tab under its
    Arrays label — a Charm-Slot splat has no Combos either, but it has content there."""
    from exalted_builder.ui.builder import resolve_tab, visible_tabs

    assert "Combos" in visible_tabs(False)
    assert "Combos" in visible_tabs(True)
    assert "Combos" not in visible_tabs(False, combos=False)
    # A player sitting on Combos when the tab vanishes lands somewhere real.
    assert resolve_tab("Combos", False, combos=False) == "Edit"
    assert resolve_tab("Combos", False) == "Combos"


def test_has_combos_tab_keeps_the_tab_for_a_charm_slot_splat(rs) -> None:
    """Alchemicals cannot build Combos either, but the same tab renders their Arrays —
    so the question is "is there content", not "may they Combo"."""
    from exalted_builder.ui import view as viewmod

    alch = Character(id="a", exalt_type="Alchemical", caste="orichalcum")
    assert viewmod.has_combos_tab(rs, alch)
    assert viewmod.has_combos_tab(rs, Character(id="s", exalt_type="Solar", caste="dawn"))
    assert not viewmod.has_combos_tab(rs, _ghost())


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_ghost_gets_no_abilities_page(user) -> None:
    """FOUND IN THE BROWSER (2026-08-01), the third of the same species: the Abilities
    page was offered to a ghost, who holds no Ability-keyed Charms at all.

    `GROUPS["abilities"]` was gated on `_all_categories` — truthy for a splat with
    Charms of ANY kind — rather than on the abilities GROUP having anything in it. It
    predates there being other groups, so it was right when written and quietly wrong
    from the moment Martial Arts became a page of its own.

    Not merely cosmetic: an empty Charm-tree page's Category dropdown raises at build
    time, which takes the whole picker down (adding-a-splat.md trap #3).
    """
    from nicegui.elements.toggle import Toggle

    await user.open('/ghost-picker')
    groups: dict = {}
    for el in user.client.elements.values():
        if isinstance(el, Toggle) and "arcanoi" in (el.options or {}):
            groups = el.options
    assert groups, "no page toggle rendered"
    assert "abilities" not in groups
    assert "arcanoi" in groups and "styles" in groups


def test_every_picker_page_is_gated_on_its_own_group(rs) -> None:
    """The engine-side invariant behind it, so the next group added cannot repeat the
    mistake: a page is offered iff this character has a category in THAT group."""
    import inspect

    from exalted_builder.ui import picker as pickermod

    src = inspect.getsource(pickermod.build_picker)
    # The three Charm-tree pages each ask their own predicate.
    for flag in ("_has_abilities", "_has_styles", "_has_arcanoi"):
        assert f"if {flag}:" in src, flag
    assert "if _all_categories:" not in src


def test_the_charm_whose_field_name_lost_its_space(rs) -> None:
    """p.244 prints "PrerequisiteCharms: Essence-DevouringGhost Touch" — the paste
    dropped the space in the FIELD NAME and again inside the Charm name.

    The human hand-corrected this in the JSON; a later re-extract silently overwrote
    the fix, and I read the resulting drop from 50 prerequisites to 49 as the data
    being stale rather than as the extractor being wrong. The parser now derives the
    correction from source, so it survives a re-extract.

    Both halves of the repair are asserted: the prerequisite is attached, AND the line
    is gone from the description it had been swallowed into.
    """
    c = rs.charms["ghost.essence-measuring-thief.feeding-the-lampreys-appetite"]
    assert [p for g in c.prerequisites for p in g] == [
        "ghost.essence-measuring-thief.essence-devouring-ghost-touch"]
    assert not c.description.lower().startswith("prerequisite")
    assert "PrerequisiteCharms" not in c.description


def test_no_arcanos_description_swallowed_a_field_line(rs) -> None:
    """The general guard behind it. A field line that does not match the field regex
    ends up as prose, which is invisible — the Charm merely loses a gate. Catch the
    whole class rather than the one instance that was reported."""
    import re

    leaked = [c.id for c in _arcanoi(rs)
              if re.search(r"(?i)\b(prerequisite\s*charms|minimum\s*(essence|compassion"
                           r"|conviction|temperance|valor)|duration)\s*:", c.description)]
    assert leaked == [], leaked


def test_no_arcanos_name_capitalises_after_an_apostrophe(rs) -> None:
    """`str.title()` treats an apostrophe as a word boundary, so the ALL-CAPS source
    headings came out as "Lamprey'S Appetite". Five Arcanoi were affected (reported at
    the browser, 2026-08-01).

    Asserted over the whole catalogue rather than the five, and over both apostrophe
    characters — the paste uses the curly U+2019, so a check written against the ASCII
    one would have passed while every affected name stayed wrong.
    """
    for c in _arcanoi(rs):
        assert "'S" not in c.name and "’S" not in c.name, c.name


def test_hyphenated_arcanoi_names_keep_both_halves_capitalised(rs) -> None:
    """The reason `string.capwords` is not the fix: it splits on whitespace only and
    would give "Ghost-devil Form"."""
    hyphenated = [c.name for c in _arcanoi(rs) if "-" in c.name]
    assert hyphenated
    for name in hyphenated:
        for half in name.split("-"):
            assert half[:1] == half[:1].upper(), name


def test_the_unspent_arcanoi_pool_is_warned_about_and_named(rs) -> None:
    """A heroic ghost gets six Arcanoi (p.126) and NOTHING said so: every other
    chargen domain warned about its leftovers — Attributes, Abilities, Virtues,
    Backgrounds, Fetters — and the Charm pool warned about none, so a ghost with no
    magic at all read as complete on that axis. The noun comes from
    `ExaltDefinition.charm_noun`, presentation data exactly like `caste_noun`, so
    the warning and the picker's readout cannot disagree about what to call the pool.
    """
    from exalted_builder.engine import validate
    from exalted_builder.models.character import Character

    assert rs.exalt_for("Ghost").charm_noun == "Arcanoi"
    heroic = validate.unspent_budget_issues(
        rs, Character(id="g", exalt_type="Ghost", origin="heroic"))
    line = next(i for i in heroic if i.where == "charms")
    assert line.severity == "warning"
    assert "6 of 6 free Arcanoi are unspent" in line.message

    # The mundane dead get two, from their own budget row (p.126 sidebar) — asserted
    # separately so a row that silently fell back to the heroic one would show.
    mundane = validate.unspent_budget_issues(
        rs, Character(id="m", exalt_type="Ghost", origin="mundane"))
    assert "2 of 2 free Arcanoi are unspent" in next(
        i for i in mundane if i.where == "charms").message
