"""v0.82: more of Birmingham's mechanisms. The pop-up house (49: a gabled
roof on a cube), the slotted rising sheet (81), a box with ends (82) and an
animal face (17)."""
# families: cubes, roofs, folds45, vfolds
import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import export_svg, live  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_stub import draw, props_shown  # noqa: E402
from popup_pro import ui  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
svg = os.path.join(tempfile.mkdtemp(), "t.svg")


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}, (kind, kw)
    return st.mechs[-1]


def model():
    return Model(st.card_dict(), [m.to_dict() for m in st.mechs])


def warns():
    return [w for w in st.warnings.split("\n") if w]


def built(prefix, allow=()):
    """Builds, exports, and gives the model; every panel is in the mesh."""
    bpy.ops.popup.build()
    assert not [w for w in warns() if not any(a in w for a in allow)], warns()
    names = [p["name"] for p in live.meta(st.rig)["panels"]]
    me = st.card.data
    vals = [0] * len(me.polygons)
    me.attributes["pop_panel"].data.foreach_get("value", vals)
    missing = [n for i, n in enumerate(names) if n.startswith(prefix) and i not in set(vals)]
    assert not missing, missing
    export_svg.export(sc, svg)
    return model()


def world(M, name, t):
    p = M.panels[name]
    A = p.asm(t)
    return [A @ v3(q) for poly in p.polys for q in poly]


def above_pages(M, prefix, tol=0.5):
    for n in M.order:
        p = M.panels[n]
        if not n.startswith(prefix) or p.kind != "panel":
            continue
        for t in M.samples:
            l, r, nl, nr = M.dirs(t)
            d = min(min(w.dot(nl), w.dot(nr)) for w in world(M, n, t))
            assert d > -tol, (n, t, d)


# ---- the pop-up house: a cube with a gabled roof
h = add("CUBE", variant="HOUSE")
assert h.roof == "GABLE" and h.size_r > h.size and h.label.startswith("House")
# (v0.83: the walls push the roof open; nearly shut, as the house leans, its
# overhang meets the page, as real card's does)
M = built("Cube", allow=("pokes through the card",))
for n in ("Rib1.Rib", "GRoof1.A", "GRoof1.B"):
    assert n in M.panels, n
t = M.tmax
ridge = [w for w in world(M, "GRoof1.A", t) if abs(w.z - max(x.z for x in world(M, "GRoof1.A", t))) < 0.01]
assert len(ridge) == 2 and abs(ridge[0].z - (h.height + h.roof_height)) < 0.05, ridge
# the ridge runs along the long walls, and is as long as them plus the eaves
assert abs((ridge[0] - ridge[1]).length - (h.size_r + 2 * h.eave)) < 0.05


def roof_on_walls(M):
    """v0.83: the walls push the roof open and never come through it; it
    moves smoothly (no lifting off on its own)."""
    rib = M.panels["Rib1.Rib"]
    prev = None
    for i in range(0, 181, 3):
        t = max(0.5, float(i))
        for rn in ("GRoof1.A", "GRoof1.B"):
            R = M.panels[rn]
            Ai = R.asm(t).inverted()
            xs = [q[0] for q in R.polys[0]]
            ys = [q[1] for q in R.polys[0]]
            inside = (Ai @ (rib.asm(t) @ v3(rib.polys[0][0]))).z
            for wn in ("Cube1.A", "Cube1.B", "Cube1.C", "Cube1.D"):
                for w in world(M, wn, t):
                    q = Ai @ w
                    if min(xs) < q.x < max(xs) and min(ys) < q.y < max(ys):
                        assert q.z * (1 if inside < 0 else -1) < 0.3, (t, rn, wn, q.z)
        a_ = (M.panels["GRoof1.A"].asm(t).to_3x3() @ v3((0, 1))).angle(
            M.panels["GRoof1.B"].asm(t).to_3x3() @ v3((0, 1)))
        if prev is not None and t >= 12.0:  # (it turns fastest as it shuts)
            assert abs(a_ - prev) < math.radians(12.0), (t, math.degrees(a_ - prev))
        prev = a_


roof_on_walls(M)
h.gable_turn = False
M = built("Cube", allow=("pokes through the card",))
roof_on_walls(M)
assert "gable_turn" in props_shown(draw(ui.POPUP_PT_mechs))
print("the pop-up house: a gabled roof on a cube")
st.mechs.clear()
st["pop_next_uid"] = 1

# ---- the slotted rising sheet
r = add("RISER")
r.slotted, r.cross_height, r.cross_width = True, 100.0, 50.0
M = built("Rise")
x = M.panels["Rise1x.Cross"]
for t in M.samples:
    l, rr, nl, nr = M.dirs(t)
    # each foot's far corner stays on its page, where its tab is glued
    for n, nrm in (("Rise1x.FootL", nl), ("Rise1x.FootR", nr)):
        pn = M.panels[n]
        on = [pn.asm(t) @ v3(q) for q in pn.polys[0] if abs(q[0]) < 1e-6]
        assert len(on) == 2 and all(abs(w.dot(nrm)) < 0.02 for w in on), (n, t)
    # the cross piece's middle line is the sheet's slot line
    S = M.panels["Rise1.Sheet"].asm(t)
    for a in (0.0, 40.0, 100.0):
        p = x.asm(t) @ v3((a, 0.0))
        q = S @ v3((a, 0.5 * r.width))
        assert (p - q).length < 0.02, (t, a, (p - q).length)
t = M.tmax  # open flat it stands square across the sheet
n_sheet = (M.panels["Rise1.Sheet"].asm(t).to_3x3() @ v3((0, 0, 1))).normalized()
n_cross = (x.asm(t).to_3x3() @ v3((0, 0, 1))).normalized()
assert abs(n_sheet.dot(n_cross)) < 0.01
tops = [w.z for w in world(M, "Rise1x.Cross", t)]
assert abs(max(tops) - 100.0) < 0.05  # (it rises past the sheet, 80 tall)
r.slotted = False
M = built("Rise")
assert "Rise1x.Cross" not in M.panels and any(n.startswith("VFold") for n in M.panels)
print("a rising sheet with a slotted cross piece")
st.mechs.clear()
st["pop_next_uid"] = 1

# ---- a box with ends
b = add("BOXEND")
for side in ("R", "L"):
    b.box_side = side
    M = built("BoxE")
    sg = 1.0 if side == "R" else -1.0
    top = world(M, "BoxE1.Top", M.tmax)  # square when the card is flat
    assert all(abs(w.z - b.height) < 0.05 for w in top), [w.z for w in top]
    assert min(sg * w.x for w in top) > -0.05 and max(sg * w.x for w in top) < b.depth + 0.05
    for t in (30.0, 60.0, 90.0):  # flat on its own page until the card is half open
        l, rr, nl, nr = M.dirs(t)
        n = nr if side == "R" else nl
        for nm in ("BoxE1.A", "BoxE1.Top", "BoxE1.B"):
            assert all(abs(w.dot(n)) < 0.05 for w in world(M, nm, t)), (nm, t)
    for t in M.samples:
        l, rr, nl, nr = M.dirs(t)
        n = nr if side == "R" else nl
        for e in "FK":
            # the ends' faces stay in the page and in the far wall they're glued to
            xb = b.height + b.depth
            pg, fw = M.panels[f"BoxE1.{e}Pg"], M.panels[f"BoxE1.{e}Fw"]
            on = [pg.asm(t) @ v3(q) for q in pg.polys[0] if abs(q[0]) < 1e-6]
            assert len(on) == 2 and all(abs(w.dot(n)) < 0.02 for w in on), (e, t)
            B = M.panels["BoxE1.B"].asm(t)
            nb, ob = (B.to_3x3() @ v3((0, 0, 1))), B @ v3((xb, 0.0))
            on = [fw.asm(t) @ v3(q) for q in fw.polys[0] if abs(q[0] - xb) < 1e-6]
            assert len(on) == 2 and all(abs((w - ob).dot(nb)) < 0.02 for w in on), (e, t)
    above_pages(M, "BoxE")
b.box_ends = "FRONT"
M = built("BoxE")
end = [n for n in ("BoxE1.FWa", "BoxE1.KWa") if n in M.panels]
assert len(end) == 1, end
ys = [w.y for w in world(M, end[0], M.tmax)]
assert max(ys) < b.y + 1.0  # (the end nearest the bottom of the card, on either page)
print("a box with ends, on either page")
st.mechs.clear()
st["pop_next_uid"] = 1

# ---- an animal face: a loop with a muzzle
f = add("TUBE", variant="FACE")
assert f.muzzle and f.front_style == "ROUND" and f.label.startswith("Face")
assert f.cone_lean == 15.0  # (a little conical, narrower at the nose)
M = built("Tube")
for t in M.samples:  # on a cone: the two halves share the crease's top and the seam's tip
    L, R = world(M, "Tube1.NoseL", t), world(M, "Tube1.NoseR", t)
    shared = [w for w in L if min((w - v).length for v in R) < 0.02]
    assert len(shared) == 2 and all(abs(w.x) < 0.02 for w in shared), (t, shared)
ear = M.panels["Tube1.TabL"]  # its base tabs are ears, out from the loop
assert len(ear.polys[0]) == 5
xs = [w.x for w in world(M, "Tube1.TabL", M.tmax)]
assert min(xs) < -(f.x + 0.9 * f.face_ear) and max(xs) < -f.x + 0.5, xs
# ---- 0.89: Birmingham's pattern: one band cut at the back (K under L),
# a forehead join at C's foot (M under N), a nose crease between the eyes,
# a muzzle join (H under J), ears at a clock position
assert not warns(), warns()
for n in ("Tube1.BrowL", "Tube1.BrowR", "Tube1.BrowRTab", "Tube1.NoseRTab", "Tube1.Close"):
    assert n in M.panels, n
assert M.panels["Tube1.Close"].parent == "Tube1.GBL1"
for t in M.samples:  # the forehead's halves meet along their seam
    L, R = world(M, "Tube1.BrowL", t), world(M, "Tube1.BrowR", t)
    shared = [w for w in L if min((w - v).length for v in R) < 0.05]
    assert len(shared) >= 2, (t, shared)
assert abs(f.height - (f.face_brow + f.face_nose)) < 1e-6
f.face_nose = 30.0
assert abs(f.height - (f.face_brow + 30.0)) < 1e-6
lean = f.cone_lean
f.face_dia = 60.0
assert abs(f.x - 30.0) < 1e-6 and abs(f.cone_lean - lean) < 0.1
f.face_dia = 50.0
cy = {}
for ck in ("10", "9", "8"):
    f.face_clock = ck
    M = built("Tube")
    assert not warns(), (ck, warns())
    cy[ck] = sum(w.y for w in world(M, "Tube1.TabL", M.tmax)) / 5.0
assert cy["10"] > cy["9"] + 2.0 > cy["8"] + 4.0, cy  # (ears leaning back, out, forward)
f.face_brow = 0.0  # an open arch
M = built("Tube")
assert "Tube1.BrowL" not in M.panels and not warns(), warns()
f.face_brow, f.face_clock = 8.0, "9"
f.cone_lean = 0.0  # (still cut as one leaning band)
M = built("Tube")
assert "Tube1.BrowL" in M.panels and not warns(), warns()
shown = props_shown(draw(ui.POPUP_PT_mechs))
assert {"muzzle", "face_width", "face_len", "face_dart", "face_brow", "face_nose", "face_dia",
        "face_clock"} <= set(shown), shown
f.face_dart = 45.0  # (on a face's loop, the darts narrow to what opens flat)
M = built("Tube")
assert not warns(), warns()
# the muzzle meets the loop along the top edge of the facet each side of C
for t in M.samples:
    N, G = world(M, "Tube1.NoseL", t), world(M, "Tube1.GFL" + str(len(
        [n for n in M.panels if n.startswith("Tube1.GFL")])), t)
    assert len([w for w in N if min((w - v).length for v in G) < 0.05]) >= 2, t
f.face_dart, f.front_style, f.front = 15.0, "OUT", 45.0  # a pointed front: flat cheeks
M = built("Tube")
assert "Tube1.NoseL" in M.panels
f.muzzle = False
M = built("Tube")
assert "Tube1.NoseL" not in M.panels
print("an animal face: a loop with a muzzle folded back by a dart")

addon.unregister()
print("V82 OK")
