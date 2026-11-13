"""Ink layers: what is drawn with Draw Anywhere, kept as Grease Pencil strokes.

A Grease Pencil stroke is always drawn facing the camera, a row of little
sprites, so strokes left standing on a folded card never sit flat on the
paper. So the card shows a picture of them instead (the paper's art
texture), and the strokes themselves are kept out of sight on one hidden
object, "Pop-up Ink Layers", in layers that can be hidden, faded, reordered
and edited; **Update Paper** redraws the picture from them. Nothing is baked
in for good.

* Each stroke is kept on its own piece of paper: a `pop_tile` number (the
  piece's art tile) and points measured on that piece (mm-scale x along the
  tile, y up it, z off the paper), so it stays put when mechanisms are
  added and the print layout moves.
* The paper before any ink is kept per tile ("Pop-up Art Base <tile>");
  the art tile is that with every visible layer drawn over it, in order,
  by the same flat render Draw Anywhere always used (art._render_strokes).
* Edit Ink lays the strokes out on the flat layout, where the view is
  straight down and they look as they print; Done Editing takes them back
  (each point onto the paper under it) and redraws the paper.
"""
import bpy
from mathutils import Matrix, Vector

from . import art, live
from .naming import N

INK_LAYERS = "Pop-up Ink Layers"
TILE = "pop_tile"  # per stroke: its piece's art tile (0: not placed yet)
BASE = "Pop-up Art Base"
Z = Vector((0.0, 0.0, 1.0))


# ---------------------------------------------------------------- the object
def ink_object(scene, create=True):
    obj = bpy.data.objects.get(N(scene, INK_LAYERS))
    if obj is not None and obj.type != "GREASEPENCIL":
        obj = None
    if obj is None and create:
        gp = bpy.data.grease_pencils.new(N(scene, INK_LAYERS))
        obj = bpy.data.objects.new(N(scene, INK_LAYERS), gp)
        from .build import _collection
        _collection(scene).objects.link(obj)
        obj.hide_render = True
        obj.hide_viewport = True
        obj.hide_select = True
    return obj


def layers(scene):
    """The ink layers, bottom first."""
    obj = ink_object(scene, create=False)
    return list(obj.data.layers) if obj is not None else []


def active_layer(scene, create=True):
    obj = ink_object(scene, create)
    if obj is None:
        return None
    gp = obj.data
    if gp.layers.active is None:
        if len(gp.layers):
            gp.layers.active = gp.layers[len(gp.layers) - 1]
        elif create:
            new_layer(scene)
    return gp.layers.active


def new_layer(scene, name=None):
    gp = ink_object(scene).data
    used = {la.name for la in gp.layers}
    n = 1
    while name is None and f"Ink {n}" in used:
        n += 1
    la = gp.layers.new(name or f"Ink {n}")
    la.use_lights = False
    la.frames.new(scene.frame_start)
    gp.layers.active = la
    return la


def editing(scene):
    """Are the strokes laid out on the flat layout to be edited just now?"""
    return bool(scene.get("pop_ink_editing"))


def _drawing(layer, scene):
    return art._drawing_of(layer, scene)


def _tiles(drawing, n=None):
    """The strokes' tile numbers (the attribute made if need be)."""
    at = drawing.attributes.get(TILE)
    if at is None:
        at = drawing.attributes.new(TILE, "INT", "CURVE")
    vals = [0] * len(drawing.strokes)
    if vals:
        at.data.foreach_get("value", vals)
    return at, vals


def _frames(scene):
    """{tile: (origin, x axis, y axis, u edge, v edge)} on the flat layout
    (rest space), and {piece: tile}."""
    out, of = {}, {}
    for pc, (num, o, eu, ev) in art._tile_frames(scene).items():
        out[num] = (o, eu.normalized(), ev.normalized(), eu, ev)
        of[pc] = num
    return out, of


def _home(r, fr):
    d = r - fr[0]
    return Vector((d.dot(fr[1]), d.dot(fr[2]), d.z))


def _rest(h, fr):
    return fr[0] + fr[1] * h.x + fr[2] * h.y + Z * h.z


def _material_slots(gp, materials):
    """Where each of the drawing object's materials is on the ink object
    (added if it isn't there yet): [index]."""
    have = list(gp.materials)
    out = []
    for m in materials:
        if m not in have:
            gp.materials.append(m)
            have.append(m)
        out.append(have.index(m))
    return out


# ---------------------------------------------------------------- strokes in
def add_strokes(scene, by_piece, materials):
    """Keep new strokes on the active layer. by_piece: {piece: [(points in
    rest space (position, radius, opacity, vertex colour), stroke attributes,
    cyclic)]}, as art.paint_free sorts them; materials: the drawing
    object's, which the strokes' material_index counts through. Returns the
    tiles drawn on."""
    frames, of = _frames(scene)
    layer = active_layer(scene)
    obj = ink_object(scene)
    slot = _material_slots(obj.data, materials)
    dr = _drawing(layer, scene)
    touched = set()
    for pc, strokes in by_piece.items():
        num = of.get(pc)
        if num is None:
            continue
        fr = frames[num]
        home = []
        for pts, attrs, cyc in strokes:
            a = dict(attrs)
            mi = a.get("material_index", 0)
            a["material_index"] = slot[mi] if 0 <= mi < len(slot) else 0
            home.append(([(_home(r, fr), rad, op, col) for r, rad, op, col in pts], a, cyc))
        first = art.put_strokes(dr, home)
        at, _vals = _tiles(dr)
        for i in range(first, len(dr.strokes)):
            at.data[i].value = num
        touched.add(num)
    return touched


def _read(drawing, vals, want):
    """Strokes of a drawing as art.put_strokes takes them, for the strokes
    whose tile value satisfies want: [(index, tile, points, attrs, cyclic)]."""
    out = []
    for i, s in enumerate(drawing.strokes):
        if not want(vals[i]):
            continue
        attrs = {k: getattr(s, k) for k in art._STROKE_ATTRS if hasattr(s, k)}
        if "fill_color" in attrs:
            attrs["fill_color"] = tuple(attrs["fill_color"])
        pts = [(Vector(p.position), p.radius, p.opacity, tuple(p.vertex_color)) for p in s.points]
        out.append((i, vals[i], pts, attrs, bool(s.cyclic)))
    return out


def strokes_on(scene, num, frames):
    """Every visible layer's strokes on one tile, bottom layer first, in
    rest space: [(layer, [(points, attrs, cyclic)])]."""
    fr = frames[num]
    out = []
    for la in layers(scene):
        if la.hide:
            continue
        dr = _drawing(la, scene)
        _at, vals = _tiles(dr)
        got = [([(_rest(h, fr), rad, op, col) for h, rad, op, col in pts], attrs, cyc)
               for _i, _t, pts, attrs, cyc in _read(dr, vals, lambda t: t == num)]
        if got:
            out.append((la, got))
    return out


# ---------------------------------------------------------------- the paper
def _base_name(scene, num):
    return N(scene, f"{BASE} {num}")


def inked_tiles(scene):
    """Tiles with ink on them now, or that have had (their paper is kept)."""
    out = set()
    for la in layers(scene):
        _at, vals = _tiles(_drawing(la, scene))
        out.update(v for v in vals if v)
    pre = _base_name(scene, "")
    for im in bpy.data.images:
        if im.name.startswith(pre) and im.name[len(pre):].isdigit():
            out.add(int(im.name[len(pre):]))
    return out


def update_paper(scene, tiles=None):
    """Redraw the paper's art from the ink layers: on the tiles given, or on
    every tile that has (or has had) ink. Returns how many were redrawn."""
    st = scene.popup
    if st.rig is None or live.meta(st.rig) is None:
        return 0
    bare = editing(scene)  # (the strokes are out on the layout: the paper shows none)
    if bpy.data.images.get(N(scene, art.ART_IMAGE)) is None:
        art.add_art_texture(scene)
    img = bpy.data.images.get(N(scene, art.ART_IMAGE))
    frames, _of = _frames(scene)
    sizes = {t.number: tuple(t.size) for t in img.tiles}
    todo = inked_tiles(scene) if tiles is None else set(tiles)
    obj = ink_object(scene, create=False)
    mats = list(obj.data.materials) if obj is not None else []
    patches = {}
    for num in sorted(todo):
        if num not in frames or num not in sizes:
            continue  # (its piece is gone: its strokes wait, should it come back)
        fr = frames[num]
        lay = [] if bare else strokes_on(scene, num, frames)
        got = art._render_strokes(scene, lay, (num, fr[0], fr[3], fr[4]), sizes[num], mats) \
            if lay else None
        patches[num] = [got] if got is not None else []
    if not patches:
        return 0

    def under(num, px):
        import numpy as np
        h, w = px.shape[:2]
        base = bpy.data.images.get(_base_name(scene, num))
        if base is not None and tuple(base.size) == (w, h):
            b = np.empty(w * h * 4, dtype=np.float32)
            base.pixels.foreach_get(b)
            px[..., :3] = b.reshape(h, w, 4)[..., :3]  # (alpha, holes and all, stays as it is)
            return
        if base is not None:  # the tile changed size: start again from what it shows
            bpy.data.images.remove(base)
        base = bpy.data.images.new(_base_name(scene, num), w, h, alpha=True)
        base.pixels.foreach_set(px.ravel())
        base.use_fake_user = True
        base.pack()

    art._paint_tiles(img, patches, under)
    art.refresh_material(scene)
    return len(patches)


# ---------------------------------------------------------------- editing
def show(scene):
    """Lay every stroke out on the flat layout to be edited, and take the
    ink off the paper meanwhile (so it isn't seen twice)."""
    st = scene.popup
    obj = ink_object(scene)
    if editing(scene):
        return obj
    frames, _of = _frames(scene)
    for la in obj.data.layers:
        dr = _drawing(la, scene)
        _at, vals = _tiles(dr)
        for i, s in enumerate(dr.strokes):
            fr = frames.get(vals[i])
            if fr is None:  # its piece is gone: left as it is (marked, to be kept so)
                if vals[i] > 0:
                    _at.data[i].value = -vals[i]
                continue
            for p in s.points:
                p.position = _rest(Vector(p.position), fr)
    lay = st.layout
    obj.matrix_world = lay.matrix_world.copy() if lay is not None else Matrix.Identity(4)
    scene["pop_ink_editing"] = True
    update_paper(scene)  # (bare paper while the strokes are out)
    obj.hide_viewport = False
    obj.hide_select = False
    obj.hide_set(False)
    return obj


def absorb(scene):
    """Take the strokes back from the layout: each point onto the paper
    under it, strokes split where they run onto another piece, points off
    the paper left out. Then redraw the paper. Returns (strokes kept, points
    left out)."""
    obj = ink_object(scene, create=False)
    if obj is None or not editing(scene):
        return 0, 0
    frames, of = _frames(scene)
    paper = art._Paper(scene)
    lay = scene.popup.layout
    Li = lay.matrix_world.inverted() if lay is not None else Matrix.Identity(4)
    kept = dropped = 0
    for la in obj.data.layers:
        W = Li @ obj.matrix_world @ la.matrix_local
        dr = _drawing(la, scene)
        _at, vals = _tiles(dr)
        new, tiles = [], []
        for _i, t_was, pts, attrs, cyc in _read(dr, vals, lambda t: True):
            if t_was < 0:  # on a piece that's gone: kept as it was
                new.append((pts, attrs, cyc))
                tiles.append(-t_was)
                continue
            segs, prev = [], None
            for r, rad, op, col in pts:
                k, on, nrm = paper.panel_at(W @ r)
                near = k is not None and (on - W @ r).length <= art.REACH_MM * paper.unit
                num = of.get(paper.piece[k]) if near else None
                if num is None:
                    dropped += 1
                    prev = None
                    continue
                if prev != num:
                    segs.append((num, []))
                home = _home(on + nrm * (art.OFFSET_MM * paper.unit), frames[num])
                segs[-1][1].append((home, rad, op, col))
                prev = num
            for num, seg in segs:
                new.append((seg, attrs, cyc and len(segs) == 1))
                tiles.append(num)
        dr.remove_strokes()
        art.put_strokes(dr, new)
        at, _vals = _tiles(dr)
        if tiles:
            at.data.foreach_set("value", tiles)
        kept += len(new)
    obj.matrix_world = Matrix.Identity(4)
    obj.hide_viewport = True
    obj.hide_select = True
    del scene["pop_ink_editing"]
    update_paper(scene)
    return kept, dropped
