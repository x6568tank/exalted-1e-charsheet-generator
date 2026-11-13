"""
ui/view/play_state.py — the play capacities that the in-play tracker reads, and
the party card of the Storyteller. Nothing flows back to the character.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Optional

from ...engine import derive
from ...models.character import Character
from ...models.rules import AbilityName, RuleSet

from ._base import _health_label


# --------------------------------------------------------------------------- #
# Play-state capacities (the in-play tracker reads these; nothing flows back) #
# --------------------------------------------------------------------------- #

@dataclass
class PlayHealthBox:
    label: str            # "-0", "-1", "Incap", with " ★" for a bonus/charm level
    incapacitated: bool


@dataclass
class PlayView:
    """The capacities the Play tab overlays its fill-state onto, all derived from
    the permanent character — the box count/labels of the health track and the
    mote/Willpower maxima. The tracker stores only the fill marks (Character.play)."""
    health_boxes: list[PlayHealthBox]
    personal_max: int
    peripheral_max: int
    willpower_max: int
    # The two pools merged into one (Beacon of Power). Carried rather than inferred
    # from `personal_max == 0`, which cannot tell "merged by rule" from "this splat
    # has no Personal pool" — the same distinction `essence_single_pool` draws for
    # the sheet. ⚠ Without it the tracker renders a Personal box reading 0/0, which
    # looks like a bug rather than a rule.
    single_pool: bool = False
    # Motes of that maximum drawable without a Willpower roll (Essence Awareness),
    # or None when all of them are. The tracker still counts spending against the
    # FULL maximum — the restricted two thirds are spendable, just not freely — so
    # this is a marker on the track, never a second cap. The roll is the table's to
    # make (decision 0009); the tracker only says where the line falls.
    free_max: Optional[int] = None
    # The fatigue-roll difficulty of each worn piece, "Buff Jacket 1" (core p.332:
    # the roll is Stamina + Endurance "with a difficulty equal to the armor's fatigue
    # value"). Read through effective_armor, so jade shows no difficulty at all for a
    # Dragon-Blooded — "jade-alloy armor has no fatigue value" (p.345). A difficulty
    # is not a dice-pool term, so it is reference text beside the counter, never a
    # line in a pool.
    fatigue_difficulties: list[str] = dc_field(default_factory=list)
    # Motes of each maximum already committed to attuned artifacts. The maxima above
    # are ALREADY reduced by these — this is carried so the tracker can say WHY the
    # pool is short. "Peripheral 4/10" with no explanation reads as a bug, the same
    # reasoning that put `single_pool` on this view.
    committed_personal: int = 0
    committed_peripheral: int = 0


def worst_penalty(play: PlayView, marks: list) -> str:
    """The label of the deepest marked health box — a convenience read of the marks
    (it does not enforce fill order). 'none' when undamaged."""
    deepest = None
    for box, mark in zip(play.health_boxes, marks):
        if mark is not None:
            deepest = box
    if deepest is None:
        return "none"
    return "Incapacitated" if deepest.incapacitated else deepest.label


def committed_note(play: PlayView, *, compact: bool = False) -> str:
    """Why the pool is short, or "" when nothing is committed.

    The maxima on `play` are ALREADY reduced, so an unexplained short pool reads as a
    defect — the same reasoning that put `single_pool` on the view. `compact` is the
    Storyteller surfaces' shorter form: those cards show one row per party member and
    a full sentence each would bury the numbers they exist to show.

    ⚠ ONE copy of this string. Four surfaces render mote inputs (ui/play, ui/gm,
    qt/play, qt/party) and four hand-written variants is how three of them end up
    saying something the fourth does not.
    """
    parts = []
    if play.committed_personal:
        parts.append(f"{play.committed_personal} Personal")
    if play.committed_peripheral:
        parts.append(f"{play.committed_peripheral} Peripheral")
    if not parts:
        return ""
    if compact:
        return f"− {' + '.join(parts)} attuned"
    return (f"{' and '.join(parts)} committed to attuned artifacts, and already taken "
            f"off the maximum above.")


def free_motes_note(play: PlayView) -> str:
    """The note under the mote inputs that says how many motes are free, or "".

    Essence Awareness makes one third of the pool free. The rest needs a Willpower
    roll, and the table makes that roll. ⚠ The inputs still go to the full maximum.
    This is a note, never a second limit.

    ⚠ ONE copy of this string, for ui/play, qt/play and server/table_view.
    """
    if play.free_max is None:
        return ""
    return (f"{play.free_max} of these may be spent freely; the rest need a "
            f"Willpower roll (Essence Awareness).")


def spent_motes(play: PlayView, state) -> tuple[int, int]:
    """Return the stored `(personal, peripheral)` spend, clamped to the pools now.
    `state` is a `PlayState`. None gives (0, 0).

    ⚠ Clamped ON READ, never written back: an attunement reduces the maxima, and a
    written clamp makes un-attuning lose the spent motes.

    ⚠ ONE helper for the four `_mote_input` sites (ui/play, ui/gm, qt/play,
    qt/party). Do not clamp at each site.
    """
    if state is None:
        return 0, 0
    return (min(state.motes_personal_spent, play.personal_max),
            min(state.motes_peripheral_spent, play.peripheral_max))


def build_play_view(ruleset: RuleSet, character: Character) -> PlayView:
    """Return the capacities of the in-play tracker, from the engine derivations: the
    health track, the Essence pools, and permanent Willpower.

    ⚠ Committed motes REDUCE the maxima (human's ruling). Not the Alchemical
    installation-motes model, which does not subtract: that is a chargen check.

    ⚠ The floor is 0. The fill state is CLAMPED ON READ, not written back: a
    derivation must not change the save, thus un-attuning gives the motes back.
    """
    d = derive.derive(ruleset, character)
    committed = derive.committed_attunement(ruleset, character)
    personal_max = max(0, d.essence_personal - committed["personal"])
    peripheral_max = max(0, d.essence_peripheral - committed["peripheral"])
    free_max = d.essence_free
    # HouseRules.committed_motes_reduce_free_essence (PER-CHARACTER, default off).
    # p.120 splits the pool into a freely-drawable third and two thirds behind a
    # Willpower roll, and never says which portion committed motes leave from — so the
    # table decides. OFF keeps the third of the PRINTED pool, which is what `derive`
    # already computed. ON re-takes it of what is left.
    #
    # ⚠ Only the tracker. `d.essence_free` is untouched, so the sheet keeps printing the
    # third of the permanent pool alongside the permanent pools themselves.
    rules = character.house_rules
    if (free_max is not None and rules is not None
            and rules.committed_motes_reduce_free_essence):
        free_max = (personal_max + peripheral_max) // 3
    return PlayView(
        health_boxes=[PlayHealthBox(_health_label(hl), hl.incapacitated)
                      for hl in d.health_levels],
        personal_max=personal_max,
        peripheral_max=peripheral_max,
        committed_personal=committed["personal"],
        committed_peripheral=committed["peripheral"],
        willpower_max=d.willpower,
        single_pool=d.essence_single_pool,
        free_max=free_max,
        fatigue_difficulties=[
            f"{a.name or 'Armour'} {eff.fatigue}"
            for a, eff in ((a, derive.effective_armor(ruleset, character, a))
                           for a in character.armor)
            if eff.fatigue],
    )


@dataclass
class PartyCardView:
    """One character as the GM's party page shows them: the same play capacities
    the Play tab uses, plus the few permanent numbers worth having on the table
    at a glance. `dodge` is the stored Ability rating, NOT a dice pool — combat
    derivation is deliberately not implemented, so the card must not invent one."""
    name: str
    exalt_type: str
    caste_label: str
    caste_noun: str          # what this splat calls the caste slot ("Caste"/"Aspect")
    essence_rating: int
    dodge: int
    soak: derive.SoakView
    play: PlayView
    chargen_locked: bool

    @property
    def identity_line(self) -> str:
        """'Fire Aspect · Dragon-Blooded' — the sub-heading under the name. A
        party is often mixed, so each card states its own splat vocabulary. A
        character with no caste (a Mortal) gets the splat alone."""
        if not self.caste_label:
            return self.exalt_type
        return f"{self.caste_label} {self.caste_noun} · {self.exalt_type}"


def build_party_card_view(ruleset: RuleSet, character: Character) -> PartyCardView:
    """The compact card for one party member. Composes build_play_view rather
    than re-deriving the capacities, so a card and the Play tab can never
    disagree about the same character."""
    caste = ruleset.castes.get(character.caste)
    return PartyCardView(
        name=character.name or "(unnamed)",
        exalt_type=character.exalt_type,
        caste_label=caste.label if caste else character.caste,
        caste_noun=ruleset.exalt_for(character.exalt_type).caste_noun,
        essence_rating=character.essence_rating,
        dodge=character.abilities.get(AbilityName.DODGE, 0),
        soak=derive.derive(ruleset, character).soak,
        play=build_play_view(ruleset, character),
        chargen_locked=character.chargen_locked,
    )
