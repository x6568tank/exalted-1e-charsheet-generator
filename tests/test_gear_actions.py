"""engine/gear_actions.py — the equipment mutators both shells drive.

The rules that used to live in `ui/gear.py` and would have been copied into
`qt/gear.py`: what a catalogue re-pick carries across, what an artifact grants, and
which acquisition channel stamps a purchase. Framework-free — no widget in sight.
"""

from exalted_builder.engine import artifacts as artifactsmod, gear_actions, lifecycle
from exalted_builder.models.character import (Armor, ArtifactEntry, BackgroundEntry,
                                              Character, Weapon)


def _solar(**kw) -> Character:
    c = Character(id="c.ga", name="Test", exalt_type="Solar", caste="dawn")
    for k, v in kw.items():
        setattr(c, k, v)
    return c


# --------------------------------------------------------------------------- #
# what a catalogue re-pick carries across
# --------------------------------------------------------------------------- #

def test_repicking_a_weapon_fills_in_the_catalogue_stats(ruleset):
    char = _solar(weapons=[Weapon(name="")])
    gear_actions.set_weapon(ruleset, char, 0, "Long Bow")
    entry = next(w for w in ruleset.weapon_catalog.values() if w.name == "Long Bow")
    assert char.weapons[0].accuracy == entry.accuracy
    assert char.weapons[0].damage == entry.damage


def test_a_name_the_catalogue_does_not_hold_is_a_rename_not_a_reset(ruleset):
    char = _solar(weapons=[Weapon(name="Long Bow", accuracy=4)])
    gear_actions.set_weapon(ruleset, char, 0, "Grandfather's bow")
    assert char.weapons[0].name == "Grandfather's bow"
    assert char.weapons[0].accuracy == 4      # free text renames, it does not blank


def test_a_repick_keeps_the_players_own_quantity_and_material(ruleset):
    char = _solar(weapons=[Weapon(name="Javelin", quantity=12, material="orichalcum")])
    gear_actions.set_weapon(ruleset, char, 0, "Javelin")
    assert char.weapons[0].quantity == 12
    assert char.weapons[0].material == "orichalcum"


def test_a_repick_keeps_the_from_artifact_link(ruleset):
    # ⚠ The link is what stops the pair being charged to the p.131 budget twice.
    char = _solar(weapons=[Weapon(name="Daiklave", from_artifact="artifact:daiklave")])
    gear_actions.set_weapon(ruleset, char, 0, "Daiklave")
    assert char.weapons[0].from_artifact == "artifact:daiklave"


def test_a_repick_keeps_the_acquisition_channel(ruleset):
    """⚠ The regression this extraction found. `ui/gear.py`'s hand-written copy list
    carried `from_artifact` because a comment warned about it, and never knew
    `acquired` existed — so re-picking a cash-bought artifact weapon's own name from
    its dropdown turned it back into a Background-funded one and charged the budget
    for something Resources had paid for."""
    char = _solar(weapons=[Weapon(name="Daiklave", artifact_rating=3,
                                  acquired=artifactsmod.ACQUIRED_PURCHASED)])
    assert artifactsmod.budgeted_items(char) == []
    gear_actions.set_weapon(ruleset, char, 0, "Daiklave")
    assert char.weapons[0].acquired == artifactsmod.ACQUIRED_PURCHASED
    assert artifactsmod.budgeted_items(char) == []


def test_the_same_carry_across_applies_to_armour(ruleset):
    # ⚠ The armour half of this merge had no test until preflight caught it once
    # before; every test written for it had used a weapon.
    char = _solar(armor=[Armor(name="Buff Jacket", material="moonsilver",
                               from_artifact="artifact:x",
                               acquired=artifactsmod.ACQUIRED_PURCHASED)])
    gear_actions.set_armor(ruleset, char, 0, "Buff Jacket")
    assert char.armor[0].material == "moonsilver"
    assert char.armor[0].from_artifact == "artifact:x"
    assert char.armor[0].acquired == artifactsmod.ACQUIRED_PURCHASED


def test_an_out_of_range_index_is_a_no_op(ruleset):
    char = _solar()
    gear_actions.set_weapon(ruleset, char, 3, "Long Bow")
    assert char.weapons == []


# --------------------------------------------------------------------------- #
# granting an artifact's stat line
# --------------------------------------------------------------------------- #

def test_picking_an_artifact_grants_its_gear_half(ruleset):
    char = _solar()
    gear_actions.add_artifact(ruleset, char, "Daiklave")
    assert len(char.weapons) == 1
    assert char.weapons[0].from_artifact == artifactsmod.item_key(
        artifactsmod.SOURCE_ARTIFACT, "Daiklave")


def test_the_granted_pair_is_counted_once(ruleset):
    char = _solar(backgrounds=[BackgroundEntry(name="Artifact", rating=3)])
    gear_actions.add_artifact(ruleset, char, "Daiklave")
    assert len(artifactsmod.budgeted_items(char)) == 1


def test_granting_twice_does_not_breed_daiklaves(ruleset):
    char = _solar()
    gear_actions.add_artifact(ruleset, char, "Daiklave")
    gear_actions.grant_gear(ruleset, char, "Daiklave")
    assert len(char.weapons) == 1


def test_an_artifact_with_no_gear_half_grants_nothing(ruleset):
    """The large majority have none. ⚠ Probed with an artifact that is REAL and is not
    also gear — twenty catalogue artifacts (Daiklave, Grand Daiklave, Myrmidon
    Carapace) are weapons or armour too, and a name the catalogue does not hold at all
    would pass this whether the rule worked or not."""
    assert "Dragon Tear Tiara" in {a.name for a in ruleset.artifact_catalog.values()}
    char = _solar()
    assert gear_actions.grant_gear(ruleset, char, "Dragon Tear Tiara") is False
    assert char.weapons == [] and char.armor == []


def test_a_granted_stat_line_inherits_the_artifacts_channel(ruleset):
    char = _solar()
    lifecycle.lock_chargen(char, ruleset)
    gear_actions.buy(ruleset, char, "artifact:Daiklave")     # cash, charged to nothing
    assert char.weapons[0].acquired == artifactsmod.ACQUIRED_PURCHASED


def test_an_orphaned_cash_bought_stat_line_stays_uncharged(ruleset):
    """⚠ Deleting an artifact deliberately leaves its stat line behind. While linked the
    granted row's channel is invisible (the pair is merged and the ARTIFACT's channel is
    read); orphaned, it is the only record there is — and defaulting to "background"
    charged the p.131 budget for something Resources had paid for."""
    char = _solar()
    lifecycle.lock_chargen(char, ruleset)
    gear_actions.buy(ruleset, char, "artifact:Daiklave")
    gear_actions.remove_artifact(char, 0)
    assert artifactsmod.budgeted_items(char) == []


def test_a_background_funded_orphan_is_still_charged(ruleset):
    """The negative control for the two above. The documented ruling stands: an orphan
    counts as an artifact in its own right again, which is VISIBLE rather than free.
    A fix that made every orphan uncharged would pass those two and break this."""
    char = _solar(backgrounds=[BackgroundEntry(name="Artifact", rating=3)])
    gear_actions.add_artifact(ruleset, char, "Daiklave")
    gear_actions.remove_artifact(char, 0)
    assert [i.name for i in artifactsmod.budgeted_items(char)] == ["Daiklave"]


def test_switching_the_channel_restamps_the_granted_stat_line(ruleset):
    """⚠ Granting copies the channel ONCE, so an artifact switched afterwards would
    leave its stat line claiming the old one — invisible until the pair is broken."""
    char = _solar()
    lifecycle.lock_chargen(char, ruleset)
    gear_actions.add_artifact(ruleset, char, "Daiklave")     # Background-funded
    assert char.weapons[0].acquired == artifactsmod.ACQUIRED_BACKGROUND
    gear_actions.set_acquired(char, 0, artifactsmod.ACQUIRED_PURCHASED)
    assert char.weapons[0].acquired == artifactsmod.ACQUIRED_PURCHASED
    gear_actions.remove_artifact(char, 0)
    assert artifactsmod.budgeted_items(char) == []


def test_the_merged_pair_is_unaffected_by_the_channel_stamp(ruleset):
    # While linked, `artifact_items` merges the two and reads the ARTIFACT's channel.
    char = _solar()
    lifecycle.lock_chargen(char, ruleset)
    gear_actions.buy(ruleset, char, "artifact:Daiklave")
    assert artifactsmod.budgeted_items(char) == []
    assert [i.name for i in artifactsmod.purchased_items(char)] == ["Daiklave"]


def test_deleting_an_artifact_leaves_its_stat_line_behind(ruleset):
    # The row may have been edited, and the orphan counts as an artifact in its own
    # right again — visible rather than free.
    char = _solar()
    gear_actions.add_artifact(ruleset, char, "Daiklave")
    gear_actions.remove_artifact(char, 0)
    assert char.artifacts == []
    assert len(char.weapons) == 1


# --------------------------------------------------------------------------- #
# the shop's key dispatch
# --------------------------------------------------------------------------- #

def test_the_key_decides_which_list_a_purchase_lands_in(ruleset):
    char = _solar()
    gear_actions.buy(ruleset, char, "weapon:Long Bow")
    gear_actions.buy(ruleset, char, "armor:Buff Jacket")
    assert [w.name for w in char.weapons] == ["Long Bow"]
    assert [a.name for a in char.armor] == ["Buff Jacket"]


def test_a_goods_purchase_carries_its_printed_price(ruleset):
    char = _solar()
    entry = next(g for g in ruleset.gear_catalog.values()
                 if g.kind == "goods" and g.resources_cost)
    gear_actions.buy(ruleset, char, f"goods:{entry.id}")
    assert char.gear[0].resources_cost == entry.resources_cost


def test_a_custom_key_adds_a_blank_row_of_that_kind(ruleset):
    char = _solar()
    gear_actions.buy(ruleset, char, "custom:gear")
    assert len(char.gear) == 1 and char.gear[0].name == ""
    assert char.weapons == [] and char.armor == []


def test_a_cash_bought_artifact_is_stamped_purchased(ruleset):
    # Decision 0017's in-play channel: bought with cash, charged to no budget.
    char = _solar()
    lifecycle.lock_chargen(char, ruleset)
    entry = next(a for a in ruleset.artifact_catalog.values() if a.resources_cost)
    gear_actions.buy(ruleset, char, f"artifact:{entry.name}")
    assert char.artifacts[-1].acquired == artifactsmod.ACQUIRED_PURCHASED
    assert artifactsmod.budgeted_items(char) == []


def test_an_unknown_key_does_nothing(ruleset):
    char = _solar()
    assert gear_actions.buy(ruleset, char, "nonsense:thing") == ""
    assert gear_actions.buy(ruleset, char, "") == ""
    assert char.weapons == [] and char.gear == [] and char.artifacts == []


# --------------------------------------------------------------------------- #
# the merit-gated channel
# --------------------------------------------------------------------------- #

def test_a_merit_gated_artifact_is_stamped_legendary(ruleset):
    """A plot device is charged to no budget — the Legendary Artifact Merit was its
    price — and the stamp comes from the CATALOGUE at pick time, so the player never
    has to know the channel exists."""
    gated = [a for a in ruleset.artifact_catalog.values() if a.requires_merit]
    assert gated, "no merit-gated artifact in the catalogue to probe with"
    assert gear_actions.acquisition_for(gated[0]) == artifactsmod.ACQUIRED_LEGENDARY
    ordinary = next(a for a in ruleset.artifact_catalog.values()
                    if not a.requires_merit)
    assert gear_actions.acquisition_for(ordinary) == artifactsmod.ACQUIRED_BACKGROUND


# --------------------------------------------------------------------------- #
# the library codec
# --------------------------------------------------------------------------- #

def test_a_library_row_drops_the_ownership_fields(ruleset):
    """A `Weapon` is not a `WeaponType`: `quantity` and `from_artifact` are facts about
    ownership, not about the design, and shipping them into the library would put
    ownership state in a catalogue."""
    payload = gear_actions.library_payload(
        "weapons", Weapon(name="Grandfather's bow", accuracy=3, quantity=4,
                          from_artifact="artifact:x"))
    assert payload["accuracy"] == 3
    assert "quantity" not in payload and "from_artifact" not in payload


def test_an_armour_library_row_defaults_the_weight_it_cannot_know(ruleset):
    # ⚠ `weight` is REQUIRED by ArmorType and an owned row carries none, so it is
    # defaulted — and the caller says so out loud rather than guessing silently.
    payload = gear_actions.library_payload("armor", Armor(name="Mine", soak_lethal=2))
    assert payload["weight"] == "Light"


def test_reserved_ids_span_every_printed_catalogue(ruleset):
    ids = gear_actions.reserved_ids(ruleset)
    assert set(ruleset.weapon_catalog) <= ids
    assert set(ruleset.armor_catalog) <= ids
    assert set(ruleset.gear_catalog) <= ids
    assert set(ruleset.artifact_catalog) <= ids
