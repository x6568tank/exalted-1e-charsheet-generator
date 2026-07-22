"""
ui/theme.py — per-splat colour palette.

The chrome (header bar, section headings, the owned-charm colour in the graph,
card tints) is themed by the character's Exalt type so a Dragon-Blooded sheet
reads red/terrestrial rather than the Solar gold. This is presentation only — no
game logic. All UI modules derive their colours from ``palette(exalt_type)``
instead of hardcoding the old ``_ACCENT = "#8a5a1a"`` constant.

Tailwind is served by NiceGUI's on-demand JIT compiler, so the ``fam``-derived
class names (``bg-red-50/60`` etc.) are generated from the DOM at runtime — any
standard colour family works.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """A splat's UI colours. `accent` drives headings / header / owned nodes;
    `fam` is the Tailwind colour family used for card tints and borders."""
    splat_label: str
    accent: str          # headings, header bar, owned graph node fill
    accent_dark: str     # owned graph node border
    ink: str             # body text
    bg: str              # page background (parchment)
    node_bg: str         # charm-graph container background
    button: str          # Quasar named colour for primary buttons
    fam: str             # Tailwind colour family ("amber" / "red")

    @property
    def card(self) -> str:
        """Card classes at the common 60/30 tint (readouts, detail panels)."""
        return f"bg-{self.fam}-50/60 border border-{self.fam}-900/30"

    @property
    def card_solid(self) -> str:
        """Card classes with an OPAQUE fill. For dialogs and anything else that
        floats over the page: the 50/60 tint `card` uses lets the content behind it
        show through, which reads as a rendering fault rather than a design."""
        return f"bg-{self.fam}-50 border border-{self.fam}-900/30"

    @property
    def card_soft(self) -> str:
        """A lighter 40/20 card tint (info boxes)."""
        return f"bg-{self.fam}-50/40 border border-{self.fam}-900/20"

    @property
    def rule(self) -> str:
        """Border class for thin section rules / underlines."""
        return f"border-{self.fam}-900/20"

    @property
    def graph_border(self) -> str:
        """CSS colour (rgba) for the charm-graph container border."""
        r, g, b = int(self.accent[1:3], 16), int(self.accent[3:5], 16), int(self.accent[5:7], 16)
        return f"rgba({r},{g},{b},0.3)"

    def head_style(self) -> str:
        """The ``<style>`` body rule setting the page background + ink colour."""
        return f"<style>body{{background:{self.bg};color:{self.ink};}}</style>"


_SOLAR = Palette(
    splat_label="Solar",
    accent="#8a5a1a", accent_dark="#5b3a10", ink="#3a2e1f",
    bg="#f7f1e3", node_bg="#fffdf7", button="brown", fam="amber",
)

# Dragon-Blooded / Terrestrial: crimson in place of the Solar gold, on a slightly
# warmer parchment. The accent is the Solar accent with its green channel pulled
# down, keeping the two themes visually a family.
_DRAGON_BLOODED = Palette(
    splat_label="Dragon-Blooded",
    accent="#8a1a1a", accent_dark="#5b1010", ink="#3a2320",
    bg="#f7ece3", node_bg="#fff8f4", button="red-10", fam="red",
)

# Abyssal / deathknight: near-black ink in place of the Solar gold, on an ashen
# grey parchment — the black-and-bone palette of the Underworld. `fam` is the
# neutral (grayscale) Tailwind family so card tints and borders read as ash.
_ABYSSAL = Palette(
    splat_label="Abyssal",
    accent="#1c1c1c", accent_dark="#000000", ink="#1a1a1a",
    bg="#ededed", node_bg="#f7f7f7", button="dark", fam="neutral",
)

# Lunar / Children of the Moon: moonsilver — a cool silver-blue in place of the
# Solar gold, on a pale silvered parchment. `fam` is the Tailwind slate family so
# card tints and borders read as brushed metal rather than sky blue.
_LUNAR = Palette(
    splat_label="Lunar",
    accent="#3f5f80", accent_dark="#27405a", ink="#1f2a35",
    bg="#eef2f6", node_bg="#f9fbfd", button="blue-grey-8", fam="slate",
)

_BY_SPLAT: dict[str, Palette] = {
    "Solar": _SOLAR,
    "Dragon-Blooded": _DRAGON_BLOODED,
    "Abyssal": _ABYSSAL,
    "Lunar": _LUNAR,
}


def palette(exalt_type: str | None) -> Palette:
    """The palette for `exalt_type`; falls back to the Solar gold for unknown or
    not-yet-themed splats."""
    return _BY_SPLAT.get(exalt_type or "Solar", _SOLAR)
