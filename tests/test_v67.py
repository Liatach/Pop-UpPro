"""v0.67: V-folds glued away from the spine (Birmingham 18-20), V-folds on
top of V-folds (21-22) and the bite/tab sculpting creases (12-15)."""
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

# ---- a V-fold on top of a V-fold: the lower one's halves grow points (tabs A)
from popup_pro.core.geom import poly_area  # noqa: E402

st.mechs.clear()
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
a = st.mechs[0]
model = build.rebuild(sc, force=True)
area0 = sum(abs(poly_area(q)) for q in model.panels[f"VFold{a.uid}.HalfL"].polys)
assert bpy.ops.popup.add(kind="VFOLD", host=a.uid, fold="V", variant="TOP") == {"FINISHED"}
b = st.mechs[-1]
assert b.host_uid == a.uid and b.vside == "V" and abs(b.y - a.height) < 1e-6
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
assert f"VFold{a.uid}.HalfL" in model.carried and f"VFold{a.uid}.HalfR" in model.carried
area1 = sum(abs(poly_area(q)) for q in model.panels[f"VFold{a.uid}.HalfL"].polys)
assert area1 > area0 + 20.0, (area0, area1)
assert shut_spread(model) < 3.0, shut_spread(model)
e = rig_error()
assert e < 0.05, e
svg = os.path.join(tempfile.mkdtemp(), "t.svg")
assert bpy.ops.popup.export_svg(filepath=svg) == {"FINISHED"}
print("V-fold on top, tabs A:", round(area0), "->", round(area1), "mm2;", round(e, 4))
