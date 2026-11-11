"""v0.24: Set Up Scene: Material Preview with the dawn HDRI, a gentle sun,
fold lines, light crisp AO; carousel stages included; paper texture as one
editable node group."""
# families: scene
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
# clean renders: the sun stays in the viewport, out of renders, white world
assert bpy.data.objects[scene_setup.SUN].hide_render
assert all(s.world is not None and s.world.name == scene_setup.WHITE for s in [sc] + stages)
sc.popup.clean_render = False
assert not bpy.data.objects[scene_setup.SUN].hide_render
assert stages[0].world is None
# one-sided beak
from popup_pro.core.model import Model  # noqa: E402
for sh, nl, nr in (("BEAK_L", 3, 4), ("BEAK_R", 4, 3)):
    V = dict(type="VFOLD", uid=1, label="v", y=60, phi_l=40, phi_r=75, alpha_l=95,
             alpha_r=60, glue=40, height=50, tab=8, tab_side="IN", shape=sh)
    m = Model(dict(W=148.5, H=210, hold="SYM"), [V])
    m.check_fit()
    assert not m.warnings, m.warnings
    assert [len(m.panels[n].polys[0]) for n in ("VFold1.HalfL", "VFold1.HalfR")] == [nl, nr]
addon.unregister()
print("V24 OK")
