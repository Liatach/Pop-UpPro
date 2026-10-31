"""v0.47: part materials. One part renders with its own material (copied
from the paper with its art), set by a Geometry Nodes modifier between the
rig and Solid Paper, kept through rebuilds; the rig is unchanged."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, materials  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
bpy.ops.popup.build()
st.mechs.clear()
bpy.ops.popup.add(kind="VFOLD")
v = st.mechs[-1]
build.rebuild(sc, force=True)
bpy.ops.popup.add_art()
half = f"VFold{v.uid}.HalfL"
st.material_part = half
st.material_whole = False
assert bpy.ops.popup.part_material(look="METALLIC") == {"FINISHED"}
it = st.part_materials[0]
mat = it.material
assert it.panel == half and mat is not None
bsdf = materials._bsdf(mat)
assert bsdf.inputs["Metallic"].default_value == 1.0
# the art came with it
assert any(n.type == "TEX_IMAGE" and n.image is not None for n in mat.node_tree.nodes)
card = st.card
names = [m.name for m in card.modifiers]
assert names.index(materials.MOD) == names.index("Pop-up Rig") + 1, names
assert names.index("Pop-up Paper") > names.index(materials.MOD), names


def mats_on(panel_names):
    rig = st.rig
    if rig.animation_data:
        rig.animation_data.action = None
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg)
    me = ev.data
    model = build.make_model(sc)[0]
    at = card.data.attributes["pop_panel"]
    out = {}
    n0 = len(card.data.polygons)
    for p in card.data.polygons:
        nm = model.order[at.data[p.index].value]
        out.setdefault(nm, set()).add(me.materials[me.polygons[p.index].material_index].name
                                      if me.materials else None)
    assert len(me.polygons) >= n0
    return out


m = mats_on(None)
assert m[half] == {mat.name}, m[half]
other = [k for k in m if k != half]
assert all(mat.name not in m[k] for k in other), m
# rebuild keeps it (and a resize too)
v.height += 10
build.rebuild(sc, force=True)
m = mats_on(None)
assert m[half] == {mat.name}, m[half]
# solid paper off and on: still placed right
st.solid_paper = False
build.rebuild(sc, force=True)
st.solid_paper = True
build.rebuild(sc, force=True)
names = [x.name for x in card.modifiers]
assert names.index(materials.MOD) == names.index("Pop-up Rig") + 1, names
for look in ("GLOSSY", "GLOW", "PLAIN"):
    assert bpy.ops.popup.part_material(look=look) == {"FINISHED"}
assert len(st.part_materials) == 1
bpy.ops.popup.part_material_remove()
assert len(st.part_materials) == 0 and card.modifiers.get(materials.MOD) is None
# the whole mechanism at once: both halves, not the tabs
st.material_whole = True
st.material_part = half
assert bpy.ops.popup.part_material(look="GLOSSY") == {"FINISHED"}
assert st.part_materials[0].panel == f"VFold{v.uid}.*"
gm = st.part_materials[0].material
m = mats_on(None)
for k in m:
    if k.startswith(f"VFold{v.uid}.Half"):
        assert m[k] == {gm.name}, (k, m[k])
    elif k.startswith(f"VFold{v.uid}.Tab") or k.startswith("Page"):
        assert gm.name not in m[k], (k, m[k])
# one half on its own on top of the whole: the half's own wins
st.material_whole = False
st.material_part = half
bpy.ops.popup.part_material(look="GLOW")
m = mats_on(None)
other_half = f"VFold{v.uid}.HalfR"
assert m[half] != {gm.name} and m[other_half] == {gm.name}, (m[half], m[other_half])
print("v47 ok")
