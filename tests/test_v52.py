"""v0.52: painting's flat colours never outlast painting: an unlit preview
left in the paper, even one a layer stack came to use as its paper, is put
back to the lit paper on rebuild (and on opening a file)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, colours  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
bpy.ops.popup.build()
bpy.ops.popup.add_art()
mat = st.card.data.materials[0]
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
st.true_colours = True
assert colours.enter(sc)
mix = nt.nodes[colours.MIX]
assert out.inputs["Surface"].links[0].from_node == mix
# something else takes the unlit preview as its paper (as a Paint Over layer
# stack set up while painting did), then the session ends without leaving
s2r = nt.nodes.new("ShaderNodeShaderToRGB")
nt.links.new(mix.outputs[0], s2r.inputs[0])
del sc[colours.KEY]
build.rebuild(sc, force=True)
assert not any(nt.nodes.get(k) for k in (colours.EMIT, colours.MIX, colours.CLEAR))
assert out.inputs["Surface"].links[0].from_node == bsdf
assert s2r.inputs[0].links[0].from_node == bsdf, "the stack gets the lit paper"
print("v52 ok")
