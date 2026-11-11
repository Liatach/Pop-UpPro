"""v0.28: off-centre pop-ups (Pop-Up Tutorial 9): the Strap's two gullies,
and a V-fold's glue folds, carry cubes, tubes and V-folds; on a V-fold's
crease a cube stands in the V (the valley), not on the mountain."""
# families: straps, hosts
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

CARD = dict(W=148.5, H=210.0, hold="SYM")


def centre(m, prefix, t):
    pts = []
    for n in m.order:
        if n.startswith(prefix):
            p = m.panels[n]
            M = p.asm(t)
            pts += [M @ Vector((q[0], q[1], 0)) for poly in p.polys for q in poly]
    return sum(pts, Vector()) / len(pts)


# ---- a cube on a V-fold's crease stands in the V, behind the crease
V = dict(type="VFOLD", uid=1, label="V", y=40, phi_l=45, phi_r=45, alpha_l=80, alpha_r=80,
         glue=60, height=70, tab=10, tab_side="IN")
m = Model(CARD, [V, dict(type="CUBE", uid=2, label="cube", y=28, size=14.7, height=14.7,
                         tab=8, host=1, vside="V", lid="PEAK", tab_side="IN")])
m.check_fit()
assert not m.warnings, m.warnings
c, *_ = m.crease("VFold1", 120.0)  # the V-fold's crease leans forward (-y)
assert c.y < 0
assert centre(m, "Cube2", 120.0).y > 40.0 + 5.0  # behind its V point: inside the V
print("cube on the crease stands in the V")

# ---- on the glue folds in front of each half: off-centre, no warnings
for vs, sx in (("FL", -1), ("FR", 1)):
    for kid, pre in ((dict(type="CUBE", uid=2, label="cube", y=12, size=15, height=15, tab=8,
                           lid="PEAK", tab_side="IN"), "Cube2"),
                     (dict(type="TUBE", uid=2, label="tube", y=9, x=6, depth=21, height=17.5,
                           front=9, back=9, tab=8, front_style="OUT", back_style="OUT",
                           tab_side="IN", roof="NONE"), "Tube2"),
                     (dict(type="VFOLD", uid=2, label="v2", y=18, phi_l=60, phi_r=60,
                           alpha_l=80, alpha_r=80, glue=15, height=15, tab=6,
                           tab_side="IN"), "VFold2")):
        m = Model(CARD, [V, dict(kid, host=1, vside=vs)])
        m.check_fit()
        assert not [w for w in m.warnings if "skipped" in w], (vs, kid["type"], m.warnings)
        x = centre(m, pre, 150.0).x
        assert sx * x > 5.0, (vs, kid["type"], x)  # off the centre, its own side
print("cubes, tubes and V-folds stand on a V-fold's front glue folds")

# ---- the Strap: a box fold with equal sides; its gullies carry pop-ups
addon.register()
sc = bpy.context.scene
st = sc.popup
assert bpy.ops.popup.build() == {"FINISHED"}
st.live = False
st.mechs.remove(0)
assert bpy.ops.popup.add(kind="BOX", variant="STRAP") == {"FINISHED"}
strap = st.mechs[-1]
assert strap.label.startswith("Strap") and strap.height == strap.depth
for kind, fold in (("CUBE", "A"), ("TUBE", "B"), ("VFOLD", "A")):
    assert bpy.ops.popup.add(kind=kind, host=strap.uid, fold=fold) == {"FINISHED"}
st.mechs.remove(len(st.mechs) - 1)  # (one each side is enough to check)
assert bpy.ops.popup.build() == {"FINISHED"}
m, _ = build.make_model(sc)
m.check_fit()
assert not m.warnings, m.warnings
cube = next(x for x in st.mechs if x.kind == "CUBE")
tube = next(x for x in st.mechs if x.kind == "TUBE")
# open flat, the strap lies on the pages and the pop-ups stand off the centre
cx = centre(m, f"Cube{cube.uid}", 179.0)
tx = centre(m, f"Tube{tube.uid}", 179.0)
assert cx.x < -20 and tx.x > 20, (cx, tx)
assert cx.z > 5 and tx.z > 5, (cx, tx)
strap_z = max((m.panels[n].asm(179.9) @ Vector((q[0], q[1], 0))).z
              for n in m.order if n.startswith(f"Box{strap.uid}.")
              for poly in m.panels[n].polys for q in poly)
assert strap_z < 2.0, strap_z  # the strap itself lies flat
addon.unregister()
print("V28 OK")
