"""v0.32: Render Look - Clean, Showcase, Dawn (Blender's sunrise light), Your Own."""
# families: scene
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=False)
import popup_pro as addon  # noqa: E402
from popup_pro import scene_setup  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
own = sc.world
assert bpy.ops.popup.build() == {"FINISHED"}
sun = bpy.data.objects[scene_setup.SUN]
assert sc.world.name == scene_setup.WHITE and sun.hide_render
print("Clean: white world, no sun in renders")

st.render_look = "SHOWCASE"
key = bpy.data.objects[scene_setup.KEY]
assert sc.world.name == scene_setup.SHOW and not key.hide_render and key.hide_viewport
assert sc.eevee.taa_render_samples >= 64
print("Showcase: white world with the sun")

assert scene_setup._sunrise_path(), "sunrise.exr not found"
st.render_look = "DAWN"
assert sc.world.name == scene_setup.DAWN and not sun.hide_render
env = [n for n in sc.world.node_tree.nodes if n.type == "TEX_ENVIRONMENT"]
assert env and env[0].image is not None
print("Dawn: sunrise world with the sun")

st.render_look = "OWN"
assert sc.world == own, sc.world
assert sun.hide_render and key.hide_render
print("Your Own: the scene's world back")

st.render_look = "CLEAN"
assert sc.world.name == scene_setup.WHITE
assert bpy.ops.popup.setup_scene(look="DAWN") == {"FINISHED"}
assert sc.world.name == scene_setup.DAWN
st.render_look = "OWN"
assert sc.world == own
print("all v32 checks pass")
