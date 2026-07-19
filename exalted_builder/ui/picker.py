"""
ui/picker.py — NiceGUI charm-tree picker (Cytoscape).

Renders a Charm category's prerequisite graph with Cytoscape.js. Nodes are
colour-coded owned / available / locked (from view.build_charm_graph, which asks
the engine). Tapping a node toggles ownership: an available Charm is learned, an
owned one is dropped; locked Charms refuse with a notice. A live readout re-runs
validation on each change. Save writes JSON via persistence.

No game logic here: the toggle asks engine.validate.meets_charm_requirements, and
node states come from the engine. Cytoscape is loaded from a CDN, so the browser
needs network access.

Run:
    python -m exalted_builder.ui.picker [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..engine import validate
from ..models.character import Character, OxBodyPurchase
from ..models.rules import RuleSet, circle_kind
from . import theme
from . import view as viewmod
from .assets import cytoscape_head_html

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "exalted_builder" / "data"
_EXAMPLE = _REPO_ROOT / "examples" / "ashes-of-dawn.character.json"


def _style(pal: theme.Palette) -> list[dict]:
    """Cytoscape stylesheet themed to `pal`. Uniform size/font for every node;
    owned / available / locked differ only by fill and border colour. Labels sit
    below the node on the parchment background, so the label outline is the page
    background and the owned fill is the splat accent (gold Solar / red DB)."""
    return [
        {"selector": "node", "style": {
            "label": "data(label)", "font-size": "14px", "font-weight": 600, "text-wrap": "wrap",
            "text-max-width": "130px", "text-valign": "bottom", "text-margin-y": 6,
            "text-outline-color": pal.bg, "text-outline-width": 3,
            "color": pal.ink, "width": 40, "height": 40,
            "background-color": "#cbd5e1", "border-width": 2, "border-color": "#94a3b8"}},
        {"selector": "node.owned", "style": {
            "background-color": pal.accent, "border-color": pal.accent_dark}},
        {"selector": "node.available", "style": {
            "background-color": "#86efac", "border-color": "#15803d", "border-width": 3}},
        {"selector": "node.locked", "style": {
            "background-color": "#e5e7eb", "border-color": "#cbd5e1"}},
        {"selector": "edge", "style": {
            "width": 2, "line-color": "#9ca3af", "target-arrow-color": "#9ca3af",
            "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 1.1}},
    ]


def _elements(graph: viewmod.CharmGraph) -> list[dict]:
    nodes = [{"data": {"id": n.id, "label": n.label}, "classes": n.state} for n in graph.nodes]
    edges = [{"data": {"id": f"{s}__{t}", "source": s, "target": t}} for s, t in graph.edges]
    return nodes + edges


def build_picker(ruleset: RuleSet, character: Character, save_path: Path,
                 *, with_header: bool = True, register_events: bool = True):
    """Render the picker. Returns its `toggle(charm_id)` so an embedding app can
    own a single charm_toggle event handler (set register_events=False then).
    with_header=False omits the title/Save bar and the head <script> (the host
    app supplies Cytoscape)."""
    pal = theme.palette(character.exalt_type)

    def _pretty(cat: str) -> str:
        if ":" in cat:                          # 'martial_arts:snake' -> 'Martial Arts: Snake'
            base, style = cat.split(":", 1)
            return f"{base.replace('_', ' ').title()}: {style.replace('_', ' ').title()}"
        return cat.replace("_", " ").title()

    def _visible_category_options() -> dict[str, str]:
        """Style-dropdown options for the CURRENT character state: their splat's
        categories, minus any a rule hides right now. The only such rule today is the
        Dragon-Blooded Dragon-Path gate (DB p241) — the elemental Dragon styles appear
        only once both enlightenment Charms (Spirit Sight + Spirit Walking) are known."""
        cats = sorted({c.category for c in ruleset.charms.values()
                       if validate.charm_matches_splat(character, c)
                       and validate.category_available(ruleset, character, c.category)})
        return {c: _pretty(c) for c in cats}

    _all_categories = sorted({c.category for c in ruleset.charms.values()
                              if validate.charm_matches_splat(character, c)})
    state = {"category": "melee" if "melee" in _all_categories
             else (_all_categories[0] if _all_categories else "")}
    widgets: dict = {}                          # holds the live category <select>

    # ---- Immaculate-vs-standard chargen path banner (Dragon-Blooded) ------- #
    def _immaculate_path_banner() -> None:
        """For a Dragon-Blooded, spell out which chargen Charm path they are on.
        The Immaculate path is triggered by any *Immaculate* Charm — the five
        Dragon-style trees (Air/Earth/Fire/Water/Wood Dragon), NOT Martial Arts in
        general: Five-Dragon Style is Martial Arts but a normal Charm and does not
        switch paths. Counts come from the budget, never hardcoded."""
        if character.exalt_type != "Dragon-Blooded":
            return
        b = ruleset.budgets_for(character.exalt_type, character.origin)
        if validate.immaculate_martial_artist(ruleset, character):
            msg = (f"Immaculate path — {b.immaculate_charm_count} Charms from one "
                   f"Dragon style; Aspect/Favored minimum waived.")
        else:
            msg = (f"Standard path — {b.charm_count} Charms, ≥{b.charm_min_caste_favored} "
                   f"Aspect/Favored. Pick a Dragon-style (Immaculate) Charm to switch "
                   f"to the Immaculate path.")
        ui.label(msg).classes("text-xs italic").style(f"color:{pal.accent}")

    # ---- live readout ----------------------------------------------------- #
    @ui.refreshable
    def readout() -> None:
        view = viewmod.build_sheet_view(ruleset, character)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        errors = [i for i in view.issues if i.severity == "error"]
        # Each Ox-Body purchase consumes a Charm pick from the shared pool of 10.
        charm_picks = len(character.charms) + len(character.ox_body)
        ui.label(f"Charms: {charm_picks} · Spells: {len(character.spells)}").classes(
            "text-sm font-semibold").style(f"color:{pal.accent}")
        _immaculate_path_banner()
        ui.label(bp).classes("text-xs text-gray-600")
        ui.separator()
        ui.label("✓ Legal" if not errors else f"✗ {len(errors)} error(s)").classes("text-sm font-bold").style(
            "color:#15803d" if not errors else "color:#b91c1c")
        for issue in view.issues:
            if issue.code == "bonus-points":
                continue
            color = {"error": "text-red-600", "warning": "text-amber-600"}.get(issue.severity, "text-gray-500")
            ui.label(f"• {issue.message}").classes(f"text-xs {color}")

    # ---- selected-charm detail panel -------------------------------------- #
    selected = {"id": None}

    @ui.refreshable
    def detail() -> None:
        if selected["id"] and selected["id"] == validate.ox_body_charm_id(ruleset, character):
            ox_body_detail()
            return
        d = viewmod.build_charm_detail(ruleset, character, selected["id"]) if selected["id"] else None
        if d is None:
            ui.label("Tap a charm to see its details.").classes("text-xs text-gray-400")
            return
        ui.label(d.name).classes("text-sm font-bold").style(f"color:{pal.accent}")
        ui.label(f"{d.type} · {d.cost}").classes("text-xs text-gray-600")
        _charm = ruleset.charms.get(d.id)
        if _charm is not None and validate.is_immaculate_charm(_charm):
            ui.label("Immaculate Order Charm (Fivefold Dragon Method)").classes(
                "text-xs font-semibold").style(f"color:{pal.accent}")
        if d.description:
            ui.label(d.description).classes("text-xs")
        ui.separator()
        ui.label(f"Requires: {d.requirement}").classes("text-xs font-semibold")
        if d.prerequisite_groups:
            ui.label("Prerequisite Charms:").classes("text-xs font-semibold")
            for group in d.prerequisite_groups:
                ui.label("• " + " or ".join(group)).classes("text-xs ml-2")
        else:
            ui.label("No prerequisite Charms.").classes("text-xs text-gray-500")
        ui.separator()
        if d.owned:
            ui.button("Remove", icon="remove", on_click=lambda: toggle(d.id)).props("dense color=negative")
        elif d.available:
            ui.button("Add", icon="add", on_click=lambda: toggle(d.id)).props("dense color=positive")
        else:
            ui.button("Add", icon="lock").props("dense disable").tooltip("Prerequisites not met")

    def select(charm_id: str) -> None:
        selected["id"] = charm_id
        detail.refresh()

    # ---- Ox-Body Technique (repeatable, variant menu; chargen) ------------- #
    def add_ox_body(variant_key: str) -> None:
        charm = validate.ox_body_charm(ruleset, character)
        variant = next((v for v in charm.variants if v.key == variant_key), None) if charm else None
        if variant is None:
            return
        if len(character.ox_body) >= validate.ox_body_cap(ruleset, character):
            ui.notify("Ox-Body: already bought once per dot of Endurance.", type="warning")
            return
        character.ox_body.append(
            OxBodyPurchase(variant=variant_key, health_levels=list(variant.health_levels)))
        ui.notify(f"Added Ox-Body Technique ({variant.label})", type="positive")
        detail.refresh(); update_graph()

    def remove_ox_body(index: int) -> None:
        if 0 <= index < len(character.ox_body):
            del character.ox_body[index]
            detail.refresh(); update_graph()

    def ox_body_detail() -> None:
        charm = validate.ox_body_charm(ruleset, character)
        if charm is None:
            ui.label("Ox-Body Technique is not in the rule set.").classes("text-xs text-red-600")
            return
        cap = validate.ox_body_cap(ruleset, character)
        bought = len(character.ox_body)
        labels = {v.key: v.label for v in charm.variants}
        ui.label(charm.name).classes("text-sm font-bold").style(f"color:{pal.accent}")
        ui.label(charm.description).classes("text-xs")
        ui.separator()
        ui.label(f"Bought {bought} / {cap}  ·  once per dot of Endurance").classes(
            "text-xs font-semibold")
        if bought:
            for i, p in enumerate(character.ox_body):
                with ui.row().classes("w-full items-center justify-between no-wrap gap-1"):
                    ui.label(f"• {labels.get(p.variant, p.variant)}").classes("text-xs")
                    ui.button(icon="remove", on_click=lambda _=None, i=i: remove_ox_body(i)).props(
                        "dense flat round size=sm color=negative")
        ui.separator()
        ui.label("Add a package:").classes("text-xs font-semibold")
        for v in charm.variants:
            btn = ui.button(v.label, icon="add",
                            on_click=lambda _=None, k=v.key: add_ox_body(k)).props("dense color=positive")
            if bought >= cap:
                btn.props("disable")
        if bought >= cap:
            ui.label("Raise Endurance to buy more." if cap else
                     "Needs at least 1 dot of Endurance.").classes("text-xs text-gray-500")

    # ---- spell picker (spells share the Charm pool; core p.100) ----------- #
    def toggle_spell(spell_id: str) -> None:
        if spell_id in character.spells:
            character.spells.remove(spell_id)
            ui.notify(f"Dropped {ruleset.spells[spell_id].name}", type="info")
        else:
            spell = ruleset.spells.get(spell_id)
            if spell is None:
                return
            if validate.meets_spell_requirements(ruleset, character, spell):
                character.spells.append(spell_id)
                ui.notify(f"Learned {spell.name}", type="positive")
            else:
                ui.notify(f"{spell.name}: not available", type="warning")
                return
        spells_panel.refresh()
        readout.refresh()

    def _spell_button(r) -> None:
        if r.owned:
            ui.button(icon="remove", on_click=lambda _=None, sid=r.id: toggle_spell(sid)).props(
                "dense flat round size=sm color=negative")
        elif r.available:
            ui.button(icon="add", on_click=lambda _=None, sid=r.id: toggle_spell(sid)).props(
                "dense flat round size=sm color=positive")
        else:
            ui.button(icon="lock").props("dense flat round size=sm disable").tooltip(r.reason)

    @ui.refreshable
    def spells_panel() -> None:
        # Spells share the Charm pool (p.100) and are gated on the Occult Sorcery
        # Charms, so they live under the Occult graph — one column per Circle —
        # and only appear on that page. Rebuilt on every Charm change so learning
        # a Circle Sorcery Charm immediately unlocks its spells.
        if state["category"] != "occult":
            return
        rows = viewmod.build_spell_picker(ruleset, character)
        if not rows:
            return
        by_circle: dict[str, list] = {}
        for r in rows:
            by_circle.setdefault(r.circle, []).append(r)
        # One column per circle actually present in the rows, in global track order
        # (sorcery Terrestrial→Solar, then necromancy Shadowlands→Void). A character
        # reaches whatever circles a learnable initiation Charm grants, so an Abyssal
        # whose Occult tree holds both sorcery and necromancy initiations shows both
        # (p.223); a plain Solar shows only Sorcery.
        present = [ce for ce in viewmod.CIRCLE_DISPLAY_ORDER if by_circle.get(ce.value)]
        kinds = {circle_kind(ce) for ce in present}
        magic_noun = ("Necromancy" if kinds == {"necromancy"}
                      else "Sorcery" if kinds == {"sorcery"}
                      else "Sorcery/Necromancy")
        with ui.card().classes(f"w-full p-3 {pal.card}"):
            with ui.row().classes("w-full items-baseline gap-3"):
                ui.label("Spells").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                ui.label(f"A spell takes a Charm pick (p.100); learn the matching Circle "
                         f"{magic_noun} Charm to unlock it.").classes("text-xs text-gray-500")
            with ui.row().classes("w-full gap-6 items-start no-wrap"):
                for circle_enum in present:
                    circle = circle_enum.value
                    with ui.column().classes("flex-1 gap-1 min-w-0"):
                        ui.label(f"{circle} Circle").classes(
                            f"text-xs font-semibold border-b {pal.rule} w-full").style(f"color:{pal.accent}")
                        for r in by_circle.get(circle, []):
                            with ui.row().classes("w-full items-center justify-between no-wrap gap-1"):
                                ui.label(r.name).classes("text-xs text-wrap").tooltip(r.description or r.name)
                                _spell_button(r)

    # ---- graph (re)build / update ---------------------------------------- #
    def init_graph() -> None:
        graph = viewmod.build_charm_graph(ruleset, character, state["category"])
        ui.run_javascript(f"""
        (function() {{
          var tries = 0;
          function go() {{
            tries += 1;
            var el = document.getElementById('charm-graph');
            if (!window.cytoscape) {{
              if (tries > 100) {{
                if (el) el.innerHTML = '<div style="padding:1rem;color:#b91c1c">'
                  + 'Could not load Cytoscape from the CDN (offline?).</div>';
                return;
              }}
              return setTimeout(go, 50);
            }}
            // wait until the container is mounted AND visible (non-zero height),
            // so the graph never renders into a hidden/collapsed tab panel
            if (!el || el.offsetHeight === 0) {{
              if (tries > 200) return;
              return setTimeout(go, 50);
            }}
            if (window.cy) {{ window.cy.destroy(); }}
            window.cy = cytoscape({{
              container: el,
              elements: {json.dumps(_elements(graph))},
              style: {json.dumps(_style(pal))},
              pixelRatio: Math.max(2, window.devicePixelRatio || 1),
              wheelSensitivity: 0.25, minZoom: 0.3, maxZoom: 3, textureOnViewport: false,
            }});
            window.cy.on('tap', 'node', function(e) {{ emitEvent('charm_select', {{id: e.target.id()}}); }});
            var lay = window.cy.layout({{name: 'breadthfirst', directed: true,
              roots: {json.dumps(graph.roots)}, spacingFactor: 1.5, padding: 30,
              avoidOverlap: true, fit: false}});
            // Fit, but never zoom below a readable level — that is what blurred the
            // labels (they render at font-size x zoom). Overflow becomes pannable.
            lay.one('layoutstop', function() {{
              window.cy.fit(undefined, 30);
              if (window.cy.zoom() < 0.85) {{ window.cy.zoom(0.85); window.cy.center(); }}
            }});
            lay.run();
          }}
          go();
        }})();
        """)

    def update_graph() -> None:
        graph = viewmod.build_charm_graph(ruleset, character, state["category"])
        states = {n.id: n.state for n in graph.nodes}
        ui.run_javascript(f"""
        if (window.cy) {{
          var s = {json.dumps(states)};
          Object.keys(s).forEach(function(id) {{
            var n = window.cy.getElementById(id);
            if (n) n.classes(s[id]);
          }});
        }}
        """)
        readout.refresh()

    def toggle(charm_id: str) -> None:
        if charm_id in character.charms:
            blockers = validate.charms_depending_on(ruleset, character, charm_id)
            if blockers:
                ui.notify(f"{ruleset.charms[charm_id].name}: can't remove — needed by "
                          f"{', '.join(blockers)}", type="warning")
                return
            character.charms.remove(charm_id)
            ui.notify(f"Removed {ruleset.charms[charm_id].name}", type="info")
        else:
            charm = ruleset.charms.get(charm_id)
            if charm is None:
                return
            if validate.meets_charm_requirements(ruleset, character, charm):
                character.charms.append(charm_id)
                ui.notify(f"Learned {charm.name}", type="positive")
            else:
                ui.notify(f"{charm.name}: prerequisites not met", type="warning")
                return
        update_graph()
        detail.refresh()
        spells_panel.refresh()        # a new/removed Sorcery Charm changes spell access
        _refresh_categories()         # learning/dropping DB enlightenment reveals/hides Dragon styles

    def set_category(value: str) -> None:
        state["category"] = value
        init_graph()
        readout.refresh()
        spells_panel.refresh()        # show/hide the Spells card with the Occult page

    def _refresh_categories() -> None:
        """Re-evaluate the visible style dropdown after a Charm change. Learning both
        Dragon-Blooded enlightenment Charms reveals the elemental Dragon styles;
        dropping one hides them again (falling back to a still-visible style)."""
        sel = widgets.get("category")
        if sel is None:
            return
        opts = _visible_category_options()
        if state["category"] in opts:
            sel.set_options(opts, value=state["category"])
        else:                          # current style just got hidden — fall back
            fallback = next(iter(opts), "")
            sel.set_options(opts, value=fallback)
            set_category(fallback)

    def save() -> None:
        persistence.save_character(character, save_path)
        ui.notify(f"Saved to {save_path}", type="positive")

    if register_events:
        ui.on("charm_select", lambda e: select(e.args["id"]))

    # ---- layout ----------------------------------------------------------- #
    if with_header:
        ui.add_head_html(cytoscape_head_html())
        ui.add_head_html(pal.head_style())

    with ui.row().classes("w-full max-w-7xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                if with_header:
                    ui.label("Charm-Tree Picker").classes("text-xl font-bold")
                widgets["category"] = ui.select(
                    _visible_category_options(), value=state["category"], label="Category",
                    on_change=lambda e: set_category(e.value)).classes("w-48")
                if with_header:
                    ui.button("Save", icon="save", on_click=save).props(f"color={pal.button}")
            with ui.row().classes("w-full gap-4 text-xs items-center justify-between"):
                with ui.row().classes("gap-4 items-center"):
                    for color, text in [(pal.accent, "owned"), ("#15803d", "available"),
                                        ("#9ca3af", "locked (tap to see why)")]:
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("circle", size="0.7rem").style(f"color:{color}")
                            ui.label(text)
                ui.label("scroll to zoom · drag to pan").classes("text-gray-400 italic")
            # A real element (not ui.html, whose inline style gets sanitised away),
            # with an explicit DOM id for Cytoscape to mount into.
            (ui.element("div").props("id=charm-graph")
             .style(f"height:720px;width:100%;border:1px solid {pal.graph_border};"
                    f"border-radius:8px;background:{pal.node_bg}"))
            # Spells live under the graph, but only render on the Occult page.
            spells_panel()
        with ui.column().classes("w-72 gap-2 sticky top-4"):
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                ui.label("Live Validation").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                readout()
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                ui.label("Charm Details").classes("text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                detail()

    # defer the first graph build until the client is connected and the div exists
    ui.timer(0.1, init_graph, once=True)
    return select


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e charm-tree picker")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset, character, path = load(args.character)

    @ui.page("/")
    def index() -> None:
        build_picker(ruleset, character, path)

    ui.run(title=f"Exalted 1e — charms: {character.name or path.stem}",
           reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
