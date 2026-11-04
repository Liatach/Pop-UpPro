"""Holes in the paper: windows, doorways and perforations.

Three sources, all turned into hole outlines in each piece's flat pattern
(millimetres) and cut out of the mesh when the card is built, so they show
in 3D and print as cut lines:

* Openings: rectangles, arches and ovals placed with sliders. An opening can
  go Through every layer behind it (frames and background, lined up as seen
  from the front when the stage is fully open) or Through to the next stage
  (the page glued back to back with this one, in a carousel).
* Painted holes: paint transparency into the art (Texture Paint, Erase Alpha)
  and press Cut Painted Holes: the see-through areas are traced into outlines
  (kept until traced again).
* Drawn holes: closed Grease Pencil strokes drawn over the flat layout (the
  "Pop-up Holes" object); Keep fixes them onto their pieces.
"""

import json
import math

import bpy
from mathutils import Vector, geometry

from .core.geom import clip_halfplane, poly_area

from .core.openings import (SEG, face_frame, opening_dict, place as _place,  # noqa: F401
                            shape)


# ------------------------------------------------------------- sources
def _piece_of(model, uid):
    """Pattern piece an opening is on: the card (0) or a mechanism's piece."""
    if uid == 0:
        return "Card"
    for name in model.pieces:
        tail = name.rstrip("0123456789")
        if name != "Card" and name[len(tail):] == str(uid) and tail in (
                "Frame", "Box", "VFold", "Tube", "Pyramid", "Roof", "Cube", "Tether", "Flap",
                "Stand", "Bridge", "Plat", "Rise", "Pic", "Jack"):
            return name
    return None


def _target(model, o):
    if o.on_piece:
        return o.on_piece if o.on_piece in model.pieces else None
    return _piece_of(model, o.on_uid)


def _behind(model, piece, poly):
    """An opening on a frame, carried straight back through every frame
    behind it and the background, as lined up when the stage is fully open:
    frames are flat chords there, so (x, y) is the same on each; on a page
    the side offset x lies at x / sin(angle / 2) from the fold."""
    out = []
    uid = int(piece[len("Frame"):]) if piece.startswith("Frame") else None
    if uid is None or uid not in model.frames:
        return out
    me = model.frames[uid]
    depth = me["depth"]
    for u, f in model.frames.items():
        if f["host"] == me["host"] and f["depth"] < depth - 1e-6:
            out.append((f"Frame{u}", list(poly)))
    sn = math.sin(math.radians(0.5 * me["open"]))
    back = "Card" if not me["host"] else f"VFold{me['host']}"
    if sn > 1e-3:
        # split at the fold: each side lands on its own page
        for sgn in (-1.0, 1.0):
            side = clip_halfplane(list(poly), (sgn, 0.0), 0.0)
            if len(side) >= 3 and abs(poly_area(side)) > 0.5:
                out.append((back, [(x / sn, y) for x, y in side]))
    return out


def place(model, o, faces=True):
    return _place(model, opening_dict(o), faces)


def _openings(scene, model, st, own=True):
    out = []
    done = getattr(model, "doors_done", set())
    for i, o in enumerate(st.openings):
        if own and o.cut == "DOOR" and i in done:
            continue  # cut and hinged by the model
        if not own and o.cut == "DOOR":
            continue
        piece = _target(model, o) if own else "Card"
        if own and piece is None:
            continue
        poly = place(model, o, faces=own)
        if len(poly) < 3:
            continue
        if own:
            out.append((piece, poly))
            if o.through == "BEHIND":
                out += _behind(model, piece, poly)
        if o.through == "NEXT" and _target(model, o) == "Card":
            out.append(("__next__" if o.x > 0 else "__prev__", poly))
    return out


def _neighbours(scene):
    st = scene.popup
    master = st.stage_master
    if master is None:
        return None, None
    from . import carousel
    sts = carousel.stages(master)
    if scene not in sts:
        return None, None
    i = sts.index(scene)
    n = len(sts)
    return sts[(i - 1) % n], sts[(i + 1) % n]


def painted(st):
    try:
        return json.loads(st.get("pop_painted", "{}"))
    except ValueError:
        return {}


def sketched(scene, model, layout):
    """Closed strokes on panels' cut layers, in their pieces' patterns."""
    from . import art
    from .naming import N
    out = []
    st = scene.popup
    obj = bpy.data.objects.get(N(scene, art.SKETCH))
    rig = st.rig
    if obj is None or obj.type != "GREASEPENCIL" or rig is None:
        return out
    mmu = st.mm_per_unit
    for layer in obj.data.layers:
        if not layer.name.endswith(art.CUT_SUFFIX) or layer.parent != rig:
            continue
        bone = rig.data.bones.get(layer.parent_bone)
        p = model.panels.get(layer.parent_bone)
        if bone is None or p is None:
            continue
        M = bone.matrix_local @ layer.matrix_parent_inverse @ layer.matrix_local
        Pi = layout["prints"][p.piece].inverted()
        fr = layer.current_frame()
        if fr is None or fr.drawing is None:
            continue
        for stroke in fr.drawing.strokes:
            pts = [(Pi @ ((M @ Vector(q.position)) * mmu)).to_2d() for q in stroke.points]
            if len(pts) >= 3 and abs(poly_area([tuple(q) for q in pts])) > 1.0:
                out.append((p.piece, [tuple(q) for q in pts]))
    return out


HOLES = "Pop-up Holes"  # Grease Pencil drawn on the flat layout


def hole_sketch(scene, create=True):
    """The flat Grease Pencil object hole outlines are drawn into, over the
    layout. It never moves with the card, and isn't part of what a carousel
    shows."""
    from . import art, build
    from .naming import N
    name = N(scene, HOLES)
    obj = bpy.data.objects.get(name)
    if obj is not None and obj.type != "GREASEPENCIL":
        obj = None
    if obj is None and create:
        gp = bpy.data.grease_pencils.new(name)
        obj = bpy.data.objects.new(name, gp)
    if obj is None:
        return None, None
    gp = obj.data
    layer = next((l for l in gp.layers if l.name == "cut"), None)
    if not create:
        # just looking (rebuilds): never change which layer the pen draws on,
        # or strokes meant as creases or cuts would land on the holes layer
        return obj, layer
    coll = build._collection(scene)
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    mat = art.cut_material()
    if mat.name not in [m.name for m in gp.materials if m]:
        gp.materials.append(mat)
    if layer is None:
        layer = gp.layers.new("cut")
        layer.frames.new(scene.frame_start)
    return obj, layer


def _drawn(scene):
    """Closed outlines drawn on the hole sketch, in layout millimetres."""
    obj, layer = hole_sketch(scene, create=False)
    st = scene.popup
    if obj is None or st.layout is None:
        return []
    mmu = st.mm_per_unit
    L = st.layout.matrix_world.inverted() @ obj.matrix_world
    out = []
    fr = layer.current_frame()
    if fr is None or fr.drawing is None:
        return out
    for stroke in fr.drawing.strokes:
        pts = [((L @ Vector(q.position)) * mmu).to_2d()[:] for q in stroke.points]
        if len(pts) >= 3 and abs(poly_area(pts)) > 1.0:
            out.append(pts)
    return out


def _to_piece(model, layout, pts):
    """The piece a layout outline lies on, and the outline in its pattern."""
    c = Vector((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), 0))
    for name, piece in model.pieces.items():
        Pi = layout["prints"][name].inverted()
        q = (Pi @ c).to_2d()
        for pn in piece.panels:
            for poly in model.panels[pn].polys:
                if _inside(tuple(q), poly):
                    return name, [(Pi @ Vector((x, y, 0))).to_2d()[:] for x, y in pts]
    return None, None


LINE_LAYERS = {"CREASE": ("crease", "Pop-up Crease Ink", (0.1, 0.35, 0.9, 1.0)),
               "CUT": ("slit", "Pop-up Slit Ink", (0.05, 0.05, 0.05, 1.0))}


def line_layer(scene, kind):
    """The layer extra creases (or cuts) are drawn on, over the layout."""
    obj, _ = hole_sketch(scene)
    gp = obj.data
    lname, mname, col = LINE_LAYERS[kind]
    mat = bpy.data.materials.get(mname)
    if mat is None:
        mat = bpy.data.materials.new(mname)
        bpy.data.materials.create_gpencil_data(mat)
        mat.grease_pencil.color = col
        mat.grease_pencil.show_stroke = True
        mat.grease_pencil.show_fill = False
    names = [m.name for m in gp.materials if m]
    if mat.name not in names:
        gp.materials.append(mat)
        names.append(mat.name)
    layer = next((l for l in gp.layers if l.name == lname), None)
    if layer is None:
        layer = gp.layers.new(lname)
        layer.frames.new(scene.frame_start)
    gp.layers.active = layer
    obj.active_material_index = names.index(mat.name)
    return obj, layer


def _open_rdp(seg, tol):
    if len(seg) < 3:
        return seg
    a, b = Vector(seg[0]), Vector(seg[-1])
    d = b - a
    L = d.length
    best, bi = -1.0, 0
    for i in range(1, len(seg) - 1):
        p = Vector(seg[i])
        dist = (p - a).length if L < 1e-9 else abs(d.x * (p.y - a.y) - d.y * (p.x - a.x)) / L
        if dist > best:
            best, bi = dist, i
    if best <= tol:
        return [seg[0], seg[-1]]
    return _open_rdp(seg[:bi + 1], tol)[:-1] + _open_rdp(seg[bi:], tol)


def take_lines(scene, model, layout, mirror=True):
    """Turn strokes drawn on the crease / slit layers into extra lines on the
    V-folds and boxes they lie on, and clear them. Returns (taken, missed)."""
    st = scene.popup
    obj, _ = hole_sketch(scene, create=False)
    if obj is None or st.layout is None:
        return 0, 0
    mmu = st.mm_per_unit
    L = st.layout.matrix_world.inverted() @ obj.matrix_world
    mechs = {m.uid: m for m in st.mechs if m.kind in ("VFOLD", "BOX", "BOXCUT", "ROOF")}
    got = miss = 0
    for kind, (lname, _, _) in LINE_LAYERS.items():
        layer = next((l for l in obj.data.layers if l.name == lname), None)
        if layer is None:
            continue
        fr = layer.current_frame()
        if fr is None or fr.drawing is None:
            continue
        for stroke in fr.drawing.strokes:
            pts = [((L @ Vector(q.position)) * mmu).to_2d()[:] for q in stroke.points]
            if len(pts) < 2:
                continue
            piece, poly = _to_piece(model, layout, pts)
            m = None
            for uid, (pc, to_user, bounds) in sorted(model.line_frames.items(),
                                                     key=lambda kv: -kv[0]):
                if pc != piece or (uid not in mechs and uid != 0):
                    continue
                user = [to_user(q) for q in poly]
                if bounds is not None:
                    cx = sum(q[0] for q in user) / len(user)
                    cy = sum(q[1] for q in user) / len(user)
                    x0, x1, y0, y1 = bounds
                    if not (x0 - 5 <= cx <= x1 + 5 and y0 - 5 <= cy <= y1 + 5):
                        continue
                m, poly = (mechs[uid] if uid else None), user
                card_line = uid == 0
                break
            else:
                card_line = False
            if m is None and not card_line:
                miss += 1
                continue
            if kind == "CREASE":
                poly = [poly[0], poly[-1]]
            else:
                poly = _open_rdp([tuple(q) for q in poly], 0.3)
            if math.hypot(poly[-1][0] - poly[0][0], poly[-1][1] - poly[0][1]) < 1.0 \
                    and len(poly) < 3:
                continue
            coll = st.card_lines if card_line else m.lines
            ln = coll.add()
            ln.kind = kind
            ln.mirror = mirror
            (ln.x0, ln.y0), (ln.x1, ln.y1) = poly[0], poly[-1]
            if len(poly) > 2:
                ln.path = json.dumps([(round(x, 3), round(y, 3)) for x, y in poly])
            if card_line:
                st.active_card_line = len(coll) - 1
            else:
                m.active_line = len(coll) - 1
            got += 1
        if len(fr.drawing.strokes):
            fr.drawing.remove_strokes()
    return got, miss


def follow_layout(scene, model, layout):
    """Strokes drawn over the layout (holes not yet kept, creases and cuts not
    yet added) belong to the piece they were drawn on. When the layout is
    packed again (a piece added, removed or resized) the pieces move; move
    the strokes with them, so they don't land on another piece."""
    from mathutils import Matrix
    st = scene.popup
    obj, _ = hole_sketch(scene, create=False)
    if obj is None or st.layout is None or st.rig is None:
        return 0
    try:
        old = json.loads(st.rig.get("pop_meta", "{}")).get("prints")
    except ValueError:
        old = None
    if not old:
        return 0
    olds = {k: Matrix([v[0:4], v[4:8], v[8:12], v[12:16]]) for k, v in old.items()}
    moves = {}
    for k, M in olds.items():
        N_ = layout["prints"].get(k)
        if N_ is None:
            continue
        D = N_ @ M.inverted()
        if any(abs(D[i][j] - (1.0 if i == j else 0.0)) > 1e-6 for i in range(4) for j in range(4)):
            moves[k] = (M.inverted(), D)
    if not moves:
        return 0
    mmu = st.mm_per_unit
    L = st.layout.matrix_world.inverted() @ obj.matrix_world
    Li = L.inverted()
    n = 0
    for layer in obj.data.layers:
        if layer.name not in ("cut", "crease", "slit"):
            continue
        fr = layer.current_frame()
        if fr is None or fr.drawing is None:
            continue
        for stroke in fr.drawing.strokes:
            pts = [(L @ Vector(q.position)) * mmu for q in stroke.points]
            if not pts:
                continue
            c = sum(pts, Vector()) / len(pts)
            piece = None
            for k in olds:
                if k not in model.pieces:
                    continue
                q = (olds[k].inverted() @ c).to_2d()
                if any(_inside(tuple(q), poly) for pn in model.pieces[k].panels
                       for poly in model.panels[pn].polys):
                    piece = k
                    break
            if piece is None or piece not in moves:
                continue
            D = moves[piece][1]
            for q, w in zip(stroke.points, pts):
                q.position = Li @ ((D @ w) / mmu)
            n += 1
    return n


def drawn(scene, model, layout):
    out = []
    for pts in _drawn(scene):
        piece, poly = _to_piece(model, layout, pts)
        if piece is not None:
            out.append((piece, poly))
    return out


def stored(st):
    try:
        return json.loads(st.get("pop_sketched", "{}"))
    except ValueError:
        return {}


def keep_drawn(scene, model, layout):
    """Fix what's drawn (and any old per-panel cut layers) as hole outlines on
    their pieces, and clear the strokes: the holes then stay with their
    pieces however the layout is rearranged."""
    from . import art
    from .naming import N
    st = scene.popup
    keep = stored(st)
    n = 0
    for piece, poly in drawn(scene, model, layout) + sketched(scene, model, layout):
        keep.setdefault(piece, []).append([(round(x, 3), round(y, 3)) for x, y in poly])
        n += 1
    st["pop_sketched"] = json.dumps(keep)
    obj, layer = hole_sketch(scene, create=False)
    if layer is not None:
        fr = layer.current_frame()
        if fr is not None and fr.drawing is not None and len(fr.drawing.strokes):
            fr.drawing.remove_strokes()
    old = bpy.data.objects.get(N(scene, art.SKETCH))
    if old is not None and old.type == "GREASEPENCIL":
        for lay in [l for l in old.data.layers if l.name.endswith(art.CUT_SUFFIX)]:
            old.data.layers.remove(lay)
    return n


def edit_kept(scene, model, layout):
    """Put the kept hole outlines back on the layout as strokes to edit."""
    st = scene.popup
    keep = stored(st)
    obj, layer = hole_sketch(scene)
    mmu = st.mm_per_unit
    L = obj.matrix_world.inverted() @ st.layout.matrix_world
    dr = layer.current_frame().drawing
    n = 0
    for piece, polys in keep.items():
        if piece not in layout["prints"]:
            continue
        P = layout["prints"][piece]
        for poly in polys:
            dr.add_strokes([len(poly)])
            stroke = dr.strokes[len(dr.strokes) - 1]
            for pt, (x, y) in zip(stroke.points, poly):
                pt.position = L @ ((P @ Vector((x, y, 0))) / mmu)
                pt.radius = 0.02
            stroke.cyclic = True
            stroke.material_index = len(obj.data.materials) - 1
            n += 1
    st["pop_sketched"] = "{}"
    return n


def collect(scene, model, layout=None):
    """{piece: [hole outline, ...]} in pattern millimetres."""
    st = scene.popup
    holes = {}

    def put(piece, poly, keep_turn=False):
        if piece in model.pieces and len(poly) >= 3:
            if not keep_turn and poly_area(poly) < 0:
                poly = poly[::-1]
            holes.setdefault(piece, []).append(poly)

    for piece, poly in _openings(scene, model, st):
        if not piece.startswith("__"):
            put(piece, poly)
    # openings on the neighbouring stages' pages that go through to this one
    prev, nxt = _neighbours(scene)
    for other, want in ((prev, "__next__"), (nxt, "__prev__")):
        if other is None or other == scene:
            continue
        for tag, poly in _openings(other, model, other.popup, own=False):
            if tag == want:
                put("Card", [(-x, y) for x, y in poly][::-1])
    for piece, polys in painted(st).items():
        for poly in polys:
            put(piece, [tuple(q) for q in poly], keep_turn=True)
    for piece, polys in stored(st).items():
        for poly in polys:
            put(piece, [tuple(q) for q in poly])
    if layout is not None:
        for piece, poly in drawn(scene, model, layout) + sketched(scene, model, layout):
            put(piece, poly)
    return holes


# ------------------------------------------------------------- checks
def check_joins(model, holes):
    """Warn when holes cut all the way along a fold, so a panel (or a glue
    tab) comes away from its neighbour."""
    for piece, hs in holes.items():
        pc = model.pieces.get(piece)
        if pc is None or not hs:
            continue
        signed = [(h, 1 if poly_area(h) >= 0 else -1) for h in hs]

        def cut_at(q):
            return sum(sg for h, sg in signed if _inside(q, h)) > 0

        segs = [(n, poly[i], poly[(i + 1) % len(poly)]) for n in pc.panels
                for poly in model.panels[n].polys for i in range(len(poly))]
        done = set()
        for i, (n1, a1, b1) in enumerate(segs):
            for n2, a2, b2 in segs[i + 1:]:
                if n1 == n2 or (n1, n2) in done:
                    continue
                d = (b1[0] - a1[0], b1[1] - a1[1])
                L = math.hypot(*d)
                if L < 1e-6:
                    continue
                u = (d[0] / L, d[1] / L)
                off = lambda q: abs((q[0] - a1[0]) * u[1] - (q[1] - a1[1]) * u[0])
                if off(a2) > 1e-3 or off(b2) > 1e-3:
                    continue
                t0, t1 = sorted(((a2[0] - a1[0]) * u[0] + (a2[1] - a1[1]) * u[1],
                                 (b2[0] - a1[0]) * u[0] + (b2[1] - a1[1]) * u[1]))
                lo, hi = max(0.0, t0), min(L, t1)
                if hi - lo < 0.5:
                    continue
                done.add((n1, n2))
                pts = [(a1[0] + u[0] * (lo + (hi - lo) * (k + 0.5) / 24),
                        a1[1] + u[1] * (lo + (hi - lo) * (k + 0.5) / 24)) for k in range(24)]
                if all(cut_at(q) for q in pts):
                    la = model.panels[n1].label
                    lb = model.panels[n2].label.split(": ")[-1]
                    model.warn(f"{la}: a hole cuts it free of its {lb} (the fold between "
                               f"them is cut right through)")


# ------------------------------------------------------------- cutting
def _inside(pt, poly):
    x, y = pt
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _clip(hole, poly):
    """Hole outline clipped to a convex CCW panel polygon."""
    out = list(hole)
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        nn = (-(b[1] - a[1]), b[0] - a[0])
        out = clip_halfplane(out, nn, nn[0] * a[0] + nn[1] * a[1])
        if len(out) < 3:
            return []
    return out


def cut(poly, holes):
    """Triangles covering a convex panel polygon minus the holes, or None if
    no hole touches it."""
    hs = []
    for h in holes:
        sgn = 1 if poly_area(h) >= 0 else -1  # clockwise: an island left inside a hole
        c = _clip(h if sgn > 0 else h[::-1], poly)
        if len(c) >= 3 and abs(poly_area(c)) > 0.05:
            hs.append((c, sgn))
    if not hs:
        return None
    verts = [Vector(q) for q in poly]
    faces = [list(range(len(poly)))]
    for h, _ in hs:
        k = len(verts)
        verts += [Vector(q) for q in h]
        faces.append(list(range(k, k + len(h))))
    try:
        vs, _, fs, *_ = geometry.delaunay_2d_cdt(verts, [], faces, 1, 1e-5)
    except Exception:
        return None
    tris = []
    for f in fs:
        pts = [tuple(vs[i]) for i in f]
        if abs(poly_area(pts)) < 1e-4:
            continue  # sliver along an edge the hole runs along
        c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        if not _inside(c, poly):
            continue
        # holes overlap freely (union); traced islands put paper back
        if sum(sg for h, sg in hs if _inside(c, h)) > 0:
            continue
        tris.append(pts)
    return tris


# ------------------------------------------------------------- painted holes
def trace(mask, step=1):
    """Outlines (lists of (col, row) grid corners, hole on the left) of the
    True areas of a 2D boolean grid (numpy array or nested lists)."""
    try:
        import numpy as np
        cells = {(int(r), int(c)) for r, c in np.argwhere(np.asarray(mask))}
    except ImportError:
        cells = {(r, c) for r, row in enumerate(mask) for c, v in enumerate(row) if v}
    nxt = {}
    for r, c in cells:
        # boundary edges of pixel (c, r), anticlockwise with the hole on the
        # left (rows run upwards)
        if (r - 1, c) not in cells:
            nxt.setdefault((c, r), []).append((c + 1, r))
        if (r, c + 1) not in cells:
            nxt.setdefault((c + 1, r), []).append((c + 1, r + 1))
        if (r + 1, c) not in cells:
            nxt.setdefault((c + 1, r + 1), []).append((c, r + 1))
        if (r, c - 1) not in cells:
            nxt.setdefault((c, r + 1), []).append((c, r))
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop = [start]
        cur = start
        while True:
            outs = nxt.get(cur)
            if not outs:
                break
            n2 = outs.pop()
            if not outs:
                del nxt[cur]
            if n2 == start:
                break
            loop.append(n2)
            cur = n2
        if len(loop) >= 4:
            loops.append(loop)
    return loops


def smooth(pts, passes=2):
    """Take the pixel stairs off a traced outline (5-point running mean)."""
    n = len(pts)
    if n < 8:
        return pts
    for _ in range(passes):
        pts = [(sum(pts[(i + j) % n][0] for j in range(-2, 3)) / 5.0,
                sum(pts[(i + j) % n][1] for j in range(-2, 3)) / 5.0) for i in range(n)]
    return pts


def simplify(pts, tol):
    """Ramer-Douglas-Peucker on a closed outline."""
    if len(pts) < 4:
        return pts

    def rdp(seg):
        if len(seg) < 3:
            return seg
        a, b = Vector(seg[0]), Vector(seg[-1])
        d = b - a
        L = d.length
        best, bi = -1.0, 0
        for i in range(1, len(seg) - 1):
            p = Vector(seg[i])
            dist = (p - a).length if L < 1e-9 else abs(d.x * (p.y - a.y) - d.y * (p.x - a.x)) / L
            if dist > best:
                best, bi = dist, i
        if best <= tol:
            return [seg[0], seg[-1]]
        return rdp(seg[:bi + 1])[:-1] + rdp(seg[bi:])

    far = max(range(len(pts)), key=lambda i: (Vector(pts[i]) - Vector(pts[0])).length)
    out = rdp(pts[:far + 1])[:-1] + rdp(pts[far:] + [pts[0]])[:-1]
    return out


def trace_painted(scene, threshold=0.5, res_mm=0.5, tol_mm=0.15):
    """Trace the see-through parts of the art, and of placed images set to
    Cut Where Transparent, into hole outlines per piece and keep them on the
    scene (they are cut at every rebuild until traced again). Erasing up to
    a piece's edge trims its outline the same way."""
    import tempfile

    import numpy as np
    from . import art, export_svg, images, live
    from .build import TILE_MM
    from .naming import N
    st = scene.popup
    meta = live.meta(st.rig)
    if meta is None:
        raise RuntimeError("build the card first")
    img = bpy.data.images.get(N(scene, art.ART_IMAGE))
    if img is None and not images.has_cuts(scene):
        raise RuntimeError("add art first")
    tiles = export_svg._tile_pngs(img, tempfile.mkdtemp(prefix="popup_holes_")) if img else {}
    out = {}
    for piece, info in meta["pieces"].items():
        if info["is_card"]:
            W, H = meta["W"], meta["H"]
            x0, y0, ex, ey = -W, 0.0, 2 * W, H
        else:
            ax, ay = info["anchor"]
            x0, y0, ex, ey = ax - TILE_MM / 2, ay - TILE_MM / 2, TILE_MM, TILE_MM
        path = tiles.get(1001 + info["slot"])
        mask = None
        if path is not None:
            t = bpy.data.images.load(path)
            try:
                w, h = t.size
                px = np.empty(w * h * 4, dtype=np.float32)
                t.pixels.foreach_get(px)
            finally:
                bpy.data.images.remove(t)
            sx, sy = ex / w, ey / h
            k = max(1, int(round(res_mm / max(sx, sy))))
            mask = px[3::4].reshape(h, w)[::k, ::k] < threshold
        if any(pl.piece == piece and pl.cut and pl.on and pl.image is not None
               for pl in st.images):
            if mask is None:
                k = 1
                sx = sy = res_mm
                mask = np.zeros((int(ey / res_mm), int(ex / res_mm)), dtype=bool)
            xs = x0 + (np.arange(mask.shape[1]) + 0.5) * k * sx
            ys = y0 + (np.arange(mask.shape[0]) + 0.5) * k * sy
            extra = images.cut_mask(scene, meta, piece, xs, ys, threshold)
            if extra is not None:
                mask = mask | extra
        if mask is None or not bool(mask.any()):
            continue
        polys = []
        for loop in trace(mask, k):
            pts = [(x0 + c * k * sx, y0 + r * k * sy) for c, r in loop]
            pts = simplify(smooth(pts), tol_mm)
            if len(pts) >= 3 and abs(poly_area(pts)) > 1.0:
                polys.append([(round(x, 3), round(y, 3)) for x, y in pts])
        if polys:
            out[piece] = polys
    st["pop_painted"] = json.dumps(out)
    return sum(len(v) for v in out.values())


# ------------------------------------------------- automatic painted cuts
def has_art(scene):
    from . import art
    from .naming import N
    return scene.popup.rig is not None and bpy.data.images.get(N(scene, art.ART_IMAGE)) is not None


def cut_painted(scene, force=False):
    """Trace the painted see-through areas (and placed images' cut shapes)
    and rebuild, if there is anything to trace. force: also when nothing is
    left to cut (an image's cut was just turned off)."""
    from . import build, images
    if not has_art(scene) and not images.has_cuts(scene):
        if force and scene.popup.get("pop_painted", "{}") != "{}":
            scene.popup["pop_painted"] = "{}"
            build.rebuild(scene, force=True)
        return 0
    before = scene.popup.get("pop_painted", "{}")
    n = trace_painted(scene)
    if scene.popup.get("pop_painted", "{}") != before:
        build.rebuild(scene, force=True)
    return n


_last_mode = {"mode": None}


def _mode_changed():
    """Leaving Texture Paint: cut what was painted see-through, so the paper
    takes the shape the paint shows (Cut Painted Areas setting)."""
    try:
        ctx = bpy.context
        mode = ctx.mode
        was = _last_mode["mode"]
        _last_mode["mode"] = mode
        sc = ctx.scene
        from .ops import switching
        if sc is not None and switching(sc):
            return  # painting carries on, on the card's other view
        if sc is not None and mode != was:
            from . import colours
            try:
                if mode == "PAINT_TEXTURE":
                    colours.enter(sc)
                elif was == "PAINT_TEXTURE":
                    colours.leave(sc)
                    from .ops import _end_paint_view
                    _end_paint_view(sc)  # left by any route: fold the card again
            except Exception:
                pass
        if was == "PAINT_TEXTURE" and mode != "PAINT_TEXTURE" and sc is not None \
                and sc.popup.auto_holes and has_art(sc):
            name = sc.name

            def run():
                scene = bpy.data.scenes.get(name)
                if scene is not None:
                    try:
                        cut_painted(scene)
                    except Exception as ex:  # keep painting usable; say why
                        scene.popup.status = f"Cutting painted areas failed: {ex}"
                return None
            bpy.app.timers.register(run, first_interval=0.05)
    except Exception:
        pass


_owner = object()


@bpy.app.handlers.persistent
def subscribe(*_args):
    bpy.msgbus.clear_by_owner(_owner)
    bpy.msgbus.subscribe_rna(key=(bpy.types.Object, "mode"), owner=_owner, args=(),
                             notify=_mode_changed)
    # a file just opened: no painting preview left in its paper, nor
    # painting's flat layout on a card no longer painted
    from . import colours
    from .ops import stale_paint_view
    try:
        scenes = list(bpy.data.scenes)
    except AttributeError:  # registering, before any file: nothing to tidy
        scenes = []
    for sc in scenes:
        try:
            if getattr(sc, "popup", None) is not None and sc.popup.card is not None:
                colours.heal(sc)
                stale_paint_view(sc)
                if sc.popup.layout is not None:
                    from .build import layout_in_renders
                    sc.popup.layout.hide_render = not layout_in_renders(sc)
        except Exception as ex:  # never stop a file opening
            print(f"Pop-Up Pro: {ex}")


def unsubscribe():
    bpy.msgbus.clear_by_owner(_owner)
