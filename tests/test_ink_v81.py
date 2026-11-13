"""v0.81: ink layers. What Draw Anywhere draws is kept as Grease Pencil
strokes on hidden layers, and the paper's art is a picture drawn from them:
layers can be hidden, faded, reordered and removed, the strokes edited on
the flat layout, and the paper redrawn, with nothing baked in for good. The
strokes stay on their piece of paper when the layout moves."""
# families: drawing, paint, ui
import os
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import art, ink, live  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
st.mechs[0].y = 60.0
assert bpy.ops.popup.build() == {"FINISHED"}
rig, card = st.rig, st.card
if rig.animation_data:
    rig.animation_data.action = None
names = [p["name"] for p in live.meta(rig)["panels"]]
mm = 1.0 / st.mm_per_unit


def set_open(t):
    rig["pop_open"] = t
    rig.update_tag()
    bpy.context.view_layer.update()


def surface():
    """(BVH of the card as it stands, face -> panel name, mesh, world verts)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = card.evaluated_get(dg)
    me = ev.to_mesh()
    n0 = len(card.data.polygons)  # (Solid Paper's back shell comes after)
    vals = [0] * len(me.polygons)
    me.attributes["pop_panel"].data.foreach_get("value", vals)
    V = [card.matrix_world @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons][:n0]
    info = [(names[vals[i]], me.polygons[i].normal.copy(), tuple(me.polygons[i].vertices))
            for i in range(n0)]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons(V, faces), info, V


def across(a, b):
    """A path on the paper from the middle of a face of panel a, over their
    shared fold, to the middle of a face of panel b (world, just off it)."""
    bvh, info, V = surface()
    fa = [(n, f) for name, n, f in info if name == a]
    fb = [(n, f) for name, n, f in info if name == b]
    for na, f1 in fa:
        for nb, f2 in fb:
            sh = set(f1) & set(f2)
            if len(sh) >= 2:
                e = sum((V[i] for i in sh), Vector()) / len(sh)
                ca = sum((V[i] for i in f1), Vector()) / len(f1)
                cb = sum((V[i] for i in f2), Vector()) / len(f2)
                pts = [ca.lerp(e, k / 10) + na * 0.25 * mm for k in range(10)] + \
                      [e.lerp(cb, k / 10) + nb * 0.25 * mm for k in range(1, 11)]
                return pts
    raise AssertionError(f"no shared fold between {a} and {b}")


def draw(world_pts):
    obj, layer = art.free_layer(sc)
    dr = art._drawing_of(layer, sc)
    Wi = (obj.matrix_world @ layer.matrix_local).inverted()
    dr.add_strokes([len(world_pts)])
    s = dr.strokes[len(dr.strokes) - 1]
    for p, w in zip(s.points, world_pts):
        p.position = Wi @ w
        p.radius = 0.4 * mm
        p.opacity = 1.0
    return obj


def art_px():
    """{tile: pixels (h, w, 4)} of the paper's art, read from saved tiles."""
    img = bpy.data.images.get("Pop-up Art")
    if img is None:
        return {}
    d = tempfile.mkdtemp()
    img.filepath_raw = os.path.join(d, "a.<UDIM>.png")
    img.file_format = "PNG"
    img.save()
    out = {}
    for t in img.tiles:
        fn = os.path.join(d, f"a.{t.number}.png")
        im = bpy.data.images.load(fn)
        out[t.number] = np.array(im.pixels[:]).reshape(im.size[1], im.size[0], 4)
        bpy.data.images.remove(im)
    img.filepath = ""
    return out




def diff(a, b, num=1001):
    """How many pixels of a tile differ."""
    return int((np.abs(a[num][..., :3] - b[num][..., :3]).max(axis=2) > 0.02).sum())


def at(px, x_mm, y_mm, num=1001):
    """The card tile's colour at a place on the right page (mm from the fold, up the card)."""
    t = px[num]
    h, w = t.shape[:2]
    W, H = live.meta(rig)["W"], live.meta(rig)["H"]
    return t[int(y_mm / H * h), int((x_mm + W) / (2 * W) * w), :3]


def line(x0, y0, x1, y1, n=24):
    """World points along a line on the right page of the flat-open card."""
    return [card.matrix_world @ Vector(((x0 + (x1 - x0) * k / n) * mm,
                                        (y0 + (y1 - y0) * k / n) * mm, 0.25 * mm))
            for k in range(n + 1)]


def layer_strokes(la):
    dr = art._drawing_of(la, sc)
    _a, vals = ink._tiles(dr)
    return len(dr.strokes), vals


set_open(180.0)
assert not ink.layers(sc)
bare = None

# ---- a stroke drawn anywhere is kept, and the paper shows a picture of it
draw(line(30, 150, 80, 150))
made, dropped = art.paint_free(sc)
assert (made, dropped) == (1, 0), (made, dropped)
obj = ink.ink_object(sc, create=False)
assert obj is not None and obj.hide_viewport and obj.hide_render
assert [la.name for la in ink.layers(sc)] == ["Ink 1"]
n, vals = layer_strokes(ink.layers(sc)[0])
assert n == 1 and vals == [1001], (n, vals)
assert not len(art._drawing_of(art.free_layer(sc)[1], sc).strokes)  # (the loose layer is emptied)
one = art_px()
assert at(one, 55, 150).max() < 0.3 and at(one, 55, 120).min() > 0.8, at(one, 55, 150)
base = bpy.data.images.get("Pop-up Art Base 1001")
assert base is not None and base.packed_file is not None
print("a stroke is kept on Ink 1 and drawn on the paper")

# ---- hide it: the paper as it was before; show it: the same picture again
i0 = 0
assert bpy.ops.popup.ink_layer(action="SHOW", index=i0) == {"FINISHED"}
bare = art_px()
assert at(bare, 55, 150).min() > 0.8
assert bpy.ops.popup.ink_layer(action="SHOW", index=i0) == {"FINISHED"}
assert diff(art_px(), one) == 0
print("hidden and shown again: nothing is baked in")

# ---- a second layer in red, over the first; then under it
assert bpy.ops.popup.ink_layer(action="ADD") == {"FINISHED"}
assert bpy.ops.popup.ink_new() == {"FINISHED"}  # (a red ink, made active)
sk = art.ensure_sketch(sc)
red = len(sk.data.materials) - 1
d = draw(line(55, 120, 55, 180))
dr = art._drawing_of(art.free_layer(sc)[1], sc)
dr.strokes[len(dr.strokes) - 1].material_index = red
assert art.paint_free(sc) == (1, 0)
assert [la.name for la in ink.layers(sc)] == ["Ink 1", "Ink 2"]
assert layer_strokes(ink.layers(sc)[1])[0] == 1 and layer_strokes(ink.layers(sc)[0])[0] == 1
two = art_px()
c = at(two, 55, 150)
assert c[0] > 0.5 and c[0] - c[1] > 0.3, c  # red over black where they cross
assert at(two, 55, 170)[0] > 0.5 and at(two, 40, 150).max() < 0.3
assert bpy.ops.popup.ink_layer(action="DOWN", index=1) == {"FINISHED"}
assert [la.name for la in ink.layers(sc)] == ["Ink 2", "Ink 1"]
c = at(art_px(), 55, 150)
assert c.max() < 0.3, c  # black over red now
print("two layers, reordered: the paper is redrawn in their order")

# ---- a layer's opacity (Update Paper redraws)
black = next(la for la in ink.layers(sc) if la.name == "Ink 1")
black.opacity = 0.4
assert bpy.ops.popup.ink_update() == {"FINISHED"}
c = at(art_px(), 40, 150)
assert 0.35 < c.max() < 0.85, c
black.opacity = 1.0
assert bpy.ops.popup.ink_update() == {"FINISHED"}
assert at(art_px(), 40, 150).max() < 0.3

# ---- Edit Ink: the strokes out on the flat layout, the paper bare meanwhile
assert bpy.ops.popup.ink_edit() == {"FINISHED"}
assert ink.editing(sc) and not obj.hide_viewport
assert diff(art_px(), bare) == 0
dr = art._drawing_of(black, sc)
W = st.layout.matrix_world.inverted() @ obj.matrix_world @ black.matrix_local  # (on the layout)
zs = [(W @ Vector(p.position)).z / mm for p in dr.strokes[0].points]
ys = [(W @ Vector(p.position)).y / mm for p in dr.strokes[0].points]
# flat on the layout, just off it, still a level line
assert max(abs(z - 0.25) for z in zs) < 0.01 and max(ys) - min(ys) < 0.01, (zs[:2], ys[:2])
for p in dr.strokes[0].points:  # move the black line up the card by 25 mm
    p.position = Vector(p.position) + Vector((0, 25 * mm, 0))
assert bpy.ops.popup.ink_done() == {"FINISHED"}
assert not ink.editing(sc) and obj.hide_viewport
moved = art_px()
assert at(moved, 40, 175).max() < 0.3 and at(moved, 40, 150).min() > 0.8
assert at(moved, 55, 150)[0] > 0.5  # (the red line where it was)
assert layer_strokes(black) == (1, [1001])
# in and out again without touching anything: nothing shifts
assert bpy.ops.popup.ink_edit() == {"FINISHED"} and bpy.ops.popup.ink_done() == {"FINISHED"}
assert diff(art_px(), moved) == 0
print("edited on the flat layout and put back")

# ---- drawn on the folded card, across a fold onto another piece
set_open(90.0)
n_before = sum(layer_strokes(la)[0] for la in ink.layers(sc))


def on(panel, n=8):
    """World points along a short line inside a face of a panel, just off it."""
    _bvh, info, V = surface()
    nrm, f = next((nr, f) for name, nr, f in info if name == panel)
    cen = sum((V[i] for i in f), Vector()) / len(f)
    a_, b_ = cen.lerp(V[f[0]], 0.4), cen.lerp(V[f[1]], 0.4)
    return [a_.lerp(b_, k / n) + nrm * 0.25 * mm for k in range(n + 1)]


draw(on("Page.L") + on("VFold1.HalfR"))  # one stroke, from the page onto the V-fold
made, dropped = art.paint_free(sc)
assert made == 2 and dropped == 0, (made, dropped)  # split where the paper changes
gp = obj.data
tiles = set()
for la in ink.layers(sc):
    tiles.update(layer_strokes(la)[1])
vt = next(t for t in tiles if t != 1001)
assert len(tiles) == 2, tiles
folded = art_px()
assert diff(folded, moved, vt) > 20 and bpy.data.images.get(f"Pop-up Art Base {vt}") is not None
print(f"drawn across a fold on the folded card: kept on tiles 1001 and {vt}")

# ---- another mechanism moves the layout: the strokes stay on their pieces
assert bpy.ops.popup.add(kind="BOX") == {"FINISHED"}
st.mechs[-1].y = 150.0
assert bpy.ops.popup.build() == {"FINISHED"}
assert bpy.ops.popup.ink_update() == {"FINISHED"}
after = art_px()
assert diff(after, folded, vt) < 12, diff(after, folded, vt)
assert diff(after, folded, 1001) < 12

# ---- removing a layer takes its strokes off the paper
i_red = [la.name for la in ink.layers(sc)].index("Ink 2")
assert bpy.ops.popup.ink_layer(action="REMOVE", index=i_red) == {"FINISHED"}
gone = art_px()
assert at(gone, 55, 150).min() > 0.8 and at(gone, 40, 175).max() < 0.3
assert [la.name for la in ink.layers(sc)] == ["Ink 1"]

# ---- the panel shows the layers
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_stub import draw as draw_panel  # noqa: E402
from popup_pro import ui  # noqa: E402
log = draw_panel(ui.POPUP_PT_art)
acts = [(e[3].get("text"), e[3].get("icon")) for e in log if e[1] == "operator"
        and e[2][0] in ("popup.ink_edit", "popup.ink_update", "popup.ink_layer")]
assert any(e[1] == "label" and e[3].get("text") == "Ink Layers (1)" for e in log)
assert len(acts) >= 7, acts


# ---- v0.82: the colour in our panel is the one drawn with, and colours are remembered
from ui_stub import Layout  # noqa: E402
set_open(180.0)
assert bpy.ops.popup.draw_anywhere() == {"FINISHED"}
gpp = sc.tool_settings.gpencil_paint
if bpy.context.mode == "PAINT_GREASE_PENCIL" and gpp.brush is not None:
    gpp.color_mode = "VERTEXCOLOR"
    gpp.unified_paint_settings.use_unified_color = True  # (Draw mode doesn't use it)
    log = []
    ui._ink_colour(Layout(log), bpy.context)
    pick = [e for e in log if e[1] == "template_color_picker"]
    assert len(pick) == 1 and pick[0][2][0] == gpp.brush and pick[0][2][1] == "color", pick
    sw = [e[2][1] for e in log if e[1] == "prop" and e[2][0] == gpp.brush]
    assert sw[:2] == ["color", "secondary_color"], sw
    assert any(e[1] == "operator" and e[2][0] == "paint.brush_colors_flip" for e in log)
    assert any(e[1] == "template_ID" and e[2][1] == "palette" for e in log)
    print("the panel's colour is the brush's own, with a palette")
    # v0.81.2: a stroke drawn is noted at once, in the brush's colour;
    # Done Drawing is in Artwork (at the top), not in Creases, Cuts and Holes
    from popup_pro import history
    gpp.brush.color = (1.0, 0.5, 0.0)
    history._ink_drawn(bpy.context)  # (looks: nothing new yet)
    draw(line(20, 60, 60, 60))
    history._ink_drawn(bpy.context)
    c0 = tuple(st.colour_history.colors[0].color)
    assert abs(c0[0] - 1) < 0.01 and abs(c0[1] - 0.5) < 0.01 and c0[2] < 0.01, c0
    n = len(st.colour_history.colors)
    history._ink_drawn(bpy.context)  # (no new stroke: nothing noted)
    assert len(st.colour_history.colors) == n
    ops_in = lambda P: [e[2][0] for e in draw_panel(P) if e[1] == "operator"]  # noqa: E731
    a_ops = ops_in(ui.POPUP_PT_art)
    assert "popup.done_drawing" in a_ops and \
        a_ops.index("popup.done_drawing") < 3, a_ops[:6]
    assert "popup.done_drawing" not in ops_in(ui.POPUP_PT_openings)
    print("a stroke's colour is noted as it is drawn; Done Drawing is in Artwork")
else:
    print("(no Draw mode without a window: the panel's colour not checked here)")
draw(line(20, 40, 60, 40))
dr = art._drawing_of(art.free_layer(sc)[1], sc)
for p in dr.strokes[len(dr.strokes) - 1].points:
    p.vertex_color = (0.0, 0.2140, 1.0, 1.0)  # (linear: sRGB 0, 0.5, 1)
assert bpy.ops.popup.done_drawing() == {"FINISHED"}
pal = st.colour_history
assert pal is not None and len(pal.colors) >= 1
c0 = tuple(pal.colors[0].color)
assert abs(c0[0]) < 0.02 and abs(c0[1] - 0.5) < 0.02 and abs(c0[2] - 1.0) < 0.02, c0
log = []
ui._palettes(Layout(log), bpy.context, gpp)
assert [e[2][1] for e in log if e[1] == "template_palette"][0] == "colour_history"
c = at(art_px(), 40, 40)
assert c[2] > 0.8 and c[0] < 0.3, c  # (and it is on the paper, blue)
print("colours drawn with are remembered, the latest first")

addon.unregister()
print("V81 OK")
