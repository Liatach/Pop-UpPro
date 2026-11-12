"""v0.49: the 45 degree fold's structural uses (Birmingham 80, 81): the
Platform (legs either side of the fold, top folding in a valley above it,
on or off the centre, propped by 45 degree folds) and the Rising Sheet (a
sheet half way between the pages, a 45 degree fold on each face)."""
# families: folds45
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
from popup_pro.core.model import Model  # noqa: E402

addon.register()

# --- the model: valley straight above the fold at the leg height, legs
# square to the line between the pages, braces flat gussets at full open
for hold in ("SYM", "RIGHT"):
    for depth_r in (0.0, 45.0):
        m = dict(uid=1, type="PLATFORM", label="P", host=0, width=60, height=35, depth=25,
                 depth_r=depth_r, brace="BOTH", brace_size=15, tab=10, y=70)
        M = Model(dict(W=148.5, H=210, hold=hold), [m])
        assert not M.warnings, M.warnings
        B, C = 25.0, depth_r or 25.0
        for t in (10.0, 60.0, 120.0, 180.0):
            L, R = M.panels["Page.L"].asm(t), M.panels["Page.R"].asm(t)
            l = L.to_3x3() @ Vector((-1, 0, 0))
            r = R.to_3x3() @ Vector((1, 0, 0))
            Y0 = Vector((0.0, 70.0, 0.0))
            A = M.panels["Plat1.TopL"].asm(t) @ Vector((35 + B, 0, 0)) - Y0
            A2 = M.panels["Plat1.TopR"].asm(t) @ Vector((35 + B, 0, 0)) - Y0
            assert (A - A2).length < 1e-4, (A - A2).length
            # the valley: 35 mm from the spine, on the line between the pages
            assert abs(A.length - 35.0) < 1e-4, (t, A)
            assert abs(A.normalized().dot(l) - A.normalized().dot(r)) < 1e-4, t
            # each top half parallel to its page
            tl = M.panels["Plat1.TopL"].asm(t).to_3x3() @ Vector((1, 0, 0))
            assert abs(abs(tl.dot(l)) - 1.0) < 1e-6
            # the right leg's foot on the right page, C out
            F = M.panels["Plat1.LegR"].asm(t) @ Vector((2 * 35 + B + C, 0, 0)) - Y0
            assert (F - C * r).length < 1e-4, (t, F, C * r)
        for k in range(4):
            c, uL, uR, ok, P3 = M.crease(f"VFold1b{k}", 179.9)
            assert ok and abs(c.y) < 0.05, (k, c)  # a gusset square across the fold
            c, *_ = M.crease(f"VFold1b{k}", 60.0)
            assert abs(c.y) > 0.3, (k, c)  # folding away as the card shuts
print("platform geometry ok")

m = dict(uid=1, type="RISER", label="S", host=0, width=70, height=80, brace_size=20, tab=12,
         y=60)
M = Model(dict(W=148.5, H=210), [m])
assert not M.warnings, M.warnings
for t in (30.0, 90.0, 180.0):
    L, R = M.panels["Page.L"].asm(t), M.panels["Page.R"].asm(t)
    l = L.to_3x3() @ Vector((-1, 0, 0))
    r = R.to_3x3() @ Vector((1, 0, 0))
    u = M.panels["Rise1.Sheet"].asm(t).to_3x3() @ Vector((1, 0, 0))
    assert abs(u.dot(l) - u.dot(r)) < 1e-6, t
# both braces' tabs on their own panels
for n in M.order:
    p = M.panels[n]
    if p.kind == "tab" and p.parent == "Rise1.Sheet":
        R_ = M.panels[p.parent].asm(90).inverted() @ p.asm(90)
        for poly in p.polys:
            for c in poly:
                q = R_ @ Vector((c[0], c[1], 0))
                assert -0.01 <= q.y <= 70.01, (n, q)
print("rising sheet geometry ok")

# --- in Blender: the rig follows, it closes, things stand on the platform
sc = bpy.context.scene
st = sc.popup
bpy.ops.popup.build()
for kind in ("PLATFORM", "RISER"):
    st.mechs.clear()
    bpy.ops.popup.add(kind=kind)
    p = st.mechs[-1]
    if kind == "PLATFORM":
        p.depth_r = 40.0
        st.active = 0
        bpy.ops.popup.add(kind="BOX", host=p.uid)
        bx = st.mechs[-1]
        bx.y, bx.width, bx.height, bx.depth = 90.0, 20.0, 12.0, 12.0
    build.rebuild(sc, force=True)
    assert not st.warnings, st.warnings
    model, lay = build.make_model(sc)
    rig, card = st.rig, st.card
    if rig.animation_data:
        rig.animation_data.action = None
    assert rig["pop_close"] < 20.0, rig["pop_close"]
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
    print(kind, "rig error", round(worst, 4))
    assert worst < 0.05, worst
    out = os.path.join(tempfile.mkdtemp(), "card.svg")
    export_svg.export(sc, out)
print("v49 ok")
