"""Guards for Cycles colour bakes (shared with Papercraft Pro v0.11).

* Some Blender builds (e.g. with a system OpenColorIO config) skip decoding
  sRGB image textures in Cycles, so painted art bakes and renders pale while
  EEVEE shows it right. textures_decode() bakes a plain grey next to an sRGB
  texture of the same grey to find out; linearize_textures() then points the
  bake's material copies at linear copies of their images (node groups
  copied too, the originals untouched).
* Materials that colour through an emission path (common in paint layer
  setups) bake black in a Base Colour bake: bake_colour()
  tries Base Colour and falls back to Emission.
"""
import bpy

CHECK_LINEAR = 0.2


def to_srgb(x):
    import numpy as np
    x = np.clip(x, 0.0, None)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def from_srgb(x):
    import numpy as np
    x = np.clip(x, 0.0, None)
    return np.where(x <= 0.04045, x / 12.92, np.power((x + 0.055) / 1.055, 2.4))


def _bake_emit(scene):
    engine = scene.render.engine
    cyc = scene.cycles
    keep = (cyc.samples, cyc.device)
    try:
        scene.render.engine = "CYCLES"
        cyc.samples = 1
        cyc.device = "CPU"
        bpy.ops.object.bake(type="EMIT", margin=1, use_clear=True, target="IMAGE_TEXTURES")
    finally:
        scene.render.engine = engine
        cyc.samples, cyc.device = keep


def textures_decode(context, check_colorspace="sRGB"):
    """Does this Blender's Cycles decode sRGB image textures?"""
    import numpy as np
    scene = context.scene
    vl = context.view_layer
    out_img = bpy.data.images.new("_pop_decode_out", 16, 8, alpha=True)
    tex_img = bpy.data.images.new("_pop_decode_tex", 4, 4, alpha=False)
    grey = float(to_srgb(np.array(CHECK_LINEAR)))
    try:  # before the pixels: changing colour space regenerates the image
        tex_img.colorspace_settings.name = check_colorspace
    except TypeError:
        pass
    tex_img.pixels.foreach_set(np.array([grey, grey, grey, 1.0] * 16, np.float32))
    mesh = bpy.data.meshes.new("_pop_decode")
    mesh.from_pydata([(0, 0, 0), (0.01, 0, 0), (0.01, 0.01, 0), (0, 0.01, 0),
                      (0.02, 0, 0), (0.03, 0, 0), (0.03, 0.01, 0), (0.02, 0.01, 0)],
                     [], [[0, 1, 2, 3], [4, 5, 6, 7]])
    uv = mesh.uv_layers.new(name="_pop_decode")
    uv.data.foreach_set("uv", (0, 0, 0.5, 0, 0.5, 1, 0, 1, 0.5, 0, 1, 0, 1, 1, 0.5, 1))
    mats = []
    for use_texture in (False, True):
        m = bpy.data.materials.new("_pop_decode")
        m.use_nodes = True
        nt = m.node_tree
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        emit = nt.nodes.new("ShaderNodeEmission")
        emit.inputs["Color"].default_value = (CHECK_LINEAR, CHECK_LINEAR, CHECK_LINEAR, 1.0)
        if use_texture:
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = tex_img
            t.interpolation = "Closest"
            nt.links.new(t.outputs["Color"], emit.inputs["Color"])
        nt.links.new(emit.outputs[0], out.inputs["Surface"])
        target = nt.nodes.new("ShaderNodeTexImage")
        target.image = out_img
        nt.nodes.active = target
        mats.append(m)
        mesh.materials.append(m)
    mesh.polygons.foreach_set("material_index", [0, 1])
    obj = bpy.data.objects.new("_pop_decode", mesh)
    obj.location = (0.0, 0.0, -10000.0)
    scene.collection.objects.link(obj)
    prev_sel = [o for o in vl.objects if o.select_get()]
    prev_active = vl.objects.active
    try:
        for o in prev_sel:
            o.select_set(False)
        obj.select_set(True)
        vl.objects.active = obj
        _bake_emit(scene)
        w, h = out_img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        out_img.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)
        plain = float(np.median(px[2:6, 1:7, :3]))
        textured = float(np.median(px[2:6, 9:15, :3]))
    finally:
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        for m in mats:
            bpy.data.materials.remove(m)
        bpy.data.images.remove(out_img)
        bpy.data.images.remove(tex_img)
        for o in prev_sel:
            try:
                o.select_set(True)
            except ReferenceError:
                pass
        vl.objects.active = prev_active
    brighter = float(to_srgb(np.array(plain)))  # undecoded: one sRGB step brighter
    decoded = abs(textured - plain) <= abs(textured - brighter)
    if not decoded:
        print(f"Pop-Up Pro: Cycles is not decoding sRGB textures here (plain {plain:.3f}, "
              f"texture {textured:.3f}); decoding them for the bake instead")
    return decoded


def linearize_textures(materials, skip=()):
    """Point material copies at linear float copies of their sRGB image
    textures (marked Non-Color, so Cycles takes them as they are). Node
    groups are copied too. Returns (groups, images) to remove afterwards.
    skip: images left alone (the bake target)."""
    import numpy as np
    groups, images = {}, {}

    def linear_copy(img):
        if img.name in images:
            return images[img.name]
        cs = img.colorspace_settings
        if img in skip or img.is_float or cs.is_data or "srgb" not in cs.name.lower():
            images[img.name] = None
            return None
        if img.source == "TILED":
            images[img.name] = _linear_tiled(img)
            return images[img.name]
        w, h = img.size
        if w == 0 or h == 0:
            images[img.name] = None
            return None
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(-1, 4)
        px[:, :3] = from_srgb(px[:, :3])
        lin = bpy.data.images.new(f"_pop_linear ({img.name})", w, h, alpha=True,
                                  float_buffer=True)
        lin.colorspace_settings.name = "Non-Color"
        lin.alpha_mode = img.alpha_mode
        lin.pixels.foreach_set(px.ravel())
        images[img.name] = lin
        return lin

    def fix(tree):
        for node in tree.nodes:
            if node.type == "GROUP" and node.node_tree is not None:
                original = node.node_tree
                if original.name not in groups:
                    groups[original.name] = original.copy()
                    fix(groups[original.name])
                node.node_tree = groups[original.name]
            elif node.type == "TEX_IMAGE" and node.image is not None:
                lin = linear_copy(node.image)
                if lin is not None:
                    node.image = lin

    for m in materials:
        if m is not None and m.node_tree is not None:
            fix(m.node_tree)
    return list(groups.values()), [i for i in images.values() if i is not None]


def _linear_tiled(img):
    """A linear (Non-Color, float) copy of a UDIM image, tile by tile."""
    import os
    import tempfile

    import numpy as np
    from .export_svg import _tile_pngs
    tiles = _tile_pngs(img, tempfile.mkdtemp(prefix="popup_lin_"))
    if not tiles:
        return None
    base = os.path.join(tempfile.mkdtemp(prefix="popup_lin_"), "lin")
    for num, path in tiles.items():
        t = bpy.data.images.load(path)
        try:
            w, h = t.size
            px = np.empty(w * h * 4, dtype=np.float32)
            t.pixels.foreach_get(px)
        finally:
            bpy.data.images.remove(t)
        px = px.reshape(-1, 4)
        px[:, :3] = from_srgb(px[:, :3])
        o = bpy.data.images.new("_pop_lin_tile", w, h, alpha=True, float_buffer=True)
        o.colorspace_settings.name = "Non-Color"
        o.pixels.foreach_set(px.ravel())
        o.filepath_raw = f"{base}.{num}.exr"
        o.file_format = "OPEN_EXR"
        o.save()
        bpy.data.images.remove(o)
    first = min(tiles)
    lin = bpy.data.images.load(f"{base}.{first}.exr")
    lin.source = "TILED"
    lin.filepath = base + ".<UDIM>.exr"
    lin.reload()
    lin.colorspace_settings.name = "Non-Color"
    lin.alpha_mode = img.alpha_mode
    lin.name = f"_pop_linear ({img.name})"
    lin.pack()
    return lin


def tiles_brightness(img):
    """Mean brightness of the opaque pixels across a UDIM image's tiles
    (-1 when nothing is opaque)."""
    import tempfile

    import numpy as np
    from .export_svg import _tile_pngs
    total, n = 0.0, 0
    for path in _tile_pngs(img, tempfile.mkdtemp(prefix="popup_chk_")).values():
        t = bpy.data.images.load(path)
        try:
            w, h = t.size
            px = np.empty(w * h * 4, dtype=np.float32)
            t.pixels.foreach_get(px)
        finally:
            bpy.data.images.remove(t)
        px = px.reshape(-1, 4)
        solid = px[px[:, 3] > 0.5]
        total += float(solid[:, :3].sum())
        n += 3 * len(solid)
    return total / n if n else -1.0
