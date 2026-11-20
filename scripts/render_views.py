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
    return (0, 115, 25), 260, (0.45, -0.75, 0.5), (175.0, 100.0, 60.0)


def slotted_sheet():
    a = add("RISER")
    a.y, a.width, a.height = 50.0, 70.0, 30.0
    au = a.uid
    c = add("CROSS", host=au, fold="A")
    c.cross_height, c.cross_width = 55.0, 46.0
    b = add("RISER")
    b.y, b.width, b.height = 120.0, 80.0, 45.0
    bu = b.uid
    c = add("CROSS", host=bu, fold="A")
    c.cross_pos, c.cross_height, c.cross_width = -18.0, 75.0, 30.0
    c = add("CROSS", host=bu, fold="A")
    c.cross_pos, c.cross_height, c.cross_width, c.feet = 20.0, 50.0, 18.0, "LEFT"
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


def vfold_bite():
    a = add("VFOLD")
    a.y, a.height, a.glue = 60.0, 70.0, 45.0
    a.bite, a.bite_len, a.bite_angle = True, 25.0, 18.0
    return (0, 85, 30), 240, (0.7, -0.6, 0.4), (170.0, 125.0, 100.0)


def bite_steps():
    a = add("VFOLD")
    a.y, a.height, a.glue = 60.0, 70.0, 45.0
    a.bite, a.bite_len, a.bite_angle = True, 42.0, 10.0
    for ln, tn in ((16.0, 10.0), (13.0, 12.0), (11.0, 14.0)):  # (a hooked beak)
        st_ = a.bite_more.add()
        st_.length, st_.angle = ln, tn
    return (0, 85, 30), 240, (0.7, -0.6, 0.4), (170.0, 125.0, 100.0)


def beak_bite():
    a = add("VFOLD")
    a.shape, a.y, a.height, a.glue = "TRI", 60.0, 75.0, 45.0
    a.bite, a.bite_len, a.bite_angle = True, 45.0, 10.0
    for ln, tn in ((16.0, 12.0), (13.0, 14.0)):
        st_ = a.bite_more.add()
        st_.length, st_.angle = ln, tn
    return (0, 85, 30), 240, (0.7, -0.6, 0.4), (170.0, 125.0, 100.0)


def jack_flat():
    bpy.ops.popup.add(kind="JACK", variant="FLAT")
    return (0, 115, 25), 260, (0.25, -0.75, 0.6), (175.0, 130.0, 90.0)


def strut_lid():
    a = add("CUBE")
    a.size, a.size_r, a.height, a.lid = 55.0, 28.0, 32.0, "STRUT"
    return (0, 105, 25), 250, (-0.35, 0.75, 0.55), (178.0, 140.0, 100.0)


def rect_lid():
    a = add("CUBE")
    a.size, a.size_r, a.height, a.lid = 55.0, 28.0, 32.0, "DIP"
    return (0, 105, 25), 250, (0.35, -0.75, 0.55), (178.0, 140.0, 100.0)


def pair():
    a = add("TUBE", variant="PAIR")
    a.y = 80.0
    return (0, 95, 30), 150, (0.55, -0.6, 0.55), (178.0, 130.0, 80.0)


def lid_host():
    a = add("CUBE")
    a.size, a.size_r, a.height, a.lid = 55.0, 28.0, 32.0, "STRUT"
    b = add("VFOLD", host=a.uid)
    b.wall = "NONE"  # (Roof Crease)
    b.y, b.height, b.glue = 8.0, 14.0, 14.0
    return (0, 110, 35), 230, (0.35, -0.75, 0.55), (178.0, 140.0, 100.0)


def strut_cutaway():
    a = add("CUBE")
    a.size, a.size_r, a.height, a.lid = 55.0, 28.0, 32.0, "STRUT"
    return (-5, 85, 15), 170, (-0.2, 0.45, 0.87), (178.0, 145.0, 115.0), \
        ("Cube1.A", "Cube1.D", "Cube1.Close")


def turning_disc():
    bpy.ops.popup.add(kind="BOX", variant="DISC")
    return (20, 105, 30), 280, (0.55, -0.6, 0.55), (178.0, 130.0, 90.0)


def disc_close():
    a = add("BOX")
    a.tri45, a.tri_size, a.tri_disc, a.disc_r = "TOP", 14.0, "FRONT", 18.0
    return (20, 125, 30), 110, (0.35, -0.55, 0.75), (170.0, 130.0, 95.0)


def disc_hidden():
    a = add("BOX")
    a.tri45, a.tri_size, a.tri_disc, a.disc_show = "TOP", 14.0, "FRONT", False
    return (-8, 168, 25), 80, (0.5, -0.4, 0.77), (170.0, 130.0, 95.0)


def turning_wheels():
    bpy.ops.popup.add(kind="BOX", variant="WHEELS")
    return (20, 105, 30), 300, (0.6, -0.2, 0.75), (178.0, 130.0, 90.0)


def swing_arm():
    a = add("SWING")
    a.y, a.arm_len = 60.0, 45.0
    b = add("BOX", host=a.uid, fold="B")
    b.width, b.height, b.depth = 20.0, 12.0, 12.0
    return (40, 90, 10), 280, (0.25, -0.45, 0.86), (178.0, 125.0, 80.0)


def swing_bare():
    a = add("SWING")
    a.y, a.arm_len, a.width, a.height = 60.0, 45.0, 6.0, 6.0  # (a stub of mask)
    return (40, 80, 8), 170, (0.2, -0.55, 0.81), (170.0, 125.0, 80.0)


def swing_shut():
    a = add("SWING")
    a.y, a.arm_len, a.width, a.height = 60.0, 45.0, 6.0, 6.0  # (a stub of mask)
    a.swing_hinge = "SHUT"
    return (35, 75, 10), 210, (0.1, -0.5, 0.86), (175.0, 140.0, 105.0)


def flapping_arms():
    a = add("VFOLD")
    a.y, a.height, a.glue = 40.0, 80.0, 45.0
    au = a.uid
    add("ARMS", host=au, fold="A")
    b = add("BOX")
    b.y, b.width, b.height, b.depth = 140.0, 50.0, 30.0, 30.0
    bu = b.uid
    add("ARMS", host=bu, fold="A")
    return (0, 105, 25), 260, (0.25, -0.9, 0.4), (175.0, 120.0, 70.0)


def on_riser():
    r = add("RISER")
    r.y, r.width, r.height = 60.0, 90.0, 70.0
    ru = r.uid
    add("BOX", host=ru, fold="RR")
    add("VFOLD", host=ru, fold="RL")
    add("BOX", host=ru, fold="RVR")
    return (0, 105, 25), 260, (0.25, -0.9, 0.45), (175.0, 120.0, 70.0)


SCENES = dict(strut_cutaway=strut_cutaway, rect_lid=rect_lid, strut_lid=strut_lid, turning_disc=turning_disc, disc_close=disc_close, disc_hidden=disc_hidden, lid_host=lid_host, pair=pair, turning_wheels=turning_wheels, jack_flat=jack_flat, bite_steps=bite_steps, beak_bite=beak_bite, swing_arm=swing_arm, swing_bare=swing_bare, swing_shut=swing_shut, house=house, on_riser=on_riser, flapping_arms=flapping_arms, vfold_bite=vfold_bite, animal_face=animal_face, box_ends=box_ends, slotted_sheet=slotted_sheet, collar_tiers=collar_tiers, loop_cone=loop_cone, cone_lid=cone_lid,
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
    if len(res) > 4:  # (a cutaway: these panels see-through in the picture)
        me = st.card.data
        mat = bpy.data.materials.new("Cutaway")
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        nt.links.new(tr.outputs[0], out.inputs[0])
        me.materials.append(mat)
        k = len(me.materials) - 1
        idx = {st.card.vertex_groups[n].index for n in res[4] if n in st.card.vertex_groups}
        inv = [any(g.group in idx and g.weight > 0.5 for g in v.groups) for v in me.vertices]
        for poly in me.polygons:
            if all(inv[i] for i in poly.vertices):
                poly.material_index = k
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
