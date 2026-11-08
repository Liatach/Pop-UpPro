"""v0.57: towers in a tube's inside corners (Birmingham's parallel castle),
the walls raised behind them, and a pyramid roof that still folds flat: two
V-folds, one in each of the tower's side corners."""
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

# ---- the Castle: a box-shaped tube with a roofed tower in every inside corner
assert bpy.ops.popup.add(kind="TUBE", variant="CASTLE") == {"FINISHED"}
tube = st.mechs[0]
towers = [m for m in st.mechs if m.kind == "BOX"]
assert tube.kind == "TUBE" and tube.x == tube.front == tube.back
assert sorted(m.wall for m in towers) == sorted(("KFL", "KFR", "KBR", "KBL"))
assert all(m.host_uid == tube.uid and m.roof == "POINTED" for m in towers)
assert all(m.height == m.depth and m.width > tube.height for m in towers)
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
print("castle: a tube and four roofed towers, no warnings")

# the walls rise to each tower's top over its width, nowhere else
top = towers[0].y + towers[0].width
wall = model.panels[f"Tube{tube.uid}.FL_"]
vs = [q[1] for poly in wall.polys for q in poly]
assert abs(max(vs) - top) < 1e-6 and abs(min(vs)) < 1e-6
a = towers[0].height
for poly in wall.polys:  # raised only within a tower's width of either corner
    if max(q[1] for q in poly) > tube.height + 1e-6:
        x0, x1 = min(q[0] for q in poly), max(q[0] for q in poly)
        assert x1 <= a + 1e-6 or x0 >= tube.depth - a - 1e-6, (x0, x1)
print("walls raised behind the towers")

# the roof: closed into a pyramid open flat, parting along its hips as the
# card shuts, and flat (in the walls' planes) shut
for m in towers:
    tips = {}
    for t in (model.tmax, 120.0, 60.0, 5.0):
        ps = []
        for k in (0, 1):
            p = model.panels[f"VFold{m.uid}r{k}.HalfL"]
            ps.append(p.asm(t) @ Vector((0.0, max(q[1] for q in p.polys[0]), 0.0)))
        tips[t] = (ps[0] - ps[1]).length
    assert tips[model.tmax] < 1e-3, tips
    assert tips[120.0] < tips[60.0] < tips[5.0], tips
nr = model.panels["Page.R"].asm(0.5).to_3x3() @ Vector((0, 0, 1))
d = [(p.asm(0.5) @ v3(q)).dot(nr) for p in model.panels.values() for poly in p.polys
     for q in poly]
assert max(d) - min(d) < 3.0, max(d) - min(d)
print("pyramid roofs: closed open flat, part along the hips, lie flat shut")

# ---- the rig follows the model (towers and roofs are tabulated)
rig, card = st.rig, st.card
if rig.animation_data:
    rig.animation_data.action = None
model, lay = build.make_model(sc)
me = card.data
at = me.attributes["pop_panel"]
s = 1 / st.mm_per_unit
t0 = rig["pop_close"]
worst = 0.0
for t in (0.0, 47.3, 90.0, 151.7, 180.0):
    rig["pop_open"] = t
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    real = t0 + t * (180 - t0) / 180
    for poly in me.polygons:
        name = model.order[at.data[poly.index].value]
        D = model.shown(name, real) @ lay["prints"][model.panels[name].piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s)) * s
                                ).length / s)
print("rig error", round(worst, 4))
assert worst < 0.05, worst
out = os.path.join(tempfile.mkdtemp(), "castle.svg")
export_svg.export(sc, out)
print("rig matches; exports")

# ---- what doesn't fit is said, not built
card_d = st.card_dict()


def one(**over):
    t = dict(uid=1, label="Keep", type="TUBE", y=60.0, x=30.0, depth=60.0, height=40.0,
             front=30.0, back=30.0, front_style="OUT", back_style="OUT", tab=10.0, host=0,
             roof="NONE", tab_side="IN")
    b = dict(uid=2, label="Tower", type="BOX", style="GLUED", y=0.0, width=55.0,
             height=12.0, depth=12.0, slant=0.0, peaks=1, tab=8.0, host=1, wall="KFL",
             fold="A", roof="POINTED", roof_height=10.0, lines=[])
    t.update({k[2:]: v for k, v in over.items() if k.startswith("t_")})
    b.update({k[2:]: v for k, v in over.items() if k.startswith("b_")})
    return Model(card_d, [t, b])


M = one()
assert not M.warnings and "VFold2r0.HalfL" in M.panels, M.warnings
M = one(b_depth=16.0)  # not square: no roof
assert any("square tower" in w for w in M.warnings) and "VFold2r0.HalfL" not in M.panels
# (since v0.72 a square tower's pyramid roof sits in a hexagon's corners too)
M = one(t_front=40.0, t_back=40.0)
assert "VFold2r0.HalfL" in M.panels, M.warnings
M = one(b_style="CUT")
assert any("only glued box folds" in w for w in M.warnings)
M = one(b_type="VFOLD", b_phi_l=60.0, b_phi_r=60.0, b_alpha_l=70.0, b_alpha_r=70.0,
        b_glue=20.0, b_shape="QUAD")
assert any("only glued box folds" in w for w in M.warnings)
M = one(b_roof="NONE")  # a plain tower
assert not M.warnings and "VFold2r0.HalfL" not in M.panels
print("no roof on an oblong tower; hexagon corners; only box folds in the corners")

# ---- towers in the corners of a tube you already have
bpy.ops.popup.remove()  # (any one: then start a fresh tube)
while st.mechs:
    st.active = 0
    bpy.ops.popup.remove()
assert bpy.ops.popup.add(kind="TUBE") == {"FINISHED"}
tb = st.mechs[0]
tb.x = tb.front = tb.back = 30.0
st.active = 0
assert bpy.ops.popup.add(kind="BOX", host=tb.uid, variant="TOWERS") == {"FINISHED"}
assert len(st.mechs) == 5 and all(m.wall.startswith("K") for m in st.mechs[1:])
assert bpy.ops.popup.add(kind="BOX", host=tb.uid, fold="KFR") == {"FINISHED"}
assert st.mechs[-1].wall == "KFR" and st.mechs[-1].host_uid == tb.uid
print("v0.57 OK")
