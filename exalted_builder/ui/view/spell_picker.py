"""
ui/view/spell_picker.py — the rows of the spell picker, in circle order.
"""

from __future__ import annotations

from ...engine import validate
from ...models.character import Character
from ...models.rules import TRACK_CIRCLES, RuleSet

from ._base import SpellPickRow, _cost_str


# Global circle order for display: the two tracks laid end to end in TRACK_CIRCLES
# order (sorcery Terrestrial→Solar, then necromancy Shadowlands→Void). A picker may
# now show circles from BOTH tracks (Abyssals reach sorcery and necromancy), so the
# index must be global rather than per-track.
CIRCLE_DISPLAY_ORDER = tuple(c for circles in TRACK_CIRCLES.values() for c in circles)
_CIRCLE_ORDER = {c: i for i, c in enumerate(CIRCLE_DISPLAY_ORDER)}


def build_spell_picker(ruleset: RuleSet, character: Character) -> list[SpellPickRow]:
    """Every Spell of a circle the character can reach, tagged by the character's
    relationship to it: owned, available (a known Charm grants its circle and it
    isn't a chargen-barred top-circle spell), or locked with a one-line reason.
    Circles the character cannot reach at all (no learnable initiation Charm grants
    them) are omitted, so a plain Solar sees only Sorcery while an Abyssal — whose
    Occult tree holds both sorcery and necromancy initiations — sees both. Ordered
    by circle then name. Pure — eligibility comes from engine.validate."""
    reachable = validate.accessible_circles(ruleset, character)
    # The top circle is barred at *creation* only (core p.100). Once chargen is
    # locked the character is in play and may buy it with experience.
    chargen = not character.chargen_locked
    barred = validate.chargen_barred_circle(ruleset, character) if chargen else None
    rows: list[SpellPickRow] = []
    for spell in sorted(ruleset.spells.values(),
                        key=lambda s: (_CIRCLE_ORDER.get(s.circle, 9), s.name)):
        if spell.circle not in reachable:
            continue
        owned = spell.id in character.spells
        available = validate.meets_spell_requirements(ruleset, character, spell,
                                                      chargen=chargen)
        reason = ""
        if not owned and not available:
            if spell.circle == barred:
                reason = f"{spell.circle.value} Circle spells can't be taken at creation"
            else:
                reason = f"needs a Charm granting the {spell.circle.value} Circle"
        rows.append(SpellPickRow(
            id=spell.id, name=spell.name, circle=spell.circle.value,
            cost=_cost_str(spell.cost), description=spell.description,
            owned=owned, available=available, reason=reason, custom=spell.custom,
        ))
    return rows
