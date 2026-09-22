"""
spikes/campaign_page — three shapes for the /table/<id> campaign page.

Throwaway. Nothing in `exalted_builder/` is edited. The cards read the shipped
presenter `view.build_party_card_view`, thus the numbers are real.

Run:  .venv/bin/python -m spikes.campaign_page   then open
      http://localhost:8765/a   /b   /c
Query parameters: `?st=0` shows the player view. The default is the Storyteller view.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from nicegui import ui

import exalted_builder
from exalted_builder import persistence, rules_db
from exalted_builder.engine import adversaries as adv, dice, play as engineplay
from exalted_builder.models.character import Damage, PlayState
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

ROOT = Path(exalted_builder.__file__).resolve().parent.parent
DATA = Path(exalted_builder.__file__).resolve().parent / "data"
PORT = 8765

RULESET = rules_db.load_ruleset(DATA)
PAL = theme.palette(None)

_GOLD, _WHITE, _BORDER = "#c9a227", "#ffffff", "#d6b98c"
_MARK = {Damage.BASHING: "#1f2937", Damage.LETHAL: "#9a1b1b", Damage.AGGRAVATED: "#6b21a8"}

CAMPAIGN = "The Thousand-Scale Court"
STORYTELLER = "gil"
PLAYERS = ["mira", "tobias", "sam", "ren"]
ME = "mira"
WATCHERS = ["jun"]
REQUESTS = [("alex", "Asks to bring Sword of the Morning (Solar · Zenith).",
             "Carries 2 homebrew Charms."), ("pat", "Asks to watch.", "")]
ROLLS = [("gil", "Initiative — Yarak", "7 dice → 3 successes"),
         ("mira", "Dex + Melee", "8 dice → 4 successes"),
         ("tobias", "Soak", "5 dice → 1 success")]


def _party() -> list[tuple[str, object]]:
    """Return (player, character) for the four example characters, with damage marked."""
    out = []
    for offset, path in enumerate(sorted((ROOT / "examples").glob("*.character.json"))):
        character = persistence.load_character(path)
        boxes = len(viewmod.build_play_view(RULESET, character).health_boxes)
        for i in range(min(offset + 1, boxes)):
            engineplay.cycle_mark(character, i, boxes)
        state = character.play or PlayState()
        state.willpower_spent = offset
        state.limit = offset * 2
        state.motes_peripheral_spent = offset * 3
        character.play = state
        out.append((PLAYERS[offset], character))
    return out


PARTY = _party()


def _adversaries() -> list:
    """REAL catalogue templates, instantiated, some damage marked. Two are allies."""
    catalog = rules_db.load_adversary_catalog(DATA)
    out = []
    for n, (tid, name, marks) in enumerate((
            ("adv.bandit", "Bandit leader", 2), ("adv.bandit", "Bandit", 0),
            ("adv.extra_competent", "Temple guard", 1),
            ("adv.beast_raiton", "Mira's raiton", 1), ("adv.partisan", "Lin the guide", 0))):
        foe = adv.instantiate(catalog[tid], f"adv.spike{n}", name=name)
        for i in range(marks):
            adv.cycle_mark(foe, i)
        out.append(foe)
    return out


ADVERSARIES = _adversaries()
# ⚠ Spike stand-in for a new `Adversary.side` field ("enemy" / "ally"). The ST sets it.
SIDE: dict[str, str] = {"adv.spike3": "ally", "adv.spike4": "ally"}


def side_of(foe) -> str:
    return SIDE.get(foe.id, "enemy")


@dataclass
class LogEntry:
    """One line of the campaign log: a message, or a roll with an optional caption.
    ⚠ A roll's caption is what the player typed. The app never names a roll (0019)."""
    who: str
    text: str = ""
    roll: dice.RollResult | None = None
    count: int = 0
    at: float = field(default_factory=time.time)


# ⚠ Process-wide on purpose: two browser windows on this spike share one log,
# thus you can watch a message cross. Production keeps it in the table context.
LOG: list[LogEntry] = []


def _seed_log() -> None:
    import random
    rng = random.Random(7)
    for who, text, count in (("gil", "The shrine doors grind open. Three bandits look up "
                              "from the offering bowls.", 0),
                             ("tobias", "Gearheart steps in front of the others.", 0),
                             ("mira", "I swing at the nearest bandit", 8),
                             ("gil", "", 6),
                             ("sam", "Can I tell if the wards are still up?", 0)):
        LOG.append(LogEntry(who, text, dice.roll(count, rng=rng) if count else None, count))


_seed_log()


# --------------------------------------------------------------------------- #
# Shared pieces
# --------------------------------------------------------------------------- #

def page_start(is_st: bool, design: str) -> None:
    ui.add_head_html(PAL.head_style())
    ui.query("body").style(f"background:{PAL.bg};color:{PAL.ink}")
    with ui.header().classes("items-center justify-between px-4 py-1").style(
            f"background:{PAL.accent}"):
        with ui.row().classes("items-center gap-1 no-wrap"):
            ui.button("Home", icon="chevron_left").props("flat dense no-caps color=white")
            ui.label("›").classes("text-white/70")
            ui.label(CAMPAIGN).classes("text-lg font-bold text-white")
            ui.label("Storyteller" if is_st else "Player").classes(
                "text-xs text-white/80 pl-2")
        with ui.row().classes("items-center gap-2 no-wrap"):
            if not is_st:
                ui.select({"kael": "Open as: Ashes-of-Dawn", "watch": "Spectate"},
                          value="kael").props(
                    "dense dark borderless options-dense").classes("text-white w-48")
            if is_st:
                with ui.button(icon="how_to_reg").props("flat round color=white"):
                    ui.badge(str(len(REQUESTS)), color="red").props("floating")
                ui.tooltip("Join requests")
            ui.button(icon="casino").props("flat round color=white").tooltip("Dice")
            ui.button(icon="more_vert").props("flat round color=white")
    ui.label(f"SPIKE {design}").classes(
        "fixed bottom-2 left-2 z-50 text-xs font-mono px-2 py-1 rounded bg-black/70 text-white")


def heading(title: str, count: int | None = None) -> None:
    text = title if count is None else f"{title} ({count})"
    ui.label(text).classes("text-xs font-bold tracking-widest").style(f"color:{PAL.accent}")


def health_strip(character, cv, size: float = 1.1) -> None:
    marks = list((character.play or PlayState()).health)
    marks += [None] * max(0, len(cv.play.health_boxes) - len(marks))
    with ui.row().classes("gap-0.5"):
        for mark in marks:
            ui.label(mark.value if mark else "").style(
                f"width:{size}rem;height:{size}rem;line-height:{size}rem;text-align:center;"
                f"font-size:{size * 0.6}rem;font-weight:700;border-radius:3px;"
                f"border:1px solid {_BORDER};background:{_GOLD if mark else _WHITE};"
                f"color:{_MARK[mark] if mark else PAL.accent}")


def dots(filled: int, total: int, size: float = 0.7) -> None:
    with ui.row().classes("gap-0.5 no-wrap"):
        for i in range(total):
            ui.element("div").style(
                f"width:{size}rem;height:{size}rem;border-radius:2px;"
                f"border:1px solid {_BORDER};background:{_GOLD if i < filled else _WHITE}")


def stat_lines(character, cv) -> None:
    cur = character.play or PlayState()
    sp, spp = viewmod.spent_motes(cv.play, cur)
    wp_left = cv.play.willpower_max - cur.willpower_spent
    with ui.row().classes("items-center gap-x-3 gap-y-0 text-xs"):
        ui.label(f"Motes {cv.play.personal_max - sp}/{cv.play.personal_max} · "
                 f"{cv.play.peripheral_max - spp}/{cv.play.peripheral_max}")
        with ui.row().classes("items-center gap-1 no-wrap"):
            ui.label(f"WP {wp_left}/{cv.play.willpower_max}")
            dots(wp_left, cv.play.willpower_max)


def compact_row(player: str, character, *, mine: bool = False) -> None:
    """One character as a dense row: accent strip, name, health, motes, Willpower."""
    cv = viewmod.build_party_card_view(RULESET, character)
    cpal = theme.palette(character.exalt_type)
    ring = f"outline:2px solid {cpal.accent};" if mine else ""
    with ui.row().classes(f"w-full no-wrap gap-0 rounded overflow-hidden {cpal.card_soft}"
                          ).style(ring):
        ui.element("div").classes("w-1 self-stretch").style(f"background:{cpal.accent}")
        with ui.column().classes("gap-1 px-2 py-1.5 min-w-0 flex-1"):
            with ui.row().classes("w-full items-baseline justify-between no-wrap gap-2"):
                ui.label(cv.name).classes("text-sm font-bold truncate").style(
                    f"color:{cpal.accent}")
                ui.label(player + (" (you)" if mine else "")).classes(
                    "text-xs opacity-60 shrink-0")
            ui.label(cv.identity_line).classes("text-xs opacity-70 truncate -mt-1")
            health_strip(character, cv, 0.95)
            stat_lines(character, cv)


def own_panel(player: str, character) -> None:
    """The viewer's own character: the same rail row, with live controls.
    Health and the dot tracks are clickable, the motes have spend and regain steps."""
    cpal = theme.palette(character.exalt_type)

    def step(field: str, delta: int, cap: int) -> None:
        cur = getattr(engineplay.play_state(character), field)
        engineplay.set_motes(character, field, cur + delta, cap)
        body.refresh()

    def click_box(el, handler) -> None:
        el.classes("cursor-pointer select-none").on("click", handler)

    @ui.refreshable
    def body() -> None:
        cv = viewmod.build_party_card_view(RULESET, character)
        cur = character.play or PlayState()
        n = len(cv.play.health_boxes)
        marks = list(cur.health) + [None] * max(0, n - len(cur.health))
        with ui.row().classes(f"w-full no-wrap gap-0 rounded overflow-hidden {cpal.card_soft}"
                              ).style(f"outline:2px solid {cpal.accent}"):
            ui.element("div").classes("w-1 self-stretch").style(f"background:{cpal.accent}")
            with ui.column().classes("gap-1.5 px-2 py-2 min-w-0 flex-1"):
                with ui.row().classes("w-full items-baseline justify-between no-wrap gap-2"):
                    ui.label(cv.name).classes("text-sm font-bold truncate").style(
                        f"color:{cpal.accent}")
                    ui.button(icon="open_in_new").props(
                        "flat dense round size=xs").tooltip("Open my sheet")
                ui.label(cv.identity_line).classes("text-xs opacity-70 truncate -mt-1.5")

                heading(f"HEALTH · penalty {engineplay_penalty(cv, marks)}")
                with ui.row().classes("gap-0.5"):
                    for i, mark in enumerate(marks):
                        box = ui.label(mark.value if mark else "").style(
                            "width:1.35rem;height:1.35rem;line-height:1.35rem;"
                            "text-align:center;font-size:.8rem;font-weight:700;"
                            f"border-radius:3px;border:1px solid {_BORDER};"
                            f"background:{_GOLD if mark else _WHITE};"
                            f"color:{_MARK[mark] if mark else cpal.accent}")
                        click_box(box, lambda _=None, i=i: (
                            engineplay.cycle_mark(character, i, n), body.refresh()))

                sp, spp = viewmod.spent_motes(cv.play, cur)
                for label, field, spent, cap in (
                        ("Personal", "motes_personal_spent", sp, cv.play.personal_max),
                        ("Peripheral", "motes_peripheral_spent", spp, cv.play.peripheral_max)):
                    mote_meter(label, field, spent, cap, step)

                wp_left = cv.play.willpower_max - cur.willpower_spent
                with ui.row().classes("w-full items-center no-wrap gap-1"):
                    ui.label(f"WP {wp_left}/{cv.play.willpower_max}").classes(
                        "text-xs w-14 shrink-0")
                    with ui.row().classes("gap-0.5"):
                        for i in range(cv.play.willpower_max):
                            d = ui.element("div").style(
                                f"width:.9rem;height:.9rem;border-radius:2px;"
                                f"border:1px solid {_BORDER};"
                                f"background:{_GOLD if i < wp_left else _WHITE}")
                            # A click spends down to the box, as the Play tab's track.
                            click_box(d, lambda _=None, i=i, m=cv.play.willpower_max: (
                                engineplay.set_count(character, "willpower_spent", m - i, m),
                                body.refresh()))
                with ui.row().classes("w-full items-center no-wrap gap-1"):
                    ui.label(f"Limit {cur.limit}/10").classes("text-xs w-14 shrink-0")
                    with ui.row().classes("gap-0.5"):
                        for i in range(10):
                            d = ui.element("div").style(
                                f"width:.9rem;height:.9rem;border-radius:2px;"
                                f"border:1px solid {_BORDER};"
                                f"background:{_GOLD if i < cur.limit else _WHITE}")
                            click_box(d, lambda _=None, i=i: (
                                engineplay.set_count(character, "limit", i + 1, 10),
                                body.refresh()))
    body()


def mote_meter(label: str, field: str, spent: int, cap: int, step) -> None:
    """One pool as a bar of what is LEFT, with − and + at its ends.
    A click on the bar opens a box: type a number and press Enter to spend it."""
    left = cap - spent
    pct = 0 if cap == 0 else 100 * left / cap
    with ui.row().classes("w-full items-center no-wrap gap-1"):
        ui.label(label).classes("text-xs w-16 shrink-0")
        ui.button(icon="remove", on_click=lambda: step(field, 1, cap)).props(
            f"flat dense round size=xs color={PAL.button}").tooltip("Spend 1")
        with ui.element("div").classes("relative flex-1 cursor-pointer rounded").style(
                f"height:1.25rem;border:1px solid {_BORDER};background:{_WHITE}"
                ).tooltip("Click to spend or regain an amount"):
            ui.element("div").classes("absolute inset-y-0 left-0 rounded-sm").style(
                f"width:{pct}%;background:{_GOLD}")
            ui.label(f"{left}/{cap}").classes(
                "absolute inset-0 text-center text-xs font-bold").style("line-height:1.2rem")
            with ui.menu().props("anchor='bottom middle' self='top middle'") as menu:
                with ui.column().classes("p-2 gap-1"):
                    amount = ui.number(f"{label} motes", value=None, min=0, format="%d").props(
                        "dense outlined autofocus").classes("w-32")

                    def apply(sign: int) -> None:
                        step(field, sign * int(amount.value or 0), cap)
                        menu.close()
                    amount.on("keydown.enter", lambda: apply(1))
                    with ui.row().classes("gap-1 no-wrap"):
                        ui.button("Spend", on_click=lambda: apply(1)).props(
                            f"dense no-caps size=sm color={PAL.button}")
                        ui.button("Regain", on_click=lambda: apply(-1)).props(
                            "dense no-caps size=sm outline")
                        ui.button("Full", on_click=lambda: (step(field, -cap, cap),
                                                            menu.close())).props(
                            "dense no-caps size=sm flat")
        ui.button(icon="add", on_click=lambda: step(field, -1, cap)).props(
            f"flat dense round size=xs color={PAL.button}").tooltip("Regain 1")


def adversary_row(foe, *, editable: bool, on_side=None) -> None:
    """One adversary: name, category, health track and penalty. The ST clicks the boxes."""
    marks = adv.normalize_damage(foe)
    penalty = adv.worst_penalty(foe)

    @ui.refreshable
    def track() -> None:
        with ui.row().classes("gap-0.5"):
            for i, mark in enumerate(adv.normalize_damage(foe)):
                box = ui.label(mark.value if mark else "").style(
                    "width:.95rem;height:.95rem;line-height:.95rem;text-align:center;"
                    "font-size:.6rem;font-weight:700;border-radius:3px;"
                    f"border:1px solid {_BORDER};background:{_GOLD if mark else _WHITE};"
                    f"color:{_MARK[mark] if mark else PAL.ink}")
                if editable:
                    box.classes("cursor-pointer select-none").on(
                        "click", lambda _=None, i=i: (adv.cycle_mark(foe, i), track.refresh()))
    with ui.row().classes("w-full no-wrap gap-0 rounded overflow-hidden").style(
            "background:#00000008;border:1px solid #0000001a"):
        ui.element("div").classes("w-1 self-stretch").style("background:#57534e")
        with ui.column().classes("gap-0.5 px-2 py-1 min-w-0 flex-1"):
            with ui.row().classes("w-full items-baseline justify-between no-wrap gap-2"):
                ui.label(foe.name).classes("text-sm font-bold truncate")
                with ui.row().classes("items-center gap-1 no-wrap shrink-0"):
                    ui.label(adv.category_label(foe)).classes("text-xs opacity-60")
                    if on_side is not None:
                        ally = side_of(foe) == "ally"
                        ui.button("Ally" if ally else "Enemy",
                                  on_click=lambda _=None: on_side(foe)).props(
                            "dense outline no-caps size=sm padding='0 6px' "
                            f"color={'positive' if ally else 'negative'}").tooltip(
                            "Players see an ally's name and health. Click to switch.")
            track()
            if penalty is not None:
                ui.label(f"Penalty {adv.level_label(penalty)}").classes("text-xs opacity-70")


def ally_row(foe) -> None:
    """An ally as a player sees it: the name and the health track. No stats."""
    with ui.row().classes("w-full no-wrap gap-0 rounded overflow-hidden").style(
            "background:#15803d0d;border:1px solid #15803d33"):
        ui.element("div").classes("w-1 self-stretch").style("background:#15803d")
        with ui.column().classes("gap-0.5 px-2 py-1 min-w-0 flex-1"):
            ui.label(foe.name).classes("text-sm font-bold truncate")
            with ui.row().classes("gap-0.5"):
                for mark in adv.normalize_damage(foe):
                    ui.label(mark.value if mark else "").style(
                        "width:.95rem;height:.95rem;line-height:.95rem;text-align:center;"
                        "font-size:.6rem;font-weight:700;border-radius:3px;"
                        f"border:1px solid {_BORDER};background:{_GOLD if mark else _WHITE};"
                        f"color:{_MARK[mark] if mark else PAL.ink}")


def engineplay_penalty(cv, marks) -> str:
    return viewmod.worst_penalty(cv.play, marks)


def full_card(player: str, character, *, mine: bool = False) -> None:
    """The Party page card, read-only: every tracker, plus soak and dodge."""
    cv = viewmod.build_party_card_view(RULESET, character)
    cpal = theme.palette(character.exalt_type)
    cur = character.play or PlayState()
    ring = f"outline:2px solid {cpal.accent};" if mine else ""
    with ui.card().classes(f"w-full p-0 gap-0 overflow-hidden {cpal.card_soft}").style(ring):
        ui.element("div").classes("w-full h-1").style(f"background:{cpal.accent}")
        with ui.column().classes("w-full gap-2 p-3"):
            with ui.row().classes("w-full items-start justify-between no-wrap"):
                with ui.column().classes("gap-0 min-w-0"):
                    ui.label(cv.name).classes("text-base font-bold truncate").style(
                        f"color:{cpal.accent}")
                    ui.label(cv.identity_line).classes("text-xs opacity-70 truncate")
                ui.label(f"Played by {player}" + (" (you)" if mine else "")).classes(
                    "text-xs opacity-60 shrink-0")
            heading("HEALTH")
            health_strip(character, cv, 1.5)
            sp, spp = viewmod.spent_motes(cv.play, cur)
            with ui.row().classes("gap-6 text-sm"):
                with ui.column().classes("gap-0"):
                    heading("MOTES")
                    ui.label(f"Personal {cv.play.personal_max - sp}/{cv.play.personal_max}")
                    ui.label(f"Peripheral {cv.play.peripheral_max - spp}/"
                             f"{cv.play.peripheral_max}")
                with ui.column().classes("gap-1"):
                    wp_left = cv.play.willpower_max - cur.willpower_spent
                    heading(f"WILLPOWER {wp_left}/{cv.play.willpower_max}")
                    dots(wp_left, cv.play.willpower_max, 1.0)
                    heading(f"LIMIT {cur.limit}/10")
                    dots(cur.limit, 10, 1.0)
            ui.label(f"Soak {cv.soak.bashing}B / {cv.soak.lethal}L / {cv.soak.aggravated}A"
                     f"  ·  Dodge {cv.dodge}  ·  Essence {cv.essence_rating}").classes(
                "text-xs opacity-80")
            with ui.row().classes("w-full justify-end gap-1"):
                ui.button("Sheet", icon="description").props("flat dense no-caps")
                if mine:
                    ui.button("Open my sheet", icon="open_in_new").props(
                        f"dense no-caps color={PAL.button}")


def board(height: str = "100%", note: str = "") -> None:
    """A placeholder for the P4 board: a drawing surface with free-text tokens.
    Decision 0020: a token is a picture and a label. It knows no character."""
    with ui.column().classes("w-full gap-0 rounded overflow-hidden").style(
            f"height:{height};border:1px solid {_BORDER};background:#fffdf7"):
        with ui.row().classes("w-full items-center gap-1 px-2 py-1").style(
                f"border-bottom:1px solid {_BORDER};background:#faf3e2"):
            for icon, tip in (("pan_tool", "Move"), ("edit", "Draw"),
                              ("crop_square", "Shape"), ("add_circle", "Token"),
                              ("image", "Background image"), ("auto_fix_normal", "Erase")):
                ui.button(icon=icon).props("flat dense round size=sm").tooltip(tip)
            ui.space()
            ui.label("BOARD — placeholder, P4").classes(
                "text-xs font-bold tracking-widest opacity-50")
        with ui.element("div").classes("relative w-full flex-1").style(
                "background-image:linear-gradient(#0000000d 1px,transparent 1px),"
                "linear-gradient(90deg,#0000000d 1px,transparent 1px);"
                "background-size:40px 40px"):
            ui.html('<svg width="100%" height="100%" style="position:absolute;inset:0">'
                    '<path d="M60 200 C 160 120, 260 260, 380 170 S 560 120, 640 220" '
                    'stroke="#8a5a1a" stroke-width="3" fill="none" opacity=".5"/>'
                    '<rect x="420" y="60" width="160" height="90" rx="6" '
                    'stroke="#1e40af" stroke-width="2" fill="#1e40af10"/>'
                    '<text x="430" y="80" font-size="12" fill="#1e40af">the shrine</text>'
                    '</svg>', sanitize=False)
            for x, y, colour, label in ((110, 150, "#b45309", "Kael"),
                                        (190, 190, "#be123c", "Yarak"),
                                        (480, 110, "#374151", "Bandit ×3"),
                                        (300, 250, "#7c3aed", "Nine Bells")):
                with ui.column().classes("absolute items-center gap-0").style(
                        f"left:{x}px;top:{y}px"):
                    ui.element("div").style(
                        f"width:28px;height:28px;border-radius:50%;background:{colour};"
                        "border:2px solid white;box-shadow:0 1px 3px #0005")
                    ui.label(label).classes("text-xs font-bold px-1 rounded bg-white/80")
            if note:
                ui.label(note).classes("absolute bottom-2 right-3 text-xs italic opacity-50")


def campaign_log(me: str, is_st: bool) -> None:
    """The one log: messages and rolls in time order, a text box and a dice box below.
    A 1-second poll repaints it when the log grows, as the table page will."""
    shown = {"n": -1}

    @ui.refreshable
    def entries() -> None:
        for e in LOG:
            mine = e.who == me
            with ui.column().classes("w-full gap-0 px-2 py-1 rounded").style(
                    f"background:{'#c9a22722' if mine else 'transparent'}"):
                with ui.row().classes("items-baseline gap-1 no-wrap"):
                    ui.label(e.who).classes("text-xs font-bold").style(
                        f"color:{PAL.accent if e.who == STORYTELLER else PAL.ink}")
                    if e.who == STORYTELLER:
                        ui.icon("star", size="0.7rem").style(f"color:{PAL.accent}")
                    ui.label(time.strftime("%H:%M", time.localtime(e.at))).classes(
                        "text-xs opacity-40")
                if e.text:
                    ui.label(e.text).classes("text-sm leading-snug")
                if e.roll is not None:
                    with ui.row().classes("items-center gap-1 no-wrap"):
                        ui.icon("casino", size="1rem").style(f"color:{PAL.accent}")
                        ui.label(f"{e.count} dice → {e.roll.summary}").classes(
                            "text-sm font-bold")
                    ui.label(" ".join(str(f) for f in sorted(e.roll.faces, reverse=True))
                             ).classes("text-xs font-mono opacity-60")

    def poll() -> None:
        if shown["n"] != len(LOG):
            shown["n"] = len(LOG)
            entries.refresh()
            area.scroll_to(percent=1.0)

    def send() -> None:
        text = (box.value or "").strip()
        if text:
            LOG.append(LogEntry(me, text))
            box.value = ""
            poll()

    def roll() -> None:
        count = int(count_in.value or 0)
        if count <= 0:
            return
        LOG.append(LogEntry(me, (box.value or "").strip(), dice.roll(count), count))
        box.value = ""
        poll()

    area = ui.scroll_area().classes("w-full").style("height:calc(100vh - 250px)")
    with area:
        with ui.column().classes("w-full gap-1"):
            entries()
    with ui.column().classes("w-full gap-1 pt-1").style(f"border-top:1px solid {_BORDER}"):
        box = ui.input(placeholder="Say something, or caption a roll…").props(
            "dense outlined").classes("w-full")
        box.on("keydown.enter", send)
        with ui.row().classes("w-full items-center no-wrap gap-1"):
            count_in = ui.number(value=6, min=1, max=dice.MAX_DICE if hasattr(dice, "MAX_DICE")
                                 else 50, format="%d").props("dense outlined").classes("w-16")
            ui.button("Roll", icon="casino", on_click=roll).props(
                f"dense no-caps color={PAL.button}").tooltip(
                "Rolls the dice. The text box, if filled, becomes the caption.")
            ui.space()
            ui.button(icon="send", on_click=send).props(
                f"flat dense round color={PAL.button}").tooltip("Send (Enter)")
    ui.timer(1.0, poll)


def notes() -> None:
    heading("SESSION NOTES")
    ui.textarea(value="Kael owes the Guild 40 talents.\nThe shrine is warded — ask "
                "Yarak's player about the seal.").props("outlined autogrow dense").classes(
        "w-full text-sm")


def members() -> None:
    heading("MEMBERS", 1 + len(PLAYERS) + len(WATCHERS))
    with ui.row().classes("gap-1"):
        ui.chip(f"{STORYTELLER} · ST", icon="star").props("outline dense")
        for p in PLAYERS:
            ui.chip(p, icon="person").props("outline dense")
        for w in WATCHERS:
            ui.chip(f"{w} · watching", icon="visibility").props("outline dense")


def st_tools(compact: bool = False) -> None:
    heading("REQUESTS", len(REQUESTS))
    for who, what, extra in REQUESTS:
        with ui.card().classes(f"w-full px-2 py-1.5 gap-0 {PAL.card_soft}"):
            ui.label(who).classes("text-sm font-bold")
            ui.label(what).classes("text-xs opacity-80")
            if extra:
                ui.label(extra).classes("text-xs")
            with ui.row().classes("gap-1 justify-end w-full"):
                ui.button("Approve", icon="check").props(
                    f"dense no-caps size=sm color={PAL.button}")
                ui.button("Reject", icon="close").props("flat dense no-caps size=sm "
                                                         "color=negative")
    heading("JOIN CODE")
    ui.label("K7Q2XD").classes("text-2xl font-mono font-bold -mt-1")
    heading("STORYTELLER")
    with ui.column().classes("gap-0"):
        for icon, label in (("military_tech", "Grant XP"), ("groups", "Adversaries"),
                            ("gavel", "House rules"), ("auto_stories", "Campaign homebrew"),
                            ("format_list_numbered", "Roll initiative")):
            ui.button(label, icon=icon).props(f"flat dense no-caps align=left color={PAL.button}").classes(
                "w-full")


def npcs(is_st: bool) -> None:
    """Allies for everyone (name and health). Enemies for the ST only (P3 §1,
    reaffirmed 2026-09-22). The ST sees every entry with its side switch."""
    def flip(foe) -> None:
        SIDE[foe.id] = "enemy" if side_of(foe) == "ally" else "ally"
        body.refresh()

    @ui.refreshable
    def body() -> None:
        allies = [f for f in ADVERSARIES if side_of(f) == "ally"]
        enemies = [f for f in ADVERSARIES if side_of(f) == "enemy"]
        if allies or is_st:
            ui.element("div").classes("pt-2")
            heading("ALLIES", len(allies))
        for foe in allies:
            if is_st:
                adversary_row(foe, editable=True, on_side=flip)
            else:
                ally_row(foe)
        if is_st:
            with ui.row().classes("w-full items-center justify-between pt-2"):
                heading("ENEMIES", len(enemies))
                ui.button(icon="add").props(
                    f"flat dense round size=sm color={PAL.button}").tooltip(
                    "Add from the catalogue")
            for foe in enemies:
                adversary_row(foe, editable=True, on_side=flip)
    body()


# --------------------------------------------------------------------------- #
# A — the virtual-tabletop layout: party rail | board | side rail
# --------------------------------------------------------------------------- #

@ui.page("/a")
def design_a(st: int = 1) -> None:
    is_st = bool(st)
    page_start(is_st, "A — tabletop: party | board | tools")
    with ui.row().classes("w-full no-wrap gap-3 p-3 items-stretch").style(
            "height:calc(100vh - 56px)"):
        with ui.scroll_area().classes("shrink-0").style("width:19rem;height:100%"):
            with ui.column().classes("w-full gap-2 pr-2"):
                heading("PARTY", len(PARTY))
                if not is_st:
                    heading("YOU PLAY")
                    for player, character in PARTY:
                        if player == ME:
                            own_panel(player, character)
                    heading("THE OTHERS")
                for player, character in PARTY:
                    if is_st or player != ME:
                        compact_row(player, character)
                npcs(is_st)
        with ui.column().classes("flex-1 min-w-0 h-full"):
            board("100%")
        me = STORYTELLER if is_st else ME
        with ui.column().classes("shrink-0 h-full gap-1").style("width:19rem"):
            with ui.tabs().props("dense no-caps align=left").classes("w-full") as tabs:
                t_log = ui.tab("Log")
                t_notes = ui.tab("Notes")
                t_st = ui.tab("ST") if is_st else None
            with ui.tab_panels(tabs, value=t_log).props("animated=false").classes(
                    "w-full bg-transparent"):
                with ui.tab_panel(t_log).classes("p-0 gap-1"):
                    campaign_log(me, is_st)
                with ui.tab_panel(t_notes).classes("p-0 gap-2"):
                    notes()
                    members()
                if t_st:
                    with ui.tab_panel(t_st).classes("p-0 gap-2"):
                        st_tools()


# --------------------------------------------------------------------------- #
# B — the builder's shape: a tab strip, one surface per tab
# --------------------------------------------------------------------------- #

@ui.page("/b")
def design_b(st: int = 1) -> None:
    is_st = bool(st)
    page_start(is_st, "B — tabs: Party | Board | Notes | Storyteller")
    with ui.column().classes("w-full max-w-6xl mx-auto px-4 py-2 gap-2"):
        with ui.row().classes("w-full items-end justify-between"):
            with ui.column().classes("gap-0"):
                ui.label(CAMPAIGN).classes("text-2xl font-bold").style(f"color:{PAL.accent}")
                ui.label(f"Storyteller: {STORYTELLER} · {len(PLAYERS)} players · "
                         f"{len(WATCHERS)} watching").classes("text-sm opacity-70")
        with ui.tabs().props("dense no-caps align=left").classes("w-full").style(
                f"border-bottom:1px solid {_BORDER}") as tabs:
            t_party = ui.tab("Party", icon="groups")
            ui.tab("Board", icon="map")
            ui.tab("Notes & rolls", icon="notes")
            if is_st:
                with ui.tab("Storyteller", icon="star"):
                    ui.badge(str(len(REQUESTS)), color="red").props("floating")
        with ui.tab_panels(tabs, value=t_party).props("animated=false").classes(
                "w-full bg-transparent"):
            with ui.tab_panel(t_party).classes("p-0 gap-3"):
                with ui.grid().classes("w-full gap-3").style(
                        "grid-template-columns:repeat(auto-fill,minmax(20rem,1fr))"):
                    for player, character in PARTY:
                        full_card(player, character, mine=(player == ME and not is_st))
                members()


@ui.page("/b-board")
def design_b_board(st: int = 1) -> None:
    """Design B with the Board tab open, for the screenshot."""
    is_st = bool(st)
    page_start(is_st, "B — tabs, Board tab open")
    with ui.column().classes("w-full px-4 py-2 gap-2"):
        ui.label(CAMPAIGN).classes("text-2xl font-bold").style(f"color:{PAL.accent}")
        with ui.tabs(value="Board").props("dense no-caps align=left").classes(
                "w-full").style(f"border-bottom:1px solid {_BORDER}"):
            ui.tab("Party", icon="groups")
            ui.tab("Board", icon="map")
            ui.tab("Notes & rolls", icon="notes")
            if is_st:
                ui.tab("Storyteller", icon="star")
        board("calc(100vh - 170px)")


# --------------------------------------------------------------------------- #
# C — board on top, the party as a dock along the bottom, ST in a drawer
# --------------------------------------------------------------------------- #

@ui.page("/c")
def design_c(st: int = 1) -> None:
    is_st = bool(st)
    page_start(is_st, "C — board + party dock + drawer")
    with ui.right_drawer(value=True, fixed=True).props("width=290 bordered").style(
            f"background:{PAL.bg}"):
        with ui.column().classes("w-full gap-2 p-1"):
            if is_st:
                st_tools()
            campaign_log(STORYTELLER if is_st else ME, is_st)
            notes()
            members()
    with ui.column().classes("w-full gap-2 p-3 no-wrap").style("height:calc(100vh - 56px)"):
        with ui.element("div").classes("w-full flex-1 min-h-0"):
            board("100%", note="Collapse the dock to give the board the whole page.")
        with ui.row().classes("w-full items-center justify-between"):
            heading("PARTY", len(PARTY))
            ui.button(icon="expand_more").props("flat dense round size=sm").tooltip(
                "Collapse the dock")
        with ui.row().classes("w-full no-wrap gap-2 overflow-x-auto shrink-0"):
            for player, character in PARTY:
                with ui.element("div").style("min-width:17rem;flex:1"):
                    compact_row(player, character, mine=(player == ME and not is_st))


@ui.page("/")
def index() -> None:
    for path, label in (("/a", "A — tabletop"), ("/b", "B — tabs"),
                        ("/b-board", "B — tabs, board open"), ("/c", "C — board + dock")):
        with ui.row():
            ui.link(label, path)
            ui.link("(player view)", path + "?st=0")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(port=PORT, reload=False, show=False, title="Campaign page spike")
