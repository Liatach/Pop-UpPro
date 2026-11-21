"""v0.90: the animal face as a mirrored low-poly mesh on the fold."""
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


# ---- a mirrored low-poly face on the fold: a V-fold whose halves are meshes,
# crushed flat as the card closes
reset()
f = add("HEAD")
assert f.label.startswith("Face")
shown = set(props_shown(draw(ui.POPUP_PT_mechs)))
assert {"head_brow", "head_nose", "head_muzzle", "head_chin", "mouth_w", "mouth_d",
        "mouth_a", "ear_clock", "ear_base", "ear_size", "width", "height"} <= shown, shown
bpy.ops.popup.build()
assert not warns(), warns()
M = model()
L = sorted(n for n in M.panels if n.startswith("Head1.L"))
assert len(L) == 9 and all(n.replace(".L", ".R") in M.panels for n in L)
for n in ("Head1.EarL", "Head1.EarR", "Head1.ForeheadTab", "Head1.MuzzleTab", "Head1.ChinTab"):
    assert n in M.panels, n


def corners(n, t):
    return world(M, n, t)


for t in M.samples + [M.tmax]:
    # the halves mirror each other and meet down the middle: every left corner
    # on the mirror plane (x = 0) has its right twin on it too
    for n in L:
        wl, wr = corners(n, t), corners(n.replace(".L", ".R"), t)
        for w in wl:
            if abs(w.x) < 0.05:
                assert min((w - v).length for v in wr) < 0.05, (t, n, w)
    # the facets keep their size, near enough (the card crushes, it hardly stretches)
    for n in L:
        P_ = M.panels[n]
        q = P_.polys[0]
        A = P_.asm(t)
        for i in range(3):
            a_, b_ = v3(q[i]), v3(q[(i + 1) % 3])
            L0 = (a_ - b_).length
            tol = 0.05 if t > 2.0 else 0.1  # (pressed right shut, a little more)
            assert abs((A @ a_ - A @ b_).length / L0 - 1.0) < tol, (t, n)
clean(M, "Head1")
# open, it stands up; shut, it lies pressed flat between the pages
top = max(w.z for n in L for w in corners(n, M.tmax))
assert top > 0.8 * f.height
# the pattern: one piece, the left half on the left of C, the right its mirror
for n in L:
    assert all(q[0] <= 1e-6 for q in M.panels[n].polys[0]), n
export_svg.export(sc, svg)
# the landmarks move it
z0 = max(w.z for w in corners("Head1.L3", M.tmax))
f.height = 35.0
M = model()
assert not warns(), warns()
assert max(w.z for w in corners("Head1.L3", M.tmax)) > z0 + 5.0
f.height = 25.0
for k, v in (("mouth_a", -20.0), ("ear_clock", 9.0), ("ear_clock", 11.0), ("head_brow", 0.0),
             ("head_chin", 0.0), ("mouth_w", 0.0)):
    old = getattr(f, k)
    setattr(f, k, v)
    bpy.ops.popup.build()
    assert not warns(), (k, v, warns())
    setattr(f, k, old)
f.mouth_d = 60.0
bpy.ops.popup.build()
assert any("mouth runs past" in w for w in warns()), warns()
f.mouth_d = 12.0
# pictures go on its facets
from popup_pro import props  # noqa: E402
p = add("PICTURE")
p.host_uid = 1
items = [i[0] for i in props.pic_face_items(p, bpy.context)]
assert "Head1.L1" in items, items
print("an animal face: a mirrored low-poly mesh on the fold")

addon.unregister()
print("V90 OK")
