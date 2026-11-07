"""v0.68: zig-zag folds (Birmingham 45-48) and multiple quadrilaterals (57),
walls on angled sticking strips with every crease square to their bottoms;
and the v0.67 follow-ups (V-fold on top, arch shapes, the M-fold) are in
test_v67."""
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

svg = os.path.join(tempfile.mkdtemp(), "t.svg")


def feet_clear(model, uid):
    """Nothing of it below either page, at any opening."""
    worst = 0.0
    for name in model.order:
        p = model.panels[name]
        if p.kind != "panel" or not name.startswith(f"Link{uid}."):
            continue
        for t in model.samples:
            _, _, nl, nr = model.dirs(t)
            for q in [v3(c) for poly in p.polys for c in poly]:
                w_ = p.asm(t) @ q
                worst = min(worst, w_.dot(nl), w_.dot(nr))
    return worst


# ---- zig-zag folds (Birmingham 45-48)
for faces in ("30", "25, 20", "20, 15, 15"):
    st.mechs.clear()
    assert bpy.ops.popup.add(kind="ZIGZAG") == {"FINISHED"}
    z = st.mechs[0]
    z.faces = faces
    model = build.rebuild(sc, force=True)
    assert not st.warnings, (faces, st.warnings)
    u = z.uid
    n = len(faces.split(","))
    walls = [k for k in model.panels if k.startswith(f"Link{u}.Z") and
             model.panels[k].kind == "panel"]
    assert len(walls) == 2 * n + 2, walls  # two glued end walls and the faces
    # every crease stays square to the bottom edges: the walls' up edges
    # are all parallel, at every opening
    for t in (170.0, 120.0, 60.0, 15.0):
        ups = [(model.panels[k].asm(t).to_3x3() @ Vector((0, 1, 0))).normalized()
               for k in walls]
        assert min(a_.dot(ups[0]) for a_ in ups) > 0.9999, t
    # the faces meet: each crease where both its walls say
    for t in (150.0, 90.0, 30.0):
        for i in range(len(walls) - 1):
            a_, b_ = model.panels[f"Link{u}.Z{i}"], model.panels[f"Link{u}.Z{i + 1}"]
            x = model.panels[f"Link{u}.Z{i + 1}"].polys[0][0][0]
            pa = a_.asm(t) @ Vector((x, 40.0, 0))
            pb = b_.asm(t) @ Vector((x, 40.0, 0))
            assert (pa - pb).length < 0.02, (faces, t, i, (pa - pb).length)
    assert feet_clear(model, u) > -0.6, feet_clear(model, u)
    assert shut_spread(model) < 3.0, shut_spread(model)
    e = rig_error()
    assert e < 0.05, e
    assert bpy.ops.popup.export_svg(filepath=svg) == {"FINISHED"}
    print("zig-zag", faces, round(e, 4))

# pointing back, strips the other way: the walls' bottoms cut to clear
z.faces, z.jut, z.phi_l = "30", "BACK", 60.0
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
assert feet_clear(model, z.uid) > -0.6
assert rig_error() < 0.05

# ---- multiple quadrilaterals (Birmingham 57)
st.mechs.clear()
assert bpy.ops.popup.add(kind="QUADS") == {"FINISHED"}
q_ = st.mechs[0]
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
u = q_.uid
P = model.panels
for k in ("K0", "K5", "SL0", "SR0", "F0", "F1"):
    assert f"Link{u}.{k}" in P, k
# the side piece's corner and the front's ends meet, opening by opening
for t in (160.0, 100.0, 40.0, 10.0):
    sr = P[f"Link{u}.SR0"]
    x_c = sr.polys[0][1][0]
    c1 = sr.asm(t) @ Vector((x_c, 20.0, 0))
    f1 = P[f"Link{u}.F1"]
    c2 = f1.asm(t) @ Vector((f1.polys[0][1][0], 20.0, 0))
    assert (c1 - c2).length < 0.05, (t, (c1 - c2).length)
# the quadrilateral balances: B to C worked out from the rest
d = q_.to_dict()
ad = float(d["faces"].split(",")[0])
bc = ad + q_.q_side - q_.width
assert abs(P[f"Link{u}.SR0"].polys[0][1][0] - P[f"Link{u}.SR0"].polys[0][0][0] - bc) < 0.01
assert feet_clear(model, u) > -0.6
assert shut_spread(model) < 3.0, shut_spread(model)
e = rig_error()
assert e < 0.05, e
assert bpy.ops.popup.export_svg(filepath=svg) == {"FINISHED"}
# strips the other way
q_.phi_l = 60.0
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
assert rig_error() < 0.05
print("multiple quadrilaterals", round(e, 4))
