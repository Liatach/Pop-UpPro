"""v0.83: Kim's notes on v0.82. Slotted cross pieces in millimetres, placed,
slotted where asked and several on a sheet; an opening cut across a fold
(a gate through a tower's corner); towers named, laid out upright and their
faces' Y running up them; a box with ends' tuck flaps and its far tab
inside. (The house's roof: tests/test_book_v82.py.)"""
# families: folds45, tubes, boxes, openings, layout
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import holes, ui  # noqa: E402
from popup_pro.core import openings  # noqa: E402
from popup_pro.core.geom import poly_area, v3  # noqa: E402
from popup_pro.core.layout import build_layout  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402
from popup_pro.props import PopupMech  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_stub import draw, props_shown  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}, (kind, kw)
    return st.mechs[-1]


def model():
    return Model(st.card_dict(), [m.to_dict() for m in st.mechs])


def warns():
    return [w for w in st.warnings.split("\n") if w]


def reset():
    st.mechs.clear()
    st.openings.clear()
    st["pop_next_uid"] = 1


def world(M, name, t):
    p = M.panels[name]
    A = p.asm(t)
    return [A @ v3(q) for poly in p.polys for q in poly]


# ---- slotted cross pieces
rn = PopupMech.bl_rna.properties
for nm in ("cross_height", "cross_width", "slot_height", "cross_pos", "cross_gap",
           "face_ear", "face_width", "face_len"):
    assert rn[nm].unit == "NONE", (nm, rn[nm].unit)  # (millimetres, not metres)
r = add("RISER")
r.slotted, r.height, r.width = True, 80.0, 90.0
shown = props_shown(draw(ui.POPUP_PT_mechs))
assert {"slot_height", "cross_count", "cross_pos"} <= set(shown), shown
assert "cross_gap" not in shown
r.cross_count, r.cross_gap, r.cross_pos = 3, 25.0, 5.0
assert "cross_gap" in props_shown(draw(ui.POPUP_PT_mechs))
M = model()
assert not M.warnings, M.warnings
assert {"Rise1x", "Rise1x2", "Rise1x3"} <= set(M.pieces)
t = M.tmax
for k, x in enumerate(("Rise1x.Cross", "Rise1x2.Cross", "Rise1x3.Cross")):
    yc = r.y + 0.5 * r.width + 5.0 + (k - 1) * 25.0
    S = M.panels["Rise1.Sheet"].asm(t)
    for a in (0.0, 30.0):  # each stands in its own slot
        p = M.panels[x].asm(t) @ v3((a, 0.0))
        q = S @ v3((a, yc - r.y))
        assert (p - q).length < 0.02, (x, a)
r.cross_count, r.cross_pos = 1, 0.0
r.cross_height, r.slot_height = 50.0, 30.0  # the sheet (80) is taller: slotted from its foot
M = model()
ym = 0.5 * r.width
slot = [poly for poly in M.panels["Rise1.Sheet"].polys
        if abs(min(q[1] for q in poly) - (ym - 1.0)) < 1e-6 and
        abs(max(q[1] for q in poly) - (ym + 1.0)) < 1e-6]
assert len(slot) == 1 and abs(min(q[0] for q in slot[0]) - 30.0) < 1e-6  # (sheet: 30 up)
cx = M.panels["Rise1x.Cross"].polys
mid = [poly for poly in cx if max(abs(q[1]) for q in poly) <= 1.0 + 1e-6]
assert len(mid) == 1 and abs(max(q[0] for q in mid[0]) - 30.0) < 1e-6  # (cross: below 30)
tabs = [n for n in M.order if n.startswith("Rise1.Tab")]
assert len(tabs) == 2  # (slot from the foot right at the middle: no extra gap)
r.cross_pos = 20.0  # the slot off the middle: the foot's tab skips it
M = model()
assert len([n for n in M.order if n.startswith("Rise1.Tab")]) == 3
r.cross_count, r.cross_gap = 2, 5.0
M = model()
assert any("overlap" in w for w in M.warnings), M.warnings
print("slotted cross pieces: placed, slotted where asked, several")
reset()

# ---- a castle's front tower, its gate across the corner
add("TUBE", variant="CASTLE")
c = st.mechs[0]
c.front_style, c.front = "OUT", 50.0
tw = add("BOX", host=c.uid, fold="KF")
assert tw.label == "Castle 1: front tower", tw.label
bpy.ops.popup.build()
M = model()
pc = f"Box{tw.uid}"
lay = build_layout(M)
for n in M.pieces:
    if n.startswith("Box"):
        assert getattr(M.pieces[n], "upright", False)
        assert abs(lay["prints"][n].to_euler().z) < 1e-6, n  # (laid out as it stands)
a_, b_ = f"{pc}.AC", f"{pc}.CB"
assert "wall by tab" in M.panels[a_].label
for f in (a_, b_):
    org, across, up, clip = openings.face_frame(M, f)
    assert up == (0.0, 1.0), up  # (Y runs up the tower)
    A = M.panels[f].asm(M.t_ref).to_3x3()
    assert (A @ v3((0.0, 1.0))).z > 0.99
bpy.ops.popup.add_opening()
o = st.openings[-1]
o.on_piece, o.face, o.shape = pc, b_, "ARCH"
o.width, o.height, o.y = 14.0, 25.0, 2.0
xs = [q[0] for q in M.panels[b_].polys[0]]
o.x = -0.5 * (max(xs) - min(xs))  # centred on the corner crease
shown = props_shown(draw(ui.POPUP_PT_openings))
assert "across" in shown, shown


def cut_faces():
    h = holes.collect(sc, M)
    return [n for n in (a_, b_) if holes.cut(M.panels[n].polys[0], h.get(pc, [])) is not None]


assert cut_faces() == [b_]  # (stops at the fold, as before)
o.across = True
assert cut_faces() == [a_, b_]
poly = openings.place(M, openings.opening_dict(o))
assert abs(abs(poly_area(poly)) - abs(poly_area(openings.shape("ARCH", 0, 0, 14, 25)))) < 0.5
print("a gate across the front tower's corner; towers upright")
reset()

# ---- a box with ends: tuck flaps and the far tab inside
b = add("BOXEND")
try:
    from shapely.geometry import Polygon  # (pip install shapely: the pattern overlap check)
except ImportError:
    Polygon = None

for side in ("R", "L"):
    b.box_side = side
    M = model()
    assert not M.warnings, M.warnings
    tucks = [n for n in M.order if "Tuck" in n]
    assert len(tucks) == 4, tucks
    pcs = M.pieces["BoxE1"]
    pp = [(n, Polygon(poly)) for n in pcs.panels for poly in M.panels[n].polys] \
        if Polygon else []
    for i, (n1, p1) in enumerate(pp):  # (nothing overlaps in the pattern)
        for n2, p2 in pp[i + 1:]:
            if n1 != n2:
                assert p1.intersection(p2).area < 0.05, (n1, n2)
    for e in "FK":
        for tag, tg in (("C", "Tp"), ("D", "Fw")):
            n = f"BoxE1.{e}Tuck{tag}"
            T = M.panels[f"BoxE1.{e}{tg}"]
            for i in range(95, 181, 5):  # (as it stands up and opens)
                t = float(i)
                nt = T.asm(t).to_3x3() @ v3((0.0, 0.0, 1.0))
                o_ = T.asm(t) @ v3((0.0, 0.0))
                ds = [nt.dot(w - o_) for w in world(M, n, t)]
                assert min(ds) > -0.05 or max(ds) < 0.05, (n, t, ds)  # (never through)
            # open: just behind the panel, inside the box
            t = M.tmax
            nt = T.asm(t).to_3x3() @ v3((0.0, 0.0, 1.0))
            o_ = T.asm(t) @ v3((0.0, 0.0))
            box = sum(world(M, "BoxE1.A", t) + world(M, "BoxE1.B", t), v3((0.0, 0.0))) / 8
            sg = 1.0 if nt.dot(box - o_) > 0 else -1.0
            ds = [sg * nt.dot(w - o_) for w in world(M, n, t)]
            assert min(ds) > -0.05 and max(ds) > 0.3, (n, ds)
b.box_side, b.tucks = "R", False
assert not [n for n in model().order if "Tuck" in n]
shown = props_shown(draw(ui.POPUP_PT_mechs))
assert {"tucks", "far_tab"} <= set(shown), shown
b.far_tab = "IN"
M = model()
xs = [w.x for w in world(M, "BoxE1.TabI", M.tmax)]
assert min(xs) > 0.0 and max(xs) < b.depth + 0.5, xs  # (folded back under the box)
b.depth = 12.0
assert any("overlap under the box" in w for w in model().warnings)
print("a box with ends: tuck flaps, the far tab inside")

addon.unregister()
print("V83 OK")
