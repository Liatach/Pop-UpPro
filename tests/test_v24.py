"""v0.24: Set Up Scene: Material Preview with the dawn HDRI, a gentle sun,
fold lines, light crisp AO; carousel stages included; paper texture as one
editable node group."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=False)
import popup_pro as addon  # noqa: E402
from popup_pro import carousel, scene_setup  # noqa: E402

addon.register()
sc = bpy.context.scene
for o in list(sc.objects):
    bpy.data.objects.remove(o)
sc.popup.size = "A5"
assert bpy.ops.popup.make_carousel(count=3) == {"FINISHED"}
stages = carousel.stages(sc)
# the first carousel in a file sets the scene up by itself
assert sc.get("pop_setup_done")
for s in [sc] + stages:
    e = s.eevee
    assert s.render.engine == "BLENDER_EEVEE"
    assert e.use_fast_gi and e.fast_gi_method == "AMBIENT_OCCLUSION_ONLY"
    assert e.fast_gi_resolution == "2" and not e.ray_tracing_options.denoise_bilateral
    assert e.ray_tracing_options.trace_max_roughness == 0.0
    assert s.view_settings.view_transform == "Standard"
    assert s.collection.objects.get(scene_setup.SUN) is not None
sun = bpy.data.objects[scene_setup.SUN]
assert abs(sun.data.energy - 0.6) < 1e-6
print("eevee, sun, colour on every stage")

# the views: whatever this headless session has
scenes, views = scene_setup.setup(bpy.context, all_workspaces=True)
for ws in bpy.data.workspaces:
    for area in ws.screens[0].areas:
        if area.type == "VIEW_3D":
            sp = area.spaces.active
            assert sp.shading.type == "MATERIAL" and sp.shading.studio_light == "sunrise.exr"
            assert sp.shading.use_scene_lights and sp.overlay.show_wireframes
print("views:", views)

# paper texture: one group, wired in and out on demand
s1 = stages[0]
with carousel.in_scene(s1):
    assert bpy.ops.popup.build() == {"FINISHED"}
scene_setup.paper_texture([s1], on=True)
from popup_pro.naming import N  # noqa: E402
mat = bpy.data.materials[N(s1, "Pop-up Paper")]
bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
assert bsdf.inputs["Normal"].is_linked
assert mat.node_tree.nodes[scene_setup.GRAIN].node_tree.name == scene_setup.GRAIN
scene_setup.paper_texture([s1], on=False)
assert not bsdf.inputs["Normal"].is_linked
# no sun when asked
scene_setup.setup(bpy.context, sun_on=False)
assert sc.collection.objects.get(scene_setup.SUN) is None
assert bpy.ops.popup.setup_scene() == {"FINISHED"}
addon.unregister()
print("V24 OK")
