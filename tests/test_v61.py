"""v0.61: Add never remembers its options between uses (a plain tube after
Add Castle was a castle too), and pyramids stand on other folds, like tubes."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False

# ---- Add's options are never remembered (the interface would reuse them)
props = bpy.ops.popup.add.get_rna_type().properties
for name in ("host", "fold", "side", "variant"):
    assert props[name].is_skip_save, name
assert bpy.ops.popup.add(kind="TUBE", variant="CASTLE") == {"FINISHED"}
n = len(st.mechs)
assert bpy.ops.popup.add(kind="TUBE") == {"FINISHED"}
assert len(st.mechs) == n + 1 and st.mechs[-1].label.startswith("Tube")
print("a plain tube after a castle is a plain tube")
while st.mechs:
    st.active = 0
    bpy.ops.popup.remove()


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}
    return st.mechs[-1].uid


def M(u):
    return next(m for m in st.mechs if m.uid == u)


# ---- pyramids on a box fold, a V-fold's crease and half, and a tube's wall
b = add("BOX")
M(b).y, M(b).width, M(b).height, M(b).depth = 20, 60, 45, 45
v = add("VFOLD")
M(v).y, M(v).glue, M(v).height = 120, 45, 45
t = add("TUBE")
M(t).y = 150
M(t).x = M(t).front = M(t).back = 20
M(t).depth = 30
pyr = [add("PYRAMID", host=b, fold="A"), add("PYRAMID", host=v, fold="V"),
       add("PYRAMID", host=v, fold="FR"), add("PYRAMID", host=t, fold="WL")]
for u, h in zip(pyr, (b, v, v, t)):
    assert M(u).host_uid == h
    assert M(u).depth < 60 and M(u).x < 20  # sized to fit its fold
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
assert all(f"Pyramid{u}" in model.pieces for u in pyr)
print("pyramids stand on box folds, V-folds and tube walls, no warnings")

rig, card = st.rig, st.card
if rig.animation_data:
    rig.animation_data.action = None
model, lay = build.make_model(sc)
me = card.data
at = me.attributes["pop_panel"]
s = 1 / st.mm_per_unit
t0 = rig["pop_close"]
worst = 0.0
for ang in (0.0, 47.3, 90.0, 151.7, 180.0):
    rig["pop_open"] = ang
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    real = t0 + ang * (180 - t0) / 180
    for poly in me.polygons:
        name = model.order[at.data[poly.index].value]
        D = model.shown(name, real) @ lay["prints"][model.panels[name].piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s)) * s
                                ).length / s)
assert worst < 0.05, worst
nr = model.panels["Page.R"].asm(0.5).to_3x3() @ Vector((0, 0, 1))
d = [(p.asm(0.5) @ v3(q)).dot(nr) for p in model.panels.values() for poly in p.polys
     for q in poly]
assert max(d) - min(d) < 3.0, max(d) - min(d)
print("the rig follows them, and the card shuts flat")
print("v0.61 OK")
