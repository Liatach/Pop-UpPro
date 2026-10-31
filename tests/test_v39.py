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
assert out.inputs["Surface"].links[0].from_node.type == "MIX_SHADER"
assert not any(n.name.startswith("Pop-up True") for n in nt.nodes), "no unlit preview inside"
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
assert out.inputs["Surface"].links[0].from_node.type == "MIX_SHADER"
assert bpy.ops.popup.paint_layers() == {"CANCELLED"}  # only once
print("all v39 checks pass")
