"""v0.69: V-fold family tidy-up (names, M-fold defaults, glued from on fans
and M-folds, zig-zag as a V-fold shape), lighter bottom cuts, hosts on
zig-zags and quadrilaterals, and V-fold on top as in Birmingham 21-22."""
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
from popup_pro import live  # noqa: E402

svg = os.path.join(tempfile.mkdtemp(), "t.svg")


def faces_in_mesh(prefix):
    """Every panel of a mechanism has paper in the built mesh."""
    bpy.ops.popup.build()
    meta = live.meta(st.rig)
    names = [p["name"] for p in meta["panels"]]
    me = st.card.data
    vals = [0] * len(me.polygons)
    me.attributes["pop_panel"].data.foreach_get("value", vals)
    have = set(vals)
    missing = [n for i, n in enumerate(names) if n.startswith(prefix) and i not in have]
    assert not missing, missing


# ---- shapes name themselves; an M-fold stands up by default
st.mechs.clear()
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
v = st.mechs[0]
v.shape = "M"
assert v.label == "M-fold 1" and v.alpha_l == 80.0 and v.m_d == 120.0, v.label
v.shape = "FAN"
assert v.label == "Fan 1"
v.label = "Tower"
v.shape = "TRI"
assert v.label == "Tower"  # (a name of its own is kept)

# ---- glued from, across the V-fold family
for shape in ("QUAD", "TRI", "FAN", "M"):
    st.mechs.clear()
    assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
    v = st.mechs[0]
    v.shape = shape
    model = build.rebuild(sc, force=True)
    a0 = sum(abs(poly_area(q)) for n in model.order if model.panels[n].kind == "panel"
             and n.startswith("VFold") for q in model.panels[n].polys)
    v.glue_from = 10.0
    model = build.rebuild(sc, force=True)
    assert not st.warnings, (shape, st.warnings)
    a1 = sum(abs(poly_area(q)) for n in model.order if model.panels[n].kind == "panel"
             and n.startswith("VFold") for q in model.panels[n].polys)
    assert a1 < a0 - 10.0, (shape, a0, a1)  # cut away near where it meets the page
    tl = model.panels[f"VFold{v.uid}.TabL"]
    near = min(math.hypot(*q) for q in tl.polys[0])
    assert near > 5.0, (shape, near)  # the tab starts out along its edge
    assert rig_error() < 0.05
    faces_in_mesh(f"VFold{v.uid}.")
    print("glued from:", shape)

# ---- the zig-zag is a V-fold shape, with clearer faces; its crease hosts
st.mechs.clear()
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
z = st.mechs[0]
z.shape = "ZIGZAG"
assert z.label == "Zig-zag 1" and z.phi_l == 120.0 and z.glue_from > 0
z.faces_n, z.face_w = 2, 22.0
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
walls = [n for n in model.order if n.startswith(f"Link{z.uid}.Z") and
         model.panels[n].kind == "panel"]
assert len(walls) == 6, walls
assert rig_error() < 0.05
faces_in_mesh(f"Link{z.uid}.")
assert bpy.ops.popup.add(kind="VFOLD", host=z.uid, fold="V") == {"FINISHED"}
kid = st.mechs[-1]
model = build.rebuild(sc, force=True)
assert f"VFold{kid.uid}.HalfL" in model.panels, st.warnings
assert rig_error() < 0.05
print("zig-zag shape, with a V-fold on its crease")

# ---- bottoms: cut lightly by default, less than cut to clear
st.mechs.clear()
assert bpy.ops.popup.add(kind="QUADS") == {"FINISHED"}
q_ = st.mechs[0]
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
light = sum(abs(poly_area(p_)) for n in model.order if n.startswith(f"Link{q_.uid}.")
            and model.panels[n].kind == "panel" for p_ in model.panels[n].polys)
q_.cut_bottoms = "CLEAR"
model = build.rebuild(sc, force=True)
clear = sum(abs(poly_area(p_)) for n in model.order if n.startswith(f"Link{q_.uid}.")
            and model.panels[n].kind == "panel" for p_ in model.panels[n].polys)
assert light > clear + 50.0, (light, clear)
q_.cut_bottoms = "NONE"
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
# and its back crease takes a stand-up
q_.cut_bottoms = "LIGHT"
build.rebuild(sc, force=True)
assert bpy.ops.popup.add(kind="STANDUP", host=q_.uid, fold="V") == {"FINISHED"}
model = build.rebuild(sc, force=True)
su = st.mechs[-1]
assert any(n.startswith(f"Stand{su.uid}") or (n.split(".")[0].endswith(str(su.uid)) and
           not n.startswith("Link")) for n in model.panels), st.warnings
print("bottoms: light", round(light), "clear", round(clear), "mm2")

# ---- V-fold on top: the top piece carries on below the join; a V-shaped
# top; a third piece on the second; every face built
st.mechs.clear()
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
a = st.mechs[0]
a.y, a.height, a.glue = 100.0, 70.0, 40.0
build.rebuild(sc, force=True)
assert bpy.ops.popup.add(kind="VFOLD", host=a.uid, fold="V", variant="TOP") == {"FINISHED"}
b = st.mechs[-1]
b.glue, b.height, b.top_below, b.top_piece = 30.0, 40.0, 20.0, 65.0
model = build.rebuild(sc, force=True)
hb = model.panels[f"VFold{b.uid}.HalfL"]
assert min(q[1] for q in hb.polys[0]) < -19.0  # (below the join)
assert rig_error() < 0.05
faces_in_mesh("VFold")
# a V-shaped top: the lifting piece's sides rise above its crease
b.top_angle, b.top_piece = 120.0, 150.0
model = build.rebuild(sc, force=True)
ha = model.panels[f"VFold{a.uid}.HalfL"]
assert max(q[1] for q in ha.polys[0]) > a.height + 5.0, ha.polys
faces_in_mesh("VFold")
# a third on the second
b.top_angle, b.top_piece = 50.0, 65.0
build.rebuild(sc, force=True)
assert bpy.ops.popup.add(kind="VFOLD", host=b.uid, fold="V", variant="TOP") == {"FINISHED"}
c = st.mechs[-1]
model = build.rebuild(sc, force=True)
assert f"VFold{b.uid}.HalfL" in model.top_cut and f"VFold{c.uid}.TopTabL" in model.panels
faces_in_mesh("VFold")
assert rig_error() < 0.05
assert bpy.ops.popup.export_svg(filepath=svg) == {"FINISHED"}
print("on top: below the join, V top, a third piece")
