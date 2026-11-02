"""v0.59 (reworked in v0.60): Draw Anywhere. Grease Pencil strokes drawn
freely on the folded card or the flat layout, across folds, are painted into
the paper itself when you're done: flat on each piece, so they show folded
and flat alike and print with the art."""
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
from popup_pro import art, export_svg, live  # noqa: E402

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


def strokes_on(obj, panel):
    lay = next((l for l in obj.data.layers if l.name == panel), None)
    if lay is None:
        return []
    fr = lay.current_frame() or lay.frames[0]
    return list(fr.drawing.strokes), lay


def world_of(obj, layer, stroke):
    pb = rig.pose.bones[layer.parent_bone]
    M = rig.matrix_world @ pb.matrix @ layer.matrix_parent_inverse @ layer.matrix_local
    return [M @ Vector(p.position) for p in stroke.points]


def off_paper(pts):
    bvh = surface()[0]
    return max(bvh.find_nearest(w)[3] for w in pts) / mm




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


def inked(before, after):
    """Tiles whose pixels got darker, and how many pixels."""
    got = {}
    for n, a in after.items():
        b = before.get(n)
        if b is None:
            b = np.ones_like(a)
        dark = (b[..., :3].mean(-1) - a[..., :3].mean(-1)) > 0.2
        if dark.any():
            got[n] = int(dark.sum())
    return got


ink = bpy.data.materials.get("Pop-up Ink")

# ---- across the spine, on the folded card part open: painted on the card's tile
set_open(90.0)
bpy.ops.popup.add_art()
before = art_px()
obj = draw(across("Page.L", "Page.R"))
made, dropped = art.paint_free(sc)
assert made == 1 and dropped == 0, (made, dropped)  # the pages are one piece: one stroke
after = art_px()
got = inked(before, after)
card_tile = 1001 + live.meta(rig)["pieces"]["Card"]["slot"]
assert list(got) == [card_tile] and got[card_tile] > 50, got
assert not len(art._drawing_of(art.free_layer(sc)[1], sc).strokes), "the loose layer is emptied"
# no sketch layers made: it's in the paper now
assert not any(l.parent is not None for l in obj.data.layers)
print("across the spine: painted into the card's own art")

# where on the tile: around the spine (the middle), at the height drawn
px = after[card_tile]
dark = (before[card_tile][..., :3].mean(-1) - px[..., :3].mean(-1)) > 0.2
ys, xs = np.nonzero(dark)
h, w = dark.shape
H = st.card_dict()["H"]
y_mm = (ys.mean() + 0.5) / h * H
assert abs(xs.mean() / w - 0.5) < 0.15, xs.mean() / w
assert abs(y_mm - 105.0) < 20.0, y_mm  # (the face centres the path runs through)
print("in the right place on the tile")

# ---- across a V-fold's crease: on the V-fold's own tile
set_open(100.0)
before = after
obj = draw(across("VFold1.HalfL", "VFold1.HalfR"))
made, dropped = art.paint_free(sc)
assert made == 1 and dropped == 0, (made, dropped)
after = art_px()
vf_tile = 1001 + live.meta(rig)["pieces"]["VFold1"]["slot"]
got = inked(before, after)
assert list(got) == [vf_tile], got
print("across a V-fold's crease: painted on the V-fold")

# ---- from a page onto the V-fold: two pieces of paper, painted on both
before = after
obj = draw(across("Page.R", "VFold1.HalfR") if False else
           across("VFold1.HalfL", "VFold1.HalfR")[:6] + across("Page.L", "Page.R")[-6:])
made, dropped = art.paint_free(sc)
assert made == 2, made
print("onto another piece of paper: painted on each")

# ---- on the flat layout: painted the same way
set_open(90.0)
lay = st.layout
lme = lay.data
vals = [0] * len(lme.polygons)
lme.attributes["pop_panel"].data.foreach_get("value", vals)
fi = max((i for i, v in enumerate(vals) if names[v] == "Page.R"),
         key=lambda i: lme.polygons[i].area)
f = lme.polygons[fi]
c = lay.matrix_world @ f.center
n = (lay.matrix_world.to_3x3() @ f.normal).normalized()
pts = [c + Vector((k * 2.0 * mm, 0.0, 0.0)) + n * 0.25 * mm for k in range(-5, 6)]
before = art_px()
obj = draw(pts)
made, dropped = art.paint_free(sc)
assert made == 1 and dropped == 0, (made, dropped)
assert list(inked(before, art_px())) == [card_tile]
print("drawn on the flat layout: painted on the card")

# ---- points off the paper are left out
far = [Vector((500.0, 500.0, 500.0)) * mm + Vector((k, 0, 0)) * mm for k in range(5)]
obj = draw(far)
made, dropped = art.paint_free(sc)
assert made == 0 and dropped == 5, (made, dropped)
print("off the paper: left out")

# ---- Put on the Paper and Done Drawing do it; a new ink to draw with
before = art_px()
obj = draw([w + Vector((0.0, 30.0 * mm, 0.0)) for w in across("Page.L", "Page.R")])
assert bpy.ops.popup.ink_paper() == {"FINISHED"}
assert inked(before, art_px())
obj = draw(across("Page.L", "Page.R"))
assert bpy.ops.popup.done_drawing() == {"FINISHED"}
assert not len(art._drawing_of(art.free_layer(sc)[1], sc).strokes)
k = len(obj.data.materials)
assert bpy.ops.popup.ink_new() == {"FINISHED"} and len(obj.data.materials) == k + 1
assert bpy.ops.popup.draw_anywhere() == {"FINISHED"}
out = os.path.join(tempfile.mkdtemp(), "card.svg")
export_svg.export(sc, out)
print("v0.60 OK")
