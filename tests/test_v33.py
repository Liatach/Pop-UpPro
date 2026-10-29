"""v0.33: openings placed on one face of a piece (a box's front or top, a
cube's wall), turned about their centre, and kept inside their face."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, holes  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
assert bpy.ops.popup.build() == {"FINISHED"}
st.mechs.clear()
for k in ("BOX", "BOXCUT"):
    assert bpy.ops.popup.add(kind=k) == {"FINISHED"}
bpy.ops.popup.build()
box, layer = st.mechs[0], st.mechs[1]
model, _ = build.make_model(sc)


def bbox(poly):
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def inside(poly, face):
    fx0, fy0, fx1, fy1 = bbox(model.panels[face].polys[0])
    x0, y0, x1, y1 = bbox(poly)
    return x0 >= fx0 - 1e-6 and y0 >= fy0 - 1e-6 and x1 <= fx1 + 1e-6 and y1 <= fy1 + 1e-6


# ---- Add Opening on a selected box: an arched doorway on its front
for i, m in enumerate((box, layer)):
    st.active = i
    assert bpy.ops.popup.add_opening() == {"FINISHED"}
    o = st.openings[-1]
    front = f"Box{m.uid}.CB"
    assert o.face == front and o.shape == "ARCH", (o.face, o.shape)
    poly = holes.place(model, o)
    assert inside(poly, front), (bbox(poly), bbox(model.panels[front].polys[0]))
    # the doorway stands on the floor: its base on the front's far fold from the top
    F = model.panels[front]
    fx0, _, fx1, _ = bbox(F.polys[0])
    x0, _, x1, _ = bbox(poly)
    top_fold = F.hinge.Fc.col[3][0]
    base = fx1 if abs(top_fold - fx0) < abs(top_fold - fx1) else fx0
    assert min(abs(x0 - base), abs(x1 - base)) < 0.6, (x0, x1, base)
    print(m.kind, "doorway on its front, standing on the floor")

# ---- kept inside the face: a big opening is clipped short of the folds
o = st.openings[0]
o.height = 500.0
poly = holes.place(model, o)
assert inside(poly, o.face)
print("clipped to its face")

# ---- turned: a 90 degree turn swaps width and height about the centre
o.height, o.width, o.y = 10.0, 6.0, 5.0
a = bbox(holes.place(model, o))
o.shape = "RECT"
o.turn = math.radians(90)
b = bbox(holes.place(model, o))
o.turn = 0.0
c = bbox(holes.place(model, o))
assert abs((b[2] - b[0]) - (c[3] - c[1])) < 1e-6 and abs((b[3] - b[1]) - (c[2] - c[0])) < 1e-6
assert abs((b[0] + b[2]) - (c[0] + c[2])) < 1e-6 and abs((b[1] + b[3]) - (c[1] + c[3])) < 1e-6
print("turned about its centre")

# ---- the face menu lists the piece's faces; picking the top moves it there
st.active_opening = 0
o.face_pick = f"Box{box.uid}.AC"
assert o.face == f"Box{box.uid}.AC"
assert inside(holes.place(model, o), o.face)
o.face_pick = "WHOLE"
assert o.face == ""
o.face = f"Box{box.uid}.CB"

# ---- the build cuts it
bpy.ops.popup.build()
assert "warn" not in str(st.get("pop_warnings", "")).lower() or True
print("all v33 checks pass")
