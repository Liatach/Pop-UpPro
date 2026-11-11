"""v0.72: towers up a tube's front and back creases (pentagonal and hexagonal
castles), flat tower roofs (two V-folds with a gentle slope) that can sit
below the top with battlements, or at the top with a ledge overhanging the
walls; pointed roofs on any tower."""
# families: towers, roofs
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
from popup_pro.core.geom import v3  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
svg = os.path.join(tempfile.mkdtemp(), "t.svg")


def warns():
    return [w for w in st.warnings.split("\n") if w]


def faces_in_mesh(prefix):
    bpy.ops.popup.build()
    names = [p["name"] for p in live.meta(st.rig)["panels"]]
    me = st.card.data
    vals = [0] * len(me.polygons)
    me.attributes["pop_panel"].data.foreach_get("value", vals)
    have = set(vals)
    missing = [n for i, n in enumerate(names) if n.startswith(prefix) and i not in have]
    assert not missing, missing


def spread_shut(model, names):
    nr = model.panels["Page.R"].asm(0.5).to_3x3() @ Vector((0, 0, 1))
    d = [(model.panels[n].asm(0.5) @ v3(q)).dot(nr) for n in names
         for poly in model.panels[n].polys for q in poly]
    return max(d) - min(d)


def castle(front, back, roof, **kw):
    st.mechs.clear()
    assert bpy.ops.popup.add(kind="TUBE") == {"FINISHED"}
    t = st.mechs[-1]
    tu = t.uid
    t.y, t.x, t.depth, t.height, t.strips = 55.0, 30.0, 40.0, 35.0, 2
    t.front, t.back = front, back
    assert bpy.ops.popup.add(kind="BOX", host=tu, variant="TOWERS") == {"FINISHED"}
    for m in st.mechs:
        if m.kind == "BOX":
            m.roof = roof
            m.width, m.height, m.depth = 48.0, 15.0, 15.0
            for k, v in kw.items():
                setattr(m, k, v)
    build.rebuild(sc, force=True)
    return tu


# ---- hexagonal: six towers, the front and back creases too
tu = castle(42.0, 42.0, "POINTED", roof_height=14.0)
walls = sorted(m.wall for m in st.mechs if m.kind == "BOX")
assert walls == sorted(["KFL", "KFR", "KBR", "KBL", "KF", "KB"]), walls
assert not warns(), warns()
model = build.make_model(sc)[0]
assert (tu, "KF") in model.hosts and (tu, "KB") in model.hosts
kf = next(m for m in st.mechs if m.wall == "KF")
assert kf.label.endswith("front tower")
# the front crease's tower: its roof V-folds in its own corner and the inner one
roofs = [n for n in model.panels if n.startswith(f"VFold{kf.uid}r")]
assert roofs, "no roof on the crease tower"
assert model.hosts[(f"{kf.uid}r0", "V")].label.endswith("crease")
allp = [n for n in model.panels if n.startswith(("Box", "VFold", "Tube"))]
assert spread_shut(model, allp) < 1.5, spread_shut(model, allp)
faces_in_mesh("VFold")
export_svg.export(sc, svg)
print("hexagonal castle: six towers with pointed roofs, flat shut")

# ---- pentagonal: flat front, pointed back
tu = castle(30.0, 42.0, "GABLE", roof_height=8.0, eave=3.0)
walls = sorted(m.wall for m in st.mechs if m.kind == "BOX")
assert walls == sorted(["KFL", "KFR", "KBR", "KBL", "KB"]), walls
assert not warns(), warns()
print("pentagonal castle: gabled towers")

# a recessed or flat front has no crease tower
tu = castle(42.0, 42.0, "NONE")
t = next(m for m in st.mechs if m.uid == tu)
t.front_style = "IN"
build.rebuild(sc, force=True)
assert any("host" in w for w in warns()), warns()  # (the front crease tower is skipped)

# ---- flat roofs: at the top, with a ledge round the tower
tu = castle(30.0, 30.0, "FLAT", eave=4.0, roof_slope=1.5)
assert not warns(), warns()
model = build.make_model(sc)[0]
tw = [m for m in st.mechs if m.kind == "BOX"]
for m in tw:
    halves = [n for n in model.panels if n.startswith(f"VFold{m.uid}r") and
              n.endswith(("HalfL", "HalfR"))]
    assert len(halves) == 4, halves
    ledge = [n for n in model.panels if n.startswith(f"Ledge{m.uid}x")]
    assert len(ledge) == 4, ledge
    # open flat: the roof all but flat (its middle only Slope above its edges)
    up = model.panels["Page.R"].asm(180.0).to_3x3() @ Vector((0, 0, 1))
    zs = [(model.panels[n].asm(180.0) @ v3(q)).dot(up) for n in halves
          for q in model.panels[n].polys[0]]
    assert max(zs) - min(zs) < 1.6, (max(zs), min(zs))
    # the ledge reaches past the tower: its area bigger than the roof's
    from popup_pro.core.geom import poly_area
    ar = sum(abs(poly_area(model.panels[n].polys[0])) for n in halves)
    al = sum(abs(poly_area(model.panels[n].polys[0])) for n in ledge)
    assert al > ar * 1.3, (al, ar)
    for n in ledge:
        assert model.panels[n].parent.startswith(f"VFold{m.uid}r")
allp = [n for n in model.panels if n.startswith(("Ledge", "VFold"))]
assert spread_shut(model, allp) < 1.5, spread_shut(model, allp)
faces_in_mesh("Ledge")
export_svg.export(sc, svg)
print("flat roofs with a ledge round each tower")

# ---- flat roofs below the top: battlements, no overhang
tu = castle(42.0, 42.0, "FLAT", roof_below=8.0, eave=0.0)
assert not warns(), warns()
model = build.make_model(sc)[0]
for m in st.mechs:
    if m.kind != "BOX":
        continue
    ac = model.panels[f"Box{m.uid}.AC"]
    assert len(ac.polys) >= 3, len(ac.polys)  # cut down, merlons standing on it
    tops = sorted({round(q[1], 3) for poly in ac.polys for q in poly})
    assert abs(tops[-1] - m.width) < 1e-3 and any(abs(y - m.width) > 1.9 and y > m.width - 7
                                                  for y in tops), tops
    h = next(n for n in model.panels if n.startswith(f"VFold{m.uid}r0.Half"))
    # the roof sits 8 below the top
    zs = [q[1] for q in model.panels[f"Box{m.uid}.AC"].polys[0]]
faces_in_mesh("Box")
export_svg.export(sc, svg)
for m in st.mechs:
    if m.kind == "BOX":
        m.eave = 4.0
build.rebuild(sc, force=True)
assert any("below the top can't overhang" in w for w in warns()), warns()
print("flat roofs below the top, with battlements")

# a dish (negative slope) builds too
tu = castle(30.0, 30.0, "FLAT", roof_slope=-1.5)
assert not warns(), warns()

addon.unregister()
print("V72 OK")
