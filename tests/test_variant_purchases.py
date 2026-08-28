"""Generic variant-menu Charms — `character.variant_purchases`.

Ox-Body Technique and Deadly Beastman Transformation predate this and keep their own
lists; every OTHER Charm carrying `variants` is stored here, keyed by charm_id, so a
new one needs data and nothing else.

Today's only member is Environmental Hazard-Resisting Meditation (Caste Book: Zenith
p.72-73): four named resistances, one per purchase, at most one purchase per
Resistance dot and — `variants_unique` — each version only once.

⚠ This Charm spent a long time misfiled. `docs/status/solar-castebooks.md` recorded
the engine as deliberately unwired, but `variant_menu_reason` keyed on two hardcoded
ids, so the Charm fell through to the ordinary toggle and was stored as a duplicate id
in `character.charms` — which loses WHICH version was taken.
"""

import pytest

from exalted_builder.engine import (advancement, charm_actions, costs, lifecycle,
                                    validate)
from exalted_builder.models.character import AbilityName, Character
from exalted_builder.ui.view import build_package_menu, build_xp_log, package_menu_kind

HAZ = "solar.resistance.environmental-hazard-resisting-meditation"


def _solar(resistance=5, essence=2, **kw):
    char = Character(id="c", exalt_type="Solar", caste="dawn",
                     essence_rating=essence, **kw)
    char.abilities[AbilityName.RESISTANCE] = resistance
    return char


# --- what makes a Charm a variant menu --------------------------------------- #

def test_the_discriminator_is_the_data_not_an_id_list(ruleset):
    """⚠ Every Charm in the catalogue carrying variants IS a variant menu, so there is
    no id list to keep in step. A new one is data alone."""
    char = _solar()
    menus = [c for c in ruleset.charms.values() if c.variants]
    assert menus, "the catalogue has no variant-menu Charms at all"
    for charm in menus:
        own = charm.id in (validate.ox_body_charm_id(ruleset, char),
                           validate.gift_charm_id(ruleset, char))
        assert validate.is_variant_menu_charm(ruleset, char, charm) is not own


def test_an_ordinary_charm_is_not_a_variant_menu(ruleset):
    char = _solar()
    ordinary = ruleset.charms["solar.melee.fire-and-stones-strike"]
    assert not ordinary.variants
    assert validate.is_variant_menu_charm(ruleset, char, ordinary) is False
    assert package_menu_kind(ruleset, char, ordinary.id) == ""


def test_the_hazard_charm_is_one_and_reports_its_kind(ruleset):
    char = _solar()
    assert package_menu_kind(ruleset, char, HAZ) == "variant"


# --- the toggle must refuse it ----------------------------------------------- #

def test_toggling_it_is_refused_rather_than_stored_as_a_duplicate_id(ruleset):
    """⚠ The defect this whole file exists for: without the refusal the Charm went
    into `character.charms` and the chosen version was lost."""
    char = _solar()
    with pytest.raises(advancement.AdvancementError, match="bought as a package"):
        charm_actions.toggle_charm(ruleset, char, HAZ)
    assert char.charms == []
    assert char.variant_purchases == []


# --- the caps ---------------------------------------------------------------- #

def test_the_cap_is_the_lower_of_the_trait_and_the_version_count(ruleset):
    """Zenith p.72-73 prints BOTH — "until she has purchased all four versions" and
    "cannot purchase this Charm more times than she has dots in Resistance"."""
    charm = ruleset.charms[HAZ]
    assert len(charm.variants) == 4 and charm.variants_unique
    # Resistance 5 would allow five, but there are only four versions.
    assert validate.variant_purchase_cap(ruleset, _solar(resistance=5), charm) == 4
    # Resistance 2 binds first.
    assert validate.variant_purchase_cap(ruleset, _solar(resistance=2), charm) == 2


def test_ox_body_variants_are_not_unique(ruleset):
    """The negative control for `variants_unique`: taking the same health-level
    package again is the whole point of Ox-Body."""
    char = _solar()
    ox = validate.ox_body_charm(ruleset, char)
    assert ox is not None and not ox.variants_unique


def test_a_version_cannot_be_taken_twice(ruleset):
    char = _solar()
    charm_actions.add_variant_purchase(ruleset, char, HAZ, ["acid"])
    with pytest.raises(advancement.AdvancementError, match="already been taken"):
        charm_actions.add_variant_purchase(ruleset, char, HAZ, ["acid"])
    assert len(char.variant_purchases) == 1


def test_buying_past_the_cap_is_refused(ruleset):
    """⚠ In practice the VERSION count is what binds, always: the Charm needs
    Resistance 5 to learn at all, so the trait cap can never be below its four
    versions. The trait half of `variant_purchase_cap` is still asserted above as a
    pure function — it is what a second Charm of this shape would lean on."""
    char = _solar(resistance=5)
    for key in ("acid", "extreme_heat", "extreme_cold", "windblown_particles"):
        charm_actions.add_variant_purchase(ruleset, char, HAZ, [key])
    assert len(char.variant_purchases) == 4
    with pytest.raises(advancement.AdvancementError, match="all 4 versions bought"):
        charm_actions.add_variant_purchase(ruleset, char, HAZ, ["acid"])


def test_an_unknown_version_is_refused(ruleset):
    char = _solar()
    with pytest.raises(advancement.AdvancementError, match="Unknown version"):
        charm_actions.add_variant_purchase(ruleset, char, HAZ, ["fire_immunity"])


# --- the enumeration --------------------------------------------------------- #

def test_each_purchase_is_its_own_pick_and_names_its_version(ruleset):
    char = _solar()
    for key in ("acid", "extreme_cold"):
        charm_actions.add_variant_purchase(ruleset, char, HAZ, [key])
    picks = [p for p in validate.charm_picks(ruleset, char)
             if p.source == "variant_purchases"]
    assert len(picks) == 2
    assert "Resistance to Acid" in picks[0].label
    assert "Resistance to Extreme Cold" in picks[1].label
    # It costs a pick from the chargen pool, like any other Charm.
    assert validate.charm_pick_count(ruleset, char) == 2


def test_a_purchase_costs_bonus_points_like_any_other_pick(ruleset):
    """It must reach the BP arithmetic, which consumes the pick enumeration."""
    char = _solar()
    picks = validate.chargen_charm_picks(ruleset, char)
    before = sum(validate.charm_pick_bp_costs(ruleset, char, picks))
    charm_actions.add_variant_purchase(ruleset, char, HAZ, ["acid"])
    picks = validate.chargen_charm_picks(ruleset, char)
    assert sum(validate.charm_pick_bp_costs(ruleset, char, picks)) > before


# --- the lock, XP, the ledger and undo --------------------------------------- #

def test_the_lock_snapshots_the_purchases(ruleset):
    """⚠ A list the snapshot does not copy silently empties at the lock, and the
    chargen audit then reads a character who never bought it."""
    char = _solar()
    charm_actions.add_variant_purchase(ruleset, char, HAZ, ["acid"])
    lifecycle.lock_chargen(char, ruleset)
    assert [p.variants for p in char.chargen_snapshot.variant_purchases] == [["acid"]]


def test_post_lock_it_is_bought_with_xp_and_logged(ruleset):
    char = _solar(chargen_locked=True)
    char.xp_earned = 100
    price = costs.variant_purchase_cost(ruleset, char, ruleset.charms[HAZ])
    assert price > 0
    charm_actions.add_variant_purchase(ruleset, char, HAZ, ["acid"])
    assert advancement.xp_spent(char) == price
    label = build_xp_log(ruleset, char)[-1].label
    assert "Resistance to Acid" in label      # the ledger names the VERSION


def test_the_xp_audit_prices_the_row(ruleset):
    """A domain the audit cannot price silently passes every wrong cost."""
    char = _solar(chargen_locked=True)
    char.xp_earned = 100
    charm_actions.add_variant_purchase(ruleset, char, HAZ, ["acid"])
    char.chargen_snapshot = char.chargen_snapshot or _solar().model_dump()
    lifecycle.lock_chargen(_solar(), ruleset)     # ensure a snapshot exists to audit
    char.xp_log[-1].cost += 7                     # a wrong price must be caught
    codes = {i.code for i in advancement.validate_xp(ruleset, char)}
    assert "xp-cost-mismatch" in codes


def test_undo_gives_back_the_right_purchase(ruleset):
    """⚠ A new XP domain must extend BOTH undo_last and the ledger label, or undo
    hands out a free trait gain."""
    char = _solar(chargen_locked=True)
    char.xp_earned = 100
    for key in ("acid", "extreme_cold"):
        charm_actions.add_variant_purchase(ruleset, char, HAZ, [key])
    advancement.undo_last(ruleset, char)
    assert [p.variants for p in char.variant_purchases] == [["acid"]]
    assert advancement.xp_spent(char) == costs.variant_purchase_cost(
        ruleset, char, ruleset.charms[HAZ])


# --- validation -------------------------------------------------------------- #

def test_a_hand_edited_save_over_the_cap_is_an_issue(ruleset):
    from exalted_builder.models.character import VariantPurchase
    char = _solar(resistance=1)
    char.variant_purchases = [VariantPurchase(charm_id=HAZ, variants=[k])
                              for k in ("acid", "extreme_cold")]
    codes = {i.code for i in validate.check_variant_purchases(ruleset, char)}
    assert "variant-over-cap" in codes


def test_a_repeated_version_is_an_issue(ruleset):
    from exalted_builder.models.character import VariantPurchase
    char = _solar()
    char.variant_purchases = [VariantPurchase(charm_id=HAZ, variants=["acid"])
                              for _ in range(2)]
    codes = {i.code for i in validate.check_variant_purchases(ruleset, char)}
    assert "variant-repeated" in codes


def test_a_clean_set_raises_nothing(ruleset):
    char = _solar()
    for key in ("acid", "extreme_cold"):
        charm_actions.add_variant_purchase(ruleset, char, HAZ, [key])
    assert validate.check_variant_purchases(ruleset, char) == []


# --- the chooser both shells drive ------------------------------------------- #

def test_the_menu_offers_every_version_and_closes_the_taken_ones(ruleset):
    char = _solar()
    charm_actions.add_variant_purchase(ruleset, char, HAZ, ["acid"])
    menu = build_package_menu(ruleset, char, HAZ)
    assert menu.kind == "variant" and menu.bought == 1 and menu.cap == 4
    assert len(menu.picks) == 4                       # the whole printed list shows
    taken = [p for p in menu.picks if p.key == "acid"][0]
    assert taken.reason == "Already taken"
    assert [p.reason for p in menu.picks if p.key != "acid"] == ["", "", ""]
    assert menu.held[0].label == "Resistance to Acid"


def test_the_cap_phrase_names_the_bound_that_actually_binds(ruleset):
    """⚠ "once per dot of Resistance" is untrue for this Charm: it needs Resistance 5
    to learn at all, so its four versions always run out first. Composed once on the
    menu so neither shell can reassemble it wrongly."""
    menu = build_package_menu(ruleset, _solar(), HAZ)
    assert menu.cap_phrase == "one of each of its 4 versions"


def test_ox_bodys_cap_phrase_still_names_its_trait(ruleset):
    """The negative control: a non-unique menu is unchanged."""
    char = _solar()
    menu = build_package_menu(ruleset, char, validate.ox_body_charm_id(ruleset, char))
    assert menu.cap_phrase == "once per dot of Endurance"
