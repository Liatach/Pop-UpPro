"""v0.67: V-folds glued away from the spine (Birmingham 18-20), V-folds on
top of V-folds (21-22) and the bite/tab sculpting creases (12-15)."""
# families: vfolds
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
from popup_pro import build, export_svg  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def rig_error():
    rig, card = st.rig, st.card
    if rig.animation_data:
        rig.animation_data.action = None
    model, lay = build.make_model(sc)
    me = card.data
    at = me.attributes["pop_panel"]
    s = 1 / st.mm_per_unit
    t0 = rig["pop_close"]
    worst = 0.0
    for t in (0.0, 47.0, 90.0, 150.0, 180.0):
        rig["pop_open"] = t
        rig.update_tag()
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        ev = card.evaluated_get(dg).data
        real = t0 + t * (180 - t0) / 180
        for poly in me.polygons:
            name = model.order[at.data[poly.index].value]
            P = lay["prints"][model.panels[name].piece].inverted()
            for vi in poly.vertices:
                q = P @ (me.vertices[vi].co / s)
                worst = max(worst, (ev.vertices[vi].co / s - model.point(name, q, real)).length)
    return worst


def shut_spread(model):
    nr = model.panels["Page.R"].asm(0.5).to_3x3() @ Vector((0, 0, 1))
    d = [(p.asm(0.5) @ v3(q)).dot(nr) for p in model.panels.values() for poly in p.polys
         for q in poly]
    return max(d) - min(d)



from popup_pro.core.geom import poly_area  # noqa: E402

# ---- glued away from the spine: tabs start a way out, the piece arches between
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
v = st.mechs[0]
v.y, v.height, v.glue = 60.0, 60.0, 40.0
v.glue_from = 15.0
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
u = v.uid
P = model.panels
for side in "LR":
    tab = P[f"VFold{u}.Tab{side}"]
    half = P[f"VFold{u}.Half{side}"]
    # the tab starts 15 mm out along the crease line on the page
    pts = [tab.asm(180.0) @ v3(q) for q in tab.polys[0]]
    near = min(math.hypot(p.x, p.y - 60.0) for p in pts)
    assert abs(near - 15.0) < 0.5, (side, near)
    # the half's spine end is cut away: nothing of it reaches the page there
    hp = [half.asm(180.0) @ v3(q) for q in half.polys[0]]
    assert len(half.polys[0]) >= 5, half.polys[0]
assert shut_spread(model) < 2.0, shut_spread(model)
e = rig_error()
assert e < 0.05, e
print("glued away from the spine:", round(e, 4))

# uneven: each side its own distance
v.symmetric = False
v.glue_from_r = 25.0
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
assert shut_spread(model) < 2.0
assert rig_error() < 0.05
print("uneven glued from")

# the cut's shape, and uneven sides with the angles still symmetric
v.symmetric = True
v.arch_uneven = True
v.glue_r, v.glue_from, v.glue_from_r, v.arch = 30.0, 12.0, 20.0, 18.0
for how in ("STRAIGHT", "ROUND", "SQUARE", "POINTED"):
    v.arch_shape = how
    model = build.rebuild(sc, force=True)
    assert not st.warnings, (how, st.warnings)
    d = v.to_dict()
    assert d["glue_r"] == 30.0 and d["glue_from_r"] == 20.0 and d["phi_r"] == d["phi_l"]
    hl = model.panels[f"VFold{u}.HalfL"]
    area = sum(abs(poly_area(q)) for q in hl.polys)
    # nothing left inside the arch: the crease is clear up to its top
    for q in hl.polys:
        for x, y in q:
            assert not (abs(x) < 1e-6 and y < 18.0 - 1e-6), (how, q)
    assert shut_spread(model) < 2.0
    e = rig_error()
    assert e < 0.05, (how, e)
    print(" cut", how, round(area), "mm2")

# ---- a V-fold on top of a V-fold: the lifting piece's top cut to a point,
# its own tabs (A) under the top piece
st.mechs.clear()
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
a = st.mechs[0]
model = build.rebuild(sc, force=True)
area0 = sum(abs(poly_area(q)) for q in model.panels[f"VFold{a.uid}.HalfL"].polys)
assert bpy.ops.popup.add(kind="VFOLD", host=a.uid, fold="V", variant="TOP") == {"FINISHED"}
b = st.mechs[-1]
assert b.host_uid == a.uid and b.vside == "V" and b.on_top
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
P = model.panels
assert f"VFold{a.uid}.HalfL" in model.top_cut and f"VFold{a.uid}.HalfR" in model.top_cut
assert f"VFold{b.uid}.TabL" not in P and f"VFold{b.uid}.TabR" not in P
for side in "LR":
    tab = P[f"VFold{b.uid}.TopTab{side}"]
    assert tab.piece == P[f"VFold{a.uid}.Half{side}"].piece  # (printed on the lifting piece)
    assert tab.parent == f"VFold{b.uid}.Half{side}"  # (stuck under the top piece)
area1 = sum(abs(poly_area(q)) for q in P[f"VFold{a.uid}.HalfL"].polys)
assert area1 < area0 - 20.0, (area0, area1)  # the corners cut off
# the top piece sits at the very top of the crease, whatever its Position says
b.y = 5.0
model = build.rebuild(sc, force=True)
top = model.panels[f"VFold{a.uid}.HalfL"].asm(120.0) @ Vector((0.0, a.height, 0.0))
vp = model.panels[f"VFold{b.uid}.HalfL"].asm(120.0) @ Vector((0.0, 0.0, 0.0))
assert (top - vp).length < 0.05, (top, vp)
assert shut_spread(model) < 3.0, shut_spread(model)
e = rig_error()
assert e < 0.05, e


def crease_elev(model, t=180.0):
    H = model.panels[f"VFold{b.uid}.HalfL"]
    d = (H.asm(t) @ Vector((0, 10, 0)) - H.asm(t) @ Vector((0, 0, 0))).normalized()
    n = model.panels["Page.R"].asm(t).to_3x3() @ Vector((0, 0, 1))
    return 90.0 - math.degrees(math.acos(max(-1.0, min(1.0, d.dot(n)))))


# the top piece lies flatter as its angle grows
el = []
for C in (60.0, 70.0, 80.0):
    b.top_piece = C
    model = build.rebuild(sc, force=True)
    el.append(crease_elev(model))
assert el[0] > el[1] > el[2], el
svg = os.path.join(tempfile.mkdtemp(), "t.svg")
assert bpy.ops.popup.export_svg(filepath=svg) == {"FINISHED"}
print("V-fold on top, tabs A: point cut", round(area0), "->", round(area1), "mm2; top piece",
      [round(x) for x in el], "degrees up;", round(e, 4))

# ---- the M-fold (Birmingham 28-29): halves glued as a V-fold's to a bend in
# their glue lines; past it crease D, a little panel E, crease H and an outer
# panel glued along the line's outer part (v0.70)
st.mechs.clear()
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
mf = st.mechs[0]
mf.shape = "M"
mf.y, mf.height = 60.0, 60.0
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
P = model.panels
u = mf.uid
for side in "LR":
    pg = "Page.L" if side == "L" else "Page.R"
    assert P[f"VFold{u}.Tab{side}"].parent == pg
    # glued on the printed side of its page (both of them)
    Mt = P[pg].asm(90.0).inverted() @ P[f"VFold{u}.Tab{side}"].asm(90.0)
    assert all((Mt @ v3(q)).z > 0.0 for q in P[f"VFold{u}.Tab{side}"].polys[0]), side
    assert P[f"VFold{u}.Outer{side}"].parent == pg
    assert P[f"VFold{u}.OuterTab{side}"].parent == pg
    assert P[f"VFold{u}.E{side}"].parent == f"VFold{u}.Half{side}"
# the halves meet along the centre crease at every opening
for t in (179.0, 140.0, 90.0, 45.0, 10.0, 1.0):
    a_, b_ = P[f"VFold{u}.HalfL"].asm(t), P[f"VFold{u}.HalfR"].asm(t)
    for y in (0.0, 60.0):
        gap = (a_ @ Vector((0.0, y, 0.0)) - b_ @ Vector((0.0, y, 0.0))).length
        assert gap < 0.05, (t, y, gap)
# open, the halves stand like a V-fold with their edges down on the page;
# the outer panels stand up too
n = P["Page.R"].asm(180.0).to_3x3() @ Vector((0, 0, 1))
top = P[f"VFold{u}.HalfR"].asm(180.0) @ Vector((0.0, 60.0, 0.0))
assert top.dot(n) > 20.0, top
assert max((P[f"VFold{u}.OuterR"].asm(180.0) @ v3(q)).dot(n)
           for q in P[f"VFold{u}.OuterR"].polys[0]) > 10.0
assert shut_spread(model) < 3.0, shut_spread(model)
e = rig_error()
assert e < 0.05, e
# its centre crease takes a V-fold like any other
assert bpy.ops.popup.add(kind="VFOLD", host=u, fold="V") == {"FINISHED"}
kid = st.mechs[-1]
kid.y, kid.height, kid.glue = 25.0, 20.0, 15.0
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
assert f"VFold{kid.uid}.HalfL" in model.panels
assert rig_error() < 0.05
assert bpy.ops.popup.export_svg(filepath=svg) == {"FINISHED"}
print("M-fold:", round(e, 4), "with a V-fold on its crease")
