"""Artwork that stays on the paper while the card moves.

* Paint texture: a UDIM image ("Pop-up Art") on the PopupArt UV map, one
  tile per piece (tile 1001 is the card). Paint it on the flat Layout or the
  folded card in Texture Paint mode, or point Paint System layers at the
  PopupArt UV map. "Bake Art" flattens any material into "Pop-up Print" for
  export.
* Sketch layers: one Grease Pencil object ("Pop-up Sketch") with a layer per
  panel, each layer parented to that panel's bone, so strokes ride along.
"""

import os
import tempfile

import bpy
from mathutils import Matrix, Vector

from . import live
from .naming import N
from .build import ART_UV, TILE_MM

ART_IMAGE = "Pop-up Art"
PRINT_IMAGE = "Pop-up Print"
SKETCH = "Pop-up Sketch"
INK = "Pop-up Ink"
CUT_INK = "Pop-up Cut"
CUT_SUFFIX = " cut"  # sketch layers ending so are cut out as holes


# ---------------------------------------------------------------- textures
def _tile_size(meta, slot, dpi):
    px = lambda mm: max(16, int(round(mm / 25.4 * dpi)))
    for p in meta["pieces"].values():
        if p["slot"] == slot and p["is_card"]:
            return px(2 * meta["W"]), px(meta["H"])
    return px(TILE_MM), px(TILE_MM)


def make_tiled_image(name, meta, dpi, color=(1, 1, 1, 1)):
    """Create (or extend) a packed UDIM image with one tile per piece. Tiles
    are written as PNG files, loaded as a tiled image and packed into the
    .blend, so nothing depends on files outside it."""
    slots = sorted({p["slot"] for p in meta["pieces"].values()})
    img = bpy.data.images.get(name)
    have = {t.number for t in img.tiles} if img is not None else set()
    need = [s for s in slots if 1001 + s not in have]
    if img is not None and not need:
        return img
    tmp = tempfile.mkdtemp(prefix="popup_art_")
    base = os.path.join(tmp, "art")
    # keep existing tiles' pixels
    if img is not None:
        img.filepath_raw = base + ".<UDIM>.png"
        img.file_format = "PNG"
        img.save()
    for s in need:
        w, h = _tile_size(meta, s, dpi)
        t = bpy.data.images.new("_pop_tile", w, h, alpha=True)
        t.generated_color = color
        t.filepath_raw = f"{base}.{1001 + s}.png"
        t.file_format = "PNG"
        t.save()
        bpy.data.images.remove(t)
    first = min(slots + [s - 1001 for s in have])
    new = bpy.data.images.load(f"{base}.{1001 + first}.png")
    new.source = "TILED"
    new.filepath = base + ".<UDIM>.png"
    new.reload()
    new.pack()
    new.filepath = ""
    if img is not None:
        img.user_remap(new)
        bpy.data.images.remove(img)
    new.name = name
    return new


def _art_nodes(mat):
    nt = mat.node_tree
    tex = nt.nodes.get("Pop-up Art")
    return nt, tex


def refresh_material(scene):
    """Hook the art image into the paper material if it exists."""
    mat = bpy.data.materials.get(N(scene, "Pop-up Paper"))
    img = bpy.data.images.get(N(scene, ART_IMAGE))
    if mat is None or img is None or not mat.use_nodes:
        return
    nt, tex = _art_nodes(mat)
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return
    if tex is None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.name = tex.label = "Pop-up Art"
        tex.location = bsdf.location + Vector((-700, 0))
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = ART_UV
        uv.location = tex.location + Vector((-220, -60))
        nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        geo.location = tex.location + Vector((0, 260))
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.name = "Pop-up Back"
        mix.location = bsdf.location + Vector((-250, 0))
        mix.inputs["B"].default_value = (0.95, 0.93, 0.88, 1.0)  # back of the paper
        nt.links.new(geo.outputs["Backfacing"], mix.inputs["Factor"])
        nt.links.new(tex.outputs["Color"], mix.inputs["A"])
        nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    tex.image = img
    nt.nodes.active = tex
    # painted transparency shows as see-through (Cut Painted Holes makes it real)
    if bsdf.inputs.get("Alpha") is not None and not bsdf.inputs["Alpha"].is_linked:
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])


def add_art_texture(scene, dpi=150):
    meta = live.meta(scene.popup.rig)
    if meta is None:
        raise RuntimeError("build the card first")
    img = make_tiled_image(N(scene, ART_IMAGE), meta, dpi)
    refresh_material(scene)
    return img


# ------------------------------------------------------------------- bake
def bake_art(scene, dpi=150):
    """Bake the card's material colour into the Pop-up Print UDIM image on the
    PopupArt UV map (works with any material, e.g. Paint System layers).

    The bake runs on a temporary copy of the flat layout with temporary
    copies of its materials, so your own materials, their active nodes and
    outputs are never touched, and the scene's render settings are put back."""
    import math as _m

    st = scene.popup
    meta = live.meta(st.rig)
    if meta is None:
        raise RuntimeError("build the card first")
    src = st.layout
    img = bpy.data.images.get(N(scene, PRINT_IMAGE))
    if img is not None:
        bpy.data.images.remove(img)
    # transparent until baked: shows whether the bake drew anything
    img = make_tiled_image(N(scene, PRINT_IMAGE), meta, dpi, color=(0, 0, 0, 0))
    margin = max(4, int(_m.ceil(st.bleed / 25.4 * dpi)) + 2)

    mesh = src.data.copy()
    mesh.name = "_pop_bake"
    mesh.uv_layers.active = mesh.uv_layers[ART_UV]
    mesh.materials.clear()
    copies = []
    for slot in src.material_slots:
        m = slot.material
        if m is None:
            mesh.materials.append(None)
            continue
        c = m.copy()
        c.name = "_pop_bake_" + m.name
        copies.append(c)
        mesh.materials.append(c)
        if not c.use_nodes:
            c.use_nodes = True
        nt = c.node_tree
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = ART_UV
        nt.links.new(uvn.outputs["UV"], n.inputs["Vector"])
        nt.nodes.active = n
    from . import bakecheck
    # Cycles on some Blender builds doesn't decode sRGB textures (pale
    # prints): check, and bake from linear copies if so
    fixed_groups, fixed_images = [], []
    try:
        decoded = bakecheck.textures_decode(bpy.context)
    except Exception as ex:  # the check must never stop a bake
        print(f"Pop-Up Pro: texture decode check skipped: {ex}")
        decoded = True
    if not decoded:
        fixed_groups, fixed_images = bakecheck.linearize_textures(copies, skip={img})
    bake_art.textures_fixed = bool(fixed_images)
    tmp = bpy.data.objects.new("_pop_bake", mesh)
    tmp.matrix_world = src.matrix_world
    scene.collection.objects.link(tmp)

    engine = scene.render.engine
    cyc = scene.cycles
    keep_cycles = (cyc.samples, cyc.device)
    vl = bpy.context.view_layer
    prev_active = vl.objects.active
    prev_sel = [o for o in vl.objects if o.select_get()]
    try:
        scene.render.engine = "CYCLES"
        cyc.samples = 1
        cyc.device = "CPU"
        for o in prev_sel:
            o.select_set(False)
        tmp.select_set(True)
        vl.objects.active = tmp
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=margin,
                            use_clear=True, target="IMAGE_TEXTURES")
        bake_art.last_pass = "BASE"
        # materials that colour through an emission path (paint add-ons)
        # bake black as base colour: bake their emission instead
        if 0.0 <= bakecheck.tiles_brightness(img) < 0.02:
            bpy.ops.object.bake(type="EMIT", margin=margin, use_clear=True,
                                target="IMAGE_TEXTURES")
            bake_art.last_pass = "EMIT"
    finally:
        scene.render.engine = engine
        cyc.samples, cyc.device = keep_cycles  # never leave render settings changed
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        for c in copies:
            bpy.data.materials.remove(c)
        for g in fixed_groups:
            bpy.data.node_groups.remove(g)
        for i in fixed_images:
            bpy.data.images.remove(i)
        for o in prev_sel:
            if o.name in vl.objects:
                o.select_set(True)
        vl.objects.active = prev_active
    img.pack()
    return img


# ---------------------------------------------------------------- sketch
def ink_material():
    mat = bpy.data.materials.get(INK)
    if mat is None:
        mat = bpy.data.materials.new(INK)
        bpy.data.materials.create_gpencil_data(mat)
        mat.grease_pencil.color = (0.05, 0.05, 0.05, 1.0)
        mat.grease_pencil.show_stroke = True
        mat.grease_pencil.show_fill = False
    return mat


def ensure_sketch(scene):
    st = scene.popup
    obj = bpy.data.objects.get(N(scene, SKETCH))
    if obj is None or obj.type != "GREASEPENCIL":
        gp = bpy.data.grease_pencils.new(N(scene, SKETCH))
        obj = bpy.data.objects.new(N(scene, SKETCH), gp)
        # not in a carousel stage's folded collection: Grease Pencil layers
        # parented to bones don't follow them in a collection instance
        from .build import _collection
        _collection(scene).objects.link(obj)
    if not obj.data.materials:
        obj.data.materials.append(ink_material())
    return obj


def cut_material():
    mat = bpy.data.materials.get(CUT_INK)
    if mat is None:
        mat = bpy.data.materials.new(CUT_INK)
        bpy.data.materials.create_gpencil_data(mat)
        mat.grease_pencil.color = (0.9, 0.1, 0.1, 1.0)
        mat.grease_pencil.show_stroke = True
        mat.grease_pencil.show_fill = True
        mat.grease_pencil.fill_color = (0.9, 0.1, 0.1, 0.25)
    return mat


def sketch_layer(scene, panel, cut=False):
    """Layer for one panel, parented to its bone (strokes are stored in the
    bone's space so they move with the panel). cut: the panel's hole layer,
    whose closed strokes are cut out of the paper."""
    st = scene.popup
    obj = ensure_sketch(scene)
    gp = obj.data
    name = panel + CUT_SUFFIX if cut else panel
    if cut:
        mat = cut_material()
        if mat.name not in [m.name for m in gp.materials if m]:
            gp.materials.append(mat)
        obj.active_material_index = [m.name if m else "" for m in gp.materials].index(mat.name)
    elif gp.materials:
        obj.active_material_index = 0
    layer = next((l for l in gp.layers if l.name == name), None)
    if layer is None:
        layer = gp.layers.new(name)
        layer.frames.new(scene.frame_start)
    layer.parent = st.rig
    layer.parent_bone = panel
    layer.use_lights = False
    gp.layers.active = layer
    return obj, layer


def panel_view(scene, panel, offset_mm=0.3):
    """World matrix of a panel's printed face right now (bone frame) and its
    centre, for aligning the view and drawing plane."""
    st = scene.popup
    rig = st.rig
    dg = bpy.context.evaluated_depsgraph_get()
    pb = rig.evaluated_get(dg).pose.bones[panel]
    M = rig.matrix_world @ pb.matrix
    # centre of the panel's faces, in world space, from the deformed card
    card = st.card.evaluated_get(dg)
    me = card.data
    attr = me.attributes.get("pop_panel")
    meta = live.meta(rig)
    idx = [p["name"] for p in meta["panels"]].index(panel)
    pts = []
    if attr is not None:
        for poly in me.polygons:
            if attr.data[poly.index].value == idx:
                pts.extend(card.matrix_world @ me.vertices[v].co for v in poly.vertices)
    centre = sum(pts, Vector()) / len(pts) if pts else M.to_translation()
    normal = (M.to_3x3() @ Vector((0, 0, 1))).normalized()
    return M, centre + normal * (offset_mm / st.mm_per_unit), normal


def release_orphans(scene, keep=None):
    """Sketch layers whose panel was deleted keep their strokes where they
    are, unparented and hidden, instead of pointing at a missing bone."""
    obj = bpy.data.objects.get(N(scene, SKETCH))
    rig = scene.popup.rig
    if obj is None or obj.type != "GREASEPENCIL" or rig is None:
        return
    for layer in obj.data.layers:
        names = keep if keep is not None else rig.data.bones
        if layer.parent == rig and layer.parent_bone not in names:
            name = layer.parent_bone
            layer.parent = None
            layer.hide = True
            if not layer.name.endswith("(removed)"):
                layer.name = f"{name} (removed)"
