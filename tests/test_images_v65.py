"""v0.65: pictures glued on any face (a stand-up on a box's front, pictures
on 45 degree triangles, on a page, on a face's back), and the stand-up's
rolled tail: picture and bridge in one piece."""
# families: images, standups
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
from popup_pro import build, export_svg  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def rig_error():
    rig, card = st.rig, st.card
    if rig.animation_data:
        rig.animation_data.action = None
    model, lay = build.make_model(sc)
    me = card.data
    at = me.attributes["pop_panel"]
    s = 1 / st.mm_per_unit
    t0 = rig["pop_close"]
    worst = 0.0
    for t in (0.0, 47.0, 90.0, 150.0, 180.0):
        rig["pop_open"] = t
        rig.update_tag()
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        ev = card.evaluated_get(dg).data
        real = t0 + t * (180 - t0) / 180
        for poly in me.polygons:
            name = model.order[at.data[poly.index].value]
            P = lay["prints"][model.panels[name].piece].inverted()
            for vi in poly.vertices:
                q = P @ (me.vertices[vi].co / s)
                worst = max(worst, (ev.vertices[vi].co / s - model.point(name, q, real)).length)
    return worst


def shut_spread(model):
    nr = model.panels["Page.R"].asm(0.5).to_3x3() @ Vector((0, 0, 1))
    d = [(p.asm(0.5) @ v3(q)).dot(nr) for p in model.panels.values() for poly in p.polys
         for q in poly]
    return max(d) - min(d)


# ---- a picture on a box's front: it stands up with it
assert bpy.ops.popup.add(kind="BOX") == {"FINISHED"}
bx = st.mechs[0]
bx.y, bx.width, bx.height, bx.depth = 40.0, 50.0, 30.0, 30.0
bpy.ops.popup.build()
st.active = 0
assert bpy.ops.popup.add(kind="PICTURE") == {"FINISHED"}
pic = st.mechs[-1]
assert pic.host_uid == bx.uid and pic.face.startswith(f"Box{bx.uid}.")
pic.face = f"Box{bx.uid}.CB"
pic.img_w, pic.img_h, pic.pic_y, pic.pic_x = 60.0, 70.0, 5.0, -30.0
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
P = model.panels
face = P[f"Pic{pic.uid}.Face"]
assert face.parent == f"Box{bx.uid}.CB"
for t in (30.0, 90.0, 160.0):  # glued flat on the front, just off it
    F = P[f"Box{bx.uid}.CB"].asm(t)
    n = F.to_3x3() @ Vector((0, 0, 1))
    for q in face.polys[0]:
        d = (face.asm(t) @ v3(q) - F.to_translation()).dot(n)
        assert abs(d - 0.3) < 1e-4, d
assert rig_error() < 0.05
f0 = model.panels[f"Pic{pic.uid}.Face"]
e0 = (f0.asm(90.0) @ v3(f0.polys[0][1])) - (f0.asm(90.0) @ v3(f0.polys[0][0]))
print("a picture on a box's front: glued on, standing up with it")

# on the back of the face, turned: still flat on it, behind
pic.pic_side, pic.pic_turn = "BACK", 30.0
model = build.rebuild(sc, force=True)
F = model.panels[f"Box{bx.uid}.CB"].asm(90.0)
n = F.to_3x3() @ Vector((0, 0, 1))
face = model.panels[f"Pic{pic.uid}.Face"]
pts = [face.asm(90.0) @ v3(q) for q in face.polys[0]]
assert all(abs((w - F.to_translation()).dot(n) + 0.3) < 1e-4 for w in pts)
nf = face.asm(90.0).to_3x3() @ Vector((0, 0, 1))
assert nf.dot(n) < -0.99  # its printed side faces away from the box's front
e = pts[1] - pts[0]  # its bottom edge, turned 30 degrees on the face (mirrored behind)
ang = math.degrees(e.angle(e0))
assert abs(ang - 30.0) < 0.5 or abs(ang - 150.0) < 0.5, ang
print("on the back of a face, turned")

# ---- pictures on the 45 degree triangles, both layouts, at both ends
bx.tri45, bx.tri_size = "BOTH", 12.0
while len(st.mechs) > 1:
    st.active = 1
    bpy.ops.popup.remove()
bpy.ops.popup.build()


def rects(model):
    """{face: picture corners in the crease's own frame (x out from the
    crease, y up the card)}"""
    hc = model.hosts[(bx.uid, "C")]
    Ti = hc.T1.inverted()
    out = {}
    for m in st.mechs:
        if m.kind != "PICTURE":
            continue
        face = model.panels[f"Pic{m.uid}.Face"]
        F = model.panels[m.face].asm(180.0).inverted() @ face.asm(180.0)
        out[m.face] = [Ti @ (F @ v3(q)) for q in face.polys[0]]
    return out


for layout in ("ALONG", "OUT"):
    while len(st.mechs) > 1:
        st.active = 1
        bpy.ops.popup.remove()
    bx.tri_pic_layout = layout
    bpy.ops.popup.build()
    assert bpy.ops.popup.tri_pictures(uid=bx.uid, which="BOTH") == {"FINISHED"}
    pics = [m for m in st.mechs if m.kind == "PICTURE"]
    assert len(pics) == 4
    model = build.rebuild(sc, force=True)
    top, bot, k = bx.y + bx.width, bx.y, 12.0
    for face, R in rects(model).items():
        xs, ys = [p.x for p in R], [p.y for p in R]
        sd = -1.0 if face.endswith("L") else 1.0
        tp = ".TriT" in face
        edge = top if tp else bot
        if layout == "ALONG":
            # one edge on the crease, from the box's edge in; out across the face
            assert min(abs(x) for x in xs) < 0.01, (face, xs)
            assert max(x * sd for x in xs) > 0.9 * k, (face, xs)
            assert abs((max(ys) if tp else min(ys)) - edge) < 0.01, (face, ys)
            assert abs(max(ys) - min(ys) - 0.6 * k) < 0.01
        else:
            # standing on the triangle, past the box's edge
            assert (max(ys) > edge + 0.5 * k) if tp else (min(ys) < edge - 0.5 * k), (face, ys)
            assert min(x * sd for x in xs) > 0.0
    assert rig_error() < 0.05
    assert shut_spread(model) < 3.0, shut_spread(model)
assert bpy.ops.popup.tri_pictures(uid=bx.uid, which="LEFT") == {"CANCELLED"}  # done already
print("pictures on the 45° triangles: along the crease or out past the edge, either end")

# ---- on a page of the card
st.active = -1
while st.mechs:
    st.active = 0
    bpy.ops.popup.remove()
st.active = -1
assert bpy.ops.popup.add(kind="PICTURE") == {"FINISHED"}
pc = st.mechs[0]
assert pc.host_uid == 0 and pc.face == "Page.R"
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
# skipped, and said, when its face is gone
M = Model(st.card_dict(), [dict(uid=3, type="PICTURE", label="P", host=9, face="Box9.CB",
                                 x=0, y=0, img_w=10, img_h=10)])
assert any("missing" in w for w in M.warnings)
print("a picture on a page; one whose face is gone is said, not built")

# ---- on the double 45's top piece: it bends and twists with it
assert bpy.ops.popup.add(kind="DOUBLE45") == {"FINISHED"}
d45 = st.mechs[-1]
bpy.ops.popup.build()
for fc in ("TopF", "GF"):
    st.active = next(i for i, x in enumerate(st.mechs) if x.uid == d45.uid)
    assert bpy.ops.popup.add(kind="PICTURE") == {"FINISHED"}
    pp = st.mechs[-1]
    pp.face = f"D45{d45.uid}.{fc}"
    pp.img_w, pp.img_h, pp.pic_y, pp.pic_x = 20.0, 18.0, 2.0, -10.0
model = build.rebuild(sc, force=True)
for pp in [x for x in st.mechs if x.kind == "PICTURE" and x.host_uid == d45.uid]:
    nm = f"Pic{pp.uid}.Face"
    assert nm in model.blend
    Mw = model.blend[nm][4]
    for t in (40.0, 90.0, 140.0):
        for q in ((-10.0, 0.0), (10.0, 9.0), (0.0, 18.0)):
            f = Mw @ v3(q)
            gap = (model.point(nm, q, t) - model.point(pp.face, (f.x, f.y), t)).length
            assert gap < 0.45, (pp.face, t, q, gap)
assert rig_error() < 0.05
print("pictures on the double 45's top piece bend with it")

# ---- the stand-up's rolled tail
while st.mechs:
    st.active = 0
    bpy.ops.popup.remove()
assert bpy.ops.popup.add(kind="STANDUP") == {"FINISHED"}
su = st.mechs[0]
su.stand = "TAIL"
su.width, su.height, su.depth = 20.0, 18.0, 15.0
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
u = su.uid
P = model.panels
assert "Bridge" + str(u) not in model.pieces  # one piece
assert {P[n].piece for n in (f"Stand{u}.CB", f"Stand{u}.AC", f"Stand{u}.Foot",
                             f"Stand{u}.TabA", f"Stand{u}.TabC")} == {f"Stand{u}"}
a, b = su.height, su.depth
for t in (150.0, 90.0, 30.0):
    S, l, r, Y, nl, nr = model.hosts[(0, "S")].dirs(t)

    def w(n, q):
        return P[n].asm(t) @ v3(q)
    # a box: the bridge parallel to the floor, the picture to the background
    ac = w(f"Stand{u}.AC", (0, -2 * b - a)) - w(f"Stand{u}.AC", (0, -b - a))
    assert abs(ac.normalized().dot(r) - 1.0) < 1e-4
    pc_ = w(f"Stand{u}.CB", (0, 10)) - w(f"Stand{u}.CB", (0, 0))
    assert abs(pc_.normalized().dot(l) - 1.0) < 1e-4
    # the tail's folds meet: floor at the picture's foot, the corner, the
    # background at the bridge, and the bridge at the picture's back
    for n1, n2, y in ((f"Stand{u}.CB", f"Stand{u}.Foot", 0.0),
                      (f"Stand{u}.TabA", f"Stand{u}.AC", -b - a),
                      (f"Stand{u}.AC", f"Stand{u}.TabC", -2 * b - a)):
        assert (w(n1, (0, y)) - w(n2, (0, y))).length < 0.2, (t, n1, n2)
    assert (w(f"Stand{u}.AC", (0, -2 * b - a)) - w(f"Stand{u}.CB", (0, a))).length < 1e-4
    # glued faces flat on the floor and the background
    assert abs((w(f"Stand{u}.Foot", (0, -5)) - S).dot(nr) - 0.15) < 1e-3
    assert abs((w(f"Stand{u}.TabA", (0, -b - 5)) - S).dot(nl) - 0.15) < 1e-3
assert shut_spread(model) < 3.0
assert rig_error() < 0.05
files = export_svg.export(sc, os.path.join(tempfile.mkdtemp(), "tail.svg"))
assert files
print("rolled tail: picture and bridge one piece, a box behind its foot")
print("v0.65 OK")
