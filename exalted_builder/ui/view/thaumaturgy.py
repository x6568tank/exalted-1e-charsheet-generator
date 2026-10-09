"""
ui/view/thaumaturgy.py — the Thaumaturgy picker (Player's Guide CH3) and the
Dragon-Blooded Elemental Power picker.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...engine import costs, validate
from ...models.character import Character
from ...models.rules import AbilityName, RuleSet


# --------------------------------------------------------------------------- #
# Thaumaturgy (Player's Guide CH3)
#
# Four genuinely different mechanical shapes — a binary Art, a rated Science, a
# levelled ritual, a flat-rate formula — so four row types rather than one flat
# list that would fight all four (see docs/status/thaumaturgy.md).
#
# Every price here is the LIST price of one purchase, in whichever currency the
# character is currently spending. It is deliberately not the amount that will be
# charged: under "Magic for Everyone" the engine zeroes the dearest eligible
# purchases collectively, an assignment no single row can know about. The panel
# shows list prices and reads the actual total off `bonus_point_breakdown`, which
# is the one place the free grant is applied.
# --------------------------------------------------------------------------- #

@dataclass
class ThaumSpecialtyRow:
    """A specialty of an Art — a printed aspect or a player-invented one. Both are
    the same purchase at the same rate (p.126); `printed` only says which of the two
    a row came from, which matters for the free grant and for the Occult gate."""
    art_id: str
    name: str
    description: str
    min_occult: int
    printed: bool
    owned: bool
    narrowed: bool
    available: bool
    reason: str
    price: int
    # What it would cost bought NARROWED — Summoning's option alone (p.127), where
    # further limiting an aspect halves the price. ⚠ A separate field rather than
    # re-pricing `price`, because narrowing is chosen at the moment of purchase and
    # the shell has to be able to show BOTH numbers; and computed here rather than in
    # a shell, because a price is `engine.costs`' answer, never a widget's.
    narrowed_price: int = 0


@dataclass
class ThaumArtRow:
    id: str
    name: str
    min_occult: int
    roll: str
    cost_text: str          # display, e.g. "3 motes per attempt"
    description: str
    owned: bool
    available: bool
    reason: str
    price: int
    allows_narrowing: bool  # Summoning alone (p.127)
    specialties: list[ThaumSpecialtyRow] = field(default_factory=list)


@dataclass
class ThaumScienceLevelRow:
    rating: int
    description: str        # "" where the book prints no rung (Alchemy 5)


@dataclass
class ThaumScienceRow:
    id: str
    name: str
    roll: str
    cost_text: str
    time: str
    duration: str
    description: str
    rating: int
    max_rating: int
    next_price: int         # to buy the NEXT dot; 0 when none may be bought
    can_raise: bool
    reason: str
    levels: list[ThaumScienceLevelRow] = field(default_factory=list)


@dataclass
class ThaumEntryRow:
    """A ritual or a formula: both are learned once and then owned in one or more
    regional orientations, at a flat point per extra (p.124)."""
    key: str                # catalogue id, or the name for a custom entry
    name: str
    kind: str               # 'ritual' | 'formula'
    level: int
    custom: bool
    owned: bool
    available: bool
    reason: str
    price: int              # to learn it in its first orientation
    orientation_price: int  # to add one further regional version
    orientations: list[str] = field(default_factory=list)   # owned, display strings
    detail: list[tuple[str, str]] = field(default_factory=list)   # (label, value)
    description: str = ""


@dataclass
class ThaumOwnedRow:
    """One line of "what this character has bought", straight off the engine's
    canonical enumeration and priced by it — including the free-grant zeroes, which
    is why this is not recomputed from the rows above."""
    kind: str
    key: str
    label: str
    cost: int
    free: bool


@dataclass
class ThaumPickerView:
    currency: str           # 'BP' | 'XP'
    usable: bool            # False for a splat that may hold but never use it
    usable_note: str
    occult: int
    free_picks: int         # "Magic for Everyone" allowance, 0 when off
    free_note: str
    arts: list[ThaumArtRow] = field(default_factory=list)
    sciences: list[ThaumScienceRow] = field(default_factory=list)
    rituals: list[ThaumEntryRow] = field(default_factory=list)
    formulas: list[ThaumEntryRow] = field(default_factory=list)
    owned: list[ThaumOwnedRow] = field(default_factory=list)
    total: int = 0


@dataclass
class ElementalPowerRow:
    """One elemental power as the picker renders it (Core p.296 / GoD p.56, PG p.68).
    `activation` and `description` are descriptive text (decision 0008); `requires`
    is the human-readable prerequisite line (Merits + Essence)."""
    id: str
    name: str
    price: int              # bp_cost chargen, bp_cost * 2 in play
    activation: str
    description: str
    requires: str
    owned: bool
    available: bool
    reason: str             # why it's locked, for the button tooltip


@dataclass
class ElementalPowerView:
    currency: str           # 'BP' | 'XP'
    total: int              # total cost of owned powers
    powers: list[ElementalPowerRow] = field(default_factory=list)
    owned: list[ElementalPowerRow] = field(default_factory=list)


def build_elemental_power_picker(ruleset: RuleSet, character: Character) -> ElementalPowerView:
    """The elemental-powers page as display rows. Pure: every gate comes from
    engine.validate and every price from engine.costs.

    Prices switch currency at the lock like every other picker — before it a purchase
    costs bonus points, after it experience (PG p.68, "learned in play for a number of
    experience points equal to double its bonus point value")."""
    in_play = character.chargen_locked
    currency = "XP" if in_play else "BP"
    held = set(character.elemental_powers)
    rows: list[ElementalPowerRow] = []
    for power in sorted(ruleset.elemental_powers.values(), key=lambda p: p.name):
        reason = "; ".join(validate.elemental_power_shortfalls(
            ruleset, character, power))
        names = [ruleset.merits_flaws[mid].name
                 for mid in power.required_merits
                 if (mid in ruleset.merits_flaws)]
        requires = ", ".join(names + [f"Essence {power.min_essence}"])
        price = (costs.elemental_power_xp(ruleset, character, power) if in_play
                 else power.bp_cost)
        rows.append(ElementalPowerRow(
            id=power.id, name=power.name, price=price,
            activation=power.activation, description=power.description,
            requires=requires, owned=power.id in held,
            available=not reason, reason=reason,
        ))
    owned = [r for r in rows if r.owned]
    # Summed off the rows so the total is in the SAME currency they are priced in —
    # bonus points before the lock, XP (double, PG p.68) after it. Re-summing bp_cost
    # here would label a BP total "XP" post-lock.
    total = sum(r.price for r in owned)
    return ElementalPowerView(currency=currency, total=total,
                              powers=rows, owned=owned)


def _thaum_specialty_rows(ruleset: RuleSet, character: Character, art,
                          state, price: int,
                          narrowed_price: int = 0) -> list[ThaumSpecialtyRow]:
    """Every printed aspect of `art`, then any player-invented specialty the
    character already holds in it. Held ones are matched case-insensitively against
    the printed list so a specialty typed as "ghosts" does not show up twice."""
    held = {s.name.casefold(): s for s in state.art_specialties if s.art_id == art.id}
    rows: list[ThaumSpecialtyRow] = []
    for aspect in art.aspects:
        owned = held.get(aspect.name.casefold())
        reason = validate.thaum_aspect_locked_reason(
            ruleset, character, art.id, aspect.name)
        rows.append(ThaumSpecialtyRow(
            art_id=art.id, name=aspect.name, description=aspect.description,
            min_occult=aspect.min_occult, printed=True, owned=owned is not None,
            narrowed=bool(owned and owned.narrowed),
            available=not reason, reason=reason, price=price,
            narrowed_price=narrowed_price))
    printed = {a.name.casefold() for a in art.aspects}
    for spec in state.art_specialties:
        if spec.art_id != art.id or spec.name.casefold() in printed:
            continue
        rows.append(ThaumSpecialtyRow(
            art_id=art.id, name=spec.name, description="", min_occult=0,
            printed=False, owned=True, narrowed=spec.narrowed,
            available=True, reason="", price=price,
            narrowed_price=narrowed_price))
    return rows


def _thaum_entry_detail(obj, kind: str) -> list[tuple[str, str]]:
    """The labelled display lines of a catalogue ritual or formula. Rituals print no
    stat block at all (everything is prose), so most of their fields are empty and
    simply do not render — see docs/status/thaumaturgy.md."""
    if kind == "ritual":
        pairs = [("Roll", obj.roll), ("Cost", obj.cost), ("Materials", obj.resources)]
    else:
        materials = obj.materials_raw or (
            f"Resources {obj.materials_resources}" if obj.materials_resources else "")
        pairs = [("Roll", obj.roll),
                 ("Difficulty", str(obj.difficulty) if obj.difficulty else ""),
                 ("Materials", materials),
                 ("Effects", obj.effects), ("Addiction", obj.addiction)]
    return [(label, value) for label, value in pairs if value]


def build_thaum_picker(ruleset: RuleSet, character: Character) -> ThaumPickerView:
    """The whole thaumaturgy page as display rows. Pure: every gate comes from
    engine.validate and every price from engine.costs.

    Prices switch currency at the lock, the same way the Charm picker does — before
    it a purchase costs bonus points, after it experience.
    """
    state = validate.thaum_state(character)
    chargen = not character.chargen_locked
    in_play = character.chargen_locked
    exalt = ruleset.exalt_for(character.exalt_type)

    art_price = (costs.thaum_art_xp(ruleset, character) if in_play
                 else costs.thaum_art_bp(ruleset, character))
    spec_price = (costs.thaum_specialty_xp(ruleset, character) if in_play
                  else costs.thaum_specialty_bp(ruleset, character))
    spec_narrowed = (costs.thaum_specialty_xp(ruleset, character, narrowed=True)
                     if in_play
                     else costs.thaum_specialty_bp(ruleset, character, narrowed=True))
    orient_price = (costs.thaum_orientation_xp(ruleset, character) if in_play
                    else costs.thaum_orientation_bp(ruleset, character))

    arts: list[ThaumArtRow] = []
    for art in sorted(ruleset.thaum_arts.values(), key=lambda a: a.name):
        reason = validate.thaum_art_locked_reason(ruleset, character, art.id)
        arts.append(ThaumArtRow(
            id=art.id, name=art.name, min_occult=art.min_occult, roll=art.roll,
            cost_text=art.cost, description=art.description,
            owned=art.id in state.arts, available=not reason, reason=reason,
            price=art_price, allows_narrowing=art.aspect_narrowing,
            specialties=_thaum_specialty_rows(ruleset, character, art, state,
                                              spec_price, spec_narrowed),
        ))

    sciences: list[ThaumScienceRow] = []
    for science in sorted(ruleset.thaum_sciences.values(), key=lambda s: s.name):
        held = next((s for s in state.sciences if s.science_id == science.id), None)
        rating = held.rating if held is not None else 0
        reason = validate.thaum_science_raise_reason(
            ruleset, character, science.id, chargen=chargen)
        step = (costs.thaum_science_step_xp(ruleset, character, rating) if in_play
                else costs.thaum_science_step_bp(ruleset, character, rating))
        # The ladder is rendered from 1..max_rating rather than from `levels`, so
        # Alchemy's undescribed five-dot rung shows as an empty rung instead of
        # silently pulling the six-dot text down into the gap.
        sciences.append(ThaumScienceRow(
            id=science.id, name=science.name, roll=science.roll,
            cost_text=science.cost, time=science.time, duration=science.duration,
            description=science.description, rating=rating,
            max_rating=science.max_rating, next_price=0 if reason else step,
            can_raise=not reason, reason=reason,
            levels=[ThaumScienceLevelRow(
                rating=r,
                description=(science.level(r).description if science.level(r) else ""))
                for r in range(1, science.max_rating + 1)],
        ))

    def _entry_rows(catalogue: dict, held: list, kind: str) -> list[ThaumEntryRow]:
        by_key = {}
        for entry in held:
            key = (entry.ritual_id if kind == "ritual" else entry.formula_id) or entry.name
            by_key[key] = entry
        rows: list[ThaumEntryRow] = []
        for obj in sorted(catalogue.values(), key=lambda o: (o.level, o.name)):
            entry = by_key.pop(obj.id, None)
            price = (costs.thaum_ritual_xp(ruleset, character, obj.level, 1) if in_play
                     else costs.thaum_ritual_bp(ruleset, character, obj.level, 1)) \
                if kind == "ritual" else (
                    costs.thaum_formula_xp(ruleset, character, 1) if in_play
                    else costs.thaum_formula_bp(ruleset, character, 1))
            # Formulas carry no purchase gate: the source states one for Arts,
            # aspects and rituals only, and inventing a Science-rating requirement
            # here would be a rule we do not have. Do not add one.
            reason = (validate.thaum_ritual_locked_reason(
                ruleset, character, obj.level, chargen=chargen)
                if kind == "ritual" else "")
            rows.append(ThaumEntryRow(
                # ⚠ `custom` means "not printed in a book", and a ritual now has TWO
                # ways of being that: a library row the loader stamped (here) or an
                # inline one on the character (below). Both wear the same mark.
                key=obj.id, name=obj.name, kind=kind, level=obj.level,
                custom=getattr(obj, "custom", False),
                owned=entry is not None, available=not reason, reason=reason,
                price=price, orientation_price=orient_price,
                orientations=[o.value for o in entry.orientations] if entry else [],
                detail=_thaum_entry_detail(obj, kind),
                # A formula has no prose block — its content is the labelled
                # Effects/Addiction lines, which are already in `detail`.
                description=obj.description if kind == "ritual" else "",
            ))
        # Whatever is left in by_key is custom — authored by the player, or a stale
        # id no longer in the catalogue. Either way it is shown, never dropped.
        for key, entry in by_key.items():
            rows.append(ThaumEntryRow(
                key=key, name=entry.name or key, kind=kind, level=entry.level,
                custom=True, owned=True, available=True, reason="",
                price=0, orientation_price=orient_price,
                orientations=[o.value for o in entry.orientations],
                description=entry.description,
            ))
        return rows

    purchases = validate.thaum_purchases(ruleset, character)
    free = validate.magic_for_everyone_grant(ruleset, character)
    # Priced through the engine's own function so the free-grant assignment shown
    # here is the same one the bonus-point breakdown charges for.
    prices = validate.thaum_purchase_bp_costs(ruleset, character, purchases,
                                              free_picks=free)
    owned = [ThaumOwnedRow(kind=p.kind, key=p.key, label=p.label, cost=c,
                           free=c == 0 and validate.magic_for_everyone_eligible(ruleset, p))
             for p, c in zip(purchases, prices)]

    free_note = ""
    if free:
        free_note = (f"Magic for Everyone: {free} free purchase(s) from Occult "
                     f"{validate.ability_rating(character, AbilityName.OCCULT)} — "
                     "rituals, formulas or printed aspects up to level 3. Applied to "
                     "the dearest eligible purchases; Arts and Sciences are never free.")

    return ThaumPickerView(
        currency="XP" if in_play else "BP",
        usable=exalt.thaumaturgy_usable,
        usable_note=("" if exalt.thaumaturgy_usable else
                     f"{character.exalt_type} may hold thaumaturgy but can never use "
                     "it (p.114) — the knowledge is kept, and can still be taught."),
        occult=validate.ability_rating(character, AbilityName.OCCULT),
        free_picks=free, free_note=free_note,
        arts=arts, sciences=sciences,
        rituals=_entry_rows(ruleset.thaum_rituals, state.rituals, "ritual"),
        formulas=_entry_rows(ruleset.thaum_formulas, state.formulas, "formula"),
        owned=owned, total=sum(prices),
    )
