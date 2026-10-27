"""v0.25: Bake Art for Print guards (from Papercraft Pro v0.11): Cycles
builds that skip the sRGB decode bake from linear copies (prints match the
viewport), materials that colour through emission bake their emission, and
nothing the bake touches is left behind."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import art, bakecheck, build  # noqa: E402
from popup_pro.export_svg import _tile_pngs  # noqa: E402
from popup_pro.naming import N  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert bpy.ops.popup.build() == {"FINISHED"}
mat = bpy.data.materials[N(sc, "Pop-up Paper")]
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")

# the paint: an sRGB image of one colour
SRGB = (0.80, 0.30, 0.20)
paint = bpy.data.images.new("paint", 8, 8, alpha=False)
paint.colorspace_settings.name = "sRGB"
paint.pixels.foreach_set(np.array(list(SRGB) + [1.0], np.float32).repeat(1).tolist() * 64)
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = paint
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])


def card_colour():
    img = bpy.data.images[N(sc, art.PRINT_IMAGE)]
    p = _tile_pngs(img, tempfile.mkdtemp())[1001]
    t = bpy.data.images.load(p)
    w, h = t.size
    px = np.empty(w * h * 4, np.float32)
    t.pixels.foreach_get(px)
    bpy.data.images.remove(t)
    px = px.reshape(-1, 4)
    solid = px[px[:, 3] > 0.5]
    return np.median(solid[:, :3], axis=0)


assert bakecheck.textures_decode(bpy.context)  # this build decodes
art.bake_art(sc, dpi=20)
n0 = (len(bpy.data.images), len(bpy.data.materials), len(bpy.data.node_groups),
      len(bpy.data.objects), len(bpy.data.meshes))
c_ok = card_colour()
assert np.abs(c_ok - SRGB).max() < 0.03, c_ok
assert art.bake_art.last_pass == "BASE" and not art.bake_art.textures_fixed
print("base colour bake matches the paint", np.round(c_ok, 3))

# a build that skips the decode: the bake uses linear copies and still
# prints the paint's colour (here Cycles does decode, so the linear copies
# must give the same answer)
real = bakecheck.textures_decode
bakecheck.textures_decode = lambda ctx, **k: False
try:
    art.bake_art(sc, dpi=20)
finally:
    bakecheck.textures_decode = real
c_fix = card_colour()
assert art.bake_art.textures_fixed
assert np.abs(c_fix - SRGB).max() < 0.03, c_fix
print("decode fix: linear copies bake the same colour", np.round(c_fix, 3))

# colour through emission (paint add-ons): base colour bakes black, so the
# emission is baked instead
emit = nt.nodes.new("ShaderNodeEmission")
nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
nt.links.new(emit.outputs[0], out.inputs["Surface"])
art.bake_art(sc, dpi=20)
c_em = card_colour()
assert art.bake_art.last_pass == "EMIT", art.bake_art.last_pass
assert np.abs(c_em - SRGB).max() < 0.03, c_em
print("emission material bakes its emission", np.round(c_em, 3))

n1 = (len(bpy.data.images), len(bpy.data.materials), len(bpy.data.node_groups),
      len(bpy.data.objects), len(bpy.data.meshes))
assert n1 == n0, (n0, n1)  # nothing left behind (the Print image existed already)
addon.unregister()
print("V25 OK")
