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
from ..models.rules import AbilityName, AttributeName, RuleSet, VirtueName
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


def set_fatigue(character: Character, value) -> None:
    """Set the accumulated armour-fatigue points (p.332). No upper clamp: the rule
    prints no maximum, and the penalty keeps accruing on every failed roll."""
    play_state(character).fatigue = max(0, int(value or 0))


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
        box = ui.label(mark.value if mark else "").classes(
            "cursor-pointer select-none").mark(f"play-health-{i}")
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


def new_pool_state(ruleset: RuleSet) -> dict:
    """The sidebar's selections. Created by the CALLER, outside its refreshable body
    — the sidebar is rebuilt every time a health box is clicked, and state owned by
    the sidebar would reset the player's chosen weapon on exactly the click that
    makes them want the pools. Returns {} when no roll catalogue shipped."""
    if not ruleset.roll_catalog:
        return {}
    return {"weapon": None, "arrow": None,
            "mobility": True, "wound": True, "fatigue": True,
            # The custom Attribute + Ability pool. Defaults chosen so the block
            # shows a real number the moment it renders rather than an empty frame.
            "custom_attribute": AttributeName.DEXTERITY.value,
            "custom_ability": AbilityName.ATHLETICS.value,
            "custom_agility": False}


def _pool_row(row: "viewmod.PoolRow", pal: theme.Palette) -> None:
    """One roll line: the total, the name, and the arithmetic underneath.

    ⚠ The `compact` breakdown is NOT optional decoration. A column of bare totals is
    precisely the "looks authoritative" surface decision 0008 rejected, and 0016
    narrowed 0008 only on the promise that every pool shown is itemised. One
    function so the preset list and the custom block cannot drift apart on it.
    """
    with ui.row().classes("w-full items-baseline gap-2 no-wrap"):
        ui.label(f"{row.total}").classes(
            "text-base font-bold w-8 text-right shrink-0").style(
            f"color:{'#b45309' if row.below_one else pal.accent}")
        with ui.column().classes("gap-0 min-w-0"):
            ui.label(row.name).classes("text-sm leading-tight")
            ui.label(row.compact).classes("text-xs text-gray-600 leading-tight")


def custom_pool_panel(ruleset: RuleSet, character: Character,
                      pal: theme.Palette, state: dict, on_change) -> None:
    """The player's own Attribute + Ability pool — a builder, not data.

    The catalogue covers the rolls the corebook spells out by name; the rest of 1e is
    "roll Attribute + Ability" for whatever the table is doing, and there is no
    printed roster of those to author (see pools.custom_roll).

    Lives in the MAIN column rather than the sidebar: the roll list is long and the
    tracker beside it is short, so this fills the space under the tracker instead of
    adding to the taller side. It shares `state` with the sidebar, which is why both
    take the caller's refresh — the sidebar's penalty toggles govern these rows too.
    """
    mobility = viewmod.pool_mobility_lines(ruleset, character)

    def _set(key, value) -> None:
        state[key] = value
        on_change()

    with _panel("Dice pool  ·  your own Attribute + Ability", pal):
        with ui.row().classes("w-full gap-2 items-end flex-wrap"):
            attributes, abilities = viewmod.pool_trait_options()
            ui.select(attributes, value=state["custom_attribute"], label="Attribute",
                      on_change=lambda e: _set("custom_attribute", e.value)
                      ).classes("w-40").props("dense outlined")
            ui.select(abilities, value=state["custom_ability"], label="Ability",
                      with_input=True,
                      on_change=lambda e: _set("custom_ability", e.value)
                      ).classes("w-40").props("dense outlined")
            # p.332's discretionary clause is the Storyteller's call, so it is a
            # control rather than a guess — see view.build_custom_pool.
            if mobility:
                ui.checkbox("Agility or balance (armour mobility applies)",
                            value=state["custom_agility"],
                            on_change=lambda e: _set("custom_agility", e.value)
                            ).props("dense").classes("text-xs")
        for row in viewmod.build_custom_pool(
                ruleset, character,
                AttributeName(state["custom_attribute"]),
                AbilityName(state["custom_ability"]),
                agility_based=state["custom_agility"],
                include_mobility=state["mobility"], include_wound=state["wound"],
                include_fatigue=state["fatigue"]):
            _pool_row(row, pal)
        ui.label("The wound, fatigue and mobility switches in the sidebar govern "
                 "these rows too. Same caveats: a BASE pool, no Charms, no stunts, "
                 "nothing rolled.").classes("text-xs text-gray-500")


def dice_pool_sidebar(ruleset: RuleSet, character: Character,
                      pal: theme.Palette, state: dict, on_change) -> None:
    """The base dice-pool sidebar (decision 0016).

    A LIST, not a picker: every roll the catalogue knows, each on one line with its
    own arithmetic, so a player scans for the row they need instead of driving a
    dropdown mid-turn. One shared weapon choice and three penalty toggles sit above
    it; the standing exclusions sit below.

    ⚠ Read 0016 before changing this. The arithmetic is in scope; resolution is not,
    and NO dice are rolled (0009). The presentation is load-bearing, not decoration:
    0008 rejected a static combat number because it "looks authoritative and is
    wrong the moment a Charm fires", and what 0016 accepted instead is an itemised
    breakdown that states what it leaves out. **Every row must keep showing its
    `compact` breakdown** — a list of bare totals is precisely what 0008 refused —
    and the exclusions block must stay put and stay undismissable.

    All arithmetic and every derived list comes from view.build_pool_sidebar; this
    function lays out what it returns and nothing else.

    `on_change` is the CALLER's refresh, not a private one: the custom-pool block
    lives in the other column and reads the same `state`, so a toggle flipped here
    has to redraw both. A refreshable local to this function could not reach it.
    """
    def _set(key, value) -> None:
        state[key] = value
        on_change()

    def panel() -> None:
        sv = viewmod.build_pool_sidebar(
            ruleset, character, weapon_index=state["weapon"],
            arrow_index=state["arrow"],
            include_mobility=state["mobility"], include_wound=state["wound"],
            include_fatigue=state["fatigue"])

        # ⚠ A stale selection is a build-time crash, not a cosmetic problem — see
        # view.clamp_pool_selection, which owns the rule and carries the reasoning.
        viewmod.clamp_pool_selection(state, sv)

        # ---- controls ---------------------------------------------------- #
        if sv.weapons:
            # Labelled "Attack with" rather than "Weapon": a plain "Weapon" select
            # already exists on the equipment surface, and two identically labelled
            # selects are indistinguishable to the test harness.
            ui.select(dict(sv.weapons), value=state["weapon"],
                      label="Attack with", clearable=True,
                      on_change=lambda e: _set("weapon", e.value)
                      ).classes("w-full").props("dense outlined")
        if sv.arrows:
            # Only for a weapon that fires them, and deliberately a SEPARATE control
            # from "Attack with": the bow is what you roll, the arrow is what lands.
            ui.select(dict(sv.arrows), value=state["arrow"], label="Nocked arrow",
                      clearable=True, on_change=lambda e: _set("arrow", e.value)
                      ).classes("w-full").props("dense outlined")
        if sv.arrow_note:
            # Reference text, sitting with the controls rather than inside a pool row,
            # so it cannot read as a term in the arithmetic. An arrow contributes no
            # dice — core p.330 gives arrows a base damage and a soak clause and no
            # accuracy — and this build derives no damage at all (decision 0008).
            ui.label(sv.arrow_note).classes("text-xs opacity-70"
                                            ).props('data-testid="arrow-note"')
            ui.label("Damage only — an arrow adds no dice to the attack pool."
                     ).classes("text-xs italic opacity-60")
        else:
            ui.label("No weapon owned — the attack rows are unarmed.").classes(
                "text-xs text-gray-600")

        with ui.column().classes("gap-0"):
            if sv.wound_label and sv.wound_label != "Incapacitated":
                ui.switch(f"Wound penalty ({sv.wound_label})", value=state["wound"],
                          on_change=lambda e: _set("wound", e.value)
                          ).props("dense").classes("text-xs")
            if sv.fatigue_points:
                ui.switch(f"Fatigue (-{sv.fatigue_points})", value=state["fatigue"],
                          on_change=lambda e: _set("fatigue", e.value)
                          ).props("dense").classes("text-xs")
            if sv.mobility_lines:
                ui.switch(f"Armour mobility ({', '.join(sv.mobility_lines)})",
                          value=state["mobility"],
                          on_change=lambda e: _set("mobility", e.value)
                          ).props("dense").classes("text-xs")
        if sv.wound_label == "Incapacitated":
            ui.label("Deepest mark is Incapacitated — that level carries no dice "
                     "penalty of its own; whether the character acts at all is the "
                     "Storyteller's call.").classes("text-xs text-amber-700")

        ui.separator()

        # ---- the rolls ---------------------------------------------------- #
        for category, rows in sv.groups:
            ui.label(category.upper()).classes(
                "text-xs font-bold tracking-widest mt-2").style(f"color:{pal.accent}")
            for row in rows:
                _pool_row(row, pal)

        if sv.any_below_one:
            # Not clamped: the book floors range penalties and nothing else (p.229),
            # so a general floor would be invented. Say what happened instead.
            ui.label("Rows in amber have been taken below one die by the penalties. "
                     "The core floors range penalties at 1 die and prints no general "
                     "rule, so that is the Storyteller's call.").classes(
                "text-xs text-amber-700 mt-2")

        ui.separator()

        # ---- the standing caveat ------------------------------------------ #
        # NOT collapsible and NOT dismissible: this is the whole reason decision
        # 0016 could narrow 0008. See the docstring.
        ui.label("These are BASE pools. They do not include:").classes(
            "text-xs font-semibold mt-2")
        for line in sv.excludes:
            ui.label(f"· {line}").classes("text-xs text-gray-600 leading-tight")
        ui.label("No dice are rolled here, and nothing is resolved.").classes(
            "text-xs text-gray-500 mt-1")

    with ui.card().classes(f"w-full p-3 {pal.card_soft} gap-2"):
        ui.label("DICE POOLS").classes(
            "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
        panel()


def build_play(ruleset: RuleSet, character: Character, save_path: Path,
               *, with_header: bool = True) -> None:
    """Render the in-play tracker for `character`. With `with_header=False` the
    title/Save bar is omitted (the embedding app provides one). The tab is live
    regardless of chargen lock — play happens after creation, but never blocks."""
    pal = theme.palette(character.exalt_type)
    # Outside `body`, deliberately — see new_pool_state.
    pool_state = new_pool_state(ruleset)

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

        # Two columns: the dice-pool sidebar on the left, the tracker on the right.
        # `items-start` so the sidebar does not stretch to the tracker's height, and
        # NO `no-wrap` on the outer row — on a narrow window the sidebar drops above
        # the tracker instead of crushing it (a `no-wrap` row has done exactly that
        # to a panel here before).
        def tracker() -> None:
            """The right-hand column: the play-state tracker proper."""
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

            # --- Accumulated armour fatigue (p.332) ---------------------- #
            # Shown only where it can matter: armour is worn, or points are already
            # on the clock (they outlive taking the armour off — they dissipate with
            # rest, not with undressing). A character who never wears armour should
            # not carry a permanently-zero control.
            if character.armor or cur.fatigue:
                with _panel(f"Armour fatigue  ({cur.fatigue} accumulated — "
                            f"-{cur.fatigue} to all actions)" if cur.fatigue
                            else "Armour fatigue  (none accumulated)", pal):
                    with ui.row().classes("gap-4 items-end flex-wrap"):
                        ui.number("Points", value=cur.fatigue, min=0, format="%d",
                                  on_change=lambda e: (
                                      set_fatigue(character, e.value), body.refresh())
                                  ).classes("w-28")
                        if pv.fatigue_difficulties:
                            ui.label("Fatigue roll difficulty: "
                                     + ", ".join(pv.fatigue_difficulties)).classes(
                                "text-xs text-gray-600")
                    ui.label("Each failed Stamina + Endurance roll against the armour's "
                             "fatigue value adds a point; each dissipates after eight "
                             "hours of rest out of the armour (p.332). Both are the "
                             "Storyteller's call — this counter is manual, like Limit.").classes(
                        "text-xs text-gray-500")

            # --- Motes (numeric; capacities derived, spend is user input) - #
            # A merged pool is ONE track: "all of which is considered Peripheral"
            # (p.41), so the Personal box would be a permanent 0/0 that reads as
            # broken. Say the rule in the header instead of rendering a dead input.
            title = ("Essence — single pool (motes spent — manual)" if pv.single_pool
                     else "Essence (motes spent — manual)")
            with _panel(title, pal):
                with ui.row().classes("gap-6 flex-wrap items-end"):
                    if not pv.single_pool:
                        _mote_input("Personal", "motes_personal_spent",
                                    cur.motes_personal_spent, pv.personal_max)
                    _mote_input("Peripheral" if not pv.single_pool else "All motes",
                                "motes_peripheral_spent",
                                cur.motes_peripheral_spent, pv.peripheral_max)
                # Essence Awareness unlocks only a third of the pool freely; the rest
                # needs a Willpower roll the table makes, not this app. The inputs
                # still run to the full maximum — those motes are spendable — so the
                # line goes under them as a note rather than as a second cap.
                if pv.free_max is not None:
                    ui.label(f"{pv.free_max} of these may be spent freely; the rest "
                             f"need a Willpower roll (Essence Awareness)"
                             ).classes("text-xs opacity-70 mt-1")

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
                        # Two different causes, and the ST needs to know which: a Flaw
                        # shortened the track outright, or permanent Resonance is
                        # occupying part of it (ruled 2026-07-31 — permanent is headroom
                        # off the maximum, not a rating riding alongside).
                        why = []
                        if character.limit_permanent:
                            why.append(f"{character.limit_permanent} permanent")
                        curse = merits.LIMIT_MAX - lim_max - character.limit_permanent
                        if curse > 0:
                            why.append(f"{curse} by a Flaw")
                        ui.label(f"Maximum {lim} reduced from {merits.LIMIT_MAX} "
                                 f"({', '.join(why)}).").classes(
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
                        ui.label(f"Cumulative with temporary {lim}: it occupies "
                                 f"{character.limit_permanent} of the {merits.LIMIT_MAX}, "
                                 f"so the track above runs to {lim_max}.").classes(
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
            # --- the custom Attribute + Ability pool (decision 0016) ----- #
            if pool_state:
                custom_pool_panel(ruleset, character, pal, pool_state, body.refresh)

            ui.button("Clear motes spent", icon="refresh", on_click=clear_motes).props(
                f"flat color={pal.button}").tooltip(
                "Resets Personal and Peripheral motes spent to 0. "
                f"Willpower, Health, and {_curse} are left to you / the ST.")

        # Two columns: the dice-pool sidebar on the left, the tracker on the right.
        # `items-start` so the sidebar does not stretch to the tracker's height, and
        # deliberately NO `no-wrap` on the outer row — on a narrow window the sidebar
        # drops above the tracker rather than crushing it, which is what a `no-wrap`
        # row has already done to a panel in this build once.
        with ui.row().classes("w-full gap-4 items-start justify-center"):
            if pool_state:
                with ui.column().classes("w-80 shrink-0 gap-2"):
                    dice_pool_sidebar(ruleset, character, pal, pool_state,
                                      body.refresh)
            with ui.column().classes("flex-1 min-w-0 max-w-3xl gap-3"):
                tracker()

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
