"""Images placed on pieces, front or back, adjusted like a UV transform.

Each placement puts one image on one piece (or the card), on its printed
front or its back, fitted to the piece's face and then moved, scaled and
turned with sliders. Nothing is painted into the art: the placement lives
in the paper material as a few nodes (it shows at once, folded or flat, and
while painting), and the export places the original image at full
resolution, clipped to its piece. Back images print on the reverse sheet.

With Cut Where Transparent, the image's see-through parts are cut out of
the paper, through the same tracing as painted holes (Cut Painted Areas).

Geometry: a placement maps the image square (s, t in 0..1, t up) onto the
piece's flat pattern (mm):  q = c + R(rot) . X . ((s - 1/2) w, (t - 1/2) h)
with c the face's centre plus the offset, w x h the fitted size times the
scale, and X a left-right mirror for the back (seen from behind, the image
reads the right way round)."""
import math
import os
import tempfile

import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty, StringProperty)

from . import live
from .naming import N

PREFIX = "PopImg"


# ------------------------------------------------------------------ data
def _changed(self, context):
    sc = self.id_data
    sync(sc)
    if self.cut:
        schedule_cut(sc)


def _cut_changed(self, context):
    sc = self.id_data
    sync(sc)
    schedule_cut(sc)


class PopupImage(bpy.types.PropertyGroup):
    uid: IntProperty()
    on: BoolProperty(name="Show", default=True, update=_cut_changed)
    image: PointerProperty(type=bpy.types.Image, name="Image", update=_changed)
    piece: StringProperty(name="Piece", update=_cut_changed,
                          description="The piece the image goes on (Card: the background)")
    side: EnumProperty(name="Side", update=_changed, items=[
        ("FRONT", "Front", "The printed side"),
        ("BACK", "Back", "The back: prints on the reverse sheet (print double-sided)")])
    fit: EnumProperty(name="Fit", update=_changed, items=[
        ("FIT", "Fit", "The whole image inside the piece's face"),
        ("FILL", "Fill", "Cover the piece's face (the image's edges may be cut off)"),
        ("STRETCH", "Stretch", "Stretch to the piece's face"),
        ("WRAP", "Wrap Around", "Round all the walls of a cube or tube, back ones included "
         "(on other pieces, across the whole face); Repeat puts a copy on each wall")])
    repeat: IntProperty(name="Repeat", default=1, min=1, max=16, update=_changed,
                        description="Copies side by side across the area it fits (4 on a "
                        "square cube's walls: one on each)")
    scale: FloatProperty(name="Scale", default=1.0, min=0.01, soft_max=5.0, update=_changed)
    offset_x: FloatProperty(name="Move X", default=0.0, soft_min=-200, soft_max=200,
                            description="mm across the piece", update=_changed)
    offset_y: FloatProperty(name="Move Y", default=0.0, soft_min=-200, soft_max=200,
                            description="mm up the piece", update=_changed)
    rotation: FloatProperty(name="Turn", default=0.0, subtype="ANGLE", update=_changed)
    opacity: FloatProperty(name="Opacity", default=1.0, min=0.0, max=1.0, subtype="FACTOR",
                           update=_changed)
    metallic: FloatProperty(name="Metallic", default=0.0, min=0.0, max=1.0, subtype="FACTOR",
                            update=_changed,
                            description="Make the image shine like metal foil in renders "
                            "(gold or silver lettering): only where the image is, the paper "
                            "round it stays matt. Prints are unchanged")
    cut: BoolProperty(name="Cut Where Transparent", default=False, update=_cut_changed,
                      description="Cut the image's see-through parts out of the paper "
                      "(holes inside, or a new outline where it reaches the edge), as painted "
                      "holes are")


# ------------------------------------------------------------- geometry
def piece_bounds(meta, piece):
    info = meta["pieces"].get(piece)
    if info is None:
        return None
    b = info.get("bounds")
    if b is None:  # an older build: the art tile
        if info["is_card"]:
            return [-meta["W"], 0.0, meta["W"], meta["H"]]
        from .build import TILE_MM
        ax, ay = info["anchor"]
        return [ax - TILE_MM / 4, ay - TILE_MM / 4, ax + TILE_MM / 4, ay + TILE_MM / 4]
    return b


def placement(pl, meta):
    """(L, c): image square -> piece pattern mm, q = c + L . (s - 1/2, t - 1/2)
    with L a 2x2 matrix (rows), or None."""
    b = piece_bounds(meta, pl.piece)
    img = pl.image
    if b is None or img is None:
        return None
    if pl.fit == "WRAP":
        b = meta["pieces"][pl.piece].get("wrap") or b  # the walls, round
    bw, bh = max(b[2] - b[0], 1e-3), max(b[3] - b[1], 1e-3)
    iw, ih = img.size if img.size[0] and img.size[1] else (1, 1)
    ia = iw * max(1, pl.repeat) / ih  # the copies side by side, as one picture
    if pl.fit in ("STRETCH", "WRAP"):
        w, h = bw, bh
    elif pl.fit == "FILL":
        w, h = (bw, bw / ia) if bw / bh > ia else (bh * ia, bh)
    else:
        w, h = (bh * ia, bh) if bw / bh > ia else (bw, bw / ia)
    w, h = w * pl.scale, h * pl.scale
    cx = 0.5 * (b[0] + b[2]) + pl.offset_x
    cy = 0.5 * (b[1] + b[3]) + pl.offset_y
    co, si = math.cos(pl.rotation), math.sin(pl.rotation)
    mx = -1.0 if pl.side == "BACK" else 1.0
    # R . X . diag(w, h)
    L = ((co * mx * w, -si * h), (si * mx * w, co * h))
    return L, (cx, cy)


def inverse(L, c):
    """q -> (s, t): s, t = M . (q - c) + 1/2."""
    a, b = L[0]
    cc, d = L[1]
    det = a * d - b * cc
    if abs(det) < 1e-12:
        return None
    M = ((d / det, -b / det), (-cc / det, a / det))
    return M


def uv_to_pattern(meta, piece):
    """UV (u, v) on the piece's tile -> pattern mm: q = (ax_u u + bx, ay_v v + by)."""
    from .build import TILE_MM
    info = meta["pieces"][piece]
    k = info["slot"]
    tu, tv = k % 10, k // 10
    if info["is_card"]:
        W, H = meta["W"], meta["H"]
        return (2 * W, -tu * 2 * W - W), (H, -tv * H), (tu, tv)
    ax, ay = info["anchor"]
    return (TILE_MM, ax - (tu + 0.5) * TILE_MM), (TILE_MM, ay - (tv + 0.5) * TILE_MM), (tu, tv)


def uv_affine(pl, meta):
    """(s, t) as affine functions of (u, v): ((su, sv, s0), (tu, tv, t0))."""
    P = placement(pl, meta)
    if P is None:
        return None
    L, c = P
    M = inverse(L, c)
    if M is None:
        return None
    (kx, bx), (ky, by), _ = uv_to_pattern(meta, pl.piece)
    # q = (kx u + bx, ky v + by); s = M00 (qx - cx) + M01 (qy - cy) + 1/2
    rows = []
    for r in M:
        rows.append((r[0] * kx, r[1] * ky, r[0] * (bx - c[0]) + r[1] * (by - c[1]) + 0.5))
    return rows


# ------------------------------------------------------------- material
def _paper(scene):
    mat = bpy.data.materials.get(N(scene, "Pop-up Paper"))
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return None
    return mat


def _base_source(nt, bsdf):
    """What fed Base Color before any images: followed back through the
    image mixes to the art's front/back mix, your own nodes, or a colour
    node standing in for a plain value."""
    inp = bsdf.inputs["Base Color"]
    sock = inp.links[0].from_socket if inp.is_linked else None
    seen = 0
    while sock is not None and sock.node.name.startswith(PREFIX + ".") and seen < 999:
        n = sock.node
        if n.type == "MIX" and n.inputs["A"].is_linked:
            sock = n.inputs["A"].links[0].from_socket
        elif n.name == f"{PREFIX}.source":
            return sock
        else:
            sock = None
        seen += 1
    if sock is not None:
        return sock
    rgb = nt.nodes.get(f"{PREFIX}.source")
    if rgb is None:
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.name = rgb.label = f"{PREFIX}.source"
        rgb.outputs[0].default_value = tuple(inp.default_value)
        rgb.location = bsdf.location.x - 900, bsdf.location.y + 300
    return rgb.outputs[0]


def _clear(nt, keep=None):
    for n in [n for n in nt.nodes if n.name.startswith(PREFIX + ".") and n != keep]:
        nt.nodes.remove(n)


SHINE = ("Metallic", "Roughness")  # BSDF inputs the metallic images drive


def _shine(nt, bsdf, metal):
    """Metallic images: Metallic up to 1 and Roughness down to a polish
    where they are (metal: their coverage, or None to let go)."""
    for name in SHINE:
        inp = bsdf.inputs.get(name)
        if inp is None:
            continue
        for ln in list(inp.links):
            if ln.from_node.name.startswith(PREFIX + "."):
                nt.links.remove(ln)
    if metal is None:
        return
    x, y = bsdf.location.x - 260, bsdf.location.y - 300
    mx = nt.nodes.new("ShaderNodeMath")
    mx.name = f"{PREFIX}.metallic"
    mx.operation = "MAXIMUM"
    mx.location = x, y
    nt.links.new(metal, mx.inputs[0])
    mx.inputs[1].default_value = bsdf.inputs["Metallic"].default_value
    nt.links.new(mx.outputs[0], bsdf.inputs["Metallic"])
    rough = bsdf.inputs.get("Roughness")
    if rough is not None and not rough.is_linked:
        mr = nt.nodes.new("ShaderNodeMix")
        mr.name = f"{PREFIX}.roughness"
        mr.data_type = "FLOAT"
        mr.location = x, y - 180
        nt.links.new(metal, mr.inputs["Factor"])
        mr.inputs["A"].default_value = rough.default_value
        mr.inputs["B"].default_value = 0.35  # polished, but catching broad light
        nt.links.new(mr.outputs["Result"], rough)


def sync(scene):
    """Put every placement in the paper material (rebuilding the nodes only
    when the list changes; sliders just change values)."""
    st = scene.popup
    meta = live.meta(st.rig)
    mat = _paper(scene)
    if mat is None or meta is None:
        return
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return
    want = [pl for pl in st.images if pl.image is not None and pl.piece in meta["pieces"]]
    sig = "v3;" + ";".join(f"{pl.uid}:{pl.image.name}:{pl.piece}:{pl.side}:{pl.metallic > 0}"
                           for pl in want)
    if nt.get("pop_images") != sig:
        _rebuild_nodes(scene, mat, bsdf, want, meta)
        nt["pop_images"] = sig
    for pl in want:
        _set_values(nt, pl, meta)


def _rebuild_nodes(scene, mat, bsdf, want, meta):
    from .build import ART_UV
    nt = mat.node_tree
    src = _base_source(nt, bsdf)
    _clear(nt, keep=src.node)
    _shine(nt, bsdf, None)
    if not want:
        if src.node.name == f"{PREFIX}.source":  # back to the plain value
            bsdf.inputs["Base Color"].default_value = tuple(src.default_value)
            nt.nodes.remove(src.node)
        else:
            nt.links.new(src, bsdf.inputs["Base Color"])
        return
    x0, y0 = bsdf.location.x - 260, bsdf.location.y - 700
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.name = f"{PREFIX}.uv"
    uvn.uv_map = ART_UV
    uvn.location = x0 - 1500, y0
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.name = f"{PREFIX}.geo"
    geo.location = x0 - 1500, y0 - 200
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.name = f"{PREFIX}.sep"
    sep.location = x0 - 1300, y0
    nt.links.new(uvn.outputs["UV"], sep.inputs[0])
    prev = src
    metal = None
    for i, pl in enumerate(want):
        y = y0 - 260 * i
        k = f"{PREFIX}.{pl.uid}"

        def node(kind, tag, x, **kw):
            n = nt.nodes.new(kind)
            n.name = f"{k}.{tag}"
            n.location = x, y
            for a, v in kw.items():
                setattr(n, a, v)
            return n

        # s and t from (u, v): s = a u + b v + c
        dots = []
        for j, ax in enumerate("st"):
            d = node("ShaderNodeVectorMath", f"dot{ax}", x0 - 1100, operation="DOT_PRODUCT")
            d.location.y -= 120 * j
            nt.links.new(uvn.outputs["UV"], d.inputs[0])
            add = node("ShaderNodeMath", f"add{ax}", x0 - 920, operation="ADD")
            add.location.y -= 120 * j
            nt.links.new(d.outputs["Value"], add.inputs[0])
            dots.append(add)
        # copies side by side: s -> fract(s n), only where 0 <= s < 1
        rep = node("ShaderNodeMath", "rep", x0 - 840, operation="MULTIPLY")
        rep.location.y += 60
        nt.links.new(dots[0].outputs[0], rep.inputs[0])
        frc = node("ShaderNodeMath", "frac", x0 - 800, operation="FRACT")
        frc.location.y += 120
        nt.links.new(rep.outputs[0], frc.inputs[0])
        gt = node("ShaderNodeMath", "s_in0", x0 - 840, operation="GREATER_THAN")
        gt.location.y -= 420
        gt.inputs[1].default_value = -1e-6
        nt.links.new(dots[0].outputs[0], gt.inputs[0])
        lt = node("ShaderNodeMath", "s_in1", x0 - 840, operation="LESS_THAN")
        lt.location.y -= 480
        lt.inputs[1].default_value = 1.0
        nt.links.new(dots[0].outputs[0], lt.inputs[0])
        comb = node("ShaderNodeCombineXYZ", "st", x0 - 760)
        nt.links.new(frc.outputs[0], comb.inputs[0])
        nt.links.new(dots[1].outputs[0], comb.inputs[1])
        tex = node("ShaderNodeTexImage", "tex", x0 - 600, image=pl.image, extension="CLIP")
        tex.label = pl.image.name
        nt.links.new(comb.outputs[0], tex.inputs["Vector"])
        # only on its own tile (UDIM): floor(u) == tu and floor(v) == tv
        _, _, (tu, tv) = uv_to_pattern(meta, pl.piece)
        masks = []
        for j, (sock, tile) in enumerate(((0, tu), (1, tv))):
            fl = node("ShaderNodeMath", f"floor{j}", x0 - 1100, operation="FLOOR")
            fl.location.y -= 240 + 60 * j
            nt.links.new(sep.outputs[sock], fl.inputs[0])
            cm = node("ShaderNodeMath", f"tile{j}", x0 - 920, operation="COMPARE")
            cm.location.y -= 240 + 60 * j
            cm.inputs[1].default_value = float(tile)
            cm.inputs[2].default_value = 0.5
            nt.links.new(fl.outputs[0], cm.inputs[0])
            masks.append(cm)
        m0 = node("ShaderNodeMath", "mask0", x0 - 760, operation="MULTIPLY")
        m0.location.y -= 260
        nt.links.new(masks[0].outputs[0], m0.inputs[0])
        nt.links.new(masks[1].outputs[0], m0.inputs[1])
        ms = node("ShaderNodeMath", "s_in", x0 - 700, operation="MULTIPLY")
        ms.location.y -= 440
        nt.links.new(gt.outputs[0], ms.inputs[0])
        nt.links.new(lt.outputs[0], ms.inputs[1])
        m1 = node("ShaderNodeMath", "mask", x0 - 640, operation="MULTIPLY")
        m1.location.y -= 300
        nt.links.new(m0.outputs[0], m1.inputs[0])
        nt.links.new(ms.outputs[0], m1.inputs[1])
        # front or back
        side = node("ShaderNodeMath", "side", x0 - 600, operation="SUBTRACT"
                    if pl.side == "FRONT" else "ADD")
        side.location.y -= 260
        side.inputs[0].default_value = 1.0 if pl.side == "FRONT" else 0.0
        if pl.side == "FRONT":
            nt.links.new(geo.outputs["Backfacing"], side.inputs[1])
        else:
            nt.links.new(geo.outputs["Backfacing"], side.inputs[0])
            side.inputs[1].default_value = 0.0
        f1 = node("ShaderNodeMath", "f1", x0 - 420, operation="MULTIPLY")
        f1.location.y -= 200
        nt.links.new(tex.outputs["Alpha"], f1.inputs[0])
        nt.links.new(m1.outputs[0], f1.inputs[1])
        f2 = node("ShaderNodeMath", "f2", x0 - 300, operation="MULTIPLY")
        f2.location.y -= 200
        nt.links.new(f1.outputs[0], f2.inputs[0])
        nt.links.new(side.outputs[0], f2.inputs[1])
        op = node("ShaderNodeMath", "opacity", x0 - 180, operation="MULTIPLY")
        op.location.y -= 200
        nt.links.new(f2.outputs[0], op.inputs[0])
        mix = node("ShaderNodeMix", "mix", x0 - 40, data_type="RGBA")
        nt.links.new(op.outputs[0], mix.inputs["Factor"])
        nt.links.new(prev, mix.inputs["A"])
        nt.links.new(tex.outputs["Color"], mix.inputs["B"])
        prev = mix.outputs["Result"]
        if pl.metallic > 0:
            # metallic: as much as the image covers there, times its Metallic
            mt = node("ShaderNodeMath", "metal", x0 - 40, operation="MULTIPLY")
            mt.location.y -= 200
            nt.links.new(op.outputs[0], mt.inputs[0])
            mt.inputs[1].default_value = pl.metallic
            if metal is None:
                metal = mt.outputs[0]
            else:
                both = node("ShaderNodeMath", "metal_max", x0 + 60, operation="MAXIMUM")
                both.location.y -= 200
                nt.links.new(metal, both.inputs[0])
                nt.links.new(mt.outputs[0], both.inputs[1])
                metal = both.outputs[0]
    nt.links.new(prev, bsdf.inputs["Base Color"])
    _shine(nt, bsdf, metal)


def _set_values(nt, pl, meta):
    k = f"{PREFIX}.{pl.uid}"
    rows = uv_affine(pl, meta)
    if rows is None:
        return
    for ax, r in zip("st", rows):
        d, a = nt.nodes.get(f"{k}.dot{ax}"), nt.nodes.get(f"{k}.add{ax}")
        if d is None or a is None:
            return
        d.inputs[1].default_value = (r[0], r[1], 0.0)
        a.inputs[1].default_value = r[2]
    op = nt.nodes.get(f"{k}.opacity")
    if op is not None:
        op.inputs[1].default_value = pl.opacity if pl.on else 0.0
    mt = nt.nodes.get(f"{k}.metal")
    if mt is not None:
        mt.inputs[1].default_value = pl.metallic
    rp = nt.nodes.get(f"{k}.rep")
    if rp is not None:
        rp.inputs[1].default_value = float(max(1, pl.repeat))


def mute_in(mat):
    """For a bake: leave the placements out of a material copy (the export
    places them at full resolution over the baked art)."""
    if mat is None or mat.node_tree is None:
        return
    for n in mat.node_tree.nodes:
        if n.name.startswith(PREFIX + ".") and n.name.endswith(".opacity"):
            n.inputs[1].default_value = 0.0


# ------------------------------------------------------------- export
def png_data(img, tmp):
    """The image's pixels as a PNG file (works for packed and generated
    images alike); returns (path, width, height) or None."""
    import base64  # noqa: F401  (callers encode)
    w, h = img.size
    if not w or not h:
        return None
    try:
        import numpy as np
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
    except Exception:
        px = list(img.pixels[:])
    out = bpy.data.images.new("_pop_place_png", w, h, alpha=True)
    try:
        try:
            out.colorspace_settings.name = img.colorspace_settings.name
        except TypeError:
            pass
        out.pixels.foreach_set(px)
        path = os.path.join(tmp, f"place_{abs(hash(img.name))}.png")
        out.filepath_raw = path
        out.file_format = "PNG"
        out.save()
    finally:
        bpy.data.images.remove(out)
    return path, w, h


def svg_matrix(pl, meta, k=0):
    """Affine (a, b, c, d, e, f) from an SVG <image width=1 height=1> (y down)
    to the piece's pattern mm: copy k of Repeat."""
    P = placement(pl, meta)
    if P is None:
        return None
    L, c = P
    n = max(1, pl.repeat)
    # pattern = c + L . (s - 1/2, 1/2 - y), s = (x + k) / n
    a, b = L[0][0] / n, L[1][0] / n
    cc, d = -L[0][1], -L[1][1]
    e = c[0] + L[0][0] * (k / n - 0.5) + 0.5 * L[0][1]
    f = c[1] + L[1][0] * (k / n - 0.5) + 0.5 * L[1][1]
    return a, b, cc, d, e, f


def for_piece(scene, piece, side):
    st = scene.popup
    return [pl for pl in st.images if pl.on and pl.image is not None and pl.piece == piece
            and pl.side == side and pl.opacity > 0.0]


# --------------------------------------------------------------- cuts
def cut_mask(scene, meta, piece, xs, ys, threshold=0.5):
    """Holes from placements with Cut Where Transparent on this piece, on a
    grid of pattern points (xs: columns, ys: rows): a boolean array
    [rows, cols], or None."""
    import numpy as np
    pls = [pl for pl in scene.popup.images if pl.on and pl.cut and pl.image is not None
           and pl.piece == piece]
    if not pls:
        return None
    X, Y = np.meshgrid(np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64))
    hole = np.zeros(X.shape, dtype=bool)
    for pl in pls:
        P = placement(pl, meta)
        if P is None:
            continue
        L, c = P
        M = inverse(L, c)
        if M is None:
            continue
        s = M[0][0] * (X - c[0]) + M[0][1] * (Y - c[1]) + 0.5
        t = M[1][0] * (X - c[0]) + M[1][1] * (Y - c[1]) + 0.5
        inside = (s >= 0) & (s < 1) & (t >= 0) & (t < 1)
        s = np.mod(s * max(1, pl.repeat), 1.0)  # copies side by side
        w, h = pl.image.size
        if not w or not h:
            continue
        px = np.empty(w * h * 4, dtype=np.float32)
        pl.image.pixels.foreach_get(px)
        alpha = px[3::4].reshape(h, w)
        ci = np.clip((s * w).astype(int), 0, w - 1)
        ri = np.clip((t * h).astype(int), 0, h - 1)
        hole |= inside & (alpha[ri, ci] < threshold)
    return hole


def has_cuts(scene):
    return any(pl.on and pl.cut and pl.image is not None for pl in scene.popup.images)


_pending = set()


def schedule_cut(scene):
    """Re-trace the cuts a moment after the last change (not on every drag
    step: a cut rebuilds the card)."""
    name = scene.name
    if name in _pending:
        return
    _pending.add(name)

    def run():
        try:
            if bpy.context.mode == "PAINT_TEXTURE":
                return 0.5  # not under the brush: once painting stops
        except AttributeError:
            pass
        _pending.discard(name)
        sc = bpy.data.scenes.get(name)
        if sc is not None and sc.popup.rig is not None:
            from . import holes
            try:
                holes.cut_painted(sc, force=True)
            except Exception as ex:
                sc.popup.status = f"Cutting image shapes failed: {ex}"
        return None
    bpy.app.timers.register(run, first_interval=0.6)


# ------------------------------------------------------------ operators
def piece_items(scene):
    meta = live.meta(scene.popup.rig)
    if meta is None:
        return []
    items = sorted(meta["pieces"].items(), key=lambda kv: (not kv[1]["is_card"], kv[1]["slot"]))
    return [(k, v["label"], "") for k, v in items]


_items = []


def _piece_enum(self, context):
    global _items
    _items = piece_items(context.scene) or [("Card", "Card", "")]
    return _items


def active_piece(scene):
    """The piece of the selected mechanism, else the card."""
    import re
    st = scene.popup
    meta = live.meta(st.rig)
    if meta is None:
        return "Card"
    if st.mechs and 0 <= st.active < len(st.mechs):
        uid = st.mechs[st.active].uid
        for p in meta["panels"]:
            m = re.match(r"^[A-Za-z]+?(\d+)[.a-z]", p["name"])
            if m and int(m.group(1)) == uid and p["kind"] != "tab":
                return p["piece"]
    return next((k for k, v in meta["pieces"].items() if v["is_card"]), "Card")


class POPUP_OT_add_image(bpy.types.Operator):
    """Put an image on a piece (front or back), fitted to it; move, scale and
    turn it after with the sliders. Images with transparency can cut the
    paper to their shape"""
    bl_idname = "popup.add_image"
    bl_label = "Add Image to a Piece"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")
    filter_image: BoolProperty(default=True, options={"HIDDEN"})
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})
    piece: EnumProperty(name="Piece", items=_piece_enum)
    side: EnumProperty(name="Side", items=[
        ("FRONT", "Front", "The printed side (on the card: inside, the scene)"),
        ("BACK", "Back", "The back (on the card: the outside cover)")])
    cut: BoolProperty(name="Cut Where Transparent", default=False)
    to_card: BoolProperty(name="On the Card", default=False, options={"SKIP_SAVE"},
                          description="Put it on the card itself (the background, or with "
                          "Back the outside cover)")

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def invoke(self, context, event):
        try:
            if self.to_card:
                meta = live.meta(context.scene.popup.rig)
                self.piece = next((k for k, v in meta["pieces"].items() if v["is_card"]),
                                  "Card")
            else:
                self.piece = active_piece(context.scene)
        except (TypeError, KeyError):
            pass
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        sc = context.scene
        st = sc.popup
        try:
            img = bpy.data.images.load(bpy.path.abspath(self.filepath), check_existing=True)
        except RuntimeError as ex:
            self.report({"ERROR"}, f"Can't open the image: {ex}")
            return {"CANCELLED"}
        try:
            img.pack()  # the .blend carries it
        except RuntimeError:
            pass
        add(sc, img, self.piece, self.side, self.cut)
        return {"FINISHED"}


def add(scene, img, piece, side="FRONT", cut=False):
    st = scene.popup
    uid = max([p.uid for p in st.images] + [0]) + 1
    pl = st.images.add()
    pl["uid"] = uid
    pl["piece"] = piece
    pl["side"] = 0 if side == "FRONT" else 1
    pl["cut"] = cut
    meta = live.meta(st.rig)
    if meta and (meta["pieces"].get(piece) or {}).get("wrap"):
        pl["fit"] = 3  # round a cube's or tube's walls
    pl.image = img  # triggers the sync
    st.active_image = len(st.images) - 1
    sync(scene)
    if cut:
        schedule_cut(scene)
    return pl


class POPUP_OT_remove_image(bpy.types.Operator):
    """Take the selected image off its piece"""
    bl_idname = "popup.remove_image"
    bl_label = "Remove Image"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return 0 <= st.active_image < len(st.images)

    def execute(self, context):
        sc = context.scene
        st = sc.popup
        had_cut = st.images[st.active_image].cut
        st.images.remove(st.active_image)
        st.active_image = max(0, min(st.active_image, len(st.images) - 1))
        sync(sc)
        if had_cut:
            schedule_cut(sc)
        return {"FINISHED"}


class POPUP_OT_image_piece(bpy.types.Operator):
    """Move the selected image to another piece"""
    bl_idname = "popup.image_piece"
    bl_label = "Choose Piece"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "piece"
    piece: EnumProperty(name="Piece", items=_piece_enum)

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return 0 <= st.active_image < len(st.images)

    def execute(self, context):
        st = context.scene.popup
        st.images[st.active_image].piece = self.piece
        return {"FINISHED"}


class POPUP_UL_images(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        meta = live.meta(context.scene.popup.rig) or {"pieces": {}}
        label = meta["pieces"].get(item.piece, {}).get("label", item.piece or "?")
        row = layout.row(align=True)
        row.prop(item, "on", text="", emboss=False,
                 icon="HIDE_OFF" if item.on else "HIDE_ON")
        row.label(text=f"{item.image.name if item.image else '(no image)'} → {label}",
                  icon="IMAGE_DATA")
        row.label(text="back" if item.side == "BACK" else "")
        if item.cut:
            row.label(text="", icon="MOD_BOOLEAN")


def draw(layout, context):
    st = context.scene.popup
    col = layout.column(align=True)
    col.label(text="Images on pieces")
    row = col.row()
    row.template_list("POPUP_UL_images", "", st, "images", st, "active_image", rows=2)
    c = row.column(align=True)
    c.operator("popup.add_image", text="", icon="ADD").to_card = False
    c.operator("popup.remove_image", text="", icon="REMOVE")
    r = col.row(align=True)
    r.operator("popup.add_image", text="Image on a Piece", icon="IMAGE_DATA").to_card = False
    r.operator("popup.add_image", text="Image on the Card", icon="FILE_IMAGE").to_card = True
    if 0 <= st.active_image < len(st.images):
        pl = st.images[st.active_image]
        meta = live.meta(st.rig) or {"pieces": {}}
        box = layout.box()
        c = box.column()
        c.use_property_split = True
        c.use_property_decorate = False
        c.template_ID(pl, "image", open="image.open")
        row = c.row(align=True)
        row.label(text="Piece: " + meta["pieces"].get(pl.piece, {}).get("label", pl.piece))
        row.operator_menu_enum("popup.image_piece", "piece", text="", icon="DOWNARROW_HLT")
        c.prop(pl, "side", expand=True)
        c.prop(pl, "fit")
        c.prop(pl, "repeat")
        c.prop(pl, "scale")
        c.prop(pl, "offset_x")
        c.prop(pl, "offset_y")
        c.prop(pl, "rotation")
        c.prop(pl, "opacity")
        c.prop(pl, "metallic")
        c.prop(pl, "cut")


classes = (PopupImage, POPUP_OT_add_image, POPUP_OT_remove_image, POPUP_OT_image_piece,
           POPUP_UL_images)


def register_props():
    bpy.utils.register_class(PopupImage)


def register():
    for c in classes[1:]:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes[1:]):
        bpy.utils.unregister_class(c)


def unregister_props():
    bpy.utils.unregister_class(PopupImage)
