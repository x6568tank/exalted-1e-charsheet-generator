"""`engine.validate.charm_picks` — the one canonical Charm-pick enumeration.

A repeatable Charm (Ox-Body Technique, Deadly Beastman Transformation) and a training
camp's granted Charms each live on their OWN `Character` list, not in
`character.charms`. Every consumer that walked `character.charms` used to special-case
each list by hand, and four separately failed to when Gifts landed. These tests pin the
enumeration and, more importantly, pin that the UI's Charm rows and pick counters agree
with it — so a fifth list is one change in the engine, not a scavenger hunt.
"""
from pathlib import Path

import pytest

from exalted_builder import rules_db
from exalted_builder.engine import validate
from exalted_builder.models.character import (
    BeastmanGiftPurchase, Character, OxBodyPurchase,
)
from exalted_builder.models.rules import AbilityName as AB
from exalted_builder.ui import view

DATA_DIR = Path(__file__).resolve().parents[1] / "exalted_builder" / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def test_plain_charms_enumerate_in_order_and_all_count(rs):
    c = Character(id="c.plain", exalt_type="Solar", caste="dawn")
    c.charms = ["solar.melee.excellent-strike", "solar.melee.hungry-tiger-technique"]
    picks = validate.charm_picks(rs, c)
    assert [p.charm_id for p in picks] == c.charms
    assert [p.label for p in picks] == ["Excellent Strike", "Hungry Tiger Technique"]
    assert all(p.source == "charms" and p.counts_toward_pool for p in picks)
    assert validate.charm_pick_count(rs, c) == 2


def test_repeatable_purchases_yield_one_entry_each_labelled_by_variant(rs):
    """The whole point of the separate list: N copies must be representable, and each
    copy is its own pick against the chargen pool."""
    c = Character(id="c.ox", exalt_type="Solar", caste="dawn")
    c.abilities[AB.ENDURANCE] = 3
    c.charms = ["solar.melee.excellent-strike"]
    ox = validate.ox_body_charm(rs, c)
    keys = [v.key for v in ox.variants][:2]
    c.ox_body = [OxBodyPurchase(variant=keys[0]), OxBodyPurchase(variant=keys[1])]

    picks = validate.charm_picks(rs, c)
    assert validate.charm_pick_count(rs, c) == 3
    ox_picks = [p for p in picks if p.source == "ox_body"]
    assert len(ox_picks) == 2
    labels = {v.key: v.label for v in ox.variants}
    assert [p.label for p in ox_picks] == [
        f"{ox.name} ({labels[keys[0]]})", f"{ox.name} ({labels[keys[1]]})"]
    assert all(p.charm_id == ox.id and p.counts_toward_pool for p in ox_picks)


def test_beastman_gifts_are_enumerated_for_a_lunar(rs):
    c = Character(id="c.lunar", exalt_type="Lunar", caste="full-moon")
    gift = validate.gift_charm(rs, c)
    assert gift is not None, "Lunar must name a Gift-granting Charm"
    keys = [v.key for v in gift.variants][:2]
    c.beastman_gifts = [BeastmanGiftPurchase(gifts=keys)]

    (pick,) = [p for p in validate.charm_picks(rs, c) if p.source == "beastman_gifts"]
    labels = {v.key: v.label for v in gift.variants}
    assert pick.label == f"{gift.name} ({labels[keys[0]]}, {labels[keys[1]]})"
    assert pick.charm_id == gift.id and pick.counts_toward_pool


def test_granted_charms_are_enumerated_but_cost_no_pick(rs):
    """A training camp's package (Cult of the Illuminated, p.90) is free — it must
    appear on the sheet but must never inflate the pick counter."""
    c = Character(id="c.granted", exalt_type="Solar", caste="dawn", origin="illuminated")
    c.charms = ["solar.melee.excellent-strike"]
    c.granted_charms = ["solar.endurance.ox-body-technique",
                        "solar.presence.harmonious-presence-meditation"]
    picks = validate.charm_picks(rs, c)
    granted = [p for p in picks if p.source == "granted"]
    assert len(granted) == 2
    assert all(not p.counts_toward_pool for p in granted)
    assert all(p.label.endswith(" (granted)") for p in granted)
    assert validate.charm_pick_count(rs, c) == 1


def test_an_unresolvable_id_is_still_yielded(rs):
    """A stale save must show the broken row rather than silently drop it."""
    c = Character(id="c.stale", exalt_type="Solar", caste="dawn")
    c.charms = ["solar.melee.no-such-charm"]
    (pick,) = validate.charm_picks(rs, c)
    assert pick.name == pick.label == "solar.melee.no-such-charm"
    assert pick.category == ""


def _kitchen_sink(rs):
    """One character holding every kind of pick at once."""
    c = Character(id="c.all", exalt_type="Solar", caste="dawn", origin="illuminated")
    c.abilities[AB.ENDURANCE] = 2
    c.charms = ["solar.melee.excellent-strike", "solar.brawl.ferocious-jab"]
    ox = validate.ox_body_charm(rs, c)
    c.ox_body = [OxBodyPurchase(variant=ox.variants[0].key)]
    c.granted_charms = ["solar.presence.harmonious-presence-meditation"]
    return c


def test_the_sheet_renders_exactly_one_row_per_pick_in_pick_order(rs):
    """`build_sheet_view` must not enumerate the four lists itself. Pinning row order
    and count against `charm_picks` is what makes a fifth list a one-line change."""
    c = _kitchen_sink(rs)
    picks = validate.charm_picks(rs, c)
    rows = view.build_sheet_view(rs, c).charms
    assert [r.name for r in rows] == [p.label for p in picks]


def test_the_pick_counters_agree_with_the_engine(rs):
    """The picker's and editor's chargen headers both report a pick count. They used to
    add the lists up independently; both now read `charm_pick_count`, so this asserts
    the number they show — 3 picks, with the granted Charm free."""
    c = _kitchen_sink(rs)
    assert validate.charm_pick_count(rs, c) == 3
    assert len(validate.charm_picks(rs, c)) == 4      # the granted one is still listed


def test_the_second_repeatable_solar_charm_is_the_case_this_unblocks(rs):
    """Environmental Hazard-Resisting Meditation (Caste Book: Zenith p.72-73) is
    repeatable in the DATA but has no `Character` list, so today it enumerates as a
    single ordinary pick. When it gets a list, `charm_picks` is the one place that
    needs a new branch — and this test is where the change should show up."""
    c = Character(id="c.hazard", exalt_type="Solar", caste="zenith")
    cid = "solar.resistance.environmental-hazard-resisting-meditation"
    assert rs.charms[cid].repeatable_cap_ability == "resistance"
    c.charms = [cid]
    (pick,) = validate.charm_picks(rs, c)
    assert pick.source == "charms" and pick.counts_toward_pool
    assert pick.label == "Environmental Hazard-Resisting Meditation"
