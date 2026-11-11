"""v0.22/0.23: the roof's lengths answer their sliders (a ridge too long to
fit the shut card is warned about, not quietly trimmed), and its twin upside
down, the valley floor, mirrors it exactly. V-folds can cut the background
away above their glue lines."""
# families: roofs, vfolds
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
from mathutils import Vector  # noqa: E402

import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

W, H = 148.5, 210.0
STAGE = dict(W=W, H=H, hold="SYM", tmax=120.0)
R = dict(type="ROOF", uid=7, label="roof", y=145, phi_l=100, alpha_l=70, glue=150, height=70,
         tab=6, tab_side="IN", level=True, host=0)


def span(m, n, t=120.0):
    p = m.panels[n]
    M = p.asm(t)
    pts = [M @ Vector((q[0], q[1], 0)) for poly in p.polys for q in poly]
    return [(min(getattr(v, a) for v in pts), max(getattr(v, a) for v in pts)) for a in "xyz"]


# ---- lengths answer their sliders
tips = []
for h in (40.0, 60.0, 80.0):
    m = Model(STAGE, [dict(R, height=h)])
    m.check_fit()
    assert not m.warnings, (h, m.warnings)
    c, *_rest, P3 = m.crease("VFold7", 120.0)
    tips.append((P3 + h * c).z)  # how far the ridge's tip reaches into the stage
assert tips[0] < tips[1] < tips[2], tips
m = Model(STAGE, [dict(R, height=120.0)])
assert any("sticks out of the closed card by" in w for w in m.warnings), m.warnings
assert span(m, "VFold7.HalfL")[2][1] > 115.0  # built as asked, warned
short = Model(STAGE, [dict(R, glue=80.0)])
assert short.roofs[7]["eaves"] == 80.0
print("roof lengths answer their sliders")

# ---- the valley floor is the roof upside down
m1 = Model(STAGE, [R])
m2 = Model(STAGE, [dict(R, valley=True, y=H - 145)])
assert not m2.warnings, m2.warnings
for n in ("VFold7.HalfL", "VFold7.HalfR", "Page.L"):
    a, b = span(m1, n), span(m2, n)
    assert abs(a[0][0] - b[0][0]) < 0.05 and abs(a[2][1] - b[2][1]) < 0.05, (n, a, b)
    assert abs(a[1][0] - (H - b[1][1])) < 0.05 and abs(a[1][1] - (H - b[1][0])) < 0.05, (n, a, b)
print("valley floor mirrors the roof")

# ---- in Blender: the stage menu offers both
addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert bpy.ops.popup.add(kind="ROOF", variant="VALLEY") == {"FINISHED"}
v = st.mechs[-1]
assert v.valley and v.label.startswith("Valley floor")
assert bpy.ops.popup.build() == {"FINISHED"}
model = build.make_model(sc)[0]
assert "VFold%d.HalfL" % v.uid in model.panels, model.warnings
import json  # noqa: E402
assert str(v.uid) in json.loads(st.rig["pop_meta"])["roofs"]
addon.unregister()
print("V22 OK")
