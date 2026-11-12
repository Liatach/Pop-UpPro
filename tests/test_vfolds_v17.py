"""v0.17: asymmetric V-folds that always fold flat (piece angles from the glue
angles and a Lean, forwards or pointing backwards), and mechanisms standing
on a V-fold's own crease, carried off the card's centre."""
# families: vfolds, hosts
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

CARD = dict(W=148.5, H=210, hold="SYM")
V = dict(type="VFOLD", uid=1, label="V", y=60, phi_l=40, phi_r=75, alpha_l=95, alpha_r=60,
         glue=60, height=70, tab=10, tab_side="IN")

# ---- the asymmetric V-fold folds flat and leans to the bigger glue angle
m = Model(CARD, [V])
m.check_fit()
assert not m.warnings, m.warnings
assert all(m.crease("VFold1", t)[3] for t in m.samples)
assert m.crease("VFold1", 90)[0].x > 0.1  # towards the right (75 > 40)
print("asymmetric V-fold folds flat and leans right")

# ---- mechanisms on its crease
KIDS = [
    dict(type="BOX", style="GLUED", uid=2, label="Box", y=20, width=20, height=15, depth=15,
         tab=8, host=1, vside="V"),
    dict(type="BOX", style="CUT", uid=2, label="Layer", y=20, width=20, height=15, depth=15,
         host=1, vside="V"),
    dict(type="VFOLD", uid=2, label="V2", y=20, phi_l=60, phi_r=60, alpha_l=80, alpha_r=80,
         glue=15, height=15, tab=6, tab_side="IN", host=1, vside="V"),
    dict(type="STANDUP", stand="UPRIGHT", uid=2, label="Stand", y=25, width=10, height=12,
         depth=12, img_w=20, img_h=25, tab=6, host=1, vside="V"),
    dict(type="MOUTH", uid=2, label="Mouth", y=35, jaw=12, upper=8, lower=6, host=1,
         vside="V"),
]
for kid in KIDS:
    m = Model(CARD, [V, kid])
    m.check_fit()
    assert not m.warnings, (kid["label"], m.warnings)
    if kid["type"] in ("BOX", "STANDUP"):
        # a parallelogram on the V-fold's crease: the top stays parallel to the
        # right half, the front to the left
        for t in (20, 60, 90, 140):
            zr = m.panels["VFold1.HalfR"].asm(t).to_3x3() @ Vector((0, 0, 1))
            zl = m.panels["VFold1.HalfL"].asm(t).to_3x3() @ Vector((0, 0, 1))
            top = "Box2.AC" if kid["type"] == "BOX" else "Stand2.AC"
            front = "Box2.CB" if kid["type"] == "BOX" else "Stand2.CB"
            za = m.panels[top].asm(t).to_3x3() @ Vector((0, 0, 1))
            zc = m.panels[front].asm(t).to_3x3() @ Vector((0, 0, 1))
            assert abs(abs(za.dot(zr)) - 1) < 1e-4 and abs(abs(zc.dot(zl)) - 1) < 1e-4, \
                (kid["label"], t)
    print(f"{kid['label']} stands on the V-fold's crease")

# cubes stand there too (0.27); what doesn't fit is refused, not crashed
m = Model(CARD, [V, dict(type="CUBE", uid=2, label="Cube", y=10, size=10, height=10, tab=6,
                         lid="NONE", tab_side="IN", host=1, vside="V")])
assert not any("skipped" in w for w in m.warnings), m.warnings
assert "Cube2.B" in m.panels or any(n.startswith("Cube2") for n in m.order)
m = Model(CARD, [V, dict(type="STAGE", uid=2, label="Stage", y=10, phi_l=60, glue=20,
                         height=20, tab=6, tab_side="OUT", host=1, vside="V")])
assert any("Stage" in w and "skipped" in w for w in m.warnings), m.warnings

# a mechanism on a host that tears is flagged, the card still builds
bad = dict(V, y=150, phi_l=110, phi_r=140, alpha_l=160, alpha_r=130)
m = Model(CARD, [bad, KIDS[0]])
assert any("can't follow" in w or "tears" in w for w in m.warnings), m.warnings
print("misfits refused, tearing hosts flagged")

# ---- in Blender: Fold Flat works the piece angles out, either way round
addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
st.hold = "SYM"
assert bpy.ops.popup.add(kind="VFOLD", variant="ASYM") == {"FINISHED"}
v = st.mechs[-1]
assert not v.symmetric and v.fold_flat and v.label.startswith("Asymmetric")
d = v.to_dict()
assert (d["alpha_l"], d["alpha_r"]) == (v.phi_r + v.lean, v.phi_l + v.lean)
v.phi_l, v.phi_r = 140.0, 105.0  # pointing backwards
d = v.to_dict()
assert (d["alpha_l"], d["alpha_r"]) == (180 - 105 + v.lean, 180 - 140 + v.lean), d
m = Model(CARD, [dict(d, host=0)])
assert not [w for w in m.warnings if "tears" in w], m.warnings
v.phi_l, v.phi_r, v.y = 40.0, 75.0, 60.0
v.glue, v.height = 60.0, 70.0
st.active = len(st.mechs) - 1
for kind in ("BOX", "STANDUP", "VFOLD"):
    assert bpy.ops.popup.add(kind=kind, host=v.uid, fold="V") == {"FINISHED"}
    assert st.mechs[-1].vside == "V" and st.mechs[-1].host_uid == v.uid
box, su, v2 = st.mechs[-3], st.mechs[-2], st.mechs[-1]
box.y, box.width, box.height, box.depth, box.tab = 14.0, 10.0, 10.0, 10.0, 6.0
su.y, su.width, su.img_w = 30.0, 8.0, 14.0
v2.y, v2.glue, v2.height = 50.0, 10.0, 10.0
st.keep_open = False
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
rig, card = st.rig, st.card
s_ = 1 / st.mm_per_unit
me = card.data
attr = me.attributes["pop_panel"]
lay = build.make_model(sc)[1]
worst = 0.0
for t in (5, 45, 90, 150, 180):
    rig["pop_open"] = float(t)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    for poly in me.polygons:
        p = model.panels[model.order[attr.data[poly.index].value]]
        D_ = model.shown(p.name, t) @ lay["prints"][p.piece].inverted()
        for vi in poly.vertices:
            want = (D_ @ (me.vertices[vi].co / s_)) * s_
            worst = max(worst, (ev.vertices[vi].co - want).length / s_)
assert worst < 0.5, worst
print(f"rig matches the geometry to {worst:.3f} mm")
addon.unregister()
print("V17 OK")
