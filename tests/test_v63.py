"""v0.63: the double 45's top piece keeps its halves apart (no passing
through itself on the way open), and a jack in the box goes on top of any
V-fold."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False

# ---- the double 45: the top piece's halves never cross, opening to shut
assert bpy.ops.popup.add(kind="DOUBLE45") == {"FINISHED"}
m = st.mechs[0]
model = build.rebuild(sc, force=True)
u, Lt, hw = m.uid, 0.5 * m.depth, 0.5 * m.width


def half(sgn, t, nx=10, ny=40, skip=2):
    V, F = [], []
    for j in range(ny + 1):
        y = sgn * Lt * j / ny
        for i in range(nx + 1):
            far = abs(y) > Lt / 2
            nm = f"D45{u}." + ({1: "TopF", -1: "TopH"} if far else {1: "GF", -1: "GH"})[sgn]
            V.append(model.point(nm, (-hw + 2 * hw * i / nx, y), t))
    for j in range(skip, ny - 1):  # (not the rows meeting at G: they share it)
        for i in range(nx):
            a = j * (nx + 1) + i
            F.append((a, a + 1, a + nx + 2, a + nx + 1))
    return BVHTree.FromPolygons(V, F)


prev, jump = None, 0.0
for t in range(5, 180, 2):
    assert not half(1, t).overlap(half(-1, t)), t
    gf = model.panels[f"D45{u}.GF"].asm(t).to_3x3() @ Vector((0, 1, 0))
    gh = model.panels[f"D45{u}.GH"].asm(t).to_3x3() @ Vector((0, -1, 0))
    o = math.degrees(gf.angle(gh))  # how far the fold at G is open
    assert t < 40 or o > 3.0, (t, o)
    if prev is not None:
        jump = max(jump, abs(o - prev) / 2.0)
    prev = o
assert jump < 2.0, jump  # no sudden snap at G
print("double 45: the top piece's halves stay apart, G opens smoothly")

# ---- a jack on top of a V-fold you already have, of other shapes
while st.mechs:
    st.active = 0
    bpy.ops.popup.remove()
for phi, alpha, glue, height in ((60.0, 90.0, 40.0, 60.0), (50.0, 70.0, 45.0, 70.0),
                                 (45.0, 60.0, 45.0, 70.0)):
    assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
    vf = st.mechs[-1]
    vf.phi_l, vf.alpha_l, vf.glue, vf.height = phi, alpha, glue, height
    st.active = len(st.mechs) - 1
    assert bpy.ops.popup.add(kind="JACK") == {"FINISHED"}
    jk = st.mechs[-1]
    assert jk.host_uid == vf.uid and jk.on_crease and \
        sum(1 for x in st.mechs if x.kind == "VFOLD") == len(st.mechs) // 2
    model = build.rebuild(sc, force=True)
    bad = [w for w in st.warnings.split("\n") if w and jk.label in w]
    assert not bad, (alpha, bad)
    assert f"Jack{jk.uid}.HeadL" in model.panels
    for t in (150.0, 90.0, 30.0):
        for side in ("L", "R"):
            Pg = model.panels[f"Page.{side}"].asm(t)
            n = Pg.to_3x3() @ Vector((0, 0, 1))
            p = model.panels[f"Jack{jk.uid}.Chest{side}"]
            assert min((p.asm(t) @ v3(q) - Pg.to_translation()).dot(n)
                       for poly in p.polys for q in poly) > -0.5
    # move it away to make room for the next
    vf.y = 30.0 + 60.0 * (len(st.mechs) // 2 - 1)
print("jack in the box: on top of V-folds of other shapes, sized to fit")

# too big for its V-fold: said, not left hanging
jk.height = 80.0
model = build.rebuild(sc, force=True)
assert any("run off the V-fold" in w for w in model.warnings), model.warnings
print("v0.63 OK")
