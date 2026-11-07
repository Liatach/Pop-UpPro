"""v0.70: cylinders (Birmingham 68: a tube whose front or back curves round),
balconies (box folds on a tube's or cube's wall, or in front of a box, with a
railing), and the M-fold's crease E panels."""
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
from popup_pro import build, export_svg, live  # noqa: E402
from popup_pro.core.model import round_arc, ROUND_FMAX  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
svg = os.path.join(tempfile.mkdtemp(), "t.svg")


def faces_in_mesh(prefix):
    bpy.ops.popup.build()
    names = [p["name"] for p in live.meta(st.rig)["panels"]]
    me = st.card.data
    vals = [0] * len(me.polygons)
    me.attributes["pop_panel"].data.foreach_get("value", vals)
    have = set(vals)
    missing = [n for i, n in enumerate(names) if n.startswith(prefix) and i not in have]
    assert not missing, missing


def warns():
    return [w for w in st.warnings.split("\n") if w]


# ---- the curve: straight shut, a quarter circle open, facets keep their size
a = 25.0
L = 0.5 * math.pi * a
pts = round_arc(0.0, L, 8)
assert all(abs(x) < 1e-6 for x, y in pts) and abs(pts[-1][1] - L) < 1e-6
pts = round_arc(a, L, 8)
assert abs(pts[-1][0] - a) < 1e-6, pts[-1]
assert abs(pts[-1][1] - a) < 0.3, pts[-1]  # (eight facets round a quarter circle)
for x in (3.0, 10.0, 20.0, a):
    p = round_arc(x, L, 8)
    assert abs(p[-1][0] - x) < 1e-6
    for (x0, y0), (x1, y1) in zip(p, p[1:]):
        assert abs(math.hypot(x1 - x0, y1 - y0) - L / 8) < 1e-9
assert 0.70 < ROUND_FMAX < 0.75
print("round halves: straight shut, a quarter circle open, facets keep their width")

# ---- a cylinder: round front and back, named, half circles by default
st.mechs.clear()
assert bpy.ops.popup.add(kind="TUBE") == {"FINISHED"}
t = st.mechs[-1]
t.y, t.x, t.depth, t.height = 60.0, 25.0, 30.0, 50.0
t.front_style = "ROUND"
assert t.label.startswith("Tube")
t.back_style = "ROUND"
assert t.label.startswith("Cylinder"), t.label
assert abs(t.front - round(0.5 * math.pi * 25.0, 1)) < 0.05 and abs(t.back - t.front) < 0.05
build.rebuild(sc, force=True)
assert not warns(), warns()
model = build.make_model(sc)[0]
T = model.tubes[t.uid]
for ang in (2.0, 40.0, 90.0, 140.0, 180.0):
    p = model.tube_plan(t.uid, ang)
    assert abs(p["CF"][0]) < 1e-6 and abs(p["CB"][0]) < 1e-6, (ang, p["CF"], p["CB"])
# open flat: a half circle round each end
p = model.tube_plan(t.uid, 180.0)
assert abs((t.y - p["CF"][1]) - 25.0) < 0.3 and abs(p["CB"][1] - (t.y + 30.0) - 25.0) < 0.3
facets = [n for n in model.panels if n.startswith(f"Tube{t.uid}.GF")]
assert len(facets) == 16, facets
assert len(model.facets) == 4 * 7, len(model.facets)  # no fold drawn between facets
assert all(model.fold_kind[pr] == "skip" for pr in model.facets)
# the front crease (F) and the corners are folds
cf = frozenset((f"Tube{t.uid}.GFL8", f"Tube{t.uid}.GFR1"))
assert cf not in model.facets
faces_in_mesh(f"Tube{t.uid}.")
# shut: flat
nr = model.panels["Page.R"].asm(0.5).to_3x3() @ Vector((0, 0, 1))
d = [(model.panels[n].asm(0.5) @ Vector((x, y, 0))).dot(nr)
     for n in facets for poly in model.panels[n].polys for x, y in poly]
assert max(d) - min(d) < 0.5, max(d) - min(d)
export_svg.export(sc, svg)
print("cylinder: round front and back, facets, flat shut, no warnings")

# ---- a flat roof follows the curve; a pointed one is refused
t.roof = "FLAT"
build.rebuild(sc, force=True)
assert not warns(), warns()
model = build.make_model(sc)[0]
roof = model.panels[f"Roof{t.uid}.L"].polys[0]
assert len(roof) > 10, len(roof)
ys = [y for x, y in roof]
assert min(ys) < t.y - 24.0 and max(ys) > t.y + 30.0 + 24.0, (min(ys), max(ys))
t.roof = "POINTED"
build.rebuild(sc, force=True)
assert any("pointed roof needs straight" in w for w in warns()), warns()
t.roof = "NONE"
print("flat roof follows the curve; pointed roof refused")

# ---- too narrow to curve round: widened, with a warning
t.front = 30.0
build.rebuild(sc, force=True)
assert any("round front needs walls" in w for w in warns()), warns()
t.front = t.back
build.rebuild(sc, force=True)
assert not warns(), warns()

# ---- a tether can glue at a round front's crease
t2 = None
assert bpy.ops.popup.add(kind="TETHER") == {"FINISHED"}
tt = st.mechs[-1]
tt.from_uid, tt.from_pt, tt.to, tt.to_y = t.uid, "CF", "RIGHT", 20.0
build.rebuild(sc, force=True)
assert not [w for w in warns() if "Traceback" in w], warns()
faces_in_mesh(f"Teth")
st.active = len(st.mechs) - 1
bpy.ops.popup.remove()
print("tether at a round front's crease")

# ---- pyramid: round isn't for it
assert bpy.ops.popup.add(kind="PYRAMID") == {"FINISHED"}
py = st.mechs[-1]
py.y = 150.0
py.front_style = "ROUND"
build.rebuild(sc, force=True)
assert any("pyramid can't have a round" in w for w in warns()), warns()
st.active = len(st.mechs) - 1
bpy.ops.popup.remove()

# ---- balconies on both side walls, with railings
assert bpy.ops.popup.add(kind="BOX", host=t.uid, variant="BALCONIES") == {"FINISHED"}
balc = [m for m in st.mechs if m.label.startswith("Balcony")]
assert len(balc) == 2 and all(m.rail > 0 and m.host_uid == t.uid for m in balc)
assert {m.wall for m in balc} == {"L", "R"}, [m.wall for m in balc]
build.rebuild(sc, force=True)
assert not warns(), warns()
model = build.make_model(sc)[0]
for m in balc:
    rp = model.panels[f"Rail{m.uid}.Rail"]
    assert rp.parent == f"Box{m.uid}.CB" and rp.hinge is None
    # stands rail above the floor (the box fold's top), on the outside of the leg
    ac = model.panels[f"Box{m.uid}.AC"]
    for ang in (60.0, 120.0, 180.0):
        top = max((rp.asm(ang) @ Vector((x, y, 0))).dot(Vector((0, 0, 1)))
                  for poly in rp.polys for x, y in poly)
        flo = max((ac.asm(ang) @ Vector((x, y, 0))).dot(Vector((0, 0, 1)))
                  for x, y in ac.polys[0])
        if ang == 180.0:
            assert abs(top - flo - m.rail) < 0.5, (top, flo, m.rail)
faces_in_mesh("Rail")
export_svg.export(sc, svg)
print("balconies on a cylinder's side walls, with railings")

# ---- a balcony in front of a box fold
assert bpy.ops.popup.add(kind="BOX") == {"FINISHED"}
bx = st.mechs[-1]
bx.y, bx.width, bx.height, bx.depth = 5.0, 40.0, 40.0, 30.0
assert bpy.ops.popup.add(kind="BOX", host=bx.uid, fold="B", variant="BALCONY") == {"FINISHED"}
bb = st.mechs[-1]
assert bb.label.startswith("Balcony") and bb.rail > 0 and bb.fold == "B"
build.rebuild(sc, force=True)
assert not warns(), warns()
faces_in_mesh(f"Rail{bb.uid}")
# a railing on a several-peaked strap: refused
bb.peaks = 2
build.rebuild(sc, force=True)
assert any("railing needs a plain box fold" in w for w in warns()), warns()
print("balcony in front of a box fold")

addon.unregister()
print("V70 OK")
