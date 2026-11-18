"""v0.88: a cube's lid lifted by a strut; turning discs and wheels on a box
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


# ---- the strut lid
for side in ("L", "R"):
    for sz in ((40.0, 0.0, 40.0), (50.0, 30.0, 35.0), (30.0, 30.0, 45.0)):
        reset()
        c = add("CUBE")
        c.size, c.size_r, c.height = sz
        c.lid, c.strut_side = "STRUT", side
        assert {"strut_side", "strut_at"} <= set(props_shown(draw(ui.POPUP_PT_mechs)))
        M = model()
        if sz == (50.0, 30.0, 35.0) and side == "R":
            continue  # (a lid half as deep again as its wall: it can't clear the pages)
        bpy.ops.popup.build()
        assert not warns(), (side, sz, warns())
        clean(M, "Cube1")
        wall = M.panels[f"Cube1.{'B' if side == 'L' else 'C'}"]
        page = M.panels["Page.L" if side == "L" else "Page.R"]
        for t in M.samples + [M.tmax]:
            L = world(M, "Cube1.Lid", t)
            # hinged on the wall's top edge
            W = world(M, wall.name, t)
            assert len([q for q in L if min((q - w).length for w in W) < 0.05]) >= 2, t
            # the strut's top runs along under the lid
            S = world(M, "Cube1S.Strut", t)[2:]
            n = (L[1] - L[0]).cross(L[3] - L[0]).normalized()
            assert max(abs((q - L[0]).dot(n)) for q in S) < 0.6, (side, t)
        # shut on the box open flat; parallel to its page while it's clear
        t = M.tmax
        nl = (world(M, "Cube1.Lid", t)[1] - world(M, "Cube1.Lid", t)[0]).cross(
            world(M, "Cube1.Lid", t)[3] - world(M, "Cube1.Lid", t)[0]).normalized()
        npg = page.asm(t).to_3x3() @ Vector((0.0, 0.0, 1.0))
        assert abs(abs(nl.dot(npg)) - 1.0) < 1e-4
        export_svg.export(sc, svg)
c.strut_at = 200.0
assert any("strut must stand inside" in w for w in model().warnings)
print("a lid lifted by a strut")

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
        d = M.panels["Box1TriTDisc.Disc"]
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
print("turning discs and wheels")

addon.unregister()
print("V88 OK")
