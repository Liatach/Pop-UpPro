"""v0.37/0.38: Paint is one on/off toggle on the card as it stands; Paper /
Layer picks what the brush paints into; True Colours leaves a material drawn
by something else (Paint System) alone."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import colours, ops  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
assert bpy.ops.popup.build() == {"FINISHED"}
cam = sc.camera
bpy.context.view_layer.objects.active = st.rig
rig_mod = st.card.modifiers["Pop-up Rig"]

# v0.38: one Paint toggle on the card as it stands
assert bpy.ops.popup.paint() == {"FINISHED"}
assert ops.painting(bpy.context) and rig_mod.show_viewport and not st.layout.hide_get()
art = ops.paint_images(sc)[0]
assert ops.painting_into(sc) == art
assert bpy.ops.popup.paint() == {"FINISHED"}  # and off again
assert bpy.context.mode == "OBJECT" and rig_mod.show_viewport and not st.layout.hide_get()
assert bpy.context.view_layer.objects.active == st.rig
print("Paint toggles on and off on the card as it stands")

# a card left flat by v0.37 folds again
rig_mod.show_viewport = False
sc["pop_paint_flat"] = True
st.layout.hide_set(True)
bpy.ops.popup.paint()
assert rig_mod.show_viewport and not st.layout.hide_get()
bpy.ops.object.mode_set(mode="OBJECT")
from popup_pro import holes  # noqa: E402
holes._last_mode["mode"] = "PAINT_TEXTURE"
holes._mode_changed()  # what Blender's mode notification runs
print("leaving by Blender's mode menu is fine too")

# a paint layer on top (as Paint System makes): pick it, and back to the paper
mat = st.card.data.materials[0]
nt = mat.node_tree
out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
layer = bpy.data.images.new("Layer", 64, 64, alpha=True)
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = layer
mix = nt.nodes.new("ShaderNodeMixShader")
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
nt.links.new(bsdf.outputs[0], mix.inputs[1])
nt.links.new(tex.outputs[0], mix.inputs[0])
nt.links.new(mix.outputs[0], out.inputs["Surface"])
bpy.ops.popup.paint()
assert out.inputs["Surface"].links[0].from_node == mix, "True Colours left it alone"
assert bpy.ops.popup.paint_into(into="OTHER") == {"FINISHED"}
assert ops.painting_into(sc) == layer
assert bpy.ops.popup.paint_into(into="ART") == {"FINISHED"}
assert ops.painting_into(sc) == art
bpy.ops.popup.paint()  # off
assert out.inputs["Surface"].links[0].from_node == mix
print("paint layers kept showing; Paper / Layer picks the target")

# a stack built on True Colours' own nodes survives leaving
nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
bpy.ops.popup.paint()
tm = nt.nodes.get(colours.MIX)
assert tm is not None
s2r = nt.nodes.new("ShaderNodeShaderToRGB")
nt.links.new(tm.outputs[0], s2r.inputs[0])
nt.links.new(s2r.outputs[0], mix.inputs[1])
nt.links.new(mix.outputs[0], out.inputs["Surface"])
bpy.ops.popup.done_painting()
assert out.inputs["Surface"].links[0].from_node == mix
assert nt.nodes.get(colours.MIX) and nt.nodes.get(colours.EMIT) and nt.nodes.get(colours.CLEAR)
print("a stack built while painting keeps its inputs and its output")
print("all v37 checks pass")
