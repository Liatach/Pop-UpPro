"""v0.88: a cube's dipped lid on a V-fold strut; turning discs and wheels on a box
fold's corner triangles."""
# families: cubes, folds45
import math
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
from mathutils import Vector  # noqa: E402

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


# ---- 0.88.2: the dipped lid on a V-fold strut (two panels across the
# corner's crease, a tab on the short wall's page and one under the lid's
# larger side), pulling the lid in as the card shuts
for sz in ((55.0, 28.0, 32.0), (28.0, 55.0, 32.0), (40.0, 40.0, 40.0), (60.0, 30.0, 30.0)):
    reset()
    c = add("CUBE")
    c.size, c.size_r, c.height = sz
    c.lid = "STRUT"
    assert "strut_at" in set(props_shown(draw(ui.POPUP_PT_mechs)))
    bpy.ops.popup.build()
    assert not warns(), (sz, warns())
    M = model()
    for n in ("Cube1S.P1", "Cube1S.P2", "Cube1S.TabC", "Cube1S.TabE", "Cube1.LidL", "Cube1.LidR"):
        assert n in M.panels, (sz, n)
    for t in M.samples + [M.tmax]:
        assert M._strut_err(t)[2] < 1e-3, (sz, t, M._strut_err(t))  # (rigid: it fits exactly)
    clean(M, "Cube1")
    export_svg.export(sc, svg)
reset()
c = add("CUBE")
c.size, c.size_r, c.height, c.lid = 55.0, 28.0, 32.0, "STRUT"
c.strut_at = 200.0
assert any("strut must stand inside" in w for w in model().warnings)
print("a dipped lid on a V-fold strut")

# ---- turning discs
for on in ("FRONT", "TOP"):
    for E in (45.0, 60.0):
        reset()
        b = add("BOX")
        b.tri45, b.tri_size, b.tri_disc, b.tri_angle = "TOP", 15.0, on, E
        assert {"tri_angle", "tri_disc", "disc_r"} <= set(props_shown(draw(ui.POPUP_PT_mechs)))
        bpy.ops.popup.build()
        assert not warns(), (on, E, warns())
        M = model()
        d = M.panels["Box1discT.Disc"]
        X = M.panels[d.parent]
        angs = []
        for t in [M.tmax] + M.samples[::-1]:
            A = X.asm(t).to_3x3().inverted() @ d.asm(t).to_3x3()
            assert abs((A @ Vector((0.0, 0.0, 1.0))).z - 1.0) < 1e-6  # (flat on its face)
            v = A @ Vector((1.0, 0.0, 0.0))
            angs.append(math.degrees(math.atan2(v.y, v.x)))
        # it turns twice the triangles' angle over the whole movement
        assert abs(abs(angs[-1] - angs[0]) - 2.0 * E) < 3.0, (on, E, angs[0], angs[-1])
        clean(M, "Box1")
        export_svg.export(sc, svg)
for v, n in (("DISC", 1), ("WHEELS", 2)):
    reset()
    assert bpy.ops.popup.add(kind="BOX", variant=v) == {"FINISHED"}
    bpy.ops.popup.build()
    assert not warns(), (v, warns())
    M = model()
    assert len([x for x in M.order if x.endswith(".Disc")]) == n
    clean(M, "Box1")
# the disc can be hidden: the L piece's turning arm still shows the turn
reset()
b = add("BOX")
b.tri45, b.tri_size, b.tri_disc, b.disc_show = "TOP", 15.0, "FRONT", False
assert "disc_show" in set(props_shown(draw(ui.POPUP_PT_mechs)))
bpy.ops.popup.build()
assert not warns(), warns()
M = model()
assert not [x for x in M.order if x.endswith(".Disc")]
assert {"Box1discTL.F", "Box1discTL.G"} <= set(M.order)
print("turning discs and wheels")

# ---- 0.88.1: rectangles take lids, creased at 45 degrees
for lid in ("DIP", "PEAK"):
    for sz in ((50.0, 30.0, 35.0), (30.0, 50.0, 35.0), (60.0, 25.0, 30.0)):
        reset()
        c = add("CUBE")
        c.size, c.size_r, c.height, c.lid = (*sz, lid)
        bpy.ops.popup.build()
        assert not warns(), (lid, sz, warns())
        M = model()
        short, long_ = ("LidR", "LidL") if sz[0] > sz[1] else ("LidL", "LidR")
        assert len(M.panels[f"Cube1.{short}"].polys[0]) == 3
        assert len(M.panels[f"Cube1.{long_}"].polys[0]) == 4
        for t in M.samples:
            A, B = world(M, "Cube1.LidL", t), world(M, "Cube1.LidR", t)
            assert len([a for a in A if min((a - b).length for b in B) < 0.05]) >= 2, t
        clean(M, "Cube1")
        export_svg.export(sc, svg)
# the disc takes paste-ons
reset()
assert bpy.ops.popup.add(kind="BOX", variant="WHEELS") == {"FINISHED"}
bpy.ops.popup.build()
from popup_pro import props  # noqa: E402
p = add("PICTURE")
p.host_uid = 1
assert "Box1discT.Disc" in [i[0] for i in props.pic_face_items(p, bpy.context)]
print("rectangle lids; paste-ons on discs")

addon.unregister()
print("V88 OK")
