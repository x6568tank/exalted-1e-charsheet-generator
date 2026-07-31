"""
ui/advantages.py — Backgrounds and Merits & Flaws, on both sides of the lock.

These two were the only traits filed under the Edit⇄XP split that do not BEHAVE like
it. Edit⇄XP is one slot seen from two sides: chargen builds a baseline, XP spends
against it. Backgrounds and M&F are not that — they are one list edited under two
budget regimes, which is the Charms/Combos shape, so they live on a tab that is on the
bar throughout and switches mode at the lock.

Filing them under the wrong shape is what forced each of them to be written twice, and
the duplication shipped real bugs before it was removed: the XP tab filtered its Merit
dropdown by splat and the editor did not, so a Solar could pick Chimera at chargen and
only be told afterwards. Two near-identical Background panels drifted the same way.
**This module is one implementation of each. Do not grow a second one anywhere else.**

Mode comes from the character, never from the caller (`_in_play`, reading
`chargen_locked`), exactly as the Charms picker does:

* **pre-lock** — Backgrounds against the chargen dot budget with the pre-bonus cap;
  M&F against bonus points, a Merit charging and a Flaw granting.
* **post-lock** — Backgrounds free and story-driven with no log row; M&F through
  `advancement.buy_merit` / `gain_flaw` / `drop_merit`, XP-priced and debt-aware.

Zero game logic: budgets, caps, prices and legality all come from the engine, and no
Merit id is named here (decision 0011).

Run:
    python -m exalted_builder.ui.advantages [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..engine import advancement, merits as meritsmod, validate
from ..models.character import BackgroundEntry, Character, MeritFlawPurchase
from ..models.rules import RuleSet
from . import theme
from . import view as viewmod
from .editor import DescribedSelect, _opts_with, dot_track, panel_card

_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"
_EXAMPLE = _PKG.parent / "examples" / "ashes-of-dawn.character.json"


def _tier_label(t: str) -> str:
    """A tier key is either a bare point value ("4") or a semantic name
    ("favored_aptitude"). Render both readably without the caller caring."""
    return t.replace("_", " + ").title() if not t.isdigit() else t.title()


def build_advantages(ruleset: RuleSet, character: Character, save_path: Path,
                     *, with_header: bool = True) -> None:
    """Render the Advantages tab — Backgrounds and Merits & Flaws, in whichever regime
    the character's lock state calls for."""
    rs = ruleset
    pal = theme.palette(character.exalt_type)

    def _in_play() -> bool:
        return character.chargen_locked

    # ---- live readout ----------------------------------------------------- #
    # Ruling 1 of the plan, and the load-bearing risk of the whole refactor: these
    # traits draw on the SHARED chargen bonus-point pool alongside everything left on
    # the Edit tab. Without a readout here a player spends 6 BP on Merits and the total
    # that moved is displayed on a tab they cannot see. The Charms picker carries its
    # own for exactly this reason; this is the same pattern.
    @ui.refreshable
    def readout() -> None:
        if _in_play():
            # Post-lock the relevant budget is experience, not bonus points. Read-only:
            # the ledger and undo live on the XP tab, wherever a purchase was made.
            available = advancement.xp_available(character)
            with ui.row().classes("w-full items-baseline gap-3"):
                ui.label(f"{available}").classes("text-2xl font-bold").style(
                    f"color:{'#15803d' if available >= 0 else '#b91c1c'}")
                ui.label("XP available").classes("text-xs text-gray-600")
            debt = advancement.xp_debt(character)
            if debt:
                ui.label(f"⚠ {debt} XP owed — all further experience clears this first."
                         ).classes("text-xs font-semibold text-amber-700")
            ui.label("The ledger and undo are on the XP tab."
                     ).classes("text-xs text-gray-500")
            return
        view = viewmod.build_sheet_view(rs, character)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        ui.label(bp).classes("text-sm font-semibold").style(f"color:{pal.accent}")
        ui.separator()
        # Only the issues this tab can do anything about — the Edit tab reports the
        # rest, and repeating all of them here would make both readouts noise.
        mine = [i for i in view.issues
                if i.code != "bonus-points"
                and ("background" in i.code or "merit" in i.code or "flaw" in i.code)]
        if not mine:
            ui.label("No Background or Merit issues.").classes("text-xs text-gray-500")
        for issue in mine:
            color = {"error": "text-red-600",
                     "warning": "text-amber-600"}.get(issue.severity, "text-gray-500")
            ui.label(f"• {issue.message}").classes(f"text-xs {color}")

    @ui.refreshable
    def bp_log() -> None:
        """The per-domain bonus-point breakdown, so the number in the readout can be
        traced to what moved it. Chargen only — post-lock there are no bonus points."""
        if _in_play():
            return
        bd = validate.bonus_point_breakdown(rs, character)
        ui.label("Bonus Points").classes(
            "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
        color = "#b91c1c" if bd.over_budget else "#15803d"
        ui.label(f"{bd.total} / {bd.available} spent").classes(
            "text-sm font-semibold").style(f"color:{color}")
        ui.separator()
        for line in bd.lines:
            muted = "" if line.points else "text-gray-400"
            with ui.row().classes("w-full justify-between no-wrap items-baseline"):
                ui.label(line.domain).classes(f"text-xs {muted}")
                ui.label(str(line.points)).classes(f"text-xs {muted}")

    def changed() -> None:
        readout.refresh()
        bp_log.refresh()

    def refresh_all() -> None:
        body.refresh()
        changed()

    dots = dot_track(pal, changed)

    def _do(action) -> None:
        try:
            action()
        except advancement.AdvancementError as ex:
            ui.notify(str(ex), type="warning")
            return
        refresh_all()

    # ---- Backgrounds: shared row, two regimes ----------------------------- #
    def add_bg() -> None:
        character.backgrounds.append(BackgroundEntry(name="", rating=1))
        refresh_all()

    def remove_bg(idx: int) -> None:
        del character.backgrounds[idx]
        refresh_all()

    def _background_rows(bg_cap) -> None:
        """The Background list itself — identical in both regimes but for the rating
        control, which is `bg_cap`'s business. This body is the whole reason the tab
        exists: it used to be two functions that differed only in their header."""
        bg_catalog = rs.backgrounds_for(character.exalt_type)
        bg_names = [b.name for b in bg_catalog]
        bg_descriptions = {b.name: b.description for b in bg_catalog}
        for idx, bg in enumerate(character.backgrounds):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                (DescribedSelect(_opts_with(bg_names, bg.name),
                                 descriptions=bg_descriptions,
                                 value=bg.name or None, label="Background",
                                 with_input=True, new_value_mode="add-unique",
                                 on_change=lambda e, bg=bg: setattr(bg, "name", e.value or ""))
                 .props("dense").classes("flex-1"))
                ui.input(value=bg.note, placeholder="note",
                         on_change=lambda e, bg=bg: setattr(bg, "note", e.value)
                         ).props("dense").classes("flex-1")
                bg_cap(bg)
                ui.button(icon="delete",
                          on_click=lambda e=None, idx=idx: remove_bg(idx)
                          ).props("flat dense round")
        ui.button("Add background", icon="add", on_click=add_bg).props("flat dense")

    def _chargen_backgrounds(b, mf_effects) -> None:
        def cap_for(name: str) -> int:
            """The highest rating this Background may be clicked to. Ordinarily 5; a
            held Flaw may lower it (Innocuous caps Allies/Contacts/Mentor at 2) or close
            it outright (Followers, Cult, Command). Asked of engine.merits, so no Merit
            id is named here."""
            key = (name or "").strip().lower()
            if key in mf_effects.barred_backgrounds:
                return 0
            return min(meritsmod.DOT_MAX,
                       mf_effects.background_caps.get(key, meritsmod.DOT_MAX))

        with panel_card(pal, f"Backgrounds ({b.background_dots} dots; "
                             f"≤{b.background_cap_pre_bp} pre-bonus)"):
            # A Flaw may cap or close a Background (Innocuous' veiled tier). Same
            # treatment the Attribute rows give a Merit cap: a ceiling the player can
            # still click past is not a ceiling.
            _background_rows(lambda bg: dots(lambda bg=bg: bg.rating,
                                             lambda v, bg=bg: setattr(bg, "rating", v),
                                             0, cap_for(bg.name)))

    def _play_backgrounds() -> None:
        # Backgrounds change in play through the story (a Manse falls, an Ally is made),
        # not by spending XP. Editable current value, no XP cost, no log entry — like
        # equipment, not like a dotted trait.
        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            with ui.row().classes("w-full items-baseline gap-2"):
                ui.label("Backgrounds").classes(
                    "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                ui.label("free — no XP").classes("text-xs text-gray-500")
            _background_rows(lambda bg: ui.number(
                value=bg.rating, min=0, max=5, format="%d",
                on_change=lambda e, bg=bg: setattr(bg, "rating", int(e.value or 0))
            ).props("dense").classes("w-16"))

    # ---- Merits & Flaws: chargen ------------------------------------------ #
    def set_merit(mp, merit_id: str) -> None:
        # Changing the entry clears every value that belonged to the old one — side,
        # tier, points, arena and detail all mean something entry-specific, and a
        # carried-over value silently mis-prices. The tier resets to the new entry's
        # first AVAILABLE option rather than to blank, so a row is never left on a dead
        # tier or on one this splat is barred from.
        mp.merit_id = merit_id or ""
        mp.tier = _default_tier(rs.merits_flaws.get(mp.merit_id))
        mp.taken_as, mp.points, mp.detail, mp.arena = "", 0, "", ""
        mp.stipulations = 0
        refresh_all()

    def add_merit() -> None:
        # The cheapest available entry, so a fresh row is always a legal selection — it
        # must come from the same filtered set the dropdown offers, or the row opens on
        # an entry that is not in its own options.
        first = min((m for m in rs.merits_flaws.values()
                     if validate.merit_available_to(m, character.exalt_type,
                                                    character.caste)),
                    key=lambda m: (m.kind != "merit", m.cost, m.name), default=None)
        if first is None:
            return
        character.merits_flaws.append(
            MeritFlawPurchase(merit_id=first.id, tier=_default_tier(first)))
        refresh_all()

    def _default_tier(definition) -> str:
        """The option a fresh row should open on: the first this SPLAT may choose, not
        merely the first authored. Prodigy's menu leads with `favored`, which four
        splats are barred from — so a Solar's new row opened on an illegal tier and
        flagged itself immediately (reported 2026-07-31)."""
        if definition is None or not definition.cost_options:
            return ""
        return next(iter(validate.merit_tiers_available(
            definition, character.exalt_type, character.caste)), "")

    def remove_merit(idx: int) -> None:
        del character.merits_flaws[idx]
        refresh_all()

    def _merit_label(m) -> str:
        # The sign so a Flaw reads as a grant, not a charge; a variable-cost entry
        # shows its range instead of a single number.
        if m.cost_options:
            lo, hi = min(m.cost_options.values()), max(m.cost_options.values())
            price = f"{lo}-{hi}"
        else:
            price = str(m.cost)
        sign = "−" if m.kind == "merit" else "+"
        return f"{m.name}  ({sign}{price} {m.category or m.kind})"

    def _chargen_merits(b) -> None:
        # A MERIT costs bonus points; a FLAW grants them, which is why the header
        # reports the grant separately rather than as a negative.
        #
        # Filtered to what this character may actually take: offering a Solar Chimera
        # only to answer with a validation error is a worse experience than not offering
        # it. Held rows survive the filter via the `row_opts.setdefault` guard, so an
        # entry that became illegal (a caste change) stays visible and flagged rather
        # than vanishing.
        merit_opts = {m.id: _merit_label(m) for m in sorted(
            rs.merits_flaws.values(), key=lambda m: (m.kind != "merit", m.name))
            if validate.merit_available_to(m, character.exalt_type, character.caste,
                                           starting_essence=b.essence_start)}
        eff = meritsmod.merits_and_flaws_calc(rs, character)
        spent = validate.merit_bonus_point_cost(rs, character)
        grant = eff.bonus_point_grant
        header = f"Merits & Flaws (−{spent} BP"
        header += f", +{grant} from Flaws)" if grant else ")"
        with panel_card(pal, header):
            # "Characters with more than 10 points of Flaws receive no bonus points for
            # the excess" (PG p.17). Say so when it bites: the grant in the header is
            # the CAPPED number, and a player who took 13 points of Flaws and sees "+10"
            # has no way to tell the cap from a bug in our arithmetic.
            if eff.flaw_points_raw > eff.bonus_point_grant:
                ui.label(f"⚠ {eff.flaw_points_raw} points of Flaws taken, "
                         f"{eff.bonus_point_grant} granted — the excess "
                         f"{eff.flaw_points_raw - eff.bonus_point_grant} is lost to the "
                         f"{meritsmod.FLAW_POINT_CAP}-point cap (p.17). The Flaws still "
                         f"apply.").classes("text-xs font-semibold text-amber-700")
            for idx, mp in enumerate(character.merits_flaws):
                definition = rs.merits_flaws.get(mp.merit_id)
                # flex-wrap, NOT no-wrap: the merge of the two old panels put more
                # controls on this row than either had alone — entry, side, tier, arena,
                # stipulations and detail can all appear at once — and a no-wrap row
                # crushes its later children to slivers rather than wrapping them. That
                # is how a sheet panel went invisible on 2026-07-31.
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    # An off-catalogue id (a save opened without its data) stays
                    # selectable rather than 500ing the select — the same guard the
                    # caste and college dropdowns use.
                    row_opts = dict(merit_opts)
                    row_opts.setdefault(mp.merit_id, mp.merit_id)
                    ui.select(row_opts, value=mp.merit_id, label="Merit / Flaw",
                              on_change=lambda e, mp=mp: set_merit(mp, e.value)
                              ).classes("flex-1 min-w-64").props("dense")
                    # Which side a two-sided entry was taken on. No blank option: the
                    # value decides whether this charges bonus points or grants them, so
                    # it must be a deliberate pick. An unrecorded choice shows empty and
                    # validate flags it.
                    if definition is not None and definition.kind == "either":
                        ui.select({"merit": "as Merit", "flaw": "as Flaw"},
                                  value=mp.taken_as or None, label="Taken",
                                  on_change=lambda e, mp=mp: (
                                      setattr(mp, "taken_as", e.value or ""),
                                      refresh_all())
                                  ).classes("w-32").props("dense")
                    if definition is not None and definition.cost_options:
                        # Only the options this splat may actually choose, and priced
                        # from the same table the pricer reads — Lucky is 1-5 but 1-3
                        # for a Sidereal. A tier already recorded stays selectable.
                        opts = validate.merit_cost_options(
                            definition, character.exalt_type, character.caste)
                        tiers = validate.merit_tiers_available(
                            definition, character.exalt_type, character.caste)
                        tier_opts = {t: f"{_tier_label(t)} ({v})"
                                     for t, v in opts.items() if t in tiers}
                        if mp.tier:
                            tier_opts.setdefault(
                                mp.tier,
                                f"{_tier_label(mp.tier)} ({opts.get(mp.tier, '?')})")
                        ui.select(tier_opts, value=mp.tier or None,
                                  label=("Oath" if meritsmod.uses_arena(definition)
                                         else "Buying"),
                                  on_change=lambda e, mp=mp: (
                                      setattr(mp, "tier", e.value or ""), refresh_all())
                                  ).classes("w-40").props("dense")
                        # Arena drives the same-arena stacking reduction (p.122); free
                        # text, because the page's list is examples, not a set. Only for
                        # the entry that HAS that rule.
                        if meritsmod.uses_arena(definition):
                            ui.input(value=mp.arena, placeholder="arena (combat, food…)",
                                     on_change=lambda e, mp=mp: (
                                         setattr(mp, "arena", e.value), refresh_all())
                                     ).classes("w-40").props("dense")
                    # A variable-cost entry's value lives on the PURCHASE — the page
                    # leaves it to the table. Without this field it stayed 0, which made
                    # all 11 of them inert at chargen: no bonus points, no effect.
                    elif definition is not None and definition.variable_cost:
                        rate = meritsmod.forfeit_rate(definition)
                        if rate:
                            # Collect DOTS and multiply rather than collecting points and
                            # flooring back: the dots are what the player chooses ("three
                            # points for every Physical Attribute dot"), and entering
                            # points directly can silently lose a remainder.
                            ui.number(value=mp.points // rate, min=0, max=20, format="%d",
                                      label=f"{meritsmod.forfeit_trait_label(definition)} dots",
                                      on_change=lambda e, mp=mp, r=rate: (
                                          setattr(mp, "points", int(e.value or 0) * r),
                                          refresh_all())
                                      ).classes("w-32").props("dense")
                        else:
                            ui.number(value=mp.points, min=0, max=20, format="%d",
                                      label="Points",
                                      on_change=lambda e, mp=mp: (
                                          setattr(mp, "points", int(e.value or 0)),
                                          refresh_all())
                                      ).classes("w-28").props("dense")
                    # Stipulations are dots, so they need a number rather than a note —
                    # "an extra dot … for every major stipulation applied to the
                    # Inheritance, up a maximum of three" (p.24).
                    if definition is not None and definition.takes_stipulations:
                        ui.number(value=mp.stipulations, label="Stipulations",
                                  min=0, max=3, precision=0,
                                  on_change=lambda e, mp=mp: (
                                      setattr(mp, "stipulations", max(0, int(e.value or 0))),
                                      refresh_all())
                                  ).classes("w-32").props("dense")
                    # A structured detail is a CLOSED set, not free text: which Attribute
                    # category a forfeit comes from, which Attribute gets Legendary
                    # Attribute's raised ceiling. Both were free-text and both failed
                    # silently — a typo became a fourth category, and an empty box left
                    # Legendary Attribute inert with no complaint.
                    choices = (meritsmod.detail_choices(definition)
                               if definition is not None else ())
                    if choices:
                        # `ui.select` RAISES at build time when its value is not among
                        # its options, and the raise takes the whole tab with it. A
                        # stored detail can legitimately be off-list: validate compares
                        # `detail.strip().title()`, so "strength" passes validation
                        # while never matching the title-cased option. Normalise the
                        # same way validate does, then keep anything still unmatched as
                        # its own option rather than crashing on it.
                        detail_opts = {c: c for c in choices}
                        current = mp.detail.strip().title() if mp.detail else ""
                        if mp.detail and current not in detail_opts:
                            current = mp.detail
                            detail_opts.setdefault(current, f"{current}  (not a choice)")
                        ui.select(detail_opts, value=current or None,
                                  label="Applies to",
                                  on_change=lambda e, mp=mp: (
                                      setattr(mp, "detail", e.value or ""), refresh_all())
                                  ).classes("w-40").props("dense")
                    else:
                        ui.input(value=mp.detail,
                                 placeholder=(definition.repeatable_by if definition
                                              and definition.repeatable_by else "note"),
                                 on_change=lambda e, mp=mp: (setattr(mp, "detail", e.value),
                                                             changed())
                                 ).classes("flex-1").props("dense")
                    ui.button(icon="delete",
                              on_click=lambda e=None, idx=idx: remove_merit(idx)
                              ).props("flat dense round")
                if definition is not None:
                    _merit_rules_text(definition)
            ui.button("Add merit / flaw", icon="add", on_click=add_merit).props("flat dense")
            # Say which held Merits this build treats as narrative, rather than letting a
            # player wonder why nothing changed.
            if eff.narrative_only:
                names = ", ".join(sorted(
                    rs.merits_flaws[m].name for m in eff.narrative_only
                    if m in rs.merits_flaws))
                if names:
                    ui.label(f"Narrative only in this build: {names}."
                             ).classes("text-xs italic opacity-70")

    def _merit_rules_text(definition) -> None:
        """The printed cost line, restrictions, gates and rules text under a row. The
        cost line always shows: a few qualifiers cannot be priced by the engine (a
        per-caste rate, a relative one), so the ST must see what the book actually says."""
        if definition.cost_note:
            ui.label(definition.cost_note).classes("text-xs font-mono opacity-60 pl-1")
        if definition.exalt_types:
            ui.label("Restricted to: " + ", ".join(definition.exalt_types)
                     ).classes("text-xs italic opacity-70 pl-1")
        # What the entry requires, so a player sees the gate BEFORE the issues panel
        # tells them they failed it. The tier-keyed groups are shown whole — which tier
        # needs what is the point of Innocuous, and hiding the other tier's line would
        # hide it.
        wants = [" or ".join(f"{r.trait} {r.rating}" for r in group)
                 for groups in definition.trait_prerequisites.values()
                 for group in groups]
        if definition.max_purchases_from_trait:
            wants.append(f"at most {definition.max_purchases_from_trait} purchases")
        if definition.prerequisite_note:
            wants.append(definition.prerequisite_note)
        if wants:
            ui.label("Requires: " + "; ".join(wants)
                     ).classes("text-xs italic opacity-70 pl-1")
        if definition.description:
            ui.label(definition.description).classes("text-xs opacity-70 pl-1")

    # ---- Merits & Flaws: in play ------------------------------------------ #
    gain_state: dict = {"id": "", "tier": "", "points": 0, "taken_as": "", "detail": ""}
    drop_state: dict = {"idx": ""}

    def _mf_changed(**kw) -> None:
        """Update the pending selection and re-render its preview, without touching the
        character — nothing is bought until Gain is pressed."""
        gain_state.update(kw)
        refresh = gain_state.get("refresh")
        if refresh is not None:
            refresh()

    def _gain_mf() -> None:
        """Gain a Merit or Flaw in play. Which side of the transaction it is depends on
        the ENTRY, not on the button — a Flaw pays the character."""
        mid = gain_state.get("id") or ""
        definition = rs.merits_flaws.get(mid)
        if definition is None:
            ui.notify("Pick a Merit or Flaw first.", type="warning")
            return
        side = definition.kind
        if side == "either":
            side = gain_state.get("taken_as", "")
            if side not in ("merit", "flaw"):
                ui.notify(f"{definition.name} is a Merit OR a Flaw — pick which side.",
                          type="warning")
                return
        kw = dict(tier=gain_state.get("tier", ""),
                  taken_as=gain_state.get("taken_as", ""),
                  points=gain_state.get("points", 0),
                  detail=gain_state.get("detail", ""))
        if side == "flaw":
            _do(lambda: advancement.gain_flaw(rs, character, mid, **kw))
        else:
            _do(lambda: advancement.buy_merit(rs, character, mid, **kw))

    def _drop_mf() -> None:
        idx = drop_state.get("idx")
        if idx == "" or idx is None:
            ui.notify("Pick a held Merit or Flaw first.", type="warning")
            return
        _do(lambda: advancement.drop_merit(rs, character, int(idx)))

    def _play_merits() -> None:
        # Only meaningful when the table uses the experience method; under the other two,
        # changes "do not cost or reward" and belong to chargen, so the card says so
        # rather than offering buttons that all read 0 XP.
        method = advancement.mf_change_method(character)
        eff = meritsmod.merits_and_flaws_calc(rs, character)
        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            ui.label("Merits & Flaws").classes(
                "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
            if method != "experience":
                ui.label(f"This table uses the '{method}' method (Player's Guide p.17), "
                         f"under which gaining or losing a Merit costs and rewards "
                         f"nothing. Unlock chargen to edit them.").classes(
                    "text-xs text-gray-600")
                return
            ui.label("Gaining a Merit or losing a Flaw costs twice its point value; "
                     "losing a Merit or gaining a Flaw pays the same. An unaffordable "
                     "change runs a debt against future XP."
                     ).classes("text-xs text-gray-600")
            # The p.17 cap applies in play too, and here it truncates the XP AWARD rather
            # than a bonus-point grant — a Flaw taken past the ceiling pays for its legal
            # part only. Silently paying less than the table expects is the worse
            # failure, so the remaining room is stated before anything is bought.
            room = max(0, meritsmod.FLAW_POINT_CAP - eff.flaw_points_raw)
            if room:
                ui.label(f"{eff.flaw_points_raw} of {meritsmod.FLAW_POINT_CAP} points of "
                         f"Flaws taken — a new Flaw pays for at most {room} more."
                         ).classes("text-xs text-gray-600")
            else:
                ui.label(f"⚠ {eff.flaw_points_raw} points of Flaws taken — at the "
                         f"{meritsmod.FLAW_POINT_CAP}-point cap (p.17). A further Flaw "
                         f"still applies, but pays no XP."
                         ).classes("text-xs font-semibold text-amber-700")
            # --- gain ------------------------------------------------------ #
            opts = {m.id: f"{m.name} {m.cost_note or ''}".strip()
                    for m in sorted(rs.merits_flaws.values(), key=lambda m: m.name)
                    if validate.merit_available_to(
                        m, character.exalt_type, character.caste,
                        starting_essence=validate.effective_budgets(
                            rs, character).essence_start)}
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select(opts, label="Merit / Flaw", with_input=True,
                          on_change=lambda e: _mf_changed(
                              id=e.value or "", taken_as="", tier="", points=0, detail="")
                          ).classes("flex-1").props("dense")
                ui.button("Gain", on_click=_gain_mf).props(f"dense color={pal.button}")

            # What the selected entry actually IS — printed cost line, any splat
            # restriction, the price this character would pay, and the rules text. Buying
            # a Merit blind off a dropdown label is how you take a Flaw by accident.
            @ui.refreshable
            def mf_detail() -> None:
                definition = rs.merits_flaws.get(gain_state.get("id") or "")
                if definition is None:
                    ui.label("Select an entry to see its rules text."
                             ).classes("text-xs italic opacity-60")
                    return
                # For a two-sided entry the chosen side decides the direction of the
                # transaction, so it drives this banner too — an unchosen one says so
                # rather than implying the Merit branch.
                chosen = gain_state.get("taken_as", "")
                effective = chosen if definition.kind == "either" else definition.kind
                side = ("Flaw — GAINING this pays the character" if effective == "flaw"
                        else "Merit — gaining this costs XP" if effective == "merit"
                        else "Merit OR Flaw — choose a side before gaining it")
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.label(definition.name).classes("text-sm font-semibold")
                    ui.label(definition.cost_note).classes("text-xs font-mono opacity-60")
                ui.label(side).classes(
                    "text-xs font-semibold "
                    + ("text-emerald-700" if effective == "flaw"
                       else "text-amber-800" if effective == "merit" else "text-rose-700"))
                if definition.kind == "either":
                    # ui.select, not ui.toggle: a toggle's options cannot be driven from
                    # the UI tests, and this is the control the whole feature turns on.
                    ui.select({"merit": "as Merit", "flaw": "as Flaw"},
                              value=chosen or None, label="Take it",
                              on_change=lambda e: _mf_changed(taken_as=e.value or "")
                              ).classes("w-40").props("dense")
                # The value controls, entry-aware — the same set chargen offers. This was
                # ONE free-text box doing double duty (a tier key for a menu-priced entry,
                # a point value for a variable-cost one), which meant the two halves of
                # the app collected the same rules through very different widgets: the
                # shape that produced the splat-filter bug.
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    if definition.cost_options:
                        tier_opts = validate.merit_cost_options(
                            definition, character.exalt_type, character.caste)
                        tiers = validate.merit_tiers_available(
                            definition, character.exalt_type, character.caste)
                        ui.select({t: f"{_tier_label(t)} ({v})"
                                   for t, v in tier_opts.items() if t in tiers},
                                  value=gain_state.get("tier") or None,
                                  label=("Oath" if meritsmod.uses_arena(definition)
                                         else "Buying"),
                                  on_change=lambda e: _mf_changed(tier=e.value or "")
                                  ).classes("w-40").props("dense")
                    elif definition.variable_cost:
                        rate = meritsmod.forfeit_rate(definition)
                        if rate:
                            ui.number(value=gain_state.get("points", 0) // rate,
                                      min=0, max=20, format="%d",
                                      label=f"{meritsmod.forfeit_trait_label(definition)} dots",
                                      on_change=lambda e, r=rate: _mf_changed(
                                          points=int(e.value or 0) * r)
                                      ).classes("w-36").props("dense")
                        else:
                            ui.number(value=gain_state.get("points", 0), min=0, max=20,
                                      format="%d", label="Points",
                                      on_change=lambda e: _mf_changed(
                                          points=int(e.value or 0))
                                      ).classes("w-28").props("dense")
                    choices = meritsmod.detail_choices(definition)
                    if choices:
                        ui.select({c: c for c in choices},
                                  value=gain_state.get("detail") or None,
                                  label="Applies to",
                                  on_change=lambda e: _mf_changed(detail=e.value or "")
                                  ).classes("w-40").props("dense")
                price = validate.merit_points(
                    definition,
                    MeritFlawPurchase(merit_id=definition.id,
                                      tier=gain_state.get("tier", ""),
                                      points=gain_state.get("points", 0),
                                      taken_as=chosen,
                                      detail=gain_state.get("detail", "")),
                    character.exalt_type, character.caste)
                xp_cost = price * rs.xp_costs_for(
                    character.exalt_type).new_merit_bp_multiplier
                ui.label(f"At the selected tier: {price} points = {xp_cost} XP"
                         ).classes("text-xs opacity-70")
                _merit_rules_text(definition)

            mf_detail()
            gain_state["refresh"] = mf_detail.refresh
            # --- lose ------------------------------------------------------ #
            if character.merits_flaws:
                held = {str(i): (rs.merits_flaws[mp.merit_id].name
                                 if mp.merit_id in rs.merits_flaws else mp.merit_id)
                        + (f" ({mp.tier})" if mp.tier else "")
                        for i, mp in enumerate(character.merits_flaws)}
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.select(held, label="Held",
                              on_change=lambda e: drop_state.update(idx=e.value or "")
                              ).classes("flex-1").props("dense")
                    ui.button("Lose / buy off", on_click=_drop_mf).props("dense flat")
            if eff.granted_merits:
                names = ", ".join(sorted(
                    rs.merits_flaws[m].name for m in eff.granted_merits
                    if m in rs.merits_flaws))
                ui.label(f"Granted free by another Merit: {names}").classes(
                    "text-xs italic opacity-70")

    # ---- body ------------------------------------------------------------- #
    @ui.refreshable
    def body() -> None:
        if _in_play():
            _play_backgrounds()
            if rs.merits_flaws:
                _play_merits()
            return
        b = validate.effective_budgets(rs, character)
        mf_effects = meritsmod.merits_and_flaws_calc(rs, character)
        _chargen_backgrounds(b, mf_effects)
        # Shown only when the rule set ships any (decision 0011: the data file is
        # optional).
        if rs.merits_flaws:
            _chargen_merits(b)

    def save() -> None:
        persistence.save_character(character, save_path)
        ui.notify(f"Saved to {save_path}", type="positive")

    # ---- layout ----------------------------------------------------------- #
    if with_header:
        ui.add_head_html(pal.head_style())
    with ui.row().classes("w-full max-w-7xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            if with_header:
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Advantages").classes("text-xl font-bold")
                    ui.button("Save", icon="save", on_click=save).props(f"color={pal.button}")
            body()
        with ui.column().classes("w-80 gap-2 sticky top-4"):
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                ui.label("Advantages").classes(
                    "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                readout()
            if not _in_play():
                with ui.card().classes(f"w-full p-3 {pal.card}"):
                    bp_log()


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e Backgrounds / Merits & Flaws")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset, character, path = load(args.character)

    @ui.page("/")
    def index() -> None:
        build_advantages(ruleset, character, path)

    ui.run(title=f"Exalted 1e — advantages: {character.name or path.stem}",
           reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
