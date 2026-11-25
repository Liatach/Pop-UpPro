"""v0.96: more opening shapes: triangles, window panes (2 x 2), round corners
(an inverse arch that runs off the paper's edge to round a corner off)."""
# families: holes, export
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import export_svg  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
svg = os.path.join(tempfile.mkdtemp(), "t.svg")
if os.environ.get("SVG_OUT"):
    svg = os.environ["SVG_OUT"]


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


from popup_pro import holes  # noqa: E402
from popup_pro.core.geom import poly_area  # noqa: E402

reset()
b = add("BOX")
bpy.ops.popup.build()
assert not warns(), warns()


def opening(shape, x, y, w, h, on="", face="", turn=0.0):
    o = st.openings.add()
    o.on_piece, o.face, o.shape = on, face, shape
    o.x, o.y, o.width, o.height, o.turn = x, y, w, h, turn
    return o


# on the card: a triangle and a window's four panes
opening("TRI", -60.0, 30.0, 30.0, 40.0)
opening("WINDOW", 60.0, 30.0, 40.0, 50.0)
M = model()
hs = holes.collect(sc, M)["Card"]
tri = [h for h in hs if len(h) == 3]
assert len(tri) == 1 and abs(abs(poly_area(tri[0])) - 0.5 * 30 * 40) < 1e-3, tri
panes = [h for h in hs if len(h) == 4]
assert len(panes) == 4, panes
bar = 0.12 * 40.0
assert abs(sum(abs(poly_area(h)) for h in panes) - (40 - bar) * (50 - bar)) < 1e-3
# a round corner on the box's front, its top right corner on the front's
# corner: it runs off the paper's free edge, but stops short of the folds
fr = f"Box{b.uid}.CB"
ff = M.panels[fr]
from popup_pro.core.openings import face_frame  # noqa: E402
org, ac, up, clip = face_frame(M, fr)
xs = [q[0] * ac[0] + q[1] * ac[1] for q in clip]
half = 0.5 * (max(xs) - min(xs))
ys = [q[0] * up[0] + q[1] * up[1] for q in clip]
hgt = max(ys) - min(ys)
o = opening("CORNER", half - 4.0, hgt - 12.0, 12.0, 12.0, on=f"Box{b.uid}", face=fr)
bpy.ops.popup.build()
assert not [w for w in warns() if "cuts it free" in w], warns()
M = model()
hc = [h for h in holes.collect(sc, M).get(f"Box{b.uid}", []) if len(h) > 8]
assert len(hc) == 1, holes.collect(sc, M)
# (the corner's square less a quarter circle, a hair short of the top fold,
# put 2 mm past the side so it surely cuts right through)
cut = abs(poly_area(hc[0]))
assert 20.0 < cut <= 144.0 - 0.25 * 3.1416 * 144.0 + 0.5, cut
# it runs past the front's free side edge (cut right off), not just to it
assert max(q[0] * ac[0] + q[1] * ac[1] for q in hc[0]) > max(xs) + 1.5
export_svg.export(sc, svg)
print("openings: triangles, window panes and round corners")
# line files can outline where the tabs glue, blue on their own layer
import glob  # noqa: E402
for content in ("LINES", "CREASE", "CUT"):
    for f_ in glob.glob(os.path.splitext(svg)[0] + "*"):
        os.remove(f_)
    export_svg.export(sc, svg, content=content, glue_lines=True)
    text = "".join(open(f_).read() for f_ in glob.glob(os.path.splitext(svg)[0] + "*.svg"))
    n = text.count('stroke="#0000ff"')
    assert (n >= 2) == (content != "CUT"), (content, n)  # (both the box's tabs, on the card)
    export_svg.export(sc, svg, content=content)
    text = "".join(open(f_).read() for f_ in glob.glob(os.path.splitext(svg)[0] + "*.svg"))
    assert 'stroke="#0000ff"' not in text
print("glue areas outlined in line files when asked")
# a V-fold glued away from the spine, its arch cut away: the half in even
# triangles (no fan of long slivers from one corner); Square really square
import math  # noqa: E402
while len(st.openings):
    st.openings.remove(0)
for how in ("ROUND", "SQUARE", "BOX", "POINTED"):
    reset()
    v = add("VFOLD")
    v.y, v.height, v.glue_from, v.arch, v.arch_shape = 60.0, 50.0, 15.0, 22.0, how
    bpy.ops.popup.build()
    assert not warns(), (how, warns())
    M = model()
    P_ = M.panels[f"VFold{v.uid}.HalfL"]
    assert len(P_.polys) > 10
    for t in P_.polys:
        assert len(t) == 3
        for i in range(3):
            p_, q_, r_ = (v3(t[(i + k) % 3]) for k in range(3))
            assert math.degrees((q_ - p_).angle(r_ - p_)) > 20.0, (how, t)
    if how == "BOX":
        # (a corner of the cut, square: straight up from the tab start then across)
        pts = {(round(q[0], 2), round(q[1], 2)) for t in P_.polys for q in t}
        assert any(abs(x - x2) < 0.05 and abs(y2 - y - 22.0) < 0.05 and abs(x) > 5
                   for x, y in pts for x2, y2 in pts), sorted(pts)[:8]
    export_svg.export(sc, svg)
print("V-fold arch cuts: even triangles")
print("V96 OK")
