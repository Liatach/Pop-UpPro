"""v0.75: collars stacked in tiers (out or in), their railings running on
round the curled corners; Kim's angled box folds (glue lines turned, mirrored
either side of the fold: one crease, or three with a shelf in the middle that
folds down its centre); the loop (Birmingham 16)."""
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


def between_pages(model, names, ts=(170.0, 120.0, 90.0, 60.0, 40.0, 25.0, 10.0, 3.0)):
    worst = 0.0
    for t in ts:
        l, r, nl, nr = model.dirs(t)
        for n in names:
            p = model.panels[n]
            M = p.asm(t)
            for poly in p.polys:
                for q in poly:
                    w = M @ v3(q)
                    worst = min(worst, w.dot(nl), w.dot(nr))
    return worst


# ---- collar tiers
def tower(**kw):
    st.mechs.clear()
    assert bpy.ops.popup.add(kind="TUBE") == {"FINISHED"}
    t = st.mechs[-1]
    t.y, t.x, t.depth, t.height = 60.0, 30.0, 40.0, 25.0
    t.front = t.back = 30.0
    assert bpy.ops.popup.add(kind="BOX", host=t.uid, fold="KFL") == {"FINISHED"}
    m = st.mechs[-1]
    m.height = m.depth = 18.0
    m.width = 60.0
    m.collar = True
    m.collar_below, m.collar_width, m.collar_slope = 14.0, 12.0, 65.0
    m.collar_rail = 6.0
    for k, v in kw.items():
        setattr(m, k, v)
    build.rebuild(sc, force=True)
    return m.uid


for d_ in ("OUT", "IN"):
    uid = tower(collar_tiers=3, collar_dir=d_, collar_crenels=(d_ == "OUT"),
                collar_width=12.0 if d_ == "OUT" else 3.0,
                collar_slope=65.0 if d_ == "OUT" else 50.0)
    assert not warns(), (d_, warns())
    model = build.make_model(sc)[0]
    for tag in ("c", "t1c", "t2c"):
        halves = [n for n in model.panels if n.startswith(f"VFold{uid}{tag}") and
                  n.endswith(("HalfL", "HalfR"))]
        assert len(halves) == 4, (tag, halves)
        rails = [n for n in model.panels if n.startswith(f"VFold{uid}{tag}") and
                 n.endswith("Rail")]
        # a railing on each floor, carried on round the two curled corners
        curl = sum(n.endswith("CurlRail") for n in rails)
        floors = len(rails) - curl
        assert floors == 4, rails
        # (out, the free corners curl, and so do their railings)
        assert curl == (2 if d_ == "OUT" else curl), rails
        assert curl == sum(n.endswith("Curl") for n in model.panels
                           if n.startswith(f"VFold{uid}{tag}")), rails
    col = [n for n in model.panels if n.startswith(f"VFold{uid}")]
    assert spread_shut(model, col) < 2.0, spread_shut(model, col)
    faces_in_mesh(f"VFold{uid}t2")
    export_svg.export(sc, svg)
    print(f"three collar tiers ({d_}), railings round the corners")

# tapered tiers only fit till they meet in the middle
uid = tower(collar_tiers=4, collar_dir="IN", collar_width=6.0)
assert any("tapered tier" in w for w in warns()), warns()

# tiers need a railing to stand on
uid = tower(collar_tiers=3, collar_rail=0.0)
assert any("tier" in w for w in warns()), warns()
model = build.make_model(sc)[0]
assert not [n for n in model.panels if n.startswith(f"VFold{uid}t1")]


# ---- angled box folds
def angled(ang, creases="ONE", crease=0.0, **kw):
    st.mechs.clear()
    assert bpy.ops.popup.add(kind="BOX", variant="ANGLED") == {"FINISHED"}
    m = st.mechs[-1]
    assert m.label.startswith("Angled box fold") and abs(m.fan_angle - 20.0) < 1e-6
    m.y, m.width, m.height = 40.0, 50.0, 35.0
    m.fan_angle, m.fan_creases, m.fan_crease = ang, creases, crease
    for k, v in kw.items():
        setattr(m, k, v)
    build.rebuild(sc, force=True)
    return m.uid


for ang in (20.0, -20.0, 40.0):
    uid = angled(ang)
    assert not warns(), (ang, warns())
    model = build.make_model(sc)[0]
    b = f"Box{uid}"
    names = [f"{b}.AC", f"{b}.CB"]
    assert all(n in model.panels for n in names + [f"{b}.TabA", f"{b}.TabB"])
    # lies flat open, flat shut, and never through the pages
    up = model.panels["Page.R"].asm(179.9).to_3x3() @ Vector((0, 0, 1))
    zs = [(model.panels[n].asm(179.9) @ v3(q)).dot(up) for n in names
          for q in model.panels[n].polys[0]]
    assert max(zs) - min(zs) < 1.0, zs
    assert spread_shut(model, names) < 1.0
    assert between_pages(model, names) > -0.5, between_pages(model, names)
    # the glue lines turned: the two ends of each tab at different distances
    # from the fold, mirrored either side
    l, r, nl, nr = model.dirs(90.0)
    S = model.panels["Page.L"].asm(90.0) @ Vector((0, 0, 0))
    out = []
    for tb, d in (("TabA", l), ("TabB", r)):
        p = model.panels[f"{b}.{tb}"]
        pts = [p.asm(90.0) @ v3(q) for q in p.polys[0]]
        out.append(sorted(round((w - S).dot(d), 1) for w in pts))
    assert out[0] == out[1], out
    assert out[0][-1] - out[0][0] > 10.0, out
    # the crease meets the glue lines on the fold: the strip's panels turn
    # into planes neither page nor square to it at 90 degrees
    n_ac = model.panels[f"{b}.AC"].asm(90.0).to_3x3() @ Vector((0, 0, 1))
    Y = Vector((0, 1, 0))
    assert abs(n_ac.dot(Y)) > 0.1, n_ac  # (a square box fold's panels contain the fold's direction)
    print(f"angled box fold {ang:+.0f}: flat open and shut, in tilted planes")
faces_in_mesh("Box")
export_svg.export(sc, svg)

# crease angle bigger than the glue angle: stands up even open flat
uid = angled(20.0, crease=26.0)
assert not warns(), warns()
model = build.make_model(sc)[0]
up = model.panels["Page.R"].asm(180.0).to_3x3() @ Vector((0, 0, 1))
zs = [(model.panels[f"Box{uid}.AC"].asm(180.0) @ v3(q)).dot(up)
      for q in model.panels[f"Box{uid}.AC"].polys[0]]
assert max(zs) > 5.0, zs
# smaller than the glue angle: it would tear, so it's made the glue angle
uid = angled(20.0, crease=10.0)
assert any("tears" in w for w in warns()), warns()

# three creases: the middle a shelf, folding down its centre (valley) as it shuts
for ang in (20.0, -25.0):
    uid = angled(ang, "THREE")
    assert not warns(), (ang, warns())
    model = build.make_model(sc)[0]
    b = f"Box{uid}"
    names = [f"{b}.{n}" for n in ("AC", "MidL", "MidR", "CB")]
    assert all(n in model.panels for n in names)
    assert between_pages(model, names) > -0.5, between_pages(model, names)
    assert spread_shut(model, names) < 1.0, spread_shut(model, names)
    # symmetric: the two middle halves at the same height off each page
    for t in (120.0, 60.0, 20.0):
        l, r, nl, nr = model.dirs(t)
        hl = [(model.panels[f"{b}.MidL"].asm(t) @ v3(q)).dot(nl)
              for q in model.panels[f"{b}.MidL"].polys[0]]
        hr = [(model.panels[f"{b}.MidR"].asm(t) @ v3(q)).dot(nr)
              for q in model.panels[f"{b}.MidR"].polys[0]]
        assert abs(min(hl) - min(hr)) < 0.05 and abs(max(hl) - max(hr)) < 0.05, (t, hl, hr)

    # the centre stays flat (a shelf) open, folds well before shut
    def centre(t):
        a_ = model.panels[f"{b}.MidL"].asm(t).to_3x3() @ Vector((0, 0, 1))
        c_ = model.panels[f"{b}.MidR"].asm(t).to_3x3() @ Vector((0, 0, 1))
        return math.degrees(a_.angle(c_))
    assert centre(120.0) < 1.0 and centre(10.0) > 90.0, (centre(120.0), centre(10.0))
faces_in_mesh("Box")
export_svg.export(sc, svg)
print("three creases: a shelf folding down its centre")

# no slant or peaks on an angled box fold
uid = angled(20.0, peaks=2)
assert any("isn't made on an angled box fold" in w for w in warns()), warns()

# ---- the loop: a ring on two tabs, its size set by how far out they are
st.mechs.clear()
assert bpy.ops.popup.add(kind="TUBE", variant="LOOP") == {"FINISHED"}
lp = st.mechs[-1]
assert lp.label.startswith("Loop") and lp.front_style == lp.back_style == "ROUND"
build.rebuild(sc, force=True)
assert not warns(), warns()
model = build.make_model(sc)[0]
p = model.tube_plan(lp.uid, 180.0)
span = (p["CB"][1] - p["CF"][1])
assert abs(span - (2 * lp.x + lp.depth)) < 0.6, (span, lp.x, lp.depth)
tab = model.panels[f"Tube{lp.uid}.TabL"].polys[0]
assert max(q[1] for q in tab) - min(q[1] for q in tab) > 7.0, tab  # a real tab, not a sliver
allp = [n for n in model.panels if n.startswith(f"Tube{lp.uid}")]
assert spread_shut(model, allp) < 1.0
faces_in_mesh(f"Tube{lp.uid}")
export_svg.export(sc, svg)
lp.x = 40.0
lp.front = lp.back = round(0.5 * math.pi * 40.0, 1)  # (half circles again)
build.rebuild(sc, force=True)
assert not warns(), warns()
model = build.make_model(sc)[0]
p2 = model.tube_plan(lp.uid, 180.0)
assert (p2["CB"][1] - p2["CF"][1]) > span + 20.0  # further out: a bigger ring
print("loop: a ring on two tabs")

addon.unregister()
print("V75 OK")
