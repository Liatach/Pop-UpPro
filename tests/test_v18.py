"""v0.18: creases and cuts in the card itself (the background folding in as a
ceiling or floor), V-folds on a floor's or ceiling's crease, crossing and
chained creases solved together, and line ends that meet an edge exactly."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
from mathutils import Vector  # noqa: E402

import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

W, H = 148.5, 210.0
STAGE = dict(W=W, H=H, hold="SYM", tmax=120.0)  # one of three carousel stages


def crease(p, q, mirror=True):
    return dict(kind="CREASE", mirror=mirror, pts=[p, q])


# ---- the background folds in as a ceiling and a floor
phi = math.radians(60)
ceil = crease((0, 0.75 * H), (-300 * math.sin(phi), 0.75 * H + 300 * math.cos(phi)))
floor = crease((0, 0.25 * H), (-300 * math.sin(phi), 0.25 * H - 300 * math.cos(phi)))
m = Model(dict(STAGE, lines=[ceil, floor]), [])
assert not m.warnings, m.warnings
folds = [n for n in m.order if n.startswith("Card.Fold")]
assert len(folds) == 4, folds
for n in folds:
    p = m.panels[n]
    top = p.polys[0][0][1] > H / 2 or any(q[1] > 0.8 * H for poly in p.polys for q in poly)
    z = p.asm(120.0).to_3x3() @ Vector((0, 0, 1))
    # the printed side faces into the stage: down from a ceiling, up off a floor
    assert (z.y < -0.6) if top else (z.y > 0.6), (n, z)
print("background folds in as a ceiling and a floor")

# ---- a V-fold on a floor's crease rises into the stage (and on a ceiling's,
# hangs down into it); boxes are turned away
for kind, sgn in (("FLOOR", 1), ("CEILING", -1)):
    F = dict(type=kind, uid=1, label=kind, y=0, depth=W, lead=0, tab=8, host=0)
    V = dict(type="VFOLD", uid=2, label="V", y=40, phi_l=60, phi_r=60, alpha_l=80,
             alpha_r=80, glue=20, height=25, tab=6, tab_side="IN", host=1, vside="V")
    m = Model(STAGE, [F, V])
    m.check_fit()
    assert not m.warnings, (kind, m.warnings)
    for t in (30, 90, 120):
        assert sgn * m.crease("VFold2", t)[0].y > 0.5, (kind, t)
    B = dict(type="BOX", style="GLUED", uid=3, label="B", y=30, width=10, height=10,
             depth=10, tab=5, host=1, vside="V")
    m = Model(STAGE, [F, B])
    assert any("only V-folds" in w for w in m.warnings), m.warnings
print("V-folds on floor and ceiling creases")

# ---- crossing creases on a beak (your tree): solved together
tree = dict(type="VFOLD", uid=6, label="tree", y=77.3, phi_l=140, phi_r=140, alpha_l=45,
            alpha_r=45, glue=60, height=65, tab=10, tab_side="IN", shape="TRI",
            lines=[crease((0.0, 39.0), (-21.2, 26.0)),
                   crease((-19.85, 54.05), (0.12, -0.96))])
m = Model(STAGE, [tree])
assert not m.warnings, m.warnings
folds = [n for n in m.order if ".Fold" in n]
assert len(folds) == 4, folds
assert max(abs(m.panels[n].hinge.fn(110.0)) for n in folds) > math.radians(20)
# a crease ending exactly on the V point and on the edge (snapped) does cut
m = Model(STAGE, [dict(tree, lines=[crease((-19.85, 54.05), (0.12, -0.96))])])
assert len([n for n in m.order if ".Fold" in n]) == 2, m.warnings
print("crossing creases fold; snapped ends cut cleanly")

# ---- in Blender: presets on the card, a V-fold on a floor's crease
addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
st.hold = "SYM"
assert bpy.ops.popup.add_card_line(preset="CEILING") == {"FINISHED"}
assert len(st.card_lines) == 1 and st.card_dict()["lines"]
assert bpy.ops.popup.build() == {"FINISHED"}
model = build.make_model(sc)[0]
assert [n for n in model.order if n.startswith("Card.Fold")], model.warnings
assert bpy.ops.popup.remove_card_line() == {"FINISHED"}
assert not st.card_lines
o = st.openings.add()
assert o.bl_rna.properties["x"].name == "X (Across Page)"
assert o.bl_rna.properties["y"].name == "Y (Up Page)"
addon.unregister()
print("V18 OK")
