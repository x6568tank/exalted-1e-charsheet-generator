/*
 * server/board.js: the canvas of the board of a campaign (docs/plans/p4-board.md).
 *
 * The server is the authority. This script draws the objects that the server
 * sends, and it sends the intents of the person: put, delete, front, back, ask.
 * A change shows on each screen when the echo of the server arrives.
 *
 * Messages from the server (ExBoard.receive):
 *   {type: "snapshot", version, objects, background}  replace all.
 *   {type: "op", version, op: "put", obj}               add or replace one object.
 *   {type: "op", version, op: "delete", id}             remove one object.
 *   {type: "op", version, op: "order", ids}             the order of the layers.
 *   {type: "mode", edit, st}                            what this viewer can do.
 * An op with a version that is not the next version asks for a snapshot.
 *
 * WARNING: decision 0020. An object is a picture. It has no link to anything
 * outside the board. A label is the text that a person typed.
 */
(function () {
  'use strict';

  var B = {
    el: null, stage: null, bg: null, main: null, tr: null, grid: null,
    objects: {}, order: [], nodes: {}, version: 0,
    edit: false, st: false,
    tool: 'select', colour: '#1f2937', width: 3, fill: false,
    selected: null, draft: null, erasing: false, erased: {},
    background: null, fitted: false
  };

  var MAX_POINTS = 2000;

  function send(op, data) {
    data = data || {};
    data.op = op;
    emitEvent('exboard', data);
  }

  function uid() {
    return 'o' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  }

  function round1(v) { return Math.round(v * 10) / 10; }

  // ---- building the nodes ------------------------------------------------- //

  function build(o) {
    var n;
    if (o.kind === 'stroke') {
      n = new Konva.Line({
        points: o.points, stroke: o.colour, strokeWidth: o.width,
        lineCap: 'round', lineJoin: 'round', tension: 0.3,
        hitStrokeWidth: Math.max(14, o.width)
      });
    } else if (o.kind === 'shape') {
      if (o.shape === 'rect') {
        n = new Konva.Rect({
          x: o.x, y: o.y, width: o.w, height: o.h, stroke: o.colour,
          strokeWidth: o.width, fill: o.fill || undefined
        });
      } else if (o.shape === 'ellipse') {
        n = new Konva.Ellipse({
          x: o.x + o.w / 2, y: o.y + o.h / 2,
          radiusX: Math.abs(o.w / 2), radiusY: Math.abs(o.h / 2),
          stroke: o.colour, strokeWidth: o.width, fill: o.fill || undefined
        });
      } else {
        var Cls = o.shape === 'arrow' ? Konva.Arrow : Konva.Line;
        n = new Cls({
          points: [o.x, o.y, o.x + o.w, o.y + o.h], stroke: o.colour,
          strokeWidth: o.width, fill: o.colour, lineCap: 'round',
          pointerLength: 6 + o.width * 2, pointerWidth: 6 + o.width * 2,
          hitStrokeWidth: Math.max(14, o.width)
        });
      }
    } else if (o.kind === 'text') {
      n = new Konva.Text({
        x: o.x, y: o.y, text: o.text, fontSize: o.size, fill: o.colour,
        fontFamily: 'sans-serif'
      });
    } else if (o.kind === 'token') {
      n = new Konva.Group({ x: o.x, y: o.y });
      n.add(new Konva.Circle({
        radius: o.r, fill: o.colour, stroke: '#00000080', strokeWidth: 2
      }));
      if (o.label) {
        n.add(new Konva.Text({
          text: o.label, fontSize: Math.max(12, o.r * 0.55), fontStyle: 'bold',
          fill: '#111111', align: 'center', width: o.r * 8, x: -o.r * 4, y: o.r + 4,
          shadowColor: '#ffffff', shadowBlur: 4, shadowOpacity: 1,
          listening: false
        }));
      }
    } else {
      return null;
    }
    n.id(o.id);
    n.name('obj');
    n.draggable(B.edit && B.tool === 'select');
    n.on('dragend', function () { moved(n); });
    n.on('transformend', function () { resized(n); });
    return n;
  }

  // The new form of the object of node `n` after a drag.
  function moved(n) {
    var o = B.objects[n.id()];
    if (!o) { return; }
    var c = Object.assign({}, o);
    if (o.kind === 'stroke') {
      var dx = n.x(), dy = n.y();
      c.points = o.points.map(function (v, i) { return round1(v + (i % 2 ? dy : dx)); });
    } else if (o.kind === 'shape' && (o.shape === 'line' || o.shape === 'arrow')) {
      c.x = round1(o.x + n.x()); c.y = round1(o.y + n.y());
    } else if (o.kind === 'shape' && o.shape === 'ellipse') {
      c.x = round1(n.x() - o.w / 2); c.y = round1(n.y() - o.h / 2);
    } else {
      c.x = round1(n.x()); c.y = round1(n.y());
    }
    send('put', { obj: c });
  }

  // The new form of the object of node `n` after a resize.
  function resized(n) {
    var o = B.objects[n.id()];
    if (!o) { return; }
    var c = Object.assign({}, o);
    var sx = n.scaleX(), sy = n.scaleY();
    if (o.kind === 'token') {
      c.r = round1(Math.min(500, Math.max(5, o.r * sx)));
      c.x = round1(n.x()); c.y = round1(n.y());
    } else if (o.kind === 'text') {
      c.size = round1(Math.min(200, Math.max(8, o.size * sy)));
      c.x = round1(n.x()); c.y = round1(n.y());
    } else if (o.kind === 'shape' && o.shape === 'rect') {
      c.x = round1(n.x()); c.y = round1(n.y());
      c.w = round1(o.w * sx); c.h = round1(o.h * sy);
    } else if (o.kind === 'shape' && o.shape === 'ellipse') {
      c.w = round1(o.w * sx); c.h = round1(o.h * sy);
      c.x = round1(n.x() - c.w / 2); c.y = round1(n.y() - c.h / 2);
    } else {
      return;
    }
    send('put', { obj: c });
  }

  function resizable(o) {
    return o && (o.kind === 'token' || o.kind === 'text' ||
      (o.kind === 'shape' && (o.shape === 'rect' || o.shape === 'ellipse')));
  }

  // ---- drawing ------------------------------------------------------------ //

  function restack() {
    B.order.forEach(function (id) {
      var n = B.nodes[id];
      if (n) { n.moveToTop(); }
    });
    if (B.draft) { B.draft.moveToTop(); }
    B.tr.moveToTop();
  }

  function place(o) {
    var old = B.nodes[o.id];
    if (old) { old.destroy(); }
    var n = build(o);
    if (!n) { return; }
    B.nodes[o.id] = n;
    B.main.add(n);
  }

  function renderAll() {
    Object.keys(B.nodes).forEach(function (id) { B.nodes[id].destroy(); });
    B.nodes = {};
    B.order.forEach(function (id) { place(B.objects[id]); });
    reselect();
    restack();
    B.main.batchDraw();
  }

  function reselect() {
    var n = B.selected && B.nodes[B.selected];
    if (!n || !B.edit || B.tool !== 'select') {
      B.selected = null;
      B.tr.nodes([]);
      return;
    }
    var o = B.objects[B.selected];
    B.tr.resizeEnabled(resizable(o));
    B.tr.keepRatio(o.kind === 'token' || o.kind === 'text');
    B.tr.nodes([n]);
  }

  function select(id) {
    B.selected = id;
    reselect();
    B.main.batchDraw();
  }

  function drawGrid() {
    B.grid.destroyChildren();
    if (B.background) { return; }
    var step = 50, span = 5000;
    for (var v = -span; v <= span; v += step) {
      B.grid.add(new Konva.Line({ points: [v, -span, v, span], stroke: '#0000000d', strokeWidth: 1 }));
      B.grid.add(new Konva.Line({ points: [-span, v, span, v], stroke: '#0000000d', strokeWidth: 1 }));
    }
    B.grid.batchDraw();
  }

  function setBackground(bg) {
    var same = B.background && bg && B.background.url === bg.url;
    B.background = bg;
    if (same) { return; }
    B.bg.destroyChildren();
    drawGrid();
    if (!bg) { B.bg.batchDraw(); return; }
    var img = new window.Image();
    img.onload = function () {
      if (B.background !== bg) { return; }
      B.bg.destroyChildren();
      B.bg.add(new Konva.Image({ image: img, x: 0, y: 0, width: bg.width, height: bg.height }));
      B.bg.batchDraw();
    };
    img.src = bg.url;
  }

  function fit() {
    var w = B.stage.width(), h = B.stage.height();
    var box = null;
    if (B.background) {
      box = { x: 0, y: 0, width: B.background.width, height: B.background.height };
    } else if (B.order.length) {
      box = B.main.getClientRect({ relativeTo: B.main, skipTransform: false });
    }
    if (!box || !box.width || !box.height || !w || !h) {
      B.stage.scale({ x: 1, y: 1 });
      B.stage.position({ x: 0, y: 0 });
      return;
    }
    var s = Math.min(8, Math.max(0.1, 0.95 * Math.min(w / box.width, h / box.height)));
    B.stage.scale({ x: s, y: s });
    B.stage.position({
      x: (w - box.width * s) / 2 - box.x * s,
      y: (h - box.height * s) / 2 - box.y * s
    });
  }

  // ---- the tools ---------------------------------------------------------- //

  function setTool(tool) {
    B.tool = tool;
    var dragging = B.edit && tool === 'select';
    Object.keys(B.nodes).forEach(function (id) { B.nodes[id].draggable(dragging); });
    B.stage.draggable(tool === 'select' || !B.edit);
    var cursor = { select: 'default', eraser: 'not-allowed', text: 'text' }[tool] || 'crosshair';
    B.stage.container().style.cursor = B.edit ? cursor : 'grab';
    reselect();
    B.main.batchDraw();
  }

  function objectOf(target) {
    var n = target;
    while (n && n !== B.stage) {
      if (n.name && n.name() === 'obj' && B.objects[n.id()]) { return n; }
      n = n.getParent();
    }
    return null;
  }

  function pointer() {
    var p = B.main.getRelativePointerPosition();
    return { x: round1(p.x), y: round1(p.y) };
  }

  function erase(target) {
    var n = objectOf(target);
    if (n && !B.erased[n.id()]) {
      B.erased[n.id()] = true;
      n.opacity(0.3);
      B.main.batchDraw();
      send('delete', { id: n.id() });
    }
  }

  function down(e) {
    if (!B.edit) { return; }
    var t = B.tool;
    if (t === 'select') { return; }
    if (t === 'eraser') {
      B.erasing = true;
      B.erased = {};
      erase(e.target);
      return;
    }
    var p = pointer();
    if (t === 'text' || t === 'token') {
      send('ask', { kind: t, x: p.x, y: p.y });
      return;
    }
    var o = { id: uid(), colour: B.colour, width: B.width, x0: p.x, y0: p.y };
    if (t === 'pen') {
      o.kind = 'stroke';
      o.points = [p.x, p.y];
      B.draft = new Konva.Line({
        points: o.points, stroke: o.colour, strokeWidth: o.width,
        lineCap: 'round', lineJoin: 'round', tension: 0.3, listening: false
      });
    } else {
      o.kind = 'shape';
      o.shape = t;
      if (t === 'rect') {
        B.draft = new Konva.Rect({ x: p.x, y: p.y, stroke: o.colour, strokeWidth: o.width, listening: false });
      } else if (t === 'ellipse') {
        B.draft = new Konva.Ellipse({ x: p.x, y: p.y, stroke: o.colour, strokeWidth: o.width, listening: false });
      } else {
        var Cls = t === 'arrow' ? Konva.Arrow : Konva.Line;
        B.draft = new Cls({
          points: [p.x, p.y, p.x, p.y], stroke: o.colour, fill: o.colour, strokeWidth: o.width,
          pointerLength: 6 + o.width * 2, pointerWidth: 6 + o.width * 2, listening: false
        });
      }
    }
    B.draft.setAttr('pending', o);
    B.main.add(B.draft);
    B.draft.moveToTop();
  }

  function move(e) {
    if (B.erasing) { erase(e.target); return; }
    if (!B.draft) { return; }
    var o = B.draft.getAttr('pending');
    var p = pointer();
    if (o.kind === 'stroke') {
      var pts = o.points, n = pts.length;
      var min = 2 / B.stage.scaleX();
      if (n / 2 >= MAX_POINTS) { return; }
      if (Math.abs(p.x - pts[n - 2]) + Math.abs(p.y - pts[n - 1]) < min) { return; }
      pts.push(p.x, p.y);
      B.draft.points(pts);
    } else if (o.shape === 'rect') {
      B.draft.position({ x: Math.min(o.x0, p.x), y: Math.min(o.y0, p.y) });
      B.draft.size({ width: Math.abs(p.x - o.x0), height: Math.abs(p.y - o.y0) });
    } else if (o.shape === 'ellipse') {
      B.draft.position({ x: (o.x0 + p.x) / 2, y: (o.y0 + p.y) / 2 });
      B.draft.radius({ x: Math.abs(p.x - o.x0) / 2, y: Math.abs(p.y - o.y0) / 2 });
    } else {
      B.draft.points([o.x0, o.y0, p.x, p.y]);
    }
    o.x1 = p.x; o.y1 = p.y;
    B.main.batchDraw();
  }

  function up() {
    if (B.erasing) { B.erasing = false; return; }
    if (!B.draft) { return; }
    var o = B.draft.getAttr('pending');
    var draft = B.draft;
    B.draft = null;
    var obj;
    if (o.kind === 'stroke') {
      var pts = o.points.slice();
      if (pts.length < 4) { pts.push(round1(pts[0] + 0.5), round1(pts[1] + 0.5)); }
      obj = { kind: 'stroke', id: o.id, points: pts, colour: o.colour, width: o.width };
    } else {
      var x1 = o.x1 === undefined ? o.x0 : o.x1, y1 = o.y1 === undefined ? o.y0 : o.y1;
      if (Math.max(Math.abs(x1 - o.x0), Math.abs(y1 - o.y0)) < 3) { draft.destroy(); B.main.batchDraw(); return; }
      obj = { kind: 'shape', id: o.id, shape: o.shape, colour: o.colour, width: o.width, fill: null };
      if (o.shape === 'rect' || o.shape === 'ellipse') {
        obj.x = Math.min(o.x0, x1); obj.y = Math.min(o.y0, y1);
        obj.w = round1(Math.abs(x1 - o.x0)); obj.h = round1(Math.abs(y1 - o.y0));
        if (B.fill) { obj.fill = o.colour; }
      } else {
        obj.x = o.x0; obj.y = o.y0; obj.w = round1(x1 - o.x0); obj.h = round1(y1 - o.y0);
      }
    }
    // The draft stays on screen until the echo of the server replaces it.
    draft.id(o.id);
    draft.name('obj');
    B.nodes[o.id] = draft;
    send('put', { obj: obj });
  }

  function wire() {
    var s = B.stage;
    s.on('mousedown touchstart', down);
    s.on('mousemove touchmove', move);
    s.on('mouseup touchend mouseleave', up);
    s.on('click tap', function (e) {
      if (!B.edit || B.tool !== 'select') { return; }
      var n = objectOf(e.target);
      select(n ? n.id() : null);
    });
    s.on('dblclick dbltap', function (e) {
      if (!B.edit || B.tool !== 'select') { return; }
      var n = objectOf(e.target);
      var o = n && B.objects[n.id()];
      if (o && (o.kind === 'token' || o.kind === 'text')) { send('ask', { id: o.id }); }
    });
    s.on('wheel', function (e) {
      e.evt.preventDefault();
      var old = s.scaleX(), p = s.getPointerPosition();
      var m = { x: (p.x - s.x()) / old, y: (p.y - s.y()) / old };
      var k = e.evt.deltaY > 0 ? old / 1.1 : old * 1.1;
      k = Math.max(0.1, Math.min(8, k));
      s.scale({ x: k, y: k });
      s.position({ x: p.x - m.x * k, y: p.y - m.y * k });
    });
  }

  function onKey(e) {
    if (!B.stage || !B.edit || !B.selected) { return; }
    var tag = (e.target && e.target.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target && e.target.isContentEditable)) { return; }
    if (e.key === 'Delete' || e.key === 'Backspace') {
      e.preventDefault();
      send('delete', { id: B.selected });
    }
  }

  // ---- the messages ------------------------------------------------------- //

  function receive(m) {
    if (!B.stage) { B.pending = (B.pending || []).concat([m]); return; }
    if (m.type === 'mode') {
      B.edit = !!m.edit;
      B.st = !!m.st;
      setTool(B.edit ? B.tool : 'select');
      return;
    }
    if (m.type === 'snapshot') {
      B.version = m.version;
      B.objects = {};
      B.order = [];
      m.objects.forEach(function (o) { B.objects[o.id] = o; B.order.push(o.id); });
      setBackground(m.background);
      renderAll();
      if (!B.fitted) { B.fitted = true; fit(); }
      return;
    }
    if (m.type !== 'op') { return; }
    if (m.version !== B.version + 1) {
      if (m.version > B.version) { send('sync'); }
      return;
    }
    B.version = m.version;
    if (m.op === 'put') {
      if (!(m.obj.id in B.objects)) { B.order.push(m.obj.id); }
      B.objects[m.obj.id] = m.obj;
      place(m.obj);
    } else if (m.op === 'delete') {
      delete B.objects[m.id];
      B.order = B.order.filter(function (id) { return id !== m.id; });
      if (B.nodes[m.id]) { B.nodes[m.id].destroy(); delete B.nodes[m.id]; }
    } else if (m.op === 'order') {
      B.order = m.ids.slice();
    }
    reselect();
    restack();
    B.main.batchDraw();
  }

  function mount(elementId, mode, snapshot, tries) {
    tries = tries || 0;
    var el = document.getElementById(elementId);
    if (!window.Konva || !el || el.offsetWidth === 0 || el.offsetHeight === 0) {
      if (tries < 200) { setTimeout(function () { mount(elementId, mode, snapshot, tries + 1); }, 50); }
      return;
    }
    if (B.stage) { B.stage.destroy(); }
    B.el = el;
    B.nodes = {};
    B.fitted = false;
    B.background = null;
    B.stage = new Konva.Stage({ container: el, width: el.clientWidth, height: el.clientHeight });
    B.grid = new Konva.Layer({ listening: false });
    B.bg = new Konva.Layer({ listening: false });
    B.main = new Konva.Layer();
    B.stage.add(B.grid, B.bg, B.main);
    B.tr = new Konva.Transformer({
      rotateEnabled: false, keepRatio: true, flipEnabled: false,
      enabledAnchors: ['top-left', 'top-right', 'bottom-left', 'bottom-right']
    });
    B.main.add(B.tr);
    if (B.resize) { B.resize.disconnect(); }
    B.resize = new ResizeObserver(function () {
      if (el.clientWidth && el.clientHeight) {
        B.stage.size({ width: el.clientWidth, height: el.clientHeight });
      }
    });
    B.resize.observe(el);
    wire();
    receive(mode);
    receive(snapshot);
    var queued = B.pending || [];
    B.pending = [];
    queued.forEach(receive);
  }

  function command(name) {
    if (!B.stage) { return; }
    if (name === 'fit') { fit(); return; }
    if (!B.edit || !B.selected) { return; }
    if (name === 'delete') { send('delete', { id: B.selected }); }
    if (name === 'front') { send('front', { id: B.selected }); }
    if (name === 'back') { send('back', { id: B.selected }); }
  }

  function style(colour, width, fill) {
    B.colour = colour;
    B.width = width;
    B.fill = !!fill;
  }

  document.addEventListener('keydown', onKey);

  window.ExBoard = {
    mount: mount, receive: receive, setTool: setTool, command: command, style: style,
    // For the tests of a person at the browser: the current state, read-only.
    debug: function () { return { version: B.version, order: B.order.slice(), edit: B.edit }; }
  };
})();
