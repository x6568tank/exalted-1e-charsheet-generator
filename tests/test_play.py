"""Tests for the in-play tracker: the PlayState model, its persistence round-trip
and back-compat, the build_play_view capacities, and the invariant that play-state
never leaks into chargen / validation (it is a separate layer)."""

from exalted_builder import persistence
from exalted_builder.engine import validate
from exalted_builder.models.character import Character, Damage, PlayState
from exalted_builder.models.rules import (
    AbilityName, CasteDefinition, Charm, CharmType, RuleSet)
from exalted_builder.ui import view as viewmod


def _ruleset() -> RuleSet:
    castes = {"dawn": CasteDefinition(
        id="dawn", label="Dawn",
        caste_abilities=[AbilityName.ARCHERY, AbilityName.BRAWL,
                         AbilityName.MARTIAL_ARTS, AbilityName.MELEE, AbilityName.THROWN])}
    charms = {"melee": Charm(id="melee", name="M", category="melee",
                             type=CharmType.SIMPLE, min_ability=1, min_essence=1)}
    return RuleSet(castes=castes, charms=charms)


def test_play_defaults_to_none():
    assert Character(id="c").play is None


def test_old_save_without_play_loads():
    """A save predating the in-play layer (no `play` key) loads with play=None."""
    c = persistence.character_from_json('{"id": "legacy", "name": "Old"}')
    assert c.play is None


def test_playstate_roundtrips_through_json():
    c = Character(id="c")
    c.play = PlayState(health=[Damage.BASHING, Damage.LETHAL, None],
                       motes_personal_spent=4, motes_peripheral_spent=7,
                       willpower_spent=2, limit=3)
    back = persistence.character_from_json(persistence.character_to_json(c))
    assert back.play.health == [Damage.BASHING, Damage.LETHAL, None]
    assert back.play.motes_personal_spent == 4
    assert back.play.willpower_spent == 2
    assert back.play.limit == 3


def test_damage_marks_serialize_as_shorthand():
    """Damage marks persist as the 1e shorthand strings / x *."""
    c = Character(id="c")
    c.play = PlayState(health=[Damage.AGGRAVATED])
    assert '"*"' in persistence.character_to_json(c)


def test_limit_is_capped_at_ten():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        PlayState(limit=11)


def test_play_state_does_not_affect_validation():
    """Play-state is a separate layer — setting damage/motes/limit must not change
    any validation issue (chargen or the always-on checks)."""
    rs, c = _ruleset(), Character(id="c", caste="dawn")
    before = [i.code for i in validate.validate(rs, c)]
    before_chargen = [i.code for i in validate.validate_chargen(rs, c)]
    c.play = PlayState(health=[Damage.LETHAL] * 7, motes_personal_spent=99,
                       willpower_spent=5, limit=10)
    assert [i.code for i in validate.validate(rs, c)] == before
    assert [i.code for i in validate.validate_chargen(rs, c)] == before_chargen


def test_build_play_view_capacities_match_engine():
    rs = _ruleset()
    c = Character(id="c", caste="dawn", essence_rating=3)
    pv = viewmod.build_play_view(rs, c)
    # base health track is 7 levels (-0/-1/-1/-2/-2/-4/Incap) with no bonuses
    assert len(pv.health_boxes) == 7
    assert pv.health_boxes[-1].incapacitated and pv.health_boxes[-1].label == "Incap"
    # Solar: personal = Ess*3 + WP, peripheral = Ess*7 + WP + ΣVirtues; WP=2, ΣV=4
    assert pv.personal_max == 3 * 3 + 2
    assert pv.peripheral_max == 3 * 7 + 2 + 4
    assert pv.willpower_max == 2


# --------------------------------------------------------------------------- #
# decision 0006, enforced structurally rather than by inspection
# --------------------------------------------------------------------------- #

def test_validate_never_imports_the_play_module():
    """⚠ decision 0006 — play-state is validation-isolated.

    `engine/play.py` now sits importably beside `engine/validate/`, so the cheap
    mistake is a convenience import that quietly lets a marked health box change what
    a character may legally buy. The behavioural tests above cover the cases someone
    thought to write; this covers the ones they did not, by forbidding the edge itself.
    """
    import ast
    from pathlib import Path

    import exalted_builder

    validate_dir = Path(exalted_builder.__file__).parent / "engine" / "validate"
    modules = sorted(validate_dir.glob("*.py"))
    assert modules, "no validate modules found — has the package moved?"
    offenders = []
    for path in modules:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = {a.name for a in node.names}
                if (node.module or "").endswith("play") or "play" in names:
                    offenders.append(f"{path.name}: from {node.module} import "
                                     f"{', '.join(sorted(names))}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.endswith(".play") or alias.name == "play":
                        offenders.append(f"{path.name}: import {alias.name}")
    assert offenders == [], offenders


def test_validate_never_reads_the_play_field():
    """The other half: no `.play` attribute access anywhere in validation. An import
    guard alone is dodgeable — `character.play` needs no import."""
    import ast
    from pathlib import Path

    import exalted_builder

    validate_dir = Path(exalted_builder.__file__).parent / "engine" / "validate"
    offenders = []
    for path in sorted(validate_dir.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Attribute) and node.attr == "play":
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], offenders


def test_validate_never_reads_the_attunement_flag():
    """The same bar for `Weapon.attuned` / `Armor.attuned_pool` (decision 0006).

    ⚠ These two sit on the GEAR row, not in `PlayState`, because a gear row has no
    stable key to point at from outside (two identical daiklaves collapse onto one
    `artifacts.item_key`). That puts a PLAY fact inside the permanent model, in the
    same objects `validate/` already walks for the Artifact budget — so the isolation
    the two tests above get from the module boundary has to be asserted directly here.

    What you are attuned to must never change what you may legally buy.
    """
    import ast
    from pathlib import Path

    import exalted_builder

    watched = {"attuned", "attuned_pool"}
    validate_dir = Path(exalted_builder.__file__).parent / "engine" / "validate"
    modules = sorted(validate_dir.glob("*.py"))
    assert modules, "no validate modules found — has the package moved?"
    offenders = []
    for path in modules:
        for node in ast.walk(ast.parse(path.read_text())):
            # `w.attuned`, and the getattr spelling that dodges an attribute check.
            if isinstance(node, ast.Attribute) and node.attr in watched:
                offenders.append(f"{path.name}:{node.lineno} .{node.attr}")
            elif isinstance(node, ast.Constant) and node.value in watched:
                offenders.append(f"{path.name}:{node.lineno} {node.value!r}")
    assert offenders == [], offenders


# --------------------------------------------------------------------------- #
# artifact attunement — the derivation (phase 2)
# --------------------------------------------------------------------------- #

def _attune_rs():
    """A ruleset with the two magical materials the doubling test needs."""
    from exalted_builder.models.rules import MagicalMaterial
    rs = _ruleset()
    return rs.model_copy(update={"material_catalog": {
        "orichalcum": MagicalMaterial(id="orichalcum", name="Orichalcum",
                                      exalt_type="Solar"),
        "jade": MagicalMaterial(id="jade", name="Jade",
                                exalt_type="Dragon-Blooded")}})


def _armed(**kw):
    from exalted_builder.models.character import Weapon
    c = Character(id="c.at", name="A", exalt_type="Solar", caste="dawn",
                  essence_rating=3)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_committed_ignores_unattuned_items():
    from exalted_builder.engine import derive
    from exalted_builder.models.character import Weapon
    char = _armed(weapons=[Weapon(name="Daiklave", artifact_rating=3, attunement=5)])
    assert derive.committed_attunement(_attune_rs(), char) == {"personal": 0,
                                                               "peripheral": 0}


def test_committed_sums_into_the_named_pool():
    from exalted_builder.engine import derive
    from exalted_builder.models.character import Weapon
    char = _armed(weapons=[
        Weapon(name="Daiklave", artifact_rating=3, attunement=5, attuned=True,
               attuned_pool="personal"),
        Weapon(name="Grand Daiklave", artifact_rating=3, attunement=8, attuned=True,
               attuned_pool="peripheral")])
    assert derive.committed_attunement(_attune_rs(), char) == {"personal": 5,
                                                               "peripheral": 8}


def test_quantity_never_multiplies_the_commitment():
    """⚠ Twenty attuned arrows are not twenty attunements. The count exists for
    ammunition and nothing in the engine reads it (decision 0008); `ArtifactItem` does
    not carry it, which is what makes that structural rather than remembered."""
    from exalted_builder.engine import derive
    from exalted_builder.models.character import Weapon
    char = _armed(weapons=[Weapon(name="Sky-Cutter", artifact_rating=2, attunement=3,
                                  attuned=True, quantity=20)])
    assert derive.committed_attunement(_attune_rs(), char)["peripheral"] == 3


def test_a_non_user_of_the_material_pays_double():
    """Jade for a non-Terrestrial. The general rule behind the Hearthstone Compass's
    printed exception (human's ruling 2026-09-03)."""
    from exalted_builder.engine import derive
    from exalted_builder.models.character import Weapon
    rs = _attune_rs()
    jade = Weapon(name="Daiklave", artifact_rating=3, attunement=5, attuned=True,
                  material="jade")
    assert derive.committed_attunement(rs, _armed(weapons=[jade]))["peripheral"] == 10


def test_a_user_of_the_material_pays_the_printed_number():
    """The negative control for the doubling — same item, resonant material."""
    from exalted_builder.engine import derive
    from exalted_builder.models.character import Weapon
    rs = _attune_rs()
    ori = Weapon(name="Daiklave", artifact_rating=3, attunement=5, attuned=True,
                 material="orichalcum")
    assert derive.committed_attunement(rs, _armed(weapons=[ori]))["peripheral"] == 5


def test_a_mundane_artifact_never_doubles():
    """⚠ "Not a user" is not the same question as `applied_material(...) is None`,
    which is ALSO None for an item naming no material at all."""
    from exalted_builder.engine import derive
    from exalted_builder.models.character import Weapon
    rs = _attune_rs()
    plain = Weapon(name="Daiklave", artifact_rating=3, attunement=5, attuned=True)
    assert derive.committed_attunement(rs, _armed(weapons=[plain]))["peripheral"] == 5


def test_a_linked_pair_commits_once_in_the_derivation():
    """The double-count guard, reached through the derivation rather than the fold."""
    from exalted_builder.engine import artifacts as artifactsmod, derive
    from exalted_builder.models.character import ArtifactEntry, Weapon
    key = artifactsmod.item_key(artifactsmod.SOURCE_ARTIFACT, "Daiklave")
    char = _armed(
        artifacts=[ArtifactEntry(name="Daiklave", rating=3, attunement=5, attuned=True)],
        weapons=[Weapon(name="Daiklave", artifact_rating=3, from_artifact=key,
                        attunement=5, attuned=True)])
    assert derive.committed_attunement(_attune_rs(), char)["peripheral"] == 5


def test_build_play_view_shrinks_the_named_pool():
    from exalted_builder.models.character import Weapon
    rs = _attune_rs()
    bare = _armed()
    before = viewmod.build_play_view(rs, bare)
    char = _armed(weapons=[Weapon(name="Daiklave", artifact_rating=3, attunement=5,
                                  attuned=True, attuned_pool="peripheral")])
    after = viewmod.build_play_view(rs, char)
    assert after.peripheral_max == before.peripheral_max - 5
    assert after.personal_max == before.personal_max      # the other pool is untouched
    assert after.committed_peripheral == 5


def test_clearing_the_flag_gives_the_pool_back():
    """The negative control for the subtraction — the same character, unattuned."""
    from exalted_builder.models.character import Weapon
    rs = _attune_rs()
    weapon = Weapon(name="Daiklave", artifact_rating=3, attunement=5, attuned=True)
    char = _armed(weapons=[weapon])
    shrunk = viewmod.build_play_view(rs, char).peripheral_max
    weapon.attuned = False
    assert viewmod.build_play_view(rs, char).peripheral_max == shrunk + 5


def test_a_merged_pool_commitment_lands_on_the_real_pool(ruleset):
    """⚠ A ghost's Personal pool is 0 BY RULE (p.41), so a commitment routed there
    would vanish and the ghost would attune for free. `attuned_pool` is ignored, not
    trusted, when the pools are merged.

    ⚠ Takes the REAL ruleset, not this module's synthetic one: `_ruleset()` defines no
    Ghost exalt, so `essence_pool_is_merged` answered False and the test passed the
    commitment straight into Personal — a green run that proved nothing.
    """
    from exalted_builder.engine import derive
    from exalted_builder.models.character import Weapon
    rs = ruleset
    ghost = Character(id="g", name="G", exalt_type="Ghost", essence_rating=3,
                      # ⚠ No material: soulsteel resonates with ABYSSALS, so naming it
                      # would double the cost for a ghost and confuse two rules in one
                      # assertion.
                      weapons=[Weapon(name="Grave Blade", artifact_rating=3,
                                      attunement=6, attuned=True,
                                      attuned_pool="personal")])
    committed = derive.committed_attunement(rs, ghost)
    assert committed == {"personal": 0, "peripheral": 6}
    view = viewmod.build_play_view(rs, ghost)
    assert view.single_pool is True
    assert view.committed_peripheral == 6


def test_a_pool_cannot_go_negative():
    from exalted_builder.models.character import Weapon
    rs = _attune_rs()
    char = _armed(weapons=[Weapon(name="Absurd", artifact_rating=5, attunement=999,
                                  attuned=True)])
    assert viewmod.build_play_view(rs, char).peripheral_max == 0


def test_already_spent_motes_clamp_on_read_without_touching_the_save():
    """⚠ Attuning shrinks the maximum under a spend that was legal a moment ago.
    `play.set_motes` clamps to a cap its CALLER passes in and never sees this. The
    clamp must not be written back: un-attuning has to give the motes back."""
    from exalted_builder.models.character import Weapon
    rs = _attune_rs()
    weapon = Weapon(name="Daiklave", artifact_rating=3, attunement=5, attuned=False)
    char = _armed(weapons=[weapon])
    full = viewmod.build_play_view(rs, char)
    char.play = PlayState(motes_peripheral_spent=full.peripheral_max)
    weapon.attuned = True
    view = viewmod.build_play_view(rs, char)
    _, spent = viewmod.spent_motes(view, char.play)
    assert spent == view.peripheral_max                      # clamped for display
    assert char.play.motes_peripheral_spent == full.peripheral_max   # save untouched
    weapon.attuned = False                                   # and it comes back whole
    restored = viewmod.build_play_view(rs, char)
    assert viewmod.spent_motes(restored, char.play)[1] == full.peripheral_max


def test_spent_motes_tolerates_no_play_state():
    rs = _attune_rs()
    view = viewmod.build_play_view(rs, _armed())
    assert viewmod.spent_motes(view, None) == (0, 0)


def test_a_character_with_no_resonant_material_pays_the_printed_cost(ruleset):
    """⚠ A mortal is a "user" of no Magical Material, so the naive doubling would
    charge them double for every artifact in the game. Both printed routes to attuning
    say otherwise: Magical Attunement is "provided she pays the normal commitment cost.
    She never gains any bonus from an artifact's Magical Material" (PG p.120), and the
    God-Blooded version says the same (PG p.66). The doubling is about wielding ANOTHER
    Exalt's material; a mortal is not on that axis.

    ⚠ REAL ruleset — the discriminator is "does any material in the catalogue resonate
    with this Exalt type", which a synthetic two-material fixture answers wrongly.
    """
    from exalted_builder.engine import derive
    from exalted_builder.models.character import Weapon
    jade = dict(name="Daiklave", artifact_rating=3, attunement=5, attuned=True,
                material="jade")
    mortal = Character(id="m", name="M", exalt_type="Mortal", essence_rating=1,
                       weapons=[Weapon(**jade)])
    assert derive.committed_attunement(ruleset, mortal)["peripheral"] == 5


def test_an_exalt_of_the_wrong_material_still_pays_double(ruleset):
    """The negative control for the carve-out above — same jade daiklave, a Solar.
    A fix that exempted everyone would pass the mortal test and break this."""
    from exalted_builder.engine import derive
    from exalted_builder.models.character import Weapon
    solar = Character(id="s", name="S", exalt_type="Solar", caste="dawn",
                      essence_rating=3,
                      weapons=[Weapon(name="Daiklave", artifact_rating=3, attunement=5,
                                      attuned=True, material="jade")])
    assert derive.committed_attunement(ruleset, solar)["peripheral"] == 10


def test_a_terrestrial_pays_the_printed_cost_for_jade(ruleset):
    """And the resonant case, so the three readings are separated: printed for a user,
    double for the wrong Exalt, printed for someone with no material at all."""
    from exalted_builder.engine import derive
    from exalted_builder.models.character import Weapon
    db = Character(id="d", name="D", exalt_type="Dragon-Blooded", caste="fire",
                   essence_rating=3,
                   weapons=[Weapon(name="Daiklave", artifact_rating=3, attunement=5,
                                   attuned=True, material="jade")])
    assert derive.committed_attunement(ruleset, db)["peripheral"] == 5


def test_a_magical_attunement_holder_never_gets_the_material_bonus(ruleset):
    """⚠ Both Merits that let a non-Exalt attune refuse the bonus in as many words:
    "She never gains any bonus from an artifact's Magical Material" (mortal, PG p.120)
    and "cannot receive a Magical Material bonus from artifacts regardless of how many
    motes they spend" (God-Blooded, PG p.66).

    ⚠ The DISCRIMINATOR matters. A mortal's exalt_type matches no material, so the
    exalt_type test alone already returns None and this rule looked implemented while
    having no implementation at all. The probe therefore uses a character whose type
    DOES resonate — a Solar with orichalcum — because that is the only shape that can
    tell the flag apart from the coincidence.
    """
    from exalted_builder.engine import derive
    from exalted_builder.models.character import MeritFlawPurchase, Weapon
    ori = Weapon(name="Daiklave", artifact_rating=3, material="orichalcum")
    solar = Character(id="s", name="S", exalt_type="Solar", caste="dawn",
                      essence_rating=3, weapons=[ori])
    assert derive.applied_material(ruleset, solar, ori) is not None   # control
    solar.merits_flaws.append(MeritFlawPurchase(merit_id="thaum.magical-attunement"))
    assert derive.applied_material(ruleset, solar, ori) is None


def test_the_material_bar_reaches_the_effective_stats(ruleset):
    """The binding test: a flag nothing reads is the bug this whole session is about."""
    from exalted_builder.engine import derive
    from exalted_builder.models.character import MeritFlawPurchase, Weapon
    # ⚠ Accuracy, not damage: orichalcum's printed deltas are speed/accuracy/defence
    # and its `weapon_damage` is 0, so a damage probe compares 5 to 5 and passes
    # whether the bar works or not.
    ori = Weapon(name="Daiklave", artifact_rating=3, accuracy=2, material="orichalcum")
    solar = Character(id="s", name="S", exalt_type="Solar", caste="dawn",
                      essence_rating=3, weapons=[ori])
    assert derive.effective_weapon(ruleset, solar, ori).accuracy > ori.accuracy
    solar.merits_flaws.append(MeritFlawPurchase(merit_id="thaum.magical-attunement"))
    assert derive.effective_weapon(ruleset, solar, ori).accuracy == ori.accuracy
