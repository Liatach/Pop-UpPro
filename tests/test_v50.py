"""v0.50: panels share their fold's vertices (Solid Paper meets at folds:
no slab poking through the next panel, as a dipped cube lid did); images
can be metallic; the Studio render look."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, images  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
bpy.ops.popup.build()
st.mechs.clear()
bpy.ops.popup.add(kind="CUBE")
cube = st.mechs[-1]
cube.lid = "DIP"
bpy.ops.popup.add(kind="VFOLD")
v = st.mechs[-1]
build.rebuild(sc, force=True)
model, lay = build.make_model(sc)
me = st.card.data
at = me.attributes["pop_panel"]
users = {}
for p in me.polygons:
    for vi in p.vertices:
        users.setdefault(vi, set()).add(model.order[at.data[p.index].value])
pairs = {frozenset(u) for u in users.values() if len(u) > 1}


def joined(a, b):
    return any({a, b} <= set(u) for u in pairs)


assert joined(f"VFold{v.uid}.HalfL", f"VFold{v.uid}.HalfR")
assert joined(f"Cube{cube.uid}.B", f"Cube{cube.uid}.LidL")
assert joined(f"Cube{cube.uid}.A", f"Cube{cube.uid}.B")
assert joined("Page.L", "Page.R")
assert not any(any(model.panels[n].kind == "tab" for n in u) for u in pairs), \
    "glue tabs stay separate"
assert not any(len({model.panels[n].piece for n in u}) > 1 for u in pairs), \
    "only within one piece"
print("folds share their vertices:", len(pairs), "kinds of join")

# the rig still follows exactly, shared vertices included
rig, card = st.rig, st.card
if rig.animation_data:
    rig.animation_data.action = None
s = 1 / st.mm_per_unit
t0 = rig["pop_close"]
worst = 0.0
for t in (3.0, 47.0, 112.3, 180.0):
    rig["pop_open"] = t
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    real = t0 + t * (180 - t0) / 180
    for poly in me.polygons:
        name = model.order[at.data[poly.index].value]
        D = model.shown(name, real) @ lay["prints"][model.panels[name].piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s)) * s
                                ).length / s)
assert worst < 0.05, worst
print("rig exact with shared folds:", round(worst, 4))

# Solid Paper: the dipped lid's slab stays inside the walls at the fold
st.solid_paper = True
build.rebuild(sc, force=True)
rig["pop_open"] = 112.0
rig.update_tag()
dg = bpy.context.evaluated_depsgraph_get()
dg.update()
ev = card.evaluated_get(dg)
em = ev.data
names = model.order
A = st.card.data.polygons
n0 = len(A)
wall = f"Cube{cube.uid}.B"
lid = f"Cube{cube.uid}.LidL"
wp = [p for p in em.polygons[:n0] if names[em.attributes["pop_panel"].data[p.index].value] == wall][0]
nrm, o = wp.normal.copy(), em.vertices[wp.vertices[0]].co.copy()  # printed side: outward
out = max((em.vertices[i].co - o).dot(nrm) for p in em.polygons
          if names[em.attributes["pop_panel"].data[p.index].value] == lid for i in p.vertices)
print("lid past the wall's outer face (mm):", round(out / s, 4))
assert out / s < 0.01, out / s

# metallic images: Metallic driven where the image is
img = bpy.data.images.new("t", 8, 8, alpha=True)
bpy.ops.popup.add_art()
pl = st.images.add()
pl.uid, pl.image, pl.piece = 1, img, f"Cube{cube.uid}"
images.sync(sc)
mat = bpy.data.materials["Pop-up Paper"]
bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
assert not bsdf.inputs["Metallic"].is_linked
pl.metallic = 1.0
assert bsdf.inputs["Metallic"].is_linked and bsdf.inputs["Roughness"].is_linked
pl.metallic = 0.0
assert not bsdf.inputs["Metallic"].is_linked
print("metallic images ok")

st.render_look = "STUDIO"
assert sc.world.name.startswith("Pop-up Studio"), sc.world.name
print("v50 ok")
