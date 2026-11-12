"""v0.78: a cone's lean set as an angle (Lean, another way to set Top Radius)
and a lid on a cone (a flat roof the shape of its top, peaked or dipped); a
collar's railing runs into the curled corner as one strip, bending where the
curl starts instead of splitting there; clicking a warning in Checks selects
the mechanism it is about."""
# families: cones, loops, roofs, collars, ui
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, live, ops, ui  # noqa: E402
from popup_pro.core.model import SAMPLES  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_stub import draw  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}, (kind, kw)
    return st.mechs[-1]


def close(a, b, tol=0.01):
    return abs(a - b) <= tol


# ---- Lean: Top Radius as an angle, each setting the other
m = add("TUBE", variant="LOOP")
m.height = 30.0
assert m.cone_lean == 0.0 and m.cone_top == 0.0  # straight up
m.cone_lean = 20.0
assert close(m.cone_top, m.x - 30.0 * math.tan(math.radians(20.0))), m.cone_top
assert close(m.cone_lean, 20.0)
m.cone_lean = -15.0  # flared
assert m.cone_top > m.x and close(m.cone_lean, -15.0)
m.cone_top = 10.0
assert close(m.cone_lean, math.degrees(math.atan2(m.x - 10.0, 30.0)))
m.height = 60.0  # (Top Radius is what's kept: a taller cone leans less)
assert close(m.cone_top, 10.0) and close(m.cone_lean, math.degrees(math.atan2(m.x - 10.0, 60.0)))
m.height = 30.0
m.cone_lean = 80.0  # never to a point
assert close(m.cone_top, 1.0)
m.cone_lean = 0.0
assert m.cone_top == 0.0
print("Lean and Top Radius set each other")

# ---- a lid on a cone
for lean in (20.0, -15.0):
    for fold in ("PEAK", "DIP"):
        m.cone_lean, m.roof, m.roof_fold = lean, "FLAT", fold
        model = build.make_model(sc)[0]
        P = model.panels
        L, R, wl = P[f"Roof{m.uid}.L"], P[f"Roof{m.uid}.R"], P[f"Tube{m.uid}.FL_"]
        assert f"Tube{m.uid}.TopL" in P and f"Tube{m.uid}.TopR" in P  # its tabs
        rt = m.cone_top
        ys = [p[1] for p in L.polys[0]]
        for t in SAMPLES:
            for y in (min(ys), max(ys)):  # the halves stay together down the crease
                gap = (L.asm(t) @ Vector((0, y, 0)) - R.asm(t) @ Vector((0, y, 0))).length
                assert gap < 1e-3, (lean, fold, t, gap)
            for y in ys[:2]:  # and each stays on its wall's top edge
                off = (wl.asm(t).inverted() @ (L.asm(t) @ Vector((-rt, y, 0)))).z
                assert abs(off) < 1e-3, (lean, fold, t, off)
        # flat when the card is open, and peaked or dipped part-way
        up = (L.asm(180.0).to_3x3() @ Vector((0, 0, 1)))
        assert abs(abs(up.z) - 1.0) < 1e-4, up
        hinge = L.asm(90.0) @ Vector((-rt, ys[0], 0))
        rise = L.asm(90.0) @ Vector((0, ys[0], 0)) - hinge
        foot = wl.asm(90.0) @ Vector((*wl.polys[0][0], 0.0))
        for q in wl.polys[0]:  # the wall's point furthest from its top: its foot
            w_ = wl.asm(90.0) @ Vector((*q, 0.0))
            if (w_ - hinge).length > (foot - hinge).length:
                foot = w_
        zs = [model.panels[P[f"Tube{m.uid}.{w}"].parent].asm(90.0).to_3x3() @ Vector((0, 0, 1))
              for w in ("FL_", "FR_")]
        up = (zs[0] + zs[1]).normalized()  # between the two pages' normals
        if up.dot(hinge - foot) < 0:
            up = -up
        assert (rise.dot(up) > 0) == (fold == "PEAK"), (lean, fold, rise.dot(up))
        if (lean, fold) == (-15.0, "DIP"):  # wider than the walls are tall
            assert any("dipped lid tucks" in w for w in model.warnings), model.warnings
        else:
            assert not model.warnings, (lean, fold, model.warnings)
# the lid reaches the built card
bpy.ops.popup.build()
names = [p["name"] for p in live.meta(st.rig)["panels"]]
vals = [0] * len(st.card.data.polygons)
st.card.data.attributes["pop_panel"].data.foreach_get("value", vals)
missing = [n for i, n in enumerate(names) if n.startswith(f"Roof{m.uid}") and i not in set(vals)]
assert not missing, missing
# other roofs still need a straight tube
m.cone_lean, m.roof = 20.0, "POINTED"
model = build.make_model(sc)[0]
assert any("no roof or a flat one (a lid)" in w for w in model.warnings), model.warnings
m.roof = "NONE"
print("a cone's lid: flat open, peaked or dipped, its halves together on the walls' tops")

# ---- a collar's railing: one strip into the curled corner
st.mechs.clear()
t = add("TUBE")
t.y, t.x, t.depth, t.height = 105.0, 30.0, 40.0, 25.0
t.front = t.back = 30.0
b = add("BOX", host=t.uid, fold="KFL")
b.height = b.depth = 18.0
b.width = 75.0
b.collar = True
b.collar_below, b.collar_width, b.collar_slope, b.collar_rail = 30.0, 9.0, 60.0, 5.0
model = build.make_model(sc)[0]
assert not model.warnings, model.warnings
curls = [n for n in model.panels if n.endswith("CurlRail")]
assert len(curls) == 2, curls
for cn in curls:
    A, B, C = model.panels[cn.replace("CurlRail", "Rail")], model.panels[cn], model.panels[cn[:-4]]
    assert B.parent == A.name  # (v0.77: it hung on the curl, and split from the railing)
    pa = [Vector(p) for poly in A.polys for p in poly]
    pb = [Vector(p) for poly in B.polys for p in poly]
    seam = [p for p in pb if any((p - q).length < 1e-4 for q in pa)]
    assert len(seam) == 2 and abs((seam[0] - seam[1]).length - 5.0) < 1e-3, seam
    bend = 0.0
    for tt in SAMPLES:
        for p in seam:  # no gap anywhere up the line where the curl starts
            assert (A.asm(tt) @ p.to_3d() - B.asm(tt) @ p.to_3d()).length < 1e-3, (cn, tt)
        nA = A.asm(tt).to_3x3() @ Vector((0, 0, 1))
        nB = B.asm(tt).to_3x3() @ Vector((0, 0, 1))
        bend = max(bend, math.degrees(nA.angle(nB)))
        # it stays by the curl's edge (cut free of it, within a few mm)
        pc = [Vector(p) for p in C.polys[0]]
        foot = [p for p in pb if any((p - q).length < 1e-4 for q in pc)]
        assert max((B.asm(tt) @ p.to_3d() - C.asm(tt) @ p.to_3d()).length for p in foot) < 3.0
    assert 20.0 < bend < 60.0, bend  # (it does bend there, following the curl)
    assert model.fold_kind[frozenset((A.name, B.name))] == "skip"  # no line printed
print("collar railing: one strip, bending where the curl starts")

# ---- clicking a warning in Checks selects its mechanism
st.mechs.clear()
a = add("BOX")
c = add("TUBE", variant="LOOP")
c.y, c.height = 150.0, 30.0
c.cone_lean, c.roof, c.roof_fold = -15.0, "FLAT", "DIP"
v = add("VFOLD")
v.y, v.height = 80.0, 400.0  # (sticks out of the card)
bpy.ops.popup.build()
ws = st.warnings.splitlines()
assert any(w.startswith(c.label + " lid:") for w in ws), ws
assert any(w.startswith(v.label + ":") for w in ws), ws
for w in ws:
    mm = ops.warned_mech(st, w)
    assert mm is not None and w.startswith(mm.label), w
assert ops.warned_mech(st, "Card: too small") is None
# "Box fold 1" isn't taken for "Box fold 12"
st.mechs[0].label = "Box fold 1"
x = add("BOX")
x.label = "Box fold 12"
assert ops.warned_mech(st, "Box fold 12: sticks out").uid == x.uid
assert ops.warned_mech(st, "Box fold 1: sticks out").uid == st.mechs[0].uid
assert ops.warned_mech(st, "Box fold 1 and Box fold 12 overlap").uid == st.mechs[0].uid
log = draw(ui.POPUP_PT_checks)
btn = [e for e in log if e[1] == "operator" and e[2][0] == "popup.select_warned"]
assert len(btn) == len([w for w in st.warnings.splitlines() if ops.warned_mech(st, w)]) > 0
uid_of = {e[3]["text"]: next(s[2][1] for s in log if s[1] == "set" and s[2][0] == "uid"
                             and s[0].startswith(e[0] + ".operator"))
          for e in btn}
st.active = 0
w = next(w for w in uid_of if w.startswith(c.label))
assert bpy.ops.popup.select_warned(uid=uid_of[w]) == {"FINISHED"}
assert st.mechs[st.active].uid == c.uid
assert bpy.ops.popup.select_warned(uid=9999) == {"CANCELLED"}
print("Checks: a click on a warning selects its mechanism")

addon.unregister()
print("V78 OK")
