"""v0.21: the background folding in set by a few numbers (Ceiling: hanging
or peaked roof; Floor), and line sets the paper can't fold to fail fast."""
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
from mathutils import Vector  # noqa: E402

import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402
from popup_pro.props import card_shape_lines  # noqa: E402

W, H = 148.5, 210.0
STAGE = dict(W=W, H=H, hold="SYM", tmax=120.0)


def ridge_y(m, psi, y0):
    roof = [n for n in m.order if n.startswith("Card.Fold") and "join" not in m.panels[n].label]
    left = min(roof, key=lambda n: sum(q[0] for poly in m.panels[n].polys for q in poly))
    M = m.panels[left].asm(m.tmax)
    a = math.radians(psi)
    return (M @ Vector((-60 * math.sin(a), y0 + 60 * math.cos(a), 0)) -
            M @ Vector((0, y0, 0))).normalized().y


# ---- peaked roof by numbers: level ridge at full opening
for tmax, slope in ((120.0, -10.0), (180.0, -10.0), (120.0, -30.0)):
    lines = card_shape_lines(W, H, tmax, "PEAK", 42.0, slope)
    assert [ln["kind"] for ln in lines] == ["CREASE", "JOIN", "CUT"]
    m = Model(dict(STAGE, tmax=tmax, lines=lines), [])
    assert not m.warnings, (tmax, slope, m.warnings)
    p = lines[1]["pts"]
    psi = math.degrees(math.atan2(p[0][0] - p[1][0], p[1][1] - p[0][1]))
    assert abs(ridge_y(m, psi, H - 42.0)) < 0.12, (tmax, slope, ridge_y(m, psi, H - 42.0))
print("peaked roof by numbers: ridge level")

# ---- hanging ceiling and floor
m = Model(dict(STAGE, lines=card_shape_lines(W, H, 120.0, "HANG", 50.0, 30.0,
                                             floor=True, rise=50.0, fslope=30.0)), [])
assert not m.warnings, m.warnings
assert len([n for n in m.order if n.startswith("Card.Fold")]) == 4
print("hanging ceiling and floor")

# ---- a cut that doesn't follow the fold: quick, and never hangs
y0 = 168.0
base = card_shape_lines(W, H, 120.0, "PEAK", H - y0, -10.0)[:2]
for cx in (-5.0, 3.0, -20.0):
    t = time.time()
    m = Model(dict(STAGE, lines=base + [dict(kind="CUT", mirror=False,
                                             pts=[(cx, y0), (cx, H + 5)])]), [])
    assert time.time() - t < 15.0, (cx, time.time() - t)
print("off-centre cuts fail fast")

# ---- in Blender
addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
st.hold = "SYM"
st.ceiling = "PEAK"
assert abs(st.ceiling_slope + 10.0) < 1e-6  # each style starts at its natural slope
assert [ln["kind"] for ln in st.card_dict()["lines"]] == ["CREASE", "JOIN", "CUT"]
st.ceiling = "HANG"
assert abs(st.ceiling_slope - 30.0) < 1e-6
st.floor = True
assert len(st.card_dict()["lines"]) == 2
assert bpy.ops.popup.build() == {"FINISHED"}
model = build.make_model(sc)[0]
assert len([n for n in model.order if n.startswith("Card.Fold")]) == 4, model.warnings
st.ceiling, st.floor = "NONE", False
assert not st.card_dict()["lines"]
addon.unregister()
print("V21 OK")
