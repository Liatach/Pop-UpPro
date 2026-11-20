"""v0.89: two pieces back to back on parallel strips (low-poly bends); the
animal face is checked in test_book_v82."""
# families: tubes
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import export_svg, ui  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_stub import draw, props_shown  # noqa: E402

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


def reset():
    st.mechs.clear()
    st["pop_next_uid"] = 1


def world(M, name, t):
    p = M.panels[name]
    A = p.asm(t)
    return [A @ v3(q) for poly in p.polys for q in poly]


def clean(M, prefix):
    for n in M.order:
        p = M.panels[n]
        if not n.startswith(prefix) or p.kind != "panel":
            continue
        for t in M.samples:
            l, r, nl, nr = M.dirs(t)
            d = min(min(w.dot(nl), w.dot(nr)) for w in world(M, n, t))
            assert d > -0.5, (n, t, d)


# ---- two pieces glued back to back, each on a strip by a tab, bending up
# into the joined top (Birmingham 53)
reset()
pr = add("TUBE", variant="PAIR")
assert pr.pair and pr.label.startswith("Pair")
shown = set(props_shown(draw(ui.POPUP_PT_mechs)))
assert {"pair_bend", "tab_side", "x", "depth", "height"} <= shown, shown
assert "front_style" not in shown
bpy.ops.popup.build()
assert not warns(), warns()
M = model()
for t in M.samples:
    # the tops meet back to back on the mirror plane, upright
    L, R = world(M, "Tube1.TopL", t), world(M, "Tube1b.TopR", t)
    for w in L + R:
        assert abs(w.x) < 0.1, (t, w)
    # each leg keeps its length, facet to facet, and starts at its tab
    for sd, pc in (("L", "Tube1"), ("R", "Tube1b")):
        ln = 0.0
        prev = None
        for k in range(1, 9):
            P_ = M.panels[f"{pc}.Leg{sd}{k}"]
            A = P_.asm(t)
            y0_, y1_ = P_.polys[0][0][1], P_.polys[0][2][1]
            a_, b_ = A @ v3((0.0, y0_)), A @ v3((0.0, y1_))
            if prev is not None:
                assert (prev - a_).length < 1e-3  # (edge to edge)
            ln += (b_ - a_).length
            prev = b_
        assert abs(ln - pr.pair_bend) < 0.05 * pr.pair_bend, (t, ln)
        tab = M.panels[f"{pc}.Tab{sd}"]
        foot = M.panels[f"{pc}.Leg{sd}1"].asm(t) @ v3((0.0, 0.0))
        assert min((foot - w).length for w in world(M, f"{pc}.Tab{sd}", t)) < 0.3
clean(M, "Tube1")
# open flat, the legs bend furthest; shut, they're straight
J = [M.panels["Tube1.TopL"].asm(t) @ v3((0.0, pr.pair_bend)) for t in (M.samples[0], M.tmax)]
assert J[0].length > J[1].length
export_svg.export(sc, svg)
# too short to reach the strips
pr.pair_bend = 15.0
bpy.ops.popup.build()
assert any("legs are too short" in w for w in warns()), warns()
pr.pair_bend = 30.0
# the top takes paste-ons
from popup_pro import props  # noqa: E402
p = add("PICTURE")
p.host_uid = 1
items = [i[0] for i in props.pic_face_items(p, bpy.context)]
assert "Tube1.TopL" in items and "Tube1b.TopR" in items, items
print("a back-to-back pair on parallel strips")

addon.unregister()
print("V89 OK")
