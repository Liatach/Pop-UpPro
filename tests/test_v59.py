"""v0.59: Draw Anywhere. Grease Pencil strokes drawn freely on the folded card
or the flat layout, across folds, are put on the panels they were drawn on
when you're done: cut where they cross a fold, so each part rides with its
panel (and prints on its piece)."""
import os
import sys
import tempfile

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


# ---- across the spine, on the folded card part open
set_open(90.0)
path = across("Page.L", "Page.R")
obj = draw(path)
made, dropped = art.place_free(sc)
assert made == 2 and dropped == 0, (made, dropped)
(sl, ll), (sr, lr) = strokes_on(obj, "Page.L"), strokes_on(obj, "Page.R")
assert len(sl) == 1 and len(sr) == 1
wl, wr = world_of(obj, ll, sl[0]), world_of(obj, lr, sr[0])
assert (wl[-1] - wr[0]).length < 0.05 * mm, "the two halves meet on the fold"
assert (wl[0] - path[0]).length < 0.05 * mm and (wr[-1] - path[-1]).length < 0.05 * mm
assert not len(art._drawing_of(art.free_layer(sc)[1], sc).strokes), "the loose layer is emptied"
print("across the spine: cut on the fold, each half on its page")

# it bends with the card: at other openings every point is still on the paper
for t in (30.0, 150.0, 179.0):
    set_open(t)
    for (ss, ly) in (strokes_on(obj, "Page.L"), strokes_on(obj, "Page.R")):
        d = off_paper(world_of(obj, ly, ss[0]))
        assert d < 0.5, (t, d)
print("it bends with the card as it opens")

# ---- across a V-fold's crease
set_open(100.0)
vfl, vfr = "VFold1.HalfL", "VFold1.HalfR"
obj = draw(across(vfl, vfr))
made, dropped = art.place_free(sc)
assert made == 2 and dropped == 0, (made, dropped)
assert len(strokes_on(obj, vfl)[0]) == 1 and len(strokes_on(obj, vfr)[0]) == 1
for t in (40.0, 160.0):
    set_open(t)
    for p in (vfl, vfr):
        ss, ly = strokes_on(obj, p)
        assert off_paper(world_of(obj, ly, ss[0])) < 0.5
print("across a V-fold's crease, and it stays on its halves")

# ---- on the flat layout: it lands on the folded card too
set_open(90.0)
lay = st.layout
lme = lay.data
vals = [0] * len(lme.polygons)
lme.attributes["pop_panel"].data.foreach_get("value", vals)
fi = next(i for i, v in enumerate(vals) if names[v] == "Page.R")
f = lme.polygons[fi]
c = lay.matrix_world @ f.center
n = (lay.matrix_world.to_3x3() @ f.normal).normalized()
pts = [c + Vector((0.0, k * 2.0 * mm, 0.0)) + n * 0.25 * mm for k in range(-3, 4)]
before = len(strokes_on(obj, "Page.R")[0])
obj = draw(pts)
made, dropped = art.place_free(sc)
assert made == 1 and dropped == 0, (made, dropped)
ss, ly = strokes_on(obj, "Page.R")
assert len(ss) == before + 1
assert off_paper(world_of(obj, ly, ss[-1])) < 0.5
print("drawn on the flat layout, it's on the folded card")

# ---- points off the paper are left out; a stroke wholly off it vanishes
far = [Vector((500.0, 500.0, 500.0)) * mm + Vector((k, 0, 0)) * mm for k in range(5)]
obj = draw(far)
made, dropped = art.place_free(sc)
assert made == 0 and dropped == 5, (made, dropped)
print("off the paper: left out")

# ---- Done Drawing places them; they print
obj = draw(across("Page.L", "Page.R"))
assert bpy.ops.popup.done_drawing() == {"FINISHED"}
assert not len(art._drawing_of(art.free_layer(sc)[1], sc).strokes)
out = os.path.join(tempfile.mkdtemp(), "card.svg")
files = export_svg.export(sc, out)
svg = open(files[0]).read()
assert "sketch" in svg
assert bpy.ops.popup.draw_anywhere() == {"FINISHED"}
print("v0.59 OK")
