"""v0.73: Kim's collar, a balcony floor round a tower that folds flat: the
floors slope up and out from the walls; at the two corners that close as the
card shuts they are one V-fold hung outside the corner, at the other two
they meet and are slit (or notched) to slide past each other."""
# families: collars, towers
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
from popup_pro.core.geom import v3, poly_area  # noqa: E402

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


def tower(fold="KFL", front=30.0, **kw):
    st.mechs.clear()
    assert bpy.ops.popup.add(kind="TUBE") == {"FINISHED"}
    t = st.mechs[-1]
    tu = t.uid
    t.y, t.x, t.depth, t.height = 60.0, 30.0, 40.0, 25.0
    t.front = t.back = front
    assert bpy.ops.popup.add(kind="BOX", host=tu, fold=fold) == {"FINISHED"}
    m = st.mechs[-1]
    m.height = m.depth = 18.0
    m.width = 60.0
    m.collar = True
    m.collar_below, m.collar_width, m.collar_slope = 14.0, 12.0, 65.0
    for k, v in kw.items():
        setattr(m, k, v)
    build.rebuild(sc, force=True)
    return m.uid


def slopes(model, uid):
    """Each floor's angle out from the tower's up, at openings down to shut."""
    host = model.placed[uid]
    out = {}
    for n in model.order:
        if not (n.startswith(f"VFold{uid}c") and n.endswith(("HalfL", "HalfR"))):
            continue
        p = model.panels[n]
        row = []
        for ang in (179.0, 140.0, 100.0, 60.0, 20.0, 2.0):
            S, l, r, Y, nl, nr = host.dirs(ang)
            M = p.asm(ang)
            nn = (M.to_3x3() @ Vector((0, 0, 1))).normalized()
            d = nn.cross(Y).normalized().cross(nn).normalized()
            ctr = S + 9.0 * (l + r) + 46.0 * Y
            c = sum((M @ v3(q) for poly in p.polys for q in poly), Vector()) / \
                sum(len(poly) for poly in p.polys)
            if d.dot(c - ctr) < 0:
                d = -d
            row.append(math.degrees(d.angle(Y)))
        out[n] = row
    return out


# ---- a collar round a castle's corner tower
uid = tower()
assert not warns(), warns()
model = build.make_model(sc)[0]
halves = [n for n in model.panels if n.startswith(f"VFold{uid}c") and
          n.endswith(("HalfL", "HalfR"))]
assert len(halves) == 4, halves  # a floor each side, two V-folds
sl = slopes(model, uid)
for n, row in sl.items():
    assert abs(row[0] - 65.0) < 2.0, (n, row)  # its slope, open flat
    assert all(b <= a + 0.5 for a, b in zip(row, row[1:])), (n, row)  # folds up, steadily
    assert row[-1] < 3.0, (n, row)  # flat against the wall, shut
# tabs along each floor's hinge, the two at a corner not overlapping
for k in (0, 1):
    tl = model.panels[f"VFold{uid}c{k}.TabL"].polys[0]
    tr_ = model.panels[f"VFold{uid}c{k}.TabR"].polys[0]
    xl, xr = [q[0] for q in tl], [q[0] for q in tr_]
    assert (max(xl) <= 1e-6 and min(xr) >= -1e-6) or (min(xl) >= -1e-6 and max(xr) <= 1e-6), \
        (xl, xr)
    assert abs(poly_area(tl)) > 20.0 and abs(poly_area(tr_)) > 20.0
# (since v0.74 the free corners slide inside, curling, not slit)
curls = [n for n in model.panels if n.startswith(f"VFold{uid}c") and n.endswith("Curl")]
assert len(curls) == 2, curls
faces_in_mesh(f"VFold{uid}c")
export_svg.export(sc, svg)
print("collar: four floors folding up flat, V-folds at two corners, sliding at two")

# notched instead: one floor at each free corner cut back
uid = tower(collar_corner="NOTCH")
assert not warns(), warns()
model = build.make_model(sc)[0]
counts = sorted(len(model.panels[n].polys) for n in model.panels
                if n.startswith(f"VFold{uid}c") and n.endswith(("HalfL", "HalfR")))
assert counts == [1, 1, 1, 1], counts
print("notched free corners")

# ---- on a hexagonal castle's crease tower: the other pair of corners
uid = tower("KF", front=42.0)
assert not warns(), warns()
model = build.make_model(sc)[0]
# (its first V-fold in the crease itself: hinged on the castle's two walls)
pars = {model.panels[f"VFold{uid}c0.Half{s_}"].parent for s_ in "LR"}
assert all(p_.startswith("Tube") for p_ in pars), pars
for n, row in slopes(model, uid).items():
    assert row[-1] < 3.0, (n, row)
print("collar on a crease tower")

# ---- slopes: steep and nearly level both fold
for s_ in (20.0, 80.0):
    uid = tower(collar_slope=s_)
    assert not warns(), warns()
    model = build.make_model(sc)[0]
    for n, row in slopes(model, uid).items():
        assert abs(row[0] - s_) < 3.5 and row[-1] < 3.0, (s_, n, row)

# ---- below the castle's walls: raised, with a warning
uid = tower(collar_below=50.0)
assert any("above the castle's walls" in w for w in warns()), warns()

# ---- with a roof as well
uid = tower(roof="GABLE", roof_height=8.0, eave=3.0)
assert not warns(), warns()

addon.unregister()
print("V73 OK")
