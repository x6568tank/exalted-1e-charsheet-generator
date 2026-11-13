"""
ui/advantages.py — Backgrounds and Merits & Flaws, on both sides of the lock.

Backgrounds and M&F are one list each, edited under two budget regimes. Thus they are
on a tab that is always shown and changes mode at the lock, as Charms and Combos.

⚠ **This module is the one implementation of each. Do not add a second one.** Two
copies drift (a splat filter on one and not on the other).

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

from nicegui import context, ui

from .. import persistence, rules_db
from ..engine import (advancement, artifacts as artifactsmod, costs as costsmod,
                      derive as derivemod, merits as meritsmod, validate)
from ..models.character import (Armor, ArtifactEntry, BackgroundEntry, Character,
                                FetterEntry, HearthstoneEntry, MeritFlawPurchase,
                                PassionEntry, Weapon)
from ..models.rules import RuleSet, VirtueName
from . import catalogue as cataloguemod
from . import theme
from . import view as viewmod
from .saving import SaveFn, save_to_path
from .editor import DescribedSelect, _opts_with, dot_track, panel_card

_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"
_EXAMPLE = _PKG.parent / "examples" / "ashes-of-dawn.character.json"


# Presentation shared with the native shell — one copy, in the presenter.
_tier_label = viewmod.merit_tier_label
_merit_label = viewmod.merit_option_label


def build_advantages(ruleset: RuleSet, character: Character, save_fn: SaveFn,
                     *, with_header: bool = True) -> None:
    """Render the Advantages tab — Backgrounds and Merits & Flaws, in whichever regime
    the character's lock state calls for."""
    rs = ruleset
    pal = theme.palette(character.exalt_type)

    def _in_play() -> bool:
        return character.chargen_locked

    # ---- live readout ----------------------------------------------------- #
    # These traits use the SHARED chargen bonus-point pool, thus this tab shows the
    # total too, as the Charms picker does.
    @ui.refreshable
    def readout() -> None:
        if _in_play():
            # Post-lock the relevant budget is experience, not bonus points. Read-only:
            # the ledger and undo live in the Edit tab's Experience card.
            available = advancement.xp_available(character)
            with ui.row().classes("w-full items-baseline gap-3"):
                ui.label(f"{available}").classes("text-2xl font-bold").style(
                    f"color:{'#15803d' if available >= 0 else '#b91c1c'}")
                ui.label("XP available").classes("text-xs text-gray-600")
            debt = advancement.xp_debt(character)
            if debt:
                ui.label(viewmod.xp_debt_note(debt)).classes("text-xs font-semibold text-amber-700")
            ui.label("The ledger and undo are in the Edit tab's Experience card."
                     ).classes("text-xs text-gray-500")
            return
        view = viewmod.build_sheet_view(rs, character)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        ui.label(bp).classes("text-sm font-semibold").style(f"color:{pal.accent}")
        ui.separator()
        # Only the issues that this tab can fix. Artifact budget issues are included:
        # the Artifact Background rating is edited here and they must update live.
        # ⚠ The Gear tab shows the same issues. Both read one issue list.
        mine = [i for i in view.issues
                if i.code != "bonus-points"
                and ("background" in i.code or "merit" in i.code or "flaw" in i.code
                     or "artifact" in i.code)]
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

    # The splat-filtered catalogue, keyed by lowercased name — the row's link back to
    # its printed rules. Built once per panel build rather than per row.
    _bg_types = {b.name.strip().lower(): b
                 for b in validate.background_catalogue_for(rs, character)}
    # A printed Hearthstone's level, so picking one records the rating the rule
    # measures rather than leaving the player to re-enter it.
    _stone_ratings = {s.name: s.rating
                      for s in artifactsmod.hearthstones(rs.artifact_catalog)}

    def _bg_type(bg):
        """Return the catalogue entry of a Background row, or None for free text.

        ⚠ Resolved through the SPLAT-FILTERED catalogue: the Manse variants share
        names, thus a global lookup by name can return a copy of a different splat."""
        return _bg_types.get(bg.name.strip().lower())

    def _grows_stones(bg) -> bool:
        """Return True if this row gets the Hearthstone picker. Asks the DATA, not the
        free-text name. A Demesne row grows none (human's ruling)."""
        return (not bg.is_demesne) and artifactsmod.grows_hearthstones(_bg_type(bg))

    def _open_hearthstones(bg) -> None:
        stones = artifactsmod.hearthstones(rs.artifact_catalog)
        allowance = artifactsmod.hearthstone_allowance(_bg_type(bg), bg.rating)
        held = artifactsmod.hearthstone_total(bg)
        # The dialog shows what each stone would COST against the row's remaining
        # allowance, so the player is not picking blind and then reading a validation
        # error. Reads the same `hearthstone_allowance` the validator does — a picker
        # that greys a stone the validator accepts (or the reverse) is worse than one
        # that greys nothing.
        remaining = max(0, allowance.combined_max - held) if allowance else 0
        rows = []
        for s in stones:
            over = s.rating > remaining or (allowance and allowance.individual_max
                                            and s.rating > allowance.individual_max)
            note = (" — exceeds this Manse's remaining Hearthstone levels"
                    if over else "")
            rows.append((s.name, s.name,
                         f"{s.rating_notes or ('•' * s.rating)} — {s.description}"
                         f"{note}",
                         s.description))

        def _pick(name) -> None:
            # Custom (name is None) adds a blank stone rather than doing nothing: a
            # Hearthstone is unique per Manse (S&S p.67) and the printed ten are
            # examples, so "my own stone" is the common case, not an edge one. It gets
            # a rating control like any other, because the rating is what the rule
            # measures.
            bg.hearthstones.append(HearthstoneEntry(
                name="" if name is None else name,
                rating=1 if name is None else _stone_ratings.get(name, 1)))
            refresh_all()

        cataloguemod.catalogue_dialog(pal, "Hearthstones", rows, _pick,
                                      icons={s.name: cataloguemod.icon_for(s.tags,
                                                                          "diamond")
                                             for s in stones},
                                      default_icon="diamond")

    def _render_hearthstones(bg):
        """The stones on one Manse row, and a running total against the allowance. The
        allowance differs by splat and rating, thus the screen shows it.

        Returns its sync function. The caller chains it onto the rating-change
        callback of the row (see `_sync` below)."""
        # Declared before `_sync_total` closes over it and CREATED after the stone
        # rows, so the running total prints beneath them. Late binding makes the order
        # legal; the first call is the one at the end of this function.
        total = None

        def _sync_total() -> None:
            """Repaint the running total IN PLACE.

            ⚠ Calculate the allowance HERE, on each call. Do not capture it at build:
            the Manse rating changes the denominator.

            ⚠ Never call `refresh_all()` from the rating control. A rebuilt input loses
            each keystroke after the first."""
            if total is None:
                return
            allowance = (None if bg.is_demesne
                         else artifactsmod.hearthstone_allowance(_bg_type(bg),
                                                                 bg.rating))
            if allowance is None:
                total.set_visibility(False)
                return
            total.set_visibility(True)
            held = artifactsmod.hearthstone_total(bg)
            over = held > allowance.combined_max
            total.set_text(
                f"Hearthstones: {held} / {allowance.combined_max} levels")
            total.classes(replace="text-xs pl-6 " + (
                "text-red-600 font-semibold" if over else "opacity-70"))

        for sidx, stone in enumerate(bg.hearthstones):
            with ui.row().classes("w-full items-center gap-2 no-wrap pl-6"):
                ui.icon("diamond").classes("text-xs opacity-60")
                ui.input(value=stone.name, placeholder="Hearthstone",
                         on_change=lambda e, s=stone: setattr(s, "name", e.value)
                         ).props("dense").classes("flex-1")
                ui.number(value=stone.rating, min=0, max=5, format="%d",
                          on_change=lambda e, s=stone: (
                              setattr(s, "rating", int(e.value or 0)), _sync_total())
                          ).props("dense").classes("w-16")
                # Removal DOES rebuild — a row has to disappear, and a click carries
                # no in-progress keystrokes to lose.
                ui.button(icon="close",
                          on_click=lambda e=None, bg=bg, sidx=sidx: (
                              bg.hearthstones.pop(sidx), refresh_all())
                          ).props("flat dense round")
        total = ui.label("").classes("text-xs pl-6").props(
            'data-testid="hearthstone-total"')
        _sync_total()
        return _sync_total

    # ⚠ Each reader of a Background rating MUST be driven from `_sync`, where a rating
    # change arrives (the Hearthstone denominator: see `row_sync` below). The
    # "buys N dot(s)" note links to the Gear tab, and `_sync` recalculates it.

    def _background_rows(bg_cap) -> None:
        """The Background list, the same in both regimes except the rating control
        (`bg_cap`). ONE body for both.

        ⚠ `bg_cap` is called with (bg, on_rating_change) and MUST call the callback
        when the rating changes: the rung label follows the rating, and the play
        regime does not rebuild the panel."""
        # The origin matters for `excluded_origins` (the ancient-only Savant): a
        # modern Dragon King must not see it, an ancient one must.
        bg_catalog = validate.background_catalogue_for(rs, character)
        bg_names = [b.name for b in bg_catalog]
        bg_descriptions = {b.name: b.description for b in bg_catalog}
        for idx, bg in enumerate(character.backgrounds):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                sel = (DescribedSelect(_opts_with(bg_names, bg.name),
                                       descriptions=bg_descriptions,
                                       value=bg.name or None, label="Background",
                                       with_input=True, new_value_mode="add-unique")
                       .props("dense").classes("flex-1"))
                ui.input(value=bg.note, placeholder="note",
                         on_change=lambda e, bg=bg: setattr(bg, "note", e.value)
                         ).props("dense").classes("flex-1")
                # Forward-declared so the rating control can call it; the closure is
                # rebound below, once `desc`/`rung` exist.
                row_sync: dict = {}
                bg_cap(bg, lambda rs_=row_sync: rs_.get("fn", lambda: None)())
                # A Manse row gets the Hearthstone catalogue. The stone level is the
                # MANSE level (core p.338). ⚠ A pick does NOT create an
                # `ArtifactEntry`: that would charge the p.131 Artifact budget.
                #
                # The Demesne toggle is on each Background that COULD grow stones, also
                # when set to Demesne: else the toggle hides itself. The picker is only
                # on rows that grow stones.
                if artifactsmod.grows_hearthstones(_bg_type(bg)):
                    ui.switch(value=bg.is_demesne,
                              on_change=lambda e, bg=bg: (
                                  setattr(bg, "is_demesne", bool(e.value)),
                                  refresh_all())
                              ).props("dense size=sm").tooltip(
                                  viewmod.DEMESNE_TOGGLE_LABEL
                              ).mark("demesne-toggle")
                if _grows_stones(bg):
                    ui.button(icon="diamond",
                              on_click=lambda e=None, bg=bg: _open_hearthstones(bg)
                              ).props("flat dense round").tooltip("Hearthstones"
                              ).mark("hearthstone-picker")
                ui.button(icon="delete",
                          on_click=lambda e=None, idx=idx: remove_bg(idx)
                          ).props("flat dense round")
            # The catalogue description under the row. The select of the row refreshes
            # it WITHOUT a panel rebuild: a rebuilt input loses keystrokes. `bg` and
            # `desc` are default-captured: else each sync binds to the LAST row. A
            # free-text name gets no description, and must never crash.
            # ⚠ `data-testid` tells this label from the M&F rules-text labels. Else
            # `should_see(description)` matches the dropdown tooltips.
            desc = ui.label("").classes("text-xs opacity-70 pl-1"
                                        ).props('data-testid="bg-desc"')
            # The printed rung for the rating this row actually holds — "•• Two
            # allies or one significant one". Its own label rather than appended to
            # `desc`, so the rating can change it without redrawing the description,
            # and so a `should_see` assertion can tell the two apart.
            rung = ui.label("").classes("text-xs opacity-70 pl-1 italic"
                                        ).props('data-testid="bg-rung"')

            def _sync(bg=bg, desc=desc, rung=rung) -> None:
                text = bg_descriptions.get(bg.name, "")
                desc.set_text(text)
                desc.set_visibility(bool(text))
                rung_text = viewmod.background_rung(bg_catalog, bg.name, bg.rating)
                # Where a splat's book separates what you BUY from what it is WORTH
                # (Mountain Folk Resources: dots + 2, max 3 dots), say so on the row.
                # A player who sees "Resources •••" and is offered a Resources ••••
                # item has no way to tell the offer from a bug. Same engine call the
                # affordability hint makes, so the row and the dialog cannot disagree.
                effective = validate.effective_background_rating(rs, character, bg.name)
                if effective != bg.rating:
                    note = f"effective {bg.name} {effective}"
                    rung_text = f"{rung_text}  ·  {note}" if rung_text else note
                # The link to the Gear tab, where the artifacts are. The row states
                # what the Background bought.
                if bg.name.strip().lower() == artifactsmod.ARTIFACT_BACKGROUND:
                    owned = len(artifactsmod.budgeted_items(character))
                    buys = f"buys {bg.rating} dot(s) of artifacts · {owned} owned"
                    rung_text = f"{rung_text}  ·  {buys}" if rung_text else buys
                rung.set_text(rung_text)
                rung.set_visibility(bool(rung_text))

            row_sync["fn"] = _sync
            sel.on_value_change(lambda e, bg=bg, sync=_sync: (
                setattr(bg, "name", e.value or ""), sync()))
            _sync()

            # The stones of this row, each with its rating (S&S p.67). Editable: the
            # printed stones are examples. Shown whenever any are held, also on a
            # Demesne or renamed row, thus a stranded stone can be deleted.
            if bg.hearthstones:
                stones_sync = _render_hearthstones(bg)
                # Rebind the rating hook to drive BOTH labels. `row_sync` is read
                # lazily by the rating control, so rebinding after the stones are
                # drawn is legal and keeps them below the rung. Without this the
                # denominator went stale: raising the Manse moved the rung text and
                # left "4 / 3" claiming the row was still over budget.
                row_sync["fn"] = lambda s=_sync, h=stones_sync: (s(), h())

        # The catalogue picker replaces the blind "Add background": browse the
        # splat-filtered catalogue, pick one, or choose Custom for a blank row.
        def _open_bg_catalogue() -> None:
            # The dialog is where a rating is CHOSEN: its "Full description" shows the
            # whole printed ladder. The summary stays the plain description. No
            # ladder: the description only.
            rows = []
            for b in sorted(bg_catalog, key=lambda b: b.name):
                ladder = viewmod.background_ladder(bg_catalog, b.name)
                # A blank line BETWEEN rungs, for comparison (human's ruling). The
                # dialog label shows the newlines only with `whitespace-pre-line` (see
                # ui/catalogue.py).
                full = b.description + (
                    "\n\n" + "\n\n".join(f"{dot}  {text}" for dot, text in ladder)
                    if ladder else "")
                rows.append((b.name, b.name, b.description, full))
            cataloguemod.catalogue_dialog(pal, "Backgrounds", rows, _pick_bg)

        def _pick_bg(name) -> None:
            if name is None:
                add_bg()
                return
            character.backgrounds.append(BackgroundEntry(name=name, rating=1))
            refresh_all()

        ui.button("Add background", icon="add", on_click=_open_bg_catalogue
                  ).props("flat dense")

    def _chargen_backgrounds(b, mf_effects) -> None:
        def cap_for(name: str) -> int:
            """Return the highest rating that a click can set. Usually 5. A held Flaw
            can lower or close it (engine.merits). A splat rule can cap or bar it
            (engine.validate). ⚠ The control must not offer more: a cap that a click
            can pass is not a ceiling."""
            key = (name or "").strip().lower()
            if key in mf_effects.barred_backgrounds:
                return 0
            data_cap = validate.background_rating_cap(b, character, name)
            merit_cap = mf_effects.background_caps.get(key)
            if merit_cap is None:
                return data_cap
            return min(data_cap, merit_cap)

        with panel_card(pal, f"Backgrounds ({validate.background_dots_budget(b, character)} dots; "
                             f"≤{b.background_cap_pre_bp} pre-bonus)"):
            # A Flaw may cap or close a Background (Innocuous' veiled tier). Same
            # treatment the Attribute rows give a Merit cap: a ceiling the player can
            # still click past is not a ceiling.
            _background_rows(lambda bg, synced: dots(
                lambda bg=bg: bg.rating,
                lambda v, bg=bg, synced=synced: (setattr(bg, "rating", v), synced()),
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
            # The ceiling comes from the engine, not a hardcoded 5 (game logic out of
            # the widget): only the `bind_post_lock` rules bind post-lock (Sidereal
            # Celestial Manse ≤3, MF Artifact ≤10), so a locked Unenlightened Mountain
            # Folk can be given Backing 4 by the story and a mortal granted an artifact.
            b = validate.effective_budgets(rs, character)
            _background_rows(lambda bg, synced: ui.number(
                value=bg.rating, min=0,
                max=validate.background_rating_cap(b, character, bg.name, post_lock=True),
                format="%d",
                on_change=lambda e, bg=bg, synced=synced: (
                    setattr(bg, "rating", int(e.value or 0)), synced())
            ).props("dense").classes("w-16").mark("bg-rating"))

    # ---- Artifacts: individually rated items ------------------------------- #
    # The artifacts are on the Gear tab (ui/gear.py). The Artifact Background row here
    # states what its dots buy and how many are owned.

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

    def _default_tier(definition) -> str:
        """The option a fresh row should open on — `view.default_merit_tier` bound to
        this character (both shells need the same splat-aware default)."""
        return viewmod.default_merit_tier(definition, character.exalt_type,
                                          character.caste)

    def remove_merit(idx: int) -> None:
        del character.merits_flaws[idx]
        refresh_all()

    # ---- Merits & Flaws: the filter bar ----------------------------------- #
    # One filter for both regimes.
    #
    # ⚠ The controls do NOT refresh the body: a `ui.input` fires per keystroke, and a
    # rebuilt input loses focus. The filter changes the live selects with
    # `set_options`.
    _MF_SIDES = {"": "All", "merit": "Merits", "flaw": "Flaws"}
    mf_filter: dict[str, str] = {"text": "", "kind": "", "category": ""}

    def _mf_categories() -> dict[str, str]:
        return {"": "All", **{c: c for c in sorted(
            {m.category for m in rs.merits_flaws.values() if m.category})}}

    def _mf_matches(m) -> bool:
        """Does this entry survive the filter bar? A two-sided entry answers to BOTH
        side filters — it is genuinely either, and hiding it from both is how a player
        loses Prodigy. Text matches name, category and rules text, so a search for
        "combat" or "essence" finds entries whose NAME says neither."""
        want = mf_filter["kind"]
        if want and m.kind not in (want, "either"):
            return False
        if mf_filter["category"] and m.category != mf_filter["category"]:
            return False
        text = mf_filter["text"].strip().lower()
        if text:
            hay = f"{m.name} {m.category or ''} {m.description or ''}".lower()
            if text not in hay:
                return False
        return True

    def _available_merits(essence_start: int | None = None) -> list:
        """Every entry this character may take, Merits before Flaws then by name. The
        splat/caste/Essence filter is the engine's, never restated here."""
        return [m for m in sorted(rs.merits_flaws.values(),
                                  key=lambda m: (m.kind != "merit", m.name))
                if validate.merit_available_to(m, character.exalt_type, character.caste,
                                               origin=character.origin,
                                               starting_essence=essence_start)]

    def _mf_filter_bar(apply_filter) -> None:
        def _set(**kw) -> None:
            mf_filter.update(kw)
            apply_filter()

        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            ui.input(value=mf_filter["text"], placeholder="search name or rules text…",
                     on_change=lambda e: _set(text=e.value or "")
                     ).props("dense clearable").classes("flex-1 min-w-48")
            ui.select(_MF_SIDES, value=mf_filter["kind"], label="Side",
                      on_change=lambda e: _set(kind=e.value or "")
                      ).props("dense").classes("w-32")
            ui.select(_mf_categories(), value=mf_filter["category"], label="Category",
                      on_change=lambda e: _set(category=e.value or "")
                      ).props("dense").classes("w-40")

    def _mf_count_label(shown: int, total: int) -> str:
        return (f"{total} available" if shown == total
                else f"{shown} of {total} shown — clear the filter to see the rest")

    def _chargen_merits(b) -> None:
        # A MERIT costs bonus points. A FLAW grants them: the header shows the grant
        # separately.
        #
        # Filtered to what the character can take. A held row stays through both
        # filters (`_row_opts`), thus an entry that became illegal stays visible and
        # flagged.
        available = _available_merits(b.essence_start)
        merit_opts = {m.id: _merit_label(m) for m in available}
        # (select, purchase) for every row on screen, so the filter bar can re-option
        # them in place without rebuilding — and so a row's own held entry survives a
        # filter that would otherwise exclude it.
        row_selects: list = []

        def _row_opts(mp) -> dict:
            """The options ONE row offers: the filtered set, plus whatever that row
            already holds. An off-catalogue id (a save opened without its data) stays
            selectable rather than 500ing the select — the same guard the caste and
            college dropdowns use — and so does an entry the filter excludes, because
            `ui.select` raises when its value is not among its options."""
            opts = {m.id: _merit_label(m) for m in available if _mf_matches(m)}
            if mp.merit_id:
                opts.setdefault(mp.merit_id,
                                merit_opts.get(mp.merit_id, mp.merit_id))
            return opts

        def _apply_filter() -> None:
            for sel, mp in row_selects:
                sel.set_options(_row_opts(mp), value=mp.merit_id)
            shown = sum(1 for m in available if _mf_matches(m))
            count.text = _mf_count_label(shown, len(available))

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
                ui.label(viewmod.flaw_excess_note(
                    eff.flaw_points_raw, eff.bonus_point_grant)).classes("text-xs font-semibold text-amber-700")
            _mf_filter_bar(_apply_filter)
            count = ui.label(_mf_count_label(
                sum(1 for m in available if _mf_matches(m)), len(available))
            ).classes("text-xs opacity-60")
            for idx, mp in enumerate(character.merits_flaws):
                definition = rs.merits_flaws.get(mp.merit_id)
                # A player-authored "Custom" row: a text input and NONE of the
                # definition controls, because `definition` is None.
                if mp.custom_name:
                    with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                        ui.input(value=mp.custom_name, label="Custom Merit / Flaw",
                                 on_change=lambda e, mp=mp: (
                                     setattr(mp, "custom_name", e.value), changed())
                                 ).classes("flex-1 min-w-64").props("dense")
                        ui.button(icon="delete",
                                  on_click=lambda e=None, idx=idx: remove_merit(idx)
                                  ).props("flat dense round")
                    continue
                # ⚠ flex-wrap, NOT no-wrap: this row can hold six controls, and a
                # no-wrap row crushes the later ones to nothing.
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    # An off-catalogue id (a save opened without its data) stays
                    # selectable rather than 500ing the select — the same guard the
                    # caste and college dropdowns use.
                    sel = ui.select(_row_opts(mp), value=mp.merit_id,
                                    label="Merit / Flaw", with_input=True,
                                    on_change=lambda e, mp=mp: set_merit(mp, e.value)
                                    ).classes("flex-1 min-w-64").props("dense")
                    row_selects.append((sel, mp))
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
                    # WHICH artifact a per-entry limit measures (Damaged Artifact). The
                    # condition is the catalogue's `per_entry` flag, never the entry's
                    # id — decision 0011 again. Without this control the Flaw's limit
                    # could never be satisfied and its soak effect never fired, which is
                    # the dead-field bug this build keeps re-finding.
                    if definition is not None and any(l.per_entry
                                                      for l in definition.points_limits):
                        items = artifactsmod.artifact_items(character)
                        art_opts = {i.key: f"{i.name} ({i.rating})" for i in items}
                        # A key that no longer resolves — the artifact was renamed or
                        # deleted — stays selectable and is labelled as broken rather
                        # than vanishing silently or crashing the select.
                        if mp.artifact_key and mp.artifact_key not in art_opts:
                            art_opts[mp.artifact_key] = f"{mp.artifact_key}  (missing)"
                        ui.select(art_opts, value=mp.artifact_key or None,
                                  label="Artifact",
                                  on_change=lambda e, mp=mp: (
                                      setattr(mp, "artifact_key", e.value or ""),
                                      refresh_all())
                                  ).classes("w-48").props("dense")
                        if not items:
                            ui.label("no artifacts owned").classes(
                                "text-xs italic text-amber-700")
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
                        # ⚠ `ui.select` RAISES at build time for a value not in its
                        # options. A stored detail can be off-list ("strength" passes
                        # validate's `detail.strip().title()`). Normalize as validate
                        # does, then keep an unmatched value as its own option.
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

            # The catalogue picker, never a blind "Add merit / flaw" that appends the
            # cheapest available. Browse the filtered set, pick one, or choose Custom
            # for a display-only player-authored row.
            def _open_mf_catalogue() -> None:
                rows = [(m.id, _merit_label(m), m.description, m.description)
                        for m in available]
                cataloguemod.catalogue_dialog(
                    pal, "Merits & Flaws", rows, _pick_mf_catalogue,
                    subtitle=f"{len(available)} available to this character")

            def _pick_mf_catalogue(key) -> None:
                if key is None:
                    # `merit_id` is required but deliberately empty: it resolves to
                    # nothing in the catalogue, so the engine skips the row entirely —
                    # the "no mechanical effect" the Custom option promises.
                    character.merits_flaws.append(
                        MeritFlawPurchase(merit_id="",
                                          custom_name="New custom Merit / Flaw"))
                    refresh_all()
                    return
                definition = rs.merits_flaws.get(key)
                if definition is None:
                    return
                character.merits_flaws.append(
                    MeritFlawPurchase(merit_id=key,
                                      tier=_default_tier(definition)))
                refresh_all()

            ui.button("Add merit / flaw", icon="add", on_click=_open_mf_catalogue
                      ).props("flat dense")
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
        # tells them they failed it. Built in ui/view/ so the two shells cannot say
        # different things — they already had, by both omitting `prerequisites`.
        wants = viewmod.merit_requirement_line(
            ruleset, definition,
            meritsmod.merits_and_flaws_calc(ruleset, character))
        if wants:
            ui.label("Requires: " + wants).classes("text-xs italic opacity-70 pl-1")
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
        the ENTRY, not on the button — a Flaw pays the character — so the branch and
        its refusals live in `advancement.gain_merit_or_flaw`, shared with the native
        shell."""
        _do(lambda: advancement.gain_merit_or_flaw(
            rs, character, gain_state.get("id") or "",
            tier=gain_state.get("tier", ""),
            taken_as=gain_state.get("taken_as", ""),
            points=gain_state.get("points", 0),
            detail=gain_state.get("detail", "")))

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
                ui.label(viewmod.merit_method_note(method)).classes(
                    "text-xs text-gray-600")
                return
            ui.label(viewmod.MERIT_EXPERIENCE_PRICING_NOTE).classes("text-xs text-gray-600")
            # The p.17 cap applies in play too, and here it truncates the XP AWARD rather
            # than a bonus-point grant — a Flaw taken past the ceiling pays for its legal
            # part only. Silently paying less than the table expects is the worse
            # failure, so the remaining room is stated before anything is bought.
            text, warn = viewmod.flaw_room_note(eff.flaw_points_raw)
            ui.label(text).classes("text-xs font-semibold text-amber-700" if warn
                                   else "text-xs text-gray-600")
            # --- gain ------------------------------------------------------ #
            available = _available_merits(
                validate.effective_budgets(rs, character).essence_start)

            # The catalogue picker replaces the dropdown: browse the filtered set, pick
            # one (the detail preview below then prices it), or choose Custom for a
            # display-only row. The side/category filter bar narrows what the dialog
            # offers; the dialog's own text search narrows within that.
            def _gain_opts() -> list:
                return [m for m in available if _mf_matches(m)]

            def _open_gain_catalogue() -> None:
                rows = [(m.id, f"{m.name} {m.cost_note or ''}".strip(),
                         m.description, m.description)
                        for m in _gain_opts()]
                cataloguemod.catalogue_dialog(
                    pal, "Merits & Flaws", rows, _pick_gain,
                    subtitle=f"{len(_gain_opts())} available to this character")

            def _pick_gain(key) -> None:
                if key is None:
                    _custom_gain()
                    return
                _mf_changed(id=key, taken_as="", tier="", points=0, detail="")

            def _custom_gain() -> None:
                # ⚠ Build the prompt in the LAYOUT context, not in the slot of the
                # catalogue dialog. A nested ui.dialog() puts a canary in the current
                # slot. When the catalogue dialog clears, the canary's finalizer
                # deletes this dialog.
                with context.client.layout:
                    with ui.dialog() as dlg, ui.card().classes(
                            f"w-[26rem] p-4 gap-2 {pal.card_solid}"):
                        ui.label("Custom Merit / Flaw").classes("text-base font-bold")
                        ui.label(viewmod.CUSTOM_MERIT_NOTE).classes("text-xs text-gray-600")
                        name = ui.input(
                            placeholder="name (e.g. a bloodline trait)").props(
                            "dense").classes("w-full")

                        def _go() -> None:
                            text = (name.value or "").strip()
                            if not text:
                                ui.notify("Give the custom Merit / Flaw a name.",
                                          type="warning")
                                return
                            # Empty `merit_id` — resolves to nothing, so the engine
                            # treats the row as no-effect (the Custom option's
                            # contract).
                            character.merits_flaws.append(
                                MeritFlawPurchase(merit_id="", custom_name=text))
                            dlg.close()
                            refresh_all()

                        ui.button("Add", icon="check", on_click=_go).props(
                            f"dense color={pal.button}").mark("cat-custom-add")
                    dlg.open()

            def _apply_filter() -> None:
                count.text = _mf_count_label(
                    sum(1 for m in available if _mf_matches(m)), len(available))

            _mf_filter_bar(_apply_filter)
            count = ui.label(_mf_count_label(
                sum(1 for m in available if _mf_matches(m)), len(available))
            ).classes("text-xs opacity-60")
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.button("Browse catalogue", icon="inventory_2",
                          on_click=_open_gain_catalogue).props("dense")
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
                side = viewmod.merit_side_label(effective)
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
                def _held_name(mp) -> str:
                    if mp.custom_name:
                        return mp.custom_name + "  (custom)"
                    return (rs.merits_flaws[mp.merit_id].name
                            if mp.merit_id in rs.merits_flaws else mp.merit_id) \
                        + (f" ({mp.tier})" if mp.tier else "")

                held = {str(i): _held_name(mp)
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

    # ---- Fetters and Passions (ghosts only, E:Ab p.126-127, p.283) --------- #
    # On this tab, not Edit (human's ruling): lists with budgets.
    #
    # The two differ:
    #   * a FETTER is bought — pool dots, then bonus points, then experience;
    #   * a PASSION is never bought. Its dots come from the Virtues and the player
    #     distributes them (p.283). Its pool readout is a live derivation, with no
    #     price.

    def _has_fetters() -> bool:
        b = rs.budgets_for(character.exalt_type, character.origin, character.upbringing)
        return bool(b.fetter_dots or character.fetters)

    def _has_passions() -> bool:
        return bool(character.passions or _has_fetters())

    def add_fetter_row() -> None:
        character.fetters.append(FetterEntry(name="", rating=1))
        refresh_all()

    def remove_fetter(idx: int) -> None:
        del character.fetters[idx]
        refresh_all()

    def _fetters_panel(b) -> None:
        spent = derivemod.fetter_dots_spent(character)
        cap = derivemod.fetter_cap(character, rs)
        title = (f"Fetters ({b.fetter_dots} dots; ≤{b.fetter_cap_pre_bp} pre-bonus)"
                 if not _in_play() else "Fetters")
        with panel_card(pal, title):
            # The cap is Willpower + Essence and it MOVES, so it is stated as a live
            # number on both sides of the lock rather than as a chargen note.
            over = spent > cap
            ui.label(viewmod.fetter_budget_text(spent, cap)).classes("text-xs font-semibold" if over else "text-xs").style(
                f"color:{'#b91c1c' if over else 'inherit'}")
            for idx, f in enumerate(character.fetters):
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    ui.input(value=f.name, placeholder="what anchors you",
                             on_change=lambda e, f=f: (setattr(f, "name", e.value),
                                                       changed())
                             ).props("dense").classes("flex-1 min-w-48")
                    if _in_play():
                        # Post-lock a Fetter is bought, so the rating is read-only here
                        # and moves through the priced controls below.
                        ui.label("●" * f.rating + "○" * (5 - f.rating)
                                 ).classes("text-sm tracking-widest").style(
                            f"color:{pal.accent}")
                    else:
                        dots(lambda f=f: f.rating,
                             lambda v, f=f: setattr(f, "rating", v), 0, 5)
                    ui.input(value=f.note, placeholder="note",
                             on_change=lambda e, f=f: setattr(f, "note", e.value)
                             ).props("dense").classes("flex-1 min-w-32")
                    if not _in_play():
                        ui.button(icon="delete",
                                  on_click=lambda e=None, idx=idx: remove_fetter(idx)
                                  ).props("flat dense round")
            if not _in_play():
                ui.button("Add Fetter", icon="add", on_click=add_fetter_row
                          ).props("flat dense")
            else:
                _fetter_play_controls()

    def _fetter_play_controls() -> None:
        """Post-lock: raise, form and shift, each at its printed price (p.283)."""
        names = {f.name: f.name for f in character.fetters if f.name}
        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            sel = ui.select(_opts_with(list(names), None), label="Fetter",
                            with_input=True).props("dense").classes("flex-1 min-w-40")
            ui.button("Raise", on_click=lambda: _do(
                lambda: advancement.raise_fetter(rs, character, sel.value or "")
            )).props(f"dense color={pal.button}")
            shift_to = ui.input(placeholder="shift focus to…"
                                ).props("dense").classes("flex-1 min-w-40")
            ui.button(f"Shift ({rs.xp_costs_for(character.exalt_type).shift_fetter} XP)",
                      on_click=lambda: _do(
                          lambda: advancement.shift_fetter(
                              rs, character, sel.value or "", shift_to.value or ""))
                      ).props("dense flat")
        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            new_name = ui.input(placeholder="form a new Fetter…"
                                ).props("dense").classes("flex-1 min-w-48")
            ui.button(f"Form ({costsmod.new_fetter_cost(rs, character)} XP)",
                      on_click=lambda: _do(
                          lambda: advancement.add_fetter(
                              rs, character, new_name.value or ""))
                      ).props(f"dense color={pal.button}")

    def add_passion_row(virtue) -> None:
        character.passions.append(PassionEntry(name="", virtue=virtue, rating=1))
        refresh_all()

    def remove_passion(idx: int) -> None:
        del character.passions[idx]
        refresh_all()

    def _passions_panel() -> None:
        pool = derivemod.passion_pool(character)
        left = derivemod.passion_dots_unspent(character)
        with panel_card(pal, "Passions"):
            # Said plainly, because it is the single most surprising rule on the sheet
            # and the one a player will otherwise try to "buy".
            ui.label("Passion dots come from the Virtues and are never bought — "
                     "raise a Virtue and a dot of that Virtue's Passions opens up "
                     "(p.283). Distribute them here."
                     ).classes("text-xs text-gray-600")
            for virtue in VirtueName:
                if not pool[virtue] and not any(p.virtue == virtue
                                                for p in character.passions):
                    continue
                remaining = left[virtue]
                colour = ("#b91c1c" if remaining < 0
                          else "#a16207" if remaining > 0 else "#15803d")
                with ui.row().classes("w-full items-baseline gap-2"):
                    ui.label(virtue.value.title()).classes(
                        "text-sm font-bold").style(f"color:{pal.accent}")
                    ui.label(f"{pool[virtue] - remaining} of {pool[virtue]} distributed"
                             ).classes("text-xs font-semibold").style(f"color:{colour}")
                for idx, p in enumerate(character.passions):
                    if p.virtue != virtue:
                        continue
                    with ui.row().classes("w-full items-center gap-2 flex-wrap pl-3"):
                        ui.input(value=p.name, placeholder="what drives you",
                                 on_change=lambda e, p=p: (setattr(p, "name", e.value),
                                                           changed())
                                 ).props("dense").classes("flex-1 min-w-48")
                        # A free setter on BOTH sides of the lock, deliberately: this
                        # distributes a derived pool, it does not buy anything, so the
                        # post-lock XP stepper the Edit tab uses would be wrong here.
                        dots(lambda p=p: p.rating,
                             lambda v, p=p: setattr(p, "rating", v), 0, 5)
                        ui.button(icon="delete",
                                  on_click=lambda e=None, idx=idx: remove_passion(idx)
                                  ).props("flat dense round")
                ui.button(f"Add {virtue.value.title()} Passion", icon="add",
                          on_click=lambda v=virtue: add_passion_row(v)
                          ).props("flat dense").classes("ml-3")
            if _in_play():
                _passion_shift_controls()

    def _passion_shift_controls() -> None:
        """The one experience operation on a Passion (p.283, 20 XP): move a dot from
        one to another. The TOTAL cannot change — the Virtues set it."""
        names = [p.name for p in character.passions if p.name]
        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            frm = ui.select(_opts_with(names, None), label="Shift from",
                            with_input=True).props("dense").classes("flex-1 min-w-40")
            to = ui.input(placeholder="…to (new or existing)"
                          ).props("dense").classes("flex-1 min-w-40")
            ui.button(f"Shift ({rs.xp_costs_for(character.exalt_type).shift_passion} XP)",
                      on_click=lambda: _do(
                          lambda: advancement.shift_passion(
                              rs, character, frm.value or "", to.value or ""))
                      ).props("dense flat")

    # ---- body ------------------------------------------------------------- #
    @ui.refreshable
    def body() -> None:
        b = validate.effective_budgets(rs, character)
        if _in_play():
            _play_backgrounds()
            if _has_fetters():
                _fetters_panel(b)
            if _has_passions():
                _passions_panel()
            if rs.merits_flaws:
                _play_merits()
            return
        mf_effects = meritsmod.merits_and_flaws_calc(rs, character)
        _chargen_backgrounds(b, mf_effects)
        # Ghosts only; every other splat has an empty Fetter budget and empty lists.
        if _has_fetters():
            _fetters_panel(b)
        if _has_passions():
            _passions_panel()
        # Shown only when the rule set ships any (decision 0011: the data file is
        # optional).
        if rs.merits_flaws:
            _chargen_merits(b)

    def save() -> None:
        save_fn(character)

    # ---- layout ----------------------------------------------------------- #
    if with_header:
        ui.add_head_html(pal.head_style())
    with ui.row().classes("w-full max-w-7xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            if with_header:
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Advantages").classes("text-xl font-bold")
                    ui.button("Save", icon="save", on_click=save).props(
                        f"color={pal.button}").mark("tab-save")
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
        build_advantages(ruleset, character, save_to_path(path))

    ui.run(title=f"Exalted 1e — advantages: {character.name or path.stem}",
           reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
