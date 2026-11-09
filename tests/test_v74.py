"""v0.74: the collar's free corners slide one inside the other, its end
curling out of the way (no slits); a railing (battlements optional) on the
collar; the collar upside down as a tapered top; Erase the Paper back in the
Artwork panel."""
import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, export_svg, live  # noqa: E402
from popup_pro.core.geom import v3, poly_area  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
svg = os.path.join(tempfile.mkdtemp(), "t.svg")


def warns():
    return [w for w in st.warnings.split("\n") if w]


def faces_in_mesh(prefix):
    bpy.ops.popup.build()
    names = [p["name"] for p in live.meta(st.rig)["panels"]]
    me = st.card.data
    vals = [0] * len(me.polygons)
    me.attributes["pop_panel"].data.foreach_get("value", vals)
    have = set(vals)
    missing = [n for i, n in enumerate(names) if n.startswith(prefix) and i not in have]
    assert not missing, missing


def tower(**kw):
    st.mechs.clear()
    assert bpy.ops.popup.add(kind="TUBE") == {"FINISHED"}
    t = st.mechs[-1]
    t.y, t.x, t.depth, t.height = 60.0, 30.0, 40.0, 25.0
    t.front = t.back = 30.0
    assert bpy.ops.popup.add(kind="BOX", host=t.uid, fold="KFL") == {"FINISHED"}
    m = st.mechs[-1]
    m.height = m.depth = 18.0
    m.width = 60.0
    m.collar = True
    m.collar_below, m.collar_width, m.collar_slope = 14.0, 10.0, 65.0
    for k, v in kw.items():
        setattr(m, k, v)
    build.rebuild(sc, force=True)
    return m.uid


def cross(model, na, nb, t):
    """How far na's polygon reaches through nb's plane, where it's over nb
    (signed: + on the far side from na's own seam side); max over its
    points."""
    pa, pb = model.panels[na], model.panels[nb]
    Ma, Mb = pa.asm(t), pb.asm(t)
    Mbi = Mb.inverted()
    o, n = Mb.translation, (Mb.to_3x3() @ Vector((0, 0, 1))).normalized()
    return [((Ma @ v3(q)) - o).dot(n) for poly in pa.polys for q in poly]


# ---- sliding free corners: a gap of a mm or two, the end curling
uid = tower()
assert not warns(), warns()
model = build.make_model(sc)[0]
curls = [n for n in model.panels if n.startswith(f"VFold{uid}c") and n.endswith("Curl")]
assert len(curls) == 2, curls
for c in curls:
    p = model.panels[c]
    assert p.parent == c[:-4] and model.fold_kind[frozenset((c, p.parent))] == "skip"
    angs = [abs(math.degrees(p.hinge.fn(t))) for t in (180.0, 179.0, 150.0, 110.0, 70.0,
                                                         30.0, 1.0)]
    assert angs[0] < 0.5 and angs[-1] < 0.5, angs  # flat open, flat shut
    assert max(angs) > 10.0, angs  # it curls on the way
# no slits: each floor one piece of paper (plus its curl)
for n in model.panels:
    if n.startswith(f"VFold{uid}c") and n.endswith(("HalfL", "HalfR")):
        assert len(model.panels[n].polys) == 1, (n, len(model.panels[n].polys))
# the free corners a gap apart when open: the floors' ends 1.5 mm apart
fr = model.collar_free[uid]
for iP in {i for _, i in fr}:
    a_, b_ = [n for n, i in fr if i == iP]
    pa, pb = model.panels[a_], model.panels[b_]
    pts_a = [pa.asm(180.0) @ v3(q) for q in pa.polys[0]]
    if a_ + "Curl" in model.panels:
        pc = model.panels[a_ + "Curl"]
        pts_a += [pc.asm(180.0) @ v3(q) for q in pc.polys[0]]
    pts_b = [pb.asm(180.0) @ v3(q) for q in pb.polys[0]]
    if b_ + "Curl" in model.panels:
        pc = model.panels[b_ + "Curl"]
        pts_b += [pc.asm(180.0) @ v3(q) for q in pc.polys[0]]
    dmin = min((p - q).length for p in pts_a for q in pts_b)
    assert 1.0 < dmin < 2.5, dmin
faces_in_mesh(f"VFold{uid}c")
export_svg.export(sc, svg)
print("free corners: a 1.5 mm gap, one end curling inside the other")

# ---- a railing with battlements on the collar
uid = tower(collar_rail=7.0, collar_crenels=True)
assert not warns(), warns()
model = build.make_model(sc)[0]
rails = [n for n in model.panels if n.startswith(f"VFold{uid}c") and n.endswith("Rail")]
assert len(rails) == 4, rails
for r_ in rails:
    p = model.panels[r_]
    assert len(p.polys) > 2  # battlements: a band and merlons
    host = model.placed[uid]
    for t in (179.0, 120.0, 60.0):
        S, l, r, Y, nl, nr = host.dirs(t)
        n = (p.asm(t).to_3x3() @ Vector((0, 0, 1))).normalized()
        assert abs(n.dot(Y)) < 0.02, (r_, t, n.dot(Y))  # upright like the walls
faces_in_mesh(f"VFold{uid}c")
export_svg.export(sc, svg)
print("railing with battlements, upright as it folds")

# ---- the collar upside down: a tapered top
uid = tower(collar_dir="IN", collar_width=8.0, collar_slope=35.0, collar_rail=6.0)
assert not warns(), warns()
model = build.make_model(sc)[0]
host = model.placed[uid]
S, l, r, Y, nl, nr = host.dirs(180.0)
ctr = S + 9.0 * (l + r)
for n in model.panels:
    if n.startswith(f"VFold{uid}c") and n.endswith(("HalfL", "HalfR")):
        p = model.panels[n]
        pts = [p.asm(180.0) @ v3(q) for q in p.polys[0]]
        # leaning in: its far edge nearer the middle than its hinge
        hinge = min(pts, key=lambda q: q.dot(Y))
        far = max(pts, key=lambda q: q.dot(Y))
        d_h = (hinge - ctr - (hinge - ctr).dot(Y) * Y).length
        d_f = (far - ctr - (far - ctr).dot(Y) * Y).length
        assert d_f < d_h, (n, d_f, d_h)
m = next(x for x in st.mechs if x.uid == uid)
m.roof = "POINTED"
build.rebuild(sc, force=True)
assert any("tapered top takes the roof" in w for w in warns()), warns()
print("tapered top")

# ---- Erase the Paper is back (Texture Paint with an erasing brush)
assert hasattr(bpy.types, "POPUP_OT_erase_paper")
from popup_pro import ui  # noqa: E402
assert hasattr(ui, "_erase_section")
st.mechs.clear()
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
build.rebuild(sc, force=True)
bpy.ops.popup.build()
assert bpy.ops.popup.erase_paper() == {"FINISHED"}
from popup_pro.ops import erasing  # noqa: E402
assert bpy.context.mode == "PAINT_TEXTURE" and erasing(sc)
assert bpy.ops.popup.done_painting() == {"FINISHED"} and bpy.context.mode == "OBJECT"
print("erase the paper")

addon.unregister()
print("V74 OK")
