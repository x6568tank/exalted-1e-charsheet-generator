"""
ui/app.py — NiceGUI read-only character sheet.

A thin renderer: it loads a RuleSet and a Character, asks ui.view to build the
display model, and lays it out to loosely follow the one-page Solar sheet —
dot-tracks for ratings, abilities grouped by ability-caste, an attributes row,
an advantages band, and a bottom band of Willpower / Health+Soak / Virtues +
Essence. No game logic lives here. Run with:

    python -m exalted_builder.ui.app [path/to/foo.character.json]

With no argument it loads the bundled example character.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..models.character import Character
from ..models.rules import RuleSet
from . import theme
from . import view as viewmod

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "exalted_builder" / "data"
_EXAMPLE = _REPO_ROOT / "examples" / "ashes-of-dawn.character.json"

# Module-scoped palette so the module-level render helpers (_heading, _trait_row,
# _panel …) can theme by splat. render_sheet sets it from the SheetView's exalt
# type before drawing anything, so it always reflects the character on screen.
pal = theme.palette(None)

# Likewise module-scoped: what this splat calls the caste slot ("Caste" / "Aspect").
# render_sheet sets it from the SheetView so _trait_row's marker tooltip matches.
caste_noun = "Caste"


def _dots(value: int, total: int = 5) -> str:
    """Filled/empty pips, e.g. 3 -> '●●●○○'. Values above `total` get a '+N'."""
    filled = min(max(value, 0), total)
    s = "●" * filled + "○" * (total - filled)
    if value > total:
        s += f" +{value - total}"
    return s


def _heading(text: str) -> None:
    with ui.row().classes("w-full items-center gap-2 mt-1"):
        ui.element("div").classes(f"flex-1 border-t border-{pal.fam}-900/40")
        ui.label(text.upper()).classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
        ui.element("div").classes(f"flex-1 border-t border-{pal.fam}-900/40")


def _panel():
    return ui.card().classes(f"w-full p-3 {pal.card_soft}")


def _trait_row(r: viewmod.TraitRow, dot_total: int = 5) -> None:
    with ui.row().classes("w-full items-center gap-1 no-wrap"):
        if r.caste:
            ui.label("●").classes("text-xs").style(f"color:{pal.accent}").tooltip(caste_noun)
        elif r.favored:
            ui.label("✦").classes("text-xs text-sky-700").tooltip("Favored")
        else:
            ui.label("").classes("w-3")
        ui.label(r.label).classes("text-sm flex-1 truncate")
        ui.label(_dots(r.value, dot_total)).classes("text-sm font-mono tracking-tight")


def _content_mark(row) -> None:
    """The provenance marker beside a Charm/spell name: homebrew from the user's
    custom library, or an id that no longer resolves at all. Nothing is drawn for
    ordinary printed content, which is the overwhelming majority of rows.

    Custom content must stay obvious at a glance on a sheet (human's requirement,
    2026-07-29) — a Storyteller reading a player's sheet needs to see which Charms
    are not in any book."""
    if getattr(row, "missing", False):
        ui.label("⚠").classes("text-xs text-red-600").tooltip(
            f"'{row.name}' is not in the rule set — its definition is missing "
            f"(a deleted custom Charm, or a library this machine does not have).")
    elif getattr(row, "custom", False):
        ui.label("✎").classes("text-xs text-violet-700").tooltip("Custom (homebrew) content")


def _named_value(label: str, value: int, dot_total: int = 5) -> None:
    with ui.row().classes("w-full items-center gap-1 no-wrap"):
        ui.label(label).classes("text-sm flex-1")
        ui.label(_dots(value, dot_total)).classes("text-sm font-mono")


def render_sheet(view: viewmod.SheetView) -> None:
    global pal, caste_noun
    pal = theme.palette(view.exalt_type)
    caste_noun = view.caste_noun
    ui.add_head_html(pal.head_style())
    with ui.column().classes("w-full max-w-6xl mx-auto gap-2 p-4"):
        # --- header ------------------------------------------------------- #
        with _panel():
            with ui.row().classes("w-full justify-between items-start"):
                with ui.column().classes("gap-0"):
                    ui.label(view.name).classes("text-2xl font-bold")
                    ui.label(f"{view.caste} {view.caste_noun} {view.exalt_type}").style(f"color:{pal.accent}")
                with ui.column().classes("gap-0 text-right text-sm text-gray-600"):
                    if view.concept:
                        ui.label(f"Concept: {view.concept}")
                    if view.nature:
                        ui.label(f"Nature: {view.nature}")
                    ui.label("Chargen locked" if view.chargen_locked else "In creation")

        # --- attributes --------------------------------------------------- #
        _heading("Attributes")
        with ui.row().classes("w-full gap-2 items-stretch no-wrap"):
            for category, rows in view.attributes:
                with _panel().classes("flex-1"):
                    ui.label(category).classes("text-xs font-semibold text-center w-full").style(f"color:{pal.accent}")
                    for r in rows:
                        _trait_row(r)
        # Dragon-King breed innate weapons (PG pp.167-174) — their own section next
        # to the breed's attribute bonuses above. Display-only (decision 0008 keeps
        # attack derivation out), so each row shows the printed Spd/Acc/Dmg/Def like
        # the Equipment panel does, without ever feeding a roll.
        if view.breed_weapons:
            _heading("Innate Weapons")
            with _panel().classes("w-full"):
                for name, speed, accuracy, damage, damage_type, defense in view.breed_weapons:
                    ui.label(f"⚔ {name}  Spd{speed:+d} Acc{accuracy:+d} "
                             f"Dmg{damage:+d}{damage_type} Def{defense:+d}").classes("text-xs")

        # --- abilities (grouped by ability-caste) ------------------------- #
        _heading("Abilities")
        ui.label(f"● {view.caste_noun.lower()} · ✦ favored").classes("text-xs text-gray-400 -mt-1")
        groups = view.ability_groups
        for chunk_start in range(0, len(groups), 3):
            with ui.row().classes("w-full gap-2 items-stretch no-wrap"):
                for group_label, rows in groups[chunk_start:chunk_start + 3]:
                    with _panel().classes("flex-1"):
                        if group_label:
                            ui.label(group_label).classes("text-xs font-semibold text-center w-full").style(f"color:{pal.accent}")
                        for r in rows:
                            _trait_row(r)

        # --- specialties + backgrounds + the conditional panels ----------- #
        # WRAPS deliberately (no `no-wrap`): this row can hold up to five panels —
        # Backgrounds, Specialties, Merits & Flaws, Colleges, Thaumaturgy — and on a
        # no-wrap row the later ones squeeze to unreadable slivers. Each gets a min
        # width so they flow onto a second line instead. Do NOT add `no-wrap` back
        # without dropping the min widths, or the row overflows horizontally.
        with ui.row().classes("w-full gap-2 items-stretch"):
            with _panel().classes("flex-1 min-w-[14rem]"):
                ui.label("Backgrounds").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                if not view.backgrounds:
                    ui.label("—").classes("text-sm text-gray-400")
                for name, rating, note in view.backgrounds:
                    with ui.row().classes("w-full items-center gap-1 no-wrap"):
                        ui.label(f"{name}{' · ' + note if note else ''}").classes("text-sm flex-1 truncate")
                        ui.label(_dots(rating)).classes("text-sm font-mono")
            # Artifacts — dropped for the many characters who own none, the same rule
            # Fetters, Merits, Colleges and Thaumaturgy follow below.
            if view.artifacts:
                with _panel().classes("flex-1 min-w-[14rem]"):
                    ui.label("Artifacts").classes("text-xs font-semibold").style(
                        f"color:{pal.accent}")
                    for name, rating, source, damage in view.artifacts:
                        with ui.row().classes("w-full items-center gap-1 no-wrap"):
                            label = f"{name}{' · ' + source if source else ''}"
                            ui.label(label).classes("text-sm flex-1 truncate")
                            # A damaged artifact says so on the sheet: its soak is
                            # already reduced in the numbers above, and an unexplained
                            # low figure reads as a bug.
                            if damage:
                                ui.label(f"−{damage}").classes(
                                    "text-xs font-mono text-red-600")
                            ui.label(_dots(rating)).classes("text-sm font-mono")
            # Fetters and Passions — ghosts only, dropped entirely for everyone else,
            # the same rule Merits, Colleges and Thaumaturgy follow.
            if view.fetters:
                with _panel().classes("flex-1 min-w-[14rem]"):
                    with ui.row().classes("w-full items-baseline gap-2 no-wrap"):
                        ui.label("Fetters").classes("text-xs font-semibold").style(
                            f"color:{pal.accent}")
                        # The cap MOVES with Willpower and Essence, so it is printed
                        # beside the dots rather than left to the rulebook.
                        total = sum(r for _n, r, _t in view.fetters)
                        ui.label(f"{total}/{view.fetter_cap}").classes(
                            "text-xs font-mono " +
                            ("text-red-600" if total > view.fetter_cap else "text-gray-500"))
                    for name, rating, note in view.fetters:
                        with ui.row().classes("w-full items-center gap-1 no-wrap"):
                            ui.label(f"{name}{' · ' + note if note else ''}"
                                     ).classes("text-sm flex-1 truncate")
                            ui.label(_dots(rating)).classes("text-sm font-mono")
            if view.passions:
                with _panel().classes("flex-1 min-w-[14rem]"):
                    ui.label("Passions").classes("text-xs font-semibold").style(
                        f"color:{pal.accent}")
                    for virtue, distributed, pool in view.passion_pools:
                        rows = [(n, r) for v, n, r in view.passions if v == virtue]
                        if not rows and distributed == pool:
                            continue
                        with ui.row().classes("w-full items-baseline gap-2 no-wrap"):
                            ui.label(virtue).classes("text-xs font-semibold flex-1")
                            ui.label(f"{distributed}/{pool}").classes(
                                "text-xs font-mono " +
                                ("text-gray-500" if distributed == pool
                                 else "text-amber-700"))
                        for name, rating in rows:
                            with ui.row().classes("w-full items-center gap-1 no-wrap pl-2"):
                                ui.label(name).classes("text-sm flex-1 truncate")
                                ui.label(_dots(rating)).classes("text-sm font-mono")
            with _panel().classes("flex-1 min-w-[14rem]"):
                ui.label("Specialties").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                if not view.specialties:
                    ui.label("—").classes("text-sm text-gray-400")
                for ability, name, rating in view.specialties:
                    ui.label(f"{ability} — {name} ({rating})").classes("text-sm")
            # Merits & Flaws, dropped when there are none — the same rule Colleges and
            # Thaumaturgy follow, rather than an empty panel on every sheet. A Flaw's
            # value is shown with a + because it GRANTS points; a Merit's with a −.
            if view.merits_flaws:
                with _panel().classes("flex-1 min-w-[14rem]"):
                    ui.label("Merits & Flaws").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                    for name, points, detail, kind, tip in view.merits_flaws:
                        with ui.row().classes("w-full items-center gap-1 no-wrap"):
                            # The rules text rides on a tooltip: the panel shares its
                            # row with four others, so there is no room to print it,
                            # but a Merit you cannot read the text of is just a word.
                            row_label = ui.label(
                                f"{name}{' · ' + detail if detail else ''}").classes(
                                "text-sm flex-1 truncate cursor-help")
                            if tip:
                                row_label.tooltip(tip)
                            ui.label(points).classes(
                                "text-sm font-mono "
                                + ("opacity-70" if kind == "merit" else "font-semibold"))
            # Astrological Colleges are Sidereal-only, so the panel appears only when
            # the character has some — an empty one would sit on every other splat's
            # sheet saying "—", the same reason the Spells panel is conditional below.
            if view.colleges:
                with _panel().classes("flex-1 min-w-[14rem]"):
                    ui.label("Astrological Colleges").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                    for name, rating, house_label, own in view.colleges:
                        with ui.row().classes("w-full items-center gap-1 no-wrap"):
                            ui.label(f"{'★ ' if own else ''}{name}").classes(
                                "text-sm flex-1 truncate").tooltip(house_label)
                            ui.label(_dots(rating)).classes("text-sm font-mono")
            # Thaumaturgy is cross-splat, so unlike Colleges this can appear on any
            # sheet — and like them it is dropped entirely when there is none, rather
            # than sitting on every non-thaumaturge's sheet saying "—".
            if view.thaumaturgy:
                with _panel().classes("flex-1 min-w-[14rem]"):
                    ui.label("Thaumaturgy").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                    if view.thaumaturgy_note:
                        ui.label(view.thaumaturgy_note).classes("text-xs italic text-amber-700")
                    for section, items in view.thaumaturgy:
                        ui.label(section).classes("text-xs text-gray-500 mt-1")
                        for item in items:
                            ui.label(item).classes("text-sm")

        # --- charms / spells ---------------------------------------------- #
        # The charm holdings are grouped by subsystem — Charms / Arcanoi (Ghost) /
        # Gifts (Lunar) / Ox-Body Technique — so each gets its own headed panel,
        # mirroring the picker's tabs. An empty Spells panel would sit there taking
        # half the band to say "—", so it is dropped entirely when there are no spells.
        _heading("Charms & Sorcery" if (view.spells or view.elemental_powers) else "Charms")
        with ui.row().classes("w-full gap-2 items-start no-wrap"):
            for section_name, section_rows in view.charm_sections:
                with _panel().classes("flex-1"):
                    ui.label(f"{section_name} ({len(section_rows)})").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                    if not section_rows:
                        ui.label("—").classes("text-sm text-gray-400")
                    for c in section_rows:
                        with ui.column().classes("w-full gap-0"):
                            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                                ui.label(c.name).classes("text-sm flex-1 truncate")
                                _content_mark(c)
                                ui.label(c.category).classes("text-xs text-gray-500")
                                ui.label(c.duration).classes("text-xs text-gray-500 w-24 text-right")
                                ui.label(c.cost).classes("text-xs font-mono text-gray-600 w-20 text-right")
                            if c.description:
                                ui.label(c.description).classes("text-xs text-gray-600 mb-1")
            if view.spells:
                with _panel().classes("flex-1"):
                    ui.label(f"Spells ({len(view.spells)})").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                    for s in view.spells:
                        with ui.column().classes("w-full gap-0"):
                            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                                ui.label(s.name).classes("text-sm flex-1 truncate")
                                _content_mark(s)
                                ui.label(s.circle).classes("text-xs text-gray-500")
                                ui.label(s.cost).classes("text-xs font-mono text-gray-600 w-20 text-right")
                            if s.description:
                                ui.label(s.description).classes("text-xs text-gray-600 mb-1")

        # --- Dragon-King Paths (PG pp.175-191) ------------------------------ #
        # A rated-track subsystem with its own pool, shown only for a character who
        # owns Paths. Each Path lists the powers its rating grants, with the ★/✚
        # favour markers (breed Paths vs the player's choice).
        if view.paths:
            _heading("Paths of Prehuman Mastery")
            with ui.row().classes("w-full gap-2 items-start no-wrap"):
                for p in view.paths:
                    with _panel().classes("flex-1"):
                        ui.label(f"{p.favored}{p.name} · {p.element_label} · {p.rating} dots").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                        for power in p.powers:
                            with ui.column().classes("w-full gap-0 min-w-0"):
                                ui.label(f"• {power.name} — {power.duration} · {power.cost}").classes("text-xs font-semibold")
                                if power.text:
                                    ui.label(power.text).classes(
                                        "text-xs text-gray-600 mb-1").style(
                                        "overflow-wrap:anywhere; word-break:break-word")

        # --- Combos ---------------------------------------------------------- #
        # Each Combo lists its member Charm names — a Dragon-King's Path powers
        # included, since the members resolve through ruleset.charms' virtual rows.
        if view.combos:
            _heading("Combos")
            with ui.row().classes("w-full gap-2 items-start no-wrap"):
                for cname, members, cost in view.combos:
                    with _panel().classes("flex-1"):
                        ui.label(f"{cname} · {cost} Charm{'s' if cost != 1 else ''}").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                        for m in members:
                            ui.label(f"· {m}").classes("text-xs text-gray-600")

        # --- bottom band: gear | willpower+health | virtues+essence ------- #
        with ui.row().classes("w-full gap-2 items-stretch no-wrap"):
            # left: equipment + anima + virtue flaw
            with _panel().classes("flex-1"):
                ui.label("Equipment").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                for w in view.weapons:
                    art = f" · A{w.artifact_rating}/{w.attunement}m" if w.artifact_rating else ""
                    rng = f" · rng {w.range}" if w.range else ""
                    mat = f" · {w.material}" if w.material else ""
                    ui.label(f"⚔ {w.name}  Spd{w.speed:+d} Acc{w.accuracy:+d} "
                             f"Dmg{w.damage:+d}{w.damage_type} Def{w.defense:+d}{rng}{art}{mat}").classes("text-xs")
                for a in view.armor:
                    art = f" · A{a.artifact_rating}/{a.attunement}m" if a.artifact_rating else ""
                    mat = f" · {a.material}" if a.material else ""
                    ui.label(f"🛡 {a.name}  Soak {a.soak_lethal}L/{a.soak_bashing}B "
                             f"Mob{a.mobility_penalty:+d} Ftg{a.fatigue}{art}{mat}").classes("text-xs")
                if not view.weapons and not view.armor:
                    ui.label("—").classes("text-sm text-gray-400")
                if view.totem or view.animal_forms:
                    ui.separator()
                    ui.label("Forms").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                    if view.totem:
                        ui.label(f"Totem: {view.totem}").classes("text-xs")
                    for animal, note in view.animal_forms:
                        ui.label(f"{animal}{' · ' + note if note else ''}").classes("text-xs")
                if view.anima:
                    ui.separator()
                    ui.label("Anima").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                    ui.label(view.anima).classes("text-xs")
                if view.virtue_flaw:
                    ui.separator()
                    ui.label("Virtue Flaw").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                    ui.label(view.virtue_flaw).classes("text-xs")

            # center: willpower + health + soak
            with _panel().classes("flex-1"):
                ui.label("Willpower").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                ui.label(_dots(view.willpower, 10)).classes("text-sm font-mono")
                ui.separator()
                ui.label("Soak").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                s = view.soak
                ui.label(f"Bashing {s.bashing}  ·  Lethal {s.lethal}  ·  Aggravated {s.aggravated}").classes("text-sm")
                ui.label(f"(Stamina {s.natural_bashing}/{s.natural_lethal} + armor {s.armor_bashing}/{s.armor_lethal})").classes("text-xs text-gray-500")
                ui.separator()
                ui.label("Health").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                ui.label("  ".join(view.health)).classes("text-sm font-mono")

            # right: virtues + essence + experience
            with _panel().classes("flex-1"):
                ui.label("Virtues").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                for r in view.virtues:
                    _named_value(r.label, r.value)
                ui.separator()
                ui.label("Essence").classes("text-xs font-semibold").style(f"color:{pal.accent}")
                _named_value("Rating", view.essence_rating)
                ui.label(view.essence_pool_label()).classes("text-sm")
                ui.separator()
                ui.label(f"Experience: {view.experience}").classes("text-xs")

        # --- experience ledger (history; the live controls are on Edit) ----- #
        # Rendered from the SheetView alone — no ruleset, no character, no callbacks —
        # which is what keeps `render_sheet` usable by the GM party screen and the
        # render tests. Adjust XP and Undo live on the Edit tab, next to the buying.
        if view.chargen_locked:
            _heading(f"Experience — {view.xp_available} available")
            with _panel():
                ui.label(f"earned {view.xp_earned} · spent {view.xp_spent}").classes(
                    "text-xs text-gray-500")
                if not view.xp_log:
                    ui.label("No XP spent yet.").classes("text-sm text-gray-400")
                for r in view.xp_log:
                    with ui.row().classes("w-full justify-between no-wrap items-baseline"):
                        ui.label(r.label).classes("text-sm")
                        ui.label(f"{r.cost} XP").classes("text-sm text-gray-600")

        # --- validation --------------------------------------------------- #
        errors = [i for i in view.issues if i.severity == "error"]
        _heading(f"Validation — {'OK' if not errors else str(len(errors)) + ' error(s)'}")
        with _panel():
            for issue in view.issues:
                color = {"error": "text-red-600", "warning": "text-amber-600"}.get(issue.severity, "text-gray-500")
                ui.label(f"[{issue.severity}] {issue.message}").classes(f"text-sm {color}")


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character]:
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e read-only character sheet")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true", help="open a browser automatically")
    args = parser.parse_args()

    ruleset, character = load(args.character)
    view = viewmod.build_sheet_view(ruleset, character)

    @ui.page("/")
    def index() -> None:
        render_sheet(view)

    ui.run(title=f"Exalted 1e — {view.name}", reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
