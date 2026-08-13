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

from nicegui import context, ui

from .. import persistence, rules_db
from ..engine import (advancement, artifacts as artifactsmod, costs as costsmod,
                      derive as derivemod, merits as meritsmod, validate)
from ..models.character import (ArtifactEntry, BackgroundEntry, Character,
                                FetterEntry, HearthstoneEntry, MeritFlawPurchase,
                                PassionEntry)
from ..models.rules import RuleSet, VirtueName
from . import catalogue as cataloguemod
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
        # Artifact issues belong here too: the Artifacts panel is on THIS tab, so the
        # two-flagships/budget findings must update live when a rating is edited,
        # rather than only appearing on the Sheet after a tab switch.
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
        """The catalogue entry a Background row names, or None for free text.

        Resolved through the SPLAT-FILTERED catalogue, which is what makes a
        Dragon-Blooded Manse row find the Dragon-Blooded allowance rather than the
        corebook's — the six Manse variants share two names between them, so a global
        lookup by name would answer for whichever copy it met first (the Illuminated
        Artifact scar)."""
        return _bg_types.get(bg.name.strip().lower())

    def _grows_stones(bg) -> bool:
        """Whether this row gets the Hearthstone picker. Asks the DATA (does this
        Background produce stones?) rather than the row's free-text name, and honours
        the per-row Demesne toggle — a Demesne grows none (human's ruling
        2026-08-12)."""
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
        """The stones held on one Manse row, plus a running total against the
        allowance. The total is printed on screen rather than left to the validator:
        the allowance differs per splat and per rating, so a player cannot know it
        without being told, and the Issue would be their first hint.

        Returns its own sync function, which the caller chains onto the row's
        rating-change callback — see `_sync` below."""
        # Declared before `_sync_total` closes over it and CREATED after the stone
        # rows, so the running total prints beneath them. Late binding makes the order
        # legal; the first call is the one at the end of this function.
        total = None

        def _sync_total() -> None:
            """Repaint the running total IN PLACE.

            ⚠ The allowance is recomputed HERE, on every call, never captured when the
            row was built. Both halves of "4 / 3" move: the numerator when a stone is
            added or re-rated, and the DENOMINATOR when the Manse rating changes — a
            Manse raised from ••• to ••••• is a bigger Manse and legalises the stone
            that was over budget a moment ago. A build-time allowance froze the
            denominator at whatever the rating happened to be when the panel was drawn
            (browser, 2026-08-12).

            ⚠ And never `refresh_all()` from the rating control. Rebuilding the panel
            rebuilds the inputs inside it, and a rebuilt input eats every keystroke
            after the first — the filter bar's lesson, recorded on the Background
            description label a few lines below, and the same shape as the dice-pool
            panel bug preflight caught on 2026-08-12 (state destroyed by exactly the
            click that produced it)."""
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

    def _background_rows(bg_cap) -> None:
        """The Background list itself — identical in both regimes but for the rating
        control, which is `bg_cap`'s business. This body is the whole reason the tab
        exists: it used to be two functions that differed only in their header.

        `bg_cap` is called with (bg, on_rating_change) and MUST invoke the callback
        when the rating moves: the rung label under the row is keyed to the rating,
        and the play regime's number input does not rebuild the panel, so without it
        the rung would keep describing the rating the row was drawn at."""
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
                # A Manse row gets the Hearthstone catalogue, because the stone is what
                # the Manse produces (core p.338) and its level is the MANSE's, not
                # Artifact's — picking one deliberately does NOT create an
                # `ArtifactEntry`, which would charge the p.131 Artifact budget for a
                # stone Artifact dots never bought.
                #
                # The Demesne toggle sits on every Background that COULD grow stones,
                # including one already flipped to Demesne — otherwise flipping it
                # would hide the control that flips it back. The picker sits only on
                # rows that actually grow them.
                if artifactsmod.grows_hearthstones(_bg_type(bg)):
                    ui.switch(value=bg.is_demesne,
                              on_change=lambda e, bg=bg: (
                                  setattr(bg, "is_demesne", bool(e.value)),
                                  refresh_all())
                              ).props("dense size=sm").tooltip(
                                  "Demesne rather than Manse — grows no Hearthstones"
                              ).mark("demesne-toggle")
                if _grows_stones(bg):
                    ui.button(icon="diamond",
                              on_click=lambda e=None, bg=bg: _open_hearthstones(bg)
                              ).props("flat dense round").tooltip("Hearthstones"
                              ).mark("hearthstone-picker")
                ui.button(icon="delete",
                          on_click=lambda e=None, idx=idx: remove_bg(idx)
                          ).props("flat dense round")
            # The catalogue description under the row — the dropdown tooltip made
            # persistent, the way the M&F rows print their rules text. Refreshed by the
            # row's own select WITHOUT rebuilding the panel: a rebuilt input eats every
            # keystroke after the first (the filter bar's lesson). `bg` and `desc` are
            # default-captured because the loop would otherwise bind every row's sync to
            # the LAST row's. A free-text name no catalogue entry covers gets nothing —
            # the label just hides. Backgrounds are free text, so this must never crash.
            # `data-testid` is the only prop that distinguishes this label from the M&F
            # rules-text labels below (which share its styling classes) — without it a
            # `should_see(description)` assertion matches the dropdown option tooltips
            # and passes against code with no persistent label at all.
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
                rung.set_text(rung_text)
                rung.set_visibility(bool(rung_text))

            row_sync["fn"] = _sync
            sel.on_value_change(lambda e, bg=bg, sync=_sync: (
                setattr(bg, "name", e.value or ""), sync()))
            _sync()

            # The Hearthstones held on this row, each with the rating the S&S p.67 cap
            # actually measures. Editable, because a stone's level is a fact about the
            # Manse that grew it and the printed ten are examples — a table's own stone
            # is the ordinary case. Shown whenever any are held, even on a row flipped
            # to Demesne or renamed off a Manse, so a stranded stone stays visible and
            # deletable rather than becoming an Issue with no control behind it.
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
            # The dialog is where a rating gets CHOSEN, so its "Full description"
            # panel carries the whole printed ladder, not just the blurb — the row
            # itself shows only the one rung the character holds. The summary stays
            # the plain description so the filter and the clamped one-liner are
            # unchanged. A Background with no transcribed ladder shows the blurb
            # alone, exactly as before.
            rows = []
            for b in sorted(bg_catalog, key=lambda b: b.name):
                ladder = viewmod.background_ladder(bg_catalog, b.name)
                # A blank line BETWEEN rungs, not just before the first: six rungs on
                # consecutive lines read as one block, and the dialog is where the
                # player compares them to choose a rating (human, click-through
                # 2026-08-12). The dialog's label renders these newlines only because
                # it carries `whitespace-pre-line` — see ui/catalogue.py.
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
            """The highest rating this Background may be clicked to. Ordinarily 5; a
            held Flaw may lower it (Innocuous caps Allies/Contacts/Mentor at 2) or close
            it outright (Followers, Cult, Command) — that half is engine.merits'. The
            engine.validate' half is the DATA ceiling: a splat rule caps or bars the
            Background (MF Backing ≤2, the mortal Artifact bar, the MF Artifact lift to
            10), and the control must not offer past it — a cap you can click past is
            not a ceiling."""
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
    def add_artifact() -> None:
        character.artifacts.append(ArtifactEntry(name="", rating=1))
        refresh_all()

    def remove_artifact(idx: int) -> None:
        del character.artifacts[idx]
        refresh_all()

    def _artifacts_panel() -> None:
        """The standalone artifacts — those that are neither weapon nor armour.

        On the Advantages tab because artifacts are bought with the Artifact Background
        and budgeted by it (E:Ab p.131), so the two belong under one eye. Weapons and
        armour keep their own `artifact_rating` on the equipment surface and are NOT
        editable here — they are only counted, in the budget line below, which is what
        stops a daiklave being entered twice.

        One panel, both regimes: an artifact is equipment, and equipment has never been
        XP-priced or log-tracked on either side of the lock.

        The name field is a combobox fed from `RuleSet.artifact_catalog`
        (`data/artifacts.json`): picking a catalogue entry fills the name and autofills
        the rating, and a typed off-catalogue name is free text that renames while
        preserving the rating. Entering a gear item both here and on the equipment
        surface counts it twice toward the budget — the same contract free text already
        has; there is no cross-catalogue dedup.
        """
        @ui.refreshable
        def _artifacts_header() -> None:
            """The budget line, its own refreshable so a rating edit updates it WITHOUT
            rebuilding the panel. Rebuilding the body from inside the rating input's
            on_change destroyed the widget mid-interaction — NiceGUI drops events that
            target a deleted element (Client.handle_event), so a rapid second click
            (5→4→5) was silently lost, the stored rating desynced from the number on
            screen, and the two-flagships warning never came back. The header and the
            readout are the only things a rating edit moves."""
            items = artifactsmod.artifact_items(character)
            rule = artifactsmod.artifact_rule(validate.effective_budgets(rs, character))
            budgeted = rule is not None and bool(rule.budget_tiers)
            header = "Artifacts"
            if budgeted:
                rating = sum(bg.rating for bg in character.backgrounds
                             if bg.name.strip().lower() == artifactsmod.ARTIFACT_BACKGROUND)
                tier = artifactsmod.budget_tier(
                    validate.effective_budgets(rs, character), rating)
                combined = sum(i.rating for i in items)
                if tier is not None:
                    # The row name is optional — the Cult of the Illuminated's table
                    # (p.96) prints bare dot rows where the Abyssal's names each one,
                    # and a blank left a trailing comma inside the parenthesis.
                    named = f", {tier.name}" if tier.name else ""
                    header = (f"Artifacts ({combined}/{tier.combined_max} combined — "
                              f"Artifact {rating}{named})")
                else:
                    header = f"Artifacts ({combined} combined — no Artifact Background)"
            with ui.row().classes("w-full items-baseline gap-2"):
                ui.label(header).classes(
                    "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                ui.label("bought with the Artifact Background").classes(
                    "text-xs text-gray-500")

        # The name combobox is fed from the catalogue (`data/artifacts.json`). Option
        # labels stay plain names so `art.name` stores cleanly; the rating and
        # description ride the option tooltip.
        # Filtered to what Artifact dots actually buy: the Hearthstones in the same
        # catalogue file come with the Manse Background, and picking one here would
        # charge the p.131 Artifact budget for something Artifact never bought. They
        # get their own picker on the Manse Background row instead.
        art_catalog = artifactsmod.purchasable_with_artifact(rs.artifact_catalog)
        art_names = [a.name for a in art_catalog]
        art_descs = {a.name: f"{a.rating_notes or ('•' * a.rating)} — {a.description}"
                     for a in art_catalog}
        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            _artifacts_header()
            for idx, art in enumerate(character.artifacts):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    sel = (DescribedSelect(_opts_with(art_names, art.name),
                                           descriptions=art_descs,
                                           value=art.name or None, label="Artifact name",
                                           with_input=True, new_value_mode="add-unique")
                           .props("dense").classes("flex-1"))
                    ui.input(value=art.note, placeholder="note",
                             on_change=lambda e, art=art: setattr(art, "note", e.value)
                             ).props("dense").classes("flex-1")
                    number = ui.number(value=art.rating, min=1, max=5, format="%d",
                                       label="Rating",
                                       on_change=lambda e, art=art: (
                                           setattr(art, "rating",
                                                   max(1, min(5, int(e.value or 1)))),
                                           _artifacts_header.refresh(),
                                           changed())
                                       ).props("dense").classes("w-24")
                    ui.button(icon="delete",
                              on_click=lambda e=None, idx=idx: remove_artifact(idx)
                              ).props("flat dense round")
                # The catalogue description under the row, mirroring the Background rows:
                # the dropdown tooltip made permanent. Refreshed by the row's own select
                # WITHOUT rebuilding the panel (a rebuilt input eats every keystroke —
                # the filter bar's lesson). A free-text name no catalogue entry covers
                # gets nothing — the label just hides. `data-testid` is the one prop that
                # distinguishes this label from the M&F rules-text labels, which share its
                # styling classes.
                desc = ui.label("").classes("text-xs opacity-70 pl-1"
                                            ).props('data-testid="art-desc"')

                def _sync(art=art, desc=desc):
                    entry = next((a for a in art_catalog if a.name == art.name), None)
                    text = entry.description if entry else ""
                    desc.set_text(text)
                    desc.set_visibility(bool(text))

                def _on_art(e, art=art, number=number, sync=_sync):
                    # A catalogue pick sets name + autofills rating; any other
                    # value is free text and only renames, preserving the rating.
                    entry = next((a for a in art_catalog
                                  if a.name == (e.value or "")), None)
                    if entry is not None:
                        art.name, art.rating = entry.name, entry.rating
                        # Keep the on-screen control in sync: the header refresh
                        # recomputes the total but must NOT rebuild the body (see
                        # the header docstring), so the number is pushed directly.
                        number.value = entry.rating
                    else:
                        art.name = e.value or ""
                    sync()
                    _artifacts_header.refresh()
                    changed()

                sel.on_value_change(_on_art)
                _sync()
            # Artifact weapons and armour count against the same budget but are edited
            # on the equipment surface. Listed read-only so the combined total above is
            # accounted for rather than looking wrong.
            gear = [i for i in artifactsmod.artifact_items(character)
                    if i.source != artifactsmod.SOURCE_ARTIFACT]
            if gear:
                ui.label("Also counted, from equipment: "
                         + ", ".join(f"{i.name} ({i.rating})" for i in gear)
                         ).classes("text-xs italic opacity-70")

            # The catalogue picker replaces the blind "Add artifact": browse the
            # catalogue (name + rating + description), pick one — name AND rating
            # autofilled — or choose Custom for a blank row.
            def _open_artifact_catalogue() -> None:
                rows = [(a.name, a.name,
                         f"{a.rating_notes or ('•' * a.rating)} — {a.description}",
                         a.description)
                        for a in art_catalog]
                icons = {a.name: cataloguemod.icon_for(a.tags, "auto_awesome")
                         for a in art_catalog}
                cataloguemod.catalogue_dialog(pal, "Artifacts", rows, _pick_artifact,
                                              icons=icons)

            def _pick_artifact(name) -> None:
                if name is None:
                    add_artifact()
                    return
                entry = next((a for a in art_catalog if a.name == name), None)
                if entry is not None:
                    character.artifacts.append(
                        ArtifactEntry(name=entry.name, rating=entry.rating))
                else:
                    character.artifacts.append(ArtifactEntry(name=name, rating=1))
                refresh_all()

            ui.button("Add artifact", icon="add", on_click=_open_artifact_catalogue
                      ).props("flat dense")

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

    # ---- Merits & Flaws: the filter bar ----------------------------------- #
    # 99 entries in one flat dropdown, which is how both regimes shipped: the chargen
    # row select had no type-ahead at all, and the play one had type-ahead over a label
    # that leads with the name, so "combat" found nothing. One filter, used by both —
    # the same discipline as the rest of this module, since a second copy is what put
    # the splat filter on one panel and not the other.
    #
    # The controls do NOT refresh the body. A `ui.input` fires per keystroke and a
    # rebuilt input has lost focus, so the search box would eat every character after
    # the first. The filter reaches into the live selects with `set_options` instead.
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
        # it. Held rows survive both this filter and the search bar's via `_row_opts`,
        # so an entry that became illegal (a caste change) stays visible and flagged
        # rather than vanishing.
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
                ui.label(f"⚠ {eff.flaw_points_raw} points of Flaws taken, "
                         f"{eff.bonus_point_grant} granted — the excess "
                         f"{eff.flaw_points_raw - eff.bonus_point_grant} is lost to the "
                         f"{meritsmod.FLAW_POINT_CAP}-point cap (p.17). The Flaws still "
                         f"apply.").classes("text-xs font-semibold text-amber-700")
            _mf_filter_bar(_apply_filter)
            count = ui.label(_mf_count_label(
                sum(1 for m in available if _mf_matches(m)), len(available))
            ).classes("text-xs opacity-60")
            for idx, mp in enumerate(character.merits_flaws):
                definition = rs.merits_flaws.get(mp.merit_id)
                # A player-authored "Custom" row (2026-08-10): no catalogue entry, no
                # mechanical effect — just a name the sheet renders. It gets a plain
                # text input instead of the select and NONE of the definition-driven
                # controls, because `merit_id` resolves to nothing and every one of
                # those controls reads `definition` (which would be None).
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
                # flex-wrap, NOT no-wrap: the merge of the two old panels put more
                # controls on this row than either had alone — entry, side, tier, arena,
                # stipulations and detail can all appear at once — and a no-wrap row
                # crushes its later children to slivers rather than wrapping them. That
                # is how a sheet panel went invisible on 2026-07-31.
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

            # The catalogue picker replaces the blind "Add merit / flaw" (which used to
            # append the cheapest available). Browse the filtered set, pick one, or
            # choose Custom for a display-only player-authored row.
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
                # Build the prompt in the LAYOUT context, not the catalogue dialog's
                # slot. A nested ui.dialog() creates a hidden canary element in the
                # current slot; the catalogue dialog's clear-on-close then deletes the
                # canary, whose weakref finalizer deletes THIS dialog — the reviewer
                # found it as "Custom is a silent no-op". Parented into layout, the
                # canary is a sibling of the catalogue dialog, not a descendant, so
                # clearing the catalogue dialog leaves the prompt alive.
                with context.client.layout:
                    with ui.dialog() as dlg, ui.card().classes(
                            f"w-[26rem] p-4 gap-2 {pal.card_solid}"):
                        ui.label("Custom Merit / Flaw").classes("text-base font-bold")
                        ui.label("Display-only — recorded on the sheet, no mechanical "
                                 "effect (2026-08-10).").classes("text-xs text-gray-600")
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
    # On this tab rather than Edit (human, 2026-08-01): they are lists edited under
    # two budget regimes, which is exactly the shape this tab exists for, not the one
    # slot seen from two sides that the Edit/XP dot tracks are.
    #
    # The two behave very differently and the panels must not blur that:
    #   * a FETTER is bought — pool dots, then bonus points, then experience;
    #   * a PASSION is not bought at ANY point. Its dots come from the Virtues and the
    #     player only distributes them (p.283). So its "pool" readout is a derivation
    #     that keeps moving after the lock, and there is no price anywhere on it.

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
            ui.label(f"{spent} of {cap} dots (cap = Willpower + Essence, p.127)"
                     ).classes("text-xs font-semibold" if over else "text-xs").style(
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
            _artifacts_panel()
            if _has_fetters():
                _fetters_panel(b)
            if _has_passions():
                _passions_panel()
            if rs.merits_flaws:
                _play_merits()
            return
        mf_effects = meritsmod.merits_and_flaws_calc(rs, character)
        _chargen_backgrounds(b, mf_effects)
        _artifacts_panel()
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
