"""Render a mechanism at three openings, side by side, for the guide.

    python scripts/render_views.py              all the pictures below
    python scripts/render_views.py loop_cone    just that one

Needs a Python with bpy (`pip install bpy`); renders with Cycles on the CPU,
so it works without a screen. Writes docs/images/<name>.jpg (about 30 KB
each). To picture something new, add a function to SCENES that builds it and
returns where to look (x, y, z in mm; the fold runs up y from 0) and from
how far (mm).
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402

OPENINGS = (175.0, 115.0, 55.0)
SIZE = (427, 400)  # each view, pixels
PAPER = (0.90, 0.66, 0.38, 1.0)  # a card colour, so the folds show
VIEW = Vector((0.3, -0.8, 0.55)).normalized()  # camera's side of the target

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}, kind
    return st.mechs[-1]


def collar_tiers():
    t = add("TUBE")
    t.y, t.x, t.depth, t.height = 105.0, 30.0, 40.0, 25.0
    t.front = t.back = 30.0
    m = add("BOX", host=t.uid, fold="KFL")
    m.height = m.depth = 18.0
    m.width = 75.0
    m.collar = True
    m.collar_below, m.collar_width, m.collar_slope = 30.0, 9.0, 60.0
    m.collar_rail, m.collar_tiers, m.collar_crenels = 5.0, 3, True
    return (-8, 100, 50), 200


def loop_cone():
    a = add("TUBE", variant="LOOP")
    a.y = 70.0
    b = add("TUBE", variant="LOOP")
    b.y, b.height, b.cone_top = 140.0, 30.0, 14.0
    return (0, 105, 12), 250


def cone_lid():
    a = add("TUBE", variant="LOOP")
    a.y, a.height, a.depth = 55.0, 30.0, 20.0
    a.cone_lean, a.roof = 20.0, "FLAT"
    b = add("TUBE", variant="LOOP")
    b.y, b.height, b.depth = 135.0, 30.0, 20.0
    b.cone_lean, b.roof, b.roof_fold = 20.0, "FLAT", "DIP"
    return (0, 95, 18), 240


def angled_box():
    a = add("BOX", variant="ANGLED")
    a.y = 60.0
    b = add("BOX", variant="ANGLED")
    b.y, b.fan_creases = 135.0, "THREE"
    return (0, 105, 15), 270


def cube_tower():
    c = add("CUBE")
    c.y, c.size, c.height = 105.0, 30.0, 45.0
    c.roof, c.roof_height = "POINTED", 20.0
    c.collar = True
    c.collar_below, c.collar_width, c.collar_slope, c.collar_rail = 14.0, 10.0, 60.0, 5.0
    return (0, 103, 34), 165


def house():
    m = add("CUBE")
    m.y, m.size, m.size_r, m.height = 70.0, 45.0, 65.0, 35.0
    m.roof, m.roof_height, m.eave, m.gable_turn = "GABLE", 20.0, 5.0, True
    return (0, 115, 25), 260


def slotted_sheet():
    a = add("RISER")
    a.y, a.width, a.height, a.brace_size = 50.0, 70.0, 30.0, 18.0
    a.slotted, a.cross_height, a.cross_width = True, 55.0, 50.0
    b = add("RISER")
    b.y, b.width, b.height = 140.0, 50.0, 45.0
    return (0, 115, 20), 270


def box_ends():
    a = add("BOXEND")
    a.y = 40.0
    b = add("BOXEND")
    b.y, b.box_side, b.depth, b.height, b.box_ends = 125.0, "L", 30.0, 30.0, "FRONT"
    return (0, 105, 12), 270, (0.3, -0.8, 0.55), (175.0, 135.0, 95.0)


def animal_face():
    a = add("TUBE", variant="FACE")
    a.y = 80.0
    return (0, 85, 20), 170, (0.25, -0.75, 0.6), (175.0, 130.0, 80.0)


SCENES = dict(house=house, animal_face=animal_face, box_ends=box_ends, slotted_sheet=slotted_sheet, collar_tiers=collar_tiers, loop_cone=loop_cone, cone_lid=cone_lid,
              angled_box=angled_box, cube_tower=cube_tower)


def tint(card):
    for mat in card.data.materials:
        nt = mat.node_tree
        if "Guide Tint" in nt.nodes:  # (the paper's material is kept between cards)
            continue
        for n in [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"]:
            base = n.inputs["Base Color"]
            mix = nt.nodes.new("ShaderNodeMix")
            mix.name = "Guide Tint"
            mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
            mix.inputs[0].default_value = 1.0
            mix.inputs[7].default_value = PAPER
            if base.is_linked:
                nt.links.new(base.links[0].from_socket, mix.inputs[6])
            else:
                mix.inputs[6].default_value = base.default_value[:]
            nt.links.new(mix.outputs[2], base)


def render(name):
    st.mechs.clear()
    res = SCENES[name]()
    target, dist = res[:2]
    # (a scene can ask for its own viewpoint and openings)
    VIEW = Vector(res[2]).normalized() if len(res) > 2 else globals()["VIEW"]
    OPENINGS = res[3] if len(res) > 3 else globals()["OPENINGS"]
    bpy.ops.popup.build()
    build.rebuild(sc, force=True)
    if st.warnings:
        print(f"{name}: {st.warnings}")
    bpy.ops.popup.setup_scene(look="SHOWCASE", view_camera=False)
    tint(st.card)
    s = 1.0 / st.mm_per_unit
    cam = sc.camera
    cam.location = Vector(target) * s + VIEW * dist * s
    cam.rotation_euler = (-VIEW).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50
    sc.render.engine = "CYCLES"
    sc.cycles.samples, sc.cycles.use_denoising = 48, True
    sc.render.resolution_x, sc.render.resolution_y = SIZE
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.exposure = -0.35
    st.keep_open = False  # Open is exactly the angle asked for
    tmp = tempfile.mkdtemp()
    tiles = []
    for i, t in enumerate(OPENINGS):
        st.rig["pop_open"] = t
        st.rig.update_tag()
        sc.frame_set(sc.frame_current)
        sc.render.filepath = os.path.join(tmp, f"{i}.png")
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(sc.render.filepath)
        px = np.empty(SIZE[0] * SIZE[1] * 4, dtype=np.float32)
        im.pixels.foreach_get(px)
        tiles += [px.reshape(SIZE[1], SIZE[0], 4), np.ones((SIZE[1], 3, 4), np.float32)]
    row = np.concatenate(tiles[:-1], axis=1)
    out = bpy.data.images.new(name, row.shape[1], row.shape[0], alpha=False)
    out.pixels.foreach_set(row.ravel())
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 82
    path = os.path.join(ROOT, "docs", "images", name + ".jpg")
    out.save_render(path, scene=sc)
    print("wrote", os.path.relpath(path, ROOT))


for name in sys.argv[1:] or list(SCENES):
    render(name)
