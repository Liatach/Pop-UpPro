"""v0.39: paint layers with Paint System (a separate extension, called, not
included). Set PAINT_SYSTEM_DIR to a folder holding a 'paint_system'
package to run the Paint System checks; without it they are skipped."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PS = os.environ.get("PAINT_SYSTEM_DIR")
if PS:
    sys.path.insert(0, PS)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import ops  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
assert bpy.ops.popup.build() == {"FINISHED"}
if not PS:
    assert not ops.ps_available()
    assert not bpy.ops.popup.paint_layers.poll()
    print("no Paint System: the panel offers to get it; nothing else changes")
    print("all v39 checks pass (Paint System checks skipped)")
    sys.exit(0)

import paint_system  # noqa: E402
paint_system.register()
assert ops.ps_available()
bpy.ops.popup.paint()  # painting with True Colours on: setting up must not mix it in
assert bpy.ops.popup.paint_layers() == {"FINISHED"}
g = ops.ps_group_node(sc)
assert g is not None
mat = st.card.data.materials[0]
nt = mat.node_tree
out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
# the layers go into the paper's colour (lit like the paper), over its art
assert bsdf.inputs["Base Color"].links[0].from_node == g
assert g.inputs["Color"].links and g.inputs["Color"].links[0].from_node.name == "Pop-up Back"
assert ops.ps_flat_setup(mat) is None
# and no unlit preview inside the stack (it's only ever on the output)
assert not any(ln.from_node.name.startswith("Pop-up True") for i in g.inputs for ln in i.links)
assert not mat.use_backface_culling, "the paper's back still shows"
art_img = ops.paint_images(sc)[0]
assert g.inputs["Color Alpha"].links and g.inputs["Color Alpha"].links[0].from_node.image == art_img
assert ops.painting(bpy.context)
now = ops.painting_into(sc)
assert now is not None and now != art_img and now.source == "TILED", now
print("Paint System layers over the paper, painting into", now.name)
from popup_pro import ui  # noqa: E402
ext = ui._ps_module("panels.extras_panels")
assert ext is not None and callable(ext.draw_brush_color_settings) and callable(ext.draw_brush_settings)
assert hasattr(bpy.types, "MAT_PT_Layers") and bpy.types.MAT_PT_Layers.poll(bpy.context)
print("its colour, brush and layer panels are found to draw in ours")
bpy.ops.popup.paint_erase()
assert ops.painting_into(sc) == art_img, "erasing works on the paper"
bpy.ops.popup.paint_into(into="OTHER")
assert ops.painting_into(sc) == now
bpy.ops.popup.paint()  # off
assert out.inputs["Surface"].links[0].from_node == bsdf
assert not any(n.name.startswith("Pop-up True") for n in nt.nodes), "flat colours gone"
assert bpy.ops.popup.paint_layers() == {"CANCELLED"}  # only once

# an older Paint Over stack (flat layers over the shaded paper) is lit again
mat2 = mat.copy()
n2 = mat2.node_tree
b2 = next(n for n in n2.nodes if n.type == "BSDF_PRINCIPLED")
g2 = next(n for n in n2.nodes if n.type == "GROUP" and n.node_tree == g.node_tree)
o2 = next(n for n in n2.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
s2r = n2.nodes.new("ShaderNodeShaderToRGB")
mix = n2.nodes.new("ShaderNodeMixShader")
clear = n2.nodes.new("ShaderNodeBsdfTransparent")
n2.links.new(b2.inputs["Base Color"].links[0].from_socket, b2.inputs["Base Color"])
n2.links.new(n2.nodes["Pop-up Back"].outputs["Result"], b2.inputs["Base Color"])
n2.links.new(b2.outputs[0], s2r.inputs[0])
n2.links.new(s2r.outputs[0], g2.inputs["Color"])
n2.links.new(g2.outputs["Color Alpha"], mix.inputs[0])
n2.links.new(clear.outputs[0], mix.inputs[1])
n2.links.new(g2.outputs["Color"], mix.inputs[2])
n2.links.new(mix.outputs[0], o2.inputs["Surface"])
assert ops.ps_flat_setup(mat2) is not None
assert ops.ps_light(mat2)
assert ops.ps_flat_setup(mat2) is None
assert o2.inputs["Surface"].links[0].from_node == b2
assert b2.inputs["Base Color"].links[0].from_node == g2
assert g2.inputs["Color"].links[0].from_node.name == "Pop-up Back"
print("a Paint Over stack is lit like the paper")
print("all v39 checks pass")
