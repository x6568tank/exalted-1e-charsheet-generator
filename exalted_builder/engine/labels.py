"""
engine/labels.py — display names derived from ids and enum values.

Input: an enum value or a `martial_arts:<slug>` category. Output: the string a sheet
or a control should show. Mechanism: title-casing for enum values; for a style
category, the AUTHORED name from the style catalogue when there is one, falling back
to the slug.

The engine holds these: engine/camp.py and both shells need them, and the engine may
not import from `ui/`. `ui/view/` re-exports both (`viewmod._label`,
`viewmod._style_label`).

⚠ **There is exactly ONE style-label generator, and a test enforces it**
(`test_no_second_style_label_generator_disagrees_with_the_authored_name`).
"""

from __future__ import annotations


def _label(value: str) -> str:
    """'martial_arts' -> 'Martial Arts'."""
    return value.replace("_", " ").title()


def _style_label(category: str, ruleset=None) -> str:
    """"martial_arts:ebon-shadow" -> "Ebon Shadow Style".

    The AUTHORED name of the style catalogue wins: `martial_arts:praying-mantis` is
    printed "Mantis Style" (Caste Book: Eclipse p.73). Else the slug: a homebrew style
    has no catalogue entry (decision 0012).
    """
    if ruleset is not None:
        for style in getattr(ruleset, "martial_arts_styles", {}).values():
            if style.category == category:
                return style.name
    slug = category.split(":", 1)[-1]
    return " ".join(w.capitalize() for w in slug.replace("_", "-").split("-")) + " Style"
