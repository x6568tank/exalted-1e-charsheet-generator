"""Unit tests for the per-splat UI palette (ui/theme.py) — pure, no NiceGUI."""

from exalted_builder.ui import theme


def test_solar_palette_is_the_gold_default():
    pal = theme.palette("Solar")
    assert pal.splat_label == "Solar"
    assert pal.accent == "#8a5a1a"          # the historical gold accent
    assert pal.fam == "amber"
    assert pal.button == "brown"


def test_dragonblooded_palette_is_red():
    pal = theme.palette("Dragon-Blooded")
    assert pal.splat_label == "Dragon-Blooded"
    assert pal.fam == "red"                  # card tints/borders swap family
    assert pal.accent.startswith("#8a") and pal.accent != "#8a5a1a"
    # red-dominant: red channel far exceeds green/blue in the accent
    r, g, b = (int(pal.accent[i:i + 2], 16) for i in (1, 3, 5))
    assert r > g and r > b


def test_lunar_palette_is_moonsilver_blue():
    pal = theme.palette("Lunar")
    assert pal.splat_label == "Lunar"
    assert pal.fam == "slate"
    # blue-dominant, and cool: the blue channel leads and red trails
    r, g, b = (int(pal.accent[i:i + 2], 16) for i in (1, 3, 5))
    assert b > g > r


def test_sidereal_palette_is_purple():
    pal = theme.palette("Sidereal")
    assert pal.splat_label == "Sidereal"
    assert pal.fam == "purple"
    # purple: red and blue lead, green trails
    r, g, b = (int(pal.accent[i:i + 2], 16) for i in (1, 3, 5))
    assert r > g and b > g


def test_alchemical_palette_is_brass():
    pal = theme.palette("Alchemical")
    assert pal.splat_label == "Alchemical"
    assert pal.fam == "yellow"
    # brass is a warm metallic gold, distinct from the Solar amber accent.
    assert pal.accent != theme.palette("Solar").accent
    r, g, b = (int(pal.accent[i:i + 2], 16) for i in (1, 3, 5))
    assert r > g > b                              # warm gold: red leads, blue trails


def test_unknown_or_missing_splat_falls_back_to_solar():
    assert theme.palette(None).accent == theme.palette("Solar").accent
    # Mortals are the next splat with no palette of their own (see CLAUDE.md's
    # colour table); Sidereal and Alchemical are both themed now.
    assert theme.palette("Mortal").accent == theme.palette("Solar").accent


def test_card_class_helpers_track_the_family():
    solar, db = theme.palette("Solar"), theme.palette("Dragon-Blooded")
    assert "amber" in solar.card and "amber" in solar.card_soft
    assert "red" in db.card and "red" in db.card_soft
    assert db.rule == "border-red-900/20"


def test_graph_border_is_the_accent_as_rgba():
    # Dragon-Blooded accent #8a1a1a -> rgba(138,26,26,0.3)
    assert theme.palette("Dragon-Blooded").graph_border == "rgba(138,26,26,0.3)"


def test_head_style_sets_background_and_ink():
    style = theme.palette("Dragon-Blooded").head_style()
    assert style.startswith("<style>body{") and "background:#f7ece3" in style


def test_card_solid_is_opaque_unlike_card():
    # Dialogs float over the page, so their fill must not be the 50/60 tint that
    # `card` uses — the content behind shows through and reads as a bug.
    pal = theme.palette("Lunar")
    assert pal.card_solid.startswith("bg-slate-50 ")
    assert "/60" not in pal.card_solid
    assert "/60" in pal.card            # the in-page card tint is still translucent
