"""v0.41: extra creases that leave the paper free to fold more than one way
(a concertina, a fan in a V-fold) settle as paper does: evenly, both sides
alike, flat when the card is. Concertina pre-folds them, alternating
mountain and valley, so they pleat as the card closes."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402
from popup_pro.ops import _add  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
m0 = _add(st, "VFOLD")
m0.y, m0.height, m0.glue = 60, 60, 45
base = m0.to_dict()


def angles(m, n, t):
    p = m.panels[n]
    M = m.panels[p.parent].asm(t).inverted() @ p.asm(t)
    return math.degrees(math.acos(max(-1.0, min(1.0, M[2][2]))))


R = 300.0
fans = {
    "radiating": [dict(kind="CREASE", mirror=True,
                       pts=[(0, 0), (-R * math.sin(math.radians(a)), R * math.cos(math.radians(a)))])
                  for a in (15, 30, 45)],
    "parallel": [dict(kind="CREASE", mirror=True, pts=[(-d, -5), (-d, 300)])
                 for d in (8, 16, 24)],
}
for name, lines in fans.items():
    for pleat in (0.0, 60.0):
        d = dict(base, lines=lines, pleat=pleat)
        m = Model(st.card_dict(), [d])
        m.check_fit()
        m.solve_hinges()
        folds = [n for n in m.order if ".Fold" in n]
        assert len(folds) == 6 and not m.warnings, (name, pleat, m.warnings)
        for n in folds:
            assert angles(m, n, 180) < 0.5, (name, n, "flat when the card is")
        if pleat == 0:
            for n in folds:  # free to stay flat: nothing pulls them
                assert angles(m, n, 90) < 1.0, (name, n, angles(m, n, 90))
        else:
            L, Rt = folds[:3], folds[3:]
            for a, b in zip(L, Rt):
                assert angles(m, a, 30) > 10 and angles(m, a, 90) > 10, (name, a)
                assert abs(angles(m, a, 90) - angles(m, b, 90)) < 1.0, (name, a, b)
                assert abs(angles(m, a, 30) - angles(m, b, 30)) < 1.0, (name, a, b)
                assert angles(m, a, 3) < 15, (name, a, "nearly flat as it shuts")
        print(f"{name} concertina {pleat:.0f}: all six folds", "pleat" if pleat else "stay flat")

# ---- in Blender: the rig follows the pleats
m0.lines.clear()
for ln in fans["parallel"]:
    x = m0.lines.add()
    x.kind, x.mirror = "CREASE", True
    (x.x0, x.y0), (x.x1, x.y1) = ln["pts"]
m0.pleat = 60.0
st.keep_open = False
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
model, lay = build.make_model(sc)
rig, card = st.rig, st.card
s = 1 / st.mm_per_unit
me = card.data
attr = me.attributes["pop_panel"]
worst = 0.0
for t in (20, 60, 100, 140, 180):
    rig["pop_open"] = float(t)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    real = t if not rig.get("pop_close") else rig["pop_close"] + t * (180 - rig["pop_close"]) / 180
    for poly in me.polygons:
        p = model.panels[model.order[attr.data[poly.index].value]]
        D = model.shown(p.name, real) @ lay["prints"][p.piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s)) * s).length / s)
assert worst < 0.5, worst
print(f"the rig follows the pleats to {worst:.3f} mm")
print("all v41 checks pass")
