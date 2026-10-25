"""v0.16: true colours while painting. In Texture Paint the paper shows its
art unlit with the Standard view transform (so colours picked off the screen
match the art), and everything is put back afterwards."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import art, colours  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert bpy.ops.popup.build() == {"FINISHED"}
art.add_art_texture(sc, dpi=20)
sc.view_settings.view_transform = "AgX"
mat = st.card.data.materials[0]
out = next(n for n in mat.node_tree.nodes if n.type == "OUTPUT_MATERIAL")
before = out.inputs["Surface"].links[0].from_node.name
n_nodes = len(mat.node_tree.nodes)

assert colours.enter(sc)
assert not colours.enter(sc)  # once only
assert sc.view_settings.view_transform == "Standard"
src = out.inputs["Surface"].links[0].from_node
assert src.name == colours.MIX
emit = mat.node_tree.nodes[colours.EMIT]
assert emit.inputs["Color"].links[0].from_node.name == "Pop-up Back"  # art front, paper back
colours.leave(sc)
assert sc.view_settings.view_transform == "AgX"
assert out.inputs["Surface"].links[0].from_node.name == before
assert len(mat.node_tree.nodes) == n_nodes
print("true colours on and off")

st.true_colours = False
assert not colours.enter(sc)
assert sc.view_settings.view_transform == "AgX"
print("can be turned off")
addon.unregister()
print("V16 OK")
