"""
ui/play.py — NiceGUI in-play tracker (the "Play" tab).

A deliberately *dumb* play-state tracker for use at the table: marked health damage,
motes spent, temporary Willpower, and Limit. It reads the capacities (health-track
shape, Essence pools, permanent Willpower) from the engine via view.build_play_view
and overlays the player's fill-state onto them, stored on Character.play. There is
NO game logic here and none in the engine for this: no auto mote-accounting, no
damage-wrapping rules, no auto-healing — the ST stays in control. This layer never
feeds back into chargen validation, the XP audit, or the permanent derivations.

Run:
    python -m exalted_builder.ui.play [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
# `merits` is imported for its LIMIT_MAX constant only. Reading a constant is not
# branching on a Merit id, which is what decision 0011 forbids.
from ..engine import derive, merits
from ..models.character import Character, Damage, PlayState
from ..models.rules import RuleSet
from . import theme
from . import view as viewmod

_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"
_EXAMPLE = _PKG.parent / "examples" / "ashes-of-dawn.character.json"

# The cycle a health box steps through on each click: empty → / → x → * → empty.
_MARK_CYCLE: list[Damage | None] = [None, Damage.BASHING, Damage.LETHAL, Damage.AGGRAVATED]
# Filled boxes are gold; the damage type is read from the symbol, tinted per type.
_GOLD = "#c9a227"
_WHITE = "#ffffff"
_BORDER = "#d6b98c"
_MARK_COLOR = {
    Damage.BASHING: "#374151",       # dark grey
    Damage.LETHAL: "#b91c1c",        # red
    Damage.AGGRAVATED: "#6b21a8",    # purple
}


# --------------------------------------------------------------------------- #
# Shared tracker widgets and mutations
#
# These are module-level (rather than closures over one character) so the GM
# party page can render the same boxes for several characters at once. Each takes
# the character to act on and an `on_change` callback for the caller's refresh —
# nothing here knows which page it is drawing on, and none of it is game logic.
# --------------------------------------------------------------------------- #

def play_state(character: Character) -> PlayState:
    """The character's play-state, created on first edit so a never-played
    character keeps a clean save until the tracker is actually used."""
    if character.play is None:
        character.play = PlayState()
    return character.play


def normalize_health(character: Character, n: int) -> list[Damage | None]:
    """Pad/trim the stored marks to the current health-track length (Ox-Body or a
    curse bought later changes the box count). Returns the live list."""
    h = play_state(character).health
    if len(h) < n:
        h += [None] * (n - len(h))
    elif len(h) > n:
        del h[n:]
    return h


def cycle_mark(character: Character, i: int, n: int) -> None:
    """Step health box `i` to the next mark: empty → / → x → * → empty."""
    h = normalize_health(character, n)
    h[i] = _MARK_CYCLE[(_MARK_CYCLE.index(h[i]) + 1) % len(_MARK_CYCLE)]


def set_motes(character: Character, field: str, value, cap: int) -> None:
    """Set a motes-spent field, clamped to 0..cap."""
    setattr(play_state(character), field, max(0, min(cap, int(value or 0))))


def set_count(character: Character, field: str, clicked: int, cap: int) -> None:
    """Dot-track click: clicking the top filled box clears it, else fill up to it."""
    cur = getattr(play_state(character), field)
    setattr(play_state(character), field,
            max(0, min(cap, clicked - 1 if clicked == cur else clicked)))


# Boxes are clickable <div>s (not q-btns) so the white/gold background applies
# cleanly — a q-btn's own background otherwise wins over an inline style.
def health_box(character: Character, i: int, label: str, mark: Damage | None,
               n: int, pal: theme.Palette, on_change) -> None:
    """One clickable health box, labelled with its wound penalty."""
    with ui.column().classes("items-center gap-0"):
        ui.label(label).classes("text-gray-500").style("font-size:0.6rem")
        sym_color = _MARK_COLOR[mark] if mark else pal.accent
        box = ui.label(mark.value if mark else "").classes("cursor-pointer select-none")
        box.style(f"width:2rem;height:2rem;line-height:2rem;text-align:center;"
                  f"font-weight:700;border-radius:4px;border:1px solid {_BORDER};"
                  f"background:{_GOLD if mark else _WHITE};color:{sym_color};")
        box.on("click", lambda: (cycle_mark(character, i, n), on_change()))


def count_box(character: Character, i: int, filled: bool, field: str, cap: int,
              on_change) -> None:
    """One box of a plain dot track (temporary Willpower, Limit)."""
    box = ui.label("").classes("cursor-pointer select-none")
    box.style(f"width:1.5rem;height:1.5rem;border-radius:4px;border:1px solid {_BORDER};"
              f"background:{_GOLD if filled else _WHITE};")
    box.on("click", lambda: (set_count(character, field, i + 1, cap), on_change()))


def worst_penalty(pv: "viewmod.PlayView", marks: list) -> str:
    """The label of the deepest marked health box — a convenience read of the marks
    (it does not enforce fill order). 'none' when undamaged."""
    deepest = None
    for box, mark in zip(pv.health_boxes, marks):
        if mark is not None:
            deepest = box
    if deepest is None:
        return "none"
    return "Incapacitated" if deepest.incapacitated else deepest.label


def build_play(ruleset: RuleSet, character: Character, save_path: Path,
               *, with_header: bool = True) -> None:
    """Render the in-play tracker for `character`. With `with_header=False` the
    title/Save bar is omitted (the embedding app provides one). The tab is live
    regardless of chargen lock — play happens after creation, but never blocks."""
    pal = theme.palette(character.exalt_type)

    # ---- mutations -------------------------------------------------------- #
    def clear_damage() -> None:
        play_state(character).health = []
        body.refresh()

    def clear_motes() -> None:
        # Motes only — Willpower, health, and Limit recover on their own terms (ST
        # discretion), so the tracker does not bulk-reset them.
        p = play_state(character)
        p.motes_personal_spent = 0
        p.motes_peripheral_spent = 0
        body.refresh()
        ui.notify("Motes spent cleared.", type="positive")

    # ---- body ------------------------------------------------------------- #
    @ui.refreshable
    def body() -> None:
        pv = viewmod.build_play_view(ruleset, character)
        cur = character.play or PlayState()
        marks = list(cur.health) + [None] * max(0, len(pv.health_boxes) - len(cur.health))

        with ui.column().classes("w-full max-w-3xl mx-auto gap-3"):
            # --- Health -------------------------------------------------- #
            with _panel("Health  ·  / bashing   x lethal   * aggravated", pal):
                with ui.row().classes("gap-1 flex-wrap items-end"):
                    for i, box in enumerate(pv.health_boxes):
                        health_box(character, i, box.label, marks[i],
                                   len(pv.health_boxes), pal, body.refresh)
                counts = {d: sum(1 for m in marks if m == d) for d in Damage}
                worst = worst_penalty(pv, marks)
                with ui.row().classes("items-center gap-4 mt-1"):
                    ui.label(f"Marked: {counts[Damage.BASHING]}/ {counts[Damage.LETHAL]}x "
                             f"{counts[Damage.AGGRAVATED]}*").classes("text-xs text-gray-600")
                    ui.label(f"Wound penalty: {worst}").classes("text-xs font-semibold").style(
                        f"color:{pal.accent}")
                    ui.button("Clear damage", icon="healing", on_click=clear_damage).props(
                        "flat dense").classes("text-xs")

            # --- Motes (numeric; capacities derived, spend is user input) - #
            with _panel("Essence (motes spent — manual)", pal):
                with ui.row().classes("gap-6 flex-wrap items-end"):
                    _mote_input("Personal", "motes_personal_spent",
                                cur.motes_personal_spent, pv.personal_max)
                    _mote_input("Peripheral", "motes_peripheral_spent",
                                cur.motes_peripheral_spent, pv.peripheral_max)

            # --- Temporary Willpower ------------------------------------- #
            with _panel(f"Temporary Willpower  ({pv.willpower_max - cur.willpower_spent} / "
                        f"{pv.willpower_max} available)", pal):
                with ui.row().classes("gap-1 flex-wrap"):
                    for i in range(pv.willpower_max):
                        count_box(character, i, i < cur.willpower_spent,
                                  "willpower_spent", pv.willpower_max, body.refresh)

            # --- Limit, or Clarity for the splats that have it instead ---- #
            # Alchemicals took no part in the Great Curse and have no Limit at all
            # (p.69); Clarity stands in its place. Only the TEMPORARY half is a
            # counter — the permanent half is derived from Essence and installed
            # Charms, so it is shown read-only above the track.
            if derive.uses_clarity(ruleset, character):
                cl = derive.clarity(ruleset, character)
                with _panel(f"Clarity  ({cl.total} / {derive.CLARITY_MAX}"
                            f"  ·  {cl.permanent} permanent + {cl.temporary} temporary)", pal):
                    if cl.sources:
                        ui.label("Permanent (derived): " + ", ".join(
                            f"{label} +{dots}" for label, dots in cl.sources)).classes(
                            "text-xs text-gray-600")
                    else:
                        ui.label("No permanent Clarity — Essence 5 or below, and no "
                                 "Charm installed that grants it.").classes(
                            "text-xs text-gray-600")
                    ui.label("Temporary (click to set):").classes("text-xs text-gray-600 mt-1")
                    with ui.row().classes("gap-1 flex-wrap"):
                        for i in range(derive.CLARITY_MAX):
                            count_box(character, i, i < cur.clarity_temporary,
                                      "clarity_temporary", derive.CLARITY_MAX, body.refresh)
                    if cl.capped:
                        ui.label(f"Permanent + temporary exceeds {derive.CLARITY_MAX}; "
                                 "the total is capped (p.69).").classes(
                            "text-xs text-amber-700")
                    ui.label(f"{cl.band}: {cl.effects}").classes("text-xs mt-1").style(
                        f"color:{pal.accent}")
                    ui.label("Clarity never breaks or resets at 10, unlike Limit "
                             "(p.70).").classes("text-xs text-gray-500")
            else:
                # Sidereals call the same 0-10 track "Paradox" (p.253) — a rename
                # carried on ExaltDefinition.limit_label, not a second mechanic.
                lim = derive.limit_label(ruleset, character)
                # Greater Curse lowers the maximum, so Limit Break arrives sooner —
                # the track is drawn to the derived maximum, not a hardcoded 10.
                lim_max = derive.limit_max(ruleset, character)
                with _panel(f"{lim}  ({cur.limit} / {lim_max}"
                            f"{f'  — {lim.upper()} BREAK' if cur.limit >= lim_max else ''})",
                            pal):
                    with ui.row().classes("gap-1 flex-wrap"):
                        for i in range(lim_max):
                            count_box(character, i, i < cur.limit, "limit", lim_max,
                                      body.refresh)
                    if lim_max < merits.LIMIT_MAX:
                        ui.label(f"Maximum {lim} reduced from "
                                 f"{merits.LIMIT_MAX} by a Flaw.").classes(
                            "text-xs text-amber-700")
                    # Death's Taint gives the Abyssal Curse a permanent counterpart,
                    # "cumulative with temporary Resonance". Shown only where held.
                    perm_cap = derive.permanent_limit_cap(ruleset, character)
                    if perm_cap:
                        # READ-ONLY here. Permanent Resonance is a permanent trait, not
                        # play-state: it is gained and shed through the XP ledger so the
                        # change has an audit trail, exactly as decision 0006 requires of
                        # a curse. The tracker shows it because it is "cumulative with
                        # temporary Resonance" and the ST needs the total at the table.
                        ui.label(f"Permanent {lim}: {character.limit_permanent} "
                                 f"/ {perm_cap} (capped at Essence)").classes(
                            "text-xs mt-1")
                        ui.label(f"Cumulative with temporary {lim}; total "
                                 f"{cur.limit + character.limit_permanent}.").classes(
                            "text-xs text-gray-500")
                        ui.label(f"Permanent {lim} is a permanent trait — gain or shed "
                                 f"it on the XP tab, not here.").classes(
                            "text-xs text-gray-500")

            # Luck pools exist only because Lucky / Unlucky do. Spending them is
            # rerolling (decision 0009) and stays out — these are counters.
            luck, bad_luck = derive.luck_pools(ruleset, character)
            if luck or bad_luck:
                with _panel("Luck", pal):
                    if luck:
                        ui.label(f"Luck pool: {luck}").classes("text-sm")
                    if bad_luck:
                        ui.label(f"Bad luck pool (Storyteller): {bad_luck}").classes(
                            "text-sm")
                    ui.label("Refreshes at the end of each story. Spending luck is a "
                             "reroll, which this build does not model.").classes(
                        "text-xs text-gray-500")

            _curse = ("Clarity" if derive.uses_clarity(ruleset, character)
                      else derive.limit_label(ruleset, character))
            ui.button("Clear motes spent", icon="refresh", on_click=clear_motes).props(
                f"flat color={pal.button}").tooltip(
                "Resets Personal and Peripheral motes spent to 0. "
                f"Willpower, Health, and {_curse} are left to you / the ST.")

    def _mote_input(label: str, field: str, value: int, cap: int) -> None:
        with ui.column().classes("gap-0"):
            ui.number(f"{label} spent", value=value, min=0, max=cap, format="%d",
                      on_change=lambda e, f=field, c=cap: (
                          set_motes(character, f, e.value, c), body.refresh())).classes("w-32")
            ui.label(f"{max(0, cap - value)} / {cap} available").classes("text-xs text-gray-600")

    # ---- header / layout -------------------------------------------------- #
    if with_header:
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"In-play — {character.name or 'character'}").classes(
                "text-lg font-bold").style(f"color:{pal.accent}")
            ui.button("Save", icon="save",
                      on_click=lambda: _save(character, save_path)).props(f"color={pal.button}")
    body()


def _panel(title: str, pal: theme.Palette):
    card = ui.card().classes(f"w-full p-3 {pal.card_soft} gap-2")
    with card:
        ui.label(title).classes("text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
    return card


def _save(character: Character, save_path: Path) -> None:
    persistence.save_character(character, save_path)
    ui.notify(f"Saved {save_path.name}", type="positive")


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e in-play tracker")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset, character, path = load(args.character)

    @ui.page("/")
    def index() -> None:
        build_play(ruleset, character, path)

    ui.run(title=f"Exalted 1e — play: {character.name or path.stem}",
           reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
