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
from .build import ART_UV, TILE_MM

ART_IMAGE = "Pop-up Art"
PRINT_IMAGE = "Pop-up Print"
SKETCH = "Pop-up Sketch"
INK = "Pop-up Ink"


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
    mat = bpy.data.materials.get("Pop-up Paper")
    img = bpy.data.images.get(ART_IMAGE)
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


def add_art_texture(scene, dpi=150):
    meta = live.meta(scene.popup.rig)
    if meta is None:
        raise RuntimeError("build the card first")
    img = make_tiled_image(ART_IMAGE, meta, dpi)
    refresh_material(scene)
    return img


# ------------------------------------------------------------------- bake
def bake_art(scene, dpi=150):
    """Bake the card's material colour into the Pop-up Print UDIM image on the
    PopupArt UV map (works with any material, e.g. Paint System layers)."""
    st = scene.popup
    meta = live.meta(st.rig)
    if meta is None:
        raise RuntimeError("build the card first")
    obj = st.layout
    img = bpy.data.images.get(PRINT_IMAGE)
    if img is not None:
        bpy.data.images.remove(img)
    img = make_tiled_image(PRINT_IMAGE, meta, dpi, color=(1, 1, 1, 1))
    mats = [m for m in obj.data.materials if m and m.use_nodes]
    added = []
    for m in mats:
        n = m.node_tree.nodes.new("ShaderNodeTexImage")
        n.image = img
        n.name = "_pop_bake"
        uvn = m.node_tree.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = ART_UV
        uvn.name = "_pop_bake_uv"
        m.node_tree.links.new(uvn.outputs["UV"], n.inputs["Vector"])
        prev = m.node_tree.nodes.active
        m.node_tree.nodes.active = n
        added.append((m, n, uvn, prev))
    engine = scene.render.engine
    cyc = scene.cycles
    keep_cycles = (cyc.samples, cyc.device)
    vl = bpy.context.view_layer
    prev_active = vl.objects.active
    prev_sel = [o for o in vl.objects if o.select_get()]
    prev_uv = obj.data.uv_layers.active
    try:
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 1
        scene.cycles.device = "CPU"
        for o in prev_sel:
            o.select_set(False)
        hidden = obj.hide_get()
        obj.hide_set(False)
        obj.select_set(True)
        vl.objects.active = obj
        obj.data.uv_layers.active = obj.data.uv_layers[ART_UV]
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=4,
                            use_clear=True, target="IMAGE_TEXTURES")
        obj.hide_set(hidden)
    finally:
        scene.render.engine = engine
        cyc.samples, cyc.device = keep_cycles  # never leave the user's render settings changed
        for m, n, uvn, prev in added:
            m.node_tree.nodes.remove(n)
            m.node_tree.nodes.remove(uvn)
            if prev is not None and prev.name in m.node_tree.nodes:
                m.node_tree.nodes.active = prev
        obj.select_set(False)
        for o in prev_sel:
            o.select_set(True)
        vl.objects.active = prev_active
        if prev_uv is not None:
            obj.data.uv_layers.active = prev_uv
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
    obj = bpy.data.objects.get(SKETCH)
    if obj is None or obj.type != "GREASEPENCIL":
        gp = bpy.data.grease_pencils.new(SKETCH)
        obj = bpy.data.objects.new(SKETCH, gp)
        from .build import _collection
        _collection(scene).objects.link(obj)
    if not obj.data.materials:
        obj.data.materials.append(ink_material())
    return obj


def sketch_layer(scene, panel):
    """Layer for one panel, parented to its bone (strokes are stored in the
    bone's space so they move with the panel)."""
    st = scene.popup
    obj = ensure_sketch(scene)
    gp = obj.data
    layer = gp.layers.get(panel) if hasattr(gp.layers, "get") else None
    if layer is None:
        layer = next((l for l in gp.layers if l.name == panel), None)
    if layer is None:
        layer = gp.layers.new(panel)
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
    obj = bpy.data.objects.get(SKETCH)
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
