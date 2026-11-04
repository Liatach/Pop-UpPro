"""v0.64: visibility per mechanism (Normal, Wire, Hidden; viewport only, and
Draw Anywhere paints through), and the plan view showing where pieces of
paper actually pass through each other."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import art, build, clashes, debug, live, visibility  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
assert bpy.ops.popup.add(kind="BOX") == {"FINISHED"}
vf, bx = st.mechs[0], st.mechs[1]
st.solid_paper = True
assert bpy.ops.popup.build() == {"FINISHED"}


def shown(obj=None):
    """{mechanism uid: faces shown}, edges, on the card (or layout) as drawn."""
    obj = obj or st.card
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    v = [0] * len(me.polygons)
    me.attributes["pop_mech"].data.foreach_get("value", v)
    out = ({u: v.count(u) for u in set(v)}, len(me.edges))
    ev.to_mesh_clear()
    return out


full, edges = shown()
assert full.get(vf.uid) and full.get(bx.uid)
# ---- wire: its faces go, its edges stay; hidden: both go
assert bpy.ops.popup.visibility(action="CYCLE", uid=vf.uid) == {"FINISHED"}
assert vf.visibility == "WIRE"
f, e = shown()
assert vf.uid not in f and f[bx.uid] == full[bx.uid] and e == edges
assert visibility.MOD in st.card.modifiers and visibility.MOD in st.layout.modifiers
assert not st.card.modifiers[visibility.MOD].show_render  # renders show it all
assert vf.uid not in shown(st.layout)[0]  # the flat layout too
bpy.ops.popup.visibility(action="CYCLE", uid=vf.uid)
assert vf.visibility == "HIDDEN"
f, e = shown()
assert vf.uid not in f and e < edges
bpy.ops.popup.visibility(action="CYCLE", uid=vf.uid)
assert vf.visibility == "NORMAL" and visibility.MOD not in st.card.modifiers
print("wire keeps the outline, hidden drops it, the layout follows, renders untouched")

# isolate and others as wire; show all
st.active = 1
for m in st.mechs:
    m.selected = False
bpy.ops.popup.visibility(action="ISOLATE")
assert vf.visibility == "HIDDEN" and bx.visibility == "NORMAL"
bpy.ops.popup.visibility(action="WIRE_OTHERS")
assert vf.visibility == "WIRE" and bx.visibility == "NORMAL"
# a rebuild keeps it, before the plan view (which stays last)
st.plan_view = True
bpy.ops.popup.build()
names = [m.name for m in st.card.modifiers]
assert names[-1] == debug.MOD and names[-2] == visibility.MOD, names
st.plan_view = False
bpy.ops.popup.visibility(action="ALL")
assert all(m.visibility == "NORMAL" for m in st.mechs)
assert visibility.MOD not in st.card.modifiers
print("isolate, others as wire, show all; kept through a rebuild")

# ---- Draw Anywhere paints through a wire mechanism onto the paper behind
rig = st.rig
if rig.animation_data:
    rig.animation_data.action = None
rig["pop_open"] = 180.0
bpy.context.view_layer.update()
bx.visibility = "WIRE"
names = [p["name"] for p in live.meta(rig)["panels"]]
meta = live.meta(rig)
paper = art._Paper(sc)
# a point on the box's top, lying flat over the left page when open flat
P = build.make_model(sc)[0]
half = P.panels[f"Box{bx.uid}.AC"]
q = [sum(c[i] for c in half.polys[0]) / len(half.polys[0]) for i in (0, 1)]
s = 1.0 / st.mm_per_unit
w = st.card.matrix_world @ (P.point(half.name, q, 180.0 * (180 - rig["pop_close"]) / 180
                                    + rig["pop_close"]) * s)
r, k = paper.to_rest(w + Vector((0, 0, 0.3 * s)))
assert k is not None and names[k] in ("Page.R", "Page.L"), names[k] if k is not None else k
bx.visibility = "NORMAL"
paper = art._Paper(sc)
r, k = paper.to_rest(w + Vector((0, 0, 0.3 * s)))
assert names[k].startswith(f"Box{bx.uid}"), names[k]
print("Draw Anywhere: through a wire mechanism onto the page; onto it when shown")

# ---- clashes: two V-folds through each other
while st.mechs:
    st.active = 0
    bpy.ops.popup.remove()
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
a, b = st.mechs[0], st.mechs[1]
b.y, b.phi_l, b.alpha_l = a.y + 10.0, 45.0, 120.0
st.solid_paper = False
bpy.ops.popup.build()
st.plan_angle = 90.0
st.plan_view = True
got = list(sc.get("pop_clashes", []))
assert any(a.label in g and b.label in g for g in got), got
obj = bpy.data.objects.get(clashes.OBJ)
assert obj is not None and len(obj.data.polygons) > 0 and obj.hide_render
# squashed with the plan view: flat along its axis
ax = debug.view_axis(st.hold, 90.0)
d = [v.co.dot(ax) for v in obj.data.vertices]
full_d = 50.0 / st.mm_per_unit
assert max(d) - min(d) < 0.1 * full_d, (max(d) - min(d))
# moved apart: none
b.y = a.y + 120.0
bpy.ops.popup.build()
st.plan_angle = 91.0
assert not list(sc.get("pop_clashes", [])), list(sc.get("pop_clashes", []))
assert bpy.data.objects.get(clashes.OBJ) is None
# a box on the spine with a V-fold on its fold: hinges and glue aren't clashes
while st.mechs:
    st.active = 0
    bpy.ops.popup.remove()
for kind in ("BOX", "DOUBLE45", "VFOLD"):
    bpy.ops.popup.add(kind=kind)
st.mechs[0].y, st.mechs[1].y, st.mechs[2].y = 5.0, 105.0, 160.0
bpy.ops.popup.build()
for t in (40.0, 90.0, 150.0):
    st.plan_angle = t
    found = list(sc.get("pop_clashes", []))
    assert not found, (t, found)
st.plan_view = False
assert bpy.data.objects.get(clashes.OBJ) is None
print("clashes: shown where pieces pass through each other, not where they hinge")
# ---- frames across an ordinary card's fold
while st.mechs:
    st.active = 0
    bpy.ops.popup.remove()
st.solid_paper = False
for _ in range(2):
    assert bpy.ops.popup.add(kind="FRAME") == {"FINISHED"}
assert all(m.host_uid == 0 and m.kind == "FRAME" for m in st.mechs)
assert st.mechs[1].x < st.mechs[0].x
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
from popup_pro.core.geom import v3  # noqa: E402
nr = model.panels["Page.R"].asm(180.0).to_3x3() @ Vector((0, 0, 1))
for m in st.mechs:  # flat on the card when it's open flat
    for side in "LR":
        p = model.panels[f"Frame{m.uid}.{side}"]
        assert max(abs((p.asm(180.0) @ v3(q)).dot(nr)) for q in p.polys[0]) < 1.0
# floors still need a stage
try:
    bpy.ops.popup.add(kind="FLOOR")
    raise AssertionError("a floor went on a plain card")
except RuntimeError as e:
    assert "Stage Set" in str(e)
rig = st.rig
if rig.animation_data:
    rig.animation_data.action = None
me, at = st.card.data, st.card.data.attributes["pop_panel"]
model, lay = build.make_model(sc)
s = 1.0 / st.mm_per_unit
worst = 0.0
for t in (20.0, 90.0, 160.0):
    rig["pop_open"] = t
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = st.card.evaluated_get(dg).data
    real = rig["pop_close"] + t * (180 - rig["pop_close"]) / 180
    for poly in me.polygons:
        name = model.order[at.data[poly.index].value]
        P = lay["prints"][model.panels[name].piece].inverted()
        for vi in poly.vertices:
            q = P @ (me.vertices[vi].co / s)
            worst = max(worst, (ev.vertices[vi].co / s - model.point(name, q, real)).length)
assert worst < 0.05, worst
print("frames across an ordinary card's fold, flat when it's open flat")
print("v0.64 OK")
