"""v0.39 (reworked in v0.58): paint layers on the paper. Pop-Up Pro calls no
other extension (Blender Extensions rule 5); any layer setup of your own on
the paper's material works with it: the brush switches between the paper
and a layer, and a layer stack set up as flat "paint over" colour is lit
like the paper."""
# families: paint
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, ops  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
assert bpy.ops.popup.build() == {"FINISHED"}
assert not hasattr(bpy.ops.popup, "paint_layers") or \
    "paint_layers" not in dir(bpy.ops.popup)
src = open(os.path.join(ROOT, "popup_pro", "ui.py")).read() + \
    open(os.path.join(ROOT, "popup_pro", "ops.py")).read()
assert "paint_system" not in src.lower() and "extensions.blender.org" not in src
print("no other extension is called or linked")

bpy.ops.popup.add_art()
mat = st.card.data.materials[0]
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)

# a layer of your own: an image (on the art's UV map) in a node group, mixed
# over the paper's colour
layer = bpy.data.images.new("My Layer", 64, 64, alpha=True)
g = bpy.data.node_groups.new("My Layers", "ShaderNodeTree")
g.interface.new_socket("Color", in_out="INPUT", socket_type="NodeSocketColor")
g.interface.new_socket("Color", in_out="OUTPUT", socket_type="NodeSocketColor")
gi, go = g.nodes.new("NodeGroupInput"), g.nodes.new("NodeGroupOutput")
uv = g.nodes.new("ShaderNodeUVMap")
uv.uv_map = build.ART_UV
tex = g.nodes.new("ShaderNodeTexImage")
tex.image = layer
g.links.new(uv.outputs[0], tex.inputs[0])
mix = g.nodes.new("ShaderNodeMix")
mix.data_type = "RGBA"
g.links.new(tex.outputs["Alpha"], mix.inputs["Factor"])
g.links.new(gi.outputs[0], mix.inputs[6])
g.links.new(tex.outputs["Color"], mix.inputs[7])
g.links.new(mix.outputs[2], go.inputs[0])
gn = nt.nodes.new("ShaderNodeGroup")
gn.node_tree = g
base = bsdf.inputs["Base Color"]
if base.links:
    nt.links.new(base.links[0].from_socket, gn.inputs[0])
nt.links.new(gn.outputs[0], base)

art_img, others = ops.paint_images(sc)
assert layer in others, others
assert bpy.ops.popup.paint() == {"FINISHED"} and ops.painting(bpy.context)
assert bpy.ops.popup.paint_into(into=layer.name) == {"FINISHED"}
assert ops.painting_into(sc) == layer
bpy.ops.popup.paint_erase()
assert ops.painting_into(sc) == art_img, "erasing works on the paper"
bpy.ops.popup.paint_into(into="OTHER")
assert ops.painting_into(sc) == layer
bpy.ops.popup.paint()  # off
assert out.inputs["Surface"].links[0].from_node == bsdf
assert not any(n.name.startswith("Pop-up True") for n in nt.nodes), "flat colours gone"
print("the brush switches between the paper and a layer of your own")

# a layer stack set up as flat "paint over" colour on the shaded paper is lit
mat2 = mat.copy()
n2 = mat2.node_tree
b2 = next(n for n in n2.nodes if n.type == "BSDF_PRINCIPLED")
g2 = next(n for n in n2.nodes if n.type == "GROUP" and n.node_tree == g)
o2 = next(n for n in n2.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
paper = g2.inputs[0].links[0].from_socket if g2.inputs[0].links else None
s2r = n2.nodes.new("ShaderNodeShaderToRGB")
mx = n2.nodes.new("ShaderNodeMixShader")
clear = n2.nodes.new("ShaderNodeBsdfTransparent")
if paper is not None:
    n2.links.new(paper, b2.inputs["Base Color"])
n2.links.new(b2.outputs[0], s2r.inputs[0])
n2.links.new(s2r.outputs[0], g2.inputs[0])
n2.links.new(clear.outputs[0], mx.inputs[1])
n2.links.new(g2.outputs[0], mx.inputs[2])
n2.links.new(mx.outputs[0], o2.inputs["Surface"])
assert ops.flat_layers(mat2) is not None
assert ops.light_layers(mat2)
assert ops.flat_layers(mat2) is None
assert o2.inputs["Surface"].links[0].from_node == b2
assert b2.inputs["Base Color"].links[0].from_node == g2
print("a paint-over layer stack is lit like the paper")
print("all v39 checks pass")
