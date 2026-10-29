"""v0.15: extra creases and cuts on box folds and box layers (Birmingham 37:
battlements, a spire, a doorway, an inset step), and parallelogram stand-ups
(Birmingham 38: an upright picture on a bridge, a flat one on a leg, and
stand-ups standing on stand-ups)."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "tests", "out")
os.makedirs(OUT, exist_ok=True)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
from mathutils import Vector  # noqa: E402

import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402
from popup_pro.core.folds import _inside  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

CARD = dict(W=148.5, H=210, hold="RIGHT")
a, b, w = 40.0, 30.0, 60.0


def at(model, q):
    return [n for n in model.order
            if any(_inside(q, poly) for poly in model.panels[n].polys)]


merlon = [dict(kind="CUT", mirror=True, pts=[(0, 4), (-8, 4), (-8, 10), (0, 10)])]
arch = [dict(kind="CUT", mirror=False, pts=[(a, 24), (a - 14, 24), (a - 18, 30),
                                             (a - 14, 36), (a, 36)])]
inset = [dict(kind="CREASE", mirror=False, pts=[(-9, 20), (-9, 40)]),
         dict(kind="CREASE", mirror=False, pts=[(9, 20), (9, 40)]),
         dict(kind="CUT", mirror=True, pts=[(-9, 20), (9, 20)])]

# ---- box layer (cut from the card): battlements stand up with the front,
# the doorway stays on the floor
m = Model(CARD, [dict(type="BOX", style="CUT", uid=1, label="Castle", y=40, width=w,
                      height=a, depth=b, lines=merlon + arch)])
m.check_fit()
assert not m.warnings, m.warnings
host = m.hosts[(0, "S")]


def P(x, y):
    return host.v1(b - a + x, 40 + y)


assert at(m, P(-4, 7)) == ["Box1.CB"] and at(m, P(-4, w - 7)) == ["Box1.CB"]
assert at(m, P(-15, 30)) == ["Box1.AC"]
assert at(m, P(a - 5, 30)) == ["Page.R"]
for t in (30, 90, 150):  # a merlon really stands above the top
    M = m.panels["Box1.CB"].asm(t)
    top = m.panels["Box1.AC"].asm(t)
    q = M @ Vector((*P(-6, 7), 0))
    up = m.dirs(t)[3]  # the floor's normal
    assert (q - top @ Vector((*P(-15, 7), 0))).dot(up) > 5.5 * math.sin(math.radians(t)), t
print("box layer: battlements stand up, doorway stays on the floor")

# ---- glued box: battlements, doorway cut away (its floor side is the tab)
m = Model(CARD, [dict(type="BOX", style="GLUED", uid=1, label="Box", y=40, width=w,
                      height=a, depth=b, tab=10, lines=merlon + arch)])
assert [n for n in at(m, (b - 4, 7)) if n.startswith("Box1")] == ["Box1.CB"]
assert not [n for n in at(m, (b + a - 5, 30)) if n.startswith("Box1")]
print("glued box: battlements, doorway")

# ---- inset step: creases + cuts across the front-top fold fold inwards
m = Model(CARD, [dict(type="BOX", style="CUT", uid=1, label="Step", y=40, width=w,
                      height=a, depth=b, lines=inset)])
assert not m.warnings, m.warnings
folds = [n for n in m.order if ".Fold" in n]
assert len(folds) == 2, folds
for t in (20, 90, 160):
    for n in folds:
        assert abs(m.panels[n].hinge.fn(t)) > math.radians(20)
print("inset step folds")

# ---- stand-ups
U = dict(type="STANDUP", stand="UPRIGHT", uid=1, label="Family", y=60, width=40, height=50,
         depth=30, img_w=90, img_h=80, tab=10)
D = dict(type="STANDUP", stand="UPRIGHT", uid=2, label="Dog", y=70, width=20, height=15,
         depth=15, img_w=35, img_h=30, tab=8, host=1, fold="B")
F = dict(type="STANDUP", stand="FLAT", uid=3, label="Carpet", y=120, width=30, height=35,
         depth=40, img_w=70, img_h=70, tab=10)
G = dict(type="STANDUP", stand="UPRIGHT", uid=4, label="Figure", y=125, width=20, height=25,
         depth=20, img_w=30, img_h=45, tab=8, host=3, fold="A")
m = Model(CARD, [U, D, F, G])
m.check_fit()
assert not m.warnings, m.warnings
for t in (10, 60, 90, 140):
    l, r, nl, nr = m.dirs(t)
    for name, par in (("Stand1.CB", nl), ("Stand2.CB", nl), ("Stand3.AC", nr),
                      ("Stand4.CB", nl)):
        z = m.panels[name].asm(t).to_3x3() @ Vector((0, 0, 1))
        assert abs(abs(z.dot(par)) - 1) < 1e-4, (name, t)
# the dog's bridge reaches the family picture, the figure stands on the carpet
q = m.panels["Stand2.TabA"].asm(90) @ Vector((-2, 10, 0))
fam = m.panels["Stand1.CB"].asm(90)
assert abs((fam.inverted() @ q).z) < 0.5
print("stand-ups: pictures stay parallel to the background or floor, and stack")

# ---- stand-ups in front of and behind a V-fold's halves
V = dict(type="VFOLD", uid=1, label="V", y=60, phi_l=60, phi_r=60, alpha_l=80, alpha_r=80,
         glue=60, height=70, tab=10, tab_side="IN")
for side in ("FL", "BL", "FR", "BR"):
    S = dict(type="STANDUP", stand="UPRIGHT", uid=2, label="S", y=15, width=20, height=25,
             depth=15, img_w=30, img_h=40, tab=8, host=1, vside=side)
    m = Model(CARD, [V, S])
    m.check_fit()
    assert not m.warnings, (side, m.warnings)
    half = f"VFold1.Half{side[1]}"
    for t in (20, 60, 90, 130, 170):
        zh = m.panels[half].asm(t).to_3x3() @ Vector((0, 0, 1))
        zp = m.panels["Stand2.CB"].asm(t).to_3x3() @ Vector((0, 0, 1))
        assert abs(abs(zh.dot(zp)) - 1) < 1e-4, (side, t)
    # bridge tab on the half, foot on the page (in front: outside the V)
    q = m.panels["Stand2.TabA"].asm(90) @ Vector((-2, 10, 0))
    assert abs((m.panels[half].asm(90).inverted() @ q).z) < 0.5, side
print("stand-ups in front of and behind V-fold halves stay parallel to them")

# ---- in Blender
addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert bpy.ops.popup.add(kind="BOXCUT") == {"FINISHED"}
st.active = 0
box = st.mechs[0]
box.y, box.width, box.height, box.depth = 25, 60, 40, 30
assert bpy.ops.popup.add_line(preset="BATTLEMENTS") == {"FINISHED"}
assert bpy.ops.popup.add_opening() == {"FINISHED"}  # a door in the front (v0.35)
st.openings[-1].cut = "DOOR"
st.openings[-1].y = 4.0  # a side-hinged door clears the floor
assert bpy.ops.popup.add(kind="STANDUP") == {"FINISHED"}
su = st.mechs[-1]
su.y, su.img_w = 108, 50
assert bpy.ops.popup.add(kind="STANDUP", host=su.uid, fold="B") == {"FINISHED"}
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
vf = st.mechs[-1]
vf.y, vf.glue, vf.height = 172, 30, 26
assert bpy.ops.popup.add(kind="STANDUP", host=vf.uid, fold="FR") == {"FINISHED"}
assert st.mechs[-1].vside == "FR" and st.mechs[-1].host_uid == vf.uid
st.keep_open = False
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
rig, card = st.rig, st.card
s_ = 1 / st.mm_per_unit
me = card.data
attr = me.attributes["pop_panel"]
lay = build.make_model(sc)[1]
worst, n_chk = 0.0, 0
for t in (5, 45, 90, 150, 180):
    rig["pop_open"] = float(t)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    for poly in me.polygons:
        p = model.panels[model.order[attr.data[poly.index].value]]
        D_ = p.asm(t) @ lay["prints"][p.piece].inverted()
        for vi in poly.vertices:
            want = (D_ @ (me.vertices[vi].co / s_)) * s_
            worst = max(worst, (ev.vertices[vi].co - want).length / s_)
            n_chk += 1
assert worst < 0.5, worst
print(f"rig matches the geometry to {worst:.3f} mm ({n_chk} points)")
path = os.path.join(OUT, "v15.svg")
assert bpy.ops.popup.export_svg(filepath=path) == {"FINISHED"}
print("printed")
addon.unregister()
print("V15 OK")
