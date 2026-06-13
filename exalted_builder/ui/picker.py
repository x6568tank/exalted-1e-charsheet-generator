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
from ..models.character import Character
from ..models.rules import RuleSet
from . import view as viewmod

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "exalted_builder" / "data"
_EXAMPLE = _REPO_ROOT / "examples" / "ashes-of-dawn.character.json"
_ACCENT = "#8a5a1a"
_CYTOSCAPE_CDN = "https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js"

# Uniform size and font for every node; owned / available / locked differ only by
# fill and border colour. Labels sit below the node on the parchment background,
# so label colour is the same everywhere (no font weight/size change between states).
_STYLE = [
    {"selector": "node", "style": {
        "label": "data(label)", "font-size": "14px", "font-weight": 600, "text-wrap": "wrap",
        "text-max-width": "130px", "text-valign": "bottom", "text-margin-y": 6,
        "text-outline-color": "#f7f1e3", "text-outline-width": 3,
        "color": "#3a2e1f", "width": 40, "height": 40,
        "background-color": "#cbd5e1", "border-width": 2, "border-color": "#94a3b8"}},
    {"selector": "node.owned", "style": {
        "background-color": _ACCENT, "border-color": "#5b3a10"}},
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
    def _pretty(cat: str) -> str:
        if ":" in cat:                          # 'martial_arts:snake' -> 'Martial Arts: Snake'
            base, style = cat.split(":", 1)
            return f"{base.replace('_', ' ').title()}: {style.replace('_', ' ').title()}"
        return cat.replace("_", " ").title()

    categories = sorted({c.category for c in ruleset.charms.values()})
    category_options = {c: _pretty(c) for c in categories}
    state = {"category": "melee" if "melee" in categories else (categories[0] if categories else "")}

    # ---- live readout ----------------------------------------------------- #
    @ui.refreshable
    def readout() -> None:
        view = viewmod.build_sheet_view(ruleset, character)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        errors = [i for i in view.issues if i.severity == "error"]
        ui.label(f"Charms: {len(character.charms)}").classes("text-sm font-semibold").style(f"color:{_ACCENT}")
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
        d = viewmod.build_charm_detail(ruleset, character, selected["id"]) if selected["id"] else None
        if d is None:
            ui.label("Tap a charm to see its details.").classes("text-xs text-gray-400")
            return
        ui.label(d.name).classes("text-sm font-bold").style(f"color:{_ACCENT}")
        ui.label(f"{d.type} · {d.cost}").classes("text-xs text-gray-600")
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
              style: {json.dumps(_STYLE)},
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

    def set_category(value: str) -> None:
        state["category"] = value
        init_graph()
        readout.refresh()

    def save() -> None:
        persistence.save_character(character, save_path)
        ui.notify(f"Saved to {save_path}", type="positive")

    if register_events:
        ui.on("charm_select", lambda e: select(e.args["id"]))

    # ---- layout ----------------------------------------------------------- #
    if with_header:
        ui.add_head_html(f'<script src="{_CYTOSCAPE_CDN}"></script>')
        ui.add_head_html("<style>body{background:#f7f1e3;color:#3a2e1f;}</style>")

    with ui.row().classes("w-full max-w-7xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                if with_header:
                    ui.label("Charm-Tree Picker").classes("text-xl font-bold")
                ui.select(category_options, value=state["category"], label="Category",
                          on_change=lambda e: set_category(e.value)).classes("w-48")
                if with_header:
                    ui.button("Save", icon="save", on_click=save).props("color=brown")
            with ui.row().classes("w-full gap-4 text-xs items-center justify-between"):
                with ui.row().classes("gap-4 items-center"):
                    for color, text in [(_ACCENT, "owned"), ("#15803d", "available"),
                                        ("#9ca3af", "locked (tap to see why)")]:
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("circle", size="0.7rem").style(f"color:{color}")
                            ui.label(text)
                ui.label("scroll to zoom · drag to pan").classes("text-gray-400 italic")
            # A real element (not ui.html, whose inline style gets sanitised away),
            # with an explicit DOM id for Cytoscape to mount into.
            (ui.element("div").props("id=charm-graph")
             .style("height:720px;width:100%;border:1px solid rgba(138,90,26,0.3);"
                    "border-radius:8px;background:#fffdf7"))
        with ui.column().classes("w-72 gap-2 sticky top-4"):
            with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30"):
                ui.label("Live Validation").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")
                readout()
            with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30"):
                ui.label("Charm Details").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")
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
