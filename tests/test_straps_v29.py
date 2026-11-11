"""v0.29: a slanted strap (creases still parallel to the spine, the strip
across at an angle), asymmetric V-folds with their own glue length each
side, rectangular cubes, mechanisms outside a cube's or tube's walls, and
the default camera from Kim's file."""
# families: straps, vfolds, cubes, scene
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import scene_setup  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

CARD = dict(W=148.5, H=210.0, hold="SYM")


def P(m, n, q, t):
    return m.panels[n].asm(t) @ Vector((q[0], q[1], 0))


def centre(m, prefix, t):
    pts = []
    for n in m.order:
        if n.startswith(prefix):
            p = m.panels[n]
            M = p.asm(t)
            pts += [M @ Vector((q[0], q[1], 0)) for poly in p.polys for q in poly]
    return sum(pts, Vector()) / len(pts)


# ---- slanted strap: flat when open, its gullies offset diagonally
for style in ("GLUED", "CUT"):
    for sl in (25.0, -25.0):
        B = dict(type="BOX", style=style, uid=1, label="strap", y=80, width=40, height=35,
                 depth=35, tab=10, slant=sl)
        m = Model(CARD, [B])
        m.check_fit()
        assert not m.warnings, (style, sl, m.warnings)
        k = math.tan(math.radians(sl))
        pts = [P(m, n, q, 179.9) for n in ("Box1.AC", "Box1.CB")
               for poly in m.panels[n].polys for q in poly]
        assert max(abs(v.z) for v in pts) < 0.5  # it lies flat
        for x in (-35.0, 35.0):  # each gully's lowest point moved by k x
            lo = min(v.y for v in pts if abs(v.x - x) < 0.5)
            assert abs(lo - (80 + k * x)) < 0.05, (style, sl, x, lo)
# and a cube stands in a slanted gully
B = dict(type="BOX", style="GLUED", uid=1, label="strap", y=80, width=40, height=35,
         depth=35, tab=10, slant=25.0)
m = Model(CARD, [B, dict(type="CUBE", uid=2, label="cube", y=80 - math.tan(math.radians(25)) * 35
                         + 5, size=15, height=15, tab=6, host=1, fold="A", lid="PEAK",
                         tab_side="IN")])
m.check_fit()
assert not m.warnings, m.warnings
print("slanted strap: flat when open, gullies offset diagonally")

# ---- asymmetric V-fold: its own glue length each side
V = dict(type="VFOLD", uid=1, label="V", y=50, phi_l=40, phi_r=75, alpha_l=95, alpha_r=60,
         glue=60, glue_r=30, height=70, tab=10, tab_side="IN")
m = Model(CARD, [V])
m.check_fit()
assert not m.warnings, m.warnings
for side, g in (("L", 60), ("R", 30)):
    far = max(math.hypot(*q) for poly in m.panels[f"VFold1.Tab{side}"].polys for q in poly)
    assert abs(far - g) < 0.5, (side, far)
print("asymmetric V-fold: 60 mm glued on the left, 30 on the right")

# ---- rectangular cubes: closed at every opening; lids only on squares
for wB, wC in ((40, 25), (25, 45)):
    C = dict(type="CUBE", uid=2, label="cube", y=50, size=wB, size_r=wC, height=30, tab=8,
             lid="NONE", tab_side="IN")
    m = Model(CARD, [C])
    m.check_fit()
    assert not m.warnings, m.warnings
    s4 = 2 * (wB + wC)
    for t in (20, 60, 100, 140, 179):
        assert (P(m, "Cube2.A", (0, 0), t) - P(m, "Cube2.D", (s4, 0), t)).length < 1e-3
    # at full opening the base is a wB x wC rectangle
    a, b = P(m, "Cube2.B", (wC, 0), 179.9), P(m, "Cube2.C", (wC + wB + wC, 0), 179.9)
    f = P(m, "Cube2.B", (wC + wB, 0), 179.9)
    assert abs((a - f).length - wB) < 1e-3 and abs((b - f).length - wC) < 1e-3
    assert abs((a - f).normalized().dot((b - f).normalized())) < 1e-3
m = Model(CARD, [dict(C, lid="PEAK")])
assert any("square" in w for w in m.warnings) and "Cube2.LidL" not in m.panels
m = Model(CARD, [dict(C, size=40, size_r=40, lid="PEAK")])
assert not m.warnings and "Cube2.LidL" in m.panels  # a square still has its lid
print("rectangular cubes fold shut; lids stay on square ones")

# ---- outside a cube's or a tube's walls
Cu = dict(type="CUBE", uid=1, label="C", y=60, size=50, height=45, tab=8, lid="PEAK",
          tab_side="IN")
Tu = dict(type="TUBE", uid=1, label="T", y=60, x=25, depth=50, height=45, front=30, back=30,
          tab=10, front_style="OUT", back_style="OUT", tab_side="IN", roof="NONE")
kid = dict(type="CUBE", uid=2, label="k", size=13, height=13, tab=6, lid="PEAK",
           tab_side="IN", y=15, host=1)
for host in (Cu, Tu):
    for wall, sx in (("L", -1), ("R", 1)):
        m = Model(CARD, [host, dict(kid, wall=wall)])
        m.check_fit()
        assert not m.warnings, (host["type"], wall, m.warnings)
        c = centre(m, "Cube2", 150.0)
        assert sx * c.x > 10.0, (host["type"], wall, c)
        if host is Cu:  # outside the front wall it stands at
            inside = Vector((-sx * math.sqrt(0.5), math.sqrt(0.5), 0))
            assert (c - Vector((0, 60, 0))).dot(inside) < 0, (wall, c)
        else:  # beyond the tube's strip on that side
            assert abs(c.x) > 25.0, (wall, c)
print("cubes stand outside cube and tube walls")

# ---- the default camera: Kim's framing
addon.register()
sc = bpy.context.scene
st = sc.popup
assert bpy.ops.popup.build() == {"FINISHED"}
cam = bpy.data.objects[scene_setup.CAMERA]
assert abs(cam.location.y + 30.981) < 1e-3 and abs(cam.location.z - 30.296) < 1e-3
assert abs(math.degrees(cam.rotation_euler.x) - 58.82) < 1e-3
addon.unregister()
print("V29 OK")
