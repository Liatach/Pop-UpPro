"""v0.95: a slotted piece (Birmingham 59-60): glued on a page by a strip along
the spine, jutting out through a slot in a face of another mechanism."""
# families: pieces
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro.core.layout import build_layout  # noqa: E402
from popup_pro import build  # noqa: E402
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


# ---- through a box fold's front: the slot rides along the piece
reset()
b = add("BOX")
b.y, b.width, b.height, b.depth = 100.0, 50.0, 40.0, 30.0
s = add("SLOT", host=b.uid)
assert s.kind == "SLOT" and s.host_uid == b.uid and s.face == f"Box{b.uid}.CB", (s.face,)
shown = set(props_shown(draw(ui.POPUP_PT_mechs)))
assert {"pic_on", "pic_face", "pic_x", "pic_y", "img_w", "slot_jut", "slot_page",
        "slot_strip", "tab"} <= shown, shown
bpy.ops.popup.build()
assert not warns(), warns()


def check(M, s, face):
    F = M.panels[face]
    sp = M.slots[F.piece][-1]
    c_ = v3((0.5 * (sp[0][0] + sp[2][0]), 0.5 * (sp[0][1] + sp[2][1])))
    P_ = M.panels[f"Slot{s.uid}.Piece"]
    Lp = max(q[0] for q in P_.polys[0])
    page = M.panels["Page.L" if s.slot_page == "L" else "Page.R"]
    for t in M.samples + [M.tmax]:
        A = P_.asm(t)
        assert abs(A.to_3x3().determinant() - 1.0) < 1e-4
        loc = A.inverted() @ (F.asm(t) @ c_)
        # the slot's middle lies in the piece, its width inside the slot
        # (open out, aimed a paper's breadth over the slot's middle: it comes
        # out on top of the face, not under it, when everything lies flat)
        assert abs(loc.z) < (1.05 if t > 90.0 else 0.05) and abs(loc.y) < 0.05, (t, loc)
        assert 1.0 < loc.x < Lp - 2.0, (t, loc.x, Lp)
        # the strip stays on its page
        h = page.asm(t).inverted() @ (A @ v3((0.0, 0.0)))
        assert abs(h.z) < 0.05, (t, h)
    # it juts out past the face by Juts Out, open
    loc = P_.asm(M.tmax).inverted() @ (F.asm(M.tmax) @ c_)
    assert abs((Lp - loc.x) - s.slot_jut) < 1.0, (Lp, loc.x)


M = model()
check(M, s, f"Box{b.uid}.CB")
# the slot is cut in the face's piece, along the spine, the piece's width and
# a little long, 2 mm wide
sp = M.slots[M.panels[f"Box{b.uid}.CB"].piece][-1]
ex = sorted((max(q[i] for q in sp) - min(q[i] for q in sp)) for i in (0, 1))
assert abs(ex[0] - 2.0) < 1e-3 and abs(ex[1] - (s.img_w + 2.0)) < 1e-3, ex
assert M.fold_kind[frozenset((f"Slot{s.uid}.Piece", f"Slot{s.uid}.Strip"))] == "valley"
export_svg.export(sc, svg)
# through the box's top instead, glued on the right page, its strip further
# out: still riding the slot
s.face, s.slot_page, s.slot_strip = f"Box{b.uid}.AC", "R", 35.0
bpy.ops.popup.build()
assert not [w for w in warns() if "skipped" in w], warns()
M = model()
check(M, s, f"Box{b.uid}.AC")
s.face, s.slot_page, s.slot_strip = f"Box{b.uid}.CB", "L", 10.0
# a slot too far out to reach at some opening: it's lengthened, and says so
s.slot_jut = 2.0
s.slot_strip = 70.0
bpy.ops.popup.build()
M = model()
check(M, s, f"Box{b.uid}.CB") if not any("lengthened" in w for w in warns()) else None
s.slot_jut, s.slot_strip = 30.0, 10.0
# a V-fold's half (Birmingham 60: the ears through a head): its slot runs
# along the crease it's glued down by, the strip on that page parallel to it
v = add("VFOLD")
v.y, v.height = 40.0, 60.0
s2 = add("SLOT", host=v.uid)
s2.face, s2.slot_page, s2.slot_strip, s2.pic_y = f"VFold{v.uid}.HalfL", "L", 10.0, 15.0
bpy.ops.popup.build()
assert not [w for w in warns() if w.startswith(s2.label)], warns()
check(model(), s2, f"VFold{v.uid}.HalfL")
# glued on the other page it can't ride the slot: the half turns about a
# line on its own page only
s2.slot_page = "R"
bpy.ops.popup.build()
assert any(w.startswith(s2.label) and "skipped" in w for w in warns()), warns()
st.mechs.remove(len(st.mechs) - 1)
st.mechs.remove(len(st.mechs) - 1)
bpy.ops.popup.build()
assert not warns(), warns()
M = model()
# the rig follows it
st.keep_open = False
mdl = build.rebuild(sc, force=True)
rig, card = st.rig, st.card
lay = build_layout(mdl)
s_ = 1 / st.mm_per_unit
me = card.data


def rig_error(ov):
    rig["pop_open"] = float(ov)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    attr = me.attributes["pop_panel"]
    worst = 0.0
    for poly in me.polygons:
        p_ = mdl.panels[mdl.order[attr.data[poly.index].value]]
        D = mdl.shown(p_.name, ov) @ lay["prints"][p_.piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s_)) * s_).length
                        / s_)
    return worst


for ov in (180.0, 120.0, 60.0, 10.0):
    assert rig_error(ov) < 0.05, (ov, rig_error(ov))
print("a slotted piece: jutting out through a slot in a face")
print("V95 OK")
