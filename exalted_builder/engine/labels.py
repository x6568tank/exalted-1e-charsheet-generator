"""
engine/labels.py — display names derived from ids and enum values.

Input: an enum value or a `martial_arts:<slug>` category. Output: the string a sheet
or a control should show. Mechanism: title-casing for enum values; for a style
category, the AUTHORED name from the style catalogue when there is one, falling back
to the slug.

These live in the engine rather than a presenter because both the camp view
(engine/camp.py) and the two shells' presenters need them, and the engine may not
import from `ui/`. `ui/view.py` re-exports both, so `viewmod._label` /
`viewmod._style_label` remain the names every existing caller uses.

⚠ **There is exactly ONE style-label generator, and a test enforces it.** A second
copy is how the same style came to be called two things on two surfaces
(`test_no_second_style_label_generator_disagrees_with_the_authored_name`).
"""

from __future__ import annotations


def _label(value: str) -> str:
    """'martial_arts' -> 'Martial Arts'."""
    return value.replace("_", " ").title()


def _style_label(category: str, ruleset=None) -> str:
    """"martial_arts:ebon-shadow" -> "Ebon Shadow Style".

    The AUTHORED name wins when the style catalogue has one, because the slug is
    not always the printed name: `martial_arts:praying-mantis` is printed "Mantis
    Style" (Caste Book: Eclipse p.73). Without this the same style is called two
    things on two surfaces. The slug remains the fallback — homebrew styles are
    minted at runtime and have no catalogue entry (decision 0012).
    """
    if ruleset is not None:
        for style in getattr(ruleset, "martial_arts_styles", {}).values():
            if style.category == category:
                return style.name
    slug = category.split(":", 1)[-1]
    return " ".join(w.capitalize() for w in slug.replace("_", "-").split("-")) + " Style"
