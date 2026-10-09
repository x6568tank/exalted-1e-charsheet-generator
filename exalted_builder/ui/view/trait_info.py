"""
ui/view/trait_info.py — the reference text of a rated trait (core ch.4): the
Attribute, Ability, and Virtue ladders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ...models.rules import AbilityName, AttributeName, RuleSet, VirtueName


@dataclass(frozen=True)
class TraitInfo:
    """One rated trait's reference text, shaped for display (core ch.4).

    `ladder` is (rating, text, is_current) per rung, `is_current` marking the row the
    character is actually at so a shell can highlight it. `sections` is ordered
    (heading, body) pairs — sample specialties and the example feats for an Ability,
    the two Virtue lists for a Virtue, empty for an Attribute. Both shells render this
    and only this, so the two cannot drift into describing a trait differently."""
    title: str
    subtitle: str
    description: str
    ladder: list[tuple[int, str, bool]] = field(default_factory=list)
    sections: list[tuple[str, str]] = field(default_factory=list)


def _ladder_rows(ladder: dict[int, str], rating: Optional[int]) -> list[tuple[int, str, bool]]:
    """Sort a rating->text ladder into display rows, flagging the character's rung."""
    return [(n, ladder[n], n == rating) for n in sorted(ladder)]


def attribute_info(ruleset: RuleSet, name: AttributeName,
                   rating: Optional[int] = None) -> Optional[TraitInfo]:
    """The reference panel for one Attribute (core pp.127-128), or None when the
    ruleset carries no trait text. `rating` only decides which rung is highlighted."""
    td = ruleset.trait_descriptions
    row = td.attribute(name) if td else None
    if row is None:
        return None
    return TraitInfo(title=row.name,
                     subtitle=f"{row.category} Attribute" if row.category else "Attribute",
                     description=row.description,
                     ladder=_ladder_rows(row.ladder, rating))


def ability_info(ruleset: RuleSet, name: AbilityName,
                 rating: Optional[int] = None) -> Optional[TraitInfo]:
    """The reference panel for one Ability (core pp.132-140), or None when the ruleset
    carries no trait text.

    ⚠ The ladder is the GENERIC one shared by every Ability — 1e prints no per-Ability
    rungs. What is per-Ability is the three example feats, whose success counts (1/3/5,
    p.132) are spelled into the headings because the page prints them only once."""
    td = ruleset.trait_descriptions
    row = td.ability(name) if td else None
    if row is None:
        return None
    sections: list[tuple[str, str]] = []
    if row.specialties:
        sections.append(("Sample specialties", ", ".join(row.specialties)))
    if row.specialties_note:
        sections.append(("Specialties", row.specialties_note))
    for heading, body in (("Standard (1 success)", row.standard),
                          ("Challenging (3 successes)", row.challenging),
                          ("Legendary (5 successes)", row.legendary)):
        if body:
            sections.append((heading, body))
    return TraitInfo(title=row.name, subtitle="Ability", description=row.description,
                     ladder=_ladder_rows(td.ability_ladder, rating), sections=sections)


def virtue_info(ruleset: RuleSet, name: VirtueName,
                rating: Optional[int] = None) -> Optional[TraitInfo]:
    """The reference panel for one Virtue (core pp.129-130), or None when the ruleset
    carries no trait text."""
    td = ruleset.trait_descriptions
    row = td.virtue(name) if td else None
    if row is None:
        return None
    sections = [(h, b) for h, b in ((f"{row.name} aids in", row.aids_in),
                                    (f"Must fail a {row.name} check to", row.must_fail_check_to))
                if b]
    return TraitInfo(title=row.name, subtitle="Virtue", description=row.description,
                     ladder=_ladder_rows(row.ladder, rating), sections=sections)
