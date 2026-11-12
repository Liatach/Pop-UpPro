"""v0.76: a collar's sliding corner curls as far as it must all the way shut
(it used to give up part-way and cut through), a smaller corner gap, tiers
that alternate out and in; the loop with longer sides (wider tabs) and as a
slice of a cone (narrower or wider at the top); tower roofs and collars on
cubes."""
# families: collars, loops, cones, cubes, towers
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
from popup_pro.core.geom import v3, ccw  # noqa: E402

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


def pokes(model, names, ts):
    worst = 0.0
    for t in ts:
        l, r, nl, nr = model.dirs(t)
        for n in names:
            M = model.panels[n].asm(t)
            for q in model.panels[n].polys[0]:
                w = M @ v3(q)
                worst = min(worst, w.dot(nl), w.dot(nr))
    return worst


def inside(poly, u):
    poly = ccw(poly)
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        if (x1 - x0) * (u.y - y0) - (y1 - y0) * (u.x - x0) < 0:
            return False
    return True


def dense(poly):
    cx = sum(q[0] for q in poly) / len(poly)
    cy = sum(q[1] for q in poly) / len(poly)
    out = [Vector((cx + f * (q[0] - cx), cy + f * (q[1] - cy), 0.0))
           for q in poly for f in (1.0, 0.75, 0.5, 0.25)]
    for i in range(len(poly)):
        q, r = poly[i], poly[(i + 1) % len(poly)]
        out += [Vector((q[0] + f * (r[0] - q[0]), q[1] + f * (r[1] - q[1]), 0.0))
                for f in (0.2, 0.4, 0.6, 0.8)]
    return out


def crossings(model, a, b):
    """Openings where panel a cuts through panel b (points of a over b on
    both sides of it)."""
    out = []
    pa, pb = model.panels[a], model.panels[b]
    for t in range(178, 0, -2):
        Ma, Mbi = pa.asm(t), pb.asm(t).inverted()
        zs = [u.z for u in (Mbi @ (Ma @ q) for q in dense(pa.polys[0]))
              if inside(pb.polys[0], u)]
        if zs and min(zs) < -0.05 and max(zs) > 0.05:
            out.append(t)
    return out


def tower(fold="KFL", **kw):
    st.mechs.clear()
    assert bpy.ops.popup.add(kind="TUBE") == {"FINISHED"}
    t = st.mechs[-1]
    t.y, t.x, t.depth, t.height = 60.0, 30.0, 40.0, 25.0
    t.front = t.back = 30.0
    assert bpy.ops.popup.add(kind="BOX", host=t.uid, fold=fold) == {"FINISHED"}
    m = st.mechs[-1]
    m.height = m.depth = 18.0
    m.width = 60.0
    m.collar = True
    m.collar_below, m.collar_width, m.collar_slope = 14.0, 12.0, 65.0
    for k, v in kw.items():
        setattr(m, k, v)
    build.rebuild(sc, force=True)
    return m.uid


# ---- the sliding corners: never through the other floor, all the way shut
for kw in (dict(), dict(collar_slope=40.0, collar_width=10.0), dict(fold="KBL"),
           dict(collar_gap=1.5)):
    uid = tower(**kw)
    assert not warns(), (kw, warns())
    assert kw or abs(next(m for m in st.mechs if m.uid == uid).collar_gap - 0.75) < 1e-6
    model = build.make_model(sc)[0]
    curls = [n for n in model.panels if n.startswith(f"VFold{uid}c") and n.endswith("Curl")]
    assert len(curls) == 2, curls
    halves = [n for n in model.panels if n.startswith(f"VFold{uid}c") and
              n.endswith(("HalfL", "HalfR"))]
    for cn in curls:
        own = cn[:-len("Curl")]
        for other in halves:
            if other.split(".")[0] == own.split(".")[0]:
                continue  # (its own V-fold's other half: hinged to it at the corner)
            for nm in (own, cn):
                bad = crossings(model, nm, other)
                assert not bad, (kw, nm, other, bad)
print("sliding corners stay clear all the way shut")

# ---- tiers alternating out and in
for d_ in ("OUT", "IN"):
    uid = tower(collar_dir=d_, collar_below=14.0 if d_ == "OUT" else 0.0,
                collar_width=6.0, collar_slope=55.0, collar_rail=5.0, collar_tiers=3,
                collar_alternate=True)
    assert not warns(), (d_, warns())
    model = build.make_model(sc)[0]
    host = model.placed[uid]
    S, l, r, Y, nl, nr = host.dirs(179.0)
    ctr = S + 9.0 * (l + r)

    def reach(tag):
        """How far out from the tower's middle a tier's floors reach, beyond
        where they're hinged."""
        hs = [n for n in model.panels if n.startswith(f"VFold{uid}{tag}") and
              n.endswith(("HalfL", "HalfR"))]
        assert len(hs) == 4, (tag, hs)
        rs = []
        for n in hs:
            p = model.panels[n]
            M = p.asm(179.0)
            ds = [((M @ v3(q)) - ctr) for q in p.polys[0]]
            ds = [(w - w.dot(Y) * Y).length for w in ds]
            rs.append(max(ds) - min(ds))
        return rs
    for tag in ("c", "t1c", "t2c"):
        assert all(x > 2.0 for x in reach(tag)), (tag, reach(tag))

    def lean(tag):  # + out, - in: the floors' outer edges vs their hinges
        hs = [n for n in model.panels if n.startswith(f"VFold{uid}{tag}") and
              n.endswith("HalfL")]
        p = model.panels[hs[0]]
        M = p.asm(179.0)
        pts = [M @ v3(q) for q in p.polys[0]]
        hi = max(pts, key=lambda w: w.dot(Y))
        lo = min(pts, key=lambda w: w.dot(Y))
        flat = lambda w: ((w - ctr) - (w - ctr).dot(Y) * Y).length
        return flat(hi) - flat(lo)
    signs = [lean(tag) > 0 for tag in ("c", "t1c", "t2c")]
    want = [True, False, True] if d_ == "OUT" else [False, True, False]
    assert signs == want, (d_, signs, [lean(t_) for t_ in ("c", "t1c", "t2c")])
    col = [n for n in model.panels if n.startswith(f"VFold{uid}")]
    assert spread_shut(model, col) < 2.0
    export_svg.export(sc, svg)
print("tiers alternating out and in")

# ---- the loop: longer sides for wider tabs
st.mechs.clear()
assert bpy.ops.popup.add(kind="TUBE", variant="LOOP") == {"FINISHED"}
lp = st.mechs[-1]
assert lp.depth >= 14.0 - 1e-6
build.rebuild(sc, force=True)
assert not warns(), warns()
model = build.make_model(sc)[0]
tab = model.panels[f"Tube{lp.uid}.TabL"].polys[0]
xs = [q[0] for q in tab]
assert max(xs) - min(xs) > 13.0, xs  # along the side wall
print("loop: wider tabs")

# ---- a cone: narrower, or wider, at the top
for top in (14.0, 34.0, 4.0):
    lp.cone_top = top
    build.rebuild(sc, force=True)
    assert not warns(), (top, warns())
    model = build.make_model(sc)[0]
    assert model.tubes[lp.uid].get("cone")
    names = [n for n in model.panels if n.startswith(f"Tube{lp.uid}.") and
             model.panels[n].kind == "panel"]
    assert len(names) == 4 * 8 + 2, len(names)
    # every wall meets the next one exactly, all the way
    order = ["FL_"] + [f"GFL{k}" for k in range(1, 9)] + [f"GFR{k}" for k in range(1, 9)] + \
        ["FR_"] + [f"GBR{k}" for k in range(1, 9)] + [f"GBL{k}" for k in range(1, 9)] + ["FL_"]
    for t in (170.0, 120.0, 70.0, 25.0, 5.0):
        for a_, b_ in zip(order, order[1:]):
            A = [model.panels[f"Tube{lp.uid}.{a_}"].asm(t) @ v3(q)
                 for q in model.panels[f"Tube{lp.uid}.{a_}"].polys[0]]
            B = [model.panels[f"Tube{lp.uid}.{b_}"].asm(t) @ v3(q)
                 for q in model.panels[f"Tube{lp.uid}.{b_}"].polys[0]]
            d = sorted(min((x - y).length for y in B) for x in A)
            assert d[1] < 1e-3, (top, t, a_, b_, d)
    assert pokes(model, names, (170.0, 120.0, 70.0, 25.0, 5.0)) > -0.5
    assert spread_shut(model, names) < 1.0
    # open flat, its top is Top Radius from the middle (across the front crease)
    S = model.panels["Page.L"].asm(180.0) @ Vector((0, 0, 0))
    up = model.panels["Page.R"].asm(180.0).to_3x3() @ Vector((0, 0, 1))
    p = model.panels[f"Tube{lp.uid}.FL_"]
    M = p.asm(180.0)
    pts = [M @ v3(q) for q in p.polys[0]]
    top_pts = [w for w in pts if abs((w - S).dot(up) - lp.height) < 0.3]
    bot_pts = [w for w in pts if abs((w - S).dot(up)) < 0.3]
    assert len(top_pts) == 2 and len(bot_pts) == 2, pts
    xa = model.panels["Page.R"].asm(180.0).to_3x3() @ Vector((1, 0, 0))
    assert abs(abs((bot_pts[0] - S).dot(xa)) - lp.x) < 0.3
    assert abs(abs((top_pts[0] - S).dot(xa)) - top) < 0.3, ((top_pts[0] - S).dot(xa), top)
    # a curved band on the pattern
    poly = model.panels[f"Tube{lp.uid}.GFL4"].polys[0]
    faces_in_mesh(f"Tube{lp.uid}")
    export_svg.export(sc, svg)
print("cone loops, narrowing and flaring")
lp.front_style = "OUT"
build.rebuild(sc, force=True)
assert any("top radius needs a round front and back" in w for w in warns()), warns()

# ---- tower roofs and collars on cubes
for roof, collar, d_ in (("POINTED", False, "OUT"), ("FLAT", False, "OUT"),
                         ("NONE", True, "OUT"), ("POINTED", True, "OUT"),
                         ("NONE", True, "IN")):
    st.mechs.clear()
    assert bpy.ops.popup.add(kind="CUBE") == {"FINISHED"}
    c = st.mechs[-1]
    c.y, c.size, c.height = 60.0, 30.0, 40.0
    c.roof, c.roof_height = roof, 18.0
    c.collar, c.collar_dir = collar, d_
    c.collar_below, c.collar_width, c.collar_slope = (14.0 if d_ == "OUT" else 0.0), 10.0, 60.0
    c.collar_rail = 5.0
    build.rebuild(sc, force=True)
    assert not warns(), (roof, collar, d_, warns())
    model = build.make_model(sc)[0]
    if roof != "NONE":
        assert f"Cube{c.uid}.LidL" not in model.panels  # (the roof replaces the lid)
        rh = [n for n in model.panels if n.startswith(f"VFold{c.uid}r") and
              n.endswith(("HalfL", "HalfR"))]
        assert len(rh) == 4, rh
        if roof == "POINTED":  # open flat: a pyramid over the cube
            up = model.panels["Page.R"].asm(179.0).to_3x3() @ Vector((0, 0, 1))
            S = model.panels["Page.L"].asm(179.0) @ Vector((0, 0, 0))
            zs = [(model.panels[n].asm(179.0) @ v3(q) - S).dot(up) for n in rh
                  for q in model.panels[n].polys[0]]
            assert max(zs) > c.height + 15.0 and min(zs) > c.height - 1.0, (min(zs), max(zs))
    if collar:
        fl = [n for n in model.panels if n.startswith(f"VFold{c.uid}c") and
              n.endswith(("HalfL", "HalfR"))]
        assert len(fl) == 4, fl
    allp = [n for n in model.panels if n.startswith(("Cube", "VFold"))]
    assert spread_shut(model, allp) < 2.0, spread_shut(model, allp)
    faces_in_mesh("VFold")
    export_svg.export(sc, svg)
print("tower roofs and collars on cubes")
c.roof = "GABLE"
build.rebuild(sc, force=True)
assert any("gabled roof goes on castle towers" in w for w in warns()), warns()

addon.unregister()
print("V76 OK")
