"""
ui/view/advantages_text.py — the Advantages-tab text that the NiceGUI and the Qt
shells both show. ⚠ Change the text here only.
"""

from __future__ import annotations

from ...engine import merits as meritsmod


# --- Advantages-tab text, shared by the NiceGUI and Qt shells ------------------------ #
# ⚠ Both shells show this text. Change it here only. Do not copy it into a shell.

DEMESNE_TOGGLE_LABEL = "Demesne rather than Manse — grows no Hearthstones"

CUSTOM_MERIT_NOTE = "Display-only — recorded on the sheet, no mechanical effect."

MERIT_EXPERIENCE_PRICING_NOTE = (
    "Gaining a Merit or losing a Flaw costs twice its point value; losing a Merit or "
    "gaining a Flaw pays the same. An unaffordable change runs a debt against future XP.")


def xp_debt_note(debt: int) -> str:
    """Return the warning for an XP debt of `debt` points."""
    return f"⚠ {debt} XP owed — all further experience clears this first."


def merit_method_note(method: str) -> str:
    """Return the in-play note for a Merit change method that is not "experience"."""
    return (f"This table uses the '{method}' method (Player's Guide p.17), under which "
            f"gaining or losing a Merit costs and rewards nothing. Unlock chargen to "
            f"edit them.")


def flaw_room_note(flaw_points: int) -> tuple[str, bool]:
    """Return the in-play note on the Flaw cap (p.17), and True if it is a warning.

    The input is the raw Flaw points taken. The cap is `merits.FLAW_POINT_CAP`.
    """
    cap = meritsmod.FLAW_POINT_CAP
    room = max(0, cap - flaw_points)
    if room:
        return (f"{flaw_points} of {cap} points of Flaws taken — a new Flaw pays for "
                f"at most {room} more."), False
    return (f"⚠ {flaw_points} points of Flaws taken — at the {cap}-point cap (p.17). "
            f"A further Flaw still applies, but pays no XP."), True


def flaw_excess_note(flaw_points: int, granted: int) -> str:
    """Return the chargen warning for Flaw points above the cap (p.17).

    The inputs are the raw Flaw points and the bonus points that the cap grants.
    """
    return (f"⚠ {flaw_points} points of Flaws taken, {granted} granted — the excess "
            f"{flaw_points - granted} is lost to the {meritsmod.FLAW_POINT_CAP}-point "
            f"cap (p.17). The Flaws still apply.")


def merit_side_label(side: str) -> str:
    """Return the gain-dialog banner for `side`: "merit", "flaw", or "" for no choice."""
    if side == "flaw":
        return "Flaw — GAINING this pays the character"
    if side == "merit":
        return "Merit — gaining this costs XP"
    return "Merit OR Flaw — choose a side before gaining it"


def fetter_budget_text(spent: int, cap: int) -> str:
    """Return the Fetter budget line: the dots spent and the cap (p.127)."""
    return f"{spent} of {cap} dots (cap = Willpower + Essence, p.127)"
